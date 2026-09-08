import copy
import json
import unittest

from terminal_starfield.content import BOSS_PROFILES, ROUTES, attack_offsets
from terminal_starfield.model import Enemy, Pickup, Projectile, Simulation


class OdysseyModelTests(unittest.TestCase):
    def combat(self, seed=17):
        sim = Simulation(density=40, seed=seed)
        sim.start_run("campaign")
        sim.state.wave_remaining = 1
        sim._spawn_clock = 999
        return sim

    def step(self, sim, seconds, fps=120):
        for _ in range(round(seconds * fps)):
            sim.update(1 / fps)

    def test_swept_fast_shots_hit_at_low_and_high_frame_rates(self):
        snapshots = []
        for fps in (30, 60, 120, 240):
            sim = self.combat()
            target = Enemy("frigate", 0, 0, .44, 10, 10, 0, 360, fire_clock=999)
            sim.state.enemies = [target]
            sim.fire_primary()
            sim.state.projectiles[0].speed = 100
            self.step(sim, .1, fps)
            snapshots.append((target.hp, sim.state.shots_fired, sim.state.shots_hit))
        self.assertEqual(snapshots, [(9, 1, 1)] * 4)

    def test_piercing_hits_distinct_targets_nearest_first_only_once(self):
        sim = self.combat()
        near = Enemy("frigate", 0, 0, .30, 5, 5, 0, 360, fire_clock=999)
        far = Enemy("frigate", 0, 0, .48, 5, 5, 0, 360, fire_clock=999)
        sim.state.enemies = [far, near]
        sim.state.upgrades["pierce"] = 1
        sim.fire_primary()
        shot = sim.state.projectiles[0]
        shot.speed = 60
        sim.update(1 / 120)
        self.assertEqual((near.hp, far.hp), (4, 4))
        self.assertEqual(len(shot.hit_targets), 2)
        self.assertIs(shot.hit_targets[0], near)
        self.assertEqual(sim.state.shots_hit, 1)
        self.assertNotIn(shot, sim.state.projectiles)

    def test_slow_pierce_cannot_repeat_damage_inside_one_hull(self):
        sim = self.combat()
        target = Enemy("boss", 0, 0, .52, 100, 100, 0, 2500, fire_clock=999)
        sim.state.enemies = [target]
        sim.state.upgrades["pierce"] = 4
        sim.fire_primary()
        shot = sim.state.projectiles[0]
        shot.z, shot.speed = .51, .01
        self.step(sim, .3)
        self.assertEqual(target.hp, 99)
        self.assertEqual(len(shot.hit_targets), 1)
        self.assertEqual(shot.pierce, 3)

    def test_expired_projectile_cannot_award_a_hit(self):
        sim = self.combat()
        enemy = Enemy("scout", 0, 0, .5, 1, 1, 0, 100)
        sim.state.enemies = [enemy]
        sim.state.projectiles = [Projectile("laser", 0, 0, .5, 2.75, 10, True, ttl=0)]
        sim.update(1 / 120)
        self.assertEqual(enemy.hp, 1)
        self.assertEqual((sim.state.kills, sim.state.shots_hit), (0, 0))

    def test_projectile_lifetime_clips_sweep_before_later_collision(self):
        sim = self.combat()
        target = Enemy("frigate", 0, 0, .7, 7, 7, 0, 360, fire_clock=999)
        sim.state.enemies = [target]
        sim.fire_primary()
        shot = sim.state.projectiles[0]
        shot.speed, shot.ttl = 100, .001
        sim.update(1 / 120)
        self.assertEqual(target.hp, 7)
        self.assertFalse(sim.state.projectiles)
        self.assertEqual(sim.state.shots_hit, 0)

    def test_relative_sweep_catches_enemy_crossing_a_stationary_shot(self):
        sim = self.combat()
        target = Enemy("frigate", 0, 0, .9, 7, 7, 100, 360, fire_clock=999)
        sim.state.enemies = [target]
        sim.fire_primary()
        shot = sim.state.projectiles[0]
        shot.speed, shot.z = 0, .5
        sim.update(1 / 120)
        self.assertEqual(target.hp, 6)
        self.assertEqual(sim.state.shots_hit, 1)

    def test_equal_enemy_values_are_still_distinct_piercing_targets(self):
        sim = self.combat()
        left = Enemy("frigate", 0, 0, .3, 7, 7, 0, 360, fire_clock=999)
        right = copy.deepcopy(left)
        sim.state.enemies = [left, right]
        sim.state.upgrades["pierce"] = 1
        sim.fire_primary()
        sim.state.projectiles[0].speed = 60
        sim.update(1 / 120)
        self.assertEqual((left.hp, right.hp), (6, 6))

    def test_auto_fire_is_identical_across_frame_rates_and_keeps_thermal_limit(self):
        results = []
        for fps in (30, 60, 120):
            sim = self.combat()
            sim.state.enemies = [Enemy("boss", 0, 0, .52, 1000, 1000, 0, 2500, fire_clock=999)]
            sim.toggle_auto_fire()
            self.step(sim, 8, fps)
            results.append(sim.render_game_to_text())
            self.assertGreater(sim.state.shots_fired, 15)
            self.assertLess(sim.state.shots_fired, 8 / .19)
            self.assertEqual(sim.state.missiles, 3)
            self.assertEqual(sim.state.energy, 100)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    def test_auto_fire_needs_aligned_target_and_survives_restart(self):
        sim = self.combat()
        sim.toggle_auto_fire()
        sim.state.enemies = [Enemy("hunter", .4, .2, .6, 100, 100, 0, 190, fire_clock=999)]
        self.step(sim, .5)
        self.assertEqual(sim.state.shots_fired, 0)
        target = sim.state.enemies[0]
        sim.aim_at(target.x, target.y)
        sim.update(1 / 120)
        self.assertEqual(sim.state.shots_fired, 1)
        self.assertTrue(sim.state.target_aligned)
        sim.restart()
        self.assertTrue(sim.state.auto_fire)

    def test_fire_buffer_is_single_use_and_expires_during_cooldown(self):
        sim = self.combat()
        sim.fire_primary()
        sim.request_fire()
        self.step(sim, .22)
        self.assertEqual(sim.state.shots_fired, 2)
        self.step(sim, .4)
        self.assertEqual(sim.state.shots_fired, 2)
        sim.state.fire_cooldown = .5
        sim.request_fire()
        self.step(sim, .7)
        self.assertEqual(sim.state.shots_fired, 2)

    def test_pause_and_systems_discard_time_and_buffer_without_input_mutation(self):
        for flag in ("paused", "help_visible", "systems_visible"):
            with self.subTest(flag=flag):
                sim = self.combat()
                sim.fire_primary()
                sim.request_fire()
                setattr(sim.state, flag, True)
                before = copy.deepcopy(sim.state)
                sim.request_fire()
                sim.aim_at(.3, .2)
                sim.toggle_auto_fire()
                sim.steer(1, 1)
                self.assertEqual(sim.state, before)
                sim.update(10)
                self.assertEqual(sim.state.elapsed, 0)
                self.assertEqual(sim.state.fire_buffer, 0)
                setattr(sim.state, flag, False)
                sim.update(1 / 120)
                self.assertAlmostEqual(sim.state.elapsed, 1 / 120)
                self.assertEqual(sim.state.shots_fired, 1)

    def test_pointer_aim_is_bounded_and_keyboard_immediately_changes_vector(self):
        sim = self.combat()
        sim.steer(1, -1)
        self.assertGreater(sim.state.heading_x, 0)
        self.assertLess(sim.state.heading_y, 0)
        sim.aim_at(99, -99)
        self.assertEqual((sim.state.heading_x, sim.state.heading_y), (.48, -.31))
        self.assertEqual((sim.state.velocity_x, sim.state.velocity_y), (0, 0))
        self.step(sim, .3)
        self.assertEqual((sim.state.heading_x, sim.state.heading_y), (.48, -.31))

    def test_fixed_step_retains_fraction_and_bounds_long_caller_delay(self):
        sim = self.combat()
        sim.update(1 / 240)
        self.assertEqual(sim.state.elapsed, 0)
        sim.update(1 / 240)
        self.assertAlmostEqual(sim.state.elapsed, 1 / 120)
        sim.update(10)
        self.assertAlmostEqual(sim.state.elapsed, .25 + 1 / 120)

    def test_target_assist_lock_and_seeker_share_one_live_reference(self):
        sim = self.combat()
        distant = Enemy("frigate", .025, 0, .8, 10, 10, 0, 360)
        off_axis = Enemy("hunter", .16, 0, .4, 3, 3, 0, 190)
        sim.state.enemies = [off_axis, distant]
        sim.refresh_target()
        self.assertIs(sim.state.target, distant)
        self.assertTrue(sim.state.target_aligned)
        self.assertTrue(sim.state.target_lock)
        sim.fire_primary()
        self.assertEqual(sim.state.projectiles[0].x, distant.x)
        sim.launch_missile()
        self.assertIs(sim.state.projectiles[-1].target, distant)
        sim._destroy_enemy(distant)
        self.assertIs(sim.state.target, off_axis)
        self.assertFalse(sim.state.target_aligned)

    def test_each_boss_latches_phase_and_angle_before_health_changes(self):
        for boss_id, profile in BOSS_PROFILES.items():
            with self.subTest(boss=boss_id):
                sim = self.combat()
                boss = Enemy("boss", .1, -.1, .52, 90, 90, 0, 2500, fire_clock=.01, boss_id=boss_id)
                sim.state.enemies = [boss]
                sim._update_combat(1 / 120)
                self.assertTrue(boss.telegraph)
                self.assertEqual(boss.attack_phase, 1)
                origin = (boss.aim_x, boss.aim_y)
                angle = boss.attack_angle
                boss.hp = 10
                self.assertEqual(boss.boss_attack, profile.attacks[0])
                sim._enemy_fire(boss)
                emitted = [(shot.x - origin[0], shot.y - origin[1]) for shot in sim.state.projectiles]
                self.assertEqual(emitted, list(attack_offsets(boss_id, 1, angle)))
                self.assertFalse(boss.telegraph)
                self.assertEqual(boss.boss_attack, profile.attacks[2])

    def test_hunter_and_frigate_commit_full_warning_then_emit_exact_lanes(self):
        for kind, lanes in (("hunter", 1), ("frigate", 3)):
            with self.subTest(kind=kind):
                sim = self.combat()
                enemy = Enemy(kind, .2, .1, .7, 10, 10, 0, 100, fire_clock=-3)
                sim.state.enemies = [enemy]
                sim._update_combat(1 / 120)
                self.assertTrue(enemy.telegraph)
                self.assertFalse(sim.state.projectiles)
                self.assertGreaterEqual(enemy.fire_clock, .55)
                sim.aim_at(-.2, -.1)
                self.step(sim, .5)
                self.assertFalse(sim.state.projectiles)
                self.step(sim, .1)
                shots = [shot for shot in sim.state.projectiles if not shot.friendly]
                self.assertEqual(len(shots), lanes)
                self.assertTrue(all(shot.y == 0 for shot in shots))

    def test_ordinary_encounter_labels_match_their_initial_contact(self):
        for wave, kind in ((1, "scout"), (3, "frigate"), (6, "scout"), (8, "frigate")):
            sim = self.combat()
            sim.state.wave = wave
            sim._begin_wave()
            sim._spawn_enemy()
            self.assertEqual(sim.state.enemies[0].kind, kind)

    def test_close_shooter_cannot_spawn_instant_plasma(self):
        sim = self.combat()
        enemy = Enemy("hunter", 0, 0, .1, 3, 3, 0, 190, fire_clock=-10)
        sim.state.enemies = [enemy]
        sim.update(1 / 120)
        self.assertFalse(sim.state.projectiles)
        self.assertFalse(enemy.telegraph)

    def test_boss_profiles_change_identity_and_recovery_by_sector(self):
        identities = []
        rhythms = []
        for wave in (5, 10, 15, 20):
            sim = self.combat()
            sim.state.run_mode = "endless"
            sim.state.wave = wave
            sim._begin_wave()
            sim._spawn_enemy()
            boss = sim.state.enemies[0]
            identities.append(boss.boss_id)
            boss.aim_x = boss.aim_y = 0
            boss.attack_phase = 1
            sim._enemy_fire(boss)
            rhythms.append(boss.fire_clock)
        self.assertEqual(identities, ["null_engine", "archon_prime", "void_seraph", "null_engine"])
        self.assertEqual(len(set(rhythms[:3])), 3)

    def test_bosses_arrive_in_engagement_range_with_sector_scaled_hulls(self):
        for wave, hp in ((5, 220), (10, 420), (15, 540)):
            with self.subTest(wave=wave):
                sim = self.combat()
                sim.state.wave = wave
                sim._begin_wave()
                sim._spawn_enemy()
                boss = sim.state.enemies[0]
                self.assertEqual((boss.hp, boss.max_hp), (hp, hp))
                self.assertGreaterEqual(boss.z, .82)
                self.assertLessEqual(boss.z, .9)
                self.assertFalse(boss.telegraph)
                self.assertFalse(sim.state.projectiles)
                self.assertGreaterEqual(boss.fire_clock, 1.3)

    def test_refit_services_charge_only_for_useful_effects_and_bound_stock(self):
        sim = self.combat()
        sim.state.credits = 100
        self.assertFalse(sim.buy_service("repair"))
        sim._finish_wave()
        self.assertFalse(sim.buy_service("repair"))
        self.assertEqual(sim.state.credits, 100)
        sim.state.shield = sim.state.max_shield - 5
        self.assertTrue(sim.buy_service("repair"))
        self.assertEqual((sim.state.shield, sim.state.credits), (sim.state.max_shield, 88))
        sim.state.missiles = 11
        self.assertTrue(sim.buy_service("missiles"))
        self.assertEqual((sim.state.missiles, sim.state.credits), (12, 78))
        self.assertFalse(sim.buy_service("missiles"))
        self.assertFalse(sim.buy_service("missing"))
        sim.state.credits = 0
        sim.state.shield = 1
        self.assertFalse(sim.buy_service("repair"))
        self.assertEqual(sim.state.shield, 1)

    def test_paid_rerolls_change_draft_and_stop_after_two(self):
        sim = self.combat()
        sim.state.credits = 100
        sim._finish_wave()
        old = set(sim.state.upgrade_choices)
        self.assertTrue(sim.buy_service("reroll"))
        self.assertNotEqual(set(sim.state.upgrade_choices), old)
        self.assertEqual(sim.state.credits, 92)
        old = set(sim.state.upgrade_choices)
        self.assertTrue(sim.buy_service("reroll"))
        self.assertNotEqual(set(sim.state.upgrade_choices), old)
        self.assertEqual(sim.state.credits, 76)
        self.assertFalse(sim.buy_service("reroll"))
        sim.choose_upgrade(0)
        self.assertEqual(sim.state.refit_rerolls, 0)

    def test_wave_clear_banks_all_pickups_once_including_final_boss_drop(self):
        for wave, screen in ((1, "upgrade"), (15, "victory")):
            with self.subTest(wave=wave):
                sim = self.combat()
                sim.state.wave = wave
                sim.state.wave_remaining = 0
                sim.state.shield = 30
                sim.state.energy = 20
                sim.state.missiles = 0
                sim.state.pickups = [Pickup(kind, .4, .2, 1.2) for kind in ("repair", "energy", "missile", "credits")]
                sim.update(1 / 120)
                self.assertEqual(sim.state.screen, screen)
                self.assertFalse(sim.state.pickups)
                self.assertGreaterEqual(sim.state.shield, 58)
                self.assertGreaterEqual(sim.state.energy, 55)
                self.assertEqual((sim.state.missiles, sim.state.credits, sim.state.score), (2, 10, 250))
                previous = (sim.state.shield, sim.state.energy, sim.state.missiles, sim.state.credits, sim.state.score)
                sim.update(.2)
                self.assertEqual(previous, (sim.state.shield, sim.state.energy, sim.state.missiles, sim.state.credits, sim.state.score))

    def test_actual_final_boss_drop_is_banked_before_victory(self):
        sim = self.combat(seed=23)
        sim.state.wave = 15
        sim.state.wave_remaining = 0
        sim.state.enemies = [Enemy("boss", 0, 0, .52, 1, 64, 0, 2500, fire_clock=999, boss_id="void_seraph")]
        sim.fire_primary()
        self.step(sim, .3)
        self.assertEqual(sim.state.screen, "victory")
        self.assertEqual((sim.state.kills, sim.state.bosses_defeated), (1, 1))
        self.assertFalse(sim.state.pickups)
        # Seed 23 chooses a credit cache for this guaranteed boss drop.
        self.assertEqual((sim.state.credits, sim.state.score), (60, 2750))

    def test_route_screen_then_jump_defers_spawn_and_applies_catalog_modifiers(self):
        sim = self.combat()
        sim.state.wave = 5
        sim._finish_wave()
        sim.choose_upgrade(0)
        self.assertEqual((sim.state.screen, sim.state.wave, sim.state.paused), ("route", 6, True))
        self.assertEqual(sim.state.route_choices, ["forge", "veil", "graveyard"])
        sim.choose_route(0)
        self.assertEqual((sim.state.screen, sim.state.route_id, sim.state.paused), ("jump", "forge", False))
        self.assertEqual(sim.state.route_history, ["frontier", "forge"])
        sim.request_fire()
        sim.aim_at(.3, .2)
        self.step(sim, 1.3)
        self.assertEqual(sim.state.screen, "jump")
        self.assertFalse(sim.state.enemies)
        self.assertEqual(sim.state.shots_fired, 0)
        self.step(sim, .1)
        self.assertEqual(sim.state.screen, "playing")
        self.assertEqual(sim.state.refit_rerolls, 0)
        sim.fire_primary()
        self.assertEqual(sim.state.weapon_heat, 13 * ROUTES["forge"].heat_scale)

    def test_routes_only_follow_boss_upgrades_and_invalid_selection_is_inert(self):
        sim = self.combat()
        before = copy.deepcopy(sim.state)
        sim.choose_route(0)
        self.assertEqual(sim.state, before)
        for mode, wave in (("campaign", 10), ("endless", 15), ("endless", 20)):
            sim.start_run(mode)
            sim.state.wave = wave
            sim._finish_wave()
            sim.choose_upgrade(0)
            self.assertEqual(sim.state.screen, "route")
            before = copy.deepcopy(sim.state)
            sim.choose_route(-1)
            sim.choose_route(3)
            sim.engage_boost()
            sim.steer(1, 1)
            sim.request_fire()
            sim.aim_at(.3, .3)
            self.assertEqual(sim.state, before)

    def test_route_salvage_hp_plasma_and_repairs_are_real_effects(self):
        sim = self.combat()
        sim.state.route_id = "forge"
        target = Enemy("scout", 0, 0, .6, 1, 1, 0, 100)
        sim.state.enemies = [target]
        sim._destroy_enemy(target)
        self.assertEqual((sim.state.score, sim.state.credits), (160, 3))
        sim.state.route_id = "graveyard"
        sim.state.wave = 5
        sim._spawn_enemy()
        self.assertEqual(sim.state.enemies[-1].max_hp, 220 * 1.25)
        sim.state.pickups.clear()
        sim.state.shield = 20
        sim._finish_wave()
        self.assertEqual(sim.state.shield, 44)
        sim.state.route_id = "veil"
        boss = sim.state.enemies[-1]
        boss.aim_x = boss.aim_y = 0
        boss.attack_phase = 1
        sim._enemy_fire(boss)
        self.assertEqual(sim.state.projectiles[-1].speed, .62 * 1.25)

    def test_leech_echo_and_graze_have_separate_mechanics(self):
        sim = self.combat()
        sim.state.shield = 50
        sim.state.upgrades["leech"] = 2
        target = Enemy("hunter", 0, 0, .5, 3, 3, 0, 190)
        sim.state.enemies = [target]
        sim._destroy_enemy(target)
        self.assertEqual(sim.state.shield, 54)

        sim.state.upgrades["echo"] = 1
        sim.state.missiles = 0
        sim.trigger_pulse()
        self.assertEqual(sim.state.missiles, 1)
        sim.state.energy = 30
        sim.state.upgrades["graze"] = 2
        sim.state.projectiles = [Projectile("plasma", .025, 0, .076, 1, 8, False)]
        sim.update(1 / 120)
        self.assertEqual(sim.state.grazes, 1)
        self.assertAlmostEqual(sim.state.energy, 46.0625)
        self.assertEqual(sim.state.shield, 54)

    def test_graze_scores_once_and_damage_stats_count_actual_shield_lost(self):
        sim = self.combat()
        sim.state.projectiles = [Projectile("plasma", .025, 0, .08, 1, 8, False)]
        self.step(sim, .2)
        self.assertEqual((sim.state.grazes, sim.state.score), (1, 25))
        self.assertEqual(sim.state.damage_taken, 0)
        sim.state.shield = 5
        sim._damage_player(20, "TEST")
        sim._damage_player(20, "TEST")
        self.assertEqual(sim.state.damage_taken, 5)
        self.assertEqual(sim.state.screen, "game_over")

    def test_seeker_cascade_damages_neighbors_without_recursive_arcs(self):
        sim = self.combat()
        sim.state.upgrades["cascade"] = 2
        struck = Enemy("frigate", 0, 0, .4, 5, 5, 0, 360, fire_clock=999)
        neighbor = Enemy("hunter", .1, 0, .4, 3, 3, 0, 190, fire_clock=999)
        beyond = Enemy("frigate", .25, 0, .4, 7, 7, 0, 360, fire_clock=999)
        sim.state.enemies = [struck, neighbor, beyond]
        sim.launch_missile()
        self.step(sim, .3)
        self.assertNotIn(struck, sim.state.enemies)
        self.assertNotIn(neighbor, sim.state.enemies)
        self.assertEqual(beyond.hp, 7)
        self.assertEqual((sim.state.kills, sim.state.shots_hit), (2, 1))

    def test_snapshot_exposes_route_weapons_services_targets_and_run_stats(self):
        sim = self.combat()
        sim._finish_wave()
        sim.state.credits = 20
        payload = json.loads(sim.render_game_to_text())
        self.assertEqual(payload["route"], "frontier")
        self.assertEqual(payload["route_history"], ["frontier"])
        self.assertEqual(payload["services"]["reroll"], {"cost": 8, "available": True})
        self.assertEqual(payload["run_stats"]["shots_fired"], 0)
        self.assertFalse(payload["target"]["aligned"])
        self.assertFalse(payload["weapons"]["auto_fire"])


if __name__ == "__main__":
    unittest.main()
