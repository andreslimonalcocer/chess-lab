#!/bin/sh
# Validación del motor mejorado, en orden. Usa casi todos los núcleos: córrelo sin otras simulaciones.
# Cada paso guarda sus partidas en un archivo propio; al final de cada uno se imprime la diferencia en Elo.
cd "$(dirname "$0")"
P=${PROCESOS:-22}

echo "== 1. Búsqueda mejorada contra la clásica, misma profundidad (3)"
pypy3 comparar.py "prof=3,mejoras=0,nombre=clásica" "prof=3,mejoras=1,nombre=mejorada" \
    --partidas 100 --procesos $P --salida validar_busqueda.jsonl

echo "== 2. Motor actual contra el original, mismo tiempo (1 s por jugada): velocidad + búsqueda"
pypy3 comparar.py "ruta=motores/original,tiempo=1,prof=30,nombre=original" "tiempo=1,prof=30,nombre=actual" \
    --partidas 100 --procesos $P --salida validar_tiempo.jsonl

echo "== 3. Términos de evaluación nuevos (pasados, escudo, movilidad), misma profundidad (3)"
pypy3 comparar.py "prof=3,nombre=sin términos" "prof=3,pesos=pasados:1/escudo:1/movilidad:1,nombre=con términos" \
    --partidas 100 --procesos $P --salida validar_evaluacion.jsonl
