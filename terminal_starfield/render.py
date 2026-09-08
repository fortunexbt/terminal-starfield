"""ANSI renderer for the flight console."""

from __future__ import annotations

import math
import re
import textwrap
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .model import GameState, SHIPS, Simulation, clamp

RGB = Tuple[int, int, int]

# Normalize at the canvas boundary: boxes, overlays and future glyphs all obey
# --ascii, with one output cell for each input cell.
ASCII_GLYPHS = {
    **dict.fromkeys("┌┐└┘├┤┬┴┼╬", "+"),
    **dict.fromkeys("─━═", "-"),
    **dict.fromkeys("│┃║", "|"),
    **dict.fromkeys("·∙•…", "."),
    **dict.fromkeys("✦✧", "*"),
    **dict.fromkeys("▓█▣", "#"),
    "░": ".", "○": "o", "●": "o", "◇": "o", "◆": "O",
    "△": "^", "▲": "^", "▽": "v", "▼": "V", "▶": ">",
    "‹": "<", "›": ">", "⌃": "^", "⌄": "v", "↑": "^",
    "↓": "v", "←": "<", "→": ">", "╲": "\\", "╱": "/",
    "⚡": "E", "➤": ">", "—": "-", "–": "-",
}


SHIP_SCHEMATICS = {
    "vanguard": (
        "             /\\",
        "            /::\\",
        "       __  /|  |\\  __",
        "      / /_/ |[]| \\_\\ \\",
        "     /____.-|  |-.____\\",
        "         /__|__|__\\",
        "           / || \\",
        "             ::",
    ),
    "wraith": (
        "             /\\",
        "            /||\\",
        "           / || \\",
        "          /  []  \\",
        "      ___/.-||||-.\\___",
        "       \\____/||\\____/",
        "            /__\\",
        "            :  :",
    ),
    "aegis": (
        "          ___/\\___",
        "      ___/   ||   \\___",
        "     | [] | /__\\ | [] |",
        "     |____| |[]| |____|",
        "       \\  \\_|__|_/  /",
        "       |___|_||_|___|",
        "         ||  ||  ||",
        "         ::  ::  ::",
    ),
}


@dataclass(frozen=True)
class Theme:
    name: str
    accent: RGB
    hot: RGB
    danger: RGB
    warning: RGB
    muted: RGB
    far: RGB
    near: RGB
    nebula: RGB


THEMES = (
    Theme("CYAN//VOID", (72, 238, 255), (255, 255, 255), (255, 70, 98), (255, 196, 74), (72, 108, 126), (55, 86, 130), (210, 247, 255), (44, 30, 100)),
    Theme("SOLAR//FLARE", (255, 190, 66), (255, 245, 200), (255, 72, 40), (255, 218, 92), (128, 91, 73), (105, 53, 68), (255, 232, 168), (104, 36, 52)),
    Theme("ION//STORM", (170, 110, 255), (246, 228, 255), (255, 58, 159), (94, 242, 214), (96, 76, 137), (55, 50, 112), (237, 212, 255), (56, 29, 105)),
    Theme("MONO//SIGNAL", (220, 230, 232), (255, 255, 255), (255, 255, 255), (222, 222, 222), (105, 112, 115), (75, 80, 82), (245, 245, 245), (45, 48, 50)),
)


@dataclass
class Cell:
    char: str = " "
    color: Optional[RGB] = None
    style: str = ""
    priority: int = 0


class Canvas:
    def __init__(self, width: int, height: int, unicode: bool = True):
        self.width = max(1, width)
        self.height = max(1, height)
        self.unicode = unicode
        self.rows: List[List[Cell]] = [[Cell() for _ in range(self.width)] for _ in range(self.height)]

    def put(self, x: int, y: int, char: str, color: Optional[RGB] = None, style: str = "", priority: int = 1) -> None:
        if 0 <= x < self.width and 0 <= y < self.height and char and priority >= self.rows[y][x].priority:
            glyph = char[0]
            if not self.unicode and not glyph.isascii():
                glyph = ASCII_GLYPHS.get(glyph, "?")
            self.rows[y][x] = Cell(glyph, color, style, priority)

    def text(self, x: int, y: int, text: str, color: Optional[RGB] = None, style: str = "", priority: int = 50, clip: bool = True) -> None:
        if not (0 <= y < self.height):
            return
        start = max(0, x) if clip else x
        for index, char in enumerate(text):
            px = x + index
            if px >= start:
                self.put(px, y, char, color, style, priority)

    def line(self, x0: int, y0: int, x1: int, y1: int, char: str, color: Optional[RGB], priority: int) -> None:
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)
        for step in range(steps + 1):
            t = step / steps
            self.put(round(x0 + dx * t), round(y0 + dy * t), char, color, "dim", priority)

    def box(self, x: int, y: int, width: int, height: int, color: RGB, title: str = "", priority: int = 90) -> None:
        if width < 4 or height < 3:
            return
        # Modal surfaces must remain legible over a high-motion starfield.
        for row in range(1, height - 1):
            for column in range(1, width - 1):
                self.put(x + column, y + row, " ", None, "", priority - 1)
        self.text(x, y, "┌" + "─" * (width - 2) + "┐", color, priority=priority)
        for row in range(1, height - 1):
            self.put(x, y + row, "│", color, priority=priority)
            self.put(x + width - 1, y + row, "│", color, priority=priority)
        self.text(x, y + height - 1, "└" + "─" * (width - 2) + "┘", color, priority=priority)
        if title:
            label = " {} ".format(title[: max(0, width - 6)])
            self.text(x + 2, y, label, color, "bold", priority + 1)

    def render(self, color: bool = True) -> str:
        lines: List[str] = []
        reset = "\x1b[0m"
        for row in self.rows:
            parts: List[str] = []
            active = None
            for cell in row:
                signature = (cell.color, cell.style) if color else None
                if color and signature != active:
                    parts.append(reset)
                    codes: List[str] = []
                    if cell.style == "bold":
                        codes.append("1")
                    elif cell.style == "dim":
                        codes.append("2")
                    if cell.color:
                        codes.append("38;2;{};{};{}".format(*cell.color))
                    if codes:
                        parts.append("\x1b[{}m".format(";".join(codes)))
                    active = signature
                parts.append(cell.char)
            if color:
                parts.append(reset)
            lines.append("".join(parts))
        return "\n".join(lines)


def mix(a: RGB, b: RGB, amount: float) -> RGB:
    amount = clamp(amount, 0.0, 1.0)
    return tuple(round(a[i] + (b[i] - a[i]) * amount) for i in range(3))  # type: ignore[return-value]


def project(state: GameState, x: float, y: float, z: float, width: int, top: int, bottom: int) -> Tuple[int, int, float, float]:
    z = max(0.035, z)
    nx = (x - state.heading_x) / z
    ny = (y - state.heading_y) / z
    center_x = (width - 1) / 2.0
    center_y = (top + bottom) / 2.0
    px = round(center_x + nx * width * 0.46)
    py = round(center_y + ny * max(1, bottom - top) * 0.48)
    return px, py, nx, ny


class Renderer:
    def __init__(self, unicode: bool = True):
        self.unicode = unicode

    def frame(self, state: GameState, width: int, height: int, color: bool = True) -> str:
        width = max(20, width)
        height = max(8, height)
        canvas = Canvas(width, height, unicode=self.unicode)
        theme = THEMES[state.theme_index % len(THEMES)]
        compact = width < 72 or height < 20
        combat = state.run_mode in ("campaign", "endless")
        top = 2 if compact else (4 if combat else 3)
        bottom = height - (2 if compact else 3)

        self._nebula(canvas, state, theme, top, bottom)
        self._stars(canvas, state, theme, top, bottom)
        if combat:
            self._pickups(canvas, state, theme, top, bottom)
            self._enemies(canvas, state, theme, top, bottom)
            self._projectiles(canvas, state, theme, top, bottom)
            self._radar(canvas, state, theme, top, bottom)
        self._contacts(canvas, state, theme, top, bottom)
        self._bursts(canvas, state, theme, top, bottom)
        self._reticle(canvas, state, theme, top, bottom)
        if not state.zen and state.screen == "playing":
            self._cockpit(canvas, state, theme, top, bottom)
        self._hud(canvas, state, theme, compact)
        self._banner(canvas, state, theme, top)
        if combat and state.screen == "playing" and not state.zen:
            self._boss_warning(canvas, state, theme, top, bottom, compact)

        if state.screen == "title":
            self._title(canvas, state, theme)
        elif state.screen == "upgrade":
            self._upgrade(canvas, state, theme)
        elif state.screen == "victory":
            self._victory(canvas, state, theme)
        elif state.help_visible:
            self._help(canvas, state, theme)
        elif state.paused:
            self._modal(canvas, theme, "FLIGHT SUSPENDED", "P / SPACE  RESUME")
        elif state.game_over or state.screen == "game_over":
            self._game_over(canvas, state, theme)
        return canvas.render(color=color)

    def _enemies(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int) -> None:
        glyphs = {
            "scout": ("▽", "▼"),
            "hunter": ("◇", "◆"),
            "frigate": ("╬", "▓"),
            "boss": ("▣", "█"),
        } if self.unicode else {
            "scout": ("v", "V"),
            "hunter": ("x", "X"),
            "frigate": ("#", "#"),
            "boss": ("@", "@"),
        }
        for enemy in sorted(state.enemies, key=lambda item: item.z, reverse=True):
            x, y, _, _ = project(state, enemy.x, enemy.y, enemy.z, canvas.width, top, bottom)
            if not (1 <= x < canvas.width - 1 and top <= y <= bottom):
                continue
            close = 1.0 - clamp(enemy.z / 1.4, 0.0, 1.0)
            color = theme.hot if enemy.flash > 0 else (theme.warning if enemy.kind == "scout" else theme.danger)
            pair = glyphs[enemy.kind]
            canvas.put(x, y, pair[1] if close > 0.58 else pair[0], color, "bold", 58)
            if enemy.kind == "boss" and canvas.width >= 50:
                hull = ("[==@==]", "<##@##>", "{XX@XX}")[enemy.boss_phase - 1]
                canvas.text(x - 3, y, hull, color, "bold", 58)
                canvas.text(x - 2, y - 1, "/-^-\\", color, "dim", 55)
            if close > 0.34 or enemy.kind == "boss":
                canvas.put(x - 2, y, "[", color, "dim", 55)
                canvas.put(x + 2, y, "]", color, "dim", 55)
            if enemy.kind in ("frigate", "boss") and canvas.width >= 72:
                bar_width = 9 if enemy.kind == "boss" else 5
                filled = round(enemy.hp / enemy.max_hp * bar_width)
                bar = ("━" if self.unicode else "=") * filled + ("─" if self.unicode else "-") * (bar_width - filled)
                canvas.text(x - bar_width // 2, y + 1, bar, color, "dim", 54)

    def _projectiles(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int) -> None:
        for shot in state.projectiles:
            x, y, _, _ = project(state, shot.x, shot.y, shot.z, canvas.width, top, bottom)
            if not (0 <= x < canvas.width and top <= y <= bottom):
                continue
            if shot.kind == "missile":
                glyph, color = ("➤" if self.unicode else ">"), theme.warning
            elif shot.friendly:
                glyph, color = ("│" if self.unicode else "|"), theme.accent
            else:
                glyph, color = ("●" if self.unicode else "o"), theme.danger
            canvas.put(x, y, glyph, color, "bold", 62)
            if shot.friendly and shot.z > 0.12:
                old_z = max(0.06, shot.z - shot.speed * 0.035)
                old_x, old_y, _, _ = project(state, shot.x, shot.y, old_z, canvas.width, top, bottom)
                canvas.line(old_x, old_y, x, y, "·" if self.unicode else ".", color, 60)

    def _pickups(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int) -> None:
        icons = {"repair": "+", "energy": "⚡" if self.unicode else "E", "missile": "▲" if self.unicode else "M", "credits": "$"}
        for pickup in state.pickups:
            x, y, _, _ = project(state, pickup.x, pickup.y, pickup.z, canvas.width, top, bottom)
            if 0 <= x < canvas.width and top <= y <= bottom:
                canvas.put(x, y, icons[pickup.kind], theme.accent, "bold", 50)
                if pickup.z < 0.6:
                    canvas.put(x - 1, y, "(", theme.muted, "dim", 49)
                    canvas.put(x + 1, y, ")", theme.muted, "dim", 49)

    def _radar(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int) -> None:
        if canvas.width < 90 or bottom - top < 14 or state.screen != "playing":
            return
        width, height = 17, 7
        x, y = canvas.width - width - 1, top + 1
        canvas.box(x, y, width, height, theme.muted, "RADAR", 64)
        cx, cy = x + width // 2, y + height // 2
        canvas.put(cx, cy, "▲" if self.unicode else "A", theme.accent, "bold", 67)
        for enemy in state.enemies:
            rx = clamp((enemy.x - state.heading_x) / 0.55, -1.0, 1.0)
            ry = clamp((enemy.y - state.heading_y) / 0.36, -1.0, 1.0)
            px = round(cx + rx * (width // 2 - 2))
            py = round(cy + ry * (height // 2 - 1))
            icon = "B" if enemy.kind == "boss" else "•"
            canvas.put(px, py, icon, theme.danger, "bold", 68)
        for pickup in state.pickups:
            rx = clamp((pickup.x - state.heading_x) / 0.55, -1.0, 1.0)
            ry = clamp((pickup.y - state.heading_y) / 0.36, -1.0, 1.0)
            canvas.put(round(cx + rx * (width // 2 - 2)), round(cy + ry * (height // 2 - 1)), "+", theme.accent, "bold", 68)

    def _nebula(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int) -> None:
        if canvas.width < 42 or bottom - top < 12:
            return
        glyphs = "..··:"
        phase = state.elapsed * 0.07
        for y in range(top, bottom + 1):
            for x in range(0, canvas.width, 2):
                wave = math.sin(x * 0.071 + phase) + math.cos(y * 0.19 - phase * 1.7) + math.sin((x + y * 3) * 0.031)
                grain = ((x * 73 + y * 151 + 19) % 97) / 97.0
                if wave > 2.02 and grain > 0.56:
                    canvas.put(x, y, glyphs[(x + y) % len(glyphs)], theme.nebula, "dim", 1)

    def _stars(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int) -> None:
        chars = (".", "·", "∙", "○", "✦") if self.unicode else (".", ".", "+", "o", "*")
        for star in sorted(state.stars, key=lambda item: item.z, reverse=True):
            x, y, nx, ny = project(state, star.x, star.y, star.z, canvas.width, top, bottom)
            if not (0 <= x < canvas.width and top <= y <= bottom):
                continue
            closeness = 1.0 - clamp(star.z / 1.45, 0.0, 1.0)
            index = min(len(chars) - 1, int(closeness * len(chars)))
            shimmer = 0.82 + math.sin(star.twinkle) * 0.18
            temperature = clamp(star.temperature * 0.36 + closeness * 0.82, 0.0, 1.0)
            star_color = mix(theme.far, theme.near, temperature * shimmer)
            priority = 8 + index * 4

            if state.trails and (state.boosting or closeness > 0.53):
                old_x, old_y, _, _ = project(state, star.x, star.y, star.previous_z, canvas.width, top, bottom)
                extension = 2.4 if state.boosting else 1.0
                trail_x = round(x + (old_x - x) * extension)
                trail_y = round(y + (old_y - y) * extension)
                glyph = "·" if self.unicode else "."
                canvas.line(trail_x, trail_y, x, y, glyph, mix(theme.nebula, star_color, 0.44), priority - 1)
            canvas.put(x, y, chars[index], star_color, "bold" if index >= 3 else "", priority)

    def _contacts(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int) -> None:
        for contact in sorted(state.contacts, key=lambda item: item.z, reverse=True):
            x, y, _, _ = project(state, contact.x, contact.y, contact.z, canvas.width, top, bottom)
            if not (1 <= x < canvas.width - 1 and top <= y <= bottom):
                continue
            close = 1.0 - clamp(contact.z / 1.35, 0.0, 1.0)
            if contact.kind == "signal":
                glyphs = ("◇", "◇", "◆") if self.unicode else ("o", "o", "O")
                glyph = glyphs[min(2, int(close * 3))]
                pulse = mix(theme.accent, theme.hot, (math.sin(contact.spin * 2.0) + 1.0) * 0.25)
                canvas.put(x, y, glyph, pulse, "bold", 42)
                if close > 0.42:
                    canvas.put(x - 1, y, "‹" if self.unicode else "<", theme.accent, "dim", 40)
                    canvas.put(x + 1, y, "›" if self.unicode else ">", theme.accent, "dim", 40)
            else:
                frames = ("△", "◇", "▽", "◇") if self.unicode else ("^", "/", "v", "\\")
                glyph = frames[int(contact.spin * 1.7) % len(frames)]
                canvas.put(x, y, glyph, theme.danger, "bold", 43)
                if close > 0.55:
                    canvas.put(x - 1, y, "!", theme.warning, "bold", 41)
                    canvas.put(x + 1, y, "!", theme.warning, "bold", 41)

    def _bursts(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int) -> None:
        cx = (canvas.width - 1) / 2.0
        cy = (top + bottom) / 2.0
        for burst in state.bursts:
            x = round(cx + burst.x * canvas.width * 0.46)
            y = round(cy + burst.y * max(1, bottom - top) * 0.48)
            radius = 1 + round(burst.progress * 6)
            color = theme.accent if burst.kind in ("signal", "pulse") else (theme.warning if burst.kind in ("enemy", "missile") else theme.danger)
            if burst.kind == "pulse":
                radius = 2 + round(burst.progress * min(14, canvas.width // 5))
            points = ((-radius, 0), (radius, 0), (0, -max(1, radius // 2)), (0, max(1, radius // 2)))
            for dx, dy in points:
                canvas.put(x + dx, y + dy, "✧" if self.unicode else "*", color, "bold", 48)

    def _reticle(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int) -> None:
        if state.zen or state.screen != "playing":
            return
        x = canvas.width // 2
        y = (top + bottom) // 2
        color = theme.hot if state.boosting else theme.accent
        left, right, up, down = ("‹", "›", "⌃", "⌄") if self.unicode else ("<", ">", "^", "v")
        canvas.put(x - 3, y, left, color, "dim", 35)
        canvas.put(x + 3, y, right, color, "dim", 35)
        canvas.put(x, y - 2, up, color, "dim", 35)
        canvas.put(x, y + 2, down, color, "dim", 35)
        canvas.put(x, y, "+", color, "bold", 36)

    def _cockpit(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int) -> None:
        if canvas.width < 50 or bottom - top < 10:
            return
        color = mix(theme.muted, theme.accent, 0.25 if not state.boosting else 0.7)
        y = bottom
        for offset in range(min(12, canvas.width // 7)):
            canvas.put(offset, y - offset // 4, "╲" if self.unicode else "\\", color, "dim", 24)
            canvas.put(canvas.width - 1 - offset, y - offset // 4, "╱" if self.unicode else "/", color, "dim", 24)
        label = " VECTOR {} ".format("LOCK" if state.boosting else "NOMINAL")
        canvas.text((canvas.width - len(label)) // 2, bottom, label, color, "dim", 25)

    def _meter(self, value: float, width: int = 10) -> str:
        filled = round(clamp(value, 0.0, 100.0) / 100.0 * width)
        if self.unicode:
            return "━" * filled + "─" * (width - filled)
        return "#" * filled + "-" * (width - filled)

    def _hud(self, canvas: Canvas, state: GameState, theme: Theme, compact: bool) -> None:
        if state.screen != "playing":
            return
        if state.zen:
            zen = " ZEN DRIFT  ·  Z return  ·  Q exit " if self.unicode else " ZEN DRIFT  |  Z return  |  Q exit "
            canvas.text(max(0, (canvas.width - len(zen)) // 2), canvas.height - 1, zen[:canvas.width], theme.muted, "dim", 70)
            return
        if state.run_mode in ("campaign", "endless"):
            self._combat_hud(canvas, state, theme, compact)
            return
        if canvas.width < 40:
            title = " STARFIELD // S{:02d}".format(state.sector)
            canvas.text(0, 0, title[:canvas.width], theme.accent, "bold", 70)
            micro = "SHD{:03d} ENG{:03d} T{:03d}".format(round(state.shield), round(state.energy), round(state.throttle * 100))
            canvas.text(0, 1, micro[:canvas.width], theme.muted, priority=70)
            controls = " WASD · H help · Q" if self.unicode else " WASD | H help | Q"
            canvas.text(0, canvas.height - 1, controls[:canvas.width], theme.muted, "dim", 70)
            return
        title = " STARFIELD // VOYAGER "
        mode = "BOOST" if state.boosting else "CRUISE"
        canvas.text(0, 0, title[:canvas.width], theme.accent, "bold", 70)
        right = "{:>7} pts  x{}  S{:02d} ".format(state.score, state.multiplier, state.sector)
        canvas.text(max(0, canvas.width - len(right)), 0, right, theme.hot, "bold", 70)

        if compact:
            line = "SPD {:03d}%  SHD {:03d}  ENG {:03d}  {}".format(round(state.throttle * 100), round(state.shield), round(state.energy), mode)
            canvas.text(0, 1, line[:canvas.width], theme.muted, priority=70)
            controls = " WASD fly  ↑↓ throttle  SPACE boost  H help  Q exit "
            if not self.unicode:
                controls = " WASD fly  arrows throttle/steer  SPACE boost  H help  Q exit "
            canvas.text(0, canvas.height - 1, controls[:canvas.width], theme.muted, "dim", 70)
            return

        shield_color = theme.danger if state.shield < 30 else theme.accent
        energy_color = theme.warning if state.energy < 25 else theme.hot
        canvas.text(1, 1, "SHIELD", theme.muted, "dim", 70)
        canvas.text(8, 1, self._meter(state.shield, 12), shield_color, "bold", 70)
        canvas.text(22, 1, "{:03d}".format(round(state.shield)), shield_color, priority=70)
        energy_x = max(28, canvas.width - 27)
        canvas.text(energy_x, 1, "ENERGY", theme.muted, "dim", 70)
        canvas.text(energy_x + 7, 1, self._meter(state.energy, 12), energy_color, "bold", 70)
        canvas.text(energy_x + 20, 1, "{:03d}".format(round(state.energy)), energy_color, priority=70)

        telemetry = "THR {:03d}%  {}  {:08.1f} AU  CAP {:03d}  {:02.0f} FPS".format(round(state.throttle * 100), mode, state.distance, state.captures, state.fps)
        canvas.text(max(0, (canvas.width - len(telemetry)) // 2), 2, telemetry[:canvas.width], theme.muted, "dim", 70)
        controls = " WASD steer · ↑↓ throttle · SPACE boost · T trails · C theme · Z zen · H help · Q exit "
        if not self.unicode:
            controls = controls.replace("·", "|")
        canvas.text(max(0, (canvas.width - len(controls)) // 2), canvas.height - 1, controls[:canvas.width], theme.muted, "dim", 70)

    def _combat_hud(self, canvas: Canvas, state: GameState, theme: Theme, compact: bool) -> None:
        ship = SHIPS[state.ship_id]
        if canvas.width < 40:
            canvas.text(0, 0, " {} // W{:02d}".format(ship.name.upper(), state.wave)[:canvas.width], theme.accent, "bold", 70)
            line = "S{:03d} E{:03d} H{:03d} M{:02d}".format(round(state.shield), round(state.energy), round(state.weapon_heat), state.missiles)
            canvas.text(0, 1, line[:canvas.width], theme.muted, priority=70)
            canvas.text(0, canvas.height - 1, " SPACE fire · H help"[:canvas.width], theme.muted, "dim", 70)
            return
        title = " {} // ROGUE ".format(ship.name.upper())
        right = "{:>8}  x{}  K{:03d} ".format(state.score, state.multiplier, state.kills)
        canvas.text(0, 0, title, theme.accent, "bold", 70)
        canvas.text(max(0, canvas.width - len(right)), 0, right, theme.hot, "bold", 70)
        if compact:
            line = "S {:03d}  E {:03d}  HEAT {:03d}  M {:02d}  WAVE {:02d}".format(round(state.shield), round(state.energy), round(state.weapon_heat), state.missiles, state.wave)
            canvas.text(0, 1, line[:canvas.width], theme.muted, priority=70)
            controls = " SPACE fire  M seeker  E pulse  B boost  H help "
            canvas.text(0, canvas.height - 1, controls[:canvas.width], theme.muted, "dim", 70)
            return
        shield_color = theme.danger if state.shield < state.max_shield * 0.3 else theme.accent
        heat_color = theme.danger if state.overheated else (theme.warning if state.weapon_heat > 65 else theme.muted)
        canvas.text(1, 1, "SHD", theme.muted, "dim", 70)
        canvas.text(5, 1, self._meter(state.shield / state.max_shield * 100, 11), shield_color, "bold", 70)
        canvas.text(17, 1, "{:03d}".format(round(state.shield)), shield_color, priority=70)
        center = max(23, canvas.width // 2 - 9)
        canvas.text(center, 1, "HEAT", theme.muted, "dim", 70)
        canvas.text(center + 5, 1, self._meter(state.weapon_heat, 10), heat_color, "bold", 70)
        energy_x = max(center + 17, canvas.width - 25)
        canvas.text(energy_x, 1, "ENG", theme.muted, "dim", 70)
        canvas.text(energy_x + 4, 1, self._meter(state.energy, 10), theme.hot, "bold", 70)
        canvas.text(energy_x + 15, 1, "{:03d}".format(round(state.energy)), theme.hot, priority=70)
        hostile_count = len(state.enemies) + state.wave_remaining
        pulse = "READY" if state.pulse_cooldown <= 0 else "{:02.0f}s".format(state.pulse_cooldown)
        telemetry = "SECTOR {:02d}  WAVE {:02d}  THREATS {:02d}  MISSILES {:02d}  PULSE {}  {:03d}% THR".format(state.sector, state.wave, hostile_count, state.missiles, pulse, round(state.throttle * 100))
        canvas.text(max(0, (canvas.width - len(telemetry)) // 2), 2, telemetry[:canvas.width], theme.muted, "dim", 70)
        controls = " WASD steer · SPACE fire · M missile · E pulse · B boost · P pause · H help · Q exit "
        if not self.unicode:
            controls = controls.replace("·", "|")
        canvas.text(max(0, (canvas.width - len(controls)) // 2), canvas.height - 1, controls[:canvas.width], theme.muted, "dim", 70)

    def _boss_warning(self, canvas: Canvas, state: GameState, theme: Theme, top: int, bottom: int, compact: bool) -> None:
        boss = next((enemy for enemy in state.enemies if enemy.kind == "boss"), None)
        if boss is None:
            return
        locked = boss.boss_telegraph
        phase = "P{} {}".format(boss.boss_phase, boss.boss_attack)
        if canvas.width < 40:
            label = "{} {}".format("LOCK" if locked else "BOSS", phase)
        elif canvas.width < 72:
            label = "{} // {}".format(phase, "AIM LOCKED // EVADE" if locked else "BOSS TRACKING")
        else:
            bar = self._meter(boss.hp / boss.max_hp * 100, 12)
            label = "{} [{}]  {}  {}".format(state.boss_name or "BOSS", bar, phase, "AIM LOCKED // EVADE" if locked else "TRACKING")
        row = canvas.height - 2 if compact else 3
        canvas.text(0, row, " " * canvas.width, priority=76)
        label = self._fit(label, canvas.width)
        canvas.text((canvas.width - len(label)) // 2, row, label, theme.warning if locked else theme.danger, "bold", 77)
        if not locked:
            return
        # The aim is a committed world coordinate, projected at the player hit
        # plane. Steering moves this mark away from the reticle before impact.
        x, y, _, _ = project(state, boss.aim_x, boss.aim_y, 0.075, canvas.width, top, bottom)
        if top <= y <= bottom and 0 <= x < canvas.width:
            canvas.text(x - 2, y, "[ ! ]", theme.warning, "bold", 79)
            canvas.put(x, y - 1, "v", theme.warning, "bold", 79)
            canvas.put(x, y + 1, "^", theme.warning, "bold", 79)

    def _title(self, canvas: Canvas, state: GameState, theme: Theme) -> None:
        ship = SHIPS[state.ship_id]
        marker = "▶ " if self.unicode else "> "
        records = "BEST {:,}  /  {} FLIGHTS".format(state.record_best, state.record_runs)
        weapons = "PHOTON {:g}/{:g}s   NOVA {:g}/{:g}s   SEEKERS {}".format(ship.primary_damage, ship.primary_cooldown, ship.pulse_damage, ship.pulse_cooldown, ship.missiles)
        if canvas.width < 72 or canvas.height < 24:
            self._clear(canvas)
            width = min(canvas.width, 64)
            x = (canvas.width - width) // 2
            if canvas.height < 12:
                # All four actions stay visible even at 20x8. Ship, seed and
                # records share the two header rows; controls have fixed rows.
                header = "STARFIELD  SEED {}".format(state.seed)
                if width < 32:
                    header = "STARFIELD #{}".format(state.seed)
                canvas.text(x, 0, self._fit(header, width), theme.hot, "bold", 92)
                brief = "{} B{} R{}".format(ship.name.upper(), self._number(state.record_best), self._number(state.record_runs))
                canvas.text(x, 1, self._fit(brief, width), theme.accent, "bold", 92)
                start = 2
            else:
                canvas.text(x, 0, "STARFIELD // FLIGHT DECK"[:width], theme.hot, "bold", 92)
                canvas.text(x, 1, self._fit("< {} >  {}".format(ship.name.upper(), ship.role.upper()), width), theme.accent, "bold", 92)
                canvas.text(x, 2, self._fit("SHIELD {:g}   PHOTON {:g}/{:g}s".format(ship.max_shield, ship.primary_damage, ship.primary_cooldown), width), theme.hot, priority=92)
                canvas.text(x, 3, self._fit("NOVA {:g}/{:g}s   SEEKERS {}".format(ship.pulse_damage, ship.pulse_cooldown, ship.missiles), width), theme.muted, priority=92)
                canvas.text(x, 4, self._fit("SEED {}".format(state.seed), width), theme.muted, priority=92)
                canvas.text(x, 5, self._fit(records, width), theme.muted, priority=92)
                start = 6
                if canvas.height >= 18:
                    for offset, line in enumerate(SHIP_SCHEMATICS[state.ship_id][2:6]):
                        canvas.text(x + max(0, (width - 29) // 2), 7 + offset, line[:width], theme.accent, "dim", 92)
                    start = 12
            for index, text in enumerate(Simulation.MENU_ITEMS):
                selected = index == state.menu_index
                label = (marker if selected else "  ") + text
                canvas.text(x, start + index, self._fit(label, width), theme.accent if selected else theme.muted, "bold" if selected else "", 92)
            canvas.text(x, canvas.height - 2, "A/D ship  ENTER fly"[:width], theme.accent, priority=92)
            canvas.text(x, canvas.height - 1, "W/S mode  Q exit"[:width], theme.muted, priority=92)
            return

        width, height = min(82, canvas.width - 4), 22
        x, y = (canvas.width - width) // 2, (canvas.height - height) // 2
        ship_index = tuple(SHIPS).index(state.ship_id) + 1
        canvas.box(x, y, width, height, theme.accent, "VOIDLINK // FLIGHT DECK", 90)
        logo = "S T A R F I E L D"
        canvas.text(x + (width - len(logo)) // 2, y + 2, logo, theme.hot, "bold", 92)
        subtitle = "R O G U E  /  DEEP SPACE OPERATIONS"
        canvas.text(x + (width - len(subtitle)) // 2, y + 3, subtitle, theme.muted, "dim", 92)
        canvas.text(x + 3, y + 5, "─" * (width - 6), theme.muted, "dim", 92)
        canvas.text(x + 3, y + 6, "01 / SELECT HULL    {:02d}/{:02d}".format(ship_index, len(SHIPS)), theme.muted, "dim", 92)
        right = x + width // 2 + 2
        canvas.text(right, y + 6, "02 / FLIGHT PLAN", theme.muted, "dim", 92)
        for offset, line in enumerate(SHIP_SCHEMATICS[state.ship_id]):
            canvas.text(x + 3, y + 7 + offset, line, theme.accent if offset < 7 else theme.warning, "bold" if offset == 3 else "dim", 92)
        notes = ("Three sectors. Three flagships.", "Survive the escalating frontier.", "Engines on. Weapons quiet.", "Return to your terminal.")
        for index, text in enumerate(Simulation.MENU_ITEMS):
            selected = index == state.menu_index
            label = (marker if selected else "  ") + text
            canvas.text(right, y + 8 + index * 2, label, theme.accent if selected else theme.muted, "bold" if selected else "", 92)
            if selected:
                canvas.text(right + 2, y + 9 + index * 2, self._fit(notes[index], x + width - right - 4), theme.hot, "dim", 92)
        identity = "{}  //  {}".format(ship.name.upper(), ship.role.upper())
        canvas.text(x + 3, y + 16, self._fit(identity, width - 6), theme.hot, "bold", 92)
        stats = "SHIELD {:g}   {}".format(ship.max_shield, weapons)
        canvas.text(x + 3, y + 17, self._fit(stats, width - 6), theme.accent, priority=92)
        canvas.text(x + 3, y + 18, self._fit(ship.description, width - 6), theme.muted, "dim", 92)
        footer = "SEED {}   |   {}".format(state.seed, records)
        canvas.text(x + 3, y + 19, self._fit(footer, width - 6), theme.muted, priority=92)
        controls = "A/D hull   W/S or ↑/↓ mode   ENTER deploy   Q exit"
        canvas.text(x + (width - len(controls)) // 2, y + 20, controls, theme.accent, priority=92)

    @staticmethod
    def _fit(text: str, width: int) -> str:
        width = max(0, width)
        return text if len(text) <= width else text[:max(0, width - 1)] + ("~" if width else "")

    @staticmethod
    def _number(value: int) -> str:
        if value < 1000:
            return str(value)
        if value < 1000000:
            return "{:g}k".format(round(value / 1000, 1))
        return "{:g}m".format(round(value / 1000000, 1))

    @staticmethod
    def _clear(canvas: Canvas) -> None:
        for y in range(canvas.height):
            canvas.text(0, y, " " * canvas.width, priority=90)

    def _upgrade(self, canvas: Canvas, state: GameState, theme: Theme) -> None:
        if canvas.width < 52 or canvas.height < 18:
            self._clear(canvas)
            canvas.text(0, 0, "WAVE {:02d} // REFIT".format(state.wave)[:canvas.width], theme.accent, "bold", 92)
            descriptions = canvas.height >= 11
            start, stride = (2, 2) if descriptions else (2, 1)
            for index, key in enumerate(state.upgrade_choices[:3]):
                name, description = Simulation.UPGRADE_INFO[key]
                label = "[{}] {}".format(index + 1, name)
                canvas.text(0, start + index * stride, self._fit(label, canvas.width), theme.hot, "bold", 92)
                if descriptions:
                    canvas.text(4, start + index * stride + 1, self._fit(description, canvas.width - 4), theme.muted, priority=92)
            canvas.text(0, canvas.height - 2, "1 / 2 / 3  INSTALL"[:canvas.width], theme.accent, "bold", 92)
            canvas.text(0, canvas.height - 1, "CHOOSE ONE UPGRADE"[:canvas.width], theme.muted, priority=92)
            return
        width = min(78, canvas.width - 2)
        height = min(20, canvas.height - 2)
        x = (canvas.width - width) // 2
        y = (canvas.height - height) // 2
        canvas.box(x, y, width, height, theme.accent, "WAVE CLEAR // CHOOSE ONE", 90)
        canvas.text(x + 3, y + 2, "The ship learns. The void escalates.", theme.muted, "dim", 92)
        stride = 4 if height >= 19 else 3
        for index, key in enumerate(state.upgrade_choices[:3]):
            row = y + 4 + index * stride
            name, description = Simulation.UPGRADE_INFO[key]
            level = state.upgrades.get(key, 0) + 1
            canvas.text(x + 4, row, self._fit("[{}] {}  MK {}".format(index + 1, name, level), width - 8), theme.hot, "bold", 92)
            canvas.text(x + 8, row + 1, self._fit(description, width - 10), theme.muted, priority=92)
        canvas.text(x + 3, y + height - 2, "Press 1, 2, or 3 to install", theme.accent, "bold", 92)

    def _victory(self, canvas: Canvas, state: GameState, theme: Theme) -> None:
        self._debrief(canvas, state, theme, victory=True)

    def _banner(self, canvas: Canvas, state: GameState, theme: Theme, top: int) -> None:
        if state.screen != "playing" or not state.messages or state.help_visible or state.game_over:
            return
        message = state.messages[-1]
        palette: Dict[str, RGB] = {
            "accent": theme.accent,
            "hot": theme.hot,
            "danger": theme.danger,
            "warning": theme.warning,
            "muted": theme.muted,
        }
        text = "[ {} ]".format(message.text)
        canvas.text(max(0, (canvas.width - len(text)) // 2), top + 1, text[:canvas.width], palette.get(message.tone, theme.accent), "bold", 75)

    def _modal(self, canvas: Canvas, theme: Theme, title: str, subtitle: str) -> None:
        if canvas.width < 40 or canvas.height < 12:
            self._clear(canvas)
            canvas.text(0, canvas.height // 2 - 1, self._fit(title, canvas.width), theme.hot, "bold", 92)
            canvas.text(0, canvas.height // 2 + 1, self._fit(subtitle, canvas.width), theme.accent, priority=92)
            return
        width = min(canvas.width - 4, max(len(title), len(subtitle)) + 8)
        height = 7
        x = (canvas.width - width) // 2
        y = (canvas.height - height) // 2
        canvas.box(x, y, width, height, theme.accent, "SYSTEM", 90)
        canvas.text(x + (width - len(title)) // 2, y + 2, title, theme.hot, "bold", 92)
        canvas.text(x + (width - len(subtitle)) // 2, y + 4, subtitle, theme.muted, priority=92)

    def _help(self, canvas: Canvas, state: GameState, theme: Theme) -> None:
        if canvas.width < 60 or canvas.height < 19:
            self._clear(canvas)
            entries = ["WASD steer", "ARROWS throttle"]
            if state.run_mode in ("campaign", "endless"):
                entries.extend(("SPACE/M fire/seeker", "E/B pulse/boost", "P/R pause/replay"))
            else:
                entries.extend(("SPACE boost", "P/R pause/replay", "Z zen drift"))
            entries.extend(("T/C trails/theme", "1-5/[ ] star density"))
            canvas.text(0, 0, "FLIGHT MANUAL"[:canvas.width], theme.accent, "bold", 92)
            for row, line in enumerate(entries[:canvas.height - 2], 1):
                canvas.text(0, row, self._fit(line, canvas.width), theme.hot, priority=92)
            canvas.text(0, canvas.height - 1, "H close  Q exit"[:canvas.width], theme.accent, priority=92)
            return
        width = min(66, canvas.width - 4)
        height = min(19, canvas.height - 2)
        x = (canvas.width - width) // 2
        y = (canvas.height - height) // 2
        canvas.box(x, y, width, height, theme.accent, "FLIGHT MANUAL", 90)
        if state.run_mode in ("campaign", "endless"):
            entries = [
                ("WASD", "steer flight vector"),
                ("↑/↓", "throttle"),
                ("SPACE", "fire photon array"),
                ("M", "launch homing seeker"),
                ("E", "nova pulse (35 energy)"),
                ("B", "vector boost"),
                ("1…5 / [ ]", "star density"),
                ("T / C", "trails / color system"),
                ("P", "suspend flight"),
                ("R", "restart run"),
                ("Q", "return to terminal"),
            ]
        else:
            entries = [
                ("WASD", "steer flight vector"),
                ("↑/↓", "throttle"),
                ("SPACE", "vector boost"),
                ("1…5 / [ ]", "star density"),
                ("T", "toggle light trails"),
                ("C", "cycle color system"),
                ("P", "suspend flight"),
                ("R", "restart voyage"),
                ("Q", "return to terminal"),
            ]
        max_entries = max(1, height - 6)
        for row, (key, action) in enumerate(entries[:max_entries]):
            canvas.text(x + 3, y + 2 + row, key.ljust(16), theme.hot, "bold", 92)
            canvas.text(x + 20, y + 2 + row, action, theme.muted, priority=92)
        if state.run_mode in ("campaign", "endless"):
            footer = "▽ scout  ◆ hunter  ╬ frigate  ▣ boss  H close" if self.unicode else "v scout  X hunter  # frigate  @ boss  H close"
        else:
            footer = "◇ capture signals   △ evade debris   H close" if self.unicode else "O capture signals   ^ evade debris   H close"
        canvas.text(x + 3, y + height - 2, footer[: width - 6], theme.accent, "dim", 92)

    def _game_over(self, canvas: Canvas, state: GameState, theme: Theme) -> None:
        if state.run_mode in ("campaign", "endless"):
            self._debrief(canvas, state, theme, victory=False)
        else:
            self._voyage_debrief(canvas, state, theme)

    def _voyage_debrief(self, canvas: Canvas, state: GameState, theme: Theme) -> None:
        lines = (
            "SIGNALS {}  CHAIN {}".format(state.captures, state.best_combo),
            "DIST {:.1f} AU".format(state.distance),
            "SCORE {:,}".format(state.score),
            "SEED {}".format(state.seed),
        )
        if canvas.width < 52 or canvas.height < 18:
            self._clear(canvas)
            canvas.text(0, 0, "VOYAGE ENDED", theme.danger, "bold", 92)
            for row, line in enumerate(lines, 1):
                canvas.text(0, row, self._fit(line, canvas.width), theme.hot, priority=92)
            canvas.text(0, canvas.height - 3, "NOT RECORDED", theme.muted, priority=92)
            canvas.text(0, canvas.height - 2, "R replay  ESC title", theme.accent, priority=92)
            canvas.text(0, canvas.height - 1, "Q exit", theme.muted, priority=92)
            return
        width, height = min(68, canvas.width - 4), 17
        x, y = (canvas.width - width) // 2, (canvas.height - height) // 2
        canvas.box(x, y, width, height, theme.danger, "VOYAGE DEBRIEF", 90)
        canvas.text(x + (width - 16) // 2, y + 2, "FLIGHT LINK LOST", theme.danger, "bold", 92)
        for row, line in enumerate(lines):
            line = self._fit(line, width - 6)
            canvas.text(x + (width - len(line)) // 2, y + 4 + row * 2, line, theme.hot if row < 2 else theme.muted, priority=92)
        status = "VOYAGE // NOT RECORDED"
        canvas.text(x + (width - len(status)) // 2, y + 13, status, theme.muted, priority=92)
        controls = "R replay  ESC title  Q exit"
        canvas.text(x + (width - len(controls)) // 2, y + 15, controls, theme.accent, priority=92)

    def _debrief(self, canvas: Canvas, state: GameState, theme: Theme, victory: bool) -> None:
        ship = SHIPS[state.ship_id]
        tone = theme.accent if victory else theme.danger
        title = "THE VOID BLINKED FIRST" if victory else "FLIGHT LINK LOST"
        mode = state.run_mode.upper()
        status = state.record_status or "FLIGHT LOG PENDING"
        build = "  /  ".join("{} MK {}".format(Simulation.UPGRADE_INFO[key][0], state.upgrades[key])
                              for key in Simulation.UPGRADE_INFO if state.upgrades.get(key, 0)) or "STOCK LOADOUT"
        if canvas.width < 64 or canvas.height < 22:
            self._clear(canvas)
            width = canvas.width
            if canvas.height < 11:
                lines = [
                    "{} // {}".format("COMPLETE" if victory else "LOST", mode),
                    "{} #{}".format(ship.name.upper(), state.seed),
                    "SCORE {} K{}".format(state.score, state.kills),
                    "W{} CHAIN{} BEST{}".format(state.wave, state.best_combo, self._number(state.record_best)),
                    "BUILD " + build,
                ]
            else:
                lines = [
                    title,
                    "{} // {}".format(mode, ship.name.upper()),
                    "SEED {}".format(state.seed),
                    "SCORE {:,}   KILLS {}".format(state.score, state.kills),
                    "WAVE {}   BEST CHAIN {}".format(state.wave, state.best_combo),
                ]
                build_rows = max(1, canvas.height - 9)
                wrapped = textwrap.wrap("BUILD  " + build, max(1, width))
                lines.extend(wrapped[:build_rows])
                if len(wrapped) > build_rows:
                    lines[-1] = self._fit(lines[-1], max(1, width - 1)) + "+"
                lines.append("BEST {:,} / {} FLIGHTS".format(state.record_best, state.record_runs))
            for row, line in enumerate(lines):
                canvas.text(0, row, self._fit(line, width), tone if row == 0 else theme.hot if row == 3 else theme.muted, "bold" if row == 0 else "", 92)
            canvas.text(0, canvas.height - 3, self._fit(status, width), theme.accent, "bold", 93)
            canvas.text(0, canvas.height - 2, "R replay  ESC title"[:width], theme.hot, priority=93)
            canvas.text(0, canvas.height - 1, "Q exit"[:width], theme.muted, priority=93)
            return

        width, height = min(82, canvas.width - 4), 22
        x, y = (canvas.width - width) // 2, (canvas.height - height) // 2
        canvas.box(x, y, width, height, tone, "FLIGHT DEBRIEF", 90)
        canvas.text(x + (width - len(title)) // 2, y + 2, title, tone, "bold", 92)
        result = "{}  //  {}".format(mode, "CAMPAIGN COMPLETE" if victory else "RUN TERMINATED")
        canvas.text(x + (width - len(result)) // 2, y + 3, result, theme.muted, "dim", 92)
        score = "SCORE {:,}".format(state.score)
        canvas.text(x + (width - len(score)) // 2, y + 5, score, theme.hot, "bold", 92)
        stats = "KILLS {:04d}   WAVE {:02d}   BEST CHAIN {:02d}".format(state.kills, state.wave, state.best_combo)
        canvas.text(x + (width - len(stats)) // 2, y + 6, stats, theme.accent, priority=92)
        canvas.text(x + 3, y + 8, self._fit("HULL  {} // {}".format(ship.name.upper(), ship.role.upper()), width - 6), theme.hot, priority=92)
        canvas.text(x + 3, y + 9, self._fit("SEED  {}   /   DISTANCE {:.1f} AU".format(state.seed, state.distance), width - 6), theme.muted, priority=92)
        canvas.text(x + 3, y + 10, "FINAL BUILD", theme.accent, "bold", 92)
        build_lines = textwrap.wrap(build, width - 6)
        for offset, line in enumerate(build_lines[:5]):
            canvas.text(x + 3, y + 11 + offset, line, theme.muted, priority=92)
        canvas.text(x + 3, y + 17, "PERSONAL BEST {:,}   /   {} RECORDED FLIGHTS".format(state.record_best, state.record_runs)[:width - 6], theme.hot, priority=92)
        canvas.text(x + 3, y + 18, self._fit(status, width - 6), theme.accent, "bold", 92)
        controls = "R replay same seed   ESC flight deck   Q exit"
        canvas.text(x + (width - len(controls)) // 2, y + 20, controls, theme.accent, priority=92)


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)
