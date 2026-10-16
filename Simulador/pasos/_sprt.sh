# Funciones comunes de los pasos (no se ejecuta solo).
cd "$(dirname "$0")/.."
P=${PROCESOS:-22}
TANDA=${TANDA:-500}   # partidas como máximo por ejecución (~1 h con 22 procesos a 1 s por jugada)
# opciones de cualquier paso: --partidas N (tamaño de la tanda) y --procesos N
while [ $# -gt 0 ]; do
    case "$1" in
        --partidas) TANDA="$2"; shift 2 ;;
        --procesos) P="$2"; shift 2 ;;
        *) echo "Opción desconocida: $1 (usa --partidas N o --procesos N)"; exit 1 ;;
    esac
done
B2="tt_persistente:1/poda_tardia:1"
B3="$B2/aspiracion:1/see:1"
# Desde v6 la combinación ganadora (B3 + futilidad, futilidad inversa, razoring y contrajugada) es la
# predeterminada de busqueda.OPCIONES: los pasos 5 y 8 ya no necesitan indicarla.

# sprt ARCHIVO BASE NUEVA: juega una tanda; si el SPRT no decide, vuelve a correr el mismo paso y continúa
sprt() {
    pypy3 comparar.py "$2" "$3" --sprt 0 10 --partidas $TANDA --procesos $P --salida "$1"
    echo
    echo "Si dice «sin decidir», vuelve a correr este mismo paso: continúa con las partidas que ya hay."
}
