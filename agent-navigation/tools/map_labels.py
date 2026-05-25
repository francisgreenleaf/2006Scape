"""Shared static and place-derived map labels for cache and topology renders."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP_LABELS_PATH = Path(__file__).resolve()
PLACES_PATH = ROOT / "data" / "places.json"

STATIC_LABELS = [
    {
        "text": "Port Sarim",
        "tile": {"x": 3026, "y": 3218, "height": 0},
        "dx": -34,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Falador",
        "tile": {"x": 2965, "y": 3378, "height": 0},
        "dx": -30,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Rimmington",
        "tile": {"x": 2957, "y": 3215, "height": 0},
        "dx": -44,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Draynor",
        "tile": {"x": 3093, "y": 3245, "height": 0},
        "dx": -30,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Al Kharid",
        "tile": {"x": 3295, "y": 3183, "height": 0},
        "dx": -38,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Edgeville",
        "tile": {"x": 3090, "y": 3500, "height": 0},
        "dx": -38,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "White Wolf Mountain",
        "tile": {"x": 2870, "y": 3437, "height": 0},
        "dx": -88,
        "dy": -24,
        "color": "white",
        "outline": True,
    },
    {
        "text": "Tree Gnome Stronghold",
        "tile": {"x": 2464, "y": 3435, "height": 0},
        "dx": -102,
        "dy": -22,
        "color": "yellow",
    },
    {
        "text": "Seers' Village",
        "tile": {"x": 2708, "y": 3488, "height": 0},
        "dx": -58,
        "dy": -20,
        "color": "yellow",
    },
    {
        "text": "Fishing Guild",
        "tile": {"x": 2605, "y": 3415, "height": 0},
        "dx": -54,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Ranging Guild",
        "tile": {"x": 2658, "y": 3438, "height": 0},
        "dx": -56,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Ardougne",
        "tile": {"x": 2662, "y": 3305, "height": 0},
        "dx": -40,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Port Khazard",
        "tile": {"x": 2665, "y": 3161, "height": 0},
        "dx": -52,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Yanille",
        "tile": {"x": 2606, "y": 3093, "height": 0},
        "dx": -28,
        "dy": -18,
        "color": "yellow",
    },
    {
        "text": "Dark Wizards",
        "tile": {"x": 3222, "y": 3372, "height": 0},
        "dx": -50,
        "dy": -18,
        "color": "white",
        "outline": True,
    },
    {
        "text": "Highwayman",
        "tile": {"x": 3006, "y": 3275, "height": 0},
        "dx": -48,
        "dy": -18,
        "color": "white",
        "outline": True,
    },
]

SUPPRESSED_PLACE_LABELS = {
    "Rimmington Center",
}


def load_places():
    if not PLACES_PATH.exists():
        return []
    data = json.loads(PLACES_PATH.read_text(encoding="utf-8"))
    return data.get("places", [])


def in_bounds(tile, bounds, plane=0):
    return (
        tile is not None
        and int(tile.get("height", 0)) == int(plane)
        and bounds["minX"] <= int(tile["x"]) <= bounds["maxX"]
        and bounds["minY"] <= int(tile["y"]) <= bounds["maxY"]
    )


def poi_kind(place):
    kind = str(place.get("kind") or "").lower()
    tags = [str(tag).lower() for tag in place.get("tags", [])]
    if kind in ("hub", "town"):
        return "town"
    if kind == "bank":
        return "bank"
    if kind == "shop":
        return "shop"
    if kind != "surface_checkpoint" and ("city" in tags or "village" in tags):
        return "town"
    return None


def short_place_label(name):
    replacements = [
        ("Lumbridge Castle Courtyard", "Lumbridge"),
        ("Varrock Square", "Varrock"),
    ]
    for source, target in replacements:
        if name == source:
            return target
    return name


def static_labels_in_bounds(bounds, plane=0):
    return [
        label
        for label in STATIC_LABELS
        if in_bounds(label.get("tile"), bounds, plane=plane)
    ]


def place_labels_in_bounds(bounds, plane=0):
    labels = []
    seen = set()
    for place in load_places():
        tile = place.get("tile")
        if not in_bounds(tile, bounds, plane=plane):
            continue
        kind = poi_kind(place)
        if kind != "town":
            continue
        name = str(place.get("name") or place.get("id") or "").strip()
        if not name or name in SUPPRESSED_PLACE_LABELS:
            continue
        text = short_place_label(name)
        if text in seen:
            continue
        seen.add(text)
        labels.append({
            "kind": kind,
            "text": text,
            "tile": {
                "x": int(tile["x"]),
                "y": int(tile["y"]),
                "height": int(tile.get("height", 0)),
            },
            "color": "yellow",
        })
    return labels


def merge_labels(labels):
    merged = []
    seen = set()
    for label in labels:
        key = str(label.get("text") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(label)
    return merged


def labels_in_bounds(bounds, plane=0):
    return merge_labels(place_labels_in_bounds(bounds, plane=plane) + static_labels_in_bounds(bounds, plane=plane))
