package com.rs2.agent;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

import com.rs2.Constants;
import com.rs2.game.items.DeprecatedItems;

public class AgentCombatPlanner {

    public static final int TARGET_MELEE_LEVEL = 50;

    private static final int COINS = 995;

    private static final int[][] WEAPON_TIERS = {
            {1, 1279},   // iron sword
            {5, 1281},   // steel sword
            {20, 1285},  // mithril sword
            {30, 1287},  // adamant sword
            {40, 1291}   // rune sword
    };

    private static final int[][] ARMOUR_TIERS = {
            {1, 1115, 1067, 1173},   // iron chainbody, platelegs, sq shield
            {5, 1105, 1069, 1175},   // steel chainbody, platelegs, sq shield
            {20, 1121, 1071, 1181},  // mithril chainbody, platelegs, sq shield
            {30, 1123, 1073, 1183},  // adamant chainbody, platelegs, sq shield
            {40, 1113, 1079, 1185}   // rune chainbody, platelegs, sq shield
    };

    private static final TrainingArea[] TRAINING_AREAS = {
            new TrainingArea("lumbridge cows", "lumbridge cows", "Cow", 1, 8, 1, 1, 12),
            new TrainingArea("lumbridge goblins", "lumbridge goblins", "Goblin", 1, 13, 2, 1, 18),
            new TrainingArea("barbarian village", "barbarian village", "Barbarian", 12, 18, 3, 10, 28),
            new TrainingArea("varrock guards", "varrock guards", "Guard", 22, 22, 6, 20, 38),
            new TrainingArea("falador white knights", "falador white knights", "White Knight", 52, 60, 8, 35, 50),
            new TrainingArea("rock crabs", "rock crabs", "Rock Crab", 50, 50, 2, 20, 50)
    };

    public static String nextTrainingStyle(int attackLevel, int strengthLevel, int defenceLevel, int targetLevel) {
        if (attackLevel >= targetLevel && strengthLevel >= targetLevel && defenceLevel >= targetLevel) {
            return "complete";
        }
        int nextWeaponUnlock = nextWeaponUnlock(attackLevel);
        int levelsToWeaponUnlock = nextWeaponUnlock - attackLevel;
        if (attackLevel < targetLevel && nextWeaponUnlock < targetLevel
                && (levelsToWeaponUnlock <= 2 || attackLevel <= strengthLevel + 5)) {
            return "attack";
        }
        if (strengthLevel < targetLevel && strengthLevel <= attackLevel + 3
                && strengthLevel <= defenceLevel + 8) {
            return "strength";
        }
        if (defenceLevel < targetLevel && defenceLevel + 5 < Math.min(attackLevel, strengthLevel)) {
            return "defence";
        }
        int bestSkill = Constants.ATTACK;
        int bestLevel = attackLevel;
        if (strengthLevel < bestLevel) {
            bestSkill = Constants.STRENGTH;
            bestLevel = strengthLevel;
        }
        if (defenceLevel < bestLevel) {
            bestSkill = Constants.DEFENCE;
        }
        if (bestSkill == Constants.STRENGTH) {
            return "strength";
        }
        if (bestSkill == Constants.DEFENCE) {
            return "defence";
        }
        return "attack";
    }

    public static TrainingArea recommendedArea(int attackLevel, int strengthLevel, int defenceLevel, int hitpointsLevel,
            int foodCount) {
        int meleeAverage = (attackLevel + strengthLevel + defenceLevel) / 3;
        if (meleeAverage >= 30 && hitpointsLevel >= 35 && foodCount >= 8) {
            return findArea("rock crabs");
        }
        if (meleeAverage >= 35 && hitpointsLevel >= 35 && foodCount >= 8) {
            return findArea("falador white knights");
        }
        if (meleeAverage >= 22 && foodCount >= 4) {
            return findArea("varrock guards");
        }
        if (meleeAverage >= 12) {
            return findArea("barbarian village");
        }
        if (meleeAverage >= 6) {
            return findArea("lumbridge goblins");
        }
        return findArea("lumbridge cows");
    }

    public static List<TrainingArea> trainingAreas() {
        ArrayList<TrainingArea> areas = new ArrayList<TrainingArea>();
        Collections.addAll(areas, TRAINING_AREAS);
        return areas;
    }

    public static TrainingArea findArea(String name) {
        String normalized = normalize(name);
        for (TrainingArea area : TRAINING_AREAS) {
            if (normalize(area.getName()).equals(normalized) || normalize(area.getLandmark()).equals(normalized)) {
                return area;
            }
        }
        for (TrainingArea area : TRAINING_AREAS) {
            if (normalize(area.getName()).contains(normalized) || normalized.contains(normalize(area.getName()))) {
                return area;
            }
        }
        return TRAINING_AREAS[0];
    }

    public static int eatAtHitpoints(int maxHitpoints) {
        return Math.max(8, (maxHitpoints * 45) / 100);
    }

    public static int retreatAtHitpoints(int maxHitpoints) {
        return Math.max(5, (maxHitpoints * 30) / 100);
    }

    public static int recommendedCoinBudget(int attackLevel, int defenceLevel, int foodCount) {
        int budget = 2000;
        if (attackLevel >= 40 || defenceLevel >= 40) {
            budget = 50000;
        } else if (attackLevel >= 30 || defenceLevel >= 30) {
            budget = 20000;
        } else if (attackLevel >= 20 || defenceLevel >= 20) {
            budget = 10000;
        }
        if (foodCount < 8) {
            budget += 3000;
        }
        return budget;
    }

    public static int scoreNpc(String name, int npcHitpoints, int npcCombatLevel, int npcMaxHit, int npcAttack,
            int npcDefence, int playerCombatLevel, int playerHitpointsLevel, int distance, boolean underAttack) {
        if (npcHitpoints <= 0) {
            return Integer.MIN_VALUE;
        }
        String normalizedName = normalize(name);
        if (isKnownBadTrainingTarget(normalizedName)) {
            return Integer.MIN_VALUE / 2;
        }
        int score = npcHitpoints * 10;
        score -= Math.max(0, npcMaxHit) * 35;
        score -= Math.max(0, npcDefence) / 3;
        score -= Math.max(0, npcAttack - playerCombatLevel) * 2;
        score -= Math.max(0, npcCombatLevel - playerCombatLevel - 8) * 10;
        score -= Math.max(0, npcMaxHit - Math.max(2, playerHitpointsLevel / 5)) * 40;
        score -= Math.max(0, distance) * 2;
        if (underAttack) {
            score -= 120;
        }
        if (normalizedName.contains("rock crab")) {
            score += 160;
        }
        if (normalizedName.contains("experiment")) {
            score += 120;
        }
        if (normalizedName.contains("white knight")) {
            score += 50;
        }
        if (normalizedName.contains("guard")) {
            score += 20;
        }
        return score;
    }

    public static int nextWeaponUnlock(int attackLevel) {
        if (attackLevel < 5) {
            return 5;
        }
        if (attackLevel < 20) {
            return 20;
        }
        if (attackLevel < 30) {
            return 30;
        }
        if (attackLevel < 40) {
            return 40;
        }
        return TARGET_MELEE_LEVEL;
    }

    public static int recommendedWeaponId(int attackLevel) {
        return bestTierItem(WEAPON_TIERS, attackLevel, 1);
    }

    public static int recommendedBodyId(int defenceLevel) {
        return bestTierItem(ARMOUR_TIERS, defenceLevel, 1);
    }

    public static int recommendedLegsId(int defenceLevel) {
        return bestTierItem(ARMOUR_TIERS, defenceLevel, 2);
    }

    public static int recommendedShieldId(int defenceLevel) {
        return bestTierItem(ARMOUR_TIERS, defenceLevel, 3);
    }

    public static int coinsItemId() {
        return COINS;
    }

    public static String itemName(int itemId) {
        return itemId < 0 ? "" : DeprecatedItems.getItemName(itemId);
    }

    private static int bestTierItem(int[][] tiers, int level, int column) {
        int itemId = -1;
        for (int i = 0; i < tiers.length; i++) {
            if (level >= tiers[i][0]) {
                itemId = tiers[i][column];
            }
        }
        return itemId;
    }

    private static boolean isKnownBadTrainingTarget(String normalizedName) {
        return normalizedName.contains("dark wizard")
                || normalizedName.contains("khazard guard")
                || normalizedName.contains("dagannoth")
                || normalizedName.contains("cave slime")
                || normalizedName.contains("poison spider")
                || normalizedName.contains("scorpion king")
                || normalizedName.contains("kalphite");
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ENGLISH).replace('_', ' ');
    }

    public static class TrainingArea {
        private final String name;
        private final String landmark;
        private final String npcName;
        private final int typicalHitpoints;
        private final int highHitpoints;
        private final int maxHit;
        private final int recommendedMeleeLevel;
        private final int recommendedUntilLevel;

        private TrainingArea(String name, String landmark, String npcName, int typicalHitpoints, int highHitpoints,
                int maxHit, int recommendedMeleeLevel, int recommendedUntilLevel) {
            this.name = name;
            this.landmark = landmark;
            this.npcName = npcName;
            this.typicalHitpoints = typicalHitpoints;
            this.highHitpoints = highHitpoints;
            this.maxHit = maxHit;
            this.recommendedMeleeLevel = recommendedMeleeLevel;
            this.recommendedUntilLevel = recommendedUntilLevel;
        }

        public String getName() {
            return name;
        }

        public String getLandmark() {
            return landmark;
        }

        public String getNpcName() {
            return npcName;
        }

        public int getTypicalHitpoints() {
            return typicalHitpoints;
        }

        public int getHighHitpoints() {
            return highHitpoints;
        }

        public int getMaxHit() {
            return maxHit;
        }

        public int getRecommendedMeleeLevel() {
            return recommendedMeleeLevel;
        }

        public int getRecommendedUntilLevel() {
            return recommendedUntilLevel;
        }
    }
}
