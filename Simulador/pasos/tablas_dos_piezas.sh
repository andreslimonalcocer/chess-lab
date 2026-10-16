#!/bin/sh
# Tablas de finales de Rey y dos piezas contra Rey (11×11), todas a la vez, un núcleo cada una, y GUARDADAS en
# tablas/ para que la computadora las use en sus partidas y se puedan practicar en «Finales».
# Con las siete: ~45 min, ~9 GB de RAM y ~2.4 GB de disco (212 MB las de piezas iguales, 429 MB las demás).
# Córrelo cuando no haya otra prueba usando los núcleos. Una tabla ya guardada en tablas/ se salta.
#
# Uso:
#   pasos/tablas_dos_piezas.sh                              # todas
#   pasos/tablas_dos_piezas.sh --excluir R+R                # todas menos R+R
#   pasos/tablas_dos_piezas.sh --excluir R+R --excluir B+N  # se puede repetir
# Combinaciones: N+N  B+B  R+R  N'+N  B'+B  R'+R  B+N (con apóstrofo, entre comillas: --excluir "N'+N").
cd "$(dirname "$0")/.."
TODAS="N+N B+B R+R N'+N B'+B R'+R B+N"
EXCLUIR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --excluir) EXCLUIR="$EXCLUIR $2"; shift 2 ;;
        *) echo "Opción desconocida: $1 (usa --excluir COMBINACIÓN)"; exit 1 ;;
    esac
done
for x in $EXCLUIR; do
    case " $TODAS " in
        *" $x "*) ;;
        *) echo "«$x» no es una de las combinaciones: $TODAS"; exit 1 ;;
    esac
done
lanzadas=""
for p in $TODAS; do
    case " $EXCLUIR " in
        *" $p "*) echo "$p: excluida."; continue ;;
    esac
    nombre=$(echo "$p" | tr "'" p | tr -d +)
    if [ -f "tablas/K${nombre}K.dtm" ]; then
        echo "$p: ya está guardada (tablas/K${nombre}K.dtm)."
        continue
    fi
    pypy3 finales_dos.py "$p" --guardar > "finales_dos_$nombre.log" 2>&1 &
    lanzadas="$lanzadas $nombre"
done
[ -z "$lanzadas" ] && { echo "No queda ninguna combinación por construir."; exit 0; }
echo "Construyendo en paralelo:$lanzadas (avance en finales_dos_*.log)..."
wait
for n in $lanzadas; do echo "== $n"; grep -A8 "contra Rey:$" "finales_dos_$n.log"; done
