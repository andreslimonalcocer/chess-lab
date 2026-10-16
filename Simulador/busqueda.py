import math, os, random, time
from motor import *

MATE = 100000
REMATE_VENTAJA = 3   # ventaja de material (en peones) a partir de la cual se busca el remate
REMATE_FINAL = 20    # material del bando débil por debajo del cual se considera final
DESPRECIO = 0.5  # cuánto le disgusta a cada bando repetir posición (en peones)
PERDER_POR_PUNTOS = MATE // 4  # la repetición la gana quien va arriba en puntos (7.6): para el otro es derrota

# Valores dinámicos de la computadora: (base, promocionada) en el medio juego y en el final. Se mezclan
# según la fase de la partida (cuánto material queda, sin contar peones, Guardianes ni Reyes). Son
# distintos de VAL (motor.py), que son los del reglamento para el desempate por puntos (7.6).
# Medio juego: duelos simulados (validar_valores.py). Final: finales exactos (finales.py).
# v7: afinados con Texel (antes, v6: ver parametros_v6.json)
VALOR_MEDIO = {'P': (0.46, 1.99), 'G': (1.89, 3.51), 'B': (3.04, 6.52), 'N': (3.54, 6.03),
               'CE': (4.97, 10.35), 'R': (4.9, 7.48), 'CA': (5.1, 6.04), 'CH': (5.97, 8.51),
               'Q': (9.04, 10.63), 'K': (0, 0)}
# Final ajustado con 33 duelos de final con peones (1,980 partidas, validar_valores.py lote-final,
# series de ajuste y de validación): con peones en juego las piezas con saltos valen más de lo que
# indican los finales de Rey y pieza contra Rey, el Guardián gana mucho valor y la Catapulta
# promocionada lo pierde. Precisión aproximada: ±0.3.
VALOR_FINAL = {'P': (0.45, 3.04), 'G': (3.12, 5.47), 'B': (3.07, 9.02), 'N': (4.53, 6.07),
               'CE': (5.98, 7.85), 'R': (4.9, 8.98), 'CA': (6.54, 6.54), 'CH': (8.51, 8.54),
               'Q': (9.53, 11.63), 'K': (0, 0)}
VERSION_IA = 'v7'  # v1: valores fijos; v2: dinámicos con el primer final; v3: final revisado; v4: final ajustado;
# v5: términos desarrollo, derechos y movilidad encendidos; v6: búsqueda moderna (OPCIONES); v7: valores y
# pesos afinados con Texel (afinar_texel.py, 1000 partidas a profundidad 3; +74 Elo) (octubre de 2026)
SIN_FASE = ('P', 'G', 'K')  # piezas que no cuentan para calcular la fase
FASE_INICIAL = sum(VALOR_MEDIO[p.t][0] for p in initial().b if p and p.t not in SIN_FASE)


# Bonos de posición: cada tipo de pieza tiene un coeficiente de centralización (por casilla de distancia al
# borde, 0 a 5) y uno de avance (por fila avanzada); la forma promocionada solo centralización. Los valores
# por defecto reproducen la evaluación original (centro 0.02 para todas las piezas, avance 0.03 para peones
# y Guardianes); afinar_texel.py los ajusta por tipo de pieza.
DIST_CENTRO = [5 - max(abs(sq % N - 5), abs(sq // N - 5)) for sq in range(N * N)]
FILA_AVANCE = [[(sq // N) if c == 0 else (N - 1 - sq // N) for sq in range(N * N)] for c in (0, 1)]
CENTRO = {t: (0.0 if t in ('P', 'G') else 0.02) for t in VALOR_MEDIO}
CENTRO_PROM = {t: 0.02 for t in VALOR_MEDIO}
AVANCE = {t: (0.03 if t in ('P', 'G') else 0.0) for t in VALOR_MEDIO}
TABLA_POS = {}  # [tipo][promocionada][color] -> bono por casilla
VALORES_IA = {}
EN_FASE = {t: t not in SIN_FASE for t in VALOR_MEDIO}


def reconstruir_tablas():
    """Recalcula las tablas derivadas de los parámetros (tras cambiarlos con cargar_parametros)."""
    global FASE_INICIAL
    FASE_INICIAL = sum(VALOR_MEDIO[p.t][0] for p in initial().b if p and p.t not in SIN_FASE)
    for t in VALOR_MEDIO:
        VALORES_IA[t] = ((VALOR_MEDIO[t][0], VALOR_FINAL[t][0]), (VALOR_MEDIO[t][1], VALOR_FINAL[t][1]))
        TABLA_POS[t] = (
            [[CENTRO[t] * DIST_CENTRO[sq] + AVANCE[t] * FILA_AVANCE[c][sq] for sq in range(N * N)] for c in (0, 1)],
            [[CENTRO_PROM[t] * DIST_CENTRO[sq] for sq in range(N * N)] for c in (0, 1)])


def parametros():
    """Parámetros afinables de la evaluación (los que lee y escribe afinar_texel.py)."""
    return {'VALOR_MEDIO': {t: list(v) for t, v in VALOR_MEDIO.items() if t != 'K'},
            'VALOR_FINAL': {t: list(v) for t, v in VALOR_FINAL.items() if t != 'K'},
            'CENTRO': dict(CENTRO), 'CENTRO_PROM': dict(CENTRO_PROM), 'AVANCE': dict(AVANCE), 'PESOS': dict(PESOS)}


def cargar_parametros(d):
    """Aplica parámetros con la forma de parametros() (pueden ser parciales)."""
    for t, v in d.get('VALOR_MEDIO', {}).items():
        VALOR_MEDIO[t] = tuple(v)
    for t, v in d.get('VALOR_FINAL', {}).items():
        VALOR_FINAL[t] = tuple(v)
    for nombre, tabla in (('CENTRO', CENTRO), ('CENTRO_PROM', CENTRO_PROM), ('AVANCE', AVANCE), ('PESOS', PESOS)):
        tabla.update(d.get(nombre, {}))
    reconstruir_tablas()


# Términos de evaluación adicionales (peso 0 = apagado). Se activan cuando las partidas de comparar.py
# muestran que ayudan:
#   pasados    peones y Guardianes pasados (sin peones ni Guardianes rivales delante, en su columna o
#              las vecinas): bono que crece con el avance, mayor en el final
#   escudo     peones y Guardianes propios delante del Rey (medio juego)
#   movilidad  casillas libres en las líneas de las piezas de largo alcance
#   rey        seguridad del Rey en el medio juego: premio por enrocar (Rey en un flanco de su primera
#              fila) y por despejar el camino del enroque, castigo por quedarse en el centro sin poder
#              enrocar o por adelantarse, y por cada casilla vecina al Rey que ataca el rival
#   desarrollo apertura: castigo por cada pieza menor o mayor (Caballo, Alfil, Arzobispo, Canciller,
#              Catapulta) que no se ha movido, y por sacar la Dama mientras quedan varias sin desarrollar
#   atacadas   piezas del bando que mueve atacadas por una pieza de menor valor o sin defensa: la
#              búsqueda de capturas ya resuelve las del rival, pero las propias solo se ven una jugada
#              después; puede salvar una, así que pesa sobre todo la segunda amenaza
#   derechos   derechos de promoción, en lugar del bono fijo: mezclado según la fase (medio juego y
#              final), también para convertir peones en Guardianes (5.4 a) y promocionar Guardianes
#              (5.4 b), y un bono parcial por cada derecho al que le falta una sola captura
# Validación (validar_terminos.sh y comparar.py, 200 partidas cada una, octubre de 2026): a profundidad 3,
# desarrollo +89, derechos +92 y movilidad +108 Elo por separado; juntos +177, y +104 con el mismo tiempo
# por jugada (1 s). rey +30 solo, pero -123 sumado a los tres con el mismo tiempo; escudo +9; atacadas -3
# y casi duplica el tiempo de la evaluación. Por eso se encienden solo los tres primeros.
#   enroque    la parte barata de «rey»: premio por enrocar y por despejar el camino del enroque, castigo
#              por quedarse en el centro sin poder enrocar o por adelantar el Rey (sin contar ataques)
PESOS = {'pasados': 0.0, 'escudo': 0.0, 'movilidad': 1.0, 'rey': 0.0, 'desarrollo': 1.0, 'atacadas': 0.0,
         'derechos': 1.0, 'enroque': 0.0}
SIN_DESARROLLAR = ('N', 'B', 'CA', 'CH', 'CE')
LARGO_ALCANCE = {'Q': (0, 8), 'R': (0, 4), 'B': (4, 8), 'CA': (4, 8), 'CH': (0, 4)}  # rayos que recorren
ESCUDO = [[[s for s in SALTOS_REY[sq] if (s // N - sq // N) == (1 if c == 0 else -1)] for sq in range(N * N)]
          for c in (0, 1)]


def terminos_extra(st, f, me):
    """Términos de PESOS, desde el bando que mueve; f es la fase (1 medio juego, 0 final)."""
    b = st.b
    peones = ([], [])
    s = 0.0
    wp, we, wm = PESOS['pasados'], PESOS['escudo'], PESOS['movilidad']
    for sq in range(N * N):
        p = b[sq]
        if p is None:
            continue
        t = p.t
        if (t == 'P' or t == 'G') and not p.pr:
            peones[p.c].append(sq)
        elif wm and t in LARGO_ALCANCE:
            a, z = LARGO_ALCANCE[t]
            libres = 0
            for rayo in RAYOS[sq][a:z]:
                for i in rayo:
                    if b[i] is not None:
                        break
                    libres += 1
            v = wm * 0.02 * libres
            s += v if p.c == me else -v
    if wp:
        for c in (0, 1):
            rivales = peones[1 - c]
            for sq in peones[c]:
                col, fila = sq % N, sq // N
                if c == 0:
                    pasado = all(not (abs(r % N - col) <= 1 and r // N > fila) for r in rivales)
                    avance = fila - 1
                else:
                    pasado = all(not (abs(r % N - col) <= 1 and r // N < fila) for r in rivales)
                    avance = N - 2 - fila
                if pasado:
                    v = wp * (0.1 + 0.06 * avance) * (1.5 - 0.5 * f)
                    s += v if c == me else -v
    if we and f > 0:
        for c in (0, 1):
            k = st.kpos[c]
            if k is None:
                continue
            escudo = sum(1 for i in ESCUDO[c][k] if b[i] is not None and b[i].c == c and b[i].t in ('P', 'G'))
            v = we * 0.1 * escudo * f
            s += v if c == me else -v
    wr, wd, wa, wder = PESOS['rey'], PESOS['desarrollo'], PESOS['atacadas'], PESOS['derechos']
    we2 = PESOS['enroque']
    if we2 and f > 0:
        for c in (0, 1):
            v = valor_enroque(b, st.kpos[c], c)
            v *= we2 * f
            s += v if c == me else -v
    if wder:
        s += wder * derechos(st, f, me)
    if wr and f > 0:
        for c in (0, 1):
            k = st.kpos[c]
            if k is None:
                continue
            fila = k // N if c == 0 else N - 1 - k // N
            col = k % N
            v = 0.0
            if fila == 0 and (col <= 2 or col >= N - 3):
                v += 0.4  # enrocado (o el Rey ya en un flanco)
            elif b[k].moved and 3 <= col <= N - 4:
                v -= 0.3  # en el centro y sin derecho a enrocar
            elif not b[k].moved and fila == 0:
                # aún puede enrocar: en el 11×11 hay que despejar cuatro casillas, así que se premia cada
                # casilla libre entre el Rey y una Torre sin mover (la búsqueda no ve tan lejos el enroque)
                mejor = 0
                for rc in (0, N - 1):
                    t = b[k - col + rc]
                    if t is not None and t.c == c and t.t == 'R' and not t.moved:
                        lo, hi = min(rc, col), max(rc, col)
                        mejor = max(mejor, sum(1 for x in range(lo + 1, hi) if b[k - col + x] is None))
                v += 0.06 * mejor
            v -= 0.15 * min(fila, 4)  # adelantado
            v -= 0.08 * sum(1 for i in SALTOS_REY[k] if attacked(b, i, 1 - c))
            v *= wr * f
            s += v if c == me else -v
    if wd and f > 0.5:
        for c in (0, 1):
            fila0 = 0 if c == 0 else N - 1
            quietas = sum(1 for col in range(N) if b[fila0 * N + col] is not None and b[fila0 * N + col].c == c
                          and b[fila0 * N + col].t in SIN_DESARROLLAR and not b[fila0 * N + col].moved)
            v = 0.12 * quietas
            if quietas >= 3:
                v += sum(0.2 for p in b if p is not None and p.c == c and p.t == 'Q' and p.moved)
            v *= -wd * (2 * f - 1)  # pesa en la apertura y desaparece hacia la mitad de la partida
            s += v if c == me else -v
    if wa:
        amenazas = []
        for sq in range(N * N):
            p = b[sq]
            if p is None or p.c != me or p.t == 'K' or not attacked(b, sq, 1 - me):
                continue
            v = valor_ia(p, f)
            if attacked(b, sq, me):  # defendida: solo cuenta si la ataca una pieza de menor valor
                a = min_att(b, sq, 1 - me)
                v = v - (a if a is not None and a < 50 else v)
            if v > 0.5:
                amenazas.append(v)
        if amenazas:
            amenazas.sort(reverse=True)
            s -= wa * (0.15 * amenazas[0] + (0.6 * amenazas[1] if len(amenazas) > 1 else 0.0))
    return s


def valor_enroque(b, k, c):
    """Situación del Rey respecto del enroque, en peones (sin el peso ni la fase)."""
    if k is None:
        return 0.0
    fila = k // N if c == 0 else N - 1 - k // N
    col = k % N
    v = 0.0
    if fila == 0 and (col <= 2 or col >= N - 3):
        v += 0.4  # enrocado (o el Rey ya en un flanco)
    elif b[k].moved and 3 <= col <= N - 4:
        v -= 0.3  # en el centro y sin derecho a enrocar
    elif not b[k].moved and fila == 0:
        mejor = 0  # casillas ya libres entre el Rey y una Torre sin mover
        for rc in (0, N - 1):
            t = b[k - col + rc]
            if t is not None and t.c == c and t.t == 'R' and not t.moved:
                lo, hi = min(rc, col), max(rc, col)
                mejor = max(mejor, sum(1 for x in range(lo + 1, hi) if b[k - col + x] is None))
        v += 0.06 * mejor
    return v - 0.15 * min(fila, 4)


def _ganancia(t, desde, f):
    """Cuánto gana una pieza de tipo t al promocionar (desde = forma de origen), en la fase f."""
    a, b = desde
    return f * (VALOR_MEDIO[b[0]][b[1]] - VALOR_MEDIO[a[0]][a[1]]) + \
        (1 - f) * (VALOR_FINAL[b[0]][b[1]] - VALOR_FINAL[a[0]][a[1]])


def derechos(st, f, me):
    """Derechos de promoción de los dos bandos, desde el que mueve. Un derecho disponible vale el 60 % de
    lo que gana la pieza al promocionar; uno al que le falta una captura (y el rival aún tiene esa pieza),
    el 15 %."""
    b = st.b
    propias = ({}, {})   # tipos con alguna pieza sin promocionar, por bando
    hay = ({}, {})       # tipos presentes (en cualquier forma), por bando
    for p in b:
        if p is not None:
            hay[p.c][p.t] = hay[p.c].get(p.t, 0) + 1
            if not p.pr:
                propias[p.c][p.t] = propias[p.c].get(p.t, 0) + 1
    s = 0.0
    for c in (0, 1):
        rival = hay[1 - c]
        v = 0.0
        ct = st.capT[c]
        for t in propias[c]:
            need = NEED.get(t)
            if not need or t in st.tprom[c]:
                continue
            tiene = ct.get(t, 0)
            if tiene >= need:
                v += 0.6 * _ganancia(t, ((t, 0), (t, 1)), f)
            elif tiene == need - 1 and rival.get(t):
                v += 0.15 * _ganancia(t, ((t, 0), (t, 1)), f)
        # 5.4 (a): peón convertido en Guardián; 5.4 (b): Guardián promocionado
        for t, capturas, usados, por, destino in (('P', st.capP[c], st.conv[c], PEONES_POR_GUARDIAN, ('G', 0)),
                                                   ('G', st.capG[c], st.gprom[c], GUARDIANES_POR_PROMOCION, ('G', 1))):
            piezas = propias[c].get(t, 0)
            if not piezas:
                continue
            ganancia = _ganancia(t, ((t, 0), destino), f)
            disponibles = min(capturas // por - usados, piezas)
            if disponibles > 0:
                v += 0.6 * ganancia * disponibles
            elif capturas % por == por - 1 and rival.get(t):
                v += 0.15 * ganancia
        s += v if c == me else -v
    return s


# v7: centralización y avance afinados con Texel (casi iguales a los originales) y pesos de los términos
CENTRO.update({'P': -0.0003, 'G': -0.0008, 'B': 0.0203, 'N': 0.0204, 'CE': 0.0197, 'R': 0.0197, 'CA': 0.0203, 'CH': 0.0197, 'Q': 0.0197, 'K': 0.02})
CENTRO_PROM.update({'P': 0.0204, 'G': 0.0203, 'B': 0.0202, 'N': 0.0204, 'CE': 0.0196, 'R': 0.0197, 'CA': 0.0204, 'CH': 0.0203, 'Q': 0.0204, 'K': 0.02})
AVANCE.update({'P': 0.028, 'G': 0.0264, 'B': -0.0007, 'N': 0.0007, 'CE': -0.0006, 'R': -0.0005, 'CA': -0.0006, 'CH': 0.0006, 'Q': -0.0005, 'K': 0.0})
PESOS.update({'pasados': 0.0, 'escudo': 0.0, 'movilidad': 1.057, 'rey': 0.0, 'desarrollo': 0.989, 'atacadas': 0.0, 'derechos': 1.065, 'enroque': 0.0})
reconstruir_tablas()


def fase(st):
    """1 = medio juego (todo el material), 0 = final (sin piezas aparte de peones y Guardianes)."""
    m = sum(VALOR_MEDIO[p.t][1 if p.pr else 0] for p in st.b if p and p.t not in SIN_FASE)
    return min(1.0, m / FASE_INICIAL)


def valor_ia(p, f):
    """Valor de una pieza para la computadora en la fase f."""
    i = 1 if p.pr else 0
    return f * VALOR_MEDIO[p.t][i] + (1 - f) * VALOR_FINAL[p.t][i]
rnd = random.Random(12345)
ZK = {}
for sq in range(N * N):
    for t in VAL:
        for c in (0, 1):
            for pr in (False, True):
                ZK[(sq, t, c, pr)] = rnd.getrandbits(62)
ZTURN = rnd.getrandbits(62)
# los mismos números, indexados por [tipo][color][promocionada][casilla] para no crear tuplas
ZKT = {t: [[[ZK[(sq, t, c, pr)] for sq in range(N * N)] for pr in (False, True)] for c in (0, 1)] for t in VAL}


def zhash(st):
    h = ZTURN if st.turn else 0
    b = st.b
    for sq in range(N * N):
        p = b[sq]
        if p is not None:
            h ^= ZKT[p.t][p.c][p.pr][sq]
    if st.ep:
        h ^= st.ep[1] * 7919
    return h


def evaluate(st):
    """Evaluación desde el punto de vista del bando que mueve."""
    me = st.turn
    medio = final = s = 0.0  # material en el medio juego, en el final y términos de posición
    material_fase = 0.0
    sin_promocionar = ({}, {})  # tipos con alguna pieza sin promocionar, por bando
    mat = [0, 0]
    b = st.b
    for sq in range(N * N):
        p = b[sq]
        if p is None:
            continue
        t = p.t
        if t == 'K':
            continue
        c = p.c
        if p.pr:
            vm, vf = VALORES_IA[t][1]
            pos = TABLA_POS[t][1][c][sq]
        else:
            vm, vf = VALORES_IA[t][0]
            sin_promocionar[c][t] = True
            pos = TABLA_POS[t][0][c][sq]
        mat[c] += vm
        if EN_FASE[t]:
            material_fase += vm
        if c == me:
            medio += vm; final += vf; s += pos
        else:
            medio -= vm; final -= vf; s -= pos
    f = min(1.0, material_fase / FASE_INICIAL)
    s += f * medio + (1 - f) * final
    if PESOS['pasados'] or PESOS['escudo'] or PESOS['movilidad'] or PESOS['rey'] or PESOS['desarrollo'] \
            or PESOS['atacadas'] or PESOS['derechos'] or PESOS['enroque']:
        s += terminos_extra(st, f, me)
    for color in (0, 1) if not PESOS['derechos'] else ():  # con «derechos», los calcula terminos_extra
        ct = st.capT[color]
        if not ct:
            continue
        bonus = 0.0
        for t in sin_promocionar[color]:
            need = NEED.get(t)
            if need and t not in st.tprom[color] and ct.get(t, 0) >= need:
                bonus += 0.6 * (VALOR_MEDIO[t][1] - VALOR_MEDIO[t][0])
        s += bonus if color == me else -bonus
    # Remate: en el final, el bando con clara ventaja empuja al Rey rival hacia el borde y acerca
    # el suyo. Sin esto la búsqueda no ve el mate a lo lejos y mueve piezas sin avanzar, lo que
    # acaba en repeticiones o en la regla de las 50 jugadas.
    fuerte = 0 if mat[0] > mat[1] else 1
    debil = 1 - fuerte
    if mat[fuerte] - mat[debil] >= REMATE_VENTAJA and mat[debil] <= REMATE_FINAL:
        kf, kd = st.kpos[fuerte], st.kpos[debil]
        borde = max(abs(kd % N - 5), abs(kd // N - 5))
        cerca = 10 - max(abs(kf % N - kd % N), abs(kf // N - kd // N))
        r = 0.12 * borde + 0.06 * cerca
        s += r if fuerte == me else -r
    return s


def gen(st, solo_capturas=False):
    out = [(mv, None) for mv in pseudo(st, solo_capturas)]
    me = st.turn
    for sq in range(N * N):
        p = st.b[sq]
        if p and p.c == me and p.t == 'CE' and p.pr:
            out.extend(centinela_chains(st, sq))
    return out


def is_capture(st, mv):
    k = mv[0]
    if k == 'ep' or k == 'ch':
        return True
    if k == 'm':
        return st.b[mv[2]] is not None
    return k in ('pr', 'cv', 'gp')


def mvv(st, mv):
    k = mv[0]
    if k == 'ch':
        return sum(val(st.b[c]) for _, caps in mv[3] for c in caps if st.b[c]) * 10
    if k == 'ep':
        return 10
    if k == 'm' and st.b[mv[2]] is not None:
        return val(st.b[mv[2]]) * 10 - val(st.b[mv[1]]) * 0.1
    if k in ('pr', 'cv', 'gp'):
        return 15
    return 0


MEJORAS = True  # búsqueda mejorada (movimiento nulo, PVS, extensión de jaques, historial, poda delta)

# Mejoras de la búsqueda inspiradas en los motores modernos (validadas con comparar.py --sprt; ver abajo):
#   tt_persistente     la tabla de transposición y el historial se conservan entre jugadas (si mueve el mismo
#                      bando); el historial se reduce a la mitad en cada jugada
#   aspiracion         ventana de aspiración en la raíz alrededor del valor de la iteración anterior
#   lmr_log            reducción de jugadas tardías graduada: ln(profundidad) × ln(número de jugada)
#   futilidad          cerca de las hojas, no analiza jugadas tranquilas si la posición está muy por debajo de alfa
#   futilidad_inversa  corta si la evaluación supera beta por un margen (movimiento nulo «estático»)
#   razoring           en profundidad 1-2, si la evaluación está muy por debajo de alfa, solo mira capturas
#   poda_tardia        en profundidad 1-3, ignora las jugadas tranquilas después de cierto número
#   see                intercambio estático: las capturas que pierden material van al final y no se miran
#                      en la búsqueda de capturas
#   contrajugada       recuerda la jugada que refutó a cada jugada del rival y la ordena antes
#   finales            usa las tablas exactas de Rey y pieza contra Rey (finales.py --guardar-tablas)
# Validación con SPRT (1 s por jugada, octubre de 2026): tt_persistente +30 y poda_tardia +50 (H1 cada una);
# aspiración + SEE sobre ellas -45 (H0), pero futilidad + futilidad inversa + razoring + contrajugada encima
# de las cuatro +104 (H1), y quitar aspiración + SEE de ese paquete -34 (H0): se quedan las ocho. lmr_log
# (-4, sin decidir) queda apagada. Todas juntas contra el motor v5: +121 Elo.
OPCIONES = {'tt_persistente': True, 'aspiracion': True, 'lmr_log': False, 'futilidad': True,
            'futilidad_inversa': True, 'razoring': True, 'poda_tardia': True, 'see': True,
            'contrajugada': True, 'finales': False}
LIMITE_TT = 1000000  # entradas (~150 MB); si la tabla crece más, se vacía
MARGEN_FUTILIDAD = 1.5      # peones por unidad de profundidad
MARGEN_FUT_INVERSA = 1.2
MARGEN_RAZORING = 2.5
MAT_PODA = MATE / 2  # no se poda cerca de un mate
REDUCCION = [[0] + [int(0.5 + math.log(d) * math.log(m) / 2.5) if d and m else 0 for m in range(1, 256)]
             for d in range(64)]


def _valor_see(p):
    return 50 if p.t == 'K' else val(p)


def see(st, mv):
    """Intercambio estático en la casilla de destino de una captura simple: material que gana (o pierde,
    si es negativo) el bando que mueve si los dos siguen capturando ahí con su pieza de menor valor."""
    b = st.b[:]
    a = mv[2]
    ganancia = [val(b[a])]
    pieza = b[mv[1]]
    b[mv[1]], b[a] = None, pieza
    lado = 1 - st.turn
    for _ in range(12):
        atk = attackers(b, a, lado)
        if not atk:
            break
        s = min(atk, key=lambda i: _valor_see(b[i]))
        ganancia.append(_valor_see(pieza) - ganancia[-1])
        pieza = b[s]
        b[s], b[a] = None, pieza
        lado = 1 - lado
    for i in range(len(ganancia) - 1, 0, -1):
        ganancia[i - 1] = -max(-ganancia[i - 1], ganancia[i])
    return ganancia[0]


def captura_mala(st, mv):
    """¿Es una captura simple que pierde material según SEE? (solo se calcula si atacante vale más)."""
    if mv[0] != 'm':
        return False
    v, a = st.b[mv[2]], st.b[mv[1]]
    return v is not None and val(v) < val(a) and see(st, mv) < 0


# ---------------------------------------------------------------- tablas exactas de finales
CARPETA_TABLAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tablas')
_TABLAS = {}
# las tablas son exactas: si ya se construyeron (finales.py --guardar-tablas), se usan por defecto
OPCIONES['finales'] = os.path.isdir(CARPETA_TABLAS) and any(f.endswith('.dtm') for f in os.listdir(CARPETA_TABLAS))


def nombre_pieza_tabla(t, pr):
    return t + ('p' if pr else '')


def archivo_tabla(t, pr, t2=None, pr2=False):
    """Tabla de Rey y una pieza (finales.py) o dos (finales_dos.py --guardar) contra Rey."""
    otra = nombre_pieza_tabla(t2, pr2) if t2 else ''
    return os.path.join(CARPETA_TABLAS, 'K%s%sK.dtm' % (nombre_pieza_tabla(t, pr), otra))


def _abrir(ruta):
    """La tabla como bytes de solo lectura. Se usa mmap: el sistema carga solo las partes que se leen y las
    comparten todos los procesos (importante con las de dos piezas, de 212 a 429 MB)."""
    if ruta not in _TABLAS:
        try:
            import mmap
            with open(ruta, 'rb') as f:
                _TABLAS[ruta] = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        except (OSError, ValueError, ImportError):
            _TABLAS[ruta] = None
    return _TABLAS[ruta]


def _tabla(t, pr):
    return _abrir(archivo_tabla(t, pr))


def _voltear(sq):
    return (N - 1 - sq // N) * N + sq % N


NP_IGUALES = N * N * (N * N - 1) // 2  # pares sin orden de dos piezas iguales (como en finales_dos.py)


def _par_iguales(x, y):
    if x > y:
        x, y = y, x
    return x * (2 * N * N - x - 1) // 2 + (y - x - 1)


def _derecho_pendiente(st, p):
    """¿Tiene el dueño de la pieza un derecho de promoción que las tablas no contemplan?"""
    t, c = p.t, p.c
    if p.pr:
        return False
    return ((t in NEED and t not in st.tprom[c] and st.capT[c].get(t, 0) >= NEED[t]) or
            (t == 'P' and st.capP[c] // PEONES_POR_GUARDIAN > st.conv[c]) or
            (t == 'G' and st.capG[c] // GUARDIANES_POR_PROMOCION > st.gprom[c]))


def dtm_final(st):
    """(medias jugadas hasta el mate del bando fuerte o 255 si no lo fuerza, color del bando fuerte) si quedan
    los dos Reyes y una o dos piezas de un mismo bando y existe su tabla; si no, None."""
    b = st.b
    otras, n = [], 0
    for sq in range(N * N):
        p = b[sq]
        if p is not None:
            n += 1
            if n > 4:
                return None
            if p.t != 'K':
                otras.append(sq)
    if not otras or n != len(otras) + 2:
        return None
    c = b[otras[0]].c
    if any(b[x].c != c or _derecho_pendiente(st, b[x]) for x in otras):
        return None
    wk, bk, turno = st.kpos[0], st.kpos[1], st.turn
    cas = list(otras)
    if c == 1:  # las tablas son de las piezas blancas: se voltea el tablero y se cambian los colores
        wk, bk, turno = _voltear(st.kpos[1]), _voltear(st.kpos[0]), 1 - st.turn
        cas = [_voltear(x) for x in cas]
    if len(cas) == 1:
        p = b[otras[0]]
        tabla = _tabla(p.t, p.pr)
        if tabla is None:
            return None
        nx = 2 * N * N if (p.t in ('P', 'G') and not p.pr) else N * N
        return tabla[((wk * N * N + bk) * nx + cas[0]) * 2 + turno], c
    pa, pb = b[otras[0]], b[otras[1]]
    if (pa.t, pa.pr) == (pb.t, pb.pr):
        tabla = _abrir(archivo_tabla(pa.t, pa.pr, pb.t, pb.pr))
        if tabla is None:
            return None
        return tabla[((wk * N * N + bk) * NP_IGUALES + _par_iguales(cas[0], cas[1])) * 2 + turno], c
    for (x, y), (sx, sy) in (((pa, pb), (cas[0], cas[1])), ((pb, pa), (cas[1], cas[0]))):
        tabla = _abrir(archivo_tabla(x.t, x.pr, y.t, y.pr))  # la primera pieza del nombre va primero
        if tabla is not None:
            # índice como en finales_dos.py: ((wk·121 + bk)·121² + a·121 + b)·2 + turno
            return tabla[((wk * N * N + bk) * (N * N) ** 2 + sx * N * N + sy) * 2 + turno], c
    return None


def consultar_final(st, ply):
    """Valor exacto (desde el bando que mueve) si quedan solo los dos Reyes y una o dos piezas de un bando y
    existe su tabla; None si no aplica. Solo se fía de la tabla si el bando fuerte no tiene un derecho de
    promoción que la tabla no contempla y si el mate llega antes de la regla de las 50 jugadas."""
    r = dtm_final(st)
    if r is None:
        return None
    d, c = r
    if d == 255:
        return 0.0  # el bando fuerte no puede forzar el mate
    if st.clock + d > 100:
        return None
    v = MATE - ply - d
    return v if st.turn == c else -v


def tiene_piezas(st, color):
    """¿Tiene el bando alguna pieza aparte del Rey, peones y Guardianes? (el movimiento nulo no es
    seguro sin piezas: en esos finales pasar el turno puede ser lo peor, «zugzwang»)."""
    for p in st.b:
        if p is not None and p.c == color and p.t not in ('K', 'P', 'G'):
            return True
    return False


MARGEN_TEMPERATURA = 8  # jugadas a más de MARGEN × temperatura de la mejor: probabilidad < 1/3000, se descartan


def puntuaciones_exactas(buscador, scores, d):
    """[(puntuación exacta, jugada, posición)] de las jugadas de la raíz a profundidad d que pueden elegirse
    con la temperatura del buscador, de mejor a peor; None si se acabó el tiempo. La mejor se calcula con
    ventana completa y las demás con una ventana de MARGEN_TEMPERATURA × temperatura bajo ella: las que
    quedan por debajo tendrían una probabilidad despreciable y se descartan sin calcular su valor exacto,
    lo que es mucho más rápido. Sirve también para generico.Buscador (misma interfaz)."""
    _, mv, n = scores[0]
    mejor = -buscador.ab(n, d - 1, -MATE * 2, MATE * 2, 1)
    if buscador.stop:
        return None
    out = [(mejor, mv, n)]
    piso = mejor - MARGEN_TEMPERATURA * buscador.temperatura
    techo = mejor + 1.0
    for _, mv, n in scores[1:]:
        sc = -buscador.ab(n, d - 1, -techo, -piso, 1)
        if not buscador.stop and sc >= techo:  # mejor de lo esperado: valor exacto con ventana completa
            sc = -buscador.ab(n, d - 1, -MATE * 2, MATE * 2, 1)
        if buscador.stop:
            return None
        if sc > piso:
            out.append((sc, mv, n))
    out.sort(key=lambda x: -x[0])
    return out


class Searcher:
    def __init__(self, time_limit=1.0, max_depth=5, mejoras=None, temperatura=0.0):
        """temperatura (en peones): 0 = juega siempre la mejor jugada; mayor = a veces elige otra con
        probabilidad que decrece con lo peor que es (exp(-diferencia / temperatura)). Sirve para los
        niveles de dificultad bajos."""
        self.tl = time_limit
        self.maxd = max_depth
        self.mejoras = MEJORAS if mejoras is None else mejoras
        self.temperatura = temperatura
        self.tt = {}
        self.killers = {}
        self.historia = {}
        self.nodes = 0
        self.vistas = set()   # posiciones ya ocurridas en la partida desde la última jugada irreversible
        self.camino = set()   # posiciones de la línea que se está analizando
        self.contra = {}      # contrajugadas: jugada del rival -> jugada que la refutó
        self.linea = [None] * 256  # jugada hecha en cada ply de la línea actual
        self.raiz = None
        self.interrumpir = None  # función que, si devuelve True, detiene la búsqueda (pensar en el turno rival)
        self.stop = False

    def timeout(self):
        if self.nodes & 255 == 0:
            if self.tl and time.time() - self.t0 > self.tl:
                self.stop = True
            elif self.interrumpir is not None and self.interrumpir():
                self.stop = True
        return self.stop

    def qs(self, st, alpha, beta, qd=0):
        self.nodes += 1
        if self.timeout():
            return 0
        stand = evaluate(st)
        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand
        if qd > 6:
            return stand
        me = st.turn
        caps = [(mv, n) for mv, n in gen(st, True) if is_capture(st, mv)]
        caps.sort(key=lambda x: -mvv(st, x[0]))
        usar_see = OPCIONES['see']
        for mv, n in caps:
            if self.mejoras and mv[0] not in ('pr', 'cv', 'gp') and stand + mvv(st, mv) / 10 + 2 < alpha:
                continue  # ni ganando la pieza capturada se alcanza alpha
            if usar_see and captura_mala(st, mv):
                continue  # pierde material en el intercambio
            if n is None:
                n = apply(st, mv)
                if in_check(n, me):
                    continue
            sc = -self.qs(n, -beta, -alpha, qd + 1)
            if self.stop:
                return 0
            if sc >= beta:
                return sc
            if sc > alpha:
                alpha = sc
        return alpha

    def ab(self, st, d, alpha, beta, ply):
        # Una posición que ya ocurrió (en la partida o en la línea analizada) se valora como una
        # repetición: derrota para quien va abajo en puntos (7.6), así que nunca la busca (por
        # ejemplo, con jaques perpetuos); y algo peor que tablas para quien va arriba, que prefiere
        # seguir jugando para dar mate. Así la partida casi nunca termina por triple repetición.
        h = zhash(st)
        if h in self.vistas or h in self.camino:
            raiz = self.raiz
            v = -PERDER_POR_PUNTOS if st.pts[raiz] < st.pts[1 - raiz] else -DESPRECIO
            return v if st.turn == raiz else -v
        self.camino.add(h)
        try:
            return self._ab(st, d, alpha, beta, ply, h)
        finally:
            self.camino.discard(h)

    def _ab(self, st, d, alpha, beta, ply, h):
        if d <= 0:
            return self.qs(st, alpha, beta)
        self.nodes += 1
        if self.timeout():
            return 0
        if OPCIONES['finales'] and ply > 0:
            v = consultar_final(st, ply)
            if v is not None:
                return v
        ent = self.tt.get(h)
        ttmove = None
        if ent:
            ed, esc, flag, ttmove = ent
            if ed >= d:
                if flag == 0 or (flag == 1 and esc >= beta) or (flag == -1 and esc <= alpha):
                    return esc
        me = st.turn
        if self.mejoras:
            return self._ab_mejorada(st, d, alpha, beta, ply, h, ttmove)
        moves = gen(st)
        kill = self.killers.get(ply, [])

        def order(x):
            mv = x[0]
            if ttmove is not None and mv == ttmove:
                return -1e9
            sc = -mvv(st, mv)
            if mv in kill:
                sc -= 5
            return sc
        moves.sort(key=order)
        a0 = alpha
        best, bmv = -MATE * 2, None
        legal_n = 0
        for mv, n in moves:
            if n is None:
                n = apply(st, mv)
                if in_check(n, me):
                    continue
            legal_n += 1
            if d >= 3 and legal_n > 4 and not is_capture(st, mv) and mv not in kill and not in_check(n, 1 - me):
                sc = -self.ab(n, d - 2, -alpha - 0.01, -alpha, ply + 1)
                if sc > alpha and not self.stop:
                    sc = -self.ab(n, d - 1, -beta, -alpha, ply + 1)
            else:
                sc = -self.ab(n, d - 1, -beta, -alpha, ply + 1)
            if self.stop:
                return 0
            if sc > best:
                best, bmv = sc, mv
            if sc > alpha:
                alpha = sc
            if alpha >= beta:
                if not is_capture(st, mv):
                    kl = self.killers.setdefault(ply, [])
                    if mv not in kl:
                        kl.insert(0, mv); del kl[2:]
                break
        if legal_n == 0:
            return -MATE + ply if in_check(st, me) else 0
        flag = 0 if a0 < best < beta else (1 if best >= beta else -1)
        self.tt[h] = (d, best, flag, bmv)
        return best

    def _ab_mejorada(self, st, d, alpha, beta, ply, h, ttmove):
        me = st.turn
        en_jaque = in_check(st, me)
        op = OPCIONES
        estatica = None
        if ply > 0 and not en_jaque and d <= 3 and abs(beta) < MATE / 2 and abs(alpha) < MATE / 2 and \
                (op['futilidad_inversa'] or op['razoring'] or op['futilidad']):
            estatica = evaluate(st)
            if op['futilidad_inversa'] and estatica - MARGEN_FUT_INVERSA * d >= beta:
                return estatica - MARGEN_FUT_INVERSA * d
            if op['razoring'] and d <= 2 and estatica + MARGEN_RAZORING * d < alpha:
                v = self.qs(st, alpha, beta)
                if self.stop:
                    return 0
                if v <= alpha:
                    return v
        # movimiento nulo: si aun pasando el turno la posición supera beta, no hace falta analizarla
        if d >= 3 and ply > 0 and not en_jaque and beta < MATE / 2 and tiene_piezas(st, me):
            n = st.copy()
            n.turn, n.ep = 1 - me, None
            self.linea[ply] = None
            sc = -self.ab(n, d - 3, -beta, -beta + 0.01, ply + 1)
            if self.stop:
                return 0
            if sc >= beta:
                return beta
        moves = gen(st)
        kill = self.killers.get(ply, [])
        historia = self.historia
        previa = self.linea[ply - 1] if ply > 0 else None
        clave_previa = (previa[1], previa[2] if len(previa) > 2 else -1) if previa is not None else None
        contra = self.contra.get(clave_previa) if op['contrajugada'] and clave_previa else None
        usar_see = op['see']

        def order(x):
            mv = x[0]
            if ttmove is not None and mv == ttmove:
                return -1e9
            m = mvv(st, mv)
            if m:
                if usar_see and captura_mala(st, mv):
                    return -100 - m / 1000  # capturas perdedoras: después de las asesinas
                return -1000 - m
            if mv in kill:
                return -500
            if contra is not None and mv == contra:
                return -450
            return -min(historia.get((mv[1], mv[2] if len(mv) > 2 else -1), 0), 400)
        moves.sort(key=order)
        podar = ply > 0 and not en_jaque and abs(alpha) < MAT_PODA
        futil = podar and op['futilidad'] and d <= 2 and estatica is not None and \
            estatica + MARGEN_FUTILIDAD * d <= alpha
        limite_tardias = (6 + 4 * d * d) if (podar and op['poda_tardia'] and d <= 3) else 10 ** 9
        tranquilas = 0
        a0 = alpha
        best, bmv = -MATE * 2, None
        legal_n = 0
        for mv, n in moves:
            if n is None:
                n = apply(st, mv)
                if in_check(n, me):
                    continue
            legal_n += 1
            da_jaque = in_check(n, 1 - me)
            tactica = is_capture(st, mv)
            if not tactica and not da_jaque and legal_n > 1:
                tranquilas += 1
                if futil or tranquilas > limite_tardias:  # futilidad / poda de jugadas tardías
                    # la futilidad garantiza estática + margen <= alfa: esa cota se puede usar; la poda de
                    # jugadas tardías no garantiza nada, así que no debe cambiar el mejor valor
                    if futil and estatica + MARGEN_FUTILIDAD * d > best:
                        best = estatica + MARGEN_FUTILIDAD * d
                    continue
            nd = d - 1 + (1 if da_jaque and ply < 2 * self.maxd else 0)  # extensión de jaques
            self.linea[ply] = mv
            if legal_n == 1:
                sc = -self.ab(n, nd, -beta, -alpha, ply + 1)
            else:
                reduccion = 1 if (d >= 3 and legal_n > 4 and not tactica and not da_jaque and
                                  not en_jaque and mv not in kill) else 0
                if reduccion and op['lmr_log']:
                    reduccion = max(1, min(REDUCCION[min(d, 63)][min(legal_n, 255)], nd - 1))
                sc = -self.ab(n, nd - reduccion, -alpha - 0.01, -alpha, ply + 1)  # ventana nula (PVS)
                if sc > alpha and not self.stop and (reduccion or sc < beta):
                    sc = -self.ab(n, nd, -beta, -alpha, ply + 1)
            if self.stop:
                return 0
            if sc > best:
                best, bmv = sc, mv
            if sc > alpha:
                alpha = sc
            if alpha >= beta:
                if not tactica:
                    kl = self.killers.setdefault(ply, [])
                    if mv not in kl:
                        kl.insert(0, mv); del kl[2:]
                    clave = (mv[1], mv[2] if len(mv) > 2 else -1)
                    historia[clave] = historia.get(clave, 0) + d * d
                    if clave_previa is not None and op['contrajugada']:
                        self.contra[clave_previa] = mv
                break
        if legal_n == 0:
            return -MATE + ply if en_jaque else 0
        flag = 0 if a0 < best < beta else (1 if best >= beta else -1)
        if bmv is None and flag != -1:  # todas podadas: el valor es solo una cota superior
            flag = -1
        self.tt[h] = (d, best, flag, bmv)
        return best

    def choose(self, st, legal_moves, rng, noise=0.05, vistas=()):
        """vistas: hashes (zhash) de las posiciones de la partida desde la última jugada irreversible,
        incluida la actual."""
        self.vistas = set(vistas)
        self.camino = set()
        if OPCIONES['tt_persistente'] and self.raiz == st.turn and len(self.tt) < LIMITE_TT:
            # se conserva lo analizado en jugadas anteriores (los valores de repetición dependen del
            # bando de la raíz, así que solo si es el mismo); el historial pierde peso poco a poco
            self.historia = {k: v // 2 for k, v in self.historia.items() if v > 1}
        else:
            self.tt.clear()  # sus valores no conocían las posiciones que ya se repitieron
            self.historia = {}
            self.contra = {}
        self.raiz = st.turn
        self.t0 = time.time()
        self.stop = False
        self.nodes = 0
        me = st.turn
        best_mv, reached = legal_moves[0], 0
        self.puntaje = None  # evaluación de la jugada elegida, desde el bando que mueve
        ordered = sorted(legal_moves, key=lambda x: -mvv(st, x[0]))
        previo = None
        for d in range(1, self.maxd + 1):
            ventana = 0.5 if (OPCIONES['aspiracion'] and d >= 3 and previo is not None and
                              abs(previo) < MATE / 2) else None
            while True:
                piso = previo - ventana if ventana else -MATE * 2
                techo = previo + ventana if ventana else MATE * 2
                scores = []
                alpha = piso
                fallo_alto = False
                for mv, n in ordered:
                    self.linea[0] = mv
                    sc = -self.ab(n, d - 1, -techo, -alpha + noise, 1)
                    if self.stop:
                        break
                    if sc >= techo:
                        fallo_alto = True
                        break
                    scores.append((sc + rng.random() * noise, mv, n))
                    if sc > alpha:
                        alpha = sc
                if self.stop or not ventana:
                    break
                if fallo_alto or not scores or max(x[0] for x in scores) <= piso + noise:
                    ventana = None  # fuera de la ventana: se repite la iteración con ventana completa
                    continue
                break
            if self.stop or not scores:
                break
            scores.sort(key=lambda x: -x[0])
            best_mv = (scores[0][1], scores[0][2])
            reached = d
            self.puntaje = previo = scores[0][0]
            ordered = [(m, n) for _, m, n in scores]
            if scores[0][0] > MATE / 2:
                break
        if self.temperatura > 0 and reached and len(scores) > 1:
            # niveles bajos: a veces otra jugada, con probabilidad exp(-(mejor - puntaje) / temperatura).
            # La búsqueda de arriba solo da exacta la puntuación de la mejor jugada (las demás son cotas
            # que se quedan cerca de ella aunque pierdan material), así que se recalculan con ventana completa.
            exactas = puntuaciones_exactas(self, scores, reached)
            if exactas is None:
                return best_mv, reached
            scores = exactas
            mejor = scores[0][0]
            pesos = [math.exp(max(-50.0, (sc - mejor) / self.temperatura)) for sc, _, _ in scores]
            r = rng.random() * sum(pesos)
            for (sc, mv, n), w in zip(scores, pesos):
                r -= w
                if r <= 0:
                    best_mv, self.puntaje = (mv, n), sc
                    break
        return best_mv, reached
