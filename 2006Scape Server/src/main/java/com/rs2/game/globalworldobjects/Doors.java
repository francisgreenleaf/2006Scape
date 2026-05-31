package com.rs2.game.globalworldobjects;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import com.rs2.GameEngine;
import com.rs2.game.objects.Objects;
import com.rs2.game.players.Player;
import com.rs2.util.DoorData;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.*;
import java.lang.reflect.Type;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Scanner;
import java.util.Set;

public class Doors {

    private static final boolean USE_INDEXED_DOOR_LOOKUP = true;
    private static final boolean VALIDATE_INDEXED_DOOR_LOOKUP = false;
    private static final boolean LOG_DOOR_LOOKUP = true;
    private static final boolean LOG_EACH_DOOR_USE = true;
    private static final int DOOR_USAGE_LOG_INTERVAL = 100;
    private static final int DOOR_RELOAD_SKIP_LOG_INTERVAL = 100;

    private static Doors singleton = null;

    private final List<Doors> doors = new ArrayList<>();
    private final Map<Long, Doors> doorsByKey = new HashMap<>();
    private final Set<Integer> knownDoorIds = new HashSet<>();

    private File doorFile;
    private boolean loaded;
    private int skippedReloads;
    private long doorLookupRequests;
    private long indexedDoorHits;
    private long linearFallbackHits;
    private long indexedDoorMissesForKnownIds;
    private long doubleDoorFallbacks;
    private long handledDoors;

    public static Doors getSingleton() {
        if (singleton == null) {
            singleton = new Doors(System.getProperty("user.dir") + "/data/doors.json");
        }
        return singleton;
    }

    private Doors(String file) {
        doorFile = new File(file);
    }

    private Doors(int door, int x, int y, int z, int face, int type, int open) {
        this.doorId = door;
        this.originalId = door;
        this.doorX = x;
        this.doorY = y;
        this.originalX = x;
        this.originalY = y;
        this.doorZ = z;
        this.originalFace = face;
        this.currentFace = face;
        this.type = type;
        this.open = open;
    }

    private Doors getDoor(int id, int x, int y, int z) {
        for (Doors d : doors) {
            if (d.doorId == id) {
                if (d.doorX == x && d.doorY == y && d.doorZ == z) {
                    return d;
                }
            }
        }
        return null;
    }

    private Doors findDoor(int id, int x, int y, int z) {
        if (!USE_INDEXED_DOOR_LOOKUP) {
            return getDoor(id, x, y, z);
        }

        doorLookupRequests++;
        Doors indexedDoor = doorsByKey.get(doorKey(id, x, y, z));
        if (indexedDoor != null) {
            indexedDoorHits++;
            if (VALIDATE_INDEXED_DOOR_LOOKUP) {
                Doors linearDoor = getDoor(id, x, y, z);
                if (linearDoor != indexedDoor) {
                    logDoor("Indexed lookup mismatch for id=" + id + " x=" + x + " y=" + y + " z=" + z
                            + "; indexed=" + describeDoor(indexedDoor) + ", linear=" + describeDoor(linearDoor));
                    if (linearDoor != null) {
                        return linearDoor;
                    }
                }
            }
            return indexedDoor;
        }

        if (knownDoorIds.contains(id)) {
            indexedDoorMissesForKnownIds++;
            Doors linearDoor = getDoor(id, x, y, z);
            if (linearDoor != null) {
                linearFallbackHits++;
                indexDoor(linearDoor);
                logDoor("Repaired indexed lookup miss for known door id=" + id + " x=" + x + " y=" + y + " z=" + z
                        + " -> " + describeDoor(linearDoor));
            }
            return linearDoor;
        }

        return null;
    }

    private long doorKey(Doors d) {
        return doorKey(d.doorId, d.doorX, d.doorY, d.doorZ);
    }

    private long doorKey(int id, int x, int y, int z) {
        return (((long) z & 0xFFFFL) << 48)
                | (((long) id & 0xFFFFL) << 32)
                | (((long) x & 0xFFFFL) << 16)
                | ((long) y & 0xFFFFL);
    }

    private void indexDoor(Doors d) {
        knownDoorIds.add(d.originalId);
        knownDoorIds.add(d.originalId - 1);
        knownDoorIds.add(d.originalId + 1);
        knownDoorIds.add(d.doorId);
        knownDoorIds.add(d.doorId - 1);
        knownDoorIds.add(d.doorId + 1);

        long key = doorKey(d);
        Doors previous = doorsByKey.get(key);
        if (previous != null && previous != d) {
            logDoor("Duplicate door index key kept existing=" + describeDoor(previous) + ", ignored=" + describeDoor(d));
            return;
        }
        doorsByKey.put(key, d);
    }

    private void reindexDoor(Doors d, long oldKey) {
        if (doorsByKey.isEmpty()) {
            return;
        }

        Doors previous = doorsByKey.get(oldKey);
        if (previous == d) {
            doorsByKey.remove(oldKey);
        } else if (previous != null) {
            logDoor("Door index old-key owner changed while reindexing " + describeDoor(d)
                    + "; old owner=" + describeDoor(previous));
        }
        indexDoor(d);
    }

    private String describeDoor(Doors d) {
        if (d == null) {
            return "null";
        }
        return "{id=" + d.doorId + ", originalId=" + d.originalId + ", x=" + d.doorX + ", y=" + d.doorY
                + ", z=" + d.doorZ + ", face=" + d.currentFace + ", type=" + d.type + ", open=" + d.open + "}";
    }

    private void logDoor(String message) {
        if (LOG_DOOR_LOOKUP) {
            System.out.println("[Doors] " + message);
        }
    }

    private void recordHandledDoor(Player player, int clickedId, int clickedX, int clickedY, int clickedZ,
            int oldDoorId, int oldDoorX, int oldDoorY, int oldDoorFace, Doors d) {
        handledDoors++;
        if (LOG_EACH_DOOR_USE) {
            logDoor("handled player=" + player.playerName + ", clicked={id=" + clickedId + ", x=" + clickedX
                    + ", y=" + clickedY + ", z=" + clickedZ + "}, before={id=" + oldDoorId + ", x="
                    + oldDoorX + ", y=" + oldDoorY + ", face=" + oldDoorFace + "}, after=" + describeDoor(d));
        }
        if (LOG_DOOR_LOOKUP && handledDoors % DOOR_USAGE_LOG_INTERVAL == 0) {
            logDoor("usage handled=" + handledDoors + ", lookupRequests=" + doorLookupRequests
                    + ", indexedHits=" + indexedDoorHits + ", linearFallbackHits=" + linearFallbackHits
                    + ", knownIdMisses=" + indexedDoorMissesForKnownIds + ", doubleDoorFallbacks="
                    + doubleDoorFallbacks + ", indexSize=" + doorsByKey.size() + ", doors=" + doors.size());
        }
    }

    public boolean handleDoor(Player player, int id, int x, int y, int z) {
        Doors d = findDoor(id, x, y, z);

        if (d == null) {
            //System.out.println("D: " + id + " null debug x: " + x + " y: " + y + ".");
            if (knownDoorIds.contains(id)) {
                doubleDoorFallbacks++;
                logDoor("Known single-door id fell through to double-door handler id=" + id + " x=" + x + " y=" + y + " z=" + z);
            }
            return DoubleDoors.getSingleton().handleDoor(player, id, x, y, z);
        }

        //todo: improvment: if player manage to get to door then open the door.
        if (player.distanceToPoint(x, y) > 1) {
            //System.out.println("Door (single): " + id + " not in distance debug at x: " + x + " y: " + y + ".");
            return false;
        }

        long oldDoorKey = doorKey(d);
        int oldDoorId = d.doorId;
        int oldDoorX = d.doorX;
        int oldDoorY = d.doorY;
        int oldDoorFace = d.currentFace;

        //Remove clipping for old door (gets added back in placeObject)
        //Region.removeClipping(x, y, z);

        int xAdjustment = 0, yAdjustment = 0;
        if (d.type == 0) {
            if (d.open == 0) {
                if (d.originalFace == 0 && d.currentFace == 0) {
                    xAdjustment = -1;
                } else if (d.originalFace == 1 && d.currentFace == 1) {
                    yAdjustment = 1;
                } else if (d.originalFace == 2 && d.currentFace == 2) {
                    xAdjustment = 1;
                } else if (d.originalFace == 3 && d.currentFace == 3) {
                    yAdjustment = -1;
                }
            } else if (d.open == 1) {
                if (d.originalFace == 0 && d.currentFace == 0) {
                    yAdjustment = 1;
                } else if (d.originalFace == 1 && d.currentFace == 1) {
                    xAdjustment = 1;
                } else if (d.originalFace == 2 && d.currentFace == 2) {
                    yAdjustment = -1;
                } else if (d.originalFace == 3 && d.currentFace == 3) {
                    xAdjustment = -1;
                }
            }
        } else if (d.type == 9) {
            if (d.open == 0) {
                if (d.originalFace == 0 && d.currentFace == 0) {
                    xAdjustment = 1;
                } else if (d.originalFace == 1 && d.currentFace == 1) {
                    xAdjustment = 1;
                } else if (d.originalFace == 2 && d.currentFace == 2) {
                    xAdjustment = -1;
                } else if (d.originalFace == 3 && d.currentFace == 3) {
                    xAdjustment = -1;
                }
            } else if (d.open == 1) {
                if (d.originalFace == 0 && d.currentFace == 0) {
                    xAdjustment = 1;
                } else if (d.originalFace == 1 && d.currentFace == 1) {
                    xAdjustment = 1;
                } else if (d.originalFace == 2 && d.currentFace == 2) {
                    xAdjustment = -1;
                } else if (d.originalFace == 3 && d.currentFace == 3) {
                    xAdjustment = -1;
                }
            }
        }
        if (xAdjustment != 0 || yAdjustment != 0) {
            Objects o = new Objects(-1, d.doorX, d.doorY, d.doorZ, 0, d.type, 0);
            GameEngine.objectHandler.placeObject(o);
        }
        if (d.doorX == d.originalX && d.doorY == d.originalY) {
            d.doorX += xAdjustment;
            d.doorY += yAdjustment;
        } else {
            Objects o = new Objects(-1, d.doorX, d.doorY, d.doorZ, 0, d.type, 0);
            GameEngine.objectHandler.placeObject(o);
            d.doorX = d.originalX;
            d.doorY = d.originalY;
        }
        if (d.doorId == d.originalId) {
            if (d.open == 0) {
                d.doorId += 1;
            } else if (d.open == 1) {
                d.doorId -= 1;
            }
        } else if (d.doorId != d.originalId) {
            if (d.open == 0) {
                d.doorId -= 1;
            } else if (d.open == 1) {
                d.doorId += 1;
            }
        }
        GameEngine.objectHandler.placeObject(new Objects(d.doorId, d.doorX, d.doorY, d.doorZ, getNextFace(d), d.type, 0));
        reindexDoor(d, oldDoorKey);
        recordHandledDoor(player, id, x, y, z, oldDoorId, oldDoorX, oldDoorY, oldDoorFace, d);
        return true;
    }

    private int getNextFace(Doors d) {
        int f = d.originalFace;
        if (d.type == 0) {
            if (d.open == 0) {
                if (d.originalFace == 0 && d.currentFace == 0) {
                    f = 1;
                } else if (d.originalFace == 1 && d.currentFace == 1) {
                    f = 2;
                } else if (d.originalFace == 2 && d.currentFace == 2) {
                    f = 3;
                } else if (d.originalFace == 3 && d.currentFace == 3) {
                    f = 0;
                } else if (d.originalFace != d.currentFace) {
                    f = d.originalFace;
                }
            } else if (d.open == 1) {
                if (d.originalFace == 0 && d.currentFace == 0) {
                    f = 3;
                } else if (d.originalFace == 1 && d.currentFace == 1) {
                    f = 0;
                } else if (d.originalFace == 2 && d.currentFace == 2) {
                    f = 1;
                } else if (d.originalFace == 3 && d.currentFace == 3) {
                    f = 2;
                } else if (d.originalFace != d.currentFace) {
                    f = d.originalFace;
                }
            }
        } else if (d.type == 9) {
            if (d.open == 0) {
                if (d.originalFace == 0 && d.currentFace == 0) {
                    f = 3;
                } else if (d.originalFace == 1 && d.currentFace == 1) {
                    f = 2;
                } else if (d.originalFace == 2 && d.currentFace == 2) {
                    f = 1;
                } else if (d.originalFace == 3 && d.currentFace == 3) {
                    f = 0;
                } else if (d.originalFace != d.currentFace) {
                    f = d.originalFace;
                }
            } else if (d.open == 1) {
                if (d.originalFace == 0 && d.currentFace == 0) {
                    f = 3;
                } else if (d.originalFace == 1 && d.currentFace == 1) {
                    f = 0;
                } else if (d.originalFace == 2 && d.currentFace == 2) {
                    f = 1;
                } else if (d.originalFace == 3 && d.currentFace == 3) {
                    f = 2;
                } else if (d.originalFace != d.currentFace) {
                    f = d.originalFace;
                }
            }
        }
        d.currentFace = f;
        return f;
    }

    public void load() {
        if (loaded) {
            skippedReloads++;
            if (LOG_DOOR_LOOKUP && (skippedReloads == 1 || skippedReloads % DOOR_RELOAD_SKIP_LOG_INTERVAL == 0)) {
                logDoor("Skipped " + skippedReloads + " duplicate door reload requests; doors=" + doors.size()
                        + ", indexSize=" + doorsByKey.size());
            }
            return;
        }

        Gson gson = new Gson();
        long start = System.currentTimeMillis();
        try {
            Type collectionType = new TypeToken<DoorData[]>() {
            }.getType();
            DoorData[] doorData = gson.fromJson(new FileReader(doorFile), collectionType);

            for (DoorData data : doorData) {
                for (DoorData.Location location : data.getLocations()) {
                    Doors door = new Doors(data.getId(), location.getX(), location.getY(), location.getHeight(), data.getFace(), data.getType(), alreadyOpen(data.getId()) ? 1 : 0);
                    doors.add(door);
                    indexDoor(door);
                }
            }
            loaded = true;
            logDoor("Loaded " + doors.size() + " doors in " + (System.currentTimeMillis() - start)
                    + " ms; indexedLookup=" + USE_INDEXED_DOOR_LOOKUP + ", validation="
                    + VALIDATE_INDEXED_DOOR_LOOKUP + ", indexSize=" + doorsByKey.size());
            //singleton.writeJsonDump();
        } catch (FileNotFoundException e) {
            e.printStackTrace();
        }
        //System.out.println("Loaded "+ doors.size() +" doors in "+ (System.currentTimeMillis() - start) +" ms.");
    }

    private void writeJsonDump() throws FileNotFoundException {
        try (Scanner scanner = new Scanner(new FileReader(doorFile))) {
            while (scanner.hasNextLine()) {
                processLine(scanner.nextLine());
            }
        }
    }

    protected void processLine(String line) {
        JSONArray array   = new JSONArray();
        Scanner   scanner = new Scanner(line);
        scanner.useDelimiter(" ");
        try {
            while (scanner.hasNextLine()) {
                int id     = Integer.parseInt(scanner.next());
                int x      = Integer.parseInt(scanner.next());
                int y      = Integer.parseInt(scanner.next());
                int face   = Integer.parseInt(scanner.next());
                int height = Integer.parseInt(scanner.next());
                int type   = Integer.parseInt(scanner.next());

                JSONObject object = new JSONObject();

                object.put("id", id);

                JSONArray  jsonArray = new JSONArray();
                JSONObject object1   = new JSONObject();
                object1.put("x", x);
                object1.put("y", y);
                object1.put("height", height);
                jsonArray.put(0, object1);
                object.put("location", jsonArray);

                object.put("face", face);
                object.put("type", type);

                array.put(object);
            }
        } finally {
            scanner.close();

            try {
                FileWriter fileWriter = new FileWriter("doors-dump.json");
                fileWriter.write(array.toString());

                System.out.println(array.toString());
            } catch (IOException e) {
                e.printStackTrace();
            }
        }
    }

    private boolean alreadyOpen(int id) {
        for (int openDoor : OPEN_DOORS) {
            if (openDoor == id) {
                return true;
            }
        }
        return false;
    }

    private int doorId;
    private int originalId;
    private int doorX;
    private int doorY;
    private int originalX;
    private int originalY;
    private int doorZ;
    private int originalFace;
    private int currentFace;
    private int type;
    private int open;

    private static final int[] OPEN_DOORS = {
            1504, 1514, 1517, 1520, 1531,
            1534, 2033, 2035, 2037, 2998,
            3271, 4468, 4697, 6101, 6103,
            6105, 6107, 6109, 6111, 6113,
            6115, 6976, 6978, 8696, 8819,
            10261, 10263, 10265, 11708, 11710,
            11712, 11715, 11994, 12445, 13002,
    };

}
