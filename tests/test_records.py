import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from terminal_starfield.cli import FlightRecorder
from terminal_starfield.model import Simulation
from terminal_starfield.records import FlightLogError, load_records, record_run
from terminal_starfield.render import Renderer


def result(index=0, score=100):
    return dict(id=str(index), finished_at="2026-09-08T12:00:00+00:00",
                mode="campaign", ship="vanguard", seed=7, outcome="game_over",
                score=score, kills=5, wave=2, best_combo=3, seconds=35.5)


class FlightLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "nested" / "flight-log.json"

    def test_missing_log_is_empty_without_creating_directories(self):
        self.assertEqual(load_records(self.path)["total_runs"], 0)
        self.assertFalse(self.path.parent.exists())

    def test_result_roundtrip_and_duplicate_is_not_counted(self):
        record_run(self.path, result())
        data = record_run(self.path, result())
        self.assertEqual(data["total_runs"], 1)
        self.assertEqual(load_records(self.path)["best"]["seed"], 7)

    def test_odyssey_statistics_roundtrip_alongside_legacy_results(self):
        record_run(self.path, result())
        entry = result(1)
        entry.update(ruleset="4.0.0", route=["frontier", "veil", "graveyard"],
                     accuracy=64.5, grazes=12, bosses=3)
        record_run(self.path, entry)
        self.assertEqual(load_records(self.path)["history"], [entry, result()])

    def test_invalid_optional_statistics_do_not_replace_previous_log(self):
        record_run(self.path, result())
        before = self.path.read_bytes()
        for field, value in (("route", ["unknown"]), ("route", ["veil"] * 33),
                             ("ruleset", "\x1b[2J"), ("accuracy", float("nan")),
                             ("accuracy", 101), ("grazes", True), ("bosses", 2 ** 63)):
            with self.subTest(field=field, value=value):
                entry = result(1)
                entry[field] = value
                with self.assertRaises(FlightLogError):
                    record_run(self.path, entry)
                self.assertEqual(self.path.read_bytes(), before)

    def test_demo_completion_is_never_recorded_even_by_enabled_observer(self):
        sim = Simulation(seed=7)
        sim.start_run("campaign")
        sim.state.demo = True
        sim.state.screen = "victory"
        FlightRecorder(self.path).observe(sim.state)
        self.assertFalse(self.path.parent.exists())

    def test_history_is_bounded_but_best_and_total_survive(self):
        for index in range(40):
            record_run(self.path, result(index, 1000 if index == 0 else 10))
        data = load_records(self.path)
        self.assertEqual(data["total_runs"], 40)
        self.assertEqual(len(data["history"]), 30)
        self.assertEqual(data["history"][0]["id"], "39")
        self.assertEqual(data["best"]["score"], 1000)

    def test_corrupt_or_invalid_log_is_preserved(self):
        self.path.parent.mkdir()
        for raw in ("broken", "[]", '{"version":99}',
                    json.dumps(dict(version=1, total_runs=True, best=None, history=[]))):
            self.path.write_text(raw)
            with self.assertRaises(FlightLogError):
                record_run(self.path, result())
            self.assertEqual(self.path.read_text(), raw)

    def test_failed_replace_preserves_previous_log(self):
        record_run(self.path, result())
        before = self.path.read_bytes()
        with patch("terminal_starfield.records.os.replace", side_effect=OSError("read only")):
            with self.assertRaises(FlightLogError):
                record_run(self.path, result(1))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(list(self.path.parent.glob("*.tmp")))

    def test_concurrent_completions_are_retained(self):
        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(lambda index: record_run(self.path, result(index)), range(12)))
        self.assertEqual(load_records(self.path)["total_runs"], 12)

    def test_only_completed_combat_results_are_accepted(self):
        for field, value in (("mode", "zen"), ("outcome", "playing"),
                             ("score", -1), ("seconds", float("nan"))):
            entry = result()
            entry[field] = value
            with self.assertRaises(FlightLogError):
                record_run(self.path, entry)
        self.assertFalse(self.path.exists())

    def test_oversized_persisted_numbers_are_rejected_and_preserved(self):
        self.path.parent.mkdir()
        fields = ("score", "kills", "wave", "best_combo", "seconds")
        for location, field in (("log", "total_runs"), *(
                (location, field) for location in ("best", "history") for field in fields)):
            for value in (2 ** 63, 10 ** 400):
                with self.subTest(location=location, field=field, value=value):
                    data = dict(version=1, total_runs=1, best=result(), history=[result()])
                    target = data if location == "log" else (
                        data["best"] if location == "best" else data["history"][0])
                    target[field] = value
                    raw = json.dumps(data)
                    self.path.write_text(raw)
                    with self.assertRaises(FlightLogError):
                        load_records(self.path)
                    with self.assertRaises(FlightLogError):
                        record_run(self.path, result(1))
                    self.assertEqual(self.path.read_text(), raw)

    def test_oversized_log_keeps_runtime_and_title_rendering_available(self):
        self.path.parent.mkdir()
        for field, value in (("seconds", 10 ** 400), ("seconds", 1e300),
                             ("score", 10 ** 400), ("total_runs", 10 ** 400)):
            with self.subTest(field=field, value=value):
                data = dict(version=1, total_runs=1, best=result(), history=[result()])
                target = data if field == "total_runs" else data["best"]
                target[field] = value
                raw = json.dumps(data)
                self.path.write_text(raw)
                recorder = FlightRecorder(self.path)
                sim = Simulation(seed=7)
                sim.show_title()
                for screen in ("title", "game_over"):
                    if screen == "game_over":
                        sim.start_run("campaign")
                        sim.state.screen = screen
                    recorder.observe(sim.state)
                    for width, height in ((20, 8), (80, 24)):
                        frame = Renderer(unicode=False).frame(sim.state, width, height, color=False)
                        self.assertEqual([len(line) for line in frame.splitlines()], [width] * height)
                    self.assertEqual(sim.state.record_status, "FLIGHT LOG UNAVAILABLE")
                self.assertTrue(recorder.failed)
                self.assertEqual(self.path.read_text(), raw)

    def test_numeric_boundaries_and_arbitrary_integer_seeds_roundtrip(self):
        maximum = 2 ** 63 - 1
        for index, seed in enumerate((10 ** 400, -(10 ** 400))):
            entry = result(index)
            entry.update(dict.fromkeys(("score", "kills", "wave", "best_combo", "seconds"), maximum))
            entry["seed"] = seed
            record_run(self.path, entry)
            self.assertEqual(load_records(self.path)["history"][0], entry)

    def test_total_run_boundary_cannot_write_an_unreadable_log(self):
        self.path.parent.mkdir()
        data = dict(version=1, total_runs=2 ** 63 - 2, best=result(), history=[result()])
        self.path.write_text(json.dumps(data))
        self.assertEqual(record_run(self.path, result(1))["total_runs"], 2 ** 63 - 1)
        before = self.path.read_bytes()
        self.assertEqual(record_run(self.path, result(1))["total_runs"], 2 ** 63 - 1)
        with self.assertRaises(FlightLogError):
            record_run(self.path, result(2))
        self.assertEqual(self.path.read_bytes(), before)
