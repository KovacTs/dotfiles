#!/usr/bin/env python3
"""Minimalist floating Control Center for Waybar + Hyprland (GTK4 + gtk4-layer-shell)."""

from __future__ import annotations

import atexit
import calendar
import ctypes
import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field

try:
    ctypes.CDLL("libgtk4-layer-shell.so", mode=ctypes.RTLD_GLOBAL)
except OSError:
    pass

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import Gdk, GLib, Graphene, Gtk, Gtk4LayerShell, Pango  # noqa: E402

PID_FILE = "/tmp/waybar-control-center.pid"
KEEP_AWAKE_STATE = "/tmp/waybar-keep-awake.json"
AIRPLANE_PREV_FILE = "/tmp/waybar-airplane-prev.json"
NIGHT_STATE_FILE = "/tmp/waybar-night-mode.json"
PERSIST_STATE_FILE = os.path.join(
    os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
    "control-center-state.json",
)
NIGHT_TEMP = 4000
NIGHT_SHADER = os.path.expanduser("~/.config/hypr/shaders/night-mode.glsl")

CSS = """
window,
window.background,
window.background.cc-backdrop,
window.cc-backdrop {
    background: transparent;
    background-color: transparent;
    background-image: none;
    box-shadow: none;
    border: none;
}

tooltip {
    background-color: rgba(13, 17, 23, 0.96);
    border: 1px solid rgba(137, 180, 250, 0.25);
    border-radius: 8px;
    color: #cdd6f4;
}

.cc-card {
    background-color: rgba(13, 17, 23, 0.96);
    background-image: none;
    border: 1px solid rgba(137, 180, 250, 0.22);
    border-radius: 14px;
    padding: 12px;
    box-shadow: none;
    color: #cdd6f4;
    font-family: "JetBrainsMono Nerd Font Propo", "Adwaita Sans", sans-serif;
    font-size: 11px;
}

.cc-title {
    color: #e6edf3;
    font-size: 11.5px;
    font-weight: 700;
}

.cc-kbd {
    background-color: rgba(49, 50, 68, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    padding: 1px 6px;
    color: #7f849c;
    font-size: 9px;
    font-weight: 600;
}

.cc-awake-chip {
    background-color: rgba(166, 227, 161, 0.14);
    border: 1px solid rgba(166, 227, 161, 0.28);
    border-radius: 999px;
    padding: 1px 7px;
    color: #a6e3a1;
    font-size: 9px;
    font-weight: 700;
}

.divider {
    background-color: rgba(255, 255, 255, 0.06);
    min-height: 1px;
}

button.tile,
button.tile:focus,
button.tile:active {
    background-color: rgba(22, 27, 36, 0.92);
    background-image: none;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 11px;
    padding: 8px 10px;
    color: #cdd6f4;
    box-shadow: none;
    text-shadow: none;
    outline: none;
    transition: background-color 140ms ease, border-color 140ms ease;
}

button.tile:hover {
    background-color: rgba(33, 39, 54, 0.96);
    background-image: none;
    border-color: rgba(255, 255, 255, 0.12);
}

button.tile:disabled {
    opacity: 0.6;
}

.tile-icon {
    background-color: rgba(49, 50, 68, 0.65);
    color: #8b949e;
    border-radius: 999px;
    min-width: 28px;
    min-height: 28px;
    font-size: 13.5px;
    transition: background-color 140ms ease, color 140ms ease;
}

.tile-title {
    color: #e6edf3;
    font-size: 10.8px;
    font-weight: 700;
}

.tile-sub {
    color: #7f849c;
    font-size: 9.2px;
    font-weight: 500;
}

/* Active accent variants per toggle */
button.tile.on-wifi {
    background-color: rgba(203, 166, 247, 0.14);
    border-color: rgba(203, 166, 247, 0.34);
}
button.tile.on-wifi .tile-icon {
    background-color: #cba6f7;
    color: #0d1117;
}
button.tile.on-wifi .tile-sub {
    color: #cba6f7;
}

button.tile.on-bt {
    background-color: rgba(137, 180, 250, 0.14);
    border-color: rgba(137, 180, 250, 0.34);
}
button.tile.on-bt .tile-icon {
    background-color: #89b4fa;
    color: #0d1117;
}
button.tile.on-bt .tile-sub {
    color: #89b4fa;
}

button.tile.on-audio {
    background-color: rgba(229, 192, 123, 0.13);
    border-color: rgba(229, 192, 123, 0.32);
}
button.tile.on-audio .tile-icon {
    background-color: #e5c07b;
    color: #0d1117;
}
button.tile.on-audio .tile-sub {
    color: #e5c07b;
}

button.tile.on-airplane {
    background-color: rgba(243, 139, 168, 0.15);
    border-color: rgba(243, 139, 168, 0.36);
}
button.tile.on-airplane .tile-icon {
    background-color: #f38ba8;
    color: #0d1117;
}
button.tile.on-airplane .tile-sub {
    color: #f38ba8;
}

button.tile.on-night {
    background-color: rgba(250, 179, 135, 0.15);
    border-color: rgba(250, 179, 135, 0.36);
}
button.tile.on-night .tile-icon {
    background-color: #fab387;
    color: #0d1117;
}
button.tile.on-night .tile-sub {
    color: #fab387;
}

button.tile.on-awake {
    background-color: rgba(166, 227, 161, 0.14);
    border-color: rgba(166, 227, 161, 0.36);
}
button.tile.on-awake .tile-icon {
    background-color: #a6e3a1;
    color: #0d1117;
}
button.tile.on-awake .tile-sub {
    color: #a6e3a1;
}

/* Sliders box */
.sliders-box {
    background-color: rgba(22, 27, 36, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 11px;
    padding: 8px 10px;
}

.slider-icon {
    color: #a6adc8;
    font-size: 13px;
    min-width: 18px;
}

.slider-val {
    color: #8b949e;
    font-size: 9.5px;
    min-width: 30px;
}

scale.cc-scale {
    padding: 4px 0;
}

scale.cc-scale trough {
    background-color: rgba(49, 50, 68, 0.90);
    background-image: none;
    border-radius: 999px;
    min-height: 5px;
    border: none;
}

scale.cc-scale highlight {
    background-color: #89b4fa;
    background-image: none;
    border-radius: 999px;
    border: none;
}

scale.cc-scale.vol-scale highlight {
    background-color: #e5c07b;
}

scale.cc-scale.bri-scale highlight {
    background-color: #fab387;
}

scale.cc-scale slider {
    background-color: #e6edf3;
    background-image: none;
    border: none;
    border-radius: 999px;
    min-width: 12px;
    min-height: 12px;
    margin: -4px 0;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.45);
}

.toast-box {
    background-color: rgba(243, 139, 168, 0.14);
    border: 1px solid rgba(243, 139, 168, 0.28);
    border-radius: 8px;
    padding: 5px 8px;
    color: #f38ba8;
    font-size: 9.8px;
}

/* Calendar */
.cal-box {
    background-color: rgba(22, 27, 36, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 11px;
    padding: 8px 10px;
}

button.cal-nav-btn,
button.cal-nav-btn:focus,
button.cal-nav-btn:active {
    background-color: rgba(49, 50, 68, 0.55);
    background-image: none;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    padding: 2px 7px;
    min-width: 22px;
    min-height: 22px;
    color: #cdd6f4;
    font-size: 11px;
    font-weight: 700;
    box-shadow: none;
    text-shadow: none;
    outline: none;
    transition: background-color 140ms ease, border-color 140ms ease;
}

button.cal-nav-btn:hover {
    background-color: rgba(69, 71, 90, 0.78);
    border-color: rgba(137, 180, 250, 0.30);
    color: #e6edf3;
}

button.cal-title-btn,
button.cal-title-btn:focus,
button.cal-title-btn:active {
    background-color: transparent;
    background-image: none;
    border: none;
    border-radius: 7px;
    padding: 2px 8px;
    min-height: 22px;
    color: #e6edf3;
    font-size: 10.6px;
    font-weight: 700;
    box-shadow: none;
    text-shadow: none;
    outline: none;
}

button.cal-title-btn:hover {
    background-color: rgba(255, 255, 255, 0.06);
}

button.cal-title-btn.other-month {
    color: #89b4fa;
}

.cal-weekday {
    color: #89b4fa;
    font-size: 9px;
    font-weight: 700;
    padding: 2px 0;
}

.cal-day {
    color: #bac2de;
    font-size: 9.8px;
    font-weight: 500;
    padding: 3px 0;
    border-radius: 7px;
}

.cal-day-other {
    color: #585b70;
    font-size: 9.4px;
    font-weight: 400;
    padding: 3px 0;
}

.cal-day-today {
    color: #f38ba8;
    font-size: 10px;
    font-weight: 800;
    background-color: rgba(243, 139, 168, 0.16);
    border: 1px solid rgba(243, 139, 168, 0.36);
    border-radius: 7px;
    padding: 2px 0;
}

/* Notification Center */
.notif-section-title {
    color: #e6edf3;
    font-size: 10.8px;
    font-weight: 700;
}

.notif-badge {
    background-color: rgba(137, 180, 250, 0.16);
    border: 1px solid rgba(137, 180, 250, 0.30);
    border-radius: 999px;
    padding: 0px 6px;
    color: #89b4fa;
    font-size: 9px;
    font-weight: 700;
}

button.notif-action-btn,
button.notif-action-btn:focus,
button.notif-action-btn:active {
    background-color: rgba(22, 27, 36, 0.92);
    background-image: none;
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 8px;
    padding: 3px 8px;
    min-height: 0;
    color: #a6adc8;
    font-size: 9.3px;
    font-weight: 600;
    box-shadow: none;
    text-shadow: none;
    outline: none;
    transition: background-color 140ms ease, border-color 140ms ease, color 140ms ease;
}

button.notif-action-btn:hover {
    background-color: rgba(33, 39, 54, 0.96);
    border-color: rgba(255, 255, 255, 0.14);
    color: #e6edf3;
}

button.notif-action-btn:disabled {
    opacity: 0.4;
}

button.notif-action-btn.dnd-active {
    background-color: rgba(243, 139, 168, 0.16);
    border-color: rgba(243, 139, 168, 0.38);
    color: #f38ba8;
}

button.notif-action-btn.dnd-active:hover {
    background-color: rgba(243, 139, 168, 0.24);
    border-color: rgba(243, 139, 168, 0.50);
}

button.notif-clear-btn:hover {
    border-color: rgba(243, 139, 168, 0.32);
    color: #f38ba8;
}

scrolledwindow.notif-scroll {
    background: transparent;
    border: none;
}

scrolledwindow.notif-scroll scrollbar slider {
    background-color: rgba(137, 180, 250, 0.22);
    border-radius: 999px;
    min-width: 4px;
}

scrolledwindow.notif-scroll scrollbar slider:hover {
    background-color: rgba(137, 180, 250, 0.42);
}

.notif-card {
    background-color: rgba(22, 27, 36, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 8px 9px;
    transition: background-color 140ms ease, border-color 140ms ease;
}

.notif-card:hover {
    background-color: rgba(30, 36, 49, 0.95);
    border-color: rgba(255, 255, 255, 0.11);
}

.notif-card.urgency-critical {
    border-color: rgba(243, 139, 168, 0.40);
    background-color: rgba(243, 139, 168, 0.08);
}

.notif-card.urgency-low {
    opacity: 0.84;
}

.notif-app-icon {
    color: #89b4fa;
    font-size: 11px;
}

.notif-card.urgency-critical .notif-app-icon {
    color: #f38ba8;
}

.notif-app-name {
    color: #89b4fa;
    font-size: 9.2px;
    font-weight: 700;
}

.notif-card.urgency-critical .notif-app-name {
    color: #f38ba8;
}

.notif-time {
    color: #6c7086;
    font-size: 8.8px;
    font-weight: 500;
}

.notif-summary {
    color: #e6edf3;
    font-size: 10.3px;
    font-weight: 700;
}

.notif-body {
    color: #a6adc8;
    font-size: 9.6px;
    font-weight: 400;
}

button.notif-icon-btn,
button.notif-icon-btn:focus,
button.notif-icon-btn:active {
    background-color: transparent;
    background-image: none;
    border: none;
    border-radius: 6px;
    padding: 1px 4px;
    min-width: 18px;
    min-height: 18px;
    color: #6c7086;
    font-size: 9.5px;
    box-shadow: none;
    text-shadow: none;
    outline: none;
}

button.notif-icon-btn:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #e6edf3;
}

button.notif-dismiss-btn:hover {
    background-color: rgba(243, 139, 168, 0.16);
    color: #f38ba8;
}

.notif-empty-box {
    background-color: rgba(22, 27, 36, 0.55);
    border: 1px dashed rgba(255, 255, 255, 0.07);
    border-radius: 10px;
    padding: 14px 10px;
}

.notif-empty-icon {
    color: #585b70;
    font-size: 16px;
}

.notif-empty-text {
    color: #7f849c;
    font-size: 9.8px;
    font-weight: 500;
}
"""


_BIDI_RE = re.compile(r"[\u2066-\u2069\u200e\u200f\u202a-\u202e]")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _BIDI_RE.sub("", text)
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    cleaned = re.sub(r"\s*\n\s*", " · ", cleaned.strip())
    return cleaned


def _format_rel_time(timestamp_us: int) -> str:
    if timestamp_us <= 0:
        return ""
    diff = max(0, int(time.monotonic() - (timestamp_us / 1_000_000.0)))
    if diff < 60:
        return "ahora"
    if diff < 3600:
        return f"hace {diff // 60} min"
    if diff < 86400:
        return f"hace {diff // 3600} h"
    return f"hace {diff // 86400} d"


def _app_icon(appname: str) -> str:
    low = (appname or "").lower()
    mapping = [
        (("discord", "vesktop"), "󰙯"),
        (("spotify",), "󰓇"),
        (("zen", "firefox", "chrome", "chromium", "brave"), "󰈹"),
        (("obsidian",), "󱓧"),
        (("telegram",), ""),
        (("whatsapp",), "󰖣"),
        (("steam",), "󰓓"),
        (("ghostty", "kitty", "alacritty", "terminal"), "󰆍"),
        (("code", "vscode", "antigravity"), "󰨞"),
        (("network", "wifi", "nm-"), "󰤨"),
        (("bluetooth",), "󰂯"),
        (("volume", "audio", "pipewire", "pulse"), "󰕾"),
        (("battery", "batería", "bateria", "power", "upower"), "󰁹"),
        (("screenshot", "grim", "slurp"), "󰄀"),
    ]
    for keys, icon in mapping:
        if any(k in low for k in keys):
            return icon
    return "󰂚"


@dataclass
class NotificationItem:
    notif_id: int
    appname: str
    summary: str
    body: str
    timestamp_us: int
    urgency: str = "NORMAL"
    urls: str = ""


@dataclass
class SystemState:
    wifi_on: bool = False
    bt_on: bool = False
    audio_on: bool = True
    volume_pct: int = 50
    airplane_on: bool = False
    night_on: bool = False
    awake_on: bool = False
    has_brightness: bool = False
    brightness_pct: int = 100
    dnd_on: bool = False
    notifications: list[NotificationItem] = field(default_factory=list)


class SystemBackend:
    def __init__(self) -> None:
        self._env = {**os.environ, "LC_ALL": "C"}
        self._persist_lock = threading.Lock()

    def _load_persist(self) -> dict:
        if not os.path.exists(PERSIST_STATE_FILE):
            return {}
        try:
            with open(PERSIST_STATE_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_persist(self, updates: dict) -> None:
        with self._persist_lock:
            data = self._load_persist()
            data.update(updates)
            try:
                os.makedirs(os.path.dirname(PERSIST_STATE_FILE), exist_ok=True)
                tmp = f"{PERSIST_STATE_FILE}.tmp.{os.getpid()}"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2)
                os.replace(tmp, PERSIST_STATE_FILE)
            except OSError:
                pass

    def _run(self, cmd: list[str], timeout: int = 8, c_locale: bool = True) -> tuple[int, str, str]:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=self._env if c_locale else os.environ,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return 1, "", str(exc)

    def _session_id(self) -> str:
        return os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or os.environ.get("XDG_SESSION_ID") or "session"

    # --- Wi-Fi ---
    def get_wifi(self) -> bool:
        rc, out, _ = self._run(["nmcli", "-t", "-f", "WIFI", "general"])
        return rc == 0 and out.strip().lower() == "enabled"

    def set_wifi(self, on: bool) -> tuple[bool, str]:
        if on:
            self._run(["rfkill", "unblock", "wifi"])
        rc, _, err = self._run(["nmcli", "radio", "wifi", "on" if on else "off"])
        if rc == 0 and on:
            self._save_persist({"airplane": False})
        return rc == 0, err.strip()

    # --- Bluetooth ---
    def get_bt(self) -> bool:
        rc, out, _ = self._run(["bluetoothctl", "show"], timeout=3)
        if rc == 0:
            for line in out.splitlines():
                if "Powered:" in line:
                    return "yes" in line.lower()
        return False

    def set_bt(self, on: bool) -> tuple[bool, str]:
        if on:
            self._run(["rfkill", "unblock", "bluetooth"])
            time.sleep(0.15)
            rc, out, err = self._run(["bluetoothctl", "power", "on"], timeout=5)
            if rc != 0 or "no default controller" in (out + err).lower():
                return False, "Bluetooth no disponible (verificá bluetooth.service)"
            self._save_persist({"bt": True, "airplane": False})
            return True, ""
        rc, _, err = self._run(["bluetoothctl", "power", "off"], timeout=5)
        rc2, _, err2 = self._run(["rfkill", "block", "bluetooth"])
        if rc == 0 or rc2 == 0:
            self._save_persist({"bt": False})
            return True, ""
        return False, err2.strip() or err.strip()

    # --- Audio ---
    def get_audio(self) -> tuple[bool, int]:
        rc, out, _ = self._run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        if rc != 0 or not out.strip():
            return True, 50
        muted = "[MUTED]" in out.upper()
        pct = 50
        for tok in out.split():
            try:
                val = float(tok)
                pct = max(0, min(100, round(val * 100)))
                break
            except ValueError:
                continue
        return (not muted), pct

    def set_audio(self, on: bool) -> tuple[bool, str]:
        rc, _, err = self._run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0" if on else "1"])
        return rc == 0, err.strip()

    def set_volume(self, pct: int) -> None:
        pct = max(0, min(100, int(pct)))
        self._run(["wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", f"{pct}%"])

    # --- Brightness ---
    def get_brightness(self) -> tuple[bool, int]:
        rc1, cur, _ = self._run(["brightnessctl", "g"])
        rc2, mx, _ = self._run(["brightnessctl", "m"])
        if rc1 != 0 or rc2 != 0:
            return False, 100
        try:
            c, m = int(cur.strip()), int(mx.strip())
            if m <= 0:
                return False, 100
            return True, max(1, min(100, round(c * 100 / m)))
        except ValueError:
            return False, 100

    def set_brightness(self, pct: int) -> None:
        pct = max(5, min(100, int(pct)))
        rc, _, _ = self._run(["brightnessctl", "set", f"{pct}%"])
        if rc == 0:
            self._save_persist({"brightness": pct})

    # --- Airplane Mode ---
    def get_airplane(self, wifi_on: bool, bt_on: bool) -> bool:
        if wifi_on or bt_on:
            return False
        # Confirm radios are off / soft-blocked
        rc, out, _ = self._run(["rfkill", "-J"])
        if rc == 0 and out.strip():
            try:
                data = json.loads(out)
                devs = data.get("rfkilldevices", [])
                if devs:
                    return all(d.get("soft") == "blocked" for d in devs)
            except Exception:
                pass
        return os.path.exists(AIRPLANE_PREV_FILE) or bool(self._load_persist().get("airplane", False))

    def set_airplane(self, on: bool) -> tuple[bool, str]:
        if on:
            prev = {"wifi": self.get_wifi(), "bt": self.get_bt()}
            try:
                with open(AIRPLANE_PREV_FILE, "w", encoding="utf-8") as fh:
                    json.dump(prev, fh)
            except OSError:
                pass
            self._save_persist({"airplane": True, "airplane_prev": prev})
            self._run(["nmcli", "radio", "all", "off"])
            self._run(["bluetoothctl", "power", "off"], timeout=4)
            self._run(["rfkill", "block", "wifi"])
            self._run(["rfkill", "block", "bluetooth"])
            return True, ""

        prev = {"wifi": True, "bt": False}
        persisted_prev = self._load_persist().get("airplane_prev")
        if isinstance(persisted_prev, dict):
            prev = persisted_prev
        elif os.path.exists(AIRPLANE_PREV_FILE):
            try:
                with open(AIRPLANE_PREV_FILE, encoding="utf-8") as fh:
                    prev = json.load(fh)
            except Exception:
                pass
        try:
            if os.path.exists(AIRPLANE_PREV_FILE):
                os.remove(AIRPLANE_PREV_FILE)
        except OSError:
            pass

        self._run(["rfkill", "unblock", "wifi"])
        self._run(["nmcli", "radio", "all", "on"])
        if not prev.get("wifi", True):
            self._run(["nmcli", "radio", "wifi", "off"])
        if prev.get("bt", False):
            self._run(["rfkill", "unblock", "bluetooth"])
            time.sleep(0.2)
            self._run(["bluetoothctl", "power", "on"], timeout=4)
        else:
            self._run(["bluetoothctl", "power", "off"], timeout=3)
            self._run(["rfkill", "block", "bluetooth"])
        self._save_persist({"airplane": False, "bt": bool(prev.get("bt", False))})
        return True, ""

    # --- Night Mode (hyprsunset daemon + hyprctl hyprsunset IPC) ---
    def _hyprsunset_running(self) -> bool:
        rc, _, _ = self._run(["pgrep", "-x", "hyprsunset"])
        return rc == 0

    def _read_night_file(self) -> bool | None:
        if not os.path.exists(NIGHT_STATE_FILE):
            return None
        try:
            with open(NIGHT_STATE_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("session") == self._session_id():
                return bool(data.get("on", False))
        except Exception:
            pass
        return None

    def _write_night_file(self, on: bool) -> None:
        try:
            with open(NIGHT_STATE_FILE, "w", encoding="utf-8") as fh:
                json.dump({"on": on, "session": self._session_id()}, fh)
        except OSError:
            pass

    def _clear_legacy_shader(self) -> None:
        self._run(["hyprctl", "eval", 'hl.config({ decoration = { screen_shader = "" } })'])

    def _hyprsunset_started_identity(self) -> bool:
        rc, out, _ = self._run(["pgrep", "-x", "hyprsunset"])
        if rc != 0 or not out.strip():
            return False
        pid = out.strip().splitlines()[0].strip()
        try:
            cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", errors="ignore")
            return "--identity" in cmd or "\x00-i\x00" in cmd
        except OSError:
            return False

    def get_night(self) -> bool:
        if shutil.which("hyprsunset"):
            if not self._hyprsunset_running():
                return False
            saved = self._read_night_file()
            if saved is not None:
                return saved
            if self._hyprsunset_started_identity():
                return False
            rc, out, _ = self._run(["hyprctl", "hyprsunset", "temperature"])
            if rc == 0 and out.strip():
                try:
                    temp = int("".join(ch for ch in out.strip() if ch.isdigit()))
                    return temp < 5800
                except ValueError:
                    pass
            return True
        return False

    def set_night(self, on: bool) -> tuple[bool, str]:
        if not shutil.which("hyprsunset"):
            return False, "hyprsunset no está instalado"

        # Ensure any previous GLSL screen_shader does not conflict with hyprsunset
        self._clear_legacy_shader()

        running = self._hyprsunset_running()
        if on:
            if running:
                rc, out, err = self._run(["hyprctl", "hyprsunset", "temperature", str(NIGHT_TEMP)])
                if rc != 0:
                    self._run(["pkill", "-x", "hyprsunset"])
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
                time.sleep(0.25)
            self._write_night_file(True)
            self._save_persist({"night": True})
            return True, ""

        # Turn OFF: switch hyprsunset cleanly to identity (no color tint)
        if running:
            rc, _, _ = self._run(["hyprctl", "hyprsunset", "identity"])
            if rc != 0:
                self._run(["pkill", "-x", "hyprsunset"])
        self._write_night_file(False)
        self._save_persist({"night": False})
        return True, ""

    # --- Keep Awake / Never Lock & Never Suspend (strictly session-only, always OFF on boot/login) ---
    def _read_awake_state(self) -> dict | None:
        if not os.path.exists(KEEP_AWAKE_STATE):
            return None
        try:
            with open(KEEP_AWAKE_STATE, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return None
        pid = data.get("pid")
        sess = data.get("session")
        if not isinstance(pid, int) or sess != self._session_id():
            return None
        cmdline_path = f"/proc/{pid}/cmdline"
        if not os.path.exists(cmdline_path):
            return None
        try:
            cmd = open(cmdline_path, "rb").read().decode("utf-8", errors="ignore")
            if "systemd-inhibit" in cmd or "sleep" in cmd:
                return data
        except OSError:
            pass
        return None

    def get_awake(self) -> bool:
        return self._read_awake_state() is not None

    def set_awake(self, on: bool) -> tuple[bool, str]:
        if on:
            if self.get_awake():
                return True, ""

            # Remember how hypridle was running so we can restore it cleanly when turned off
            rc_sys, out_sys, _ = self._run(["systemctl", "--user", "is-active", "hypridle.service"])
            hypridle_systemd = rc_sys == 0 and out_sys.strip() == "active"
            rc_pg, _, _ = self._run(["pgrep", "-x", "hypridle"])
            hypridle_proc = rc_pg == 0

            # Stop hypridle ONLY for this session (never disables systemd unit across reboots!)
            if hypridle_systemd:
                self._run(["systemctl", "--user", "stop", "hypridle.service"])
            if hypridle_proc:
                self._run(["pkill", "-x", "hypridle"])

            # Hold OS-level idle + sleep + lid-switch inhibitor for this session only
            try:
                proc = subprocess.Popen(
                    [
                        "systemd-inhibit",
                        "--what=idle:sleep:handle-lid-switch",
                        "--who=ControlCenter",
                        "--why=Modo no bloquear activo en esta sesion",
                        "--mode=block",
                        "sleep",
                        "infinity",
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            except FileNotFoundError:
                return False, "systemd-inhibit no está disponible"

            state = {
                "pid": proc.pid,
                "session": self._session_id(),
                "hypridle_systemd": hypridle_systemd,
                "hypridle_proc": hypridle_proc,
            }
            try:
                with open(KEEP_AWAKE_STATE, "w", encoding="utf-8") as fh:
                    json.dump(state, fh)
            except OSError:
                pass
            return True, ""

        # Turn OFF Keep Awake and restore hypridle
        data = self._read_awake_state() or {}
        pid = data.get("pid")
        if isinstance(pid, int):
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except OSError:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
        try:
            if os.path.exists(KEEP_AWAKE_STATE):
                os.remove(KEEP_AWAKE_STATE)
        except OSError:
            pass

        if data.get("hypridle_systemd"):
            self._run(["systemctl", "--user", "start", "hypridle.service"])
        elif data.get("hypridle_proc"):
            subprocess.Popen(
                ["hypridle"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        else:
            # Best-effort: if hypridle.service is enabled, start it back up
            rc_en, out_en, _ = self._run(["systemctl", "--user", "is-enabled", "hypridle.service"])
            if rc_en == 0 and out_en.strip() == "enabled":
                self._run(["systemctl", "--user", "start", "hypridle.service"])
        return True, ""

    # --- Notifications (dunstctl) ---
    def get_dnd(self) -> bool:
        if not shutil.which("dunstctl"):
            return False
        rc, out, _ = self._run(["dunstctl", "is-paused"], timeout=2)
        return rc == 0 and out.strip().lower() == "true"

    def set_dnd(self, on: bool) -> tuple[bool, str]:
        if not shutil.which("dunstctl"):
            return False, "dunstctl no está disponible"
        rc, _, err = self._run(["dunstctl", "set-paused", "true" if on else "false"], timeout=3)
        return rc == 0, err.strip()

    def get_notifications(self) -> list[NotificationItem]:
        if not shutil.which("dunstctl"):
            return []
        rc, out, _ = self._run(["dunstctl", "history"], timeout=3, c_locale=False)
        if rc != 0 or not out.strip():
            return []
        try:
            payload = json.loads(out)
            entries = payload.get("data", [[]])[0]
        except Exception:
            return []

        items: list[NotificationItem] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue

            def _field(name: str, default=""):
                val = entry.get(name)
                if isinstance(val, dict):
                    return val.get("data", default)
                return default

            notif_id = int(_field("id", 0) or 0)
            appname = str(_field("appname", "") or "Sistema").strip()
            summary = _clean_text(str(_field("summary", "") or ""))
            body = _clean_text(str(_field("body", "") or ""))
            timestamp_us = int(_field("timestamp", 0) or 0)
            urgency = str(_field("urgency", "NORMAL") or "NORMAL").upper()
            urls = str(_field("urls", "") or "").strip()

            if not summary and not body:
                continue
            items.append(
                NotificationItem(
                    notif_id=notif_id,
                    appname=appname,
                    summary=summary or appname,
                    body=body,
                    timestamp_us=timestamp_us,
                    urgency=urgency,
                    urls=urls,
                )
            )
        items.sort(key=lambda n: n.timestamp_us, reverse=True)
        return items

    def dismiss_notification(self, notif_id: int) -> None:
        if shutil.which("dunstctl") and notif_id > 0:
            self._run(["dunstctl", "history-rm", str(notif_id)], timeout=2)

    def clear_notifications(self) -> None:
        if shutil.which("dunstctl"):
            self._run(["dunstctl", "close-all"], timeout=2)
            self._run(["dunstctl", "history-clear"], timeout=2)

    def read_all(self) -> SystemState:
        wifi_on = self.get_wifi()
        bt_on = self.get_bt()
        audio_on, vol_pct = self.get_audio()
        airplane_on = self.get_airplane(wifi_on, bt_on)
        night_on = self.get_night()
        awake_on = self.get_awake()
        has_bri, bri_pct = self.get_brightness()
        dnd_on = self.get_dnd()
        notifications = self.get_notifications()
        return SystemState(
            wifi_on=wifi_on,
            bt_on=bt_on,
            audio_on=audio_on,
            volume_pct=vol_pct,
            airplane_on=airplane_on,
            night_on=night_on,
            awake_on=awake_on,
            has_brightness=has_bri,
            brightness_pct=bri_pct,
            dnd_on=dnd_on,
            notifications=notifications,
        )


class ToggleTile(Gtk.Button):
    def __init__(self, title: str, icon_on: str, icon_off: str, active_css: str) -> None:
        super().__init__()
        self.icon_on = icon_on
        self.icon_off = icon_off
        self.active_css = active_css
        self.is_on = False

        self.add_css_class("tile")
        self.set_hexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
        box.set_valign(Gtk.Align.CENTER)

        self.icon_lbl = Gtk.Label(label=icon_off)
        self.icon_lbl.add_css_class("tile-icon")
        self.icon_lbl.set_halign(Gtk.Align.CENTER)
        self.icon_lbl.set_valign(Gtk.Align.CENTER)
        box.append(self.icon_lbl)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)

        self.title_lbl = Gtk.Label(label=title, xalign=0)
        self.title_lbl.add_css_class("tile-title")
        self.title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        text_box.append(self.title_lbl)

        self.sub_lbl = Gtk.Label(label="...", xalign=0)
        self.sub_lbl.add_css_class("tile-sub")
        self.sub_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        text_box.append(self.sub_lbl)

        box.append(text_box)
        self.set_child(box)

    def set_state(self, on: bool, subtitle: str) -> None:
        self.is_on = on
        self.icon_lbl.set_label(self.icon_on if on else self.icon_off)
        self.sub_lbl.set_label(subtitle)
        if on:
            self.add_css_class(self.active_css)
        else:
            self.remove_css_class(self.active_css)


class CalendarWidget(Gtk.Box):
    _MONTHS = (
        "",
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    )
    _WEEKDAYS = ("Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do")

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("cal-box")

        today = datetime.date.today()
        self.view_year = today.year
        self.view_month = today.month
        self._cal = calendar.Calendar(firstweekday=0)

        # Navigation header: prev | Month Year (click -> today) | next
        nav = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        nav.set_valign(Gtk.Align.CENTER)

        prev_btn = Gtk.Button(label="‹")
        prev_btn.add_css_class("cal-nav-btn")
        prev_btn.set_tooltip_text("Mes anterior")
        prev_btn.connect("clicked", lambda _b: self.shift_month(-1))
        nav.append(prev_btn)

        self.title_btn = Gtk.Button(label="")
        self.title_btn.add_css_class("cal-title-btn")
        self.title_btn.set_hexpand(True)
        self.title_btn.connect("clicked", lambda _b: self.go_today())
        nav.append(self.title_btn)

        next_btn = Gtk.Button(label="›")
        next_btn.add_css_class("cal-nav-btn")
        next_btn.set_tooltip_text("Mes siguiente")
        next_btn.connect("clicked", lambda _b: self.shift_month(1))
        nav.append(next_btn)

        self.append(nav)

        self.grid = Gtk.Grid()
        self.grid.set_column_homogeneous(True)
        self.grid.set_row_spacing(2)
        self.grid.set_column_spacing(2)
        self.append(self.grid)

        self._render()

    def shift_month(self, delta: int) -> None:
        month = self.view_month + delta
        year = self.view_year
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        self.view_year = year
        self.view_month = month
        self._render()

    def go_today(self) -> None:
        today = datetime.date.today()
        if self.view_year == today.year and self.view_month == today.month:
            return
        self.view_year = today.year
        self.view_month = today.month
        self._render()

    def _render(self) -> None:
        today = datetime.date.today()
        is_current_month = self.view_year == today.year and self.view_month == today.month
        self.title_btn.set_label(f"{self._MONTHS[self.view_month]} {self.view_year}")
        if is_current_month:
            self.title_btn.remove_css_class("other-month")
            self.title_btn.set_tooltip_text("Mes actual")
        else:
            self.title_btn.add_css_class("other-month")
            self.title_btn.set_tooltip_text("Click para volver al mes actual")

        child = self.grid.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt

        for col, name in enumerate(self._WEEKDAYS):
            lbl = Gtk.Label(label=name)
            lbl.add_css_class("cal-weekday")
            lbl.set_halign(Gtk.Align.FILL)
            self.grid.attach(lbl, col, 0, 1, 1)

        weeks = self._cal.monthdatescalendar(self.view_year, self.view_month)
        for row_idx, week in enumerate(weeks, start=1):
            for col_idx, day in enumerate(week):
                lbl = Gtk.Label(label=str(day.day))
                lbl.set_halign(Gtk.Align.FILL)
                if day == today:
                    lbl.add_css_class("cal-day-today")
                elif day.month == self.view_month:
                    lbl.add_css_class("cal-day")
                else:
                    lbl.add_css_class("cal-day-other")
                self.grid.attach(lbl, col_idx, row_idx, 1, 1)


class ControlCenterApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=None)
        self.backend = SystemBackend()
        self.state = SystemState()
        self.win: Gtk.ApplicationWindow | None = None
        self.root: Gtk.Box | None = None
        self.card: Gtk.Box | None = None
        self.busy_keys: set[str] = set()
        self._syncing_sliders = False
        self._toast_timer: int | None = None
        self._vol_debounce: int | None = None
        self._bri_debounce: int | None = None
        self._notif_poll_timer: int | None = None
        self._last_notif_sig: tuple | None = None

    def do_activate(self) -> None:
        self._load_css()
        self._build_window()
        self.win.present()
        self.refresh_state()
        self._notif_poll_timer = GLib.timeout_add_seconds(3, self._poll_notifications)

    def do_shutdown(self) -> None:
        if self._notif_poll_timer is not None:
            GLib.source_remove(self._notif_poll_timer)
            self._notif_poll_timer = None
        Gtk.Application.do_shutdown(self)

    def _load_css(self) -> None:
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-application-prefer-dark-theme", True)

        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )

    def _build_window(self) -> None:
        win = Gtk.ApplicationWindow(application=self)
        win.add_css_class("cc-backdrop")
        win.set_decorated(False)
        win.set_resizable(True)
        self.win = win

        if Gtk4LayerShell.is_supported():
            Gtk4LayerShell.init_for_window(win)
            Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_namespace(win, "control-center")
            Gtk4LayerShell.set_exclusive_zone(win, 0)
            Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.EXCLUSIVE)
            for edge in (
                Gtk4LayerShell.Edge.TOP,
                Gtk4LayerShell.Edge.BOTTOM,
                Gtk4LayerShell.Edge.LEFT,
                Gtk4LayerShell.Edge.RIGHT,
            ):
                Gtk4LayerShell.set_anchor(win, edge, True)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        win.add_controller(key_ctrl)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.set_hexpand(True)
        root.set_vexpand(True)
        self.root = root

        click_ctrl = Gtk.GestureClick()
        click_ctrl.set_button(0)
        click_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click_ctrl.connect("pressed", self._on_backdrop_click)
        root.add_controller(click_ctrl)

        # Floating card centered right underneath the center of Waybar
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        card.add_css_class("cc-card")
        card.set_size_request(356, -1)
        card.set_hexpand(True)
        card.set_halign(Gtk.Align.CENTER)
        card.set_valign(Gtk.Align.START)
        card.set_margin_top(4)
        self.card = card

        # --- Header ---
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_valign(Gtk.Align.CENTER)

        title = Gtk.Label(label="Centro de control", xalign=0)
        title.add_css_class("cc-title")
        title.set_hexpand(True)
        header.append(title)

        self.awake_chip = Gtk.Label(label="󰅶 Sin suspensión")
        self.awake_chip.add_css_class("cc-awake-chip")
        self.awake_chip.set_visible(False)
        header.append(self.awake_chip)

        kbd = Gtk.Label(label="SUPER+W")
        kbd.add_css_class("cc-kbd")
        header.append(kbd)

        card.append(header)

        div = Gtk.Box()
        div.add_css_class("divider")
        card.append(div)

        # --- 2x3 Quick Toggles Grid ---
        grid = Gtk.Grid()
        grid.set_row_spacing(7)
        grid.set_column_spacing(7)
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)

        self.tiles: dict[str, ToggleTile] = {
            "wifi": ToggleTile("Wi-Fi", "󰤨", "󰤭", "on-wifi"),
            "bt": ToggleTile("Bluetooth", "󰂯", "󰂲", "on-bt"),
            "audio": ToggleTile("Sonido", "󰕾", "󰝟", "on-audio"),
            "airplane": ToggleTile("Modo avión", "󰀝", "󰀞", "on-airplane"),
            "night": ToggleTile("Nocturno", "󰖔", "󰖙", "on-night"),
            "awake": ToggleTile("No bloquear", "󰅶", "󰾪", "on-awake"),
        }

        layout = [
            ("wifi", 0, 0),
            ("bt", 1, 0),
            ("audio", 0, 1),
            ("airplane", 1, 1),
            ("night", 0, 2),
            ("awake", 1, 2),
        ]
        for key, col, row in layout:
            tile = self.tiles[key]
            tile.connect("clicked", self._on_tile_clicked, key)
            grid.attach(tile, col, row, 1, 1)

        card.append(grid)

        # --- Sliders (Volume + Brightness) ---
        sliders_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        sliders_box.add_css_class("sliders-box")

        # Volume slider
        vol_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vol_row.set_valign(Gtk.Align.CENTER)
        self.vol_icon = Gtk.Label(label="󰕾")
        self.vol_icon.add_css_class("slider-icon")
        vol_row.append(self.vol_icon)

        self.vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol_scale.add_css_class("cc-scale")
        self.vol_scale.add_css_class("vol-scale")
        self.vol_scale.set_draw_value(False)
        self.vol_scale.set_hexpand(True)
        self.vol_scale.connect("value-changed", self._on_vol_changed)
        vol_row.append(self.vol_scale)

        self.vol_val = Gtk.Label(label="--%", xalign=1)
        self.vol_val.add_css_class("slider-val")
        vol_row.append(self.vol_val)
        sliders_box.append(vol_row)

        # Brightness slider (hidden automatically if no backlight device)
        self.bri_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.bri_row.set_valign(Gtk.Align.CENTER)
        bri_icon = Gtk.Label(label="󰃠")
        bri_icon.add_css_class("slider-icon")
        self.bri_row.append(bri_icon)

        self.bri_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 5, 100, 1)
        self.bri_scale.add_css_class("cc-scale")
        self.bri_scale.add_css_class("bri-scale")
        self.bri_scale.set_draw_value(False)
        self.bri_scale.set_hexpand(True)
        self.bri_scale.connect("value-changed", self._on_bri_changed)
        self.bri_row.append(self.bri_scale)

        self.bri_val = Gtk.Label(label="--%", xalign=1)
        self.bri_val.add_css_class("slider-val")
        self.bri_row.append(self.bri_val)
        sliders_box.append(self.bri_row)

        card.append(sliders_box)

        # --- Calendar ---
        self.calendar_widget = CalendarWidget()
        card.append(self.calendar_widget)

        # --- Notification Center ---
        notif_div = Gtk.Box()
        notif_div.add_css_class("divider")
        card.append(notif_div)

        notif_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        notif_header.set_valign(Gtk.Align.CENTER)

        notif_title = Gtk.Label(label="󰂚 Notificaciones", xalign=0)
        notif_title.add_css_class("notif-section-title")
        notif_header.append(notif_title)

        self.notif_badge = Gtk.Label(label="0")
        self.notif_badge.add_css_class("notif-badge")
        self.notif_badge.set_visible(False)
        notif_header.append(self.notif_badge)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        notif_header.append(spacer)

        self.dnd_btn = Gtk.Button(label="󰂛 No molestar")
        self.dnd_btn.add_css_class("notif-action-btn")
        self.dnd_btn.set_tooltip_text("Pausar o reanudar notificaciones")
        self.dnd_btn.connect("clicked", self._on_dnd_clicked)
        notif_header.append(self.dnd_btn)

        self.clear_notifs_btn = Gtk.Button(label="󰎟 Limpiar")
        self.clear_notifs_btn.add_css_class("notif-action-btn")
        self.clear_notifs_btn.add_css_class("notif-clear-btn")
        self.clear_notifs_btn.set_tooltip_text("Borrar todas las notificaciones")
        self.clear_notifs_btn.set_sensitive(False)
        self.clear_notifs_btn.connect("clicked", self._on_clear_notifs_clicked)
        notif_header.append(self.clear_notifs_btn)

        card.append(notif_header)

        notif_scroll = Gtk.ScrolledWindow()
        notif_scroll.add_css_class("notif-scroll")
        notif_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        notif_scroll.set_propagate_natural_height(True)
        notif_scroll.set_max_content_height(200)

        self.notif_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        notif_scroll.set_child(self.notif_list_box)
        card.append(notif_scroll)

        # --- Error toast ---
        self.toast_rev = Gtk.Revealer()
        self.toast_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.toast_rev.set_transition_duration(150)

        toast_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        toast_box.add_css_class("toast-box")
        self.toast_lbl = Gtk.Label(label="", xalign=0)
        self.toast_lbl.set_wrap(True)
        self.toast_lbl.set_hexpand(True)
        toast_box.append(self.toast_lbl)
        self.toast_rev.set_child(toast_box)
        card.append(self.toast_rev)

        root.append(card)
        win.set_child(root)

    def _on_key_pressed(self, _ctrl, keyval: int, _keycode: int, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.quit()
            return True
        return False

    def _on_backdrop_click(self, _gesture, _n_press: int, x: float, y: float) -> None:
        if not self.card or not self.root:
            return
        ok, rect = self.card.compute_bounds(self.root)
        if not ok:
            return
        pt = Graphene.Point()
        pt.init(float(x), float(y))
        if not rect.contains_point(pt):
            self.quit()

    def _show_toast(self, msg: str) -> None:
        if self._toast_timer is not None:
            GLib.source_remove(self._toast_timer)
        self.toast_lbl.set_label(msg)
        self.toast_rev.set_reveal_child(True)
        self._toast_timer = GLib.timeout_add(3800, self._hide_toast)

    def _hide_toast(self) -> bool:
        self._toast_timer = None
        self.toast_rev.set_reveal_child(False)
        return False

    def refresh_state(self) -> None:
        def worker() -> None:
            st = self.backend.read_all()
            GLib.idle_add(self._apply_state, st)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_state(self, st: SystemState) -> bool:
        self.state = st
        self.tiles["wifi"].set_state(st.wifi_on, "Activado" if st.wifi_on else "Desactivado")
        self.tiles["bt"].set_state(st.bt_on, "Activado" if st.bt_on else "Desactivado")
        self.tiles["audio"].set_state(
            st.audio_on,
            f"{st.volume_pct}%" if st.audio_on else "Silenciado",
        )
        self.tiles["airplane"].set_state(st.airplane_on, "Activo" if st.airplane_on else "Desactivado")
        self.tiles["night"].set_state(st.night_on, "Filtro cálido" if st.night_on else "Desactivado")
        self.tiles["awake"].set_state(st.awake_on, "Solo sesión" if st.awake_on else "Desactivado")
        self.awake_chip.set_visible(st.awake_on)

        self._syncing_sliders = True
        self.vol_scale.set_value(st.volume_pct)
        self.vol_val.set_label(f"{st.volume_pct}%")
        self.vol_icon.set_label("󰕾" if st.audio_on else "󰝟")
        self.bri_row.set_visible(st.has_brightness)
        if st.has_brightness:
            self.bri_scale.set_value(st.brightness_pct)
            self.bri_val.set_label(f"{st.brightness_pct}%")
        self._syncing_sliders = False

        self._apply_notifications(st.dnd_on, st.notifications)
        return False

    def _poll_notifications(self) -> bool:
        def worker() -> None:
            dnd_on = self.backend.get_dnd()
            notifs = self.backend.get_notifications()
            GLib.idle_add(self._apply_notifications, dnd_on, notifs)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _apply_notifications(self, dnd_on: bool, notifs: list[NotificationItem], force: bool = False) -> bool:
        self.state.dnd_on = dnd_on
        self.state.notifications = notifs

        if dnd_on:
            self.dnd_btn.add_css_class("dnd-active")
            self.dnd_btn.set_label("󰂛 Silenciado")
        else:
            self.dnd_btn.remove_css_class("dnd-active")
            self.dnd_btn.set_label("󰂛 No molestar")

        count = len(notifs)
        self.notif_badge.set_label(str(count))
        self.notif_badge.set_visible(count > 0)
        self.clear_notifs_btn.set_sensitive(count > 0)

        sig = (dnd_on, tuple((n.notif_id, n.summary, n.body, _format_rel_time(n.timestamp_us)) for n in notifs))
        if not force and sig == self._last_notif_sig:
            return False
        self._last_notif_sig = sig

        child = self.notif_list_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.notif_list_box.remove(child)
            child = nxt

        if not notifs:
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            empty_box.add_css_class("notif-empty-box")
            empty_box.set_halign(Gtk.Align.FILL)

            empty_icon = Gtk.Label(label="󰂛" if dnd_on else "󰂜")
            empty_icon.add_css_class("notif-empty-icon")
            empty_box.append(empty_icon)

            empty_lbl = Gtk.Label(
                label="No molestar activado · Sin notificaciones" if dnd_on else "No hay notificaciones"
            )
            empty_lbl.add_css_class("notif-empty-text")
            empty_box.append(empty_lbl)
            self.notif_list_box.append(empty_box)
            return False

        for item in notifs:
            self.notif_list_box.append(self._build_notif_card(item))
        return False

    def _build_notif_card(self, item: NotificationItem) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        card.add_css_class("notif-card")
        if item.urgency == "CRITICAL":
            card.add_css_class("urgency-critical")
        elif item.urgency == "LOW":
            card.add_css_class("urgency-low")

        # Top row: app icon + appname + timestamp + optional link + dismiss
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        top.set_valign(Gtk.Align.CENTER)

        app_icon = Gtk.Label(label=_app_icon(item.appname))
        app_icon.add_css_class("notif-app-icon")
        top.append(app_icon)

        app_lbl = Gtk.Label(label=item.appname, xalign=0)
        app_lbl.add_css_class("notif-app-name")
        app_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        app_lbl.set_hexpand(True)
        top.append(app_lbl)

        rel_time = _format_rel_time(item.timestamp_us)
        if rel_time:
            time_lbl = Gtk.Label(label=rel_time, xalign=1)
            time_lbl.add_css_class("notif-time")
            top.append(time_lbl)

        first_url = item.urls.splitlines()[0].strip() if item.urls else ""
        if first_url:
            link_btn = Gtk.Button(label="󰌹")
            link_btn.add_css_class("notif-icon-btn")
            link_btn.set_tooltip_text(f"Abrir enlace: {first_url}")
            link_btn.connect("clicked", self._on_open_notif_url, first_url)
            top.append(link_btn)

        dismiss_btn = Gtk.Button(label="✕")
        dismiss_btn.add_css_class("notif-icon-btn")
        dismiss_btn.add_css_class("notif-dismiss-btn")
        dismiss_btn.set_tooltip_text("Descartar notificación")
        dismiss_btn.connect("clicked", self._on_dismiss_notif, item.notif_id)
        top.append(dismiss_btn)

        card.append(top)

        summary_lbl = Gtk.Label(label=item.summary, xalign=0)
        summary_lbl.add_css_class("notif-summary")
        summary_lbl.set_wrap(True)
        summary_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        summary_lbl.set_lines(2)
        summary_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        summary_lbl.set_max_width_chars(38)
        card.append(summary_lbl)

        if item.body:
            body_lbl = Gtk.Label(label=item.body, xalign=0)
            body_lbl.add_css_class("notif-body")
            body_lbl.set_wrap(True)
            body_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            body_lbl.set_lines(3)
            body_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            body_lbl.set_max_width_chars(42)
            card.append(body_lbl)

        return card

    def _on_dnd_clicked(self, _btn: Gtk.Button) -> None:
        target = not self.state.dnd_on
        self.dnd_btn.set_sensitive(False)

        def worker() -> None:
            ok, err = self.backend.set_dnd(target)
            dnd_on = self.backend.get_dnd()
            notifs = self.backend.get_notifications()
            GLib.idle_add(self._on_dnd_done, ok, err, dnd_on, notifs)

        threading.Thread(target=worker, daemon=True).start()

    def _on_dnd_done(self, ok: bool, err: str, dnd_on: bool, notifs: list[NotificationItem]) -> bool:
        self.dnd_btn.set_sensitive(True)
        self._apply_notifications(dnd_on, notifs, force=True)
        if not ok and err:
            self._show_toast(err)
        return False

    def _on_dismiss_notif(self, _btn: Gtk.Button, notif_id: int) -> None:
        remaining = [n for n in self.state.notifications if n.notif_id != notif_id]
        self._apply_notifications(self.state.dnd_on, remaining, force=True)

        def worker() -> None:
            self.backend.dismiss_notification(notif_id)
            notifs = self.backend.get_notifications()
            GLib.idle_add(self._apply_notifications, self.state.dnd_on, notifs)

        threading.Thread(target=worker, daemon=True).start()

    def _on_clear_notifs_clicked(self, _btn: Gtk.Button) -> None:
        self._apply_notifications(self.state.dnd_on, [], force=True)

        def worker() -> None:
            self.backend.clear_notifications()
            notifs = self.backend.get_notifications()
            GLib.idle_add(self._apply_notifications, self.state.dnd_on, notifs)

        threading.Thread(target=worker, daemon=True).start()

    def _on_open_notif_url(self, _btn: Gtk.Button, url: str) -> None:
        try:
            subprocess.Popen(
                ["xdg-open", url],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            self._show_toast(f"No se pudo abrir el enlace: {exc}")
            return
        self.quit()

    def _on_tile_clicked(self, _btn: Gtk.Button, key: str) -> None:
        if key in self.busy_keys:
            return
        self.busy_keys.add(key)
        self.tiles[key].set_sensitive(False)
        target = not self.tiles[key].is_on

        def worker() -> None:
            handlers = {
                "wifi": self.backend.set_wifi,
                "bt": self.backend.set_bt,
                "audio": self.backend.set_audio,
                "airplane": self.backend.set_airplane,
                "night": self.backend.set_night,
                "awake": self.backend.set_awake,
            }
            ok, err = handlers[key](target)
            st = self.backend.read_all()
            GLib.idle_add(self._on_toggle_done, key, ok, err, st)

        threading.Thread(target=worker, daemon=True).start()

    def _on_toggle_done(self, key: str, ok: bool, err: str, st: SystemState) -> bool:
        self.busy_keys.discard(key)
        self.tiles[key].set_sensitive(True)
        self._apply_state(st)
        if not ok and err:
            self._show_toast(err)
        return False

    def _on_vol_changed(self, scale: Gtk.Scale) -> None:
        if self._syncing_sliders:
            return
        val = int(round(scale.get_value()))
        self.vol_val.set_label(f"{val}%")
        if self.state.audio_on:
            self.tiles["audio"].sub_lbl.set_label(f"{val}%")
        if self._vol_debounce is not None:
            GLib.source_remove(self._vol_debounce)
        self._vol_debounce = GLib.timeout_add(35, self._commit_vol, val)

    def _commit_vol(self, val: int) -> bool:
        self._vol_debounce = None
        threading.Thread(target=self.backend.set_volume, args=(val,), daemon=True).start()
        return False

    def _on_bri_changed(self, scale: Gtk.Scale) -> None:
        if self._syncing_sliders:
            return
        val = int(round(scale.get_value()))
        self.bri_val.set_label(f"{val}%")
        if self._bri_debounce is not None:
            GLib.source_remove(self._bri_debounce)
        self._bri_debounce = GLib.timeout_add(35, self._commit_bri, val)

    def _commit_bri(self, val: int) -> bool:
        self._bri_debounce = None
        threading.Thread(target=self.backend.set_brightness, args=(val,), daemon=True).start()
        return False


def _cleanup_pid() -> None:
    try:
        if os.path.exists(PID_FILE) and open(PID_FILE).read().strip() == str(os.getpid()):
            os.remove(PID_FILE)
    except OSError:
        pass


def main() -> int:
    with open(PID_FILE, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))
    atexit.register(_cleanup_pid)

    app = ControlCenterApp()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (app.quit(), False)[1])
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: (app.quit(), False)[1])
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
