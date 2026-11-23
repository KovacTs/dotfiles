# Dotfiles (Arch Linux + Hyprland)

Configuración personal de entorno de escritorio con **Hyprland (`uwsm`)**, **Waybar** (con Centro de control GTK4, calendario y notificaciones), **Wofi**, **Wlogout**, **Ghostty**, **Zsh** y lista completa de aplicaciones instaladas (`pacman` + `AUR`).

## Estructura

- `packages/pacman.txt` — Paquetes oficiales instalados explícitamente.
- `packages/aur.txt` — Paquetes de AUR instalados con `yay`.
- `config/` — Configuraciones de `~/.config/` (`hypr`, `waybar`, `wofi`, `wlogout`, `ghostty`, `systemd/user`, `mimeapps.list`, `spotify-flags.conf`, `xdg-terminals.list`).
- `local/bin/` — Scripts personales (`battery-notify.sh`, `control-center-restore.py`).
- `home/` — Archivos de shell (`.zshrc`, `.bashrc`, `.bash_profile`).
- `wallpapers/` — Fondos de pantalla.

## Instalación en una PC nueva

```bash
git clone <URL_DE_TU_REPO> ~/dotfiles
cd ~/dotfiles
./install.sh
```

Para aplicar solo las configuraciones sin instalar paquetes:

```bash
./install.sh --no-packages
```

## Actualizar el repositorio con nuevos cambios o apps

Cada vez que instales nuevas aplicaciones o modifiques configuraciones:

```bash
cd ~/dotfiles
./sync.sh
git status
git add .
git commit -m "Actualizar dotfiles"
git push
```
