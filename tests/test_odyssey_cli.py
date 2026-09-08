"""Terminal input and discoverable Odyssey controls."""

import io
import unittest
from contextlib import redirect_stdout

from terminal_starfield.cli import KeyDecoder, build_parser, handle_key, main
from terminal_starfield.model import Simulation


class MouseInputTests(unittest.TestCase):
    def test_fragmented_mouse_event_preserves_following_arrow(self):
        decoder = KeyDecoder()
        self.assertEqual(decoder.feed(b"\x1b[<35;50", now=1), [])
        events = decoder.feed(b";15M\x1b[A", now=1.01)
        self.assertEqual(len(events), 2)
        self.assertEqual((events[0].button, events[0].x, events[0].y), (35, 50, 15))
        self.assertEqual(events[1], "UP")

    def test_click_release_and_wheel_are_distinct(self):
        events = KeyDecoder().feed(b"\x1b[<0;20;12M\x1b[<0;20;12m\x1b[<64;20;12M")
        self.assertEqual(len(events), 3)
        self.assertFalse(events[0].released)
        self.assertTrue(events[1].released)
        self.assertEqual(events[2].button, 64)

    def test_invalid_mouse_packets_are_ignored_without_losing_keys(self):
        events = KeyDecoder().feed(b"\x1b[<0;0;12M\x1b[<999;20;12M\x1b[<0;999999;12Mq")
        self.assertEqual(events, ["q"])

    def test_incomplete_escape_has_a_bounded_buffer(self):
        decoder = KeyDecoder()
        decoder.feed(b"\x1b[" + b"1" * 10000, now=1)
        self.assertLessEqual(len(decoder.pending), 64)


class OdysseyControlTests(unittest.TestCase):
    def test_new_options_are_available(self):
        args = build_parser().parse_args(["--auto-fire", "--mouse", "--demo"])
        self.assertTrue(args.auto_fire and args.mouse and args.demo)

    def test_systems_overlay_blocks_flight_until_closed(self):
        sim = Simulation(seed=3)
        sim.start_run("campaign")
        handle_key(sim, "i")
        self.assertTrue(sim.state.systems_visible)
        handle_key(sim, "w")
        handle_key(sim, " ")
        self.assertEqual(sim.state.heading_y, 0)
        self.assertFalse(sim.state.projectiles)
        handle_key(sim, "ESC")
        self.assertFalse(sim.state.systems_visible)
        handle_key(sim, "f")
        self.assertTrue(sim.state.auto_fire)

    def test_snapshot_screens_render_without_terminal_or_records(self):
        for screen in ("route", "jump", "boss", "systems"):
            with self.subTest(screen=screen), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--snapshot", "80x24", "--snapshot-screen", screen,
                                       "--ascii", "--no-color", "--no-record"]), 0)
                self.assertTrue(output.getvalue().isascii())
                self.assertEqual(len(output.getvalue().splitlines()), 24)
