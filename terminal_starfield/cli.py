"""Command line and raw-terminal runtime."""

from __future__ import annotations

import argparse
import os
import select
import shutil
import signal
import sys
import termios
import time
import tty
from contextlib import AbstractContextManager
from typing import List, Optional, Tuple

from . import __version__
from .model import Simulation
from .render import Renderer


ENTER_SCREEN = "\x1b[?1049h\x1b[2J\x1b[H\x1b[?25l\x1b[?7l"
LEAVE_SCREEN = "\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l"


class TerminalSession(AbstractContextManager):
    """Owns terminal state and guarantees restoration on every exit path."""

    def __init__(self) -> None:
        self.fd = sys.stdin.fileno()
        self.settings = None
        self.resize_pending = False
        self.old_winch = None
        self.old_term = None

    def __enter__(self) -> "TerminalSession":
        self.settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        self.old_winch = signal.getsignal(signal.SIGWINCH)
        self.old_term = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGWINCH, self._on_resize)
        signal.signal(signal.SIGTERM, self._on_terminate)
        sys.stdout.write(ENTER_SCREEN)
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
        sys.stdout.write(LEAVE_SCREEN)
        sys.stdout.flush()

    @staticmethod
    def size() -> Tuple[int, int]:
        size = shutil.get_terminal_size((100, 30))
        return max(20, size.columns), max(8, size.lines)

    def read_keys(self) -> List[str]:
        keys: List[str] = []
        while select.select([sys.stdin], [], [], 0.0)[0]:
            char = os.read(self.fd, 1)
            if not char:
                break
            if char == b"\x1b":
                sequence = char
                deadline = time.monotonic() + 0.004
                while time.monotonic() < deadline and select.select([sys.stdin], [], [], 0.001)[0]:
                    sequence += os.read(self.fd, 1)
                    if len(sequence) >= 6:
                        break
                keys.append({b"\x1b[A": "UP", b"\x1b[B": "DOWN", b"\x1b[C": "RIGHT", b"\x1b[D": "LEFT"}.get(sequence, "ESC"))
            else:
                try:
                    keys.append(char.decode("utf-8"))
                except UnicodeDecodeError:
                    continue
        return keys


def handle_key(simulation: Simulation, key: str) -> bool:
    """Apply one input event. Return False when the runtime should exit."""
    state = simulation.state
    lower = key.lower()
    if lower in ("q",) or key == "\x03":
        return False
    if state.screen == "title":
        if key in ("UP", "w"):
            simulation.move_menu(-1)
        elif key in ("DOWN", "s"):
            simulation.move_menu(1)
        elif key in ("\r", "\n", " "):
            return simulation.activate_menu()
        return True
    if state.screen == "upgrade":
        if key in "123":
            simulation.choose_upgrade(int(key) - 1)
        return True
    if state.screen in ("game_over", "victory"):
        if lower == "r":
            simulation.restart()
        elif key == "ESC":
            simulation.show_title()
        return True
    if lower in ("h", "?"):
        state.help_visible = not state.help_visible
        state.paused = False
        return True
    if key == "ESC":
        state.help_visible = False
        state.paused = False
        return True
    if state.help_visible:
        return True
    if lower == "r":
        simulation.restart()
    elif lower == "p":
        state.paused = not state.paused
    elif key == " ":
        if state.paused:
            state.paused = False
        elif state.run_mode in ("campaign", "endless"):
            simulation.fire_primary()
        else:
            simulation.engage_boost()
    elif lower == "b" and state.run_mode in ("campaign", "endless"):
        simulation.engage_boost()
    elif lower == "m" and state.run_mode in ("campaign", "endless"):
        simulation.launch_missile()
    elif lower == "e" and state.run_mode in ("campaign", "endless"):
        simulation.trigger_pulse()
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
    elif lower in ("w", "i"):
        simulation.steer(0.0, -1.0)
    elif lower in ("s", "k"):
        simulation.steer(0.0, 1.0)
    elif key in "12345":
        simulation.density_preset(int(key) - 1)
    elif key == "[":
        simulation.set_density(state.density - 40)
    elif key == "]":
        simulation.set_density(state.density + 40)
    return True


def run_interactive(args: argparse.Namespace) -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("terminal-starfield needs a TTY. Try --snapshot 100x30 for non-interactive output.", file=sys.stderr)
        return 2
    simulation = Simulation(density=args.stars, seed=args.seed, zen=args.zen)
    simulation.state.theme_index = args.theme
    simulation.state.trails = not args.no_trails
    if args.zen:
        simulation.start_run("zen")
    elif args.mode:
        simulation.start_run(args.mode)
    else:
        simulation.show_title()
    renderer = Renderer(unicode=not args.ascii)
    target_frame = 1.0 / args.fps
    last = time.monotonic()
    running = True
    with TerminalSession() as terminal:
        while running:
            frame_started = time.monotonic()
            dt = frame_started - last
            last = frame_started
            for key in terminal.read_keys():
                running = handle_key(simulation, key)
                if not running:
                    break
            simulation.update(dt)
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
    parser.add_argument("--theme", type=int, choices=range(4), default=0, metavar="N", help="initial theme, 0–3")
    parser.add_argument("--zen", action="store_true", help="start as a pure starfield without HUD gameplay")
    parser.add_argument("--mode", choices=("campaign", "endless", "voyage", "zen"), help="skip the title and start a mode directly")
    parser.add_argument("--ascii", action="store_true", help="use ASCII-only glyphs")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI color")
    parser.add_argument("--no-trails", action="store_true", help="disable star streaks")
    parser.add_argument("--snapshot", type=parse_size, metavar="WIDTHxHEIGHT", help="render one deterministic frame and exit")
    parser.add_argument("--state-snapshot", action="store_true", help="print deterministic gameplay state as JSON and exit")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    args.stars = max(40, min(800, args.stars))
    args.no_color = args.no_color or "NO_COLOR" in os.environ
    if args.snapshot or args.state_snapshot:
        width, height = args.snapshot or (100, 30)
        mode = "zen" if args.zen else (args.mode or "campaign")
        simulation = Simulation(density=args.stars, seed=42 if args.seed is None else args.seed, zen=args.zen)
        simulation.start_run(mode)
        simulation.state.theme_index = args.theme
        simulation.state.trails = not args.no_trails
        # Advance into an interesting, fully populated moment.
        simulation.advance_time(2200)
        if args.state_snapshot:
            print(simulation.render_game_to_text())
            return 0
        print(Renderer(unicode=not args.ascii).frame(simulation.state, width, height, color=not args.no_color))
        return 0
    return run_interactive(args)


if __name__ == "__main__":
    raise SystemExit(main())
