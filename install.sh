#!/usr/bin/env bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$HOME/.dotfiles-backup/$(date +%Y%m%d-%H%M%S)"
INSTALL_PKGS=true

for arg in "$@"; do
    case "$arg" in
        --no-packages) INSTALL_PKGS=false ;;
        -h|--help)
            echo "Uso: $0 [--no-packages]"
            echo "  --no-packages  Omite la instalación de paquetes pacman/AUR y solo aplica configuraciones."
            exit 0
            ;;
        *)
            echo "Opción desconocida: $arg" >&2
            exit 1
            ;;
    esac
done

link_item() {
    local src="$1"
    local dst="$2"

    mkdir -p "$(dirname "$dst")"
    if [ -e "$dst" ] || [ -L "$dst" ]; then
        if [ -L "$dst" ] && [ "$(readlink -f "$dst")" = "$(readlink -f "$src")" ]; then
            return 0
        fi
        mkdir -p "$BACKUP_DIR"
        echo "  Respaldando $dst -> $BACKUP_DIR/"
        mv "$dst" "$BACKUP_DIR/"
    fi
    ln -s "$src" "$dst"
    echo "  Enlazado: $dst -> $src"
}

if [ "$INSTALL_PKGS" = true ]; then
    echo "==> Instalando paquetes oficiales (pacman)..."
    if [ -f "$DOTFILES_DIR/packages/pacman.txt" ]; then
        sudo pacman -S --needed --noconfirm - < "$DOTFILES_DIR/packages/pacman.txt"
    fi

    echo "==> Verificando yay (AUR)..."
    if ! command -v yay >/dev/null 2>&1; then
        sudo pacman -S --needed --noconfirm base-devel git
        tmp_yay="$(mktemp -d)"
        git clone https://aur.archlinux.org/yay.git "$tmp_yay/yay"
        (cd "$tmp_yay/yay" && makepkg -si --noconfirm)
        rm -rf "$tmp_yay"
    fi

    echo "==> Instalando paquetes AUR (yay)..."
    if [ -f "$DOTFILES_DIR/packages/aur.txt" ] && [ -s "$DOTFILES_DIR/packages/aur.txt" ]; then
        yay -S --needed --noconfirm - < "$DOTFILES_DIR/packages/aur.txt"
    fi
fi

echo "==> Enlazando configuraciones en ~/.config ..."
for dir in hypr waybar wofi wlogout ghostty; do
    if [ -d "$DOTFILES_DIR/config/$dir" ]; then
        link_item "$DOTFILES_DIR/config/$dir" "$HOME/.config/$dir"
    fi
done

for file in mimeapps.list spotify-flags.conf xdg-terminals.list; do
    if [ -f "$DOTFILES_DIR/config/$file" ]; then
        link_item "$DOTFILES_DIR/config/$file" "$HOME/.config/$file"
    fi
done

echo "==> Enlazando unidades systemd --user ..."
mkdir -p "$HOME/.config/systemd/user"
for unit in "$DOTFILES_DIR/config/systemd/user/"*; do
    [ -e "$unit" ] || continue
    link_item "$unit" "$HOME/.config/systemd/user/$(basename "$unit")"
done

echo "==> Enlazando scripts en ~/.local/bin ..."
mkdir -p "$HOME/.local/bin"
for script in "$DOTFILES_DIR/local/bin/"*; do
    [ -e "$script" ] || continue
    chmod +x "$script"
    link_item "$script" "$HOME/.local/bin/$(basename "$script")"
done

echo "==> Enlazando archivos de shell en ~ ..."
for rc in .zshrc .bashrc .bash_profile; do
    if [ -f "$DOTFILES_DIR/home/$rc" ]; then
        link_item "$DOTFILES_DIR/home/$rc" "$HOME/$rc"
    fi
done

if [ -d "$DOTFILES_DIR/wallpapers" ]; then
    echo "==> Enlazando wallpapers ..."
    link_item "$DOTFILES_DIR/wallpapers" "$HOME/wallpapers"
fi

echo "==> Habilitando servicios systemd --user ..."
if systemctl --user daemon-reload 2>/dev/null; then
    systemctl --user enable --now battery-notify.timer 2>/dev/null || true
    systemctl --user enable --now control-center-restore.service 2>/dev/null || true
    systemctl --user enable hypridle.service 2>/dev/null || true
else
    echo "  (Aviso: no se detectó sesión systemd --user activa; habilita los servicios al iniciar Hyprland)"
fi

echo ""
echo "Listo. Si se respaldaron archivos anteriores, están en: $BACKUP_DIR"
