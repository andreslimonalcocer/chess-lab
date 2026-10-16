"""Partidas entre dos configuraciones de la computadora: mide la diferencia de fuerza en Elo.

Cada configuración se escribe como «clave=valor,...»:
  ruta      carpeta del motor (motor.py y busqueda.py); por defecto, esta carpeta
  prof      profundidad máxima (medias jugadas)
  tiempo    segundos máximos por jugada (0 = sin límite)
  temp      temperatura: imprecisión para los niveles bajos (0 = siempre la mejor jugada)
  mejoras   1 = búsqueda mejorada, 0 = búsqueda clásica (si el motor la tiene)
  pesos     términos de evaluación, separados por «/»: pasados:1/escudo:1/movilidad:1 (por defecto los de
            busqueda.PESOS); si una clave se repite, vale la última
  opciones  mejoras de la búsqueda (busqueda.OPCIONES), separadas por «/»: aspiracion:1/see:1
  parametros archivo JSON con parámetros de la evaluación (busqueda.cargar_parametros), como el que
            escribe afinar_texel.py
  nombre    nombre para el reporte

Cada apertura se juega dos veces, con cada configuración en blancas y en negras. Las partidas que
no terminan en mate cuentan como tablas.

Con --sprt ELO0 ELO1 se usa la prueba secuencial de razón de verosimilitudes (como Fishtest): se juega
hasta que los resultados muestran, con 95 % de confianza, que la diferencia es al menos ELO1 (H1,
aceptar el cambio) o como mucho ELO0 (H0, rechazarlo); --partidas es entonces el máximo. Lo usual es
--sprt 0 10: «¿mejora al menos unos 10 Elo o no mejora?».

Ejemplos:
  # ¿cuánto aporta la búsqueda mejorada?
  pypy3 comparar.py "prof=3,mejoras=0,nombre=clásica" "prof=3,mejoras=1,nombre=mejorada" --partidas 100 --procesos 22
  # ¿ayudan los términos de evaluación nuevos?
  pypy3 comparar.py "prof=3,nombre=sin" "prof=3,pesos=pasados:1/escudo:1/movilidad:1,nombre=con" --partidas 100 --procesos 22
  # contra una copia guardada del motor
  pypy3 comparar.py "ruta=~/motor_viejo,prof=4" "prof=4" --partidas 60 --procesos 22
  # una mejora de la búsqueda con la misma cantidad de tiempo, hasta decidir
  pypy3 comparar.py "tiempo=1,prof=30,nombre=base" "tiempo=1,prof=30,opciones=aspiracion:1,nombre=aspiración" --sprt 0 10 --partidas 2000 --procesos 22
"""
import argparse, json, math, os, random, subprocess, sys, time
from multiprocessing import Pool

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from motor import initial, legal, in_check, insufficient, poskey

CLAVES = {'ruta': str, 'prof': int, 'tiempo': float, 'temp': float, 'mejoras': int, 'nombre': str, 'pesos': str,
          'opciones': str, 'parametros': str}


def leer_config(texto):
    cfg = {'ruta': AQUI, 'prof': 3, 'tiempo': 0.0, 'temp': 0.0, 'mejoras': None}
    for parte in filter(None, texto.split(',')):
        k, _, v = parte.partition('=')
        k = k.strip()
        if k not in CLAVES:
            raise SystemExit('Clave desconocida en «%s»: %s (usa %s)' % (texto, k, ', '.join(CLAVES)))
        cfg[k] = CLAVES[k](os.path.expanduser(v.strip()) if k in ('ruta', 'parametros') else v.strip())
    cfg.setdefault('nombre', texto)
    if cfg.get('parametros'):
        with open(cfg['parametros'], encoding='utf-8') as f:
            cfg['parametros_json'] = json.load(f)
    return cfg


def _pares(texto):
    return {k: float(v) for k, v in (p.split(':') for p in texto.split('/') if p)}


class Computadora:
    """Un proceso motor_ia.py con una configuración."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.proc = subprocess.Popen([sys.executable, os.path.join(AQUI, 'motor_ia.py'), cfg['ruta']],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def jugada(self, hist, semilla):
        c = self.cfg
        req = {'hist': hist, 'prof': c['prof'], 'tiempo': c['tiempo'] or None, 'temperatura': c['temp'],
               'mejoras': None if c['mejoras'] is None else bool(c['mejoras']), 'semilla': semilla}
        if c.get('pesos'):
            req['pesos'] = _pares(c['pesos'])
        if c.get('opciones'):
            req['opciones'] = {k: bool(v) for k, v in _pares(c['opciones']).items()}
        if c.get('parametros_json'):
            req['parametros'] = c['parametros_json']
        self.proc.stdin.write(json.dumps(req) + '\n')
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())['idx']

    def cerrar(self):
        self.proc.kill()
        self.proc.wait()


def jugar(tarea):
    """Una partida: cfg_x contra cfg_y, x con blancas o con negras. Devuelve los puntos de x."""
    semilla, cfg_x, cfg_y, x_blancas, aleat, max_jug = tarea
    rng = random.Random(semilla)
    compu = [Computadora(cfg_x if x_blancas else cfg_y), Computadora(cfg_y if x_blancas else cfg_x)]
    st, hist, vistas, ply = initial(), [], {}, 0
    t0 = time.time()
    try:
        while True:
            k = poskey(st)
            vistas[k] = vistas.get(k, 0) + 1
            movs = legal(st)
            motivo, ganador = None, None
            if not movs:
                motivo = 'jaque mate' if in_check(st, st.turn) else 'ahogado'
                ganador = 1 - st.turn if motivo == 'jaque mate' else None
            elif vistas[k] >= 3:
                motivo = 'triple repetición'
            elif st.clock >= 100:
                motivo = '50 jugadas'
            elif insufficient(st):
                motivo = 'material insuficiente'
            elif ply >= 2 * max_jug:
                motivo = 'límite de jugadas'
            if motivo:
                color_x = 0 if x_blancas else 1
                puntos = 0.5 if ganador is None else (1.0 if ganador == color_x else 0.0)
                return dict(x=cfg_x['nombre'], y=cfg_y['nombre'], semilla=semilla, x_blancas=x_blancas,
                            puntos_x=puntos, motivo=motivo, jugadas=(ply + 1) // 2,
                            segundos=round(time.time() - t0, 1))
            if ply < aleat:
                idx = rng.randrange(len(movs))
            else:
                idx = compu[st.turn].jugada(hist, semilla * 1000 + ply)
            hist.append(idx)
            st = movs[idx][1]
            ply += 1
    finally:
        for c in compu:
            c.cerrar()


def elo(puntaje):
    p = min(max(puntaje, 0.001), 0.999)
    return 400 * math.log10(p / (1 - p))


def resumen(resultados, nombre_x, nombre_y):
    g = [r for r in resultados if r['x'] == nombre_x and r['y'] == nombre_y]
    if not g:
        return None
    n = len(g)
    s = sum(r['puntos_x'] for r in g) / n
    w = sum(1 for r in g if r['puntos_x'] == 1)
    l = sum(1 for r in g if r['puntos_x'] == 0)
    var = sum((r['puntos_x'] - s) ** 2 for r in g) / max(1, n - 1)
    e = 1.96 * math.sqrt(var / n)
    return dict(n=n, gana=w, tablas=n - w - l, pierde=l, puntaje=s, elo=elo(s),
                elo_bajo=elo(s - e), elo_alto=elo(s + e))


def tareas(cfg_x, cfg_y, partidas, inicio, aleat, max_jug):
    return [(inicio + i, cfg_x, cfg_y, xb, aleat, max_jug)
            for i in range((partidas + 1) // 2) for xb in (True, False)]


def puntaje_elo(e):
    return 1 / (1 + 10 ** (-e / 400))


def llr(puntos, elo0, elo1):
    """Razón de verosimilitudes logarítmica (aproximación normal, como en Fishtest) de H1 (diferencia elo1)
    contra H0 (elo0), con los puntos de cada partida (1, 0.5 o 0)."""
    n = len(puntos)
    if n < 2:
        return 0.0
    m = sum(puntos) / n
    var = sum((x - m) ** 2 for x in puntos) / n
    if var <= 0:
        return 0.0
    s0, s1 = puntaje_elo(elo0), puntaje_elo(elo1)
    return n * (s1 - s0) * (2 * m - s0 - s1) / (2 * var)


def limites_sprt(alfa=0.05, beta=0.05):
    return math.log(beta / (1 - alfa)), math.log((1 - beta) / alfa)


def correr(lista, procesos, salida, sprt=None, previos=()):
    """Juega las partidas de lista. sprt = (elo0, elo1): se detiene en cuanto la prueba decide; previos son
    los puntos de partidas anteriores del mismo enfrentamiento (del archivo de salida)."""
    resultados = []
    puntos = list(previos)
    bajo, alto = limites_sprt()
    decision = None
    pool = Pool(procesos) if procesos > 1 else None
    try:
        with open(salida, 'a', encoding='utf-8') as f:
            it = pool.imap_unordered(jugar, lista) if pool else map(jugar, lista)
            for i, r in enumerate(it, 1):
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
                f.flush()
                resultados.append(r)
                extra = ''
                if sprt:
                    puntos.append(r['puntos_x'])
                    v = llr(puntos, *sprt)
                    extra = ' · LLR %.2f [%.2f, %.2f]' % (v, bajo, alto)
                    if len(puntos) >= 20 and (v >= alto or v <= bajo):
                        decision = 'H1' if v >= alto else 'H0'
                print('[%d/%d] %s contra %s: %s (%s, %d jugadas, %.0f s)%s' % (
                    i, len(lista), r['x'], r['y'], {1.0: 'gana', 0.0: 'pierde', 0.5: 'tablas'}[r['puntos_x']],
                    r['motivo'], r['jugadas'], r['segundos'], extra), flush=True)
                if decision:
                    break
    finally:
        if pool:
            pool.terminate()
    if sprt:
        if decision == 'H1':
            print('\nSPRT: H1 aceptada: la diferencia es de al menos %+g Elo (con 95 %% de confianza).' % sprt[1])
        elif decision == 'H0':
            print('\nSPRT: H0 aceptada: la diferencia es como mucho %+g Elo; el cambio no mejora.' % sprt[0])
        else:
            print('\nSPRT: sin decidir tras %d partidas (LLR %.2f); se puede continuar con otra corrida.' % (
                len(puntos), llr(puntos, *sprt)))
    return resultados


def main():
    ap = argparse.ArgumentParser(description='Partidas entre dos configuraciones de la computadora',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('a', help='configuración A (la de referencia)')
    ap.add_argument('b', help='configuración B (la que se mide contra A)')
    ap.add_argument('--partidas', type=int, default=60, help='partidas (60; se juegan por pares)')
    ap.add_argument('--procesos', type=int, default=1, help='partidas en paralelo')
    ap.add_argument('--aperturas-aleatorias', type=int, default=4, help='medias jugadas al azar al inicio (4)')
    ap.add_argument('--max-jugadas', type=int, default=200, help='límite de jugadas por partida (200)')
    ap.add_argument('--semilla', type=int, default=0, help='semilla inicial (0)')
    ap.add_argument('--salida', default='comparar.jsonl', help='archivo de resultados (comparar.jsonl)')
    ap.add_argument('--sprt', nargs=2, type=float, metavar=('ELO0', 'ELO1'),
                    help='prueba secuencial: se detiene al decidir entre ELO0 (no mejora) y ELO1 (mejora)')
    a = ap.parse_args()
    ca, cb = leer_config(a.a), leer_config(a.b)
    if ca['nombre'] == cb['nombre']:
        ca['nombre'], cb['nombre'] = 'A: ' + ca['nombre'], 'B: ' + cb['nombre']
    print('%s contra %s: %d partidas con %d procesos...' % (cb['nombre'], ca['nombre'], a.partidas, a.procesos))
    t0 = time.time()
    previos = []
    if a.sprt and os.path.exists(a.salida):
        previos = [r['puntos_x'] for r in (json.loads(l) for l in open(a.salida, encoding='utf-8') if l.strip())
                   if r['x'] == cb['nombre'] and r['y'] == ca['nombre']]
        if previos and a.semilla == 0:
            a.semilla = max(r['semilla'] for r in (json.loads(l) for l in open(a.salida, encoding='utf-8'))
                            if r['x'] == cb['nombre']) + 1
    correr(tareas(cb, ca, a.partidas, a.semilla, a.aperturas_aleatorias, a.max_jugadas), a.procesos, a.salida,
           tuple(a.sprt) if a.sprt else None, previos)
    r = resumen([json.loads(l) for l in open(a.salida, encoding='utf-8')], cb['nombre'], ca['nombre'])
    print('\nListo en %.0f s.' % (time.time() - t0))
    print('%s contra %s: %d partidas, %d ganadas, %d tablas, %d perdidas, puntaje %.1f%%' % (
        cb['nombre'], ca['nombre'], r['n'], r['gana'], r['tablas'], r['pierde'], 100 * r['puntaje']))
    print('Diferencia: %+.0f Elo (intervalo del 95%%: %+.0f a %+.0f)' % (r['elo'], r['elo_bajo'], r['elo_alto']))


if __name__ == '__main__':
    main()
