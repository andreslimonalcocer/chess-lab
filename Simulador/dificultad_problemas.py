"""Dificultad de los problemas (Juego/problemas.json): la profundidad mínima con que la computadora encuentra la
solución. La app la convierte en el Elo de cada problema (650 + 200 × profundidad: profundidad 1 = 850,
3 = 1250, 5 = 1650...), para el Elo de problemas, el orden «Para mi nivel» y el problema del día.

  - Mate en N: profundidad 2N - 1 (no hace falta buscar).
  - Táctico: se prueba con profundidad 1, 2, 3... hasta que la jugada elegida es la de la solución; si no la
    encuentra hasta --max-prof, queda en --max-prof + 1 (los más difíciles).

Solo calcula los que aún no tienen dificultad (con --todos, todos otra vez). Guarda cada 25 problemas, así que
se puede interrumpir y continuar. Ejemplos:
  pypy3 dificultad_problemas.py --procesos 8
  pypy3 dificultad_problemas.py --procesos 1 --max 20       # prueba con 20 problemas
"""
import argparse, json, os, random, sys, time
from multiprocessing import Pool

AQUI = os.path.dirname(os.path.abspath(__file__))
JUEGO = os.path.join(os.path.dirname(AQUI), 'Juego')
sys.path.insert(0, AQUI)
sys.path.insert(1, JUEGO)
PROBLEMAS = os.path.join(JUEGO, 'problemas.json')
SEGUNDOS = 120  # tope por profundidad (los problemas que lo agotan quedan como «muy difíciles»)


def medir(tarea):
    problema, maxima = tarea
    from ia import Partida
    t0 = time.time()
    try:
        p = Partida(problema.get('variante') or {'tipo': 'extendido'})
        st = p.inicial(problema.get('inicio'))
        for i in problema['hist']:
            st = p.legal(st)[i][1]
        movs = p.legal(st)
        for d in range(1, maxima + 1):
            b = p.nuevo_buscador(SEGUNDOS, d, 0.0)
            (mv, _), alcanzada = b.choose(st, movs, random.Random(0))
            if alcanzada < d:  # se acabó el tiempo
                break
            if next(i for i, (m, _) in enumerate(movs) if m == mv) == problema['solucion_idx']:
                return problema['id'], d, time.time() - t0
        return problema['id'], maxima + 1, time.time() - t0
    except Exception as e:
        return problema['id'], None, str(e)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--procesos', type=int, default=1)
    ap.add_argument('--max-prof', type=int, default=6, help='profundidad máxima que se prueba (6)')
    ap.add_argument('--max', type=int, default=0, help='calcular como mucho N problemas (0: todos)')
    ap.add_argument('--todos', action='store_true', help='recalcular también los que ya tienen dificultad')
    ap.add_argument('--archivo', default=PROBLEMAS)
    a = ap.parse_args()
    with open(a.archivo, encoding='utf-8') as f:
        problemas = json.load(f)
    mates = 0
    for x in problemas:
        if x.get('tipo', 'mate') == 'mate' and (a.todos or not x.get('dificultad')):
            x['dificultad'] = 2 * x['mate_en'] - 1
            mates += 1
    faltan = [x for x in problemas if x.get('tipo') == 'tactico' and (a.todos or not x.get('dificultad'))]
    if a.max:
        faltan = faltan[:a.max]
    print('%d problemas de mate (dificultad directa) y %d tácticos por medir, con %d procesos.' % (
        mates, len(faltan), a.procesos), flush=True)

    def guardar():
        with open(a.archivo, 'w', encoding='utf-8') as f:
            json.dump(problemas, f, ensure_ascii=False)

    guardar()
    por_id = {x['id']: x for x in problemas}
    tareas = [(x, a.max_prof) for x in faltan]
    it = Pool(a.procesos).imap_unordered(medir, tareas) if a.procesos > 1 else map(medir, tareas)
    t0, cuenta = time.time(), {}
    for k, (ident, d, extra) in enumerate(it, 1):
        if d is None:
            print('[%d/%d] error: %s' % (k, len(tareas), extra), flush=True)
            continue
        por_id[ident]['dificultad'] = d
        cuenta[d] = cuenta.get(d, 0) + 1
        print('[%d/%d] profundidad %d (%.1f s)' % (k, len(tareas), d, extra), flush=True)
        if k % 25 == 0:
            guardar()
    guardar()
    print('\nListo en %.0f s. Tácticos por profundidad mínima: %s' % (
        time.time() - t0, ', '.join('%d: %d' % x for x in sorted(cuenta.items()))))


if __name__ == '__main__':
    main()
