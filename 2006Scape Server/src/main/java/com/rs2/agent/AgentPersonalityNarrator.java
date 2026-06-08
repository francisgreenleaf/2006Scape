package com.rs2.agent;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.ConcurrentMap;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.rs2.Constants;
import com.rs2.game.players.Player;
import com.rs2.util.Misc;
import com.rs2.util.Stream;

public class AgentPersonalityNarrator {

    public static final AgentPersonalityNarrator INSTANCE = new AgentPersonalityNarrator();

    static final long LLM_COOLDOWN_MS = 10L * 60L * 1000L;
    static final long PUBLIC_CHAT_COOLDOWN_MS = 4L * 60L * 1000L;
    static final long AMBIENT_CHATTER_INTERVAL_MS = 30L * 60L * 1000L;
    static final int MAX_LLM_REQUESTS_PER_SESSION = 8;
    static final int MAX_PUBLIC_LINES_PER_SESSION = 48;
    static final int AMBIENT_EVENT_INTERVAL = 20;
    private static final int MAX_PENDING_REQUESTS = 200;

    private final ConcurrentMap<String, SessionNarrationState> sessionStates =
            new ConcurrentHashMap<String, SessionNarrationState>();
    private final ConcurrentMap<String, ProfileNarrationState> profileStates =
            new ConcurrentHashMap<String, ProfileNarrationState>();
    private final ConcurrentMap<String, PendingNarration> pendingById =
            new ConcurrentHashMap<String, PendingNarration>();
    private final ConcurrentLinkedQueue<String> pendingOrder = new ConcurrentLinkedQueue<String>();
    private volatile Long nowForTests;

    public void observe(AgentSessionLog log, AgentSession session, JsonObject entry) {
        if (log == null || session == null || entry == null) {
            return;
        }
        String event = string(entry, "event", "");
        if (event.startsWith("personality_")) {
            return;
        }
        long now = now();
        SessionNarrationState sessionState = sessionState(session);
        ProfileNarrationState profileState = profileState(session);
        sessionState.eventCount++;
        if (!sessionState.ambientClockStarted) {
            sessionState.ambientClockStarted = true;
            sessionState.lastAmbientAtMs = now;
            sessionState.lastAmbientEventCount = sessionState.eventCount;
        }
        NarrationSignal signal = classify(session, entry, sessionState, now);
        if (signal == null && shouldAmbient(sessionState, now)) {
            signal = ambientSignal(session, entry, sessionState, profileState);
        }
        if (signal == null) {
            return;
        }
        if (!rememberDedupe(sessionState, signal)) {
            if ("ambient".equals(signal.milestone) || !shouldAmbient(sessionState, now)) {
                return;
            }
            signal = ambientSignal(session, entry, sessionState, profileState);
            if (!rememberDedupe(sessionState, signal)) {
                return;
            }
        }

        String fallback = validateGeneratedText(signal.fallbackText);
        if (fallback.length() == 0) {
            return;
        }
        writeChatter(log, session, signal, fallback, "template");
        rememberSelfTalk(profileState, fallback);
        if ("ambient".equals(signal.milestone)) {
            recordAmbientFired(sessionState, now);
        }
        maybeSpeak(log, session, signal, fallback, now, sessionState, profileState);
        if (signal.highSignal && shouldQueueLlm(sessionState, profileState, now)) {
            queueLlmRequest(session, signal, now, sessionState, profileState);
        }
    }

    public JsonObject pendingForSession(AgentSession session, int limit) {
        JsonObject response = new JsonObject();
        response.addProperty("success", true);
        JsonArray requests = new JsonArray();
        if (session == null) {
            response.add("requests", requests);
            return response;
        }
        int cappedLimit = Math.max(1, Math.min(8, limit));
        for (String requestId : pendingOrder) {
            PendingNarration pending = pendingById.get(requestId);
            if (pending == null || !pending.sessionId.equals(session.getSessionId())) {
                continue;
            }
            requests.add(pending.toJson());
            if (requests.size() >= cappedLimit) {
                break;
            }
        }
        response.add("requests", requests);
        return response;
    }

    public JsonObject complete(AgentSessionLog log, AgentSession session, JsonObject request) {
        JsonObject response = new JsonObject();
        if (session == null || request == null) {
            response.addProperty("success", false);
            response.addProperty("message", "Missing personality narration session.");
            return response;
        }
        String requestId = string(request, "requestId", "");
        PendingNarration pending = requestId.length() == 0 ? null : pendingById.remove(requestId);
        if (pending == null || !pending.sessionId.equals(session.getSessionId())) {
            recordFailure(log, session, requestId, "unknown_request");
            response.addProperty("success", false);
            response.addProperty("message", "Unknown personality narration request.");
            return response;
        }
        pendingOrder.remove(requestId);
        String text = validateGeneratedText(string(request, "text", ""));
        if (text.length() == 0 || !textAllowedForSignal(text, pending.signal)) {
            recordFailure(log, session, requestId, "invalid_llm_text");
            response.addProperty("success", false);
            response.addProperty("message", "Generated personality chatter was rejected.");
            return response;
        }
        SessionNarrationState sessionState = sessionState(session);
        ProfileNarrationState profileState = profileState(session);
        writeChatter(log, session, pending.signal, text, "llm");
        rememberSelfTalk(profileState, text);
        maybeSpeak(log, session, pending.signal, text, now(), sessionState, profileState);
        response.addProperty("success", true);
        response.addProperty("accepted", true);
        return response;
    }

    public JsonObject failed(AgentSessionLog log, AgentSession session, JsonObject request) {
        JsonObject response = new JsonObject();
        if (session == null || request == null) {
            response.addProperty("success", false);
            response.addProperty("message", "Missing personality narration session.");
            return response;
        }
        String requestId = string(request, "requestId", "");
        if (requestId.length() > 0) {
            pendingById.remove(requestId);
            pendingOrder.remove(requestId);
        }
        recordFailure(log, session, requestId, compact(string(request, "reason", "llm_failed"), 80));
        response.addProperty("success", true);
        return response;
    }

    void resetForTests() {
        sessionStates.clear();
        profileStates.clear();
        pendingById.clear();
        pendingOrder.clear();
        nowForTests = null;
    }

    void setNowForTests(long now) {
        nowForTests = Long.valueOf(now);
    }

    int pendingCountForTests() {
        return pendingById.size();
    }

    static String validateGeneratedText(String text) {
        String cleaned = compact(text, 140);
        if (cleaned.length() == 0 || cleaned.length() > 140) {
            return "";
        }
        String lower = cleaned.toLowerCase(Locale.ENGLISH);
        String[] banned = {"codex", "api", "token", "secret", "password", "cookie", "json", "bridge",
                "session", "log", "tool", "rs.", "coordinate", "x=", "y=", "http", "localhost"};
        for (String word : banned) {
            if (lower.contains(word)) {
                return "";
            }
        }
        if (lower.matches(".*\\b[0-9]{4},[0-9]{4}\\b.*")) {
            return "";
        }
        return cleaned;
    }

    static JsonObject compactRequestForTests(String profile, String milestone, String place) {
        NarrationSignal signal = new NarrationSignal(milestone, true, true, place,
                "Right. Bank first, heroics later.");
        signal.facts.add("Reached " + place + ".");
        signal.moodSignals.add("practical");
        signal.styleTags.add("lumbridge-practical");
        return PendingNarration.create("test-request", "test-session", profile, signal, 0L,
                new ArrayList<String>()).toJson();
    }

    private NarrationSignal classify(AgentSession session, JsonObject entry,
            SessionNarrationState state, long now) {
        String event = string(entry, "event", "");
        JsonObject data = object(entry, "data");
        JsonObject player = object(entry, "player");
        boolean dead = bool(player, "isDead", false);
        if (dead) {
            NarrationSignal signal = signal("death_risk", true, true, entry,
                    "Next time, food first. Pride can walk behind me.");
            signal.facts.add("Death or critical risk was observed.");
            signal.moodSignals.add("rattled");
            signal.styleTags.add("cautious-traveller");
            return signal;
        }
        if ("session_claimed".equals(event)) {
            NarrationSignal signal = signal("session_start", false, false, entry,
                    "Boots on. Let's find out what the road thinks today.");
            signal.facts.add("The agent session was claimed by a local client.");
            signal.moodSignals.add("ready");
            signal.styleTags.add("quest-helper");
            return signal;
        }
        if ("turn_requested".equals(event) || "turn_started".equals(event)) {
            String command = compact(string(data, "command", ""), 90);
            if (command.length() == 0) {
                return null;
            }
            NarrationSignal signal = signal("task_start", false, false, entry,
                    "A task, then. Best make it tidy.");
            signal.facts.add("Task: " + command);
            signal.moodSignals.add("focused");
            signal.styleTags.add("quest-helper");
            return signal;
        }
        if ("session_expired".equals(event) || "session_invalidated".equals(event)) {
            String reason = compact(string(data, "reason", "session ended"), 90);
            NarrationSignal signal = signal("session_end", true, true, entry,
                    "That is enough for now. Pack the lesson before the kit.");
            signal.facts.add("Session ended: " + reason);
            signal.moodSignals.add("reflective");
            signal.styleTags.add("cautious-traveller");
            return signal;
        }
        if (event.startsWith("goal_")) {
            return classifyGoal(event, data, entry);
        }
        if ("tool_failed".equals(event)) {
            return classifyFailure(data, entry, state);
        }
        if ("tool_completed".equals(event)) {
            return classifySuccess(data, entry, state);
        }
        return null;
    }

    private NarrationSignal classifyGoal(String event, JsonObject data, JsonObject entry) {
        JsonObject goal = object(data, "goal");
        String message = compact(string(goal, "message", ""), 90);
        if ("goal_started".equals(event)) {
            NarrationSignal signal = signal("goal_start", false, false, entry,
                    "Long road, small steps. Very RuneScape.");
            signal.facts.add(message.length() == 0 ? "A durable goal started." : message);
            signal.moodSignals.add("steady");
            signal.styleTags.add("skiller-routine");
            return signal;
        }
        if ("goal_progress".equals(event)) {
            NarrationSignal signal = signal("goal_progress", true, true, entry,
                    "There. Progress. Quietly heroic, in a muddy sort of way.");
            signal.facts.add(message.length() == 0 ? "A durable goal reported progress." : message);
            signal.moodSignals.add("encouraged");
            signal.styleTags.add("skiller-routine");
            return signal;
        }
        if ("goal_completed".equals(event)) {
            NarrationSignal signal = signal("goal_completed", true, true, entry,
                    "Done. I will pretend that looked planned the whole time.");
            signal.facts.add(message.length() == 0 ? "A durable goal completed." : message);
            signal.moodSignals.add("pleased");
            signal.styleTags.add("dry-quest-helper");
            return signal;
        }
        if ("goal_blocked".equals(event) || "goal_stopped".equals(event)) {
            boolean death = containsAny(message, "dead", "death", "killed");
            NarrationSignal signal = signal(death ? "death_risk" : "goal_blocked", true, true, entry,
                    death ? "Next time, food first. Pride can walk behind me."
                            : "The plan has met a wall. Rude, but informative.");
            signal.facts.add(message.length() == 0 ? "A durable goal stopped or blocked." : message);
            signal.moodSignals.add(death ? "rattled" : "blocked");
            signal.styleTags.add(death ? "cautious-traveller" : "shop-bank-pragmatist");
            return signal;
        }
        return null;
    }

    private NarrationSignal classifyFailure(JsonObject data, JsonObject entry,
            SessionNarrationState state) {
        state.failureCount++;
        String tool = string(data, "tool", "unknown");
        JsonObject result = object(data, "result");
        String message = compact(string(result, "message", "tool failed"), 90);
        String lower = message.toLowerCase(Locale.ENGLISH);
        if (containsAny(lower, "dead", "death", "killed")) {
            NarrationSignal signal = signal("death_risk", true, true, entry,
                    "Next time, food first. Pride can walk behind me.");
            signal.facts.add("Risk blocker: " + message);
            signal.moodSignals.add("rattled");
            signal.styleTags.add("cautious-traveller");
            return signal;
        }
        if (containsAny(lower, "inventory", "space", "full")) {
            state.inventoryPressureCount++;
            NarrationSignal signal = signal("inventory_pressure", false, true, entry,
                    "Right. Bank first, heroics later.");
            signal.facts.add("Inventory blocker: " + message);
            signal.moodSignals.add("practical");
            signal.styleTags.add("shop-bank-pragmatist");
            return signal;
        }
        if (containsAny(lower, "nearby", "reachable", "reach", "no matching object", "found")) {
            state.routeFrictionCount++;
            boolean repeated = state.routeFrictionCount >= 3;
            NarrationSignal signal = signal(repeated ? "route_friction_repeated" : "route_friction",
                    repeated, repeated, entry,
                    "That path has opinions. I shall ask it differently.");
            signal.facts.add("Route blocker: " + message);
            signal.facts.add("Failed action: " + compact(tool, 40));
            signal.moodSignals.add("stubborn");
            signal.styleTags.add("cautious-traveller");
            return signal;
        }
        if (containsAny(lower, "shop", "bank", "interface", "dialogue", "window")) {
            NarrationSignal signal = signal("interface_blocker", false, true, entry,
                    "Wrong window, wrong moment. Very official.");
            signal.facts.add("Interface blocker: " + message);
            signal.moodSignals.add("dry");
            signal.styleTags.add("shop-bank-pragmatist");
            return signal;
        }
        if (containsAny(lower, "required", "requires", "missing", "need ", "level")) {
            NarrationSignal signal = signal("missing_requirement", true, true, entry,
                    "A requirement. Of course. The world loves paperwork.");
            signal.facts.add("Requirement blocker: " + message);
            signal.moodSignals.add("wry");
            signal.styleTags.add("dry-quest-helper");
            return signal;
        }
        return null;
    }

    private NarrationSignal classifySuccess(JsonObject data, JsonObject entry,
            SessionNarrationState state) {
        state.successCount++;
        String tool = string(data, "tool", "");
        JsonObject result = object(data, "result");
        JsonArray skillChanges = array(result, "skillChanges");
        if (skillChanges.size() > 0) {
            state.skillProgressCount++;
            boolean levelGain = hasLevelGain(skillChanges);
            NarrationSignal signal = signal("skill_progress", levelGain, levelGain, entry,
                    "A little better. That is how the grind sneaks up on you.");
            signal.facts.add(skillProgressFact(skillChanges));
            signal.moodSignals.add("encouraged");
            signal.styleTags.add("skiller-routine");
            return signal;
        }
        String status = string(result, "status", "");
        String message = string(result, "message", "");
        if ((tool.startsWith("travel_to_landmark") || tool.startsWith("walk_to_tile"))
                && ("arrived".equalsIgnoreCase(status) || containsAny(message.toLowerCase(Locale.ENGLISH), "arrived", "complete"))) {
            state.arrivalCount++;
            NarrationSignal signal = signal("arrival", true, true, entry,
                    "Arrived. Somehow, my boots and I remain on speaking terms.");
            signal.facts.add("Movement reached its target.");
            signal.moodSignals.add("relieved");
            signal.styleTags.add("cautious-traveller");
            return signal;
        }
        return null;
    }

    private boolean hasLevelGain(JsonArray skillChanges) {
        if (skillChanges == null || skillChanges.size() == 0 || !skillChanges.get(0).isJsonObject()) {
            return false;
        }
        JsonObject change = skillChanges.get(0).getAsJsonObject();
        int baseBefore = intValue(change, "baseBefore", -1);
        int baseAfter = intValue(change, "baseAfter", -1);
        int baseGained = intValue(change, "baseGained", 0);
        return baseGained > 0 || (baseBefore > 0 && baseAfter > baseBefore);
    }

    private String skillProgressFact(JsonArray skillChanges) {
        if (skillChanges == null || skillChanges.size() == 0 || !skillChanges.get(0).isJsonObject()) {
            return "A skill XP change was recorded.";
        }
        JsonObject change = skillChanges.get(0).getAsJsonObject();
        String skill = compact(string(change, "skill", "skill"), 30);
        int baseBefore = intValue(change, "baseBefore", -1);
        int baseAfter = intValue(change, "baseAfter", -1);
        int baseGained = intValue(change, "baseGained", 0);
        int xpGained = intValue(change, "xpGained", -1);
        if (baseAfter > 0 && (baseGained > 0 || (baseBefore > 0 && baseAfter > baseBefore))) {
            return "Skill progress: " + skill + " reached level " + baseAfter + ".";
        }
        if (xpGained > 0) {
            return "Skill progress: " + skill + " gained XP.";
        }
        return "Skill progress: " + skill + " changed.";
    }

    private NarrationSignal ambientSignal(AgentSession session, JsonObject entry,
            SessionNarrationState state, ProfileNarrationState profileState) {
        NarrationSignal signal = signal("ambient", false, true, entry,
                ambientFallback(state, profileState));
        signal.facts.add("Active play reflection " + (state.ambientLines + 1) + ".");
        signal.moodSignals.add("steady");
        signal.styleTags.add("skiller-routine");
        return signal;
    }

    private String ambientFallback(SessionNarrationState state, ProfileNarrationState profileState) {
        int choice = (int) ((state.eventCount * 31L + state.ambientLines * 17L
                + state.successCount * 7L + state.failureCount * 13L) % 8L);
        if (state.routeFrictionCount >= 3 && choice % 2 == 0) {
            return "The path keeps arguing, but I am learning its habits.";
        }
        if (state.inventoryPressureCount > 0 && choice % 3 == 0) {
            return "Bank first, heroics later. I do know this bit now.";
        }
        if (state.skillProgressCount > 0 && choice % 3 == 1) {
            return "The grind is quiet, but it is still adding up.";
        }
        if (state.arrivalCount > 0 && choice % 4 == 3) {
            return "A few arrivals make the map feel a little less smug.";
        }
        String reflected = reflectedAmbient(profileState, choice);
        if (reflected.length() > 0 && choice % 3 == 2) {
            return reflected;
        }
        String[] lines = {
                "Small steps, steady hands. The routine is doing its work.",
                "A quiet stretch, then. I will keep my boots pointed forward.",
                "Patient feet, tidy clicks, and maybe fewer surprises.",
                "The pack and the plan are both behaving. Suspicious, but welcome.",
                "One more ordinary bit done. That is usually how progress looks."
        };
        return lines[choice % lines.length];
    }

    private String reflectedAmbient(ProfileNarrationState profileState, int choice) {
        String recent = lastRecentSelfTalk(profileState);
        if (recent.length() == 0) {
            return "";
        }
        String lower = recent.toLowerCase(Locale.ENGLISH);
        if (containsAny(lower, "path", "road", "boots", "walk")) {
            return "I remember the road being fussy. Patient feet, better choices.";
        }
        if (containsAny(lower, "bank", "pack", "inventory", "food")) {
            return "I am keeping the bank in mind before the pack gets silly.";
        }
        if (containsAny(lower, "progress", "grind", "better", "level")) {
            return "The last bit of progress is still warm. Keep at it.";
        }
        if (containsAny(lower, "requirement", "paperwork", "wrong window")) {
            return "The world had paperwork earlier. Best keep one eye open.";
        }
        if (choice % 2 == 0) {
            return "I remember enough from earlier to be careful with this next bit.";
        }
        return "";
    }

    private String lastRecentSelfTalk(ProfileNarrationState profileState) {
        synchronized (profileState.recentSelfTalk) {
            if (profileState.recentSelfTalk.isEmpty()) {
                return "";
            }
            return profileState.recentSelfTalk.get(profileState.recentSelfTalk.size() - 1);
        }
    }

    private NarrationSignal signal(String milestone, boolean highSignal, boolean speakable,
            JsonObject entry, String fallback) {
        String place = placeFrom(entry);
        NarrationSignal signal = new NarrationSignal(milestone, highSignal, speakable, place, fallback);
        if (place.length() > 0) {
            signal.facts.add("Place: " + place);
        }
        return signal;
    }

    private boolean shouldAmbient(SessionNarrationState state, long now) {
        return state.eventCount - state.lastAmbientEventCount >= AMBIENT_EVENT_INTERVAL
                && now - state.lastAmbientAtMs >= AMBIENT_CHATTER_INTERVAL_MS;
    }

    private boolean shouldQueueLlm(SessionNarrationState sessionState,
            ProfileNarrationState profileState, long now) {
        if (sessionState.llmRequests >= MAX_LLM_REQUESTS_PER_SESSION) {
            return false;
        }
        return now - profileState.lastLlmAtMs >= LLM_COOLDOWN_MS;
    }

    private void queueLlmRequest(AgentSession session, NarrationSignal signal,
            long now, SessionNarrationState sessionState, ProfileNarrationState profileState) {
        trimPendingQueue();
        String requestId = UUID.randomUUID().toString();
        PendingNarration pending = PendingNarration.create(requestId, session.getSessionId(),
                session.getPlayerName(), signal, now, recentSelfTalkSnapshot(profileState));
        pendingById.put(requestId, pending);
        pendingOrder.add(requestId);
        sessionState.llmRequests++;
        profileState.lastLlmAtMs = now;
    }

    private boolean rememberDedupe(SessionNarrationState sessionState, NarrationSignal signal) {
        if (!sessionState.recentDedupeKeys.add(signal.dedupeKey())) {
            return false;
        }
        while (sessionState.recentDedupeKeys.size() > 40) {
            Iterator<String> iterator = sessionState.recentDedupeKeys.iterator();
            if (iterator.hasNext()) {
                iterator.next();
                iterator.remove();
            } else {
                break;
            }
        }
        return true;
    }

    private void recordAmbientFired(SessionNarrationState state, long now) {
        state.lastAmbientAtMs = now;
        state.lastAmbientEventCount = state.eventCount;
        state.ambientLines++;
    }

    private void rememberSelfTalk(ProfileNarrationState profileState, String text) {
        String cleaned = validateGeneratedText(text);
        if (cleaned.length() == 0) {
            return;
        }
        synchronized (profileState.recentSelfTalk) {
            profileState.recentSelfTalk.add(cleaned);
            while (profileState.recentSelfTalk.size() > 6) {
                profileState.recentSelfTalk.remove(0);
            }
        }
    }

    private List<String> recentSelfTalkSnapshot(ProfileNarrationState profileState) {
        synchronized (profileState.recentSelfTalk) {
            return new ArrayList<String>(profileState.recentSelfTalk);
        }
    }

    private void trimPendingQueue() {
        while (pendingById.size() >= MAX_PENDING_REQUESTS) {
            String oldest = pendingOrder.poll();
            if (oldest == null) {
                break;
            }
            pendingById.remove(oldest);
        }
    }

    private void writeChatter(AgentSessionLog log, AgentSession session,
            NarrationSignal signal, String text, String source) {
        JsonObject data = new JsonObject();
        data.addProperty("source", source);
        data.addProperty("milestone", signal.milestone);
        data.addProperty("text", text);
        data.addProperty("speakable", signal.speakable);
        data.add("styleTags", cappedArray(signal.styleTags, 3));
        data.add("moodSignals", cappedArray(signal.moodSignals, 3));
        data.add("factIds", factIds(signal.facts));
        if (signal.place.length() > 0) {
            data.addProperty("place", signal.place);
        }
        log.recordPersonalityEvent(session, "personality_chatter", data);
    }

    private void maybeSpeak(AgentSessionLog log, AgentSession session, NarrationSignal signal,
            String text, long now, SessionNarrationState sessionState, ProfileNarrationState profileState) {
        if (!signal.speakable || text.length() == 0 || sessionState.publicLines >= MAX_PUBLIC_LINES_PER_SESSION
                || now - profileState.lastPublicChatAtMs < PUBLIC_CHAT_COOLDOWN_MS) {
            return;
        }
        if (!canSpeak(session.getPlayer())) {
            return;
        }
        sessionState.publicLines++;
        profileState.lastPublicChatAtMs = now;
        queueSpeech(log, session, signal.milestone, text);
    }

    private boolean canSpeak(Player player) {
        return player != null && !player.disconnected && !player.isDead && !player.playerIsBusy();
    }

    private void queueSpeech(final AgentSessionLog log, final AgentSession session,
            final String reason, final String text) {
        AgentActionService.INSTANCE.enqueueOnGameTick("personality_speech", new Callable<JsonObject>() {
            @Override
            public JsonObject call() {
                Player player = session.getPlayer();
                if (!canSpeak(player)) {
                    recordFailure(log, session, "", "speak_unavailable");
                    return AgentToolService.failure("Personality speech target was unavailable.");
                }
                String message = compact(text, 80);
                Stream stream = new Stream(new byte[Constants.BUFFER_SIZE]);
                Misc.textPack(stream, message);
                player.setChatTextColor(0);
                player.setChatTextEffects(0);
                player.setChatTextSize((byte) stream.currentOffset);
                player.setChatText(Arrays.copyOf(stream.buffer, stream.currentOffset));
                player.setChatTextUpdateRequired(true);
                JsonObject spoken = new JsonObject();
                spoken.addProperty("text", text);
                spoken.addProperty("reason", reason);
                spoken.addProperty("cooldownMs", PUBLIC_CHAT_COOLDOWN_MS);
                log.recordPersonalityEvent(session, "personality_spoken", spoken);
                return AgentToolService.success("Personality speech queued on game tick.");
            }
        });
    }

    private void recordFailure(AgentSessionLog log, AgentSession session, String requestId, String reason) {
        if (log == null || session == null) {
            return;
        }
        JsonObject data = new JsonObject();
        data.addProperty("requestId", requestId == null ? "" : compact(requestId, 80));
        data.addProperty("reason", compact(reason, 80));
        log.recordPersonalityEvent(session, "personality_chatter_failed", data);
    }

    private boolean textAllowedForSignal(String text, NarrationSignal signal) {
        if (signal == null || signal.facts.isEmpty()) {
            return true;
        }
        String lower = text.toLowerCase(Locale.ENGLISH);
        for (String fact : signal.facts) {
            String factLower = fact.toLowerCase(Locale.ENGLISH);
            if (factLower.contains("bank") && lower.contains("bank")) {
                return true;
            }
            if (factLower.contains("food") && containsAny(lower, "food", "eat", "cook")) {
                return true;
            }
            if (factLower.contains("route") && containsAny(lower, "road", "path", "walk")) {
                return true;
            }
            if (factLower.contains("skill") && containsAny(lower, "better", "progress", "grind")) {
                return true;
            }
        }
        return text.length() <= 90;
    }

    private SessionNarrationState sessionState(AgentSession session) {
        SessionNarrationState existing = sessionStates.get(session.getSessionId());
        if (existing != null) {
            return existing;
        }
        SessionNarrationState created = new SessionNarrationState();
        SessionNarrationState previous = sessionStates.putIfAbsent(session.getSessionId(), created);
        return previous == null ? created : previous;
    }

    private ProfileNarrationState profileState(AgentSession session) {
        String key = safeProfileName(session.getPlayerName());
        ProfileNarrationState existing = profileStates.get(key);
        if (existing != null) {
            return existing;
        }
        ProfileNarrationState created = new ProfileNarrationState();
        ProfileNarrationState previous = profileStates.putIfAbsent(key, created);
        return previous == null ? created : previous;
    }

    private long now() {
        Long fixed = nowForTests;
        return fixed == null ? System.currentTimeMillis() : fixed.longValue();
    }

    private String placeFrom(JsonObject entry) {
        String joined = (string(entry, "playerName", "") + " " + entry.toString()).toLowerCase(Locale.ENGLISH);
        if (joined.contains("lumbridge")) {
            return "Lumbridge";
        }
        if (joined.contains("varrock")) {
            return "Varrock";
        }
        if (joined.contains("al-kharid") || joined.contains("al kharid")) {
            return "Al Kharid";
        }
        if (joined.contains("falador")) {
            return "Falador";
        }
        if (joined.contains("catherby")) {
            return "Catherby";
        }
        if (joined.contains("dwarven")) {
            return "Dwarven Mine";
        }
        return "";
    }

    private JsonArray factIds(List<String> facts) {
        JsonArray ids = new JsonArray();
        int limit = Math.min(4, facts.size());
        for (int i = 0; i < limit; i++) {
            ids.add("f" + (i + 1));
        }
        return ids;
    }

    private JsonArray cappedArray(List<String> values, int limit) {
        JsonArray array = new JsonArray();
        for (int i = 0; i < values.size() && i < limit; i++) {
            array.add(compact(values.get(i), 40));
        }
        return array;
    }

    private static boolean containsAny(String text, String... needles) {
        String lower = text == null ? "" : text.toLowerCase(Locale.ENGLISH);
        for (String needle : needles) {
            if (lower.contains(needle)) {
                return true;
            }
        }
        return false;
    }

    private static JsonObject object(JsonObject object, String name) {
        return object != null && object.has(name) && object.get(name).isJsonObject()
                ? object.get(name).getAsJsonObject()
                : new JsonObject();
    }

    private static JsonArray array(JsonObject object, String name) {
        return object != null && object.has(name) && object.get(name).isJsonArray()
                ? object.get(name).getAsJsonArray()
                : new JsonArray();
    }

    private static String string(JsonObject object, String name, String fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            String value = object.get(name).getAsString();
            return value == null ? fallback : compact(value, 220);
        }
        return fallback;
    }

    private static boolean bool(JsonObject object, String name, boolean fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            return object.get(name).getAsBoolean();
        }
        return fallback;
    }

    private static int intValue(JsonObject object, String name, int fallback) {
        if (object != null && object.has(name) && object.get(name).isJsonPrimitive()) {
            try {
                return object.get(name).getAsInt();
            } catch (NumberFormatException ignored) {
                return fallback;
            }
        }
        return fallback;
    }

    private static String compact(String value, int maxLength) {
        if (value == null) {
            return "";
        }
        String text = value.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ').trim();
        while (text.contains("  ")) {
            text = text.replace("  ", " ");
        }
        if (maxLength > 0 && text.length() > maxLength) {
            text = text.substring(0, Math.max(0, maxLength - 3)) + "...";
        }
        return text;
    }

    private static String safeProfileName(String playerName) {
        String safe = playerName == null ? "unknown" : playerName.trim().toLowerCase(Locale.ENGLISH)
                .replaceAll("[^a-z0-9._-]+", "-");
        return safe.length() == 0 ? "unknown" : safe;
    }

    private static class SessionNarrationState {
        private int eventCount;
        private int llmRequests;
        private int publicLines;
        private int routeFrictionCount;
        private int inventoryPressureCount;
        private int skillProgressCount;
        private int arrivalCount;
        private int successCount;
        private int failureCount;
        private int ambientLines;
        private int lastAmbientEventCount;
        private long lastAmbientAtMs;
        private boolean ambientClockStarted;
        private final LinkedHashSet<String> recentDedupeKeys = new LinkedHashSet<String>();
    }

    private static class ProfileNarrationState {
        private long lastLlmAtMs = -LLM_COOLDOWN_MS;
        private long lastPublicChatAtMs = -PUBLIC_CHAT_COOLDOWN_MS;
        private final List<String> recentSelfTalk = Collections.synchronizedList(new ArrayList<String>());
    }

    private static class NarrationSignal {
        private final String milestone;
        private final boolean highSignal;
        private final boolean speakable;
        private final String place;
        private final String fallbackText;
        private final List<String> facts = new ArrayList<String>();
        private final List<String> moodSignals = new ArrayList<String>();
        private final List<String> styleTags = new ArrayList<String>();

        private NarrationSignal(String milestone, boolean highSignal, boolean speakable,
                String place, String fallbackText) {
            this.milestone = milestone;
            this.highSignal = highSignal;
            this.speakable = speakable;
            this.place = place == null ? "" : place;
            this.fallbackText = fallbackText == null ? "" : fallbackText;
        }

        private String dedupeKey() {
            String firstFact = facts.isEmpty() ? "" : facts.get(0);
            return milestone + "|" + place + "|" + compact(firstFact, 60);
        }
    }

    private static class PendingNarration {
        private final String requestId;
        private final String sessionId;
        private final String profile;
        private final NarrationSignal signal;
        private final long createdAtMs;
        private final List<String> recentSelfTalk;

        private PendingNarration(String requestId, String sessionId, String profile,
                NarrationSignal signal, long createdAtMs, List<String> recentSelfTalk) {
            this.requestId = requestId;
            this.sessionId = sessionId;
            this.profile = profile;
            this.signal = signal;
            this.createdAtMs = createdAtMs;
            this.recentSelfTalk = recentSelfTalk == null
                    ? new ArrayList<String>()
                    : new ArrayList<String>(recentSelfTalk);
        }

        private static PendingNarration create(String requestId, String sessionId, String profile,
                NarrationSignal signal, long createdAtMs, List<String> recentSelfTalk) {
            return new PendingNarration(requestId, sessionId, profile, signal, createdAtMs, recentSelfTalk);
        }

        private JsonObject toJson() {
            JsonObject object = new JsonObject();
            object.addProperty("requestId", requestId);
            object.addProperty("profile", compact(profile, 64));
            object.addProperty("milestone", signal.milestone);
            object.addProperty("place", compact(signal.place, 40));
            object.add("facts", facts());
            object.add("moodSignals", capped(signal.moodSignals, 3, 40));
            object.add("styleTags", capped(signal.styleTags, 3, 40));
            object.add("recentSelfTalk", recentSelfTalk());
            object.addProperty("speakable", signal.speakable);
            object.addProperty("createdAtMs", createdAtMs);
            return object;
        }

        private JsonArray facts() {
            JsonArray array = new JsonArray();
            for (int i = 0; i < signal.facts.size() && i < 4; i++) {
                array.add(compact(signal.facts.get(i), 90));
            }
            return array;
        }

        private JsonArray recentSelfTalk() {
            JsonArray array = new JsonArray();
            int start = Math.max(0, recentSelfTalk.size() - 2);
            for (int i = start; i < recentSelfTalk.size(); i++) {
                array.add(compact(recentSelfTalk.get(i), 90));
            }
            return array;
        }

        private JsonArray capped(List<String> values, int limit, int maxLength) {
            JsonArray array = new JsonArray();
            for (int i = 0; i < values.size() && i < limit; i++) {
                array.add(compact(values.get(i), maxLength));
            }
            return array;
        }
    }
}
