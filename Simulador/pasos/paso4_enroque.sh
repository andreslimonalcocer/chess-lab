#!/bin/sh
# Paso 4 (~1 h por tanda): el término «enroque» encima de B3.
. "$(dirname "$0")/_sprt.sh"
sprt sprt2_enroque.jsonl "tiempo=1,prof=30,opciones=$B3,nombre=B3" \
    "tiempo=1,prof=30,opciones=$B3,pesos=enroque:1,nombre=B3+enroque"
