package com.rs2.agent;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import com.rs2.game.players.Player;

public class AgentKnowledgeBase {

    private static final int DEFAULT_ARRIVAL_RADIUS = 4;
    private static final int BANK_ARRIVAL_RADIUS = 1;
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
        add(new Landmark("lumbridge axe shop", tile(3231, 3203, 0), lumbridgeAxeShopRoute()));
        add(new Landmark("bob axes", tile(3231, 3203, 0), lumbridgeAxeShopRoute()));
        add(new Landmark("bob's axes", tile(3231, 3203, 0), lumbridgeAxeShopRoute()));
        add(new Landmark("al kharid furnace", tile(3274, 3186, 0), alKharidFurnaceRoute()));
        add(new Landmark("furnace", tile(3274, 3186, 0), alKharidFurnaceRoute()));
        add(new Landmark("al kharid bank", tile(3269, 3167, 0), alKharidBankRoute(), BANK_ARRIVAL_RADIUS));
        add(new Landmark("al kharid general store", tile(3313, 3183, 0), alKharidGeneralStoreRoute()));
        add(new Landmark("al kharid store", tile(3313, 3183, 0), alKharidGeneralStoreRoute()));
        add(new Landmark("varrock", tile(3210, 3424, 0), varrockRoute()));
        add(new Landmark("varrock east mine", tile(3285, 3365, 0), varrockEastMineRoute()));
        add(new Landmark("iron mine", tile(3285, 3365, 0), varrockEastMineRoute()));
        add(new Landmark("varrock east coal mine", tile(3302, 3317, 0), varrockEastCoalMineRoute()));
        add(new Landmark("coal mine", tile(3302, 3317, 0), varrockEastCoalMineRoute()));
        add(new Landmark("varrock east bank", tile(3253, 3420, 0), varrockEastBankRoute(), BANK_ARRIVAL_RADIUS));
        add(new Landmark("east bank", tile(3253, 3420, 0), varrockEastBankRoute(), BANK_ARRIVAL_RADIUS));
        add(new Landmark("varrock west bank", tile(3185, 3436, 0), varrockWestBankRoute(), BANK_ARRIVAL_RADIUS));
        add(new Landmark("west bank", tile(3185, 3436, 0), varrockWestBankRoute(), BANK_ARRIVAL_RADIUS));
        add(new Landmark("varrock guards", tile(3210, 3424, 0), varrockGuardsRoute()));
        add(new Landmark("varrock general store", tile(3216, 3415, 0), varrockGeneralStoreRoute()));
        add(new Landmark("varrock west anvils", tile(3188, 3425, 0), varrockWestAnvilRoute()));
        add(new Landmark("anvils", tile(3188, 3425, 0), varrockWestAnvilRoute()));
        add(new Landmark("varrock sword shop", tile(3206, 3399, 0), varrockSwordShopRoute()));
        add(new Landmark("sword shop", tile(3206, 3399, 0), varrockSwordShopRoute()));
        add(new Landmark("varrock armour shop", tile(3229, 3438, 0), varrockArmourShopRoute()));
        add(new Landmark("armour shop", tile(3229, 3438, 0), varrockArmourShopRoute()));
        add(new Landmark("champions guild stairs", tile(3191, 3363, 0), championsGuildStairsRoute()));
        add(new Landmark("champions guild rune store", tile(3192, 3358, 1), championsGuildRuneStoreRoute()));
        add(new Landmark("scavvo rune store", tile(3192, 3358, 1), championsGuildRuneStoreRoute()));
        add(new Landmark("scavvo", tile(3192, 3358, 1), championsGuildRuneStoreRoute()));
        add(new Landmark("barbarian village", tile(3081, 3429, 0), barbarianVillageRoute()));
        add(new Landmark("helmet shop", tile(3076, 3428, 0), barbarianVillageRoute()));
        add(new Landmark("barbarian pickaxe", tile(3081, 3429, 0), barbarianVillageRoute()));
        add(new Landmark("dwarven mine ladder", tile(3024, 3450, 0), dwarvenMineLadderRoute()));
        add(new Landmark("dwarven mine trapdoor", tile(3024, 3450, 0), dwarvenMineLadderRoute()));
        add(new Landmark("dwarven mine north ladder underground", tile(3077, 9893, 0),
                dwarvenMineNorthUndergroundLadderRoute()));
        add(new Landmark("dwarven mine trapdoor underground", tile(3020, 9850, 0),
                dwarvenMineTrapdoorUndergroundRoute()));
        add(new Landmark("pickaxe shop", tile(2998, 9843, 0), nurmofPickaxeShopRoute()));
        add(new Landmark("nurmof pickaxe shop", tile(2998, 9843, 0), nurmofPickaxeShopRoute()));
        add(new Landmark("tati pickaxe shop", tile(2923, 10211, 0), route(tile(2923, 10211, 0))));
        add(new Landmark("edgeville monastery", tile(3052, 3484, 0), edgevilleMonasteryRoute()));
        add(new Landmark("monastery", tile(3052, 3484, 0), edgevilleMonasteryRoute()));
        add(new Landmark("al kharid legs shop", tile(3315, 3175, 0), alKharidLegsShopRoute()));
        add(new Landmark("al kharid scimitar shop", tile(3289, 3189, 0), alKharidScimitarShopRoute()));
        add(new Landmark("al kharid kebab shop", tile(3275, 3180, 0), alKharidKebabShopRoute()));
        add(new Landmark("kebab shop", tile(3275, 3180, 0), alKharidKebabShopRoute()));
        add(new Landmark("karim kebabs", tile(3275, 3180, 0), alKharidKebabShopRoute()));
        add(new Landmark("shantay pass", tile(3303, 3124, 0), shantayPassRoute()));
        add(new Landmark("shantay gate north", tile(3304, 3117, 0), shantayGateNorthRoute()));
        add(new Landmark("shantay rug merchant", tile(3311, 3109, 0), shantayRugMerchantRoute()));
        add(new Landmark("nardah adventurer store", tile(3407, 2921, 0), nardahAdventurerStoreRoute()));
        add(new Landmark("seddu adventurer store", tile(3407, 2921, 0), nardahAdventurerStoreRoute()));
        add(new Landmark("oziach rune armour", tile(3069, 3517, 0), oziachRuneArmourRoute()));
        add(new Landmark("oziach", tile(3069, 3517, 0), oziachRuneArmourRoute()));
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
        if (distance(x, y, target.x, target.y) <= landmark.getArrivalRadius() && height == target.height) {
            return TravelStep.complete(target);
        }
        List<Tile> route = landmark.getRoute();
        if (route.isEmpty()) {
            return TravelStep.walk(target, true);
        }
        Tile alKharidGateApproach = alKharidGateApproachRecovery(x, y, height, route);
        if (alKharidGateApproach != null) {
            return TravelStep.walk(alKharidGateApproach, false);
        }
        Tile alKharidGateReturn = alKharidGateReturnRecovery(x, y, height, route);
        if (alKharidGateReturn != null) {
            return TravelStep.walk(alKharidGateReturn, false);
        }
        Tile lumbridgeCowRecovery = lumbridgeCowRouteRecovery(x, y, height, route);
        if (lumbridgeCowRecovery != null) {
            return TravelStep.walk(lumbridgeCowRecovery, false);
        }
        Tile trapRecovery = alKharidNorthTrapRecovery(x, y, height, route);
        if (trapRecovery != null) {
            return TravelStep.walk(trapRecovery, false);
        }
        Tile alKharidSouthboundRoadRecovery = alKharidSouthboundRoadRecovery(x, y, height, route);
        if (alKharidSouthboundRoadRecovery != null) {
            return TravelStep.walk(alKharidSouthboundRoadRecovery, false);
        }
        Tile alKharidNorthConnectorRecovery = alKharidNorthConnectorRecovery(x, y, height, route);
        if (alKharidNorthConnectorRecovery != null) {
            return TravelStep.walk(alKharidNorthConnectorRecovery, false);
        }
        Tile alKharidRoadRecovery = alKharidNorthRoadRecovery(x, y, height, route);
        if (alKharidRoadRecovery != null) {
            return TravelStep.walk(alKharidRoadRecovery, false);
        }
        Tile darkWizardRecovery = varrockSouthDarkWizardRecovery(x, y, height, route);
        if (darkWizardRecovery != null) {
            return TravelStep.walk(darkWizardRecovery, false);
        }
        Tile blackKnightFortressRecovery = rockCrabsBlackKnightFortressRecovery(x, y, height, route);
        if (blackKnightFortressRecovery != null) {
            return TravelStep.walk(blackKnightFortressRecovery, false);
        }
        Tile goblinVillageRockCrabsRecovery = rockCrabsGoblinVillageRecovery(x, y, height, route);
        if (goblinVillageRockCrabsRecovery != null) {
            return TravelStep.walk(goblinVillageRockCrabsRecovery, false);
        }
        Tile westernSurfaceReturnRecovery = westernSurfaceRoadReturnRecovery(x, y, height, route);
        if (westernSurfaceReturnRecovery != null) {
            return TravelStep.walk(westernSurfaceReturnRecovery, false);
        }
        Tile westernSurfaceRecovery = westernSurfaceRoadRecovery(x, y, height, route);
        if (westernSurfaceRecovery != null) {
            return TravelStep.walk(westernSurfaceRecovery, false);
        }
        Tile varrockEastBankApproachRecovery = varrockEastBankApproachRecovery(x, y, height, route);
        if (varrockEastBankApproachRecovery != null) {
            return TravelStep.walk(varrockEastBankApproachRecovery, false);
        }
        Tile varrockEastMineBankRecovery = varrockEastMineToBankRecovery(x, y, height, route);
        if (varrockEastMineBankRecovery != null) {
            return TravelStep.walk(varrockEastMineBankRecovery, false);
        }
        Tile varrockCenterRecovery = varrockCenterToEastBankRecovery(x, y, height, route);
        if (varrockCenterRecovery != null) {
            return TravelStep.walk(varrockCenterRecovery, false);
        }
        Tile varrockToFurnaceRecovery = varrockToAlKharidFurnaceRecovery(x, y, height, route);
        if (varrockToFurnaceRecovery != null) {
            return TravelStep.walk(varrockToFurnaceRecovery, false);
        }
        Tile varrockSouthWestRoadRecovery = varrockSouthWestRoadRecovery(x, y, height, route);
        if (varrockSouthWestRoadRecovery != null) {
            return TravelStep.walk(varrockSouthWestRoadRecovery, false);
        }
        Tile varrockSouthRoadRecovery = varrockEastBankSouthRoadRecovery(x, y, height, route);
        if (varrockSouthRoadRecovery != null) {
            return TravelStep.walk(varrockSouthRoadRecovery, false);
        }
        Tile shantayRouteRecovery = shantayRouteRecovery(x, y, height, route);
        if (shantayRouteRecovery != null) {
            return TravelStep.walk(shantayRouteRecovery, false);
        }
        Tile shantayReturnRecovery = shantayToAlKharidRecovery(x, y, height, route);
        if (shantayReturnRecovery != null) {
            return TravelStep.walk(shantayReturnRecovery, false);
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
        if (finalTarget && distance(x, y, next.x, next.y) <= landmark.getArrivalRadius() && height == next.height) {
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

    private static List<Tile> withAlKharidApproach(List<Tile> route) {
        ArrayList<Tile> expanded = new ArrayList<Tile>();
        expanded.add(tile(3274, 3186, 0));
        expanded.add(tile(3274, 3195, 0));
        expanded.add(tile(3268, 3227, 0));
        expanded.add(tile(3267, 3227, 0));
        expanded.add(tile(3252, 3236, 0));
        expanded.add(tile(3252, 3266, 0));
        for (Tile tile : route) {
            expanded.add(tile);
        }
        return expanded;
    }

    private static List<Tile> withDwarvenMineSurfaceApproach(List<Tile> route) {
        ArrayList<Tile> expanded = new ArrayList<Tile>(dwarvenMineSurfaceToVarrockRoute());
        expanded.addAll(route);
        return expanded;
    }

    private static List<Tile> dwarvenMineSurfaceToVarrockRoute() {
        return route(tile(3065, 3492, 0), tile(3058, 3485, 0), tile(3050, 3474, 0),
                tile(3050, 3464, 0), tile(3054, 3450, 0), tile(3060, 3440, 0),
                tile(3070, 3436, 0), tile(3081, 3429, 0), tile(3100, 3429, 0),
                tile(3100, 3421, 0), tile(3108, 3421, 0),
                tile(3116, 3421, 0), tile(3124, 3418, 0), tile(3132, 3417, 0),
                tile(3140, 3417, 0), tile(3148, 3417, 0), tile(3156, 3417, 0),
                tile(3164, 3423, 0), tile(3172, 3425, 0), tile(3180, 3426, 0),
                tile(3188, 3429, 0), tile(3196, 3429, 0), tile(3204, 3429, 0),
                tile(3210, 3424, 0));
    }

    private static Tile lumbridgeCowRouteRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !routeContains(route, tile(3255, 3266, 0))) {
            return null;
        }
        if (x >= 3258 && x <= 3280 && y >= 3190 && y <= 3226) {
            return tile(3267, 3227, 0);
        }
        if (x >= 3260 && x <= 3280 && y >= 3227 && y <= 3245) {
            return tile(3252, 3236, 0);
        }
        if (x >= 3244 && x <= 3260 && y >= 3230 && y < 3262) {
            return tile(3252, 3266, 0);
        }
        return null;
    }

    private static Tile alKharidNorthTrapRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0) {
            return null;
        }
        Tile gateLine = tile(3267, 3227, 0);
        if (!routeContains(route, gateLine) || !routeContains(route, tile(3252, 3236, 0))) {
            return null;
        }
        if (routeEndsSouthOfAlKharidGate(route)
                && routeContains(route, tile(3268, 3227, 0))
                && routeContains(route, tile(3274, 3195, 0))) {
            return null;
        }
        if (x >= 3266 && x <= 3272 && y >= 3220 && y <= 3227 && (x != gateLine.x || y != gateLine.y)) {
            return gateLine;
        }
        return x >= 3260 && x <= 3276 && y >= 3228 && y <= 3255 ? gateLine : null;
    }

    private static Tile alKharidNorthRoadRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || x < 3240 || x > 3276 || y < 3266 || y > 3315) {
            return null;
        }
        if (routeEndsSouthOfAlKharidGate(route) && routeContains(route, tile(3240, 3302, 0))) {
            return null;
        }
        if (x < 3258 && y <= 3278 && routeContains(route, tile(3250, 3275, 0))) {
            return null;
        }
        Tile northRoad = tile(3261, 3322, 0);
        return routeContains(route, northRoad) ? northRoad : null;
    }

    private static Tile alKharidSouthboundRoadRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !routeEndsSouthOfAlKharidGate(route)
                || !routeContains(route, tile(3240, 3302, 0))) {
            return null;
        }
        Tile southRoad = tile(3240, 3302, 0);
        if (x == southRoad.x && y == southRoad.y) {
            return null;
        }
        return x >= 3240 && x <= 3265 && y >= 3300 && y <= 3325 ? southRoad : null;
    }

    private static Tile alKharidNorthConnectorRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !routeEndsSouthOfAlKharidGate(route)) {
            return null;
        }
        Tile gateLine = tile(3267, 3227, 0);
        if (!routeContains(route, gateLine) || x == gateLine.x && y == gateLine.y) {
            return null;
        }
        return x >= 3260 && x <= 3276 && y >= 3256 && y <= 3315 ? gateLine : null;
    }

    private static Tile alKharidGateApproachRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0) {
            return null;
        }
        Tile westGate = tile(3267, 3227, 0);
        Tile eastGate = tile(3268, 3227, 0);
        Tile alKharidRoad = tile(3274, 3195, 0);
        if (!routeEndsSouthOfAlKharidGate(route) || !routeContains(route, westGate)
                || !routeContains(route, eastGate) || !routeContains(route, alKharidRoad)) {
            return null;
        }
        if (x == westGate.x && y == westGate.y) {
            return null;
        }
        if (x == eastGate.x && y == eastGate.y) {
            return alKharidRoad;
        }
        if (isAlKharidSouthwestCityPocket(x, y) && routeContains(route, alKharidRoad)) {
            return null;
        }
        if (distance(x, y, alKharidRoad.x, alKharidRoad.y) <= 4) {
            return null;
        }
        if (x >= eastGate.x && x <= 3280 && y >= 3190 && y < westGate.y) {
            return alKharidRoad;
        }
        if (x >= 3258 && x <= westGate.x && y >= 3190 && y < westGate.y) {
            return westGate;
        }
        if (x >= 3260 && x <= 3276 && y >= westGate.y && y <= 3255) {
            return westGate;
        }
        return null;
    }

    private static boolean isAlKharidSouthwestCityPocket(int x, int y) {
        return x >= 3258 && x <= 3264 && y >= 3160 && y <= 3198;
    }

    private static Tile rockCrabsBlackKnightFortressRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !routeContains(route, tile(2666, 3716, 0))
                || !routeContains(route, tile(3012, 3484, 0))) {
            return null;
        }
        if (x >= 3014 && x <= 3042 && y >= 3494 && y <= 3520) {
            return tile(3012, 3484, 0);
        }
        return null;
    }

    private static Tile rockCrabsGoblinVillageRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !routeContains(route, tile(2666, 3716, 0))
                || !routeContains(route, tile(2948, 3492, 0))) {
            return null;
        }
        if (x >= 2958 && x <= 2970 && y >= 3488 && y <= 3498) {
            return tile(2948, 3492, 0);
        }
        if (x >= 2936 && x <= 2944 && y >= 3491 && y <= 3500) {
            return tile(2939, 3490, 0);
        }
        return null;
    }

    private static Tile westernSurfaceRoadRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !usesWesternSurfaceRoadRecovery(route)) {
            return null;
        }
        if (x >= 2930 && x <= 2965 && y >= 3440 && y <= 3515) {
            return distance(x, y, 2954, 3440) > 4 ? tile(2954, 3440, 0) : tile(2990, 3429, 0);
        }
        if (x >= 2960 && x <= 3005 && y >= 3420 && y <= 3450) {
            return distance(x, y, 2990, 3429) > 4 ? tile(2990, 3429, 0) : tile(3022, 3429, 0);
        }
        if (x >= 2990 && x <= 3035 && y >= 3380 && y < 3415) {
            return distance(x, y, 3005, 3404) > 4 ? tile(3005, 3404, 0) : tile(3023, 3420, 0);
        }
        if (x >= 2990 && x <= 3035 && y >= 3415 && y <= 3440) {
            if (x > 3026) {
                return tile(3040, 3428, 0);
            }
            return distance(x, y, 3022, 3429) > 4 ? tile(3022, 3429, 0) : tile(3040, 3428, 0);
        }
        if (x >= 3030 && x <= 3085 && y >= 3418 && y <= 3440) {
            if (x > 3080) {
                return tile(3092, 3429, 0);
            }
            return distance(x, y, 3076, 3428) > 4 ? tile(3076, 3428, 0) : tile(3092, 3429, 0);
        }
        if (x >= 3070 && x < 3100 && y >= 3420 && y <= 3435) {
            if (x > 3096) {
                return tile(3124, 3429, 0);
            }
            return distance(x, y, 3092, 3429) > 4 ? tile(3092, 3429, 0) : tile(3124, 3429, 0);
        }
        if (x >= 3100 && x < 3148 && y >= 3420 && y <= 3435) {
            if (x > 3128) {
                return tile(3154, 3426, 0);
            }
            return distance(x, y, 3124, 3429) > 4 ? tile(3124, 3429, 0) : tile(3154, 3426, 0);
        }
        if (x >= 3148 && x <= 3205 && y >= 3420 && y <= 3435) {
            if (x > 3198) {
                return tile(3210, 3424, 0);
            }
            return distance(x, y, 3194, 3430) > 4 ? tile(3194, 3430, 0) : tile(3210, 3424, 0);
        }
        return null;
    }

    private static boolean usesWesternSurfaceRoadRecovery(List<Tile> route) {
        if (routeContains(route, tile(2666, 3716, 0))
                || routeContains(route, tile(3024, 3450, 0))
                || routeContains(route, tile(3275, 3180, 0))) {
            return false;
        }
        if (route.isEmpty() || route.get(route.size() - 1).x < 3210) {
            return false;
        }
        return routeContains(route, tile(2974, 3383, 0))
                || routeContains(route, tile(3210, 3424, 0));
    }

    private static Tile westernSurfaceRoadReturnRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !usesWesternSurfaceRoadReturnRecovery(route)) {
            return null;
        }
        if (x >= 3030 && x <= 3085 && y >= 3418 && y <= 3440) {
            if (x < 3044) {
                return tile(3023, 3420, 0);
            }
            return distance(x, y, 3040, 3428) > 4 ? tile(3040, 3428, 0) : tile(3023, 3420, 0);
        }
        if (x >= 2990 && x < 3035 && y >= 3415 && y <= 3440) {
            return distance(x, y, 3023, 3420) > 4 ? tile(3023, 3420, 0) : tile(3005, 3404, 0);
        }
        return null;
    }

    private static boolean usesWesternSurfaceRoadReturnRecovery(List<Tile> route) {
        return routeContains(route, tile(3005, 3404, 0))
                && routeContains(route, tile(3023, 3420, 0))
                && routeContains(route, tile(3040, 3428, 0))
                && !routeContains(route, tile(2666, 3716, 0));
    }

    private static Tile alKharidGateReturnRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || routeEndsSouthOfAlKharidGate(route)) {
            return null;
        }
        Tile westGate = tile(3267, 3227, 0);
        Tile eastGate = tile(3268, 3227, 0);
        Tile alKharidRoad = tile(3274, 3195, 0);
        if (!routeContains(route, westGate) || !routeContains(route, eastGate)
                || !routeContains(route, alKharidRoad)) {
            return null;
        }
        if (x == westGate.x && y == westGate.y || x == eastGate.x && y == eastGate.y) {
            return null;
        }
        if (x >= 3258 && x <= westGate.x && y >= 3190 && y < westGate.y) {
            return westGate;
        }
        if (x >= eastGate.x && x <= 3280 && y >= 3190 && y < westGate.y) {
            return eastGate;
        }
        return null;
    }

    private static Tile varrockSouthDarkWizardRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || x < 3200 || x > 3240 || y < 3350 || y > 3392) {
            return null;
        }
        Tile northernRoad = tile(3238, 3420, 0);
        if (routeContains(route, northernRoad)) {
            return northernRoad;
        }
        Tile easternRoad = tile(3260, 3420, 0);
        return routeContains(route, easternRoad) && routeContains(route, tile(3253, 3420, 0)) ? easternRoad : null;
    }

    private static Tile varrockEastMineToBankRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !routeEndsAt(route, tile(3253, 3420, 0))) {
            return null;
        }
        if (x >= 3298 && x <= 3310 && y >= 3310 && y < 3324) {
            return tile(3295, 3317, 0);
        }
        if (x >= 3288 && x < 3298 && y >= 3310 && y < 3330) {
            Tile northRoad = tile(3280, 3343, 0);
            return routeContains(route, northRoad) ? northRoad : null;
        }
        if (x >= 3285 && x <= 3310 && y >= 3265 && y < 3330) {
            Tile scorpionRoad = tile(3301, 3325, 0);
            if (x == scorpionRoad.x && y == scorpionRoad.y) {
                Tile northRoad = tile(3280, 3343, 0);
                return routeContains(route, northRoad) ? northRoad : null;
            }
            return scorpionRoad;
        }
        if (x >= 3288 && x <= 3310 && y >= 3330 && y < 3355) {
            return tile(3285, 3365, 0);
        }
        if (x >= 3278 && x <= 3300 && y >= 3350 && y < 3380) {
            return tile(3289, 3388, 0);
        }
        if (x >= 3278 && x <= 3300 && y >= 3380 && y < 3402) {
            return tile(3278, 3408, 0);
        }
        if (x >= 3268 && x <= 3292 && y >= 3400 && y < 3418) {
            return tile(3260, 3420, 0);
        }
        return null;
    }

    private static Tile varrockEastBankApproachRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !routeEndsAt(route, tile(3253, 3420, 0))
                || !routeContains(route, tile(3260, 3420, 0))) {
            return null;
        }
        if (x >= 3261 && x <= 3280 && y >= 3414 && y <= 3430) {
            return tile(3260, 3420, 0);
        }
        return null;
    }

    private static Tile varrockCenterToEastBankRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || x < 3200 || x >= 3234 || y < 3410 || y > 3440) {
            return null;
        }
        Tile northernRoad = tile(3238, 3420, 0);
        return routeContains(route, tile(3260, 3420, 0)) && routeContains(route, tile(3253, 3420, 0))
                ? northernRoad : null;
    }

    private static Tile varrockToAlKharidFurnaceRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !routeContains(route, tile(3274, 3186, 0))
                || !routeContains(route, tile(3260, 3220, 0))) {
            return null;
        }
        if (x >= 3298 && x <= 3310 && y >= 3310 && y <= 3323) {
            return tile(3295, 3317, 0);
        }
        if (x >= 3288 && x < 3298 && y >= 3310 && y <= 3323) {
            return tile(3261, 3322, 0);
        }
        if (x >= 3297 && x <= 3306 && y >= 3324 && y <= 3332) {
            return tile(3295, 3338, 0);
        }
        if (x >= 3290 && x <= 3302 && y >= 3333 && y <= 3345) {
            return tile(3280, 3343, 0);
        }
        if (x >= 3270 && x <= 3280 && y >= 3421 && y <= 3430) {
            return tile(3274, 3417, 0);
        }
        if (x >= 3245 && x <= 3270 && y >= 3392 && y <= 3402) {
            return tile(3255, 3404, 0);
        }
        if (x >= 3245 && x <= 3270 && y >= 3360 && y <= 3402) {
            return tile(3289, 3388, 0);
        }
        return null;
    }

    private static Tile varrockSouthWestRoadRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || x < 3245 || x > 3270 || y < 3360 || y >= 3420) {
            return null;
        }
        if (!routeContains(route, tile(3260, 3420, 0)) || !routeContains(route, tile(3274, 3417, 0))) {
            return null;
        }
        if (y < 3404) {
            return tile(3255, Math.min(3404, y + 16), 0);
        }
        return tile(3260, 3420, 0);
    }

    private static Tile varrockEastBankSouthRoadRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || x < 3270 || x > 3280 || y < 3416 || y > 3430) {
            return null;
        }
        Tile eastBankRoad = tile(3260, 3420, 0);
        if (routeContains(route, eastBankRoad) && !routeContains(route, tile(3274, 3417, 0))) {
            return eastBankRoad;
        }
        if (y <= 3420) {
            return null;
        }
        Tile southRoad = tile(3274, 3417, 0);
        return routeContains(route, southRoad)
                && routeContains(route, tile(3278, 3408, 0))
                && routeContains(route, tile(3252, 3266, 0)) ? southRoad : null;
    }

    private static Tile shantayRouteRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !routeContains(route, tile(3303, 3124, 0))) {
            return null;
        }
        Tile desertBend = tile(3328, 3150, 0);
        if (x >= 3320 && x <= 3345 && y >= 3135 && y <= 3160) {
            return distance(x, y, desertBend.x, desertBend.y) <= 4 ? tile(3303, 3124, 0) : desertBend;
        }
        if (routeContains(route, tile(3304, 3117, 0))
                && x >= 3298 && x <= 3310 && y >= 3118 && y <= 3130) {
            return tile(3304, 3117, 0);
        }
        if (x >= 3300 && x <= 3335 && y >= 3120 && y < 3135) {
            return tile(3303, 3124, 0);
        }
        return null;
    }

    private static Tile shantayToAlKharidRecovery(int x, int y, int height, List<Tile> route) {
        if (height != 0 || !routeContains(route, tile(3274, 3186, 0))
                || routeContains(route, tile(3303, 3124, 0))) {
            return null;
        }
        if (routeContains(route, tile(3305, 3186, 0)) || routeContains(route, tile(3313, 3183, 0))) {
            return null;
        }
        Tile desertBend = tile(3328, 3150, 0);
        if (x >= 3320 && x <= 3345 && y >= 3135 && y <= 3160) {
            return distance(x, y, desertBend.x, desertBend.y) <= 4 ? tile(3315, 3175, 0) : desertBend;
        }
        Tile alKharidBend = tile(3315, 3175, 0);
        if (x >= 3310 && x <= 3335 && y >= 3148 && y <= 3182) {
            return distance(x, y, alKharidBend.x, alKharidBend.y) <= 4 ? tile(3289, 3189, 0) : alKharidBend;
        }
        if (x >= 3300 && x <= 3320 && y >= 3168 && y <= 3192) {
            return tile(3289, 3189, 0);
        }
        return null;
    }

    private static boolean routeContains(List<Tile> route, Tile candidate) {
        for (Tile tile : route) {
            if (tile.x == candidate.x && tile.y == candidate.y && tile.height == candidate.height) {
                return true;
            }
        }
        return false;
    }

    private static boolean routeEndsAt(List<Tile> route, Tile candidate) {
        if (route.isEmpty()) {
            return false;
        }
        Tile last = route.get(route.size() - 1);
        return last.x == candidate.x && last.y == candidate.y && last.height == candidate.height;
    }

    private static boolean routeEndsSouthOfAlKharidGate(List<Tile> route) {
        if (route.isEmpty()) {
            return false;
        }
        Tile last = route.get(route.size() - 1);
        return last.height == 0 && last.y <= 3220;
    }

    private static List<Tile> varrockRoute() {
        return withDwarvenMineSurfaceApproach(withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0))));
    }

    private static List<Tile> lumbridgeGoblinsRoute() {
        List<Tile> route = varrockEastBankToLumbridgeRoute();
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
        List<Tile> route = varrockEastBankToLumbridgeRoute();
        route.add(tile(3209, 3215, 0));
        return route;
    }

    private static List<Tile> lumbridgeFishingSpotRoute() {
        List<Tile> route = varrockEastBankToLumbridgeRoute();
        route.add(tile(3239, 3218, 0));
        route.add(tile(3260, 3220, 0));
        route.add(tile(3274, 3195, 0));
        route.add(tile(3274, 3190, 0));
        route.add(tile(3274, 3179, 0));
        route.add(tile(3268, 3164, 0));
        route.add(tile(3267, 3148, 0));
        return route;
    }

    private static List<Tile> alKharidFurnaceRoute() {
        return route(tile(3253, 3420, 0), tile(3260, 3420, 0), tile(3274, 3417, 0),
                tile(3278, 3408, 0), tile(3288, 3396, 0), tile(3289, 3388, 0),
                tile(3285, 3365, 0), tile(3280, 3343, 0), tile(3261, 3322, 0),
                tile(3240, 3302, 0), tile(3237, 3295, 0), tile(3237, 3284, 0),
                tile(3250, 3275, 0), tile(3253, 3267, 0), tile(3252, 3266, 0),
                tile(3252, 3236, 0), tile(3260, 3220, 0),
                tile(3267, 3227, 0), tile(3268, 3227, 0),
                tile(3274, 3195, 0), tile(3274, 3186, 0));
    }

    private static List<Tile> alKharidBankRoute() {
        List<Tile> route = new ArrayList<Tile>(alKharidFurnaceRoute());
        route.add(tile(3274, 3179, 0));
        route.add(tile(3269, 3167, 0));
        return route;
    }

    private static List<Tile> varrockEastMineRoute() {
        return withDwarvenMineSurfaceApproach(withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0),
                tile(3274, 3417, 0), tile(3260, 3420, 0), tile(3238, 3420, 0),
                tile(3210, 3424, 0), tile(3238, 3420, 0), tile(3260, 3420, 0),
                tile(3274, 3417, 0), tile(3278, 3408, 0),
                tile(3288, 3396, 0), tile(3289, 3388, 0), tile(3285, 3365, 0))));
    }

    private static List<Tile> varrockEastCoalMineRoute() {
        List<Tile> route = new ArrayList<Tile>(varrockEastMineRoute());
        route.add(tile(3291, 3351, 0));
        route.add(tile(3295, 3338, 0));
        route.add(tile(3301, 3325, 0));
        route.add(tile(3302, 3317, 0));
        return route;
    }

    private static List<Tile> varrockEastBankRoute() {
        return withDwarvenMineSurfaceApproach(withAlKharidApproach(lumbridgeToVarrockEastBankRoute()));
    }

    private static List<Tile> lumbridgeToVarrockEastBankRoute() {
        return route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3253, 3420, 0));
    }

    private static List<Tile> varrockEastBankToLumbridgeRoute() {
        return route(tile(3253, 3420, 0), tile(3260, 3420, 0), tile(3274, 3417, 0),
                tile(3278, 3408, 0), tile(3288, 3396, 0), tile(3289, 3388, 0),
                tile(3285, 3365, 0), tile(3280, 3343, 0), tile(3261, 3322, 0),
                tile(3240, 3302, 0), tile(3237, 3295, 0), tile(3237, 3284, 0),
                tile(3250, 3275, 0), tile(3253, 3267, 0), tile(3252, 3266, 0),
                tile(3252, 3236, 0), tile(3234, 3230, 0), tile(3222, 3218, 0));
    }

    private static List<Tile> lumbridgeAxeShopRoute() {
        List<Tile> route = varrockEastBankToLumbridgeRoute();
        route.add(tile(3231, 3203, 0));
        return route;
    }

    private static List<Tile> varrockWestBankRoute() {
        return withDwarvenMineSurfaceApproach(withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0),
                tile(3194, 3430, 0), tile(3185, 3436, 0))));
    }

    private static List<Tile> varrockGuardsRoute() {
        return withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0)));
    }

    private static List<Tile> varrockGeneralStoreRoute() {
        return withDwarvenMineSurfaceApproach(withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3216, 3415, 0))));
    }

    private static List<Tile> varrockWestAnvilRoute() {
        return withDwarvenMineSurfaceApproach(withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0),
                tile(3196, 3428, 0), tile(3188, 3425, 0))));
    }

    private static List<Tile> varrockSwordShopRoute() {
        return withDwarvenMineSurfaceApproach(withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0),
                tile(3206, 3399, 0))));
    }

    private static List<Tile> varrockArmourShopRoute() {
        return withDwarvenMineSurfaceApproach(withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3229, 3438, 0))));
    }

    private static List<Tile> championsGuildStairsRoute() {
        return withDwarvenMineSurfaceApproach(withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
                tile(3252, 3266, 0), tile(3253, 3267, 0), tile(3250, 3275, 0),
                tile(3237, 3284, 0), tile(3237, 3295, 0), tile(3240, 3302, 0),
                tile(3261, 3322, 0), tile(3280, 3343, 0), tile(3285, 3365, 0),
                tile(3289, 3388, 0), tile(3288, 3396, 0), tile(3278, 3408, 0), tile(3274, 3417, 0),
                tile(3260, 3420, 0), tile(3238, 3420, 0), tile(3210, 3424, 0),
                tile(3206, 3399, 0), tile(3198, 3384, 0), tile(3191, 3363, 0))));
    }

    private static List<Tile> championsGuildRuneStoreRoute() {
        List<Tile> route = championsGuildStairsRoute();
        route.add(tile(3192, 3358, 1));
        return route;
    }

    private static List<Tile> barbarianVillageRoute() {
        return withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
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
                tile(3092, 3429, 0), tile(3081, 3429, 0)));
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
        List<Tile> route = alKharidFurnaceRoute();
        route.add(tile(3289, 3189, 0));
        route.add(tile(3305, 3186, 0));
        route.add(tile(3313, 3183, 0));
        route.add(tile(3315, 3175, 0));
        return route;
    }

    private static List<Tile> alKharidScimitarShopRoute() {
        return route(tile(3222, 3218, 0), tile(3239, 3218, 0), tile(3260, 3220, 0),
                tile(3267, 3227, 0), tile(3268, 3227, 0),
                tile(3274, 3195, 0), tile(3289, 3189, 0));
    }

    private static List<Tile> alKharidGeneralStoreRoute() {
        return route(tile(3222, 3218, 0), tile(3239, 3218, 0), tile(3260, 3220, 0),
                tile(3267, 3227, 0), tile(3268, 3227, 0),
                tile(3274, 3195, 0), tile(3289, 3189, 0), tile(3305, 3186, 0),
                tile(3313, 3183, 0));
    }

    private static List<Tile> alKharidKebabShopRoute() {
        List<Tile> route = reverse(barbarianVillageRoute());
        route.add(tile(3239, 3218, 0));
        route.add(tile(3260, 3220, 0));
        route.add(tile(3267, 3227, 0));
        route.add(tile(3268, 3227, 0));
        route.add(tile(3274, 3195, 0));
        route.add(tile(3275, 3180, 0));
        return route;
    }

    private static List<Tile> shantayPassRoute() {
        List<Tile> route = new ArrayList<Tile>(alKharidFurnaceRoute());
        route.add(tile(3289, 3189, 0));
        route.add(tile(3315, 3175, 0));
        route.add(tile(3328, 3150, 0));
        route.add(tile(3303, 3124, 0));
        return route;
    }

    private static List<Tile> shantayGateNorthRoute() {
        List<Tile> route = new ArrayList<Tile>(shantayPassRoute());
        route.add(tile(3304, 3117, 0));
        return route;
    }

    private static List<Tile> shantayRugMerchantRoute() {
        List<Tile> route = new ArrayList<Tile>(shantayGateNorthRoute());
        route.add(tile(3304, 3115, 0));
        route.add(tile(3311, 3109, 0));
        return route;
    }

    private static List<Tile> nardahAdventurerStoreRoute() {
        List<Tile> route = new ArrayList<Tile>(shantayRugMerchantRoute());
        route.add(tile(3401, 2915, 0));
        route.add(tile(3407, 2921, 0));
        return route;
    }

    private static List<Tile> oziachRuneArmourRoute() {
        List<Tile> route = new ArrayList<Tile>(edgevilleMonasteryRoute());
        route.add(tile(3058, 3494, 0));
        route.add(tile(3064, 3504, 0));
        route.add(tile(3069, 3517, 0));
        return route;
    }

    private static List<Tile> faladorShieldShopRoute() {
        return withAlKharidApproach(route(tile(3222, 3218, 0), tile(3234, 3238, 0), tile(3252, 3236, 0),
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
                tile(3076, 3428, 0), tile(3040, 3428, 0), tile(3023, 3420, 0),
                tile(3005, 3404, 0),
                tile(2974, 3383, 0)));
    }

    private static List<Tile> faladorWhiteKnightsRoute() {
        List<Tile> route = new ArrayList<Tile>(faladorShieldShopRoute());
        route.add(tile(2974, 3365, 0));
        route.add(tile(2977, 3343, 0));
        return route;
    }

    private static List<Tile> pickaxeShopRoute() {
        return nurmofPickaxeShopRoute();
    }

    private static List<Tile> dwarvenMineLadderRoute() {
        List<Tile> route = new ArrayList<Tile>(barbarianVillageRoute());
        route.add(tile(3076, 3428, 0));
        route.add(tile(3040, 3428, 0));
        route.add(tile(3023, 3420, 0));
        route.add(tile(3024, 3450, 0));
        return route;
    }

    private static List<Tile> nurmofPickaxeShopRoute() {
        List<Tile> route = new ArrayList<Tile>();
        route.add(tile(3046, 9757, 0));
        route.add(tile(3039, 9765, 0));
        route.add(tile(3041, 9773, 0));
        route.add(tile(3042, 9781, 0));
        route.add(tile(3042, 9789, 0));
        route.add(tile(3042, 9797, 0));
        route.add(tile(3043, 9805, 0));
        route.add(tile(3041, 9813, 0));
        route.add(tile(3039, 9821, 0));
        route.add(tile(3038, 9829, 0));
        route.add(tile(3032, 9830, 0));
        route.add(tile(3024, 9822, 0));
        route.add(tile(3018, 9817, 0));
        route.add(tile(3013, 9813, 0));
        route.add(tile(3005, 9814, 0));
        route.add(tile(2999, 9819, 0));
        route.add(tile(2999, 9827, 0));
        route.add(tile(2999, 9835, 0));
        route.add(tile(2998, 9843, 0));
        return route;
    }

    private static List<Tile> dwarvenMineNorthUndergroundLadderRoute() {
        return route(tile(3077, 9887, 0), tile(3077, 9893, 0));
    }

    private static List<Tile> dwarvenMineTrapdoorUndergroundRoute() {
        return route(tile(3020, 9850, 0));
    }

    private static List<Tile> rockCrabsRoute() {
        List<Tile> route = new ArrayList<Tile>(edgevilleMonasteryRoute());
        route.add(tile(3038, 3484, 0));
        route.add(tile(3012, 3484, 0));
        route.add(tile(2990, 3488, 0));
        route.add(tile(2980, 3505, 0));
        route.add(tile(2948, 3492, 0));
        route.add(tile(2939, 3490, 0));
        route.add(tile(2939, 3484, 0));
        route.add(tile(2939, 3480, 0));
        route.add(tile(2944, 3470, 0));
        route.add(tile(2944, 3460, 0));
        route.add(tile(2938, 3452, 0));
        route.add(tile(2936, 3451, 0));
        route.add(tile(2935, 3451, 0));
        route.add(tile(2934, 3451, 0));
        route.add(tile(2933, 3451, 0));
        route.add(tile(2932, 3451, 0));
        route.add(tile(2931, 3451, 0));
        route.add(tile(2930, 3451, 0));
        route.add(tile(2929, 3451, 0));
        route.add(tile(2928, 3451, 0));
        route.add(tile(2927, 3451, 0));
        route.add(tile(2926, 3451, 0));
        route.add(tile(2925, 3451, 0));
        route.add(tile(2924, 3451, 0));
        route.add(tile(2923, 3451, 0));
        route.add(tile(2922, 3451, 0));
        route.add(tile(2921, 3451, 0));
        route.add(tile(2920, 3451, 0));
        route.add(tile(2920, 3453, 0));
        route.add(tile(2920, 3455, 0));
        route.add(tile(2920, 3457, 0));
        route.add(tile(2918, 3459, 0));
        route.add(tile(2917, 3461, 0));
        route.add(tile(2918, 3463, 0));
        route.add(tile(2919, 3465, 0));
        route.add(tile(2919, 3467, 0));
        route.add(tile(2919, 3469, 0));
        route.add(tile(2919, 3471, 0));
        route.add(tile(2919, 3473, 0));
        route.add(tile(2917, 3475, 0));
        route.add(tile(2915, 3477, 0));
        route.add(tile(2913, 3479, 0));
        route.add(tile(2911, 3481, 0));
        route.add(tile(2909, 3483, 0));
        route.add(tile(2907, 3485, 0));
        route.add(tile(2905, 3487, 0));
        route.add(tile(2903, 3489, 0));
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
        private final int arrivalRadius;

        public Landmark(String name, Tile target, List<Tile> route) {
            this(name, target, route, DEFAULT_ARRIVAL_RADIUS);
        }

        public Landmark(String name, Tile target, List<Tile> route, int arrivalRadius) {
            this.name = name;
            this.target = target;
            this.route = route;
            this.arrivalRadius = Math.max(0, arrivalRadius);
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

        public int getArrivalRadius() {
            return arrivalRadius;
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
