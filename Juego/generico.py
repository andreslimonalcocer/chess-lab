"""Motor genérico de variantes de ajedrez: clásico, Capablanca, gótico, el Ajedrez Extendido y las del laboratorio.

Una variante se describe con un diccionario (guardable como JSON):
    {'nombre': ..., 'ancho': 8, 'alto': 8, 'tema': 'madera',
     'piezas': {tipo: definición, ...},
     'posicion': [[columna, fila, tipo, color], ...],
     'reglas': {...}}
Cada pieza se define por sus movimientos ('movs'), una lista de componentes:
  {'dirs': 'orto'|'diag'|'todas', 'alcance': n}   desliza n casillas en esas direcciones (0 = sin límite);
      'salta': True  -> las piezas en medio no la bloquean;  'modo': 'ambos'|'mov'|'cap' (mueve y captura,
      solo mueve o solo captura; por defecto, ambos)
  {'salto': [a, b]}                               salta (a, b) en todas sus simetrías (el Caballo: [1, 2]);
      'repite': True -> repite el salto en línea mientras las casillas estén vacías (el Jinete nocturno)
  {'casillas': [[dc, dr, modo, salta, cond], ...], 'salta': b}  casillas sueltas relativas a la pieza, vistas
      desde las blancas (dr > 0 es hacia adelante; para las negras se reflejan). 'salta' (de cada casilla o, si
      falta, del componente): las piezas en medio no la bloquean. Sin saltar, las que están en línea recta
      necesitan el camino libre; las demás (como las del Caballo) se alcanzan siempre.
  Cualquiera de ellos puede llevar:
      'cond': 'primera' -> solo mientras la pieza conserva su primer avance y está en su fila de inicio
              'jaque'   -> solo si el propio rey está en jaque (y la jugada lo tapa); solo para moverse
      'come': True      -> captura las piezas adversarias sobre las que salta (el rey no se puede saltar)
Componentes especiales:
  {'pantalla': dirs, 'tras': 'justo'|'libre'|'primera', 'modo', 'come': b, 'pegada': b}  salta sobre una pieza
      (la pantalla): cae justo detrás (Saltamontes), en cualquier casilla detrás (León) o captura la primera
      pieza detrás (Cañón). Con 'come', captura la pantalla y cae justo detrás (Langosta). Con 'pegada', la
      pantalla tiene que estar junto a la pieza.
  {'secuencia': dirs, 'minimo': 2, 'come': b}      salta una fila continua de piezas (desde la casilla de al lado)
      hasta la primera casilla vacía (salto extendido de la Catapulta)
  {'cadena': dirs, 'fila': b}                      capturas en cadena: saltos de dos casillas sobre piezas
      adversarias, obligatorios mientras haya capturas (la Catapulta extendida, 4.8.5 del reglamento)
  {'empuje': [[dc, dr], ...], 'tipos': [...]}      empuja una pieza adversaria de esos tipos una casilla y ocupa
      su lugar (el Guardián)
  {'intercambio': [[dc, dr], ...], 'tipos': [...]} cambia su lugar con una pieza propia de esos tipos
  {'camino': [[[dc, dr, destino], ...], ...]}      recorridos casilla a casilla (piezas torcidas como el Mao o
      el Grifo, o curvas como la Rosa): cada casilla debe estar vacía para seguir; 'destino' dice si la pieza
      puede detenerse en ella
Un componente puede llevar 'de': tipo, si vino de combinar otra pieza (solo informativo, para el editor).
Propiedades de una pieza:
  'aura': [[dc, dr], ...]   ninguna pieza adversaria puede caer saltando en esas casillas; las piezas propias en
      ellas no se capturan al ser saltadas (el bloqueo de saltos del Guardián)
  'como_peon': True         sus avances en recto cuentan como de peón (regla de las 50 jugadas), conserva el
      primer avance aunque se mueva de lado, y captura y puede ser capturada al paso
  'extension': {'pieza': tipo, 'llegada': b, 'captura': n, 'repetir': b}   su forma extendida (otra pieza de la
      variante, con 'base': este tipo): al llegar a la última fila, o (costando el turno) tras capturar n piezas
      adversarias de su tipo; sin 'repetir', solo se extiende una de las propias
  'conversion': {'pieza': tipo, 'captura': n}  por cada n piezas adversarias de su tipo capturadas, una propia
      puede convertirse en esa pieza (costando el turno)
  'puntos': n               valor para el desempate por puntos (si no, el 'valor')
El peón y el rey tienen reglas propias (avance, captura al paso, promoción, enroque, jaque).
"""
import copy, math, random, time
from collections import Counter

LETRAS = 'abcdefghijklmnop'
ORTO = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))
DIRS = {'orto': ORTO, 'diag': DIAG, 'todas': ORTO + DIAG}
MATE = 100000
DESPRECIO = 0.5
IMAGENES = ['rey', 'dama', 'torre', 'alfil', 'caballo', 'arzobispo', 'canciller', 'catapulta', 'guardian', 'peon']

REGLAS_BASE = {
    'objetivo': 'mate',        # 'mate' o 'capturar_rey'
    'ahogado': 'tablas',       # 'tablas' o 'victoria' (gana quien ahoga)
    'enroque': True, 'pasos_enroque': 2,   # o [hacia la columna a, hacia la última columna]
    'doble_paso': True, 'al_paso': True,
    'pasos_peon': 2,           # casillas del primer avance del peón (con doble_paso)
    'promocion': ['Q', 'R', 'B', 'N'],
    'zona_promocion': 1,       # filas del final en las que el peón promociona
    'promocion_opcional': False,    # en la zona, salvo la última fila, puede seguir siendo peón
    'promocion_capturadas': False,  # solo a piezas propias que ya fueron capturadas (Gran Ajedrez)
    'cincuenta': True, 'repeticion': True, 'material': True,
    'desempate': False,        # tablas por repetición, 50 jugadas o material: gana quien tiene más puntos
}


def _p(nombre, simbolo, imagen, valor, movs, dorada=False, **extra):
    d = {'nombre': nombre, 'simbolo': simbolo, 'imagen': imagen, 'dorada': dorada, 'valor': valor, 'movs': movs}
    d.update(extra)
    return d


TORRE = [{'dirs': 'orto', 'alcance': 0}]
ALFIL = [{'dirs': 'diag', 'alcance': 0}]
CABALLO = [{'salto': [1, 2]}]
CATALOGO = {
    'K': _p('Rey', 'R', 'rey', 0, [{'dirs': 'orto', 'alcance': 1}, {'dirs': 'diag', 'alcance': 1}], real=True),
    'Q': _p('Dama', 'D', 'dama', 9, TORRE + ALFIL),
    'R': _p('Torre', 'T', 'torre', 5, TORRE, enroca=True),
    'B': _p('Alfil', 'A', 'alfil', 3.25, ALFIL),
    'N': _p('Caballo', 'C', 'caballo', 3, CABALLO),
    'P': _p('Peón', '', 'peon', 1, [], peon=True),
    'CA': _p('Arzobispo', 'Az', 'arzobispo', 7, ALFIL + CABALLO),
    'CH': _p('Canciller', 'Ch', 'canciller', 8.5, TORRE + CABALLO),
    'AM': _p('Amazona', 'Am', 'dama', 12, TORRE + ALFIL + CABALLO, dorada=True),
    'H': _p('Hombre', 'H', 'guardian', 3, [{'dirs': 'orto', 'alcance': 1}, {'dirs': 'diag', 'alcance': 1}]),
    'CM': _p('Camello', 'Cm', 'caballo', 2.5, [{'salto': [1, 3]}], dorada=True),
}


def preset(ident, nombre, descripcion, fila, reglas=None, alto=8, fila_peones=1):
    ancho = len(fila)
    tipos = set(fila) | {'P'}
    posicion = []
    for c, t in enumerate(fila):
        if t:
            posicion += [[c, 0, t, 0], [c, alto - 1, t, 1]]
    for c in range(ancho):
        posicion += [[c, fila_peones, 'P', 0], [c, alto - 1 - fila_peones, 'P', 1]]
    r = dict(REGLAS_BASE)
    r.update(reglas or {})
    return {'id': ident, 'nombre': nombre, 'descripcion': descripcion, 'ancho': ancho, 'alto': alto,
            'tema': 'madera', 'piezas': {t: copy.deepcopy(CATALOGO[t]) for t in CATALOGO if t in tipos},
            'posicion': posicion, 'reglas': r}


PRESETS = {
    'clasico': preset('clasico', 'Ajedrez clásico', 'El ajedrez de siempre: 8×8, 32 piezas.',
                      ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']),
    'capablanca': preset('capablanca', 'Ajedrez Capablanca', 'Tablero de 10×8 con Arzobispo y Canciller.',
                         ['R', 'N', 'CA', 'B', 'Q', 'K', 'B', 'CH', 'N', 'R'],
                         {'pasos_enroque': 3, 'promocion': ['Q', 'CH', 'CA', 'R', 'B', 'N']}),
    'gotico': preset('gotico', 'Ajedrez gótico', 'Capablanca con otra posición inicial, sin peones indefensos.',
                     ['R', 'N', 'B', 'Q', 'CH', 'K', 'CA', 'B', 'N', 'R'],
                     {'pasos_enroque': 3, 'promocion': ['Q', 'CH', 'CA', 'R', 'B', 'N']}),
}


def saltos_simetricos(a, b):
    return sorted({(sa * x, sb * y) for x, y in ((a, b), (b, a)) for sa in (1, -1) for sb in (1, -1)})


# clases de movimiento: rayo bloqueable, rayo que pasa por encima de las piezas, solo la casilla final (con el
# camino libre) y salto (una casilla que se alcanza saltando: la bloquea el aura de un Guardián)
DESLIZA, SALTA, EXACTA, SALTO = 0, 1, 2, 3
MODOS = ('ambos', 'mov', 'cap')
CONDICIONES = {'primera': 1, 'jaque': 2}
OPUESTA = (1, 0, 3, 2, 7, 6, 5, 4)  # índice de la dirección contraria en ORTO + DIAG
ESPECIALES = ('pantalla', 'secuencia', 'cadena', 'empuje', 'intercambio', 'camino')


def formas_completas(defn, ancho, alto, color=0):
    """Formas de movimiento de una pieza para un color: [(dc, dr, alcance, clase, modo, cond, come)].
    DESLIZA: todas las casillas del rayo hasta la primera ocupada; SALTA: todas hasta el alcance, sin bloqueo;
    EXACTA: solo la casilla a esa distancia, con el camino libre; SALTO: una casilla, saltando. El modo 'atq'
    solo ataca (la primera captura de una cadena)."""
    out = {}
    largo = max(ancho, alto)

    def poner(dc, dr, alc, clase, modo, cond=0, come=False):
        clave = (dc, dr, clase, modo, cond, come, alc if clase == EXACTA else None)
        out[clave] = max(out.get(clave, 0), alc)

    for m in defn.get('movs', []):
        cond = CONDICIONES.get(m.get('cond'), 0)
        come = bool(m.get('come'))
        modo = m.get('modo', 'ambos')
        if 'salto' in m:
            for dc, dr in saltos_simetricos(*m['salto']):
                if m.get('repite'):
                    poner(dc, dr, m.get('alcance', 0) or largo, DESLIZA, modo, cond)
                else:
                    poner(dc, dr, 1, SALTO, modo, cond)
        elif 'casillas' in m:
            for e in m['casillas']:
                dc, dr, md = e[0], e[1], e[2]
                salta = e[3] if len(e) > 3 and e[3] is not None else m.get('salta')
                cd = CONDICIONES.get(e[4], 0) if len(e) > 4 and e[4] else cond
                if (dc, dr) == (0, 0):
                    continue
                if color == 1:
                    dr = -dr
                g = math.gcd(abs(dc), abs(dr))
                en_linea = dc == 0 or dr == 0 or abs(dc) == abs(dr)
                if salta or not en_linea:
                    poner(dc, dr, 1, SALTO, md, cd, come and en_linea and g > 1)
                elif g == 1:
                    poner(dc, dr, 1, SALTA, md, cd)
                else:
                    poner(dc // g, dr // g, g, EXACTA, md, cd)
        elif 'dirs' in m:
            alc = m.get('alcance', 0) or largo
            for dc, dr in DIRS[m['dirs']]:
                poner(dc, dr, alc, SALTA if m.get('salta') else DESLIZA, modo, cond, come and bool(m.get('salta')))
        elif 'cadena' in m:
            for dc, dr in DIRS[m['cadena']]:
                poner(2 * dc, 2 * dr, 1, SALTO, 'atq')
    return sorted((dc, dr, alc, clase, modo, cond, come)
                  for (dc, dr, clase, modo, cond, come, _), alc in out.items())


def formas(defn, ancho, alto, color=0):
    """Formas sencillas [(dc, dr, alcance, clase, modo)] (los saltos como SALTA), sin las que solo atacan."""
    return [(dc, dr, alc, SALTA if clase == SALTO else clase, modo)
            for dc, dr, alc, clase, modo, _, _ in formas_completas(defn, ancho, alto, color) if modo != 'atq']


def es_simple(defn):
    """¿Movimientos «clásicos» (simétricos, que mueven y capturan igual, rayos bloqueables o saltos simples)?
    Solo esas piezas pueden tener tablas de finales (tablas_genericas.py)."""
    if defn.get('peon') or any(defn.get(k) for k in ('aura', 'como_peon', 'extension', 'conversion', 'base')):
        return False
    for m in defn.get('movs', []):
        if any(k in m for k in ESPECIALES) or m.get('cond') or m.get('come') or m.get('repite'):
            return False
        if any(len(e) > 4 and e[4] for e in m.get('casillas', [])):
            return False
    fs = formas(defn, 15, 15)
    if any(modo != 'ambos' or clase == EXACTA or (clase == SALTA and alc != 1) for _, _, alc, clase, modo in fs):
        return False
    conjunto = {(dc, dr, clase) for dc, dr, _, clase, _ in fs}
    return all((-dc, -dr, clase) in conjunto for dc, dr, clase in conjunto)


def _tr(texto):
    """Traducción de la interfaz (idioma.py), si está disponible (no lo está en el proceso de la computadora)."""
    global _traductor
    if _traductor is None:
        try:
            from idioma import tr
            _traductor = tr
        except Exception:
            _traductor = lambda x: x
    return _traductor(texto)


_traductor = None


def describir_movs(defn):
    """Resumen en texto de los movimientos de una pieza (para el Laboratorio y las reglas), ya traducido: cada
    parte se traduce por separado."""
    partes = []
    nombre_dirs = {'orto': 'recto', 'diag': 'diagonal', 'todas': 'recto y diagonal'}
    T = _tr
    for m in defn.get('movs', []):
        extra = ''
        if m.get('cond') == 'primera':
            extra += T(' (primer avance)')
        elif m.get('cond') == 'jaque':
            extra += T(' (solo para tapar un jaque)')
        if m.get('come'):
            extra += T(' (captura lo que salta)')
        if 'salto' in m:
            partes.append(T(('jinete %d-%d' if m.get('repite') else 'salto %d-%d') % tuple(m['salto'])) + extra)
        elif 'casillas' in m:
            n = len(m['casillas'])
            saltan = sum(1 for e in m['casillas'] if (e[3] if len(e) > 3 and e[3] is not None else m.get('salta')))
            texto = T('1 casilla propia' if n == 1 else '%d casillas propias' % n)
            if saltan == n:
                texto += T(' (salta)')
            elif saltan:
                texto += T(' (%d saltando)' % saltan)
            condicionadas = sum(1 for e in m['casillas'] if len(e) > 4 and e[4])
            if condicionadas:
                texto += T(' (%d con condición)' % condicionadas)
            partes.append(texto + extra)
        elif 'dirs' in m:
            texto = T(nombre_dirs[m['dirs']]) + (T(' hasta %d' % m['alcance']) if m.get('alcance') else '')
            if m.get('salta'):
                texto += T(' (salta)')
            if m.get('modo', 'ambos') != 'ambos':
                texto += T(' (solo mueve)' if m['modo'] == 'mov' else ' (solo captura)')
            partes.append(texto + extra)
        elif 'pantalla' in m:
            donde = T(nombre_dirs[m['pantalla']] if isinstance(m['pantalla'], str) else 'direcciones propias')
            tras = {'justo': 'cae justo detrás', 'libre': 'cae en cualquier casilla detrás',
                    'primera': 'captura la primera pieza detrás'}[m.get('tras', 'justo')]
            texto = (T('salta sobre una pieza en %s y la captura') % donde if m.get('come')
                     else T('salta sobre una pieza en %s y %s') % (donde, T(tras)))
            if m.get('pegada'):
                texto += T(' (pieza de al lado)')
            partes.append(texto)
        elif 'secuencia' in m:
            partes.append(T('salto sobre una fila de piezas en %s') % T(nombre_dirs[m['secuencia']]) +
                          (T(' (captura las adversarias)') if m.get('come') else ''))
        elif 'cadena' in m:
            partes.append(T('capturas en cadena en %s') % T(nombre_dirs[m['cadena']]))
        elif 'empuje' in m:
            partes.append(T('empuja piezas adversarias'))
        elif 'intercambio' in m:
            partes.append(T('se intercambia con piezas propias'))
        elif 'camino' in m:
            partes.append(T('%d recorridos propios' % len(m['camino'])))
    return ', '.join(partes)


def destinos_vacio(defn, ancho, alto, sq, color=0):
    """{casilla: modo} a las que llega la pieza desde sq en el tablero vacío."""
    out = {}
    c0, r0 = sq % ancho, sq // ancho

    def poner(c, r, modo):
        y = r * ancho + c
        previo = out.get(y)
        out[y] = modo if previo in (None, modo) else 'ambos'

    for dc, dr, alc, clase, modo in formas(defn, ancho, alto, color):
        ks = [alc] if clase == EXACTA else range(1, alc + 1)
        for k in ks:
            c, r = c0 + dc * k, r0 + dr * k
            if not (0 <= c < ancho and 0 <= r < alto):
                break
            poner(c, r, modo)
    for m in defn.get('movs', []):
        if 'camino' not in m:
            continue
        for camino in m['camino']:
            for dc, dr, destino in camino:
                c, r = c0 + dc, r0 + (dr if color == 0 else -dr)
                if not (0 <= c < ancho and 0 <= r < alto):
                    break
                if destino:
                    poner(c, r, m.get('modo', 'ambos'))
    return out


def valor_sugerido(defn, ancho, alto):
    """Valor aproximado por la movilidad media en el tablero vacío (Caballo ≈ 3, Torre ≈ 5, Dama ≈ 9)."""
    if defn.get('real'):
        return 0
    if defn.get('peon'):
        return 1
    total = 0
    for sq in range(ancho * alto):
        for modo in destinos_vacio(defn, ancho, alto, sq).values():
            total += 1 if modo == 'ambos' else 0.6  # solo mover o solo capturar vale menos
    movil = total / (ancho * alto) * (64 / (ancho * alto)) ** 0.25
    extra = 0.0
    for m in defn.get('movs', []):  # lo que el tablero vacío no muestra
        if 'pantalla' in m:
            extra += 1.0 if m['pantalla'] == 'todas' else 0.6
        elif 'cadena' in m or 'secuencia' in m:
            extra += 1.0
    return round(max(0.5, 0.36 * movil + 1.1 + extra) * 4) / 4


class Estado:
    __slots__ = ('b', 'turn', 'ep', 'reloj', 'rey', 'cap', 'usos')

    def copy(s):
        n = Estado.__new__(Estado)
        n.b, n.turn, n.ep, n.reloj, n.rey, n.cap, n.usos = s.b[:], s.turn, s.ep, s.reloj, s.rey[:], s.cap, s.usos
        return n


def _indices_dirs(nombre, color=0):
    """Índices en ORTO + DIAG de 'orto', 'diag', 'todas' o de una lista de direcciones [[dc, dr], ...] (vistas
    desde las blancas: para las negras se reflejan)."""
    if isinstance(nombre, str):
        return [i for i, d in enumerate(ORTO + DIAG) if d in DIRS[nombre]]
    todas = ORTO + DIAG
    return [todas.index((dc, dr if color == 0 else -dr)) for dc, dr in nombre if (dc, dr) in todas]


class Motor:
    """Reglas de una variante. Las piezas en el tablero son tuplas (tipo, color, movida, primer, marca):
    'primer' es la fila desde la que aún puede hacer su primer avance (o None) y 'marca', el último intercambio
    (para no deshacerlo)."""

    def __init__(self, cfg):
        self.cfg = cfg
        W, H = self.W, self.H = cfg['ancho'], cfg['alto']
        self.defs = cfg['piezas']
        self.reglas = dict(REGLAS_BASE)
        self.reglas.update(cfg.get('reglas', {}))
        self.real = {t for t, d in self.defs.items() if d.get('real')}
        self.peones = {t for t, d in self.defs.items() if d.get('peon')}
        self.berolina = {t for t in self.peones if self.defs[t].get('berolina')}  # avanzan en diagonal
        self.enroca = {t for t, d in self.defs.items() if d.get('enroca')}
        self.como_peon = {t for t, d in self.defs.items() if d.get('como_peon') and not d.get('peon')}
        self.base = {t: (d.get('base') if d.get('base') in self.defs else t) for t, d in self.defs.items()}
        self.valor = {t: float(d.get('valor') if d.get('valor') is not None else valor_sugerido(d, W, H))
                      for t, d in self.defs.items()}
        self.puntos = {t: float(d['puntos']) if d.get('puntos') is not None else self.valor[t]
                       for t, d in self.defs.items()}
        self.promo = [t for t in self.reglas['promocion']
                      if t in self.defs and t not in self.real and t not in self.peones]
        self.mate = self.reglas['objetivo'] == 'mate'
        self.pasos_peon = max(2, int(self.reglas.get('pasos_peon') or 2))
        self.zona = max(1, int(self.reglas.get('zona_promocion') or 1))
        # extensiones: por llegada (automáticas) y derechos que cuestan el turno
        self.ext_llegada = {}
        self.derechos_def = []  # [(tipo, nuevo tipo, capturas necesarias, se repite)]
        for t, d in self.defs.items():
            e = d.get('extension') or {}
            if e.get('pieza') in self.defs:
                if e.get('llegada'):
                    self.ext_llegada[t] = e['pieza']
                if e.get('captura'):
                    self.derechos_def.append((t, e['pieza'], max(1, int(e['captura'])), bool(e.get('repetir'))))
            c = d.get('conversion') or {}
            if c.get('pieza') in self.defs and c.get('captura'):
                self.derechos_def.append((t, c['pieza'], max(1, int(c['captura'])), True))
        self.con_ext = bool(self.derechos_def)
        self.usa_jaque = False
        # mov[t][color][sq]: [(rayo, clase, mueve, captura)] por los que se mueve la pieza t;
        # esp[t][color][sq]: lo mismo para las formas con condición o que capturan lo saltado
        self.mov, self.esp, self.dup, self.rayos = {}, {}, {}, {}
        grupos = [{}, {}]  # (dc, dr, alcance, clase) -> tipos que capturan así (para detectar ataques)
        grupos_cond = [{}, {}]  # lo mismo, para las que solo valen en el primer avance
        for t, d in self.defs.items():
            if t in self.peones:
                continue
            self.mov[t], self.esp[t] = [], []
            for color in (0, 1):
                fs = formas_completas(d, W, H, color)
                simples = [f for f in fs if not f[5] and not f[6] and f[4] != 'atq']
                otras = [f for f in fs if (f[5] or f[6]) and f[4] != 'atq']
                for dc, dr, alc, clase, modo, cond, come in fs:
                    if modo == 'mov' or cond == 2:  # las del jaque solo sirven para moverse
                        continue
                    (grupos_cond if cond == 1 else grupos)[color].setdefault((dc, dr, alc, clase), set()).add(t)
                if any(f[5] == 2 for f in otras):
                    self.usa_jaque = True
                self.mov[t].append([[(ray, f[3], f[4] != 'cap', f[4] != 'mov') for ray, f in self._rayos(sq, simples)]
                                    for sq in range(W * H)])
                esp = []
                for sq in range(W * H):
                    lista = []
                    for ray, f in self._rayos(sq, otras):
                        medio = None
                        if f[6] and f[3] == SALTO:  # casillas que se saltan en línea recta
                            g = math.gcd(abs(f[0]), abs(f[1]))
                            medio = [sq + (f[1] // g) * k * W + (f[0] // g) * k for k in range(1, g)]
                        lista.append((ray, f[3], f[4] != 'cap', f[4] != 'mov', f[5], f[6], medio))
                    esp.append(lista)
                self.esp[t].append(esp)
            # ¿pueden dos formas llegar a la misma casilla? Entonces se quitan las jugadas repetidas
            centro = (H // 2) * W + W // 2
            vistas = [y for ray, clase, _, _ in self.mov[t][0][centro]
                      for y in (ray[-1:] if clase == EXACTA else ray)]
            vistas += [y for ray, clase, *_ in self.esp[t][0][centro] for y in (ray[-1:] if clase == EXACTA else ray)]
            self.dup[t] = len(vistas) != len(set(vistas)) or bool(self.esp[t][0][centro])
            if es_simple(d):  # rayos clásicos (para las tablas de finales)
                self.rayos[t] = [[ray for ray, _, _, _ in self.mov[t][0][sq]] for sq in range(W * H)]
        # ataques[color][sq]: [(rayo desde sq hacia el atacante, clase, tipos)]
        self.ataques = [[[(ray, clase, frozenset(ts))
                          for (dc, dr, alc, clase), ts in grupos[color].items()
                          for ray, _ in self._rayos(sq, [(-dc, -dr, alc, clase)])]
                         for sq in range(W * H)] for color in (0, 1)]
        self.ataques_cond = [[[(ray, clase, frozenset(ts))
                               for (dc, dr, alc, clase), ts in grupos_cond[color].items()
                               for ray, _ in self._rayos(sq, [(-dc, -dr, alc, clase)])]
                              for sq in range(W * H)] for color in (0, 1)]
        self._preparar_especiales()
        cx, cy = (W - 1) / 2, (H - 1) / 2
        self.centro = [max(cx, cy) - max(abs(sq % W - cx), abs(sq // W - cy)) for sq in range(W * H)]
        rnd = random.Random(2024)
        self.zob = {(sq, t, c): rnd.getrandbits(62) for sq in range(W * H) for t in self.defs for c in (0, 1)}
        self.zturno = rnd.getrandbits(62)
        self.originales = {(r * W + c, t, col) for c, r, t, col in cfg['posicion']}
        self.material0 = max(1.0, max(sum(self.valor[t] for c, r, t, col in cfg['posicion']
                                          if col == lado and t not in self.real) for lado in (0, 1)))

    def _rayos(self, sq, fs):
        """[(rayo, forma)] desde sq para cada forma (dc, dr, alcance, clase, ...). El rayo de EXACTA es el camino
        completo (la última casilla es el destino) y solo existe si cabe en el tablero."""
        W, H = self.W, self.H
        c0, r0 = sq % W, sq // W
        out = []
        for f in fs:
            dc, dr, a, clase = f[0], f[1], f[2], f[3]
            ray = []
            k = 1
            while k <= a and 0 <= c0 + dc * k < W and 0 <= r0 + dr * k < H:
                ray.append((r0 + dr * k) * W + c0 + dc * k)
                k += 1
            if ray and (clase != EXACTA or len(ray) == a):
                out.append((ray, f))
        return out

    def _preparar_especiales(self):
        """Tablas de los componentes especiales (pantallas, secuencias, cadenas, empujes, intercambios,
        recorridos) y de las auras."""
        W, H = self.W, self.H
        NN = W * H
        self.rayos8 = []  # rayos8[sq][i]: rayo completo en la dirección i de ORTO + DIAG
        for sq in range(NN):
            c0, r0 = sq % W, sq // W
            fila = []
            for dc, dr in ORTO + DIAG:
                ray, c, r = [], c0 + dc, r0 + dr
                while 0 <= c < W and 0 <= r < H:
                    ray.append(r * W + c)
                    c += dc
                    r += dr
                fila.append(ray)
            self.rayos8.append(fila)

        def vec(dc, dr, color):
            return (dc, dr if color == 0 else -dr)

        self.pantallas, self.secuencias, self.cadenas = {}, {}, {}
        self.empujes, self.intercambios, self.caminos = {}, {}, {}
        atq_pantallas = [{}, {}]
        atq_caminos = [[{} for _ in range(NN)] for _ in (0, 1)]
        for t, d in self.defs.items():
            if t in self.peones:
                continue
            for m in d.get('movs', []):
                modo = m.get('modo', 'ambos')
                if 'pantalla' in m:
                    come = bool(m.get('come'))
                    comp = ([_indices_dirs(m['pantalla'], c) for c in (0, 1)], m.get('tras', 'justo'),
                            modo != 'cap' and not come, modo != 'mov' or come, come, bool(m.get('pegada')))
                    self.pantallas.setdefault(t, []).append(comp)
                    if comp[3]:
                        for color in (0, 1):
                            for i in comp[0][color]:
                                atq_pantallas[color].setdefault((i, comp[1], come, comp[5]), set()).add(t)
                elif 'secuencia' in m:
                    self.secuencias.setdefault(t, []).append((_indices_dirs(m['secuencia']),
                                                              max(1, int(m.get('minimo', 2))), bool(m.get('come'))))
                elif 'cadena' in m:
                    self.cadenas.setdefault(t, []).append((DIRS[m['cadena']], m.get('fila', True)))
                elif 'empuje' in m:
                    self.empujes.setdefault(t, []).append(([[vec(dc, dr, c) for dc, dr in m['empuje']] for c in (0, 1)],
                                                           set(m.get('tipos') or [])))
                elif 'intercambio' in m:
                    self.intercambios.setdefault(t, []).append(
                        ([[vec(dc, dr, c) for dc, dr in m['intercambio']] for c in (0, 1)], set(m.get('tipos') or [])))
                elif 'camino' in m:
                    porcol = []
                    for color in (0, 1):
                        tabla = []
                        for sq in range(NN):
                            c0, r0 = sq % W, sq // W
                            lista = []
                            for camino in m['camino']:
                                casillas, mascara = [], []
                                for dc, dr, destino in camino:
                                    c, r = c0 + dc, r0 + (dr if color == 0 else -dr)
                                    if not (0 <= c < W and 0 <= r < H):
                                        break
                                    casillas.append(r * W + c)
                                    mascara.append(bool(destino))
                                if any(mascara):
                                    lista.append((casillas, mascara))
                            tabla.append(lista)
                            if modo != 'mov':
                                for casillas, mascara in lista:
                                    for j, (s, destino) in enumerate(zip(casillas, mascara)):
                                        if destino:
                                            atq_caminos[color][s].setdefault((sq, tuple(casillas[:j])), set()).add(t)
                        porcol.append(tabla)
                    self.caminos.setdefault(t, []).append((porcol, modo != 'cap', modo != 'mov'))
        self.atq_pantallas = [[(i, tras, come, pegada, frozenset(ts)) for (i, tras, come, pegada), ts in g.items()]
                              for g in atq_pantallas]
        self.atq_caminos = [[[(a, medio, frozenset(ts)) for (a, medio), ts in casilla.items()] for casilla in color]
                            for color in atq_caminos]
        self.especial = set(self.pantallas) | set(self.secuencias) | set(self.cadenas) | set(self.empujes) | \
            set(self.intercambios) | set(self.caminos)
        self.extra_atq = bool(any(any(x for x in col) for col in self.ataques_cond) or any(self.atq_pantallas) or
                              any(any(x for x in col) for col in self.atq_caminos))
        # auras: aura_cub[t][color][sq] = casillas que cubre; aura_inv[color][sq] = [(casilla, tipos)] desde las
        # que una pieza con aura de ese color cubre sq
        self.aura_cub = {}
        inv = [[{} for _ in range(NN)] for _ in (0, 1)]
        for t, d in self.defs.items():
            if not d.get('aura'):
                continue
            porcol = []
            for color in (0, 1):
                tabla = []
                for sq in range(NN):
                    c0, r0 = sq % W, sq // W
                    cub = []
                    for dc, dr in d['aura']:
                        c, r = c0 + dc, r0 + (dr if color == 0 else -dr)
                        if 0 <= c < W and 0 <= r < H and (c, r) != (c0, r0):
                            cub.append(r * W + c)
                            inv[color][r * W + c].setdefault(sq, set()).add(t)
                    tabla.append(cub)
                porcol.append(tabla)
            self.aura_cub[t] = porcol
        self.aura_inv = [[[(s, frozenset(ts)) for s, ts in casilla.items()] for casilla in color]
                         for color in inv] if self.aura_cub else None

    # -------------------------------------------------------------- posiciones
    def pieza(self, t, color, movida=True, primer=None):
        return (t, color, movida, primer, None)

    def inicial(self):
        return self.construir([[r * self.W + c, t, col] for c, r, t, col in self.cfg['posicion']], 0)

    def construir(self, piezas, turno):
        """piezas: [[casilla, tipo, color], ...]. Las piezas en su casilla original conservan el enroque
        y los peones en su segunda fila, el doble paso."""
        W, H = self.W, self.H
        st = Estado.__new__(Estado)
        st.b = [None] * (W * H)
        st.rey = [None, None]
        usos = [[0] * len(self.derechos_def), [0] * len(self.derechos_def)]
        for sq, t, c, *_ in piezas:
            r = sq // W
            inicio = 1 if c == 0 else H - 2
            original = (sq, t, c) in self.originales
            if t in self.peones:
                movida = r != inicio and not original
            else:
                movida = not original
            primer = r if (original or ((t in self.peones or t in self.como_peon) and r == inicio)) else None
            st.b[sq] = (t, c, movida, primer, None)
            if t in self.real and st.rey[c] is None:
                st.rey[c] = sq
            base = self.base[t]
            if base != t:  # una pieza ya extendida: se gastó el derecho que no se repite
                for i, (x, nuevo, n, repetir) in enumerate(self.derechos_def):
                    if x == base and nuevo == t and not repetir:
                        usos[c][i] = 1
        st.turn, st.ep, st.reloj, st.cap = turno, None, 0, ((), ())
        st.usos = (tuple(usos[0]), tuple(usos[1]))
        return st

    def clave(self, st):
        if self.con_ext:
            cuenta = tuple(tuple(sorted(Counter(self.base[t] for t in st.cap[c]).items())) for c in (0, 1))
            return (tuple(st.b), st.turn, st.ep, cuenta, st.usos)
        return (tuple(st.b), st.turn, st.ep)

    def zhash(self, st):
        h = self.zturno if st.turn else 0
        for sq, p in enumerate(st.b):
            if p is not None:
                h ^= self.zob[(sq, p[0], p[1])]
        if st.ep:
            h ^= st.ep[0] * 7919
        if self.con_ext and (st.usos[0] or st.usos[1]):
            h ^= hash(st.usos) & 0x3FFFFFFFFFFFFFFF
        return h

    # -------------------------------------------------------------- ataques
    def cubierta(self, b, sq, color):
        """¿Está sq en el aura de una pieza de ese color? (Las del otro bando no pueden caer ahí saltando.)"""
        for s, tipos in self.aura_inv[color][sq]:
            q = b[s]
            if q is not None and q[1] == color and q[0] in tipos:
                return True
        return False

    def bloqueos(self, b, color):
        """Casillas cubiertas por las auras de las piezas de ese color."""
        out = set()
        cub = self.aura_cub
        for sq, p in enumerate(b):
            if p is not None and p[1] == color and p[0] in cub:
                out.update(cub[p[0]][color][sq])
        return out

    def atacada(self, b, sq, por):
        W = self.W
        f = 1 if por == 0 else -1
        r = sq // W - f
        if 0 <= r < self.H:
            for c in (sq % W - 1, sq % W + 1):
                if 0 <= c < W:
                    q = b[r * W + c]
                    if q is not None and q[1] == por and q[0] in self.peones and q[0] not in self.berolina:
                        return True
            if self.berolina:  # el peón de Berolina captura en recto
                q = b[r * W + sq % W]
                if q is not None and q[1] == por and q[0] in self.berolina:
                    return True
        bloq = self.aura_inv is not None and self.cubierta(b, sq, 1 - por)
        for ray, clase, tipos in self.ataques[por][sq]:
            if clase == DESLIZA:
                for s in ray:
                    q = b[s]
                    if q is not None:
                        if q[1] == por and q[0] in tipos:
                            return True
                        break
            elif clase == SALTO:
                if bloq:
                    continue
                q = b[ray[0]]
                if q is not None and q[1] == por and q[0] in tipos:
                    return True
            elif clase == SALTA:
                libre = True
                for s in ray:
                    q = b[s]
                    if q is not None:
                        if q[1] == por and q[0] in tipos and (libre or not bloq):
                            return True
                        libre = False
            else:  # EXACTA: el atacante al final del camino, con el camino libre
                q = b[ray[-1]]
                if q is not None and q[1] == por and q[0] in tipos and all(b[s] is None for s in ray[:-1]):
                    return True
        if self.extra_atq:
            return self._atacada_extra(b, sq, por, bloq)
        return False

    def _atacada_extra(self, b, sq, por, bloq):
        """Ataques de las formas del primer avance, de los recorridos y de las piezas que saltan pantallas."""
        W = self.W
        for ray, clase, tipos in self.ataques_cond[por][sq]:
            if clase == SALTO and bloq:
                continue
            if clase == EXACTA:
                cand = [ray[-1]] if all(b[s] is None for s in ray[:-1]) else []
            elif clase == DESLIZA:
                cand = []
                for s in ray:
                    if b[s] is not None:
                        cand = [s]
                        break
            else:
                cand = [s for s in ray if b[s] is not None]
            for s in cand:
                q = b[s]
                if q[1] == por and q[0] in tipos and q[3] == s // W:
                    return True
        for a, medio, tipos in self.atq_caminos[por][sq]:
            q = b[a]
            if q is not None and q[1] == por and q[0] in tipos and all(b[s] is None for s in medio):
                return True
        if bloq or not self.atq_pantallas[por]:
            return False
        for i, tras, come, pegada, tipos in self.atq_pantallas[por]:
            atras = self.rayos8[sq][OPUESTA[i]]  # de sq hacia el atacante
            if come:  # la Langosta captura la pantalla (sq) y cae justo detrás: sq + dirección vacía
                delante = self.rayos8[sq][i]
                if not delante or b[delante[0]] is not None or (
                        self.aura_inv is not None and self.cubierta(b, delante[0], 1 - por)):
                    continue
                for k, s in enumerate(atras):
                    q = b[s]
                    if q is not None:
                        if q[1] == por and q[0] in tipos:
                            return True
                        break
                    if pegada:
                        break
                continue
            if tras == 'justo':  # la pantalla está justo antes de sq
                if not atras or b[atras[0]] is None:
                    continue
                for s in atras[1:]:
                    q = b[s]
                    if q is not None:
                        if q[1] == por and q[0] in tipos:
                            return True
                        break
                    if pegada:
                        break
            else:  # 'libre' y 'primera': sq es la primera pieza tras la pantalla
                k = 0
                while k < len(atras) and b[atras[k]] is None:
                    k += 1
                k += 1  # la pantalla
                inicio = k
                while k < len(atras) and b[atras[k]] is None:
                    if pegada:
                        break
                    k += 1
                if k < len(atras) and (not pegada or k == inicio):
                    q = b[atras[k]]
                    if q is not None and q[1] == por and q[0] in tipos:
                        return True
        return False

    def en_jaque(self, st, color):
        k = st.rey[color]
        return k is not None and self.atacada(st.b, k, 1 - color)

    # -------------------------------------------------------------- jugadas
    def pseudo(self, st):
        """Jugadas sin comprobar si dejan al propio rey en jaque: ('m', de, a, promo), ('ep', de, a,
        víctima), ('cs', rey_de, rey_a, (torre_de, torre_a)), ('ch', de, a, ((llegada, capturadas), ...)) (saltos
        que capturan otras casillas, como las cadenas de la Catapulta), ('em', de, a, None) (empuje),
        ('in', de, a, None) (intercambio) y ('ex', casilla, None, nuevo tipo) (extensión o conversión)."""
        W, H, b, me = self.W, self.H, st.b, st.turn
        out = []
        ultima = H - 1 if me == 0 else 0
        blk = self.bloqueos(b, 1 - me) if self.aura_cub else None
        chk = self.en_jaque(st, me) if self.usa_jaque else False
        if self.reglas.get('promocion_capturadas'):
            self._perdidas = self.perdidas(st, me)
        for sq, p in enumerate(b):
            if p is None or p[1] != me:
                continue
            t = p[0]
            if t in self.peones:
                self._peon_jugadas(out, st, sq, p)
                continue
            inicio = len(out)
            for ray, clase, mueve, captura in self.mov[t][me][sq]:
                if clase == DESLIZA:
                    for s in ray:
                        q = b[s]
                        if q is None:
                            if mueve:
                                out.append(('m', sq, s, None))
                            continue
                        if q[1] != me and captura:
                            out.append(('m', sq, s, None))
                        break
                elif clase == SALTO:
                    s = ray[0]
                    if blk is not None and s in blk:
                        continue
                    q = b[s]
                    if q is None:
                        if mueve:
                            out.append(('m', sq, s, None))
                    elif q[1] != me and captura:
                        out.append(('m', sq, s, None))
                elif clase == SALTA:
                    salto = False
                    for s in ray:
                        q = b[s]
                        if q is None:
                            if mueve and not (salto and blk is not None and s in blk):
                                out.append(('m', sq, s, None))
                        else:
                            if q[1] != me and captura and not (salto and blk is not None and s in blk):
                                out.append(('m', sq, s, None))
                            salto = True
                else:  # EXACTA
                    if any(b[s] is not None for s in ray[:-1]):
                        continue
                    s = ray[-1]
                    q = b[s]
                    if (q is None and mueve) or (q is not None and q[1] != me and captura):
                        out.append(('m', sq, s, None))
            if self.esp[t][me][sq]:
                self._formas_especiales(out, st, sq, p, blk, chk)
            if t in self.especial:
                self._especiales(out, st, sq, p, blk, inicio)
            if t in self.como_peon and st.ep and self.reglas['al_paso']:
                f = W if me == 0 else -W
                for dc in (-1, 1):
                    c = sq % W + dc
                    to = sq + f + dc
                    if 0 <= c < W and 0 <= to < W * H and to == st.ep[0] and b[to] is None and st.ep[1] == sq + dc:
                        out.append(('ep', sq, to, st.ep[1]))
            if self.dup[t] and len(out) - inicio > 1:  # formas que llegan a la misma casilla
                vistas, unicas = set(), []
                for mv in out[inicio:]:
                    k = mv[2] if mv[0] == 'm' else mv
                    if k not in vistas:
                        vistas.add(k)
                        unicas.append(mv)
                out[inicio:] = unicas
            if t in self.real and not p[2] and self.reglas['enroque'] and not self.en_jaque(st, me):
                self._enroques(out, st, sq)
        if self.con_ext:
            self._derechos(out, st)
        return out

    def _peon_jugadas(self, out, st, sq, p):
        W, H, b, me = self.W, self.H, st.b, st.turn
        f = W if me == 0 else -W
        one = sq + f
        if p[0] in self.berolina:  # avanza en diagonal (dos la primera vez) y captura en recto
            if 0 <= one < W * H:
                q = b[one]
                if q is not None and q[1] != me:
                    self._peon(out, sq, one, me)
                for dc in (-1, 1):
                    c = sq % W + dc
                    if 0 <= c < W and b[one + dc] is None:
                        self._peon(out, sq, one + dc, me)
                        dos = one + dc + f + dc
                        if (self.reglas['doble_paso'] and p[3] == sq // W and 0 <= c + dc < W
                                and 0 <= dos < W * H and b[dos] is None):
                            self._peon(out, sq, dos, me)
            return
        if 0 <= one < W * H and b[one] is None:
            self._peon(out, sq, one, me)
            if self.reglas['doble_paso'] and p[3] == sq // W:
                s = one
                for _ in range(self.pasos_peon - 1):
                    s += f
                    if not (0 <= s < W * H) or b[s] is not None:
                        break
                    self._peon(out, sq, s, me)
        for dc in (-1, 1):
            c = sq % W + dc
            if 0 <= c < W and 0 <= one < W * H:
                to = one + dc
                q = b[to]
                if q is not None and q[1] != me:
                    self._peon(out, sq, to, me)
                elif (q is None and st.ep and st.ep[0] == to and self.reglas['al_paso']
                      and st.ep[1] == sq + dc):
                    out.append(('ep', sq, to, st.ep[1]))

    def _peon(self, out, de, a, color):
        """Avance o captura de peón: con las promociones si llega a la zona de promoción."""
        H, W = self.H, self.W
        fila = a // W
        desde_final = H - 1 - fila if color == 0 else fila
        if desde_final >= self.zona or not self.promo:
            out.append(('m', de, a, None))
            return
        opciones = self.promo
        if self.reglas.get('promocion_capturadas'):  # solo piezas propias que el rival ya capturó
            opciones = [t for t in self.promo if t in self._perdidas]
        if not opciones:
            if desde_final > 0:  # en la zona sin pieza a la que promocionar: sigue siendo peón
                out.append(('m', de, a, None))
            return  # a la última fila solo se llega promocionando
        if desde_final > 0 and self.reglas.get('promocion_opcional'):
            out.append(('m', de, a, None))
        for t in opciones:
            out.append(('m', de, a, t))

    def _enroques(self, out, st, sq):
        W, b, me = self.W, st.b, st.turn
        c0, fila = sq % W, sq // W
        pasos = self.reglas['pasos_enroque']
        for d in (-1, 1):
            k = (pasos[0] if d < 0 else pasos[1]) if isinstance(pasos, (list, tuple)) else pasos
            c = c0 + d
            while 0 <= c < W and b[fila * W + c] is None:
                c += d
            if not (0 <= c < W):
                continue
            q = b[fila * W + c]
            if q[1] != me or q[0] not in self.enroca or q[2] or d * (c - c0) <= k:
                continue
            if any(self.atacada(b, fila * W + c0 + d * i, 1 - me) for i in range(1, k + 1)):
                continue
            destino = fila * W + c0 + d * k
            out.append(('cs', sq, destino, (fila * W + c, destino - d)))

    def _formas_especiales(self, out, st, sq, p, blk, chk):
        """Formas con condición (primer avance, tapar un jaque) o que capturan las piezas que saltan."""
        W, b, me = self.W, st.b, st.turn
        for ray, clase, mueve, captura, cond, come, medio in self.esp[p[0]][me][sq]:
            if cond == 1 and p[3] != sq // W:
                continue
            if cond == 2 and not chk:
                continue
            if clase == DESLIZA:
                for s in ray:
                    q = b[s]
                    if q is None:
                        if mueve:
                            out.append(('m', sq, s, None))
                        continue
                    if q[1] != me and captura:
                        out.append(('m', sq, s, None))
                    break
            elif clase == EXACTA:
                if any(b[s] is not None for s in ray[:-1]):
                    continue
                s = ray[-1]
                q = b[s]
                if (q is None and mueve) or (q is not None and q[1] != me and captura):
                    out.append(('m', sq, s, None))
            elif not come:  # SALTO o SALTA sin capturar lo saltado
                salto = clase == SALTO
                for s in ray:
                    q = b[s]
                    vale = not (salto and blk is not None and s in blk)
                    if q is None:
                        if mueve and vale:
                            out.append(('m', sq, s, None))
                    else:
                        if q[1] != me and captura and vale:
                            out.append(('m', sq, s, None))
                        salto = True
            else:  # captura las piezas adversarias que salta (salvo las protegidas por un aura); el rey no se salta
                saltadas = list(medio) if clase == SALTO else []
                for s in ray:
                    if any(b[x] is not None and b[x][1] != me and b[x][0] in self.real for x in saltadas):
                        break
                    q = b[s]
                    hay = any(b[x] is not None for x in saltadas)
                    if not (hay and blk is not None and s in blk) and (
                            (q is None and mueve) or (q is not None and q[1] != me and captura)):
                        caps = [x for x in saltadas if b[x] is not None and b[x][1] != me
                                and not (blk is not None and x in blk)]
                        if caps:
                            if q is not None:
                                caps.append(s)
                            out.append(('ch', sq, s, ((s, tuple(caps)),)))
                        else:
                            out.append(('m', sq, s, None))
                    saltadas.append(s)

    def _especiales(self, out, st, sq, p, blk, inicio):
        W, H, b, me = self.W, self.H, st.b, st.turn
        t = p[0]
        rayos = self.rayos8[sq]
        for dirs, tras, mueve, captura, come, pegada in self.pantallas.get(t, ()):
            for i in dirs[me]:
                ray = rayos[i]
                k = 0
                while k < len(ray) and b[ray[k]] is None:
                    k += 1
                if k >= len(ray) or (pegada and k > 0):
                    continue
                pantalla = ray[k]
                if come:  # Langosta: captura la pantalla adversaria y cae justo detrás
                    q = b[pantalla]
                    if q[1] == me or (blk is not None and pantalla in blk):
                        continue
                    if k + 1 < len(ray) and b[ray[k + 1]] is None and not (blk is not None and ray[k + 1] in blk):
                        out.append(('ch', sq, ray[k + 1], ((ray[k + 1], (pantalla,)),)))
                    continue
                resto = ray[k + 1:]
                if tras == 'justo':
                    resto = resto[:1]
                for s in resto:
                    q = b[s]
                    vale = blk is None or s not in blk
                    if q is None:
                        if mueve and vale and tras != 'primera':
                            out.append(('m', sq, s, None))
                        continue
                    if q[1] != me and captura and vale:
                        out.append(('m', sq, s, None))
                    break
        for dirs, minimo, come in self.secuencias.get(t, ()):
            for i in dirs:
                ray = rayos[i]
                k = 0
                while k < len(ray) and b[ray[k]] is not None:
                    k += 1
                if k < minimo or k >= len(ray):
                    continue
                destino = ray[k]
                if blk is not None and destino in blk:
                    continue
                if come:
                    fila = ray[:k]
                    if any(b[x][1] != me and b[x][0] in self.real for x in fila):
                        continue
                    rivales = [x for x in fila if b[x][1] != me]
                    if rivales and not (blk is not None and any(x in blk for x in rivales)):
                        out.append(('ch', sq, destino, ((destino, tuple(rivales)),)))
                        continue
                out.append(('m', sq, destino, None))
        for vecs, tipos in self.empujes.get(t, ()):
            for dc, dr in vecs[me]:
                c, r = sq % W + dc, sq // W + dr
                if not (0 <= c < W and 0 <= r < H):
                    continue
                i = r * W + c
                q = b[i]
                if q is None or q[1] == me or q[0] not in tipos:
                    continue
                c2, r2 = c + dc, r + dr
                if 0 <= c2 < W and 0 <= r2 < H and b[r2 * W + c2] is None:
                    out.append(('em', sq, i, None))
        for vecs, tipos in self.intercambios.get(t, ()):
            for dc, dr in vecs[me]:
                c, r = sq % W + dc, sq // W + dr
                if not (0 <= c < W and 0 <= r < H):
                    continue
                i = r * W + c
                q = b[i]
                if q is None or q[1] != me or q[0] not in tipos:
                    continue
                if p[4] is not None and p[4] == (i, sq) and q[4] == (i, sq):
                    continue  # no se deshace el intercambio con la misma pieza
                out.append(('in', sq, i, None))
        for porcol, mueve, captura in self.caminos.get(t, ()):
            for casillas, mascara in porcol[me][sq]:
                for s, destino in zip(casillas, mascara):
                    q = b[s]
                    if destino:
                        if q is None:
                            if mueve:
                                out.append(('m', sq, s, None))
                            continue
                        if q[1] != me and captura:
                            out.append(('m', sq, s, None))
                        break
                    if q is not None:
                        break
        for dirs, secuencia in self.cadenas.get(t, ()):
            # un salto recto de dos sobre una pieza siempre es parte de la cadena (que decide si captura)
            c0, r0 = sq % W, sq // W
            sobre = set()
            for dc, dr in dirs:
                if 0 <= c0 + 2 * dc < W and 0 <= r0 + 2 * dr < H and b[(r0 + dr) * W + c0 + dc] is not None:
                    sobre.add((r0 + 2 * dr) * W + c0 + 2 * dc)
            if sobre:
                out[inicio:] = [mv for mv in out[inicio:] if not (mv[0] == 'm' and mv[2] in sobre)]
            simples = {mv[2] for mv in out[inicio:] if mv[0] == 'm'}
            for mv in self._cadenas(st, sq, dirs, secuencia):
                pasos = mv[3]
                if len(pasos) == 1 and not pasos[0][1] and pasos[0][0] in simples:
                    continue  # un salto sin capturas que ya es una jugada normal
                out.append(mv)

    def _saltar(self, st, de, a, caps):
        n = st.copy()
        for c in caps:
            self._capturar(n, c, st.turn)
        p = n.b[de]
        n.b[de] = None
        n.b[a] = p
        return n

    def _cadenas(self, st, sq, dirs, secuencia=True):
        """Capturas en cadena (4.8.5 del reglamento): el primer salto es uno recto de dos casillas (captura la
        intermedia y la de llegada) o un salto sobre una fila de piezas (captura las adversarias); después,
        saltos de dos sobre una pieza adversaria hasta una casilla vacía, obligatorios mientras haya. Las piezas
        en el aura de una adversaria no se capturan al ser saltadas y no se puede caer en ellas; el rey
        adversario no se salta; la cadena termina si da jaque."""
        W, H = self.W, self.H
        b, me = st.b, st.turn
        opp = 1 - me
        cub = (lambda bb, x: self.cubierta(bb, x, opp)) if self.aura_inv is not None else (lambda bb, x: False)
        c0, r0 = sq % W, sq // W
        inicios = []
        for dc, dr in dirs:
            ci, ri, cd, rd = c0 + dc, r0 + dr, c0 + 2 * dc, r0 + 2 * dr
            if not (0 <= cd < W and 0 <= rd < H):
                continue
            I, D = ri * W + ci, rd * W + cd
            qi, qd = b[I], b[D]
            if qi is not None and qi[1] == opp and qi[0] in self.real:
                continue
            if not (qd is not None and (qd[1] == me or qd[0] in self.real)) and not cub(b, D):
                saltadas = [I] if (qi is not None and qi[1] == opp) else []
                caps = [] if any(cub(b, x) for x in saltadas) else list(saltadas)
                if qd is not None and qd[1] == opp:
                    caps.append(D)
                if caps or qi is not None:
                    inicios.append((D, caps))
            if not secuencia:
                continue
            c, r = ci, ri
            fila = []
            while 0 <= c < W and 0 <= r < H and b[r * W + c] is not None:
                fila.append(r * W + c)
                c += dc
                r += dr
            if len(fila) >= 2 and 0 <= c < W and 0 <= r < H:
                destino = r * W + c
                if any(b[x][1] == opp and b[x][0] in self.real for x in fila) or cub(b, destino):
                    continue
                rivales = [x for x in fila if b[x][1] == opp]
                if not rivales or any(cub(b, x) for x in rivales):
                    inicios.append((destino, []))
                else:
                    inicios.append((destino, rivales))
        resultados = []

        def seguir(estado, pos, pasos):
            if self.en_jaque(estado, me):
                return
            if self.en_jaque(estado, opp):
                resultados.append(pasos)
                return
            hay = False
            pc, pr = pos % W, pos // W
            bb = estado.b
            for dc, dr in dirs:
                cd, rd = pc + 2 * dc, pr + 2 * dr
                if not (0 <= cd < W and 0 <= rd < H):
                    continue
                I, D = (pr + dr) * W + pc + dc, rd * W + cd
                qi = bb[I]
                if (qi is not None and qi[1] == opp and qi[0] not in self.real and bb[D] is None
                        and not cub(bb, D) and not cub(bb, I)):
                    sig = self._saltar(estado, pos, D, [I])
                    if not self.en_jaque(sig, me):
                        hay = True
                        seguir(sig, D, pasos + [(D, (I,))])
            if not hay:
                resultados.append(pasos)

        for destino, caps in inicios:
            seguir(self._saltar(st, sq, destino, caps), destino, [(destino, tuple(caps))])
        return [('ch', sq, pasos[-1][0], tuple(pasos)) for pasos in resultados]

    def _derechos(self, out, st):
        """Extensiones y conversiones que cuestan el turno."""
        me = st.turn
        cuenta = Counter(self.base[t] for t in st.cap[me])
        usos = st.usos[me]
        for i, (t, nuevo, n, repetir) in enumerate(self.derechos_def):
            c = cuenta.get(self.base[t], 0)
            disp = (c // n - usos[i]) if repetir else (1 if c >= n and not usos[i] else 0)
            if disp > 0:
                for sq, p in enumerate(st.b):
                    if p is not None and p[1] == me and p[0] == t:
                        out.append(('ex', sq, None, nuevo))

    def derechos(self, st, color):
        """[(tipo, nuevo, disponibles)] que ese bando puede ejercer (con la pieza en el tablero)."""
        cuenta = Counter(self.base[t] for t in st.cap[color])
        propias = {p[0] for p in st.b if p is not None and p[1] == color}
        out = []
        for i, (t, nuevo, n, repetir) in enumerate(self.derechos_def):
            c = cuenta.get(self.base[t], 0)
            disp = (c // n - st.usos[color][i]) if repetir else (1 if c >= n and not st.usos[color][i] else 0)
            if disp > 0 and t in propias:
                out.append((t, nuevo, disp))
        return out

    def perdidas(self, st, color):
        """Tipos de los que ese bando tiene menos piezas que al empezar (para promocionar a piezas capturadas)."""
        if not hasattr(self, '_iniciales'):
            self._iniciales = [Counter(t for c, r, t, col in self.cfg['posicion'] if col == x) for x in (0, 1)]
        ahora = Counter(p[0] for p in st.b if p is not None and p[1] == color)
        return {t for t, n in self._iniciales[color].items() if ahora.get(t, 0) < n}

    def _capturar(self, n, sq, me):
        q = n.b[sq]
        n.b[sq] = None
        cap = list(n.cap)
        cap[me] = cap[me] + (q[0],)
        n.cap = tuple(cap)
        if q[0] in self.real and n.rey[1 - me] == sq:
            n.rey[1 - me] = None

    def aplicar(self, st, mv):
        n = st.copy()
        b, me, W = n.b, st.turn, self.W
        k, de, a = mv[0], mv[1], mv[2]
        p = b[de]
        n.ep = None
        if k == 'ex':
            t, nuevo = p[0], mv[3]
            i = next((j for j, (x, y, _, _) in enumerate(self.derechos_def) if x == t and y == nuevo), None)
            b[de] = (nuevo, me, p[2], p[3], p[4])
            if i is not None:
                usos = list(n.usos)
                fila = list(usos[me])
                fila[i] += 1
                usos[me] = tuple(fila)
                n.usos = tuple(usos)
            n.turn = 1 - me
            n.reloj = 0
            return n
        t0 = p[0]
        f = W if me == 0 else -W
        reset = t0 in self.peones
        primer = p[3]
        capturo = False
        if k == 'cs':
            rd, ra = mv[3]
            torre = b[rd]
            b[rd] = None
            b[ra] = (torre[0], torre[1], True, None, torre[4])
        elif k == 'in':
            q = b[a]
            marca = (de, a)
            b[de] = (q[0], q[1], q[2], q[3], marca)
            b[a] = (t0, me, True, primer, marca)
            n.turn = 1 - me
            n.reloj = st.reloj + 1
            return n
        elif k == 'em':
            q = b[a]
            b[a + (a - de)] = (q[0], q[1], True, None, q[4])
            b[a] = None
            reset = True
        elif k == 'ch':
            for _, caps in mv[3]:
                for c in caps:
                    self._capturar(n, c, me)
                    capturo = True
        elif k == 'ep':
            self._capturar(n, mv[3], me)
            capturo = True
        elif b[a] is not None:
            self._capturar(n, a, me)
            capturo = True
        b[de] = None
        t = mv[3] if (k == 'm' and mv[3]) else t0
        recto = de % W == a % W and (a - de) * f > 0
        if (k == 'm' and recto and primer == de // W and (t0 in self.peones or t0 in self.como_peon)
                and abs(a - de) >= 2 * W):
            n.ep = (a - f, a)
        if primer is not None and k != 'em':
            if t0 not in self.como_peon or recto or k == 'ep':
                primer = None
        if t0 in self.como_peon and recto:
            reset = True
        if t in self.ext_llegada and a // W == (self.H - 1 if me == 0 else 0):
            t = self.ext_llegada[t]
            reset = True
        b[a] = (t, me, True, primer, p[4])
        if t0 in self.real:
            n.rey[me] = a
        if capturo:
            reset = True
        n.turn = 1 - me
        n.reloj = 0 if reset else st.reloj + 1
        return n

    def legal(self, st):
        me = st.turn
        if self.real and (st.rey[0] is None or st.rey[1] is None) and not self.mate:
            return []  # se capturó un rey: la partida terminó
        out = []
        for mv in self.pseudo(st):
            n = self.aplicar(st, mv)
            if not self.mate or not self.en_jaque(n, me):
                out.append((mv, n))
        return out

    def insuficiente(self, st):
        if not self.reglas['material']:
            return False
        lista = self.reglas.get('insuficientes')
        for c in (0, 1):
            otras = [p[0] for p in st.b if p and p[1] == c and p[0] not in self.real]
            if any(t in self.peones for t in otras) or len(otras) > 1:
                return False
            if otras and (otras[0] not in lista if lista is not None else self.valor[otras[0]] > 3.5):
                return False
        return True

    def puntos_de(self, st, color):
        return sum(self.puntos[t] for t in st.cap[color])

    def resultado(self, st, movs, repeticiones):
        """(motivo, ganador) si la partida terminó; ganador None = tablas."""
        if not self.mate and self.real:
            for c in (0, 1):
                if st.rey[c] is None:
                    return 'Rey capturado', 1 - c
        if not movs:
            if self.mate and self.en_jaque(st, st.turn):
                return 'Jaque mate', 1 - st.turn
            if self.reglas['ahogado'] == 'victoria':
                return 'Ahogado (gana quien ahoga)', 1 - st.turn
            return 'Ahogado', None
        if self.reglas['repeticion'] and repeticiones >= 3:
            return 'Triple repetición', None
        if self.reglas['cincuenta'] and st.reloj >= 100:
            return 'Regla de las 50 jugadas', None
        if self.insuficiente(st):
            return 'Material insuficiente', None
        return None

    def es_captura(self, st, mv):
        k = mv[0]
        if k == 'm':
            return st.b[mv[2]] is not None
        return k == 'ep' or (k == 'ch' and any(c for _, c in mv[3]))

    def capturadas(self, st, mv):
        """Casillas cuyas piezas captura la jugada."""
        k = mv[0]
        if k == 'm':
            return [mv[2]] if st.b[mv[2]] is not None else []
        if k == 'ep':
            return [mv[3]]
        if k == 'ch':
            return [c for _, cs in mv[3] for c in cs]
        return []

    # -------------------------------------------------------------- evaluación
    def evaluar(self, st):
        """Desde el punto de vista del bando que mueve."""
        me, W, H = st.turn, self.W, self.H
        s = 0.0
        mat = [0.0, 0.0]
        for sq, p in enumerate(st.b):
            if p is None or p[0] in self.real:
                continue
            t, c = p[0], p[1]
            v = self.valor[t]
            mat[c] += v
            if t in self.peones:
                v += 0.04 * (sq // W if c == 0 else H - 1 - sq // W)
            else:
                v += 0.03 * self.centro[sq]
            s += v if c == me else -v
        fuerte = 0 if mat[0] > mat[1] else 1
        debil = 1 - fuerte
        kf, kd = st.rey[fuerte], st.rey[debil]
        if (kf is not None and kd is not None and mat[fuerte] - mat[debil] >= 3
                and mat[debil] <= 0.35 * self.material0):
            borde = max(W, H) / 2 - self.centro[kd]
            cerca = max(W, H) - max(abs(kf % W - kd % W), abs(kf // W - kd // W))
            r = 0.12 * borde + 0.06 * cerca
            s += r if fuerte == me else -r
        return s


def tablas_de(motor):
    """Tablas exactas de finales de la variante (tablas_genericas.py), o False si no hay ninguna."""
    t = getattr(motor, '_tablas', None)
    if t is None:
        t = False
        try:
            import tablas_genericas as TG
            if TG.aplicable(motor.cfg) and any(TG.existe(motor.cfg, [x]) for x in TG.piezas_posibles(motor.cfg)):
                t = TG.Tablas(motor)
        except Exception:  # sin el módulo o con una variante rara: se juega sin tablas
            t = False
        motor._tablas = t
    return t


def _agregar_presets():
    from presets import variantes
    for k, cfg in variantes().items():
        PRESETS.setdefault(k, cfg)


_agregar_presets()


class Buscador:
    """Alfa-beta con profundización iterativa, quietud, tabla de transposición, jugadas asesinas
    y evitación de repeticiones (como Simulador/busqueda.py, pero para cualquier variante)."""

    def __init__(self, motor, time_limit=None, max_depth=3, temperatura=0.0):
        self.m = motor
        self.tl, self.maxd = time_limit, max_depth
        self.temperatura = temperatura  # imprecisión de los niveles bajos (como en busqueda.py)
        self.tt, self.killers = {}, {}
        self.vistas, self.camino = set(), set()

    def timeout(self):
        if self.tl and self.nodes & 255 == 0 and time.time() - self.t0 > self.tl:
            self.stop = True
        return self.stop

    def mvv(self, st, mv):
        m = self.m
        k = mv[0]
        if k == 'ep':
            return 10
        if k == 'm':
            q = st.b[mv[2]]
            sc = 0
            if q is not None:
                sc = (50 if q[0] in m.real else m.valor[q[0]]) * 10 - m.valor[st.b[mv[1]][0]] * 0.1
            if mv[3]:
                sc += m.valor[mv[3]] * 10
            return sc
        if k == 'ch':
            return sum((50 if st.b[c][0] in m.real else m.valor[st.b[c][0]]) * 10
                       for _, cs in mv[3] for c in cs if st.b[c] is not None)
        if k == 'ex':
            return (m.valor[mv[3]] - m.valor[st.b[mv[1]][0]]) * 10
        return 0

    def tactica(self, st, mv):
        k = mv[0]
        if k == 'm':
            return st.b[mv[2]] is not None or bool(mv[3])
        return k == 'ep' or k == 'ex' or (k == 'ch' and any(c for _, c in mv[3]))

    def _hijo(self, st, mv):
        n = self.m.aplicar(st, mv)
        if self.m.mate and self.m.en_jaque(n, st.turn):
            return None
        return n

    def qs(self, st, alpha, beta, qd=0):
        self.nodes += 1
        if self.timeout():
            return 0
        m = self.m
        if not m.mate and m.real and st.rey[st.turn] is None:
            return -MATE
        stand = m.evaluar(st)
        if stand >= beta:
            return stand
        alpha = max(alpha, stand)
        if qd > 6:
            return stand
        movs = [mv for mv in m.pseudo(st) if self.tactica(st, mv)]
        movs.sort(key=lambda mv: -self.mvv(st, mv))
        for mv in movs:
            n = self._hijo(st, mv)
            if n is None:
                continue
            sc = -self.qs(n, -beta, -alpha, qd + 1)
            if self.stop:
                return 0
            if sc >= beta:
                return sc
            alpha = max(alpha, sc)
        return alpha

    def ab(self, st, d, alpha, beta, ply):
        h = self.m.zhash(st)
        if h in self.vistas or h in self.camino:
            return -DESPRECIO if st.turn == self.raiz else DESPRECIO
        self.camino.add(h)
        try:
            return self._ab(st, d, alpha, beta, ply, h)
        finally:
            self.camino.discard(h)

    def _ab(self, st, d, alpha, beta, ply, h):
        m = self.m
        me = st.turn
        if not m.mate and m.real and st.rey[me] is None:
            return -MATE + ply
        if d <= 0:
            return self.qs(st, alpha, beta)
        self.nodes += 1
        if self.timeout():
            return 0
        if ply > 0:  # finales de Rey y una o dos piezas contra Rey: valor exacto si existe su tabla
            fin = tablas_de(m)
            if fin:
                v = fin.valor(st)
                if v is not None:
                    r, dd = v
                    if r == 'tablas':
                        return 0.0
                    if st.reloj + dd <= 100:
                        return MATE - ply - dd if r == 'gana' else -(MATE - ply - dd)
        ent = self.tt.get(h)
        ttmove = None
        if ent:
            ed, esc, flag, ttmove = ent
            if ed >= d and (flag == 0 or (flag == 1 and esc >= beta) or (flag == -1 and esc <= alpha)):
                return esc
        movs = m.pseudo(st)
        kill = self.killers.get(ply, [])

        def orden(mv):
            if mv == ttmove:
                return -1e9
            return -self.mvv(st, mv) - (5 if mv in kill else 0)
        movs.sort(key=orden)
        a0, best, bmv, n_legales = alpha, -MATE * 2, None, 0
        for mv in movs:
            n = self._hijo(st, mv)
            if n is None:
                continue
            n_legales += 1
            tact = self.tactica(st, mv)
            if d >= 3 and n_legales > 4 and not tact and mv not in kill and not m.en_jaque(n, 1 - me):
                sc = -self.ab(n, d - 2, -alpha - 0.01, -alpha, ply + 1)
                if sc > alpha and not self.stop:
                    sc = -self.ab(n, d - 1, -beta, -alpha, ply + 1)
            else:
                sc = -self.ab(n, d - 1, -beta, -alpha, ply + 1)
            if self.stop:
                return 0
            if sc > best:
                best, bmv = sc, mv
            alpha = max(alpha, sc)
            if alpha >= beta:
                if not tact:
                    kl = self.killers.setdefault(ply, [])
                    if mv not in kl:
                        kl.insert(0, mv)
                        del kl[2:]
                break
        if n_legales == 0:
            if m.mate and m.en_jaque(st, me):
                return -MATE + ply
            return -MATE + ply if m.reglas['ahogado'] == 'victoria' else 0
        flag = 0 if a0 < best < beta else (1 if best >= beta else -1)
        self.tt[h] = (d, best, flag, bmv)
        return best

    def choose(self, st, legal_moves, rng, noise=0.05, vistas=()):
        self.vistas, self.camino = set(vistas), set()
        self.raiz = st.turn
        self.tt.clear()
        self.t0, self.stop, self.nodes = time.time(), False, 0
        best_mv, reached = legal_moves[0], 0
        self.puntaje = None  # evaluación de la jugada elegida, desde el bando que mueve
        ordered = sorted(legal_moves, key=lambda x: -self.mvv(st, x[0]))
        for d in range(1, self.maxd + 1):
            scores = []
            alpha = -MATE * 2
            for mv, n in ordered:
                sc = -self.ab(n, d - 1, -MATE * 2, -alpha + noise, 1)
                if self.stop:
                    break
                scores.append((sc + rng.random() * noise, mv, n))
                alpha = max(alpha, sc)
            if self.stop:
                break
            scores.sort(key=lambda x: -x[0])
            best_mv, reached = (scores[0][1], scores[0][2]), d
            self.puntaje = scores[0][0]
            ordered = [(mv, n) for _, mv, n in scores]
            if scores[0][0] > MATE / 2:
                break
        if self.temperatura > 0 and reached and len(scores) > 1:
            # la búsqueda de arriba solo da exacta la puntuación de la mejor jugada (las demás son cotas que
            # se quedan cerca de ella aunque pierdan material): se recalculan con ventana completa
            # (con una ventana de 8 × temperatura bajo la mejor: las de más abajo, con probabilidad
            # despreciable, se descartan sin calcular su valor exacto; como en busqueda.py)
            _, mv, n = scores[0]
            mejor = -self.ab(n, reached - 1, -MATE * 2, MATE * 2, 1)
            if self.stop:
                return best_mv, reached
            exactas = [(mejor, mv, n)]
            piso, techo = mejor - 8 * self.temperatura, mejor + 1.0
            for _, mv, n in scores[1:]:
                sc = -self.ab(n, reached - 1, -techo, -piso, 1)
                if not self.stop and sc >= techo:
                    sc = -self.ab(n, reached - 1, -MATE * 2, MATE * 2, 1)
                if self.stop:
                    return best_mv, reached
                if sc > piso:
                    exactas.append((sc, mv, n))
            scores = sorted(exactas, key=lambda x: -x[0])
            mejor = scores[0][0]
            pesos = [math.exp(max(-50.0, (sc - mejor) / self.temperatura)) for sc, _, _ in scores]
            r = rng.random() * sum(pesos)
            for (sc, mv, n), w in zip(scores, pesos):
                r -= w
                if r <= 0:
                    best_mv, self.puntaje = (mv, n), sc
                    break
        return best_mv, reached
