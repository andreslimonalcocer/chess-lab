"""Resumen estadístico de las partidas simuladas.

Uso: python reporte.py resultados.jsonl
"""
import json, sys, statistics as st
from collections import Counter


def pct(a, b):
    return '%.1f%%' % (100.0 * a / b) if b else '-'


def main(path):
    R = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]
    n = len(R)
    if not n:
        print('Sin partidas.'); return
    print('Partidas: %d   Profundidad: %s   Profundidad media alcanzada: %.2f' % (
        n, sorted(set(r.get('profundidad') for r in R)), st.mean(r['profundidad_media'] for r in R)))

    print('\nRESULTADOS')
    for k, v in Counter(r['resultado'] for r in R).most_common():
        print('  %-8s %5d  %s' % (k, v, pct(v, n)))

    print('\nMOTIVO DE FINALIZACIÓN')
    for k, v in Counter(r['motivo'] for r in R).most_common():
        print('  %-36s %5d  %s' % (k, v, pct(v, n)))

    mates = [r for r in R if r['motivo'] == 'jaque mate']
    if mates:
        mv = [r['jugadas'] for r in mates]
        print('\nJUGADAS HASTA EL MATE (%d mates)' % len(mates))
        print('  media %.1f   mediana %s   mínimo %d   máximo %d' % (st.mean(mv), st.median(mv), min(mv), max(mv)))
        if len(mv) >= 4:
            q = st.quantiles(mv, n=4)
            print('  la mitad de los mates ocurre entre las jugadas %d y %d' % (q[0], q[2]))
        for a, b in ((1, 20), (21, 30), (31, 40), (41, 60), (61, 80), (81, 120), (121, 9999)):
            c = sum(a <= x <= b for x in mv)
            print('  %-10s %4d  %s' % ('%d-%s' % (a, b if b < 9999 else '+'), c, pct(c, len(mates))))

        print('\nPIEZA QUE DA EL MATE (% de los mates)')
        cnt = Counter()
        for r in mates:
            for p in set(r['piezas_mate']):
                cnt[p] += 1
        for k, v in cnt.most_common():
            print('  %-28s %4d  %s' % (k, v, pct(v, len(mates))))
        base = Counter()
        for r in mates:
            for p in set(x.replace(' promocionada', '').replace(' promocionado', '') for x in r['piezas_mate']):
                base[p] += 1
        print('  -- agrupado por tipo de pieza --')
        for k, v in base.most_common():
            print('  %-28s %4d  %s' % (k, v, pct(v, len(mates))))
        prom = sum(1 for r in mates if any('promocionad' in p for p in r['piezas_mate']))
        print('  mates con pieza promocionada: %s' % pct(prom, len(mates)))
        adel = sum(1 for r in mates if r['puntos'][0 if r['resultado'] == 'blancas' else 1] >
                   r['puntos'][1 if r['resultado'] == 'blancas' else 0])
        print('  el ganador iba arriba en puntos en %s de los mates' % pct(adel, len(mates)))

    print('\nPROMOCIONES (% de partidas en que ocurre al menos una vez)')
    pc = Counter()
    for r in R:
        for p in set(x[1] for x in r['promociones']):
            pc[p] += 1
    for k, v in pc.most_common():
        print('  %-26s %4d  %s' % (k, v, pct(v, n)))
    prim = [r['promociones'][0][2] for r in R if r['promociones']]
    if prim:
        print('  primera promoción: jugada %s (mediana)' % st.median(prim))

    if any('enroques' in r for r in R):
        con = [r for r in R if 'enroques' in r]
        todos = [e for r in con for e in r['enroques']]
        print('\nENROQUES (%d partidas con este dato)' % len(con))
        print('  partidas con algún enroque: %s · enroques por partida: %.2f' % (
            pct(sum(1 for r in con if r['enroques']), len(con)), len(todos) / len(con)))
        for bando in ('blancas', 'negras'):
            e = [x for x in todos if x[0] == bando]
            if e:
                print('  %-8s %3d (hacia la columna a: %d, hacia la k: %d) · jugada mediana %s' % (
                    bando, len(e), sum(1 for x in e if x[1] == 'a'), sum(1 for x in e if x[1] == 'k'),
                    st.median(x[2] for x in e)))

    jl = [r['jugadas'] for r in R]
    print('\nDURACIÓN: media %.1f jugadas, mediana %s' % (st.mean(jl), st.median(jl)))
    print('TIEMPO: %.0f s por partida en promedio' % st.mean(r['segundos'] for r in R))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'resultados.jsonl')
