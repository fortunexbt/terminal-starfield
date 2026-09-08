"""Odyssey art and the readable contracts that must survive small terminals."""

import unittest
from unittest.mock import patch

from terminal_starfield.content import BOSS_PROFILES, ROUTES, ROUTE_CHOICES, attack_offsets
from terminal_starfield.graphics import VectorInk, draw_ship, draw_world
from terminal_starfield.model import Enemy, Simulation
from terminal_starfield.render import Canvas, Renderer, THEMES, project, strip_ansi


class OdysseyRenderTests(unittest.TestCase):
    def state(self):
        sim = Simulation(seed=731)
        sim.start_run("campaign")
        sim.state.messages.clear()
        sim.state.upgrade_choices = ["damage", "multishot", "shield"]
        sim.state.route_choices = list(ROUTE_CHOICES)
        return sim.state

    def test_odyssey_surfaces_fit_exactly_and_ascii_is_complete(self):
        state = self.state()
        for size in ((20, 8), (40, 12), (80, 24), (100, 34)):
            for screen in ("playing", "route", "jump", "upgrade", "systems", "game_over", "victory"):
                state.screen = "playing" if screen == "systems" else screen
                state.systems_visible = screen == "systems"
                for unicode in (True, False):
                    with self.subTest(size=size, screen=screen, unicode=unicode):
                        frame = Renderer(unicode).frame(state, *size)
                        self.assertEqual([len(row) for row in strip_ansi(frame).splitlines()], [size[0]] * size[1])
                        if not unicode:
                            self.assertTrue(frame.isascii())

    def test_tiny_route_and_refit_keep_actions_visible(self):
        state = self.state()
        state.screen = "route"
        route = Renderer(False).frame(state, 20, 8, False)
        for index, key in enumerate(ROUTE_CHOICES, 1):
            self.assertIn("[{}] {}".format(index, ROUTES[key].name), route)
        state.screen = "upgrade"
        refit = Renderer(False).frame(state, 20, 8, False)
        for label in ("[1] PHOTON LENS", "[2] SPLIT ARRAY", "[3] AEGIS PLATING", "4 SHD$12", "5 M$10", "6 REROLL $8", "INSTALL"):
            self.assertIn(label, refit)

    def test_reroll_price_and_unavailable_services_are_truthful(self):
        state = self.state()
        state.screen = "upgrade"
        state.credits = 100
        state.refit_rerolls = 1
        state.missiles = 12
        rows = Renderer()._service_rows(state)
        self.assertEqual([(row[2], row[3]) for row in rows], [(12, False), (10, False), (16, True)])
        state.refit_rerolls = 2
        self.assertEqual(Renderer()._service_rows(state)[2][2:], (32, False))
        text = Renderer(False).frame(state, 80, 24, False)
        self.assertIn("$32", text)
        self.assertEqual(text.count("UNAVAILABLE"), 3)

    def test_every_committed_boss_impact_is_marked_at_collision_plane(self):
        state = self.state()
        state.heading_x, state.heading_y = .013, -.007
        renderer = Renderer(False)
        for boss_id in BOSS_PROFILES:
            for phase in (1, 2, 3):
                with self.subTest(boss=boss_id, phase=phase):
                    boss = Enemy("boss", .1, -.1, .6, 1, 40, 0, 1000,
                                 aim_x=.008, aim_y=-.003, boss_id=boss_id,
                                 attack_phase=phase, attack_angle=.38)
                    state.enemies = [boss]
                    canvas = Canvas(120, 40, False)
                    renderer._boss_warning(canvas, state, THEMES[0], 4, 37, False)
                    expected = set()
                    for dx, dy in attack_offsets(boss_id, phase, .38):
                        x, y, _, _ = project(state, boss.aim_x + dx, boss.aim_y + dy, .075, 120, 4, 37)
                        if 0 <= x < 120 and 4 <= y <= 37:
                            expected.add((x, y))
                    marked = {(x, y) for y, row in enumerate(canvas.rows) for x, cell in enumerate(row) if cell.char == "!"}
                    self.assertEqual(marked, expected)
                    self.assertIn("P{} ".format(phase), canvas.render(False))

    def test_frigate_warns_all_three_lanes_and_steering_moves_them(self):
        state = self.state()
        state.enemies = [Enemy("frigate", .1, 0, .6, 6, 6, 0, 100, aim_x=0, aim_y=0)]
        positions = []
        for heading in (0, .015):
            state.heading_x = heading
            canvas = Canvas(100, 30, False)
            Renderer(False)._boss_warning(canvas, state, THEMES[0], 4, 27, False)
            positions.append([x for row in canvas.rows for x, cell in enumerate(row) if cell.char == "!"])
        self.assertEqual(len(positions[0]), 3)
        self.assertTrue(all(after < before for before, after in zip(*positions)))

    def test_route_worlds_and_flagships_have_distinct_authored_geometry(self):
        state = self.state()
        worlds, ships = [], []
        for route in ROUTES.values():
            canvas = Canvas(100, 34)
            draw_world(canvas, state, route, 4, 31)
            worlds.append(canvas.render(False))
        for profile in BOSS_PROFILES.values():
            canvas = Canvas(80, 24)
            enemy = Enemy("boss", 0, 0, .5, 40, 40, 0, 1000, boss_id=profile.id)
            draw_ship(canvas, enemy, 40, 12, 30, (200, 100, 100), profile.shape, 3, 20)
            ships.append(canvas.render(False))
        self.assertEqual(len(set(worlds)), 4)
        self.assertEqual(len(set(ships)), 3)
        self.assertTrue(all(sum(not char.isspace() for char in frame) > 50 for frame in ships))

    def test_subcell_lines_merge_and_have_a_native_ascii_fallback(self):
        for unicode in (True, False):
            canvas = Canvas(10, 5, unicode)
            ink = VectorInk(canvas, (100, 200, 255))
            ink.line((1, 1), (8, 3))
            ink.line((1, 3), (8, 1))
            ink.flush()
            frame = canvas.render(False)
            self.assertGreater(sum(not char.isspace() for char in frame), 10)
            self.assertNotIn("?", frame)
            self.assertEqual(frame.isascii(), not unicode)

    def test_hull_faces_mask_background_but_preserve_aim_and_warnings(self):
        for kind, shape in (("boss", "engine"), ("boss", "citadel"), ("boss", "seraph"), ("frigate", "frigate")):
            for unicode in (True, False):
                with self.subTest(kind=kind, shape=shape, unicode=unicode):
                    canvas = Canvas(80, 24, unicode)
                    for y in range(24):
                        canvas.text(0, y, "." * 80, (40, 60, 80), priority=2)
                    canvas.put(40, 12, "!", (255, 200, 80), priority=79)
                    canvas.put(37, 12, "[", (80, 200, 255), priority=59)
                    enemy = Enemy(kind, 0, 0, .5, 40, 40, 0, 1000)
                    draw_ship(canvas, enemy, 40, 12, 32, (255, 90, 110), shape, 3, 20)
                    face_cells = [(x, y, cell) for y, row in enumerate(canvas.rows)
                                  for x, cell in enumerate(row) if cell.priority == 53]
                    self.assertGreater(len(face_cells), 15)
                    self.assertLess(len(face_cells), 250)
                    self.assertGreater(len({cell.color for _, _, cell in face_cells}), 1)
                    self.assertTrue(all(20 <= x <= 60 and 3 <= y <= 20 for x, y, _ in face_cells))
                    self.assertEqual(canvas.rows[12][40].char, "!")
                    self.assertEqual(canvas.rows[12][37].char, "[")
                    if not unicode:
                        self.assertTrue(canvas.render(False).isascii())

    def test_fullscreen_compact_overlays_skip_unseen_world(self):
        state = self.state()
        renderer = Renderer()
        with patch.object(renderer, "_stars", side_effect=AssertionError("unseen background")):
            for screen in ("title", "upgrade", "game_over", "route", "jump"):
                state.screen = screen
                renderer.frame(state, 20, 8)
            state.screen, state.systems_visible = "playing", True
            renderer.frame(state, 100, 34)

    def test_systems_and_debrief_expose_actual_build_and_run_stats(self):
        state = self.state()
        state.systems_visible = True
        state.upgrades = {"damage": 2, "rapid": 1, "coolant": 1}
        state.route_id = "forge"
        systems = Renderer(False).frame(state, 100, 34, False)
        self.assertIn("PHOTON 3 dmg / 0.156s / 12.7 heat", systems)
        self.assertIn("PHOTON LENS MK 2", systems)
        self.assertIn("+25% weapon heat", systems)
        state.systems_visible = False
        state.screen = "victory"
        state.shots_fired, state.shots_hit = 10, 7
        state.grazes, state.bosses_defeated = 12, 3
        state.route_history = ["frontier", "forge", "veil"]
        state.record_status = "NOT RECORDED"
        debrief = Renderer(False).frame(state, 100, 34, False)
        for label in ("ACCURACY 70%", "GRAZES 12", "BOSSES 3", "PALE MERIDIAN", "EMBER FORGE", "ION VEIL", "SEED  731", "PHOTON LENS MK 2", "NOT RECORDED"):
            self.assertIn(label, debrief)


if __name__ == "__main__":
    unittest.main()
