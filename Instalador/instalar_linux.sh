#!/bin/sh
# Instalador para Linux: comprueba Python y Tkinter, instala Pillow (opcional) y crea el acceso
# en el menú de aplicaciones. Uso: sh instalar_linux.sh
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
PY=python3
[ -x /usr/bin/python3 ] && PY=/usr/bin/python3
echo "Carpeta del juego: $RAIZ"
if ! command -v "$PY" >/dev/null 2>&1; then
    echo "Falta Python 3. Instálalo con el gestor de paquetes de tu distribución:"
    echo "  Fedora: sudo dnf install python3 python3-tkinter"
    echo "  Debian/Ubuntu: sudo apt install python3 python3-tk"
    echo "  Arch: sudo pacman -S python tk"
    exit 1
fi
if ! "$PY" -c "import tkinter" 2>/dev/null; then
    echo "Python no tiene Tkinter. Instálalo:"
    echo "  Fedora: sudo dnf install python3-tkinter"
    echo "  Debian/Ubuntu: sudo apt install python3-tk"
    echo "  Arch: sudo pacman -S tk"
    exit 1
fi
if ! "$PY" -c "import PIL" 2>/dev/null; then
    echo "Instalando Pillow (mejora el dibujo de las piezas)..."
    "$PY" -m pip install --user pillow || echo "No se pudo instalar Pillow; el juego funciona sin él."
fi
chmod +x "$RAIZ/Juego/jugar.sh"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS"
cat > "$APPS/ajedrez11x11.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Ajedrez
Comment=Ajedrez Extendido, clásico, Capablanca, gótico y más variantes contra la computadora
Exec="$RAIZ/Juego/jugar.sh"
Path=$RAIZ/Juego
Icon=$RAIZ/Piezas/blancas/png/rey.png
Terminal=false
Categories=Game;BoardGame;
StartupWMClass=Ajedrez11x11
DESK
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" 2>/dev/null || true
echo "Listo: busca «Ajedrez» en el menú de aplicaciones o ejecuta $RAIZ/Juego/jugar.sh"
if ! command -v pypy3 >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/pypy3" ]; then
    echo "Sugerencia: instala PyPy (https://pypy.org/download.html o el paquete pypy3 de tu distribución);"
    echo "la computadora piensa varias veces más rápido con él."
fi
