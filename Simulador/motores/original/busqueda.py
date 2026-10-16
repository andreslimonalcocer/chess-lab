import random, time
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
VERSION_IA = 'v4'  # v1: valores fijos; v2: dinámicos con el primer final; v3: final revisado; v4: final ajustado
SIN_FASE = ('P', 'G', 'K')  # piezas que no cuentan para calcular la fase
FASE_INICIAL = sum(VALOR_MEDIO[p.t][0] for p in initial().b if p and p.t not in SIN_FASE)


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


def zhash(st):
    h = ZTURN if st.turn else 0
    b = st.b
    for sq in range(N * N):
        p = b[sq]
        if p is not None:
            h ^= ZK[(sq, p.t, p.c, p.pr)]
    if st.ep:
        h ^= st.ep[1] * 7919
    return h


def evaluate(st):
    """Evaluación desde el punto de vista del bando que mueve."""
    me = st.turn
    medio = final = s = 0.0  # material en el medio juego, en el final y términos de posición
    material_fase = 0.0
    unprom = (set(), set())
    mat = [0, 0]
    b = st.b
    for sq in range(N * N):
        p = b[sq]
        if p is None or p.t == 'K':
            continue
        i = 1 if p.pr else 0
        vm, vf = VALOR_MEDIO[p.t][i], VALOR_FINAL[p.t][i]
        mat[p.c] += vm
        if p.t not in SIN_FASE:
            material_fase += vm
        if not p.pr:
            unprom[p.c].add(p.t)
        if p.t in ('P', 'G') and not p.pr:
            pos = 0.03 * ((sq // N) if p.c == 0 else (N - 1 - sq // N))
        else:
            pos = 0.02 * (5 - max(abs(sq % N - 5), abs(sq // N - 5)))
        if p.c == me:
            medio += vm; final += vf; s += pos
        else:
            medio -= vm; final -= vf; s -= pos
    f = min(1.0, material_fase / FASE_INICIAL)
    s += f * medio + (1 - f) * final
    for color in (0, 1):
        ct = st.capT[color]
        if not ct:
            continue
        bonus = 0.0
        for t in unprom[color]:
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


def gen(st):
    out = [(mv, None) for mv in pseudo(st)]
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


class Searcher:
    def __init__(self, time_limit=1.0, max_depth=5):
        self.tl = time_limit
        self.maxd = max_depth
        self.tt = {}
        self.killers = {}
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
        caps = [(mv, n) for mv, n in gen(st) if is_capture(st, mv)]
        caps.sort(key=lambda x: -mvv(st, x[0]))
        for mv, n in caps:
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

    def choose(self, st, legal_moves, rng, noise=0.05, vistas=()):
        """vistas: hashes (zhash) de las posiciones de la partida desde la última jugada irreversible,
        incluida la actual."""
        self.vistas = set(vistas)
        self.camino = set()
        self.raiz = st.turn
        self.tt.clear()  # sus valores no conocían las posiciones que ya se repitieron
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
        return best_mv, reached
