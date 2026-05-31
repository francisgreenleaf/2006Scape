package com.rs2.world.clip;

import java.util.ArrayList;
import java.util.List;
import com.rs2.game.players.Player;
import com.rs2.util.Misc;

public class PathFinder {

	private static final PathFinder pathFinder = new PathFinder();
	private static final int LOCAL_MAP_SIZE = 104;
	private static final int MAX_PATH_QUEUE_SIZE = 4000;
	private static final int PATH_QUEUE_OVERFLOW_ROOM = 8;

	public static PathFinder getPathFinder() {
		return pathFinder;
	}

	public void findRoute(Player player, int destX, int destY, boolean moveNear,
			int xLength, int yLength) {
		if (destX == player.getLocalX() && destY == player.getLocalY() && !moveNear) {
			player.getPacketSender().sendMessage("ERROR!");
			return;
		}
		destX = destX - 8 * player.getMapRegionX();
		destY = destY - 8 * player.getMapRegionY();
		int[][] via = new int[LOCAL_MAP_SIZE][LOCAL_MAP_SIZE];
		int[][] cost = new int[LOCAL_MAP_SIZE][LOCAL_MAP_SIZE];
		int[] tileQueueX = new int[MAX_PATH_QUEUE_SIZE + PATH_QUEUE_OVERFLOW_ROOM];
		int[] tileQueueY = new int[MAX_PATH_QUEUE_SIZE + PATH_QUEUE_OVERFLOW_ROOM];
		for (int xx = 0; xx < LOCAL_MAP_SIZE; xx++) {
			for (int yy = 0; yy < LOCAL_MAP_SIZE; yy++) {
				cost[xx][yy] = 99999999;
			}
		}
		int curX = player.getLocalX();
		int curY = player.getLocalY();
		if (curX < 0 || curY < 0 || curX >= LOCAL_MAP_SIZE || curY >= LOCAL_MAP_SIZE) {
			return;
		}
		via[curX][curY] = 99;
		cost[curX][curY] = 0;
		int tail = 0;
		int queueSize = enqueue(tileQueueX, tileQueueY, 0, curX, curY);
		boolean foundPath = false;
		while (tail != queueSize && queueSize < MAX_PATH_QUEUE_SIZE) {
			curX = tileQueueX[tail];
			curY = tileQueueY[tail];
			int curAbsX = player.getMapRegionX() * 8 + curX;
			int curAbsY = player.getMapRegionY() * 8 + curY;
			if (curX == destX && curY == destY) {
				foundPath = true;
				break;
			}
			tail++;
			int thisCost = cost[curX][curY] + 1;
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, 0, -1, 1, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, -1, 0, 2, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, 0, 1, 4, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, 1, 0, 8, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, -1, -1, 3, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, -1, 1, 6, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, 1, -1, 9, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, 1, 1, 12, thisCost);
		}
		if (!foundPath) {
			if (moveNear) {
				int i_223_ = 1000;
				int thisCost = 100;
				int i_225_ = 10;
				for (int x = destX - i_225_; x <= destX + i_225_; x++) {
					for (int y = destY - i_225_; y <= destY + i_225_; y++) {
						if (x >= 0 && y >= 0 && x < 104 && y < 104
								&& cost[x][y] < 100) {
							int i_228_ = 0;
							if (x < destX) {
								i_228_ = destX - x;
							} else if (x > destX + xLength - 1) {
								i_228_ = x - (destX + xLength - 1);
							}
							int i_229_ = 0;
							if (y < destY) {
								i_229_ = destY - y;
							} else if (y > destY + yLength - 1) {
								i_229_ = y - (destY + yLength - 1);
							}
							int i_230_ = i_228_ * i_228_ + i_229_ * i_229_;
							if (i_230_ < i_223_ || i_230_ == i_223_
									&& cost[x][y] < thisCost) {
								i_223_ = i_230_;
								thisCost = cost[x][y];
								curX = x;
								curY = y;
							}
						}
					}
				}
				if (i_223_ == 1000) {
					return;
				}
			} else {
				return;
			}
		}
		tail = 0;
		tileQueueX[tail] = curX;
		tileQueueY[tail++] = curY;
		int l5;
		for (int j5 = l5 = via[curX][curY]; curX != player.getLocalX()
				|| curY != player.getLocalY(); j5 = via[curX][curY]) {
			if (j5 != l5) {
				l5 = j5;
				tileQueueX[tail] = curX;
				tileQueueY[tail++] = curY;
			}
			if ((j5 & 2) != 0) {
				curX++;
			} else if ((j5 & 8) != 0) {
				curX--;
			}
			if ((j5 & 1) != 0) {
				curY++;
			} else if ((j5 & 4) != 0) {
				curY--;
			}
		}
		player.resetWalkingQueue();
		int size = tail--;
		int pathX = player.getMapRegionX() * 8 + tileQueueX[tail];
		int pathY = player.getMapRegionY() * 8 + tileQueueY[tail];
		player.addToWalkingQueue(localize(pathX, player.getMapRegionX()),
				localize(pathY, player.getMapRegionY()));
		for (int i = 1; i < size; i++) {
			tail--;
			pathX = player.getMapRegionX() * 8 + tileQueueX[tail];
			pathY = player.getMapRegionY() * 8 + tileQueueY[tail];
			player.addToWalkingQueue(localize(pathX, player.getMapRegionX()),
					localize(pathY, player.getMapRegionY()));
		}
	}

	public List<int[]> findRouteTiles(Player player, int destX, int destY, boolean moveNear,
			int xLength, int yLength) {
		ArrayList<int[]> route = new ArrayList<int[]>();
		if (player == null || destX < 0 || destY < 0) {
			return route;
		}
		destX = destX - 8 * player.getMapRegionX();
		destY = destY - 8 * player.getMapRegionY();
		if (destX < 0 || destY < 0 || destX >= 104 || destY >= 104) {
			return route;
		}
		if (destX == player.getLocalX() && destY == player.getLocalY() && !moveNear) {
			return route;
		}
		int[][] via = new int[LOCAL_MAP_SIZE][LOCAL_MAP_SIZE];
		int[][] cost = new int[LOCAL_MAP_SIZE][LOCAL_MAP_SIZE];
		int[] tileQueueX = new int[MAX_PATH_QUEUE_SIZE + PATH_QUEUE_OVERFLOW_ROOM];
		int[] tileQueueY = new int[MAX_PATH_QUEUE_SIZE + PATH_QUEUE_OVERFLOW_ROOM];
		for (int xx = 0; xx < LOCAL_MAP_SIZE; xx++) {
			for (int yy = 0; yy < LOCAL_MAP_SIZE; yy++) {
				cost[xx][yy] = 99999999;
			}
		}
		int curX = player.getLocalX();
		int curY = player.getLocalY();
		if (curX < 0 || curY < 0 || curX >= LOCAL_MAP_SIZE || curY >= LOCAL_MAP_SIZE) {
			return route;
		}
		via[curX][curY] = 99;
		cost[curX][curY] = 0;
		int tail = 0;
		int queueSize = enqueue(tileQueueX, tileQueueY, 0, curX, curY);
		boolean foundPath = false;
		while (tail != queueSize && queueSize < MAX_PATH_QUEUE_SIZE) {
			curX = tileQueueX[tail];
			curY = tileQueueY[tail];
			int curAbsX = player.getMapRegionX() * 8 + curX;
			int curAbsY = player.getMapRegionY() * 8 + curY;
			if (curX == destX && curY == destY) {
				foundPath = true;
				break;
			}
			tail++;
			int thisCost = cost[curX][curY] + 1;
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, 0, -1, 1, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, -1, 0, 2, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, 0, 1, 4, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, 1, 0, 8, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, -1, -1, 3, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, -1, 1, 6, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, 1, -1, 9, thisCost);
			queueSize = addRouteStep(player, via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, 1, 1, 12, thisCost);
		}
		if (!foundPath) {
			if (!moveNear) {
				return route;
			}
			int bestDistance = 1000;
			int bestCost = 100;
			int radius = 10;
			for (int x = destX - radius; x <= destX + radius; x++) {
				for (int y = destY - radius; y <= destY + radius; y++) {
					if (x >= 0 && y >= 0 && x < 104 && y < 104 && cost[x][y] < 100) {
						int dx = 0;
						if (x < destX) {
							dx = destX - x;
						} else if (x > destX + xLength - 1) {
							dx = x - (destX + xLength - 1);
						}
						int dy = 0;
						if (y < destY) {
							dy = destY - y;
						} else if (y > destY + yLength - 1) {
							dy = y - (destY + yLength - 1);
						}
						int score = dx * dx + dy * dy;
						if (score < bestDistance || score == bestDistance && cost[x][y] < bestCost) {
							bestDistance = score;
							bestCost = cost[x][y];
							curX = x;
							curY = y;
						}
					}
				}
			}
			if (bestDistance == 1000) {
				return route;
			}
		}
		tail = 0;
		tileQueueX[tail] = curX;
		tileQueueY[tail++] = curY;
		int previousDirection;
		for (int direction = previousDirection = via[curX][curY]; curX != player.getLocalX()
				|| curY != player.getLocalY(); direction = via[curX][curY]) {
			if (direction != previousDirection) {
				previousDirection = direction;
				tileQueueX[tail] = curX;
				tileQueueY[tail++] = curY;
			}
			if ((direction & 2) != 0) {
				curX++;
			} else if ((direction & 8) != 0) {
				curX--;
			}
			if ((direction & 1) != 0) {
				curY++;
			} else if ((direction & 4) != 0) {
				curY--;
			}
		}
		int size = tail--;
		for (int i = 0; i < size; i++) {
			int pathX = player.getMapRegionX() * 8 + tileQueueX[tail];
			int pathY = player.getMapRegionY() * 8 + tileQueueY[tail];
			route.add(new int[] { pathX, pathY, player.heightLevel });
			tail--;
		}
		return route;
	}

	private int addRouteStep(Player player, int[][] via, int[][] cost, int[] tileQueueX,
			int[] tileQueueY, int queueSize, int curX, int curY, int curAbsX, int curAbsY,
			int dx, int dy, int viaFlag, int thisCost) {
		int nextX = curX + dx;
		int nextY = curY + dy;
		if (nextX < 0 || nextY < 0 || nextX >= LOCAL_MAP_SIZE || nextY >= LOCAL_MAP_SIZE
				|| via[nextX][nextY] != 0) {
			return queueSize;
		}
		if (!canStep(curAbsX, curAbsY, player.heightLevel, dx, dy)) {
			return queueSize;
		}
		queueSize = enqueue(tileQueueX, tileQueueY, queueSize, nextX, nextY);
		via[nextX][nextY] = viaFlag;
		cost[nextX][nextY] = thisCost;
		return queueSize;
	}

	private boolean canStep(int curAbsX, int curAbsY, int height, int dx, int dy) {
		if (dx == 0 && dy == -1) {
			return (Region.getClipping(curAbsX, curAbsY - 1, height) & 0x1280102) == 0;
		}
		if (dx == -1 && dy == 0) {
			return (Region.getClipping(curAbsX - 1, curAbsY, height) & 0x1280108) == 0;
		}
		if (dx == 0 && dy == 1) {
			return (Region.getClipping(curAbsX, curAbsY + 1, height) & 0x1280120) == 0;
		}
		if (dx == 1 && dy == 0) {
			return (Region.getClipping(curAbsX + 1, curAbsY, height) & 0x1280180) == 0;
		}
		if (dx == -1 && dy == -1) {
			return (Region.getClipping(curAbsX - 1, curAbsY - 1, height) & 0x128010e) == 0
					&& (Region.getClipping(curAbsX - 1, curAbsY, height) & 0x1280108) == 0
					&& (Region.getClipping(curAbsX, curAbsY - 1, height) & 0x1280102) == 0;
		}
		if (dx == -1 && dy == 1) {
			return (Region.getClipping(curAbsX - 1, curAbsY + 1, height) & 0x1280138) == 0
					&& (Region.getClipping(curAbsX - 1, curAbsY, height) & 0x1280108) == 0
					&& (Region.getClipping(curAbsX, curAbsY + 1, height) & 0x1280120) == 0;
		}
		if (dx == 1 && dy == -1) {
			return (Region.getClipping(curAbsX + 1, curAbsY - 1, height) & 0x1280183) == 0
					&& (Region.getClipping(curAbsX + 1, curAbsY, height) & 0x1280180) == 0
					&& (Region.getClipping(curAbsX, curAbsY - 1, height) & 0x1280102) == 0;
		}
		if (dx == 1 && dy == 1) {
			return (Region.getClipping(curAbsX + 1, curAbsY + 1, height) & 0x12801e0) == 0
					&& (Region.getClipping(curAbsX + 1, curAbsY, height) & 0x1280180) == 0
					&& (Region.getClipping(curAbsX, curAbsY + 1, height) & 0x1280120) == 0;
		}
		return false;
	}

	public int getRegionCoordinate(int x) {
		return (x >> 3) - 6;
	}

	public int getLocalCoordinate(int x) {
		return x - 8 * getRegionCoordinate(x);
	}

	public boolean accessible(int x, int y, int heightLevel, int destX, int destY) {
		int baseRegionX = getRegionCoordinate(x);
		int baseRegionY = getRegionCoordinate(y);
		destX = destX - 8 * baseRegionX;
		destY = destY - 8 * baseRegionY;
		if (destX < 0 || destY < 0 || destX >= LOCAL_MAP_SIZE || destY >= LOCAL_MAP_SIZE) {
			return false;
		}
		int[][] via = new int[LOCAL_MAP_SIZE][LOCAL_MAP_SIZE];
		int[][] cost = new int[LOCAL_MAP_SIZE][LOCAL_MAP_SIZE];
		int[] tileQueueX = new int[MAX_PATH_QUEUE_SIZE + PATH_QUEUE_OVERFLOW_ROOM];
		int[] tileQueueY = new int[MAX_PATH_QUEUE_SIZE + PATH_QUEUE_OVERFLOW_ROOM];
		for (int xx = 0; xx < LOCAL_MAP_SIZE; xx++) {
			for (int yy = 0; yy < LOCAL_MAP_SIZE; yy++) {
				cost[xx][yy] = 99999999;
			}
		}
		int curX = getLocalCoordinate(x);
		int curY = getLocalCoordinate(y);
		if (curX < 0 || curY < 0 || curX >= LOCAL_MAP_SIZE || curY >= LOCAL_MAP_SIZE) {
			return false;
		}
		via[curX][curY] = 99;
		cost[curX][curY] = 0;
		int tail = 0;
		int queueSize = enqueue(tileQueueX, tileQueueY, 0, curX, curY);
		boolean foundPath = false;
		while (tail != queueSize && queueSize < MAX_PATH_QUEUE_SIZE) {
			curX = tileQueueX[tail];
			curY = tileQueueY[tail];
			int curAbsX = baseRegionX * 8 + curX;
			int curAbsY = baseRegionY * 8 + curY;
			if (curX == destX && curY == destY) {
				foundPath = true;
				break;
			}
			tail++;
			int thisCost = cost[curX][curY] + 1;
			queueSize = addAccessibleStep(via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, heightLevel, 0, -1, 1, thisCost);
			queueSize = addAccessibleStep(via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, heightLevel, -1, 0, 2, thisCost);
			queueSize = addAccessibleStep(via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, heightLevel, 0, 1, 4, thisCost);
			queueSize = addAccessibleStep(via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, heightLevel, 1, 0, 8, thisCost);
			queueSize = addAccessibleStep(via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, heightLevel, -1, -1, 3, thisCost);
			queueSize = addAccessibleStep(via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, heightLevel, -1, 1, 6, thisCost);
			queueSize = addAccessibleStep(via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, heightLevel, 1, -1, 9, thisCost);
			queueSize = addAccessibleStep(via, cost, tileQueueX, tileQueueY, queueSize,
					curX, curY, curAbsX, curAbsY, heightLevel, 1, 1, 12, thisCost);
		}
		return foundPath;
	}

	private int addAccessibleStep(int[][] via, int[][] cost, int[] tileQueueX,
			int[] tileQueueY, int queueSize, int curX, int curY, int curAbsX, int curAbsY,
			int heightLevel, int dx, int dy, int viaFlag, int thisCost) {
		int nextX = curX + dx;
		int nextY = curY + dy;
		if (nextX < 0 || nextY < 0 || nextX >= LOCAL_MAP_SIZE || nextY >= LOCAL_MAP_SIZE
				|| via[nextX][nextY] != 0) {
			return queueSize;
		}
		if (!canStep(curAbsX, curAbsY, heightLevel, dx, dy)) {
			return queueSize;
		}
		queueSize = enqueue(tileQueueX, tileQueueY, queueSize, nextX, nextY);
		via[nextX][nextY] = viaFlag;
		cost[nextX][nextY] = thisCost;
		return queueSize;
	}

	private int enqueue(int[] tileQueueX, int[] tileQueueY, int queueSize, int x, int y) {
		if (queueSize >= tileQueueX.length) {
			return queueSize;
		}
		tileQueueX[queueSize] = x;
		tileQueueY[queueSize] = y;
		return queueSize + 1;
	}

	public static boolean isProjectilePathClear(int x0, int y0, int z, int x1, int y1) {
		int deltaX = x1 - x0;
		int deltaY = y1 - y0;

		double error = 0;
		final double deltaError = Math.abs(
				(deltaY) / (deltaX == 0
						? ((double) deltaY)
						: ((double) deltaX)));

		int x = x0;
		int y = y0;

		int pX = x;
		int pY = y;

		boolean incrX = x0 < x1;
		boolean incrY = y0 < y1;

		while (true) {
			if (x != x1) {
				x += (incrX ? 1 : -1);
			}

			if (y != y1) {
				error += deltaError;

				if (error >= 0.5) {
					y += (incrY ? 1 : -1);
					error -= 1;
				}
			}

			if (!shootable(x, y, z, pX, pY)) {
				return false;
			}

			if (incrX && incrY
					&& x >= x1 && y >= y1) {
				break;
			} else if (!incrX && !incrY
					&& x <= x1 && y <= y1) {
				break;
			} else if (!incrX && incrY
					&& x <= x1 && y >= y1) {
				break;
			} else if (incrX && !incrY
					&& x >= x1 && y <= y1) {
				break;
			}

			pX = x;
			pY = y;
		}

		return true;
	}

	private static boolean shootable(int x, int y, int z, int px, int py) {
		if (x == px && y == py) {
			return true;
		}

		int[] delta1 = Misc.delta(x, y, px, py);
		int[] delta2 = Misc.delta(px, py, x, y);

		int dir = Misc.directionFromDelta(delta1[0], delta1[1]);
		int dir2 = Misc.directionFromDelta(delta2[0], delta2[1]);

		if (dir == -1 || dir2 == -1) {
			return false;
		}

		return Region.canMove(x, y, z, dir) && Region.canMove(px, py, z, dir2)
				|| Region.canShoot(x, y, z, dir) && Region.canShoot(px, py, z, dir2);
	}

	public int localize(int x, int mapRegion) {
		return x - 8 * mapRegion;
	}

}
