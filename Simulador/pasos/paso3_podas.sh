#!/bin/sh
# Paso 3 (~1 h por tanda): futilidad + futilidad inversa + razoring + contrajugada, en grupo, encima de B3.
. "$(dirname "$0")/_sprt.sh"
sprt sprt2_podas.jsonl "tiempo=1,prof=30,opciones=$B3,nombre=B3" \
    "tiempo=1,prof=30,opciones=$B3/futilidad:1/futilidad_inversa:1/razoring:1/contrajugada:1,nombre=B3+podas"
