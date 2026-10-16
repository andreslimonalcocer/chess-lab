"""Afinado de la evaluación con el método de Texel (como los motores de ajedrez antes de las redes).

Toma posiciones tranquilas de partidas con resultado conocido (bitácoras del simulador, del espectador o
de tus partidas) y ajusta los parámetros de la evaluación para que predigan mejor el resultado:
    probabilidad de ganar de las blancas = 1 / (1 + 10^(-K · evaluación / 4))
Se minimiza el error cuadrático medio entre esa probabilidad y el resultado real (1, ½ o 0).

Parámetros que ajusta (los de busqueda.parametros()):
  VALOR_MEDIO, VALOR_FINAL  valor de cada pieza (base y promocionada) en el medio juego y en el final
  CENTRO, CENTRO_PROM       bono por casilla de centralización de cada tipo de pieza (base / promocionada)
  AVANCE                    bono por fila avanzada de cada tipo de pieza sin promocionar
  PESOS                     peso de los términos de evaluación encendidos (o de todos con --todos-los-pesos)

La evaluación es lineal en casi todos ellos, así que primero se calculan las «características» de cada
posición y después se optimiza muy rápido (descenso de gradiente con Adam), con una regularización que
mantiene los parámetros cerca de los actuales cuando los datos no dicen lo contrario. Un 10 % de las
partidas se reserva para comprobar que el ajuste generaliza (y detenerlo antes de que memorice).

Resultado: texel_parametros.json (todos los parámetros, listo para comparar.py) y un informe con los
cambios. Para validarlo en partidas:
    pypy3 comparar.py "tiempo=1,prof=30,nombre=v5" "tiempo=1,prof=30,parametros=texel_parametros.json,nombre=texel" --sprt 0 10 --partidas 2000 --procesos 22

Datos: cuantas más partidas, mejor (cientos como mínimo; miles es lo ideal). Por ejemplo:
    pypy3 simular.py --profundidad 3 --partidas 1000 --procesos 22 --salida texel_p3.jsonl --bitacora texel_p3_bitacora.jsonl
    pypy3 afinar_texel.py texel_p3_bitacora.jsonl
"""
import argparse, json, math, os, random, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(1, os.path.join(os.path.dirname(AQUI), 'Juego'))
import busqueda as B
import bitacora
from motor import initial, legal, in_check, N

GRUPOS = {'VM': 1.0, 'VF': 1.0, 'C': 0.02, 'CP': 0.02, 'A': 0.03, 'W': 0.5}  # escala de cada grupo


# ---------------------------------------------------------------------- datos
def posiciones(rutas, saltar, cada, rng):
    """[(estado, resultado de las blancas, id de partida)] de posiciones tranquilas."""
    from motor import initial as ini
    from ia import construir_posicion  # noqa: posiciones de entrenamiento con «inicio»
    out, partidas = [], 0
    for ruta in rutas:
        for r in bitacora.leer(ruta):
            if (r.get('variante') or {}).get('tipo', 'extendido') != 'extendido' or not r.get('resultado'):
                continue
            res = {'blancas': 1.0, 'negras': 0.0, 'tablas': 0.5}.get(r['resultado'])
            if res is None:
                continue
            partidas += 1
            st = ini() if not r.get('inicio') else construir_posicion(r['inicio']['piezas'], r['inicio']['turno'])
            for k, j in enumerate(r['jugadas']):
                movs = legal(st)
                if j['i'] >= len(movs):
                    break
                mv, n = movs[j['i']]
                if k >= saltar and (k % cada == 0) and not in_check(st, st.turn) and not B.is_capture(st, mv) \
                        and not j.get('azar'):
                    out.append((st, res, partidas))
                st = n
    rng.shuffle(out)
    return out, partidas


def caracteristicas(st, pesos_libres):
    """{parámetro: coeficiente} de la evaluación a favor de las blancas (lineal en los parámetros) y el resto
    constante, de modo que evaluación = Σ θ·φ + resto con los parámetros actuales."""
    phi = {}
    material_fase = 0.0
    for p in st.b:
        if p is not None and p.t != 'K' and B.EN_FASE[p.t]:
            material_fase += B.VALOR_MEDIO[p.t][1 if p.pr else 0]
    f = min(1.0, material_fase / B.FASE_INICIAL)
    for sq in range(N * N):
        p = st.b[sq]
        if p is None or p.t == 'K':
            continue
        s = 1.0 if p.c == 0 else -1.0
        i = 1 if p.pr else 0
        for clave, v in ((('VM', p.t, i), s * f), (('VF', p.t, i), s * (1 - f))):
            phi[clave] = phi.get(clave, 0.0) + v
        if p.pr:
            k = ('CP', p.t)
            phi[k] = phi.get(k, 0.0) + s * B.DIST_CENTRO[sq]
        else:
            for k, v in ((('C', p.t), s * B.DIST_CENTRO[sq]), (('A', p.t), s * B.FILA_AVANCE[p.c][sq])):
                if v:
                    phi[k] = phi.get(k, 0.0) + v
    guardados = dict(B.PESOS)
    try:
        for nombre in pesos_libres:
            for k in B.PESOS:
                B.PESOS[k] = 1.0 if k == nombre else 0.0
            v = B.terminos_extra(st, f, 0)
            if v:
                phi[('W', nombre)] = v
    finally:
        B.PESOS.update(guardados)
    e = B.evaluate(st)
    e = e if st.turn == 0 else -e
    resto = e - sum(theta_actual(k) * v for k, v in phi.items())
    return phi, resto


def theta_actual(k):
    g = k[0]
    if g == 'VM':
        return B.VALOR_MEDIO[k[1]][k[2]]
    if g == 'VF':
        return B.VALOR_FINAL[k[1]][k[2]]
    if g == 'C':
        return B.CENTRO[k[1]]
    if g == 'CP':
        return B.CENTRO_PROM[k[1]]
    if g == 'A':
        return B.AVANCE[k[1]]
    return B.PESOS[k[1]]


# ---------------------------------------------------------------------- optimización
def prob(e, K):
    x = max(-60.0, min(60.0, -K * e / 4))
    return 1.0 / (1.0 + 10 ** x)


def error(datos, theta, K):
    s = 0.0
    for phi, resto, r in datos:
        e = resto + sum(theta[i] * v for i, v in phi)
        s += (r - prob(e, K)) ** 2
    return s / max(1, len(datos))


def ajustar_K(datos, theta):
    a, b = 0.05, 5.0
    for _ in range(40):  # sección áurea
        m1, m2 = a + (b - a) * 0.382, a + (b - a) * 0.618
        if error(datos, theta, m1) < error(datos, theta, m2):
            b = m2
        else:
            a = m1
    return (a + b) / 2


def optimizar(entreno, prueba, theta0, escalas, K, lam, epocas, lr):
    theta = list(theta0)
    m = [0.0] * len(theta)
    v = [0.0] * len(theta)
    b1, b2, eps = 0.9, 0.999, 1e-8
    mejor = (error(prueba, theta, K), list(theta), 0)
    paciencia = 0
    ln10 = math.log(10)
    for ep in range(1, epocas + 1):
        grad = [0.0] * len(theta)
        for phi, resto, r in entreno:
            e = resto + sum(theta[i] * x for i, x in phi)
            p = prob(e, K)
            g = -2 * (r - p) * p * (1 - p) * K * ln10 / 4  # d(error)/d(evaluación)
            for i, x in phi:
                grad[i] += g * x
        n = len(entreno)
        for i in range(len(theta)):
            z = (theta[i] - theta0[i]) / escalas[i]
            gz = grad[i] / n * escalas[i] + 2 * lam * z  # gradiente respecto del parámetro normalizado
            m[i] = b1 * m[i] + (1 - b1) * gz
            v[i] = b2 * v[i] + (1 - b2) * gz * gz
            mh, vh = m[i] / (1 - b1 ** ep), v[i] / (1 - b2 ** ep)
            theta[i] -= lr * escalas[i] * mh / (math.sqrt(vh) + eps)
        if ep % 10 == 0:
            ep_prueba = error(prueba, theta, K)
            if ep_prueba < mejor[0] - 1e-7:
                mejor, paciencia = (ep_prueba, list(theta), ep), 0
            else:
                paciencia += 1
                if paciencia >= 6:  # el error de prueba ya no baja: se detiene antes de memorizar
                    break
            print('  época %4d: error de entrenamiento %.6f, de prueba %.6f' % (
                ep, error(entreno, theta, K), ep_prueba), flush=True)
    return mejor


# ---------------------------------------------------------------------- principal
def main():
    ap = argparse.ArgumentParser(description='Afinado de la evaluación (método de Texel)',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('bitacoras', nargs='+', help='archivos de bitácora (del 11×11, con resultado)')
    ap.add_argument('--saltar', type=int, default=8, help='medias jugadas iniciales que no se usan (8)')
    ap.add_argument('--cada', type=int, default=1, help='usar una de cada N posiciones (1 = todas)')
    ap.add_argument('--max-posiciones', type=int, default=400000, help='máximo de posiciones (400000)')
    ap.add_argument('--regularizacion', type=float, default=0.002,
                    help='cuánto se resiste a alejarse de los valores actuales (0.002)')
    ap.add_argument('--epocas', type=int, default=600, help='épocas máximas (600)')
    ap.add_argument('--ritmo', type=float, default=0.05, help='tasa de aprendizaje (0.05)')
    ap.add_argument('--todos-los-pesos', action='store_true',
                    help='ajusta también los pesos de los términos apagados (por defecto, solo los encendidos)')
    ap.add_argument('--salida', default='texel_parametros.json', help='parámetros ajustados (texel_parametros.json)')
    a = ap.parse_args()
    rng = random.Random(1)
    t0 = time.time()
    datos, partidas = posiciones(a.bitacoras, a.saltar, a.cada, rng)
    datos = datos[:a.max_posiciones]
    if not datos:
        raise SystemExit('No hay posiciones: hacen falta bitácoras del 11×11 con resultado.')
    print('%d posiciones tranquilas de %d partidas (%.0f s). Calculando características...' % (
        len(datos), partidas, time.time() - t0), flush=True)
    pesos_libres = [k for k in B.PESOS if a.todos_los_pesos or B.PESOS[k]]
    filas, claves = [], {}
    for k, (st, r, pid) in enumerate(datos):
        phi, resto = caracteristicas(st, pesos_libres)
        fila = []
        for c, x in phi.items():
            if c not in claves:
                claves[c] = len(claves)
            fila.append((claves[c], x))
        filas.append((fila, resto, r, pid))
        if (k + 1) % 20000 == 0:
            print('  %d / %d' % (k + 1, len(datos)), flush=True)
    lista = sorted(claves, key=claves.get)
    theta0 = [theta_actual(c) for c in lista]
    escalas = [GRUPOS[c[0]] for c in lista]
    prueba = [(f, s, r) for f, s, r, pid in filas if pid % 10 == 0]
    entreno = [(f, s, r) for f, s, r, pid in filas if pid % 10 != 0]
    K = ajustar_K(entreno, theta0)
    e_ent, e_pru = error(entreno, theta0, K), error(prueba, theta0, K)
    print('K = %.3f. Error con los parámetros actuales: entrenamiento %.6f, prueba %.6f' % (K, e_ent, e_pru))
    print('Optimizando %d parámetros con %d posiciones de entrenamiento y %d de prueba...' % (
        len(theta0), len(entreno), len(prueba)), flush=True)
    e_final, theta, ep = optimizar(entreno, prueba, theta0, escalas, K, a.regularizacion, a.epocas, a.ritmo)
    print('\nMejor error de prueba: %.6f (antes %.6f, %.2f%% menos), en la época %d.' % (
        e_final, e_pru, 100 * (e_pru - e_final) / e_pru if e_pru else 0, ep))

    params = B.parametros()
    nombres = {'VM': 'VALOR_MEDIO', 'VF': 'VALOR_FINAL', 'C': 'CENTRO', 'CP': 'CENTRO_PROM', 'A': 'AVANCE', 'W': 'PESOS'}
    print('\n%-30s %9s %9s %9s' % ('parámetro', 'actual', 'ajustado', 'cambio'))
    for c, v0, v in sorted(zip(lista, theta0, theta), key=lambda x: (x[0][0], str(x[0][1:]))):
        g = nombres[c[0]]
        if c[0] in ('VM', 'VF'):
            params[g][c[1]][c[2]] = round(v, 3)
            etiqueta = '%s %s%s' % (g, c[1], "'" if c[2] else '')
        else:
            params[g][c[1]] = round(v, 4)
            etiqueta = '%s %s' % (g, c[1])
        print('%-30s %9.3f %9.3f %+9.3f' % (etiqueta, v0, v, v - v0))
    params['_afinado'] = {'fecha': time.strftime('%Y-%m-%d %H:%M'), 'posiciones': len(datos), 'partidas': partidas,
                          'K': round(K, 4), 'error_prueba_antes': round(e_pru, 6), 'error_prueba': round(e_final, 6),
                          'bitacoras': [os.path.basename(x) for x in a.bitacoras]}
    with open(a.salida, 'w', encoding='utf-8') as fh:
        json.dump(params, fh, ensure_ascii=False, indent=1)
    print('\nParámetros guardados en %s (%.0f s en total). Valídalos con comparar.py (ver la ayuda: -h).' % (
        a.salida, time.time() - t0))


if __name__ == '__main__':
    main()
