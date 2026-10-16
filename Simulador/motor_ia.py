"""Proceso de una computadora con un motor y una configuración dados (lo usan comparar.py y
calibrar_elo.py). Permite enfrentar versiones distintas del motor en la misma partida.

Uso: pypy3 motor_ia.py CARPETA_DEL_MOTOR   (la carpeta con motor.py y busqueda.py)
Lee por la entrada estándar, una por línea:
    {"hist": [12, 40, ...], "prof": 3, "tiempo": 0, "temperatura": 0, "mejoras": true, "semilla": 5,
     "pesos": {"pasados": 1, "escudo": 1, "movilidad": 1}, "opciones": {"see": true},
     "parametros": {...}}   (parámetros de la evaluación, como los de afinar_texel.py)
y responde {"idx": 17, "prof": 3}: el índice de la jugada elegida dentro de legal().
"""
import inspect, json, os, random, sys

sys.path.insert(0, os.path.abspath(sys.argv[1]))
from motor import initial, legal
import busqueda
from busqueda import Searcher, zhash

PARAMETROS = inspect.signature(Searcher.__init__).parameters  # las versiones viejas no tienen todos


def main():
    hist, st = [], initial()
    vistas = [zhash(st)]
    buscador, clave = None, None
    parametros_cargados = False
    for linea in sys.stdin:
        req = json.loads(linea)
        nuevo = req['hist']
        if nuevo[:len(hist)] != hist:
            hist, st = [], initial()
            vistas = [zhash(st)]
        for i in nuevo[len(hist):]:
            st = legal(st)[i][1]
            if st.clock == 0:
                vistas = []
            vistas.append(zhash(st))
        hist = list(nuevo)
        movs = legal(st)
        if req.get('parametros') and hasattr(busqueda, 'cargar_parametros') and not parametros_cargados:
            busqueda.cargar_parametros(req['parametros'])  # antes que «pesos», que puede cambiar alguno
            parametros_cargados = True
        if req.get('pesos') and hasattr(busqueda, 'PESOS'):  # términos de evaluación de esta configuración
            busqueda.PESOS.update(req['pesos'])
        if req.get('opciones') and hasattr(busqueda, 'OPCIONES'):  # mejoras de la búsqueda
            busqueda.OPCIONES.update(req['opciones'])
        k = (req['prof'], req.get('tiempo'), req.get('temperatura', 0), req.get('mejoras'))
        if k != clave:
            extra = {}
            if 'mejoras' in PARAMETROS and req.get('mejoras') is not None:
                extra['mejoras'] = req['mejoras']
            if 'temperatura' in PARAMETROS:
                extra['temperatura'] = req.get('temperatura', 0)
            buscador, clave = Searcher(req.get('tiempo') or None, req['prof'], **extra), k
        (mv, _), prof = buscador.choose(st, movs, random.Random(req.get('semilla')), vistas=vistas)
        idx = next(i for i, (m, _) in enumerate(movs) if m == mv)
        try:
            print(json.dumps({'idx': idx, 'prof': prof}), flush=True)
        except BrokenPipeError:  # comparar.py ya terminó (por ejemplo, el SPRT decidió): salir sin ruido
            os._exit(0)


if __name__ == '__main__':
    main()
