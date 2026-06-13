"""Small 2006Scape game-login protocol probe shared by deployment checks."""

import random
import socket
import ssl
import time


CLIENT_RSA_EXPONENT = 65537
RSA_MODULUS = int(
    "91553247461173033466542043374346300088148707506479543786501537350363031301992107112953015516557748875487935404852620239974482067336878286174236183516364787082711186740254168914127361643305190640280157664988536979163450791820893999053469529344247707567448479470137716627440246788713008490213212272520901741443"
)

LOGIN_STATUS = {
    0: "exchange_data",
    1: "delay",
    2: "ok",
    3: "invalid_credentials",
    4: "account_disabled_or_invalid",
    5: "account_online",
    6: "game_updated",
    7: "server_full",
    8: "login_server_offline",
    9: "too_many_connections",
    10: "bad_session_id",
    11: "login_server_rejected_session",
    12: "members_account_required",
    13: "could_not_complete",
    14: "server_updating",
    15: "reconnection_ok",
    16: "too_many_logins",
    17: "in_members_area",
    20: "invalid_login_server",
    21: "profile_transfer",
}
TLS_MINIMUM_VERSION = getattr(getattr(ssl, "TLSVersion", object), "TLSv1_2", None)


class LoginProbeError(RuntimeError):
    pass


def create_tls_client_context(allow_untrusted_tls=False):
    context = ssl._create_unverified_context() if allow_untrusted_tls else ssl.create_default_context()
    if TLS_MINIMUM_VERSION is not None and hasattr(context, "minimum_version"):
        context.minimum_version = TLS_MINIMUM_VERSION
    else:
        # Python builds without SSLContext.minimum_version are old; disable legacy versions when possible.
        for option in ("OP_NO_SSLv2", "OP_NO_SSLv3", "OP_NO_TLSv1", "OP_NO_TLSv1_1"):
            if hasattr(ssl, option):
                context.options |= getattr(ssl, option)
    return context


def read_exact(sock, length):
    chunks = []
    remaining = length
    while remaining > 0:
        data = sock.recv(remaining)
        if not data:
            raise LoginProbeError("socket closed while reading {} bytes".format(length))
        chunks.append(data)
        remaining -= len(data)
    return b"".join(chunks)


def write_short(value):
    return int(value & 0xFFFF).to_bytes(2, "big")


def write_int(value):
    return int(value & 0xFFFFFFFF).to_bytes(4, "big")


def write_long(value):
    return int(value & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "big")


def write_string(value):
    return (value or "").encode("latin-1") + b"\n"


def java_positive_bigint_bytes(value):
    length = max(1, (value.bit_length() + 7) // 8)
    data = value.to_bytes(length, "big")
    if data[0] & 0x80:
        data = b"\x00" + data
    return data


def login_payload(username, password, server_seed):
    client_seed = random.getrandbits(64)
    secure = bytearray()
    secure.append(10)
    secure += write_long(client_seed)
    secure += write_long(server_seed)
    secure += write_int(0)
    secure += write_string(username)
    secure += write_string(password)
    encrypted = java_positive_bigint_bytes(pow(int.from_bytes(secure, "big"), CLIENT_RSA_EXPONENT, RSA_MODULUS))

    payload = bytearray()
    payload.append(255)
    payload += write_short(1)
    payload.append(0)
    for _ in range(9):
        payload += write_int(0)
    payload.append(len(encrypted))
    payload += encrypted
    return bytes([16, len(payload)]) + payload


def open_socket(host, port, timeout, use_tls=False, tls_sni_host="", allow_untrusted_tls=False):
    raw = socket.create_connection((host, port), timeout=timeout)
    raw.settimeout(timeout)
    if not use_tls:
        return raw
    try:
        context = create_tls_client_context(allow_untrusted_tls)
        return context.wrap_socket(raw, server_hostname=tls_sni_host or host)
    except Exception:
        raw.close()
        raise


def login_socket(host, port, username, password, timeout=4.0, use_tls=False,
        tls_sni_host="", allow_untrusted_tls=False):
    sock = open_socket(host, port, timeout, use_tls=use_tls, tls_sni_host=tls_sni_host,
            allow_untrusted_tls=allow_untrusted_tls)
    try:
        sock.sendall(bytes([14, 0]))
        exchange = read_exact(sock, 17)
        if exchange[0] != 0:
            raise LoginProbeError("{} exchange status was {}".format(username, exchange[0]))
        server_seed = int.from_bytes(exchange[9:17], "big")
        sock.sendall(login_payload(username, password, server_seed))
        status = read_exact(sock, 1)[0]
        result = {
            "username": username,
            "host": host,
            "port": int(port),
            "status": status,
            "statusName": LOGIN_STATUS.get(status, "unknown"),
            "tls": bool(use_tls),
        }
        if status == 2:
            rights_flagged = read_exact(sock, 2)
            result["rights"] = rights_flagged[0]
            result["flagged"] = bool(rights_flagged[1])
            return sock, result
        sock.close()
        return None, result
    except Exception:
        try:
            sock.close()
        except OSError:
            pass
        raise


def probe_login(host, port, username, password, timeout=4.0, use_tls=False,
        tls_sni_host="", allow_untrusted_tls=False, hold_seconds=0.0):
    sock, result = login_socket(host, port, username, password, timeout=timeout,
            use_tls=use_tls, tls_sni_host=tls_sni_host,
            allow_untrusted_tls=allow_untrusted_tls)
    try:
        if sock is not None and hold_seconds > 0:
            time.sleep(hold_seconds)
        return result
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
