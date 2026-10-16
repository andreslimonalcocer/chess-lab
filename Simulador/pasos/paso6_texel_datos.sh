#!/bin/sh
# Paso 6: partidas a profundidad 3 para el afinado Texel (~45 min por cada 500 con 22 procesos).
# Por defecto juega 500; con --partidas 1000 las juega todas de una vez (~1.5 h). Si lo corres otra vez,
# continúa con semillas nuevas y suma las partidas al mismo archivo.
#   pasos/paso6_texel_datos.sh --partidas 1000
. "$(dirname "$0")/_sprt.sh"
pypy3 simular.py --profundidad 3 --partidas $TANDA --procesos $P \
    --salida texel_p3.jsonl --bitacora texel_p3_bitacora.jsonl
echo
echo "Partidas acumuladas: $(wc -l < texel_p3.jsonl) (la meta son 1000)."
