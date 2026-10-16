"""Tablas exactas de finales para el ajedrez clásico, Capablanca, gótico y las variantes del Laboratorio:
Rey y una o dos piezas contra Rey (Juego/tablas_genericas.py). La computadora de esas variantes las usa
sola en cuanto existen, y la sección «Finales» del juego permite practicarlas.

Uso:
  pypy3 finales_variante.py clasico                    # todas las piezas solas (segundos)
  pypy3 finales_variante.py clasico B+B B+N            # también pares (1-5 min en 8×8)
  pypy3 finales_variante.py capablanca --pares         # piezas solas y todos los pares (10×8: más lento)
  pypy3 finales_variante.py "Mi variante"              # una variante guardada en el Laboratorio
Las tablas quedan en tablas/variantes/ (con un .json de resumen cada una).
"""
import argparse, itertools, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'Juego'))
import tablas_genericas as TG
from simular_variante import cargar_variante


def main():
    ap = argparse.ArgumentParser(description='Tablas de finales de las variantes',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('variante', help='clasico, capablanca, gotico, una variante del Laboratorio o un JSON')
    ap.add_argument('pares', nargs='*', help='pares de piezas, por ejemplo B+B o B+N (tipos de la variante)')
    ap.add_argument('--pares', dest='todos_pares', action='store_true', help='construye todos los pares')
    ap.add_argument('--rehacer', action='store_true', help='reconstruye aunque ya existan')
    a = ap.parse_args()
    cfg = cargar_variante(a.variante)
    if not TG.aplicable(cfg):
        raise SystemExit('Esta variante no tiene objetivo «jaque mate» con un único rey: no hay tablas.')
    solas = [[t] for t in TG.piezas_posibles(cfg)]
    pares = [sorted(p.split('+')) for p in a.pares]
    if a.todos_pares:
        pares = [list(p) for p in itertools.combinations_with_replacement(sorted(TG.piezas_posibles(cfg)), 2)]
    for tipos in solas + pares:
        for t in tipos:
            if t not in cfg['piezas']:
                raise SystemExit('La variante no tiene la pieza «%s» (tipos: %s).' % (t, ', '.join(cfg['piezas'])))
        if TG.existe(cfg, tipos) and not a.rehacer:
            r = TG.resumen(cfg, tipos) or {}
            print('%s: ya existe (%.1f %% ganadas, mate más largo %s).' % (
                '+'.join(tipos), 100 * r.get('ganadas', 0), r.get('maximo')))
            continue
        TG.construir(cfg, tipos, avisar=lambda *x: print(*x, flush=True))


if __name__ == '__main__':
    main()
