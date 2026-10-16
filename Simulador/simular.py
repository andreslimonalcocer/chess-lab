"""Simulador de autojuego del Ajedrez 11x11.

Ejemplos:
    python simular.py --profundidad 3 --partidas 50
    pypy3 simular.py --profundidad 5 --partidas 20 --procesos 8 --salida prof5.jsonl
    pypy3 simular.py --profundidad 4 --partidas 10 --bitacora prof4_bitacora.jsonl

Con --bitacora (o --bitácora) se guardan además todas las jugadas de cada partida, con la
evaluación de la computadora; el juego de escritorio las reproduce: ./jugar.sh --bitacora archivo
"""
import argparse, json, os, random, sys, time
from multiprocessing import Pool
from motor import *
from busqueda import Searcher, zhash, VERSION_IA
from notacion import notacion
import bitacora

NOMBRES = {'K': 'Rey', 'Q': 'Dama', 'R': 'Torre', 'B': 'Alfil', 'N': 'Caballo', 'CA': 'Arzobispo',
           'CH': 'Canciller', 'CE': 'Catapulta', 'G': 'Guardián', 'P': 'Peón'}


def nombre_pieza(p):
    if not p.pr:
        return NOMBRES[p.t]
    return NOMBRES[p.t] + (' promocionada' if p.t in ('Q', 'R', 'CE') else ' promocionado')


def jugar(args):
    seed, prof, tiempo, aleat, max_jug, con_bitacora = args
    rng = random.Random(seed)
    st = initial()
    hist, promos, depths = {}, [], []
    enroques = []  # [bando, lado ('a' o 'k'), jugada]
    vistas = [zhash(st)]  # posiciones desde la última jugada irreversible, para evitar repeticiones
    ply = 0
    S = [Searcher(tiempo, prof), Searcher(tiempo, prof)]
    registro = []  # jugadas para la bitácora
    t0 = time.time()
    while True:
        key = poskey(st)
        hist[key] = hist.get(key, 0) + 1
        moves = legal(st)
        if registro and in_check(st, st.turn):
            registro[-1]['j'] += '+' if moves else '#'
        res = None
        if not moves:
            if in_check(st, st.turn):
                k = st.kpos[st.turn]
                res = dict(resultado='blancas' if st.turn == 1 else 'negras', motivo='jaque mate',
                           piezas_mate=[nombre_pieza(st.b[i]) for i in attackers(st.b, k, 1 - st.turn)])
            else:
                res = dict(resultado='tablas', motivo='ahogado')
        elif hist[key] >= 3:
            res = dict(motivo='triple repetición')
        elif st.clock >= 100:
            res = dict(motivo='50 jugadas')
        elif insufficient(st):
            res = dict(motivo='material insuficiente')
        elif ply >= max_jug * 2:
            res = dict(motivo='límite de jugadas de la simulación')
        if res:
            if 'resultado' not in res:
                res['resultado'] = ('blancas' if st.pts[0] > st.pts[1] else
                                    'negras' if st.pts[1] > st.pts[0] else 'tablas')
                res['desempate_por_puntos'] = True
            res.update(semilla=seed, jugadas=(ply + 1) // 2, medias_jugadas=ply, puntos=st.pts,
                       promociones=promos, enroques=enroques, profundidad_media=round(sum(depths) / max(1, len(depths)), 2),
                       segundos=round(time.time() - t0, 1))
            if con_bitacora:
                res['bitacora'] = registro
            return res
        if ply < aleat:
            mv, n = rng.choice(moves)
            d = None
        else:
            (mv, n), d = S[st.turn].choose(st, moves, rng, vistas=vistas)
            depths.append(d)
        if con_bitacora:
            idx = next(i for i, (m, _) in enumerate(moves) if m is mv)
            registro.append(bitacora.jugada(idx, notacion(st, mv, n, moves), st.turn,
                                            None if d is None else S[st.turn].puntaje, d, azar=d is None))
        me = 'blancas' if st.turn == 0 else 'negras'
        if mv[0] in ('pr', 'gp'):
            promos.append([me, NOMBRES[st.b[mv[1]].t], (ply + 2) // 2])
        elif mv[0] == 'cs':
            enroques.append([me, 'a' if mv[3][0] % N == 0 else 'k', (ply + 2) // 2])
        elif mv[0] == 'cv':
            promos.append([me, 'Peón a Guardián', (ply + 2) // 2])
        elif mv[0] == 'm' and st.b[mv[1]].t in ('P', 'G') and not st.b[mv[1]].pr and n.b[mv[2]].pr:
            promos.append([me, NOMBRES[st.b[mv[1]].t] + ' (última fila)', (ply + 2) // 2])
        st = n
        ply += 1
        if st.clock == 0:
            vistas = []
        vistas.append(zhash(st))


def main():
    ap = argparse.ArgumentParser(description='Autojuego del Ajedrez 11x11')
    ap.add_argument('--profundidad', type=int, default=3,
                    help='medias jugadas que la computadora analiza hacia adelante (por defecto 3)')
    ap.add_argument('--partidas', type=int, default=20, help='número de partidas (por defecto 20)')
    ap.add_argument('--tiempo', type=float, default=0,
                    help='segundos máximos por jugada; 0 = sin límite, siempre profundidad completa')
    ap.add_argument('--procesos', type=int, default=1, help='partidas en paralelo (núcleos del procesador)')
    ap.add_argument('--aperturas-aleatorias', type=int, default=4,
                    help='medias jugadas iniciales al azar para variar las partidas (por defecto 4)')
    ap.add_argument('--max-jugadas', type=int, default=200, help='límite de jugadas por partida (por defecto 200)')
    ap.add_argument('--semilla', type=int, default=None,
                    help='semilla inicial (por defecto, la siguiente a la mayor que ya haya en el archivo de '
                         'salida, para no repetir partidas)')
    ap.add_argument('--salida', default='resultados.jsonl', help='archivo de resultados')
    ap.add_argument('--bitacora', '--bitácora', dest='bitacora', default=None, metavar='ARCHIVO',
                    help='guarda todas las jugadas de cada partida en ARCHIVO (una partida por línea), '
                         'con la evaluación de la computadora; el juego de escritorio las reproduce')
    a = ap.parse_args()
    if a.semilla is None:
        a.semilla = 0
        if os.path.exists(a.salida):
            with open(a.salida, encoding='utf-8') as f:
                usadas = [json.loads(l)['semilla'] for l in f if l.strip()]
            if usadas:
                a.semilla = max(usadas) + 1
    tareas = [(a.semilla + i, a.profundidad, a.tiempo or None, a.aperturas_aleatorias, a.max_jugadas,
               a.bitacora is not None) for i in range(a.partidas)]
    print('Simulando %d partidas a profundidad %d...' % (a.partidas, a.profundidad), flush=True)
    t0 = time.time()
    fb = open(a.bitacora, 'a', encoding='utf-8') if a.bitacora else None
    with open(a.salida, 'a', encoding='utf-8') as f:
        if a.procesos > 1:
            it = Pool(a.procesos).imap_unordered(jugar, tareas)
        else:
            it = map(jugar, tareas)
        for i, r in enumerate(it, 1):
            r['profundidad'] = a.profundidad
            jugadas = r.pop('bitacora', None)
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
            if fb:
                cpu = {'profundidad': a.profundidad, 'tiempo': a.tiempo or None, 'valores_ia': VERSION_IA}
                registro = bitacora.nuevo('simulador', semilla=r['semilla'], blancas=cpu, negras=cpu,
                                          aperturas_aleatorias=a.aperturas_aleatorias,
                                          **{k: r[k] for k in ('resultado', 'motivo', 'puntos', 'piezas_mate')
                                             if k in r})
                registro['jugadas'] = jugadas
                bitacora.escribir(fb, registro)
            f.flush()
            print('[%d/%d] %s por %s en %d jugadas (%.0f s)' % (i, a.partidas, r['resultado'], r['motivo'],
                                                               r['jugadas'], r['segundos']), flush=True)
    if fb:
        fb.close()
        print('Bitácora en %s (reprodúcela con: Juego/jugar.sh --bitacora %s).' % (
            a.bitacora, os.path.abspath(a.bitacora)))
    print('Listo en %.0f s. Resultados en %s. Ejecuta: python reporte.py %s' % (time.time() - t0, a.salida, a.salida))


if __name__ == '__main__':
    main()
