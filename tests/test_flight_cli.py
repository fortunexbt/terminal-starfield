import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from terminal_starfield.cli import FlightRecorder, KeyDecoder, build_parser, handle_key, main, run_interactive
from terminal_starfield.model import Projectile, Simulation


class InputTests(unittest.TestCase):
    def test_batched_arrows_preserve_every_key(self):
        self.assertEqual(KeyDecoder().feed(b"\x1b[A\x1b[Ds m"), ["UP", "LEFT", "s", " ", "m"])

    def test_split_arrow_and_escape_timeout(self):
        decoder = KeyDecoder()
        self.assertEqual(decoder.feed(b"\x1b", now=1), [])
        self.assertEqual(decoder.feed(b"[", now=1.01), [])
        self.assertEqual(decoder.feed(b"C", now=1.02), ["RIGHT"])
        self.assertEqual(decoder.feed(b"\x1b", now=2), [])
        self.assertEqual(decoder.feed(b"", now=2.1), ["ESC"])

    def test_ss3_and_modified_arrows(self):
        self.assertEqual(KeyDecoder().feed(b"\x1bOA\x1b[1;5D"), ["UP", "LEFT"])

    def test_ship_selection_and_direct_cli(self):
        args = build_parser().parse_args(["--ship", "aegis", "--no-record"])
        self.assertEqual(args.ship, "aegis")
        sim = Simulation(seed=7)
        sim.show_title()
        handle_key(sim, "d")
        self.assertEqual(sim.state.ship_id, "wraith")
        handle_key(sim, "\r")
        self.assertEqual(sim.state.ship_id, "wraith")

    def test_pause_blocks_actions_until_resumed(self):
        sim = Simulation(seed=7)
        sim.start_run("campaign")
        handle_key(sim, "p")
        for key in ("a", "d", "e", "b", "m", "UP"):
            handle_key(sim, key)
        self.assertEqual(sim.state.velocity_x, 0)
        self.assertEqual(sim.state.energy, 100)
        self.assertEqual(sim.state.throttle, .38)
        self.assertEqual(sim.state.pulse_cooldown, 0)
        handle_key(sim, " ")
        self.assertFalse(sim.state.paused)


class RuntimeRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "log.json"

    def test_quit_does_not_advance_or_record_a_pending_loss(self):
        sim = Simulation(seed=7)
        args = build_parser().parse_args(["--mode", "campaign", "--seed", "7",
                                         "--record-file", str(self.path)])

        class FakeTTY(io.StringIO):
            def isatty(self):
                return True

        def quit_before_impact():
            sim.state.shield = 1
            sim.state.projectiles = [Projectile("plasma", 0, 0, 0.08, 1, 10, False)]
            return ["q"]

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch("terminal_starfield.cli.Simulation", return_value=sim))
            terminal_class = stack.enter_context(mock.patch("terminal_starfield.cli.TerminalSession"))
            terminal = terminal_class.return_value.__enter__.return_value
            terminal.read_keys.side_effect = quit_before_impact
            terminal.size.return_value = (80, 24)
            stack.enter_context(mock.patch("terminal_starfield.cli.sys.stdin", FakeTTY()))
            stack.enter_context(contextlib.redirect_stdout(FakeTTY()))
            stack.enter_context(mock.patch("terminal_starfield.cli.time.monotonic",
                                           side_effect=[1.0, 1.08, 1.2]))
            self.assertEqual(run_interactive(args), 0)

        with self.subTest(effect="simulation advance"):
            self.assertEqual(sim.state.elapsed, 0)
        with self.subTest(effect="loss"):
            self.assertEqual(sim.state.screen, "playing")
            self.assertFalse(sim.state.game_over)
            self.assertEqual(sim.state.shield, 1)
        with self.subTest(effect="flight log"):
            self.assertFalse(self.path.exists())

    def test_finish_saved_once_and_restart_can_save_again(self):
        recorder = FlightRecorder(self.path)
        sim = Simulation(seed=7)
        sim.start_run("campaign")
        recorder.observe(sim.state)
        self.assertFalse(self.path.exists())
        sim.state.screen = "victory"
        sim.state.score = 200
        for _ in range(3):
            recorder.observe(sim.state)
        self.assertEqual(json.loads(self.path.read_text())["total_runs"], 1)
        self.assertEqual(sim.state.record_status, "NEW PERSONAL BEST")
        sim.restart()
        recorder.observe(sim.state)
        sim.state.screen = "game_over"
        recorder.observe(sim.state)
        self.assertEqual(json.loads(self.path.read_text())["total_runs"], 2)

    def test_disabled_or_corrupt_log_does_not_break_play(self):
        sim = Simulation(seed=7)
        sim.start_run("endless")
        sim.state.screen = "game_over"
        FlightRecorder(self.path, enabled=False).observe(sim.state)
        self.assertFalse(self.path.exists())
        self.path.write_text("broken")
        FlightRecorder(self.path).observe(sim.state)
        self.assertEqual(sim.state.record_status, "FLIGHT LOG UNAVAILABLE")
        self.assertEqual(self.path.read_text(), "broken")

    def test_snapshots_never_write_log(self):
        for screen in ("playing", "title", "upgrade", "game_over", "victory"):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--snapshot", "80x24", "--snapshot-screen", screen,
                             "--ship", "aegis", "--ascii", "--no-color",
                             "--record-file", str(self.path)])
            self.assertEqual(code, 0)
            self.assertTrue(output.getvalue().isascii())
            self.assertEqual(len(output.getvalue().splitlines()), 24)
            if screen == "game_over":
                self.assertIn("FLIGHT LINK LOST", output.getvalue())
        self.assertFalse(self.path.exists())

    def test_record_readout_without_tty(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--records", "--record-file", str(self.path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["total_runs"], 0)
