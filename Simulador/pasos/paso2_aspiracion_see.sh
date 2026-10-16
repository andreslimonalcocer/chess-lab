#!/bin/sh
# Paso 2 (~1 h por tanda): aspiración + SEE encima de lo ya aceptado (tt_persistente + poda_tardia).
. "$(dirname "$0")/_sprt.sh"
sprt sprt2_asp_see.jsonl "tiempo=1,prof=30,opciones=$B2,nombre=B2" "tiempo=1,prof=30,opciones=$B3,nombre=B2+asp+see"
