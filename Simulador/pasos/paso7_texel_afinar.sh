#!/bin/sh
# Paso 7 (~15-30 min, un solo núcleo): afina la evaluación con las bitácoras del paso 6.
cd "$(dirname "$0")/.."
pypy3 afinar_texel.py texel_p3_bitacora.jsonl | tee texel_informe.txt
