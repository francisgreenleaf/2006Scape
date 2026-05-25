package com.rs2.game.content.custom;

import com.rs2.game.players.Player;

public final class CustomQuestState {

    private CustomQuestState() {
    }

    public static int get(Player player, String questKey) {
        Integer stage = player.customQuestStages.get(questKey);
        return stage == null ? 0 : stage;
    }

    public static void set(Player player, String questKey, int stage) {
        player.customQuestStages.put(questKey, stage);
    }
}
