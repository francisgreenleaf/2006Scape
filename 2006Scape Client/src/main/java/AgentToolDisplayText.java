import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

public final class AgentToolDisplayText {

    private static final String FALLBACK_ACTION = "working...";
    private static final Map<String, String> ACTIONS = createActions();

    private AgentToolDisplayText() {
    }

    public static String actionFor(String tool) {
        String normalized = normalizeToolName(tool);
        String action = ACTIONS.get(normalized);
        return action == null ? FALLBACK_ACTION : action;
    }

    public static String progressFor(String tool) {
        String action = actionFor(tool);
        if (action.length() == 0) {
            return "";
        }
        return Character.toUpperCase(action.charAt(0)) + action.substring(1);
    }

    public static boolean hasActionFor(String tool) {
        return ACTIONS.containsKey(normalizeToolName(tool));
    }

    public static Map<String, String> actionsForTests() {
        return ACTIONS;
    }

    private static String normalizeToolName(String tool) {
        if (tool == null) {
            return "";
        }
        String cleaned = tool.trim();
        if (cleaned.startsWith("rs.")) {
            return cleaned.substring(3);
        }
        return cleaned;
    }

    private static Map<String, String> createActions() {
        Map<String, String> actions = new HashMap<String, String>();
        put(actions, "observe_state_XXS", "checking status...");
        put(actions, "observe_state_XS", "checking surroundings...");
        put(actions, "observe_state_if_changed_XXS", "checking for changes...");
        put(actions, "observe_state_if_changed_XS", "checking for changes...");
        put(actions, "combat_state_XXS", "checking combat...");
        put(actions, "combat_state_XS", "checking combat...");
        put(actions, "observe_state", "checking details...");
        put(actions, "continue_dialogue", "continuing dialogue...");
        put(actions, "select_dialogue_option", "choosing reply...");
        put(actions, "close_interfaces", "closing interface...");
        put(actions, "agent_chat_send_XS", "sending message...");
        put(actions, "agent_chat_read_XS", "reading messages...");
        put(actions, "agent_chat_status_XS", "checking messages...");
        put(actions, "set_run", "setting run...");
        put(actions, "set_run_XXS", "setting run...");
        put(actions, "use_item_on_item", "using items...");
        put(actions, "use_item_on_object", "using item...");
        put(actions, "use_inventory_item", "using inventory...");
        put(actions, "click_interface_button", "clicking button...");
        put(actions, "click_interface_button_XXS", "clicking button...");
        put(actions, "trade_status_XS", "checking trade...");
        put(actions, "request_player_trade_XS", "requesting trade...");
        put(actions, "offer_trade_item_XS", "offering item...");
        put(actions, "accept_trade_XS", "accepting trade...");
        put(actions, "select_interface_item", "selecting item...");
        put(actions, "preview_local_path", "checking path...");
        put(actions, "walk_to_tile", "walking...");
        put(actions, "walk_path_steps", "following path...");
        put(actions, "walk_path_steps_XXS", "following path...");
        put(actions, "walk_path_steps_XS", "following path...");
        put(actions, "walk_to_tile_until_arrived", "walking...");
        put(actions, "walk_to_tile_until_arrived_XXS", "walking...");
        put(actions, "walk_to_tile_until_arrived_XS", "walking...");
        put(actions, "travel_to_landmark", "traveling...");
        put(actions, "travel_to_landmark_until_arrived", "traveling...");
        put(actions, "travel_to_landmark_until_arrived_XXS", "traveling...");
        put(actions, "travel_to_landmark_until_arrived_XS", "traveling...");
        put(actions, "wait_ticks", "waiting...");
        put(actions, "wait_ticks_XXS", "waiting...");
        put(actions, "wait_ticks_XS", "waiting...");
        put(actions, "wait_until_idle", "waiting to finish...");
        put(actions, "wait_until_idle_XXS", "waiting to finish...");
        put(actions, "wait_until_idle_XS", "waiting to finish...");
        put(actions, "wait_until_combat_event_XXS", "watching combat...");
        put(actions, "wait_until_combat_event_XS", "watching combat...");
        put(actions, "wait_until_combat_event_smart_XXS", "watching combat...");
        put(actions, "wait_until_combat_event_smart_XS", "watching combat...");
        put(actions, "find_nearest_npc", "finding npc...");
        put(actions, "find_training_npc", "finding target...");
        put(actions, "interact_npc", "talking to npc...");
        put(actions, "attack_npc", "attacking...");
        put(actions, "attack_npc_XXS", "attacking...");
        put(actions, "cast_spell_on_npc", "casting spell...");
        put(actions, "cast_spell_on_npc_XS", "casting spell...");
        put(actions, "cast_spell_on_npc_XXS", "casting spell...");
        put(actions, "find_nearest_object", "finding object...");
        put(actions, "find_nearest_object_XS", "finding object...");
        put(actions, "find_nearest_rock", "finding rock...");
        put(actions, "find_nearest_tree", "finding tree...");
        put(actions, "set_combat_style", "setting combat style...");
        put(actions, "set_combat_style_XXS", "setting combat style...");
        put(actions, "equip_item", "equipping item...");
        put(actions, "unequip_item", "unequipping item...");
        put(actions, "unequip_items_XXS", "unequipping items...");
        put(actions, "unequip_items_XS", "unequipping items...");
        put(actions, "unequip_item_XS", "unequipping item...");
        put(actions, "eat_item", "eating...");
        put(actions, "eat_best_food", "eating food...");
        put(actions, "eat_best_food_XXS", "eating food...");
        put(actions, "bury_bones", "burying bones...");
        put(actions, "bury_bones_XXS", "burying bones...");
        put(actions, "bury_bones_XS", "burying bones...");
        put(actions, "pickup_ground_item", "picking up item...");
        put(actions, "pickup_ground_item_XXS", "picking up item...");
        put(actions, "open_nearest_shop", "opening shop...");
        put(actions, "buy_shop_item", "buying item...");
        put(actions, "sell_inventory_item", "selling item...");
        put(actions, "sell_inventory_items", "selling items...");
        put(actions, "interact_object", "using object...");
        put(actions, "interact_object_XXS", "using object...");
        put(actions, "interact_object_XS", "using object...");
        put(actions, "object_transition_step_XXS", "passing obstacle...");
        put(actions, "object_transition_step_XS", "passing obstacle...");
        put(actions, "drop_inventory_items", "dropping items...");
        put(actions, "deposit_inventory_items", "depositing items...");
        put(actions, "deposit_inventory_items_XXS", "depositing items...");
        put(actions, "deposit_inventory_items_XS", "depositing items...");
        put(actions, "withdraw_bank_items", "withdrawing items...");
        put(actions, "withdraw_bank_items_XXS", "withdrawing items...");
        put(actions, "withdraw_bank_items_XS", "withdrawing items...");
        put(actions, "bank_item_count_XS", "checking bank...");
        put(actions, "food_bank_XXS", "checking supplies...");
        put(actions, "food_bank_XS", "checking supplies...");
        put(actions, "deposit_excess_coins", "banking coins...");
        put(actions, "deposit_excess_coins_XXS", "banking coins...");
        put(actions, "cancel_current_action", "stopping...");
        return Collections.unmodifiableMap(actions);
    }

    private static void put(Map<String, String> actions, String tool, String action) {
        actions.put(tool, action);
    }
}
