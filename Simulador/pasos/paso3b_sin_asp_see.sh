#!/bin/sh
# Paso 3b (~1 h por tanda): ¿sobran la aspiración y SEE? El paquete con las podas, sin ellas, contra con ellas.
. "$(dirname "$0")/_sprt.sh"
PODAS="futilidad:1/futilidad_inversa:1/razoring:1/contrajugada:1"
sprt sprt3_sin_asp_see.jsonl "tiempo=1,prof=30,opciones=$B3/$PODAS,nombre=con asp+see" \
    "tiempo=1,prof=30,opciones=$B2/$PODAS,nombre=sin asp+see"
