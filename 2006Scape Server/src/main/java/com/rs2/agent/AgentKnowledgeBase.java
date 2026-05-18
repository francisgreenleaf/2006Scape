package com.rs2.agent;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import com.rs2.game.players.Player;

public class AgentKnowledgeBase {

    private static final Map<String, Landmark> LANDMARKS = new LinkedHashMap<String, Landmark>();

    static {
        add(new Landmark("lumbridge", tile(3222, 3218, 0),
                route(tile(3222, 3218, 0))));
        add(new Landmark("lumbridge goblins", tile(3252, 3236, 0), lumbridgeGoblinsRoute()));
        add(new Landmark("goblins", tile(3252, 3236, 0), lumbridgeGoblinsRoute()));
        add(new Landmark("lumbridge cows", tile(3255, 3266, 0), lumbridgeCowsRoute()));
        add(new Landmark("cows", tile(3255, 3266, 0), lumbridgeCowsRoute()));
        add(new Landmark("lumbridge trees", tile(3233, 3233, 0),
                route(tile(3222, 3218, 0), tile(3233, 3229, 0), tile(3233, 3233, 0))));
        add(new Landmark("lumbridge oaks", tile(3209, 3243, 0),
                route(tile(3222, 3218, 0), tile(3218, 3230, 0), tile(3209, 3243, 0))));
        add(new Landmark("lumbridge range", tile(3209, 3215, 0), lumbridgeRangeRoute()));
        add(new Landmark("range", tile(3209, 3215, 0), lumbridgeRangeRoute()));
        add(new Landmark("lumbridge kitchen", tile(3209, 3215, 0), lumbridgeRangeRoute()));
        add(new Landmark("lumbridge fishing spot", tile(3267, 3148, 0), lumbridgeFishingSpotRoute()));
        add(new Landmark("fishing spot", tile(3267, 3148, 0), lumbridgeFishingSpotRoute()));
        add(new Landmark("lumbridge general store", tile(3212, 3246, 0),
                route(tile(3222, 3218, 0), tile(3218, 3230, 0), tile(3212, 3246, 0))));
        add(new Landmark("general store", tile(3212, 3246, 0),
                route(tile(3222, 3218, 0), tile(3218, 3230, 0), tile(3212, 3246, 0))));
        add(new Landmark("al kharid furnace", tile(3274, 3186, 0), alKharidFurnaceRoute()));
        add(new Landmark("furnace", tile(3274, 3186, 0), alKharidFurnaceRoute()));
        add(new Landmark("varrock", tile(3210, 3424, 0), varrockRoute()));
        add(new Landmark("varrock east mine", tile(3285, 3365, 0), varrockEastMineRoute()));
        add(new Landmark("iron mine", tile(3285, 3365, 0), varrockEastMineRoute()));
        add(new Landmark("varrock east bank", tile(3256, 3418, 0), varrockEastBankRoute()));
        add(new Landmark("east bank", tile(3256, 3418, 0), varrockEastBankRoute()));
        add(new Landmark("varrock west bank", tile(3185, 3436, 0), varrockWestBankRoute()));
        add(new Landmark("west bank", tile(3185, 3436, 0), varrockWestBankRoute()));
        add(new Landmark("varrock guards", tile(3214, 3429, 0), varrockGuardsRoute()));
        add(new Landmark("varrock general store", tile(3216, 3415, 0), varrockGeneralStoreRoute()));
        add(new Landmark("varrock west anvils", tile(3188, 3425, 0), varrockWestAnvilRoute()));
        add(new Landmark("anvils", tile(3188, 3425, 0), varrockWestAnvilRoute()));
        add(new Landmark("varrock sword shop", tile(3206, 3399, 0), varrockSwordShopRoute()));
        add(new Landmark("sword shop", tile(3206, 3399, 0), varrockSwordShopRoute()));
        add(new Landmark("varrock armour shop", tile(3229, 3438, 0), varrockArmourShopRoute()));
        add(new Landmark("armour shop", tile(3229, 3438, 0), varrockArmourShopRoute()));
        add(new Landmark("barbarian village", tile(3081, 3429, 0), barbarianVillageRoute()));
        add(new Landmark("helmet shop", tile(3076, 3428, 0), barbarianVillageRoute()));
        add(new Landmark("barbarian pickaxe", tile(3081, 3429, 0), barbarianVillageRoute()));
        add(new Landmark("edgeville monastery", tile(3052, 3484, 0), edgevilleMonasteryRoute()));
        add(new Landmark("monastery", tile(3052, 3484, 0), edgevilleMonasteryRoute()));
        add(new Landmark("al kharid legs shop", tile(3315, 3175, 0), alKharidLegsShopRoute()));
        add(new Landmark("al kharid scimitar shop", tile(3289, 3189, 0), alKharidScimitarShopRoute()));
        add(new Landmark("al kharid kebab shop", tile(3275, 3180, 0), alKharidKebabShopRoute()));
        add(new Landmark("kebab shop", tile(3275, 3180, 0), alKharidKebabShopRoute()));
        add(new Landmark("karim kebabs", tile(3275, 3180, 0), alKharidKebabShopRoute()));
        add(new Landmark("falador shield shop", tile(2974, 3383, 0), faladorShieldShopRoute()));
        add(new Landmark("falador white knights", tile(2977, 3343, 0), faladorWhiteKnightsRoute()));
        add(new Landmark("white knights", tile(2977, 3343, 0), faladorWhiteKnightsRoute()));
        add(new Landmark("rock crabs", tile(2666, 3716, 0), rockCrabsRoute()));
    }

    public static Landmark findLandmark(String name) {
        if (name == null) {
            return null;
        }
        String normalized = normalize(name);
        Landmark exact = LANDMARKS.get(normalized);
        if (exact != null) {
            return exact;
        }
        for (Map.Entry<String, Landmark> entry : LANDMARKS.entrySet()) {
            if (entry.getKey().contains(normalized) || normalized.contains(entry.getKey())) {
                return entry.getValue();
            }
        }
        return null;
    }

    public static List<String> landmarkNames() {
        return new ArrayList<String>(LANDMARKS.keySet());
    }

    public static TravelStep nextTravelStep(Player player, Landmark landmark) {
        return nextTravelStep(player.absX, player.absY, player.heightLevel, landmark);
    }

    public static TravelStep nextTravelStep(int x, int y, int height, Landmark landmark) {
        Tile target = landmark.getTarget();
        if (distance(x, y, target.x, target.y) <= 4 && height == target.height) {
            return TravelStep.complete(target);
        }
        List<Tile> route = landmark.getRoute();
        if (route.isEmpty()) {
            return TravelStep.walk(target, true);
        }
        int closest = 0;
        int closestDistance = Integer.MAX_VALUE;
        for (int i = 0; i < route.size(); i++) {
            Tile tile = route.get(i);
            int distance = distance(x, y, tile.x, tile.y);
            if (distance < closestDistance || (distance == closestDistance && i > closest)) {
                closest = i;
                closestDistance = distance;
            }
        }
        int nextIndex = closestDistance <= 16 ? closest + 1 : closest;
        if (nextIndex >= route.size()) {
            nextIndex = route.size() - 1;
        }
        Tile next = route.get(nextIndex);
        boolean finalTarget = nextIndex == route.size() - 1;
        if (finalTarget && distance(x, y, next.x, next.y) <= 4 && height == next.height) {
            return TravelStep.complete(next);
        }
        return TravelStep.walk(next, finalTarget);
    }

    private static void add(Landmark landmark) {
        LANDMARKS.put(normalize(landmark.getName()), landmark);
    }

    private static String normalize(String name) {
        return name.trim().toLowerCase(Locale.ENGLISH).replace('_', ' ');
    }

    public static int distance(int x1, int y1, int x2, int y2) {
        return Math.max(Math.abs(x1 - x2), Math.abs(y1 - y2));
    }

    private static List<Tile> varrockRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0));
    }

    private static List<Tile> alKharidFurnaceRoute() {
        List<Tile> route = reverse(varrockRoute());
        route.add(tile(3239, 3218, 0));
        route.add(tile(3260, 3220, 0));
        route.add(tile(3274, 3195, 0));
        route.add(tile(3274, 3186, 0));
        return route;
    }

    private static List<Tile> lumbridgeGoblinsRoute() {
        List<Tile> route = reverse(varrockEastBankRoute());
        route.add(tile(3234, 3230, 0));
        route.add(tile(3252, 3236, 0));
        return route;
    }

    private static List<Tile> lumbridgeCowsRoute() {
        List<Tile> route = lumbridgeGoblinsRoute();
        route.add(tile(3255, 3266, 0));
        return route;
    }

    private static List<Tile> lumbridgeRangeRoute() {
        List<Tile> route = reverse(varrockEastBankRoute());
        route.add(tile(3234, 3230, 0));
        route.add(tile(3222, 3218, 0));
        route.add(tile(3209, 3215, 0));
        return route;
    }

    private static List<Tile> lumbridgeFishingSpotRoute() {
        List<Tile> route = reverse(varrockEastBankRoute());
        route.add(tile(3234, 3230, 0));
        route.add(tile(3222, 3218, 0));
        route.add(tile(3239, 3218, 0));
        route.add(tile(3260, 3220, 0));
        route.add(tile(3274, 3195, 0));
        route.add(tile(3267, 3148, 0));
        return route;
    }

    private static List<Tile> varrockEastMineRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0));
    }

    private static List<Tile> varrockEastBankRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3256, 3418, 0));
    }

    private static List<Tile> varrockWestBankRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0),
                tile(3194, 3430, 0), tile(3185, 3436, 0));
    }

    private static List<Tile> varrockGuardsRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3214, 3429, 0));
    }

    private static List<Tile> varrockGeneralStoreRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3216, 3415, 0));
    }

    private static List<Tile> varrockWestAnvilRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0),
                tile(3196, 3428, 0), tile(3188, 3425, 0));
    }

    private static List<Tile> varrockGeneralStoreRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3216, 3415, 0));
    }

    private static List<Tile> varrockSwordShopRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0),
                tile(3206, 3399, 0));
    }

    private static List<Tile> varrockArmourShopRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3229, 3438, 0));
    }

    private static List<Tile> barbarianVillageRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0),
                tile(3194, 3430, 0), tile(3190, 3430, 0), tile(3186, 3430, 0),
                tile(3182, 3430, 0), tile(3178, 3430, 0), tile(3174, 3430, 0),
                tile(3170, 3430, 0), tile(3166, 3430, 0), tile(3162, 3428, 0),
                tile(3158, 3426, 0), tile(3154, 3426, 0), tile(3148, 3429, 0),
                tile(3140, 3429, 0), tile(3132, 3429, 0), tile(3124, 3429, 0),
                tile(3116, 3429, 0), tile(3110, 3422, 0), tile(3100, 3424, 0),
                tile(3092, 3429, 0), tile(3081, 3429, 0));
    }

    private static List<Tile> edgevilleMonasteryRoute() {
        List<Tile> route = new ArrayList<Tile>(barbarianVillageRoute());
        route.add(tile(3078, 3440, 0));
        route.add(tile(3068, 3455, 0));
        route.add(tile(3059, 3472, 0));
        route.add(tile(3052, 3484, 0));
        return route;
    }

    private static List<Tile> alKharidLegsShopRoute() {
        return route(tile(3222, 3218, 0), tile(3239, 3218, 0), tile(3260, 3220, 0),
                tile(3274, 3195, 0), tile(3289, 3189, 0), tile(3315, 3175, 0));
    }

    private static List<Tile> alKharidScimitarShopRoute() {
        return route(tile(3222, 3218, 0), tile(3239, 3218, 0), tile(3260, 3220, 0),
                tile(3274, 3195, 0), tile(3289, 3189, 0));
    }

    private static List<Tile> alKharidKebabShopRoute() {
        List<Tile> route = reverse(barbarianVillageRoute());
        route.add(tile(3239, 3218, 0));
        route.add(tile(3260, 3220, 0));
        route.add(tile(3274, 3195, 0));
        route.add(tile(3275, 3180, 0));
        return route;
    }

    private static List<Tile> faladorShieldShopRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0),
                tile(3194, 3430, 0), tile(3190, 3430, 0), tile(3186, 3430, 0),
                tile(3182, 3430, 0), tile(3178, 3430, 0), tile(3174, 3430, 0),
                tile(3170, 3430, 0), tile(3166, 3430, 0), tile(3162, 3428, 0),
                tile(3158, 3426, 0), tile(3154, 3426, 0), tile(3148, 3429, 0),
                tile(3140, 3429, 0), tile(3132, 3429, 0), tile(3124, 3429, 0),
                tile(3116, 3429, 0), tile(3110, 3422, 0), tile(3100, 3424, 0),
                tile(3092, 3429, 0),
                tile(3076, 3428, 0), tile(3040, 3428, 0), tile(3005, 3404, 0),
                tile(2974, 3383, 0));
    }

    private static List<Tile> faladorWhiteKnightsRoute() {
        List<Tile> route = new ArrayList<Tile>(faladorShieldShopRoute());
        route.add(tile(2974, 3365, 0));
        route.add(tile(2977, 3343, 0));
        return route;
    }

    private static List<Tile> rockCrabsRoute() {
        List<Tile> route = new ArrayList<Tile>(edgevilleMonasteryRoute());
        route.add(tile(3038, 3489, 0));
        route.add(tile(3018, 3510, 0));
        route.add(tile(3005, 3512, 0));
        route.add(tile(2980, 3505, 0));
        route.add(tile(2948, 3492, 0));
        route.add(tile(2902, 3490, 0));
        route.add(tile(2848, 3490, 0));
        route.add(tile(2806, 3434, 0));
        route.add(tile(2740, 3480, 0));
        route.add(tile(2720, 3540, 0));
        route.add(tile(2700, 3608, 0));
        route.add(tile(2672, 3668, 0));
        route.add(tile(2666, 3716, 0));
        return route;
    }

    private static Tile tile(int x, int y, int height) {
        return new Tile(x, y, height);
    }

    private static List<Tile> route(Tile... tiles) {
        ArrayList<Tile> route = new ArrayList<Tile>();
        Collections.addAll(route, tiles);
        return route;
    }

    private static List<Tile> reverse(List<Tile> tiles) {
        ArrayList<Tile> route = new ArrayList<Tile>(tiles);
        Collections.reverse(route);
        return route;
    }

    public static class Landmark {
        private final String name;
        private final Tile target;
        private final List<Tile> route;

        public Landmark(String name, Tile target, List<Tile> route) {
            this.name = name;
            this.target = target;
            this.route = route;
        }

        public String getName() {
            return name;
        }

        public Tile getTarget() {
            return target;
        }

        public List<Tile> getRoute() {
            return route;
        }
    }

    public static class Tile {
        public final int x;
        public final int y;
        public final int height;

        public Tile(int x, int y, int height) {
            this.x = x;
            this.y = y;
            this.height = height;
        }
    }

    public static class TravelStep {
        private final boolean complete;
        private final Tile tile;
        private final boolean finalTarget;

        private TravelStep(boolean complete, Tile tile, boolean finalTarget) {
            this.complete = complete;
            this.tile = tile;
            this.finalTarget = finalTarget;
        }

        public static TravelStep complete(Tile tile) {
            return new TravelStep(true, tile, true);
        }

        public static TravelStep walk(Tile tile, boolean finalTarget) {
            return new TravelStep(false, tile, finalTarget);
        }

        public boolean isComplete() {
            return complete;
        }

        public Tile getTile() {
            return tile;
        }

        public boolean isFinalTarget() {
            return finalTarget;
        }
    }
}
