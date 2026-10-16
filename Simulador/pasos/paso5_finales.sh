#!/bin/sh
# Paso 5 (~1 h por tanda): las tablas exactas de finales (tablas/) contra no usarlas, con la búsqueda v6.
. "$(dirname "$0")/_sprt.sh"
sprt sprt2_finales.jsonl "tiempo=1,prof=30,opciones=finales:0,nombre=v6 sin tablas" \
    "tiempo=1,prof=30,opciones=finales:1,nombre=v6 con tablas"
