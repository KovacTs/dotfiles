#!/usr/bin/env python3
"""Smooth marquee / scrolling MPRIS module for Waybar (Spotify, browsers, mpv, etc.)."""

from __future__ import annotations

import html
import json
import signal
import subprocess
import sys
import threading
import time

MAX_LEN = 26            # Visible characters before scrolling kicks in
SCROLL_INTERVAL = 0.22  # Seconds per 1-char step (~4.5 chars/sec)
PAUSE_TICKS = 6         # Pause ticks at offset 0 (~1.3s) so title start is easy to read
LOOP_GAP = "   •   "    # Separator between end and start while looping

FORMAT = "{{status}}\t{{playerName}}\t{{title}}\t{{artist}}\t{{xesam:albumArtist}}"

STATUS_ICONS = {
    "Playing": "▶",
    "Paused": "⏸",
}


class MediaState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.event = threading.Event()
        self.status = "Stopped"
        self.player = ""
        self.title = ""
        self.artist = ""
        self.version = 0
        self.stop_flag = False
        self.proc: subprocess.Popen[str] | None = None

    def update(self, status: str, player: str, title: str, artist: str) -> None:
        with self.lock:
            changed = (
                status != self.status
                or player != self.player
                or title != self.title
                or artist != self.artist
            )
            if changed:
                self.status = status
                self.player = player
                self.title = title
                self.artist = artist
                self.version += 1
                self.event.set()

    def clear(self) -> None:
        self.update("Stopped", "", "", "")

    def snapshot(self) -> tuple[str, str, str, str, int]:
        with self.lock:
            return self.status, self.player, self.title, self.artist, self.version

    def terminate(self) -> None:
        self.stop_flag = True
        self.event.set()
        proc = self.proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass


def parse_line(raw: str) -> tuple[str, str, str, str]:
    parts = raw.rstrip("\r\n").split("\t")
    while len(parts) < 5:
        parts.append("")
    status = parts[0].strip()
    player = parts[1].strip()
    title = " ".join(parts[2].split())
    artist = " ".join(parts[3].split()) or " ".join(parts[4].split())
    return status, player, title, artist


def watch_playerctl(state: MediaState) -> None:
    while not state.stop_flag:
        try:
            proc = subprocess.Popen(
                ["playerctl", "--follow", "metadata", "--format", FORMAT],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            state.proc = proc
        except FileNotFoundError:
            state.clear()
            time.sleep(5.0)
            continue

        assert proc.stdout is not None
        got_any = False
        for line in proc.stdout:
            if state.stop_flag:
                break
            got_any = True
            status, player, title, artist = parse_line(line)
            if not status or status == "Stopped" or (not title and not artist):
                state.clear()
            else:
                state.update(status, player, title, artist)

        proc.wait()
        state.proc = None
        if not state.stop_flag:
            if got_any:
                state.clear()
            time.sleep(1.0)


def build_display_text(title: str, artist: str) -> str:
    if title and artist:
        # Avoid duplicating artist when video title already starts with it identically
        if artist.lower() == title.lower():
            return title
        return f"{title} — {artist}"
    return title or artist


def emit(payload: dict[str, str]) -> bool:
    try:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return True
    except BrokenPipeError:
        return False


def main() -> int:
    state = MediaState()

    def handle_signal(_signum: int, _frame) -> None:
        state.terminate()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    watcher = threading.Thread(target=watch_playerctl, args=(state,), daemon=True)
    watcher.start()

    last_payload: dict[str, str] | None = None
    last_track_key: tuple[str, str] = ("", "")
    offset = 0
    pause_left = PAUSE_TICKS

    # Emit initial empty state so Waybar initializes cleanly
    emit({"text": "", "tooltip": "", "class": "stopped"})

    try:
        while not state.stop_flag:
            state.event.clear()
            status, player, title, artist, _ver = state.snapshot()

            if status not in STATUS_ICONS or (not title and not artist):
                payload = {"text": "", "tooltip": "", "class": "stopped"}
                if payload != last_payload:
                    if not emit(payload):
                        break
                    last_payload = payload
                last_track_key = ("", "")
                offset = 0
                pause_left = PAUSE_TICKS
                state.event.wait(timeout=2.0)
                continue

            full_text = build_display_text(title, artist)
            track_key = (title, artist)
            if track_key != last_track_key:
                last_track_key = track_key
                offset = 0
                pause_left = PAUSE_TICKS

            icon = STATUS_ICONS[status]
            css_class = "playing" if status == "Playing" else "paused"
            player_label = player.capitalize() if player else "Reproductor"
            tooltip_raw = (
                f"{player_label}: {full_text}\n"
                "Click izq: Pausar/Reanudar | Der: Siguiente"
            )

            needs_scroll = len(full_text) > MAX_LEN
            if not needs_scroll:
                visible = full_text
            elif status != "Playing":
                visible = full_text[: MAX_LEN - 1].rstrip() + "…"
            else:
                ring = full_text + LOOP_GAP
                doubled = ring + ring
                visible = doubled[offset : offset + MAX_LEN]

            payload = {
                "text": f"{icon} {html.escape(visible, quote=False)}",
                "tooltip": html.escape(tooltip_raw, quote=False),
                "class": css_class,
            }

            if payload != last_payload:
                if not emit(payload):
                    break
                last_payload = payload

            if needs_scroll and status == "Playing":
                if state.event.wait(timeout=SCROLL_INTERVAL):
                    continue
                if pause_left > 0:
                    pause_left -= 1
                else:
                    ring_len = len(full_text) + len(LOOP_GAP)
                    offset = (offset + 1) % ring_len
                    if offset == 0:
                        pause_left = PAUSE_TICKS
            else:
                state.event.wait(timeout=2.0)
    finally:
        state.terminate()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
