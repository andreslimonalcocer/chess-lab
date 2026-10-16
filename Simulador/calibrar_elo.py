"""Calibración en Elo de los niveles de dificultad de la computadora (Ajedrez 11x11).

Juega una escalera de niveles (configuraciones de profundidad, tiempo y temperatura) contra sus
vecinos, calcula el Elo de cada nivel con el modelo logístico (el mismo del ajedrez) y guarda
niveles_elo.json, que el juego de escritorio usa para ofrecer la dificultad en Elo.

El Elo es relativo: hace falta fijar un punto. Por convención el nivel más bajo vale --ancla (800).
Para el 11x11 no existe un rival de referencia con Elo conocido, así que la escala es propia del
juego: 400 puntos de diferencia significan que el más fuerte gana alrededor de 10 de cada 11.

Ejemplos:
  pypy3 calibrar_elo.py --partidas 40 --procesos 22
  pypy3 calibrar_elo.py --partidas 40 --procesos 22 --hasta 6      # sin los niveles más lentos
  python3 calibrar_elo.py --solo-ajuste                            # recalcular con lo ya jugado
"""
import argparse, json, math, os, random, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from comparar import correr, tareas, leer_config

# escalera de niveles, de menor a mayor fuerza: (profundidad, segundos por jugada, temperatura)
# Versión 2 (octubre de 2026): la temperatura ya usa puntuaciones exactas (antes las jugadas malas
# parecían casi tan buenas como la mejor), así que los niveles con imprecisión escalonan de verdad.
ESCALERA = [
    (1, 0, 0.6),
    (1, 0, 0.0),
    (2, 0, 0.4),
    (2, 0, 0.0),
    (3, 0, 0.3),
    (3, 0, 0.1),
    (3, 0, 0.0),
    (4, 0, 0.0),
    (5, 10, 0.0),
    # niveles altos (octubre de 2026): con la búsqueda v6 la profundidad 5 cuesta menos de un segundo, así que
    # se agregan más profundos; el último no tiene límite de profundidad, solo de tiempo
    # Ajuste tras medir qué profundidad alcanza cada nivel en partidas reales: con 5 s la profundidad 6 no
    # siempre se completaba (quedó a la par del nivel anterior) y con 10 s la 7 se quedaba en 6 en la mitad del
    # medio juego. Ahora: profundidad 6 con 10 s (siempre la completa), profundidad 7 con 20 s (la completa
    # salvo en la apertura) y sin límite de profundidad con 30 s (7-8 en el medio juego, 9-11 en los finales).
    # Las partidas de las versiones anteriores quedan en el archivo, pero ya no cuentan.
    (6, 10, 0.0),
    (7, 20, 0.0),
    (30, 30, 0.0),
]
DISTANCIAS = (1, 2, 3)  # cada nivel juega contra los tres siguientes, para unir bien la escala


def nombre(i):
    """Nombre de un nivel según sus parámetros: los resultados siguen valiendo si cambia la escalera."""
    prof, tiempo, temp = ESCALERA[i]
    return 'p%d_t%g_T%g' % (prof, tiempo, temp)


def config(i):
    prof, tiempo, temp = ESCALERA[i]
    return leer_config('prof=%d,tiempo=%g,temp=%g,mejoras=1,nombre=%s' % (prof, tiempo, temp, nombre(i)))


def ajustar(resultados, ancla):
    """Elo de cada nivel de la escalera por máxima verosimilitud (logístico), con el más bajo = ancla.
    Cada enfrentamiento lleva además una tabla «virtual»: sin ella, un 40-0 daría una diferencia
    infinita (y el valor dependería de cuántas iteraciones haga el ajuste)."""
    orden = {nombre(i): i for i in range(len(ESCALERA))}
    resultados = [r for r in resultados if r['x'] in orden and r['y'] in orden]
    pares = {(r['x'], r['y']) for r in resultados}
    resultados = resultados + [{'x': x, 'y': y, 'puntos_x': 0.5} for x, y in pares]
    niveles = sorted({r[k] for r in resultados for k in ('x', 'y')}, key=lambda n: orden[n])
    elo = {n: 0.0 for n in niveles}
    k = math.log(10) / 400
    for _ in range(3000):  # ascenso por gradiente, simple y suficiente para pocas decenas de niveles
        grad = {n: 0.0 for n in niveles}
        for r in resultados:
            p = 1 / (1 + math.exp(-k * (elo[r['x']] - elo[r['y']])))
            grad[r['x']] += r['puntos_x'] - p
            grad[r['y']] -= r['puntos_x'] - p
        for n in niveles:
            if n != niveles[0]:
                elo[n] += 4.0 * grad[n]
    return {n: ancla + elo[n] - elo[niveles[0]] for n in niveles}


def main():
    ap = argparse.ArgumentParser(description='Calibración en Elo de los niveles de la computadora',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--partidas', type=int, default=40,
                    help='partidas por enfrentamiento en total (40); solo se juegan las que falten en --salida')
    ap.add_argument('--procesos', type=int, default=1)
    ap.add_argument('--hasta', type=int, default=len(ESCALERA) - 1, help='último nivel a calibrar (todos)')
    ap.add_argument('--ancla', type=float, default=800, help='Elo del nivel más bajo (800)')
    ap.add_argument('--salida', default='calibracion_v2.jsonl',
                    help='partidas jugadas (calibracion_v2.jsonl; calibracion.jsonl es de antes de corregir la '
                         'temperatura y no sirve para la escalera nueva)')
    ap.add_argument('--niveles', default=os.path.join(AQUI, '..', 'Juego', 'niveles_elo.json'),
                    help='archivo de niveles para el juego (Juego/niveles_elo.json)')
    ap.add_argument('--solo-ajuste', action='store_true', help='no jugar: recalcular con lo ya jugado')
    a = ap.parse_args()
    if not a.solo_ajuste:
        lista = []
        jugadas = {}
        if os.path.exists(a.salida):
            for l in open(a.salida, encoding='utf-8'):
                r = json.loads(l)
                jugadas[(r['x'], r['y'])] = jugadas.get((r['x'], r['y']), 0) + 1
        for i in range(a.hasta):  # cada nivel contra los siguientes (DISTANCIAS)
            for j in (i + d for d in DISTANCIAS):
                if j <= a.hasta:
                    # --partidas es el total por enfrentamiento: solo se juegan las que faltan, así que se
                    # puede retomar y, al agregar niveles, solo se juegan sus enfrentamientos
                    previas = jugadas.get((nombre(j), nombre(i)), 0)
                    faltan = a.partidas - previas
                    if faltan > 0:
                        lista += tareas(config(j), config(i), faltan, 1000 * j + 100 * i + previas // 2, 4, 200)
        random.Random(1).shuffle(lista)  # mezclar niveles rápidos y lentos para repartir la carga
        print('Calibrando %d niveles: %d partidas con %d procesos...' % (a.hasta + 1, len(lista), a.procesos))
        correr(lista, a.procesos, a.salida)
    resultados = [json.loads(l) for l in open(a.salida, encoding='utf-8')]
    elo = ajustar(resultados, a.ancla)
    niveles = []
    print('\n%-5s %-6s %-7s %-6s %s' % ('nivel', 'prof.', 'tiempo', 'temp.', 'Elo'))
    orden = [nombre(i) for i in range(len(ESCALERA)) if nombre(i) in elo]
    for k, n in enumerate(orden):
        prof, tiempo, temp = ESCALERA[[nombre(i) for i in range(len(ESCALERA))].index(n)]
        print('%-5s %-6d %-7s %-6g %.0f' % ('N%d' % k, prof, ('%g s' % tiempo) if tiempo else '—', temp, elo[n]))
        niveles.append({'elo': round(elo[n] / 50) * 50, 'profundidad': prof, 'tiempo': tiempo, 'temperatura': temp})
    for k in range(1, len(orden)):  # la escalera debe subir: si no, dos niveles valen lo mismo
        if elo[orden[k]] < elo[orden[k - 1]] + 30:
            print('Aviso: N%d (%s) no es más fuerte que N%d (%s): %.0f contra %.0f Elo. Conviene cambiar uno de '
                  'los dos en ESCALERA.' % (k, orden[k], k - 1, orden[k - 1], elo[orden[k]], elo[orden[k - 1]]))
    with open(a.niveles, 'w', encoding='utf-8') as f:
        json.dump({'descripcion': 'Niveles de la computadora calibrados en Elo con calibrar_elo.py (%s); '
                                  'el nivel más bajo vale %g por convención.' % (time.strftime('%Y-%m-%d'), a.ancla),
                   'niveles': niveles}, f, ensure_ascii=False, indent=1)
    print('\nNiveles guardados en %s.' % os.path.abspath(a.niveles))


if __name__ == '__main__':
    main()
