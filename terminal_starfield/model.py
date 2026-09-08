"""Deterministic simulation model, intentionally independent of terminal I/O."""

from __future__ import annotations

import math
import random
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .content import BOSS_PROFILES, EXTRA_UPGRADES, REFIT_SERVICES, ROUTES, ROUTE_CHOICES, attack_offsets, boss_for_sector


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class ShipSpec:
    name: str
    role: str
    description: str
    max_shield: float
    primary_damage: float
    primary_cooldown: float
    heat_per_shot: float
    missiles: int
    pulse_damage: float
    pulse_cooldown: float


SHIPS = {
    "vanguard": ShipSpec(
        "VANGUARD", "BALANCED INTERCEPTOR", "Reliable shields and a steady photon battery.",
        100, 1, 0.19, 13, 3, 2, 9,
    ),
    "wraith": ShipSpec(
        "WRAITH", "PHOTON SPECIALIST", "Fast, hard-hitting lasers on a fragile hull.",
        70, 1.5, 0.15, 15, 2, 2, 9,
    ),
    "aegis": ShipSpec(
        "AEGIS", "NOVA TANK", "Heavy shields and a stronger, faster nova pulse.",
        150, 1, 0.26, 12, 4, 4, 7,
    ),
}


@dataclass
class Star:
    x: float
    y: float
    z: float
    previous_z: float
    temperature: float
    twinkle: float
    magnitude: float


@dataclass
class Contact:
    kind: str  # "signal" or "debris"
    x: float
    y: float
    z: float = 1.35
    spin: float = 0.0
    seed: int = 0


@dataclass
class Enemy:
    kind: str
    x: float
    y: float
    z: float
    hp: float
    max_hp: float
    speed: float
    score: int
    spin: float = 0.0
    phase: float = 0.0
    fire_clock: float = 2.0
    flash: float = 0.0
    aim_x: Optional[float] = None
    aim_y: Optional[float] = None
    boss_id: str = "null_engine"
    attack_phase: int = 0
    attack_angle: float = 0.0

    @property
    def boss_phase(self) -> int:
        if self.hp > self.max_hp * 2.0 / 3.0:
            return 1
        if self.hp > self.max_hp / 3.0:
            return 2
        return 3

    @property
    def boss_telegraph(self) -> bool:
        return self.kind == "boss" and self.telegraph

    @property
    def telegraph(self) -> bool:
        return self.aim_x is not None and self.aim_y is not None

    @property
    def boss_attack(self) -> str:
        phase = self.attack_phase if self.telegraph and self.attack_phase else self.boss_phase
        return BOSS_PROFILES[self.boss_id].attacks[phase - 1]

    @property
    def impact_offsets(self) -> Tuple[Tuple[float, float], ...]:
        if self.kind == "boss":
            phase = self.attack_phase if self.telegraph and self.attack_phase else self.boss_phase
            return attack_offsets(self.boss_id, phase, self.attack_angle)
        if self.kind == "frigate":
            return ((-.024, 0.0), (0.0, 0.0), (.024, 0.0))
        return ((0.0, 0.0),)


@dataclass
class Projectile:
    kind: str
    x: float
    y: float
    z: float
    speed: float
    damage: float
    friendly: bool
    ttl: float = 4.0
    target: Optional[Enemy] = None
    pierce: int = 0
    hit_targets: List[Enemy] = field(default_factory=list, compare=False, repr=False)
    previous_z: Optional[float] = None


@dataclass
class Pickup:
    kind: str
    x: float
    y: float
    z: float
    spin: float = 0.0


@dataclass
class Burst:
    x: float
    y: float
    kind: str
    age: float = 0.0
    lifetime: float = 0.7

    @property
    def progress(self) -> float:
        return clamp(self.age / self.lifetime, 0.0, 1.0)


@dataclass
class Message:
    text: str
    tone: str = "accent"
    ttl: float = 2.2


@dataclass
class GameState:
    stars: List[Star] = field(default_factory=list)
    contacts: List[Contact] = field(default_factory=list)
    enemies: List[Enemy] = field(default_factory=list)
    projectiles: List[Projectile] = field(default_factory=list)
    pickups: List[Pickup] = field(default_factory=list)
    bursts: List[Burst] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)
    elapsed: float = 0.0
    distance: float = 0.0
    score: int = 0
    combo: int = 0
    best_combo: int = 0
    captures: int = 0
    shield: float = 100.0
    energy: float = 100.0
    throttle: float = 0.38
    heading_x: float = 0.0
    heading_y: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    boost_time: float = 0.0
    impact_flash: float = 0.0
    paused: bool = False
    help_visible: bool = False
    zen: bool = False
    trails: bool = True
    game_over: bool = False
    theme_index: int = 0
    density: int = 260
    fps: float = 0.0
    screen: str = "playing"
    run_mode: str = "voyage"
    menu_index: int = 0
    wave: int = 1
    wave_remaining: int = 0
    kills: int = 0
    credits: int = 0
    max_shield: float = 100.0
    weapon_heat: float = 0.0
    overheated: bool = False
    fire_cooldown: float = 0.0
    missiles: int = 3
    missile_cooldown: float = 0.0
    pulse_cooldown: float = 0.0
    invulnerable: float = 0.0
    upgrades: Dict[str, int] = field(default_factory=dict)
    upgrade_choices: List[str] = field(default_factory=list)
    boss_name: str = ""
    wave_banner: float = 0.0
    ship_id: str = "vanguard"
    seed: int = 0
    record_best: int = 0
    record_runs: int = 0
    record_status: str = ""
    auto_fire: bool = False
    systems_visible: bool = False
    demo: bool = False
    fire_buffer: float = 0.0
    target: Optional[Enemy] = None
    target_aligned: bool = False
    target_lock: bool = False
    muzzle_flash: float = 0.0
    hit_flash: float = 0.0
    route_id: str = "frontier"
    route_choices: List[str] = field(default_factory=list)
    route_history: List[str] = field(default_factory=lambda: ["frontier"])
    jump_time: float = 0.0
    refit_rerolls: int = 0
    shots_fired: int = 0
    shots_hit: int = 0
    damage_taken: float = 0.0
    grazes: int = 0
    bosses_defeated: int = 0
    wave_total: int = 0

    @property
    def boosting(self) -> bool:
        return self.boost_time > 0.0 and self.energy > 0.0

    @property
    def sector(self) -> int:
        if self.run_mode in ("campaign", "endless"):
            return 1 + (self.wave - 1) // 5
        return 1 + int(self.distance // 1800)

    @property
    def multiplier(self) -> int:
        return min(8, 1 + self.combo // 3)

    @property
    def speed(self) -> float:
        return self.throttle * (2.85 if self.boosting else 1.0)

    @property
    def boss_wave(self) -> bool:
        return self.run_mode in ("campaign", "endless") and self.wave % 5 == 0


class Simulation:
    """State machine for flight, contacts, collisions, and scoring."""

    DENSITY_PRESETS = (80, 150, 260, 420, 650)
    MENU_ITEMS = ("CAMPAIGN // 15 WAVES", "ENDLESS // DEEP RUN", "ZEN DRIFT", "QUIT")
    UPGRADE_INFO = {
        "rapid": ("OVERCLOCKED CAPACITORS", "laser cooldown -18%"),
        "damage": ("PHOTON LENS", "laser damage +1"),
        "multishot": ("SPLIT ARRAY", "adds a laser lane"),
        "pierce": ("PHASE ROUNDS", "lasers pierce +1 target"),
        "shield": ("AEGIS PLATING", "+25 max shield and repair"),
        "reactor": ("ZERO-POINT REACTOR", "nova pulse cooldown -0.7s"),
        "missiles": ("WARHEAD FABRICATOR", "+3 missiles now and each wave"),
        "coolant": ("CRYO MANIFOLD", "heat generation -22%"),
        "score": ("VOID PROTOCOL", "+50% score yield"),
    }
    UPGRADE_INFO.update({key: value[:2] for key, value in EXTRA_UPGRADES.items()})
    UPGRADE_CAPS = {"multishot": 2, "rapid": 5, "reactor": 6}
    UPGRADE_CAPS.update({key: value[2] for key, value in EXTRA_UPGRADES.items()})
    BOSS_NAMES = tuple(profile.name for profile in BOSS_PROFILES.values())
    FIXED_STEP = 1.0 / 120.0

    def __init__(self, density: int = 260, seed: Optional[int] = None, zen: bool = False, ship: str = "vanguard"):
        if ship not in SHIPS:
            raise ValueError("unknown ship: {}".format(ship))
        actual_seed = random.SystemRandom().randrange(2 ** 63) if seed is None else seed
        # Cosmetic star recycling must never influence encounters, drops, or drafts.
        self.rng = random.Random(actual_seed)
        self.visual_rng = random.Random(actual_seed)
        spec = SHIPS[ship]
        self.state = GameState(
            density=clamp_int(density, 40, 800), zen=zen,
            ship_id=ship, seed=actual_seed,
            shield=spec.max_shield, max_shield=spec.max_shield, missiles=spec.missiles,
        )
        self._spawn_clock = 1.5
        self._fps_smooth = 60.0
        self._time_remainder = 0.0
        self._populate(self.state.density)
        self.notify("FLIGHT LINK ESTABLISHED", "accent", 2.8)

    def show_title(self) -> None:
        self.state.screen = "title"
        self.state.paused = False
        self.state.help_visible = False
        self.state.systems_visible = False
        self.state.fire_buffer = 0.0
        self.state.game_over = False
        self.state.menu_index = 0
        self._time_remainder = 0.0

    def move_menu(self, amount: int) -> None:
        if self.state.screen == "title":
            self.state.menu_index = (self.state.menu_index + amount) % len(self.MENU_ITEMS)

    def cycle_ship(self, amount: int) -> None:
        if self.state.screen == "title":
            ships = list(SHIPS)
            self.state.ship_id = ships[(ships.index(self.state.ship_id) + amount) % len(ships)]

    def activate_menu(self) -> bool:
        """Activate the selected title item. False means quit."""
        if self.state.menu_index == 0:
            self.start_run("campaign")
        elif self.state.menu_index == 1:
            self.start_run("endless")
        elif self.state.menu_index == 2:
            self.start_run("zen")
        else:
            return False
        return True

    def start_run(self, mode: str = "campaign", ship: Optional[str] = None) -> None:
        if mode not in ("campaign", "endless", "zen", "voyage"):
            raise ValueError("unknown run mode: {}".format(mode))
        ship_id = self.state.ship_id if ship is None else ship
        if ship_id not in SHIPS:
            raise ValueError("unknown ship: {}".format(ship_id))
        spec = SHIPS[ship_id]
        density = self.state.density
        theme = self.state.theme_index
        trails = self.state.trails
        seed = self.state.seed
        record_best, record_runs = self.state.record_best, self.state.record_runs
        auto_fire, demo = self.state.auto_fire, self.state.demo
        self.rng.seed(seed)
        self.visual_rng.seed(seed)
        self.state = GameState(
            density=density,
            theme_index=theme,
            trails=trails,
            run_mode=mode,
            zen=mode == "zen",
            screen="playing",
            ship_id=ship_id,
            seed=seed,
            shield=spec.max_shield,
            max_shield=spec.max_shield,
            missiles=spec.missiles,
            record_best=record_best,
            record_runs=record_runs,
            auto_fire=auto_fire,
            demo=demo,
        )
        self._populate(density)
        self._spawn_clock = 1.5
        self._fps_smooth = 60.0
        self._time_remainder = 0.0
        if mode in ("campaign", "endless"):
            self._begin_wave()
        elif mode == "zen":
            self.notify("ZEN DRIFT // NO TARGETS // NO END", "accent", 2.8)
        else:
            self.notify("SIGNAL HUNT", "accent", 2.0)

    def _begin_wave(self) -> None:
        state = self.state
        state.screen = "playing"
        state.paused = False
        state.game_over = False
        state.wave_banner = 2.4
        state.enemies.clear()
        state.projectiles.clear()
        state.pickups.clear()
        state.wave_remaining = 1 if state.boss_wave else 5 + state.wave * 2
        state.wave_total = state.wave_remaining
        state.refit_rerolls = 0
        state.fire_buffer = 0.0
        state.target = None
        state.target_aligned = state.target_lock = False
        refill = state.upgrades.get("missiles", 0) * 3
        state.missiles = max(state.missiles, min(12, state.missiles + refill))
        self._spawn_clock = 0.35
        if state.boss_wave:
            state.boss_name = boss_for_sector(state.sector).name
            self.notify("BOSS VECTOR // {}".format(state.boss_name), "danger", 3.2)
        else:
            state.boss_name = ""
            self.notify("WAVE {:02d} // HOSTILES INBOUND".format(state.wave), "warning", 2.2)

    def _finish_wave(self) -> None:
        state = self.state
        if state.screen != "playing":
            return
        self._bank_pickups()
        state.fire_buffer = 0.0
        state.boost_time = 0.0
        state.velocity_x = state.velocity_y = 0.0
        state.shield = min(state.max_shield, state.shield + 12.0 + ROUTES[state.route_id].repair_bonus)
        if state.run_mode == "campaign" and state.wave >= 15:
            state.screen = "victory"
            state.paused = True
            self.notify("THE VOID BLINKED FIRST", "accent", 99.0)
            return
        state.screen = "upgrade"
        state.paused = True
        state.upgrade_choices = self._draft_upgrades()

    def _draft_pool(self) -> List[str]:
        state = self.state
        return [
            upgrade for upgrade in self.UPGRADE_INFO
            if upgrade not in self.UPGRADE_CAPS or state.upgrades.get(upgrade, 0) < self.UPGRADE_CAPS[upgrade]
        ]

    def _draft_upgrades(self, previous: Optional[List[str]] = None) -> List[str]:
        choices = self._draft_pool()
        self.rng.shuffle(choices)
        draft = choices[:3]
        # Rerolls replace a card even when a shuffle happens to choose the same set.
        if previous and set(draft) == set(previous):
            replacement = next((choice for choice in choices if choice not in previous), None)
            if replacement is not None:
                draft[-1] = replacement
        return draft

    def service_status(self, service: str) -> Dict[str, object]:
        state = self.state
        if service not in REFIT_SERVICES:
            return {"cost": 0, "available": False}
        cost = REFIT_SERVICES[service][1]
        if service == "reroll":
            cost *= 2 ** state.refit_rerolls
            useful = state.refit_rerolls < 2 and any(upgrade not in state.upgrade_choices for upgrade in self._draft_pool())
        elif service == "repair":
            useful = state.shield < state.max_shield
        else:
            useful = state.missiles < 12
        available = state.screen == "upgrade" and not (state.help_visible or state.systems_visible) and useful and state.credits >= cost
        return {"cost": cost, "available": available}

    def buy_service(self, service: str) -> bool:
        status = self.service_status(service)
        if not status["available"]:
            return False
        state = self.state
        state.credits -= status["cost"]
        if service == "repair":
            state.shield = min(state.max_shield, state.shield + 30.0)
        elif service == "missiles":
            state.missiles = min(12, state.missiles + 3)
        else:
            state.upgrade_choices = self._draft_upgrades(state.upgrade_choices)
            state.refit_rerolls += 1
        self.notify(REFIT_SERVICES[service][0] + " // COMPLETE", "accent", 1.2)
        return True

    def choose_upgrade(self, index: int) -> None:
        state = self.state
        if state.screen != "upgrade" or state.help_visible or state.systems_visible or not 0 <= index < len(state.upgrade_choices):
            return
        upgrade = state.upgrade_choices[index]
        level = state.upgrades.get(upgrade, 0) + 1
        state.upgrades[upgrade] = level
        if upgrade == "shield":
            state.max_shield += 25.0
            state.shield = min(state.max_shield, state.shield + 35.0)
        elif upgrade == "missiles":
            state.missiles = min(12, state.missiles + 3)
        sector_clear = state.boss_wave
        state.wave += 1
        state.upgrade_choices.clear()
        if sector_clear:
            state.screen = "route"
            state.paused = True
            state.route_choices = list(ROUTE_CHOICES)
        else:
            self._begin_wave()

    def choose_route(self, index: int) -> None:
        state = self.state
        if state.screen != "route" or state.help_visible or state.systems_visible or not 0 <= index < len(state.route_choices):
            return
        state.route_id = state.route_choices[index]
        state.route_history.append(state.route_id)
        state.route_choices.clear()
        state.screen = "jump"
        state.paused = False
        state.jump_time = 1.4
        state.boost_time = state.fire_buffer = 0.0
        state.enemies.clear()
        state.projectiles.clear()
        state.target = None
        state.target_aligned = state.target_lock = False
        self._time_remainder = 0.0

    def advance_time(self, milliseconds: float) -> None:
        """Deterministic stepping hook analogous to a web game's advanceTime()."""
        remaining = max(0.0, milliseconds / 1000.0)
        while remaining > 1e-12:
            dt = min(1.0 / 60.0, remaining)
            self.update(dt)
            remaining -= dt

    def render_game_to_text(self) -> str:
        """Concise machine-readable state for scripted gameplay verification."""
        state = self.state
        payload = {
            "coordinates": "world x right, y down, z 0 player to 1.4 horizon",
            "screen": state.screen,
            "mode": state.run_mode,
            "ship": state.ship_id,
            "seed": state.seed,
            "upgrades": state.upgrades,
            "player": {
                "heading": [round(state.heading_x, 3), round(state.heading_y, 3)],
                "shield": round(state.shield, 1),
                "energy": round(state.energy, 1),
                "heat": round(state.weapon_heat, 1),
                "missiles": state.missiles,
            },
            "wave": state.wave,
            "remaining": state.wave_remaining,
            "score": state.score,
            "kills": state.kills,
            "credits": state.credits,
            "wave_total": state.wave_total,
            "route": state.route_id,
            "route_history": state.route_history,
            "route_choices": state.route_choices,
            "jump_time": round(state.jump_time, 3),
            "target": {
                "kind": state.target.kind if state.target is not None else None,
                "aligned": state.target_aligned,
                "lock": state.target_lock,
            },
            "weapons": {
                "auto_fire": state.auto_fire,
                "overheated": state.overheated,
                "fire_buffer": round(state.fire_buffer, 3),
                "primary_cooldown": round(state.fire_cooldown, 3),
                "missile_cooldown": round(state.missile_cooldown, 3),
                "pulse_cooldown": round(state.pulse_cooldown, 3),
            },
            "run_stats": {
                "shots_fired": state.shots_fired,
                "shots_hit": state.shots_hit,
                "accuracy": round(state.shots_hit / state.shots_fired, 3) if state.shots_fired else 0.0,
                "damage_taken": round(state.damage_taken, 2),
                "grazes": state.grazes,
                "bosses_defeated": state.bosses_defeated,
            },
            "services": {service: self.service_status(service) for service in REFIT_SERVICES},
            "enemies": [
                {
                    "kind": enemy.kind, "x": round(enemy.x, 3), "y": round(enemy.y, 3),
                    "z": round(enemy.z, 3), "hp": round(enemy.hp, 1),
                    "boss_phase": enemy.boss_phase if enemy.kind == "boss" else None,
                    "boss_attack": enemy.boss_attack if enemy.kind == "boss" else None,
                    "boss_telegraph": enemy.boss_telegraph,
                    "telegraph": enemy.telegraph,
                    "boss_id": enemy.boss_id if enemy.kind == "boss" else None,
                    "attack_phase": enemy.attack_phase if enemy.telegraph else None,
                    "attack_angle": round(enemy.attack_angle, 3) if enemy.telegraph else None,
                    "aim_x": round(enemy.aim_x, 3) if enemy.aim_x is not None else None,
                    "aim_y": round(enemy.aim_y, 3) if enemy.aim_y is not None else None,
                }
                for enemy in state.enemies
            ],
            "projectiles": [
                {"kind": shot.kind, "x": round(shot.x, 3), "y": round(shot.y, 3), "z": round(shot.z, 3), "friendly": shot.friendly}
                for shot in state.projectiles[:16]
            ],
            "pickups": [{"kind": item.kind, "x": round(item.x, 3), "y": round(item.y, 3), "z": round(item.z, 3)} for item in state.pickups],
            "upgrade_choices": state.upgrade_choices,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    def _new_star(self, near: bool = False) -> Star:
        rng = self.visual_rng
        z = rng.uniform(0.08 if near else 0.65, 1.45)
        spread = 1.18
        return Star(
            x=rng.uniform(-spread, spread),
            y=rng.uniform(-spread * 0.62, spread * 0.62),
            z=z,
            previous_z=z,
            temperature=rng.random(),
            twinkle=rng.uniform(0.0, math.tau),
            magnitude=rng.uniform(0.55, 1.0),
        )

    def _populate(self, count: int) -> None:
        self.state.stars = [self._new_star(near=True) for _ in range(count)]

    def set_density(self, count: int) -> None:
        count = clamp_int(count, 40, 800)
        current = len(self.state.stars)
        if count > current:
            self.state.stars.extend(self._new_star() for _ in range(count - current))
        else:
            del self.state.stars[count:]
        self.state.density = count
        self.notify("STAR DENSITY // {:03d}".format(count), "muted", 1.2)

    def density_preset(self, index: int) -> None:
        if 0 <= index < len(self.DENSITY_PRESETS):
            self.set_density(self.DENSITY_PRESETS[index])

    def steer(self, dx: float, dy: float) -> None:
        if not self._flight_active():
            return
        state = self.state
        dx, dy = clamp(dx, -1.0, 1.0), clamp(dy, -1.0, 1.0)
        state.heading_x = clamp(state.heading_x + dx * 0.028, -0.48, 0.48)
        state.heading_y = clamp(state.heading_y + dy * 0.022, -0.31, 0.31)
        state.velocity_x = clamp(state.velocity_x + dx * 0.12, -0.30, 0.30)
        state.velocity_y = clamp(state.velocity_y + dy * 0.10, -0.24, 0.24)
        self.refresh_target()

    def aim_at(self, x: float, y: float) -> None:
        if not self._flight_active():
            return
        state = self.state
        state.heading_x = clamp(x, -0.48, 0.48)
        state.heading_y = clamp(y, -0.31, 0.31)
        state.velocity_x = state.velocity_y = 0.0
        self.refresh_target()

    def change_throttle(self, amount: float) -> None:
        if not self._flight_active():
            return
        self.state.throttle = clamp(self.state.throttle + amount, 0.08, 1.0)
        self.notify("THROTTLE // {:03d}%".format(round(self.state.throttle * 100)), "muted", 0.8)

    def engage_boost(self) -> None:
        state = self.state
        if not self._flight_active():
            return
        if state.energy >= 14.0:
            state.boost_time = max(state.boost_time, 1.35)
            self.notify("VECTOR DRIVE ENGAGED", "hot", 1.2)
        else:
            self.notify("VECTOR DRIVE CHARGING", "warning", 1.0)

    def cycle_theme(self) -> None:
        self.state.theme_index = (self.state.theme_index + 1) % 4

    def toggle_zen(self) -> None:
        self.state.zen = not self.state.zen
        self.state.contacts.clear()
        self.notify("ZEN DRIFT" if self.state.zen else "SIGNAL HUNT", "accent", 1.8)

    def notify(self, text: str, tone: str = "accent", ttl: float = 2.2) -> None:
        self.state.messages.append(Message(text=text, tone=tone, ttl=ttl))
        del self.state.messages[:-3]

    def restart(self) -> None:
        zen = self.state.zen
        self.start_run(self.state.run_mode)
        if self.state.run_mode == "voyage":
            self.state.zen = zen

    def _reset_star(self, star: Star) -> None:
        replacement = self._new_star()
        star.x = replacement.x
        star.y = replacement.y
        star.z = replacement.z
        star.previous_z = replacement.previous_z
        star.temperature = replacement.temperature
        star.twinkle = replacement.twinkle
        star.magnitude = replacement.magnitude

    def _spawn_contact(self) -> None:
        difficulty = min(0.64, 0.26 + self.state.sector * 0.045)
        kind = "debris" if self.rng.random() < difficulty else "signal"
        angle = self.rng.uniform(0.0, math.tau)
        if kind == "debris" and self.rng.random() < 0.78:
            # Debris on the current flight vector forces an evasive move.
            x = self.state.heading_x + self.rng.uniform(-0.006, 0.006)
            y = self.state.heading_y + self.rng.uniform(-0.008, 0.008)
        else:
            # Signals ask the pilot to choose and hold a new vector.
            radius = self.rng.uniform(0.08, 0.42)
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius * 0.64
        self.state.contacts.append(Contact(
            kind=kind,
            x=x,
            y=y,
            z=1.35,
            spin=self.rng.uniform(0.0, math.tau),
            seed=self.rng.randrange(10000),
        ))

    def _project_normalized(self, x: float, y: float, z: float) -> Tuple[float, float]:
        z = max(0.035, z)
        return ((x - self.state.heading_x) / z, (y - self.state.heading_y) / z)

    def _flight_active(self) -> bool:
        state = self.state
        return state.screen == "playing" and not (state.paused or state.help_visible or state.systems_visible or state.game_over) and state.shield > 0.0

    def _combat_active(self) -> bool:
        return self._flight_active() and self.state.run_mode in ("campaign", "endless")

    def refresh_target(self) -> None:
        state = self.state
        candidates = []
        for enemy in state.enemies:
            if enemy.hp > 0.0 and enemy.z > .075:
                x, y = self._project_normalized(enemy.x, enemy.y, enemy.z)
                candidates.append((math.hypot(x, y), enemy.z, abs(x) + abs(y), enemy))
        state.target_aligned = state.target_lock = False
        if not candidates:
            state.target = None
            return
        distance, _, lock, state.target = min(candidates, key=lambda candidate: candidate[:2])
        state.target_aligned = distance <= .09
        state.target_lock = lock <= .78

    def request_fire(self) -> None:
        if not self._combat_active():
            return
        self.state.fire_buffer = .24
        self.fire_primary()

    def toggle_auto_fire(self) -> None:
        if self.state.screen != "title" and not self._combat_active():
            return
        if self.state.help_visible or self.state.systems_visible:
            return
        self.state.auto_fire = not self.state.auto_fire

    def fire_primary(self) -> None:
        state = self.state
        if not self._combat_active():
            return
        if state.fire_cooldown > 0.0 or state.overheated or state.game_over:
            return
        spec = SHIPS[state.ship_id]
        lanes = min(3, 1 + state.upgrades.get("multishot", 0))
        spread = 0.012
        self.refresh_target()
        # A narrow, visible alignment cone corrects a near miss; it never follows
        # off-axis enemies or substitutes for steering the flight vector.
        aim_x, aim_y = state.heading_x, state.heading_y
        if state.target_aligned and state.target is not None:
            aim_x, aim_y = state.target.x, state.target.y
        for lane in range(lanes):
            offset = (lane - (lanes - 1) / 2.0) * spread
            state.projectiles.append(Projectile(
                kind="laser",
                x=aim_x + offset,
                y=aim_y,
                z=0.055,
                speed=2.75,
                damage=spec.primary_damage + state.upgrades.get("damage", 0),
                friendly=True,
                ttl=0.75,
                pierce=state.upgrades.get("pierce", 0),
            ))
            state.shots_fired += 1
        state.fire_buffer = 0.0
        state.muzzle_flash = .11
        rapid = min(self.UPGRADE_CAPS["rapid"], state.upgrades.get("rapid", 0))
        state.fire_cooldown = spec.primary_cooldown * math.pow(0.82, rapid)
        coolant = state.upgrades.get("coolant", 0)
        state.weapon_heat = min(110.0, state.weapon_heat + spec.heat_per_shot * math.pow(0.78, coolant) * ROUTES[state.route_id].heat_scale)
        if state.weapon_heat >= 100.0:
            state.overheated = True
            self.notify("WEAPON BUS OVERHEATED", "danger", 1.6)

    def launch_missile(self) -> None:
        state = self.state
        if not self._combat_active():
            return
        if state.missile_cooldown > 0.0 or state.missiles <= 0:
            return
        self.refresh_target()
        target = state.target
        if target is None:
            self.notify("NO LOCK", "muted", 0.8)
            return
        if not state.target_lock:
            self.notify("TARGET OUTSIDE LOCK CONE", "warning", 0.9)
            return
        state.missiles -= 1
        state.missile_cooldown = 0.8
        state.projectiles.append(Projectile("missile", state.heading_x, state.heading_y, 0.06, 1.45, 5.0, True, ttl=2.2, target=target))
        state.shots_fired += 1
        state.muzzle_flash = .16
        self.notify("SEEKER AWAY", "hot", 0.9)

    def trigger_pulse(self) -> None:
        state = self.state
        if not self._combat_active():
            return
        if state.pulse_cooldown > 0.0 or state.energy < 35.0:
            return
        spec = SHIPS[state.ship_id]
        state.energy -= 35.0
        if state.upgrades.get("echo", 0):
            state.missiles = min(12, state.missiles + 1)
        reactor = min(self.UPGRADE_CAPS["reactor"], state.upgrades.get("reactor", 0))
        state.pulse_cooldown = spec.pulse_cooldown - reactor * 0.7
        destroyed = 0
        for projectile in list(state.projectiles):
            if not projectile.friendly and projectile.z < 0.75:
                state.projectiles.remove(projectile)
                destroyed += 1
        for enemy in list(state.enemies):
            if enemy.z < 0.62:
                enemy.hp -= spec.pulse_damage
                enemy.flash = 0.25
                if enemy.hp <= 0.0:
                    self._destroy_enemy(enemy)
        state.bursts.append(Burst(0.0, 0.0, "pulse", lifetime=1.0))
        self.notify("NOVA PULSE // {} THREATS SCRUBBED".format(destroyed), "accent", 1.3)

    def _spawn_enemy(self) -> None:
        state = self.state
        hull_scale = ROUTES[state.route_id].enemy_hp_scale
        if state.boss_wave:
            # Sector builds need time to meet all three attack phases. Arrival is
            # already inside engagement range, so hull buys combat, not free fire.
            base_hull = 220.0 if state.sector == 1 else 180.0 + state.sector * 120.0
            hp = (base_hull + (state.wave if state.run_mode == "endless" else 0)) * hull_scale
            profile = boss_for_sector(state.sector)
            state.enemies.append(Enemy("boss", 0.0, -0.05, .88, hp, hp, 0.055, 2500,
                                       phase=self.rng.uniform(0, math.tau), fire_clock=1.3, boss_id=profile.id))
            state.wave_remaining = 0
            return
        stage = (state.wave - 1) % 5
        roll = self.rng.random()
        heavy_contact = stage == 2 and state.wave_remaining == state.wave_total
        if heavy_contact or (stage == 3 and roll > .7):
            kind, hp, speed, score = "frigate", 7.0, 0.075, 360
        elif stage in (1, 2, 3) and roll > .28:
            kind, hp, speed, score = "hunter", 3.0, 0.115, 190
        else:
            kind, hp, speed, score = "scout", 1.0, 0.17, 100
        radius = self.rng.uniform(0.05, 0.48)
        angle = self.rng.uniform(0.0, math.tau)
        state.enemies.append(Enemy(
            kind,
            math.cos(angle) * radius,
            math.sin(angle) * radius * 0.62,
            self.rng.uniform(1.12, 1.38),
            hp * hull_scale,
            hp * hull_scale,
            speed,
            score,
            phase=self.rng.uniform(0.0, math.tau),
            fire_clock=self.rng.uniform(1.2, 3.0),
        ))
        state.wave_remaining -= 1

    def _enemy_fire(self, enemy: Enemy) -> None:
        state = self.state
        if not enemy.telegraph:
            return
        plasma_scale = ROUTES[state.route_id].plasma_scale
        if enemy.kind == "boss":
            phase = enemy.attack_phase or enemy.boss_phase
            rhythms = {
                "null_engine": ((1.75, 2.1), (1.5, 1.85), (1.05, 1.3)),
                "archon_prime": ((2.2, 2.5), (1.95, 2.3), (1.7, 2.0)),
                "void_seraph": ((1.55, 1.9), (1.35, 1.65), (1.1, 1.35)),
            }
            speed, damage = {"null_engine": (.62, 11.0), "archon_prime": (.52, 12.0), "void_seraph": (.68, 10.0)}[enemy.boss_id]
            cooldown = rhythms[enemy.boss_id][phase - 1]
        else:
            speed, damage = (.44, 9.0) if enemy.kind == "frigate" else (.48, 8.0)
            cooldown = (2.4, 3.2) if enemy.kind == "frigate" else (1.8, 2.6)
        # Both origin and pattern were advertised before any projectile existed.
        for dx, dy in enemy.impact_offsets:
            state.projectiles.append(Projectile(
                "plasma", enemy.aim_x + dx, enemy.aim_y + dy, enemy.z,
                speed * plasma_scale, damage, False, ttl=3.5,
            ))
        enemy.fire_clock = self.rng.uniform(*cooldown)
        enemy.aim_x = enemy.aim_y = None

    def _update_enemy_weapon(self, enemy: Enemy, dt: float) -> None:
        if enemy.kind not in ("boss", "hunter", "frigate") or enemy.z >= .92:
            return
        if enemy.kind != "boss" and enemy.z <= .24:
            # A close passing hull cannot create an instant, unavoidable impact.
            enemy.aim_x = enemy.aim_y = None
            return
        warning = {"null_engine": .7, "archon_prime": .95, "void_seraph": .8}[enemy.boss_id] if enemy.kind == "boss" else .55
        enemy.fire_clock -= dt
        if not enemy.telegraph and enemy.fire_clock <= warning:
            enemy.aim_x, enemy.aim_y = self.state.heading_x, self.state.heading_y
            enemy.attack_phase = enemy.boss_phase if enemy.kind == "boss" else 0
            enemy.attack_angle = enemy.phase
            # Even an overdue or newly engaged shooter gives the entire warning.
            enemy.fire_clock = warning
        elif enemy.telegraph and enemy.fire_clock <= 1e-12:
            self._enemy_fire(enemy)

    def _damage_player(self, amount: float, message: str) -> None:
        state = self.state
        if state.invulnerable > 0.0 or state.game_over:
            return
        state.damage_taken += min(state.shield, amount)
        state.shield = max(0.0, state.shield - amount)
        state.combo = 0
        state.impact_flash = 0.55
        state.invulnerable = 0.45
        state.bursts.append(Burst(0.0, 0.0, "debris", lifetime=0.8))
        self.notify(message, "danger", 1.5)
        if state.shield <= 0.0:
            state.game_over = True
            state.screen = "game_over"
            state.boost_time = 0.0
            state.fire_buffer = 0.0
            self.notify("SHIP LOST // RUN TERMINATED", "danger", 99.0)

    def _destroy_enemy(self, enemy: Enemy) -> None:
        state = self.state
        if not self._enemy_alive(enemy):
            return
        state.enemies[:] = [other for other in state.enemies if other is not enemy]
        state.kills += 1
        state.combo += 1
        state.best_combo = max(state.best_combo, state.combo)
        multiplier = state.multiplier
        score_bonus = 1.0 + 0.5 * state.upgrades.get("score", 0)
        salvage_scale = ROUTES[state.route_id].salvage_scale
        points = round(enemy.score * multiplier * score_bonus * salvage_scale)
        state.score += points
        state.credits += max(1, round((enemy.score // 50) * salvage_scale))
        state.shield = min(state.max_shield, state.shield + 2 * state.upgrades.get("leech", 0))
        sx, sy = self._project_normalized(enemy.x, enemy.y, max(0.1, enemy.z))
        state.bursts.append(Burst(sx, sy, "boss" if enemy.kind == "boss" else "enemy", lifetime=1.2 if enemy.kind == "boss" else 0.65))
        if enemy.kind == "boss":
            state.bosses_defeated += 1
            self.notify("{} DESTROYED // +{:04d}".format(state.boss_name, points), "accent", 3.0)
        elif state.combo % 5 == 0:
            self.notify("KILL CHAIN {:02d} // x{}".format(state.combo, multiplier), "hot", 1.2)
        drop_chance = 1.0 if enemy.kind == "boss" else 0.24
        if self.rng.random() < drop_chance:
            kind = self.rng.choices(("repair", "energy", "missile", "credits"), weights=(2, 4, 2, 3), k=1)[0]
            state.pickups.append(Pickup(kind, enemy.x, enemy.y, max(0.2, enemy.z)))
        self.refresh_target()

    def _enemy_alive(self, enemy: Optional[Enemy]) -> bool:
        return enemy is not None and any(other is enemy for other in self.state.enemies)

    def _cascade(self, source: Enemy) -> None:
        damage = 2 * self.state.upgrades.get("cascade", 0)
        if not damage:
            return
        for enemy in list(self.state.enemies):
            distance = (enemy.x - source.x) ** 2 + (enemy.y - source.y) ** 2 + (enemy.z - source.z) ** 2
            if distance <= .18 ** 2:
                enemy.hp -= damage
                enemy.flash = .22
                sx, sy = self._project_normalized(enemy.x, enemy.y, enemy.z)
                self.state.bursts.append(Burst(sx, sy, "arc", lifetime=.45))
                if enemy.hp <= 0:
                    self._destroy_enemy(enemy)

    def _collect_pickup(self, pickup: Pickup) -> None:
        state = self.state
        if pickup.kind == "repair":
            state.shield = min(state.max_shield, state.shield + 28.0)
            label = "SHIELD PATCH +28"
        elif pickup.kind == "energy":
            state.energy = min(100.0, state.energy + 35.0)
            label = "REACTOR CHARGE +35"
        elif pickup.kind == "missile":
            state.missiles = min(12, state.missiles + 2)
            label = "SEEKERS +2"
        else:
            scale = ROUTES[state.route_id].salvage_scale
            state.credits += round(10 * scale)
            points = round(250 * scale)
            state.score += points
            label = "VOID CACHE +{}".format(points)
        self.notify(label, "accent", 1.2)

    def _bank_pickups(self) -> None:
        for pickup in self.state.pickups:
            self._collect_pickup(pickup)
        self.state.pickups.clear()

    def _move_enemy(self, enemy: Enemy, dt: float) -> None:
        state = self.state
        enemy.flash = max(0.0, enemy.flash - dt)
        enemy.spin += dt * (1.0 if enemy.kind == "boss" else 2.2)
        enemy.phase += dt
        if enemy.kind == "scout":
            # Scouts dive inward, while hunters strafe across the flight vector.
            enemy.x += (-enemy.x * .28 + math.sin(enemy.phase * 2.3) * .024) * dt
            enemy.y += (-enemy.y * .24 + math.cos(enemy.phase * 1.7) * .009) * dt
        elif enemy.kind == "hunter":
            enemy.x += math.sin(enemy.phase * 1.6) * .052 * dt
            enemy.y += math.cos(enemy.phase * 1.1) * .016 * dt
        elif enemy.kind == "frigate":
            enemy.x += math.sin(enemy.phase * .8) * .008 * dt
            enemy.y -= enemy.y * .035 * dt
        else:
            frequency, weave = {"null_engine": (1.1, .01), "archon_prime": (.6, .006), "void_seraph": (1.4, .02)}[enemy.boss_id]
            enemy.x += math.sin(enemy.phase * frequency) * weave * dt
            enemy.y += math.cos(enemy.phase * frequency * .8) * weave * .45 * dt
        enemy.x = clamp(enemy.x, -.48, .48)
        enemy.y = clamp(enemy.y, -.31, .31)
        enemy.z -= (enemy.speed + state.speed * .055) * dt
        if enemy.kind == "boss":
            floor = {"null_engine": .52, "archon_prime": .58, "void_seraph": .55}[enemy.boss_id]
            enemy.z = max(floor, enemy.z)
        self._update_enemy_weapon(enemy, dt)

    @staticmethod
    def _swept_hit(start: Tuple[float, float, float], end: Tuple[float, float, float], radius: float) -> Optional[float]:
        """First intersection of a relative-motion segment and an enemy hull."""
        entry, leave = 0.0, 1.0
        for first, last, extent in zip(start, end, (radius, radius, .065)):
            movement = last - first
            if abs(movement) < 1e-12:
                if abs(first) > extent:
                    return None
                continue
            low, high = (-extent - first) / movement, (extent - first) / movement
            if low > high:
                low, high = high, low
            entry, leave = max(entry, low), min(leave, high)
            if entry > leave:
                return None
        return entry

    def _hit_enemy(self, shot: Projectile, enemy: Enemy) -> None:
        state = self.state
        if not shot.hit_targets:
            # Directly injected diagnostic projectiles are not counted as fired.
            state.shots_hit = min(state.shots_fired, state.shots_hit + 1)
        shot.hit_targets.append(enemy)
        enemy.hp -= shot.damage
        enemy.flash = .12
        state.hit_flash = .14
        if enemy.hp <= 0.0:
            self._destroy_enemy(enemy)
            if shot.kind == "missile":
                self._cascade(enemy)
        if shot.kind == "missile":
            sx, sy = self._project_normalized(enemy.x, enemy.y, max(.1, enemy.z))
            state.bursts.append(Burst(sx, sy, "missile", lifetime=.8))

    def _update_projectiles(self, dt: float, old_positions: Dict[int, Tuple[float, float, float]], old_heading: Tuple[float, float]) -> None:
        state = self.state
        survivors = []
        for shot in state.projectiles:
            if shot.ttl <= 0.0 or shot.z > 1.55:
                continue
            duration = min(dt, shot.ttl)
            fraction = duration / dt
            start = (shot.x, shot.y, shot.z)
            shot.previous_z = shot.z
            if shot.friendly:
                if shot.kind == "missile" and self._enemy_alive(shot.target):
                    target = shot.target
                    tracking = min(1.0, duration * 7.0)
                    shot.x += (target.x - shot.x) * tracking
                    shot.y += (target.y - shot.y) * tracking
                shot.z += shot.speed * duration
                impacts = []
                for enemy in state.enemies:
                    if any(previous is enemy for previous in shot.hit_targets):
                        continue
                    before = old_positions.get(id(enemy), (enemy.x, enemy.y, enemy.z))
                    after = tuple(first + (last - first) * fraction for first, last in zip(before, (enemy.x, enemy.y, enemy.z)))
                    relative_start = tuple(value - center for value, center in zip(start, before))
                    relative_end = tuple(value - center for value, center in zip((shot.x, shot.y, shot.z), after))
                    contact = self._swept_hit(relative_start, relative_end, .09 if enemy.kind == "boss" else .035)
                    if contact is not None:
                        impacts.append((contact, enemy))
                consumed = False
                for _, enemy in sorted(impacts, key=lambda impact: impact[0]):
                    if not self._enemy_alive(enemy):
                        continue
                    self._hit_enemy(shot, enemy)
                    if shot.pierce > 0:
                        shot.pierce -= 1
                    else:
                        consumed = True
                        break
                if consumed:
                    continue
            else:
                shot.z -= shot.speed * duration
                if shot.z <= .075:
                    # Sample the player's vector at the crossing, not at frame end.
                    crossed = clamp((start[2] - .075) / max(1e-12, start[2] - shot.z), 0.0, 1.0) * fraction
                    heading_x = old_heading[0] + (state.heading_x - old_heading[0]) * crossed
                    heading_y = old_heading[1] + (state.heading_y - old_heading[1]) * crossed
                    sx, sy = (shot.x - heading_x) / .075, (shot.y - heading_y) / .075
                    if abs(sx) < .16 and abs(sy) < .21:
                        self._damage_player(shot.damage, "PLASMA STRIKE // EVADE")
                    elif abs(sx) < .42 and abs(sy) < .5:
                        state.grazes += 1
                        state.score += round(25 * ROUTES[state.route_id].salvage_scale)
                        state.energy = min(100.0, state.energy + 8 * state.upgrades.get("graze", 0))
                        state.bursts.append(Burst(sx, sy, "graze", lifetime=.4))
                    continue
            shot.ttl -= dt
            if shot.ttl > 0.0 and shot.z <= 1.55:
                survivors.append(shot)
        state.projectiles = survivors

    def _update_combat(self, dt: float, old_heading: Optional[Tuple[float, float]] = None) -> None:
        state = self.state
        if old_heading is None:
            old_heading = (state.heading_x, state.heading_y)
        state.wave_banner = max(0.0, state.wave_banner - dt)
        state.fire_cooldown = max(0.0, state.fire_cooldown - dt)
        state.fire_buffer = max(0.0, state.fire_buffer - dt)
        state.missile_cooldown = max(0.0, state.missile_cooldown - dt)
        state.pulse_cooldown = max(0.0, state.pulse_cooldown - dt)
        state.invulnerable = max(0.0, state.invulnerable - dt)
        state.weapon_heat = max(0.0, state.weapon_heat - (24.0 + state.upgrades.get("coolant", 0) * 3.0) * dt)
        if state.overheated and state.weapon_heat < 42.0:
            state.overheated = False
            self.notify("WEAPON BUS READY", "accent", .9)

        self._spawn_clock -= dt
        cap = min(7, 3 + state.sector)
        if state.wave_remaining > 0 and len(state.enemies) < cap and self._spawn_clock <= 0.0:
            self._spawn_enemy()
            self._spawn_clock = .65 if state.boss_wave else max(.35, 1.05 - state.wave * .025)

        old_positions = {id(enemy): (enemy.x, enemy.y, enemy.z) for enemy in state.enemies}
        for enemy in state.enemies:
            self._move_enemy(enemy, dt)
        self.refresh_target()
        if state.fire_buffer > 0.0 or (state.auto_fire and state.target_aligned):
            self.fire_primary()
        self._update_projectiles(dt, old_positions, old_heading)

        for enemy in list(state.enemies):
            if enemy.kind != "boss" and enemy.z <= .085:
                sx, sy = self._project_normalized(enemy.x, enemy.y, .085)
                if abs(sx) < .16 and abs(sy) < .2:
                    self._damage_player(16.0, "RAM IMPACT // SHIELDS HIT")
                state.enemies[:] = [other for other in state.enemies if other is not enemy]
                state.combo = 0

        cleared = state.wave_remaining == 0 and not state.enemies
        if cleared and not state.game_over:
            # Bank the last kill's drop before remaining plasma can outlive it.
            self._bank_pickups()
        else:
            for pickup in list(state.pickups):
                pickup.z -= (.11 + state.speed * .06) * dt
                pickup.spin += dt * 3.0
                if pickup.z <= .095:
                    sx, sy = self._project_normalized(pickup.x, pickup.y, .095)
                    if abs(sx) < .2 and abs(sy) < .24:
                        self._collect_pickup(pickup)
                    state.pickups.remove(pickup)
        self.refresh_target()
        if not state.game_over and cleared and not any(not shot.friendly for shot in state.projectiles):
            self._finish_wave()

    def _resolve_contact(self, contact: Contact) -> None:
        state = self.state
        sx, sy = self._project_normalized(contact.x, contact.y, contact.z)
        centered = abs(sx) < 0.105 and abs(sy) < 0.15
        if contact.kind == "signal" and centered:
            state.combo += 1
            state.best_combo = max(state.best_combo, state.combo)
            state.captures += 1
            points = 100 * state.multiplier
            state.score += points
            state.energy = min(100.0, state.energy + 18.0)
            state.bursts.append(Burst(sx, sy, "signal"))
            self.notify("SIGNAL CAPTURED // +{:04d}".format(points), "accent", 1.6)
        elif contact.kind == "debris" and centered:
            damage = max(12.0, 25.0 - state.sector)
            state.damage_taken += min(state.shield, damage)
            state.shield = max(0.0, state.shield - damage)
            state.combo = 0
            state.impact_flash = 0.55
            state.bursts.append(Burst(sx, sy, "debris", lifetime=0.9))
            self.notify("HULL IMPACT // SHIELD -{:02d}".format(round(damage)), "danger", 2.0)
            if state.shield <= 0.0:
                state.game_over = True
                state.screen = "game_over"
                state.boost_time = 0.0
                self.notify("FLIGHT LINK LOST", "danger", 99.0)
        elif contact.kind == "signal":
            state.combo = 0

    def update(self, dt: float) -> None:
        state = self.state
        if not math.isfinite(dt) or dt <= 0.0:
            return
        instant_fps = min(240.0, 1.0 / dt)
        self._fps_smooth = self._fps_smooth * 0.93 + instant_fps * 0.07
        state.fps = self._fps_smooth
        if state.paused or state.help_visible or state.systems_visible or state.game_over:
            self._time_remainder = 0.0
            state.fire_buffer = 0.0
            return
        # Render cadence only supplies elapsed time. Every gameplay integration,
        # encounter roll and auto-fire decision runs on the same 120 Hz clock.
        self._time_remainder += min(dt, .25)
        while self._time_remainder + 1e-12 >= self.FIXED_STEP:
            self._time_remainder = max(0.0, self._time_remainder - self.FIXED_STEP)
            self._step(self.FIXED_STEP)
            if state.paused or state.help_visible or state.systems_visible or state.game_over:
                self._time_remainder = 0.0
                break

    def _step(self, dt: float) -> None:
        state = self.state

        state.elapsed += dt
        state.impact_flash = max(0.0, state.impact_flash - dt)
        state.muzzle_flash = max(0.0, state.muzzle_flash - dt)
        state.hit_flash = max(0.0, state.hit_flash - dt)
        for message in state.messages:
            message.ttl -= dt
        state.messages[:] = [message for message in state.messages if message.ttl > 0.0]
        for burst in state.bursts:
            burst.age += dt
        state.bursts[:] = [burst for burst in state.bursts if burst.age < burst.lifetime]

        old_heading = (state.heading_x, state.heading_y)
        if state.screen == "playing":
            state.heading_x = clamp(state.heading_x + state.velocity_x * dt, -.48, .48)
            state.heading_y = clamp(state.heading_y + state.velocity_y * dt, -.31, .31)
            damping = math.exp(-5.0 * dt)
            state.velocity_x *= damping
            state.velocity_y *= damping
            if state.boosting:
                state.boost_time = max(0.0, state.boost_time - dt)
                state.energy = max(0.0, state.energy - 28.0 * dt)
            else:
                state.boost_time = 0.0
                state.energy = min(100.0, state.energy + 7.5 * dt)

        speed = 2.4 if state.screen == "jump" else state.speed
        state.distance += speed * dt * 128.0
        for star in state.stars:
            star.previous_z = star.z
            star.z -= speed * dt * (0.72 + 0.34 * star.magnitude)
            star.twinkle += dt * (1.2 + star.magnitude)
            sx, sy = self._project_normalized(star.x, star.y, star.z)
            if star.z <= 0.035 or abs(sx) > 1.35 or abs(sy) > 1.55:
                self._reset_star(star)

        if state.screen == "jump":
            state.jump_time = max(0.0, state.jump_time - dt)
            if state.jump_time <= 1e-12:
                state.jump_time = 0.0
                self._begin_wave()
            return
        if state.screen != "playing":
            return

        if state.run_mode in ("campaign", "endless"):
            self._update_combat(dt, old_heading)
        elif not state.zen:
            self._spawn_clock -= dt
            if self._spawn_clock <= 0.0 and len(state.contacts) < 4:
                self._spawn_contact()
                base = max(0.72, 2.15 - state.sector * 0.08)
                self._spawn_clock = self.rng.uniform(base * 0.75, base * 1.25)

            survivors: List[Contact] = []
            for contact in state.contacts:
                contact.z -= speed * dt * (0.70 if contact.kind == "signal" else 0.76)
                contact.spin += dt * (2.4 if contact.kind == "signal" else 1.4)
                if contact.z <= 0.115:
                    self._resolve_contact(contact)
                else:
                    survivors.append(contact)
            state.contacts = survivors


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))
