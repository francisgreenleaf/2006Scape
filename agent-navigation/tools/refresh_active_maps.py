#!/usr/bin/env python3
"""Continuously refresh the active canonical map exports.

The full cache-world map is static, so this watcher only refreshes it when it
is missing or explicitly requested. Active movement/route maps run in their own
workers by default so slow topology renders do not block quick route-map updates.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
TOOLS = ROOT / "tools"
TOPOLOGY = ROOT / "topology"
LOCAL = ROOT / ".local" / "map-refresh"
DEFAULT_STATUS = LOCAL / "status.json"
DEFAULT_TMP = LOCAL / "tmp"
DEFAULT_RENDER_CACHE = ROOT / ".local" / "topology-render-cache"


@dataclass(frozen=True)
class MapJob:
    job_id: str
    label: str
    output: Path
    summary: Path | None
    command_name: str
    args: tuple[str, ...]
    render_cache_namespace: str | None = None


WORLD_MAP = MapJob(
    job_id="cache-world-map",
    label="Cache World Map",
    output=TOPOLOGY / "cache-world-map.png",
    summary=TOPOLOGY / "cache-world-map.json",
    command_name="cache_world_map.py",
    args=("--output", "{output}", "--summary", "{summary}"),
)

ACTIVE_JOBS = (
    MapJob(
        job_id="surface-routes",
        label="Surface Routes",
        output=TOPOLOGY / "surface-routes.png",
        summary=None,
        command_name="render_navigation_png.py",
        args=("--region", "all", "--output", "{output}"),
    ),
    MapJob(
        job_id="mr-flame",
        label="Mr. Flame",
        output=TOPOLOGY / "movement-topology-v4.png",
        summary=TOPOLOGY / "movement-topology-v4.json",
        command_name="render_movement_topology_v4.py",
        args=("--output", "{output}", "--summary", "{summary}", "--coverage-cache-dir", "{render_cache_dir}"),
        render_cache_namespace="mr-flame",
    ),
    MapJob(
        job_id="heat-map",
        label="Heat Map",
        output=TOPOLOGY / "movement-topology-v5-heatmap.png",
        summary=TOPOLOGY / "movement-topology-v5-heatmap.json",
        command_name="render_movement_topology_v5.py",
        args=("--output", "{output}", "--summary", "{summary}", "--coverage-cache-dir", "{render_cache_dir}"),
        render_cache_namespace="heat-map",
    ),
    MapJob(
        job_id="mr-flame-fog",
        label="Mr. Flame Fog",
        output=TOPOLOGY / "movement-topology-v6.png",
        summary=TOPOLOGY / "movement-topology-v6.json",
        command_name="render_movement_topology_v6.py",
        args=("--output", "{output}", "--summary", "{summary}", "--coverage-cache-dir", "{render_cache_dir}"),
        render_cache_namespace="mr-flame-fog",
    ),
)

ALL_ACTIVE_BY_ID = {job.job_id: job for job in ACTIVE_JOBS}

status_lock = threading.Lock()
process_lock = threading.Lock()
status_doc: dict = {}
active_processes: dict[str, subprocess.Popen] = {}
stop_event = threading.Event()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    print(f"[{utc_now()}] {message}", flush=True)


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("value must be a number")
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def nonnegative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("value must be a number")
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be nonnegative")
    return parsed


def safe_profile(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum() or ch in ("-", "_"))


def build_command(job: MapJob, output: Path, summary: Path | None, args) -> list[str]:
    render_cache_dir = args.render_cache_dir
    if job.render_cache_namespace:
        namespace = job.render_cache_namespace
        if args.trace_profile:
            namespace = namespace + "-" + safe_profile(args.trace_profile)
        render_cache_dir = render_cache_dir / namespace
    values = {
        "output": str(output),
        "summary": str(summary) if summary is not None else "",
        "render_cache_dir": str(render_cache_dir),
    }
    command = [sys.executable, str(TOOLS / job.command_name)]
    command.extend(arg.format(**values) for arg in job.args)
    if job.command_name.startswith("render_movement_topology_") and args.trace_profile:
        command.extend(["--trace-profile", args.trace_profile])
    if job.command_name.startswith("render_movement_topology_") and args.include_unscoped_traces:
        command.append("--include-unscoped-traces")
    return command


def temp_paths(job: MapJob, tmp_dir: Path) -> tuple[Path, Path | None]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base = tmp_dir / f"{job.job_id}-{stamp}-{os.getpid()}"
    output = base.with_suffix(job.output.suffix)
    summary = base.with_suffix(".json") if job.summary is not None else None
    return output, summary


def write_status(status_file: Path) -> None:
    status_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = status_file.with_suffix(status_file.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(status_doc, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, status_file)


def update_status(status_file: Path, job: MapJob, **fields) -> None:
    with status_lock:
        if not status_doc:
            status_doc.update({
                "schemaVersion": 1,
                "startedAt": utc_now(),
                "repo": str(REPO_ROOT),
                "jobs": {},
            })
        status_doc["updatedAt"] = utc_now()
        status_doc.setdefault("jobs", {}).setdefault(job.job_id, {
            "label": job.label,
            "output": str(job.output),
            "summary": str(job.summary) if job.summary is not None else None,
        }).update(fields)
        write_status(status_file)


def json_tail(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def normalize_summary(summary_path: Path, canonical_output: Path, canonical_summary: Path) -> dict:
    with summary_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    canonical_output_text = str(canonical_output.resolve())
    canonical_summary_text = str(canonical_summary.resolve())
    if "output" in data:
        data["output"] = canonical_output_text
    if "png" in data:
        data["png"] = canonical_output_text
    if "summary" in data:
        data["summary"] = canonical_summary_text
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return data


def summarize_metadata(metadata: dict) -> str:
    parts = []
    for key in ("records", "nodes", "edges", "deaths"):
        if key in metadata:
            parts.append(f"{key}={metadata[key]}")
    cache = metadata.get("cache") or {}
    if cache:
        cache_bits = []
        for key in ("topologyCache", "baseLayerCache", "poiCache"):
            if key in cache:
                cache_bits.append(f"{key}={cache[key]}")
        if cache_bits:
            parts.append("cache(" + ", ".join(cache_bits) + ")")
    if metadata.get("coverageFogCache"):
        parts.append(
            "fog={cache} cached={cached} rendered={rendered}".format(
                cache=metadata.get("coverageFogCache"),
                cached=metadata.get("coverageFogCachedNodes"),
                rendered=metadata.get("coverageFogRenderedNodes"),
            )
        )
    if metadata.get("coverageHeatmap"):
        parts.append(f"heatRadius={metadata.get('coverageHeatRadiusTiles')}")
    return " ".join(parts)


def run_job(job: MapJob, args, reason: str = "scheduled") -> bool:
    output_tmp, summary_tmp = temp_paths(job, args.tmp_dir)
    output_tmp.parent.mkdir(parents=True, exist_ok=True)
    job.output.parent.mkdir(parents=True, exist_ok=True)
    command = build_command(job, output_tmp, summary_tmp, args)

    if args.dry_run:
        log(f"dry-run {job.label}: {' '.join(command)}")
        return True

    started_at = utc_now()
    update_status(args.status_file, job, state="running", reason=reason, lastStartedAt=started_at)
    log(f"start {job.label}: {reason} -> {job.output}")
    start = time.monotonic()
    env = os.environ.copy()
    if args.profile:
        env["RS_PROFILE"] = args.profile
    if args.trace_profile:
        env["RS_TRACE_PROFILE"] = args.trace_profile
    proc = subprocess.Popen(
        command,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    with process_lock:
        active_processes[job.job_id] = proc
    try:
        try:
            stdout, stderr = proc.communicate(timeout=args.render_timeout_seconds or None)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            stderr = (stderr or "") + f"\nrender timed out after {args.render_timeout_seconds}s"
    finally:
        with process_lock:
            active_processes.pop(job.job_id, None)

    duration = time.monotonic() - start
    if proc.returncode != 0:
        detail = (stderr or stdout or "").strip()[-1200:]
        log(f"fail {job.label}: code={proc.returncode} duration={duration:.1f}s {detail}")
        update_status(
            args.status_file,
            job,
            state="failed",
            lastFinishedAt=utc_now(),
            lastDurationSeconds=round(duration, 3),
            lastReturnCode=proc.returncode,
            lastError=detail,
        )
        cleanup_temp(output_tmp, summary_tmp)
        return False

    metadata = {}
    if summary_tmp is not None and job.summary is not None:
        metadata = normalize_summary(summary_tmp, job.output, job.summary)
        os.replace(output_tmp, job.output)
        os.replace(summary_tmp, job.summary)
    else:
        os.replace(output_tmp, job.output)
        metadata = json_tail(stdout)

    detail = summarize_metadata(metadata)
    suffix = f" {detail}" if detail else ""
    log(f"done {job.label}: {duration:.1f}s -> {job.output}{suffix}")
    update_status(
        args.status_file,
        job,
        state="idle",
        lastFinishedAt=utc_now(),
        lastDurationSeconds=round(duration, 3),
        lastReturnCode=proc.returncode,
        lastOutput=str(job.output),
        lastSummary=str(job.summary) if job.summary is not None else None,
        lastMetadata=compact_metadata(metadata),
        lastError=None,
    )
    return True


def compact_metadata(metadata: dict) -> dict:
    keep = [
        "success",
        "mapVersion",
        "records",
        "nodes",
        "edges",
        "deaths",
        "pixelWidth",
        "pixelHeight",
        "coverageHeatmap",
        "coverageHeatRadiusTiles",
        "coverageFogCache",
        "coverageFogCachedNodes",
        "coverageFogRenderedNodes",
        "coverageFogRadiusTiles",
        "cache",
        "regions",
        "tiles",
        "objects",
    ]
    return {key: metadata.get(key) for key in keep if key in metadata}


def cleanup_temp(output: Path, summary: Path | None) -> None:
    for path in (output, summary):
        if path is not None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def worker(job: MapJob, args, initial_delay: float) -> None:
    if initial_delay > 0 and not args.once:
        log(f"wait {job.label}: initial stagger {initial_delay:.1f}s")
        if stop_event.wait(initial_delay):
            return
    while not stop_event.is_set():
        start = time.monotonic()
        run_job(job, args)
        if args.once or stop_event.is_set():
            return
        elapsed = time.monotonic() - start
        wait_seconds = max(0.0, args.interval_seconds - elapsed)
        log(f"next {job.label}: {wait_seconds:.1f}s")
        stop_event.wait(wait_seconds)


def run_serial(jobs: list[MapJob], args) -> None:
    while not stop_event.is_set():
        start = time.monotonic()
        for job in jobs:
            if stop_event.is_set():
                break
            run_job(job, args)
        if args.once or stop_event.is_set():
            return
        elapsed = time.monotonic() - start
        wait_seconds = max(0.0, args.interval_seconds - elapsed)
        log(f"next serial cycle: {wait_seconds:.1f}s")
        stop_event.wait(wait_seconds)


def ensure_world_map(args) -> None:
    missing = not WORLD_MAP.output.exists() or (WORLD_MAP.summary is not None and not WORLD_MAP.summary.exists())
    if args.no_world_map_check:
        return
    if args.refresh_world_map or missing:
        reason = "forced refresh" if args.refresh_world_map else "missing canonical export"
        run_job(WORLD_MAP, args, reason=reason)
    else:
        log(f"skip {WORLD_MAP.label}: existing cached export is present")


def handle_signal(signum, _frame) -> None:
    log(f"received signal {signum}; stopping after active renders terminate")
    stop_event.set()
    with process_lock:
        processes = list(active_processes.items())
    for job_id, proc in processes:
        if proc.poll() is None:
            log(f"terminate active render: {job_id}")
            proc.terminate()


def parse_args():
    parser = argparse.ArgumentParser(description="Continuously refresh active 2006Scape map exports.")
    parser.add_argument("--profile", default=os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or "",
                        help="Profile label to pass through to child renderers.")
    parser.add_argument("--trace-profile",
                        default=os.environ.get("RS_TRACE_PROFILE") or os.environ.get("RS_PROFILE") or os.environ.get("RSBRIDGE_PROFILE") or "",
                        help="Only render movement traces for this profile.")
    parser.add_argument("--include-unscoped-traces", action="store_true",
                        help="When filtering by profile, also include legacy traces with no player name.")
    parser.add_argument("--interval-seconds", type=positive_float, default=30.0,
                        help="Target cadence per map. If a render exceeds this, its next pass starts immediately.")
    parser.add_argument("--stagger-seconds", type=nonnegative_float, default=8.0,
                        help="Initial delay between parallel workers.")
    parser.add_argument("--only", action="append", choices=sorted(ALL_ACTIVE_BY_ID),
                        help="Refresh only this active map id. May be repeated.")
    parser.add_argument("--serial", action="store_true",
                        help="Run selected maps one after another instead of one worker per map.")
    parser.add_argument("--once", action="store_true",
                        help="Run selected maps once and exit.")
    parser.add_argument("--refresh-world-map", action="store_true",
                        help="Render cache-world-map once before active refreshes.")
    parser.add_argument("--no-world-map-check", action="store_true",
                        help="Do not render cache-world-map even if the canonical export is missing.")
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS,
                        help="Ignored JSON status file for background monitoring.")
    parser.add_argument("--tmp-dir", type=Path, default=DEFAULT_TMP,
                        help="Ignored temp directory used for atomic output replacement.")
    parser.add_argument("--render-cache-dir", type=Path, default=DEFAULT_RENDER_CACHE,
                        help="Ignored persistent cache root. Topology workers use per-map subdirectories here.")
    parser.add_argument("--render-timeout-seconds", type=nonnegative_float, default=0.0,
                        help="Kill an individual render after this many seconds. 0 disables timeout.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print commands without rendering.")
    parser.add_argument("--list-maps", action="store_true",
                        help="Print active map ids and exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.profile and not args.trace_profile:
        args.trace_profile = args.profile
    if args.list_maps:
        for job in ACTIVE_JOBS:
            print(f"{job.job_id}\t{job.label}\t{job.output}")
        return 0

    args.status_file = args.status_file.resolve()
    args.tmp_dir = args.tmp_dir.resolve()
    args.render_cache_dir = args.render_cache_dir.resolve()
    selected = [ALL_ACTIVE_BY_ID[job_id] for job_id in args.only] if args.only else list(ACTIVE_JOBS)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    log(
        "refresh active maps: interval={:.1f}s mode={} jobs={}".format(
            args.interval_seconds,
            "serial" if args.serial else "parallel",
            ",".join(job.job_id for job in selected),
        )
    )
    ensure_world_map(args)

    if args.serial:
        run_serial(selected, args)
    else:
        threads = []
        for index, job in enumerate(selected):
            initial_delay = 0.0 if args.once else args.stagger_seconds * index
            thread = threading.Thread(target=worker, args=(job, args, initial_delay), name=job.job_id)
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()

    log("map refresh stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
