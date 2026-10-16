"""Simulador para las demás variantes: clásico, Capablanca, gótico y las del Laboratorio.

Usa el motor genérico (Juego/generico.py). La variante se indica con su nombre corto (clasico,
capablanca, gotico), con el nombre de una variante guardada en el Laboratorio o con la ruta de
su archivo JSON.

Modos:
  partidas VARIANTE        Autojuego: la computadora juega contra sí misma. Mide la ventaja de las
                           blancas, cómo terminan las partidas, su duración y las promociones.
  duelo VARIANTE X Y       Un bando tiene la pieza X y el otro la pieza Y en la misma casilla de la
                           primera fila (por defecto, la de la pieza más valiosa que no es el rey);
                           todo lo demás es igual. Cada semilla se juega con X en blancas y en negras.
                           X e Y son los tipos de pieza de la variante (Q, R, CA, ...); varias piezas
                           se suman con «+» (R+P): la primera va en la casilla y las demás en la
                           tercera fila. Sirve para medir los valores de las piezas nuevas.
  reporte ARCHIVO          Resume un archivo de resultados (se puede llamar mientras corre).

Ejemplos:
  pypy3 simular_variante.py partidas capablanca --partidas 40 --procesos 8 --profundidad 3
  pypy3 simular_variante.py partidas "Mi variante" --partidas 20 --bitacora mi_variante_bitacora.jsonl
  pypy3 simular_variante.py duelo capablanca CA CH --partidas 60 --procesos 8
  python3 simular_variante.py reporte variante.jsonl
"""
import argparse, copy, json, math, os, random, re, sys, time
from multiprocessing import Pool

AQUI = os.path.dirname(os.path.abspath(__file__))
JUEGO = os.path.join(os.path.dirname(AQUI), 'Juego')
sys.path.insert(0, AQUI)
sys.path.insert(0, JUEGO)
import generico as G
import bitacora

LABORATORIO = os.path.join(JUEGO, 'laboratorio')


# ---------------------------------------------------------------------- variantes
def cargar_variante(texto):
    """Configuración de una variante: preset, ruta de un JSON o nombre de una variante del Laboratorio."""
    if texto in G.PRESETS:
        return copy.deepcopy(G.PRESETS[texto])
    if os.path.isfile(texto):
        with open(texto, encoding='utf-8') as f:
            return json.load(f)
    clave = re.sub(r'[^a-z0-9]+', '_', texto.lower()).strip('_')
    if os.path.isdir(LABORATORIO):
        for nombre in sorted(os.listdir(LABORATORIO)):
            if nombre.endswith('.json'):
                with open(os.path.join(LABORATORIO, nombre), encoding='utf-8') as f:
                    cfg = json.load(f)
                if nombre[:-5] == clave or cfg.get('nombre', '').lower() == texto.lower():
                    return cfg
    raise SystemExit('No encuentro la variante «%s». Usa clasico, capablanca, gotico, el nombre de una variante '
                     'guardada en el Laboratorio o la ruta de su archivo JSON.' % texto)


def leer_grupo(cfg, texto):
    tipos = [t.strip() for t in texto.split('+') if t.strip()]
    for t in tipos:
        if t not in cfg['piezas']:
            raise SystemExit('La variante no tiene la pieza «%s». Tipos: %s' % (t, ', '.join(sorted(cfg['piezas']))))
        if cfg['piezas'][t].get('real'):
            raise SystemExit('El rey no puede ser una pieza del duelo.')
    return tipos


def columna_duelo(cfg):
    """Columna de la pieza más valiosa de la primera fila de las blancas que no es el rey ni un peón."""
    m = G.Motor(cfg)
    fila = [(c, t) for c, r, t, col in cfg['posicion'] if r == 0 and col == 0
            and t not in m.real and t not in m.peones]
    if not fila:
        return cfg['ancho'] // 2
    return max(fila, key=lambda x: (m.valor[x[1]], -abs(x[0] - (cfg['ancho'] - 1) / 2)))[0]


def config_duelo(cfg, x, y, x_blancas, col):
    """La variante con el grupo x en un bando y el grupo y en el otro."""
    cfg = copy.deepcopy(cfg)
    W, H = cfg['ancho'], cfg['alto']
    for color, grupo in ((0, x if x_blancas else y), (1, y if x_blancas else x)):
        atras, extra = (0, 2) if color == 0 else (H - 1, H - 3)
        pos = [p for p in cfg['posicion'] if not (p[0] == col and p[1] == atras)]
        ocupadas = {(p[0], p[1]) for p in pos}
        libres = sorted((c for c in range(W) if (c, extra) not in ocupadas), key=lambda c: abs(c - col))
        for i, t in enumerate(grupo):
            if i == 0:
                pos.append([col, atras, t, color])
            elif libres:
                pos.append([libres.pop(0), extra, t, color])
        cfg['posicion'] = pos
    return cfg


# ---------------------------------------------------------------------- una partida
def jugar(tarea):
    """tarea: dict con cfg, semilla, profundidad, tiempo, aleat, max_jug, bitacora y, en los duelos, x, y,
    x_blancas y columna."""
    a = tarea
    cfg = a['cfg']
    if 'x' in a:
        cfg = config_duelo(cfg, a['x'], a['y'], a['x_blancas'], a['columna'])
    m = G.Motor(cfg)
    notacion = None
    if a['bitacora']:
        from variantes import Generica
        notacion = Generica(cfg).notacion
    rng = random.Random(a['semilla'])
    st = m.inicial()
    S = [G.Buscador(m, a['tiempo'], a['profundidad']) for _ in (0, 1)]
    vistas, rep, registro, promos, prof = [m.zhash(st)], {}, [], [], []
    t0, ply = time.time(), 0
    while True:
        k = m.clave(st)
        rep[k] = rep.get(k, 0) + 1
        movs = m.legal(st)
        if registro and m.mate and m.en_jaque(st, st.turn):
            registro[-1]['j'] += '+' if movs else '#'
        fin = m.resultado(st, movs, rep[k])
        if fin is None and ply >= 2 * a['max_jug']:
            fin = ('Límite de jugadas de la simulación', None)
        if fin:
            motivo, ganador = fin
            r = dict(semilla=a['semilla'], resultado='tablas' if ganador is None else ('blancas', 'negras')[ganador],
                     motivo=motivo, jugadas=(ply + 1) // 2, profundidad=a['profundidad'],
                     material=[sum(m.valor[t] for t in st.cap[c]) for c in (0, 1)], promociones=promos,
                     profundidad_media=round(sum(prof) / max(1, len(prof)), 2), segundos=round(time.time() - t0, 1),
                     variante=cfg.get('nombre', '?'))
            if 'x' in a:
                color_x = 0 if a['x_blancas'] else 1
                r.update(x='+'.join(a['x']), y='+'.join(a['y']), x_blancas=a['x_blancas'],
                         puntos_x=0.5 if ganador is None else (1.0 if ganador == color_x else 0.0))
            if a['bitacora']:
                r['bitacora'] = registro
                r['config'] = cfg
            return r
        if ply < a['aleat']:
            mv, n = rng.choice(movs)
            d = None
        else:
            (mv, n), d = S[st.turn].choose(st, movs, rng, vistas=vistas)
            prof.append(d)
        if notacion:
            idx = next(i for i, (x, _) in enumerate(movs) if x is mv)
            registro.append(bitacora.jugada(idx, notacion(st, mv, n, movs), st.turn,
                                            None if d is None else S[st.turn].puntaje, d, azar=d is None))
        if mv[0] == 'm' and mv[3]:
            promos.append([('blancas', 'negras')[st.turn], cfg['piezas'][mv[3]]['nombre'], ply // 2 + 1])
        st = n
        ply += 1
        if st.reloj == 0:
            vistas = []
        vistas.append(m.zhash(st))


# ---------------------------------------------------------------------- ejecución
def siguiente_semilla(salida, filtro):
    if not os.path.exists(salida):
        return 0
    usadas = [r['semilla'] for r in leer_resultados(salida) if filtro(r)]
    return max(usadas) + 1 if usadas else 0


def leer_resultados(ruta):
    with open(ruta, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def ejecutar(tareas, a, cfg):
    t0 = time.time()
    fb = open(a.bitacora, 'a', encoding='utf-8') if a.bitacora else None
    with open(a.salida, 'a', encoding='utf-8') as f:
        it = Pool(a.procesos).imap_unordered(jugar, tareas) if a.procesos > 1 else map(jugar, tareas)
        for i, r in enumerate(it, 1):
            jugadas, config = r.pop('bitacora', None), r.pop('config', None)
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
            f.flush()
            if fb:
                cpu = {'profundidad': a.profundidad, 'tiempo': a.tiempo or None}
                reg = bitacora.nuevo('simulador', {'tipo': 'generica', 'config': config}, None,
                                     variante_nombre=config.get('nombre'), semilla=r['semilla'], blancas=cpu,
                                     negras=cpu, aperturas_aleatorias=a.aperturas_aleatorias,
                                     resultado=r['resultado'], motivo=r['motivo'])
                if 'x' in r:
                    reg['duelo'] = {'x': r['x'], 'y': r['y'], 'x_blancas': r['x_blancas']}
                reg['jugadas'] = jugadas
                bitacora.escribir(fb, reg)
                fb.flush()
            duelo = (' [%s vs %s, X con %s]' % (r['x'], r['y'], 'blancas' if r['x_blancas'] else 'negras')
                     if 'x' in r else '')
            print('[%d/%d] %s por %s en %d jugadas (%.0f s)%s' % (
                i, len(tareas), r['resultado'], r['motivo'].lower(), r['jugadas'], r['segundos'], duelo), flush=True)
    if fb:
        fb.close()
    print('Listo en %.0f s.\n' % (time.time() - t0), flush=True)
    reporte_archivo(a.salida, cfg.get('nombre'))


def base(a, cfg):
    return dict(cfg=cfg, profundidad=a.profundidad, tiempo=a.tiempo or None, aleat=a.aperturas_aleatorias,
                max_jug=a.max_jugadas, bitacora=a.bitacora is not None)


def partidas(a):
    cfg = cargar_variante(a.variante)
    nombre = cfg.get('nombre')
    inicio = a.semilla if a.semilla is not None else siguiente_semilla(
        a.salida, lambda r: 'x' not in r and r.get('variante') == nombre and r['profundidad'] == a.profundidad)
    print('%s: %d partidas a profundidad %d con %d procesos...' % (nombre, a.partidas, a.profundidad, a.procesos),
          flush=True)
    ejecutar([dict(base(a, cfg), semilla=inicio + i) for i in range(a.partidas)], a, cfg)


def duelo(a):
    cfg = cargar_variante(a.variante)
    x, y = leer_grupo(cfg, a.x), leer_grupo(cfg, a.y)
    col = (G.LETRAS.index(a.columna) if a.columna else columna_duelo(cfg))
    nombre = cfg.get('nombre')
    xs, ys = '+'.join(x), '+'.join(y)
    inicio = a.semilla if a.semilla is not None else siguiente_semilla(
        a.salida, lambda r: r.get('x') == xs and r.get('y') == ys and r.get('variante') == nombre
        and r['profundidad'] == a.profundidad)
    print('%s: duelo %s contra %s en la columna %s, %d partidas a profundidad %d con %d procesos...' % (
        nombre, xs, ys, G.LETRAS[col], a.partidas, a.profundidad, a.procesos), flush=True)
    tareas = [dict(base(a, cfg), semilla=inicio + i, x=x, y=y, x_blancas=xb, columna=col)
              for i in range(max(1, (a.partidas + 1) // 2)) for xb in (True, False)]
    ejecutar(tareas, a, cfg)


# ---------------------------------------------------------------------- reporte
def elo(p):
    p = min(max(p, 0.001), 0.999)
    return 400 * math.log10(p / (1 - p))


def reporte_archivo(ruta, solo_variante=None):
    rs = leer_resultados(ruta)
    if solo_variante:
        rs = [r for r in rs if r.get('variante') == solo_variante]
    grupos = {}
    for r in rs:
        k = (r.get('variante', '?'), r['profundidad'], r.get('x'), r.get('y'))
        grupos.setdefault(k, []).append(r)
    for (variante, prof, x, y), g in sorted(grupos.items(), key=lambda kv: tuple(str(v) for v in kv[0])):
        n = len(g)
        if x is None:
            b = sum(1 for r in g if r['resultado'] == 'blancas')
            ne = sum(1 for r in g if r['resultado'] == 'negras')
            t = n - b - ne
            print('== %s · autojuego a profundidad %d: %d partidas' % (variante, prof, n))
            print('   Blancas %d (%.0f%%) · Negras %d (%.0f%%) · Tablas %d (%.0f%%) · puntaje de las blancas %.1f%%'
                  % (b, 100 * b / n, ne, 100 * ne / n, t, 100 * t / n, 100 * (b + t / 2) / n))
        else:
            px = sum(r['puntos_x'] for r in g) / n
            gx = sum(1 for r in g if r['puntos_x'] == 1)
            gy = sum(1 for r in g if r['puntos_x'] == 0)
            var = sum((r['puntos_x'] - px) ** 2 for r in g) / max(1, n - 1)
            e = 1.96 * math.sqrt(var / n)
            print('== %s · duelo %s contra %s a profundidad %d: %d partidas' % (variante, x, y, prof, n))
            print('   Gana %s %d · tablas %d · gana %s %d · puntaje de %s %.1f%% (%+.0f Elo, intervalo %+.0f a %+.0f)'
                  % (x, gx, n - gx - gy, y, gy, x, 100 * px, elo(px), elo(px - e), elo(px + e)))
            veredicto = ('%s vale más que %s' % (x, y) if px - e > 0.5 else
                         '%s vale más que %s' % (y, x) if px + e < 0.5 else
                         'sin diferencia clara (faltan partidas o valen parecido)')
            print('   Veredicto: %s.' % veredicto)
        motivos = {}
        for r in g:
            motivos[r['motivo']] = motivos.get(r['motivo'], 0) + 1
        print('   Final: ' + ', '.join('%s %d%%' % (m, round(100 * c / n))
                                     for m, c in sorted(motivos.items(), key=lambda kv: -kv[1])))
        promos = sum(len(r['promociones']) for r in g)
        print('   Jugadas: media %.0f · promociones por partida %.2f · profundidad media %.1f · %.0f s por partida'
              % (sum(r['jugadas'] for r in g) / n, promos / n, sum(r['profundidad_media'] for r in g) / n,
                 sum(r['segundos'] for r in g) / n))
        print()


def main():
    ap = argparse.ArgumentParser(description='Simulador para las variantes genéricas y las del Laboratorio',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest='modo', required=True)

    def comunes(p):
        p.add_argument('--partidas', type=int, default=20, help='número de partidas (20)')
        p.add_argument('--profundidad', type=int, default=3, help='medias jugadas de búsqueda (3)')
        p.add_argument('--tiempo', type=float, default=0, help='segundos máximos por jugada (0 = sin límite)')
        p.add_argument('--procesos', type=int, default=1, help='partidas en paralelo (1)')
        p.add_argument('--aperturas-aleatorias', type=int, default=4, help='medias jugadas iniciales al azar (4)')
        p.add_argument('--max-jugadas', type=int, default=200, help='límite de jugadas por partida (200)')
        p.add_argument('--semilla', type=int, default=None, help='semilla inicial (por defecto, la siguiente libre)')
        p.add_argument('--salida', default='variantes.jsonl', help='archivo de resultados (variantes.jsonl)')
        p.add_argument('--bitacora', '--bitácora', dest='bitacora', default=None, metavar='ARCHIVO',
                       help='guarda todas las jugadas en ARCHIVO; el juego de escritorio las reproduce')
    p = sub.add_parser('partidas', help='autojuego de una variante')
    p.add_argument('variante')
    comunes(p)
    p = sub.add_parser('duelo', help='pieza X contra pieza Y')
    p.add_argument('variante')
    p.add_argument('x')
    p.add_argument('y')
    p.add_argument('--columna', default=None, help='columna de la casilla del duelo (letra; por defecto, la de '
                                                   'la pieza más valiosa)')
    comunes(p)
    p = sub.add_parser('reporte', help='resume un archivo de resultados')
    p.add_argument('archivo')
    a = ap.parse_args()
    if a.modo == 'partidas':
        partidas(a)
    elif a.modo == 'duelo':
        duelo(a)
    else:
        reporte_archivo(a.archivo)


if __name__ == '__main__':
    main()
