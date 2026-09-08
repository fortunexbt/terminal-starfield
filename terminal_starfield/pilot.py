"""An attract-mode pilot using the same actions available to a player."""

from __future__ import annotations

import math

from .model import Simulation, clamp


class DemoPilot:
    """Reads threats and issues bounded steering/weapon inputs at 20 Hz."""

    def __init__(self) -> None:
        self.clock = 0.0
        self.result_time = 0.0
        self.dodge_side = 1.0

    def update(self, simulation: Simulation, dt: float) -> None:
        state = simulation.state
        state.demo = True
        if state.screen in ("victory", "game_over"):
            self.result_time += dt
            if self.result_time >= 4:
                simulation.restart()
                self.result_time = 0.0
            return
        self.result_time = 0.0
        if state.screen == "upgrade":
            if state.shield < state.max_shield * .85:
                simulation.buy_service("repair")
            if state.missiles < 5:
                simulation.buy_service("missiles")
            priorities = ("damage", "multishot", "leech", "coolant", "echo", "cascade", "rapid", "shield", "graze", "reactor", "missiles", "pierce", "score")
            selection = min(range(len(state.upgrade_choices)),
                            key=lambda i: priorities.index(state.upgrade_choices[i]))
            simulation.choose_upgrade(selection)
            return
        if state.screen == "route":
            index = state.route_choices.index("graveyard") if "graveyard" in state.route_choices else 0
            simulation.choose_route(index)
            return
        if state.screen != "playing":
            return
        self.clock += dt
        if self.clock < .05:
            return
        self.clock %= .05
        if not state.auto_fire:
            simulation.toggle_auto_fire()
        if not state.enemies:
            simulation.steer(-state.heading_x * .2, -state.heading_y * .2)
            return
        target = min(state.enemies, key=lambda enemy: enemy.z)
        desired_x, desired_y = target.x, target.y
        danger = [shot for shot in state.projectiles if not shot.friendly and shot.z < .28
                  and abs(shot.x - state.heading_x) < .04 and abs(shot.y - state.heading_y) < .04]
        warning = next((enemy for enemy in state.enemies if enemy.telegraph
                        and abs(enemy.aim_x - state.heading_x) < .06
                        and abs(enemy.aim_y - state.heading_y) < .06), None)
        if danger or warning:
            if abs(state.heading_x) > .3:
                self.dodge_side = -math.copysign(1.0, state.heading_x)
            desired_x = clamp(state.heading_x + .16 * self.dodge_side, -.42, .42)
            desired_y = clamp(state.heading_y + .035, -.25, .25)
            if danger and state.energy >= 35 and state.pulse_cooldown <= 0:
                simulation.trigger_pulse()
        simulation.steer(clamp((desired_x - state.heading_x) * 12, -1, 1),
                         clamp((desired_y - state.heading_y) * 15, -1, 1))
        simulation.request_fire()
        if target.kind in ("boss", "frigate") and state.target_lock:
            simulation.launch_missile()
        if target.kind == "boss" and target.z < .62 and state.energy > 70:
            simulation.trigger_pulse()
