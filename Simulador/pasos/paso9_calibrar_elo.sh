#!/bin/sh
# Paso 9: recalibrar la escala de Elo de los niveles con la computadora v7: 40 partidas por enfrentamiento
# (21 enfrentamientos = 840 partidas, ~4-5 h con 22 procesos) y al final reescribe Juego/niveles_elo.json.
# --partidas N es el total por enfrentamiento: solo se juegan las que falten (se puede retomar).
. "$(dirname "$0")/_sprt.sh"
TANDA_ELO=40
[ "$TANDA" != "500" ] && TANDA_ELO=$TANDA
pypy3 calibrar_elo.py --partidas $TANDA_ELO --procesos $P --salida calibracion_v7.jsonl
echo
echo "Partidas acumuladas: $(wc -l < calibracion_v7.jsonl) (la meta son 840)."
