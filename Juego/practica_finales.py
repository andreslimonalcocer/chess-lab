"""Práctica de finales de Rey y pieza contra Rey del Ajedrez Extendido con las tablas exactas (Simulador/finales.py
--guardar-tablas): valor de una posición, la jugada perfecta de cada bando y posiciones de práctica.

En las tablas la pieza es de las blancas; las posiciones con la pieza negra se consultan volteando el
tablero. El valor es exacto: medias jugadas hasta el mate con juego perfecto de los dos bandos, o tablas.
"""
import json, os, random

import busqueda as B
from motor import N, legal

PIEZAS = ['Q', 'R', 'B', 'N', 'CA', 'CH', 'CE', 'G', 'P']
PIEZAS_DOS = ['Q', 'R', 'B', 'N', 'CA', 'CH']  # las que admite finales_dos.py
INICIALES = {'Q': ['e1'], 'R': ['a1', 'k1'], 'B': ['c1', 'j1'], 'N': ['b1', 'i1'], 'CA': ['d1'], 'CH': ['h1'],
             'CE': ['g1']}
CASILLA_INICIAL = {'Q': 'e1', 'R': 'a1', 'B': 'c1', 'N': 'b1', 'CA': 'd1', 'CH': 'h1', 'CE': 'g1', 'G': 'f2',
                   'P': 'd2'}
RESUMEN = os.path.join(os.path.dirname(B.CARPETA_TABLAS), 'finales.json')
DIFICULTADES = [('Fácil (mate en 1 a 5)', 1, 5), ('Media (mate en 6 a 12)', 6, 12), ('Difícil (mate en 13 o más)', 13, 99)]


def hay_tabla(t, pr):
    return os.path.exists(B.archivo_tabla(t, pr))


def resumen():
    """{'Q': {...}, "Q'": {...}} con lo que calculó finales.py (si se puede forzar el mate, el más largo...)."""
    try:
        with open(RESUMEN, encoding='utf-8') as f:
            return {r['pieza']: r for r in json.load(f)}
    except (OSError, ValueError):
        return {}


def pieza_sola(st):
    """(casilla, pieza) de la única pieza que no es un Rey, o None si no es un final de Rey y pieza contra Rey."""
    otra = None
    for sq in range(N * N):
        p = st.b[sq]
        if p is not None and p.t != 'K':
            if otra is not None:
                return None
            otra = sq
    return (otra, st.b[otra]) if otra is not None else None


def _indice(t, pr, wk, bk, sq, turno):
    nx = 2 * N * N if (t in ('P', 'G') and not pr) else N * N
    return ((wk * N * N + bk) * nx + sq) * 2 + turno


def valor(st):
    """Desde el bando que mueve: ('gana', medias jugadas), ('pierde', medias jugadas), ('tablas', 0), o None
    si la posición no es de Rey y una o dos piezas contra Rey o falta su tabla."""
    if all(p is None or p.t == 'K' for p in st.b):
        return ('tablas', 0)  # solo quedan los Reyes
    r = B.dtm_final(st)
    if r is None:
        return None
    d, c = r
    if d == 255:
        return ('tablas', 0)
    return ('gana', d) if st.turn == c else ('pierde', d)


def puntaje(v):
    """Para ordenar resultados desde el bando que mueve: ganar pronto > ganar tarde > tablas > perder tarde."""
    if v is None:
        return 0
    r, d = v
    return 1000 - d if r == 'gana' else (-1000 + d if r == 'pierde' else 0)


def jugadas_valoradas(st, movs=None):
    """[(puntaje para el que mueve, índice, jugada, posición siguiente)], de la mejor a la peor."""
    movs = movs if movs is not None else legal(st)
    out = []
    for i, (mv, n) in enumerate(movs):
        v = valor(n)  # desde el rival, que mueve en n
        if v is not None and v[0] == 'pierde':  # el rival recibe mate en d: yo lo doy en d + 1
            sc = 1000 - (v[1] + 1)
        elif v is not None and v[0] == 'gana':
            sc = -1000 + (v[1] + 1)
        else:
            sc = 0
        out.append((sc, i, mv, n))
    out.sort(key=lambda x: -x[0])
    return out


def mejor_jugada(st, movs=None, rng=random):
    """Índice de una jugada perfecta (entre varias igual de buenas, una al azar)."""
    vals = jugadas_valoradas(st, movs)
    if not vals:
        return None
    mejores = [x for x in vals if x[0] == vals[0][0]]
    return rng.choice(mejores)[1]


def describir(v):
    """Texto del valor de una posición desde el bando que mueve."""
    if v is None:
        return ''
    r, d = v
    if r == 'tablas':
        return 'Tablas: el mate no se puede forzar.'
    jug = (d + 1) // 2
    return ('Mate en %d con juego perfecto.' % jug) if r == 'gana' else ('Recibe mate en %d con juego perfecto.' % jug)


def posicion(t, pr, como='inicial', minimo=1, maximo=99, rng=random, intentos=200000):
    """Posición de práctica: {'piezas': [[casilla, tipo, color, promocionada], ...], 'turno': 0} con la pieza de
    las blancas. 'inicial': Reyes en f1 y f11 y la pieza en su casilla de inicio; 'aleatoria': una posición al
    azar en la que las blancas, al mover, dan mate en minimo..maximo jugadas con juego perfecto."""
    from motor import sqn
    if como == 'inicial':
        return {'piezas': [[sqn('f1'), 'K', 0, False], [sqn('f11'), 'K', 1, False],
                           [sqn(CASILLA_INICIAL[t]), t, 0, pr]], 'turno': 0}
    tabla = B._tabla(t, pr)
    if tabla is None:
        return None
    mejor = None
    for _ in range(intentos):
        wk, bk, sq = rng.randrange(N * N), rng.randrange(N * N), rng.randrange(N * N)
        d = tabla[_indice(t, pr, wk, bk, sq, 0)]
        if d == 255 or d == 0:
            continue
        jug = (d + 1) // 2
        if minimo <= jug <= maximo:
            return {'piezas': [[wk, 'K', 0, False], [bk, 'K', 1, False], [sq, t, 0, pr]], 'turno': 0}
        if mejor is None or abs(jug - minimo) < abs(mejor[0] - minimo):
            mejor = (jug, wk, bk, sq)
    if mejor:  # no hay mates tan largos con esta pieza: el más cercano encontrado
        _, wk, bk, sq = mejor
        return {'piezas': [[wk, 'K', 0, False], [bk, 'K', 1, False], [sq, t, 0, pr]], 'turno': 0}
    # con esta pieza no se puede forzar el mate: cualquier posición válida (para practicar igual)
    from ia import construir_posicion
    from motor import in_check
    while True:
        wk, bk, sq = rng.sample(range(N * N), 3)
        if max(abs(wk % N - bk % N), abs(wk // N - bk // N)) <= 1:
            continue
        if t in ('P', 'G') and not pr and sq // N in (0, N - 1):
            continue
        ini = {'piezas': [[wk, 'K', 0, False], [bk, 'K', 1, False], [sq, t, 0, pr]], 'turno': 0}
        st = construir_posicion(ini['piezas'], 0)
        if not in_check(st, 1) and legal(st):
            return ini


# ---------------------------------------------------------------------- interfaz común (11×11 y variantes)
COLORES_ALFIL = [('Cualquiera', None), ('Casillas claras', 'claro'), ('Casillas oscuras', 'oscuro')]


def color_casilla(sq, ancho):
    """'claro' u 'oscuro', como se dibuja el tablero (a1 es clara)."""
    return 'claro' if (sq % ancho + sq // ancho) % 2 == 0 else 'oscuro'


def cumple_colores(ligadas, color, ancho):
    """ligadas: casillas de las piezas que no cambian de color (Alfiles). Con una, debe estar en el color pedido;
    con dos, en colores distintos (con dos Alfiles del mismo color no se puede dar mate)."""
    if len(ligadas) == 1:
        return color is None or color_casilla(ligadas[0], ancho) == color
    if len(ligadas) == 2:
        return color_casilla(ligadas[0], ancho) != color_casilla(ligadas[1], ancho)
    return True


def elegir_inicial(candidatas, usadas, ligada, color, ancho):
    """La primera casilla inicial libre (del color pedido, si la pieza es un Alfil)."""
    libres = [s for s in candidatas if s not in usadas]
    if ligada and color:
        buenas = [s for s in libres if color_casilla(s, ancho) == color]
        if buenas:
            return buenas[0]
    return libres[0] if libres else None
class Practica11:
    """Finales del Ajedrez Extendido (tablas de Simulador/finales.py)."""

    def __init__(self, v):
        self.v = v

    def valor(self, st):
        return valor(st)

    def jugadas_valoradas(self, st, movs=None):
        return jugadas_valoradas(st, movs)

    def mejor_jugada(self, st, movs=None, rng=random):
        return mejor_jugada(st, movs, rng)

    def posicion(self, cfg, minimo=1, maximo=99, rng=random):
        if cfg.get('par'):
            return self.posicion_par(cfg, minimo, maximo, rng)
        return posicion(cfg['t'], cfg['pr'], cfg.get('posicion', 'inicial'), minimo, maximo, rng)

    @staticmethod
    def ligada(t, pr):
        return t == 'B' and not pr

    def alfiles(self, cfg):
        """Cuántas piezas del final no cambian de color de casilla (Alfiles sin promocionar)."""
        if cfg.get('par'):
            return sum(1 for t, pr in cfg['par'] if self.ligada(t, pr))
        return 1 if self.ligada(cfg['t'], cfg['pr']) else 0

    def posicion_par(self, cfg, minimo=1, maximo=99, rng=random, intentos=100000):
        from motor import sqn
        from ia import construir_posicion
        (ta, pa), (tb, pb) = cfg['par']
        color = cfg.get('color_alfil')
        if cfg.get('posicion', 'inicial') == 'inicial':
            usadas = set()
            a = elegir_inicial([sqn(x) for x in INICIALES[ta]], usadas, self.ligada(ta, pa), color, N)
            usadas.add(a)
            b = elegir_inicial([sqn(x) for x in INICIALES[tb]], usadas, self.ligada(tb, pb), color, N)
            ligadas = [x for x, (t, pr) in ((a, (ta, pa)), (b, (tb, pb))) if self.ligada(t, pr)]
            if a is not None and b is not None and cumple_colores(ligadas, color, N):
                return {'piezas': [[sqn('f1'), 'K', 0, False], [sqn('f11'), 'K', 1, False], [a, ta, 0, pa],
                                   [b, tb, 0, pb]], 'turno': 0}
        mejor = None
        for _ in range(intentos):
            wk, bk, a, b = rng.sample(range(N * N), 4)
            if not cumple_colores([x for x, (t, pr) in ((a, (ta, pa)), (b, (tb, pb))) if self.ligada(t, pr)],
                                  color, N):
                continue
            ini = {'piezas': [[wk, 'K', 0, False], [bk, 'K', 1, False], [a, ta, 0, pa], [b, tb, 0, pb]], 'turno': 0}
            st = construir_posicion(ini['piezas'], 0)
            w = valor(st)
            if w is None or w[0] != 'gana' or not legal(st):
                continue
            jug = (w[1] + 1) // 2
            if minimo <= jug <= maximo:
                return ini
            if mejor is None or abs(jug - minimo) < mejor[0]:
                mejor = (abs(jug - minimo), ini)
        return mejor[1] if mejor else None

    def opciones(self):
        """[(cfg parcial, nombre, hay tabla, resumen)] de los finales que se pueden practicar."""
        res = resumen()
        out = []
        for t in PIEZAS:
            for pr in (False, True):
                r = res.get(t + ("'" if pr else ''), {})
                info = None
                if r:
                    vals = [x for x in r['inicio'].values() if x]
                    info = {'ganadas': r.get('ganadas', 0), 'maximo': r.get('maximo'),
                            'inicio': min(vals) if vals else None}
                out.append(({'t': t, 'pr': pr}, self.v.nombre_pieza(t, pr), hay_tabla(t, pr), info))
        # finales de dos piezas con tabla guardada (finales_dos.py --guardar)
        formas = [(t, pr) for t in PIEZAS_DOS for pr in (False, True)]
        for i, (ta, pa) in enumerate(formas):
            for tb, pb in formas[i:]:
                for x, y in (((ta, pa), (tb, pb)), ((tb, pb), (ta, pa))):
                    if os.path.exists(B.archivo_tabla(x[0], x[1], y[0], y[1])):
                        clave = '%s+%s' % (x[0] + ("'" if x[1] else ''), y[0] + ("'" if y[1] else ''))
                        r = res.get(clave, {})
                        info = None
                        if r:
                            g = r.get('grupos', {})
                            pos = sum(v['posiciones'] for v in g.values())
                            gan = sum(v['posiciones'] * v['ganadas'] for v in g.values())
                            vals = [v for v in r.get('inicio', {}).values() if v]
                            info = {'ganadas': gan / pos if pos else 0,
                                    'maximo': max((v['maximo'] or 0) for v in g.values()) or None,
                                    'inicio': min(vals) if vals else None}
                        nombre = '%s y %s' % (self.v.nombre_pieza(*x), self.v.nombre_pieza(*y))
                        out.append(({'par': [list(x), list(y)]}, nombre, True, info))
                        break
        return out


class PracticaVariante:
    """Finales de las variantes del motor genérico (tablas de tablas_genericas.py)."""

    def __init__(self, v):
        import tablas_genericas as TG
        self.TG, self.v, self.cfg = TG, v, v.cfg
        self.t = TG.Tablas(v.m)
        self.rey = TG.rey_de(self.cfg)

    def valor(self, st):
        return self.t.valor(st)

    def jugadas_valoradas(self, st, movs=None):
        movs = movs if movs is not None else self.v.legal(st)
        out = []
        for i, (mv, n) in enumerate(movs):
            w = self.valor(n)
            if w is not None and w[0] == 'pierde':
                sc = 1000 - (w[1] + 1)
            elif w is not None and w[0] == 'gana':
                sc = -1000 + (w[1] + 1)
            else:
                sc = 0
            out.append((sc, i, mv, n))
        out.sort(key=lambda x: -x[0])
        return out

    def mejor_jugada(self, st, movs=None, rng=random):
        vals = self.jugadas_valoradas(st, movs)
        if not vals:
            return None
        return rng.choice([x for x in vals if x[0] == vals[0][0]])[1]

    def _casillas_iniciales(self):
        reyes = {c: r * self.cfg['ancho'] + col for col, r, t, c in self.cfg['posicion'] if t == self.rey}
        piezas = {}
        for col, r, t, c in sorted(self.cfg['posicion'], key=lambda p: (p[1], p[0])):
            if c == 0:
                piezas.setdefault(t, []).append(r * self.cfg['ancho'] + col)
        return reyes, piezas

    def ligada(self, t):
        """¿La pieza solo se desliza en diagonal (y por eso nunca cambia de color de casilla)?"""
        movs = self.cfg['piezas'][t].get('movs', [])
        return bool(movs) and all(m.get('dirs') == 'diag' for m in movs)

    def alfiles(self, cfg):
        return sum(1 for t in cfg['tipos'] if self.ligada(t))

    def posicion(self, cfg, minimo=1, maximo=99, rng=random, intentos=60000):
        tipos = cfg['tipos']
        W = self.cfg['ancho']
        NS = W * self.cfg['alto']
        color = cfg.get('color_alfil')
        if cfg.get('posicion', 'inicial') == 'inicial':
            reyes, piezas = self._casillas_iniciales()
            cas, usadas = [], {reyes.get(0), reyes.get(1)}
            for t in tipos:
                s = elegir_inicial(piezas.get(t, []), usadas, self.ligada(t), color, W)
                if s is None:
                    s = rng.choice([x for x in range(NS) if x not in usadas])
                usadas.add(s)
                cas.append(s)
            if 0 in reyes and 1 in reyes and cumple_colores([x for x, t in zip(cas, tipos) if self.ligada(t)],
                                                            color, W):
                return {'piezas': [[reyes[0], self.rey, 0, False], [reyes[1], self.rey, 1, False]] +
                        [[s, t, 0, False] for s, t in zip(cas, tipos)], 'turno': 0}
        mejor = None
        for k in range(intentos):
            sq = rng.sample(range(NS), 2 + len(tipos))
            if not cumple_colores([x for x, t in zip(sq[2:], tipos) if self.ligada(t)], color, W):
                continue
            ini = {'piezas': [[sq[0], self.rey, 0, False], [sq[1], self.rey, 1, False]] +
                   [[s, t, 0, False] for s, t in zip(sq[2:], tipos)], 'turno': 0}
            st = self.v.construir(ini['piezas'], 0)
            if self.v.en_jaque(st, 1) or not self.v.legal(st):
                continue
            w = self.valor(st)
            if w is None:
                continue
            if w[0] != 'gana':
                if mejor is None:
                    mejor = (99, ini)
                continue
            jug = (w[1] + 1) // 2
            if minimo <= jug <= maximo:
                return ini
            if mejor is None or abs(jug - minimo) < mejor[0]:
                mejor = (abs(jug - minimo), ini)
        return mejor[1] if mejor else None

    def opciones(self):
        out = []
        TG, cfg = self.TG, self.cfg
        combos = [[t] for t in TG.piezas_posibles(cfg)]
        if os.path.isdir(TG.CARPETA):  # pares con tabla ya construida
            for f in sorted(os.listdir(TG.CARPETA)):
                if f.endswith('.json'):
                    try:
                        with open(os.path.join(TG.CARPETA, f), encoding='utf-8') as fh:
                            r = json.load(fh)
                    except (OSError, ValueError):
                        continue
                    if len(r.get('piezas', [])) == 2 and all(t in cfg['piezas'] for t in r['piezas']) \
                            and TG.clave(cfg, r['piezas']) == r.get('clave'):
                        combos.append(r['piezas'])
        for tipos in combos:
            r = TG.resumen(cfg, tipos)
            info = None
            if r:
                info = {'ganadas': r['ganadas'], 'maximo': r['maximo'], 'inicio': None}
                ini = self.posicion({'tipos': tipos, 'posicion': 'inicial'})
                if ini:
                    w = self.valor(self.v.construir(ini['piezas'], 0))
                    if w and w[0] == 'gana':
                        info['inicio'] = (w[1] + 1) // 2
            nombre = ' y '.join(cfg['piezas'][t]['nombre'] for t in tipos)
            out.append(({'tipos': tipos}, nombre, TG.existe(cfg, tipos), info))
        return out


def para(v):
    """La práctica de finales adecuada para la variante v."""
    return Practica11(v) if v.id == 'extendido' else PracticaVariante(v)
