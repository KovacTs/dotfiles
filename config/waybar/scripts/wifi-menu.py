#!/usr/bin/env python3
"""Minimalist floating Wi-Fi panel for Waybar + Hyprland (GTK4 + gtk4-layer-shell)."""

from __future__ import annotations

import atexit
import ctypes
import os
import signal
import subprocess
import threading
from dataclasses import dataclass

# Ensure libgtk4-layer-shell is loaded globally before libwayland-client
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

PID_FILE = "/tmp/waybar-wifi-popup.pid"

CSS = """
window,
window.background,
window.background.wifi-backdrop,
window.wifi-backdrop {
    background: transparent;
    background-color: transparent;
    background-image: none;
    box-shadow: none;
    border: none;
}

tooltip {
    background-color: rgba(13, 17, 23, 0.96);
    border: 1px solid rgba(203, 166, 247, 0.25);
    border-radius: 8px;
    color: #cdd6f4;
}

.wifi-card {
    background-color: rgba(13, 17, 23, 0.96);
    background-image: none;
    border: 1px solid rgba(203, 166, 247, 0.22);
    border-radius: 13px;
    padding: 10px;
    box-shadow: none;
    color: #cdd6f4;
    font-family: "JetBrainsMono Nerd Font Propo", "Adwaita Sans", sans-serif;
    font-size: 11px;
}

.header-badge {
    background-color: rgba(203, 166, 247, 0.14);
    color: #cba6f7;
    border-radius: 999px;
    min-width: 26px;
    min-height: 26px;
    font-size: 13px;
}

.header-badge.off {
    background-color: rgba(108, 112, 134, 0.16);
    color: #6c7086;
}

.header-title {
    color: #e6edf3;
    font-size: 11.5px;
    font-weight: 700;
}

.header-subtitle {
    color: #8b949e;
    font-size: 9.5px;
    font-weight: 500;
}

.header-subtitle.connected {
    color: #a6e3a1;
}

button.icon-btn {
    background: transparent;
    background-color: transparent;
    background-image: none;
    border: 1px solid transparent;
    border-radius: 999px;
    color: #a6adc8;
    min-width: 24px;
    min-height: 24px;
    padding: 0;
    font-size: 12px;
    box-shadow: none;
    text-shadow: none;
    transition: background-color 150ms ease, color 150ms ease;
}

button.icon-btn:hover {
    background-color: rgba(49, 50, 68, 0.78);
    background-image: none;
    color: #e6edf3;
}

button.icon-btn:disabled {
    opacity: 0.35;
}

switch.wifi-switch {
    background-color: rgba(49, 50, 68, 0.90);
    background-image: none;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 999px;
    min-width: 34px;
    min-height: 18px;
    box-shadow: none;
    transition: background-color 180ms ease;
}

switch.wifi-switch:checked {
    background-color: #cba6f7;
    background-image: none;
    border-color: rgba(203, 166, 247, 0.45);
}

switch.wifi-switch slider {
    background-color: #e6edf3;
    background-image: none;
    border: none;
    border-radius: 999px;
    min-width: 13px;
    min-height: 13px;
    margin: 2px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
}

switch.wifi-switch:checked slider {
    background-color: #0d1117;
    background-image: none;
}

.divider {
    background-color: rgba(255, 255, 255, 0.06);
    min-height: 1px;
    margin-top: 1px;
    margin-bottom: 1px;
}

.status-banner {
    background-color: rgba(24, 29, 40, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 8px;
    padding: 5px 8px;
    font-size: 10px;
    color: #cdd6f4;
}

.status-banner.success {
    background-color: rgba(166, 227, 161, 0.12);
    border-color: rgba(166, 227, 161, 0.28);
    color: #a6e3a1;
}

.status-banner.error {
    background-color: rgba(243, 139, 168, 0.12);
    border-color: rgba(243, 139, 168, 0.28);
    color: #f38ba8;
}

.section-label {
    color: #6c7086;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.5px;
    margin-left: 3px;
    margin-top: 1px;
    margin-bottom: 1px;
}

scrolledwindow.net-scroll,
scrolledwindow.net-scroll viewport,
.net-list {
    background: transparent;
    background-color: transparent;
    background-image: none;
    border: none;
}

scrolledwindow.net-scroll scrollbar {
    background: transparent;
    background-color: transparent;
}

scrolledwindow.net-scroll scrollbar slider {
    background-color: rgba(166, 173, 200, 0.22);
    border-radius: 999px;
    min-width: 3px;
    min-height: 20px;
}

scrolledwindow.net-scroll scrollbar slider:hover {
    background-color: rgba(203, 166, 247, 0.45);
}

.net-item {
    background-color: rgba(22, 27, 36, 0.88);
    background-image: none;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 9px;
    transition: background-color 140ms ease, border-color 140ms ease;
}

.net-item.active {
    background-color: rgba(203, 166, 247, 0.11);
    border-color: rgba(203, 166, 247, 0.28);
}

.net-item.expanded {
    background-color: rgba(26, 32, 44, 0.96);
    border-color: rgba(255, 255, 255, 0.10);
}

.net-item.active.expanded {
    background-color: rgba(203, 166, 247, 0.14);
    border-color: rgba(203, 166, 247, 0.34);
}

button.net-row-btn,
button.net-row-btn:focus,
button.net-row-btn:active {
    background: transparent;
    background-color: transparent;
    background-image: none;
    border: none;
    border-radius: 8px;
    padding: 5px 8px;
    color: #cdd6f4;
    box-shadow: none;
    text-shadow: none;
    outline: none;
    transition: background-color 140ms ease;
}

button.net-row-btn:hover {
    background-color: rgba(44, 50, 70, 0.72);
    background-image: none;
}

.net-icon {
    font-size: 13px;
    color: #a6adc8;
    min-width: 16px;
}

.net-icon.saved {
    color: #cba6f7;
}

.net-icon.active {
    color: #a6e3a1;
}

.net-ssid {
    color: #e6edf3;
    font-size: 11px;
    font-weight: 600;
}

.net-meta {
    color: #6c7086;
    font-size: 9px;
    font-weight: 500;
}

.net-badge-active {
    color: #a6e3a1;
    background-color: rgba(166, 227, 161, 0.14);
    border-radius: 999px;
    padding: 1px 6px;
    font-size: 8.5px;
    font-weight: 700;
}

.net-badge-saved {
    color: #cba6f7;
    background-color: rgba(203, 166, 247, 0.14);
    border-radius: 999px;
    padding: 1px 6px;
    font-size: 8.5px;
    font-weight: 600;
}

.net-lock {
    color: #7f849c;
    font-size: 10px;
}

.net-signal {
    color: #7f849c;
    font-size: 9.5px;
    min-width: 24px;
}

.drawer-box {
    background: transparent;
    background-color: transparent;
    padding: 3px 8px 8px 8px;
}

.drawer-info {
    color: #8b949e;
    font-size: 9.5px;
    margin-bottom: 2px;
}

.pw-entry {
    background-color: rgba(13, 17, 23, 0.96);
    background-image: none;
    border: 1px solid rgba(255, 255, 255, 0.11);
    border-radius: 8px;
    padding: 3px 8px;
    color: #e6edf3;
    font-size: 10.5px;
    min-height: 26px;
    box-shadow: none;
    caret-color: #cba6f7;
}

.pw-entry:focus-within {
    border-color: rgba(203, 166, 247, 0.65);
    box-shadow: 0 0 0 2px rgba(203, 166, 247, 0.14);
}

.pw-entry text {
    color: #e6edf3;
}

.pw-entry image {
    color: #a6adc8;
}

button.pill-primary {
    background-color: #cba6f7;
    background-image: none;
    color: #0d1117;
    border: none;
    border-radius: 7px;
    padding: 4px 10px;
    font-size: 10px;
    font-weight: 700;
    box-shadow: none;
    text-shadow: none;
    transition: background-color 140ms ease;
}

button.pill-primary:hover {
    background-color: #d8bdf9;
    background-image: none;
}

button.pill-primary:disabled {
    opacity: 0.45;
}

button.pill-secondary {
    background-color: rgba(49, 50, 68, 0.85);
    background-image: none;
    color: #cdd6f4;
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 7px;
    padding: 4px 9px;
    font-size: 10px;
    font-weight: 600;
    box-shadow: none;
    text-shadow: none;
    transition: background-color 140ms ease;
}

button.pill-secondary:hover {
    background-color: rgba(69, 71, 90, 0.95);
    background-image: none;
    color: #ffffff;
}

button.pill-secondary:disabled {
    opacity: 0.45;
}

button.pill-danger {
    background-color: rgba(243, 139, 168, 0.15);
    background-image: none;
    color: #f38ba8;
    border: 1px solid rgba(243, 139, 168, 0.25);
    border-radius: 7px;
    padding: 4px 9px;
    font-size: 10px;
    font-weight: 600;
    box-shadow: none;
    text-shadow: none;
    transition: background-color 140ms ease;
}

button.pill-danger:hover {
    background-color: rgba(243, 139, 168, 0.26);
    background-image: none;
}

button.pill-danger:disabled {
    opacity: 0.45;
}

.empty-box {
    padding: 18px 10px;
}

.empty-icon {
    font-size: 22px;
    color: #585b70;
    margin-bottom: 2px;
}

.empty-title {
    color: #cdd6f4;
    font-size: 11px;
    font-weight: 600;
}

.empty-desc {
    color: #6c7086;
    font-size: 9.5px;
}
"""


@dataclass
class NetworkInfo:
    ssid: str
    signal: int
    security: str
    active: bool
    saved: bool
    conn_name: str | None = None

    @property
    def secured(self) -> bool:
        sec = self.security.strip()
        return bool(sec and sec != "--")


def split_nmcli_terse(line: str) -> list[str]:
    """Split a terse (-t) nmcli line on unescaped colons and unescape values."""
    parts: list[str] = []
    buf: list[str] = []
    escaped = False
    for ch in line:
        if escaped:
            buf.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == ":":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if escaped:
        buf.append("\\")
    parts.append("".join(buf))
    return parts


def signal_icon(strength: int) -> str:
    if strength >= 80:
        return "󰤨"
    if strength >= 60:
        return "󰤥"
    if strength >= 40:
        return "󰤢"
    if strength >= 20:
        return "󰤟"
    return "󰤯"


def friendly_error(raw: str) -> str:
    low = raw.lower()
    if "secrets were required" in low or "no secrets" in low or "bad password" in low or "property 'psk'" in low:
        return "Contraseña incorrecta o requerida"
    if "timeout" in low or "timed out" in low:
        return "Tiempo de espera agotado al conectar"
    if "no network with ssid" in low:
        return "Red fuera de alcance"
    if "not authorized" in low or "permission" in low:
        return "Sin permisos para modificar la red"
    first = raw.strip().splitlines()[0] if raw.strip() else "No se pudo completar la operación"
    return first[:72] + ("…" if len(first) > 72 else "")


class NMBackend:
    def __init__(self) -> None:
        self._env = {**os.environ, "LC_ALL": "C"}

    def _run(self, args: list[str], timeout: int = 25) -> tuple[int, str, str]:
        try:
            proc = subprocess.run(
                ["nmcli", *args],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._env,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return 124, "", "Connection timed out"
        except FileNotFoundError:
            return 127, "", "nmcli no está instalado"

    def wifi_enabled(self) -> bool:
        rc, out, _ = self._run(["-t", "-f", "WIFI", "general"], timeout=5)
        return rc == 0 and out.strip().lower() == "enabled"

    def set_wifi_enabled(self, enabled: bool) -> tuple[bool, str]:
        rc, _, err = self._run(["radio", "wifi", "on" if enabled else "off"], timeout=10)
        return rc == 0, err.strip()

    def get_wifi_device(self) -> str | None:
        rc, out, _ = self._run(["-t", "-f", "DEVICE,TYPE", "device", "status"], timeout=5)
        if rc != 0:
            return None
        for line in out.splitlines():
            cols = split_nmcli_terse(line)
            if len(cols) >= 2 and cols[1] == "wifi":
                return cols[0]
        return None

    def get_active_wifi_details(self) -> tuple[str | None, str | None]:
        """Return (active_conn_name, ip_address) for the active Wi-Fi device."""
        dev = self.get_wifi_device()
        if not dev:
            return None, None
        rc, out, _ = self._run(
            ["-t", "-f", "GENERAL.CONNECTION,IP4.ADDRESS", "device", "show", dev],
            timeout=5,
        )
        if rc != 0:
            return None, None
        conn_name: str | None = None
        ip_addr: str | None = None
        for line in out.splitlines():
            cols = split_nmcli_terse(line)
            if len(cols) < 2:
                continue
            key, val = cols[0], cols[1].strip()
            if key == "GENERAL.CONNECTION" and val and val != "--":
                conn_name = val
            elif key.startswith("IP4.ADDRESS") and val and not ip_addr:
                ip_addr = val.split("/")[0]
        return conn_name, ip_addr

    def saved_wifi_connections(self) -> set[str]:
        rc, out, _ = self._run(["-t", "-f", "NAME,TYPE", "connection", "show"], timeout=5)
        saved: set[str] = set()
        if rc != 0:
            return saved
        for line in out.splitlines():
            cols = split_nmcli_terse(line)
            if len(cols) >= 2 and cols[1] == "802-11-wireless":
                saved.add(cols[0])
        return saved

    def list_networks(self, rescan: bool = False) -> tuple[bool, list[NetworkInfo], str | None]:
        enabled = self.wifi_enabled()
        if not enabled:
            return False, [], None

        saved = self.saved_wifi_connections()
        active_conn, active_ip = self.get_active_wifi_details()

        args = ["-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes" if rescan else "no"]
        rc, out, _ = self._run(args, timeout=15)
        if rc != 0:
            return True, [], active_ip

        by_ssid: dict[str, NetworkInfo] = {}
        for line in out.splitlines():
            cols = split_nmcli_terse(line)
            if len(cols) < 4:
                continue
            active = cols[0].strip().lower() == "yes"
            ssid = cols[1].strip()
            if not ssid:
                continue
            try:
                sig = int(cols[2].strip() or "0")
            except ValueError:
                sig = 0
            sec = cols[3].strip()
            is_saved = (ssid in saved) or (active and active_conn is not None)
            conn_name = active_conn if (active and active_conn) else (ssid if ssid in saved else None)

            existing = by_ssid.get(ssid)
            if existing is None:
                by_ssid[ssid] = NetworkInfo(
                    ssid=ssid,
                    signal=sig,
                    security=sec,
                    active=active,
                    saved=is_saved,
                    conn_name=conn_name,
                )
            else:
                if active and not existing.active:
                    existing.active = True
                    existing.saved = True
                    existing.conn_name = conn_name or existing.conn_name
                if sig > existing.signal:
                    existing.signal = sig
                if sec and sec != "--" and not existing.secured:
                    existing.security = sec

        networks = sorted(
            by_ssid.values(),
            key=lambda n: (not n.active, not n.saved, -n.signal, n.ssid.lower()),
        )
        return True, networks, active_ip

    def connect(self, net: NetworkInfo, password: str | None = None) -> tuple[bool, str]:
        if password is not None:
            if net.saved and net.conn_name:
                rc_mod, _, _ = self._run(
                    ["connection", "modify", "id", net.conn_name, "wifi-sec.psk", password],
                    timeout=10,
                )
                if rc_mod == 0:
                    rc_up, _, err_up = self._run(["connection", "up", "id", net.conn_name], timeout=30)
                    if rc_up == 0:
                        return True, ""
                    # Fallback: recreate profile if key-mgmt or security changed
                    self._run(["connection", "delete", "id", net.conn_name], timeout=10)
                    rc, _, err = self._run(
                        ["device", "wifi", "connect", net.ssid, "password", password],
                        timeout=30,
                    )
                    return rc == 0, err.strip() or err_up.strip()
                self._run(["connection", "delete", "id", net.conn_name], timeout=10)

            was_saved = net.ssid in self.saved_wifi_connections()
            rc, _, err = self._run(
                ["device", "wifi", "connect", net.ssid, "password", password],
                timeout=30,
            )
            if rc != 0 and not was_saved:
                # Clean up broken auto-created profile after failed password attempt
                self._run(["connection", "delete", "id", net.ssid], timeout=5)
            return rc == 0, err.strip()

        if net.saved and net.conn_name:
            rc, _, err = self._run(["connection", "up", "id", net.conn_name], timeout=30)
            if rc == 0:
                return True, ""
            return False, err.strip()

        rc, _, err = self._run(["device", "wifi", "connect", net.ssid], timeout=30)
        return rc == 0, err.strip()

    def disconnect(self, net: NetworkInfo) -> tuple[bool, str]:
        if net.conn_name:
            rc, _, err = self._run(["connection", "down", "id", net.conn_name], timeout=15)
            if rc == 0:
                return True, ""
        dev = self.get_wifi_device()
        if dev:
            rc, _, err = self._run(["device", "disconnect", dev], timeout=15)
            return rc == 0, err.strip()
        return False, "No se encontró dispositivo Wi-Fi"

    def forget(self, net: NetworkInfo) -> tuple[bool, str]:
        target = net.conn_name or net.ssid
        rc, _, err = self._run(["connection", "delete", "id", target], timeout=10)
        return rc == 0, err.strip()


class WifiPopupApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=None)
        self.nm = NMBackend()
        self.win: Gtk.ApplicationWindow | None = None
        self.root: Gtk.Box | None = None
        self.card: Gtk.Box | None = None

        self.wifi_enabled = True
        self.networks: list[NetworkInfo] = []
        self.active_ip: str | None = None
        self.expanded_ssid: str | None = None
        self.password_mode_ssid: str | None = None
        self.busy = False
        self.scanning = False
        self._updating_switch = False
        self._scan_gen = 0
        self._banner_timer: int | None = None
        self._active_pw_entry: Gtk.PasswordEntry | None = None

    def do_activate(self) -> None:
        self._load_css()
        self._build_window()
        self.win.present()
        self.refresh(rescan=False, follow_up_rescan=True)

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
        win.add_css_class("wifi-backdrop")
        win.set_decorated(False)
        # Keep resizable=True so all-4-edge layer-shell stretches full screen (never centered)
        win.set_resizable(True)
        self.win = win

        # Fullscreen transparent click-catcher below Waybar (exclusive_zone=0 keeps Waybar clickable)
        if Gtk4LayerShell.is_supported():
            Gtk4LayerShell.init_for_window(win)
            Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_namespace(win, "wifi-popup")
            Gtk4LayerShell.set_exclusive_zone(win, 0)
            Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.EXCLUSIVE)
            for edge in (
                Gtk4LayerShell.Edge.TOP,
                Gtk4LayerShell.Edge.BOTTOM,
                Gtk4LayerShell.Edge.LEFT,
                Gtk4LayerShell.Edge.RIGHT,
            ):
                Gtk4LayerShell.set_anchor(win, edge, True)

        # Escape key closes popup from anywhere (CAPTURE phase so it works inside PasswordEntry too)
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        win.add_controller(key_ctrl)

        # Transparent fullscreen container: only an explicit CLICK outside closes the popup
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.set_hexpand(True)
        root.set_vexpand(True)
        self.root = root

        click_ctrl = Gtk.GestureClick()
        click_ctrl.set_button(0)
        click_ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click_ctrl.connect("pressed", self._on_backdrop_click)
        root.add_controller(click_ctrl)

        # Compact floating card pinned strictly at top-right right below Waybar's network pill
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        card.add_css_class("wifi-card")
        card.set_size_request(272, -1)
        card.set_hexpand(True)
        card.set_halign(Gtk.Align.END)
        card.set_valign(Gtk.Align.START)
        card.set_margin_top(4)
        card.set_margin_end(72)
        self.card = card

        # --- Header ---
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_valign(Gtk.Align.CENTER)

        self.header_badge = Gtk.Label(label="󰤨")
        self.header_badge.add_css_class("header-badge")
        self.header_badge.set_halign(Gtk.Align.CENTER)
        self.header_badge.set_valign(Gtk.Align.CENTER)
        header.append(self.header_badge)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title_box.set_hexpand(True)
        title_box.set_valign(Gtk.Align.CENTER)

        title = Gtk.Label(label="Wi-Fi", xalign=0)
        title.add_css_class("header-title")
        title_box.append(title)

        self.subtitle_lbl = Gtk.Label(label="Cargando...", xalign=0)
        self.subtitle_lbl.add_css_class("header-subtitle")
        self.subtitle_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_box.append(self.subtitle_lbl)
        header.append(title_box)

        self.scan_spinner = Gtk.Spinner()
        self.scan_spinner.set_size_request(14, 14)
        self.scan_spinner.set_visible(False)
        header.append(self.scan_spinner)

        self.refresh_btn = Gtk.Button(label="󰑐")
        self.refresh_btn.add_css_class("icon-btn")
        self.refresh_btn.set_tooltip_text("Buscar redes")
        self.refresh_btn.connect("clicked", lambda *_: self.refresh(rescan=True, follow_up_rescan=False))
        header.append(self.refresh_btn)

        self.wifi_switch = Gtk.Switch()
        self.wifi_switch.add_css_class("wifi-switch")
        self.wifi_switch.set_valign(Gtk.Align.CENTER)
        self.wifi_switch.connect("state-set", self._on_switch_toggled)
        header.append(self.wifi_switch)

        card.append(header)

        # Divider
        div = Gtk.Box()
        div.add_css_class("divider")
        card.append(div)

        # --- Feedback banner ---
        self.banner_revealer = Gtk.Revealer()
        self.banner_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.banner_revealer.set_transition_duration(160)

        self.banner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.banner_box.add_css_class("status-banner")
        self.banner_spinner = Gtk.Spinner()
        self.banner_spinner.set_size_request(13, 13)
        self.banner_spinner.set_visible(False)
        self.banner_box.append(self.banner_spinner)

        self.banner_lbl = Gtk.Label(label="", xalign=0)
        self.banner_lbl.set_wrap(True)
        self.banner_lbl.set_hexpand(True)
        self.banner_box.append(self.banner_lbl)
        self.banner_revealer.set_child(self.banner_box)
        card.append(self.banner_revealer)

        # --- Network list container ---
        self.section_lbl = Gtk.Label(label="REDES DISPONIBLES", xalign=0)
        self.section_lbl.add_css_class("section-label")
        card.append(self.section_lbl)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.add_css_class("net-scroll")
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_propagate_natural_height(True)
        self.scroll.set_max_content_height(260)

        self.list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.list_box.add_css_class("net-list")
        self.scroll.set_child(self.list_box)
        card.append(self.scroll)

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

    def _set_banner(self, text: str | None, kind: str = "info", spinning: bool = False, auto_hide_ms: int = 0) -> None:
        if self._banner_timer is not None:
            GLib.source_remove(self._banner_timer)
            self._banner_timer = None

        if not text:
            self.banner_spinner.stop()
            self.banner_spinner.set_visible(False)
            self.banner_revealer.set_reveal_child(False)
            return

        self.banner_box.remove_css_class("success")
        self.banner_box.remove_css_class("error")
        if kind in ("success", "error"):
            self.banner_box.add_css_class(kind)

        self.banner_lbl.set_label(text)
        if spinning:
            self.banner_spinner.set_visible(True)
            self.banner_spinner.start()
        else:
            self.banner_spinner.stop()
            self.banner_spinner.set_visible(False)

        self.banner_revealer.set_reveal_child(True)
        if auto_hide_ms > 0:
            self._banner_timer = GLib.timeout_add(auto_hide_ms, self._clear_banner_cb)

    def _clear_banner_cb(self) -> bool:
        self._banner_timer = None
        self._set_banner(None)
        return False

    def _set_scanning(self, active: bool) -> None:
        self.scanning = active
        self.refresh_btn.set_sensitive(not active and self.wifi_enabled and not self.busy)
        if active:
            self.scan_spinner.set_visible(True)
            self.scan_spinner.start()
        else:
            self.scan_spinner.stop()
            self.scan_spinner.set_visible(False)

    def _update_header(self) -> None:
        self._updating_switch = True
        self.wifi_switch.set_active(self.wifi_enabled)
        self.wifi_switch.set_state(self.wifi_enabled)
        self._updating_switch = False

        self.subtitle_lbl.remove_css_class("connected")
        if not self.wifi_enabled:
            self.header_badge.set_label("󰤭")
            self.header_badge.add_css_class("off")
            self.subtitle_lbl.set_label("Desactivado")
            self.refresh_btn.set_sensitive(False)
            return

        self.header_badge.set_label("󰤨")
        self.header_badge.remove_css_class("off")
        self.refresh_btn.set_sensitive(not self.scanning and not self.busy)

        active_net = next((n for n in self.networks if n.active), None)
        if active_net:
            self.subtitle_lbl.add_css_class("connected")
            if self.active_ip:
                self.subtitle_lbl.set_label(f"IP: {self.active_ip}")
            else:
                self.subtitle_lbl.set_label(f"Conectado · {active_net.ssid}")
        elif self.scanning:
            self.subtitle_lbl.set_label("Buscando redes...")
        else:
            self.subtitle_lbl.set_label("Desconectado")

    def _on_switch_toggled(self, switch: Gtk.Switch, state: bool) -> bool:
        if self._updating_switch or self.busy:
            return True

        self.busy = True
        self.expanded_ssid = None
        self.password_mode_ssid = None
        self.wifi_switch.set_sensitive(False)
        self.refresh_btn.set_sensitive(False)
        self._set_banner("Activando Wi-Fi..." if state else "Apagando Wi-Fi...", spinning=True)

        def worker() -> None:
            ok, err = self.nm.set_wifi_enabled(state)
            GLib.idle_add(self._on_switch_done, state, ok, err)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _on_switch_done(self, target_state: bool, ok: bool, err: str) -> bool:
        self.busy = False
        self.wifi_switch.set_sensitive(True)
        if not ok:
            self._set_banner(friendly_error(err), kind="error", auto_hide_ms=4000)
            self.refresh(rescan=False, follow_up_rescan=False)
            return False

        self.wifi_enabled = target_state
        self._set_banner(None)
        if target_state:
            self._update_header()
            self._render_list()
            # Give hardware a short moment to bring up Wi-Fi before scanning
            GLib.timeout_add(700, lambda: (self.refresh(rescan=True, follow_up_rescan=False), False)[1])
        else:
            self.networks = []
            self.active_ip = None
            self._update_header()
            self._render_list()
        return False

    def refresh(self, rescan: bool = False, follow_up_rescan: bool = False, preserve_if_typing: bool = False) -> None:
        self._scan_gen += 1
        gen = self._scan_gen
        if rescan:
            self._set_scanning(True)

        def worker() -> None:
            enabled, nets, ip = self.nm.list_networks(rescan=rescan)
            GLib.idle_add(self._on_refresh_done, gen, enabled, nets, ip, rescan, follow_up_rescan, preserve_if_typing)

        threading.Thread(target=worker, daemon=True).start()

    def _is_user_typing_password(self) -> bool:
        if self._active_pw_entry is None:
            return False
        try:
            return bool(self._active_pw_entry.get_text())
        except Exception:
            return False

    def _on_refresh_done(
        self,
        gen: int,
        enabled: bool,
        nets: list[NetworkInfo],
        ip: str | None,
        was_rescan: bool,
        follow_up_rescan: bool,
        preserve_if_typing: bool,
    ) -> bool:
        if gen != self._scan_gen:
            return False
        if was_rescan:
            self._set_scanning(False)

        self.wifi_enabled = enabled
        self.active_ip = ip

        if preserve_if_typing and (self.busy or self._is_user_typing_password()):
            self._update_header()
            return False

        self.networks = nets
        # Collapse if expanded SSID disappeared
        if self.expanded_ssid and not any(n.ssid == self.expanded_ssid for n in nets):
            self.expanded_ssid = None
            self.password_mode_ssid = None

        self._update_header()
        self._render_list()

        if follow_up_rescan and enabled:
            self.refresh(rescan=True, follow_up_rescan=False, preserve_if_typing=True)
        return False

    def _clear_list(self) -> None:
        self._active_pw_entry = None
        child = self.list_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.list_box.remove(child)
            child = nxt

    def _render_list(self) -> None:
        self._clear_list()

        if not self.wifi_enabled:
            self.section_lbl.set_visible(False)
            empty = self._build_empty_state(
                "󰤭",
                "Wi-Fi desactivado",
                "Activá el interruptor superior para ver redes",
            )
            self.list_box.append(empty)
            return

        if not self.networks:
            self.section_lbl.set_visible(False)
            if self.scanning:
                empty = self._build_empty_state("󰤨", "Buscando redes...", "Escaneando señales cercanas")
            else:
                empty = self._build_empty_state(
                    "󰤯",
                    "Sin redes visibles",
                    "No se detectaron redes Wi-Fi cercanas",
                    retry=True,
                )
            self.list_box.append(empty)
            return

        self.section_lbl.set_visible(True)
        for net in self.networks:
            self.list_box.append(self._build_network_item(net))

    def _build_empty_state(self, icon: str, title: str, desc: str, retry: bool = False) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class("empty-box")
        box.set_halign(Gtk.Align.CENTER)

        ic = Gtk.Label(label=icon)
        ic.add_css_class("empty-icon")
        box.append(ic)

        tl = Gtk.Label(label=title)
        tl.add_css_class("empty-title")
        box.append(tl)

        ds = Gtk.Label(label=desc)
        ds.add_css_class("empty-desc")
        box.append(ds)

        if retry:
            btn = Gtk.Button(label="Reintentar")
            btn.add_css_class("pill-secondary")
            btn.set_margin_top(8)
            btn.set_halign(Gtk.Align.CENTER)
            btn.connect("clicked", lambda *_: self.refresh(rescan=True))
            box.append(btn)

        return box

    def _build_network_item(self, net: NetworkInfo) -> Gtk.Box:
        is_expanded = self.expanded_ssid == net.ssid
        show_pw = is_expanded and (
            (not net.saved and net.secured) or (self.password_mode_ssid == net.ssid)
        )

        item = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        item.add_css_class("net-item")
        if net.active:
            item.add_css_class("active")
        if is_expanded:
            item.add_css_class("expanded")

        # Main clickable row
        row_btn = Gtk.Button()
        row_btn.add_css_class("net-row-btn")
        row_btn.connect("clicked", self._on_row_clicked, net)

        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        row_box.set_valign(Gtk.Align.CENTER)

        ic = Gtk.Label(label=signal_icon(net.signal))
        ic.add_css_class("net-icon")
        if net.active:
            ic.add_css_class("active")
        elif net.saved:
            ic.add_css_class("saved")
        row_box.append(ic)

        ssid_lbl = Gtk.Label(label=net.ssid, xalign=0)
        ssid_lbl.add_css_class("net-ssid")
        ssid_lbl.set_hexpand(True)
        ssid_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        row_box.append(ssid_lbl)

        if net.active:
            badge = Gtk.Label(label="Conectada")
            badge.add_css_class("net-badge-active")
            row_box.append(badge)
        elif net.saved:
            badge = Gtk.Label(label="Guardada")
            badge.add_css_class("net-badge-saved")
            row_box.append(badge)

        if net.secured:
            lock = Gtk.Label(label="󰌾")
            lock.add_css_class("net-lock")
            row_box.append(lock)

        sig_lbl = Gtk.Label(label=f"{net.signal}%", xalign=1)
        sig_lbl.add_css_class("net-signal")
        row_box.append(sig_lbl)

        row_btn.set_child(row_box)
        item.append(row_btn)

        # Inline expandable action drawer
        if is_expanded:
            drawer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            drawer.add_css_class("drawer-box")

            if net.active and self.active_ip:
                info = Gtk.Label(label=f"IP: {self.active_ip}  ·  Seguridad: {net.security or 'Abierta'}", xalign=0)
                info.add_css_class("drawer-info")
                drawer.append(info)

            pw_entry: Gtk.PasswordEntry | None = None
            if show_pw:
                pw_entry = Gtk.PasswordEntry()
                pw_entry.add_css_class("pw-entry")
                pw_entry.set_show_peek_icon(True)
                pw_entry.set_property("placeholder-text", "Contraseña de la red...")
                pw_entry.set_hexpand(True)
                pw_entry.connect("activate", lambda e, n=net: self._do_connect(n, e.get_text()))
                drawer.append(pw_entry)
                self._active_pw_entry = pw_entry
                GLib.idle_add(pw_entry.grab_focus)

            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            if net.active:
                disc_btn = Gtk.Button(label="Desconectar")
                disc_btn.add_css_class("pill-secondary")
                disc_btn.set_hexpand(True)
                disc_btn.set_sensitive(not self.busy)
                disc_btn.connect("clicked", lambda *_, n=net: self._do_disconnect(n))
                actions.append(disc_btn)

                forget_btn = Gtk.Button(label="Olvidar")
                forget_btn.add_css_class("pill-danger")
                forget_btn.set_sensitive(not self.busy)
                forget_btn.connect("clicked", lambda *_, n=net: self._do_forget(n))
                actions.append(forget_btn)

            elif net.saved:
                conn_btn = Gtk.Button(label="Conectar")
                conn_btn.add_css_class("pill-primary")
                conn_btn.set_hexpand(True)
                conn_btn.set_sensitive(not self.busy)
                if show_pw and pw_entry is not None:
                    conn_btn.connect("clicked", lambda *_, n=net, e=pw_entry: self._do_connect(n, e.get_text()))
                else:
                    conn_btn.connect("clicked", lambda *_, n=net: self._do_connect(n, None))
                actions.append(conn_btn)

                if net.secured:
                    pw_btn = Gtk.Button(label="Ocultar" if show_pw else "Contraseña")
                    pw_btn.add_css_class("pill-secondary")
                    pw_btn.set_sensitive(not self.busy)
                    pw_btn.connect("clicked", lambda *_, n=net: self._toggle_password_mode(n))
                    actions.append(pw_btn)

                forget_btn = Gtk.Button(label="Olvidar")
                forget_btn.add_css_class("pill-danger")
                forget_btn.set_sensitive(not self.busy)
                forget_btn.connect("clicked", lambda *_, n=net: self._do_forget(n))
                actions.append(forget_btn)

            else:
                conn_btn = Gtk.Button(label="Conectar")
                conn_btn.add_css_class("pill-primary")
                conn_btn.set_hexpand(True)
                conn_btn.set_sensitive(not self.busy)
                if pw_entry is not None:
                    conn_btn.connect("clicked", lambda *_, n=net, e=pw_entry: self._do_connect(n, e.get_text()))
                else:
                    conn_btn.connect("clicked", lambda *_, n=net: self._do_connect(n, None))
                actions.append(conn_btn)

                cancel_btn = Gtk.Button(label="Cancelar")
                cancel_btn.add_css_class("pill-secondary")
                cancel_btn.set_sensitive(not self.busy)
                cancel_btn.connect("clicked", lambda *_: self._collapse_drawer())
                actions.append(cancel_btn)

            drawer.append(actions)
            item.append(drawer)

        return item

    def _on_row_clicked(self, _btn: Gtk.Button, net: NetworkInfo) -> None:
        if self.busy:
            return
        if self.expanded_ssid == net.ssid:
            self.expanded_ssid = None
            self.password_mode_ssid = None
        else:
            self.expanded_ssid = net.ssid
            self.password_mode_ssid = None
        self._render_list()

    def _toggle_password_mode(self, net: NetworkInfo) -> None:
        if self.password_mode_ssid == net.ssid:
            self.password_mode_ssid = None
        else:
            self.password_mode_ssid = net.ssid
        self._render_list()

    def _collapse_drawer(self) -> None:
        self.expanded_ssid = None
        self.password_mode_ssid = None
        self._render_list()

    def _do_connect(self, net: NetworkInfo, password: str | None) -> None:
        if self.busy:
            return
        if password is not None and not password.strip():
            self._set_banner("Ingresá una contraseña para continuar", kind="error", auto_hide_ms=3000)
            if self._active_pw_entry:
                self._active_pw_entry.grab_focus()
            return

        self.busy = True
        self._render_list()
        self._set_banner(f"Conectando a {net.ssid}...", spinning=True)

        def worker() -> None:
            ok, err = self.nm.connect(net, password)
            GLib.idle_add(self._on_action_done, "connect", net, ok, err)

        threading.Thread(target=worker, daemon=True).start()

    def _do_disconnect(self, net: NetworkInfo) -> None:
        if self.busy:
            return
        self.busy = True
        self._render_list()
        self._set_banner(f"Desconectando de {net.ssid}...", spinning=True)

        def worker() -> None:
            ok, err = self.nm.disconnect(net)
            GLib.idle_add(self._on_action_done, "disconnect", net, ok, err)

        threading.Thread(target=worker, daemon=True).start()

    def _do_forget(self, net: NetworkInfo) -> None:
        if self.busy:
            return
        self.busy = True
        self._render_list()
        self._set_banner(f"Olvidando {net.ssid}...", spinning=True)

        def worker() -> None:
            ok, err = self.nm.forget(net)
            GLib.idle_add(self._on_action_done, "forget", net, ok, err)

        threading.Thread(target=worker, daemon=True).start()

    def _on_action_done(self, action: str, net: NetworkInfo, ok: bool, err: str) -> bool:
        self.busy = False
        if ok:
            self.expanded_ssid = None
            self.password_mode_ssid = None
            msg = {
                "connect": f"Conectado a {net.ssid}",
                "disconnect": f"Desconectado de {net.ssid}",
                "forget": f"Red {net.ssid} olvidada",
            }[action]
            self._set_banner(msg, kind="success", auto_hide_ms=2600)
        else:
            # If auth failed on a saved secured network, open password input automatically
            if action == "connect" and net.secured:
                self.expanded_ssid = net.ssid
                self.password_mode_ssid = net.ssid
            self._set_banner(friendly_error(err), kind="error", auto_hide_ms=4500)

        self.refresh(rescan=False, follow_up_rescan=False)
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

    app = WifiPopupApp()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (app.quit(), False)[1])
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: (app.quit(), False)[1])
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
