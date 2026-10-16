#!/bin/sh
# Paso 1 (~1 h por tanda): todas las mejoras juntas, con la poda de jugadas tardías ya corregida.
# El resultado anterior (con el error) se guarda aparte la primera vez.
. "$(dirname "$0")/_sprt.sh"
if [ -f sprt_todas.jsonl ] && [ ! -f sprt_todas_con_error.jsonl ]; then
    mv sprt_todas.jsonl sprt_todas_con_error.jsonl
fi
sprt sprt_todas.jsonl "tiempo=1,prof=30,nombre=base" \
    "tiempo=1,prof=30,opciones=tt_persistente:1/aspiracion:1/lmr_log:1/futilidad:1/futilidad_inversa:1/razoring:1/poda_tardia:1/see:1/contrajugada:1,nombre=todas"
