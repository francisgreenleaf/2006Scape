package com.rs2.game.content.skills.agility;

import com.rs2.Constants;
import com.rs2.event.CycleEvent;
import com.rs2.event.CycleEventContainer;
import com.rs2.event.CycleEventHandler;
import com.rs2.game.content.StaticItemList;
import com.rs2.game.players.Player;
import com.rs2.util.Misc;

public class BrimhavenAgility {

	private static final int COINS = 995;
	private static final int ENTRY_FEE = 200;
	private static final int ACTIVE_DISPENSER_SECONDS = 60;
	private static final int CROSS_X = 0;
	private static final int CROSS_Y = 1;

	public static final int BALANCING_ROPE_1 = 3551;
	public static final int BALANCING_ROPE_2 = 3552;
	public static final int LOG_BALANCE_1 = 3553;
	public static final int LOG_BALANCE_2 = 3554;
	public static final int LOG_BALANCE_3 = 3555;
	public static final int LOG_BALANCE_4 = 3556;
	public static final int LOG_BALANCE_5 = 3557;
	public static final int LOG_BALANCE_6 = 3558;
	public static final int BALANCING_LEDGE_1 = 3559;
	public static final int BALANCING_LEDGE_2 = 3560;
	public static final int BALANCING_LEDGE_3 = 3561;
	public static final int BALANCING_LEDGE_4 = 3562;
	public static final int MONKEY_BARS_1 = 3563;
	public static final int MONKEY_BARS_2 = 3564;
	public static final int LOW_WALL = 3565;
	public static final int ROPE_SWING = 3566;
	public static final int BLADE_1 = 3567;
	public static final int BLADE_2 = 3568;
	public static final int BLADE_3 = 3569;
	public static final int PLANK_1 = 3570;
	public static final int PLANK_2 = 3571;
	public static final int PLANK_3 = 3572;
	public static final int PLANK_4 = 3573;
	public static final int PLANK_5 = 3574;
	public static final int PLANK_6 = 3575;
	public static final int PLANK_7 = 3576;
	public static final int PLANK_8 = 3577;
	public static final int PILLAR_1 = 3578;
	public static final int PILLAR_2 = 3579;
	public static final int SPINNING_BLADES = 3580;
	public static final int TICKET_DISPENSER = 3581;
	public static final int FLOOR_SPIKES = 3582;
	public static final int HAND_HOLDS_1 = 3583;
	public static final int HAND_HOLDS_2 = 3584;
	public static final int PRESSURE_PAD = 3585;
	public static final int INACTIVE_TICKET_DISPENSER = 3608;
	public static final int EXIT_LADDER = 3618;

	private static final Tile ARENA_ENTRY = new Tile(2809, 9562, 3);
	private static final Tile ARENA_EXIT = new Tile(2809, 3192, 0);
	private static final Tile[] DISPENSERS = new Tile[] {
			new Tile(2761, 9546, 3),
			new Tile(2772, 9546, 3),
			new Tile(2783, 9546, 3),
			new Tile(2794, 9546, 3),
			new Tile(2805, 9546, 3),
			new Tile(2761, 9557, 3),
			new Tile(2772, 9557, 3),
			new Tile(2783, 9557, 3),
			new Tile(2794, 9557, 3),
			new Tile(2805, 9557, 3),
			new Tile(2761, 9568, 3),
			new Tile(2772, 9568, 3),
			new Tile(2783, 9568, 3),
			new Tile(2794, 9568, 3),
			new Tile(2805, 9568, 3),
			new Tile(2761, 9579, 3),
			new Tile(2772, 9579, 3),
			new Tile(2783, 9579, 3),
			new Tile(2794, 9579, 3),
			new Tile(2805, 9579, 3),
			new Tile(2761, 9590, 3),
			new Tile(2772, 9590, 3),
			new Tile(2783, 9590, 3),
			new Tile(2794, 9590, 3)
	};
	private static final ObstacleSpan[] OBSTACLE_SPANS = new ObstacleSpan[] {
			new ObstacleSpan(LOW_WALL, LOW_WALL, 2783, 2783, 9558, 9567, CROSS_Y),
			new ObstacleSpan(LOW_WALL, LOW_WALL, 2805, 2805, 9558, 9567, CROSS_Y),
			new ObstacleSpan(LOW_WALL, LOW_WALL, 2773, 2782, 9590, 9590, CROSS_X),
			new ObstacleSpan(BALANCING_ROPE_1, BALANCING_ROPE_2, 2772, 2772, 9559, 9566, CROSS_Y),
			new ObstacleSpan(BALANCING_ROPE_1, BALANCING_ROPE_2, 2783, 2783, 9581, 9588, CROSS_Y),
			new ObstacleSpan(BALANCING_ROPE_1, BALANCING_ROPE_2, 2794, 2794, 9548, 9555, CROSS_Y),
			new ObstacleSpan(LOG_BALANCE_1, LOG_BALANCE_6, 2764, 2769, 9579, 9579, CROSS_X),
			new ObstacleSpan(LOG_BALANCE_1, LOG_BALANCE_6, 2794, 2794, 9582, 9587, CROSS_Y),
			new ObstacleSpan(LOG_BALANCE_1, LOG_BALANCE_6, 2805, 2805, 9549, 9554, CROSS_Y),
			new ObstacleSpan(BALANCING_LEDGE_1, BALANCING_LEDGE_4, 2764, 2769, 9546, 9546, CROSS_X),
			new ObstacleSpan(BALANCING_LEDGE_1, BALANCING_LEDGE_4, 2764, 2769, 9590, 9590, CROSS_X),
			new ObstacleSpan(BALANCING_LEDGE_1, BALANCING_LEDGE_4, 2797, 2802, 9546, 9546, CROSS_X),
			new ObstacleSpan(MONKEY_BARS_1, MONKEY_BARS_2, 2772, 2772, 9571, 9576, CROSS_Y),
			new ObstacleSpan(MONKEY_BARS_1, MONKEY_BARS_2, 2775, 2780, 9546, 9546, CROSS_X),
			new ObstacleSpan(MONKEY_BARS_1, MONKEY_BARS_2, 2794, 2794, 9560, 9565, CROSS_Y),
			new ObstacleSpan(BLADE_1, BLADE_3, 2761, 2761, 9584, 9585, CROSS_Y),
			new ObstacleSpan(BLADE_1, BLADE_3, 2783, 2783, 9551, 9552, CROSS_Y),
			new ObstacleSpan(BLADE_1, BLADE_3, 2788, 2789, 9579, 9579, CROSS_X),
			new ObstacleSpan(SPINNING_BLADES, SPINNING_BLADES, 2777, 2779, 9556, 9556, CROSS_X),
			new ObstacleSpan(SPINNING_BLADES, SPINNING_BLADES, 2777, 2779, 9580, 9580, CROSS_X),
			new ObstacleSpan(SPINNING_BLADES, SPINNING_BLADES, 2782, 2782, 9573, 9575, CROSS_Y),
			new ObstacleSpan(PLANK_1, PLANK_8, 2764, 2769, 9556, 9558, CROSS_X),
			new ObstacleSpan(PLANK_1, PLANK_8, 2797, 2802, 9589, 9591, CROSS_X),
			new ObstacleSpan(PILLAR_1, PILLAR_2, 2761, 2761, 9549, 9554, CROSS_Y),
			new ObstacleSpan(PILLAR_1, PILLAR_2, 2786, 2791, 9568, 9568, CROSS_X),
			new ObstacleSpan(PILLAR_1, PILLAR_2, 2805, 2805, 9571, 9576, CROSS_Y),
			new ObstacleSpan(FLOOR_SPIKES, FLOOR_SPIKES, 2761, 2761, 9573, 9574, CROSS_Y),
			new ObstacleSpan(FLOOR_SPIKES, FLOOR_SPIKES, 2772, 2772, 9551, 9552, CROSS_Y),
			new ObstacleSpan(FLOOR_SPIKES, FLOOR_SPIKES, 2799, 2800, 9568, 9568, CROSS_X),
			new ObstacleSpan(HAND_HOLDS_1, HAND_HOLDS_2, 2759, 2759, 9559, 9566, CROSS_Y),
			new ObstacleSpan(HAND_HOLDS_1, HAND_HOLDS_2, 2785, 2792, 9544, 9544, CROSS_X),
			new ObstacleSpan(HAND_HOLDS_1, HAND_HOLDS_2, 2785, 2792, 9592, 9592, CROSS_X),
			new ObstacleSpan(PRESSURE_PAD, PRESSURE_PAD, 2772, 2772, 9584, 9585, CROSS_Y),
			new ObstacleSpan(PRESSURE_PAD, PRESSURE_PAD, 2799, 2800, 9557, 9557, CROSS_X),
			new ObstacleSpan(PRESSURE_PAD, PRESSURE_PAD, 2799, 2800, 9579, 9579, CROSS_X)
	};

	private final Player c;
	private long lastTaggedWindow = -1;
	private int lastTaggedDispenser = -1;
	private boolean hasTaggedFirstDispenser = false;
	private long lastHintWindow = -1;

	public BrimhavenAgility(Player player) {
		this.c = player;
	}

	public void process() {
		if (!isInArena()) {
			lastHintWindow = -1;
			return;
		}
		long window = currentWindow();
		if (window != lastHintWindow) {
			sendActiveHint(activeDispenserIndex(window), window);
		}
	}

	public boolean brimhavenCourse(int objectId) {
		if (!isArenaObject(objectId)) {
			return false;
		}
		if (objectId == EXIT_LADDER) {
			leaveArena();
			return true;
		}
		if (!isInArena() && !isTicketDispenserObject(objectId)) {
			c.getPacketSender().sendMessage("You need to be inside the Brimhaven Agility Arena to use that.");
			return true;
		}
		if (isTicketDispenserObject(objectId)) {
			tagDispenser();
			return true;
		}
		if (!hasLevel(objectId)) {
			return true;
		}
		if (!nearClickedObject(5)) {
			c.getPacketSender().sendMessage("You need to get closer to that obstacle.");
			return true;
		}
		Obstacle obstacle = obstacleFor(objectId);
		if (obstacle == null) {
			c.getPacketSender().sendMessage("Nothing interesting happens.");
			return true;
		}
		if (shouldFail(obstacle)) {
			failObstacle(obstacle);
			return true;
		}
		addXp(obstacle.xp);
		Tile destination = obstacleDestination();
		moveLater(destination.x, destination.y, destination.h, obstacle.animation, obstacle.delay,
				obstacle.successMessage);
		return true;
	}

	public static boolean enterArena(Player player) {
		if (player.heightLevel == 3 && isArenaTile(player.getX(), player.getY(), player.heightLevel)) {
			player.getPacketSender().sendMessage("You are already inside the arena.");
			return true;
		}
		if (!player.getItemAssistant().playerHasItem(COINS, ENTRY_FEE)) {
			player.getPacketSender().sendMessage("You need " + ENTRY_FEE + " coins to enter the Brimhaven Agility Arena.");
			return true;
		}
		player.getItemAssistant().deleteItem(COINS, ENTRY_FEE);
		player.getBrimhavenAgility().resetTicketStreak();
		player.getPlayerAssistant().movePlayer(ARENA_ENTRY.x, ARENA_ENTRY.y, ARENA_ENTRY.h);
		player.getPacketSender().sendMessage("Cap'n Izzy takes your fee and lets you into the arena.");
		player.getBrimhavenAgility().sendActiveHint();
		return true;
	}

	public static boolean exchangeTickets(Player player) {
		int tickets = player.getItemAssistant().getItemAmount(StaticItemList.AGILITY_ARENA_TICKET);
		if (tickets <= 0) {
			player.getPacketSender().sendMessage("Pirate Jackie will exchange any Agility arena tickets you bring her.");
			return true;
		}
		player.getItemAssistant().deleteItem(StaticItemList.AGILITY_ARENA_TICKET, tickets);
		player.getPlayerAssistant().addSkillXP(ticketXp(tickets), Constants.AGILITY);
		player.getBrimhavenAgility().resetTicketStreak();
		player.getPacketSender().sendMessage("Pirate Jackie exchanges your tickets for Agility experience.");
		return true;
	}

	public static boolean isArenaObject(int objectId) {
		return (objectId >= BALANCING_ROPE_1 && objectId <= PRESSURE_PAD)
				|| objectId == INACTIVE_TICKET_DISPENSER || objectId == EXIT_LADDER;
	}

	private static boolean isTicketDispenserObject(int objectId) {
		return objectId == TICKET_DISPENSER || objectId == INACTIVE_TICKET_DISPENSER;
	}

	private void leaveArena() {
		if (!isInArena()) {
			c.getPacketSender().sendMessage("You are already outside the Brimhaven Agility Arena.");
			return;
		}
		c.getPlayerAssistant().movePlayer(ARENA_EXIT.x, ARENA_EXIT.y, ARENA_EXIT.h);
		resetTicketStreak();
		c.getPacketSender().sendMessage("You climb the ladder out of the Brimhaven Agility Arena.");
	}

	private static int ticketXp(int tickets) {
		int remaining = tickets;
		int xp = 0;
		while (remaining >= 1000) {
			xp += 320000;
			remaining -= 1000;
		}
		while (remaining >= 100) {
			xp += 28000;
			remaining -= 100;
		}
		while (remaining >= 25) {
			xp += 6500;
			remaining -= 25;
		}
		while (remaining >= 10) {
			xp += 2480;
			remaining -= 10;
		}
		return xp + remaining * 240;
	}

	private void tagDispenser() {
		if (!isInArena()) {
			c.getPacketSender().sendMessage("You need to be inside the arena to use that dispenser.");
			return;
		}
		int clicked = clickedDispenserIndex();
		if (clicked < 0) {
			c.getPacketSender().sendMessage("You can't reach that dispenser from here.");
			return;
		}
		long window = currentWindow();
		int active = activeDispenserIndex(window);
		sendActiveHint(active, window);
		if (clicked != active) {
			resetTicketStreak();
			c.getPacketSender().sendMessage("The flashing arrow is pointing at a different dispenser.");
			return;
		}
		if (!hasTaggedFirstDispenser) {
			hasTaggedFirstDispenser = true;
			lastTaggedWindow = window;
			lastTaggedDispenser = clicked;
			c.getPacketSender().sendMessage("You tag the active dispenser. Tag the next one for a ticket.");
			return;
		}
		if (lastTaggedWindow == window && lastTaggedDispenser == clicked) {
			resetTicketStreak();
			c.getPacketSender().sendMessage("You have already tagged this dispenser.");
			return;
		}
		if (lastTaggedDispenser == clicked) {
			resetTicketStreak();
			c.getPacketSender().sendMessage("You need to tag a different dispenser next.");
			return;
		}
		if (window != lastTaggedWindow + 1L) {
			hasTaggedFirstDispenser = true;
			lastTaggedWindow = window;
			lastTaggedDispenser = clicked;
			c.getPacketSender().sendMessage("You missed a dispenser. Tag the next one for a ticket.");
			return;
		}
		if (c.getItemAssistant().freeSlots() < 1
				&& !c.getItemAssistant().playerHasItem(StaticItemList.AGILITY_ARENA_TICKET)) {
			c.getPacketSender().sendMessage("You need a free inventory space for an Agility arena ticket.");
			return;
		}
		c.getItemAssistant().addItem(StaticItemList.AGILITY_ARENA_TICKET, 1);
		lastTaggedWindow = window;
		lastTaggedDispenser = clicked;
		c.getPacketSender().sendMessage("You receive an Agility arena ticket.");
	}

	private void resetTicketStreak() {
		lastTaggedWindow = -1;
		lastTaggedDispenser = -1;
		hasTaggedFirstDispenser = false;
	}

	private int clickedDispenserIndex() {
		for (int i = 0; i < DISPENSERS.length; i++) {
			if (DISPENSERS[i].matches(c.objectX, c.objectY, c.heightLevel)) {
				return i;
			}
		}
		return -1;
	}

	private void sendActiveHint() {
		long window = currentWindow();
		sendActiveHint(activeDispenserIndex(window), window);
	}

	private void sendActiveHint(int active) {
		sendActiveHint(active, currentWindow());
	}

	private void sendActiveHint(int active, long window) {
		Tile tile = DISPENSERS[active];
		c.getPacketSender().createObjectHints(tile.x, tile.y, 130, 2);
		lastHintWindow = window;
	}

	private long currentWindow() {
		return System.currentTimeMillis() / (ACTIVE_DISPENSER_SECONDS * 1000L);
	}

	private int activeDispenserIndex(long window) {
		return (int) (Math.abs(window) % DISPENSERS.length);
	}

	private boolean hasLevel(int objectId) {
		int required = requiredLevel(objectId);
		if (c.playerLevel[Constants.AGILITY] < required) {
			c.getPacketSender().sendMessage("You need atleast " + required + " agility to do this.");
			return false;
		}
		return true;
	}

	private int requiredLevel(int objectId) {
		switch (objectId) {
			case FLOOR_SPIKES:
			case PRESSURE_PAD:
			case HAND_HOLDS_1:
			case HAND_HOLDS_2:
				return 20;
			case SPINNING_BLADES:
				return 40;
			default:
				return 1;
		}
	}

	private Obstacle obstacleFor(int objectId) {
		switch (objectId) {
			case LOW_WALL:
				return new Obstacle(8.0, Agility.WALL_EMOTE, 2, 1, "You climb over the low wall.");
			case ROPE_SWING:
				return new Obstacle(20.0, 3067, 2, 2, "You swing across the gap.");
			case PLANK_1:
			case PLANK_2:
			case PLANK_3:
			case PLANK_4:
			case PLANK_5:
			case PLANK_6:
			case PLANK_7:
			case PLANK_8:
				return new Obstacle(6.0, 2295, 2, 1, "You cross the plank.");
			case PILLAR_1:
			case PILLAR_2:
				return new Obstacle(18.0, 3067, 2, 1, "You jump to the next platform.");
			case BALANCING_ROPE_1:
			case BALANCING_ROPE_2:
				return new Obstacle(10.0, Agility.LOG_EMOTE, 3, 2, "You cross the balancing rope.");
			case LOG_BALANCE_1:
			case LOG_BALANCE_2:
			case LOG_BALANCE_3:
			case LOG_BALANCE_4:
			case LOG_BALANCE_5:
			case LOG_BALANCE_6:
				return new Obstacle(12.0, Agility.LOG_EMOTE, 3, 2, "You cross the log balance.");
			case BALANCING_LEDGE_1:
			case BALANCING_LEDGE_2:
			case BALANCING_LEDGE_3:
			case BALANCING_LEDGE_4:
				return new Obstacle(16.0, 756, 3, 2, "You edge across the ledge.");
			case MONKEY_BARS_1:
			case MONKEY_BARS_2:
				return new Obstacle(14.0, 744, 3, 2, "You swing across the monkey bars.");
			case HAND_HOLDS_1:
			case HAND_HOLDS_2:
				return new Obstacle(22.0, 756, 3, 3, "You climb across the hand holds.");
			case FLOOR_SPIKES:
				return new Obstacle(24.0, 3067, 2, 3, "You dodge the floor spikes.");
			case PRESSURE_PAD:
				return new Obstacle(26.0, 3067, 2, 3, "You step across the pressure pads.");
			case SPINNING_BLADES:
				return new Obstacle(28.0, 1603, 2, 3, "You dodge the spinning blades.");
			case BLADE_1:
			case BLADE_2:
			case BLADE_3:
				return new Obstacle(0.0, 1603, 2, 2, "You time your run past the saw blade.");
			default:
				return null;
		}
	}

	private boolean shouldFail(Obstacle obstacle) {
		int level = c.playerLevel[Constants.AGILITY];
		int chance = obstacle.failChance - Math.max(0, level - 40) / 3;
		chance = Math.max(0, Math.min(45, chance));
		return chance > 0 && Misc.random(99) < chance;
	}

	private void failObstacle(Obstacle obstacle) {
		int damage = Math.max(1, Math.min(5, obstacle.failDamage));
		c.dealDamage(damage);
		c.handleHitMask(damage);
		c.getPacketSender().sendMessage("You slip and hurt yourself.");
		Tile destination = obstacleDestination();
		moveLater(destination.x, destination.y, destination.h, obstacle.animation, 1, null);
	}

	private Tile obstacleDestination() {
		Tile spanDestination = obstacleSpanDestination();
		if (spanDestination != null) {
			return spanDestination;
		}
		int dx = c.objectX - c.getX();
		int dy = c.objectY - c.getY();
		int destX = c.objectX;
		int destY = c.objectY;
		if (Math.abs(dx) >= Math.abs(dy) && dx != 0) {
			destX = c.objectX + (dx > 0 ? 1 : -1);
		} else if (dy != 0) {
			destY = c.objectY + (dy > 0 ? 1 : -1);
		} else {
			destY = c.objectY + 1;
		}
		return clampToArena(destX, destY);
	}

	private Tile obstacleSpanDestination() {
		for (ObstacleSpan span : OBSTACLE_SPANS) {
			if (span.matches(c.objectId, c.objectX, c.objectY)) {
				return span.destination(c.getX(), c.getY(), c.objectX, c.objectY);
			}
		}
		return null;
	}

	private Tile clampToArena(int x, int y) {
		x = Math.max(2761, Math.min(2806, x));
		y = Math.max(9544, Math.min(9592, y));
		return new Tile(x, y, 3);
	}

	private boolean nearClickedObject(int distance) {
		return c.heightLevel == 3
				&& Math.abs(c.getX() - c.objectX) <= distance
				&& Math.abs(c.getY() - c.objectY) <= distance;
	}

	private boolean isInArena() {
		return isArenaTile(c.getX(), c.getY(), c.heightLevel);
	}

	private static boolean isArenaTile(int x, int y, int height) {
		return height == 3 && x >= 2760 && x <= 2810 && y >= 9543 && y <= 9593;
	}

	private void addXp(double xp) {
		if (xp > 0.0) {
			c.getPlayerAssistant().addSkillXP(xp, Constants.AGILITY);
		}
	}

	private void moveLater(final int x, final int y, final int h, int animation, int delay, final String message) {
		c.getPlayerAction().setAction(true);
		c.getPlayerAction().canWalk(false);
		if (animation > 0) {
			c.startAnimation(animation);
		}
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
				sendActiveHint();
				container.stop();
			}

			@Override
			public void stop() {
			}
		}, Math.max(1, delay));
	}

	private static final class Obstacle {
		private final double xp;
		private final int animation;
		private final int delay;
		private final int failDamage;
		private final int failChance;
		private final String successMessage;

		private Obstacle(double xp, int animation, int delay, int failDamage, String successMessage) {
			this.xp = xp;
			this.animation = animation;
			this.delay = delay;
			this.failDamage = failDamage;
			this.failChance = failDamage * 6;
			this.successMessage = successMessage;
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

		private boolean matches(int x, int y, int h) {
			return this.x == x && this.y == y && this.h == h;
		}
	}

	private static final class ObstacleSpan {
		private final int minId;
		private final int maxId;
		private final int minX;
		private final int maxX;
		private final int minY;
		private final int maxY;
		private final int crossingAxis;

		private ObstacleSpan(int minId, int maxId, int minX, int maxX, int minY, int maxY, int crossingAxis) {
			this.minId = minId;
			this.maxId = maxId;
			this.minX = minX;
			this.maxX = maxX;
			this.minY = minY;
			this.maxY = maxY;
			this.crossingAxis = crossingAxis;
		}

		private boolean matches(int objectId, int objectX, int objectY) {
			return objectId >= minId && objectId <= maxId
					&& objectX >= minX && objectX <= maxX
					&& objectY >= minY && objectY <= maxY;
		}

		private Tile destination(int playerX, int playerY, int objectX, int objectY) {
			int x = clamp(playerX, minX, maxX);
			int y = clamp(playerY, minY, maxY);
			if (crossingAxis == CROSS_X) {
				if (playerX <= minX) {
					x = maxX + 1;
				} else if (playerX > maxX) {
					x = minX - 1;
				} else {
					x = playerX <= objectX ? maxX + 1 : minX - 1;
				}
			} else {
				if (playerY <= minY) {
					y = maxY + 1;
				} else if (playerY > maxY) {
					y = minY - 1;
				} else {
					y = playerY <= objectY ? maxY + 1 : minY - 1;
				}
			}
			return new Tile(Math.max(2761, Math.min(2806, x)),
					Math.max(9544, Math.min(9592, y)), 3);
		}

		private int clamp(int value, int min, int max) {
			return Math.max(min, Math.min(max, value));
		}
	}
}
