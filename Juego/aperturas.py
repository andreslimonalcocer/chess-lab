"""Explorador de aperturas del Ajedrez Extendido: estadísticas de las partidas (simulaciones, espectador y tus partidas)
por posición, junto con el libro de aperturas calculado por la computadora (Simulador/libro_aperturas.py).

Las posiciones se identifican por la secuencia de jugadas desde la inicial (índices de jugadas legales, como
en las bitácoras), así que dos órdenes de jugadas distintos que llegan a la misma posición se cuentan aparte.
"""
import glob, json, os

AQUI = os.path.dirname(os.path.abspath(__file__))
SIMULADOR = os.path.join(os.path.dirname(AQUI), 'Simulador')
LIBRO = os.path.join(AQUI, 'libro_aperturas.json')
PLIES = 40  # medias jugadas que se cuentan de cada partida


def fuentes(simulaciones=True, mias=True):
    """[(ruta, tipo)]: bitácoras del simulador ('simulacion'), del espectador y tus partidas ('mias')."""
    out = []
    if simulaciones:
        for ruta in sorted(glob.glob(os.path.join(SIMULADOR, '*.jsonl'))):
            try:
                with open(ruta, encoding='utf-8') as f:
                    if 'bitacora-ajedrez' in f.read(300):
                        out.append((ruta, 'simulacion'))
            except OSError:
                pass
    if mias:
        for carpeta in ('bitacoras', 'partidas'):
            out += [(r, 'mias') for r in sorted(glob.glob(os.path.join(AQUI, carpeta, '*.jsonl')))]
    return out


def construir(simulaciones=True, mias=True):
    """(árbol, partidas): árbol {clave de la posición: {idx: [nota, partidas, blancas, tablas, negras, al azar]}}."""
    arbol, total = {}, 0
    for ruta, _ in fuentes(simulaciones, mias):
        try:
            with open(ruta, encoding='utf-8') as f:
                lineas = f.readlines()
        except OSError:
            continue
        for linea in lineas:
            try:
                r = json.loads(linea)
            except ValueError:
                continue
            if (r.get('variante') or {}).get('tipo', 'extendido') != 'extendido' or r.get('inicio') is not None:
                continue
            res = r.get('resultado')
            if res not in ('blancas', 'negras', 'tablas'):
                continue
            col = {'blancas': 2, 'tablas': 3, 'negras': 4}[res]
            total += 1
            clave = []
            for j in r.get('jugadas', [])[:PLIES]:
                nodo = arbol.setdefault(','.join(clave), {})
                x = nodo.setdefault(j['i'], [j['j'].rstrip('+#'), 0, 0, 0, 0, 0])
                x[1] += 1
                x[col] += 1
                if j.get('azar'):
                    x[5] += 1
                clave.append(str(j['i']))
    return arbol, total


def cargar_libro():
    try:
        with open(LIBRO, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def filas(arbol, libro, hist, turno):
    """Jugadas desde la posición hist: [{'idx', 'nota', 'n', 'b', 't', 'ng', 'azar', 'puntos', 'libro'}], de la
    más jugada a la menos (las del libro primero si no hay partidas). 'puntos': % para el bando que mueve."""
    clave = ','.join(map(str, hist))
    out = {}
    for idx, (nota, n, b, t, ng, azar) in arbol.get(clave, {}).items():
        propios = b if turno == 0 else ng
        out[idx] = {'idx': idx, 'nota': nota, 'n': n, 'b': b, 't': t, 'ng': ng, 'azar': azar,
                    'puntos': 100.0 * (propios + t / 2) / n, 'libro': None}
    for idx, nota, sc in (libro.get('posiciones') or {}).get(clave, []):
        x = out.setdefault(idx, {'idx': idx, 'nota': nota, 'n': 0, 'b': 0, 't': 0, 'ng': 0, 'azar': 0,
                                 'puntos': None, 'libro': None})
        x['libro'] = sc
    return sorted(out.values(), key=lambda x: (-x['n'], -(x['libro'] if x['libro'] is not None else -99)))
