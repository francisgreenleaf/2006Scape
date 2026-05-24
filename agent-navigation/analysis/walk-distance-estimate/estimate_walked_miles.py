#!/usr/bin/env python3
"""Estimate MrFlame's walked distance from recorded movement telemetry."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


METERS_PER_MILE = 1609.344
NORMAL_TICK_TILE_LIMIT = 2


@dataclass
class Segment:
    source: str
    path: str
    line: int
    timestamp_ms: int | None
    meters: int
    sampled: bool


@dataclass
class SourceSummary:
    source: str
    files: set[str] = field(default_factory=set)
    records: int = 0
    movement_segments: int = 0
    meters: int = 0
    skipped_teleport_or_region: int = 0
    skipped_missing_tiles: int = 0
    skipped_plane_change: int = 0
    skipped_large_jump: int = 0
    first_timestamp_ms: int | None = None
    last_timestamp_ms: int | None = None

    def note_timestamp(self, timestamp_ms: int | None) -> None:
        if timestamp_ms is None:
            return
        if self.first_timestamp_ms is None or timestamp_ms < self.first_timestamp_ms:
            self.first_timestamp_ms = timestamp_ms
        if self.last_timestamp_ms is None or timestamp_ms > self.last_timestamp_ms:
            self.last_timestamp_ms = timestamp_ms


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def default_inputs(repo_root: Path) -> list[Path]:
    paths: list[Path] = []
    patterns = [
        repo_root / "2006Scape Server" / "data" / "logs" / "player-movement-traces",
        repo_root / "2006Scape Server" / "data" / "logs" / "agent-movement-traces",
    ]
    for directory in patterns:
        if directory.exists():
            paths.extend(sorted(directory.glob("**/*.jsonl")))

    legacy_trace = repo_root / "agent-navigation" / "data" / "movement_traces.jsonl"
    if legacy_trace.exists():
        paths.append(legacy_trace)
    return paths


def source_for(path: Path) -> str:
    parts = set(path.parts)
    if "player-movement-traces" in parts:
        return "server_passive"
    if "agent-movement-traces" in parts:
        return "agent_batch"
    if path.name == "movement_traces.jsonl":
        return "legacy_route_recorder"
    return "unknown"


def timestamp_ms(record: dict[str, Any]) -> int | None:
    value = record.get("timestampMs")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    timestamp = record.get("timestamp")
    if not isinstance(timestamp, str):
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def tile(record: dict[str, Any], key: str) -> tuple[int, int, int] | None:
    value = record.get(key)
    if not isinstance(value, dict):
        return None
    try:
        return int(value["x"]), int(value["y"]), int(value.get("height", 0))
    except (KeyError, TypeError, ValueError):
        return None


def grid_steps(previous: tuple[int, int, int], current: tuple[int, int, int]) -> int | None:
    px, py, ph = previous
    cx, cy, ch = current
    if ph != ch:
        return None
    return max(abs(cx - px), abs(cy - py))


def iter_records(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                yield line_number, record


def collect(paths: list[Path]) -> tuple[dict[str, SourceSummary], list[Segment]]:
    summaries: dict[str, SourceSummary] = {}
    segments: list[Segment] = []

    for path in paths:
        source = source_for(path)
        summary = summaries.setdefault(source, SourceSummary(source=source))
        summary.files.add(str(path))

        for line_number, record in iter_records(path):
            summary.records += 1
            ts_ms = timestamp_ms(record)
            summary.note_timestamp(ts_ms)

            if not record.get("moved"):
                continue
            if record.get("teleported") or record.get("mapRegionChanged"):
                summary.skipped_teleport_or_region += 1
                continue

            previous_tile = tile(record, "previousTile")
            current_tile = tile(record, "tile")
            if previous_tile is None or current_tile is None:
                summary.skipped_missing_tiles += 1
                continue

            steps = grid_steps(previous_tile, current_tile)
            if steps is None:
                summary.skipped_plane_change += 1
                continue
            if steps == 0:
                continue

            sampled = source == "legacy_route_recorder"
            if not sampled and steps > NORMAL_TICK_TILE_LIMIT:
                summary.skipped_large_jump += 1
                continue

            summary.movement_segments += 1
            summary.meters += steps
            segments.append(
                Segment(
                    source=source,
                    path=str(path),
                    line=line_number,
                    timestamp_ms=ts_ms,
                    meters=steps,
                    sampled=sampled,
                )
            )

    return summaries, segments


def fmt_miles(meters: int) -> str:
    return f"{meters / METERS_PER_MILE:.3f}"


def fmt_timestamp(timestamp_ms: int | None) -> str:
    if timestamp_ms is None:
        return "-"
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def combine_estimate(segments: list[Segment]) -> dict[str, Any]:
    passive = [segment for segment in segments if segment.source == "server_passive"]
    first_passive_ts = min((segment.timestamp_ms for segment in passive if segment.timestamp_ms is not None), default=None)

    agent_pre_passive = [
        segment
        for segment in segments
        if segment.source == "agent_batch"
        and segment.timestamp_ms is not None
        and (first_passive_ts is None or segment.timestamp_ms < first_passive_ts)
    ]

    detailed = passive + agent_pre_passive
    first_detailed_ts = min((segment.timestamp_ms for segment in detailed if segment.timestamp_ms is not None), default=None)

    legacy_pre_detailed = [
        segment
        for segment in segments
        if segment.source == "legacy_route_recorder"
        and segment.timestamp_ms is not None
        and (first_detailed_ts is None or segment.timestamp_ms < first_detailed_ts)
    ]

    detailed_meters = sum(segment.meters for segment in detailed)
    sampled_meters = sum(segment.meters for segment in legacy_pre_detailed)
    total_meters = detailed_meters + sampled_meters

    return {
        "detailed_meters": detailed_meters,
        "sampled_lower_bound_meters": sampled_meters,
        "total_meters": total_meters,
        "total_miles": total_meters / METERS_PER_MILE,
        "first_passive_timestamp": fmt_timestamp(first_passive_ts),
        "first_detailed_timestamp": fmt_timestamp(first_detailed_ts),
        "components": {
            "server_passive_segments": len(passive),
            "agent_batch_pre_passive_segments": len(agent_pre_passive),
            "legacy_pre_detailed_segments": len(legacy_pre_detailed),
        },
    }


def as_report(summaries: dict[str, SourceSummary], combined: dict[str, Any]) -> dict[str, Any]:
    return {
        "assumption": "One walked tile-step is counted as one meter; diagonal tile-steps count as one tile-step.",
        "method": (
            "Use Chebyshev grid distance max(abs(dx), abs(dy)) between previousTile and tile, "
            "skip teleports/map-region jumps/plane changes, and use server passive traces plus "
            "pre-passive agent batch traces to avoid double counting overlap."
        ),
        "combined": combined,
        "sources": [
            {
                "source": summary.source,
                "files": len(summary.files),
                "records": summary.records,
                "movement_segments": summary.movement_segments,
                "meters": summary.meters,
                "miles": summary.meters / METERS_PER_MILE,
                "first_timestamp": fmt_timestamp(summary.first_timestamp_ms),
                "last_timestamp": fmt_timestamp(summary.last_timestamp_ms),
                "skipped_teleport_or_region": summary.skipped_teleport_or_region,
                "skipped_missing_tiles": summary.skipped_missing_tiles,
                "skipped_plane_change": summary.skipped_plane_change,
                "skipped_large_jump": summary.skipped_large_jump,
            }
            for summary in sorted(summaries.values(), key=lambda item: item.source)
        ],
    }


def print_report(report: dict[str, Any]) -> None:
    combined = report["combined"]
    print("Walk distance estimate for MrFlame")
    print("Assumption: 1 tile-step = 1 meter; diagonal steps count as one tile-step.")
    print()
    print("Combined estimate avoiding known overlap:")
    print(f"  Detailed tick traces: {combined['detailed_meters']:,} m / {fmt_miles(combined['detailed_meters'])} mi")
    print(
        "  Legacy sampled add-on: "
        f"{combined['sampled_lower_bound_meters']:,} m / {fmt_miles(combined['sampled_lower_bound_meters'])} mi"
    )
    print(f"  Total estimate:       {combined['total_meters']:,} m / {combined['total_miles']:.3f} mi")
    print()
    print("Source totals before overlap filtering:")
    print("  source                  files  records  move_segments  meters   miles   time range")
    for source in report["sources"]:
        time_range = f"{source['first_timestamp']} -> {source['last_timestamp']}"
        print(
            f"  {source['source']:<22}"
            f"{source['files']:>5}"
            f"{source['records']:>9}"
            f"{source['movement_segments']:>15}"
            f"{source['meters']:>9,}"
            f"{source['miles']:>8.3f}   "
            f"{time_range}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--write-json", type=Path, help="Optional path to write the structured report.")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    summaries, segments = collect(default_inputs(repo_root))
    report = as_report(summaries, combine_estimate(segments))
    print_report(report)

    if args.write_json:
        args.write_json.parent.mkdir(parents=True, exist_ok=True)
        with args.write_json.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
