"""Libro de aperturas del 11×11 calculado por la computadora (Juego/libro_aperturas.json).

Desde la posición inicial, en cada posición del libro se buscan las jugadas a profundidad --prof y se guardan
las que quedan a menos de --margen peones de la mejor; luego se repite tras cada una de ellas, hasta --plies
medias jugadas. Así el libro es un árbol de buenas jugadas, no de las más frecuentes (las partidas simuladas
empiezan con jugadas al azar y no sirven para esto).

--ancho dice cuántas jugadas se siguen en cada media jugada: «3,3,2,2,1» = 3 en las dos primeras, 2 en las dos
siguientes y después solo la mejor (el último valor se repite). Así las líneas son largas sin que el árbol crezca
sin control: con el valor por defecto son 36 líneas de 16 medias jugadas (unas 460 posiciones).

Para qué sirve:
  - La app (si está activado en Ajustes) hace que la computadora juegue del libro mientras pueda, eligiendo
    al azar entre sus jugadas (las mejores, más a menudo). Sus partidas empiezan distinto cada vez sin jugar
    peor. Las simulaciones y la calibración de Elo no lo usan.
  - El explorador de aperturas muestra la evaluación del libro junto a las estadísticas de tus partidas.

Continúa donde se quedó: las posiciones ya calculadas se saltan (con --prof o --margen distintos, borra el
archivo o usa --rehacer). Guarda tras cada posición. Ejemplos:
  pypy3 libro_aperturas.py --procesos 8                     # 16 medias jugadas, ancho 3,3,2,2,1
  pypy3 libro_aperturas.py --plies 24 --procesos 8          # alarga las mismas líneas hasta 24 medias jugadas
  pypy3 libro_aperturas.py --ancho 3,3,3,2,2,1 --procesos 8 # más variedad al principio (unas 3 veces más)
  pypy3 libro_aperturas.py --plies 2 --prof 3               # prueba rápida
"""
import argparse, json, os, random, sys, time
from multiprocessing import Pool

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
SALIDA = os.path.join(os.path.dirname(AQUI), 'Juego', 'libro_aperturas.json')
_CFG = {}


def preparar(cfg):
    _CFG.update(cfg)


def analizar(tarea):
    """[(idx, notación, puntuación)] de las mejores jugadas tras hist (desde el bando que mueve), como mucho
    maximo (al menos una)."""
    hist, maximo = tarea
    import busqueda as B
    import motor as M
    from notacion import notacion
    st = M.initial()
    for i in hist:
        st = M.legal(st)[i][1]
    movs = M.legal(st)
    if not movs:
        return hist, []
    b = B.Searcher(None, _CFG['prof'])
    (mejor, n), d = b.choose(st, movs, random.Random(0), noise=0.0)
    # puntuaciones exactas de las jugadas a menos del margen de la mejor (como con la temperatura)
    b.temperatura = _CFG['margen'] / B.MARGEN_TEMPERATURA
    scores = [(0, mejor, n)] + [(0, mv, x) for mv, x in movs if mv != mejor]
    exactas = B.puntuaciones_exactas(b, scores, d) or [(b.puntaje or 0.0, mejor, n)]
    piso = exactas[0][0] - _CFG['margen']
    out = []
    for sc, mv, x in exactas[:max(1, maximo)]:
        if sc < piso:
            break
        idx = next(i for i, (m, _) in enumerate(movs) if m == mv)
        out.append([idx, notacion(st, mv, x, movs), round(sc, 2)])
    return hist, out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--plies', type=int, default=16, help='medias jugadas del libro (16)')
    ap.add_argument('--ancho', default='3,3,2,2,1',
                    help='jugadas que se siguen en cada media jugada; el último valor se repite (3,3,2,2,1)')
    ap.add_argument('--prof', type=int, default=5, help='profundidad de búsqueda en cada posición (5)')
    ap.add_argument('--margen', type=float, default=0.3, help='peones por debajo de la mejor que se aceptan (0.3)')
    ap.add_argument('--procesos', type=int, default=1)
    ap.add_argument('--salida', default=SALIDA)
    ap.add_argument('--rehacer', action='store_true', help='empezar de cero')
    a = ap.parse_args()
    from busqueda import VERSION_IA
    libro = {}
    if os.path.exists(a.salida) and not a.rehacer:
        with open(a.salida, encoding='utf-8') as f:
            libro = json.load(f)
        if (libro.get('prof'), libro.get('margen')) != (a.prof, a.margen):
            raise SystemExit('El libro existente usa profundidad %s y margen %s: usa los mismos o --rehacer.' % (
                libro.get('prof'), libro.get('margen')))
    anchos = [max(1, int(x)) for x in a.ancho.split(',')]
    ancho = lambda ply: anchos[min(ply, len(anchos) - 1)]
    libro.pop('max_jugadas', None)
    libro.update(version=VERSION_IA, prof=a.prof, margen=a.margen, ancho=a.ancho,
                 plies=max(a.plies, libro.get('plies', 0)))
    pos = libro.setdefault('posiciones', {})

    def guardar():
        tmp = a.salida + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(libro, f, ensure_ascii=False)
        os.replace(tmp, a.salida)

    cfg = {'prof': a.prof, 'margen': a.margen}
    pool = Pool(a.procesos, initializer=preparar, initargs=(cfg,)) if a.procesos > 1 else None
    preparar(cfg)
    t0 = time.time()
    nivel = [[]]
    for ply in range(a.plies):
        faltan = [h for h in nivel if ','.join(map(str, h)) not in pos]
        print('Media jugada %d: %d posiciones (%d por calcular)...' % (ply + 1, len(nivel), len(faltan)), flush=True)
        tareas = [(h, ancho(ply)) for h in faltan]
        it = pool.imap_unordered(analizar, tareas) if pool else map(analizar, tareas)
        for k, (h, jugadas) in enumerate(it, 1):
            pos[','.join(map(str, h))] = jugadas
            guardar()
            print('  [%d/%d] %s → %s' % (k, len(faltan), ' '.join(map(str, h)) or 'inicio',
                                         ', '.join('%s (%+.2f)' % (j[1], j[2]) for j in jugadas)), flush=True)
        nivel = [h + [j[0]] for h in nivel for j in pos.get(','.join(map(str, h)), [])[:ancho(ply)]]
    if pool:
        pool.close()
    print('\nListo en %.0f s: %d posiciones en %s.' % (time.time() - t0, len(pos), a.salida))


if __name__ == '__main__':
    main()
