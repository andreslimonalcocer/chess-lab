#!/bin/sh
# Validación de las mejoras de la búsqueda (busqueda.OPCIONES) con SPRT, todas con 1 s por jugada (así cuenta
# también lo que cuesta cada una). Primero todas juntas; después cada una por separado. Cada prueba se
# detiene sola en cuanto decide: «H1» = mejora al menos ELO1 Elo; «H0» = no mejora. Si una prueba no
# decide en el máximo de partidas, vuelve a correr la misma línea: continúa donde se quedó.
# Usa casi todos los núcleos: córrelo sin otras simulaciones.
cd "$(dirname "$0")"
P=${PROCESOS:-22}
MAX=${PARTIDAS:-1200}
SPRT=${SPRT:-"0 15"}
BASE="tiempo=1,prof=30,nombre=base"
TODAS="tt_persistente:1/aspiracion:1/lmr_log:1/futilidad:1/futilidad_inversa:1/razoring:1/poda_tardia:1/see:1/contrajugada:1"

echo "== todas las mejoras juntas"
pypy3 comparar.py "$BASE" "tiempo=1,prof=30,opciones=$TODAS,nombre=todas" --sprt $SPRT --partidas $MAX \
    --procesos $P --salida sprt_todas.jsonl

for op in tt_persistente aspiracion see poda_tardia lmr_log futilidad futilidad_inversa razoring contrajugada; do
    echo "== $op"
    pypy3 comparar.py "$BASE" "tiempo=1,prof=30,opciones=$op:1,nombre=$op" --sprt $SPRT --partidas $MAX \
        --procesos $P --salida "sprt_$op.jsonl"
done

if ls tablas/*.dtm >/dev/null 2>&1; then
    echo "== finales exactos (tablas/)"
    pypy3 comparar.py "tiempo=1,prof=30,opciones=finales:0,nombre=sin tablas" \
        "tiempo=1,prof=30,opciones=finales:1,nombre=con tablas" --sprt $SPRT --partidas $MAX --procesos $P \
        --salida sprt_finales.jsonl
fi
