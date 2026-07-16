"""Deterministic simulation model, intentionally independent of terminal I/O."""

from __future__ import annotations

import math
import random
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


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

    def __init__(self, density: int = 260, seed: Optional[int] = None, zen: bool = False):
        self.rng = random.Random(seed)
        self.state = GameState(density=clamp_int(density, 40, 800), zen=zen)
        self._spawn_clock = 1.5
        self._fps_smooth = 60.0
        self._populate(self.state.density)
        self.notify("FLIGHT LINK ESTABLISHED", "accent", 2.8)

    def show_title(self) -> None:
        self.state.screen = "title"
        self.state.paused = False
        self.state.help_visible = False
        self.state.game_over = False
        self.state.menu_index = 0

    def move_menu(self, amount: int) -> None:
        if self.state.screen == "title":
            self.state.menu_index = (self.state.menu_index + amount) % len(self.MENU_ITEMS)

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

    def start_run(self, mode: str = "campaign") -> None:
        if mode not in ("campaign", "endless", "zen", "voyage"):
            raise ValueError("unknown run mode: {}".format(mode))
        density = self.state.density
        theme = self.state.theme_index
        trails = self.state.trails
        self.state = GameState(
            density=density,
            theme_index=theme,
            trails=trails,
            run_mode=mode,
            zen=mode == "zen",
            screen="playing",
        )
        self._populate(density)
        self._spawn_clock = 0.65
        if mode in ("campaign", "endless"):
            self._begin_wave()
        elif mode == "zen":
            self.notify("ZEN DRIFT // NO TARGETS // NO END", "accent", 2.8)
        else:
            self.notify("SIGNAL HUNT", "accent", 2.0)

    def _begin_wave(self) -> None:
        state = self.state
        state.screen = "playing"
        state.game_over = False
        state.wave_banner = 2.4
        state.enemies.clear()
        state.projectiles.clear()
        state.pickups.clear()
        state.wave_remaining = 1 if state.boss_wave else 5 + state.wave * 2
        state.missiles = min(9, state.missiles + state.upgrades.get("missiles", 0))
        self._spawn_clock = 0.35
        if state.boss_wave:
            state.boss_name = self.rng.choice(("THE NULL ENGINE", "ARCHON PRIME", "VOID SERAPH", "RED GIANT"))
            self.notify("BOSS VECTOR // {}".format(state.boss_name), "danger", 3.2)
        else:
            state.boss_name = ""
            self.notify("WAVE {:02d} // HOSTILES INBOUND".format(state.wave), "warning", 2.2)

    def _finish_wave(self) -> None:
        state = self.state
        if state.run_mode == "campaign" and state.wave >= 15:
            state.screen = "victory"
            state.paused = True
            self.notify("THE VOID BLINKED FIRST", "accent", 99.0)
            return
        state.screen = "upgrade"
        state.paused = True
        choices = list(self.UPGRADE_INFO)
        self.rng.shuffle(choices)
        state.upgrade_choices = choices[:3]
        state.shield = min(state.max_shield, state.shield + 12.0)

    def choose_upgrade(self, index: int) -> None:
        state = self.state
        if state.screen != "upgrade" or not 0 <= index < len(state.upgrade_choices):
            return
        upgrade = state.upgrade_choices[index]
        level = state.upgrades.get(upgrade, 0) + 1
        state.upgrades[upgrade] = level
        if upgrade == "shield":
            state.max_shield += 25.0
            state.shield = min(state.max_shield, state.shield + 35.0)
        elif upgrade == "missiles":
            state.missiles = min(12, state.missiles + 3)
        state.wave += 1
        state.paused = False
        state.upgrade_choices.clear()
        self._begin_wave()

    def advance_time(self, milliseconds: float) -> None:
        """Deterministic stepping hook analogous to a web game's advanceTime()."""
        steps = max(1, round(milliseconds / (1000.0 / 60.0)))
        for _ in range(steps):
            self.update(1.0 / 60.0)

    def render_game_to_text(self) -> str:
        """Concise machine-readable state for scripted gameplay verification."""
        state = self.state
        payload = {
            "coordinates": "world x right, y down, z 0 player to 1.4 horizon",
            "screen": state.screen,
            "mode": state.run_mode,
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
            "enemies": [
                {"kind": enemy.kind, "x": round(enemy.x, 3), "y": round(enemy.y, 3), "z": round(enemy.z, 3), "hp": round(enemy.hp, 1)}
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
        z = self.rng.uniform(0.08 if near else 0.65, 1.45)
        spread = 1.18
        return Star(
            x=self.rng.uniform(-spread, spread),
            y=self.rng.uniform(-spread * 0.62, spread * 0.62),
            z=z,
            previous_z=z,
            temperature=self.rng.random(),
            twinkle=self.rng.uniform(0.0, math.tau),
            magnitude=self.rng.uniform(0.55, 1.0),
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
        if self.state.game_over:
            return
        self.state.velocity_x = clamp(self.state.velocity_x + dx * 0.34, -0.72, 0.72)
        self.state.velocity_y = clamp(self.state.velocity_y + dy * 0.26, -0.52, 0.52)

    def change_throttle(self, amount: float) -> None:
        self.state.throttle = clamp(self.state.throttle + amount, 0.08, 1.0)
        self.notify("THROTTLE // {:03d}%".format(round(self.state.throttle * 100)), "muted", 0.8)

    def engage_boost(self) -> None:
        state = self.state
        if state.energy >= 14.0 and not state.game_over:
            state.boost_time = max(state.boost_time, 1.35)
            self.notify("VECTOR DRIVE ENGAGED", "hot", 1.2)
        elif not state.game_over:
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
        if self.state.run_mode in ("campaign", "endless", "zen"):
            self.start_run(self.state.run_mode)
            return
        density = self.state.density
        theme = self.state.theme_index
        zen = self.state.zen
        trails = self.state.trails
        self.state = GameState(density=density, theme_index=theme, zen=zen, trails=trails)
        self._populate(density)
        self._spawn_clock = 1.2
        self.notify("NAVIGATION RESET // GOOD HUNTING", "accent", 2.2)

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

    def fire_primary(self) -> None:
        state = self.state
        if state.screen != "playing" or state.run_mode not in ("campaign", "endless"):
            return
        if state.fire_cooldown > 0.0 or state.overheated or state.game_over:
            return
        lanes = min(3, 1 + state.upgrades.get("multishot", 0))
        spread = 0.012
        for lane in range(lanes):
            offset = (lane - (lanes - 1) / 2.0) * spread
            state.projectiles.append(Projectile(
                kind="laser",
                x=state.heading_x + offset,
                y=state.heading_y,
                z=0.055,
                speed=2.75,
                damage=1.0 + state.upgrades.get("damage", 0),
                friendly=True,
                ttl=0.75,
                pierce=state.upgrades.get("pierce", 0),
            ))
        rapid = state.upgrades.get("rapid", 0)
        state.fire_cooldown = max(0.075, 0.19 * math.pow(0.82, rapid))
        coolant = state.upgrades.get("coolant", 0)
        state.weapon_heat = min(110.0, state.weapon_heat + 13.0 * math.pow(0.78, coolant))
        if state.weapon_heat >= 100.0:
            state.overheated = True
            self.notify("WEAPON BUS OVERHEATED", "danger", 1.6)

    def launch_missile(self) -> None:
        state = self.state
        if state.screen != "playing" or state.missile_cooldown > 0.0 or state.missiles <= 0:
            return
        candidates = []
        for enemy in state.enemies:
            sx, sy = self._project_normalized(enemy.x, enemy.y, enemy.z)
            candidates.append((abs(sx) + abs(sy), enemy))
        if not candidates:
            self.notify("NO LOCK", "muted", 0.8)
            return
        lock, target = min(candidates, key=lambda item: item[0])
        if lock > 0.78:
            self.notify("TARGET OUTSIDE LOCK CONE", "warning", 0.9)
            return
        state.missiles -= 1
        state.missile_cooldown = 0.8
        state.projectiles.append(Projectile("missile", state.heading_x, state.heading_y, 0.06, 1.45, 5.0, True, ttl=2.2, target=target))
        self.notify("SEEKER AWAY", "hot", 0.9)

    def trigger_pulse(self) -> None:
        state = self.state
        if state.screen != "playing" or state.pulse_cooldown > 0.0 or state.energy < 35.0:
            return
        state.energy -= 35.0
        state.pulse_cooldown = max(5.0, 9.0 - state.upgrades.get("reactor", 0) * 0.7)
        destroyed = 0
        for projectile in list(state.projectiles):
            if not projectile.friendly and projectile.z < 0.75:
                state.projectiles.remove(projectile)
                destroyed += 1
        for enemy in list(state.enemies):
            if enemy.z < 0.62:
                enemy.hp -= 2.0
                enemy.flash = 0.25
                if enemy.hp <= 0.0:
                    self._destroy_enemy(enemy)
        state.bursts.append(Burst(0.0, 0.0, "pulse", lifetime=1.0))
        self.notify("NOVA PULSE // {} THREATS SCRUBBED".format(destroyed), "accent", 1.3)

    def _spawn_enemy(self) -> None:
        state = self.state
        if state.boss_wave:
            hp = 28.0 + state.sector * 12.0 + (state.wave if state.run_mode == "endless" else 0)
            state.enemies.append(Enemy("boss", 0.0, -0.05, 1.28, hp, hp, 0.055, 2500, phase=self.rng.uniform(0, math.tau), fire_clock=1.3))
            state.wave_remaining = 0
            return
        roll = self.rng.random() + min(0.45, state.wave * 0.025)
        if roll > 1.08:
            kind, hp, speed, score = "frigate", 7.0, 0.075, 360
        elif roll > 0.65:
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
            hp,
            hp,
            speed,
            score,
            phase=self.rng.uniform(0.0, math.tau),
            fire_clock=self.rng.uniform(1.2, 3.0),
        ))
        state.wave_remaining -= 1

    def _enemy_fire(self, enemy: Enemy) -> None:
        state = self.state
        shots = 3 if enemy.kind == "boss" else 1
        for index in range(shots):
            spread = (index - (shots - 1) / 2.0) * 0.025
            state.projectiles.append(Projectile(
                "plasma",
                enemy.x + spread,
                enemy.y,
                enemy.z,
                0.62 if enemy.kind == "boss" else 0.48,
                11.0 if enemy.kind == "boss" else 8.0,
                False,
                ttl=3.5,
            ))
        enemy.fire_clock = self.rng.uniform(0.75, 1.25) if enemy.kind == "boss" else self.rng.uniform(1.8, 3.2)

    def _damage_player(self, amount: float, message: str) -> None:
        state = self.state
        if state.invulnerable > 0.0 or state.game_over:
            return
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
            self.notify("SHIP LOST // RUN TERMINATED", "danger", 99.0)

    def _destroy_enemy(self, enemy: Enemy) -> None:
        state = self.state
        if enemy not in state.enemies:
            return
        state.enemies.remove(enemy)
        state.kills += 1
        state.combo += 1
        state.best_combo = max(state.best_combo, state.combo)
        multiplier = state.multiplier
        score_bonus = 1.0 + 0.5 * state.upgrades.get("score", 0)
        points = round(enemy.score * multiplier * score_bonus)
        state.score += points
        state.credits += max(1, enemy.score // 50)
        sx, sy = self._project_normalized(enemy.x, enemy.y, max(0.1, enemy.z))
        state.bursts.append(Burst(sx, sy, "boss" if enemy.kind == "boss" else "enemy", lifetime=1.2 if enemy.kind == "boss" else 0.65))
        if enemy.kind == "boss":
            self.notify("{} DESTROYED // +{:04d}".format(state.boss_name, points), "accent", 3.0)
        elif state.combo % 5 == 0:
            self.notify("KILL CHAIN {:02d} // x{}".format(state.combo, multiplier), "hot", 1.2)
        drop_chance = 1.0 if enemy.kind == "boss" else 0.24
        if self.rng.random() < drop_chance:
            kind = self.rng.choices(("repair", "energy", "missile", "credits"), weights=(2, 4, 2, 3), k=1)[0]
            state.pickups.append(Pickup(kind, enemy.x, enemy.y, max(0.2, enemy.z)))

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
            state.credits += 10
            state.score += 250
            label = "VOID CACHE +250"
        self.notify(label, "accent", 1.2)

    def _update_combat(self, dt: float) -> None:
        state = self.state
        state.wave_banner = max(0.0, state.wave_banner - dt)
        state.fire_cooldown = max(0.0, state.fire_cooldown - dt)
        state.missile_cooldown = max(0.0, state.missile_cooldown - dt)
        state.pulse_cooldown = max(0.0, state.pulse_cooldown - dt)
        state.invulnerable = max(0.0, state.invulnerable - dt)
        state.weapon_heat = max(0.0, state.weapon_heat - (24.0 + state.upgrades.get("coolant", 0) * 3.0) * dt)
        if state.overheated and state.weapon_heat < 42.0:
            state.overheated = False
            self.notify("WEAPON BUS READY", "accent", 0.9)

        self._spawn_clock -= dt
        cap = min(7, 3 + state.sector)
        if state.wave_remaining > 0 and len(state.enemies) < cap and self._spawn_clock <= 0.0:
            self._spawn_enemy()
            self._spawn_clock = 0.65 if state.boss_wave else max(0.35, 1.05 - state.wave * 0.025)

        for enemy in list(state.enemies):
            enemy.flash = max(0.0, enemy.flash - dt)
            enemy.spin += dt * (1.0 if enemy.kind == "boss" else 2.2)
            enemy.phase += dt
            weave = 0.018 if enemy.kind == "scout" else 0.009
            enemy.x += math.sin(enemy.phase * (2.3 if enemy.kind == "scout" else 1.1)) * weave * dt
            enemy.y += math.cos(enemy.phase * 1.7) * weave * 0.45 * dt
            enemy.z -= (enemy.speed + state.speed * 0.055) * dt
            enemy.fire_clock -= dt
            if enemy.kind in ("hunter", "frigate", "boss") and enemy.z < 0.92 and enemy.fire_clock <= 0.0:
                self._enemy_fire(enemy)
            if enemy.z <= 0.085:
                sx, sy = self._project_normalized(enemy.x, enemy.y, 0.085)
                if abs(sx) < 0.16 and abs(sy) < 0.2:
                    self._damage_player(28.0 if enemy.kind == "boss" else 16.0, "RAM IMPACT // SHIELDS HIT")
                if enemy in state.enemies:
                    state.enemies.remove(enemy)
                    state.combo = 0

        for shot in list(state.projectiles):
            shot.ttl -= dt
            if shot.friendly:
                if shot.kind == "missile" and shot.target in state.enemies:
                    target = shot.target
                    tracking = min(1.0, dt * 7.0)
                    shot.x += (target.x - shot.x) * tracking
                    shot.y += (target.y - shot.y) * tracking
                shot.z += shot.speed * dt
                for enemy in list(state.enemies):
                    radius = 0.035 if enemy.kind != "boss" else 0.09
                    if abs(shot.z - enemy.z) < 0.085 and abs(shot.x - enemy.x) < radius and abs(shot.y - enemy.y) < radius:
                        enemy.hp -= shot.damage
                        enemy.flash = 0.12
                        if enemy.hp <= 0.0:
                            self._destroy_enemy(enemy)
                        if shot.kind == "missile":
                            sx, sy = self._project_normalized(shot.x, shot.y, max(0.1, shot.z))
                            state.bursts.append(Burst(sx, sy, "missile", lifetime=0.8))
                        if shot.pierce > 0:
                            shot.pierce -= 1
                        elif shot in state.projectiles:
                            state.projectiles.remove(shot)
                        break
            else:
                shot.z -= shot.speed * dt
                if shot.z <= 0.075:
                    sx, sy = self._project_normalized(shot.x, shot.y, 0.075)
                    if abs(sx) < 0.16 and abs(sy) < 0.21:
                        self._damage_player(shot.damage, "PLASMA STRIKE // EVADE")
                    if shot in state.projectiles:
                        state.projectiles.remove(shot)
            if shot in state.projectiles and (shot.ttl <= 0.0 or shot.z > 1.55):
                state.projectiles.remove(shot)

        for pickup in list(state.pickups):
            pickup.z -= (0.11 + state.speed * 0.06) * dt
            pickup.spin += dt * 3.0
            if pickup.z <= 0.095:
                sx, sy = self._project_normalized(pickup.x, pickup.y, 0.095)
                if abs(sx) < 0.2 and abs(sy) < 0.24:
                    self._collect_pickup(pickup)
                state.pickups.remove(pickup)

        if not state.game_over and state.wave_remaining == 0 and not state.enemies and not any(not shot.friendly for shot in state.projectiles):
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
        dt = clamp(dt, 0.0, 0.08)
        if dt <= 0.0:
            return
        instant_fps = min(240.0, 1.0 / dt)
        self._fps_smooth = self._fps_smooth * 0.93 + instant_fps * 0.07
        state.fps = self._fps_smooth
        if state.paused or state.help_visible or state.game_over:
            return

        state.elapsed += dt
        state.impact_flash = max(0.0, state.impact_flash - dt)
        for message in state.messages:
            message.ttl -= dt
        state.messages[:] = [message for message in state.messages if message.ttl > 0.0]

        # Steering has inertia but recenters gently, which feels like piloting rather than a cursor.
        state.heading_x = clamp(state.heading_x + state.velocity_x * dt, -0.48, 0.48)
        state.heading_y = clamp(state.heading_y + state.velocity_y * dt, -0.31, 0.31)
        damping = math.pow(0.13, dt)
        state.velocity_x *= damping
        state.velocity_y *= damping
        state.heading_x *= math.pow(0.82, dt)
        state.heading_y *= math.pow(0.82, dt)

        if state.boosting:
            state.boost_time = max(0.0, state.boost_time - dt)
            state.energy = max(0.0, state.energy - 28.0 * dt)
        else:
            state.boost_time = 0.0
            state.energy = min(100.0, state.energy + 7.5 * dt)

        speed = state.speed
        state.distance += speed * dt * 128.0
        for star in state.stars:
            star.previous_z = star.z
            star.z -= speed * dt * (0.72 + 0.34 * star.magnitude)
            star.twinkle += dt * (1.2 + star.magnitude)
            sx, sy = self._project_normalized(star.x, star.y, star.z)
            if star.z <= 0.035 or abs(sx) > 1.35 or abs(sy) > 1.55:
                self._reset_star(star)

        if state.screen != "playing":
            return

        if state.run_mode in ("campaign", "endless"):
            self._update_combat(dt)
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

        for burst in state.bursts:
            burst.age += dt
        state.bursts[:] = [burst for burst in state.bursts if burst.age < burst.lifetime]


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))
