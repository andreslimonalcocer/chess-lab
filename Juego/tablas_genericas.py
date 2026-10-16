"""Tablas exactas de finales para las variantes del motor genérico (clásico, Capablanca, gótico y las del
Laboratorio): Rey y una o dos piezas contra Rey solo.

Cada tabla guarda, para cada posición (dónde están los Reyes y las piezas y a quién le toca), en cuántas
medias jugadas dan mate las blancas con juego perfecto de los dos bandos (255 = no se fuerza). Se construye
con análisis retrógrado (desde los mates, deshaciendo jugadas) usando los movimientos definidos en la
variante, así que vale para cualquier pieza del Laboratorio. Solo para piezas que no son peones, en
variantes con objetivo «jaque mate»; no se consideran el enroque ni la regla de las 50 jugadas.

Las tablas se identifican por lo que las determina (tamaño del tablero, movimientos del Rey y de las
piezas, regla del ahogado), no por el nombre de la variante: el Alfil del clásico y el de una variante del
Laboratorio de 8×8 comparten tabla. Se guardan en Simulador/tablas/variantes/.
"""
import hashlib, json, os, time
from array import array

import generico as G

AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(os.path.dirname(AQUI), 'Simulador', 'tablas', 'variantes')
SIN = 255


# ---------------------------------------------------------------------- piezas y claves
def rey_de(cfg):
    reales = [t for t, d in cfg['piezas'].items() if d.get('real')]
    return reales[0] if len(reales) == 1 else None


def piezas_posibles(cfg):
    """Tipos que pueden tener tabla: ni el rey ni los peones, y solo piezas de movimientos simétricos que mueven
    y capturan igual (el análisis retrógrado deshace jugadas con los mismos movimientos)."""
    return [t for t, d in cfg['piezas'].items() if not d.get('real') and not d.get('peon') and G.es_simple(d)]


def aplicable(cfg):
    r = dict(G.REGLAS_BASE)
    r.update(cfg.get('reglas', {}))
    return r['objetivo'] == 'mate' and rey_de(cfg) is not None and G.es_simple(cfg['piezas'][rey_de(cfg)])


def clave(cfg, tipos):
    """Identificador de la tabla: tamaño, movimientos del rey y de las piezas, y regla del ahogado."""
    tipos = sorted(tipos)
    r = dict(G.REGLAS_BASE)
    r.update(cfg.get('reglas', {}))
    datos = {'ancho': cfg['ancho'], 'alto': cfg['alto'], 'rey': cfg['piezas'][rey_de(cfg)]['movs'],
             'piezas': [cfg['piezas'][t]['movs'] for t in tipos], 'ahogado': r['ahogado']}
    h = hashlib.sha1(json.dumps(datos, sort_keys=True).encode()).hexdigest()[:12]
    return '%s_%dx%d_%s' % (h, cfg['ancho'], cfg['alto'], '+'.join(tipos))


def ruta(cfg, tipos):
    return os.path.join(CARPETA, clave(cfg, tipos) + '.dtm')


def existe(cfg, tipos):
    return os.path.exists(ruta(cfg, tipos))


# ---------------------------------------------------------------------- geometría
class Geometria:
    """Movimientos de cada tipo en el tablero vacío (rayos y casillas intermedias), del motor genérico."""

    def __init__(self, cfg):
        self.m = G.Motor(cfg)
        self.W, self.H = self.m.W, self.m.H
        self.NS = self.W * self.H
        self.entre = {}  # entre[t][x] = {casilla alcanzable: casillas intermedias}
        for t in self.m.rayos:
            self.entre[t] = []
            for x in range(self.NS):
                d = {}
                for ray in self.m.rayos[t][x]:
                    for k, y in enumerate(ray):
                        d[y] = ray[:k]
                self.entre[t].append(d)

    def ataca(self, t, x, y, ocupadas):
        e = self.entre[t][x].get(y)
        if e is None:
            return False
        for s in e:
            if s in ocupadas:
                return False
        return True

    def destinos(self, t, x, ocupadas):
        """Casillas libres a las que llega (o de las que pudo venir: los movimientos son simétricos)."""
        out = []
        for ray in self.m.rayos[t][x]:
            for y in ray:
                if y in ocupadas:
                    break
                out.append(y)
        return out

    def voltear(self, sq):
        return (self.H - 1 - sq // self.W) * self.W + sq % self.W


# ---------------------------------------------------------------------- índice
class Indice:
    def __init__(self, NS, tipos):
        self.NS, self.tipos = NS, list(tipos)
        self.k = len(tipos)
        self.iguales = self.k == 2 and tipos[0] == tipos[1]
        if self.k == 1:
            self.np = NS
        elif self.iguales:
            self.par = [[-1] * NS for _ in range(NS)]
            self.pa, self.pb = array('i'), array('i')
            for a in range(NS):
                for b in range(a + 1, NS):
                    self.par[a][b] = self.par[b][a] = len(self.pa)
                    self.pa.append(a)
                    self.pb.append(b)
            self.np = len(self.pa)
        else:
            self.np = NS * NS
        self.total = NS * NS * self.np * 2

    def codigo(self, cas):
        if self.k == 1:
            return cas[0]
        if self.iguales:
            return self.par[cas[0]][cas[1]]
        return cas[0] * self.NS + cas[1]

    def casillas(self, cod):
        if self.k == 1:
            return (cod,)
        if self.iguales:
            return (self.pa[cod], self.pb[cod])
        return (cod // self.NS, cod % self.NS)

    def todas(self):
        NS = self.NS
        if self.k == 1:
            for a in range(NS):
                yield a, (a,)
        elif self.iguales:
            for c in range(self.np):
                yield c, (self.pa[c], self.pb[c])
        else:
            for a in range(NS):
                for b in range(NS):
                    if a != b:
                        yield a * NS + b, (a, b)

    def i(self, wk, bk, cod, turno):
        return ((wk * self.NS + bk) * self.np + cod) * 2 + turno


# ---------------------------------------------------------------------- construcción
def construir(cfg, tipos, avisar=print):
    """Construye (y guarda) la tabla de Rey + tipos contra Rey; antes, las de una pieza que hagan falta.
    Devuelve el resumen."""
    tipos = sorted(tipos)
    if not aplicable(cfg):
        raise ValueError('La variante no tiene objetivo «jaque mate» con un único rey.')
    if len(tipos) == 2:  # tras capturar el Rey negro una pieza queda la otra: su tabla hace falta antes
        for t in set(tipos):
            if not existe(cfg, [t]):
                construir(cfg, [t], avisar)
    g = Geometria(cfg)
    K = rey_de(cfg)
    r = dict(G.REGLAS_BASE)
    r.update(cfg.get('reglas', {}))
    ahogado_gana = r['ahogado'] == 'victoria'
    ix = Indice(g.NS, tipos)
    NS = g.NS
    avisar('%s: %s contra %s, %d posiciones...' % (
        cfg.get('nombre', ''), ' y '.join(cfg['piezas'][t]['nombre'] for t in tipos), cfg['piezas'][K]['nombre'],
        ix.total))
    dtm = bytearray(b'\xff') * ix.total
    cuenta = bytearray(ix.total)   # negras: jugadas que aún no pierden (250 = se salva); blancas: 1 = válida
    ext = bytearray(ix.total)      # negras: la captura perdedora más larga
    restos = {}
    if len(tipos) == 2:
        for t in set(tipos):
            restos[t] = (Indice(NS, [t]), cargar(cfg, [t]))
    pendientes, perdidas = {}, array('l')
    t0 = time.time()

    def jaque_negro(wk, bk, cas):  # ¿está en jaque el Rey negro?
        ocup = (wk, bk) + cas
        if g.ataca(K, wk, bk, ocup):
            return True
        for t, x in zip(tipos, cas):
            if g.ataca(t, x, bk, ocup):
                return True
        return False

    for wk in range(NS):
        for bk in range(NS):
            if wk == bk or g.ataca(K, bk, wk, (wk, bk)):  # el Rey blanco no puede estar en jaque del negro
                continue
            for cod, cas in ix.todas():
                if wk in cas or bk in cas:
                    continue
                i = ix.i(wk, bk, cod, 0)
                jaque = jaque_negro(wk, bk, cas)
                if not jaque:
                    cuenta[i] = 1
                jugadas, salva, peor = 0, False, 0
                destinos = []  # jugadas del Rey negro: hasta una pieza blanca (que puede capturar)
                for ray in g.m.rayos[K][bk]:
                    for y in ray:
                        if y == wk:
                            break
                        destinos.append(y)
                        if y in cas:
                            break
                for y in destinos:
                    if y in cas:
                        quedan = [(t, x) for t, x in zip(tipos, cas) if x != y]
                        q = (wk, y) + tuple(x for _, x in quedan)
                        if g.ataca(K, wk, y, q) or any(g.ataca(t, x, y, q) for t, x in quedan):
                            continue
                        if not quedan:
                            salva = True
                            continue
                        ti, tab = restos[quedan[0][0]]
                        d = tab[ti.i(wk, y, quedan[0][1], 0)] if tab else SIN
                        if d == SIN:
                            salva = True
                        else:
                            peor = max(peor, d + 1)
                        continue
                    q = (wk, y) + cas
                    if g.ataca(K, wk, y, q) or any(g.ataca(t, x, y, q) for t, x in zip(tipos, cas)):
                        continue
                    jugadas += 1
                j = i + 1
                if salva:
                    cuenta[j] = 250
                    continue
                cuenta[j] = jugadas
                ext[j] = peor
                if jugadas == 0:
                    if peor:
                        pendientes.setdefault(peor, array('l')).append(j)
                    elif jaque or ahogado_gana:
                        dtm[j] = 0
                        perdidas.append(j)
                    else:
                        cuenta[j] = 250  # ahogado: tablas
        if wk % max(1, NS // 8) == 0:
            avisar('  inicialización %d %% (%.0f s)' % (100 * (wk + 1) // NS, time.time() - t0))

    n = 0
    while perdidas or pendientes:
        for j in pendientes.pop(n, ()):
            if dtm[j] == SIN:
                dtm[j] = n
                perdidas.append(j)
        ganadas = array('l')
        for i in perdidas:  # blancas: desde toda posición previa se gana en n + 1
            cod = (i >> 1) % ix.np
            rr = (i >> 1) // ix.np
            wk, bk = rr // NS, rr % NS
            cas = ix.casillas(cod)
            ocup = (wk, bk) + cas
            previas = [(y,) + cas for y in g.destinos(K, wk, ocup)]
            for p, (t, x) in enumerate(zip(tipos, cas)):
                for y in g.destinos(t, x, ocup):
                    previas.append((wk,) + cas[:p] + (y,) + cas[p + 1:])
            for prev in previas:
                wk2, cas2 = prev[0], prev[1:]
                if g.ataca(K, bk, wk2, (wk2, bk) + cas2) or jaque_negro(wk2, bk, cas2):
                    continue
                j = ix.i(wk2, bk, ix.codigo(cas2), 0)
                if dtm[j] == SIN:
                    dtm[j] = n + 1
                    ganadas.append(j)
        n += 1
        perdidas = array('l')
        for i in ganadas:  # negras: una posición previa se pierde cuando todas sus jugadas pierden
            cod = (i >> 1) % ix.np
            rr = (i >> 1) // ix.np
            wk, bk = rr // NS, rr % NS
            cas = ix.casillas(cod)
            for y in g.destinos(K, bk, (wk,) + cas):
                if g.ataca(K, y, wk, (wk, y) + cas):  # en la previa el Rey blanco no puede estar en jaque
                    continue
                j = ix.i(wk, y, cod, 1)
                c = cuenta[j]
                if c == 250 or dtm[j] != SIN:
                    continue
                c -= 1
                cuenta[j] = c
                if c == 0:
                    if ext[j] > n + 1:
                        pendientes.setdefault(ext[j], array('l')).append(j)
                    else:
                        dtm[j] = n + 1
                        perdidas.append(j)
        n += 1
        if n > 250:
            raise ValueError('Mates de más de 125 jugadas: no caben en la tabla.')

    # resumen y guardado
    validas = ganadas_n = suma = maximo = 0
    for wk in range(NS):
        for bk in range(NS):
            base = (wk * NS + bk) * ix.np
            for cod in range(ix.np):
                i = (base + cod) * 2
                if cuenta[i] != 1:
                    continue
                validas += 1
                d = dtm[i]
                if d != SIN:
                    ganadas_n += 1
                    jj = (d + 1) // 2
                    suma += jj
                    maximo = max(maximo, jj)
    os.makedirs(CARPETA, exist_ok=True)
    with open(ruta(cfg, tipos) + '.tmp', 'wb') as f:
        f.write(dtm)
    os.replace(ruta(cfg, tipos) + '.tmp', ruta(cfg, tipos))
    res = {'clave': clave(cfg, tipos), 'variante': cfg.get('nombre'), 'piezas': tipos,
           'nombres': [cfg['piezas'][t]['nombre'] for t in tipos], 'posiciones': validas,
           'ganadas': ganadas_n / validas if validas else 0, 'media': suma / ganadas_n if ganadas_n else None,
           'maximo': maximo or None, 'segundos': round(time.time() - t0)}
    with open(ruta(cfg, tipos)[:-4] + '.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    _CACHE.pop(clave(cfg, tipos), None)
    avisar('  listo: %.1f %% de las posiciones ganadas, mate más largo en %s jugadas (%.0f s)' % (
        100 * res['ganadas'], res['maximo'] or '—', res['segundos']))
    return res


# ---------------------------------------------------------------------- consulta
_CACHE = {}


def cargar(cfg, tipos):
    k = clave(cfg, tipos)
    if k not in _CACHE:
        try:
            with open(ruta(cfg, tipos), 'rb') as f:
                _CACHE[k] = f.read()
        except OSError:
            _CACHE[k] = None
    return _CACHE[k]


def resumen(cfg, tipos):
    try:
        with open(ruta(cfg, tipos)[:-4] + '.json', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


class Tablas:
    """Consulta de las tablas de una variante desde posiciones del motor genérico."""

    def __init__(self, motor):
        self.m = motor
        self.cfg = motor.cfg
        self.ok = aplicable(self.cfg)
        self.g = None
        self.indices = {}

    def _geo(self):
        if self.g is None:
            self.g = Geometria(self.cfg)
        return self.g

    def valor(self, st):
        """Desde el bando que mueve: ('gana' | 'pierde' | 'tablas', medias jugadas), o None si no aplica."""
        if not self.ok:
            return None
        piezas, reyes = [], 0
        for sq, p in enumerate(st.b):
            if p is None:
                continue
            if p[0] in self.m.real:
                reyes += 1
            elif p[0] in self.m.peones:
                return None
            else:
                piezas.append((p[0], p[1], sq))
                if len(piezas) > 2:
                    return None
        if reyes != 2:
            return None
        if not piezas:
            return ('tablas', 0)
        color = piezas[0][1]
        if any(c != color for _, c, _ in piezas):
            return None
        tipos = sorted(t for t, _, _ in piezas)
        tabla = cargar(self.cfg, tipos)
        if tabla is None:
            return None
        g = self._geo()
        k = tuple(tipos)
        if k not in self.indices:
            self.indices[k] = Indice(g.NS, tipos)
        ix = self.indices[k]
        wk, bk, turno = st.rey[0], st.rey[1], st.turn
        cas = [sq for _, _, sq in sorted(piezas)]
        if color == 1:  # tablas de las blancas: se voltea el tablero y se cambian los colores
            wk, bk, turno = g.voltear(st.rey[1]), g.voltear(st.rey[0]), 1 - st.turn
            cas = [g.voltear(sq) for sq in cas]
        if ix.iguales:
            cas.sort()
        d = tabla[ix.i(wk, bk, ix.codigo(tuple(cas)), turno)]
        if d == SIN:
            return ('tablas', 0)
        return ('gana', d) if st.turn == color else ('pierde', d)
