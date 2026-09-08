"""Command line and raw-terminal runtime."""

from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import signal
import sys
import termios
import time
import tty
import uuid
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from . import __version__
from .model import GameState, SHIPS, Simulation
from .content import ROUTE_CHOICES
from .pilot import DemoPilot
from .records import FlightLogError, default_record_path, load_records, record_run
from .render import Renderer


ENTER_SCREEN = "\x1b[?1049h\x1b[2J\x1b[H\x1b[?25l\x1b[?7l"
LEAVE_SCREEN = "\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l"


@dataclass(frozen=True)
class MouseEvent:
    button: int
    x: int
    y: int
    released: bool = False


InputEvent = Union[str, MouseEvent]
MOUSE_ON = "\x1b[?1003h\x1b[?1006h"
MOUSE_OFF = "\x1b[?1003l\x1b[?1006l"


class KeyDecoder:
    """Incremental ANSI/SGR decoder with bounded incomplete escape storage."""

    def __init__(self) -> None:
        self.pending = b""
        self.escape_started: Optional[float] = None

    @staticmethod
    def _mouse(sequence: bytes) -> Optional[MouseEvent]:
        if not sequence.startswith(b"\x1b[<") or sequence[-1:] not in (b"M", b"m"):
            return None
        fields = sequence[3:-1].split(b";")
        if len(fields) != 3 or any(not field.isdigit() or len(field) > 5 for field in fields):
            return None
        button, x, y = map(int, fields)
        if 0 <= button <= 255 and 1 <= x <= 65535 and 1 <= y <= 65535:
            return MouseEvent(button, x, y, sequence[-1:] == b"m")
        return None

    def feed(self, data: bytes, now: Optional[float] = None) -> List[InputEvent]:
        now = time.monotonic() if now is None else now
        buffer = self.pending + data
        cursor = 0
        keys: List[InputEvent] = []
        while cursor < len(buffer):
            char = buffer[cursor]
            if char != 27:
                if char < 128:
                    keys.append(chr(char))
                cursor += 1
                self.escape_started = None
                continue
            if self.escape_started is None:
                self.escape_started = now
            if cursor + 1 < len(buffer) and buffer[cursor + 1] not in (ord("["), ord("O")):
                keys.append("ESC")
                cursor += 1
                self.escape_started = None
                continue
            end = next((index for index in range(cursor + 2, min(len(buffer), cursor + 65))
                        if 64 <= buffer[index] <= 126), None)
            if end is not None:
                sequence = buffer[cursor:end + 1]
                mouse = self._mouse(sequence)
                if mouse is not None:
                    keys.append(mouse)
                elif not sequence.startswith(b"\x1b[<"):
                    key = {65: "UP", 66: "DOWN", 67: "RIGHT", 68: "LEFT"}.get(buffer[end])
                    if key:
                        keys.append(key)
                cursor = end + 1
                self.escape_started = None
            elif len(buffer) - cursor > 64:
                # A valid supported sequence is at most a few dozen bytes.
                cursor = len(buffer)
                self.escape_started = None
            elif now - self.escape_started >= 0.04:
                keys.append("ESC")
                cursor = len(buffer)
                self.escape_started = None
            else:
                break
        self.pending = buffer[cursor:]
        return keys


class FlightRecorder:
    """Observe each completed combat run once, outside the simulation."""

    def __init__(self, path: Path, enabled: bool = True):
        self.path = path
        self.enabled = enabled
        self.failed = False
        self.current: Optional[GameState] = None
        self.completed = False
        self.data = {"total_runs": 0, "best": None}
        if enabled:
            try:
                self.data = load_records(path)
            except FlightLogError:
                self.failed = True

    def observe(self, state: GameState) -> None:
        if self.current is not state:
            self.current = state
            self.completed = False
            state.record_status = ""
        if (not state.demo and not self.completed and state.run_mode in ("campaign", "endless") and
                state.screen in ("victory", "game_over")):
            self.completed = True
            if not self.enabled:
                state.record_status = "FLIGHT LOG DISABLED"
            elif not self.failed:
                entry = dict(
                    id=uuid.uuid4().hex, finished_at=datetime.now(timezone.utc).isoformat(),
                    mode=state.run_mode, ship=state.ship_id, seed=state.seed,
                    outcome=state.screen, score=state.score, kills=state.kills,
                    wave=state.wave, best_combo=state.best_combo, seconds=round(state.elapsed, 2),
                    ruleset=__version__, route=list(state.route_history[-32:]),
                    accuracy=round(100 * state.shots_hit / max(1, state.shots_fired), 1),
                    grazes=state.grazes, bosses=state.bosses_defeated,
                )
                try:
                    self.data = record_run(self.path, entry)
                    best = self.data["best"]
                    state.record_status = "NEW PERSONAL BEST" if best and best["id"] == entry["id"] else "FLIGHT LOG SAVED"
                except FlightLogError:
                    self.failed = True
        state.record_best = self.data["best"]["score"] if self.data["best"] else 0
        state.record_runs = self.data["total_runs"]
        if self.failed:
            state.record_status = "FLIGHT LOG UNAVAILABLE"


class TerminalSession(AbstractContextManager):
    """Owns terminal state and guarantees restoration on every exit path."""

    def __init__(self, mouse: bool = False) -> None:
        self.mouse = mouse
        self.fd = sys.stdin.fileno()
        self.settings = None
        self.resize_pending = False
        self.old_winch = None
        self.old_term = None
        self.decoder = KeyDecoder()

    def __enter__(self) -> "TerminalSession":
        self.settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        self.old_winch = signal.getsignal(signal.SIGWINCH)
        self.old_term = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGWINCH, self._on_resize)
        signal.signal(signal.SIGTERM, self._on_terminate)
        sys.stdout.write(ENTER_SCREEN + (MOUSE_ON if self.mouse else ""))
        sys.stdout.flush()
        return self

    def _on_resize(self, _signum: int, _frame: object) -> None:
        self.resize_pending = True

    def _on_terminate(self, _signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.settings is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.settings)
        if self.old_winch is not None:
            signal.signal(signal.SIGWINCH, self.old_winch)
        if self.old_term is not None:
            signal.signal(signal.SIGTERM, self.old_term)
        sys.stdout.write((MOUSE_OFF if self.mouse else "") + LEAVE_SCREEN)
        sys.stdout.flush()

    @staticmethod
    def size() -> Tuple[int, int]:
        size = shutil.get_terminal_size((100, 30))
        return max(20, size.columns), max(8, size.lines)

    def read_keys(self) -> List[InputEvent]:
        data = bytearray()
        while select.select([sys.stdin], [], [], 0.0)[0]:
            chunk = os.read(self.fd, 4096)
            if not chunk:
                break
            data.extend(chunk)
        return self.decoder.feed(bytes(data))


def handle_key(simulation: Simulation, key: str) -> bool:
    """Apply one input event. Return False when the runtime should exit."""
    state = simulation.state
    lower = key.lower()
    if lower in ("q",) or key == "\x03":
        return False
    if state.screen == "title":
        if key == "UP" or lower == "w":
            simulation.move_menu(-1)
        elif key == "DOWN" or lower == "s":
            simulation.move_menu(1)
        elif key == "LEFT" or lower == "a":
            simulation.cycle_ship(-1)
        elif key == "RIGHT" or lower == "d":
            simulation.cycle_ship(1)
        elif lower == "f":
            simulation.toggle_auto_fire()
        elif key in ("\r", "\n", " "):
            return simulation.activate_menu()
        return True
    if state.systems_visible:
        if lower == "i" or key == "ESC":
            state.systems_visible = False
        return True
    if lower == "i" and state.screen in ("playing", "upgrade"):
        state.systems_visible = True
        state.help_visible = False
        return True
    if state.screen == "upgrade":
        if key in ("1", "2", "3"):
            simulation.choose_upgrade(int(key) - 1)
        elif key in ("4", "5", "6"):
            simulation.buy_service({"4": "repair", "5": "missiles", "6": "reroll"}[key])
        return True
    if state.screen == "route":
        if key in ("1", "2", "3"):
            simulation.choose_route(int(key) - 1)
        return True
    if state.screen == "jump":
        return True
    if state.screen in ("game_over", "victory"):
        if lower == "r":
            simulation.restart()
        elif key == "ESC":
            simulation.show_title()
        return True
    if lower in ("h", "?"):
        state.help_visible = not state.help_visible
        state.systems_visible = False
        state.paused = False
        return True
    if key == "ESC":
        state.help_visible = False
        state.systems_visible = False
        state.paused = False
        return True
    if state.help_visible or state.systems_visible:
        return True
    if state.paused and lower not in ("p", "r", "t", "c") and key != " ":
        return True
    if lower == "r":
        simulation.restart()
    elif lower == "p":
        state.paused = not state.paused
    elif key == " ":
        if state.paused:
            state.paused = False
        elif state.run_mode in ("campaign", "endless"):
            simulation.request_fire()
        else:
            simulation.engage_boost()
    elif lower == "b" and state.run_mode in ("campaign", "endless"):
        simulation.engage_boost()
    elif lower == "m" and state.run_mode in ("campaign", "endless"):
        simulation.launch_missile()
    elif lower == "e" and state.run_mode in ("campaign", "endless"):
        simulation.trigger_pulse()
    elif lower == "f" and state.run_mode in ("campaign", "endless"):
        simulation.toggle_auto_fire()
    elif lower == "z" and state.run_mode not in ("campaign", "endless"):
        simulation.toggle_zen()
    elif lower == "t":
        state.trails = not state.trails
        simulation.notify("LIGHT TRAILS // {}".format("ON" if state.trails else "OFF"), "muted", 1.0)
    elif lower == "c":
        simulation.cycle_theme()
    elif key == "UP":
        simulation.change_throttle(0.055)
    elif key == "DOWN":
        simulation.change_throttle(-0.055)
    elif key in ("LEFT", "a"):
        simulation.steer(-1.0, 0.0)
    elif key in ("RIGHT", "d"):
        simulation.steer(1.0, 0.0)
    elif lower == "w":
        simulation.steer(0.0, -1.0)
    elif lower in ("s", "k"):
        simulation.steer(0.0, 1.0)
    elif key in ("1", "2", "3", "4", "5"):
        simulation.density_preset(int(key) - 1)
    elif key == "[":
        simulation.set_density(state.density - 40)
    elif key == "]":
        simulation.set_density(state.density + 40)
    return True


def handle_mouse(simulation: Simulation, event: MouseEvent, width: int, height: int) -> None:
    """The pointer steers the flight vector; the centered sight remains the aim."""
    state = simulation.state
    if state.screen != "playing" or state.paused or state.help_visible or state.systems_visible or state.game_over:
        return
    if event.button & 64:
        simulation.change_throttle(.05 if event.button & 1 == 0 else -.05)
        return
    x = ((event.x - 1) / max(1, width - 1) - .5) * .96
    y = ((event.y - 1) / max(1, height - 1) - .5) * .62
    simulation.aim_at(x, y)
    if not event.released:
        button = event.button & 3
        if button == 0:
            simulation.request_fire()
        elif button == 2:
            simulation.launch_missile()


def run_interactive(args: argparse.Namespace) -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("terminal-starfield needs a TTY. Try --snapshot 100x30 for non-interactive output.", file=sys.stderr)
        return 2
    simulation = Simulation(density=args.stars, seed=args.seed, zen=args.zen, ship=args.ship)
    simulation.state.auto_fire = args.auto_fire or args.demo
    simulation.state.theme_index = args.theme
    simulation.state.trails = not args.no_trails
    if args.zen:
        simulation.start_run("zen")
    elif args.demo:
        simulation.start_run(args.mode or "campaign")
    elif args.mode:
        simulation.start_run(args.mode)
    else:
        simulation.show_title()
    renderer = Renderer(unicode=not args.ascii)
    demo_mode = args.demo
    pilot = DemoPilot()
    recorder = FlightRecorder(args.record_file, enabled=not (args.no_record or demo_mode))
    recorder.observe(simulation.state)
    target_frame = 1.0 / args.fps
    last = time.monotonic()
    running = True
    with TerminalSession(mouse=args.mouse) as terminal:
        while running:
            frame_started = time.monotonic()
            dt = frame_started - last
            last = frame_started
            events = terminal.read_keys()
            if demo_mode and events:
                if any(isinstance(event, str) and event.lower() in ("q", "\x03") for event in events):
                    running = False
                else:
                    demo_mode = False
                    simulation.state.demo = False
                    simulation.show_title()
                    recorder = FlightRecorder(args.record_file, enabled=not args.no_record)
                events = []
            for event in events:
                if isinstance(event, MouseEvent):
                    if args.mouse:
                        handle_mouse(simulation, event, *terminal.size())
                else:
                    running = handle_key(simulation, event)
                if not running:
                    break
            if not running:
                break
            if demo_mode:
                pilot.update(simulation, min(.08, dt))
            simulation.update(dt)
            simulation.state.demo = demo_mode
            recorder.observe(simulation.state)
            width, height = terminal.size()
            output = renderer.frame(simulation.state, width, height, color=not args.no_color)
            sys.stdout.write("\x1b[H" + output)
            sys.stdout.flush()
            delay = target_frame - (time.monotonic() - frame_started)
            if delay > 0.0:
                time.sleep(delay)
    print("Voyage complete // score {:,} // distance {:.1f} AU".format(simulation.state.score, simulation.state.distance))
    return 0


def parse_size(value: str) -> Tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError("size must look like 100x30")
    if not (20 <= width <= 300 and 8 <= height <= 100):
        raise argparse.ArgumentTypeError("snapshot size must be between 20x8 and 300x100")
    return width, height


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="terminal-starfield",
        description="A zero-dependency deep-space flight console for your terminal.",
    )
    parser.add_argument("--stars", type=int, default=260, metavar="N", help="star density, 40–800 (default: 260)")
    parser.add_argument("--fps", type=int, choices=range(15, 121), default=60, metavar="N", help="frame rate, 15–120 (default: 60)")
    parser.add_argument("--seed", type=int, default=None, help="deterministic universe seed")
    parser.add_argument("--ship", choices=tuple(SHIPS), default="vanguard", help="starting ship (default: vanguard)")
    parser.add_argument("--auto-fire", action="store_true", help="automatically fire while a target is aligned (F toggles)")
    parser.add_argument("--mouse", action="store_true", help="SGR mouse steering, left fire, right seeker, wheel throttle")
    parser.add_argument("--demo", action="store_true", help="watch a pilot play; any key returns to flight deck; never recorded")
    parser.add_argument("--theme", type=int, choices=range(4), default=0, metavar="N", help="initial theme, 0–3")
    parser.add_argument("--zen", action="store_true", help="start as a pure starfield without HUD gameplay")
    parser.add_argument("--mode", choices=("campaign", "endless", "voyage", "zen"), help="skip the title and start a mode directly")
    parser.add_argument("--ascii", action="store_true", help="use ASCII-only glyphs")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI color")
    parser.add_argument("--no-trails", action="store_true", help="disable star streaks")
    parser.add_argument("--snapshot", type=parse_size, metavar="WIDTHxHEIGHT", help="render one deterministic frame and exit")
    parser.add_argument("--snapshot-screen", choices=("playing", "title", "upgrade", "game_over", "victory", "route", "jump", "boss", "systems"), default="playing", help="screen to preview with --snapshot")
    parser.add_argument("--state-snapshot", action="store_true", help="print deterministic gameplay state as JSON and exit")
    parser.add_argument("--records", action="store_true", help="print local flight history as JSON and exit")
    parser.add_argument("--record-file", type=Path, default=default_record_path(), metavar="PATH", help="flight log location (default: XDG data directory)")
    parser.add_argument("--no-record", action="store_true", help="disable local flight log reads and writes")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.demo and (args.zen or args.mode in ("zen", "voyage")):
        build_parser().error("--demo supports campaign and endless modes")
    args.stars = max(40, min(800, args.stars))
    args.no_color = args.no_color or "NO_COLOR" in os.environ
    if args.records:
        try:
            print(json.dumps(load_records(args.record_file), indent=2))
        except FlightLogError as error:
            print("Flight log unavailable: {}. Existing data was preserved.".format(error), file=sys.stderr)
            return 2
        return 0
    if args.snapshot or args.state_snapshot:
        width, height = args.snapshot or (100, 30)
        mode = "zen" if args.zen else (args.mode or "campaign")
        simulation = Simulation(density=args.stars, seed=42 if args.seed is None else args.seed, zen=args.zen, ship=args.ship)
        simulation.start_run(mode)
        simulation.state.auto_fire = args.auto_fire
        simulation.state.theme_index = args.theme
        simulation.state.trails = not args.no_trails
        # Advance into an interesting, fully populated moment.
        simulation.advance_time(2200)
        if args.snapshot_screen in ("route", "jump"):
            simulation.state.wave = 6
            simulation.state.screen = "route"
            simulation.state.paused = True
            simulation.state.route_choices = list(ROUTE_CHOICES)
            if args.snapshot_screen == "jump":
                simulation.choose_route(0)
                simulation.advance_time(500)
        elif args.snapshot_screen == "boss":
            simulation.start_run("campaign")
            simulation.state.wave = 10
            simulation._begin_wave()
            simulation._spawn_enemy()
            boss = simulation.state.enemies[0]
            boss.z = .55
            boss.hp = boss.max_hp * .55
            boss.fire_clock = .65
            simulation.state.messages.clear()
            simulation.update(1 / 60)
        elif args.snapshot_screen == "systems":
            simulation.state.systems_visible = True
        if args.snapshot_screen == "title":
            simulation.show_title()
        elif args.snapshot_screen == "upgrade":
            simulation.state.screen = "upgrade"
            simulation.state.paused = True
            simulation.state.upgrade_choices = ["damage", "shield", "reactor"]
        elif args.snapshot_screen in ("game_over", "victory"):
            simulation.state.screen = args.snapshot_screen
            simulation.state.game_over = args.snapshot_screen == "game_over"
            simulation.state.paused = args.snapshot_screen == "victory"
            simulation.state.record_status = "PREVIEW // NOT RECORDED"
        if args.state_snapshot:
            print(simulation.render_game_to_text())
            return 0
        print(Renderer(unicode=not args.ascii).frame(simulation.state, width, height, color=not args.no_color))
        return 0
    try:
        return run_interactive(args)
    except KeyboardInterrupt:
        # TerminalSession has already restored the TTY and alternate screen.
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
