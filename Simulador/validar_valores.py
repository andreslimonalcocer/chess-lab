"""Validación de los valores de las piezas del Ajedrez 11x11.

Modos:
  movilidad   Casillas de cada pieza (base y promocionada), separando las que solo puede
              mover, las que solo puede capturar y las que sirven para ambas cosas.
  duelo X Y   Partidas con desequilibrio: un bando tiene la pieza X y el otro la pieza Y en
              la misma casilla; todo lo demás es igual. Si el bando con X gana más de la
              mitad, X vale más que Y. Cada semilla se juega dos veces, con X en blancas y
              en negras, para cancelar la ventaja de mover primero.
  lote        Los duelos de LOTE (14), pensados para comparar los valores actuales con la
              anteriores (ver ANTERIOR). --partidas es por duelo: con 10, se juegan 140.
  final X Y   Duelo en el final: Reyes, dos peones y un Guardián por bando, más la pieza X
              en un bando y la pieza Y en el otro. Mide los valores de final (VALOR_FINAL).
  lote-final  Duelos de final. --serie validacion (por defecto): LOTE_FINAL_VALIDACION (19), que no
              se usaron para ajustar los valores; --serie ajuste: LOTE_FINAL (14); --serie todas.
  reporte     Resume un archivo de resultados (se puede llamar mientras corre).

Piezas: P, G, B, N, R, CE, CA, CH, Q; con apóstrofo, promocionada (B'). Varias piezas se
suman con «+» (por ejemplo N+P); la primera va en la casilla del duelo y las demás en la
tercera fila. Las partidas que no terminan en mate cuentan como tablas: el desempate por
puntos depende de los propios valores que se quieren medir.

Ejemplos:
  pypy3 validar_valores.py movilidad
  pypy3 validar_valores.py duelo CE N --partidas 100 --procesos 22 --profundidad 3
  pypy3 validar_valores.py lote --partidas 60 --procesos 22 --profundidad 2
  pypy3 validar_valores.py lote-final --partidas 60 --procesos 22 --profundidad 4
  python3 validar_valores.py reporte valores_finales.jsonl
"""
import argparse, json, math, os, random, sys, time
from multiprocessing import Pool
from motor import *
from busqueda import Searcher, zhash, VALOR_FINAL, VERSION_IA

TIPOS = ('P', 'G', 'B', 'N', 'R', 'CE', 'CA', 'CH', 'Q')
NOMBRES = {'P': 'Peón', 'G': 'Guardián', 'B': 'Alfil', 'N': 'Caballo', 'R': 'Torre', 'CE': 'Catapulta',
           'CA': 'Arzobispo', 'CH': 'Canciller', 'Q': 'Dama'}
# Valores anteriores (base, promocionada), para comparar; los actuales están en motor.VAL
ANTERIOR = {'P': (1, 3), 'G': (2, 4), 'B': (3, 6), 'N': (4, 6), 'CE': (4, 6), 'R': (5, 7), 'CA': (5, 7),
            'CH': (6, 8), 'Q': (9, 13)}  # valores antes del ajuste de octubre de 2026
LOTE = [('CE', 'N'), ('CE', 'R'), ("CE'", "R'"), ('N', 'B'), ("B'", 'R'), ("B'", "R'"), ("R'", 'Q'),
        ("CA'", 'CH'), ("CH'", 'Q'), ("Q'", 'Q+B'), ("G'", 'N'), ("N'", "B'"), ("N'", 'CH'), ("CE'", 'Q')]
# Duelos de final: prueban los valores de final de busqueda.VALOR_FINAL. El más importante es
# Catapulta prom. contra Torre prom.: en el medio juego gana la Catapulta, en el final debería ganar la Torre.
LOTE_FINAL = [('R', 'CE'), ('R', 'CA'), ('CH', 'R'), ('B', 'N'), ('N', 'P+P'), ('B', 'P+P'), ("CE'", "R'"),
              ("CE'", 'R'), ("R'", 'Q'), ("Q'", 'Q'), ("B'", 'R'), ("B'", "N'"), ("G'", 'N'), ("CA'", 'R')]
# Valores de final de la versión v3 (la anterior a la vigente), para comparar
FINAL_ANTERIOR = {'P': (1, 2.5), 'G': (2.5, 4.5), 'B': (3, 8.5), 'N': (4, 6.5), 'CE': (6, 7.5), 'R': (5, 9),
                  'CA': (6, 6.5), 'CH': (7.5, 8.5), 'Q': (9.5, 11)}
# Serie de validación: duelos de final que no se usaron para ajustar VALOR_FINAL. Cubren todas las
# piezas en sus dos formas y el valor de los peones (grupos con +P).
LOTE_FINAL_VALIDACION = [
    ('CE', 'CA'), ('N', 'CE'), ('N', 'R'), ('B+P+P', 'R'), ('N+P', 'R'), ('N', 'B+P'),
    ("G'", 'B'), ('G', 'P+P'), ("P'", 'N'), ("P'", 'P+P'),
    ("CH'", 'Q'), ('CH', "CE'"), ("CA'", 'CE'), ("N'", "CE'"), ("R'", "B'"), ("CE'", "CH'"),
    ("B'", 'CH'), ('Q', 'R+R'), ("Q'", 'Q+P')]
# Posición de final, vista desde las blancas; las negras son su giro de 180° (casilla -> 120 - casilla)
FINAL_REY, FINAL_PEONES, FINAL_GUARDIAN = 'f2', ('c4', 'i4'), 'f3'
FINAL_CASILLA, FINAL_FILA_EXTRA = 'd2', 3  # la pieza del duelo y, si es un grupo, las demás en la fila 4


# ====================================================================== piezas
def leer(pieza):
    """'B'' -> ('B', True)."""
    t, pr = pieza.rstrip("'"), pieza.endswith("'")
    if t not in TIPOS:
        raise SystemExit('Pieza desconocida: %s (usa %s)' % (pieza, ', '.join(TIPOS)))
    return t, pr


def leer_grupo(texto):
    return [leer(p) for p in texto.split('+')]


def valor(grupo, tabla):
    return sum(tabla[t][1 if pr else 0] for t, pr in grupo)


def nombre(grupo):
    return ' + '.join(NOMBRES[t] + (' prom.' if pr else '') for t, pr in grupo)


# ====================================================================== movilidad
def _estado(t, pr, sq, rival=None, ocupadas=()):
    st = empty_state()
    put(st, sq, t, 0, pr=pr, moved=True)
    for s, c in ocupadas:
        put(st, s, 'P', c, moved=True)
    if rival is not None:
        put(st, rival, 'P', 1, moved=True)
    return st


def _con_reyes(st, sq):
    libres = [s for s in range(N * N) if st.b[s] is None and s != sq]
    put(st, libres[0], 'K', 0)
    put(st, libres[-1], 'K', 1)
    return st


def casillas(t, pr, sq, ocupadas=()):
    """(solo mover, solo capturar, ambas) desde sq. Capturar: casillas donde capturaría una pieza
    adversaria si la hubiera (con la cadena, en la Catapulta promocionada)."""
    ocup = {s for s, _ in ocupadas}
    mueve = {m[2] for m in pseudo(_estado(t, pr, sq, None, ocupadas)) if m[0] in ('m', 'swap') and m[1] == sq
             and m[2] not in ocup}
    captura = set()
    for s in range(N * N):
        if s == sq or s in ocup:
            continue
        st = _estado(t, pr, sq, s, ocupadas)
        if any(m[1] == sq and m[0] in ('m', 'ep') and m[2] == s for m in pseudo(st)):
            captura.add(s)
        elif t == 'CE' and pr:
            st = _con_reyes(st, sq)
            if any(s in caps for mv, _ in centinela_chains(st, sq) for _, caps in mv[3]):
                captura.add(s)
    return mueve - captura, captura - mueve, mueve & captura


def movilidad(args):
    rng = random.Random(1)
    centro = [sq for sq in range(N * N) if 2 <= sq % N <= 8 and 2 <= sq // N <= 8]
    print('Casillas promedio desde las casillas centrales (c3-i9), tablero vacío y con 30% ocupado.')
    print('«mover» = solo moverse; «capturar» = solo capturar; «ambas» = mover o capturar.\n')
    print('%-24s %21s   %21s   %5s %8s' % ('', 'TABLERO VACÍO', 'TABLERO 30% OCUPADO', 'VALOR', 'ANTERIOR'))
    print('%-24s %6s %8s %6s   %6s %8s %6s' % ('pieza', 'mover', 'capturar', 'ambas', 'mover', 'capturar', 'ambas'))
    for t in TIPOS:
        for pr in (False, True):
            tot = [[0, 0, 0], [0, 0, 0]]
            muestras = centro[::args.paso] if args.paso > 1 else centro
            for sq in muestras:
                for k, (o, rep) in enumerate(((0.0, 1), (0.3, args.repeticiones))):
                    for _ in range(rep):
                        ocupadas = [(s, rng.randint(0, 1)) for s in range(N * N) if s != sq and rng.random() < o]
                        a, b, c = casillas(t, pr, sq, ocupadas)
                        tot[k][0] += len(a) / rep
                        tot[k][1] += len(b) / rep
                        tot[k][2] += len(c) / rep
            n = len(muestras)
            fila = [x / n for x in tot[0] + tot[1]]
            print('%-24s %6.1f %8.1f %6.1f   %6.1f %8.1f %6.1f   %5g %8g' % (
                (NOMBRES[t] + ((' promocionada' if t in ('R', 'CE', 'Q') else ' promocionado') if pr else ''))[:24],
                *fila, VAL[t][1 if pr else 0],
                ANTERIOR[t][1 if pr else 0]), flush=True)


# ====================================================================== duelos
def posicion(x, y, x_blancas, casilla):
    """Posición inicial con el grupo x en un bando y el grupo y en el otro, en la casilla del duelo."""
    st = initial()
    col = sqn(casilla) % N
    pid = 200
    for color, grupo in ((0, x if x_blancas else y), (1, y if x_blancas else x)):
        fila_atras = 0 if color == 0 else N - 1
        fila_extra = 2 if color == 0 else N - 3
        st.b[fila_atras * N + col] = None
        extras = sorted((c for c in range(N) if st.b[fila_extra * N + c] is None), key=lambda c: abs(c - col))
        for i, (t, pr) in enumerate(grupo):
            sq = fila_atras * N + col if i == 0 else fila_extra * N + extras.pop(0)
            put(st, sq, t, color, pr=pr, moved=True, pid=pid)
            pid += 1
            if pr and t not in ('P', 'G'):
                st.tprom[color].add(t)
    return st


def posicion_final(x, y, x_blancas, guardian):
    """Final simétrico: Rey, dos peones y (opcional) un Guardián por bando, más el grupo x en un bando
    y el grupo y en el otro. Las negras son el giro de 180° de las blancas."""
    st = empty_state()
    pid = 300
    for color, grupo in ((0, x if x_blancas else y), (1, y if x_blancas else x)):
        gira = (lambda sq: sq) if color == 0 else (lambda sq: N * N - 1 - sq)
        put(st, gira(sqn(FINAL_REY)), 'K', color, moved=True)
        casillas = [(sqn(c), 'P') for c in FINAL_PEONES] + ([(sqn(FINAL_GUARDIAN), 'G')] if guardian else [])
        for sq, t in casillas:
            put(st, gira(sq), t, color, moved=True, pid=pid)
            pid += 1
        col = sqn(FINAL_CASILLA) % N
        ocupadas = {sq for sq, _ in casillas} | {sqn(FINAL_REY)}
        extras = sorted((c for c in range(N) if FINAL_FILA_EXTRA * N + c not in ocupadas), key=lambda c: abs(c - col))
        for i, (t, pr) in enumerate(grupo):
            sq = sqn(FINAL_CASILLA) if i == 0 else FINAL_FILA_EXTRA * N + extras.pop(0)
            put(st, gira(sq), t, color, pr=pr, moved=True, pid=pid)
            pid += 1
            if pr and t not in ('P', 'G'):
                st.tprom[color].add(t)
    st.turn = 0
    return st


def jugar(tarea):
    seed, xs, ys, x_blancas, prof, tiempo, aleat, max_jug, casilla, tipo, guardian = tarea
    x, y = leer_grupo(xs), leer_grupo(ys)
    rng = random.Random(seed)  # la misma semilla da la misma apertura con X en blancas o en negras
    st = posicion_final(x, y, x_blancas, guardian) if tipo == 'final' else posicion(x, y, x_blancas, casilla)
    hist, vistas = {}, [zhash(st)]
    S = [Searcher(tiempo, prof), Searcher(tiempo, prof)]
    t0, ply = time.time(), 0
    while True:
        k = poskey(st)
        hist[k] = hist.get(k, 0) + 1
        moves = legal(st)
        motivo, ganador = None, None
        if not moves:
            motivo = 'jaque mate' if in_check(st, st.turn) else 'ahogado'
            ganador = (1 - st.turn) if motivo == 'jaque mate' else None
        elif hist[k] >= 3:
            motivo = 'triple repetición'
        elif st.clock >= 100:
            motivo = '50 jugadas'
        elif insufficient(st):
            motivo = 'material insuficiente'
        elif ply >= max_jug * 2:
            motivo = 'límite de jugadas'
        if motivo:
            color_x = 0 if x_blancas else 1
            puntos_x = 0.5 if ganador is None else (1.0 if ganador == color_x else 0.0)
            r = dict(x=xs, y=ys, semilla=seed, x_blancas=x_blancas, motivo=motivo, puntos_x=puntos_x,
                     jugadas=(ply + 1) // 2, profundidad=prof, segundos=round(time.time() - t0, 1),
                     valores_ia=VERSION_IA)
            if tipo == 'final':
                r.update(tipo='final', guardian=guardian)
            return r
        if ply < aleat:
            mv, n = rng.choice(moves)
        else:
            (mv, n), _ = S[st.turn].choose(st, moves, rng, vistas=vistas)
        st = n
        ply += 1
        if st.clock == 0:
            vistas = []
        vistas.append(zhash(st))


def es_final(a):
    return a.modo in ('final', 'lote-final')


def tareas_duelo(x, y, a, inicio):
    out = []
    tipo = 'final' if es_final(a) else 'inicial'
    guardian = not getattr(a, 'sin_guardian', False)
    for i in range(max(1, (a.partidas + 1) // 2)):  # por pares: X con blancas y con negras
        for x_blancas in (True, False):
            out.append((inicio + i, x, y, x_blancas, a.profundidad, a.tiempo or None, a.aperturas_aleatorias,
                        a.max_jugadas, getattr(a, 'casilla', None), tipo, guardian))
    return out


SIN_MARCA = None  # versión para resultados sin marca (opción --sin-marca del reporte)


def version(r):
    """Valores con que jugó la computadora: v1 fijos, v2 dinámicos, v3 final revisado, v4 final ajustado. Los resultados
    sin marca son v1, salvo los de final, que empezaron con v2 (o lo que indique --sin-marca)."""
    return r.get('valores_ia') or SIN_MARCA or ('v2' if r.get('tipo') == 'final' else 'v1')


def clave(r):
    """Grupo de un resultado: duelo, profundidad, tipo (inicial, o final con o sin Guardián) y versión."""
    tipo = r.get('tipo', 'inicial')
    if tipo == 'final':
        tipo = 'final' if r.get('guardian', True) else 'final sin G'
    return r['x'], r['y'], r['profundidad'], tipo, version(r)


def siguiente_semilla(salida, x, y, a):
    if not os.path.exists(salida):
        return 0
    tipo = ('final' if not getattr(a, 'sin_guardian', False) else 'final sin G') if es_final(a) else 'inicial'
    usadas = [r['semilla'] for r in leer_resultados(salida) if clave(r) == (x, y, a.profundidad, tipo, VERSION_IA)]
    return max(usadas) + 1 if usadas else 0


def ejecutar(tareas, a):
    duelos = len({(t[1], t[2]) for t in tareas})
    por_duelo = len(tareas) // duelos
    print('Jugando %d duelo%s × %d partidas = %d partidas, a profundidad %d con %d procesos...' % (
        duelos, '' if duelos == 1 else 's', por_duelo, len(tareas), a.profundidad, a.procesos), flush=True)
    t0 = time.time()
    with open(a.salida, 'a', encoding='utf-8') as f:
        it = Pool(a.procesos).imap_unordered(jugar, tareas) if a.procesos > 1 else map(jugar, tareas)
        for i, r in enumerate(it, 1):
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
            f.flush()
            print('[%d/%d] %s vs %s: %s (%s, %d jugadas, %.0f s)' % (
                i, len(tareas), r['x'], r['y'], {1.0: 'gana X', 0.0: 'gana Y', 0.5: 'tablas'}[r['puntos_x']],
                r['motivo'], r['jugadas'], r['segundos']), flush=True)
    print('Listo en %.0f s.\n' % (time.time() - t0))
    reporte_archivo(a.salida, [(t[1], t[2]) for t in tareas])


def duelo(a):
    inicio = a.semilla if a.semilla is not None else siguiente_semilla(a.salida, a.x, a.y, a)
    ejecutar(tareas_duelo(a.x, a.y, a, inicio), a)


def lista_lote(a):
    if not es_final(a):
        return LOTE
    return {'ajuste': LOTE_FINAL, 'validacion': LOTE_FINAL_VALIDACION,
            'todas': LOTE_FINAL + LOTE_FINAL_VALIDACION}[a.serie]


def lote(a):
    tareas = []
    for x, y in lista_lote(a):
        inicio = a.semilla if a.semilla is not None else siguiente_semilla(a.salida, x, y, a)
        tareas += tareas_duelo(x, y, a, inicio)
    ejecutar(tareas, a)


# ====================================================================== reporte
def leer_resultados(ruta):
    with open(ruta, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def veredicto(score, n, diff):
    """¿Concuerda el resultado con una diferencia de valores 'diff' (X - Y)? Usa el intervalo del 95%."""
    error = 1.96 * math.sqrt(max(score * (1 - score), 0.04) / n)
    bajo, alto = score - error, score + error
    if diff > 0:
        return 'sí' if bajo > 0.5 else ('no' if alto < 0.5 else '¿?')
    if diff < 0:
        return 'sí' if alto < 0.5 else ('no' if bajo > 0.5 else '¿?')
    return 'sí' if bajo <= 0.5 <= alto else 'no'


def reporte_archivo(ruta, solo=None):
    rs = leer_resultados(ruta)
    grupos = {}
    for r in rs:
        grupos.setdefault(clave(r), []).append(r)
    pares = list(dict.fromkeys(solo or []))
    validacion = set(LOTE_FINAL_VALIDACION)
    orden = sorted((k for k in grupos if not pares or k[:2] in pares),
                   key=lambda k: (k[3], k[4], k[:2] in validacion, k[2], pares.index(k[:2]) if pares else 0))
    seccion = None
    for k in orden:
        final = k[3].startswith('final')
        nueva = (k[3], k[4], final and k[:2] in validacion)
        if nueva != seccion:
            seccion = nueva
            if final:
                tablas = [('final IA', VALOR_FINAL), ('final ant.', FINAL_ANTERIOR), ('reglamento', VAL)]
            else:
                tablas = [('actual', VAL), ('anterior', ANTERIOR)]
            titulo = {'inicial': 'DUELOS DESDE LA POSICIÓN INICIAL', 'final': 'DUELOS DE FINAL (con Guardián)',
                      'final sin G': 'DUELOS DE FINAL (sin Guardián)'}[k[3]]
            if final:
                titulo += ' · serie de ' + ('validación' if nueva[2] else 'ajuste')
            print('\n%s · computadora %s' % (titulo, k[4]))
            print('%-12s %-12s %4s %5s %13s %8s %7s |' % ('X', 'Y', 'prof', 'n', 'gana/tab/pie', 'X puntúa', 'Elo')
                  + ''.join(' %-11s' % n for n, _ in tablas))
            print('%-12s %-12s %4s %5s %13s %8s %7s |' % ('', '', '', '', '', '', '')
                  + ''.join(' %-11s' % 'X-Y ¿ok?' for _ in tablas))
        g = grupos[k]
        n = len(g)
        s = sum(r['puntos_x'] for r in g) / n
        w = sum(1 for r in g if r['puntos_x'] == 1)
        l = sum(1 for r in g if r['puntos_x'] == 0)
        elo = 400 * math.log10(min(max(s, 0.01), 0.99) / (1 - min(max(s, 0.01), 0.99)))
        x, y = leer_grupo(k[0]), leer_grupo(k[1])
        columnas = ''
        for _, t in tablas:
            d = valor(x, t) - valor(y, t)
            columnas += ' %+5g %-5s' % (d, veredicto(s, n, d))
        print('%-12s %-12s %4d %5d %5d/%d/%-5d %7.1f%% %+7.0f |' % (
            k[0], k[1], k[2], n, w, n - w - l, l, 100 * s, elo) + columnas)
    print('\nEn los finales: «final IA» son los valores de final vigentes de la computadora (VALOR_FINAL),')
    print('«final ant.» los de la versión v3 y «reglamento» los del Apéndice A. Desde la posición inicial:')
    print('«actual» y «anterior» son los del reglamento vigente y los de antes del ajuste.')
    print('«computadora v1-v4»: valores con que jugó (v1 fijos, v2 dinámicos, v3 final revisado, v4 ajustado).')
    print('X puntúa: porcentaje de puntos del bando con X (las tablas valen medio punto).')
    print('¿ok?: «sí» si el resultado concuerda con esa diferencia de valores (intervalo del 95%), «no» si la')
    print('contradice y «¿?» si faltan partidas para decidir. Con diferencia 0 se espera un resultado parejo.')


def reporte(a):
    global SIN_MARCA
    SIN_MARCA = a.sin_marca
    reporte_archivo(a.archivo)


def main():
    ap = argparse.ArgumentParser(description='Validación de los valores de las piezas del Ajedrez 11x11',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest='modo', required=True)
    m = sub.add_parser('movilidad', help='casillas para mover y para capturar de cada pieza')
    m.add_argument('--repeticiones', type=int, default=3, help='tableros aleatorios por casilla (3)')
    m.add_argument('--paso', type=int, default=1, help='usar una de cada N casillas centrales (más rápido)')
    for nombre_modo, ayuda in (('duelo', 'partidas X contra Y'), ('lote', 'serie de duelos de valoración'),
                               ('final', 'duelo X contra Y en el final'), ('lote-final', 'serie de duelos de final')):
        final = nombre_modo in ('final', 'lote-final')
        d = sub.add_parser(nombre_modo, help=ayuda)
        if nombre_modo in ('duelo', 'final'):
            d.add_argument('x', help="pieza(s) del bando X, por ejemplo CE, B' o N+P")
            d.add_argument('y', help='pieza(s) del bando Y')
        d.add_argument('--partidas', type=int, default=60,
                       help='partidas POR DUELO (60); se juegan por pares, así que un número impar se redondea '
                            'hacia arriba. En «lote» el total es este número por la cantidad de duelos')
        d.add_argument('--profundidad', type=int, default=2, help='medias jugadas de búsqueda (2)')
        d.add_argument('--tiempo', type=float, default=0, help='segundos máximos por jugada (0 = sin límite)')
        d.add_argument('--procesos', type=int, default=1, help='partidas en paralelo')
        d.add_argument('--aperturas-aleatorias', type=int, default=2 if final else 4,
                       help='medias jugadas iniciales al azar (%d)' % (2 if final else 4))
        d.add_argument('--max-jugadas', type=int, default=200, help='límite de jugadas por partida (200)')
        if final:
            d.add_argument('--sin-guardian', action='store_true', help='finales solo con dos peones por bando')
            if nombre_modo == 'lote-final':
                d.add_argument('--serie', choices=('validacion', 'ajuste', 'todas'), default='validacion',
                               help='validacion: %d duelos nuevos (por defecto); ajuste: los %d con que se '
                                    'ajustaron los valores; todas' % (len(LOTE_FINAL_VALIDACION), len(LOTE_FINAL)))
        else:
            d.add_argument('--casilla', default='g1', help='casilla del duelo para las blancas (g1, la Catapulta)')
        d.add_argument('--semilla', type=int, default=None, help='semilla inicial (por defecto continúa el archivo)')
        salida = 'valores_finales.jsonl' if final else 'valores.jsonl'
        d.add_argument('--salida', default=salida, help='archivo de resultados (%s)' % salida)
    r = sub.add_parser('reporte', help='resumen de un archivo de resultados')
    r.add_argument('archivo', nargs='?', default='valores.jsonl')
    r.add_argument('--sin-marca', choices=('v1', 'v2', 'v3', 'v4'), default=None,
                   help='versión de la computadora para resultados sin marca (por ejemplo v2 para '
                        'valores_dinamicos.jsonl, jugado antes de existir la marca)')
    a = ap.parse_args()
    if a.modo != 'movilidad' and a.modo != 'reporte':
        lista = [(a.x, a.y)] if a.modo in ('duelo', 'final') else lista_lote(a)
        for x, y in lista:
            leer_grupo(x), leer_grupo(y)
    {'movilidad': movilidad, 'duelo': duelo, 'lote': lote, 'final': duelo, 'lote-final': lote,
     'reporte': reporte}[a.modo](a)


if __name__ == '__main__':
    main()
