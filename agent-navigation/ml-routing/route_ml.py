#!/usr/bin/env python3
"""One-command entrypoint for the 2006Scape ML routing pipeline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from ml_routing.benchmark import run_benchmark
from ml_routing.comparison_maps import run_comparison_maps
from ml_routing.dataset import export_dataset
from ml_routing.feedback import record_outcome
from ml_routing.model import train_model
from ml_routing.planner import DEFAULT_ROUTE_EVIDENCE_JSONL, rank_routes
from usage_log import log_usage


DEFAULT_ROUTE_DEFINITION_DIR = "agent-navigation/.local/ml-route-definitions"


def safe_route_filename(route_id: str) -> str:
    safe = []
    for char in str(route_id or "route").lower():
        if char.isalnum() or char in ("-", "_"):
            safe.append(char)
        else:
            safe.append("-")
    text = "".join(safe).strip("-")
    while "--" in text:
        text = text.replace("--", "-")
    return (text or "route")[:180] + ".json"


def persist_route_definition(args: argparse.Namespace, definition: dict | None) -> dict | None:
    if not isinstance(definition, dict) or not definition.get("actionable"):
        return definition
    if not definition.get("routeSteps"):
        return definition
    output_dir = Path(getattr(args, "route_definition_dir", "") or DEFAULT_ROUTE_DEFINITION_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / safe_route_filename(definition.get("routeId"))
    execution = definition.setdefault("execution", {})
    command = list(execution.get("command") or [])
    path_text = str(output_path)
    if "--route-definition" in command:
        index = command.index("--route-definition")
        if index + 1 < len(command):
            command[index + 1] = path_text
        else:
            command.append(path_text)
    else:
        command.extend(["--route-definition", path_text])
    execution["command"] = command
    execution["routeDefinitionPath"] = path_text
    output_path.write_text(json.dumps(definition, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return definition


def persist_recommended_definition(args: argparse.Namespace, result: dict) -> dict | None:
    recommended = result.get("recommended") if isinstance(result, dict) else None
    if not isinstance(recommended, dict):
        return None
    definition = persist_route_definition(args, recommended.get("routeDefinition"))
    if definition is not None:
        recommended["routeDefinition"] = definition
        command = (definition.get("execution") or {}).get("command")
        if command:
            recommended["routeExecutionCommand"] = command
            recommended["routeRunnerCommand"] = command
    return definition


def add_shared_route_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from", dest="from_tile", default="lumbridge_castle_courtyard",
                        help="Start tile x,y,h or place id/name.")
    parser.add_argument("--to", default="varrock_square", help="Target place id/name or x,y,h tile.")
    parser.add_argument("--combat-level", type=int, default=3)
    parser.add_argument("--food", type=int, default=0)
    parser.add_argument("--coins", type=int, default=0)
    parser.add_argument("--run-energy", type=int, default=0)
    parser.add_argument("--run-enabled", action="store_true")
    parser.add_argument("--allow-lethal", action="store_true")
    parser.add_argument("--allow-failed-candidate", action="store_true")
    parser.add_argument("--trace-file", action="append")
    parser.add_argument("--trace-profile", default="")
    parser.add_argument("--include-unscoped-traces", action="store_true")
    parser.add_argument("--graph-snap-distance", type=int, default=16)
    parser.add_argument("--hazard-buffer", type=int, default=10)
    parser.add_argument("--failure-buffer", type=int, default=8)
    parser.add_argument("--max-static-leg", type=int, default=32)
    parser.add_argument("--max-batch-distance", type=int, default=24)
    parser.add_argument("--compress-gap", type=int, default=18)
    parser.add_argument("--no-cache-collision", action="store_true",
                        help="Disable cache-derived clipped path expansion for diagnostics.")
    parser.add_argument("--collision-padding-tiles", type=int, default=64,
                        help="Extra cache tiles around a route when expanding macro edges.")
    parser.add_argument("--collision-max-expansions", type=int, default=250000,
                        help="A* node expansion cap per macro segment.")
    parser.add_argument("--waypoint-arrival-radius", type=int, default=1,
                        help="When an intermediate macro waypoint is clipped, allow stopping this close to it.")
    parser.add_argument("--no-shortcut-optimize", action="store_true",
                        help="Disable post-route cache-clipped shortcut pruning.")
    parser.add_argument("--shortcut-max-span", type=int, default=128,
                        help="Max adjacent-tile span considered for one shortcut pruning attempt.")
    parser.add_argument("--shortcut-min-savings", type=int, default=4,
                        help="Minimum tile savings required before replacing an evidenced subpath.")
    parser.add_argument("--shortcut-corridor-radius", type=int, default=18,
                        help="Keep shortcut candidates this close to the original evidenced corridor.")
    parser.add_argument("--route-step-gap", type=int, default=10,
                        help="Gap for compact routeSteps derived from the clipped path.")
    parser.add_argument("--no-cache-direct", action="store_true",
                        help="Disable cache-clipped direct-route candidates for diagnostics.")
    parser.add_argument("--direct-candidate-min-detour", type=float, default=1.22,
                        help="Try a cache-direct candidate when the learned route detour ratio reaches this value.")
    parser.add_argument("--direct-candidate-min-savings", type=int, default=24,
                        help="Minimum tile savings before a complete cache-direct candidate replaces a learned route.")
    parser.add_argument("--direct-hazard-buffer", type=int, default=10,
                        help="Extra hazard influence radius for cache-direct routing.")
    parser.add_argument("--direct-max-expansions", type=int, default=350000,
                        help="A* expansion cap for one cache-direct route.")
    parser.add_argument("--direct-combat-margin", type=int, default=5,
                        help="Treat hazards as runnable when combat is within this many levels and food/run are ready.")
    parser.add_argument("--runnable-hazard-cost-factor", type=float, default=0.15,
                        help="Hazard-cost multiplier when stats, food, and run energy make a hazard runnable.")
    parser.add_argument("--terminal-hazard-cost-factor", type=float, default=0.25,
                        help="Hazard-cost multiplier close to a target that intentionally sits inside a hazard influence zone.")
    parser.add_argument("--max-warnings", type=int, default=8)
    parser.add_argument("--max-suspects", type=int, default=5)
    parser.add_argument("--max-candidates", type=int, default=3)
    parser.add_argument("--output-candidates", type=int, default=0,
                        help="Include this many ranked alternatives in JSON output. Default keeps agent output compact.")
    parser.add_argument("--runner-max-batches", type=int, default=8)
    parser.add_argument("--route-evidence-jsonl", default=DEFAULT_ROUTE_EVIDENCE_JSONL,
                        help="Path the legacy compatibility executor should append per-batch route evidence to.")
    parser.add_argument("--no-route-evidence", action="store_true",
                        help="Do not add --evidence-jsonl to generated compatibility commands.")
    parser.add_argument("--route-definition-dir", default=DEFAULT_ROUTE_DEFINITION_DIR,
                        help="Directory for route definition artifacts used by generated execution commands.")
    parser.add_argument("--model", default="")
    parser.add_argument("--planner", choices=["fast", "full"], default="fast",
                        help="fast uses the trained ML graph; full wraps router.py/route_eval.py and is slower.")


def cmd_export(args: argparse.Namespace) -> int:
    summary = export_dataset(args)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    model = train_model(args)
    compact = {
        "modelId": model["modelId"],
        "trainedAt": model["trainedAt"],
        "datasetDir": model["datasetDir"],
        "records": model["training"]["records"],
        "workers": model["training"]["workers"],
        "global": model["global"],
    }
    print(json.dumps(compact, indent=2, sort_keys=True))
    return 0


def cmd_route(args: argparse.Namespace) -> int:
    result = rank_routes(args)
    persist_recommended_definition(args, result)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        rec = result.get("recommended", {})
        print("ml-route: {} -> {} status={} quality={} score={}".format(
            result["request"]["from"], result["request"]["to"],
            rec.get("status"), rec.get("quality"), rec.get("score")))
        print("next:", rec.get("next"))
        print("run:", " ".join(rec.get("routeExecutionCommand") or rec.get("routeRunnerCommand") or []))
    return 0 if result.get("recommended", {}).get("actionable") is True else 2


def cmd_define(args: argparse.Namespace) -> int:
    result = rank_routes(args)
    persist_recommended_definition(args, result)
    definition = result.get("recommended", {}).get("routeDefinition")
    if definition is None:
        definition = {
            "schemaVersion": 1,
            "api": "2006scape.route-definition",
            "actionable": False,
            "error": result.get("recommended", {}).get("error") or "no route definition",
            "route": result.get("recommended", {}),
        }
    print(json.dumps(definition, indent=2, sort_keys=True))
    return 0 if definition.get("actionable") is True else 2


def cmd_go(args: argparse.Namespace) -> int:
    result = rank_routes(args)
    definition = persist_recommended_definition(args, result)
    command = ((definition or {}).get("execution") or {}).get("command") or result.get("recommended", {}).get("routeRunnerCommand") or []
    if args.dry_run:
        print(json.dumps({
            "dryRun": True,
            "route": result,
            "command": command,
        }, indent=2, sort_keys=True))
        return 0 if result.get("recommended", {}).get("actionable") is True else 2
    if not command:
        print(json.dumps({"success": False, "error": "no route execution command", "route": result}, indent=2, sort_keys=True))
        return 2
    proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    payload = {
        "success": proc.returncode == 0,
        "returncode": proc.returncode,
        "route": result,
        "stdout": proc.stdout.strip()[-4000:],
        "stderr": proc.stderr.strip()[-4000:],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return proc.returncode


def cmd_benchmark(args: argparse.Namespace) -> int:
    report = run_benchmark(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("actionableCount", 0) == report["caseCount"] else 2


def cmd_compare_maps(args: argparse.Namespace) -> int:
    report = run_comparison_maps(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def cmd_loop(args: argparse.Namespace) -> int:
    completed = 0
    while args.once or args.iterations == 0 or completed < args.iterations:
        export_args = SimpleNamespace(**vars(args))
        dataset = export_dataset(export_args)
        train_args = SimpleNamespace(**vars(args))
        train_args.dataset_dir = dataset["outputDir"]
        model = train_model(train_args)
        benchmark_args = SimpleNamespace(**vars(args))
        benchmark_args.model = model["modelPath"]
        report = run_benchmark(benchmark_args)
        print(json.dumps({
            "iteration": completed + 1,
            "dataset": dataset["outputDir"],
            "modelId": model["modelId"],
            "benchmark": report["outputDir"],
            "okCount": report["okCount"],
            "caseCount": report["caseCount"],
        }, sort_keys=True))
        completed += 1
        if args.once:
            break
        time.sleep(max(1, args.interval_seconds))
    return 0


def cmd_record_outcome(args: argparse.Namespace) -> int:
    result = record_outcome(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="2006Scape ML routing pipeline.")
    sub = parser.add_subparsers(dest="command")

    export = sub.add_parser("export", help="Export training/evaluation datasets from existing route evidence.")
    export.add_argument("--profile", default="")
    export.add_argument("--run-id", default="")
    export.add_argument("--output-dir", default="")
    export.add_argument("--trace-file", action="append")
    export.add_argument("--include-unscoped-traces", action="store_true")
    export.add_argument("--include-agent-batch-traces", action="store_true")
    export.add_argument("--include-legacy-recorder-traces", action="store_true")
    export.add_argument("--no-local-evidence", action="store_true")
    export.set_defaults(func=cmd_export)

    train = sub.add_parser("train", help="Train the local empirical edge/risk model.")
    train.add_argument("--dataset-dir", default="")
    train.add_argument("--model-id", default="")
    train.add_argument("--output-dir", default="")
    train.add_argument("--workers", type=int, default=16)
    train.set_defaults(func=cmd_train)

    route = sub.add_parser("route", help="Rank route candidates for an agent routing request.")
    add_shared_route_args(route)
    route.add_argument("--json", action="store_true")
    route.set_defaults(func=cmd_route)

    define = sub.add_parser("define", help="Return only the stable agent-facing route definition JSON.")
    add_shared_route_args(define)
    define.set_defaults(func=cmd_define)

    go = sub.add_parser("go", help="Compatibility executor: rank a route and run the legacy route_runner command.")
    add_shared_route_args(go)
    go.add_argument("--dry-run", action="store_true",
                    help="Print the selected command without moving the live character.")
    go.set_defaults(func=cmd_go)

    bench = sub.add_parser("benchmark", help="Run offline route-ranking benchmarks.")
    add_shared_route_args(bench)
    bench.add_argument("--run-id", default="")
    bench.add_argument("--output-dir", default="")
    bench.add_argument("--limit", type=int, default=0)
    bench.set_defaults(func=cmd_benchmark)

    compare = sub.add_parser("compare-maps", help="Render fast ML route maps for benchmark routes.")
    add_shared_route_args(compare)
    compare.add_argument("--run-id", default="")
    compare.add_argument("--output-dir", default="")
    compare.add_argument("--limit", type=int, default=0)
    compare.add_argument("--case", action="append",
                         help="Benchmark case name, from place, or target place to render. Repeatable.")
    compare.add_argument("--include-old-planner", action="store_true",
                         help="Also run and draw the deprecated full planner in red for explicit regression comparisons.")
    compare.add_argument("--pixels-per-tile", type=int, default=4)
    compare.add_argument("--padding-tiles", type=int, default=12)
    compare.add_argument("--header-pixels", type=int, default=64)
    compare.add_argument("--no-mapfunction-icons", dest="mapfunction_icons", action="store_false", default=True,
                         help="Hide cache-backed minimap mapfunction icons on comparison maps.")
    compare.add_argument("--mapfunction-labels", action="store_true",
                         help="Label every mapfunction icon. Usually leave off and read labels from JSON.")
    compare.add_argument("--no-place-markers", dest="place_markers", action="store_false", default=True)
    compare.add_argument("--no-place-labels", dest="place_labels", action="store_false", default=True)
    compare.add_argument("--max-place-markers", type=int, default=80)
    compare.set_defaults(func=cmd_compare_maps)

    loop = sub.add_parser("loop", help="Asynchronous export/train/benchmark improvement loop.")
    add_shared_route_args(loop)
    loop.add_argument("--profile", default="")
    loop.add_argument("--run-id", default="")
    loop.add_argument("--output-dir", default="")
    loop.add_argument("--dataset-dir", default="")
    loop.add_argument("--model-id", default="")
    loop.add_argument("--workers", type=int, default=16)
    loop.add_argument("--iterations", type=int, default=0,
                      help="0 means run forever unless --once is set.")
    loop.add_argument("--once", action="store_true")
    loop.add_argument("--interval-seconds", type=int, default=1800)
    loop.add_argument("--include-agent-batch-traces", action="store_true")
    loop.add_argument("--include-legacy-recorder-traces", action="store_true")
    loop.add_argument("--no-local-evidence", action="store_true")
    loop.add_argument("--limit", type=int, default=0)
    loop.set_defaults(func=cmd_loop)

    outcome = sub.add_parser("record-outcome", help="Append route outcome/problem feedback for future training/export.")
    outcome.add_argument("--route-id", default="")
    outcome.add_argument("--profile", default="")
    outcome.add_argument("--from", dest="from_tile", required=True,
                         help="Start tile x,y,h or original route request string.")
    outcome.add_argument("--to", required=True, help="Target place id/name or x,y,h tile.")
    outcome.add_argument("--target-tile", default="")
    outcome.add_argument("--final", default="", help="Final tile x,y,h if known.")
    outcome.add_argument("--status", required=True,
                         help="success, blocked, combat, death, stalled, bad_route, or another compact status.")
    outcome.add_argument("--success", action="store_true")
    outcome.add_argument("--failure-kind", default="")
    outcome.add_argument("--problem-kind", default="")
    outcome.add_argument("--hitpoints-lost", type=int, default=0)
    outcome.add_argument("--is-dead", action="store_true")
    outcome.add_argument("--is-in-combat", action="store_true")
    outcome.add_argument("--run-enabled", action="store_true")
    outcome.add_argument("--run-energy-spent", type=int, default=0)
    outcome.add_argument("--route-quality", default="")
    outcome.add_argument("--route-mode", default="")
    outcome.add_argument("--route-distance", type=int)
    outcome.add_argument("--route-step-count", type=int)
    outcome.add_argument("--hazard-id", action="append")
    outcome.add_argument("--enemy-name", default="")
    outcome.add_argument("--enemy-level", type=int)
    outcome.add_argument("--enemy-tile", default="")
    outcome.add_argument("--enemy-aggressive", action="store_true")
    outcome.add_argument("--notes", default="")
    outcome.add_argument("--source", default="manual_agent_feedback")
    outcome.add_argument("--evidence-jsonl", default=DEFAULT_ROUTE_EVIDENCE_JSONL)
    outcome.set_defaults(func=cmd_record_outcome)
    return parser


def main(argv=None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv_list)
    log_usage("route_ml", surface="full", argv=argv_list)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
