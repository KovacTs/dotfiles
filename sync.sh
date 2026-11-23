#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Actualizando listas de paquetes..."
mkdir -p "$DOTFILES_DIR/packages"
pacman -Qqen | sort > "$DOTFILES_DIR/packages/pacman.txt"
pacman -Qqem | grep -v -- '-debug$' | sort > "$DOTFILES_DIR/packages/aur.txt" || true

copy_dir() {
    local src="$1"
    local dst="$2"
    [ -d "$src" ] || return 0
    if [ -L "$src" ] && [ "$(readlink -f "$src")" = "$(readlink -f "$dst")" ]; then
        return 0
    fi
    rm -rf "$dst"
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    find "$dst" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
}

copy_file() {
    local src="$1"
    local dst="$2"
    [ -f "$src" ] || return 0
    if [ -L "$src" ] && [ "$(readlink -f "$src")" = "$(readlink -f "$dst")" ]; then
        return 0
    fi
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
}

echo "==> Sincronizando configuraciones..."
for dir in hypr waybar wofi wlogout ghostty; do
    copy_dir "$HOME/.config/$dir" "$DOTFILES_DIR/config/$dir"
done

for file in mimeapps.list spotify-flags.conf xdg-terminals.list; do
    copy_file "$HOME/.config/$file" "$DOTFILES_DIR/config/$file"
done

for unit in battery-notify.service battery-notify.timer control-center-restore.service; do
    copy_file "$HOME/.config/systemd/user/$unit" "$DOTFILES_DIR/config/systemd/user/$unit"
done

for script in battery-notify.sh battery-popup.py control-center-restore.py; do
    copy_file "$HOME/.local/bin/$script" "$DOTFILES_DIR/local/bin/$script"
done

for rc in .zshrc .bashrc .bash_profile; do
    copy_file "$HOME/$rc" "$DOTFILES_DIR/home/$rc"
done

copy_dir "$HOME/wallpapers" "$DOTFILES_DIR/wallpapers"

echo "==> Resumen:"
echo "  Paquetes pacman: $(wc -l < "$DOTFILES_DIR/packages/pacman.txt")"
echo "  Paquetes AUR:    $(wc -l < "$DOTFILES_DIR/packages/aur.txt")"
echo "Listo. Revisa cambios con: cd $DOTFILES_DIR && git status"
