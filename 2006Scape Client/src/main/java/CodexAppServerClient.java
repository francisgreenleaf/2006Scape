import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;

public class CodexAppServerClient {

    private static final Gson GSON = new Gson();

    private final AgentBridgeHttpClient bridgeHttpClient;
    private final Consumer<String> messageConsumer;
    private final AgentTerminalLog terminalLog;
    private final Runnable turnCompleteConsumer;
    private final AtomicInteger requestId = new AtomicInteger(1);
    private final Map<Integer, CompletableFuture<JsonObject>> pendingRequests = new ConcurrentHashMap<Integer, CompletableFuture<JsonObject>>();
    private final StringBuilder currentAssistantMessage = new StringBuilder();

    private Process process;
    private BufferedWriter writer;
    private Thread readerThread;
    private volatile boolean initialized;
    private volatile boolean accountReady;
    private volatile String threadId;
    private volatile String currentTurnId;
    private volatile long currentTurnStartedAtMs;

    public CodexAppServerClient(AgentBridgeHttpClient bridgeHttpClient, Consumer<String> messageConsumer, Runnable turnCompleteConsumer) {
        this(bridgeHttpClient, messageConsumer, new AgentTerminalLog(), turnCompleteConsumer);
    }

    public CodexAppServerClient(AgentBridgeHttpClient bridgeHttpClient, Consumer<String> messageConsumer, AgentTerminalLog terminalLog, Runnable turnCompleteConsumer) {
        this.bridgeHttpClient = bridgeHttpClient;
        this.messageConsumer = messageConsumer;
        this.terminalLog = terminalLog;
        this.turnCompleteConsumer = turnCompleteConsumer;
    }

    public synchronized void start() throws IOException {
        if (isRunning()) {
            return;
        }
        File executable = findCodexExecutable();
        ProcessBuilder builder = executable == null
                ? new ProcessBuilder("codex", "app-server", "--listen", "stdio://")
                : new ProcessBuilder(executable.getAbsolutePath(), "app-server", "--listen", "stdio://");
        builder.redirectError(ProcessBuilder.Redirect.INHERIT);
        process = builder.start();
        writer = new BufferedWriter(new OutputStreamWriter(process.getOutputStream(), StandardCharsets.UTF_8));
        readerThread = new Thread(() -> readLoop(), "CodexAppServerReader");
        readerThread.setDaemon(true);
        readerThread.start();
        terminalLog.system("Codex app-server started.");
    }

    public synchronized void initialize() throws Exception {
        start();
        if (initialized) {
            return;
        }
        JsonObject clientInfo = new JsonObject();
        clientInfo.addProperty("name", "2006scape_agent");
        clientInfo.addProperty("title", "2006Scape Agent");
        clientInfo.addProperty("version", "0.1.0");
        JsonObject capabilities = new JsonObject();
        capabilities.addProperty("experimentalApi", true);
        JsonObject params = new JsonObject();
        params.add("clientInfo", clientInfo);
        params.add("capabilities", capabilities);
        awaitResult(sendRequest("initialize", params), 30_000L);
        sendNotification("initialized", new JsonObject());
        initialized = true;
        terminalLog.system("Codex app-server initialized.");
        refreshAccount();
    }

    public synchronized boolean refreshAccount() {
        try {
            JsonObject params = new JsonObject();
            params.addProperty("refreshToken", false);
            JsonObject result = awaitResult(sendRequest("account/read", params), 15_000L);
            JsonObject account = result.has("account") && result.get("account").isJsonObject()
                    ? result.get("account").getAsJsonObject()
                    : null;
            accountReady = account != null;
            return accountReady;
        } catch (Exception e) {
            accountReady = false;
            return false;
        }
    }

    public synchronized void loginWithApiKey(String apiKey) throws Exception {
        initialize();
        JsonObject params = new JsonObject();
        params.addProperty("type", "apiKey");
        params.addProperty("apiKey", apiKey);
        awaitResult(sendRequest("account/login/start", params), 30_000L);
        accountReady = true;
        terminalLog.system("Codex account authenticated.");
    }

    public synchronized void ensureThread() throws Exception {
        initialize();
        if (!accountReady && !refreshAccount()) {
            throw new IllegalStateException("Codex is not authenticated. Use /agent key first.");
        }
        if (threadId != null && !threadId.isEmpty()) {
            return;
        }
        JsonObject params = new JsonObject();
        params.addProperty("cwd", workspaceDir());
        params.addProperty("approvalPolicy", "never");
        params.addProperty("sandbox", "read-only");
        params.addProperty("serviceName", "2006Scape Agent");
        params.addProperty("developerInstructions", developerInstructions());
        params.add("dynamicTools", dynamicTools());
        JsonObject result = awaitResult(sendRequest("thread/start", params), 30_000L);
        JsonObject thread = result.get("thread").getAsJsonObject();
        threadId = thread.get("id").getAsString();
        terminalLog.system("Codex thread ready.");
    }

    public synchronized void startTurn(String userCommand) throws Exception {
        ensureThread();
        currentAssistantMessage.setLength(0);
        JsonObject params = new JsonObject();
        params.addProperty("threadId", threadId);
        params.add("input", userInput(userPrompt(userCommand)));
        JsonObject sandboxPolicy = new JsonObject();
        sandboxPolicy.addProperty("type", "readOnly");
        sandboxPolicy.addProperty("networkAccess", false);
        params.add("sandboxPolicy", sandboxPolicy);
        params.addProperty("approvalPolicy", "never");
        JsonObject result = awaitResult(sendRequest("turn/start", params), 30_000L);
        JsonObject turn = result.get("turn").getAsJsonObject();
        currentTurnId = turn.get("id").getAsString();
        currentTurnStartedAtMs = System.currentTimeMillis();
        JsonObject event = new JsonObject();
        event.addProperty("threadId", threadId);
        event.addProperty("turnId", currentTurnId);
        event.addProperty("command", userCommand == null ? "" : userCommand);
        recordSessionEvent("turn_started", event);
        terminalLog.task("Turn started: " + (userCommand == null ? "" : userCommand));
    }

    public synchronized void interruptCurrentTurn() {
        if (threadId == null || currentTurnId == null) {
            return;
        }
        JsonObject event = new JsonObject();
        event.addProperty("threadId", threadId);
        event.addProperty("turnId", currentTurnId);
        event.addProperty("durationMs", currentTurnDurationMs());
        recordSessionEvent("turn_interrupted", event);
        terminalLog.warn("Turn interrupted.");
        JsonObject params = new JsonObject();
        params.addProperty("threadId", threadId);
        params.addProperty("turnId", currentTurnId);
        sendRequest("turn/interrupt", params);
        currentTurnId = null;
        currentTurnStartedAtMs = 0L;
    }

    public boolean isRunning() {
        return process != null && process.isAlive();
    }

    public boolean hasAccount() {
        return accountReady;
    }

    public String status() {
        if (!isRunning()) {
            return "app-server stopped";
        }
        if (!accountReady) {
            return "needs API key";
        }
        if (!bridgeHttpClient.hasSession()) {
            return "needs game bridge session";
        }
        return "ready" + (bridgeHttpClient.getPlayerName().isEmpty() ? "" : " for " + bridgeHttpClient.getPlayerName());
    }

    private File findCodexExecutable() {
        String[] candidates = {"/opt/homebrew/bin/codex", "/usr/local/bin/codex"};
        for (String candidate : candidates) {
            File file = new File(candidate);
            if (file.exists() && file.canExecute()) {
                return file;
            }
        }
        return null;
    }

    private CompletableFuture<JsonObject> sendRequest(String method, JsonObject params) {
        int id = requestId.getAndIncrement();
        CompletableFuture<JsonObject> future = new CompletableFuture<JsonObject>();
        pendingRequests.put(id, future);
        JsonObject request = new JsonObject();
        request.addProperty("id", id);
        request.addProperty("method", method);
        if (params != null) {
            request.add("params", params);
        }
        try {
            sendJson(request);
        } catch (IOException e) {
            pendingRequests.remove(id);
            future.completeExceptionally(e);
        }
        return future;
    }

    private void sendNotification(String method, JsonObject params) throws IOException {
        JsonObject request = new JsonObject();
        request.addProperty("method", method);
        if (params != null) {
            request.add("params", params);
        }
        sendJson(request);
    }

    private synchronized void sendJson(JsonObject object) throws IOException {
        if (writer == null) {
            throw new IOException("Codex app-server is not running.");
        }
        writer.write(GSON.toJson(object));
        writer.newLine();
        writer.flush();
    }

    private JsonObject awaitResult(CompletableFuture<JsonObject> future, long timeoutMs) throws Exception {
        JsonObject response = future.get(timeoutMs, TimeUnit.MILLISECONDS);
        if (response.has("error")) {
            JsonObject error = response.get("error").getAsJsonObject();
            String message = error.has("message") ? error.get("message").getAsString() : error.toString();
            throw new IOException(message);
        }
        return response.has("result") && response.get("result").isJsonObject()
                ? response.get("result").getAsJsonObject()
                : new JsonObject();
    }

    private void readLoop() {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                handleServerMessage(line);
            }
        } catch (IOException e) {
            terminalLog.error("Codex app-server disconnected: " + cleanMessage(e));
            messageConsumer.accept("Codex app-server disconnected: " + e.getMessage());
        }
    }

    private void handleServerMessage(String line) {
        JsonObject message;
        try {
            message = new JsonParser().parse(line).getAsJsonObject();
        } catch (Exception ignored) {
            return;
        }
        if (message.has("id") && !message.has("method")) {
            int id = message.get("id").getAsInt();
            CompletableFuture<JsonObject> future = pendingRequests.remove(id);
            if (future != null) {
                future.complete(message);
            }
            return;
        }
        if (message.has("id") && message.has("method")) {
            handleServerRequest(message);
            return;
        }
        if (message.has("method")) {
            handleNotification(message.get("method").getAsString(), message.has("params") ? message.get("params").getAsJsonObject() : new JsonObject());
        }
    }

    private void handleServerRequest(JsonObject request) {
        String method = request.get("method").getAsString();
        int id = request.get("id").getAsInt();
        if (!"item/tool/call".equals(method)) {
            sendError(id, -32601, "Unsupported app-server request: " + method);
            return;
        }
        String displayTool = "tool";
        long startedAt = System.currentTimeMillis();
        try {
            JsonObject params = request.get("params").getAsJsonObject();
            String namespace = params.has("namespace") && !params.get("namespace").isJsonNull() ? params.get("namespace").getAsString() : "";
            String tool = params.get("tool").getAsString();
            displayTool = namespace == null || namespace.length() == 0 ? tool : namespace + "." + tool;
            JsonObject arguments = params.has("arguments") && params.get("arguments").isJsonObject()
                    ? params.get("arguments").getAsJsonObject()
                    : new JsonObject();
            JsonObject toolResponse = "rs".equals(namespace) ? bridgeHttpClient.callTool(tool, arguments) : errorObject("Unknown tool namespace: " + namespace);
            boolean success = toolResponse.has("success") && toolResponse.get("success").getAsBoolean();
            terminalLog.toolResult(displayTool, success, summarizeToolResponse(toolResponse), System.currentTimeMillis() - startedAt);
            JsonObject result = new JsonObject();
            JsonArray contentItems = new JsonArray();
            JsonObject text = new JsonObject();
            text.addProperty("type", "inputText");
            text.addProperty("text", GSON.toJson(toolResponse));
            contentItems.add(text);
            result.add("contentItems", contentItems);
            result.addProperty("success", toolResponse.has("success") && toolResponse.get("success").getAsBoolean());
            JsonObject response = new JsonObject();
            response.addProperty("id", id);
            response.add("result", result);
            sendJson(response);
        } catch (Exception e) {
            terminalLog.toolResult(displayTool, false, cleanMessage(e), System.currentTimeMillis() - startedAt);
            sendError(id, -32000, e.getMessage());
        }
    }

    private JsonObject errorObject(String message) {
        JsonObject object = new JsonObject();
        object.addProperty("success", false);
        object.addProperty("message", message);
        return object;
    }

    private void sendError(int id, int code, String messageText) {
        JsonObject response = new JsonObject();
        response.addProperty("id", id);
        JsonObject error = new JsonObject();
        error.addProperty("code", code);
        error.addProperty("message", messageText == null ? "Tool call failed." : messageText);
        response.add("error", error);
        try {
            sendJson(response);
        } catch (IOException ignored) {
        }
    }

    private void handleNotification(String method, JsonObject params) {
        if ("item/agentMessage/delta".equals(method)) {
            if (params.has("delta")) {
                currentAssistantMessage.append(params.get("delta").getAsString());
            }
            return;
        }
        if ("item/started".equals(method) && params.has("item")) {
            JsonObject item = params.get("item").getAsJsonObject();
            if (item.has("type") && "dynamicToolCall".equals(item.get("type").getAsString()) && item.has("tool")) {
                String tool = "rs." + item.get("tool").getAsString();
                terminalLog.toolStart(tool);
                messageConsumer.accept("Using " + tool + "...");
            }
            return;
        }
        if ("item/completed".equals(method) && params.has("item")) {
            JsonObject item = params.get("item").getAsJsonObject();
            if (item.has("type") && "agentMessage".equals(item.get("type").getAsString()) && item.has("text")) {
                String text = item.get("text").getAsString().trim();
                if (!text.isEmpty()) {
                    terminalLog.assistant(text);
                    messageConsumer.accept(text);
                    JsonObject event = new JsonObject();
                    event.addProperty("threadId", threadId == null ? "" : threadId);
                    event.addProperty("turnId", currentTurnId == null ? "" : currentTurnId);
                    event.addProperty("text", text);
                    recordSessionEvent("assistant_message", event);
                }
            }
            return;
        }
        if ("turn/completed".equals(method)) {
            JsonObject event = new JsonObject();
            event.addProperty("threadId", threadId == null ? "" : threadId);
            event.addProperty("turnId", currentTurnId == null ? "" : currentTurnId);
            event.addProperty("durationMs", currentTurnDurationMs());
            recordSessionEvent("turn_completed", event);
            terminalLog.success("Turn completed.");
            currentTurnId = null;
            currentTurnStartedAtMs = 0L;
            turnCompleteConsumer.run();
        }
    }

    private String summarizeToolResponse(JsonObject response) {
        if (response == null) {
            return "No response.";
        }
        if (response.has("message") && response.get("message").isJsonPrimitive()) {
            return compact(response.get("message").getAsString(), 260);
        }
        return compact(GSON.toJson(response), 260);
    }

    private String compact(String value, int maxLength) {
        if (value == null) {
            return "";
        }
        String text = value.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').trim();
        if (text.length() > maxLength) {
            text = text.substring(0, maxLength - 3) + "...";
        }
        return text;
    }

    private String cleanMessage(Exception e) {
        String message = e.getMessage();
        if (message == null || message.trim().isEmpty()) {
            message = e.getClass().getSimpleName();
        }
        return compact(message, 260);
    }

    private void recordSessionEvent(String event, JsonObject data) {
        try {
            bridgeHttpClient.recordSessionEvent(event, data);
        } catch (IOException ignored) {
        }
    }

    private long currentTurnDurationMs() {
        return currentTurnStartedAtMs <= 0L ? 0L : Math.max(0L, System.currentTimeMillis() - currentTurnStartedAtMs);
    }

    private JsonArray dynamicTools() {
        JsonArray tools = new JsonArray();
        tools.add(tool("observe_state", "Observe current player state, inventory, nearby NPCs, nearby objects, and nearby ground items.", schema()));
        tools.add(tool("observe_state_XS", "Default compact observation surface. Returns compact player, inventory/food, bank summary, equipment, nearby NPC/object/ground-item context, and nonzero skill levels. Use full observe_state only when XS omits a field needed for debugging or evidence.", schema()));
        tools.add(tool("plan_combat_training", "Plan safe and efficient melee combat training toward target attack, strength, and defence levels. Returns next style, target area, food, gear, and coin-budget guidance.", schema("targetLevel", "number")));
        tools.add(tool("continue_dialogue", "Continue the currently open dialogue using the normal dialogue continue flow.", schema()));
        tools.add(tool("select_dialogue_option", "Select a visible dialogue option by number, using normal dialogue button handling. For ladder prompts, option 1 climbs up and option 2 climbs down.", schema("option", "number")));
        tools.add(tool("close_interfaces", "Close open game interfaces such as shops or dialogues.", schema()));
        tools.add(tool("set_run", "Enable or disable the normal run toggle. Use enabled=true before repeated travel when run energy is available.", schema("enabled", "boolean")));
        tools.add(tool("use_item_on_item", "Use one inventory item on another through normal item-on-item mechanics. Prefer this primitive in external scripts instead of adding new skill-specific Java tools.", schema("itemId", "number", "slot", "number", "name", "string", "targetItemId", "number", "targetSlot", "number", "targetName", "string", "useWithItemId", "number", "withItemId", "number")));
        tools.add(tool("use_item_on_object", "Use an inventory item on an object tile through normal item-on-object mechanics. Prefer this primitive in external scripts for skilling and quest interactions.", schema("itemId", "number", "slot", "number", "name", "string", "objectId", "number", "x", "number", "y", "number", "height", "number")));
        tools.add(tool("click_interface_button", "Click a game interface/action button by buttonId through shared server button handlers. Use after primitives that open make/select/dialogue interfaces.", schema("buttonId", "number", "actionButtonId", "number", "id", "number")));
        tools.add(tool("select_interface_item", "Select an item shown in a game interface by itemId/interfaceId and amount through normal interface item handlers. Use for smithing-interface item choices after opening the interface with item-on-object.", schema("interfaceId", "number", "widgetId", "number", "itemId", "number", "id", "number", "slot", "number", "amount", "number")));
        tools.add(tool("preview_local_path", "Preview the server-side clipped local path to an absolute tile without moving the player. Use this before new route legs to avoid long clicks into blocked or hazardous corridors.", schema("x", "number", "y", "number", "height", "number", "moveNear", "boolean", "applyBounds", "boolean", "maxWalkDistance", "number", "xLength", "number", "yLength", "number")));
        tools.add(tool("walk_to_tile", "Walk the player toward an absolute tile using normal pathfinding.", schema("x", "number", "y", "number", "height", "number", "stopDistance", "number", "maxWalkDistance", "number")));
        tools.add(tool("walk_path_steps", "Queue a short list of adjacent client-style walking steps. Clipping is enforced unless allowObjectTransition=true after an object interaction such as an opened gate.", schema("steps", "array", "path", "array", "run", "boolean", "allowObjectTransition", "boolean")));
        tools.add(tool("walk_to_tile_until_arrived", "Walk toward an absolute tile through normal pathfinding on server ticks until within stopDistance, maxTicks is reached, or a blocker occurs. Emits tile-level movement trace events for learned routing. Use this for efficient repeated routes when exact tiles are known.", schema("x", "number", "y", "number", "height", "number", "stopDistance", "number", "maxTicks", "number", "maxWalkDistance", "number", "stopOnCombat", "boolean", "stopOnStall", "boolean")));
        tools.add(tool("walk_to_tile_until_arrived_XS", "Default compact walk batch. Same movement behavior as walk_to_tile_until_arrived, but returns compact status, final player/inventory context, nearby hazards/objects, and route blocker fields without full state payloads.", schema("x", "number", "y", "number", "height", "number", "stopDistance", "number", "maxTicks", "number", "maxWalkDistance", "number", "stopOnCombat", "boolean", "stopOnStall", "boolean")));
        tools.add(tool("travel_to_landmark", "Walk toward a known landmark waypoint. Call again after movement advances until complete is true; wait_ticks returns updated state, so avoid an extra observe after each wait.", schema("name", "string")));
        tools.add(tool("travel_to_landmark_until_arrived", "Walk toward a known landmark through normal pathing on server ticks until arrived, maxTicks is reached, or a blocker occurs. Emits tile-level movement trace events for learned routing. Use this for efficient repeated bank and resource trips instead of polling travel_to_landmark and wait_ticks.", schema("name", "string", "maxTicks", "number", "stopOnCombat", "boolean", "stopOnStall", "boolean")));
        tools.add(tool("travel_to_landmark_until_arrived_XS", "Compact landmark travel batch. Same behavior as travel_to_landmark_until_arrived, but returns compact status and final player/inventory context.", schema("name", "string", "maxTicks", "number", "stopOnCombat", "boolean", "stopOnStall", "boolean")));
        tools.add(tool("wait_ticks", "Wait for server ticks and return updated state. Use this as the observation after waiting, and prefer one multi-tick wait over repeated one-tick polling. Prefer wait_until_idle or an *_until_* batch tool when one fits.", schema("ticks", "number")));
        tools.add(tool("wait_ticks_XS", "Compact tick wait. Same behavior as wait_ticks, but returns compact status and final player/inventory context. Prefer wait_until_idle_XS when waiting for movement, skilling, or combat state to clear.", schema("ticks", "number")));
        tools.add(tool("wait_until_idle", "Wait server-side until selected busy states clear, then return observed state. Use after smelting, smithing, cooking, fishing, combat, or object interactions instead of repeated wait_ticks polling. Defaults: movement=true, skilling=true, combat=false.", schema("maxTicks", "number", "movement", "boolean", "skilling", "boolean", "combat", "boolean", "includeMovement", "boolean", "includeSkilling", "boolean", "includeCombat", "boolean")));
        tools.add(tool("wait_until_idle_XS", "Default compact wait. Same behavior as wait_until_idle, but returns compact status and final player/inventory context instead of the full observe_state payload.", schema("maxTicks", "number", "movement", "boolean", "skilling", "boolean", "combat", "boolean", "includeMovement", "boolean", "includeSkilling", "boolean", "includeCombat", "boolean")));
        tools.add(tool("find_nearest_npc", "Find the nearest live NPC by name. Set reachable=true to skip NPCs blocked by clipping or fences.", schema("name", "string", "maxDistance", "number", "reachable", "boolean")));
        tools.add(tool("find_training_npc", "Find the best nearby combat-training NPC by balancing high hitpoints, low max hit, combat level, reachability, and whether it is already under attack.", schema("name", "string", "npc", "string", "maxDistance", "number", "minHitpoints", "number", "maxNpcMaxHit", "number", "reachable", "boolean", "allowUnderAttack", "boolean")));
        tools.add(tool("interact_npc", "Interact with a nearby NPC using the first, second, or third normal NPC option. Use this primitive for fishing spots, travel NPCs, shops/dialogues, and other non-combat NPC actions from external scripts.", schema("npcIndex", "number", "npcId", "number", "npcIds", "array", "type", "number", "name", "string", "npc", "string", "option", "string", "maxDistance", "number", "reachable", "boolean", "requireReachable", "boolean")));
        tools.add(tool("attack_npc", "Attack a live NPC by npcIndex using normal combat mechanics, walking into melee range first when needed.", schema("npcIndex", "number")));
        tools.add(tool("train_combat", "Run one safe combat-training step: eat if HP is low, set the next melee style, continue current combat, attack a good nearby target, or travel to the recommended training area. Use style to temporarily force attack, strength, defence, or controlled.", schema("targetLevel", "number", "style", "string", "trainingStyle", "string", "eatAtHitpoints", "number", "retreatAtHitpoints", "number", "area", "string", "landmark", "string", "name", "string", "npc", "string", "maxDistance", "number", "minHitpoints", "number", "maxNpcMaxHit", "number")));
        tools.add(tool("train_smithing_profit", "Run one high-level smithing profit step toward a coin target: sell smithing products, bank/restock, withdraw bars or ores, smelt, smith the best item by XP or margin, or report a concrete blocker.", schema("targetCoins", "number", "strategy", "string", "category", "string")));
        tools.add(tool("start_combat_goal", "Start a durable server-side combat training goal that keeps using normal train_combat steps across game ticks after the current Codex turn ends. By default it lets the combat planner rotate attack/strength/defence and move to better areas as the account levels; pass fixedStyle or fixedArea only when the player explicitly wants a locked style or place. It preserves account progression by looting useful combat drops and banking them when inventory space gets low.", schema("targetLevel", "number", "level", "number", "stepIntervalTicks", "number", "ticksBetweenSteps", "number", "maxActions", "number", "area", "string", "landmark", "string", "name", "string", "npc", "string", "style", "string", "trainingStyle", "string", "fixedArea", "boolean", "lockArea", "boolean", "fixedStyle", "boolean", "lockStyle", "boolean")));
        tools.add(tool("observe_goal", "Observe the currently registered durable gameplay goal and updated player state.", schema()));
        tools.add(tool("stop_goal", "Stop the currently registered durable gameplay goal for this player.", schema()));
        tools.add(tool("find_nearest_object", "Find the nearest object by name, objectIds, or resource such as iron.", schema("name", "string", "resource", "string", "maxDistance", "number")));
        tools.add(tool("find_nearest_object_XS", "Default compact object search. Finds the nearest object like find_nearest_object; on failure it returns nearby compact object candidates so the next step can adjust name/id/reachability without a full observe.", schema("name", "string", "resource", "string", "maxDistance", "number", "objectIds", "array", "objectId", "number")));
        tools.add(tool("find_nearest_rock", "Find the nearest mineable rock by ore/resource name such as copper, tin, or iron.", schema("ore", "string", "resource", "string", "maxDistance", "number")));
        tools.add(tool("find_nearest_tree", "Find the nearest choppable tree by tree/resource name such as tree, oak, willow, maple, yew, or magic.", schema("tree", "string", "resource", "string", "maxDistance", "number")));
        tools.add(tool("set_combat_style", "Set melee combat XP style to attack, strength, defence, or controlled using normal combat style state.", schema("style", "string")));
        tools.add(tool("equip_item", "Equip a matching inventory item by name, itemId, or slot using normal item equipment requirements.", schema("name", "string", "item", "string", "itemId", "number", "slot", "number")));
        tools.add(tool("unequip_item", "Unequip a matching equipped item into inventory by equipment slot, slotName, name, or itemId using normal equipment mechanics.", schema("equipmentSlot", "number", "slotName", "string", "name", "string", "item", "string", "itemId", "number")));
        tools.add(tool("unequip_items_XS", "Compact multi-unequip surface. Unequip one or more equipped items by equipmentSlots, slotNames, itemIds, names/items, or all=true; returns compact moved items and final equipment/inventory state.", schema("equipmentSlot", "number", "equipmentSlots", "array", "slot", "number", "slots", "array", "slotName", "string", "slotNames", "array", "name", "string", "names", "array", "item", "string", "items", "array", "itemId", "number", "itemIds", "array", "all", "boolean")));
        tools.add(tool("unequip_item_XS", "Compact unequip alias. Use unequip_items_XS for several slots/items; this accepts the same multi-item fields for compatibility and returns compact equipment/inventory state.", schema("equipmentSlot", "number", "equipmentSlots", "array", "slot", "number", "slots", "array", "slotName", "string", "slotNames", "array", "name", "string", "names", "array", "item", "string", "items", "array", "itemId", "number", "itemIds", "array", "all", "boolean")));
        tools.add(tool("equip_best_items", "Equip the best combat upgrades currently in inventory using normal equipment requirements. Call after picking up gear drops, buying gear, or smithing gear.", schema()));
        tools.add(tool("eat_item", "Eat matching inventory food by name, itemId, or slot using normal food mechanics.", schema("name", "string", "item", "string", "itemId", "number", "slot", "number")));
        tools.add(tool("eat_best_food", "Eat the best inventory food for the current missing hitpoints. Set emergency=true to prefer the highest-healing food.", schema("emergency", "boolean")));
        tools.add(tool("pickup_ground_item", "Pick up a visible nearby ground item or known global spawn by name, itemId, itemIds, or tile using normal ground-item mechanics. Call again after walking toward the item.", schema("name", "string", "item", "string", "itemId", "number", "x", "number", "y", "number", "maxDistance", "number")));
        tools.add(tool("fish_food", "Catch raw fish at a nearby net fishing spot using a small fishing net and normal Fishing mechanics. If no net spot is nearby, it walks toward the known Lumbridge fishing spot.", schema("maxDistance", "number")));
        tools.add(tool("cook_food", "Cook raw food at a nearby range or fire using normal Cooking mechanics. If no cooking object is nearby, it walks toward the known Lumbridge range unless fireOnly=true.", schema("itemId", "number", "amount", "number", "maxDistance", "number", "fireOnly", "boolean")));
        tools.add(tool("light_fire", "Light a cooking fire from a tinderbox and logs on the current outdoor tile using normal Firemaking mechanics.", schema("logId", "number")));
        tools.add(tool("open_nearest_shop", "Open a nearby shopkeeper's shop through normal shop mechanics. Use name to prefer a shop or NPC name.", schema("name", "string", "maxDistance", "number")));
        tools.add(tool("buy_shop_item", "Buy a matching item from the currently open shop by name, itemId, itemIds, or slot using coins and normal stock rules.", schema("name", "string", "item", "string", "itemId", "number", "slot", "number", "amount", "number")));
        tools.add(tool("sell_inventory_item", "Sell a matching inventory item to the currently open shop by name, itemId, or slot using normal shop rules.", schema("name", "string", "item", "string", "itemId", "number", "slot", "number", "amount", "number")));
        tools.add(tool("sell_inventory_items", "Sell multiple matching inventory items to the currently open shop by category, name, itemId, or itemIds using normal shop rules.", schema("category", "string", "name", "string", "item", "string", "itemId", "number", "amount", "number")));
        tools.add(tool("interact_object", "Interact with an object using first, second, third, or fourth option.", schema("objectId", "number", "x", "number", "y", "number", "option", "string")));
        tools.add(tool("mine_ore", "Find and mine the requested ore with normal mining mechanics. If mining is already underway, do not restart it; wait_ticks returns updated inventory and XP state.", schema("ore", "string", "maxDistance", "number")));
        tools.add(tool("mine_ore_until_inventory_full", "Mine the requested ore through normal mining mechanics on server ticks until inventory is full, maxTicks is reached, or a blocker occurs. Use this for efficient banking runs instead of polling mine_ore and wait_ticks per ore.", schema("ore", "string", "maxDistance", "number", "maxTicks", "number")));
        tools.add(tool("chop_tree", "Find and chop a nearby tree with normal woodcutting mechanics. If woodcutting is already underway, do not restart it. Use tree=tree below level 15 and tree=oak at level 15+ when oaks are nearby.", schema("tree", "string", "resource", "string", "maxDistance", "number")));
        tools.add(tool("chop_tree_until_inventory_full", "Chop the requested tree through normal woodcutting mechanics on server ticks until inventory is full, maxTicks is reached, or a blocker occurs. Use this for efficient log gathering instead of polling chop_tree and wait_ticks per log.", schema("tree", "string", "resource", "string", "maxDistance", "number", "maxTicks", "number")));
        tools.add(tool("fletch_logs", "Use a knife on inventory logs and start making the best available fletching product for the current level, or a requested product/log when supplied.", schema("logId", "number", "itemId", "number", "productId", "number", "log", "string", "resource", "string", "product", "string", "make", "string", "amount", "number")));
        tools.add(tool("fletch_logs_until_inventory_empty", "Fletch inventory logs through normal knife-and-log mechanics on server ticks until logs are gone, targetLevel is reached, maxTicks is reached, or a blocker occurs. Use this for efficient log-to-bow batches.", schema("logId", "number", "itemId", "number", "productId", "number", "log", "string", "resource", "string", "product", "string", "make", "string", "amount", "number", "targetLevel", "number", "targetFletchingLevel", "number", "maxTicks", "number")));
        tools.add(tool("drop_inventory_items", "Drop inventory items by name or itemIds using the normal drop mechanic. Use this only when explicitly asked to drop items.", schema("name", "string")));
        tools.add(tool("deposit_inventory_items", "Deposit matching inventory items into the bank by name, itemId, or itemIds. Pass itemIds to deposit multiple item types in one call. The player must already be in a bank area.", schema("name", "string", "item", "string", "itemId", "number", "itemIds", "array", "keepFoodCount", "number")));
        tools.add(tool("deposit_inventory_items_XS", "Default compact bank deposit. Same behavior as deposit_inventory_items, including itemIds for multiple item types and keepFoodCount for preserving food, but returns compact inventory/bank state.", schema("name", "string", "item", "string", "itemId", "number", "itemIds", "array", "keepFoodCount", "number")));
        tools.add(tool("withdraw_bank_items", "Withdraw matching bank items by name or itemIds. The player must already be in a bank area.", schema("name", "string", "amount", "number")));
        tools.add(tool("food_bank_XS", "Compact non-mutating food, bank, inventory, equipment, and combat-supply summary. Use before cooking/fishing/banking decisions instead of a full observation when the question is food or loadout state.", schema()));
        tools.add(tool("deposit_excess_coins", "Deposit inventory coins above a combat budget into the bank. Use this before training or shopping so the player does not carry unnecessary capital.", schema("keepAmount", "number")));
        tools.add(tool("smelt_bar", "Smelt bars at a nearby furnace using normal smelting mechanics.", schema("bar", "string", "name", "string", "itemId", "number", "amount", "number", "maxDistance", "number")));
        tools.add(tool("smith_item", "Smith an item at a nearby anvil using normal smithing requirements and bars.", schema("name", "string", "item", "string", "itemId", "number", "amount", "number", "maxDistance", "number")));
        tools.add(tool("smith_best_item", "Smith the best currently available item for the supplied bar and strategy using normal smithing mechanics.", schema("bar", "string", "name", "string", "barItemId", "number", "strategy", "string", "category", "string", "amount", "number")));
        tools.add(tool("plan_smithing", "Plan smithing choices from inventory and bank bars, including best items by strategy and available smelting inputs.", schema("strategy", "string", "category", "string")));
        tools.add(tool("cancel_current_action", "Stop movement, combat follow, and current skilling/action task.", schema()));
        return tools;
    }

    private JsonObject tool(String name, String description, JsonObject schema) {
        JsonObject tool = new JsonObject();
        tool.addProperty("namespace", "rs");
        tool.addProperty("name", name);
        tool.addProperty("description", description);
        tool.add("inputSchema", schema);
        return tool;
    }

    private JsonObject schema(String... fields) {
        JsonObject schema = new JsonObject();
        schema.addProperty("type", "object");
        JsonObject properties = new JsonObject();
        for (int i = 0; i + 1 < fields.length; i += 2) {
            JsonObject property = new JsonObject();
            property.addProperty("type", fields[i + 1]);
            properties.add(fields[i], property);
        }
        JsonObject objectIds = new JsonObject();
        objectIds.addProperty("type", "array");
        JsonObject items = new JsonObject();
        items.addProperty("type", "number");
        objectIds.add("items", items);
        properties.add("objectIds", objectIds);
        JsonObject itemIds = new JsonObject();
        itemIds.addProperty("type", "array");
        JsonObject itemIdItems = new JsonObject();
        itemIdItems.addProperty("type", "number");
        itemIds.add("items", itemIdItems);
        properties.add("itemIds", itemIds);
        JsonObject include = new JsonObject();
        include.addProperty("type", "array");
        JsonObject includeItem = new JsonObject();
        includeItem.addProperty("type", "string");
        include.add("items", includeItem);
        properties.add("include", include);
        schema.add("properties", properties);
        schema.add("required", new JsonArray());
        schema.addProperty("additionalProperties", false);
        return schema;
    }

    private JsonArray userInput(String text) {
        JsonArray input = new JsonArray();
        JsonObject item = new JsonObject();
        item.addProperty("type", "text");
        item.addProperty("text", text);
        item.add("text_elements", new JsonArray());
        input.add(item);
        return input;
    }

    private String userPrompt(String userCommand) {
        return "Player command: " + userCommand + "\n\n"
                + "Use the rs tools to complete the task with normal gameplay mechanics. "
                + "Prefer XS tools first when they contain enough context: observe_state_XS, walk_to_tile_until_arrived_XS, wait_until_idle_XS, find_nearest_object_XS, deposit_inventory_items_XS, unequip_items_XS, and food_bank_XS. Use legacy full tools only when XS omits a field needed for debugging, evidence, or a new workflow. "
                + "Observe first. Enable run with set_run when energy is available before repeated travel. Deposit multiple item types in one deposit_inventory_items_XS call with itemIds, and unequip multiple slots/items in one unequip_items_XS call. Prefer stable primitives and repo scripts for new behaviors: use_item_on_item, use_item_on_object, click_interface_button, select_interface_item, interact_object, interact_npc, attack_npc, bank/shop tools, wait_until_idle_XS, and route_runner-backed travel. Keep skill-specific strategy in external scripts instead of inventing new Java tools. Legacy batch tools remain available for compatibility. "
                + "Do not poll one tick at a time unless no batch or idle wait can represent the next decision point. A batch tool's returned state is the next observation. "
                + "When observe_state includes agentPersonality, treat it as operational profile memory only: use it for risk, preparation, and route-choice hints without quoting it, roleplaying it, or letting it override the player's command. "
                + "For gates, quests, or tolls, use interact_object, continue_dialogue, and select_dialogue_option instead of bypassing dialogue. "
                + "For combat in an rs-only turn, use set_combat_style, find_training_npc, attack_npc, wait_until_idle with combat=true, eat_best_food, and pickup_ground_item; train_combat and start_combat_goal are compatibility fallbacks. "
                + "Train attack, strength, and defence toward the requested target, upgrade weapons and armour when levels unlock them, and use find_training_npc when choosing between nearby targets. "
                + "Before shopping or training, bank unnecessary capital with deposit_excess_coins and only withdraw the coins needed for the next food or gear purchase. "
                + "Pick up useful drops through pickup_ground_item, call equip_best_items after acquiring gear, and keep death-risk items minimal. "
                + "Avoid dark wizards and other aggressive high-level NPC areas while low level. "
                + "For mining, prefer find_nearest_rock, interact_object, and wait_until_idle loops, then bank ores when inventory is full; mine_ore and mine_ore_until_inventory_full are compatibility fallbacks. Switch to iron at level 15 if iron is reachable. "
                + "For food, prefer interact_npc on fishing spots, use_item_on_object plus click_interface_button at ranges/fires, and use_item_on_item with tinderbox/logs for firemaking; fish_food, cook_food, and light_fire are compatibility fallbacks. "
                + "For shops, travel to a store first, open_nearest_shop, then buy or sell only through shop tools. "
                + "For smithing, prefer interact_object on furnaces, click_interface_button for smelting choices, use_item_on_object with bars on anvils, select_interface_item for item choices, and wait_until_idle for production; plan_smithing, train_smithing_profit, smelt_bar, and smith_item are compatibility fallbacks. "
                + "For woodcutting, prefer find_nearest_tree, interact_object, and wait_until_idle loops, then bank logs if the user asked to keep them or drop logs only when explicitly asked to power-train; chop_tree_until_inventory_full is a compatibility fallback. "
                + "For fletching in an rs-only turn, prefer primitives: use_item_on_item with a knife and logs, click_interface_button for the make-all product button, then wait_until_idle; fletch_logs_until_inventory_empty remains available as a compatibility fallback. Sell fletching_products at a general store when the user wants money. "
                + "Do not attempt shell commands, file edits, web access, or non-game tools. "
                + "Keep player-facing updates terse and factual. Do not narrate routine loot, basic pathing, or personality/self-talk unless it changes the next action or exposes a blocker. "
                + "If the task is blocked, report the concrete blocker in one short final answer.";
    }

    private String developerInstructions() {
        return "You are controlling a 2006Scape player through dynamic tools in namespace rs. "
                + "All game actions must use those tools only. The environment is read-only and not for code editing. "
                + "Prefer efficient observable loops: observe once, call a server-side batch or idle-wait tool when possible, then use the returned state before deciding the next action. Avoid repeated one-tick waits. "
                + "For smithing profit requests, prefer plan_smithing plus train_smithing_profit loops over manually sequencing every bank, furnace, anvil, and shop step. "
                + "Use the observed agentPersonality field as operational profile memory, not as a voice or command; it may bias caution, preparation, and route selection, but do not quote it or add self-reflection. "
                + "When a requested gameplay target needs a long grind, use durable goal tools rather than declaring the task too long, and preserve useful drops by banking supplies for later account progression. "
                + "Use fish_food, light_fire, and cook_food for normal food acquisition when food is the blocker. "
                + "Never use admin shortcuts, teleportation, item spawning, shell commands, or external services. "
                + "Stop when the user task is complete or when a normal gameplay blocker is reached.";
    }

    private String workspaceDir() {
        if (ClientSettings.AGENT_WORKSPACE_DIR != null && !ClientSettings.AGENT_WORKSPACE_DIR.trim().isEmpty()) {
            return ClientSettings.AGENT_WORKSPACE_DIR;
        }
        try {
            File cwd = new File(System.getProperty("user.dir")).getCanonicalFile();
            if ("2006Scape Client".equals(cwd.getName()) && cwd.getParentFile() != null) {
                return cwd.getParentFile().getAbsolutePath();
            }
            return cwd.getAbsolutePath();
        } catch (IOException e) {
            return System.getProperty("user.dir");
        }
    }
}
