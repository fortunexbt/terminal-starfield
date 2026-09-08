import copy
import json
import unittest

from terminal_starfield.model import Enemy, SHIPS, Simulation


class FlightModelTests(unittest.TestCase):
    def test_loadouts_change_survivability_and_weapons(self):
        expected = {
            "vanguard": (100, 1.0, 0.19, 13, 3, 2, 9),
            "wraith": (70, 1.5, 0.15, 15, 2, 2, 9),
            "aegis": (150, 1.0, 0.26, 12, 4, 4, 7),
        }
        for ship_id, stats in expected.items():
            with self.subTest(ship=ship_id):
                sim = Simulation(seed=17, ship=ship_id)
                sim.start_run("campaign")
                shield, damage, cooldown, heat, missiles, pulse_damage, pulse_cooldown = stats
                self.assertEqual(sim.state.ship_id, ship_id)
                self.assertEqual((sim.state.shield, sim.state.max_shield), (shield, shield))
                self.assertEqual(sim.state.missiles, missiles)
                sim.fire_primary()
                self.assertEqual(sim.state.projectiles[0].damage, damage)
                self.assertAlmostEqual(sim.state.fire_cooldown, cooldown)
                self.assertEqual(sim.state.weapon_heat, heat)
                enemy = Enemy("frigate", 0, 0, 0.55, 10, 10, 0, 360)
                sim.state.enemies = [enemy]
                sim.trigger_pulse()
                self.assertEqual(enemy.hp, 10 - pulse_damage)
                self.assertEqual(sim.state.pulse_cooldown, pulse_cooldown)

    def test_ship_selection_is_title_only_and_invalid_ids_fail_before_reset(self):
        sim = Simulation(seed=1)
        sim.cycle_ship(1)
        self.assertEqual(sim.state.ship_id, "vanguard")
        sim.show_title()
        sim.cycle_ship(-1)
        self.assertEqual(sim.state.ship_id, "aegis")
        sim.start_run("endless")
        self.assertEqual(sim.state.max_shield, 150)
        previous = sim.state
        with self.assertRaises(ValueError):
            sim.start_run("campaign", ship="missing")
        self.assertIs(sim.state, previous)
        with self.assertRaises(ValueError):
            Simulation(ship="missing")

    def test_density_and_title_idle_do_not_change_combat_or_drafts(self):
        left = Simulation(density=40, seed=891)
        right = Simulation(density=800, seed=891)
        right.show_title()
        right.advance_time(1800)
        left.start_run("endless")
        right.start_run("endless")
        right.set_density(650)
        for _ in range(240):
            left.update(1 / 60)
            right.update(1 / 60)
        self.assertEqual(left.render_game_to_text(), right.render_game_to_text())
        left._finish_wave()
        right._finish_wave()
        self.assertEqual(left.state.upgrade_choices, right.state.upgrade_choices)

    def test_restart_replays_every_mode_and_preserves_ship_and_record_summary(self):
        for mode in ("campaign", "endless", "zen", "voyage"):
            with self.subTest(mode=mode):
                sim = Simulation(density=40, seed=404, ship="wraith")
                sim.start_run(mode)
                start_stars = copy.deepcopy(sim.state.stars)
                sim.advance_time(2400)
                first = sim.render_game_to_text()
                sim.state.record_best = 9000
                sim.state.record_runs = 3
                sim.state.record_status = "SAVED"
                sim.restart()
                self.assertEqual(sim.state.stars, start_stars)
                self.assertEqual((sim.state.seed, sim.state.ship_id), (404, "wraith"))
                self.assertEqual((sim.state.record_best, sim.state.record_runs), (9000, 3))
                self.assertEqual(sim.state.record_status, "")
                sim.advance_time(2400)
                self.assertEqual(sim.render_game_to_text(), first)

    def test_generated_seed_can_reproduce_the_initial_run(self):
        first = Simulation(density=40)
        self.assertIsInstance(first.state.seed, int)
        second = Simulation(density=40, seed=first.state.seed)
        first.advance_time(2600)
        second.advance_time(2600)
        self.assertEqual(first.state.stars, second.state.stars)
        self.assertEqual(first.render_game_to_text(), second.render_game_to_text())

    def test_all_flight_actions_are_inert_outside_active_flight(self):
        for blocked in ("paused", "help_visible", "game_over", "title", "upgrade", "dead"):
            with self.subTest(blocked=blocked):
                sim = Simulation(seed=7)
                sim.start_run("campaign")
                sim.state.enemies = [Enemy("frigate", 0, 0, 0.55, 10, 10, 0, 360)]
                if blocked in ("title", "upgrade"):
                    sim.state.screen = blocked
                elif blocked == "dead":
                    sim.state.shield = 0
                else:
                    setattr(sim.state, blocked, True)
                before = copy.deepcopy(sim.state)
                sim.fire_primary()
                sim.launch_missile()
                sim.trigger_pulse()
                sim.engage_boost()
                sim.steer(1, -1)
                sim.change_throttle(0.1)
                self.assertEqual(sim.state, before)

    def test_boss_cannot_escape_and_names_follow_sector_order(self):
        sim = Simulation(seed=16)
        sim.start_run("endless")
        names = []
        for wave in (5, 10, 15, 20, 25):
            sim.state.wave = wave
            sim._begin_wave()
            names.append(sim.state.boss_name)
        self.assertEqual(names, ["THE NULL ENGINE", "ARCHON PRIME", "VOID SERAPH", "THE NULL ENGINE", "ARCHON PRIME"])
        boss = Enemy("boss", 0, 0, 0.53, 40, 40, 0.5, 2500, fire_clock=999)
        sim.state.enemies = [boss]
        sim.state.wave_remaining = 0
        for _ in range(120):
            sim.update(1 / 60)
        self.assertIn(boss, sim.state.enemies)
        self.assertEqual(boss.z, 0.52)
        self.assertEqual(sim.state.screen, "playing")

    def test_boss_commits_aim_then_player_can_evade_the_lance(self):
        sim = Simulation(seed=9)
        sim.start_run("campaign")
        boss = Enemy("boss", 0.2, -0.1, 0.52, 90, 90, 0, 2500, fire_clock=0.72)
        sim.state.enemies = [boss]
        sim.state.wave_remaining = 0
        sim.state.heading_x, sim.state.heading_y = 0.1, 0.08
        sim._update_combat(0.03)
        self.assertTrue(boss.boss_telegraph)
        self.assertEqual((boss.aim_x, boss.aim_y), (0.1, 0.08))
        sim.state.heading_x, sim.state.heading_y = -0.3, -0.2
        for _ in range(10):
            sim._update_combat(0.07)
        self.assertFalse(boss.boss_telegraph)
        plasma = [shot for shot in sim.state.projectiles if not shot.friendly]
        self.assertEqual(len(plasma), 1)
        self.assertEqual((plasma[0].x, plasma[0].y), (0.1, 0.08))
        for _ in range(12):
            sim._update_combat(0.07)
        self.assertEqual(sim.state.shield, sim.state.max_shield)

    def test_boss_first_attack_waits_for_an_engagement_telegraph(self):
        sim = Simulation(seed=9)
        sim.start_run("campaign")
        boss = Enemy("boss", 0, 0, 1.2, 90, 90, 0, 2500, fire_clock=1.3)
        sim.state.enemies = [boss]
        sim.state.wave_remaining = 0
        for _ in range(80):
            sim._update_combat(0.05)
        self.assertFalse(sim.state.projectiles)
        self.assertFalse(boss.boss_telegraph)
        self.assertAlmostEqual(boss.fire_clock, 1.3)
        boss.z = 0.91
        for _ in range(12):
            sim._update_combat(0.05)
        self.assertTrue(boss.boss_telegraph)
        self.assertFalse(sim.state.projectiles)

    def test_committed_attack_hits_a_pilot_who_holds_the_marked_vector(self):
        for hp in (90, 60, 30):
            with self.subTest(hp=hp):
                sim = Simulation(seed=9)
                sim.start_run("campaign")
                boss = Enemy("boss", 0.2, -0.1, 0.52, hp, 90, 0, 2500)
                sim.state.enemies = [boss]
                sim.state.wave_remaining = 0
                boss.aim_x, boss.aim_y = sim.state.heading_x, sim.state.heading_y
                sim._enemy_fire(boss)
                for _ in range(15):
                    sim._update_combat(0.05)
                self.assertEqual(sim.state.shield, sim.state.max_shield - 11)

    def test_boss_phases_have_distinct_patterns_and_faster_final_cooldown(self):
        patterns = []
        cooldowns = []
        for hp, phase, attack in ((90, 1, "LANCE"), (60, 2, "FAN"), (30, 3, "CROSSFIRE")):
            sim = Simulation(seed=123)
            boss = Enemy("boss", 0.2, -0.2, 0.52, hp, 90, 0, 2500)
            boss.aim_x, boss.aim_y = 0.1, 0.05
            self.assertEqual(boss.boss_phase, phase)
            self.assertEqual(boss.boss_attack, attack)
            sim._enemy_fire(boss)
            points = {(round(shot.x, 3), round(shot.y, 3)) for shot in sim.state.projectiles}
            self.assertIn((0.1, 0.05), points)
            patterns.append(points)
            cooldowns.append(boss.fire_clock)
            self.assertFalse(boss.boss_telegraph)
        self.assertEqual(len(patterns[0]), 1)
        self.assertGreater(len(patterns[1]), 1)
        self.assertNotEqual(patterns[1], patterns[2])
        self.assertLess(cooldowns[2], cooldowns[0])
        self.assertLess(cooldowns[2], cooldowns[1])

    def test_capped_upgrades_never_appear_in_drafts(self):
        for seed in range(20):
            sim = Simulation(seed=seed)
            sim.start_run("endless")
            sim.state.upgrades = {"multishot": 2, "rapid": 5, "reactor": 6}
            sim._finish_wave()
            self.assertEqual(len(sim.state.upgrade_choices), 3)
            self.assertFalse(set(sim.state.upgrades) & set(sim.state.upgrade_choices))

    def test_each_offered_cooldown_rank_improves_every_loadout(self):
        for ship_id in SHIPS:
            with self.subTest(ship=ship_id):
                sim = Simulation(seed=5, ship=ship_id)
                sim.start_run("campaign")
                previous = float("inf")
                for rank in range(6):
                    sim.state.upgrades["rapid"] = rank
                    sim.state.fire_cooldown = 0
                    sim.state.weapon_heat = 0
                    sim.fire_primary()
                    self.assertGreater(sim.state.fire_cooldown, 0)
                    self.assertLess(sim.state.fire_cooldown, previous)
                    previous = sim.state.fire_cooldown
                previous = float("inf")
                for rank in range(7):
                    sim.state.upgrades["reactor"] = rank
                    sim.state.pulse_cooldown = 0
                    sim.state.energy = 100
                    sim.trigger_pulse()
                    self.assertEqual(sim.state.energy, 65)
                    self.assertGreater(sim.state.pulse_cooldown, 0)
                    self.assertLess(sim.state.pulse_cooldown, previous)
                    previous = sim.state.pulse_cooldown

    def test_fabricator_refills_three_per_level_without_reducing_stock(self):
        sim = Simulation(seed=5)
        sim.start_run("campaign")
        sim.state.upgrades["missiles"] = 2
        sim.state.missiles = 1
        sim._begin_wave()
        self.assertEqual(sim.state.missiles, 7)
        sim.state.missiles = 11
        sim._begin_wave()
        self.assertEqual(sim.state.missiles, 12)
        sim.state.upgrades.clear()
        sim._begin_wave()
        self.assertEqual(sim.state.missiles, 12)

    def test_text_state_exposes_ship_seed_build_and_committed_boss_attack(self):
        sim = Simulation(seed=314, ship="aegis")
        sim.start_run("campaign")
        sim.state.upgrades = {"damage": 2}
        boss = Enemy("boss", 0, 0, 0.52, 20, 90, 0, 2500)
        boss.aim_x, boss.aim_y = 0.2, -0.1
        sim.state.enemies = [boss]
        payload = json.loads(sim.render_game_to_text())
        self.assertEqual((payload["ship"], payload["seed"]), ("aegis", 314))
        self.assertEqual(payload["upgrades"], {"damage": 2})
        entry = payload["enemies"][0]
        self.assertEqual((entry["boss_phase"], entry["boss_attack"]), (3, "CROSSFIRE"))
        self.assertTrue(entry["boss_telegraph"])
        self.assertEqual((entry["aim_x"], entry["aim_y"]), (0.2, -0.1))


if __name__ == "__main__":
    unittest.main()
