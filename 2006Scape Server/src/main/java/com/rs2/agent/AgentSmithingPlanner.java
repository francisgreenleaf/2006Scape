package com.rs2.agent;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import com.rs2.game.content.skills.smithing.SmithingData;
import com.rs2.game.items.DeprecatedItems;

public class AgentSmithingPlanner {

    public enum Strategy {
        XP_PER_BAR,
        XP_PER_ACTION,
        HIGHEST_QUALITY
    }

    public static SmithingChoice bestSmithableItem(int smithingLevel, int barItemId, int availableBars, Strategy strategy) {
        return bestSmithableItem(smithingLevel, barItemId, availableBars, strategy, "");
    }

    public static SmithingChoice bestSmithableItem(int smithingLevel, int barItemId, int availableBars, Strategy strategy,
            String category) {
        SmithingChoice best = null;
        for (SmithingData data : SmithingData.values()) {
            if (requiredBarForItem(data.getId()) != barItemId) {
                continue;
            }
            if (data.getLvl() > smithingLevel || data.getAmount() > availableBars) {
                continue;
            }
            if (!matchesCategory(data, category)) {
                continue;
            }
            SmithingChoice choice = new SmithingChoice(data);
            if (best == null || isBetter(choice, best, strategy)) {
                best = choice;
            }
        }
        return best;
    }

    public static List<SmithingChoice> smithableItems(int smithingLevel, int barItemId, int availableBars) {
        return smithableItems(smithingLevel, barItemId, availableBars, "");
    }

    public static List<SmithingChoice> smithableItems(int smithingLevel, int barItemId, int availableBars,
            String category) {
        ArrayList<SmithingChoice> choices = new ArrayList<SmithingChoice>();
        for (SmithingData data : SmithingData.values()) {
            if (requiredBarForItem(data.getId()) == barItemId
                    && data.getLvl() <= smithingLevel
                    && data.getAmount() <= availableBars
                    && matchesCategory(data, category)) {
                choices.add(new SmithingChoice(data));
            }
        }
        return choices;
    }

    public static Strategy strategy(String value) {
        String normalized = normalize(value);
        if ("xp per action".equals(normalized) || "action xp".equals(normalized) || "total xp".equals(normalized)) {
            return Strategy.XP_PER_ACTION;
        }
        if ("highest quality".equals(normalized) || "highest level".equals(normalized)
                || "best quality".equals(normalized) || "quality".equals(normalized)) {
            return Strategy.HIGHEST_QUALITY;
        }
        return Strategy.XP_PER_BAR;
    }

    public static int barItemId(String name) {
        String normalized = normalize(name);
        if (normalized.endsWith(" bar")) {
            normalized = normalized.substring(0, normalized.length() - 4);
        }
        if ("mith".equals(normalized)) {
            normalized = "mithril";
        } else if ("addy".equals(normalized)) {
            normalized = "adamant";
        } else if ("runite".equals(normalized)) {
            normalized = "rune";
        }
        if ("bronze".equals(normalized)) {
            return 2349;
        }
        if ("iron".equals(normalized)) {
            return 2351;
        }
        if ("steel".equals(normalized)) {
            return 2353;
        }
        if ("mithril".equals(normalized)) {
            return 2359;
        }
        if ("adamant".equals(normalized)) {
            return 2361;
        }
        if ("rune".equals(normalized)) {
            return 2363;
        }
        return -1;
    }

    public static int requiredBarForItem(int itemId) {
        SmithingData data = SmithingData.forId(itemId);
        if (data == null) {
            return -1;
        }
        String name = data.name();
        if (name.startsWith("BRONZE_")) {
            return 2349;
        }
        if (name.startsWith("IRON_")) {
            return 2351;
        }
        if (name.startsWith("STEEL_")) {
            return 2353;
        }
        if (name.startsWith("MITH_")) {
            return 2359;
        }
        if (name.startsWith("ADDY_")) {
            return 2361;
        }
        if (name.startsWith("RUNE_")) {
            return 2363;
        }
        return -1;
    }

    public static boolean isSmithingProduct(int itemId) {
        return SmithingData.forId(itemId) != null;
    }

    private static boolean matchesCategory(SmithingData data, String category) {
        String normalized = normalize(category);
        if (normalized.isEmpty() || "any".equals(normalized) || "all".equals(normalized)) {
            return true;
        }
        String name = data.name();
        if ("armor".equals(normalized) || "armour".equals(normalized)) {
            return name.contains("_MED") || name.contains("_FULL") || name.contains("_HELM")
                    || name.contains("_SQ") || name.contains("_CHAIN") || name.contains("_KITE")
                    || name.contains("_LEGS") || name.contains("_SKIRT") || name.contains("_BODY")
                    || name.contains("_PLATE");
        }
        if ("weapon".equals(normalized) || "weapons".equals(normalized)) {
            return name.contains("_DAGGER") || name.contains("_MACE") || name.contains("_SWORD")
                    || name.contains("_SCIM") || name.contains("_LONG") || name.contains("_BATTLE")
                    || name.contains("_2H") || name.contains("_AXE");
        }
        return true;
    }

    private static boolean isBetter(SmithingChoice candidate, SmithingChoice current, Strategy strategy) {
        if (strategy == Strategy.HIGHEST_QUALITY) {
            if (candidate.getRequiredLevel() != current.getRequiredLevel()) {
                return candidate.getRequiredLevel() > current.getRequiredLevel();
            }
            if (candidate.getBarsNeeded() != current.getBarsNeeded()) {
                return candidate.getBarsNeeded() > current.getBarsNeeded();
            }
        }
        int candidatePrimary = strategy == Strategy.XP_PER_ACTION ? candidate.getXp() : candidate.getXpPerThousandBars();
        int currentPrimary = strategy == Strategy.XP_PER_ACTION ? current.getXp() : current.getXpPerThousandBars();
        if (candidatePrimary != currentPrimary) {
            return candidatePrimary > currentPrimary;
        }
        if (candidate.getRequiredLevel() != current.getRequiredLevel()) {
            return candidate.getRequiredLevel() > current.getRequiredLevel();
        }
        if (candidate.getXp() != current.getXp()) {
            return candidate.getXp() > current.getXp();
        }
        return candidate.getBarsNeeded() > current.getBarsNeeded();
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ENGLISH).replace('_', ' ');
    }

    public static class SmithingChoice {
        private final SmithingData data;

        private SmithingChoice(SmithingData data) {
            this.data = data;
        }

        public int getItemId() {
            return data.getId();
        }

        public String getItemName() {
            return DeprecatedItems.getItemName(data.getId());
        }

        public int getXp() {
            return data.getXp();
        }

        public int getRequiredLevel() {
            return data.getLvl();
        }

        public int getBarsNeeded() {
            return data.getAmount();
        }

        public int getXpPerThousandBars() {
            return (data.getXp() * 1000) / Math.max(1, data.getAmount());
        }
    }
}
