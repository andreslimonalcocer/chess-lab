"""Posiciones y partidas en texto, para copiarlas, guardarlas o pegarlas.

Posición (parecida al FEN del ajedrez): las filas de arriba hacia abajo separadas por «/», las
casillas vacías como números, las piezas con su letra (mayúscula: blancas; minúscula: negras);
los tipos de varias letras van entre paréntesis, (CE) o (ce), y un apóstrofo marca la forma
promocionada. Al final, «w» si mueven las blancas o «b» si mueven las negras. Ejemplo (clásico):
    rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b

Partida: encabezados entre corchetes y las jugadas en la notación del juego:
    [Variante "Ajedrez Extendido"]
    [Resultado "1-0"]
    1. Ct g3  G g7
    2. k4  G e7
Al leerla se reconocen las jugadas comparándolas con las legales, así que admite espacios dentro
de la notación, números de jugada y símbolos como +, #, ?, !.
"""
import json, re

import variantes as V
import generico as G

RESULTADOS = {'blancas': '1-0', 'negras': '0-1', 'tablas': '1/2-1/2'}


# ---------------------------------------------------------------------- posiciones
def _token(t, c):
    s = t if len(t) == 1 else '(%s)' % t
    return s.upper() if c == 0 else s.lower()


def fen(v, st):
    filas = []
    for r in range(v.alto - 1, -1, -1):
        fila, vacias = '', 0
        for c in range(v.ancho):
            p = v.pieza(st, r * v.ancho + c)
            if p is None:
                vacias += 1
                continue
            if vacias:
                fila, vacias = fila + str(vacias), 0
            fila += _token(p[0], p[1]) + ("'" if p[2] else '')
        filas.append(fila + (str(vacias) if vacias else ''))
    return '/'.join(filas) + (' w' if st.turn == 0 else ' b')


def leer_fen(v, texto):
    """{casilla: (tipo, color, promocionada)} y el turno. ValueError con la explicación si no es válida."""
    texto = texto.strip()
    partes = texto.split()
    if not partes:
        raise ValueError('La posición está vacía.')
    turno = 0
    if len(partes) > 1:
        if partes[1].lower() not in ('w', 'b'):
            raise ValueError('Después de las filas va «w» (mueven las blancas) o «b» (mueven las negras).')
        turno = 0 if partes[1].lower() == 'w' else 1
    filas = partes[0].split('/')
    if len(filas) != v.alto:
        raise ValueError('La posición tiene %d filas y el tablero de %s tiene %d.' % (len(filas), v.nombre, v.alto))
    tipos = {t.upper(): t for t in v.paleta}
    piezas = {}
    for i, fila in enumerate(filas):
        r, c = v.alto - 1 - i, 0
        for m in re.finditer(r"(\d+)|\(([^)]+)\)('?)|([A-Za-z])('?)|(.)", fila):
            if m.group(1):
                c += int(m.group(1))
                continue
            if m.group(6):
                raise ValueError('Carácter no válido en la fila %d: «%s».' % (r + 1, m.group(6)))
            letra, prom = (m.group(2), m.group(3)) if m.group(2) else (m.group(4), m.group(5))
            t = tipos.get(letra.upper())
            if t is None:
                raise ValueError('«%s» no es una pieza de %s (piezas: %s).' % (
                    letra, v.nombre, ', '.join(_token(t, 0) for t in v.paleta)))
            if c >= v.ancho:
                raise ValueError('La fila %d tiene más de %d columnas.' % (r + 1, v.ancho))
            color = 0 if letra[0].isupper() else 1
            piezas[r * v.ancho + c] = (t, color, bool(prom) and v.tiene_promocionadas)
            c += 1
        if c != v.ancho:
            raise ValueError('La fila %d tiene %d columnas y deben ser %d.' % (r + 1, c, v.ancho))
    return piezas, turno


def inicio_de_fen(v, texto):
    piezas, turno = leer_fen(v, texto)
    return {'piezas': [[sq, t, c, pr] for sq, (t, c, pr) in sorted(piezas.items())], 'turno': turno}


# ---------------------------------------------------------------------- partidas
def _necesita_config(v):
    return v.spec.get('tipo') == 'generica' and v.id not in G.PRESETS


def partida(v, estado_inicial, notas, encabezados, resultado=None, inicio=None):
    """Texto de una partida. notas: las jugadas en notación; resultado: 'blancas', 'negras', 'tablas'."""
    lineas = ['[Variante "%s"]' % v.nombre]
    for k, val in encabezados:
        if val:
            lineas.append('[%s "%s"]' % (k, str(val).replace('"', "'")))
    res = RESULTADOS.get(resultado, '*')
    lineas.append('[Resultado "%s"]' % res)
    if inicio is not None:
        lineas.append('[Posicion "%s"]' % fen(v, estado_inicial))
    if _necesita_config(v):
        lineas.append('[Configuracion "%s"]' % json.dumps(v.cfg, ensure_ascii=False, separators=(',', ':')).replace('"', '\\"'))
    lineas.append('')
    negras_primero = estado_inicial.turn == 1
    k, n = 0, 1
    if negras_primero and notas:
        lineas.append('%d. ...  %s' % (n, notas[0]))
        k, n = 1, 2
    while k < len(notas):
        par = notas[k:k + 2]
        lineas.append('%d. %s' % (n, '  '.join(par)))
        k, n = k + 2, n + 1
    lineas.append(res)
    return '\n'.join(lineas) + '\n'


def _variante(encabezados, actual=None):
    if 'Configuracion' in encabezados:
        try:
            return V.Generica(json.loads(encabezados['Configuracion']))
        except (ValueError, KeyError, TypeError) as e:
            raise ValueError('La configuración de la variante no es válida: %s' % e)
    nombre = V.nombre_actual(encabezados.get('Variante', '').strip()).lower()
    candidatas = V.todas() + [V.Generica(c) for c in V.guardadas()]
    for v in candidatas:
        if v.nombre.lower() == nombre or v.id == nombre:
            return v
    if actual is not None and not nombre:
        return actual
    raise ValueError('No conozco la variante «%s». Las predefinidas y las guardadas en el Laboratorio se '
                     'reconocen por su nombre.' % encabezados.get('Variante', ''))


def leer_partida(texto, actual=None):
    """(variante, inicio, [(idx, nota)], encabezados). ValueError con la jugada que no se reconoce."""
    encabezados = dict(re.findall(r'\[(\w+)\s+"((?:[^"\\]|\\.)*)"\]', texto))
    encabezados = {k: v.replace('\\"', '"') for k, v in encabezados.items()}
    v = _variante(encabezados, actual)
    inicio = inicio_de_fen(v, encabezados['Posicion']) if encabezados.get('Posicion') else None
    st = v.inicial() if inicio is None else v.construir(inicio['piezas'], inicio['turno'])
    cuerpo = re.sub(r'\[[^\]]*\]', ' ', texto)
    cuerpo = re.sub(r'\{[^}]*\}', ' ', cuerpo)  # comentarios
    jugadas, pos = [], 0
    while True:
        m = re.compile(r'(\s+|\d+\.(\s*\.\.\.?)?|\.\.\.)+').match(cuerpo, pos)
        if m:
            pos = m.end()
        if pos >= len(cuerpo) or re.match(r'(1-0|0-1|1/2-1/2|½-½|\*)\s*$', cuerpo[pos:]):
            break
        movs = v.legal(st)
        mejor = None
        for i, (mv, n) in enumerate(movs):
            nota = v.notacion(st, mv, n, movs)
            fin = pos + len(nota)
            if cuerpo.startswith(nota, pos) and (fin == len(cuerpo) or cuerpo[fin] in ' \t\r\n+#!?'):
                if mejor is None or len(nota) > len(mejor[1]):
                    mejor = (i, nota)
        if mejor is None:
            fragmento = cuerpo[pos:pos + 20].split('\n')[0]
            raise ValueError('No reconozco la jugada %d («%s…»): no es legal en esa posición.' % (
                len(jugadas) + 1, fragmento.strip()))
        i, nota = mejor
        pos += len(nota)
        sufijo = re.compile(r'[+#!?]*').match(cuerpo, pos)
        jugadas.append((i, nota + ''.join(ch for ch in sufijo.group() if ch in '+#')))
        pos = sufijo.end()
        st = movs[i][1]
    return v, inicio, jugadas, encabezados


def texto_de_registro(r):
    """Texto de una partida guardada (registro con el formato de las bitácoras), para exportar varias juntas."""
    import variantes as V
    v = V.crear(r.get('variante') or {'tipo': 'extendido'})
    ini = r.get('inicio')
    st = v.inicial() if ini is None else v.construir(ini['piezas'], ini['turno'])
    nivel = lambda c: (c or {}).get('nivel') or ('profundidad %s' % (c or {}).get('profundidad', '?'))
    if r.get('dos_jugadores'):
        blancas, negras = 'Jugador 1', 'Jugador 2'
    elif r.get('origen') == 'partida':
        compu = 'Computadora (%s)' % nivel(r.get('computadora'))
        blancas, negras = ('Tú', compu) if r.get('humano', 'blancas') == 'blancas' else (compu, 'Tú')
    else:
        blancas, negras = nivel(r.get('blancas')), nivel(r.get('negras'))
    enc = [('Fecha', (r.get('fecha') or '')[:16]), ('Blancas', blancas), ('Negras', negras),
           ('Motivo', r.get('motivo'))]
    return partida(v, st, [j['j'] for j in r.get('jugadas', [])], enc, r.get('resultado'), ini)
