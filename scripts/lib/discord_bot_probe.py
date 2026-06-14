"""Helpers for proving configured 2006Scape agent Discord bots are usable."""

import datetime as dt
import json
import os
import stat
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DISCORD_API_BASE = "https://discord.com/api/v10"
PLACEHOLDER_DISCORD_VALUES = {
    "REPLACE_WITH_DISCORD_BOT_TOKEN",
    "DISCORD_BOT_TOKEN",
    "123456789012345678",
}


class DiscordProbeError(RuntimeError):
    pass


def canonical(value):
    return "" if value is None else str(value).strip().lower()


def load_json(path):
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except OSError as exc:
        raise DiscordProbeError("could not read {}: {}".format(path, exc))
    except json.JSONDecodeError as exc:
        raise DiscordProbeError("invalid JSON in {}: {}".format(path, exc))


def ensure_real_secret_path(path, allow_placeholders=False):
    path = Path(path)
    if allow_placeholders:
        return
    if path.is_symlink():
        raise DiscordProbeError("Discord secrets must not be a symlink: {}".format(path))
    if os.name == "posix":
        try:
            mode = path.stat().st_mode
        except OSError as exc:
            raise DiscordProbeError("could not stat Discord secrets {}: {}".format(path, exc))
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise DiscordProbeError("Discord secrets permissions must be owner-only: {}".format(path))


def string_value(mapping, keys, index, required=False):
    for key in keys:
        if key in mapping:
            value = mapping.get(key)
            if not isinstance(value, str):
                raise DiscordProbeError("agent-discord-bots[{}].{} must be a string".format(index, key))
            clean = value.strip()
            if required and not clean:
                raise DiscordProbeError("agent-discord-bots[{}].{} must not be empty".format(index, key))
            return clean
    if required:
        raise DiscordProbeError("agent-discord-bots[{}] needs {}".format(index, "/".join(keys)))
    return ""


def is_placeholder(value):
    clean = str(value or "").strip()
    return clean in PLACEHOLDER_DISCORD_VALUES or clean.upper().startswith("REPLACE_WITH_")


def reject_placeholder(value, index, label, allow_placeholders):
    if value and not allow_placeholders and is_placeholder(value):
        raise DiscordProbeError("agent-discord-bots[{}].{} still contains a placeholder value".format(index, label))


def load_bot_configs(secrets_path, allow_placeholders=False, agents=None):
    ensure_real_secret_path(secrets_path, allow_placeholders=allow_placeholders)
    secrets = load_json(secrets_path)
    bots = secrets.get("agent-discord-bots", [])
    if not isinstance(bots, list) or not bots:
        raise DiscordProbeError("no agent-discord-bots are configured in {}".format(secrets_path))
    wanted = set(canonical(agent) for agent in (agents or []) if canonical(agent))
    configs = []
    seen = set()
    for index, bot in enumerate(bots):
        if not isinstance(bot, dict):
            raise DiscordProbeError("agent-discord-bots[{}] must be an object".format(index))
        agent = string_value(bot, ("agent", "profile", "name"), index, required=True)
        agent_key = canonical(agent)
        if wanted and agent_key not in wanted:
            continue
        if agent_key in seen:
            raise DiscordProbeError("duplicate Discord bot config for agent/profile: {}".format(agent))
        token = string_value(bot, ("token",), index, required=True)
        channel_id = string_value(bot, ("channelId", "channel_id"), index)
        channel_name = string_value(bot, ("channelName", "channel_name"), index)
        reject_placeholder(token, index, "token", allow_placeholders)
        reject_placeholder(channel_id, index, "channelId/channel_id", allow_placeholders)
        reject_placeholder(channel_name, index, "channelName/channel_name", allow_placeholders)
        if not channel_id and not channel_name:
            raise DiscordProbeError("agent-discord-bots[{}] needs channelId/channelName".format(index))
        configs.append({
            "index": index,
            "agent": agent,
            "agentKey": agent_key,
            "token": token,
            "channelId": channel_id,
            "channelName": channel_name,
        })
        seen.add(agent_key)
    if wanted and not configs:
        raise DiscordProbeError("no configured Discord bots matched requested agents: {}".format(
            ", ".join(sorted(wanted))))
    return configs


def discord_api_request(token, method, path, timeout=4.0, payload=None):
    body = None
    headers = {
        "Authorization": "Bot {}".format(token),
        "Accept": "application/json",
        "User-Agent": "2006Scape-Discord-Probe/1.0",
    }
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        DISCORD_API_BASE + path,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise DiscordProbeError("Discord API HTTP {} for {} {}: {}".format(
            exc.code, method, path, detail[:300]))
    except urllib.error.URLError as exc:
        raise DiscordProbeError("Discord API request failed for {} {}: {}".format(method, path, exc.reason))
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiscordProbeError("Discord API returned invalid JSON for {} {}: {}".format(method, path, exc))


def escape_discord_mentions(value):
    return "" if value is None else str(value).replace("@", "@\u200B")


def default_probe_message(agent):
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return "2006Scape Discord probe for {} at {}".format(agent, timestamp)


def probe_bot(config, timeout=4.0, send_test_message=False, message=""):
    user = discord_api_request(config["token"], "GET", "/users/@me", timeout=timeout)
    if not isinstance(user, dict) or not user.get("id"):
        raise DiscordProbeError("Discord bot token for {} did not return a user id".format(config["agent"]))
    if user.get("bot") is False:
        raise DiscordProbeError("Discord token for {} is not a bot user token".format(config["agent"]))
    result = {
        "agent": config["agent"],
        "botUserId": str(user.get("id")),
        "botUsername": str(user.get("global_name") or user.get("username") or ""),
        "channelId": config.get("channelId", ""),
        "channelName": config.get("channelName", ""),
        "channelChecked": False,
        "messageSent": False,
    }
    channel_id = config.get("channelId", "")
    if channel_id:
        channel = discord_api_request(config["token"], "GET", "/channels/{}".format(channel_id), timeout=timeout)
        if not isinstance(channel, dict) or str(channel.get("id")) != channel_id:
            raise DiscordProbeError("Discord channel probe for {} did not return channel {}".format(
                config["agent"], channel_id))
        result["channelChecked"] = True
        result["channelType"] = channel.get("type")
        result["channelName"] = str(channel.get("name") or result["channelName"])
        if send_test_message:
            content = escape_discord_mentions(message or default_probe_message(config["agent"]))
            sent = discord_api_request(
                config["token"],
                "POST",
                "/channels/{}/messages".format(channel_id),
                timeout=timeout,
                payload={"content": content},
            )
            if not isinstance(sent, dict) or not sent.get("id"):
                raise DiscordProbeError("Discord test message for {} did not return a message id".format(
                    config["agent"]))
            result["messageSent"] = True
            result["messageId"] = str(sent.get("id"))
    elif send_test_message:
        raise DiscordProbeError("Discord test messages require channelId for {}".format(config["agent"]))
    else:
        result["warning"] = "channelName configured; REST probe cannot prove channel lookup without runtime gateway state"
    return result


def probe_discord_bots(secrets_path, timeout=4.0, agents=None, send_test_message=False, message=""):
    configs = load_bot_configs(secrets_path, allow_placeholders=False, agents=agents)
    return [
        probe_bot(config, timeout=timeout, send_test_message=send_test_message, message=message)
        for config in configs
    ]


def validate_message_limit(limit):
    try:
        clean = int(limit)
    except (TypeError, ValueError):
        raise DiscordProbeError("Discord message limit must be an integer")
    if clean < 1 or clean > 100:
        raise DiscordProbeError("Discord message limit must be between 1 and 100")
    return clean


def clip_text(value, limit=180):
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:max(0, limit - 3)] + "..."


def discord_channel_messages(config, timeout=4.0, limit=50, after_id=""):
    channel_id = config.get("channelId", "")
    if not channel_id:
        raise DiscordProbeError("Discord channel message verification requires channelId for {}".format(
            config["agent"]))
    params = {"limit": str(validate_message_limit(limit))}
    if after_id:
        params["after"] = str(after_id).strip()
    path = "/channels/{}/messages?{}".format(
        urllib.parse.quote(str(channel_id), safe=""),
        urllib.parse.urlencode(params),
    )
    messages = discord_api_request(config["token"], "GET", path, timeout=timeout)
    if not isinstance(messages, list):
        raise DiscordProbeError("Discord channel messages for {} did not return a list".format(config["agent"]))
    return messages


def message_author_id(message):
    author = message.get("author") if isinstance(message, dict) else {}
    if not isinstance(author, dict):
        return ""
    return str(author.get("id") or "")


def message_author_is_bot(message):
    author = message.get("author") if isinstance(message, dict) else {}
    return isinstance(author, dict) and bool(author.get("bot"))


def sanitize_message(message):
    author = message.get("author") if isinstance(message, dict) else {}
    if not isinstance(author, dict):
        author = {}
    return {
        "id": str(message.get("id") or ""),
        "timestamp": str(message.get("timestamp") or ""),
        "authorId": str(author.get("id") or ""),
        "authorUsername": str(author.get("global_name") or author.get("username") or ""),
        "authorBot": bool(author.get("bot")),
        "contentPreview": clip_text(message.get("content", "")),
    }


def verify_channel_message(config, text_contains, timeout=4.0, limit=50, after_id="",
        require_bot_author=True):
    marker = "" if text_contains is None else str(text_contains)
    if not marker:
        raise DiscordProbeError("Discord channel message marker must not be empty")
    bot_probe = probe_bot(config, timeout=timeout, send_test_message=False)
    messages = discord_channel_messages(config, timeout=timeout, limit=limit, after_id=after_id)
    bot_user_id = str(bot_probe.get("botUserId") or "")
    matches = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        if marker not in str(message.get("content", "")):
            continue
        if require_bot_author and message_author_id(message) != bot_user_id:
            continue
        matches.append(sanitize_message(message))
    if not matches:
        author_detail = " authored by the configured bot" if require_bot_author else ""
        raise DiscordProbeError("no Discord channel message{} matched marker for {}".format(
            author_detail, config["agent"]))
    latest = matches[0]
    return {
        "agent": config["agent"],
        "botUserId": bot_user_id,
        "botUsername": str(bot_probe.get("botUsername") or ""),
        "channelId": config.get("channelId", ""),
        "channelName": str(bot_probe.get("channelName") or config.get("channelName", "")),
        "matched": len(matches),
        "latestMessageId": latest.get("id", ""),
        "latestTimestamp": latest.get("timestamp", ""),
        "latestAuthorId": latest.get("authorId", ""),
        "latestAuthorBot": latest.get("authorBot", False),
        "latestContentPreview": latest.get("contentPreview", ""),
    }


def verify_channel_messages(secrets_path, text_contains, timeout=4.0, agents=None, limit=50,
        after_id="", require_bot_author=True, require_all=False):
    configs = load_bot_configs(secrets_path, allow_placeholders=False, agents=agents)
    results = []
    failures = []
    for config in configs:
        try:
            results.append(verify_channel_message(
                config,
                text_contains,
                timeout=timeout,
                limit=limit,
                after_id=after_id,
                require_bot_author=require_bot_author,
            ))
        except DiscordProbeError as exc:
            if require_all:
                raise
            failures.append("{}: {}".format(config["agent"], exc))
    if not results:
        detail = "; ".join(failures) if failures else "no selected Discord bots"
        raise DiscordProbeError("no selected Discord channel contained the marker: {}".format(detail))
    return results
