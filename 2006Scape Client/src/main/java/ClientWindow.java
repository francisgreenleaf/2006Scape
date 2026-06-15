import java.awt.Color;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.Frame;
import java.awt.GraphicsEnvironment;
import java.awt.Graphics;
import java.awt.Image;
import java.awt.Rectangle;
import java.awt.Shape;
import java.awt.image.ImageObserver;

final class ClientWindow {

	private static final int MAX_SCALE = 4;
	static final int BASE_WIDTH = 765;
	static final int BASE_HEIGHT = 503;
	static final int NAVBAR_HEIGHT = 25;

	private ClientWindow() {
	}

	static int clampScale(int scale) {
		if (scale < 1) {
			return 1;
		}
		if (scale > MAX_SCALE) {
			return MAX_SCALE;
		}
		return scale;
	}

	static Dimension gameSizeForScale(int scale) {
		int clampedScale = clampScale(scale);
		return new Dimension(BASE_WIDTH * clampedScale, BASE_HEIGHT * clampedScale);
	}

	static boolean configureTile(int slot, int total) {
		if (!isSupportedTile(slot, total)) {
			ClientSettings.CLIENT_TILE_SLOT = 0;
			ClientSettings.CLIENT_TILE_TOTAL = 0;
			return false;
		}
		ClientSettings.CLIENT_TILE_SLOT = slot;
		ClientSettings.CLIENT_TILE_TOTAL = total;
		return true;
	}

	static boolean configureTile(String value) {
		TileSpec spec = parseTileSpec(value);
		if (spec == null) {
			ClientSettings.CLIENT_TILE_SLOT = 0;
			ClientSettings.CLIENT_TILE_TOTAL = 0;
			return false;
		}
		ClientSettings.CLIENT_TILE_SLOT = spec.slot;
		ClientSettings.CLIENT_TILE_TOTAL = spec.total;
		return true;
	}

	static boolean hasConfiguredTile() {
		return isSupportedTile(ClientSettings.CLIENT_TILE_SLOT, ClientSettings.CLIENT_TILE_TOTAL);
	}

	static void clearConfiguredTile() {
		ClientSettings.CLIENT_TILE_SLOT = 0;
		ClientSettings.CLIENT_TILE_TOTAL = 0;
	}

	static void retile(Frame frame) {
		if (frame == null) {
			return;
		}
		if (hasConfiguredTile()) {
			frame.setBounds(tileBounds(ClientSettings.CLIENT_TILE_SLOT, ClientSettings.CLIENT_TILE_TOTAL));
		} else {
			frame.setLocationRelativeTo(null);
		}
	}

	static Rectangle tileBounds(int slot, int total) {
		return tileBounds(GraphicsEnvironment.getLocalGraphicsEnvironment().getMaximumWindowBounds(), slot, total);
	}

	static Rectangle tileBounds(Rectangle usableBounds, int slot, int total) {
		if (usableBounds == null) {
			usableBounds = new Rectangle(0, 0, BASE_WIDTH, BASE_HEIGHT);
		}
		if (!isSupportedTile(slot, total) || total == 1) {
			return new Rectangle(usableBounds);
		}
		if (total == 2) {
			int leftWidth = usableBounds.width / 2;
			if (slot == 1) {
				return new Rectangle(usableBounds.x, usableBounds.y, leftWidth, usableBounds.height);
			}
			return new Rectangle(usableBounds.x + leftWidth, usableBounds.y,
					usableBounds.width - leftWidth, usableBounds.height);
		}

		int col = (slot - 1) % 2;
		int row = (slot - 1) / 2;
		int leftWidth = usableBounds.width / 2;
		int topHeight = usableBounds.height / 2;
		int x = col == 0 ? usableBounds.x : usableBounds.x + leftWidth;
		int y = row == 0 ? usableBounds.y : usableBounds.y + topHeight;
		int width = col == 0 ? leftWidth : usableBounds.width - leftWidth;
		int height = row == 0 ? topHeight : usableBounds.height - topHeight;
		return new Rectangle(x, y, width, height);
	}

	static TileSpec parseTileSpec(String value) {
		if (value == null) {
			return null;
		}
		String trimmed = value.trim();
		if (trimmed.length() == 0) {
			return null;
		}
		String[] parts = trimmed.split("/");
		if (parts.length != 2) {
			return null;
		}
		try {
			int slot = Integer.parseInt(parts[0].trim());
			int total = Integer.parseInt(parts[1].trim());
			if (!isSupportedTile(slot, total)) {
				return null;
			}
			return new TileSpec(slot, total);
		} catch (NumberFormatException e) {
			return null;
		}
	}

	static TileSpec tileForNewClient(int existingClientCount, int currentSlot) {
		int total = tileTotalForClientCount(existingClientCount + 1);
		int childSlot = Math.max(1, Math.min(total, existingClientCount + 1));
		return new TileSpec(childSlot, total);
	}

	static TileSpec tileForCurrentClient(int existingClientCount, int currentSlot) {
		int total = tileTotalForClientCount(Math.max(1, existingClientCount + 1));
		int slot = isSupportedTile(currentSlot, total) ? currentSlot : 1;
		return new TileSpec(slot, total);
	}

	static int tileTotalForClientCount(int clientCount) {
		if (clientCount <= 1) {
			return 1;
		}
		if (clientCount == 2) {
			return 2;
		}
		return 4;
	}

	private static boolean isSupportedTile(int slot, int total) {
		return (total == 1 || total == 2 || total == 4) && slot >= 1 && slot <= total;
	}

	static Rectangle gameViewport(Component component) {
		int width = component.getWidth();
		int height = component.getHeight();
		if (width <= 0 || height <= 0) {
			int scale = clampScale(ClientSettings.CLIENT_SCALE);
			width = BASE_WIDTH * scale;
			height = BASE_HEIGHT * scale;
		}

		double scale = Math.min(width / (double) BASE_WIDTH, height / (double) BASE_HEIGHT);
		if (scale <= 0D) {
			scale = 1D;
		}
		int viewportWidth = Math.max(1, (int) Math.round(BASE_WIDTH * scale));
		int viewportHeight = Math.max(1, (int) Math.round(BASE_HEIGHT * scale));
		return new Rectangle((width - viewportWidth) / 2, (height - viewportHeight) / 2, viewportWidth, viewportHeight);
	}

	static boolean containsGamePoint(Component component, int x, int y) {
		Rectangle viewport = gameViewport(component);
		return x >= viewport.x && y >= viewport.y && x < viewport.x + viewport.width
				&& y < viewport.y + viewport.height;
	}

	static int toGameX(Component component, int x) {
		Rectangle viewport = gameViewport(component);
		return toGameCoordinate(x, viewport.x, viewport.width, BASE_WIDTH);
	}

	static int toGameY(Component component, int y) {
		Rectangle viewport = gameViewport(component);
		return toGameCoordinate(y, viewport.y, viewport.height, BASE_HEIGHT);
	}

	static void drawImage(Component component, Graphics graphics, Image image, int baseX, int baseY, int baseWidth,
			int baseHeight, ImageObserver observer) {
		Rectangle viewport = gameViewport(component);
		if (baseX == 0 && baseY == 0 && baseWidth == BASE_WIDTH && baseHeight == BASE_HEIGHT) {
			Color oldColor = graphics.getColor();
			graphics.setColor(Color.BLACK);
			graphics.fillRect(0, 0, Math.max(1, component.getWidth()), Math.max(1, component.getHeight()));
			graphics.setColor(oldColor);
		}

		double scaleX = viewport.width / (double) BASE_WIDTH;
		double scaleY = viewport.height / (double) BASE_HEIGHT;
		int x = viewport.x + scaled(baseX, scaleX);
		int y = viewport.y + scaled(baseY, scaleY);
		int width = Math.max(1, scaled(baseWidth, scaleX));
		int height = Math.max(1, scaled(baseHeight, scaleY));

		Shape oldClip = graphics.getClip();
		graphics.setClip(viewport);
		graphics.drawImage(image, x, y, width, height, observer);
		graphics.setClip(oldClip);
	}

	private static int toGameCoordinate(int value, int viewportOffset, int viewportSize, int baseSize) {
		double scale = viewportSize / (double) baseSize;
		int coordinate = (int) ((value - viewportOffset) / scale);
		if (coordinate < 0 || coordinate >= baseSize) {
			return -1;
		}
		return coordinate;
	}

	private static int scaled(int value, double scale) {
		return (int) Math.round(value * scale);
	}

	static final class TileSpec {
		final int slot;
		final int total;

		TileSpec(int slot, int total) {
			this.slot = slot;
			this.total = total;
		}

		String asArgument() {
			return slot + "/" + total;
		}
	}
}
