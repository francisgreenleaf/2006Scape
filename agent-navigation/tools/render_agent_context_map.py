#!/usr/bin/env python3
"""Fast agent-facing context map wrapper.

This is the map command agents should use during live routing. It keeps output
bounded, current, and cheap enough for tactical route debugging.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import map_grid
import render_context_map
from usage_log import log_usage


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_MAP_ARCHIVE = ROOT / ".local" / "context-maps"


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


def requested_paths(args):
    if args.output and args.summary:
        return args.output, args.summary
    if args.output:
        return args.output, str(Path(args.output).with_suffix(".json"))
    if args.summary:
        return str(Path(args.summary).with_suffix(".png")), args.summary
    return None, None


def main():
    log_usage("render_agent_context_map", surface="full", argv=sys.argv[1:])
    parser = argparse.ArgumentParser(description="Render the fast bounded map agents should use while routing.")
    parser.add_argument("--center", default="latest", help="latest/current, x,y,h, or place id/name.")
    parser.add_argument("--grid-cell",
                        help="Level-0 map grid cell such as AU21. Renders that cell instead of --center.")
    parser.add_argument("--grid-padding-tiles", type=nonnegative_int, default=4,
                        help="Extra tiles around --grid-cell bounds.")
    parser.add_argument("--segment-from")
    parser.add_argument("--segment-to")
    parser.add_argument("--radius-tiles", type=positive_int, default=64)
    parser.add_argument("--padding-tiles", type=positive_int, default=32)
    parser.add_argument("--max-span-tiles", type=positive_int, default=224)
    parser.add_argument("--context-place-radius", type=nonnegative_int, default=0,
                        help="For segment maps, include nearby tactical context such as docks, ports, banks, and shops.")
    parser.add_argument("--max-context-anchors", type=nonnegative_int, default=12)
    parser.add_argument("--pixels-per-tile", type=positive_int, default=4)
    parser.add_argument("--recent-seconds", type=nonnegative_int, default=90)
    parser.add_argument("--max-trace-records", type=nonnegative_int, default=50000)
    parser.add_argument("--player", default=os.environ.get("RS_TRACE_PROFILE") or os.environ.get("RS_PROFILE") or "mrflame")
    parser.add_argument("--trace-file", action="append")
    parser.add_argument("--output")
    parser.add_argument("--summary")
    parser.add_argument("--artifact-dir", default=str(CONTEXT_MAP_ARCHIVE),
                        help="Default archive root for unique context-map artifacts.")
    parser.add_argument("--no-current-marker", action="store_true")
    parser.add_argument("--no-mapfunction-icons", action="store_true",
                        help="Hide cache-backed minimap mapfunction icons.")
    parser.add_argument("--mapfunction-labels", action="store_true",
                        help="Also draw object labels for every mapfunction icon.")
    parser.add_argument("--no-place-markers", action="store_true")
    parser.add_argument("--no-place-labels", action="store_true")
    parser.add_argument("--max-place-markers", type=positive_int, default=60)
    parser.add_argument("--no-reference-grid", action="store_true",
                        help="Hide the level-0 reference grid overlay.")
    args = parser.parse_args()

    if bool(args.segment_from) != bool(args.segment_to):
        raise SystemExit("--segment-from and --segment-to must be used together")
    if args.grid_cell and (args.segment_from or args.segment_to):
        raise SystemExit("--grid-cell cannot be combined with --segment-from/--segment-to")

    output, summary = requested_paths(args)
    render_args = SimpleNamespace(
        center=args.center,
        bounds=None,
        grid_cell=args.grid_cell,
        grid_padding_tiles=args.grid_padding_tiles,
        radius_tiles=args.radius_tiles,
        padding_tiles=args.padding_tiles,
        max_span_tiles=args.max_span_tiles,
        context_place_radius=args.context_place_radius,
        max_context_anchors=args.max_context_anchors,
        plane=0,
        pixels_per_tile=args.pixels_per_tile,
        recent_seconds=args.recent_seconds,
        segment_from=args.segment_from,
        segment_to=args.segment_to,
        fit_segment=True,
        player=args.player,
        trace_file=args.trace_file,
        max_trace_records=args.max_trace_records,
        current_marker=not args.no_current_marker,
        mapfunction_icons=not args.no_mapfunction_icons,
        mapfunction_labels=args.mapfunction_labels,
        place_markers=not args.no_place_markers,
        place_labels=not args.no_place_labels,
        max_place_markers=args.max_place_markers,
        grid_interval=0,
        reference_grid=not args.no_reference_grid,
        reference_grid_cell_tiles=map_grid.DEFAULT_GRID_CELL_TILES,
        reference_grid_row_origin=map_grid.DEFAULT_ROW_ORIGIN,
        reference_grid_alpha=0.30,
        reference_grid_major_alpha=0.48,
        reference_grid_major_every=4,
        reference_grid_cell_labels="all",
        reference_grid_label_scale=2,
        output=output,
        summary=summary,
        artifact_dir=args.artifact_dir,
    )
    result = render_context_map.render(render_args)
    compact = {
        "success": result["success"],
        "output": result["output"],
        "summary": result["summary"],
        "artifact": result.get("artifact"),
        "bounds": result["bounds"],
        "center": result["center"],
        "spanTiles": result["spanTiles"],
        "recentEdgesDrawn": result["recentEdgesDrawn"],
        "segmentEdgesDrawn": result["segmentEdgesDrawn"],
        "mapFunctionMarkerCount": result["mapFunctionMarkerCount"],
        "mapFunctionIconsDrawn": result["mapFunctionIconsDrawn"],
        "placeLabelsDrawn": result["placeLabelsDrawn"],
        "contextAnchors": result.get("contextAnchors", []),
        "totalTraceRecords": result["totalTraceRecords"],
        "traceRecordsConsidered": result["traceRecordsConsidered"],
        "maxTraceRecords": result["maxTraceRecords"],
        "currentGridCell": result.get("currentGridCell"),
        "centerGridCell": result.get("centerGridCell"),
        "referenceGrid": result.get("referenceGrid"),
        "referenceGridCellTiles": result.get("referenceGridCellTiles"),
        "referenceGridCells": result.get("referenceGridCells", []),
        "referenceGridColumnStartLabel": result.get("referenceGridColumnStartLabel"),
        "referenceGridColumnEndLabel": result.get("referenceGridColumnEndLabel"),
        "referenceGridRowStartLabel": result.get("referenceGridRowStartLabel"),
        "referenceGridRowEndLabel": result.get("referenceGridRowEndLabel"),
    }
    print(json.dumps(compact, sort_keys=True))


if __name__ == "__main__":
    main()
