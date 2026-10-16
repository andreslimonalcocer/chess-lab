#!/bin/sh
# Abre el juego. Usa el Python del sistema (su Tk dibuja mejor las letras que el de conda).
cd "$(dirname "$0")"
if [ -x /usr/bin/python3 ]; then exec /usr/bin/python3 ajedrez.py "$@"; fi
exec python3 ajedrez.py "$@"
