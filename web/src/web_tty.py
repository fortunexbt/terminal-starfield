"""Browser stand-in for TerminalSession: xterm.js supplies the bytes and the size."""

import time

from terminal_starfield.cli import ENTER_SCREEN, LEAVE_SCREEN, MOUSE_OFF, MOUSE_ON, Flight, KeyDecoder, build_parser


class BrowserTTY:
    def __init__(self, argv):
        self.args = build_parser().parse_args(list(argv))
        self.flight = Flight(self.args)
        self.decoder = KeyDecoder()
        self.last = time.monotonic()
        self.saved_runs = self.flight.recorder.data["total_runs"]

    def open(self):
        return ENTER_SCREEN + (MOUSE_ON if self.args.mouse else "")

    def close(self):
        return (MOUSE_OFF if self.args.mouse else "") + LEAVE_SCREEN + self.flight.farewell()

    def step(self, data, width, height):
        """Return the next frame, or None once the player quits."""
        now = time.monotonic()
        dt, self.last = now - self.last, now
        return self.flight.step(self.decoder.feed(data.encode(), now), dt, width, height)

    def log_changed(self):
        runs = self.flight.recorder.data["total_runs"]
        changed, self.saved_runs = runs != self.saved_runs, runs
        return changed
