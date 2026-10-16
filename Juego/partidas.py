"""Partidas guardadas y perfil del jugador (Elo e historial).

Cada partida contra la computadora se guarda automáticamente, jugada a jugada, en la carpeta
'partidas' con el formato de las bitácoras (Simulador/bitacora.py); así se puede reanudar,
reproducir o analizar. El perfil (perfil.json) lleva el Elo del jugador en cada variante cuyos
niveles están calibrados en Elo, con el sistema Elo del ajedrez.
"""
import json, os, time

AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA = os.path.join(AQUI, 'partidas')
PERFIL = os.path.join(AQUI, 'perfil.json')
ELO_INICIAL = 1200


def nueva_ruta(variante_id):
    os.makedirs(CARPETA, exist_ok=True)
    return os.path.join(CARPETA, '%s_%s.jsonl' % (time.strftime('%Y%m%d_%H%M%S'), variante_id))


def guardar(ruta, registro):
    with open(ruta, 'w', encoding='utf-8') as f:
        f.write(json.dumps(registro, ensure_ascii=False) + '\n')


def leer(ruta):
    with open(ruta, encoding='utf-8') as f:
        return actualizar(json.loads(f.readline()))


def actualizar(r):
    """Pone al día los nombres antiguos (el Ajedrez 11×11 ahora es el Ajedrez Extendido; sus promociones,
    extensiones)."""
    nombre = r.get('variante_nombre')
    if nombre in ('Ajedrez 11×11', 'Ajedrez 11x11'):
        r['variante_nombre'] = 'Ajedrez Extendido'
    if r.get('tema') == 'promoción' and (r.get('variante') or {}).get('tipo', 'extendido') == 'extendido':
        r['tema'] = 'extensión'
    return r


def listar():
    """[(ruta, registro)] de las partidas guardadas, de la más reciente a la más antigua."""
    if not os.path.isdir(CARPETA):
        return []
    out = []
    for nombre in sorted(os.listdir(CARPETA), reverse=True):
        if nombre.endswith('.jsonl'):
            ruta = os.path.join(CARPETA, nombre)
            try:
                out.append((ruta, leer(ruta)))
            except (OSError, ValueError):
                pass
    return out


def sin_terminar():
    """La partida sin terminar más reciente (ruta, registro), o None."""
    for ruta, r in listar():
        if not r.get('resultado') and r.get('jugadas'):
            return ruta, r
    return None


def describir(r):
    jugadas = (len(r.get('jugadas', [])) + 1) // 2
    nivel = 'otra persona' if r.get('dos_jugadores') else (r.get('computadora') or {}).get('nivel', '?')
    estado = ('%s (%s)' % (r['resultado'], r.get('motivo', ''))) if r.get('resultado') else 'sin terminar'
    color = r.get('humano', 'blancas')
    return '%s · %s · con %s contra %s · %d jugadas · %s' % (
        r.get('fecha', '')[:16], r.get('variante_nombre', '?'), color, nivel, jugadas, estado)


# ---------------------------------------------------------------------- perfil y Elo
def cargar_perfil():
    try:
        with open(PERFIL, encoding='utf-8') as f:
            perfil = json.load(f)
    except (OSError, ValueError):
        return {'variantes': {}}
    for d in perfil.get('variantes', {}).values():  # nombres antiguos de las variantes
        if d.get('nombre') in ('Ajedrez 11×11', 'Ajedrez 11x11'):
            d['nombre'] = 'Ajedrez Extendido'
    return perfil


def guardar_perfil(perfil):
    with open(PERFIL, 'w', encoding='utf-8') as f:
        json.dump(perfil, f, ensure_ascii=False, indent=1)


def datos_variante(perfil, variante_id):
    return perfil['variantes'].setdefault(variante_id, {'elo': ELO_INICIAL, 'partidas': 0, 'historial': []})


def esperado(elo, rival):
    return 1 / (1 + 10 ** ((rival - elo) / 400))


def registrar(variante_id, variante_nombre, nivel, elo_rival, puntos, color):
    """Actualiza el Elo tras una partida puntuada (puntos: 1, 0.5 o 0). Devuelve (antes, después).
    K = 40 en las primeras 20 partidas (el Elo se acerca rápido al real) y 20 después."""
    perfil = cargar_perfil()
    d = datos_variante(perfil, variante_id)
    antes = d['elo']
    k = 40 if d['partidas'] < 20 else 20
    despues = round(antes + k * (puntos - esperado(antes, elo_rival)))
    d['elo'], d['partidas'] = despues, d['partidas'] + 1
    d['historial'].append({'fecha': time.strftime('%Y-%m-%d %H:%M'), 'nivel': nivel, 'elo_rival': elo_rival,
                           'puntos': puntos, 'color': color, 'elo_antes': antes, 'elo_despues': despues})
    d['nombre'] = variante_nombre
    guardar_perfil(perfil)
    return antes, despues


def elo_jugador(variante_id):
    d = cargar_perfil()['variantes'].get(variante_id)
    return (d['elo'], d['partidas']) if d else (None, 0)


# ---------------------------------------------------------------------- problemas
PROBLEMAS = os.path.join(AQUI, 'problemas.json')
MIS_PROBLEMAS = os.path.join(AQUI, 'mis_problemas.json')  # tus errores, del análisis de tus partidas
ELO_PROBLEMAS = 1200
# Elo de un problema según la profundidad mínima con que lo resuelve la computadora (Simulador/
# dificultad_problemas.py) o, si aún no se midió, según su tipo
ELO_TEMA = {'captura': 1100, 'jaque': 1250, 'extensión': 1250, 'promoción': 1250, 'Catapulta en cadena': 1350,
            'jugada tranquila': 1500, 'tu error': 1250}
ELO_MATE = {1: 900, 2: 1350, 3: 1750}


def _leer_json(ruta):
    try:
        with open(ruta, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def cargar_problemas():
    """Los problemas de problemas.json y tus errores convertidos en problemas (mis_problemas.json)."""
    return [actualizar(p) for p in _leer_json(PROBLEMAS) + _leer_json(MIS_PROBLEMAS)]


def agregar_mis_problemas(nuevos):
    """Agrega problemas personales (sin repetir). Devuelve cuántos son nuevos."""
    actuales = _leer_json(MIS_PROBLEMAS)
    ids = {p['id'] for p in actuales}
    nuevos = [p for p in nuevos if p['id'] not in ids]
    if nuevos:
        with open(MIS_PROBLEMAS, 'w', encoding='utf-8') as f:
            json.dump(actuales + nuevos, f, ensure_ascii=False)
    return len(nuevos)


def elo_problema(p):
    if p.get('dificultad'):  # profundidad mínima con que la computadora lo resuelve
        return 650 + 200 * min(p['dificultad'], 8)
    if p.get('tipo', 'mate') == 'mate':
        return ELO_MATE.get(p.get('mate_en'), 1750)
    return ELO_TEMA.get('tu error' if p.get('personal') else p.get('tema'), 1300)


def categoria_problema(p):
    if p.get('personal'):
        return 'Mis errores'
    if p.get('tipo', 'mate') == 'mate':
        return 'Mate en %d' % p.get('mate_en', 0)
    return 'Táctica: %s' % p.get('tema', '?')


def elo_problemas():
    """(tu Elo de problemas, problemas puntuados)."""
    d = cargar_perfil().get('elo_problemas') or {}
    return d.get('elo', ELO_PROBLEMAS), d.get('n', 0)


def marcar_problema(ident, resuelto, elo=None):
    """Anota un intento; un problema queda resuelto si alguna vez se resolvió. El primer intento de cada
    problema actualiza tu Elo de problemas (si se da el Elo del problema): devuelve (antes, después) o None."""
    perfil = cargar_perfil()
    p = perfil.setdefault('problemas', {}).get(ident)
    nuevo = p is None
    if nuevo:
        p = perfil['problemas'][ident] = {'resuelto': False, 'intentos': 0, 'primero': resuelto}
    p['intentos'] += 1
    p['resuelto'] = p['resuelto'] or resuelto
    cambio = None
    if nuevo and elo is not None:
        d = perfil.setdefault('elo_problemas', {'elo': ELO_PROBLEMAS, 'n': 0, 'historial': []})
        antes = d['elo']
        k = 40 if d['n'] < 20 else 20
        d['elo'] = round(antes + k * ((1.0 if resuelto else 0.0) - esperado(antes, elo)))
        d['n'] += 1
        d['historial'] = (d.get('historial', []) + [[time.strftime('%Y-%m-%d'), d['elo']]])[-500:]
        p['elo'] = elo
        cambio = (antes, d['elo'])
    guardar_perfil(perfil)
    return cambio


def estadisticas_problemas(problemas):
    """[(categoría, intentados, resueltos al primer intento, resueltos alguna vez)] de tus intentos."""
    hechos = cargar_perfil().get('problemas', {})
    tabla = {}
    for p in problemas:
        h = hechos.get(p['id'])
        if h is None:
            continue
        t = tabla.setdefault(categoria_problema(p), [0, 0, 0])
        t[0] += 1
        t[1] += 1 if h.get('primero', h.get('resuelto') and h.get('intentos') == 1) else 0
        t[2] += 1 if h.get('resuelto') else 0
    return sorted((c, *v) for c, v in tabla.items())


def problema_del_dia(problemas, elo, fecha=None):
    """Un problema sin resolver cercano a tu Elo, el mismo durante todo el día."""
    import hashlib
    resueltos = problemas_resueltos()
    candidatos = [p for p in problemas if p['id'] not in resueltos and not p.get('personal')]
    if not candidatos:
        return None
    candidatos.sort(key=lambda p: (abs(elo_problema(p) - elo), p['id']))
    cerca = [p for p in candidatos if abs(elo_problema(p) - elo) <= 150] or candidatos[:30]
    semilla = int(hashlib.sha1((fecha or time.strftime('%Y-%m-%d')).encode()).hexdigest(), 16)
    return cerca[semilla % len(cerca)]


def marcar_leccion(ident, hechas):
    """Anota cuántos ejercicios de una lección se han completado (se queda con el máximo)."""
    perfil = cargar_perfil()
    d = perfil.setdefault('lecciones', {})
    d[ident] = max(d.get(ident, 0), hechas)
    guardar_perfil(perfil)


def lecciones_hechas():
    """{id de lección: ejercicios completados}."""
    return cargar_perfil().get('lecciones', {})


def problemas_resueltos():
    return {k for k, v in cargar_perfil().get('problemas', {}).items() if v.get('resuelto')}
