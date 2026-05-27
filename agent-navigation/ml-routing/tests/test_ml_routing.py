#!/usr/bin/env python3
"""Lightweight tests for the ML routing package."""

from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml_routing.common import coordinate_layer, coordinate_layer_transition_block, parse_tile, tile_key  # noqa: E402
from ml_routing.collision import CollisionGrid, FULL_TILE_BLOCK  # noqa: E402
from ml_routing.feedback import record_outcome  # noqa: E402
from ml_routing.fast_planner import fast_route  # noqa: E402
from ml_routing.fast_planner import _route_hint_records  # noqa: E402
from ml_routing.model import segment_prediction, train_model  # noqa: E402
from ml_routing.planner import route_definition  # noqa: E402
from route_ml import persist_route_definition  # noqa: E402


class CommonTests(unittest.TestCase):
    def test_tile_roundtrip(self):
        tile = parse_tile("3200,3210,0")
        self.assertEqual(tile_key(tile), "3200,3210,0")

    def test_coordinate_layers_match_cache_surface_bounds(self):
        self.assertEqual(coordinate_layer(parse_tile("3093,3498,0")), "surface")
        self.assertEqual(coordinate_layer(parse_tile("3111,9934,0")), "underground")
        self.assertEqual(coordinate_layer(parse_tile("3093,4352,0")), "off_surface")
        block = coordinate_layer_transition_block(
            parse_tile("3093,3498,0"),
            parse_tile("3111,9934,0"),
        )
        self.assertIsNotNone(block)
        self.assertEqual(block["status"], "requires-object-transition")
        self.assertEqual(block["fromLayer"], "surface")
        self.assertEqual(block["toLayer"], "underground")
        self.assertIn("cannot route underground", block["message"])
        block = coordinate_layer_transition_block(
            parse_tile("3096,9868,0"),
            parse_tile("3111,9934,0"),
        )
        self.assertIsNotNone(block)
        self.assertEqual(block["status"], "unsupported-coordinate-layer")
        self.assertEqual(block["fromLayer"], "underground")
        self.assertEqual(block["toLayer"], "underground")
        self.assertIn("cannot route underground", block["message"])


class CollisionTests(unittest.TestCase):
    def test_grid_routes_around_blocked_tile(self):
        grid = CollisionGrid(
            bounds={"minX": 0, "minY": 0, "maxX": 4, "maxY": 4},
            plane=0,
            clips={(2, 2): FULL_TILE_BLOCK},
            stats={},
        )
        path = grid.find_path(
            {"x": 1, "y": 2, "height": 0},
            {"x": 3, "y": 2, "height": 0},
        )
        self.assertIsNotNone(path)
        self.assertNotIn({"x": 2, "y": 2, "height": 0}, path)
        self.assertGreater(len(path), 2)

    def test_grid_routes_around_penalized_tile(self):
        grid = CollisionGrid(
            bounds={"minX": 0, "minY": 0, "maxX": 4, "maxY": 4},
            plane=0,
            clips={},
            stats={},
        )
        path = grid.find_path(
            {"x": 1, "y": 2, "height": 0},
            {"x": 3, "y": 2, "height": 0},
            tile_penalty=lambda x, y: 50.0 if (x, y) == (2, 2) else 0.0,
        )
        self.assertIsNotNone(path)
        self.assertNotIn({"x": 2, "y": 2, "height": 0}, path)


class ModelTests(unittest.TestCase):
    def test_train_and_score_tiny_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset"
            dataset.mkdir()
            record = {
                "from": "1,1,0",
                "to": "2,1,0",
                "fromTile": {"x": 1, "y": 1, "height": 0},
                "toTile": {"x": 2, "y": 1, "height": 0},
                "attempts": 4,
                "successes": 4,
                "failures": 0,
                "ticks": 4,
                "distance": 1,
                "combatTicks": 0,
                "hitpointsLost": 0,
            }
            with (dataset / "edge_examples.jsonl").open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
            model = train_model(SimpleNamespace(
                dataset_dir=str(dataset),
                model_id="test",
                output_dir=str(Path(tmp) / "model"),
                workers=2,
                update_latest=False,
            ))
            prediction = segment_prediction(
                model,
                {"x": 1, "y": 1, "height": 0},
                {"x": 2, "y": 1, "height": 0},
            )
            self.assertEqual(prediction["source"], "edge")
            self.assertGreater(prediction["confidence"], 0.5)

    def test_train_uses_route_attempt_outcomes_for_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset"
            dataset.mkdir()
            edge = {
                "from": "1,1,0",
                "to": "2,1,0",
                "fromTile": {"x": 1, "y": 1, "height": 0},
                "toTile": {"x": 2, "y": 1, "height": 0},
                "attempts": 4,
                "successes": 4,
                "failures": 0,
                "ticks": 4,
                "distance": 1,
            }
            attempt = {
                "event": "route_outcome",
                "fromTile": {"x": 10, "y": 10, "height": 0},
                "finalTile": {"x": 11, "y": 10, "height": 0},
                "success": False,
                "status": "combat",
                "isInCombat": True,
                "hitpointsLost": 3,
                "enemy": {
                    "name": "Highwayman",
                    "combatLevel": 5,
                    "tile": {"x": 16, "y": 16, "height": 0},
                    "aggressive": True,
                },
            }
            (dataset / "edge_examples.jsonl").write_text(json.dumps(edge) + "\n", encoding="utf-8")
            (dataset / "route_attempts.jsonl").write_text(json.dumps(attempt) + "\n", encoding="utf-8")
            model = train_model(SimpleNamespace(
                dataset_dir=str(dataset),
                model_id="attempt-risk",
                output_dir=str(Path(tmp) / "model"),
                workers=2,
                update_latest=False,
            ))
            prediction = segment_prediction(
                model,
                {"x": 10, "y": 10, "height": 0},
                {"x": 16, "y": 16, "height": 0},
            )
            self.assertEqual(prediction["source"], "edge")
            self.assertGreater(prediction["riskScore"], 0.2)

    def test_fast_route_with_tiny_model(self):
        model = {
            "modelId": "tiny",
            "trainedAt": "test",
            "datasetDir": "",
            "weights": {},
            "global": {
                "averageTicks": 1.0,
                "averageDistance": 1.0,
                "riskScore": 0.0,
                "confidence": 0.8,
            },
            "regionStats": {},
            "edgeStats": {
                "3200,3210,0>3201,3210,0": {
                    "successes": 3,
                    "failures": 0,
                    "averageTicks": 1.0,
                    "averageDistance": 1.0,
                    "riskScore": 0.0,
                    "confidence": 0.8,
                    "objectInteractionRate": 0.0,
                },
                "3201,3210,0>3202,3210,0": {
                    "successes": 3,
                    "failures": 0,
                    "averageTicks": 1.0,
                    "averageDistance": 1.0,
                    "riskScore": 0.0,
                    "confidence": 0.8,
                    "objectInteractionRate": 0.0,
                }
            },
        }
        result = fast_route(SimpleNamespace(
            from_tile="3200,3210,0",
            to="3202,3210,0",
            combat_level=3,
            food=0,
            coins=0,
            run_energy=0,
            run_enabled=False,
            allow_lethal=False,
            hazard_buffer=10,
            graph_snap_distance=0,
            max_batch_distance=24,
            compress_gap=18,
            max_suspects=5,
            max_warnings=8,
            no_cache_collision=True,
            no_cache_direct=True,
        ), model)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["next"], {"x": 3201, "y": 3210, "height": 0})

    def test_fast_route_blocks_surface_to_underground(self):
        model = {
            "modelId": "tiny",
            "trainedAt": "test",
            "weights": {},
            "global": {
                "averageTicks": 1.0,
                "averageDistance": 1.0,
                "riskScore": 0.0,
                "confidence": 0.8,
            },
            "regionStats": {},
            "edgeStats": {},
        }
        result = fast_route(SimpleNamespace(
            from_tile="3093,3498,0",
            to="3111,9934,0",
            combat_level=30,
            food=10,
            coins=0,
            run_energy=89,
            run_enabled=True,
            allow_lethal=False,
            hazard_buffer=10,
            graph_snap_distance=16,
            max_batch_distance=24,
            compress_gap=18,
            max_suspects=5,
            max_warnings=8,
        ), model)
        self.assertEqual(result["status"], "requires-object-transition")
        self.assertEqual(result["coordinateLayers"], {"from": "surface", "to": "underground"})
        self.assertIsNone(result.get("next"))

    def test_fast_route_blocks_underground_routing(self):
        model = {
            "modelId": "tiny",
            "trainedAt": "test",
            "weights": {},
            "global": {
                "averageTicks": 1.0,
                "averageDistance": 1.0,
                "riskScore": 0.0,
                "confidence": 0.8,
            },
            "regionStats": {},
            "edgeStats": {},
        }
        result = fast_route(SimpleNamespace(
            from_tile="3096,9868,0",
            to="3111,9934,0",
            combat_level=30,
            food=10,
            coins=0,
            run_energy=67,
            run_enabled=True,
            allow_lethal=False,
            hazard_buffer=10,
            graph_snap_distance=16,
            max_batch_distance=24,
            compress_gap=18,
            max_suspects=5,
            max_warnings=8,
        ), model)
        self.assertEqual(result["status"], "unsupported-coordinate-layer")
        self.assertEqual(result["mode"], "surface_only")
        self.assertEqual(result["coordinateLayers"], {"from": "underground", "to": "underground"})
        self.assertIn("cannot route underground", result["message"])
        self.assertIsNone(result.get("next"))

    def test_current_route_hints_override_stale_model_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset"
            dataset.mkdir()
            stale = {"routeId": "stale", "routeIndex": 0}
            (dataset / "route_hint_edges.jsonl").write_text(json.dumps(stale) + "\n", encoding="utf-8")
            current = {"routeId": "current", "routeIndex": 0}
            with patch("ml_routing.dataset.route_hint_edges", return_value=[current]):
                records = _route_hint_records({"datasetDir": str(dataset)})
            self.assertEqual(records, [current])


class ApiTests(unittest.TestCase):
    def test_route_definition_includes_execution_and_feedback(self):
        args = SimpleNamespace(
            from_tile="1,1,0",
            to="3,1,0",
            allow_lethal=False,
            max_batch_distance=24,
            runner_max_batches=8,
            trace_profile="",
            route_evidence_jsonl="agent-navigation/.local/run-evidence/test.routes.jsonl",
            no_route_evidence=False,
            planner="fast",
        )
        candidate = {
            "planner": "fast",
            "mode": "cache_direct",
            "status": "ok",
            "quality": "watch",
            "targetTile": {"x": 3, "y": 1, "height": 0},
            "routeDistance": 2,
            "estimatedTicks": 2.0,
            "next": {"x": 2, "y": 1, "height": 0},
            "edgeSources": {"model_trace": 2},
            "routeSteps": [
                {"x": 1, "y": 1, "height": 0},
                {"x": 2, "y": 1, "height": 0},
                {"x": 3, "y": 1, "height": 0},
            ],
            "runPlan": {"policy": "default", "routeDistance": 2, "runTileDistance": 0, "walkTileDistance": 2, "segmentCount": 0},
            "routeRunnerCommand": ["python3", "agent-navigation/tools/route_runner.py", "--to", "3,1,0", "--evidence-jsonl", "agent-navigation/.local/run-evidence/test.routes.jsonl"],
        }
        definition = route_definition(args, candidate)
        self.assertEqual(definition["api"], "2006scape.route-definition")
        self.assertEqual(definition["routeStepCount"], 3)
        self.assertIn("agent-navigation/tools/execute_route_definition.py", definition["execution"]["command"])
        self.assertIn("--evidence-jsonl", definition["execution"]["command"])
        self.assertIn("legacyRouteRunnerCommand", definition["execution"])
        self.assertEqual(definition["evidence"]["level"], "trace_proven")
        self.assertTrue(definition["evidence"]["proven"])
        self.assertEqual(definition["feedback"]["automaticEvidenceJsonl"], "agent-navigation/.local/run-evidence/test.routes.jsonl")

    def test_route_definition_explains_coordinate_layer_transition_block(self):
        args = SimpleNamespace(
            from_tile="3093,3498,0",
            to="3111,9934,0",
            allow_lethal=False,
            max_batch_distance=24,
            runner_max_batches=8,
            trace_profile="",
            route_evidence_jsonl="",
            no_route_evidence=False,
            planner="fast",
        )
        candidate = {
            "planner": "fast",
            "mode": "requires_object_transition",
            "status": "requires-object-transition",
            "quality": "bad",
            "targetTile": {"x": 3111, "y": 9934, "height": 0},
            "error": "ML routing cannot cross coordinate layers yet.",
            "message": "ML routing cannot cross coordinate layers yet.",
            "coordinateLayers": {"from": "surface", "to": "underground"},
            "transition": {
                "fromLayer": "surface",
                "toLayer": "underground",
                "fromTile": {"x": 3093, "y": 3498, "height": 0},
                "targetTile": {"x": 3111, "y": 9934, "height": 0},
            },
        }
        definition = route_definition(args, candidate)
        self.assertFalse(definition["actionable"])
        self.assertEqual(definition["status"], "requires-object-transition")
        self.assertEqual(definition["coordinateLayers"], {"from": "surface", "to": "underground"})
        self.assertIn("surface/underground", definition["safety"]["reviewReasons"][1])
        self.assertEqual(definition["execution"]["strategy"], "not_actionable")
        self.assertEqual(definition["execution"]["command"], [])

    def test_persist_route_definition_adds_runner_file_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            definition = {
                "api": "2006scape.route-definition",
                "schemaVersion": 1,
                "routeId": "test route",
                "actionable": True,
                "routeSteps": [
                    {"x": 1, "y": 1, "height": 0},
                    {"x": 2, "y": 1, "height": 0},
                ],
                "execution": {
                    "command": ["python3", "agent-navigation/tools/route_runner.py", "--to", "2,1,0"],
                },
            }
            persisted = persist_route_definition(SimpleNamespace(route_definition_dir=tmp), definition)
            command = persisted["execution"]["command"]
            self.assertIn("--route-definition", command)
            path = Path(command[command.index("--route-definition") + 1])
            self.assertTrue(path.exists())
            self.assertEqual(path.parent, Path(tmp))

    def test_record_outcome_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "outcome.jsonl"
            result = record_outcome(SimpleNamespace(
                evidence_jsonl=str(output),
                route_id="test",
                profile="mrflame",
                from_tile="1,1,0",
                to="target",
                target_tile="2,2,0",
                final="1,2,0",
                status="combat",
                success=False,
                failure_kind="enemy",
                problem_kind="enemy_contact",
                hitpoints_lost=2,
                is_dead=False,
                is_in_combat=True,
                run_enabled=True,
                run_energy_spent=4,
                route_quality="suspicious",
                route_mode="cache_direct",
                route_distance=12,
                route_step_count=3,
                hazard_id=["hazard_a"],
                enemy_name="Highwayman",
                enemy_level=5,
                enemy_tile="1,3,0",
                enemy_aggressive=True,
                notes="test",
                source="unit",
            ))
            self.assertTrue(result["success"])
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[0]["event"], "route_outcome")
            self.assertEqual(records[0]["enemy"]["name"], "Highwayman")


if __name__ == "__main__":
    unittest.main()
