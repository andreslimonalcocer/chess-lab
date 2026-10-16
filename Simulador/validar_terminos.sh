#!/bin/sh
# Validación de los términos de evaluación (busqueda.PESOS), cada uno por separado y luego juntos.
# Usa casi todos los núcleos: córrelo sin otras simulaciones. Cada paso guarda sus partidas en su propio
# archivo y al final imprime la diferencia en Elo contra el motor sin términos. Si un archivo ya tiene
# partidas, comparar.py las suma (puedes repetir un paso para afinar el resultado).
cd "$(dirname "$0")"
P=${PROCESOS:-22}
N=${PARTIDAS:-200}
# todos los términos apagados de forma explícita (desde v5, busqueda.PESOS enciende algunos por defecto);
# en comparar.py, si una clave se repite en «pesos», vale la última
CERO="pasados:0/escudo:0/movilidad:0/rey:0/desarrollo:0/atacadas:0/derechos:0"
BASE="prof=3,pesos=$CERO,nombre=sin términos"

for t in rey desarrollo atacadas derechos escudo movilidad; do
    echo "== $t (profundidad 3)"
    pypy3 comparar.py "$BASE" "prof=3,pesos=$CERO/$t:1,nombre=con $t" --partidas $N --procesos $P \
        --salida "validar_$t.jsonl"
done

echo "== rey + desarrollo + atacadas (profundidad 3)"
pypy3 comparar.py "$BASE" "prof=3,pesos=$CERO/rey:1/desarrollo:1/atacadas:1,nombre=con los tres" \
    --partidas $N --procesos $P --salida validar_tres.jsonl

echo "== rey + desarrollo + atacadas con el mismo tiempo (1 s por jugada): incluye lo que cuestan"
pypy3 comparar.py "tiempo=1,prof=30,pesos=$CERO,nombre=sin términos 1s" \
    "tiempo=1,prof=30,pesos=$CERO/rey:1/desarrollo:1/atacadas:1,nombre=con los tres 1s" \
    --partidas $N --procesos $P --salida validar_tres_tiempo.jsonl
