import java.awt.Color;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.Frame;
import java.awt.Graphics;
import java.awt.GraphicsEnvironment;
import java.awt.Image;
import java.awt.Rectangle;
import java.awt.Shape;
import java.awt.image.ImageObserver;

final class ClientWindow {

	private static final int MAX_SCALE = 4;
	private static final int MIN_GAME_WIDTH = 360;
	private static final int MIN_GAME_HEIGHT = 236;
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

	static Dimension minimumGameSize() {
		return new Dimension(MIN_GAME_WIDTH, MIN_GAME_HEIGHT);
	}

	static boolean applyConfiguredTile(Frame frame) {
		int total = ClientSettings.WINDOW_TILE_TOTAL;
		if (total <= 1) {
			return false;
		}
		int slot = ClientSettings.WINDOW_TILE_SLOT;
		if (slot < 0) {
			slot = 0;
		}
		Rectangle cell = tileCell(slot, total);
		frame.setBounds(cell);
		frame.validate();
		return true;
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

	private static Rectangle tileCell(int slot, int total) {
		Rectangle screen = GraphicsEnvironment.getLocalGraphicsEnvironment().getMaximumWindowBounds();
		int clampedTotal = Math.max(1, total);
		int clampedSlot = Math.max(0, Math.min(slot, clampedTotal - 1));
		int columns = columnsFor(clampedTotal);
		int rows = (int) Math.ceil(clampedTotal / (double) columns);
		int column = clampedSlot % columns;
		int row = clampedSlot / columns;
		int x = screen.x + (screen.width * column) / columns;
		int y = screen.y + (screen.height * row) / rows;
		int right = screen.x + (screen.width * (column + 1)) / columns;
		int bottom = screen.y + (screen.height * (row + 1)) / rows;
		return new Rectangle(x, y, Math.max(1, right - x), Math.max(1, bottom - y));
	}

	private static int columnsFor(int total) {
		if (total <= 1) {
			return 1;
		}
		if (total == 2) {
			return 2;
		}
		return (int) Math.ceil(Math.sqrt(total));
	}
}
