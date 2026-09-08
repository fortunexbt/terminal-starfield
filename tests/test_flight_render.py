"""Readable flight surfaces at real terminal sizes."""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from terminal_starfield.model import Enemy, SHIPS, Simulation
from terminal_starfield.render import Renderer, strip_ansi


class FlightRenderTests(unittest.TestCase):
    def test_voyage_loss_preserves_signals_distance_and_unrecorded_status(self):
        from terminal_starfield.cli import FlightRecorder
        from terminal_starfield.model import Contact

        sim = Simulation(seed=731)
        sim.start_run("voyage")
        sim.state.distance = 1234
        sim.state.shield = 1
        sim.state.contacts = [Contact("signal", 0, 0, .09), Contact("debris", 0, 0, .09)]
        sim.update(1 / 60)
        self.assertEqual(sim.state.screen, "game_over")
        self.assertEqual(sim.state.captures, 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "log.json"
            FlightRecorder(path, enabled=False).observe(sim.state)
            for width, height in ((20, 8), (40, 12), (80, 24)):
                with self.subTest(size=(width, height)):
                    frame = Renderer(unicode=False).frame(sim.state, width, height, color=False)
                    self.assertIn("SIGNALS 1", frame)
                    self.assertIn("1234.8 AU", frame)
                    self.assertIn("CHAIN 1", frame)
                    self.assertIn("NOT RECORDED", frame)
                    self.assertNotIn("PENDING", frame)
                    self.assertNotIn("KILLS", frame)
                    self.assertNotIn("BUILD", frame)
                    self.assertEqual([len(row) for row in frame.splitlines()], [width] * height)
            self.assertFalse(path.exists())

    def test_small_title_keeps_every_selected_mode_visible(self):
        sim = Simulation(seed=13)
        sim.show_title()
        for index, name in enumerate(("CAMPAIGN", "ENDLESS", "ZEN DRIFT", "QUIT")):
            with self.subTest(mode=name):
                sim.state.menu_index = index
                frame = Renderer(unicode=False).frame(sim.state, 20, 8, color=False)
                self.assertTrue(any(line.lstrip().startswith("> " + name) for line in frame.splitlines()), frame)

    def test_small_upgrade_exposes_all_three_choices(self):
        sim = Simulation(seed=13)
        sim.start_run("campaign")
        sim.state.screen = "upgrade"
        sim.state.upgrade_choices = ["damage", "multishot", "shield"]
        frame = Renderer(unicode=False).frame(sim.state, 20, 8, color=False)
        for index, name in enumerate(("PHOTON LENS", "SPLIT ARRAY", "AEGIS PLATING"), 1):
            self.assertIn("[{}] {}".format(index, name), frame)

    def test_small_manual_preserves_flight_controls_and_close_action(self):
        sim = Simulation(seed=13)
        sim.start_run("campaign")
        sim.state.help_visible = True
        frame = Renderer(unicode=False).frame(sim.state, 20, 8, color=False)
        for value in ("WASD steer", "ARROWS throttle", "SPACE/M fire/seeker", "E/B pulse/boost", "H close"):
            self.assertIn(value, frame)

    def test_ascii_covers_entire_frame_including_modal_and_manual(self):
        sim = Simulation(seed=13)
        sim.start_run("campaign")
        sim.state.upgrade_choices = ["damage", "multishot", "shield"]
        for screen in ("playing", "title", "upgrade", "game_over", "victory", "help", "paused"):
            with self.subTest(screen=screen):
                sim.state.screen = "playing" if screen in ("help", "paused") else screen
                sim.state.help_visible = screen == "help"
                sim.state.paused = screen == "paused"
                sim.state.game_over = screen == "game_over"
                frame = Renderer(unicode=False).frame(sim.state, 100, 32, color=False)
                self.assertTrue(frame.isascii(), "Non-ASCII characters: {!r}".format(set(c for c in frame if not c.isascii())))

    def test_all_surfaces_preserve_terminal_geometry(self):
        sim = Simulation(seed=13)
        sim.start_run("campaign")
        sim.state.upgrade_choices = ["rapid", "reactor", "missiles"]
        sim.state.upgrades = dict.fromkeys(Simulation.UPGRADE_INFO, 2)
        for width, height in ((20, 8), (40, 12), (52, 18), (80, 24), (100, 34)):
            for screen in ("playing", "title", "upgrade", "game_over", "victory", "help", "paused"):
                for unicode in (True, False):
                    with self.subTest(size=(width, height), screen=screen, unicode=unicode):
                        sim.state.screen = "playing" if screen in ("help", "paused") else screen
                        sim.state.help_visible = screen == "help"
                        sim.state.paused = screen == "paused"
                        sim.state.game_over = screen == "game_over"
                        frame = Renderer(unicode=unicode).frame(sim.state, width, height, color=True)
                        lines = strip_ansi(frame).splitlines()
                        self.assertEqual([len(line) for line in lines], [width] * height)
                        if not unicode:
                            self.assertTrue(frame.isascii())

    def test_flight_deck_exposes_actual_ship_tradeoffs_and_records(self):
        frames = []
        for ship_id, ship in SHIPS.items():
            sim = Simulation(seed=731, ship=ship_id)
            sim.show_title()
            sim.state.record_best = 17840
            sim.state.record_runs = 7
            frame = Renderer(unicode=False).frame(sim.state, 80, 24, color=False)
            for value in (ship.name.upper(), ship.role.upper(), ship.description,
                          "SHIELD {:g}".format(ship.max_shield),
                          "PHOTON {:g}/{:g}s".format(ship.primary_damage, ship.primary_cooldown),
                          "NOVA {:g}/{:g}s".format(ship.pulse_damage, ship.pulse_cooldown),
                          "SEEKERS {}".format(ship.missiles), "SEED 731", "BEST 17,840", "7 FLIGHTS"):
                self.assertIn(value, frame)
            for mode in Simulation.MENU_ITEMS:
                self.assertIn(mode, frame)
            frames.append(frame.splitlines()[8:16])
        self.assertNotEqual(frames[0], frames[1])
        self.assertNotEqual(frames[1], frames[2])

    def test_upgrade_copy_and_debrief_share_model_catalog(self):
        sim = Simulation(seed=731, ship="wraith")
        sim.start_run("endless")
        sim.state.upgrade_choices = ["damage", "reactor", "missiles"]
        sim.state.upgrades = {"damage": 2}
        with patch.dict(Simulation.UPGRADE_INFO, {"damage": ("EXPERIMENTAL LENS", "catalog source description")}):
            sim.state.screen = "upgrade"
            upgrade = Renderer().frame(sim.state, 80, 24, color=False)
            self.assertIn("EXPERIMENTAL LENS", upgrade)
            self.assertIn("catalog source description", upgrade)
            sim.state.screen = "game_over"
            debrief = Renderer().frame(sim.state, 80, 24, color=False)
            self.assertIn("EXPERIMENTAL LENS MK 2", debrief)

    def test_debrief_carries_replay_identity_stats_build_and_records(self):
        sim = Simulation(seed=731, ship="aegis")
        sim.start_run("campaign")
        sim.state.score = 17840
        sim.state.kills = 152
        sim.state.wave = 15
        sim.state.best_combo = 32
        sim.state.upgrades = {"damage": 4, "multishot": 2}
        sim.state.record_best = 17840
        sim.state.record_runs = 8
        sim.state.record_status = "NEW PERSONAL BEST"
        for screen in ("victory", "game_over"):
            sim.state.screen = screen
            frame = Renderer().frame(sim.state, 80, 24, color=False)
            for value in ("FLIGHT DEBRIEF", "CAMPAIGN", "AEGIS", "SEED  731", "SCORE 17,840",
                          "KILLS 0152", "WAVE 15", "BEST CHAIN 32", "PHOTON LENS MK 4", "SPLIT ARRAY MK 2",
                          "PERSONAL BEST 17,840", "8 RECORDED FLIGHTS", "NEW PERSONAL BEST", "R replay same seed",
                          "ESC flight deck", "Q exit"):
                self.assertIn(value, frame)
            self.assertNotIn("SPACE fire", frame)

    def test_boss_warning_follows_committed_aim_when_pilot_steers(self):
        sim = Simulation(seed=13)
        sim.start_run("campaign")
        sim.state.messages.clear()
        boss = Enemy("boss", 0, 0, .52, 10, 40, 0, 1000, aim_x=0, aim_y=0)
        sim.state.enemies = [boss]
        sim.state.boss_name = "TEST TITAN"
        renderer = Renderer(unicode=False)
        before = renderer.frame(sim.state, 100, 30, color=False)
        self.assertIn("TEST TITAN", before)
        self.assertIn("P3 CROSSFIRE", before)
        self.assertIn("AIM LOCKED // EVADE", before)
        before_column = next(line.index("[ ! ]") for line in before.splitlines() if "[ ! ]" in line)
        sim.state.heading_x = .02
        after = renderer.frame(sim.state, 100, 30, color=False)
        after_column = next(line.index("[ ! ]") for line in after.splitlines() if "[ ! ]" in line)
        self.assertLess(after_column, before_column)
        self.assertEqual((boss.aim_x, boss.aim_y), (0, 0))
        compact = renderer.frame(sim.state, 20, 8, color=False)
        self.assertIn("LOCK P3 CROSSFIRE", compact)
        boss.aim_x = boss.aim_y = None
        clear = renderer.frame(sim.state, 100, 30, color=False)
        self.assertNotIn("[ ! ]", clear)
        self.assertNotIn("AIM LOCKED", clear)


if __name__ == "__main__":
    unittest.main()
