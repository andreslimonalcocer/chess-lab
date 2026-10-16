#!/bin/sh
# Abre el juego en macOS (doble clic en el Finder).
cd "$(dirname "$0")"
exec python3 ajedrez.py "$@"
