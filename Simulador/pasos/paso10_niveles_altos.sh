#!/bin/sh
# Paso 10: calibra los niveles altos (profundidad 6 con 10 s, profundidad 7 con 20 s y sin límite de
# profundidad con 30 s) contra sus tres vecinos de abajo. Solo juega las partidas que falten hasta --partidas
# por enfrentamiento (por defecto 40), así que tras cambiar un nivel solo se juegan sus enfrentamientos, y al
# final reescribe Juego/niveles_elo.json con la escala completa. Para hacerlo en tandas:
#   pasos/paso10_niveles_altos.sh --partidas 10    (y luego 20, 30 y 40: cada vez juega solo las nuevas)
. "$(dirname "$0")/_sprt.sh"
TANDA_ELO=40
[ "$TANDA" != "500" ] && TANDA_ELO=$TANDA
pypy3 calibrar_elo.py --partidas $TANDA_ELO --procesos $P --salida calibracion_v7.jsonl
echo
echo "Partidas acumuladas en calibracion_v7.jsonl: $(wc -l < calibracion_v7.jsonl)."
