#!/usr/bin/env python3
"""Restores and saves persistent Control Center states (Bluetooth, Brightness, Night Mode, Airplane Mode)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

PERSIST_STATE_FILE = os.path.join(
    os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
    "control-center-state.json",
)
NIGHT_STATE_FILE = "/tmp/waybar-night-mode.json"
NIGHT_TEMP = 4000

ENV_C = {**os.environ, "LC_ALL": "C"}


def run(cmd: list[str], timeout: int = 8) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=ENV_C,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 1, "", str(exc)


def load_state() -> dict:
    if not os.path.exists(PERSIST_STATE_FILE):
        return {}
    try:
        with open(PERSIST_STATE_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(updates: dict) -> None:
    data = load_state()
    data.update(updates)
    try:
        os.makedirs(os.path.dirname(PERSIST_STATE_FILE), exist_ok=True)
        tmp = f"{PERSIST_STATE_FILE}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, PERSIST_STATE_FILE)
    except OSError:
        pass


def session_id() -> str:
    return os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or os.environ.get("XDG_SESSION_ID") or "session"


def write_night_session_file(on: bool) -> None:
    try:
        with open(NIGHT_STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"on": on, "session": session_id()}, fh)
    except OSError:
        pass


def restore_brightness(pct: int) -> None:
    if not shutil.which("brightnessctl"):
        return
    pct = max(5, min(100, int(pct)))
    run(["brightnessctl", "set", f"{pct}%"])


def restore_airplane() -> None:
    if shutil.which("nmcli"):
        run(["nmcli", "radio", "all", "off"])
    if shutil.which("bluetoothctl"):
        run(["bluetoothctl", "power", "off"], timeout=4)
    if shutil.which("rfkill"):
        run(["rfkill", "block", "wifi"])
        run(["rfkill", "block", "bluetooth"])


def restore_bluetooth(on: bool) -> None:
    if on:
        if shutil.which("rfkill"):
            run(["rfkill", "unblock", "bluetooth"])
        time.sleep(0.2)
        if shutil.which("bluetoothctl"):
            run(["bluetoothctl", "power", "on"], timeout=5)
    else:
        if shutil.which("bluetoothctl"):
            run(["bluetoothctl", "power", "off"], timeout=4)
        if shutil.which("rfkill"):
            run(["rfkill", "block", "bluetooth"])


def restore_night(on: bool) -> None:
    if not shutil.which("hyprsunset"):
        return

    if on:
        # Wait briefly for Hyprland's autostart `hyprsunset --identity` so we don't race with it
        running = False
        for _ in range(12):
            rc, _, _ = run(["pgrep", "-x", "hyprsunset"])
            if rc == 0:
                running = True
                break
            time.sleep(0.25)

        if running:
            time.sleep(0.2)
            rc, _, _ = run(["hyprctl", "hyprsunset", "temperature", str(NIGHT_TEMP)])
            if rc != 0:
                run(["pkill", "-x", "hyprsunset"])
                time.sleep(0.1)
                running = False

        if not running:
            subprocess.Popen(
                ["hyprsunset", "-t", str(NIGHT_TEMP)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        write_night_session_file(True)
    else:
        rc, _, _ = run(["pgrep", "-x", "hyprsunset"])
        if rc == 0:
            run(["hyprctl", "hyprsunset", "identity"])
        write_night_session_file(False)


def save_current_brightness() -> None:
    if not shutil.which("brightnessctl"):
        return
    rc1, cur, _ = run(["brightnessctl", "g"])
    rc2, mx, _ = run(["brightnessctl", "m"])
    if rc1 != 0 or rc2 != 0:
        return
    try:
        c, m = int(cur.strip()), int(mx.strip())
        if m > 0:
            pct = max(5, min(100, round(c * 100 / m)))
            save_state({"brightness": pct})
    except ValueError:
        pass


def do_restore() -> None:
    state = load_state()
    if not state:
        return

    if "brightness" in state and isinstance(state["brightness"], (int, float)):
        restore_brightness(int(state["brightness"]))

    if state.get("airplane") is True:
        restore_airplane()
    elif "bt" in state and isinstance(state["bt"], bool):
        restore_bluetooth(state["bt"])

    if "night" in state and isinstance(state["night"], bool):
        restore_night(state["night"])


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else "--restore"
    if arg == "--restore":
        do_restore()
    elif arg == "--save-brightness":
        save_current_brightness()
    else:
        print(f"Uso: {sys.argv[0]} [--restore|--save-brightness]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
