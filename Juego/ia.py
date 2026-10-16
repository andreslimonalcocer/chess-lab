"""Proceso de la computadora para el juego de escritorio.

Lee peticiones JSON por la entrada estándar, una por línea:
    {"id": 1, "variante": {...}, "inicio": null, "hist": [12, 40, ...], "prof": 3, "tiempo": 5,
     "temperatura": 0}   (temperatura: imprecisión de los niveles bajos, en peones)
'variante' es {"tipo": "extendido"} (Ajedrez Extendido) o {"tipo": "generica", "config": {...}}.
'inicio' es null para la posición inicial o, en el entrenamiento, una posición
{"piezas": [[casilla, tipo, color, promocionada], ...], "turno": 0}.
'hist' son los índices, dentro de legal(), de las jugadas hechas desde 'inicio'.
Responde con {"id": 1, "idx": 17, "prof": 3, "eval": 0.4}: el índice de la jugada elegida, la
profundidad alcanzada y su evaluación desde el bando que mueve.
Con "pensar": true (solo el Ajedrez Extendido) no responde: piensa durante el turno del rival hasta que llega la
siguiente petición, para contestar más rápido (ver pensar()).
Se ejecuta con PyPy cuando está disponible, porque es varias veces más rápido.
"""
import json, os, random, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Simulador'))
from motor import N, initial, empty_state, put, legal, start_row
from busqueda import Searcher, zhash


def construir_posicion(piezas, turno):
    """Posición de entrenamiento. Rey y Torres en su casilla original conservan el enroque;
    peones y Guardianes en su segunda fila conservan el avance doble."""
    st = empty_state()
    for pid, (sq, t, c, pr) in enumerate(piezas, 1):
        r0 = 0 if c == 0 else N - 1
        original = (t == 'K' and sq == r0 * N + 5) or (t == 'R' and sq in (r0 * N, r0 * N + N - 1))
        en_segunda = sq // N == start_row(c) and t in ('P', 'G') and not pr
        put(st, sq, t, c, pr=pr, pid=pid, moved=not original, dbl=en_segunda, init=en_segunda and t == 'G')
        if pr and t not in ('P', 'G'):
            st.tprom[c].add(t)
    st.turn = turno
    return st


def posicion(inicio):
    return initial() if inicio is None else construir_posicion(inicio['piezas'], inicio['turno'])


class Partida:
    """Motor y búsqueda de una variante: el Ajedrez Extendido (motor.py) o una genérica (generico.py)."""

    def __init__(self, spec):
        self.extendido = spec is None or spec.get('tipo') == 'extendido'
        if self.extendido:
            self.inicial, self.legal, self.hash = posicion, legal, zhash
            from busqueda import evaluate
            self.evaluar = evaluate
            self.nuevo_buscador = lambda tiempo, prof, temp: Searcher(tiempo or None, prof, temperatura=temp)
            self.reloj = lambda st: st.clock
        else:
            import generico
            m = generico.Motor(spec['config'])
            self.inicial = lambda ini: m.inicial() if ini is None else m.construir(
                [p[:3] for p in ini['piezas']], ini['turno'])
            self.legal, self.hash = m.legal, m.zhash
            self.evaluar = m.evaluar
            self.nuevo_buscador = lambda tiempo, prof, temp: generico.Buscador(m, tiempo or None, prof,
                                                                               temperatura=temp)
            self.reloj = lambda st: st.reloj


def leer_entrada(cola):
    """Lee las peticiones en un hilo aparte: así la búsqueda puede ver que llegó una nueva y detenerse."""
    for linea in sys.stdin:
        if linea.strip():
            cola.put(json.loads(linea))
    cola.put(None)


def pensar(p, b, st, vistas, rng, hay_peticion):
    """Piensa durante el turno del rival: analiza, de la más probable a la menos, la posición tras cada
    respuesta suya, como si ya la hubiera jugado. Lo analizado queda en la tabla de transposición (que se
    conserva entre jugadas), así que cuando el rival juega la computadora responde mucho antes. Se
    detiene en cuanto llega otra petición."""
    import busqueda
    busqueda.OPCIONES['tt_persistente'] = True
    movs = p.legal(st)
    if not movs:
        return
    # primero la respuesta que la computadora esperaba en su propio análisis (la guarda su tabla de
    # transposición), luego la mejor según una búsqueda corta desde el lado del rival, y después el resto
    esperada = (b.tt.get(p.hash(st)) or (None,) * 4)[3]
    orden = Searcher(None, 2)
    orden.interrumpir = hay_peticion
    (corta, _), _ = orden.choose(st, movs, rng, vistas=vistas)
    if orden.stop:
        return
    def prioridad(x):
        if esperada is not None and x[0] == esperada:
            return -2e9
        if x[0] == corta:
            return -1e9
        return -orden.historia.get((x[0][1], x[0][2] if len(x[0]) > 2 else -1), 0)
    probables = sorted(movs, key=prioridad)
    b.interrumpir = hay_peticion
    try:
        for mv, n in probables:
            respuestas = p.legal(n)
            if not respuestas:
                continue
            b.choose(n, respuestas, rng, vistas=vistas + [p.hash(n)] if p.reloj(n) else [p.hash(n)])
            if b.stop:
                break
    finally:
        b.interrumpir = None


LIBRO = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libro_aperturas.json')
_libro = None


def jugada_de_libro(hist, rng):
    """Del libro de aperturas (Simulador/libro_aperturas.py), si la posición está en él: (idx, puntuación),
    eligiendo al azar entre sus jugadas, las mejores más a menudo. None si no está."""
    global _libro
    if _libro is None:
        try:
            with open(LIBRO, encoding='utf-8') as f:
                _libro = json.load(f).get('posiciones', {})
        except (OSError, ValueError):
            _libro = {}
    jugadas = _libro.get(','.join(map(str, hist)))
    if not jugadas:
        return None
    mejor = jugadas[0][2]
    import math
    pesos = [math.exp((sc - mejor) / 0.1) for _, _, sc in jugadas]
    r = rng.random() * sum(pesos)
    for (idx, _, sc), w in zip(jugadas, pesos):
        r -= w
        if r <= 0:
            return idx, sc
    return jugadas[0][0], mejor


def linea_principal(p, b, st, maximo=8):
    """La continuación que espera la búsqueda desde st (las mejores jugadas guardadas en su tabla de
    transposición), como índices de jugadas legales."""
    out, vistos = [], set()
    while len(out) < maximo:
        h = p.hash(st)
        ent = b.tt.get(h)
        if h in vistos or not ent or ent[3] is None:
            break
        vistos.add(h)
        movs = p.legal(st)
        i = next((k for k, (m, _) in enumerate(movs) if m == ent[3]), None)
        if i is None:
            break
        out.append(i)
        st = movs[i][1]
    return out


def main():
    import queue, threading
    cola = queue.Queue()
    threading.Thread(target=leer_entrada, args=(cola,), daemon=True).start()
    hay_peticion = lambda: not cola.empty()
    partidas = {}
    clave_actual, inicio, hist, st, vistas = None, None, [], None, []
    buscadores = {}
    rng = random.Random()
    while True:
        req = cola.get()
        if req is None:
            break
        spec = req.get('variante')
        clave = json.dumps(spec, sort_keys=True)
        if clave not in partidas:
            partidas = {clave: Partida(spec)}
            buscadores = {}
        p = partidas[clave]
        nuevo = req['hist']
        if clave != clave_actual or req.get('inicio') != inicio or nuevo[:len(hist)] != hist:
            clave_actual, inicio = clave, req.get('inicio')
            hist, st = [], p.inicial(inicio)
            vistas = [p.hash(st)]  # posiciones desde la última jugada irreversible, para evitar repeticiones
        for i in nuevo[len(hist):]:
            st = p.legal(st)[i][1]
            if p.reloj(st) == 0:
                vistas = []
            vistas.append(p.hash(st))
        hist = list(nuevo)
        movs = p.legal(st)
        bk = (clave, req['prof'], req['tiempo'], req.get('temperatura', 0.0))
        if bk not in buscadores:  # se guardan unos pocos para no perder lo analizado (barra, análisis...)
            if len(buscadores) >= 4:
                buscadores.clear()
            buscadores[bk] = p.nuevo_buscador(req['tiempo'], req['prof'], req.get('temperatura', 0.0))
        b = buscadores[bk]
        if req.get('libro') and p.extendido and inicio is None and not req.get('pensar'):
            elegida = jugada_de_libro(hist, rng)
            if elegida is not None and elegida[0] < len(movs):
                print(json.dumps({'id': req['id'], 'idx': elegida[0], 'prof': 0, 'eval': elegida[1], 'libro': True,
                                  'linea': []}), flush=True)
                continue
        if req.get('pensar'):
            if p.extendido:
                pensar(p, b, st, vistas, rng, hay_peticion)
            continue
        (mv, _), prof = b.choose(st, movs, rng, vistas=vistas)
        idx = next(i for i, (m, _) in enumerate(movs) if m == mv)
        ev = getattr(b, 'puntaje', None)
        r = {'id': req['id'], 'idx': idx, 'prof': prof, 'eval': None if ev is None else round(ev, 2)}
        if req.get('linea'):  # lo que espera después de su jugada (pistas y «¿Por qué jugó eso?»)
            r['linea'] = linea_principal(p, b, movs[idx][1])
        print(json.dumps(r), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BrokenPipeError:  # la app se cerró mientras respondía
        try:
            sys.stdout = open(os.devnull, 'w')
        except OSError:
            pass
