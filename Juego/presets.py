"""Variantes predefinidas del motor genérico (además de clásico, Capablanca y gótico, en generico.py): el Ajedrez
Extendido descrito con las piezas del Laboratorio, Capablanca y gótico en 10 × 10, el Gran Ajedrez y otras
variantes conocidas.

generico.py las añade a PRESETS al importarse. Este módulo no importa generico.py al cargarse (lo hace dentro de
las funciones), para que el orden de importación no importe.
"""
import copy


def _cas(lista, modo='ambos', salta=None, cond=None):
    """Casillas [[dc, dr, modo, salta, cond]] a partir de [(dc, dr)]."""
    out = []
    for dc, dr in lista:
        e = [dc, dr, modo]
        if salta is not None or cond:
            e.append(salta)
        if cond:
            e.append(cond)
        out.append(e)
    return out


def _sim(a, b):
    """Las ocho simetrías de (a, b)."""
    return sorted({(sx * x, sy * y) for x, y in ((a, b), (b, a)) for sx in (1, -1) for sy in (1, -1)})


DIAGONALES = [(1, 1), (-1, 1), (1, -1), (-1, -1)]
ADYACENTES = [(dc, dr) for dc in (-1, 0, 1) for dr in (-1, 0, 1) if (dc, dr) != (0, 0)]
ANILLO_RECTO = _sim(0, 2) + _sim(2, 2)
ANILLO_CABALLO = _sim(1, 2)


# ---------------------------------------------------------------------- Ajedrez Extendido
def piezas_extendido():
    """Las piezas del Ajedrez Extendido (reglamento oficial), con sus formas extendidas ('Q+', 'R+'...)."""
    def p(nombre, simbolo, imagen, valor, puntos, movs, **extra):
        d = {'nombre': nombre, 'simbolo': simbolo, 'imagen': imagen, 'dorada': False, 'valor': valor,
             'puntos': puntos, 'movs': movs}
        d.update(extra)
        return d

    def ext(base, nombre, simbolo, imagen, valor, puntos, movs, **extra):
        d = p(nombre, simbolo, imagen, valor, puntos, movs, base=base, **extra)
        d['dorada'] = True
        return d

    torre = [{'dirs': 'orto', 'alcance': 0}]
    alfil = [{'dirs': 'diag', 'alcance': 0}]
    caballo = [{'salto': [1, 2]}]
    catapulta_mov = [{'casillas': _cas(ADYACENTES, 'mov', True)}]
    guardian = [
        {'casillas': _cas([(0, 1), (0, 2)], 'mov')},                      # avance: hasta dos, por casillas vacías
        {'casillas': _cas([(0, 3)], 'mov'), 'cond': 'primera'},          # tres en su primer avance
        {'casillas': _cas([(1, 0), (-1, 0)], 'mov')},                     # desplazamiento lateral
        {'casillas': _cas(DIAGONALES, 'cap')},                            # captura en las cuatro diagonales
        {'casillas': _cas(DIAGONALES, 'mov'), 'cond': 'jaque'},          # bloqueo de jaque (4.10.6)
        {'empuje': [[0, 1]], 'tipos': ['P']},                             # empuje (4.10.4)
        {'intercambio': [[1, 0], [-1, 0]], 'tipos': ['P']},              # intercambio (4.10.3)
    ]
    return {
        'K': p('Rey', 'R', 'rey', 0, 0, [{'dirs': 'todas', 'alcance': 1}], real=True),
        'Q': p('Dama', 'D', 'dama', 9, 9, torre + alfil, extension={'pieza': 'Q+', 'captura': 1}),
        'Q+': ext('Q', 'Dama extendida', "D'", 'dama', 10.5, 10.5, torre + alfil + caballo),
        'R': p('Torre', 'T', 'torre', 5, 5, torre, enroca=True, extension={'pieza': 'R+', 'captura': 2}),
        'R+': ext('R', 'Torre extendida', "T'", 'torre', 8, 8,
                  torre + [{'dirs': 'diag', 'alcance': 3, 'salta': True}], enroca=True),
        'B': p('Alfil', 'A', 'alfil', 3, 3, alfil, extension={'pieza': 'B+', 'captura': 2}),
        'B+': ext('B', 'Alfil extendido', "A'", 'alfil', 6.5, 6.5,
                  alfil + [{'dirs': 'orto', 'alcance': 3, 'salta': True}]),
        'N': p('Caballo', 'C', 'caballo', 3.5, 3.5, [{'salto': [1, 2]}, {'salto': [1, 3]}],
               extension={'pieza': 'N+', 'captura': 2}),
        'N+': ext('N', 'Caballo extendido', "C'", 'caballo', 6, 6,
                  [{'salto': [1, 2]}, {'salto': [1, 3]}, {'salto': [2, 3]}]),
        'CA': p('Arzobispo', 'Az', 'arzobispo', 5, 5, caballo + [{'dirs': 'diag', 'alcance': 5}],
                extension={'pieza': 'CA+', 'captura': 1}),
        'CA+': ext('CA', 'Arzobispo extendido', "Az'", 'arzobispo', 6, 6, caballo + alfil),
        'CH': p('Canciller', 'Ch', 'canciller', 6, 6, caballo + [{'dirs': 'orto', 'alcance': 5}],
                extension={'pieza': 'CH+', 'captura': 1}),
        'CH+': ext('CH', 'Canciller extendido', "Ch'", 'canciller', 8, 8, caballo + torre),
        'CE': p('Catapulta', 'Ct', 'catapulta', 5, 5,
                catapulta_mov + [{'casillas': _cas(ANILLO_RECTO + ANILLO_CABALLO, 'ambos', True)},
                                 {'secuencia': 'todas', 'minimo': 2}],
                extension={'pieza': 'CE+', 'captura': 1}),
        'CE+': ext('CE', 'Catapulta extendida', "Ct'", 'catapulta', 9.5, 9.5,
                   catapulta_mov + [{'casillas': _cas(ANILLO_CABALLO, 'ambos', True)},
                                    {'casillas': _cas(ANILLO_RECTO, 'mov', True)},
                                    {'cadena': 'todas', 'fila': True}]),
        'G': p('Guardián', 'G', 'guardian', 2, 2, guardian, aura=[list(d) for d in DIAGONALES], como_peon=True,
               extension={'pieza': 'G+', 'llegada': True, 'captura': 5, 'repetir': True}),
        'G+': ext('G', 'Guardián extendido', "G'", 'guardian', 3.5, 3.5, [{'dirs': 'todas', 'alcance': 2}]),
        'P': p('Peón', '', 'peon', 1, 1, [], peon=True, extension={'pieza': 'P+', 'llegada': True},
               conversion={'pieza': 'G', 'captura': 4}),
        'P+': ext('P', 'Peón extendido', "P'", 'peon', 2, 2, [{'dirs': 'todas', 'alcance': 1}]),
    }


def extendido():
    import generico as G
    fila = ['R', 'N', 'B', 'CA', 'Q', 'K', 'CE', 'CH', 'N', 'B', 'R']
    posicion = []
    for c, t in enumerate(fila):
        posicion += [[c, 0, t, 0], [c, 10, t, 1]]
    for c in range(11):
        t = 'G' if c in (4, 5, 6) else 'P'
        posicion += [[c, 1, t, 0], [c, 9, t, 1]]
    r = dict(G.REGLAS_BASE)
    r.update(pasos_enroque=4, promocion=[], desempate=True, insuficientes=['B', 'N'])
    return {'id': 'extendido_lab', 'nombre': 'Ajedrez Extendido (Laboratorio)',
            'descripcion': 'El Ajedrez Extendido descrito con las piezas del Laboratorio, para modificarlo.',
            'ancho': 11, 'alto': 11, 'tema': 'madera', 'piezas': piezas_extendido(), 'posicion': posicion,
            'reglas': r}


# ---------------------------------------------------------------------- otras variantes
def _variante(ident, nombre, descripcion, filas, piezas, reglas=None, alto=8, nombres=None):
    """filas: {fila: (texto de las blancas, texto de las negras o None = el mismo)}, con un tipo por columna
    separados por espacios ('.' = vacía). Las negras se colocan en la fila simétrica."""
    import generico as G
    posicion = []
    for fila, (blancas, negras) in filas.items():
        for color, texto in ((0, blancas), (1, negras or blancas)):
            r = fila if color == 0 else alto - 1 - fila
            for c, t in enumerate(texto.split()):
                if t != '.':
                    posicion.append([c, r, t, color])
    ancho = len(next(iter(filas.values()))[0].split())
    r = dict(G.REGLAS_BASE)
    r.update(reglas or {})
    defs = copy.deepcopy(piezas)
    for t, n in (nombres or {}).items():
        defs[t]['nombre'] = n
    return {'id': ident, 'nombre': nombre, 'descripcion': descripcion, 'ancho': ancho, 'alto': alto,
            'tema': 'madera', 'piezas': defs, 'posicion': posicion, 'reglas': r}


def _piezas(*tipos, **magicas):
    """Piezas del catálogo clásico (generico.CATALOGO) y del de piezas mágicas (clave: pieza mágica)."""
    import generico as G
    import piezas_magicas as PM
    out = {t: copy.deepcopy(G.CATALOGO[t]) for t in tipos}
    for t, clave in magicas.items():
        out[t] = PM.pieza(clave)
    return out


CAPABLANCA = ['Q', 'CH', 'CA', 'R', 'B', 'N']


def variantes():
    """{id: configuración} de las variantes predefinidas de este módulo."""
    peones = lambda n: ' '.join(['P'] * n)
    out = {'extendido_lab': extendido()}
    out['capablanca10'] = _variante(
        'capablanca10', 'Ajedrez Capablanca 10×10',
        'Tablero de 10×10 con Arzobispo y Canciller; el peón avanza hasta tres casillas la primera vez.',
        {0: ('R N CA B Q K B CH N R', None), 1: (peones(10), None)}, _piezas('K', 'Q', 'R', 'B', 'N', 'P', 'CA', 'CH'),
        {'pasos_enroque': 3, 'promocion': CAPABLANCA, 'pasos_peon': 3}, alto=10)
    out['gotico10'] = _variante(
        'gotico10', 'Ajedrez gótico 10×10',
        'El gótico en 10×10; el peón avanza hasta tres casillas la primera vez.',
        {0: ('R N B Q CH K CA B N R', None), 1: (peones(10), None)}, _piezas('K', 'Q', 'R', 'B', 'N', 'P', 'CA', 'CH'),
        {'pasos_enroque': 3, 'promocion': CAPABLANCA, 'pasos_peon': 3}, alto=10)
    out['gran_ajedrez'] = _variante(
        'gran_ajedrez', 'Gran Ajedrez',
        'De Christian Freeling (1984), en 10×10: las Torres solas en la primera fila, el Mariscal y el Cardenal; '
        'sin enroque. El peón promociona en las tres últimas filas (en la última, obligatoriamente), y solo a una '
        'pieza propia ya capturada.',
        {0: ('R . . . . . . . . R', None), 1: ('. N B Q K CH CA B N .', None), 2: (peones(10), None)},
        _piezas('K', 'Q', 'R', 'B', 'N', 'P', 'CA', 'CH'),
        {'enroque': False, 'promocion': CAPABLANCA, 'zona_promocion': 3, 'promocion_opcional': True,
         'promocion_capturadas': True}, alto=10, nombres={'CH': 'Mariscal', 'CA': 'Cardenal'})
    out['jano'] = _variante(
        'jano', 'Ajedrez Jano',
        'De Werner Schöndorf (1978), en 10×8, con dos Janos (Alfil + Caballo) junto a las Torres. Enroque largo '
        'hacia la columna b y corto hacia la i.',
        {0: ('R CA N B K Q B N CA R', None), 1: (peones(10), None)}, _piezas('K', 'Q', 'R', 'B', 'N', 'P', 'CA'),
        {'pasos_enroque': [3, 4], 'promocion': ['Q', 'CA', 'R', 'B', 'N']}, nombres={'CA': 'Jano'})
    out['embajada'] = _variante(
        'embajada', 'Ajedrez Embajada',
        'De Kevin Hill (2005), en 10×8: el Mariscal (Torre + Caballo) junto al Rey y el Cardenal (Alfil + Caballo) '
        'a su lado. El rey enroca moviéndose tres casillas.',
        {0: ('R N B Q K CH CA B N R', None), 1: (peones(10), None)}, _piezas('K', 'Q', 'R', 'B', 'N', 'P', 'CA', 'CH'),
        {'pasos_enroque': 3, 'promocion': CAPABLANCA}, nombres={'CH': 'Mariscal', 'CA': 'Cardenal'})
    out['moderno'] = _variante(
        'moderno', 'Ajedrez moderno',
        'De Gabriel Maura (1968), en 9×9, con el Ministro (Alfil + Caballo). Los dos Alfiles empiezan en casillas '
        'oscuras.',
        {0: ('R N B CA K Q B N R', 'R N B Q K CA B N R'), 1: (peones(9), None)},
        _piezas('K', 'Q', 'R', 'B', 'N', 'P', 'CA'), {'promocion': ['Q', 'CA', 'R', 'B', 'N']}, alto=9,
        nombres={'CA': 'Ministro'})
    out['courier'] = _variante(
        'courier', 'Ajedrez Courier',
        'El ajedrez alemán medieval (siglo XIII), en 12×8, con el Courier (el Alfil moderno), el Hombre, el '
        'Schleich (un paso en recto), la Fers y el Alfil antiguo. Sin enroque ni avance doble; el peón promociona '
        'a Fers.',
        {0: ('R N E C M K F S C E N R', None), 1: (peones(12), None)},
        _piezas('K', 'R', 'N', 'P', E='elefante', C='courier', M='hombre', F='consejero', S='visir'),
        {'enroque': False, 'doble_paso': False, 'al_paso': False, 'promocion': ['F']},
        nombres={'S': 'Schleich'})
    out['shatranj'] = _variante(
        'shatranj', 'Shatranj',
        'El ajedrez árabe medieval: la Fers (un paso en diagonal) en lugar de la Dama y el Alfil antiguo (salta dos '
        'en diagonal). Sin enroque ni avance doble; el peón promociona a Fers; ahogar al rival gana.',
        {0: ('R N E F K E N R', None), 1: (peones(8), None)}, _piezas('K', 'R', 'N', 'P', E='elefante', F='consejero'),
        {'enroque': False, 'doble_paso': False, 'al_paso': False, 'promocion': ['F'], 'ahogado': 'victoria'})
    out['makruk'] = _variante(
        'makruk', 'Makruk',
        'El ajedrez tailandés: el Met (un paso en diagonal) junto al Rey, los Khon (un paso en diagonal o adelante) '
        'y los peones en la tercera fila, que promocionan a Met al llegar a la sexta. Sin enroque ni avance doble.',
        {0: ('R N S K M S N R', 'R N S M K S N R'), 2: (peones(8), None)},
        _piezas('K', 'R', 'N', 'P', S='khon', M='consejero'),
        {'enroque': False, 'doble_paso': False, 'al_paso': False, 'promocion': ['M'], 'zona_promocion': 3},
        nombres={'M': 'Met'})
    out['los_alamos'] = _variante(
        'los_alamos', 'Ajedrez de Los Álamos',
        'El primer ajedrez jugado por una computadora (1956): 6×6, sin Alfiles, sin enroque ni avance doble.',
        {0: ('R N Q K N R', None), 1: (peones(6), None)}, _piezas('K', 'Q', 'R', 'N', 'P'),
        {'enroque': False, 'doble_paso': False, 'al_paso': False, 'promocion': ['Q', 'R', 'N']}, alto=6)
    out['gardner'] = _variante(
        'gardner', 'Miniajedrez de Gardner',
        'De Martin Gardner (1969): 5×5, una pieza de cada; sin enroque ni avance doble.',
        {0: ('R N B Q K', None), 1: (peones(5), None)}, _piezas('K', 'Q', 'R', 'B', 'N', 'P'),
        {'enroque': False, 'doble_paso': False, 'al_paso': False}, alto=5)
    out['berolina'] = _variante(
        'berolina', 'Ajedrez Berolina',
        'De Edmund Nebermann (1926): los peones avanzan en diagonal (dos casillas la primera vez) y capturan en '
        'recto hacia adelante.',
        {0: ('R N B Q K B N R', None), 1: (peones(8), None)}, _piezas('K', 'Q', 'R', 'B', 'N', P='peon_berolina'),
        {'al_paso': False}, nombres={'P': 'Peón de Berolina'})
    knightmate = _piezas('Q', 'R', 'B', 'P', H='hombre')
    knightmate['K'] = {'nombre': 'Rey caballo', 'simbolo': 'R', 'imagen': 'caballo', 'dorada': True, 'valor': 0,
                       'movs': [{'salto': [1, 2]}], 'real': True}
    out['knightmate'] = _variante(
        'knightmate', 'Knightmate',
        'De Bruce Zimov (1972): el Rey se mueve como el Caballo (y hay que darle mate) y los Caballos se cambian '
        'por Hombres, que se mueven como el Rey.',
        {0: ('R H B Q K B H R', None), 1: (peones(8), None)}, knightmate, {'promocion': ['Q', 'R', 'B', 'H']})
    out['saltamontes'] = _variante(
        'saltamontes', 'Ajedrez de los saltamontes',
        'Una fila de Saltamontes delante de las piezas y los peones en la tercera fila, sin avance doble. El '
        'Saltamontes salta sobre la primera pieza que encuentra y cae justo detrás.',
        {0: ('R N B Q K B N R', None), 1: (' '.join(['G'] * 8), None), 2: (peones(8), None)},
        _piezas('K', 'Q', 'R', 'B', 'N', 'P', G='saltamontes'),
        {'doble_paso': False, 'al_paso': False, 'promocion': ['Q', 'R', 'B', 'N', 'G']})
    out['casi'] = _variante(
        'casi', 'Casi ajedrez',
        'De Ralph Betza (1977): el ajedrez de siempre, pero con un Canciller (Torre + Caballo) en lugar de la Dama.',
        {0: ('R N B CH K B N R', None), 1: (peones(8), None)}, _piezas('K', 'R', 'B', 'N', 'P', 'CH'),
        {'promocion': ['CH', 'R', 'B', 'N']})
    return out


# variantes del menú «Más variantes», en orden (las de 10 × 10 están en las tarjetas de Capablanca y gótico)
OTRAS = ['gran_ajedrez', 'jano', 'embajada', 'moderno', 'courier', 'shatranj', 'makruk', 'los_alamos', 'gardner',
         'berolina', 'knightmate', 'saltamontes', 'casi']
