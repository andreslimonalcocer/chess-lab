"""Finales de Rey y pieza contra Rey: ¿puede la pieza dar mate y en cuántas jugadas?

Para cada pieza construye la tabla completa del final Rey + pieza contra Rey solo: recorre
todas las posiciones posibles (dónde está cada Rey, dónde está la pieza y a quién le toca) y,
partiendo de los mates, calcula hacia atrás cuántas jugadas necesita el bando fuerte con
juego perfecto de ambos lados. El resultado no depende de la habilidad de la computadora:
  - si la pieza puede forzar el mate (desde la posición inicial y en general);
  - el mínimo de jugadas para dar mate desde las casillas iniciales (Rey blanco en f1, Rey
    negro en f11 y la pieza en su casilla de inicio, juegan las blancas);
  - el mate más largo posible y el porcentaje de posiciones ganadas, en total y dentro del
    límite de la regla de las 50 jugadas (7.4).
Usa las reglas de motor.py. No se aplica la regla de material insuficiente (7.5), que daría
por terminados al instante los finales de Alfil o Caballo: precisamente se quiere ver si con
ellos se puede dar mate. El peón y el Guardián promocionan al llegar a la última fila (5.2).
No se considera el enroque.

Con --guardar-tablas se guarda además la tabla completa de cada pieza en la carpeta tablas/
(K<pieza>K.dtm, de 3.5 a 7 MB cada una; las 18 ocupan unos 80 MB). La computadora las usa durante la
búsqueda si se activa busqueda.OPCIONES['finales']: en esos finales juega el mate más corto y sabe
cuándo son tablas.

Ejemplos:
  pypy3 finales.py                         # las 18 formas, 6 en paralelo
  pypy3 finales.py --guardar-tablas --procesos 9
  pypy3 finales.py --piezas R B N --procesos 3
  pypy3 finales.py --piezas "CE'" "R'"
"""
import argparse, functools, json, os, sys, time
from array import array
from multiprocessing import Pool
from motor import *

TIPOS = ('Q', 'R', 'B', 'N', 'CA', 'CH', 'CE', 'G', 'P')
NOMBRES = {'P': 'Peón', 'G': 'Guardián', 'B': 'Alfil', 'N': 'Caballo', 'R': 'Torre', 'CE': 'Catapulta',
           'CA': 'Arzobispo', 'CH': 'Canciller', 'Q': 'Dama'}
CAPTURADA = -2  # el Rey solo capturó la pieza: tablas
REY_B, REY_N = sqn('f1'), sqn('f11')


def nombre(t, pr):
    if not pr:
        return NOMBRES[t]
    return NOMBRES[t] + (' promocionada' if t in ('Q', 'R', 'CE') else ' promocionado')


def adyacentes(a, b):
    return max(abs(a % N - b % N), abs(a // N - b // N)) <= 1


class Tabla:
    def __init__(self, t, pr):
        self.t, self.pr = t, pr
        # estados de la pieza: casilla (+121 si está promocionada); peón y Guardián pueden promocionar
        self.promociona = t in ('P', 'G') and not pr
        self.nx = 2 * N * N if self.promociona else N * N
        self.total = N * N * N * N * self.nx * 2

    def idx(self, wk, bk, xi, turno):
        return ((wk * N * N + bk) * self.nx + xi) * 2 + turno

    def xi(self, sq, pr):
        return sq + (N * N if (pr and self.promociona) else 0)

    def pieza(self, xi):
        """(casilla, promocionada) de un estado de la pieza."""
        if self.promociona:
            return xi % (N * N), xi >= N * N
        return xi, self.pr

    def estado(self, wk, bk, sq, pr, turno):
        st = St.__new__(St)
        b = [None] * (N * N)
        b[wk] = Pc('K', 0, moved=True)
        b[bk] = Pc('K', 1, moved=True)
        inicial = sq // N == start_row(0) and self.t in ('P', 'G') and not pr
        b[sq] = Pc(self.t, 0, pr=pr, moved=True, dbl=inicial, init=inicial and self.t == 'G', pid=1)
        st.b, st.turn, st.ep = b, turno, None
        st.capP, st.capG, st.capT = [0, 0], [0, 0], [{}, {}]
        st.conv, st.gprom = [0, 0], [0, 0]
        st.tprom = [{self.t} if (pr and self.t not in ('P', 'G')) else set(), set()]
        st.pts, st.clock, st.kpos = [0.0, 0.0], 0, [wk, bk]
        return st

    def construir(self):
        """Genera todas las posiciones legales y sus sucesoras."""
        t0 = time.time()
        self.valida = bytearray(self.total)
        self.jaque = bytearray(self.total)
        self.ini = array('q', [0]) * (self.total + 1)
        hijos = array('i')
        ultimo = 0
        for wk in range(N * N):
            for bk in range(N * N):
                if wk == bk or adyacentes(wk, bk):
                    for xi in range(self.nx):
                        for turno in (0, 1):
                            self.ini[self.idx(wk, bk, xi, turno) + 1] = len(hijos)
                    continue
                for xi in range(self.nx):
                    sq, pr = self.pieza(xi)
                    fila = sq // N
                    invalida = sq in (wk, bk) or (self.t in ('P', 'G') and not pr and fila == N - 1) or \
                        (self.t == 'P' and fila == 0)
                    for turno in (0, 1):
                        p = self.idx(wk, bk, xi, turno)
                        if not invalida:
                            st = self.estado(wk, bk, sq, pr, turno)
                            if not (turno == 0 and in_check(st, 1)):  # el que no mueve no puede estar en jaque
                                self.valida[p] = 1
                                self.jaque[p] = in_check(st, turno)
                                for mv, n in legal(st):
                                    hijos.append(self.hijo(wk, bk, xi, sq, turno, mv, n))
                        self.ini[p + 1] = len(hijos)
        self.hijos = hijos
        self.t_construir = time.time() - t0

    def hijo(self, wk, bk, xi, sq, turno, mv, n):
        """Índice de la posición tras la jugada mv (en n)."""
        de, a = mv[1], mv[2]
        if turno == 1:  # solo puede mover el Rey negro
            return CAPTURADA if a == sq else self.idx(wk, a, xi, 0)
        if de == wk:
            return self.idx(a, bk, xi, 1)
        return self.idx(wk, bk, self.xi(a, n.b[a].pr), 1)  # la pieza (puede haber promocionado al llegar)

    def resolver(self):
        """Análisis retrógrado: dtm[p] = medias jugadas hasta el mate con juego perfecto (-1 = no se fuerza)."""
        t0 = time.time()
        dtm = array('h', [-1]) * self.total
        ini, hijos, valida = self.ini, self.hijos, self.valida
        blancas, negras = array('i'), array('i')
        for p in range(self.total):
            if not valida[p]:
                continue
            if p & 1:
                if ini[p] == ini[p + 1] and self.jaque[p]:
                    dtm[p] = 0  # mate
                else:
                    negras.append(p)
            else:
                blancas.append(p)
        n, vacias = 0, 0
        while vacias < 2:
            n += 1
            nuevos = []
            if n % 2:  # juegan las blancas: ganan si alguna jugada lleva a una posición perdida en n-1
                quedan = array('i')
                for p in blancas:
                    for k in range(ini[p], ini[p + 1]):
                        c = hijos[k]
                        if c >= 0 and dtm[c] == n - 1:
                            nuevos.append(p)
                            break
                    else:
                        quedan.append(p)
                blancas = quedan
            else:  # juegan las negras: pierden si todas sus jugadas llevan a posiciones ganadas
                quedan = array('i')
                for p in negras:
                    for k in range(ini[p], ini[p + 1]):
                        c = hijos[k]
                        if c < 0 or dtm[c] < 0:
                            quedan.append(p)
                            break
                    else:
                        if ini[p] < ini[p + 1]:
                            nuevos.append(p)
                        else:
                            quedan.append(p)  # ahogado
                negras = quedan
            for p in nuevos:
                dtm[p] = n
            vacias = 0 if nuevos else vacias + 1
        self.dtm = dtm
        self.t_resolver = time.time() - t0

    def resumen(self):
        jugadas = lambda d: (d + 1) // 2
        validas = ganadas = en50 = suma = maximo = 0
        for p in range(0, self.total, 2):
            if not self.valida[p]:
                continue
            sq, pr = self.pieza(((p // 2) % self.nx))
            if pr != self.pr:
                continue
            validas += 1
            d = self.dtm[p]
            if d >= 0:
                ganadas += 1
                j = jugadas(d)
                suma += j
                maximo = max(maximo, j)
                en50 += j <= 50
        inicio = {}
        for sq in sorted(s for s, p in enumerate(initial().b) if p and p.c == 0 and p.t == self.t):
            d = self.dtm[self.idx(REY_B, REY_N, self.xi(sq, self.pr), 0)]
            inicio[name(sq)] = jugadas(d) if d >= 0 else None
        return dict(pieza=self.t + ("'" if self.pr else ''), nombre=nombre(self.t, self.pr), inicio=inicio,
                    ganadas=ganadas / validas, ganadas50=en50 / validas, media=suma / ganadas if ganadas else None,
                    maximo=maximo if ganadas else None, posiciones=validas,
                    segundos=round(self.t_construir + self.t_resolver))


def guardar_tabla(tabla):
    """dtm de cada posición en un byte: medias jugadas hasta el mate (255 = no se fuerza el mate)."""
    from busqueda import archivo_tabla, CARPETA_TABLAS
    os.makedirs(CARPETA_TABLAS, exist_ok=True)
    datos = bytes(d if 0 <= d < 255 else 255 for d in tabla.dtm)
    ruta = archivo_tabla(tabla.t, tabla.pr)
    with open(ruta + '.tmp', 'wb') as f:
        f.write(datos)
    os.replace(ruta + '.tmp', ruta)


def analizar(pieza, guardar=False):
    t, pr = pieza.rstrip("'"), pieza.endswith("'")
    tabla = Tabla(t, pr)
    tabla.construir()
    tabla.resolver()
    if guardar:
        guardar_tabla(tabla)
    return tabla.resumen()


def imprimir(resultados):
    print('\n%-24s %-26s %8s %9s %8s %8s' % ('', 'MATE DESDE EL INICIO', 'POSIC.', 'GANADAS', 'MEDIA', 'MÁS'))
    print('%-24s %-26s %8s %9s %8s %8s' % ('pieza', '(jugadas, por casilla)', 'GANADAS', 'EN ≤50', 'JUGADAS', 'LARGO'))
    for r in resultados:
        ini = ', '.join('%s: %s' % (c, j if j is not None else 'no') for c, j in r['inicio'].items())
        print('%-24s %-26s %7.1f%% %8.1f%% %8s %8s' % (
            r['nombre'], ini[:26], 100 * r['ganadas'], 100 * r['ganadas50'],
            '%.1f' % r['media'] if r['media'] else '—', r['maximo'] if r['maximo'] else '—'))
        if len(ini) > 26:
            print('%-24s %s' % ('', ini[26:]))
    print('\nMate desde el inicio: jugadas de las blancas para dar mate con juego perfecto, desde Rey en f1,')
    print('Rey negro en f11 y la pieza en cada una de sus casillas iniciales; «no» = no se puede forzar.')
    print('Posiciones ganadas: de todas las posiciones posibles con turno de las blancas, en cuántas se fuerza')
    print('el mate; «en ≤50», dentro del límite de la regla de las 50 jugadas.')


def main():
    ap = argparse.ArgumentParser(description='Finales de Rey y pieza contra Rey (análisis exacto)',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--piezas', nargs='+', default=[t + p for t in TIPOS for p in ('', "'")],
                    help="piezas a analizar: Q R B N CA CH CE G P, con apóstrofo la promocionada (todas)")
    ap.add_argument('--procesos', type=int, default=6, help='piezas en paralelo (6; cada una usa ~0.5-1 GB)')
    ap.add_argument('--salida', default='finales.json', help='archivo de resultados (finales.json)')
    ap.add_argument('--guardar-tablas', action='store_true',
                    help='guarda las tablas completas en tablas/ para que la computadora las use')
    a = ap.parse_args()
    for p in a.piezas:
        if p.rstrip("'") not in TIPOS:
            raise SystemExit('Pieza desconocida: %s' % p)
    print('Analizando %d piezas con %d procesos (unos minutos por pieza)...' % (len(a.piezas), a.procesos), flush=True)
    t0 = time.time()
    resultados = []
    f = functools.partial(analizar, guardar=a.guardar_tablas)
    it = Pool(a.procesos).imap(f, a.piezas) if a.procesos > 1 else map(f, a.piezas)
    for r in it:
        resultados.append(r)
        print('  %s listo (%d s)' % (r['nombre'], r['segundos']), flush=True)
    imprimir(resultados)
    previos = {}
    if os.path.exists(a.salida):
        with open(a.salida, encoding='utf-8') as f:
            previos = {r['pieza']: r for r in json.load(f)}
    previos.update({r['pieza']: r for r in resultados})
    with open(a.salida, 'w', encoding='utf-8') as f:
        json.dump(list(previos.values()), f, ensure_ascii=False, indent=1)
    print('\nListo en %.0f s. Resultados guardados en %s.' % (time.time() - t0, a.salida))


if __name__ == '__main__':
    main()
