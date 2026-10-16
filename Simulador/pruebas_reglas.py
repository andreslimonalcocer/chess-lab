from motor import *

def base(wk='a1', bk='k11'):
    s = empty_state(); put(s, sqn(wk), 'K', 0); put(s, sqn(bk), 'K', 1); return s

def chains(s):
    return [(m, n) for m, n in legal(s) if m[0] == 'ch']

def ncap(m): return sum(len(c) for _, c in m[3])

# 1) Posición "bloqueo con pieza rival": el salto extendido permite capturar los 4
s = base(); put(s, sqn('f6'), 'CE', 0, pr=True)
for x in ('g6', 'h6', 'h7', 'h8'): put(s, sqn(x), 'P', 1)
cs = chains(s); best = max(cs, key=lambda x: ncap(x[0]))
print('1) max capturas:', ncap(best[0]), [name(l) for l, _ in best[0][3]])
# la cadena que empieza con salto corto se bloquea en 2
short = [m for m, n in cs if m[3][0][0] == sqn('h6')]
print('   cadena corta captura:', [ncap(m) for m in short])

# 2) Posición "bloqueo con pieza propia"
s = base(); put(s, sqn('f6'), 'CE', 0, pr=True)
for x in ('g6', 'h6', 'h7'): put(s, sqn(x), 'P', 1)
put(s, sqn('h8'), 'P', 0)
cs = chains(s); best = max(cs, key=lambda x: ncap(x[0]))
print('2) max capturas:', ncap(best[0]), [name(l) for l, _ in best[0][3]])

# 3) Jaque a distancia dos dentro de la secuencia
s = base(bk='h6'); put(s, sqn('f6'), 'CE', 0, pr=True); put(s, sqn('g6'), 'P', 0)
print('3) Rey en h6 en jaque:', in_check(s, 1))
s = base(bk='i6'); put(s, sqn('f6'), 'CE', 0, pr=True); put(s, sqn('g6'), 'P', 0); put(s, sqn('h6'), 'P', 1)
print('   Rey en i6 en jaque:', in_check(s, 1))

# 4) Jaque al final de la cadena (diagrama de 3 saltos)
s = base(bk='j2', wk='a11'); put(s, sqn('f6'), 'CE', 0, pr=True)
for x in ('g7', 'i7', 'j5', 'j3'): put(s, sqn(x), 'P', 1)
cs = chains(s)
for m, n in cs:
    if ncap(m) == 3:
        print('4) cadena:', [name(l) for l, _ in m[3]], 'jaque:', in_check(n, 1))

# 5) Empuje del Guardián
s = base(); put(s, sqn('f6'), 'G', 0); put(s, sqn('f7'), 'P', 1)
pm = [m for m, n in legal(s) if m[0] == 'push']
n = apply(s, pm[0]); print('5) empuje:', pm, '-> G en', name(n.kpos[0]) if False else [name(i) for i, p in enumerate(n.b) if p and p.t != 'K'])

# 6) Enroques desde la posición inicial vaciada
s = initial()
for c in 'bcdeghij': s.b[sqn(c + '1')] = None
print('6) enroques:', [(name(m[1]), name(m[2])) for m, n in legal(s) if m[0] == 'cs'])

# 7) Posición inicial: número de jugadas legales
print('7) jugadas iniciales blancas:', len(legal(initial())))

# 8) Bloqueo de jaque del Guardián (diagrama del reglamento)
s = base(wk='d4', bk='a11'); put(s, sqn('g5'), 'G', 0); put(s, sqn('i9'), 'B', 1)
gm = [name(m[2]) for m, n in legal(s) if m[1] == sqn('g5')]
print('8) Guardián en g5 con el Rey en jaque puede ir a:', gm)
s = base(wk='a1', bk='a11'); put(s, sqn('g5'), 'G', 0)
gm = [name(m[2]) for m, n in legal(s) if m[1] == sqn('g5')]
print('   sin jaque, sus movimientos son:', sorted(gm))

# 9) Bloqueo de saltos del Guardián
s = base(wk='a1', bk='k11'); put(s, sqn('f6'), 'G', 0); put(s, sqn('g7'), 'P', 0)
put(s, sqn('i8'), 'N', 1); s.turn = 1
dest = [name(m[2]) for m, n in legal(s) if m[1] == sqn('i8')]
print('9) Caballo negro en i8 puede ir a g7 (pieza protegida)?', 'g7' in dest, '| destinos:', sorted(dest))
s = base(wk='f1', bk='k11'); put(s, sqn('e2'), 'G', 0); put(s, sqn('g2'), 'G', 0); put(s, sqn('g3'), 'N', 1)
print('   Rey en f1 (diagonal a Guardianes) en jaque por Caballo en g3?', in_check(s, 0))
s = base(wk='f1', bk='k11'); put(s, sqn('g3'), 'N', 1)
print('   sin Guardianes, en jaque?', in_check(s, 0))
s = base(wk='f1', bk='k11'); put(s, sqn('e2'), 'G', 0, pr=True); put(s, sqn('g3'), 'N', 1)
print('   con Guardián promocionado en e2, en jaque?', in_check(s, 0))

# 10) Protección de la cadena por el Guardián
for conG in (False, True):
    s = base(wk='a1', bk='a11'); put(s, sqn('f6'), 'CE', 0, pr=True)
    put(s, sqn('g6'), 'P', 1); put(s, sqn('h6'), 'P', 1)
    if conG: put(s, sqn('i7'), 'G', 1)
    cs = [(m, n) for m, n in legal(s) if m[0] == 'ch' and m[3][0][0] == sqn('i6')]
    print('10) con Guardián' if conG else '10) sin Guardián', [[(name(l), [name(c) for c in caps]) for l, caps in m[3]] for m, n in cs])

# 11) Salto sobre piezas aliadas que continúa la cadena
s = base(wk='a1', bk='a11'); put(s, sqn('f6'), 'CE', 0, pr=True)
put(s, sqn('g6'), 'P', 0); put(s, sqn('h6'), 'P', 0); put(s, sqn('i7'), 'P', 1)
cs = [m for m, n in legal(s) if m[0] == 'ch' and m[3][0][0] == sqn('i6')]
print('11) extendido sobre aliadas:', [[(name(l), [name(c) for c in caps]) for l, caps in m[3]] for m in cs])
s = base(wk='a1', bk='a11'); put(s, sqn('f6'), 'CE', 0, pr=True)
put(s, sqn('g6'), 'P', 0); put(s, sqn('h7'), 'P', 1)
cs = [m for m, n in legal(s) if m[0] == 'ch' and m[3][0][0] == sqn('h6')]
print('    dos casillas sobre aliada:', [[(name(l), [name(c) for c in caps]) for l, caps in m[3]] for m in cs])
plain = [name(m[2]) for m, n in legal(s) if m[0] == 'm' and m[1] == sqn('f6') and m[2] == sqn('h6')]
print('    ¿queda como movimiento simple a h6 (sin continuar)?', plain)

# 12) Guardián creado y captura al paso solo en apertura
s = base(); put(s, sqn('d2'), 'P', 0, dbl=True); s.capP[0] = PEONES_POR_GUARDIAN
n = [n for m, n in legal(s) if m[0] == 'cv'][0]; n.turn = 0
print('12) G creado de peón sin mover avanza a:', sorted(name(m[2]) for m, x in legal(n) if m[1] == sqn('d2') and m[0] == 'm' and m[2] % N == 3))
s = base(); put(s, sqn('e5'), 'G', 1); s.turn = 1
print('    G avanza 2 fuera de apertura, captura al paso posible:', apply(s, ('m', sqn('e5'), sqn('e3'))).ep is not None)
# 13) Enroque impedido por casilla atacada en el camino
s = empty_state(); put(s, sqn('f1'), 'K', 0); put(s, sqn('k1'), 'R', 0); put(s, sqn('a11'), 'K', 1); put(s, sqn('h8'), 'R', 1)
print('13) enroque con h1 atacada:', [m for m, n in legal(s) if m[0] == 'cs'])
# 14) La misma posición del Diagrama 34, con el Rey adversario cerca (4.8.5 g):
#     Catapulta en c7, peones en d7, e7, e8 y e9. Al caer en d9 da jaque al Rey de f11
#     (casilla de captura a distancia dos), así que ese salto es el último y e9 se salva.
for bk in ('f11', 'k11'):
    s = base(bk=bk); put(s, sqn('c7'), 'CE', 0, pr=True)
    for x in ('d7', 'e7', 'e8', 'e9'): put(s, sqn(x), 'P', 1)
    best = max(chains(s), key=lambda x: ncap(x[0]))
    print('14) Rey en %s: max capturas %d %s jaque: %s' % (bk, ncap(best[0]), [name(l) for l, _ in best[0][3]],
                                                          in_check(best[1], 1)))
# 15) Promoción por acumulación (5.4): 4 peones por conversión, 5 Guardianes por promoción
s = base(); put(s, sqn('d2'), 'P', 0); put(s, sqn('e2'), 'G', 0)
for capP, capG in ((3, 4), (4, 5)):
    s.capP[0], s.capG[0] = capP, capG
    print('15) %d peones y %d Guardianes capturados -> cv: %s, gp: %s' % (
        capP, capG, any(m[0] == 'cv' for m, n in legal(s)), any(m[0] == 'gp' for m, n in legal(s))))
