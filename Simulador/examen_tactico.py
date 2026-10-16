"""Examen táctico de la computadora: resuelve los problemas de Juego/problemas.json (mates en N y
problemas tácticos de extraer_problemas.py --tacticos) con una o varias configuraciones y dice cuántos
resuelve, por tipo y por tema. Es mucho más rápido que un SPRT (minutos en lugar de horas) y sirve de
filtro: un cambio que empeora la táctica se ve aquí antes de gastar horas en partidas. No sustituye al
SPRT, que mide la fuerza real.

Un problema de mate está resuelto si la computadora ve el mate en las jugadas pedidas (o menos); uno
táctico, si elige la jugada de la solución (que es la única buena: la segunda está al menos 1.5 peones por
debajo).

Las configuraciones se escriben como en comparar.py (prof, tiempo, temp, pesos, opciones, parametros,
nombre); para versiones viejas del motor guardadas en otra carpeta (ruta=) usa comparar.py. Ejemplos:
  pypy3 examen_tactico.py --procesos 22                                   # v6 con 1 s por problema
  pypy3 examen_tactico.py "tiempo=1,prof=30,nombre=v6" "tiempo=1,prof=30,parametros=texel_parametros.json,nombre=texel" --procesos 22
  pypy3 examen_tactico.py "prof=3,nombre=p3" "prof=4,nombre=p4" --tipo tactico --variante extendido
"""
import argparse, json, os, random, sys, time
from multiprocessing import Pool

AQUI = os.path.dirname(os.path.abspath(__file__))
JUEGO = os.path.join(os.path.dirname(AQUI), 'Juego')
sys.path.insert(0, AQUI)
from comparar import leer_config, _pares

MATE = 100000
PROBLEMAS = os.path.join(JUEGO, 'problemas.json')
_CFG = None


def preparar(cfg):
    """Inicializa un proceso con el motor y la configuración (ruta, opciones, pesos y parámetros)."""
    global _CFG
    _CFG = cfg
    sys.path.insert(0, cfg['ruta'])
    import busqueda  # el de la ruta indicada
    if cfg.get('parametros_json') and hasattr(busqueda, 'cargar_parametros'):
        busqueda.cargar_parametros(cfg['parametros_json'])
    if cfg.get('pesos') and hasattr(busqueda, 'PESOS'):
        busqueda.PESOS.update(_pares(cfg['pesos']))
    if cfg.get('opciones') and hasattr(busqueda, 'OPCIONES'):
        busqueda.OPCIONES.update({k: bool(v) for k, v in _pares(cfg['opciones']).items()})
    sys.path.insert(1, JUEGO)


def resolver(problema):
    cfg = _CFG
    from ia import Partida
    spec = problema.get('variante') or {'tipo': 'extendido'}
    t0 = time.time()
    try:
        p = Partida(spec)
        st = p.inicial(problema.get('inicio'))
        for i in problema['hist']:
            st = p.legal(st)[i][1]
        movs = p.legal(st)
        b = p.nuevo_buscador(cfg['tiempo'] or None, cfg['prof'], cfg['temp'])
        (mv, _), prof = b.choose(st, movs, random.Random(0))
        idx = next(i for i, (m, _) in enumerate(movs) if m == mv)
        puntaje = getattr(b, 'puntaje', None) or 0
        if problema.get('tipo', 'mate') == 'mate':
            ok = puntaje >= MATE - (2 * problema['mate_en'] - 1) - 0.5
        else:
            ok = idx == problema['solucion_idx']
        return {'id': problema['id'], 'ok': ok, 'idx': idx, 'prof': prof, 'segundos': time.time() - t0}
    except Exception as e:
        return {'id': problema['id'], 'ok': False, 'error': str(e), 'segundos': time.time() - t0}


def categoria(p):
    if p.get('tipo', 'mate') == 'mate':
        return 'mate en %d' % p['mate_en']
    return 'táctica: %s' % p.get('tema', '?')


def main():
    ap = argparse.ArgumentParser(description='Examen táctico de la computadora',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('configs', nargs='*', default=['tiempo=1,prof=30,nombre=actual'],
                    help='configuraciones (como en comparar.py); por defecto, la actual con 1 s por problema')
    ap.add_argument('--problemas', default=PROBLEMAS, help='archivo de problemas (Juego/problemas.json)')
    ap.add_argument('--variante', default='todas', help='extendido, el nombre de una variante o todas')
    ap.add_argument('--tipo', choices=('todos', 'mate', 'tactico'), default='todos')
    ap.add_argument('--procesos', type=int, default=1)
    ap.add_argument('--salida', default='examen_tactico.jsonl', help='resultados (examen_tactico.jsonl)')
    a = ap.parse_args()
    with open(a.problemas, encoding='utf-8') as f:
        problemas = json.load(f)
    if a.variante != 'todas':
        problemas = [p for p in problemas if (p.get('variante') or {}).get('tipo', 'extendido') == a.variante
                     or p.get('variante_nombre') == a.variante]
    if a.tipo != 'todos':
        problemas = [p for p in problemas if p.get('tipo', 'mate') == a.tipo]
    if not problemas:
        raise SystemExit('No hay problemas con esos filtros (créalos con extraer_problemas.py).')
    configs = [leer_config(c) for c in a.configs]
    if any(os.path.abspath(c['ruta']) != AQUI for c in configs):
        raise SystemExit('El examen usa el motor de esta carpeta: «ruta=» no está disponible (usa comparar.py).')
    print('Examen: %d problemas, %d configuraci%s, %d procesos.' % (
        len(problemas), len(configs), 'ón' if len(configs) == 1 else 'ones', a.procesos), flush=True)
    por_id = {p['id']: p for p in problemas}
    resultados = {}
    with open(a.salida, 'a', encoding='utf-8') as fs:
        for cfg in configs:
            t0 = time.time()
            if a.procesos > 1:
                with Pool(a.procesos, initializer=preparar, initargs=(cfg,)) as pool:
                    rs = list(pool.imap_unordered(resolver, problemas))
            else:
                preparar(cfg)
                rs = [resolver(p) for p in problemas]
            resultados[cfg['nombre']] = {r['id']: r for r in rs}
            fs.write(json.dumps({'config': cfg['nombre'], 'fecha': time.strftime('%Y-%m-%d %H:%M'),
                                 'resultados': rs}, ensure_ascii=False) + '\n')
            ok = sum(r['ok'] for r in rs)
            errores = sum(1 for r in rs if 'error' in r)
            print('  %s: %d de %d resueltos (%.1f %%) en %.0f s%s' % (
                cfg['nombre'], ok, len(rs), 100 * ok / len(rs), time.time() - t0,
                (' · %d con error' % errores) if errores else ''), flush=True)
    # tabla por categoría
    nombres = list(resultados)
    cats = sorted({categoria(p) for p in problemas})
    print('\n%-32s %6s  %s' % ('categoría', 'total', '  '.join('%12s' % n[:12] for n in nombres)))
    for c in cats + ['TOTAL']:
        ids = [p['id'] for p in problemas if c == 'TOTAL' or categoria(p) == c]
        celdas = []
        for n in nombres:
            ok = sum(1 for i in ids if resultados[n][i]['ok'])
            celdas.append('%5d (%3.0f%%)' % (ok, 100 * ok / len(ids)))
        print('%-32s %6d  %s' % (c, len(ids), '  '.join(celdas)))
    if len(nombres) == 2:
        x, y = nombres
        solo_x = sum(1 for i in por_id if resultados[x][i]['ok'] and not resultados[y][i]['ok'])
        solo_y = sum(1 for i in por_id if resultados[y][i]['ok'] and not resultados[x][i]['ok'])
        print('\nSolo los resuelve %s: %d · solo %s: %d' % (x, solo_x, y, solo_y))
    print('Detalle en %s.' % a.salida)


if __name__ == '__main__':
    main()
