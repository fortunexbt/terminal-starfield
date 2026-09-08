"""Exercise real terminal setup, input, resizing, and cleanup on supported OSes."""

import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
import time
import unittest


class TerminalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.master, self.slave = pty.openpty()
        self.addCleanup(os.close, self.master)
        self.addCleanup(os.close, self.slave)
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        self.settings = termios.tcgetattr(self.slave)
        env = dict(os.environ, TERM="xterm-256color", PYTHONDONTWRITEBYTECODE="1")
        env.pop("COLUMNS", None)
        env.pop("LINES", None)
        self.process = subprocess.Popen(
            [sys.executable, "starfield.py", "--no-record", "--ascii", "--no-color", "--fps", "30", "--stars", "40", "--seed", "7"],
            cwd=Path(__file__).resolve().parents[1], stdin=self.slave, stdout=self.slave,
            stderr=self.slave, env=env, start_new_session=True,
        )
        self.addCleanup(self.stop_child)
        self.output = b""
        self.read_until(b"FLIGHT DECK")

    def stop_child(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=3)

    def read_until(self, marker):
        deadline = time.monotonic() + 5
        while marker not in self.output and time.monotonic() < deadline:
            if select.select([self.master], [], [], .1)[0]:
                self.output += os.read(self.master, 65536)
        self.assertIn(marker, self.output)

    def assert_restored(self):
        while select.select([self.master], [], [], 0)[0]:
            self.output += os.read(self.master, 65536)
        settings = termios.tcgetattr(self.slave)
        # macOS sets its pending-input bookkeeping flag on tcsetattr itself.
        settings[3] &= ~getattr(termios, "PENDIN", 0)
        expected = list(self.settings)
        expected[3] &= ~getattr(termios, "PENDIN", 0)
        self.assertEqual(settings, expected)
        self.assertNotIn(b"Traceback", self.output)

    def test_ship_menu_pause_resume_resize_and_quit(self):
        os.write(self.master, b"\x1b[C\r")
        self.read_until(b"WRAITH // ROGUE")
        os.write(self.master, b"p")
        self.read_until(b"FLIGHT SUSPENDED")
        os.write(self.master, b" ")
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", 12, 40, 0, 0))
        self.process.send_signal(signal.SIGWINCH)
        self.read_until(b"SPACE fire  M seeker")
        frame = self.output.rsplit(b"\x1b[H", 1)[-1].split(b"\r\n")
        self.assertEqual(len(frame), 12)
        self.assertTrue(all(len(row) == 40 for row in frame))
        os.write(self.master, b"q")
        self.read_until(b"\x1b[?1049l")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assert_restored()

    def test_sigterm_restores_terminal_without_traceback(self):
        self.process.send_signal(signal.SIGTERM)
        self.read_until(b"\x1b[?1049l")
        self.process.wait(timeout=3)
        self.assert_restored()
