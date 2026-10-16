import math, random, time
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
VALOR_MEDIO = {'P': (1, 2), 'G': (2, 3.5), 'B': (3, 6.5), 'N': (3.5, 6), 'CE': (5, 10.5), 'R': (5, 7.5),
               'CA': (5, 6), 'CH': (6, 8.5), 'Q': (9, 10.5), 'K': (0, 0)}
# Final ajustado con 33 duelos de final con peones (1,980 partidas, validar_valores.py lote-final,
# series de ajuste y de validación): con peones en juego las piezas con saltos valen más de lo que
# indican los finales de Rey y pieza contra Rey, el Guardián gana mucho valor y la Catapulta
# promocionada lo pierde. Precisión aproximada: ±0.3.
VALOR_FINAL = {'P': (1, 3), 'G': (3.5, 5.5), 'B': (3, 9), 'N': (4.5, 6), 'CE': (6, 8), 'R': (5, 9),
               'CA': (6.5, 6.5), 'CH': (8.5, 8.5), 'Q': (9.5, 11.5), 'K': (0, 0)}
VERSION_IA = 'v5'  # v1: valores fijos; v2: dinámicos con el primer final; v3: final revisado; v4: final ajustado;
# v5: términos desarrollo, derechos y movilidad encendidos (octubre de 2026)
SIN_FASE = ('P', 'G', 'K')  # piezas que no cuentan para calcular la fase
FASE_INICIAL = sum(VALOR_MEDIO[p.t][0] for p in initial().b if p and p.t not in SIN_FASE)


# tablas para la evaluación: bonos de posición por casilla y valores por tipo de pieza
BONO_AVANCE = [[0.03 * ((sq // N) if c == 0 else (N - 1 - sq // N)) for sq in range(N * N)] for c in (0, 1)]
BONO_CENTRO = [0.02 * (5 - max(abs(sq % N - 5), abs(sq // N - 5))) for sq in range(N * N)]
VALORES_IA = {t: ((VALOR_MEDIO[t][0], VALOR_FINAL[t][0]), (VALOR_MEDIO[t][1], VALOR_FINAL[t][1])) for t in VALOR_MEDIO}
EN_FASE = {t: t not in SIN_FASE for t in VALOR_MEDIO}


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
PESOS = {'pasados': 0.0, 'escudo': 0.0, 'movilidad': 1.0, 'rey': 0.0, 'desarrollo': 1.0, 'atacadas': 0.0,
         'derechos': 1.0}
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
            pos = BONO_CENTRO[sq]
        else:
            vm, vf = VALORES_IA[t][0]
            sin_promocionar[c][t] = True
            pos = BONO_AVANCE[c][sq] if (t == 'P' or t == 'G') else BONO_CENTRO[sq]
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
            or PESOS['atacadas'] or PESOS['derechos']:
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


def tiene_piezas(st, color):
    """¿Tiene el bando alguna pieza aparte del Rey, peones y Guardianes? (el movimiento nulo no es
    seguro sin piezas: en esos finales pasar el turno puede ser lo peor, «zugzwang»)."""
    for p in st.b:
        if p is not None and p.c == color and p.t not in ('K', 'P', 'G'):
            return True
    return False


def puntuaciones_exactas(buscador, scores, d):
    """[(puntuación exacta, jugada, posición)] de las jugadas de la raíz a profundidad d, de mejor a peor;
    None si se acabó el tiempo. Sirve también para generico.Buscador (misma interfaz)."""
    out = []
    for _, mv, n in scores:
        sc = -buscador.ab(n, d - 1, -MATE * 2, MATE * 2, 1)
        if buscador.stop:
            return None
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

    def timeout(self):
        if self.tl and self.nodes & 255 == 0 and time.time() - self.t0 > self.tl:
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
        for mv, n in caps:
            if self.mejoras and mv[0] not in ('pr', 'cv', 'gp') and stand + mvv(st, mv) / 10 + 2 < alpha:
                continue  # ni ganando la pieza capturada se alcanza alpha
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
        # movimiento nulo: si aun pasando el turno la posición supera beta, no hace falta analizarla
        if d >= 3 and ply > 0 and not en_jaque and beta < MATE / 2 and tiene_piezas(st, me):
            n = st.copy()
            n.turn, n.ep = 1 - me, None
            sc = -self.ab(n, d - 3, -beta, -beta + 0.01, ply + 1)
            if self.stop:
                return 0
            if sc >= beta:
                return beta
        moves = gen(st)
        kill = self.killers.get(ply, [])
        historia = self.historia

        def order(x):
            mv = x[0]
            if ttmove is not None and mv == ttmove:
                return -1e9
            m = mvv(st, mv)
            if m:
                return -1000 - m
            if mv in kill:
                return -500
            return -min(historia.get((mv[1], mv[2] if len(mv) > 2 else -1), 0), 400)
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
            da_jaque = in_check(n, 1 - me)
            tactica = is_capture(st, mv)
            nd = d - 1 + (1 if da_jaque and ply < 2 * self.maxd else 0)  # extensión de jaques
            if legal_n == 1:
                sc = -self.ab(n, nd, -beta, -alpha, ply + 1)
            else:
                reduccion = 1 if (d >= 3 and legal_n > 4 and not tactica and not da_jaque and
                                  not en_jaque and mv not in kill) else 0
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
                break
        if legal_n == 0:
            return -MATE + ply if en_jaque else 0
        flag = 0 if a0 < best < beta else (1 if best >= beta else -1)
        self.tt[h] = (d, best, flag, bmv)
        return best

    def choose(self, st, legal_moves, rng, noise=0.05, vistas=()):
        """vistas: hashes (zhash) de las posiciones de la partida desde la última jugada irreversible,
        incluida la actual."""
        self.vistas = set(vistas)
        self.camino = set()
        self.raiz = st.turn
        self.tt.clear()  # sus valores no conocían las posiciones que ya se repitieron
        self.historia = {}
        self.t0 = time.time()
        self.stop = False
        self.nodes = 0
        me = st.turn
        best_mv, reached = legal_moves[0], 0
        self.puntaje = None  # evaluación de la jugada elegida, desde el bando que mueve
        ordered = sorted(legal_moves, key=lambda x: -mvv(st, x[0]))
        for d in range(1, self.maxd + 1):
            scores = []
            alpha = -MATE * 2
            for mv, n in ordered:
                sc = -self.ab(n, d - 1, -MATE * 2, -alpha + noise, 1)
                if self.stop:
                    break
                scores.append((sc + rng.random() * noise, mv, n))
                if sc > alpha:
                    alpha = sc
            if self.stop:
                break
            scores.sort(key=lambda x: -x[0])
            best_mv = (scores[0][1], scores[0][2])
            reached = d
            self.puntaje = scores[0][0]
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
