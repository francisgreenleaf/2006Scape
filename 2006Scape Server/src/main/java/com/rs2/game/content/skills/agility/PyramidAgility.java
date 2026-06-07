package com.rs2.game.content.skills.agility;

import com.rs2.Constants;
import com.rs2.event.CycleEvent;
import com.rs2.event.CycleEventContainer;
import com.rs2.event.CycleEventHandler;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.players.Player;
import com.rs2.util.Misc;

public class PyramidAgility {

	private static final int COURSE_REQUIREMENT = 30;
	private static final int PYRAMID_TOP_VALUE = 1000;
	private static final int PYRAMID_TOP_BONUS_XP = 300;
	private static final int COINS = 995;
	// The local cache collapses a few 2006 Pyramid obstacle segments into one clickable object.
	// These values preserve the 1,014 XP clean-lap total using the cache's real object placements.
	private static final double XP_STONE_BLOCK = 12.0;
	private static final double XP_LOW_WALL = 8.0;
	private static final double XP_DOUBLE_LOW_WALL = 16.0;
	private static final double XP_LEDGE = 52.0;
	private static final double XP_PLANK = 56.4;
	private static final double XP_PLANK_ROUNDED = 57.0;
	private static final double XP_CROSS_GAP = 56.4;
	private static final double XP_TWO_CROSS_GAPS = 113.0;
	private static final double XP_JUMP_GAP = 22.0;
	private static final double XP_THREE_JUMP_GAPS = 66.0;

	public static final int PYRAMID_DOORWAY_1 = 10848;
	public static final int PYRAMID_DOORWAY_2 = 10849;
	public static final int PYRAMID_DOORWAY_3 = 10855;
	public static final int PYRAMID_DOORWAY_4 = 10856;
	public static final int PYRAMID_ROCKS_WIDE = 10851;
	public static final int PYRAMID_ROCKS = 10852;
	public static final int PYRAMID_STAIRCE_OBJECT = 10857;
	public static final int PYRAMID_STAIRS_DOWN_OBJECT = 10858;
	public static final int PYRAMID_JUMP = 10859;
	public static final int LEDGE = 10860;
	public static final int PYRAMID_GAP_2 = 10861;
	public static final int PYRAMID_GAP_3 = 10862;
	public static final int PYRAMID_GAP_4 = 10863;
	public static final int PYRAMID_GAP_5 = 10864;
	public static final int PYRAMID_WALL_OBJECT = 10865;
	public static final int PYRAMID_PLANK_OBJECT_1 = 10867;
	public static final int PYRAMID_PLANK_OBJECT = 10868;
	public static final int PYRAMID_BLOCK_1 = 10877;
	public static final int PYRAMID_BLOCK_2 = 10878;
	public static final int PYRAMID_BLOCK_3 = 10879;
	public static final int PYRAMID_BLOCK_4 = 10880;
	public static final int PYRAMID_BLOCK_5 = 10881;
	public static final int PYRAMID_GAP_1 = 10882;
	public static final int PYRAMID_GAP_6 = 10883;
	public static final int PYRAMID_GAP = 10884;
	public static final int PYRAMID_GAP_7 = 10885;
	public static final int LEDGE_2 = 10886;
	public static final int LEDGE_4 = 10887;
	public static final int LEDGE_3 = 10888;
	public static final int LEDGE_5 = 10889;
	public static final int PYRAMID_CACHE_NULL_BLOCK = 3550;
	public static final int PYRAMID_CACHE_NULL_EAST_BLOCK = 10897;

	private static final int ANIM_JUMP = 3067;
	private static final int ANIM_BALANCE = 762;
	private static final int ANIM_LEDGE = 756;
	private static final int ANIM_STEP = 2753;
	private static final int ANIM_PLANK = 2295;
	private static final int ANIM_BLOCK = 1603;

	private static final Tile PYRAMID_START = new Tile(3355, 2830, 0);
	private static final Tile BASE_EXIT = new Tile(3351, 2838, 0);
	private static final Tile FLOOR_1_START = new Tile(3355, 2833, 1);
	private static final Tile FLOOR_2_START = new Tile(3356, 2835, 2);
	private static final Tile FLOOR_3_START = new Tile(3358, 2837, 3);

	private static final PyramidStep[] STEPS = new PyramidStep[] {
		step(PYRAMID_STAIRCE_OBJECT, 3354, 2831, 0, 0.0, Agility.CLIMB_UP_EMOTE, 1, false, 0,
				new Tile(3354, 2833, 1), null,
				new Tile[] { new Tile(3354, 2830, 0) },
				"You climb up the stairs."),
		step(PYRAMID_STAIRCE_OBJECT, 3354, 2831, 0, 0.0, Agility.CLIMB_UP_EMOTE, 1, false, 0,
				FLOOR_1_START, null,
				new Tile[] { PYRAMID_START },
				"You climb up the stairs."),

		step(PYRAMID_CACHE_NULL_BLOCK, 3355, 2841, 1, XP_STONE_BLOCK, ANIM_BLOCK, 1, false, 0,
				new Tile(3355, 2848, 1), PYRAMID_START,
				new Tile[] { new Tile(3355, 2841, 1), new Tile(3354, 2841, 1) },
				"You dodge past the moving block."),
		step(PYRAMID_CACHE_NULL_BLOCK, 3354, 2841, 1, XP_STONE_BLOCK, ANIM_BLOCK, 1, false, 0,
				new Tile(3354, 2848, 1), PYRAMID_START,
				new Tile[] { new Tile(3355, 2841, 1), new Tile(3354, 2841, 1) },
				"You dodge past the moving block."),
		step(PYRAMID_WALL_OBJECT, 3354, 2849, 1, XP_DOUBLE_LOW_WALL, Agility.WALL_EMOTE, 2, false, 4,
				new Tile(3354, 2850, 1), PYRAMID_START,
				new Tile[] { new Tile(3354, 2848, 1) },
				"You climb over the low wall."),
		step(PYRAMID_WALL_OBJECT, 3354, 2849, 1, XP_DOUBLE_LOW_WALL, Agility.WALL_EMOTE, 2, false, 4,
				new Tile(3355, 2850, 1), PYRAMID_START,
				new Tile[] { new Tile(3355, 2848, 1) },
				"You climb over the low wall."),
		step(LEDGE, 3364, 2851, 1, XP_LEDGE, ANIM_LEDGE, 2, false, 10,
				new Tile(3368, 2851, 1), PYRAMID_START,
				new Tile[] { new Tile(3363, 2851, 1) },
				"You carefully cross the ledge."),
		step(LEDGE, 3366, 2851, 1, XP_LEDGE, ANIM_LEDGE, 2, false, 10,
				new Tile(3368, 2851, 1), PYRAMID_START,
				new Tile[] { new Tile(3363, 2851, 1) },
				"You carefully cross the ledge."),
		step(PYRAMID_BLOCK_2, 3368, 2849, 1, XP_STONE_BLOCK, ANIM_BLOCK, 1, false, 8,
				new Tile(3371, 2849, 1), PYRAMID_START,
				new Tile[] { new Tile(3368, 2851, 1), new Tile(3367, 2849, 1), new Tile(3367, 2850, 1) },
				"You dodge past the moving block."),
		step(PYRAMID_CACHE_NULL_EAST_BLOCK, 3372, 2849, 1, XP_STONE_BLOCK, ANIM_BLOCK, 1, false, 8,
				new Tile(3374, 2849, 1), PYRAMID_START,
				new Tile[] { new Tile(3371, 2849, 1) },
				"You dodge past the moving block."),
		step(PYRAMID_PLANK_OBJECT, 3375, 2845, 1, XP_PLANK_ROUNDED, ANIM_PLANK, 6, false, 10,
				new Tile(3375, 2839, 1), PYRAMID_START,
				new Tile[] { new Tile(3374, 2846, 1), new Tile(3375, 2845, 1), new Tile(3375, 2846, 1) },
				"You cross the plank."),
		step(PYRAMID_PLANK_OBJECT_1, 3375, 2840, 1, XP_PLANK_ROUNDED, ANIM_PLANK, 6, false, 10,
				new Tile(3375, 2839, 1), PYRAMID_START,
				new Tile[] { new Tile(3375, 2840, 1), new Tile(3375, 2841, 1) },
				"You cross the plank."),
		step(PYRAMID_CACHE_NULL_BLOCK, 3374, 2835, 1, XP_STONE_BLOCK, ANIM_BLOCK, 1, false, 0,
				new Tile(3374, 2834, 1), PYRAMID_START,
				new Tile[] { new Tile(3374, 2836, 1), new Tile(3375, 2836, 1) },
				"You dodge past the moving block."),
		step(PYRAMID_CACHE_NULL_BLOCK, 3375, 2835, 1, XP_STONE_BLOCK, ANIM_BLOCK, 1, false, 0,
				new Tile(3375, 2834, 1), PYRAMID_START,
				new Tile[] { new Tile(3374, 2836, 1), new Tile(3375, 2836, 1) },
				"You dodge past the moving block."),
		step(PYRAMID_GAP_4, 3372, 2832, 1, XP_CROSS_GAP, ANIM_BALANCE, 2, false, 8,
				new Tile(3367, 2832, 1), PYRAMID_START,
				new Tile[] { new Tile(3372, 2832, 1) },
				"You cross the gap."),
		step(PYRAMID_GAP_1, 3370, 2831, 1, XP_CROSS_GAP, ANIM_BALANCE, 2, false, 8,
				new Tile(3367, 2831, 1), PYRAMID_START,
				new Tile[] { new Tile(3372, 2831, 1) },
				"You cross the gap."),
		step(LEDGE_2, 3362, 2831, 1, XP_LEDGE, ANIM_LEDGE, 2, false, 10,
				new Tile(3359, 2832, 1), PYRAMID_START,
				new Tile[] { new Tile(3364, 2832, 1) },
				"You carefully cross the ledge."),
		step(LEDGE_4, 3360, 2831, 1, XP_LEDGE, ANIM_LEDGE, 2, false, 10,
				new Tile(3359, 2832, 1), PYRAMID_START,
				new Tile[] { new Tile(3364, 2832, 1) },
				"You carefully cross the ledge."),
		step(PYRAMID_STAIRCE_OBJECT, 3356, 2833, 1, 0.0, Agility.CLIMB_UP_EMOTE, 1, false, 0,
				FLOOR_2_START, null,
				new Tile[] { new Tile(3356, 2832, 1) },
				"You climb up the stairs."),
		step(PYRAMID_STAIRCE_OBJECT, 3356, 2833, 1, 0.0, Agility.CLIMB_UP_EMOTE, 1, false, 0,
				new Tile(3357, 2835, 2), null,
				new Tile[] { new Tile(3357, 2832, 1) },
				"You climb up the stairs."),

		step(PYRAMID_GAP_4, 3357, 2836, 2, XP_THREE_JUMP_GAPS, ANIM_JUMP, 2, true, 8,
				new Tile(3357, 2841, 2), FLOOR_1_START,
				new Tile[] { new Tile(3357, 2836, 2) },
				"You jump the gap."),
		step(PYRAMID_GAP, 3356, 2837, 2, XP_THREE_JUMP_GAPS, ANIM_JUMP, 2, true, 8,
				new Tile(3356, 2841, 2), FLOOR_1_START,
				new Tile[] { new Tile(3356, 2836, 2) },
				"You jump the gap."),
		step(PYRAMID_JUMP, 3356, 2847, 2, XP_JUMP_GAP, ANIM_JUMP, 2, true, 8,
				new Tile(3356, 2849, 2), FLOOR_1_START,
				new Tile[] { new Tile(3356, 2846, 2) },
				"You jump the gap."),
		step(PYRAMID_JUMP, 3356, 2847, 2, XP_JUMP_GAP, ANIM_JUMP, 2, true, 8,
				new Tile(3357, 2849, 2), FLOOR_1_START,
				new Tile[] { new Tile(3357, 2846, 2) },
				"You jump the gap."),
		step(PYRAMID_GAP_4, 3359, 2849, 2, XP_TWO_CROSS_GAPS, ANIM_BALANCE, 2, false, 8,
				new Tile(3366, 2849, 2), FLOOR_1_START,
				new Tile[] { new Tile(3359, 2849, 2), new Tile(3359, 2850, 2) },
				"You cross the gap."),
		step(PYRAMID_CACHE_NULL_BLOCK, 3368, 2849, 2, XP_STONE_BLOCK, ANIM_BLOCK, 1, false, 0,
				new Tile(3373, 2849, 2), FLOOR_1_START,
				new Tile[] { new Tile(3367, 2849, 2), new Tile(3368, 2849, 2) },
				"You dodge past the moving block."),
		step(PYRAMID_CACHE_NULL_BLOCK, 3368, 2850, 2, XP_STONE_BLOCK, ANIM_BLOCK, 1, false, 0,
				new Tile(3373, 2850, 2), FLOOR_1_START,
				new Tile[] { new Tile(3367, 2850, 2), new Tile(3368, 2850, 2) },
				"You dodge past the moving block."),
		step(LEDGE, 3372, 2839, 2, XP_LEDGE, ANIM_LEDGE, 2, false, 10,
				new Tile(3372, 2836, 2), FLOOR_1_START,
				new Tile[] { new Tile(3372, 2841, 2), new Tile(3373, 2841, 2) },
				"You carefully cross the ledge."),
		step(LEDGE, 3372, 2837, 2, XP_LEDGE, ANIM_LEDGE, 2, false, 10,
				new Tile(3372, 2836, 2), FLOOR_1_START,
				new Tile[] { new Tile(3372, 2841, 2), new Tile(3373, 2841, 2) },
				"You carefully cross the ledge."),
		step(PYRAMID_WALL_OBJECT, 3370, 2833, 2, XP_LOW_WALL, Agility.WALL_EMOTE, 2, false, 4,
				new Tile(3369, 2834, 2), FLOOR_1_START,
				new Tile[] { new Tile(3371, 2834, 2) },
				"You climb over the low wall."),
		step(PYRAMID_WALL_OBJECT, 3370, 2833, 2, XP_LOW_WALL, Agility.WALL_EMOTE, 2, false, 4,
				new Tile(3369, 2833, 2), FLOOR_1_START,
				new Tile[] { new Tile(3371, 2833, 2) },
				"You climb over the low wall."),
		step(PYRAMID_JUMP, 3364, 2833, 2, XP_JUMP_GAP, ANIM_JUMP, 2, true, 8,
				new Tile(3363, 2834, 2), FLOOR_1_START,
				new Tile[] { new Tile(3366, 2834, 2) },
				"You jump the gap."),
		step(PYRAMID_JUMP, 3364, 2833, 2, XP_JUMP_GAP, ANIM_JUMP, 2, true, 8,
				new Tile(3363, 2833, 2), FLOOR_1_START,
				new Tile[] { new Tile(3366, 2833, 2) },
				"You jump the gap."),
		step(PYRAMID_STAIRCE_OBJECT, 3358, 2835, 2, 0.0, Agility.CLIMB_UP_EMOTE, 1, false, 0,
				FLOOR_3_START, null,
				new Tile[] { new Tile(3358, 2834, 2) },
				"You climb up the stairs."),
		step(PYRAMID_STAIRCE_OBJECT, 3358, 2835, 2, 0.0, Agility.CLIMB_UP_EMOTE, 1, false, 0,
				new Tile(3359, 2837, 3), null,
				new Tile[] { new Tile(3359, 2834, 2) },
				"You climb up the stairs."),

		step(PYRAMID_WALL_OBJECT, 3358, 2839, 3, XP_LOW_WALL, Agility.WALL_EMOTE, 2, false, 4,
				new Tile(3358, 2840, 3), FLOOR_2_START,
				new Tile[] { new Tile(3358, 2838, 3) },
				"You climb over the low wall."),
		step(PYRAMID_WALL_OBJECT, 3358, 2839, 3, XP_LOW_WALL, Agility.WALL_EMOTE, 2, false, 4,
				new Tile(3359, 2840, 3), FLOOR_2_START,
				new Tile[] { new Tile(3359, 2838, 3) },
				"You climb over the low wall."),
		step(LEDGE_3, 3358, 2843, 3, XP_LEDGE, ANIM_LEDGE, 2, false, 10,
				new Tile(3359, 2847, 3), FLOOR_2_START,
				new Tile[] { new Tile(3359, 2842, 3) },
				"You carefully cross the ledge."),
		step(LEDGE_5, 3358, 2845, 3, XP_LEDGE, ANIM_LEDGE, 2, false, 10,
				new Tile(3359, 2847, 3), FLOOR_2_START,
				new Tile[] { new Tile(3359, 2842, 3) },
				"You carefully cross the ledge."),
		step(PYRAMID_JUMP, 3370, 2841, 3, XP_JUMP_GAP, ANIM_JUMP, 2, true, 8,
				new Tile(3370, 2840, 3), FLOOR_2_START,
				new Tile[] { new Tile(3370, 2843, 3) },
				"You jump the gap."),
		step(PYRAMID_JUMP, 3370, 2841, 3, XP_JUMP_GAP, ANIM_JUMP, 2, true, 8,
				new Tile(3371, 2840, 3), FLOOR_2_START,
				new Tile[] { new Tile(3371, 2843, 3) },
				"You jump the gap."),
		step(PYRAMID_PLANK_OBJECT, 3370, 2835, 3, XP_PLANK, ANIM_PLANK, 6, false, 10,
				new Tile(3364, 2835, 3), FLOOR_2_START,
				new Tile[] { new Tile(3370, 2835, 3) },
				"You cross the plank."),
		step(PYRAMID_PLANK_OBJECT, 3370, 2835, 3, XP_PLANK, ANIM_PLANK, 6, false, 10,
				new Tile(3365, 2835, 3), FLOOR_2_START,
				new Tile[] { new Tile(3371, 2835, 3) },
				"You cross the plank."),
		step(PYRAMID_PLANK_OBJECT_1, 3365, 2835, 3, XP_PLANK, ANIM_PLANK, 6, false, 10,
				new Tile(3364, 2835, 3), FLOOR_2_START,
				new Tile[] { new Tile(3365, 2835, 3) },
				"You cross the plank."),
		step(PYRAMID_STAIRCE_OBJECT, 3360, 2837, 3, 0.0, Agility.CLIMB_UP_EMOTE, 1, false, 0,
				new Tile(3363, 2830, 0), null,
				new Tile[] { new Tile(3360, 2836, 3), new Tile(3361, 2836, 3) },
				"You climb to the summit."),

		step(PYRAMID_BLOCK_1, 3354, 2841, 0, 0.0, ANIM_BLOCK, 1, false, 8,
				new Tile(3356, 2841, 0), PYRAMID_START,
				new Tile[] { new Tile(3353, 2841, 0) },
				"You dodge past the moving block."),
		step(PYRAMID_BLOCK_3, 3374, 2835, 0, 0.0, ANIM_BLOCK, 1, false, 8,
				new Tile(3372, 2835, 0), PYRAMID_START,
				new Tile[] { new Tile(3375, 2835, 0) },
				"You dodge past the moving block.")
	};

	private final Player c;

	public PyramidAgility(Player player) {
		this.c = player;
	}

	public boolean pyramidCourse(int objectId) {
		if (!isPyramidObject(objectId)) {
			return false;
		}
		if (objectId == PYRAMID_ROCKS || objectId == PYRAMID_ROCKS_WIDE) {
			return handleRocks();
		}
		if (isDoorway(objectId)) {
			return handleDoorway();
		}
		if (objectId == PYRAMID_STAIRS_DOWN_OBJECT) {
			return handleStairsDown();
		}
		if (!hasLevel()) {
			return true;
		}
		PyramidStep step = findForwardStep(objectId);
		if (step != null) {
			return attemptStep(step);
		}
		PyramidStep reverse = findReverseStep(objectId);
		if (reverse != null) {
			failStep(reverse, 1, "You try to go backwards and fall down.");
			return true;
		}
		c.getPacketSender().sendMessage("You can't use that obstacle from here.");
		return true;
	}

	public static boolean sellPyramidTops(Player player) {
		int tops = player.getItemAssistant().getItemAmount(StaticItemList.PYRAMID_TOP);
		if (tops <= 0) {
			player.getPacketSender().sendMessage("Simon will buy any pyramid tops you bring him.");
			return true;
		}
		player.getItemAssistant().deleteItem(StaticItemList.PYRAMID_TOP, tops);
		player.getItemAssistant().addItem(COINS, tops * PYRAMID_TOP_VALUE);
		player.getPacketSender().sendMessage("Simon exchanges your pyramid top" + (tops == 1 ? "" : "s")
				+ " for " + (tops * PYRAMID_TOP_VALUE) + " coins.");
		return true;
	}

	public static boolean isPyramidObject(int objectId) {
		if (isDoorway(objectId)) {
			return true;
		}
		switch (objectId) {
			case PYRAMID_ROCKS_WIDE:
			case PYRAMID_ROCKS:
			case PYRAMID_STAIRCE_OBJECT:
			case PYRAMID_STAIRS_DOWN_OBJECT:
			case PYRAMID_JUMP:
			case LEDGE:
			case PYRAMID_GAP_2:
			case PYRAMID_GAP_3:
			case PYRAMID_GAP_4:
			case PYRAMID_GAP_5:
			case PYRAMID_WALL_OBJECT:
			case PYRAMID_PLANK_OBJECT_1:
			case PYRAMID_PLANK_OBJECT:
			case PYRAMID_BLOCK_1:
			case PYRAMID_BLOCK_2:
			case PYRAMID_BLOCK_3:
			case PYRAMID_BLOCK_4:
			case PYRAMID_BLOCK_5:
			case PYRAMID_CACHE_NULL_BLOCK:
			case PYRAMID_CACHE_NULL_EAST_BLOCK:
			case PYRAMID_GAP_1:
			case PYRAMID_GAP_6:
			case PYRAMID_GAP:
			case PYRAMID_GAP_7:
			case LEDGE_2:
			case LEDGE_4:
			case LEDGE_3:
			case LEDGE_5:
				return true;
			default:
				return false;
		}
	}

	private static boolean isDoorway(int objectId) {
		return objectId == PYRAMID_DOORWAY_1 || objectId == PYRAMID_DOORWAY_2
				|| objectId == PYRAMID_DOORWAY_3 || objectId == PYRAMID_DOORWAY_4;
	}

	private boolean handleRocks() {
		if (!hasLevel()) {
			return true;
		}
		if (c.heightLevel != 0) {
			c.getPacketSender().sendMessage("You can't use those rocks from here.");
			return true;
		}
		if (c.absX <= 3344) {
			moveLater(3349, c.absY, 0, Agility.CLIMB_UP_EMOTE, 1,
					"You enter the agility pyramid.");
		} else if (c.absX >= 3348) {
			moveLater(3343, c.absY, 0, Agility.CLIMB_DOWN_EMOTE, 1,
					"You leave the agility pyramid.");
		} else {
			c.getPacketSender().sendMessage("You can't reach those rocks from here.");
		}
		return true;
	}

	private boolean handleDoorway() {
		if (c.heightLevel != 0 || !nearObject(3)) {
			c.getPacketSender().sendMessage("You can't enter that doorway from here.");
			return true;
		}
		moveLater(BASE_EXIT.x, BASE_EXIT.y, BASE_EXIT.h, Agility.CLIMB_DOWN_EMOTE, 1,
				"You climb down a steep passage to the base of the pyramid.");
		return true;
	}

	private boolean handleStairsDown() {
		if (c.heightLevel == 1 && clicked(3354, 2831)) {
			moveLater(3355, 2830, 0, Agility.CLIMB_DOWN_EMOTE, 1, "You climb down the stairs.");
		} else if (c.heightLevel == 2 && clicked(3356, 2833)) {
			moveLater(3356, 2832, 1, Agility.CLIMB_DOWN_EMOTE, 1, "You climb down the stairs.");
		} else if (c.heightLevel == 3 && clicked(3358, 2835)) {
			moveLater(3358, 2834, 2, Agility.CLIMB_DOWN_EMOTE, 1, "You climb down the stairs.");
		} else {
			c.getPacketSender().sendMessage("You can't use those stairs from here.");
		}
		return true;
	}

	private boolean attemptStep(PyramidStep step) {
		if (step.completesCourse() && c.getItemAssistant().freeSlots() < 1) {
			c.getPacketSender().sendMessage("You need a free inventory space to take the pyramid top.");
			return true;
		}
		if (shouldFail(step)) {
			failStep(step, step.failDamage, failureMessage(step));
			return true;
		}
		addXp(step.xp);
		if (step.completesCourse()) {
			addXp(PYRAMID_TOP_BONUS_XP);
			c.getItemAssistant().addItem(StaticItemList.PYRAMID_TOP, 1);
			c.getPacketSender().sendMessage("You take the pyramid top.");
			c.getPacketSender().sendMessage("You received some bonus experience for completing the course.");
		}
		moveLater(step.destination.x, step.destination.y, step.destination.h, step.animation, step.delay,
				step.message);
		return true;
	}

	private void failStep(PyramidStep step, int damage, String message) {
		Tile fail = step.failDestination;
		if (fail == null) {
			fail = failDestinationForHeight(c.heightLevel);
		}
		applyDamage(Math.max(1, damage));
		moveLater(fail.x, fail.y, fail.h, step.animation, 1, message);
	}

	private boolean shouldFail(PyramidStep step) {
		if (step.failDamage <= 0) {
			return false;
		}
		int level = c.playerLevel[Constants.AGILITY];
		if (level >= 75) {
			return false;
		}
		if (level >= 70 && !step.jumpGap) {
			return false;
		}
		int chance = 50 - (level - COURSE_REQUIREMENT);
		if (level >= 70 && step.jumpGap) {
			chance = 6;
		}
		chance = Math.max(2, Math.min(50, chance));
		return Misc.random(99) < chance;
	}

	private String failureMessage(PyramidStep step) {
		if (step.jumpGap) {
			return "You miss your footing and fall down.";
		}
		if (isLedge(step.objectId) || isPlank(step.objectId)) {
			return "You lose your balance and fall down.";
		}
		if (step.objectId == PYRAMID_WALL_OBJECT) {
			return "You slip while climbing the wall.";
		}
		return "The obstacle knocks you down to a lower level.";
	}

	private PyramidStep findForwardStep(int objectId) {
		for (PyramidStep step : STEPS) {
			if (step.matches(objectId, c.objectX, c.objectY, c.heightLevel, c.getX(), c.getY())) {
				return step;
			}
		}
		return null;
	}

	private PyramidStep findReverseStep(int objectId) {
		for (PyramidStep step : STEPS) {
			if (step.matchesReverse(objectId, c.objectX, c.objectY, c.heightLevel, c.getX(), c.getY())) {
				return step;
			}
		}
		return null;
	}

	private boolean hasLevel() {
		if (c.playerLevel[Constants.AGILITY] < COURSE_REQUIREMENT) {
			c.getPacketSender().sendMessage("You need atleast " + COURSE_REQUIREMENT + " agility to do this.");
			return false;
		}
		return true;
	}

	private void addXp(double xp) {
		if (xp > 0.0) {
			c.getPlayerAssistant().addSkillXP(xp, Constants.AGILITY);
		}
	}

	private void applyDamage(int damage) {
		c.dealDamage(damage);
		c.handleHitMask(damage);
	}

	private Tile failDestinationForHeight(int height) {
		if (height >= 3) {
			return FLOOR_2_START;
		}
		if (height == 2) {
			return FLOOR_1_START;
		}
		return PYRAMID_START;
	}

	private boolean clicked(int x, int y) {
		return c.objectX == x && c.objectY == y;
	}

	private boolean nearObject(int distance) {
		return c.heightLevel == 0
				&& Math.abs(c.getX() - c.objectX) <= distance
				&& Math.abs(c.getY() - c.objectY) <= distance;
	}

	private static boolean isLedge(int objectId) {
		return objectId == LEDGE || objectId == LEDGE_2 || objectId == LEDGE_3
				|| objectId == LEDGE_4 || objectId == LEDGE_5;
	}

	private static boolean isPlank(int objectId) {
		return objectId == PYRAMID_PLANK_OBJECT || objectId == PYRAMID_PLANK_OBJECT_1;
	}

	private void moveLater(final int x, final int y, final int h, int animation, int delay, final String message) {
		c.getPlayerAction().setAction(true);
		c.getPlayerAction().canWalk(false);
		c.startAnimation(animation);
		CycleEventHandler.getSingleton().addEvent(c, new CycleEvent() {
			@Override
			public void execute(CycleEventContainer container) {
				if (c.disconnected) {
					container.stop();
					return;
				}
				c.getPlayerAssistant().movePlayer(x, y, h);
				c.getPlayerAction().setAction(false);
				c.getPlayerAction().canWalk(true);
				c.isRunning2 = true;
				c.playerWalkIndex = 0x333;
				c.getPacketSender().sendConfig(173, 1);
				c.getPlayerAssistant().requestUpdates();
				if (message != null && message.length() > 0) {
					c.getPacketSender().sendMessage(message);
				}
				container.stop();
			}

			@Override
			public void stop() {
			}
		}, Math.max(1, delay));
	}

	private static PyramidStep step(int objectId, int objectX, int objectY, int height, double xp,
			int animation, int delay, boolean jumpGap, int failDamage, Tile destination, Tile failDestination,
			Tile[] starts, String message) {
		return new PyramidStep(objectId, objectX, objectY, height, xp, animation, delay,
				jumpGap, failDamage, destination, failDestination, starts, message);
	}

	private static final class PyramidStep {
		private final int objectId;
		private final int objectX;
		private final int objectY;
		private final int height;
		private final double xp;
		private final int animation;
		private final int delay;
		private final boolean jumpGap;
		private final int failDamage;
		private final Tile destination;
		private final Tile failDestination;
		private final Tile[] starts;
		private final String message;

		private PyramidStep(int objectId, int objectX, int objectY, int height, double xp,
				int animation, int delay, boolean jumpGap, int failDamage, Tile destination,
				Tile failDestination, Tile[] starts, String message) {
			this.objectId = objectId;
			this.objectX = objectX;
			this.objectY = objectY;
			this.height = height;
			this.xp = xp;
			this.animation = animation;
			this.delay = delay;
			this.jumpGap = jumpGap;
			this.failDamage = failDamage;
			this.destination = destination;
			this.failDestination = failDestination;
			this.starts = starts;
			this.message = message;
		}

		private boolean matches(int clickedId, int clickedX, int clickedY, int clickedH, int playerX, int playerY) {
			if (clickedId != objectId || clickedX != objectX || clickedY != objectY || clickedH != height) {
				return false;
			}
			for (Tile start : starts) {
				if (start.matches(playerX, playerY, clickedH)) {
					return true;
				}
			}
			return false;
		}

		private boolean matchesReverse(int clickedId, int clickedX, int clickedY, int clickedH, int playerX, int playerY) {
			return clickedId == objectId && clickedX == objectX && clickedY == objectY
					&& clickedH == height && destination.matches(playerX, playerY, clickedH);
		}

		private boolean completesCourse() {
			return objectId == PYRAMID_STAIRCE_OBJECT && height == 3 && objectX == 3360 && objectY == 2837;
		}
	}

	private static final class Tile {
		private final int x;
		private final int y;
		private final int h;

		private Tile(int x, int y, int h) {
			this.x = x;
			this.y = y;
			this.h = h;
		}

		private boolean matches(int otherX, int otherY, int otherH) {
			return x == otherX && y == otherY && h == otherH;
		}
	}
}
