"""Bounded local flight history. Simulation and snapshots never touch this file."""

from __future__ import annotations

import fcntl
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from .model import SHIPS

MAX_LOG_CHARS = 1_000_000
HISTORY_LIMIT = 30
MAX_RECORD_NUMBER = 2 ** 63 - 1


class FlightLogError(Exception):
    """A log is unreadable, invalid, or could not be saved safely."""


def default_record_path() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "terminal-starfield" / "flight-log.json"


def _validate_result(entry: Any) -> None:
    if not isinstance(entry, dict):
        raise FlightLogError("invalid flight entry")
    for key in ("id", "finished_at"):
        value = entry.get(key)
        if not isinstance(value, str) or not 1 <= len(value) <= 80 or not value.isprintable():
            raise FlightLogError("invalid flight entry")
    if (entry.get("mode") not in ("campaign", "endless") or
            not isinstance(entry.get("ship"), str) or entry["ship"] not in SHIPS or
            entry.get("outcome") not in ("game_over", "victory")):
        raise FlightLogError("invalid flight entry")
    for key in ("seed", "score", "kills", "wave", "best_combo"):
        value = entry.get(key)
        if type(value) is not int or (key != "seed" and not 0 <= value <= MAX_RECORD_NUMBER):
            raise FlightLogError("invalid flight entry")
    seconds = entry.get("seconds")
    # Check range before math.isfinite converts arbitrary-size integers to float.
    if (type(seconds) not in (int, float) or not 0 <= seconds <= MAX_RECORD_NUMBER or
            not math.isfinite(seconds)):
        raise FlightLogError("invalid flight duration")


def load_records(path: Path) -> Dict[str, Any]:
    """Read without creating anything. Refuse malformed data instead of erasing it."""
    try:
        with Path(path).open("r", encoding="utf-8") as source:
            raw = source.read(MAX_LOG_CHARS + 1)
    except FileNotFoundError:
        return {"version": 1, "total_runs": 0, "best": None, "history": []}
    except (OSError, UnicodeError) as error:
        raise FlightLogError("cannot read flight log") from error
    try:
        if len(raw) > MAX_LOG_CHARS:
            raise FlightLogError("flight log is too large")
        data = json.loads(raw)
        if (not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1 or
                type(data.get("total_runs")) is not int or not 0 <= data["total_runs"] <= MAX_RECORD_NUMBER or
                not isinstance(data.get("history"), list) or len(data["history"]) > HISTORY_LIMIT or
                "best" not in data or data["total_runs"] < len(data["history"])):
            raise FlightLogError("invalid flight log")
        if data["best"] is not None:
            _validate_result(data["best"])
        for entry in data["history"]:
            _validate_result(entry)
        return data
    except (ValueError, TypeError, RecursionError) as error:
        raise FlightLogError("invalid flight log") from error


def record_run(path: Path, entry: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize writers, merge fresh history, then replace the file atomically."""
    _validate_result(entry)
    path = Path(path)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = load_records(path)
            if any(previous["id"] == entry["id"] for previous in data["history"]):
                return data
            if data["total_runs"] == MAX_RECORD_NUMBER:
                raise FlightLogError("flight count limit reached")
            data["total_runs"] += 1
            data["history"] = [dict(entry)] + data["history"][:HISTORY_LIMIT - 1]
            if data["best"] is None or entry["score"] > data["best"]["score"]:
                data["best"] = dict(entry)
            fd, temporary = tempfile.mkstemp(prefix="flight-", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as destination:
                json.dump(data, destination, indent=2, allow_nan=False)
                destination.write("\n")
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, path)
            temporary = None
            return data
    except (OSError, ValueError) as error:
        raise FlightLogError("cannot save flight log") from error
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
