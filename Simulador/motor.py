"""Motor de reglas del Ajedrez 11x11 (reglamento oficial)."""
N = 11
ALL8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
ORTH = ALL8[:4]
DIAG = ALL8[4:]
KN_STD = [(1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)]
KN_EXT = [(1, 3), (3, 1), (-1, 3), (-3, 1), (1, -3), (3, -1), (-1, -3), (-3, -1)]
KN_PROM = [(2, 3), (3, 2), (-2, 3), (-3, 2), (2, -3), (3, -2), (-2, -3), (-3, -2)]
RAD2 = [(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3) if (dx, dy) != (0, 0)]
RING = [d for d in RAD2 if max(abs(d[0]), abs(d[1])) == 2]
RING_ST = [d for d in RING if d[0] == 0 or d[1] == 0 or abs(d[0]) == abs(d[1])]
RING_KN = [d for d in RING if d not in RING_ST]

# Apéndice A: valores (base, promocionada) para el desempate por puntos (7.6). Ajustados en octubre
# de 2026 con duelos simulados (validar_valores.py) y finales exactos (finales.py).
VAL = {'P': (1, 2), 'G': (2, 3.5), 'B': (3, 6.5), 'N': (3.5, 6), 'CE': (5, 9.5), 'R': (5, 8), 'CA': (5, 6),
       'CH': (6, 8), 'Q': (9, 10.5), 'K': (0, 0)}
NEED = {'Q': 1, 'CA': 1, 'CH': 1, 'CE': 1, 'R': 2, 'B': 2, 'N': 2}
PEONES_POR_GUARDIAN = 4       # 5.4 (a): peones adversarios capturados por cada peón convertido en Guardián
GUARDIANES_POR_PROMOCION = 5  # 5.4 (b): Guardianes adversarios capturados por cada Guardián promocionado


def on(c, r):
    return 0 <= c < N and 0 <= r < N


# ------------------------------------------------------------------ tablas precalculadas
# Para cada casilla: vecinos, rayos y saltos ya calculados (en el mismo orden que ALL8, KN_STD, etc.),
# para no repetir las comprobaciones de borde en cada jugada. No cambian el orden de las jugadas.
NN = N * N


def _destinos(sq, offs):
    c0, r0 = sq % N, sq // N
    return [(r0 + dr) * N + c0 + dc for dc, dr in offs if on(c0 + dc, r0 + dr)]


def _rayo(sq, dc, dr, largo=N):
    c, r, out = sq % N, sq // N, []
    for _ in range(largo):
        c += dc; r += dr
        if not on(c, r):
            break
        out.append(r * N + c)
    return out


RAYOS = [[_rayo(sq, dc, dr) for dc, dr in ALL8] for sq in range(NN)]          # 0-3 rectas, 4-7 diagonales
SALTOS_REY = [_destinos(sq, ALL8) for sq in range(NN)]
SALTOS_C = [_destinos(sq, KN_STD) for sq in range(NN)]                         # salto tradicional
SALTOS_CX = [_destinos(sq, KN_EXT) for sq in range(NN)]                        # salto largo
SALTOS_CP = [_destinos(sq, KN_PROM) for sq in range(NN)]                       # saltos del Caballo promocionado
SALTOS_N = [SALTOS_C[sq] + SALTOS_CX[sq] for sq in range(NN)]
SALTOS_NP = [SALTOS_N[sq] + SALTOS_CP[sq] for sq in range(NN)]
DIAGONALES = [_destinos(sq, DIAG) for sq in range(NN)]
ANILLO = [_destinos(sq, RING) for sq in range(NN)]
# desplazamientos de 1 a 3 casillas (Torre y Alfil promocionados): por dirección, (destino, intermedias)
TRES_DIAG = [[[(r[k], r[:k]) for k in range(len(r[:3]))] for r in RAYOS[sq][4:]] for sq in range(NN)]
TRES_ORTO = [[[(r[k], r[:k]) for k in range(len(r[:3]))] for r in RAYOS[sq][:4]] for sq in range(NN)]
# vecinos para el ataque: (casilla, es diagonal, casilla siguiente en la misma dirección o -1)
VECINOS = [[(r[0], d >= 4, r[1] if len(r) > 1 else -1) for d, r in enumerate(RAYOS[sq]) if r]
           for sq in range(NN)]


def fwd(color):
    return 1 if color == 0 else -1


def last_row(color):
    return N - 1 if color == 0 else 0


def start_row(color):
    return 1 if color == 0 else N - 2


def _peon(sq, color):
    """(una adelante, dos adelante, [(captura, casilla de al lado)]) para un peón o Guardián."""
    c0, r0, f = sq % N, sq // N, fwd(color)
    uno = (r0 + f) * N + c0 if on(c0, r0 + f) else -1
    dos = (r0 + 2 * f) * N + c0 if on(c0, r0 + 2 * f) else -1
    capt = [((r0 + f) * N + c0 + dc, r0 * N + c0 + dc) for dc in (-1, 1) if on(c0 + dc, r0 + f)]
    return uno, dos, capt


PEON = [[_peon(sq, c) for sq in range(NN)] for c in (0, 1)]
# Guardián: avance (hasta 3 casillas), laterales y diagonales con su dirección vertical
GUARDIAN_AVANCE = [[_rayo(sq, 0, fwd(c), 3) for sq in range(NN)] for c in (0, 1)]
GUARDIAN_LADOS = [_destinos(sq, ((-1, 0), (1, 0))) for sq in range(NN)]
GUARDIAN_DIAG = [[((sq // N + dr) * N + sq % N + dc, dr, sq // N * N + sq % N + dc) for dc, dr in DIAG
                  if on(sq % N + dc, sq // N + dr)] for sq in range(NN)]
# Catapulta: casillas a distancia 1 o 2 (en el orden de RAD2) con (destino, recto a dos, a distancia 2, intermedia)
CATAPULTA = [[((sq // N + dr) * N + sq % N + dc, (dc, dr) in RING_ST, (dc, dr) in RING,
               (sq // N + dr // 2) * N + sq % N + dc // 2) for dc, dr in RAD2 if on(sq % N + dc, sq // N + dr)]
             for sq in range(NN)]

# casillas desde las que un peón del bando 'by' ataca la casilla sq
PEON_ATACA = [[[(sq // N - fwd(by)) * N + sq % N + dc for dc in (-1, 1)
                if on(sq % N + dc, sq // N - fwd(by))] for sq in range(NN)] for by in (0, 1)]


class Pc:
    __slots__ = ('t', 'c', 'pr', 'moved', 'dbl', 'init', 'pid', 'ls')

    def __init__(s, t, c, pr=False, moved=False, dbl=False, init=False, pid=0, ls=None):
        s.t, s.c, s.pr, s.moved, s.dbl, s.init, s.pid, s.ls = t, c, pr, moved, dbl, init, pid, ls

    def cp(s):
        return Pc(s.t, s.c, s.pr, s.moved, s.dbl, s.init, s.pid, s.ls)

    def key(s):
        return (s.t, s.c, s.pr, s.moved, s.dbl, s.init)


def val(p):
    return VAL[p.t][1 if p.pr else 0]


class St:
    __slots__ = ('b', 'turn', 'ep', 'capP', 'capG', 'capT', 'conv', 'gprom', 'tprom', 'pts', 'clock', 'kpos')

    def copy(s):
        n = St.__new__(St)
        n.b = s.b[:]
        n.turn = s.turn
        n.ep = s.ep
        n.capP = s.capP[:]
        n.capG = s.capG[:]
        n.capT = [dict(s.capT[0]), dict(s.capT[1])]
        n.conv = s.conv[:]
        n.gprom = s.gprom[:]
        n.tprom = [set(s.tprom[0]), set(s.tprom[1])]
        n.pts = s.pts[:]
        n.clock = s.clock
        n.kpos = s.kpos[:]
        return n


def initial():
    s = St.__new__(St)
    b = [None] * (N * N)
    back = ['R', 'N', 'B', 'CA', 'Q', 'K', 'CE', 'CH', 'N', 'B', 'R']
    pid = 1
    for color in (0, 1):
        r0 = 0 if color == 0 else N - 1
        r1 = 1 if color == 0 else N - 2
        for c, t in enumerate(back):
            b[r0 * N + c] = Pc(t, color, pid=pid); pid += 1
        for c in range(N):
            if c in (4, 5, 6):
                b[r1 * N + c] = Pc('G', color, init=True, dbl=True, pid=pid)
            else:
                b[r1 * N + c] = Pc('P', color, dbl=True, pid=pid)
            pid += 1
    s.b = b
    s.turn = 0
    s.ep = None
    s.capP = [0, 0]; s.capG = [0, 0]
    s.capT = [{}, {}]
    s.conv = [0, 0]; s.gprom = [0, 0]
    s.tprom = [set(), set()]
    s.pts = [0.0, 0.0]
    s.clock = 0
    s.kpos = [5, (N - 1) * N + 5]
    return s


def empty_state():
    s = initial()
    s.b = [None] * (N * N)
    s.kpos = [None, None]
    return s


def put(s, sq, t, color, **kw):
    p = Pc(t, color, **kw)
    s.b[sq] = p
    if t == 'K':
        s.kpos[color] = sq


def sqn(name):
    return (int(name[1:]) - 1) * N + 'abcdefghijk'.index(name[0])


def name(sq):
    return 'abcdefghijk'[sq % N] + str(sq // N + 1)


# ------------------------------------------------------------------ bloqueo de saltos
def jump_blocked(b, sq, mover):
    """True si la casilla está en diagonal a un Guardián (no promocionado) adversario de 'mover'."""
    c0, r0 = sq % N, sq // N
    for dc, dr in DIAG:
        c, r = c0 + dc, r0 + dr
        if 0 <= c < N and 0 <= r < N:
            p = b[r * N + c]
            if p is not None and p.c != mover and p.t == 'G' and not p.pr:
                return True
    return False


# ------------------------------------------------------------------ ataques
def attackers(b, sq, by, first=False):
    c0, r0 = sq % N, sq // N
    out = []

    def add(i):
        out.append(i)
        return first

    f = fwd(by)
    for dc in (-1, 1):
        c, r = c0 + dc, r0 - f
        if on(c, r):
            p = b[r * N + c]
            if p and p.c == by and p.t == 'P' and not p.pr and add(r * N + c):
                return out
    for dc, dr in ALL8:
        c, r = c0 + dc, r0 + dr
        if on(c, r):
            p = b[r * N + c]
            if p and p.c == by:
                if p.t == 'K' or (p.t in ('P', 'G') and p.pr) or (p.t == 'G' and not p.pr and dc != 0 and dr != 0):
                    if add(r * N + c):
                        return out
            c2, r2 = c0 + 2 * dc, r0 + 2 * dr
            if on(c2, r2) and b[r * N + c] is None:
                p2 = b[r2 * N + c2]
                if p2 and p2.c == by and p2.t == 'G' and p2.pr and add(r2 * N + c2):
                    return out
    jb = jump_blocked(b, sq, by)
    for dc, dr in ([] if jb else KN_STD):
        c, r = c0 + dc, r0 + dr
        if on(c, r):
            p = b[r * N + c]
            if p and p.c == by and (p.t in ('N', 'CA', 'CH') or (p.t == 'Q' and p.pr)) and add(r * N + c):
                return out
    for dc, dr in ([] if jb else KN_EXT):
        c, r = c0 + dc, r0 + dr
        if on(c, r):
            p = b[r * N + c]
            if p and p.c == by and p.t == 'N' and add(r * N + c):
                return out
    for dc, dr in ([] if jb else KN_PROM):
        c, r = c0 + dc, r0 + dr
        if on(c, r):
            p = b[r * N + c]
            if p and p.c == by and p.t == 'N' and p.pr and add(r * N + c):
                return out
    for dirs, sl, lim_t in ((ORTH, ('R', 'Q'), 'CH'), (DIAG, ('B', 'Q'), 'CA')):
        for dc, dr in dirs:
            c, r, k = c0, r0, 0
            while True:
                c += dc; r += dr; k += 1
                if not on(c, r):
                    break
                p = b[r * N + c]
                if p is None:
                    continue
                if p.c == by and (p.t in sl or (p.t == lim_t and (p.pr or k <= 5))):
                    if add(r * N + c):
                        return out
                break
    for dirs, t in ((DIAG, 'R'), (ORTH, 'B')):
        for dc, dr in dirs:
            for k in (1, 2, 3):
                c, r = c0 + dc * k, r0 + dr * k
                if not on(c, r):
                    break
                p = b[r * N + c]
                if p and p.c == by and p.t == t and p.pr:
                    if jb and any(b[(r0 + dr * j) * N + c0 + dc * j] is not None for j in range(1, k)):
                        continue
                    if add(r * N + c):
                        return out
    for dc, dr in ([] if jb else RING):
        c, r = c0 + dc, r0 + dr
        if on(c, r):
            p = b[r * N + c]
            if p and p.c == by and p.t == 'CE' and add(r * N + c):
                return out
    return out


def attacked(b, sq, by):
    """¿Ataca el bando 'by' la casilla sq? Equivale a bool(attackers(b, sq, by)), con tablas."""
    for s in PEON_ATACA[by][sq]:
        p = b[s]
        if p is not None and p.c == by and p.t == 'P' and not p.pr:
            return True
    for s, diag, s2 in VECINOS[sq]:
        p = b[s]
        if p is not None:
            if p.c == by:
                t = p.t
                if t == 'K' or (p.pr and (t == 'P' or t == 'G')) or (t == 'G' and diag and not p.pr):
                    return True
        elif s2 >= 0:
            p2 = b[s2]
            if p2 is not None and p2.c == by and p2.t == 'G' and p2.pr:
                return True
    bloqueada = False  # en diagonal a un Guardián del bando atacado: no se puede llegar saltando
    for s in DIAGONALES[sq]:
        p = b[s]
        if p is not None and p.c != by and p.t == 'G' and not p.pr:
            bloqueada = True
            break
    if not bloqueada:
        for s in SALTOS_C[sq]:
            p = b[s]
            if p is not None and p.c == by and (p.t == 'N' or p.t == 'CA' or p.t == 'CH' or (p.t == 'Q' and p.pr)):
                return True
        for s in SALTOS_CX[sq]:
            p = b[s]
            if p is not None and p.c == by and p.t == 'N':
                return True
        for s in SALTOS_CP[sq]:
            p = b[s]
            if p is not None and p.c == by and p.t == 'N' and p.pr:
                return True
    rayos = RAYOS[sq]
    for d in range(8):
        k = 0
        for s in rayos[d]:
            k += 1
            p = b[s]
            if p is None:
                continue
            if p.c == by:
                t = p.t
                if d < 4:
                    if t == 'R' or t == 'Q' or (t == 'CH' and (p.pr or k <= 5)):
                        return True
                elif t == 'B' or t == 'Q' or (t == 'CA' and (p.pr or k <= 5)):
                    return True
            break
    for tabla, t in ((TRES_DIAG, 'R'), (TRES_ORTO, 'B')):
        for pasos in tabla[sq]:
            for s, intermedias in pasos:
                p = b[s]
                if p is not None and p.c == by and p.t == t and p.pr:
                    if bloqueada and any(b[j] is not None for j in intermedias):
                        continue
                    return True
    if not bloqueada:
        for s in ANILLO[sq]:
            p = b[s]
            if p is not None and p.c == by and p.t == 'CE':
                return True
    return False


def in_check(s, color):
    return attacked(s.b, s.kpos[color], 1 - color)


def min_att(b, sq, by):
    a = attackers(b, sq, by)
    if not a:
        return None
    return min(50 if b[i].t == 'K' else val(b[i]) for i in a)


# ------------------------------------------------------------------ aplicar
def capture(s, sq, me):
    p = s.b[sq]
    s.b[sq] = None
    s.pts[me] += val(p)
    s.capT[me][p.t] = s.capT[me].get(p.t, 0) + 1
    if p.t == 'P':
        s.capP[me] += 1
    elif p.t == 'G':
        s.capG[me] += 1


def apply(st, mv):
    n = st.copy()
    me = st.turn
    b = n.b
    kind = mv[0]
    n.ep = None
    reset = False
    if kind == 'm':
        frm, to = mv[1], mv[2]
        p = b[frm].cp()
        if b[to] is not None:
            capture(n, to, me); reset = True
        b[frm] = None
        p.moved = True
        r_to, r_fr = to // N, frm // N
        if p.t == 'P' and not p.pr:
            reset = True
            if abs(r_to - r_fr) == 2:
                n.ep = (to, to - fwd(me) * N)
            p.dbl = False
            if r_to == last_row(me):
                p.pr = True
        elif p.t == 'G' and not p.pr:
            if to % N == frm % N and (r_to - r_fr) * fwd(me) > 0:
                reset = True
                if abs(r_to - r_fr) >= 2 and p.dbl and r_fr == start_row(me):
                    n.ep = (to, to - fwd(me) * N)
                p.dbl = False
            if r_to == last_row(me):
                p.pr = True; reset = True
        if p.t == 'K':
            n.kpos[me] = to
        b[to] = p
    elif kind == 'ep':
        frm, to, victim = mv[1], mv[2], mv[3]
        capture(n, victim, me)
        p = b[frm].cp(); p.moved = True; p.dbl = False
        b[frm] = None; b[to] = p; reset = True
    elif kind == 'cs':
        kf, kt, rf, rt = mv[1], mv[2], mv[3][0], mv[3][1]
        k = b[kf].cp(); k.moved = True
        r = b[rf].cp(); r.moved = True
        b[kf] = None; b[rf] = None; b[kt] = k; b[rt] = r
        n.kpos[me] = kt
    elif kind == 'push':
        frm, to = mv[1], mv[2]
        pawn = b[to].cp(); pawn.dbl = False; pawn.moved = True
        g = b[frm].cp(); g.moved = True
        b[to + fwd(me) * N] = pawn
        b[to] = g; b[frm] = None
        reset = True
    elif kind == 'swap':
        frm, to = mv[1], mv[2]
        g = b[frm].cp(); pw = b[to].cp()
        g.ls = (pw.pid, frm, to); g.moved = True
        b[frm] = pw; b[to] = g
    elif kind == 'ch':
        frm = mv[1]
        pos = frm
        for land, caps in mv[3]:
            for c in caps:
                capture(n, c, me)
            p = b[pos]; b[pos] = None; b[land] = p
            pos = land
        p = b[pos].cp(); p.moved = True; b[pos] = p
        reset = True
    elif kind == 'pr':
        p = b[mv[1]].cp(); p.pr = True; b[mv[1]] = p
        n.tprom[me].add(p.t); reset = True
    elif kind == 'cv':
        old = b[mv[1]]
        opening = old.dbl and mv[1] // N == start_row(me)
        b[mv[1]] = Pc('G', me, moved=True, dbl=opening, pid=old.pid)
        n.conv[me] += 1; reset = True
    elif kind == 'gp':
        p = b[mv[1]].cp(); p.pr = True; b[mv[1]] = p
        n.gprom[me] += 1; reset = True
    n.turn = 1 - me
    n.clock = 0 if reset else st.clock + 1
    return n


# ------------------------------------------------------------------ generación
def _saltos(b, sq, opp, destinos, blk, out, solo):
    for i in destinos:
        if blk is not None and i in blk:
            continue
        q = b[i]
        if q is None:
            if not solo:
                out.append(('m', sq, i))
        elif q.c == opp and q.t != 'K':
            out.append(('m', sq, i))


def _rayos(b, sq, opp, rayos, lim, out, solo):
    for rayo in rayos:
        for i in (rayo if lim is None else rayo[:lim]):
            q = b[i]
            if q is None:
                if not solo:
                    out.append(('m', sq, i))
                continue
            if q.c == opp and q.t != 'K':
                out.append(('m', sq, i))
            break


def _tres(b, sq, opp, tabla, blk, out, solo):
    """Desplazamiento de 1 a 3 casillas de la Torre o el Alfil promocionados; solo es salto si pasa
    por encima de alguna pieza (y entonces no puede caer en una casilla bloqueada por un Guardián)."""
    for pasos in tabla:
        for i, intermedias in pasos:
            if i in blk and any(b[j] is not None for j in intermedias):
                continue
            q = b[i]
            if q is None:
                if not solo:
                    out.append(('m', sq, i))
            elif q.c == opp and q.t != 'K':
                out.append(('m', sq, i))


def pseudo(st, solo_capturas=False):
    """Movimientos ordinarios (sin cadenas de la Catapulta promocionada). Con solo_capturas, solo las
    capturas y las promociones que cuestan turno, en el mismo orden (para la búsqueda de quietud)."""
    b = st.b
    me = st.turn
    opp = 1 - me
    out = []
    solo = solo_capturas
    chk = not solo and st.kpos[me] is not None and attacked(b, st.kpos[me], opp)
    blk = set()
    for i in range(NN):
        q = b[i]
        if q is not None and q.c == opp and q.t == 'G' and not q.pr:
            blk.update(DIAGONALES[i])
    for sq in range(NN):
        p = b[sq]
        if p is None or p.c != me:
            continue
        t = p.t
        if t == 'K':
            _saltos(b, sq, opp, SALTOS_REY[sq], None, out, solo)
            c0, r0 = sq % N, sq // N
            if not solo and not p.moved and not attacked(b, sq, opp):
                for rc, kc, rt in ((0, 1, 2), (N - 1, N - 2, N - 3)):
                    rs = r0 * N + rc
                    rk = b[rs]
                    if rk and rk.c == me and rk.t == 'R' and not rk.moved:
                        lo, hi = min(rc, c0), max(rc, c0)
                        if all(b[r0 * N + c] is None for c in range(lo + 1, hi)):
                            step = -1 if rc < c0 else 1
                            path = [r0 * N + c0 + step * k for k in range(1, 5)]
                            if all(not attacked(b, x, opp) for x in path):
                                out.append(('cs', sq, r0 * N + kc, (rs, r0 * N + rt)))
            continue
        if t == 'Q':
            _rayos(b, sq, opp, RAYOS[sq], None, out, solo)
            if p.pr:
                _saltos(b, sq, opp, SALTOS_C[sq], blk, out, solo)
            continue
        if t == 'R':
            _rayos(b, sq, opp, RAYOS[sq][:4], None, out, solo)
            if p.pr:
                _tres(b, sq, opp, TRES_DIAG[sq], blk, out, solo)
            continue
        if t == 'B':
            _rayos(b, sq, opp, RAYOS[sq][4:], None, out, solo)
            if p.pr:
                _tres(b, sq, opp, TRES_ORTO[sq], blk, out, solo)
            continue
        if t == 'N':
            _saltos(b, sq, opp, SALTOS_NP[sq] if p.pr else SALTOS_N[sq], blk, out, solo)
            continue
        if t == 'CA':
            _saltos(b, sq, opp, SALTOS_C[sq], blk, out, solo)
            _rayos(b, sq, opp, RAYOS[sq][4:], None if p.pr else 5, out, solo)
            continue
        if t == 'CH':
            _saltos(b, sq, opp, SALTOS_C[sq], blk, out, solo)
            _rayos(b, sq, opp, RAYOS[sq][:4], None if p.pr else 5, out, solo)
            continue
        if t == 'P':
            if p.pr:
                _saltos(b, sq, opp, SALTOS_REY[sq], None, out, solo)
                continue
            uno, dos, capt = PEON[me][sq]
            if not solo and uno >= 0 and b[uno] is None:
                out.append(('m', sq, uno))
                if p.dbl and sq // N == start_row(me) and dos >= 0 and b[dos] is None:
                    out.append(('m', sq, dos))
            for i, lado in capt:
                q = b[i]
                if q and q.c == opp and q.t != 'K':
                    out.append(('m', sq, i))
                elif st.ep and st.ep[1] == i and st.ep[0] == lado:
                    out.append(('ep', sq, i, st.ep[0]))
            continue
        if t == 'G':
            if p.pr:  # hasta dos casillas en línea recta; la intermedia debe estar vacía
                for rayo in RAYOS[sq]:
                    if not rayo:
                        continue
                    q = b[rayo[0]]
                    if q is None:
                        if not solo:
                            out.append(('m', sq, rayo[0]))
                        if len(rayo) > 1:
                            q2 = b[rayo[1]]
                            if q2 is None:
                                if not solo:
                                    out.append(('m', sq, rayo[1]))
                            elif q2.c == opp and q2.t != 'K':
                                out.append(('m', sq, rayo[1]))
                    elif q.c == opp and q.t != 'K':
                        out.append(('m', sq, rayo[0]))
                continue
            f = fwd(me)
            if not solo:
                avance = GUARDIAN_AVANCE[me][sq]
                maxk = 3 if (p.dbl and sq // N == start_row(me)) else 2
                for k, i in enumerate(avance[:maxk], 1):
                    q = b[i]
                    if q is None:
                        out.append(('m', sq, i)); continue
                    if k == 1 and q.c == opp and q.t == 'P' and not q.pr:
                        atras = i + f * N
                        if 0 <= atras < NN and b[atras] is None:
                            out.append(('push', sq, i))
                    break
                for i in GUARDIAN_LADOS[sq]:
                    q = b[i]
                    if q is None:
                        out.append(('m', sq, i))
                    elif q.c == me and q.t == 'P' and not q.pr:
                        if not (p.ls and p.ls[0] == q.pid and p.ls[2] == sq and p.ls[1] == i):
                            out.append(('swap', sq, i))
            for i, dr, lado in GUARDIAN_DIAG[sq]:
                q = b[i]
                if q and q.c == opp and q.t != 'K':
                    out.append(('m', sq, i))
                elif q is None and chk:
                    out.append(('m', sq, i))  # bloqueo de jaque (4.10.6)
                if q is None and dr == f and st.ep and st.ep[1] == i and st.ep[0] == lado:
                    out.append(('ep', sq, i, st.ep[0]))
            continue
        if t == 'CE':
            for i, recto2, anillo, medio in CATAPULTA[sq]:
                if i in blk:
                    continue
                q = b[i]
                if q is None:
                    if solo:
                        continue
                    if p.pr and recto2 and b[medio] is not None:
                        continue  # salto sobre una pieza: lo gestiona la cadena
                    out.append(('m', sq, i))
                elif q.c == opp and q.t != 'K' and anillo:
                    if not p.pr or not recto2:
                        out.append(('m', sq, i))
            if not solo and not p.pr:  # salto extendido sobre una fila continua de piezas
                for rayo in RAYOS[sq]:
                    k = 0
                    while k < len(rayo) and b[rayo[k]] is not None:
                        k += 1
                    if k >= 2 and k < len(rayo) and rayo[k] not in blk:
                        out.append(('m', sq, rayo[k]))
    # promociones que cuestan turno
    for sq in range(N * N):
        p = b[sq]
        if p is None or p.c != me or p.pr:
            continue
        if p.t in NEED and p.t not in st.tprom[me] and st.capT[me].get(p.t, 0) >= NEED[p.t]:
            out.append(('pr', sq))
        if p.t == 'P' and st.capP[me] // PEONES_POR_GUARDIAN > st.conv[me]:
            out.append(('cv', sq))
        if p.t == 'G' and st.capG[me] // GUARDIANES_POR_PROMOCION > st.gprom[me]:
            out.append(('gp', sq))
    return out


def _jump(st, pos, land, caps):
    n = st.copy()
    me = st.turn
    for c in caps:
        capture(n, c, me)
    p = n.b[pos]
    n.b[pos] = None
    n.b[land] = p
    return n


def centinela_chains(st, sq):
    """Cadenas de la Catapulta promocionada. Devuelve [(mov, estado_final)].
    Una pieza 'protegida' es la que está en diagonal a un Guardián de su bando:
    no puede ser capturada al ser saltada. Si un primer salto pasa sobre alguna
    pieza protegida, se hace como movimiento (sin capturar lo saltado) y la
    cadena puede continuar con capturas de piezas no protegidas."""
    b = st.b
    me = st.turn
    opp = 1 - me
    c0, r0 = sq % N, sq // N
    starts = []
    for dc, dr in ALL8:
        ci, ri, cd, rd = c0 + dc, r0 + dr, c0 + 2 * dc, r0 + 2 * dr
        if not on(cd, rd):
            continue
        I, D = ri * N + ci, rd * N + cd
        qi, qd = b[I], b[D]
        if qi and qi.c == opp and qi.t == 'K':
            continue
        # salto recto de dos casillas
        if not (qd and (qd.c == me or qd.t == 'K')) and not jump_blocked(b, D, me):
            jumped = [I] if (qi and qi.c == opp) else []
            prot = any(jump_blocked(b, x, me) for x in jumped)
            caps = [] if prot else list(jumped)
            if qd and qd.c == opp:
                caps.append(D)
            if caps or qi is not None:
                starts.append((D, caps))
        # salto extendido
        c, r = ci, ri
        run = []
        while on(c, r) and b[r * N + c] is not None:
            run.append(r * N + c); c += dc; r += dr
        if len(run) >= 2 and on(c, r):
            land = r * N + c
            if any(b[x].c == opp and b[x].t == 'K' for x in run) or jump_blocked(b, land, me):
                continue
            rivals = [x for x in run if b[x].c == opp]
            if not rivals or any(jump_blocked(b, x, me) for x in rivals):
                starts.append((land, []))
            else:
                starts.append((land, rivals))
    results = []

    def dfs(state, pos, steps):
        if in_check(state, me):
            return
        if in_check(state, opp):
            results.append((steps, state)); return
        cont = False
        pc, pr_ = pos % N, pos // N
        for dc, dr in ALL8:
            ci, ri, cd, rd = pc + dc, pr_ + dr, pc + 2 * dc, pr_ + 2 * dr
            if not on(cd, rd):
                continue
            I, D = ri * N + ci, rd * N + cd
            qi = state.b[I]
            if (qi and qi.c == opp and qi.t != 'K' and state.b[D] is None
                    and not jump_blocked(state.b, D, me) and not jump_blocked(state.b, I, me)):
                nxt = _jump(state, pos, D, [I])
                if not in_check(nxt, me):
                    cont = True
                    dfs(nxt, D, steps + [(D, [I])])
        if not cont:
            results.append((steps, state))

    for land, caps in starts:
        dfs(_jump(st, sq, land, caps), land, [(land, caps)])
    out = []
    for steps, state in results:
        fin = state.copy()
        p = fin.b[steps[-1][0]].cp(); p.moved = True; fin.b[steps[-1][0]] = p
        fin.turn = opp
        fin.ep = None
        fin.clock = 0 if any(c for _, c in steps) else st.clock + 1
        out.append((('ch', sq, steps[-1][0], steps), fin))
    return out


def legal(st, first_only=False):
    me = st.turn
    res = []
    for mv in pseudo(st):
        n = apply(st, mv)
        if not in_check(n, me):
            res.append((mv, n))
            if first_only:
                return res
    for sq in range(N * N):
        p = st.b[sq]
        if p and p.c == me and p.t == 'CE' and p.pr:
            res.extend(centinela_chains(st, sq))
            if first_only and res:
                return res[:1]
    return res


def poskey(st):
    return (tuple(p.key() if p else None for p in st.b), st.turn, st.ep, tuple(st.capP), tuple(st.capG),
            tuple(st.conv), tuple(st.gprom), frozenset(st.tprom[0]), frozenset(st.tprom[1]),
            tuple(sorted(st.capT[0].items())), tuple(sorted(st.capT[1].items())))


def insufficient(st):
    for color in (0, 1):
        pcs = [p for p in st.b if p and p.c == color and p.t != 'K']
        if not pcs:
            continue
        if len(pcs) == 1 and pcs[0].t in ('B', 'N') and not pcs[0].pr:
            continue
        return False
    return True
