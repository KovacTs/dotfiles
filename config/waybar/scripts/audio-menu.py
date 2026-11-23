#!/usr/bin/env python3
"""Minimalist floating Audio panel for Waybar + Hyprland (GTK4 + gtk4-layer-shell)."""

from __future__ import annotations

import atexit
import ctypes
import json
import os
import re
import signal
import subprocess
import threading
from dataclasses import dataclass

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

PID_FILE = "/tmp/waybar-audio-popup.pid"

CSS = """
window,
window.background,
window.background.audio-backdrop,
window.audio-backdrop {
    background: transparent;
    background-color: transparent;
    background-image: none;
    box-shadow: none;
    border: none;
}

tooltip {
    background-color: rgba(13, 17, 23, 0.96);
    border: 1px solid rgba(229, 192, 123, 0.25);
    border-radius: 8px;
    color: #cdd6f4;
}

.audio-card {
    background-color: rgba(13, 17, 23, 0.96);
    background-image: none;
    border: 1px solid rgba(229, 192, 123, 0.24);
    border-radius: 13px;
    padding: 11px;
    box-shadow: none;
    color: #cdd6f4;
    font-family: "JetBrainsMono Nerd Font Propo", "Adwaita Sans", sans-serif;
    font-size: 11px;
}

.header-badge {
    background-color: rgba(229, 192, 123, 0.14);
    color: #e5c07b;
    border-radius: 999px;
    min-width: 26px;
    min-height: 26px;
    font-size: 13px;
}

.header-title {
    color: #e6edf3;
    font-size: 11.5px;
    font-weight: 700;
}

.header-subtitle {
    color: #8b949e;
    font-size: 9.2px;
    font-weight: 500;
}

button.icon-btn,
button.icon-btn:focus,
button.icon-btn:active {
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
    outline: none;
    transition: background-color 140ms ease, color 140ms ease;
}

button.icon-btn:hover {
    background-color: rgba(49, 50, 68, 0.78);
    color: #e6edf3;
}

.divider {
    background-color: rgba(255, 255, 255, 0.06);
    min-height: 1px;
}

.section-label {
    color: #7f849c;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.5px;
    margin-left: 2px;
    margin-top: 2px;
}

scrolledwindow.dev-scroll,
scrolledwindow.dev-scroll viewport {
    background: transparent;
    background-color: transparent;
    background-image: none;
    border: none;
}

scrolledwindow.dev-scroll scrollbar {
    background: transparent;
}

scrolledwindow.dev-scroll scrollbar slider {
    background-color: rgba(229, 192, 123, 0.24);
    border-radius: 999px;
    min-width: 3px;
    min-height: 20px;
}

scrolledwindow.dev-scroll scrollbar slider:hover {
    background-color: rgba(229, 192, 123, 0.45);
}

.dev-card {
    background-color: rgba(22, 27, 36, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 7px 9px;
    transition: background-color 140ms ease, border-color 140ms ease;
}

.dev-card:hover {
    background-color: rgba(28, 34, 46, 0.94);
    border-color: rgba(255, 255, 255, 0.11);
}

.dev-card.sink.active {
    background-color: rgba(229, 192, 123, 0.11);
    border-color: rgba(229, 192, 123, 0.34);
}

.dev-card.source.active {
    background-color: rgba(137, 180, 250, 0.11);
    border-color: rgba(137, 180, 250, 0.34);
}

button.dev-select-btn,
button.dev-select-btn:focus,
button.dev-select-btn:active {
    background: transparent;
    background-color: transparent;
    background-image: none;
    border: none;
    border-radius: 7px;
    padding: 2px 4px;
    color: #cdd6f4;
    box-shadow: none;
    text-shadow: none;
    outline: none;
}

button.dev-select-btn:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

.dev-radio {
    color: #585b70;
    font-size: 10px;
    min-width: 12px;
}

.dev-card.sink.active .dev-radio {
    color: #e5c07b;
}

.dev-card.source.active .dev-radio {
    color: #89b4fa;
}

.dev-icon {
    color: #8b949e;
    font-size: 12px;
    min-width: 16px;
}

.dev-card.sink.active .dev-icon {
    color: #e5c07b;
}

.dev-card.source.active .dev-icon {
    color: #89b4fa;
}

.dev-name {
    color: #e6edf3;
    font-size: 10.2px;
    font-weight: 600;
}

.dev-sub {
    color: #7f849c;
    font-size: 8.8px;
    font-weight: 500;
}

.active-pill {
    border-radius: 999px;
    padding: 0px 6px;
    font-size: 8.5px;
    font-weight: 700;
}

.active-pill.sink {
    background-color: rgba(229, 192, 123, 0.18);
    border: 1px solid rgba(229, 192, 123, 0.35);
    color: #e5c07b;
}

.active-pill.source {
    background-color: rgba(137, 180, 250, 0.18);
    border: 1px solid rgba(137, 180, 250, 0.35);
    color: #89b4fa;
}

button.mute-btn,
button.mute-btn:focus,
button.mute-btn:active {
    background-color: rgba(49, 50, 68, 0.55);
    background-image: none;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 7px;
    padding: 2px 6px;
    min-width: 24px;
    min-height: 22px;
    color: #cdd6f4;
    font-size: 11px;
    box-shadow: none;
    text-shadow: none;
    outline: none;
}

button.mute-btn:hover {
    background-color: rgba(69, 71, 90, 0.78);
    color: #e6edf3;
}

button.mute-btn.muted {
    background-color: rgba(243, 139, 168, 0.16);
    border-color: rgba(243, 139, 168, 0.38);
    color: #f38ba8;
}

scale.dev-scale {
    padding: 3px 0;
}

scale.dev-scale trough {
    background-color: rgba(49, 50, 68, 0.90);
    background-image: none;
    border-radius: 999px;
    min-height: 5px;
    border: none;
}

scale.dev-scale.sink-scale highlight {
    background-color: #e5c07b;
    background-image: none;
    border-radius: 999px;
    border: none;
}

scale.dev-scale.source-scale highlight {
    background-color: #89b4fa;
    background-image: none;
    border-radius: 999px;
    border: none;
}

scale.dev-scale.muted highlight {
    background-color: #6c7086;
}

scale.dev-scale slider {
    background-color: #e6edf3;
    background-image: none;
    border: none;
    border-radius: 999px;
    min-width: 11px;
    min-height: 11px;
    margin: -3px 0;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.45);
}

.vol-val {
    color: #8b949e;
    font-size: 9.3px;
    min-width: 30px;
}

.empty-box {
    background-color: rgba(22, 27, 36, 0.55);
    border: 1px dashed rgba(255, 255, 255, 0.07);
    border-radius: 9px;
    padding: 10px;
    color: #7f849c;
    font-size: 9.6px;
}
"""


@dataclass
class AudioDevice:
    kind: str  # "sink" or "source"
    name: str
    label: str
    subtitle: str
    full_desc: str
    volume_pct: int
    muted: bool
    is_default: bool
    icon: str


def _parse_volume_pct(vol_obj: dict) -> int:
    if not isinstance(vol_obj, dict):
        return 50
    vals: list[int] = []
    for ch in vol_obj.values():
        if isinstance(ch, dict):
            vp = str(ch.get("value_percent", ""))
            m = re.search(r"(\d+)", vp)
            if m:
                vals.append(int(m.group(1)))
    if not vals:
        return 50
    return max(0, min(100, round(sum(vals) / len(vals))))


def _pick_icon(kind: str, name: str, desc: str, port_name: str, bus: str) -> str:
    hay = f"{name} {desc} {port_name} {bus}".lower()
    if "bluez" in hay or "bluetooth" in hay:
        return "󰂯"
    if kind == "source":
        if "headset" in hay or "headphone" in hay:
            return "󰋎"
        return "󰍬"
    if "headphone" in hay or "headset" in hay or "auricular" in hay:
        return "󰋋"
    if "hdmi" in hay or "displayport" in hay:
        return "󰍹"
    if "usb" in hay:
        return "󰕾"
    return "󰓃"


def _friendly_labels(entry: dict) -> tuple[str, str, str]:
    desc = str(entry.get("description") or entry.get("name") or "Dispositivo").strip()
    active_port = str(entry.get("active_port") or "")
    port_desc = ""
    for port in entry.get("ports") or []:
        if isinstance(port, dict) and port.get("name") == active_port:
            port_desc = str(port.get("description") or "").strip()
            break
    if port_desc and port_desc.lower() not in desc.lower():
        return port_desc, desc, f"{port_desc} — {desc}"
    return desc, "", desc


class AudioBackend:
    def __init__(self) -> None:
        self._env = {**os.environ, "LC_ALL": "C"}

    def _run(self, cmd: list[str], timeout: int = 5, c_locale: bool = False) -> tuple[int, str, str]:
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

    def _get_default(self, kind: str) -> str:
        rc, out, _ = self._run(["pactl", f"get-default-{kind}"], c_locale=True)
        return out.strip() if rc == 0 else ""

    def list_devices(self, kind: str) -> list[AudioDevice]:
        plural = "sinks" if kind == "sink" else "sources"
        rc, out, _ = self._run(["pactl", "-f", "json", "list", plural])
        if rc != 0 or not out.strip():
            return []
        try:
            entries = json.loads(out)
        except Exception:
            return []

        default_name = self._get_default(kind)
        devices: list[AudioDevice] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "")
            if not name:
                continue
            props = entry.get("properties") or {}
            if kind == "source":
                # Skip virtual monitor sources (loopback of output sinks)
                if name.endswith(".monitor") or entry.get("monitor_of") or props.get("device.class") == "monitor":
                    continue

            label, subtitle, full_desc = _friendly_labels(entry)
            vol_pct = _parse_volume_pct(entry.get("volume") or {})
            muted = bool(entry.get("mute", False))
            active_port = str(entry.get("active_port") or "")
            bus = str(props.get("device.bus") or "")
            icon = _pick_icon(kind, name, full_desc, active_port, bus)

            devices.append(
                AudioDevice(
                    kind=kind,
                    name=name,
                    label=label,
                    subtitle=subtitle,
                    full_desc=full_desc,
                    volume_pct=vol_pct,
                    muted=muted,
                    is_default=(name == default_name),
                    icon=icon,
                )
            )

        devices.sort(key=lambda d: (not d.is_default, d.label.lower()))
        return devices

    def read_all(self) -> tuple[list[AudioDevice], list[AudioDevice]]:
        return self.list_devices("sink"), self.list_devices("source")

    def set_default(self, kind: str, name: str) -> None:
        self._run(["pactl", f"set-default-{kind}", name], c_locale=True)
        # Move active streams so playing/recording apps switch immediately
        stream_type = "sink-inputs" if kind == "sink" else "source-outputs"
        move_cmd = "move-sink-input" if kind == "sink" else "move-source-output"
        rc, out, _ = self._run(["pactl", "-f", "json", "list", stream_type], c_locale=True)
        if rc == 0 and out.strip():
            try:
                for stream in json.loads(out):
                    idx = stream.get("index")
                    if idx is not None:
                        self._run(["pactl", move_cmd, str(idx), name], c_locale=True)
            except Exception:
                pass

    def set_volume(self, kind: str, name: str, pct: int) -> None:
        pct = max(0, min(100, int(pct)))
        self._run(["pactl", f"set-{kind}-volume", name, f"{pct}%"], c_locale=True)

    def toggle_mute(self, kind: str, name: str) -> None:
        self._run(["pactl", f"set-{kind}-mute", name, "toggle"], c_locale=True)


class AudioPopupApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=None)
        self.backend = AudioBackend()
        self.win: Gtk.ApplicationWindow | None = None
        self.root: Gtk.Box | None = None
        self.card: Gtk.Box | None = None
        self._debounces: dict[tuple[str, str], int] = {}

    def do_activate(self) -> None:
        self._load_css()
        self._build_window()
        self.win.present()
        self.refresh()

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
        win.add_css_class("audio-backdrop")
        win.set_decorated(False)
        win.set_resizable(True)
        self.win = win

        if Gtk4LayerShell.is_supported():
            Gtk4LayerShell.init_for_window(win)
            Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_namespace(win, "audio-popup")
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

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("audio-card")
        card.set_size_request(336, -1)
        card.set_hexpand(True)
        card.set_halign(Gtk.Align.END)
        card.set_valign(Gtk.Align.START)
        card.set_margin_top(4)
        card.set_margin_end(125)
        self.card = card

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_valign(Gtk.Align.CENTER)

        badge = Gtk.Label(label="󰕾")
        badge.add_css_class("header-badge")
        badge.set_halign(Gtk.Align.CENTER)
        badge.set_valign(Gtk.Align.CENTER)
        header.append(badge)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title_box.set_hexpand(True)
        title = Gtk.Label(label="Dispositivos de audio", xalign=0)
        title.add_css_class("header-title")
        title_box.append(title)

        self.subtitle_lbl = Gtk.Label(label="Cargando...", xalign=0)
        self.subtitle_lbl.add_css_class("header-subtitle")
        title_box.append(self.subtitle_lbl)
        header.append(title_box)

        refresh_btn = Gtk.Button(label="󰑐")
        refresh_btn.add_css_class("icon-btn")
        refresh_btn.set_tooltip_text("Actualizar dispositivos")
        refresh_btn.connect("clicked", lambda _b: self.refresh())
        header.append(refresh_btn)

        card.append(header)

        div = Gtk.Box()
        div.add_css_class("divider")
        card.append(div)

        # Scrollable body with Output + Input sections
        scroll = Gtk.ScrolledWindow()
        scroll.add_css_class("dev-scroll")
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_height(True)
        scroll.set_max_content_height(460)

        self.body_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        scroll.set_child(self.body_box)
        card.append(scroll)

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

    def refresh(self) -> None:
        def worker() -> None:
            sinks, sources = self.backend.read_all()
            GLib.idle_add(self._render_devices, sinks, sources)

        threading.Thread(target=worker, daemon=True).start()

    def _render_devices(self, sinks: list[AudioDevice], sources: list[AudioDevice]) -> bool:
        self.subtitle_lbl.set_label(f"{len(sinks)} salida(s) · {len(sources)} entrada(s)")

        child = self.body_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.body_box.remove(child)
            child = nxt

        # Outputs
        out_hdr = Gtk.Label(label="SALIDA", xalign=0)
        out_hdr.add_css_class("section-label")
        self.body_box.append(out_hdr)

        if sinks:
            for dev in sinks:
                self.body_box.append(self._build_device_card(dev))
        else:
            empty = Gtk.Label(label="No se encontraron dispositivos de salida", xalign=0)
            empty.add_css_class("empty-box")
            self.body_box.append(empty)

        # Inputs
        in_hdr = Gtk.Label(label="ENTRADA", xalign=0)
        in_hdr.add_css_class("section-label")
        self.body_box.append(in_hdr)

        if sources:
            for dev in sources:
                self.body_box.append(self._build_device_card(dev))
        else:
            empty = Gtk.Label(label="No se encontraron dispositivos de entrada", xalign=0)
            empty.add_css_class("empty-box")
            self.body_box.append(empty)

        return False

    def _build_device_card(self, dev: AudioDevice) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        box.add_css_class("dev-card")
        box.add_css_class(dev.kind)
        if dev.is_default:
            box.add_css_class("active")

        # Top row: selector button + mute toggle
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        top.set_valign(Gtk.Align.CENTER)

        select_btn = Gtk.Button()
        select_btn.add_css_class("dev-select-btn")
        select_btn.set_hexpand(True)
        select_btn.set_tooltip_text(dev.full_desc)

        sel_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        sel_row.set_valign(Gtk.Align.CENTER)

        radio = Gtk.Label(label="●" if dev.is_default else "○")
        radio.add_css_class("dev-radio")
        sel_row.append(radio)

        icon_lbl = Gtk.Label(label=dev.icon)
        icon_lbl.add_css_class("dev-icon")
        sel_row.append(icon_lbl)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        text_box.set_hexpand(True)
        name_lbl = Gtk.Label(label=dev.label, xalign=0)
        name_lbl.add_css_class("dev-name")
        name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        name_lbl.set_max_width_chars(24)
        text_box.append(name_lbl)

        if dev.subtitle:
            sub_lbl = Gtk.Label(label=dev.subtitle, xalign=0)
            sub_lbl.add_css_class("dev-sub")
            sub_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            sub_lbl.set_max_width_chars(28)
            text_box.append(sub_lbl)

        sel_row.append(text_box)

        if dev.is_default:
            pill = Gtk.Label(label="Activo")
            pill.add_css_class("active-pill")
            pill.add_css_class(dev.kind)
            sel_row.append(pill)

        select_btn.set_child(sel_row)
        select_btn.connect("clicked", self._on_select_device, dev.kind, dev.name)
        top.append(select_btn)

        mute_icon = (
            ("󰝟" if dev.muted else "󰕾")
            if dev.kind == "sink"
            else ("󰍭" if dev.muted else "󰍬")
        )
        mute_btn = Gtk.Button(label=mute_icon)
        mute_btn.add_css_class("mute-btn")
        if dev.muted:
            mute_btn.add_css_class("muted")
        mute_btn.set_tooltip_text("Activar sonido" if dev.muted else "Silenciar")
        mute_btn.connect("clicked", self._on_toggle_mute, dev.kind, dev.name)
        top.append(mute_btn)

        box.append(top)

        # Bottom row: volume slider + percentage
        vol_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vol_row.set_valign(Gtk.Align.CENTER)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.add_css_class("dev-scale")
        scale.add_css_class(f"{dev.kind}-scale")
        if dev.muted:
            scale.add_css_class("muted")
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.set_value(dev.volume_pct)

        val_lbl = Gtk.Label(label=f"{dev.volume_pct}%", xalign=1)
        val_lbl.add_css_class("vol-val")

        scale.connect("value-changed", self._on_vol_changed, dev.kind, dev.name, val_lbl)
        vol_row.append(scale)
        vol_row.append(val_lbl)

        box.append(vol_row)
        return box

    def _on_select_device(self, _btn: Gtk.Button, kind: str, name: str) -> None:
        def worker() -> None:
            self.backend.set_default(kind, name)
            sinks, sources = self.backend.read_all()
            GLib.idle_add(self._render_devices, sinks, sources)

        threading.Thread(target=worker, daemon=True).start()

    def _on_toggle_mute(self, _btn: Gtk.Button, kind: str, name: str) -> None:
        def worker() -> None:
            self.backend.toggle_mute(kind, name)
            sinks, sources = self.backend.read_all()
            GLib.idle_add(self._render_devices, sinks, sources)

        threading.Thread(target=worker, daemon=True).start()

    def _on_vol_changed(
        self, scale: Gtk.Scale, kind: str, name: str, val_lbl: Gtk.Label
    ) -> None:
        val = int(round(scale.get_value()))
        val_lbl.set_label(f"{val}%")
        key = (kind, name)
        prev = self._debounces.get(key)
        if prev is not None:
            GLib.source_remove(prev)
        self._debounces[key] = GLib.timeout_add(35, self._commit_vol, kind, name, val)

    def _commit_vol(self, kind: str, name: str, val: int) -> bool:
        self._debounces.pop((kind, name), None)
        threading.Thread(
            target=self.backend.set_volume, args=(kind, name, val), daemon=True
        ).start()
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

    app = AudioPopupApp()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (app.quit(), False)[1])
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: (app.quit(), False)[1])
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
