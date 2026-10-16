"""Problemas de práctica a partir de las bitácoras: mates en N y, con --tacticos, problemas tácticos.

Busca en las bitácoras las posiciones en las que la computadora vio un mate forzado (jugadas con
«m»), comprueba cada una con una búsqueda propia (2N medias jugadas) y
guarda las confirmadas en Juego/problemas.json, que el juego muestra en «Problemas». Sirven las
bitácoras del simulador (--bitacora), del modo espectador, de las partidas guardadas y de las
simulaciones del Laboratorio, de cualquier variante.

Problemas tácticos (--tacticos): posiciones en las que existe una jugada que gana material o una ventaja
clara y que es la única buena. Se buscan donde la evaluación de la partida dio un salto (alguien no vio una
táctica) y se comprueban con una búsqueda profunda: la mejor jugada debe ganar al menos --ganancia peones
respecto de la evaluación estática, la segunda mejor debe quedar al menos --margen peones por debajo, y una
búsqueda corta (profundidad 2) no debe encontrarla (si no, sería demasiado fácil). Cada uno lleva su tema:
captura, captura en cadena de la Catapulta, promoción, jaque o jugada tranquila. Sirven también para el
examen táctico de la computadora (examen_tactico.py).

Las posiciones ya comprobadas (con cualquier resultado) se anotan en Juego/problemas_revisados.json: una
búsqueda posterior solo revisa las de partidas nuevas (o las que no alcanzó --max). Con --todo se revisan
todas otra vez (por ejemplo, tras cambiar --ganancia o --margen).

Ejemplos:
  pypy3 extraer_problemas.py                       # carpetas del juego y bitácoras de esta carpeta
  pypy3 extraer_problemas.py --tacticos texel_p3_bitacora.jsonl --procesos 22 --max 300
  pypy3 extraer_problemas.py prof4_bitacora.jsonl --max-mate 2 --procesos 4
  pypy3 extraer_problemas.py ../Juego/bitacoras --tiempo 60
"""
import argparse, glob, json, os, random, sys, time
from multiprocessing import Pool

AQUI = os.path.dirname(os.path.abspath(__file__))
JUEGO = os.path.join(os.path.dirname(AQUI), 'Juego')
sys.path.insert(0, AQUI)
sys.path.insert(0, JUEGO)
import bitacora
from ia import Partida

MATE = 100000
SALIDA = os.path.join(JUEGO, 'problemas.json')
# posiciones ya comprobadas (de cualquier resultado): una segunda búsqueda solo revisa las nuevas
REVISADOS = os.path.join(JUEGO, 'problemas_revisados.json')
POR_DEFECTO = [os.path.join(JUEGO, d) for d in ('bitacoras', 'partidas', 'simulaciones')] + \
              sorted(glob.glob(os.path.join(AQUI, '*bitacora*.jsonl')))


def archivos(rutas):
    for r in rutas:
        if os.path.isdir(r):
            for f in sorted(os.listdir(r)):
                if f.endswith('.jsonl'):
                    yield os.path.join(r, f)
        elif os.path.isfile(r):
            yield r


def candidatos(ruta, max_mate):
    """(registro, k, n) de las posiciones tras k jugadas en las que el bando que mueve tendría mate en n."""
    try:
        partidas = bitacora.leer(ruta)
    except (OSError, ValueError):
        return
    for numero, r in enumerate(partidas, 1):
        ultimo = None  # (k, bando) del último candidato, para tomar solo el primero de cada racha
        for k, j in enumerate(r.get('jugadas', [])):
            if 'm' not in j:
                continue
            ganador = 0 if j['m'] > 0 else 1
            n = abs(j['m'])
            turno = (r.get('inicio') or {}).get('turno', 0)
            mueve = (turno + k) % 2
            # la jugada k la hizo «mueve»: si el mate es suyo, la posición es la de antes de la jugada;
            # si es del rival, la de después (le toca al que da mate)
            pos = k if ganador == mueve else k + 1
            if n > max_mate or (ultimo and ultimo[1] == ganador and pos - ultimo[0] <= 2 * n):
                continue
            ultimo = (pos, ganador)
            yield r, numero, pos, n


def candidatos_tacticos(ruta, salto):
    """(registro, número, k) de las posiciones tras k jugadas en las que, a juzgar por la evaluación de la
    partida, el bando que mueve tenía una táctica: la evaluación cambió a su favor en al menos «salto»."""
    try:
        partidas = bitacora.leer(ruta)
    except (OSError, ValueError):
        return
    for numero, r in enumerate(partidas, 1):
        j = r.get('jugadas', [])
        turno = (r.get('inicio') or {}).get('turno', 0)
        for k in range(1, len(j)):
            a, b = j[k - 1], j[k]
            if 'e' not in a or 'e' not in b or a.get('azar') or b.get('azar'):
                continue
            mueve = (turno + k) % 2  # quien juega la jugada k
            cambio = (b['e'] - a['e']) * (1 if mueve == 0 else -1)
            if cambio >= salto:
                yield r, numero, k


def tema(v, st, mv, n):
    if v.destino(mv) is None:
        return 'extensión'  # extensiones del Ajedrez Extendido (cuestan el turno)
    if v.es_cadena(mv):
        return 'Catapulta en cadena'
    if mv[0] in ('cv', 'gp', 'pr'):
        return 'extensión'
    if v.en_jaque(n, n.turn):
        return 'jaque'
    if v.es_captura(st, mv):
        return 'captura'
    return 'jugada tranquila'


def linea_principal(p, v, b, st, mv, sig, movs, plies=6):
    """La línea que calculó el buscador b (de su tabla de transposición): la jugada mv y las siguientes,
    como [{'i': índice en legal(), 'j': notación}]. Sirve para mostrar la idea completa del problema."""
    linea = [{'i': next(i for i, (m, _) in enumerate(movs) if m == mv), 'j': v.notacion(st, mv, sig, movs)}]
    s, vistas = sig, {p.hash(st)}
    for _ in range(plies - 1):
        h = p.hash(s)
        ent = b.tt.get(h)
        if not ent or ent[3] is None or h in vistas:
            break
        vistas.add(h)
        ms = p.legal(s)
        k = next((i for i, (m, _) in enumerate(ms) if m == ent[3]), None)
        if k is None:
            break
        m, n = ms[k]
        linea.append({'i': k, 'j': v.notacion(s, m, n, ms)})
        s = n
    return linea


def verificar_tactico(tarea):
    ruta, numero, r, k, prof, tiempo, ganancia, margen = tarea
    spec = r.get('variante') or {'tipo': 'extendido'}
    try:
        p = Partida(spec)
        st = p.inicial(r.get('inicio'))
        hist = [j['i'] for j in r['jugadas'][:k]]
        for i in hist:
            st = p.legal(st)[i][1]
        movs = p.legal(st)
        if len(movs) < 2:
            return None
        from variantes import crear
        v = crear(spec)
        if v.en_jaque(st, st.turn):
            return None  # en jaque las jugadas son forzadas: no es un problema interesante
        b = p.nuevo_buscador(tiempo, prof, 0.0)
        (mv, sig), _ = b.choose(st, movs, random.Random(0))
        mejor = b.puntaje
        if mejor is None or abs(mejor) > MATE / 2:
            return None  # los mates ya son los otros problemas
        estatica = p.evaluar(st)
        if mejor - estatica < ganancia:
            return None
        resto = [x for x in movs if x[0] is not mv]
        b2 = p.nuevo_buscador(tiempo, prof, 0.0)
        b2.choose(st, resto, random.Random(0))
        segunda = b2.puntaje
        if segunda is None or mejor - segunda < margen:
            return None  # no es la única buena
        linea = linea_principal(p, v, b, st, mv, sig, movs)
        corta = p.nuevo_buscador(None, 2, 0.0)
        (mv2, _), _ = corta.choose(st, movs, random.Random(0))
        if mv2 == mv:
            return None  # demasiado fácil: se ve a profundidad 2
        idx = next(i for i, (m, _) in enumerate(movs) if m == mv)
        return {'id': 't%s:%x' % (spec.get('tipo'), p.hash(st) & 0xFFFFFFFFFFFF), 'tipo': 'tactico',
                'variante': spec, 'variante_nombre': r.get('variante_nombre') or v.nombre,
                'inicio': r.get('inicio'), 'hist': hist, 'turno': st.turn,
                'gana': round(mejor - estatica, 1), 'margen': round(mejor - segunda, 1), 'prof': prof,
                'tema': tema(v, st, mv, sig), 'solucion': v.notacion(st, mv, sig, movs), 'solucion_idx': idx,
                'linea': linea,
                'origen': '%s, partida %d, jugada %d' % (os.path.basename(ruta), numero, k // 2 + 1)}
    except Exception as e:
        return {'error': '%s: %s' % (os.path.basename(ruta), e)}


def clave_candidato(modo, ruta, numero, r, k):
    """Identifica una posición candidata: tipo de búsqueda, bitácora, partida (y su fecha) y jugada."""
    return '%s|%s|%d|%s|%d' % (modo, os.path.basename(ruta), numero, r.get('fecha', ''), k)


def _mate_con_clave(t):
    return t[0], verificar(t[1])


def _tactico_con_clave(t):
    return t[0], verificar_tactico(t[1])


def verificar(tarea):
    ruta, numero, r, k, n, tiempo = tarea
    spec = r.get('variante') or {'tipo': 'extendido'}
    try:
        p = Partida(spec)
        st = p.inicial(r.get('inicio'))
        hist = [j['i'] for j in r['jugadas'][:k]]
        for i in hist:
            st = p.legal(st)[i][1]
        movs = p.legal(st)
        if not movs:
            return None
        b = p.nuevo_buscador(tiempo, 2 * n, 0.0)  # una media jugada más para ver el mate en la hoja
        (mv, sig), _ = b.choose(st, movs, random.Random(0))
        puntaje = getattr(b, 'puntaje', None)
        if puntaje is None or puntaje < MATE / 2:
            return None
        n_real = (round(MATE - puntaje) + 1) // 2
        if not 1 <= n_real <= n:
            return None
        from variantes import crear
        v = crear(spec)
        idx = next(i for i, (m, _) in enumerate(movs) if m == mv)
        return {'id': '%s:%x' % (spec.get('tipo'), p.hash(st) & 0xFFFFFFFFFFFF),
                'variante': spec, 'variante_nombre': r.get('variante_nombre') or v.nombre,
                'inicio': r.get('inicio'), 'hist': hist, 'turno': st.turn, 'mate_en': n_real,
                'solucion': v.notacion(st, mv, sig, movs), 'solucion_idx': idx,
                'origen': '%s, partida %d, jugada %d' % (os.path.basename(ruta), numero, k // 2 + 1)}
    except Exception as e:  # una bitácora de otra versión de las reglas no debe detener todo
        return {'error': '%s: %s' % (os.path.basename(ruta), e)}


def completar_linea(tarea):
    """Calcula la línea principal de un problema táctico guardado sin ella."""
    pr, tiempo = tarea
    try:
        spec = pr.get('variante') or {'tipo': 'extendido'}
        p = Partida(spec)
        from variantes import crear
        v = crear(spec)
        st = p.inicial(pr.get('inicio'))
        for i in pr['hist']:
            st = p.legal(st)[i][1]
        movs = p.legal(st)
        b = p.nuevo_buscador(tiempo, pr.get('prof', 5), 0.0)
        b.choose(st, movs, random.Random(0))
        mv, sig = movs[pr['solucion_idx']]
        # la primera jugada es la de la solución; el resto, lo que el buscador espera tras ella
        return pr['id'], linea_principal(p, v, b, st, mv, sig, movs)
    except Exception as e:
        return pr['id'], None


def main():
    ap = argparse.ArgumentParser(description='Problemas de mate a partir de las bitácoras',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('rutas', nargs='*', help='bitácoras o carpetas (por defecto, las del juego y las de aquí)')
    ap.add_argument('--max-mate', type=int, default=3, help='mate en cuántas jugadas como máximo (3)')
    ap.add_argument('--tiempo', type=float, default=30, help='segundos máximos para comprobar cada uno (30)')
    ap.add_argument('--procesos', type=int, default=1, help='comprobaciones en paralelo (1)')
    ap.add_argument('--salida', default=SALIDA, help='archivo de problemas (Juego/problemas.json)')
    ap.add_argument('--tacticos', action='store_true', help='busca problemas tácticos en lugar de mates')
    ap.add_argument('--prof', type=int, default=5, help='tácticos: profundidad de la búsqueda (5)')
    ap.add_argument('--ganancia', type=float, default=2.0, help='tácticos: peones que debe ganar (2)')
    ap.add_argument('--margen', type=float, default=1.5,
                    help='tácticos: ventaja mínima sobre la segunda mejor jugada (1.5)')
    ap.add_argument('--salto', type=float, default=2.0,
                    help='tácticos: salto de la evaluación de la partida que marca un candidato (2)')
    ap.add_argument('--max', type=int, default=0, help='máximo de candidatos a comprobar (0 = todos)')
    ap.add_argument('--revisados', default=REVISADOS, help='registro de posiciones ya comprobadas')
    ap.add_argument('--todo', action='store_true',
                    help='revisa también las posiciones ya comprobadas en búsquedas anteriores')
    ap.add_argument('--completar-lineas', action='store_true',
                    help='calcula la línea principal de los problemas tácticos que no la tienen y termina')
    a = ap.parse_args()
    if a.tacticos and a.tiempo == 30:
        a.tiempo = 15
    try:
        with open(a.salida, encoding='utf-8') as f:
            problemas = json.load(f)
    except (OSError, ValueError):
        problemas = []
    conocidos = {p['id'] for p in problemas}
    if a.completar_lineas:
        faltan = [x for x in problemas if x.get('tipo') == 'tactico' and not x.get('linea')]
        print('Calculando la línea de %d problemas tácticos...' % len(faltan), flush=True)
        tareas = [(x, a.tiempo if a.tiempo != 30 else 15) for x in faltan]
        it = Pool(a.procesos).imap_unordered(completar_linea, tareas) if a.procesos > 1 else map(completar_linea, tareas)
        por_id = {x['id']: x for x in problemas}
        hechos = 0
        for k, (ident, linea) in enumerate(it, 1):
            if linea:
                por_id[ident]['linea'] = linea
                hechos += 1
            print('[%d/%d] %s' % (k, len(tareas), ' '.join(x['j'] for x in linea) if linea else 'sin línea'), flush=True)
        with open(a.salida, 'w', encoding='utf-8') as f:
            json.dump(problemas, f, ensure_ascii=False)
        print('Listo: %d líneas agregadas.' % hechos)
        return
    try:
        with open(a.revisados, encoding='utf-8') as fr:
            revisados = set(json.load(fr))
    except (OSError, ValueError):
        revisados = set()
    modo = 'tactico' if a.tacticos else 'mate'
    tareas, saltadas = [], 0
    for ruta in archivos(a.rutas or POR_DEFECTO):
        if a.tacticos:
            gen = ((r, numero, k, (ruta, numero, r, k, a.prof, a.tiempo, a.ganancia, a.margen))
                   for r, numero, k in candidatos_tacticos(ruta, a.salto))
        else:
            gen = ((r, numero, k, (ruta, numero, r, k, n, a.tiempo)) for r, numero, k, n in candidatos(ruta, a.max_mate))
        for r, numero, k, tarea in gen:
            c = clave_candidato(modo, ruta, numero, r, k)
            if c in revisados and not a.todo:
                saltadas += 1
                continue
            tareas.append((c, tarea))
    if a.max and len(tareas) > a.max:
        random.Random(0).shuffle(tareas)
        tareas = tareas[:a.max]
    print('%d posiciones candidatas nuevas (%d ya revisadas antes se saltan); comprobando con %d proceso%s...' % (
        len(tareas), saltadas, a.procesos, '' if a.procesos == 1 else 's'), flush=True)
    t0, nuevos = time.time(), 0

    def guardar_revisados():
        with open(a.revisados + '.tmp', 'w', encoding='utf-8') as fr:
            json.dump(sorted(revisados), fr, ensure_ascii=False)
        os.replace(a.revisados + '.tmp', a.revisados)

    funcion = _tactico_con_clave if a.tacticos else _mate_con_clave
    it = Pool(a.procesos).imap_unordered(funcion, tareas) if a.procesos > 1 else map(funcion, tareas)
    for i, (c, p) in enumerate(it, 1):
        if not (p and 'error' in p):  # las que dieron error se reintentan la próxima vez
            revisados.add(c)
        if i % 25 == 0:
            guardar_revisados()
        if p is None:
            estado = 'descartado'
        elif 'error' in p:
            estado = 'error: ' + p['error']
        elif p['id'] in conocidos:
            estado = 'ya estaba'
        else:
            problemas.append(p)
            conocidos.add(p['id'])
            nuevos += 1
            estado = ('táctica: %s, gana %.1f (%s)' % (p['tema'], p['gana'], p['variante_nombre'])
                      if a.tacticos else 'mate en %d (%s)' % (p['mate_en'], p['variante_nombre']))
            with open(a.salida, 'w', encoding='utf-8') as f:
                json.dump(problemas, f, ensure_ascii=False)
        print('[%d/%d] %s' % (i, len(tareas), estado), flush=True)
    guardar_revisados()
    print('\nListo en %.0f s: %d problemas nuevos, %d en total, en %s.' % (
        time.time() - t0, nuevos, len(problemas), a.salida), flush=True)


if __name__ == '__main__':
    main()
