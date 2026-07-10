package com.rs2.game.content.combat.magic;

import com.rs2.Constants;
import com.rs2.game.content.randomevents.RandomEventHandler;
import com.rs2.game.players.Player;

public class MagicTeleports {

	public enum SpellTeleportResult {
		STARTED,
		ALREADY_TELEPORTING,
		WILDERNESS_BLOCKED,
		LEVEL_TOO_LOW,
		MISSING_RUNES,
		GAMEPLAY_REJECTED,
		UNKNOWN_SPELL
	}

	public static void handleLoginText(Player player) {
		player.getPacketSender().sendString("Level 25: Varrock Teleport", 1300);
		player.getPacketSender().sendString("Level 31: Lumbridge Teleport", 1325);
		player.getPacketSender().sendString("Level 37: Falador Teleport", 1350);
		player.getPacketSender().sendString("Level 45: Camelot Teleport", 1382);
		player.getPacketSender().sendString("Level 51: Ardougne Teleport", 1415);
		player.getPacketSender().sendString("Level 54: Paddewwa Teleport", 13037);
		player.getPacketSender().sendString("Level 60: Senntisten Teleport", 13047);
		player.getPacketSender().sendString("Level 66: Kharyrll Teleport", 13055);
		player.getPacketSender().sendString("Level 72: Lassar Teleport", 13063);
		player.getPacketSender().sendString("Level 78: Dareeyak Teleport", 13071);
	}

	public static SpellTeleportResult handleSpellTeleport(Player player, SpellTeleport teleport) {
		if (teleport == null) {
			return SpellTeleportResult.UNKNOWN_SPELL;
		}
		if (player.teleTimer > 0) {
			return SpellTeleportResult.ALREADY_TELEPORTING;
		}
		if (player.wildLevel > 20) {
			player.getPacketSender().sendMessage("You can't teleport above level 20 wilderness.");
			return SpellTeleportResult.WILDERNESS_BLOCKED;
		}
		if (player.playerLevel[Constants.MAGIC] < teleport.getRequiredLevel()) {
			player.getPacketSender().sendMessage("You need a magic level of " + teleport.getRequiredLevel() + " to cast this spell.");
			return SpellTeleportResult.LEVEL_TOO_LOW;
		}
		if (!CastRequirements.hasRunes(player, teleport.getRequiredRunes())) {
			player.getPacketSender().sendMessage("You don't have the required runes to cast this spell.");
			return SpellTeleportResult.MISSING_RUNES;
		}
		RandomEventHandler.addRandom(player);
		player.getPlayerAssistant().startTeleport(teleport.getDestX(), teleport.getDestY(), teleport.getDestZ(), teleport.getType());
		boolean started = player.teleTimer > 0
				&& player.teleX == teleport.getDestX()
				&& player.teleY == teleport.getDestY()
				&& player.teleHeight == teleport.getDestZ();
		if (!started) {
			return SpellTeleportResult.GAMEPLAY_REJECTED;
		}
		CastRequirements.deleteRunes(player, teleport.getRequiredRunes());
		player.getPlayerAssistant().addSkillXP(teleport.getExperienceGained(), Constants.MAGIC);
		return SpellTeleportResult.STARTED;
	}
}
