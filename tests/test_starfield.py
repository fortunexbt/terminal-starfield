import unittest

from terminal_starfield.cli import handle_key, parse_size
from terminal_starfield.model import Contact, Enemy, Projectile, Simulation
from terminal_starfield.render import Renderer, strip_ansi


class SimulationTests(unittest.TestCase):
    def test_title_menu_starts_campaign(self):
        sim = Simulation(seed=3)
        sim.show_title()
        self.assertEqual(sim.state.screen, "title")
        self.assertTrue(sim.activate_menu())
        self.assertEqual(sim.state.run_mode, "campaign")
        self.assertEqual(sim.state.screen, "playing")
        self.assertEqual(sim.state.wave_remaining, 7)

    def test_primary_fire_kills_enemy_and_advances_score(self):
        sim = Simulation(seed=3)
        sim.start_run("campaign")
        sim.state.wave_remaining = 1
        enemy = Enemy("scout", 0.0, 0.0, 0.35, 1, 1, 0, 100)
        sim.state.enemies = [enemy]
        sim.fire_primary()
        sim.advance_time(180)
        self.assertNotIn(enemy, sim.state.enemies)
        self.assertEqual(sim.state.kills, 1)
        self.assertGreaterEqual(sim.state.score, 100)

    def test_wave_completion_offers_then_applies_upgrade(self):
        sim = Simulation(seed=3)
        sim.start_run("campaign")
        sim.state.wave_remaining = 0
        sim.state.enemies.clear()
        sim.state.projectiles.clear()
        sim.update(1 / 60)
        self.assertEqual(sim.state.screen, "upgrade")
        self.assertEqual(len(sim.state.upgrade_choices), 3)
        selected = sim.state.upgrade_choices[0]
        sim.choose_upgrade(0)
        self.assertEqual(sim.state.upgrades[selected], 1)
        self.assertEqual(sim.state.wave, 2)
        self.assertEqual(sim.state.screen, "playing")

    def test_text_state_contains_actionable_combat_data(self):
        sim = Simulation(seed=3)
        sim.start_run("endless")
        state_text = sim.render_game_to_text()
        self.assertIn('"coordinates"', state_text)
        self.assertIn('"mode":"endless"', state_text)
        self.assertIn('"wave":1', state_text)

    def test_missile_locks_tracks_kills_and_consumes_ammo(self):
        sim = Simulation(seed=4)
        sim.start_run("campaign")
        target = Enemy("hunter", 0.05, 0.0, 0.55, 3, 3, 0, 190)
        sim.state.enemies = [target]
        ammo = sim.state.missiles
        sim.launch_missile()
        self.assertEqual(sim.state.missiles, ammo - 1)
        self.assertTrue(any(shot.kind == "missile" for shot in sim.state.projectiles))
        sim.advance_time(600)
        self.assertNotIn(target, sim.state.enemies)

    def test_nova_pulse_scrubs_plasma_and_uses_energy(self):
        sim = Simulation(seed=4)
        sim.start_run("campaign")
        sim.state.projectiles = [Projectile("plasma", 0, 0, 0.4, 0.5, 8, False)]
        sim.trigger_pulse()
        self.assertFalse(sim.state.projectiles)
        self.assertEqual(sim.state.energy, 65)
        self.assertGreater(sim.state.pulse_cooldown, 0)

    def test_primary_weapon_overheats_and_recovers(self):
        sim = Simulation(seed=4)
        sim.start_run("campaign")
        for _ in range(8):
            sim.fire_primary()
            sim.state.fire_cooldown = 0
        self.assertTrue(sim.state.overheated)
        sim.advance_time(3000)
        self.assertFalse(sim.state.overheated)

    def test_title_keyboard_flow_selects_endless(self):
        sim = Simulation(seed=4)
        sim.show_title()
        self.assertTrue(handle_key(sim, "s"))
        self.assertEqual(sim.state.menu_index, 1)
        self.assertTrue(handle_key(sim, "\r"))
        self.assertEqual(sim.state.run_mode, "endless")

    def test_full_fifteen_wave_campaign_reaches_victory(self):
        sim = Simulation(density=40, seed=17)
        sim.start_run("campaign")
        for _ in range(60 * 300):
            state = sim.state
            if state.screen == "upgrade":
                sim.choose_upgrade(0)
            elif state.screen == "playing" and state.enemies:
                target = min(state.enemies, key=lambda enemy: enemy.z)
                state.heading_x = target.x
                state.heading_y = target.y
                sim.fire_primary()
                if target.kind in ("frigate", "boss"):
                    sim.launch_missile()
                if state.pulse_cooldown <= 0 and any(not shot.friendly and shot.z < 0.6 for shot in state.projectiles):
                    sim.trigger_pulse()
            sim.update(1 / 60)
            if sim.state.screen in ("victory", "game_over"):
                break
        self.assertEqual(sim.state.screen, "victory")
        self.assertEqual(sim.state.wave, 15)
        self.assertGreater(sim.state.kills, 200)

    def test_seed_is_deterministic(self):
        left = Simulation(seed=7)
        right = Simulation(seed=7)
        self.assertEqual(left.state.stars[0], right.state.stars[0])
        left.update(0.016)
        right.update(0.016)
        self.assertEqual(left.state.stars[0], right.state.stars[0])

    def test_density_presets_and_clamps(self):
        sim = Simulation(density=1, seed=1)
        self.assertEqual(sim.state.density, 40)
        sim.density_preset(4)
        self.assertEqual(len(sim.state.stars), 650)
        sim.set_density(9000)
        self.assertEqual(sim.state.density, 800)

    def test_signal_capture_scores_and_recharges(self):
        sim = Simulation(seed=1)
        sim.state.energy = 20
        contact = Contact("signal", sim.state.heading_x, sim.state.heading_y, z=0.1)
        sim._resolve_contact(contact)
        self.assertEqual(sim.state.captures, 1)
        self.assertEqual(sim.state.score, 100)
        self.assertGreater(sim.state.energy, 20)

    def test_debris_can_end_voyage(self):
        sim = Simulation(seed=1)
        sim.state.shield = 1
        contact = Contact("debris", sim.state.heading_x, sim.state.heading_y, z=0.1)
        sim._resolve_contact(contact)
        self.assertTrue(sim.state.game_over)
        self.assertEqual(sim.state.shield, 0)

    def test_controls_change_state(self):
        sim = Simulation(seed=1)
        heading_velocity = sim.state.velocity_y
        self.assertTrue(handle_key(sim, "w"))
        self.assertLess(sim.state.velocity_y, heading_velocity)
        throttle = sim.state.throttle
        self.assertTrue(handle_key(sim, "UP"))
        self.assertGreater(sim.state.throttle, throttle)
        self.assertTrue(handle_key(sim, " "))
        self.assertTrue(sim.state.boosting)
        self.assertFalse(handle_key(sim, "q"))


class RenderTests(unittest.TestCase):
    def test_title_and_upgrade_layers_are_visible(self):
        sim = Simulation(seed=2)
        sim.show_title()
        title = Renderer().frame(sim.state, 80, 28, color=False)
        self.assertIn("R  O  G  U  E", title)
        self.assertIn("CAMPAIGN // 15 WAVES", title)
        sim.start_run("campaign")
        sim.state.wave_remaining = 0
        sim.state.enemies.clear()
        sim.update(1 / 60)
        upgrade = Renderer().frame(sim.state, 80, 28, color=False)
        self.assertIn("WAVE CLEAR // CHOOSE ONE", upgrade)
        self.assertIn("Press 1, 2, or 3", upgrade)

    def test_combat_hud_and_enemy_are_rendered(self):
        sim = Simulation(seed=2)
        sim.start_run("campaign")
        sim.state.enemies = [Enemy("boss", 0, 0, 0.6, 20, 40, 0, 1000)]
        sim.state.boss_name = "TEST TITAN"
        frame = Renderer().frame(sim.state, 100, 30, color=False)
        self.assertIn("STARFIELD // ROGUE", frame)
        self.assertIn("TEST TITAN", frame)
        self.assertIn("THREATS", frame)
        self.assertIn("RADAR", frame)

    def test_plain_frame_has_exact_dimensions(self):
        sim = Simulation(seed=2)
        sim.update(0.016)
        frame = Renderer().frame(sim.state, 80, 24, color=False)
        lines = frame.splitlines()
        self.assertEqual(len(lines), 24)
        self.assertTrue(all(len(line) == 80 for line in lines))

    def test_ansi_frame_strips_to_exact_dimensions(self):
        sim = Simulation(seed=2)
        frame = strip_ansi(Renderer().frame(sim.state, 52, 16, color=True))
        self.assertEqual([len(line) for line in frame.splitlines()], [52] * 16)

    def test_tiny_supported_viewport_does_not_crash(self):
        sim = Simulation(seed=2)
        frame = Renderer(unicode=False).frame(sim.state, 20, 8, color=False)
        self.assertEqual(len(frame.splitlines()), 8)

    def test_snapshot_size_parser(self):
        self.assertEqual(parse_size("100x30"), (100, 30))


if __name__ == "__main__":
    unittest.main()
