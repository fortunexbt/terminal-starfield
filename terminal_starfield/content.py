"""Shared encounter, route, and refit catalog for Odyssey."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

RGB = Tuple[int, int, int]


@dataclass(frozen=True)
class RouteSpec:
    id: str
    name: str
    subtitle: str
    description: str
    risk: str
    reward: str
    heat_scale: float = 1.0
    plasma_scale: float = 1.0
    salvage_scale: float = 1.0
    enemy_hp_scale: float = 1.0
    repair_bonus: float = 0.0
    palette: RGB = (70, 180, 235)
    world: str = "planet"


ROUTES = {
    "frontier": RouteSpec(
        "frontier", "PALE MERIDIAN", "THE LAST MAPPED SKY",
        "The old beacon still answers. Something beyond it answers back.",
        "Unknown contacts", "Standard salvage", palette=(72, 178, 230), world="planet",
    ),
    "forge": RouteSpec(
        "forge", "EMBER FORGE", "THROUGH THE FURNACE",
        "A broken foundry circles a star that refuses to die.",
        "+25% weapon heat", "+60% score and salvage",
        heat_scale=1.25, salvage_scale=1.6, palette=(245, 136, 61), world="sun",
    ),
    "veil": RouteSpec(
        "veil", "ION VEIL", "LIGHTNING UNDER ICE",
        "The frozen giant hides an ocean of charged dust.",
        "+25% hostile plasma speed", "-30% weapon heat",
        heat_scale=.7, plasma_scale=1.25, palette=(100, 209, 220), world="rings",
    ),
    "graveyard": RouteSpec(
        "graveyard", "TITAN GRAVEYARD", "WHERE FLEETS GO QUIET",
        "Repair drones still tend the bones of an ancient fleet.",
        "+25% enemy hull", "+12 repair after each wave",
        enemy_hp_scale=1.25, repair_bonus=12, palette=(170, 135, 236), world="ruins",
    ),
}
ROUTE_CHOICES = ("forge", "veil", "graveyard")


@dataclass(frozen=True)
class BossSpec:
    id: str
    name: str
    subtitle: str
    shape: str
    attacks: Tuple[str, str, str]


BOSS_PROFILES = {
    "null_engine": BossSpec("null_engine", "THE NULL ENGINE", "A MACHINE BUILT TO ERASE STARS", "engine", ("LANCE", "FAN", "CROSSFIRE")),
    "archon_prime": BossSpec("archon_prime", "ARCHON PRIME", "THE CITADEL HAS LEFT ITS ORBIT", "citadel", ("HAMMER", "GATES", "CRUCIBLE")),
    "void_seraph": BossSpec("void_seraph", "VOID SERAPH", "THE SIGNAL WAS NEVER A DISTRESS CALL", "seraph", ("HALO", "SPIRAL", "CROWN")),
}


def boss_for_sector(sector: int) -> BossSpec:
    return tuple(BOSS_PROFILES.values())[(max(1, sector) - 1) % len(BOSS_PROFILES)]


def attack_offsets(boss_id: str, phase: int, angle: float = 0.0) -> Tuple[Tuple[float, float], ...]:
    """Exact impact-plane offsets, shared by emitted shots and their warning."""
    phase = max(1, min(3, phase))
    if boss_id == "null_engine":
        if phase == 1:
            return ((0.0, 0.0),)
        if phase == 2:
            return tuple((lane * .018, 0.0) for lane in range(-2, 3))
        return ((0.0, 0.0), (-.035, 0.0), (.035, 0.0), (0.0, -.028), (0.0, .028))
    if boss_id == "archon_prime":
        if phase == 1:
            return ((0.0, -.032), (0.0, 0.0), (0.0, .032))
        if phase == 2:
            return tuple((side * .04, row * .025) for side in (-1, 1) for row in range(-2, 3))
        return tuple((lane * .025, row * .025) for lane, row in ((0, 0), (-2, 0), (-1, 0), (1, 0), (2, 0), (0, -2), (0, -1), (0, 1), (0, 2)))
    if boss_id == "void_seraph":
        # A two-position opening rotates with the latched angle. The center shot
        # stops the ring from becoming an invitation to stand still forever.
        count = (8, 10, 12)[phase - 1]
        radius = (.06, .075, .09)[phase - 1]
        ring = tuple((math.cos(angle + i * math.tau / count) * radius,
                      math.sin(angle + i * math.tau / count) * radius * .8)
                     for i in range(count) if i not in (0, 1))
        return ((0.0, 0.0),) + ring
    raise ValueError("unknown boss: {}".format(boss_id))


EXTRA_UPGRADES = {
    "leech": ("SIPHON ARRAY", "kills restore 2 shield per rank", 3),
    "graze": ("EVENT HORIZON", "grazes recharge 8 energy per rank", 2),
    "cascade": ("ARC RELAY", "seeker kills arc 2 damage per rank", 2),
    "echo": ("NOVA ECHO", "nova fabricates 1 seeker per use", 1),
}

REFIT_SERVICES = {
    "repair": ("FIELD REPAIR", 12, "restore 30 shield"),
    "missiles": ("SEEKER CRATE", 10, "supply 3 seekers"),
    "reroll": ("REROUTE DRAFT", 8, "new upgrades; price doubles; twice per wave"),
}

SECTOR_NAMES = ("THE OUTER REACH", "THE SHATTERED ORBIT", "THE LAST TRANSMISSION")
SECTOR_BRIEFS = (
    "NAV // The beacon is ahead. Bring the signal home.",
    "COMMS // These ships were waiting for us. Choose another way through.",
    "COMMS // The signal has your voice. End it at the source.",
)
WAVE_LABELS = ("SCOUT WING", "HUNTER PACK", "HEAVY CONTACT", "STRIKE FLEET", "FLAGSHIP")
