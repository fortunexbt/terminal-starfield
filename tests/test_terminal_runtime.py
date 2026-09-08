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
import tempfile
import termios
import time
import unittest


class TerminalHarness:
    initial_marker = b"FLIGHT DECK"

    def startup_args(self):
        return ["--no-record"]

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
            [sys.executable, "starfield.py", "--ascii", "--no-color", "--fps", "30", "--stars", "40", "--seed", "7"] + self.startup_args(),
            cwd=Path(__file__).resolve().parents[1], stdin=self.slave, stdout=self.slave,
            stderr=self.slave, env=env, start_new_session=True,
        )
        self.addCleanup(self.stop_child)
        self.output = b""
        self.read_until(self.initial_marker)

    def stop_child(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=3)

    def read_until(self, marker):
        deadline = time.monotonic() + 5
        while marker not in self.output and time.monotonic() < deadline:
            if select.select([self.master], [], [], .1)[0]:
                self.output += os.read(self.master, 65536)
        self.assertTrue(marker in self.output, repr(self.output[-4000:]))

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


class TerminalRuntimeTests(TerminalHarness, unittest.TestCase):
    def test_ship_menu_pause_resume_resize_and_quit(self):
        os.write(self.master, b"\x1b[C\r")
        self.read_until(b"WRAITH // ODYSSEY")
        os.write(self.master, b"p")
        self.read_until(b"FLIGHT SUSPENDED")
        os.write(self.master, b" ")
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", 12, 40, 0, 0))
        self.process.send_signal(signal.SIGWINCH)
        self.read_until(b"SPACE fire F auto M seeker I systems H?")
        frame = self.output.rsplit(b"\x1b[H", 1)[-1].split(b"\r\n")
        self.assertEqual(len(frame), 12)
        self.assertTrue(all(len(row) == 40 for row in frame))
        os.write(self.master, b"q")
        self.read_until(b"\x1b[?1049l")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assert_restored()


class MouseTerminalTests(TerminalHarness, unittest.TestCase):
    def startup_args(self):
        return ["--no-record", "--mouse"]

    def test_fragmented_mouse_systems_and_quit_restore_mouse_modes(self):
        self.assertIn(b"\x1b[?1003h\x1b[?1006h", self.output)
        os.write(self.master, b"\r")
        self.read_until(b"VANGUARD // ODYSSEY")
        os.write(self.master, b"\x1b[<0;40;")
        os.write(self.master, b"12Mi")
        self.read_until(b"SHIP SYSTEMS")
        os.write(self.master, b"iq")
        self.read_until(b"\x1b[?1003l\x1b[?1006l")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assert_restored()

    def test_sigterm_restores_mouse_modes(self):
        self.process.send_signal(signal.SIGTERM)
        self.read_until(b"\x1b[?1003l\x1b[?1006l")
        self.process.wait(timeout=3)
        self.assert_restored()


class DemoTerminalTests(TerminalHarness, unittest.TestCase):
    initial_marker = b"DEMO / ANY KEY TO PILOT"

    def startup_args(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.record_path = Path(temporary.name) / "records.json"
        return ["--demo", "--record-file", str(self.record_path)]

    def test_demo_interrupt_returns_to_title_without_creating_log(self):
        os.write(self.master, b" ")
        self.read_until(b"FLIGHT DECK")
        self.assertFalse(self.record_path.exists())
        self.assertFalse(self.record_path.with_suffix(".json.lock").exists())
        os.write(self.master, b"q")
        self.read_until(b"\x1b[?1049l")
        self.assertEqual(self.process.wait(timeout=3), 0)
        self.assert_restored()

    def test_sigterm_restores_terminal_without_traceback(self):
        self.process.send_signal(signal.SIGTERM)
        self.read_until(b"\x1b[?1049l")
        self.process.wait(timeout=3)
        self.assert_restored()
