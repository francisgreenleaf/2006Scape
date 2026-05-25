#!/usr/bin/env python3
"""Level-0 reference grid helpers for cache-backed maps.

The grid is a stable shorthand over the level-0 surface cache export. Columns
run west-to-east as A..Z, AA.., and rows default to south-to-north as 1..N.
"""

import argparse
import json
import math
import re

import cache_world_map


LEVEL0_SURFACE_BOUNDS = dict(cache_world_map.LEVEL0_SURFACE_BOUNDS)
DEFAULT_GRID_CELL_TILES = 32
DEFAULT_ROW_ORIGIN = "south"
CELL_RE = re.compile(r"^\s*([A-Za-z]+)\s*[-_ ]?\s*(\d+)\s*$")


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("value must be an integer")
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def nonnegative_int(value):
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("value must be an integer")
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be nonnegative")
    return parsed


def normalize_bounds(bounds=None):
    source = dict(bounds or LEVEL0_SURFACE_BOUNDS)
    normalized = {
        "minX": int(source["minX"]),
        "minY": int(source["minY"]),
        "maxX": int(source["maxX"]),
        "maxY": int(source["maxY"]),
    }
    if normalized["maxX"] < normalized["minX"] or normalized["maxY"] < normalized["minY"]:
        raise ValueError("bounds are inverted")
    return normalized


def column_label(index):
    index = int(index)
    if index < 0:
        raise ValueError("column index must be nonnegative")
    label = ""
    while True:
        label = chr(ord("A") + (index % 26)) + label
        index = index // 26 - 1
        if index < 0:
            return label


def column_index(label):
    text = str(label or "").strip().upper()
    if not text or any(ch < "A" or ch > "Z" for ch in text):
        raise ValueError("column label must contain only letters")
    value = 0
    for ch in text:
        value = value * 26 + ord(ch) - ord("A") + 1
    return value - 1


def grid_dimensions(bounds=None, cell_tiles=DEFAULT_GRID_CELL_TILES):
    bounds = normalize_bounds(bounds)
    cell_tiles = int(cell_tiles)
    width = bounds["maxX"] - bounds["minX"] + 1
    height = bounds["maxY"] - bounds["minY"] + 1
    return {
        "columns": int(math.ceil(width / float(cell_tiles))),
        "rows": int(math.ceil(height / float(cell_tiles))),
    }


def row_label(row_index, bounds=None, cell_tiles=DEFAULT_GRID_CELL_TILES, row_origin=DEFAULT_ROW_ORIGIN):
    row_index = int(row_index)
    if row_index < 0:
        raise ValueError("row index must be nonnegative")
    dimensions = grid_dimensions(bounds, cell_tiles)
    if row_index >= dimensions["rows"]:
        raise ValueError("row index is outside the reference grid")
    if row_origin == "south":
        return str(row_index + 1)
    if row_origin == "north":
        return str(dimensions["rows"] - row_index)
    raise ValueError("row origin must be south or north")


def row_index_from_label(label, bounds=None, cell_tiles=DEFAULT_GRID_CELL_TILES, row_origin=DEFAULT_ROW_ORIGIN):
    try:
        row_number = int(label)
    except ValueError:
        raise ValueError("row label must be numeric")
    dimensions = grid_dimensions(bounds, cell_tiles)
    if row_number < 1 or row_number > dimensions["rows"]:
        raise ValueError("row label is outside the reference grid")
    if row_origin == "south":
        return row_number - 1
    if row_origin == "north":
        return dimensions["rows"] - row_number
    raise ValueError("row origin must be south or north")


def parse_cell(cell, bounds=None, cell_tiles=DEFAULT_GRID_CELL_TILES, row_origin=DEFAULT_ROW_ORIGIN):
    match = CELL_RE.match(str(cell or ""))
    if not match:
        raise ValueError("grid cell must look like AU21")
    col = column_index(match.group(1))
    row = row_index_from_label(match.group(2), bounds, cell_tiles, row_origin)
    dimensions = grid_dimensions(bounds, cell_tiles)
    if col < 0 or col >= dimensions["columns"]:
        raise ValueError("column label is outside the reference grid")
    return {
        "cell": "{}{}".format(column_label(col), row_label(row, bounds, cell_tiles, row_origin)),
        "column": col,
        "columnLabel": column_label(col),
        "row": row,
        "rowLabel": row_label(row, bounds, cell_tiles, row_origin),
    }


def cell_for_tile(tile, bounds=None, cell_tiles=DEFAULT_GRID_CELL_TILES, row_origin=DEFAULT_ROW_ORIGIN):
    bounds = normalize_bounds(bounds)
    x = int(tile["x"])
    y = int(tile["y"])
    cell_tiles = int(cell_tiles)
    col = int(math.floor((x - bounds["minX"]) / float(cell_tiles)))
    row = int(math.floor((y - bounds["minY"]) / float(cell_tiles)))
    dimensions = grid_dimensions(bounds, cell_tiles)
    in_reference_bounds = 0 <= col < dimensions["columns"] and 0 <= row < dimensions["rows"]
    if in_reference_bounds:
        col_label = column_label(col)
        row_text = row_label(row, bounds, cell_tiles, row_origin)
        cell = "{}{}".format(col_label, row_text)
    else:
        col_label = None
        row_text = None
        cell = None
    return {
        "cell": cell,
        "column": col,
        "columnLabel": col_label,
        "row": row,
        "rowLabel": row_text,
        "tile": {"x": x, "y": y, "height": int(tile.get("height", 0))},
        "inReferenceBounds": in_reference_bounds,
        "referenceBounds": bounds,
        "cellTiles": cell_tiles,
        "rowOrigin": row_origin,
    }


def bounds_for_cell(cell, padding=0, bounds=None, cell_tiles=DEFAULT_GRID_CELL_TILES,
                    row_origin=DEFAULT_ROW_ORIGIN):
    reference = normalize_bounds(bounds)
    parsed = parse_cell(cell, reference, cell_tiles, row_origin)
    cell_tiles = int(cell_tiles)
    min_x = reference["minX"] + parsed["column"] * cell_tiles
    min_y = reference["minY"] + parsed["row"] * cell_tiles
    max_x = min(reference["maxX"], min_x + cell_tiles - 1)
    max_y = min(reference["maxY"], min_y + cell_tiles - 1)
    padding = int(padding)
    result = {
        "minX": max(reference["minX"], min_x - padding),
        "minY": max(reference["minY"], min_y - padding),
        "maxX": min(reference["maxX"], max_x + padding),
        "maxY": min(reference["maxY"], max_y + padding),
    }
    return result


def center_for_cell(cell, height=0, bounds=None, cell_tiles=DEFAULT_GRID_CELL_TILES,
                    row_origin=DEFAULT_ROW_ORIGIN):
    cell_bounds = bounds_for_cell(cell, 0, bounds, cell_tiles, row_origin)
    return {
        "x": (cell_bounds["minX"] + cell_bounds["maxX"]) // 2,
        "y": (cell_bounds["minY"] + cell_bounds["maxY"]) // 2,
        "height": int(height),
    }


def cells_for_bounds(bounds, reference_bounds=None, cell_tiles=DEFAULT_GRID_CELL_TILES,
                     row_origin=DEFAULT_ROW_ORIGIN):
    bounds = normalize_bounds(bounds)
    reference = normalize_bounds(reference_bounds)
    cell_tiles = int(cell_tiles)
    col_start = int(math.floor((bounds["minX"] - reference["minX"]) / float(cell_tiles)))
    col_end = int(math.floor((bounds["maxX"] - reference["minX"]) / float(cell_tiles)))
    row_start = int(math.floor((bounds["minY"] - reference["minY"]) / float(cell_tiles)))
    row_end = int(math.floor((bounds["maxY"] - reference["minY"]) / float(cell_tiles)))
    dimensions = grid_dimensions(reference, cell_tiles)
    col_start = max(0, min(dimensions["columns"] - 1, col_start))
    col_end = max(0, min(dimensions["columns"] - 1, col_end))
    row_start = max(0, min(dimensions["rows"] - 1, row_start))
    row_end = max(0, min(dimensions["rows"] - 1, row_end))
    cells = []
    for row in range(row_start, row_end + 1):
        for col in range(col_start, col_end + 1):
            cells.append("{}{}".format(column_label(col), row_label(row, reference, cell_tiles, row_origin)))
    return {
        "referenceGrid": True,
        "referenceGridOrigin": "level0",
        "referenceGridRowOrigin": row_origin,
        "referenceGridDatumBounds": reference,
        "referenceGridCellTiles": cell_tiles,
        "referenceGridColumns": max(0, col_end - col_start + 1),
        "referenceGridRows": max(0, row_end - row_start + 1),
        "referenceGridColumnStart": col_start,
        "referenceGridColumnEnd": col_end,
        "referenceGridColumnStartLabel": column_label(col_start),
        "referenceGridColumnEndLabel": column_label(col_end),
        "referenceGridRowStart": row_start,
        "referenceGridRowEnd": row_end,
        "referenceGridRowStartLabel": row_label(row_start, reference, cell_tiles, row_origin),
        "referenceGridRowEndLabel": row_label(row_end, reference, cell_tiles, row_origin),
        "referenceGridCells": cells,
    }


def parse_tile_arg(value):
    parts = [part.strip() for part in str(value).split(",")]
    if len(parts) not in (2, 3):
        raise argparse.ArgumentTypeError("tile must be x,y or x,y,h")
    try:
        x = int(parts[0])
        y = int(parts[1])
        h = int(parts[2]) if len(parts) == 3 else 0
    except ValueError:
        raise argparse.ArgumentTypeError("tile must contain integers")
    return {"x": x, "y": y, "height": h}


def parse_bounds_arg(value):
    parts = [part.strip() for part in str(value).split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bounds must be minX,minY,maxX,maxY")
    try:
        return normalize_bounds({
            "minX": int(parts[0]),
            "minY": int(parts[1]),
            "maxX": int(parts[2]),
            "maxY": int(parts[3]),
        })
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def print_json(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description="Inspect the level-0 cache-map reference grid.")
    parser.add_argument("--cell-tiles", type=positive_int, default=DEFAULT_GRID_CELL_TILES)
    parser.add_argument("--row-origin", choices=("south", "north"), default=DEFAULT_ROW_ORIGIN)
    subparsers = parser.add_subparsers(dest="command", required=True)

    locate = subparsers.add_parser("locate", help="Return the grid cell for a world tile.")
    locate.add_argument("--tile", required=True, type=parse_tile_arg, help="Tile as x,y,h.")

    bounds = subparsers.add_parser("bounds", help="Return tile bounds and center for a grid cell.")
    bounds.add_argument("--cell", required=True, help="Cell such as AU21.")
    bounds.add_argument("--padding-tiles", type=nonnegative_int, default=0)

    range_parser = subparsers.add_parser("range", help="Return visible grid cells for tile bounds.")
    range_parser.add_argument("--bounds", required=True, type=parse_bounds_arg,
                              help="Bounds as minX,minY,maxX,maxY.")

    args = parser.parse_args()
    if args.command == "locate":
        print_json(cell_for_tile(args.tile, cell_tiles=args.cell_tiles, row_origin=args.row_origin))
    elif args.command == "bounds":
        cell_bounds = bounds_for_cell(
            args.cell,
            padding=args.padding_tiles,
            cell_tiles=args.cell_tiles,
            row_origin=args.row_origin,
        )
        print_json({
            "cell": parse_cell(args.cell, cell_tiles=args.cell_tiles, row_origin=args.row_origin),
            "bounds": cell_bounds,
            "center": center_for_cell(args.cell, cell_tiles=args.cell_tiles, row_origin=args.row_origin),
            "paddingTiles": args.padding_tiles,
            "referenceBounds": LEVEL0_SURFACE_BOUNDS,
            "cellTiles": args.cell_tiles,
            "rowOrigin": args.row_origin,
        })
    elif args.command == "range":
        print_json(cells_for_bounds(args.bounds, cell_tiles=args.cell_tiles, row_origin=args.row_origin))


if __name__ == "__main__":
    main()
