"""Finales de Rey y DOS piezas contra Rey solo, en el 11×11: ¿se puede forzar el mate y en cuántas jugadas?

Como finales.py, pero con dos piezas blancas: dos iguales (N+N, B+B, R+R) o una promocionada y una normal
(N'+N, B'+B, R'+R), o cualquier otra combinación de Q R B N CA CH CE (con apóstrofo, promocionada; el peón
y el Guardián no, porque promocionan al avanzar). Con dos piezas hay entre 212 y 429 millones de
posiciones, así que no se guardan las jugadas: se usa análisis retrógrado (desde los mates, deshaciendo
jugadas), con las reglas exactas del motor:
  - Caballo: saltos (1,2) y (1,3); promocionado, además (2,3).
  - Alfil: diagonales; promocionado, además 1 a 3 casillas en recto (saltando).
  - Torre: líneas rectas; promocionada, además 1 a 3 casillas en diagonal (saltando).
Si el Rey negro captura una pieza, se consulta la tabla exacta de Rey y la pieza que queda (tablas/,
de finales.py --guardar-tablas); sin esa tabla se cuenta como tablas. Sin regla de las 50 jugadas ni enroque.

Uso:
  pypy3 finales_dos.py N+N            # ~10 min, ~1 GB de memoria (piezas iguales)
  pypy3 finales_dos.py "R'+R"         # ~20-40 min, ~1.5 GB (piezas distintas)
  pypy3 finales_dos.py B+N            # Alfil y Caballo (separa el Alfil de casillas claras y oscuras)
  pypy3 finales_dos.py B+B --guardar  # además guarda la tabla en tablas/ (212 o 429 MB)
El resumen se agrega a finales.json (pieza «N+N», «R'+R», ...).
"""
import argparse, json, os, sys, time
from array import array

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from motor import (N, SALTOS_REY, SALTOS_C, SALTOS_N, SALTOS_NP, RAYOS, TRES_DIAG, TRES_ORTO, sqn)
import busqueda as B

NN = N * N
NOMBRES = {'Q': 'Dama', 'R': 'Torre', 'B': 'Alfil', 'N': 'Caballo', 'CA': 'Arzobispo', 'CH': 'Canciller',
           'CE': 'Catapulta'}
INICIO = {'Q': ['e1'], 'R': ['a1', 'k1'], 'B': ['c1', 'j1'], 'N': ['b1', 'i1'], 'CA': ['d1'], 'CH': ['h1'],
          'CE': ['g1']}

VECINO = bytearray(NN * NN)  # VECINO[x*NN+y] = 1 si x e y son vecinas (o la misma casilla)
for _x in range(NN):
    VECINO[_x * NN + _x] = 1
    for _y in SALTOS_REY[_x]:
        VECINO[_x * NN + _y] = 1


class Pieza:
    """Movimientos de una pieza sin promocionar o promocionada: deslizamientos (rayos) y saltos."""

    def __init__(self, t, pr):
        self.t, self.pr = t, pr
        rayos, saltos = [[] for _ in range(NN)], [[] for _ in range(NN)]
        for sq in range(NN):
            if t in ('Q', 'R', 'CH'):  # rectas (la Dama, además, diagonales)
                rayos[sq] += RAYOS[sq] if t == 'Q' else RAYOS[sq][:4]
            if t in ('B', 'CA'):
                rayos[sq] += RAYOS[sq][4:]
            if t == 'N':
                saltos[sq] += SALTOS_NP[sq] if pr else SALTOS_N[sq]
            if t in ('CA', 'CH'):
                saltos[sq] += SALTOS_C[sq]
            if pr and t == 'Q':
                saltos[sq] += SALTOS_C[sq]
            if pr and t == 'R':
                saltos[sq] += [i for pasos in TRES_DIAG[sq] for i, _ in pasos]
            if pr and t == 'B':
                saltos[sq] += [i for pasos in TRES_ORTO[sq] for i, _ in pasos]
        if t not in ('Q', 'R', 'B', 'N', 'CA', 'CH'):
            raise SystemExit('Pieza no admitida: %s (usa Q R B N CA CH)' % t)
        if pr and t in ('CA', 'CH'):
            raise SystemExit('El Arzobispo y el Canciller promocionados no están en este análisis.')
        self.rayos = rayos
        self.salta = bytearray(NN * NN)
        self.saltos = saltos
        for x in range(NN):
            for y in saltos[x]:
                self.salta[x * NN + y] = 1
        self.entre = [dict() for _ in range(NN)]  # casillas intermedias por cada casilla de sus rayos
        for x in range(NN):
            for rayo in rayos[x]:
                for k, y in enumerate(rayo):
                    self.entre[x][y] = rayo[:k]

    def ataca(self, p, sq, bloq1, bloq2):
        """¿La pieza en p ataca sq, con bloq1 y bloq2 como posibles obstáculos?"""
        if self.salta[p * NN + sq]:
            return True
        e = self.entre[p].get(sq)
        return e is not None and bloq1 not in e and bloq2 not in e

    def destinos(self, p, ocupadas):
        """Casillas a las que puede ir (o de las que pudo venir) desde p, sin pasar por las ocupadas."""
        out = [y for y in self.saltos[p] if y not in ocupadas]
        for rayo in self.rayos[p]:
            for y in rayo:
                if y in ocupadas:
                    break
                out.append(y)
        return out


def leer(texto):
    t = texto.strip()
    return t.rstrip("'"), t.endswith("'")


class Final:
    def __init__(self, a, b):
        (ta, pa), (tb, pb) = leer(a), leer(b)
        self.A, self.B = Pieza(ta, pa), Pieza(tb, pb)
        self.nombre = 'Rey, %s y %s' % (nombre(ta, pa), nombre(tb, pb))
        self.clave = '%s+%s' % (a, b)
        self.iguales = (ta, pa) == (tb, pb)
        if self.iguales:  # pares sin orden
            self.par = [[-1] * NN for _ in range(NN)]
            self.pa, self.pb = array('i'), array('i')
            for x in range(NN):
                for y in range(x + 1, NN):
                    self.par[x][y] = self.par[y][x] = len(self.pa)
                    self.pa.append(x)
                    self.pb.append(y)
            self.np = len(self.pa)
        else:
            self.np = NN * NN
        self.total = NN * NN * self.np * 2

    def indice_par(self, a, b):
        return self.par[a][b] if self.iguales else a * NN + b

    def casillas(self, par):
        return (self.pa[par], self.pb[par]) if self.iguales else (par // NN, par % NN)

    def pares(self):
        if self.iguales:
            for par in range(self.np):
                yield par, self.pa[par], self.pb[par]
        else:
            for a in range(NN):
                for b in range(NN):
                    if a != b:
                        yield a * NN + b, a, b

    def jaque(self, a, b, wk, bk):
        """¿Las piezas en a y b atacan al Rey negro en bk?"""
        return self.A.ataca(a, bk, wk, b) or self.B.ataca(b, bk, wk, a)


def nombre(t, pr):
    n = NOMBRES[t]
    return n + ((' promocionada' if t in ('Q', 'R', 'CE') else ' promocionado') if pr else '')


def tabla_una(t, pr):
    """dtm de Rey y una pieza contra Rey (con turno de las blancas), o None si no está la tabla."""
    tabla = B._tabla(t, pr)
    if tabla is None:
        return None
    return lambda wk, bk, sq: tabla[((wk * NN + bk) * NN + sq) * 2]


def construir(F):
    dtm = bytearray(b'\xff') * F.total   # medias jugadas hasta el mate (255 = sin mate forzado / inválida)
    cuenta = bytearray(F.total)          # negras: jugadas que aún no pierden (250 = se salva); blancas: 1 = válida
    ext = bytearray(F.total)             # negras: la más larga de sus capturas perdedoras (medias jugadas)
    sin_a, sin_b = tabla_una(F.B.t, F.B.pr), tabla_una(F.A.t, F.A.pr)  # tras capturar a A queda B, y viceversa
    pendientes = {}                      # medias jugadas -> posiciones negras perdidas por sus capturas
    perdidas = array('l')
    t0 = time.time()
    for wk in range(NN):
        for bk in range(NN):
            if VECINO[wk * NN + bk]:
                continue
            base = (wk * NN + bk) * F.np
            for par, a, b in F.pares():
                if a == wk or a == bk or b == wk or b == bk:
                    continue
                i = (base + par) * 2
                jaque = F.jaque(a, b, wk, bk)
                if not jaque:
                    cuenta[i] = 1
                jugadas, salva, peor = 0, False, 0
                for y in SALTOS_REY[bk]:
                    if VECINO[wk * NN + y]:
                        continue
                    if y == a or y == b:  # captura: queda Rey y la otra pieza contra Rey
                        if y == a:
                            if F.B.ataca(b, y, wk, -1):
                                continue
                            d = sin_a(wk, y, b) if sin_a else 255
                        else:
                            if F.A.ataca(a, y, wk, -1):
                                continue
                            d = sin_b(wk, y, a) if sin_b else 255
                        if d == 255:
                            salva = True
                        else:
                            peor = max(peor, d + 1)
                        continue
                    if F.A.ataca(a, y, wk, b) or F.B.ataca(b, y, wk, a):
                        continue
                    jugadas += 1
                if salva:
                    cuenta[i + 1] = 250
                    continue
                cuenta[i + 1] = jugadas
                ext[i + 1] = peor
                if jugadas == 0:
                    if peor:
                        pendientes.setdefault(peor, array('l')).append(i + 1)
                    elif jaque:
                        dtm[i + 1] = 0
                        perdidas.append(i + 1)
                    else:
                        cuenta[i + 1] = 250  # ahogado: tablas
        if wk % 11 == 10:
            print('  inicialización: fila %d de 11 (%.0f s)' % (wk // N + 1, time.time() - t0), flush=True)
    print('Mates encontrados: %d. Calculando hacia atrás...' % len(perdidas), flush=True)

    n = 0
    while perdidas or pendientes:
        for i in pendientes.pop(n, ()):  # perdidas cuya peor captura dura justo n
            if dtm[i] == 255:
                dtm[i] = n
                perdidas.append(i)
        # blancas: toda posición desde la que se llega a una perdida de las negras se gana en n + 1
        ganadas = array('l')
        for i in perdidas:
            par = (i >> 1) % F.np
            r = (i >> 1) // F.np
            wk, bk = r // NN, r % NN
            a, b = F.casillas(par)
            ocupadas = (wk, bk, a, b)
            previas = [(y, a, b) for y in SALTOS_REY[wk] if y not in ocupadas and not VECINO[y * NN + bk]]
            previas += [(wk, y, b) for y in F.A.destinos(a, ocupadas)]
            previas += [(wk, a, y) for y in F.B.destinos(b, ocupadas)]
            for wk2, a2, b2 in previas:
                if F.jaque(a2, b2, wk2, bk):  # juegan las blancas: el Rey negro no puede estar en jaque
                    continue
                j = ((wk2 * NN + bk) * F.np + F.indice_par(a2, b2)) * 2
                if dtm[j] == 255:
                    dtm[j] = n + 1
                    ganadas.append(j)
        n += 1
        # negras: una posición queda perdida cuando todas sus jugadas llevan a posiciones ganadas
        perdidas = array('l')
        for i in ganadas:
            par = (i >> 1) % F.np
            r = (i >> 1) // F.np
            wk, bk = r // NN, r % NN
            a, b = F.casillas(par)
            for y in SALTOS_REY[bk]:  # el Rey negro vino de y
                if y == wk or y == a or y == b or VECINO[wk * NN + y]:
                    continue
                j = ((wk * NN + y) * F.np + par) * 2 + 1
                c = cuenta[j]
                if c == 250 or dtm[j] != 255:
                    continue
                c -= 1
                cuenta[j] = c
                if c == 0:
                    if ext[j] > n + 1:  # una de sus capturas aguanta más: se pierde más tarde
                        pendientes.setdefault(ext[j], array('l')).append(j)
                    else:
                        dtm[j] = n + 1
                        perdidas.append(j)
        n += 1
        if n > 250:
            raise SystemExit('Mates de más de 125 jugadas: no caben en la tabla de un byte.')
        print('  %d medias jugadas: %d posiciones ganadas, %d perdidas para las negras (%.0f s)' % (
            n, len(ganadas), len(perdidas), time.time() - t0), flush=True)
    return dtm, cuenta, time.time() - t0


def resumen(F, dtm, cuenta, segundos):
    """Estadísticas de las posiciones con turno de las blancas (Alfiles normales: por color de casilla)."""
    grupos = {}
    dos_alfiles = F.A.t == F.B.t == 'B' and not F.A.pr and not F.B.pr
    # con un solo Alfil sin promocionar importa el color de sus casillas: en el 11×11 las cuatro esquinas son
    # claras (columna + fila par), así que el de casillas oscuras no tiene esquina propia
    alfil = None if dos_alfiles else (0 if (F.A.t == 'B' and not F.A.pr) else (1 if (F.B.t == 'B' and not F.B.pr) else None))
    for wk in range(NN):
        for bk in range(NN):
            if VECINO[wk * NN + bk]:
                continue
            base = (wk * NN + bk) * F.np
            for par, a, b in F.pares():
                i = (base + par) * 2
                if cuenta[i] != 1:
                    continue
                g = 'todas'
                if alfil is not None:
                    x_ = (a, b)[alfil]
                    g = 'Alfil de casillas claras' if (x_ % N + x_ // N) % 2 == 0 else 'Alfil de casillas oscuras'
                if dos_alfiles:
                    g = 'mismo color' if (a % N + a // N) % 2 == (b % N + b // N) % 2 else 'distinto color'
                x = grupos.setdefault(g, [0, 0, 0, 0])  # válidas, ganadas, suma de jugadas, máximo
                x[0] += 1
                if dtm[i] != 255:
                    j = (dtm[i] + 1) // 2
                    x[1] += 1
                    x[2] += j
                    x[3] = max(x[3], j)
    ca, cb = INICIO[F.A.t], INICIO[F.B.t]
    if F.A.t == F.B.t:  # dos del mismo tipo: una en cada casilla inicial
        combinaciones = [(ca[0], cb[1] if len(cb) > 1 else cb[0])]
    else:  # tipos distintos: todas las combinaciones de casillas iniciales (por ejemplo, Alfil en c1 o en j1)
        combinaciones = [(x, y) for x in ca for y in cb]
    inicio = {}
    for xa, xb in combinaciones:
        a, b = sqn(xa), sqn(xb)
        if a == b:
            continue
        d = dtm[((sqn('f1') * NN + sqn('f11')) * F.np + F.indice_par(a, b)) * 2]
        inicio['%s y %s' % (xa, xb)] = (d + 1) // 2 if d != 255 else None
    return {'pieza': F.clave, 'nombre': F.nombre, 'inicio': inicio,
            'grupos': {g: {'posiciones': x[0], 'ganadas': x[1] / x[0] if x[0] else 0,
                           'media': x[2] / x[1] if x[1] else None, 'maximo': x[3] or None}
                       for g, x in grupos.items()},
            'segundos': round(segundos)}


def main():
    ap = argparse.ArgumentParser(description='Finales de Rey y dos piezas contra Rey',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('piezas', help="las dos piezas, por ejemplo N+N, B+B, R+R, \"N'+N\", \"R'+R\"")
    ap.add_argument('--guardar', action='store_true', help='guarda la tabla en tablas/ (212 o 429 MB)')
    ap.add_argument('--salida', default=os.path.join(AQUI, 'finales.json'))
    a = ap.parse_args()
    partes = a.piezas.split('+')
    if len(partes) != 2:
        raise SystemExit('Indica dos piezas separadas por «+», por ejemplo N+N o "R\'+R".')
    F = Final(*partes)
    print('%s contra Rey: %d posiciones posibles. Inicializando...' % (F.nombre, F.total), flush=True)
    dtm, cuenta, seg = construir(F)
    r = resumen(F, dtm, cuenta, seg)
    print('\n%s contra Rey:' % r['nombre'])
    for g, x in r['grupos'].items():
        print('  %-15s %6.2f %% de las posiciones ganadas · media %s jugadas · el mate más largo: %s jugadas'
              % (g, 100 * x['ganadas'], '%.1f' % x['media'] if x['media'] else '—', x['maximo'] or '—'))
    for casillas, j in r['inicio'].items():
        print('  desde el inicio (Reyes en f1 y f11, piezas en %s): %s' % (
            casillas, ('mate en %d' % j) if j else 'no se fuerza el mate'))
    previos = []
    if os.path.exists(a.salida):
        with open(a.salida, encoding='utf-8') as f:
            previos = [x for x in json.load(f) if x['pieza'] != r['pieza']]
    with open(a.salida, 'w', encoding='utf-8') as f:
        json.dump(previos + [r], f, ensure_ascii=False, indent=1)
    if a.guardar:
        os.makedirs(B.CARPETA_TABLAS, exist_ok=True)
        ruta = os.path.join(B.CARPETA_TABLAS, 'K%sK.dtm' % F.clave.replace("'", 'p').replace('+', ''))
        with open(ruta, 'wb') as f:
            f.write(dtm)
        print('Tabla guardada en %s.' % ruta)
    print('Listo en %.0f s. Resumen agregado a %s.' % (seg, a.salida))


if __name__ == '__main__':
    main()
