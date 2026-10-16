"""Catálogo de piezas mágicas (del ajedrez de fantasía) para el Laboratorio: las clásicas de la literatura
(T. R. Dawson, D. B. Pritchard, «The Encyclopedia of Chess Variants», y la tradición de los problemistas), las de
los ajedreces históricos y regionales, y algunas creaciones propias del Laboratorio.

Cada pieza tiene su imagen ('pre:clave', en Piezas/predisenos; ver Piezas/generar_disenos.py) y sus
movimientos en el formato de generico.py. Este módulo no importa el resto del juego.
"""
import copy

CATEGORIAS = [
    ('extendido', 'Del Ajedrez Extendido', 'La Catapulta y el Guardián, con sus formas extendidas.'),
    ('saltadores', 'Saltadores', 'Saltan a casillas fijas, por encima de lo que haya en medio.'),
    ('jinetes', 'Jinetes', 'Repiten un salto en línea mientras las casillas estén vacías.'),
    ('compuestas', 'Compuestas', 'Suman los movimientos de dos piezas.'),
    ('pantalla', 'Saltadoras sobre pantalla', 'Necesitan saltar sobre otra pieza (la pantalla).'),
    ('torcidas', 'Torcidas y curvas', 'Recorren caminos que cambian de dirección; las piezas en el camino las bloquean.'),
    ('historicas', 'Históricas y regionales', 'Del shatranj, el makruk, el shogi, el xiangqi y el Courier.'),
    ('peones', 'Peones de fantasía', 'Peones con otras reglas.'),
    ('laboratorio', 'Creaciones del Laboratorio', 'Piezas inventadas para este juego.'),
]


def _sim(a, b):
    return sorted({(sx * x, sy * y) for x, y in ((a, b), (b, a)) for sx in (1, -1) for sy in (1, -1)})


def _cas(lista, modo='ambos', salta=None):
    return {'casillas': [[dc, dr, modo] if salta is None else [dc, dr, modo, salta] for dc, dr in lista]}


def _salto(a, b, **kw):
    d = {'salto': [a, b]}
    d.update(kw)
    return d


def _linea(dirs, alcance=0, **kw):
    d = {'dirs': dirs, 'alcance': alcance}
    d.update(kw)
    return d


def _torcidos(primero, luego, alcance=1, primera_destino=False):
    """Recorridos de una pieza torcida (ver generico.caminos_torcidos), sin importar generico."""
    ORTO = ((1, 0), (-1, 0), (0, 1), (0, -1))
    DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))
    dirs = {'orto': ORTO, 'diag': DIAG}
    out = []
    for a in dirs[primero]:
        for b in dirs[luego]:
            if a[0] * b[0] < 0 or a[1] * b[1] < 0 or a[0] * b[1] - a[1] * b[0] == 0:
                continue
            camino = [[a[0], a[1], primera_destino]]
            for k in range(1, (alcance or 15) + 1):
                camino.append([a[0] + b[0] * k, a[1] + b[1] * k, True])
            out.append(camino)
    return out


def _rosa():
    pasos = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
    out = []
    for i in range(8):
        for sentido in (1, -1):
            c = r = 0
            camino = []
            for k in range(7):
                dc, dr = pasos[(i + sentido * k) % 8]
                c, r = c + dc, r + dr
                camino.append([c, r, True])
            out.append(camino)
    return out


TORRE = _linea('orto')
ALFIL = _linea('diag')
DAMA = _linea('todas')
REY = _linea('todas', 1)
VISIR = _linea('orto', 1)
FERS = _linea('diag', 1)
CABALLO = _salto(1, 2)
ADELANTE_DIAG = [(1, 1), (-1, 1)]

# clave: (nombre, símbolo, categoría, descripción, movimientos, extra)
PIEZAS = {
    # ---------------------------------------------------------------- saltadores
    'visir': ('Visir', 'W', 'saltadores', 'Un paso en recto (el «wazir» del ajedrez antiguo).', [VISIR], {}),
    'consejero': ('Fers', 'F', 'saltadores', 'Un paso en diagonal (el «fers» o consejero del ajedrez antiguo).',
                  [FERS], {}),
    'elefante': ('Alfil antiguo', 'E', 'saltadores', 'Salta exactamente dos casillas en diagonal (el elefante del '
                 'shatranj).', [_salto(2, 2)], {}),
    'dabbaba': ('Dabbaba', 'Db', 'saltadores', 'Salta exactamente dos casillas en recto (la máquina de asedio).',
                [_salto(0, 2)], {}),
    'alibaba': ('Alibabá', 'Ab', 'saltadores', 'Salta exactamente dos casillas en recto o en diagonal (Alfil antiguo '
                '+ Dabbaba).', [_salto(2, 2), _salto(0, 2)], {}),
    'tres_saltador': ('Trisaltador', 'Ts', 'saltadores', 'Salta exactamente tres casillas en recto.',
                      [_salto(0, 3)], {}),
    'tripper': ('Tripper', 'Tp', 'saltadores', 'Salta exactamente tres casillas en diagonal.', [_salto(3, 3)], {}),
    'camello': ('Camello', 'Cm', 'saltadores', 'Salta tres y una (un Caballo alargado).', [_salto(1, 3)], {}),
    'cebra': ('Cebra', 'Z', 'saltadores', 'Salta tres y dos.', [_salto(2, 3)], {}),
    'jirafa': ('Jirafa', 'Jf', 'saltadores', 'Salta cuatro y una.', [_salto(1, 4)], {}),
    'antilope': ('Antílope', 'An', 'saltadores', 'Salta cuatro y tres.', [_salto(3, 4)], {}),
    'nu': ('Ñu', 'Ñ', 'saltadores', 'Salta como el Caballo o como el Camello.', [CABALLO, _salto(1, 3)], {}),
    'bisonte': ('Bisonte', 'Bs', 'saltadores', 'Salta como el Camello o como la Cebra.',
                [_salto(1, 3), _salto(2, 3)], {}),
    'okapi': ('Okapi', 'Ok', 'saltadores', 'Salta como el Caballo o como la Cebra.', [CABALLO, _salto(2, 3)], {}),
    'bufalo': ('Búfalo', 'Bf', 'saltadores', 'Salta como el Caballo, el Camello o la Cebra.',
               [CABALLO, _salto(1, 3), _salto(2, 3)], {}),
    'ardilla': ('Ardilla', 'Ar', 'saltadores', 'Salta a cualquier casilla a distancia dos: Caballo, Alfil antiguo y '
                'Dabbaba.', [CABALLO, _salto(2, 2), _salto(0, 2)], {}),
    'kirin': ('Kirin', 'Ki', 'saltadores', 'Un paso en diagonal o un salto de dos en recto (Fers + Dabbaba).',
              [FERS, _salto(0, 2)], {}),
    'fenix': ('Fénix', 'Fx', 'saltadores', 'Un paso en recto o un salto de dos en diagonal (Visir + Alfil antiguo).',
              [VISIR, _salto(2, 2)], {}),
    'hombre': ('Hombre', 'H', 'saltadores', 'Se mueve como el Rey, pero no es la pieza real (el «Mann» del '
               'Courier).', [REY], {}),
    'centauro': ('Centauro', 'Ce', 'compuestas', 'Rey + Caballo (sin ser la pieza real).', [REY, CABALLO], {}),
    # ---------------------------------------------------------------- jinetes
    'jinete_nocturno': ('Jinete nocturno', 'NN', 'jinetes', 'Repite el salto del Caballo en la misma dirección '
                        'mientras las casillas estén vacías.', [_salto(1, 2, repite=True)], {}),
    'jinete_camello': ('Jinete camello', 'CmR', 'jinetes', 'Repite el salto del Camello en línea.',
                       [_salto(1, 3, repite=True)], {}),
    'jinete_cebra': ('Jinete cebra', 'ZR', 'jinetes', 'Repite el salto de la Cebra en línea.',
                     [_salto(2, 3, repite=True)], {}),
    'bede': ('Bede', 'Bd', 'jinetes', 'Alfil + jinete de Dabbaba (saltos de dos en recto, repetidos).',
             [ALFIL, _salto(0, 2, repite=True)], {}),
    'waran': ('Waran', 'Wr', 'jinetes', 'Torre + Jinete nocturno.', [TORRE, _salto(1, 2, repite=True)], {}),
    'unicornio': ('Unicornio', 'U', 'jinetes', 'Alfil + Jinete nocturno.', [ALFIL, _salto(1, 2, repite=True)], {}),
    # ---------------------------------------------------------------- compuestas
    'amazona': ('Amazona', 'Am', 'compuestas', 'Dama + Caballo: la pieza más poderosa.', [DAMA, CABALLO], {}),
    'emperatriz': ('Emperatriz', 'Em', 'compuestas', 'Torre + Caballo (el Canciller o Mariscal).',
                   [TORRE, CABALLO], {}),
    'princesa': ('Princesa', 'Pr', 'compuestas', 'Alfil + Caballo (el Arzobispo o Cardenal).', [ALFIL, CABALLO], {}),
    'dragon': ('Rey dragón', 'Dr', 'compuestas', 'Torre + un paso en diagonal (la Torre coronada del shogi).',
               [TORRE, FERS], {}),
    'caballo_dragon': ('Caballo dragón', 'CD', 'compuestas', 'Alfil + un paso en recto (el Alfil coronado del '
                       'shogi).', [ALFIL, VISIR], {}),
    'caballo_coronado': ('Caballo coronado', 'CC', 'compuestas', 'Caballo + un paso de Rey en cualquier dirección.',
                         [CABALLO, REY], {}),
    # ---------------------------------------------------------------- saltadoras sobre pantalla
    'saltamontes': ('Saltamontes', 'S', 'pantalla', 'Se mueve en recto o en diagonal saltando sobre la primera pieza '
                    'que encuentra y cae en la casilla justo detrás (vacía, o captura lo que haya).',
                    [{'pantalla': 'todas', 'tras': 'justo'}], {}),
    'saltamontes_torre': ('Saltamontes de torre', 'ST', 'pantalla', 'Como el Saltamontes, solo en recto.',
                          [{'pantalla': 'orto', 'tras': 'justo'}], {}),
    'saltamontes_alfil': ('Saltamontes de alfil', 'SA', 'pantalla', 'Como el Saltamontes, solo en diagonal.',
                          [{'pantalla': 'diag', 'tras': 'justo'}], {}),
    'leon': ('León', 'L', 'pantalla', 'Salta sobre una pieza (en recto o en diagonal) y cae en cualquier casilla '
             'detrás, hasta la siguiente pieza, que puede capturar.', [{'pantalla': 'todas', 'tras': 'libre'}], {}),
    'canon': ('Cañón', 'Cñ', 'pantalla', 'Se mueve como la Torre sin capturar; captura saltando una pieza en recto '
              'y tomando la primera que hay detrás (el cañón del xiangqi).',
              [_linea('orto', modo='mov'), {'pantalla': 'orto', 'tras': 'primera', 'modo': 'cap'}], {}),
    'vao': ('Vao', 'V', 'pantalla', 'El Cañón en diagonal: se mueve como el Alfil y captura saltando una pieza.',
            [_linea('diag', modo='mov'), {'pantalla': 'diag', 'tras': 'primera', 'modo': 'cap'}], {}),
    'leo': ('Leo', 'Lo', 'pantalla', 'Se mueve como la Dama y captura como el Cañón, en recto o en diagonal.',
            [_linea('todas', modo='mov'), {'pantalla': 'todas', 'tras': 'primera', 'modo': 'cap'}], {}),
    'langosta': ('Langosta', 'Lg', 'pantalla', 'Captura saltando sobre una pieza adversaria (en recto o en diagonal, '
                 'a cualquier distancia) y cae justo detrás, que debe estar vacía. Solo se mueve capturando.',
                 [{'pantalla': 'todas', 'come': True}], {}),
    # ---------------------------------------------------------------- torcidas y curvas
    'mao': ('Mao', 'Mo', 'torcidas', 'Un paso en recto y otro en diagonal alejándose: el Caballo del xiangqi, que se '
            'bloquea si la primera casilla está ocupada.', [{'camino': _torcidos('orto', 'diag', 1)}], {}),
    'moa': ('Moa', 'Ma', 'torcidas', 'Un paso en diagonal y otro en recto alejándose (un Caballo que se bloquea).',
            [{'camino': _torcidos('diag', 'orto', 1)}], {}),
    'elefante_chino': ('Elefante chino', 'EC', 'torcidas', 'Dos casillas en diagonal, con la intermedia vacía (el '
                       'elefante del xiangqi, sin el río).', [_cas(_sim(2, 2), 'ambos', False)], {}),
    'grifo': ('Grifo', 'Gr', 'torcidas', 'Un paso en diagonal y luego en recto, alejándose, sin límite.',
              [{'camino': _torcidos('diag', 'orto', 0, True)}], {}),
    'aanca': ('Aanca', 'Aa', 'torcidas', 'Un paso en recto y luego en diagonal, alejándose, sin límite.',
              [{'camino': _torcidos('orto', 'diag', 0, True)}], {}),
    'rosa': ('Rosa', 'Rs', 'torcidas', 'Encadena saltos de Caballo girando en círculo (un octógono), en los dos '
             'sentidos, mientras las casillas estén vacías.', [{'camino': _rosa()}], {}),
    # ---------------------------------------------------------------- históricas y regionales
    'khon': ('Khon', 'Kh', 'historicas', 'Un paso en diagonal o uno recto hacia adelante (el makruk; el General de '
             'plata del shogi).', [_cas([(1, 1), (-1, 1), (1, -1), (-1, -1), (0, 1)])], {}),
    'general_oro': ('General de oro', 'GO', 'historicas', 'Un paso en recto o uno en diagonal hacia adelante (el '
                    'shogi).', [_cas([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1)])], {}),
    'lanza': ('Lanza', 'Lz', 'historicas', 'Avanza en recto hacia adelante sin límite y no retrocede (el shogi).',
              [_cas([(0, k) for k in range(1, 16)], 'ambos', False)], {}),
    'keima': ('Caballo del shogi', 'Km', 'historicas', 'Solo los dos saltos de Caballo hacia adelante.',
              [_cas([(1, 2), (-1, 2)])], {}),
    'courier': ('Courier', 'Co', 'historicas', 'Se mueve como el Alfil moderno (el «correo» del Courier).',
                [ALFIL], {}),
    # ---------------------------------------------------------------- peones de fantasía
    'peon_berolina': ('Peón de Berolina', '', 'peones', 'Avanza en diagonal (dos casillas la primera vez) y captura '
                      'en recto hacia adelante.', [], {'peon': True, 'berolina': True}),
    'peon_damas': ('Peón de damas', 'Pd', 'peones', 'Avanza un paso en diagonal hacia adelante y captura saltando '
                   'sobre una pieza adversaria de al lado, en diagonal hacia adelante, cayendo justo detrás.',
                   [_cas(ADELANTE_DIAG, 'mov'),
                    {'pantalla': [[1, 1], [-1, 1]], 'come': True, 'pegada': True}], {}),
    # ---------------------------------------------------------------- creaciones del Laboratorio
    'yelmo': ('Escudero', 'Ed', 'laboratorio', 'Avanza un paso en recto y captura un paso en diagonal, en cualquier '
              'sentido.', [_linea('orto', 1, modo='mov'), _linea('diag', 1, modo='cap')], {}),
    'mago': ('Mago', 'Mg', 'laboratorio', 'Un paso en diagonal o un salto de Camello.', [FERS, _salto(1, 3)], {}),
    'arquero': ('Arquero', 'Aq', 'laboratorio', 'Se mueve como el Rey y captura también a dos casillas en línea '
                'recta (sin saltar).', [REY, _cas(_sim(0, 2) + _sim(2, 2), 'cap', False)], {}),
    'centinela': ('Centinela', 'Cn', 'laboratorio', 'Se mueve como el Rey; captura además hasta tres casillas hacia '
                  'adelante.', [REY, _cas([(0, 2), (0, 3)], 'cap', False)], {}),
    'llama': ('Llama', 'Ll', 'laboratorio', 'Se desliza hasta tres casillas en diagonal o salta dos en recto.',
              [_linea('diag', 3), _salto(0, 2)], {}),
    'rayo': ('Rayo', 'Ry', 'laboratorio', 'Salta hasta cuatro casillas en recto, por encima de lo que haya.',
             [_linea('orto', 4, salta=True)], {}),
    'estrella': ('Estrella', 'Es', 'laboratorio', 'Llega a cualquier casilla a una o dos de distancia, saltando.',
                 [_cas(sorted({(x, y) for x in range(-2, 3) for y in range(-2, 3)} - {(0, 0)}), 'ambos', True)], {}),
    'diamante': ('Diamante', 'Di', 'laboratorio', 'Salta exactamente tres casillas en recto o en diagonal.',
                 [_salto(0, 3), _salto(3, 3)], {}),
}

# piezas del Ajedrez Extendido (con las imágenes del juego): clave -> (tipo en presets.piezas_extendido, descripción)
DEL_EXTENDIDO = {
    'catapulta': ('CE', 'Mueve a una o dos casillas saltando, captura solo a dos y salta filas de piezas. Incluye su '
                        'forma extendida (capturas en cadena), que se gana al capturar la Catapulta adversaria.'),
    'catapulta_extendida': ('CE+', 'La Catapulta extendida: captura en las casillas del Caballo y con capturas en '
                                   'cadena.'),
    'guardian': ('G', 'Avanza hasta dos (tres la primera vez), se mueve de lado, captura en diagonal, empuja peones, '
                      'se intercambia con ellos, tapa jaques y bloquea los saltos adversarios en sus diagonales. Se '
                      'extiende al llegar a la última fila o tras capturar cinco Guardianes.'),
    'guardian_extendido': ('G+', 'El Guardián extendido: hasta dos casillas en cualquier dirección.'),
}


def _del_extendido(clave):
    import presets
    defs = presets.piezas_extendido()
    tipo = DEL_EXTENDIDO[clave][0]
    d = copy.deepcopy(defs[tipo])
    d.pop('base', None)
    e = d.get('extension')
    if e:  # la forma extendida va con la pieza; el editor la guarda como «tipo+»
        d['_ext_def'] = copy.deepcopy(defs[e['pieza']])
    return d


def claves(categoria=None):
    out = [k for k in DEL_EXTENDIDO if categoria in (None, 'extendido')]
    return out + [k for k, v in PIEZAS.items() if categoria is None or v[2] == categoria]


def nombre(clave):
    return _del_extendido(clave)['nombre'] if clave in DEL_EXTENDIDO else PIEZAS[clave][0]


def imagen(clave):
    return _del_extendido(clave)['imagen'] if clave in DEL_EXTENDIDO else 'pre:' + clave


def pieza(clave, nombre=None):
    """Definición de pieza (generico.py) de una pieza del catálogo."""
    if clave in DEL_EXTENDIDO:
        d = _del_extendido(clave)
        if nombre:
            d['nombre'] = nombre
        return d
    titulo, simbolo, _, _, movs, extra = PIEZAS[clave]
    d = {'nombre': nombre or titulo, 'simbolo': simbolo, 'imagen': 'pre:' + clave, 'dorada': False, 'valor': None,
         'movs': copy.deepcopy(movs)}
    d.update(copy.deepcopy(extra))
    return d


def descripcion(clave):
    return DEL_EXTENDIDO[clave][1] if clave in DEL_EXTENDIDO else PIEZAS[clave][3]
