#!/bin/sh
# Instalador para macOS: comprueba Python 3 con Tkinter, instala Pillow (opcional) y crea
# «Ajedrez.app» en ~/Applications. Uso: sh instalar_mac.sh
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    echo "Falta Python 3: descárgalo de https://www.python.org/downloads/macos/ (incluye Tkinter)"
    echo "o con Homebrew: brew install python python-tk"
    exit 1
fi
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "Python no tiene Tkinter. Con Homebrew: brew install python-tk"
    echo "o instala Python desde https://www.python.org/downloads/macos/"
    exit 1
fi
python3 -c "import PIL" 2>/dev/null || python3 -m pip install --user pillow || \
    echo "No se pudo instalar Pillow; el juego funciona sin él."
chmod +x "$RAIZ/Juego/jugar.command"
APP="$HOME/Applications/Ajedrez.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/MacOS/Ajedrez" <<SCRIPT
#!/bin/sh
cd "$RAIZ/Juego"
exec "$(command -v python3)" ajedrez.py
SCRIPT
chmod +x "$APP/Contents/MacOS/Ajedrez"
if command -v sips >/dev/null 2>&1; then
    sips -s format icns "$RAIZ/Piezas/blancas/png/rey.png" --out "$APP/Contents/Resources/icono.icns" >/dev/null 2>&1 || true
fi
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Ajedrez</string>
  <key>CFBundleExecutable</key><string>Ajedrez</string>
  <key>CFBundleIdentifier</key><string>local.ajedrez11x11</string>
  <key>CFBundleIconFile</key><string>icono</string>
  <key>CFBundlePackageType</key><string>APPL</string>
</dict></plist>
PLIST
echo "Listo: abre «Ajedrez» desde ~/Applications (o Juego/jugar.command)."
command -v pypy3 >/dev/null 2>&1 || echo "Sugerencia: brew install pypy3 hace que la computadora piense varias veces más rápido."
