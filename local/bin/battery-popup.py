#!/usr/bin/env python3
"""Modern top-center Waybar battery alert popup (GTK4 + gtk4-layer-shell)."""

from __future__ import annotations

import argparse
import atexit
import ctypes
import glob
import os
import signal
import sys

try:
    ctypes.CDLL("libgtk4-layer-shell.so", mode=ctypes.RTLD_GLOBAL)
except OSError:
    pass

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")

from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell  # noqa: E402

PID_FILE = "/tmp/waybar-battery-popup.pid"

LEVEL_CONFIG = {
    "warning": {
        "badge": "ALERTA DE BATERÍA",
        "title": "Batería baja",
        "subtitle": "Conecta el cargador pronto para evitar interrupciones.",
        "icon": "󰁻",
        "timeout": 10.0,
        "css_class": "level-warning",
    },
    "low": {
        "badge": "BATERÍA MUY BAJA",
        "title": "Batería muy baja",
        "subtitle": "Queda muy poca energía. Conecta el cargador ahora.",
        "icon": "󰁺",
        "timeout": 14.0,
        "css_class": "level-low",
    },
    "critical": {
        "badge": "BATERÍA CRÍTICA",
        "title": "Batería crítica",
        "subtitle": "El equipo se apagará en breve. Guarda tu trabajo y conecta el cargador.",
        "icon": "󰂃",
        "timeout": 18.0,
        "css_class": "level-critical",
    },
}

CSS = """
window,
window.background,
window.battery-window {
    background: transparent;
    background-color: transparent;
    background-image: none;
    box-shadow: none;
    border: none;
}

.battery-card {
    background-color: rgba(13, 17, 23, 0.94);
    background-image: none;
    border-radius: 16px;
    border: 1.5px solid rgba(249, 226, 175, 0.42);
    padding: 0;
    color: #cdd6f4;
    font-family: "JetBrainsMono Nerd Font Propo", "Adwaita Sans", sans-serif;
}

.battery-card.level-warning {
    border-color: rgba(249, 226, 175, 0.45);
}

.battery-card.level-low {
    border-color: rgba(243, 139, 168, 0.55);
}

.battery-card.level-critical {
    border-color: rgba(255, 92, 124, 0.78);
    background-color: rgba(22, 13, 19, 0.95);
}

.accent-bar {
    min-height: 4px;
    border-radius: 16px 16px 0 0;
}

.level-warning .accent-bar {
    background-color: #f9e2af;
}

.level-low .accent-bar {
    background-color: #f38ba8;
}

.level-critical .accent-bar {
    background-color: #ff5c7c;
}

.card-body {
    padding: 16px 18px 14px 18px;
}

.icon-badge {
    min-width: 54px;
    min-height: 54px;
    border-radius: 14px;
    font-size: 28px;
}

.level-warning .icon-badge {
    background-color: rgba(249, 226, 175, 0.14);
    border: 1px solid rgba(249, 226, 175, 0.28);
    color: #f9e2af;
}

.level-low .icon-badge {
    background-color: rgba(243, 139, 168, 0.15);
    border: 1px solid rgba(243, 139, 168, 0.32);
    color: #f38ba8;
}

.level-critical .icon-badge {
    background-color: rgba(255, 92, 124, 0.20);
    border: 1px solid rgba(255, 92, 124, 0.48);
    color: #ff5c7c;
}

.severity-pill {
    border-radius: 999px;
    padding: 2px 9px;
    font-size: 9.5px;
    font-weight: 800;
    letter-spacing: 0.7px;
}

.level-warning .severity-pill {
    background-color: rgba(249, 226, 175, 0.14);
    color: #f9e2af;
}

.level-low .severity-pill {
    background-color: rgba(243, 139, 168, 0.16);
    color: #f38ba8;
}

.level-critical .severity-pill {
    background-color: rgba(255, 92, 124, 0.22);
    color: #ff7b96;
}

.alert-title {
    color: #f0f6fc;
    font-size: 16px;
    font-weight: 800;
}

.alert-subtitle {
    color: #9da7b3;
    font-size: 11.5px;
    font-weight: 500;
}

.pct-big {
    font-size: 22px;
    font-weight: 800;
}

.level-warning .pct-big {
    color: #f9e2af;
}

.level-low .pct-big {
    color: #f38ba8;
}

.level-critical .pct-big {
    color: #ff5c7c;
}

button.close-btn,
button.close-btn:focus,
button.close-btn:active {
    background: rgba(255, 255, 255, 0.05);
    background-image: none;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 999px;
    color: #9da7b3;
    min-width: 26px;
    min-height: 26px;
    padding: 0;
    font-size: 12px;
    box-shadow: none;
    text-shadow: none;
    outline: none;
    transition: background-color 140ms ease, color 140ms ease;
}

button.close-btn:hover {
    background-color: rgba(255, 255, 255, 0.14);
    color: #f0f6fc;
}

progressbar.battery-meter trough {
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 999px;
    min-height: 8px;
}

progressbar.battery-meter progress {
    border-radius: 999px;
    min-height: 8px;
}

.level-warning progressbar.battery-meter progress {
    background-color: #f9e2af;
}

.level-low progressbar.battery-meter progress {
    background-color: #f38ba8;
}

.level-critical progressbar.battery-meter progress {
    background-color: #ff5c7c;
}

progressbar.timer-bar trough {
    background-color: rgba(255, 255, 255, 0.04);
    border-radius: 0 0 16px 16px;
    min-height: 3px;
}

progressbar.timer-bar progress {
    border-radius: 0 0 16px 16px;
    min-height: 3px;
}

.level-warning progressbar.timer-bar progress {
    background-color: rgba(249, 226, 175, 0.55);
}

.level-low progressbar.timer-bar progress {
    background-color: rgba(243, 139, 168, 0.60);
}

.level-critical progressbar.timer-bar progress {
    background-color: rgba(255, 92, 124, 0.72);
}

.hint-label {
    color: #6e7681;
    font-size: 9.5px;
    font-weight: 500;
}
"""


def _is_discharging() -> bool:
    for bat in sorted(glob.glob("/sys/class/power_supply/BAT*")):
        status_path = os.path.join(bat, "status")
        try:
            with open(status_path, encoding="utf-8") as fh:
                return fh.read().strip() == "Discharging"
        except OSError:
            continue
    return True


def _kill_previous() -> None:
    if not os.path.exists(PID_FILE):
        return
    try:
        with open(PID_FILE, encoding="utf-8") as fh:
            old_pid = int(fh.read().strip())
        if old_pid != os.getpid():
            os.kill(old_pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass


def _cleanup_pid() -> None:
    try:
        if os.path.exists(PID_FILE):
            with open(PID_FILE, encoding="utf-8") as fh:
                if fh.read().strip() == str(os.getpid()):
                    os.remove(PID_FILE)
    except OSError:
        pass


class BatteryPopupApp(Gtk.Application):
    def __init__(self, level: str, capacity: int, timeout: float, test_mode: bool) -> None:
        super().__init__(application_id=None)
        self.cfg = LEVEL_CONFIG[level]
        self.capacity = max(0, min(100, capacity))
        self.timeout_total = max(2.0, timeout)
        self.remaining = self.timeout_total
        self.test_mode = test_mode
        self.hovered = False
        self.win: Gtk.ApplicationWindow | None = None
        self.timer_bar: Gtk.ProgressBar | None = None

    def do_activate(self) -> None:
        self._load_css()
        self._build_window()
        if self.win:
            self.win.present()
        GLib.timeout_add(50, self._tick_timer)
        if not self.test_mode:
            GLib.timeout_add(1000, self._check_charger)

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
        win.add_css_class("battery-window")
        win.set_decorated(False)
        win.set_resizable(False)
        self.win = win

        if Gtk4LayerShell.is_supported():
            Gtk4LayerShell.init_for_window(win)
            Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_namespace(win, "battery-popup")
            Gtk4LayerShell.set_exclusive_zone(win, 0)
            Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.NONE)
            Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.TOP, True)
            Gtk4LayerShell.set_margin(win, Gtk4LayerShell.Edge.TOP, 10)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("battery-card")
        card.add_css_class(self.cfg["css_class"])
        card.set_size_request(440, -1)

        # Hover pauses auto-dismiss
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._on_hover_enter)
        motion.connect("leave", self._on_hover_leave)
        card.add_controller(motion)

        # Clicking anywhere on the card dismisses it
        click = Gtk.GestureClick()
        click.connect("released", lambda *_args: self.quit())
        card.add_controller(click)

        # Top colored accent bar
        accent = Gtk.Box()
        accent.add_css_class("accent-bar")
        card.append(accent)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.add_css_class("card-body")

        # Main row: Icon + Info + Percentage/Close
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        top_row.set_valign(Gtk.Align.CENTER)

        icon_box = Gtk.Label(label=self.cfg["icon"])
        icon_box.add_css_class("icon-badge")
        icon_box.set_valign(Gtk.Align.CENTER)
        top_row.append(icon_box)

        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        text_col.set_hexpand(True)

        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_row.set_valign(Gtk.Align.CENTER)

        pill = Gtk.Label(label=self.cfg["badge"])
        pill.add_css_class("severity-pill")
        pill.set_halign(Gtk.Align.START)
        header_row.append(pill)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        header_row.append(spacer)

        close_btn = Gtk.Button(label="✕")
        close_btn.add_css_class("close-btn")
        close_btn.set_tooltip_text("Cerrar notificación")
        close_btn.connect("clicked", lambda _b: self.quit())
        header_row.append(close_btn)

        text_col.append(header_row)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_row.set_valign(Gtk.Align.BASELINE)

        title = Gtk.Label(label=self.cfg["title"], xalign=0)
        title.add_css_class("alert-title")
        title.set_hexpand(True)
        title_row.append(title)

        pct_lbl = Gtk.Label(label=f"{self.capacity}%", xalign=1)
        pct_lbl.add_css_class("pct-big")
        title_row.append(pct_lbl)

        text_col.append(title_row)

        subtitle = Gtk.Label(label=self.cfg["subtitle"], xalign=0)
        subtitle.add_css_class("alert-subtitle")
        subtitle.set_wrap(True)
        subtitle.set_max_width_chars(38)
        text_col.append(subtitle)

        top_row.append(text_col)
        body.append(top_row)

        # Battery visual progress bar
        meter = Gtk.ProgressBar()
        meter.add_css_class("battery-meter")
        meter.set_fraction(max(0.03, self.capacity / 100.0))
        body.append(meter)

        # Subtle hint footer
        hint = Gtk.Label(label="Haz clic para cerrar · Se ocultará al conectar el cargador", xalign=0.5)
        hint.add_css_class("hint-label")
        body.append(hint)

        card.append(body)

        # Auto-dismiss countdown bar at the very bottom
        timer_bar = Gtk.ProgressBar()
        timer_bar.add_css_class("timer-bar")
        timer_bar.set_fraction(1.0)
        self.timer_bar = timer_bar
        card.append(timer_bar)

        win.set_child(card)

    def _on_hover_enter(self, *_args) -> None:
        self.hovered = True

    def _on_hover_leave(self, *_args) -> None:
        self.hovered = False

    def _tick_timer(self) -> bool:
        if not self.hovered:
            self.remaining -= 0.05
            if self.timer_bar:
                self.timer_bar.set_fraction(max(0.0, self.remaining / self.timeout_total))
            if self.remaining <= 0:
                self.quit()
                return False
        return True

    def _check_charger(self) -> bool:
        if not _is_discharging():
            self.quit()
            return False
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Modern Waybar battery alert popup")
    parser.add_argument(
        "--level",
        choices=["warning", "low", "critical"],
        default="warning",
        help="Alert severity level",
    )
    parser.add_argument(
        "--capacity",
        type=int,
        default=20,
        help="Battery percentage (0-100)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Auto-dismiss duration in seconds",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode (do not auto-close if charger is connected)",
    )
    args = parser.parse_args()

    _kill_previous()
    with open(PID_FILE, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))
    atexit.register(_cleanup_pid)

    timeout = args.timeout if args.timeout is not None else LEVEL_CONFIG[args.level]["timeout"]
    app = BatteryPopupApp(args.level, args.capacity, timeout, args.test)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: (app.quit(), False)[1])
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: (app.quit(), False)[1])
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
