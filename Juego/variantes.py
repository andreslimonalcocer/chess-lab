"""Variantes de ajedrez con una interfaz común para la pantalla de juego.

- Extendido: el Ajedrez Extendido (11 × 11), con el motor de Simulador/motor.py.
- Genérica: cualquier variante descrita para generico.py (clásico, Capablanca, gótico, laboratorio).

Cada variante ofrece: posiciones, jugadas legales, notación, fin de partida, imágenes de
las piezas y lo necesario para el editor de posiciones del entrenamiento.
"""
import copy, json, os, re, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'Simulador'))
import motor as M
import notacion as NT
import generico as G
from ia import construir_posicion

PIEZAS = os.path.join(RAIZ, 'Piezas')
COLORES = ('blancas', 'negras')
LABORATORIO = os.path.join(AQUI, 'laboratorio')


def ruta_imagen(archivo, color, dorada=False):
    """Imagen de una pieza según su estilo, prediseño o diseño propio (ver disenos.py)."""
    import disenos
    return disenos.ruta(archivo, color, dorada)


# nombres anteriores de las variantes (partidas, problemas y textos guardados con ellos siguen valiendo)
NOMBRES_ANTIGUOS = {'Ajedrez 11×11': 'Ajedrez Extendido', 'Ajedrez 11x11': 'Ajedrez Extendido'}


def nombre_actual(nombre):
    return NOMBRES_ANTIGUOS.get(nombre, nombre)


class Variante:
    """Interfaz común. 'acciones' son jugadas sin casilla de destino (promociones que cuestan turno)."""
    id = nombre = ''
    ancho = alto = 8
    tema = 'madera'
    tiene_promocionadas = False   # el editor ofrece la forma promocionada de cada pieza
    con_puntos = False            # el marcador muestra puntos (desempate por puntos)

    def nombre_casilla(self, sq):
        return G.LETRAS[sq % self.ancho] + str(sq // self.ancho + 1)

    def destino(self, mv):
        return mv[2]

    def es_cadena(self, mv):
        return False

    def derechos(self, st, color):
        return None


# ---------------------------------------------------------------------- Ajedrez 11x11 extendido
ARCHIVO = {'K': 'rey', 'Q': 'dama', 'R': 'torre', 'B': 'alfil', 'N': 'caballo', 'CA': 'arzobispo',
           'CH': 'canciller', 'CE': 'catapulta', 'G': 'guardian', 'P': 'peon'}
NOMBRES = {'K': 'Rey', 'Q': 'Dama', 'R': 'Torre', 'B': 'Alfil', 'N': 'Caballo', 'CA': 'Arzobispo',
           'CH': 'Canciller', 'CE': 'Catapulta', 'G': 'Guardián', 'P': 'Peón'}
SIMBOLO = {'K': 'R', 'Q': 'D', 'R': 'T', 'B': 'A', 'N': 'C', 'CA': 'Az', 'CH': 'Ch', 'CE': 'Ct',
           'G': 'G', 'P': 'P'}
ORDEN_CAPTURAS = ['Q', 'CH', 'CA', 'R', 'CE', 'N', 'B', 'G', 'P']


class Extendido(Variante):
    id = 'extendido'
    nombre = 'Ajedrez Extendido'
    resumen = 'Tablero de 11 × 11 con Catapulta, Guardianes y una forma extendida para cada pieza.'
    ancho = alto = 11
    tiene_promocionadas = True
    con_puntos = True
    spec = {'tipo': 'extendido'}
    paleta = ['K', 'Q', 'R', 'B', 'N', 'CA', 'CH', 'CE', 'G', 'P']
    rey, peon = 'K', 'P'

    def inicial(self):
        return M.initial()

    def legal(self, st):
        return M.legal(st)

    def en_jaque(self, st, c):
        return st.kpos[c] is not None and M.in_check(st, c)

    def casilla_rey(self, st, c):
        return st.kpos[c]

    def clave(self, st):
        return M.poskey(st)

    def pieza(self, st, sq):
        p = st.b[sq]
        return None if p is None else (p.t, p.c, p.pr)

    def imagen(self, t, c, pr):
        return ruta_imagen(ARCHIVO[t], c, pr and t != 'K')

    def nombre_pieza(self, t, pr=False):
        if not pr:
            return NOMBRES[t]
        return NOMBRES[t] + (' extendida' if t in ('Q', 'R', 'CE') else ' extendido')

    def notacion(self, st, mv, n, movs):
        """Notación del Apéndice C del reglamento (la misma que usa el simulador)."""
        return NT.notacion(st, mv, n, movs)

    def descripcion(self, st, mv):
        k, b, name = mv[0], st.b, M.name
        if k == 'm':
            q = b[mv[2]]
            return ('Capturar %s en %s' % (NOMBRES[q.t], name(mv[2]))) if q else 'Mover a ' + name(mv[2])
        if k == 'ep':
            return 'Capturar al paso en ' + name(mv[2])
        if k == 'push':
            return 'Empujar el peón de ' + name(mv[2])
        if k == 'swap':
            return 'Intercambiar con el peón de ' + name(mv[2])
        if k == 'cs':
            return 'Enroque hacia la columna ' + ('a' if mv[3][0] % M.N == 0 else 'k')
        if k == 'ch':
            ncap = sum(len(c) for _, c in mv[3])
            return 'Cadena %s → %s (captura %d)' % (name(mv[1]), ' → '.join(name(l) for l, _ in mv[3]), ncap)
        if k == 'pr':
            return 'Extender %s de %s' % (NOMBRES[b[mv[1]].t], name(mv[1]))
        if k == 'cv':
            return 'Convertir el peón de %s en Guardián' % name(mv[1])
        if k == 'gp':
            return 'Extender el Guardián de %s' % name(mv[1])
        return str(mv)

    def casillas(self, mv):
        k = mv[0]
        if k in ('pr', 'cv', 'gp'):
            return {mv[1]}
        if k == 'cs':
            return {mv[1], mv[2], mv[3][0], mv[3][1]}
        if k == 'ch':
            return {mv[1]} | {l for l, _ in mv[3]}
        return {mv[1], mv[2]}

    def destino(self, mv):
        return None if mv[0] in ('pr', 'cv', 'gp') else mv[2]

    def es_cadena(self, mv):
        return mv[0] == 'ch'

    def es_captura(self, st, mv):
        return (mv[0] == 'ep' or (mv[0] == 'm' and st.b[mv[2]] is not None)
                or (mv[0] == 'ch' and any(c for _, c in mv[3])))

    def fin(self, st, movs, repeticiones, entrenamiento):
        """(motivo, ganador, detalle); ganador None = tablas."""
        if not movs:
            if M.in_check(st, st.turn):
                return 'Jaque mate', 1 - st.turn, ''
            return 'Ahogado', None, ''
        if repeticiones >= 3:
            motivo = 'Triple repetición'
        elif st.clock >= 100:
            motivo = 'Regla de las 50 jugadas'
        elif M.insufficient(st) and not entrenamiento:
            motivo = 'Material insuficiente'
        else:
            return None
        if entrenamiento:
            return motivo, None, ''
        a, b = st.pts
        detalle = 'Desempate por puntos: blancas %g, negras %g.' % (a, b)
        return motivo, (None if a == b else (0 if a > b else 1)), detalle

    def capturas(self, st, color):
        return [(t, False) for t in ORDEN_CAPTURAS for _ in range(st.capT[color].get(t, 0))]

    def puntos(self, st, color):
        return st.pts[color]

    def derechos(self, st, color):
        """Extensiones que el jugador puede ejercer (5.3 y 5.4)."""
        out = []
        propias = {p.t for p in st.b if p and p.c == color and not p.pr}
        for t in M.NEED:
            if t in propias and t not in st.tprom[color] and st.capT[color].get(t, 0) >= M.NEED[t]:
                out.append(NOMBRES[t])
        n = st.capP[color] // M.PEONES_POR_GUARDIAN - st.conv[color]
        if n > 0 and 'P' in propias:
            out.append('Peón → Guardián' + (' ×%d' % n if n > 1 else ''))
        n = st.capG[color] // M.GUARDIANES_POR_PROMOCION - st.gprom[color]
        if n > 0 and 'G' in propias:
            out.append('Guardián' + (' ×%d' % n if n > 1 else ''))
        return out

    def ajustar(self, t, c, pr, sq):
        if t in ('P', 'G') and sq // M.N == M.last_row(c):
            pr = True  # en la última fila ya estaría promocionado (5.2)
        return t, c, pr and t != 'K'

    def construir(self, piezas, turno):
        return construir_posicion(piezas, turno)


# ---------------------------------------------------------------------- variantes genéricas
class Generica(Variante):
    def __init__(self, cfg):
        self.cfg = cfg
        import tkinter
        if getattr(tkinter, '_default_root', None) is not None:  # diseños propios de otra computadora
            import disenos
            disenos.asegurar_cfg(cfg)
        self.m = G.Motor(cfg)
        self.id = cfg.get('id', 'laboratorio')
        self.nombre = cfg.get('nombre', 'Variante')
        self.resumen = cfg.get('descripcion', '')
        self.ancho, self.alto = cfg['ancho'], cfg['alto']
        self.tema = cfg.get('tema', 'madera')
        self.spec = {'tipo': 'generica', 'config': cfg}
        defs = cfg['piezas']
        self.paleta = sorted(defs, key=lambda t: (not defs[t].get('real'), bool(defs[t].get('peon')),
                                                  -self.m.valor[t], defs[t]['nombre']))
        self.rey = next((t for t in self.paleta if defs[t].get('real')), None)
        self.peon = next((t for t in self.paleta if defs[t].get('peon')), None)
        self.con_puntos = bool(self.m.reglas.get('desempate'))

    def inicial(self):
        return self.m.inicial()

    def legal(self, st):
        return self.m.legal(st)

    def en_jaque(self, st, c):
        return self.m.mate and self.m.en_jaque(st, c)

    def casilla_rey(self, st, c):
        return st.rey[c]

    def clave(self, st):
        return self.m.clave(st)

    def pieza(self, st, sq):
        p = st.b[sq]
        return None if p is None else (p[0], p[1], False)

    def imagen(self, t, c, pr=False):
        d = self.cfg['piezas'][t]
        return ruta_imagen(d['imagen'], c, d.get('dorada', False))

    def nombre_pieza(self, t, pr=False):
        return self.cfg['piezas'][t]['nombre']

    def _simbolo(self, t):
        return self.cfg['piezas'][t].get('simbolo', '')

    def notacion(self, st, mv, n, movs):
        k, b, name = mv[0], st.b, self.nombre_casilla
        if k == 'cs':
            return '0-0' if mv[3][0] % self.ancho > mv[1] % self.ancho else '0-0-0'
        frm, to = mv[1], mv[2]
        t = b[frm][0]
        if k == 'ex':  # extensión o conversión: Cc3=C' (como en el reglamento del Ajedrez Extendido)
            return '%s%s=%s' % (self._simbolo(t), name(frm), self._simbolo(mv[3]) or self.nombre_pieza(mv[3])[0])
        cap = self.m.es_captura(st, mv)
        if k == 'ch':  # saltos que capturan: Ct' f6xi6xg8
            return self._simbolo(t) + name(frm) + ''.join(('x' if c else '-') + name(l) for l, c in mv[3])
        if t in self.m.peones:
            s = (name(frm)[0] + 'x' if cap else '') + name(to)
        else:
            s = self._simbolo(t)
            otros = [m[1] for m, _ in movs if m[0] == k and m[2] == to and m[1] != frm and b[m[1]][0] == t]
            s += _desambiguar(frm, otros, self.ancho, name)
            s += ('x' if cap else '') + name(to)
        if k == 'ep':
            s += ' a.p.'
        elif k == 'm' and mv[3]:
            s += '=' + (self._simbolo(mv[3]) or self.nombre_pieza(mv[3])[0])
        elif k == 'm' and n is not None and n.b[to] is not None and n.b[to][0] != t:  # extensión por llegada
            s += '=' + (self._simbolo(n.b[to][0]) or self.nombre_pieza(n.b[to][0])[0])
        return s

    def descripcion(self, st, mv):
        k, name = mv[0], self.nombre_casilla
        if k == 'cs':
            return 'Enroque hacia la columna ' + G.LETRAS[mv[3][0] % self.ancho]
        if k == 'ep':
            return 'Capturar al paso en ' + name(mv[2])
        if k == 'ex':
            t = st.b[mv[1]][0]
            if self.cfg['piezas'][mv[3]].get('base') == t:
                return 'Extender %s de %s' % (self.nombre_pieza(t), name(mv[1]))
            return 'Convertir %s de %s en %s' % (self.nombre_pieza(t), name(mv[1]), self.nombre_pieza(mv[3]))
        if k == 'em':
            return 'Empujar %s de %s' % (self.nombre_pieza(st.b[mv[2]][0]), name(mv[2]))
        if k == 'in':
            return 'Intercambiar con %s de %s' % (self.nombre_pieza(st.b[mv[2]][0]), name(mv[2]))
        if k == 'ch':
            ncap = sum(len(c) for _, c in mv[3])
            if len(mv[3]) == 1:
                return 'Saltar a %s (captura %d)' % (name(mv[2]), ncap)
            return 'Cadena %s → %s (captura %d)' % (name(mv[1]), ' → '.join(name(l) for l, _ in mv[3]), ncap)
        if mv[3]:
            return 'Promocionar a ' + self.nombre_pieza(mv[3])
        q = st.b[mv[2]]
        return ('Capturar %s en %s' % (self.nombre_pieza(q[0]), name(mv[2]))) if q else 'Mover a ' + name(mv[2])

    def casillas(self, mv):
        k = mv[0]
        if k == 'cs':
            return {mv[1], mv[2], mv[3][0], mv[3][1]}
        if k == 'ex':
            return {mv[1]}
        if k == 'ch':
            return {mv[1]} | {l for l, _ in mv[3]}
        if k == 'em':
            return {mv[1], mv[2], mv[2] + (mv[2] - mv[1])}
        return {mv[1], mv[2]}

    def destino(self, mv):
        return None if mv[0] == 'ex' else mv[2]

    def es_cadena(self, mv):
        return mv[0] == 'ch'

    def derechos(self, st, color):
        """Extensiones y conversiones que el jugador puede ejercer (None si la variante no tiene)."""
        if not self.m.con_ext:
            return None
        out = []
        for t, nuevo, n in self.m.derechos(st, color):
            nombre = (self.nombre_pieza(t) if self.cfg['piezas'][nuevo].get('base') == t
                      else '%s → %s' % (self.nombre_pieza(t), self.nombre_pieza(nuevo)))
            out.append(nombre + (' ×%d' % n if n > 1 else ''))
        return out

    def es_captura(self, st, mv):
        return self.m.es_captura(st, mv)

    def fin(self, st, movs, repeticiones, entrenamiento):
        r = self.m.resultado(st, movs, repeticiones)
        if r is None:
            return None
        motivo, ganador = r
        if entrenamiento and motivo == 'Material insuficiente':
            return None
        if (ganador is None and self.con_puntos and not entrenamiento
                and motivo in ('Triple repetición', 'Regla de las 50 jugadas', 'Material insuficiente')):
            a, b = self.puntos(st, 0), self.puntos(st, 1)
            return motivo, (None if a == b else (0 if a > b else 1)), \
                'Desempate por puntos: blancas %g, negras %g.' % (a, b)
        return motivo, ganador, ''

    def capturas(self, st, color):
        orden = {t: i for i, t in enumerate(self.paleta)}
        return [(t, False) for t in sorted(st.cap[color], key=lambda t: orden.get(t, 99))]

    def puntos(self, st, color):
        return self.m.puntos_de(st, color)

    def ajustar(self, t, c, pr, sq):
        if sq // self.ancho == (self.alto - 1 if c == 0 else 0):
            if t in self.m.ext_llegada:  # en la última fila ya estaría extendida
                t = self.m.ext_llegada[t]
            elif t in self.m.peones and self.m.promo:
                t = self.m.promo[0]
        return t, c, False

    def construir(self, piezas, turno):
        return self.m.construir([p[:3] for p in piezas], turno)


def _desambiguar(frm, otros, ancho, name):
    return NT.desambiguar(frm, otros, ancho, name)


def crear(spec):
    if spec['tipo'] == 'extendido':
        return Extendido()
    return Generica(spec['config'])


def predefinidas():
    """Las cuatro variantes del menú principal, en orden."""
    return [Generica(copy.deepcopy(G.PRESETS['clasico'])), Extendido(),
            Generica(copy.deepcopy(G.PRESETS['capablanca'])), Generica(copy.deepcopy(G.PRESETS['gotico']))]


def predefinida(ident):
    return Extendido() if ident == 'extendido' else Generica(copy.deepcopy(G.PRESETS[ident]))


# la versión de 10 × 10 de las variantes del menú que la tienen
EN_10X10 = {'capablanca': 'capablanca10', 'gotico': 'gotico10'}


def otras():
    """Las variantes de «Más variantes» (Gran Ajedrez, Jano, Shatranj...)."""
    import presets
    return [predefinida(k) for k in presets.OTRAS]


def todas():
    """Todas las variantes predefinidas: las del menú, sus versiones de 10 × 10 y las de «Más variantes»."""
    return predefinidas() + [predefinida(k) for k in EN_10X10.values()] + otras()


# ---------------------------------------------------------------------- variantes del laboratorio
def _archivo(nombre):
    base = re.sub(r'[^a-z0-9]+', '_', nombre.lower()).strip('_') or 'variante'
    return os.path.join(LABORATORIO, base + '.json')


def guardadas():
    if not os.path.isdir(LABORATORIO):
        return []
    out = []
    for f in sorted(os.listdir(LABORATORIO)):
        if f.endswith('.json'):
            try:
                with open(os.path.join(LABORATORIO, f), encoding='utf-8') as fh:
                    out.append(json.load(fh))
            except (OSError, ValueError):
                pass
    return out


def guardar(cfg):
    os.makedirs(LABORATORIO, exist_ok=True)
    ruta = _archivo(cfg['nombre'])
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    return ruta


def borrar(cfg):
    ruta = _archivo(cfg['nombre'])
    if os.path.exists(ruta):
        os.remove(ruta)
