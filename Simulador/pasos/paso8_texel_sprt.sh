#!/bin/sh
# Paso 8 (~1 h por tanda): la evaluación afinada (texel_parametros.json) contra la de v6 (parametros_v6.json).
# Ya decidido: +74 Elo (H1); desde v7 los valores afinados son los predeterminados.
. "$(dirname "$0")/_sprt.sh"
sprt sprt_texel.jsonl "tiempo=1,prof=30,parametros=parametros_v6.json,nombre=v6" "tiempo=1,prof=30,parametros=texel_parametros.json,nombre=v6 texel"
