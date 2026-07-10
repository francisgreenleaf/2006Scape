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
ML2_TOOLS = ROOT / "tools"
if str(ML2_TOOLS) not in sys.path:
    sys.path.insert(0, str(ML2_TOOLS))
TOOLS = ROOT.parent / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(ML2_TOOLS) in sys.path:
    sys.path.remove(str(ML2_TOOLS))
sys.path.insert(0, str(ML2_TOOLS))

from ml_routing.common import coordinate_layer, coordinate_layer_transition_block, parse_tile, tile_key  # noqa: E402
from ml_routing.benchmark import ML2_SHOWCASE_CASES  # noqa: E402
from ml_routing.collision import CollisionGrid, FULL_TILE_BLOCK, cache_area_transition_block  # noqa: E402
from ml_routing.dataset import route_hint_edges  # noqa: E402
from ml_routing.feedback import record_outcome  # noqa: E402
from ml_routing.fast_planner import fast_route  # noqa: E402
from ml_routing.fast_planner import _route_hint_records  # noqa: E402
from ml_routing.fast_planner import _route_hint_requirement_penalty  # noqa: E402
from ml_routing.model import segment_prediction, train_model  # noqa: E402
from ml_routing.planner import route_definition  # noqa: E402
from ml_routing.transition_catalog import transition_catalog  # noqa: E402
from ml_routing.validation import model_edge_warnings, route_geometry_summary, validate_route_steps  # noqa: E402
import execute_route_definition  # noqa: E402
import navdb  # noqa: E402
from execute_route_definition import choose_lookahead_target  # noqa: E402
from route_ml import persist_route_definition  # noqa: E402
from xs_common import route_definition as compact_route_definition  # noqa: E402


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
        self.assertIn("cannot cross", block["message"])
        self.assertIsNone(coordinate_layer_transition_block(
            parse_tile("3096,9868,0"),
            parse_tile("3111,9934,0"),
        ))
        block = coordinate_layer_transition_block(
            parse_tile("3093,4352,0"),
            parse_tile("3094,4353,0"),
        )
        self.assertIsNotNone(block)
        self.assertEqual(block["status"], "unsupported-coordinate-layer")
        self.assertEqual(block["fromLayer"], "off_surface")
        self.assertEqual(block["toLayer"], "off_surface")

    def test_underground_cache_area_blocks_separate_areas(self):
        self.assertIsNone(cache_area_transition_block(
            parse_tile("3096,9868,0"),
            parse_tile("3103,9910,0"),
        ))
        block = cache_area_transition_block(
            parse_tile("3096,9868,0"),
            parse_tile("2690,9090,0"),
        )
        self.assertIsNotNone(block)
        self.assertEqual(block["status"], "requires-object-transition")
        self.assertEqual(block["fromLayer"], "underground")
        self.assertEqual(block["toLayer"], "underground")
        self.assertNotEqual(
            block["fromArea"]["componentId"],
            block["toArea"]["componentId"],
        )


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


class TraceGraphTests(unittest.TestCase):
    def test_teleport_is_preserved_but_not_added_as_walk_edge(self):
        record = {
            "event": "teleport",
            "teleported": True,
            "mapRegionChanged": True,
            "tool": "server_passive_tick",
            "traceId": "teleport-regression",
            "previousTile": {"x": 3269, "y": 3167, "height": 0},
            "tile": {"x": 2662, "y": 3304, "height": 0},
        }
        with patch.object(navdb, "iter_movement_traces", return_value=iter([record])):
            graph = navdb.build_trace_graph()
        self.assertNotIn(("3269,3167,0", "2662,3304,0"), graph["edges"])
        self.assertEqual(graph["transitionKinds"], {"teleport": 1})
        self.assertEqual(graph["transitions"][0]["distance"], 607)

    def test_object_interaction_is_not_collapsed_into_walk_edge(self):
        record = {
            "event": "object_interaction",
            "tool": "server_passive_tick",
            "objectId": 190,
            "objectName": "Gate",
            "previousTile": {"x": 2459, "y": 3382, "height": 0},
            "tile": {"x": 2459, "y": 3385, "height": 0},
        }
        with patch.object(navdb, "iter_movement_traces", return_value=iter([record])):
            graph = navdb.build_trace_graph()
        self.assertFalse(graph["edges"])
        self.assertEqual(graph["transitionKinds"], {"object_interaction": 1})
        self.assertEqual(graph["transitions"][0]["objectId"], 190)

    def test_normal_map_region_boundary_step_remains_walkable(self):
        record = {
            "event": "movement",
            "mapRegionChanged": True,
            "tool": "server_passive_tick",
            "previousTile": {"x": 3053, "y": 3462, "height": 0},
            "tile": {"x": 3053, "y": 3464, "height": 0},
        }
        with patch.object(navdb, "iter_movement_traces", return_value=iter([record])):
            graph = navdb.build_trace_graph()
        self.assertIn(("3053,3462,0", "3053,3464,0"), graph["edges"])
        self.assertFalse(graph["transitions"])


class BenchmarkTests(unittest.TestCase):
    def test_ml2_showcase_cases_keep_requested_mix(self):
        self.assertEqual(len(ML2_SHOWCASE_CASES), 10)
        self.assertEqual(len({case["name"] for case in ML2_SHOWCASE_CASES}), 10)
        lengths = {}
        themes = set()
        for case in ML2_SHOWCASE_CASES:
            lengths[case["length"]] = lengths.get(case["length"], 0) + 1
            themes.add(case["theme"])
        self.assertGreaterEqual(lengths.get("long", 0), 6)
        self.assertEqual(lengths.get("medium", 0), 2)
        self.assertEqual(lengths.get("small", 0), 2)
        self.assertTrue({"wilderness", "morytania", "castle_wars"}.issubset(themes))


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
            self.assertIn("combatExposure", prediction)

    def test_train_refuses_untyped_long_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset"
            dataset.mkdir()
            record = {
                "from": "3269,3167,0",
                "to": "2662,3304,0",
                "fromTile": {"x": 3269, "y": 3167, "height": 0},
                "toTile": {"x": 2662, "y": 3304, "height": 0},
                "attempts": 1,
                "successes": 1,
                "ticks": 1,
                "distance": 607,
            }
            (dataset / "edge_examples.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid untyped walk edges"):
                train_model(SimpleNamespace(
                    dataset_dir=str(dataset),
                    model_id="invalid",
                    output_dir=str(Path(tmp) / "model"),
                    workers=2,
                    update_latest=False,
                ))

    def test_model_audit_finds_exact_al_kharid_discontinuity(self):
        warnings = model_edge_warnings({
            "edgeStats": {"3269,3167,0>2662,3304,0": {"successes": 1}},
        })
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["distance"], 607)

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
            self.assertGreater(prediction["combatExposure"], 0.0)

    def test_fast_route_prefers_low_combat_exposure_detour(self):
        model = {
            "modelId": "tiny",
            "trainedAt": "test",
            "datasetDir": "",
            "weights": {
                "combatExposurePenalty": 420.0,
                "hpLossPenalty": 35.0,
            },
            "global": {
                "averageTicks": 1.0,
                "averageDistance": 1.0,
                "riskScore": 0.0,
                "combatExposure": 0.0,
                "hpLossPerAttempt": 0.0,
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
                    "combatExposure": 1.0,
                    "hpLossPerAttempt": 1.0,
                    "confidence": 0.8,
                    "objectInteractionRate": 0.0,
                },
                "3201,3210,0>3202,3210,0": {
                    "successes": 3,
                    "failures": 0,
                    "averageTicks": 1.0,
                    "averageDistance": 1.0,
                    "riskScore": 0.0,
                    "combatExposure": 1.0,
                    "hpLossPerAttempt": 1.0,
                    "confidence": 0.8,
                    "objectInteractionRate": 0.0,
                },
                "3200,3210,0>3200,3211,0": {
                    "successes": 3,
                    "failures": 0,
                    "averageTicks": 1.0,
                    "averageDistance": 1.0,
                    "riskScore": 0.0,
                    "combatExposure": 0.0,
                    "hpLossPerAttempt": 0.0,
                    "confidence": 0.8,
                    "objectInteractionRate": 0.0,
                },
                "3200,3211,0>3201,3211,0": {
                    "successes": 3,
                    "failures": 0,
                    "averageTicks": 1.0,
                    "averageDistance": 1.0,
                    "riskScore": 0.0,
                    "combatExposure": 0.0,
                    "hpLossPerAttempt": 0.0,
                    "confidence": 0.8,
                    "objectInteractionRate": 0.0,
                },
                "3201,3211,0>3202,3210,0": {
                    "successes": 3,
                    "failures": 0,
                    "averageTicks": 1.0,
                    "averageDistance": 1.0,
                    "riskScore": 0.0,
                    "combatExposure": 0.0,
                    "hpLossPerAttempt": 0.0,
                    "confidence": 0.8,
                    "objectInteractionRate": 0.0,
                },
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
        self.assertEqual(result["next"], {"x": 3201, "y": 3211, "height": 0})

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

    def test_fast_route_supports_same_underground_area(self):
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
            to="3103,9910,0",
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
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "cache_direct")
        self.assertEqual(result["edgeSources"], {"cache_direct": result["routeDistance"]})
        self.assertTrue(result["collision"]["success"])
        self.assertTrue(result["collision"]["gridStats"]["validTileBoundary"])
        self.assertGreater(result["routeStepCount"], 1)

    def test_fast_route_cache_mesh_avoids_service_anchor_detour(self):
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
            "edgeStats": {},
        }
        result = fast_route(SimpleNamespace(
            from_tile="3254,3421,0",
            to="ardougne_south_bank",
            combat_level=61,
            food=3,
            coins=0,
            run_energy=80,
            run_enabled=True,
            allow_lethal=False,
            hazard_buffer=10,
            direct_hazard_buffer=10,
            direct_combat_margin=5,
            runnable_hazard_cost_factor=0.15,
            terminal_hazard_cost_factor=0.25,
            graph_snap_distance=16,
            max_batch_distance=24,
            compress_gap=18,
            max_suspects=5,
            max_warnings=8,
            no_cache_collision=False,
            no_cache_direct=False,
            no_cache_mesh=False,
            collision_padding_tiles=64,
            collision_max_expansions=250000,
            waypoint_arrival_radius=1,
            no_shortcut_optimize=False,
            shortcut_max_span=128,
            shortcut_min_savings=4,
            shortcut_corridor_radius=18,
            route_step_gap=10,
            direct_candidate_min_detour=1.22,
            direct_candidate_min_savings=24,
            direct_max_expansions=350000,
        ), model)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "cache_mesh")
        self.assertLess(result["routeDistance"], 1000)
        self.assertGreater(result["selectedOverLearned"]["savedTiles"], 400)
        self.assertEqual(result["routesUsed"], {
            "taverley_white_wolf_gate_west_to_east_transition_static_source": 1,
        })
        service_detours = {
            (3185, 3436),
            (2946, 3369),
        }
        route_step_xy = {(step["x"], step["y"]) for step in result.get("routeSteps", [])}
        self.assertFalse(service_detours & route_step_xy)

    def test_fast_route_rejects_underground_collision_failures(self):
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
            "edgeStats": {
                "3096,9868,0>3130,9919,0": {
                    "successes": 3,
                    "failures": 0,
                    "averageTicks": 1.0,
                    "averageDistance": 1.0,
                    "riskScore": 0.0,
                    "confidence": 0.8,
                    "objectInteractionRate": 0.0,
                },
            },
        }
        result = fast_route(SimpleNamespace(
            from_tile="3096,9868,0",
            to="3130,9919,0",
            combat_level=30,
            food=10,
            coins=0,
            run_energy=67,
            run_enabled=True,
            allow_lethal=False,
            hazard_buffer=10,
            graph_snap_distance=0,
            max_batch_distance=24,
            compress_gap=18,
            max_suspects=5,
            max_warnings=8,
            no_cache_direct=True,
        ), model)
        self.assertEqual(result["status"], "invalid-route-geometry")
        self.assertFalse(result["collisionExpanded"])
        self.assertIn("collision", result["message"])

    def test_fast_route_rejects_surface_collision_failures(self):
        model = {
            "modelId": "tiny",
            "trainedAt": "test",
            "weights": {},
            "global": {"averageTicks": 1.0, "averageDistance": 1.0, "riskScore": 0.0, "confidence": 0.8},
            "regionStats": {},
            "edgeStats": {
                "3200,3200,0>3250,3200,0": {
                    "successes": 3,
                    "failures": 0,
                    "averageTicks": 50.0,
                    "averageDistance": 50.0,
                    "riskScore": 0.0,
                    "confidence": 0.8,
                    "objectInteractionRate": 0.0,
                },
            },
        }
        args = SimpleNamespace(
            from_tile="3200,3200,0",
            to="3250,3200,0",
            combat_level=30,
            food=10,
            coins=0,
            run_energy=67,
            run_enabled=True,
            allow_lethal=False,
            hazard_buffer=10,
            graph_snap_distance=0,
            max_batch_distance=24,
            compress_gap=18,
            max_suspects=5,
            max_warnings=8,
            no_cache_collision=False,
            no_cache_direct=True,
            no_cache_mesh=True,
            collision_padding_tiles=64,
            collision_max_expansions=250000,
            waypoint_arrival_radius=1,
            no_shortcut_optimize=False,
            shortcut_max_span=128,
            shortcut_min_savings=4,
            shortcut_corridor_radius=18,
            route_step_gap=10,
        )
        failed_expansion = {
            "success": False,
            "tiles": [{"x": 3200, "y": 3200, "height": 0}],
            "distance": 0,
            "warnings": [{"reason": "no-cache-clipped-path"}],
            "failures": [{
                "from": "3200,3200,0",
                "to": "3250,3200,0",
                "distance": 50,
                "reason": "no-cache-clipped-path",
            }],
            "segmentsExpanded": 0,
            "skippedObjectTransitions": 0,
            "grid": {},
        }
        with patch("ml_routing.fast_planner.expand_route_path", return_value=failed_expansion):
            result = fast_route(args, model)
        self.assertEqual(result["status"], "invalid-route-geometry")
        self.assertFalse(result["collision"]["success"])
        self.assertIsNone(result["next"])

    def test_fast_route_blocks_separate_underground_areas(self):
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
            to="2690,9090,0",
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
        self.assertEqual(result["status"], "requires-object-transition")
        self.assertEqual(result["mode"], "requires_object_transition")
        self.assertEqual(result["coordinateLayers"], {"from": "underground", "to": "underground"})
        self.assertIn("separate underground cache areas", result["message"])
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

    def test_tree_gnome_gate_route_hint_preserves_transition_metadata(self):
        records = [
            record for record in route_hint_edges()
            if record.get("routeId") == "tree_gnome_stronghold_south_gate_transition_static_source"
            and record.get("objectTransition")
        ]
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["from"], "2459,3382,0")
        self.assertEqual(record["to"], "2459,3385,0")
        transition = record["transition"]
        self.assertEqual(transition["objectId"], 190)
        self.assertEqual(transition["objectTile"], {"x": 2459, "y": 3383, "height": 0})
        self.assertEqual(transition["preTile"], {"x": 2459, "y": 3382, "height": 0})
        self.assertEqual(transition["postTile"], {"x": 2459, "y": 3385, "height": 0})

    def test_fast_route_tree_gnome_gate_emits_mixed_route_steps(self):
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
            "edgeStats": {},
        }
        args = SimpleNamespace(
            from_tile="2459,3382,0",
            to="2459,3385,0",
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
            no_cache_collision=False,
            no_cache_direct=True,
            no_cache_mesh=True,
            collision_padding_tiles=64,
            collision_max_expansions=250000,
            waypoint_arrival_radius=1,
            no_shortcut_optimize=False,
            shortcut_max_span=128,
            shortcut_min_savings=4,
            shortcut_corridor_radius=18,
            route_step_gap=10,
        )
        result = fast_route(args, model)
        self.assertEqual(result["status"], "ok")
        transitions = [step for step in result["routeSteps"] if step.get("type") == "object_transition"]
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0]["objectId"], 190)
        definition_args = SimpleNamespace(
            **args.__dict__,
            runner_max_batches=8,
            trace_profile="",
            route_evidence_jsonl="agent-navigation/.local/run-evidence/test.routes.jsonl",
            no_route_evidence=False,
            planner="fast",
        )
        definition = route_definition(definition_args, result)
        self.assertEqual(definition["routeStepSchema"], "mixed_walk_object_transition_v1")
        self.assertTrue(any(step.get("type") == "object_transition" and step.get("objectId") == 190 for step in definition["routeSteps"]))

    def test_validation_flags_known_gate_crossed_as_plain_walk(self):
        catalog = [
            transition for transition in transition_catalog({"routes": [
                {
                    "id": "tree_gnome_stronghold_south_gate_transition_static_source",
                    "status": "verified",
                    "bidirectional": True,
                    "steps": [
                        {
                            "type": "object_transition",
                            "objectId": 190,
                            "objectName": "Gate",
                            "objectTile": {"x": 2459, "y": 3383, "height": 0},
                            "preTile": {"x": 2459, "y": 3382, "height": 0},
                            "postTile": {"x": 2459, "y": 3385, "height": 0},
                            "transitionProof": {
                                "preTile": {"x": 2459, "y": 3382, "height": 0},
                                "objectTile": {"x": 2459, "y": 3383, "height": 0},
                                "postTile": {"x": 2459, "y": 3385, "height": 0},
                            },
                        },
                    ],
                },
            ]})
        ]
        warnings = validate_route_steps([
            {"type": "walk", "x": 2459, "y": 3382, "height": 0},
            {"type": "walk", "x": 2459, "y": 3385, "height": 0},
        ], catalog)
        self.assertEqual(warnings[0]["type"], "known_transition_as_plain_walk")
        self.assertEqual(warnings[0]["objectId"], 190)

    def test_route_hint_requirement_penalty_counts_safety_warnings(self):
        self.assertEqual(_route_hint_requirement_penalty([]), 0.0)
        self.assertGreater(
            _route_hint_requirement_penalty([
                "route wants combat 3 < required 20",
                "route wants food 0 < required 3",
            ]),
            _route_hint_requirement_penalty(["route wants food 0 < required 3"]),
        )


class ApiTests(unittest.TestCase):
    def test_corrupt_route_is_non_actionable_and_compact_output_exposes_jump(self):
        args = SimpleNamespace(
            from_tile="3254,3421,0",
            to="ardougne_south_bank",
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
            "mode": "learned",
            "status": "ok",
            "targetTile": {"x": 2618, "y": 3332, "height": 0},
            "routeDistance": 894,
            "edgeSources": {"model_trace": 2},
            "routeSteps": [
                {"type": "walk", "x": 3269, "y": 3167, "height": 0},
                {"type": "walk", "x": 2662, "y": 3295, "height": 0},
            ],
        }
        definition = route_definition(args, candidate)
        self.assertEqual(definition["status"], "invalid-route-geometry")
        self.assertFalse(definition["actionable"])
        self.assertFalse(definition["evidence"]["proven"])
        self.assertEqual(definition["geometry"]["largestDiscontinuity"]["distance"], 607)
        self.assertEqual(definition["execution"]["command"], [])
        compact = compact_route_definition(definition)
        self.assertEqual(compact["geometry"]["largestJump"]["distance"], 607)
        self.assertIn("do_not_execute", compact["decision"])
        with tempfile.TemporaryDirectory() as tmp:
            persisted = persist_route_definition(SimpleNamespace(route_definition_dir=tmp), definition)
        self.assertEqual(persisted["execution"]["command"], [])

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
        self.assertIn("agent-navigation/ml2-routing/tools/execute_route_definition.py", definition["execution"]["command"])
        self.assertIn("--evidence-jsonl", definition["execution"]["command"])
        self.assertIn("legacyRouteRunnerCommand", definition["execution"])
        self.assertEqual(definition["evidence"]["level"], "trace_proven")
        self.assertTrue(definition["evidence"]["proven"])
        self.assertEqual(definition["feedback"]["automaticEvidenceJsonl"], "agent-navigation/.local/run-evidence/test.routes.jsonl")

    def test_cache_planned_evidence_is_actionable_not_player_proven(self):
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
            "edgeSources": {"cache_direct": 2},
            "routeSteps": [
                {"x": 1, "y": 1, "height": 0},
                {"x": 2, "y": 1, "height": 0},
                {"x": 3, "y": 1, "height": 0},
            ],
            "runPlan": {"policy": "default", "routeDistance": 2, "runTileDistance": 0, "walkTileDistance": 2, "segmentCount": 0},
            "routeRunnerCommand": ["python3", "agent-navigation/tools/route_runner.py", "--to", "3,1,0"],
        }
        definition = route_definition(args, candidate)
        self.assertTrue(definition["actionable"])
        self.assertEqual(definition["evidence"]["level"], "cache_planned")
        self.assertFalse(definition["evidence"]["proven"])
        self.assertIn("Planned from the cache map", definition["evidence"]["summary"])

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
        self.assertIn("coordinate layers", definition["safety"]["reviewReasons"][0])
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


class ExecutorTests(unittest.TestCase):
    def test_executor_rejects_corrupt_route_before_bridge_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            route_path = Path(tmp) / "route.json"
            evidence_path = Path(tmp) / "evidence.jsonl"
            route_path.write_text(json.dumps({
                "schemaVersion": 1,
                "api": "2006scape.route-definition",
                "routeId": "corrupt-regression",
                "mode": "learned",
                "from": "3254,3421,0",
                "to": "ardougne_south_bank",
                "targetTile": {"x": 2618, "y": 3332, "height": 0},
                "routeSteps": [
                    {"type": "walk", "x": 3269, "y": 3167, "height": 0},
                    {"type": "walk", "x": 2662, "y": 3295, "height": 0},
                ],
            }), encoding="utf-8")
            args = SimpleNamespace(
                route_definition=str(route_path),
                profile="",
                evidence_jsonl=str(evidence_path),
                run_mode="auto",
                eat_at=0,
                arrival_radius=None,
                max_ticks=95,
                max_walk_distance=36,
                stop_distance=0,
                transition_approach_distance=0,
                transition_post_distance=0,
                transition_max_ticks=20,
                lookahead_distance=30,
                lookahead_step_limit=4,
                no_lookahead=False,
                off_route_distance=-1,
                stop_on_combat=False,
                observe_on_contact=False,
                report_every=100,
            )
            with patch.object(execute_route_definition.bridge, "observe") as observe, \
                    patch.object(execute_route_definition.bridge, "call_tool") as call_tool:
                self.assertEqual(execute_route_definition.run(args), 5)
            observe.assert_not_called()
            call_tool.assert_not_called()
            outcome = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual(outcome["problemKind"], "route_data_corruption")
            self.assertEqual(outcome["geometry"]["largestDiscontinuity"]["distance"], 607)

    def test_executor_dispatches_object_transition_and_stops_walk_lookahead(self):
        with tempfile.TemporaryDirectory() as tmp:
            route_path = Path(tmp) / "route.json"
            evidence_path = Path(tmp) / "evidence.jsonl"
            route_path.write_text(json.dumps({
                "schemaVersion": 1,
                "api": "2006scape.route-definition",
                "routeId": "unit-transition",
                "mode": "cache_mesh",
                "quality": "watch",
                "to": "target",
                "targetTile": {"x": 12, "y": 0, "height": 0},
                "arrivalRadius": 0,
                "routeSteps": [
                    {"type": "walk", "x": 1, "y": 0, "height": 0},
                    {
                        "type": "object_transition",
                        "objectId": 99,
                        "objectName": "Gate",
                        "objectTile": {"x": 1, "y": 1, "height": 0},
                        "preTile": {"x": 1, "y": 0, "height": 0},
                        "postTile": {"x": 2, "y": 0, "height": 0},
                        "option": "open",
                    },
                    {"type": "walk", "x": 12, "y": 0, "height": 0},
                ],
            }), encoding="utf-8")
            player = {
                "name": "Unit",
                "tile": {"x": 0, "y": 0, "height": 0},
                "hitpoints": 10,
                "maxHitpoints": 10,
                "runEnergy": 50,
                "runEnabled": True,
                "inventory": [],
            }
            calls = []

            def result_player():
                return dict(player)

            def call_tool(name, arguments, profile=""):
                calls.append((name, dict(arguments)))
                if name == "walk_to_tile_until_arrived_XS":
                    player["tile"] = {"x": int(arguments["x"]), "y": int(arguments["y"]), "height": int(arguments.get("height", 0))}
                    return {"success": True, "batchStatus": "arrived", "player": result_player()}
                if name == "object_transition_step_XS":
                    player["tile"] = {"x": 2, "y": 0, "height": 0}
                    return {"success": True, "status": "arrived", "player": result_player()}
                raise AssertionError("unexpected tool call {}".format(name))

            args = SimpleNamespace(
                route_definition=str(route_path),
                profile="",
                evidence_jsonl=str(evidence_path),
                run_mode="auto",
                eat_at=0,
                arrival_radius=None,
                max_ticks=95,
                max_walk_distance=36,
                stop_distance=0,
                transition_approach_distance=0,
                transition_post_distance=0,
                transition_max_ticks=20,
                lookahead_distance=30,
                lookahead_step_limit=4,
                no_lookahead=False,
                off_route_distance=-1,
                stop_on_combat=False,
                observe_on_contact=False,
                report_every=100,
            )
            with patch.object(execute_route_definition.bridge, "observe", return_value=player), \
                    patch.object(execute_route_definition.bridge, "call_tool", side_effect=call_tool):
                self.assertEqual(execute_route_definition.run(args), 0)
            self.assertEqual([name for name, _args in calls], [
                "walk_to_tile_until_arrived_XS",
                "object_transition_step_XS",
                "walk_to_tile_until_arrived_XS",
            ])
            self.assertEqual(calls[0][1]["x"], 1)
            self.assertEqual(calls[1][1]["objectId"], 99)
            self.assertEqual(calls[2][1]["x"], 12)

    def test_choose_lookahead_target_advances_multiple_route_steps(self):
        steps = [
            {"x": 0, "y": 0, "height": 0},
            {"x": 10, "y": 0, "height": 0},
            {"x": 20, "y": 0, "height": 0},
            {"x": 30, "y": 0, "height": 0},
            {"x": 40, "y": 0, "height": 0},
        ]
        index, target, planned = choose_lookahead_target(
            steps,
            0,
            {"x": 0, "y": 0, "height": 0},
            lookahead_distance=30,
            step_limit=4,
        )
        self.assertEqual(index, 3)
        self.assertEqual(target, {"x": 30, "y": 0, "height": 0})
        self.assertEqual(planned, 30)

    def test_choose_lookahead_target_can_preserve_single_step_mode(self):
        steps = [
            {"x": 0, "y": 0, "height": 0},
            {"x": 10, "y": 0, "height": 0},
        ]
        index, target, _planned = choose_lookahead_target(
            steps,
            0,
            {"x": 0, "y": 0, "height": 0},
            lookahead_distance=0,
            step_limit=4,
        )
        self.assertEqual(index, 0)
        self.assertEqual(target, {"x": 0, "y": 0, "height": 0})


if __name__ == "__main__":
    unittest.main()
