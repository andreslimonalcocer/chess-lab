"""Notación de las jugadas del Ajedrez 11x11 (Apéndice C del reglamento).

La usan el simulador (bitácoras) y el juego de escritorio, para que una partida se anote igual
en los dos lados.
"""
from motor import N, name

SIMBOLO = {'K': 'R', 'Q': 'D', 'R': 'T', 'B': 'A', 'N': 'C', 'CA': 'Az', 'CH': 'Ch', 'CE': 'Ct',
           'G': 'G', 'P': 'P'}


def simbolo(p):
    return SIMBOLO[p.t] + ("'" if p.pr else '')


def desambiguar(frm, otros, ancho, nombre_casilla):
    """Columna, fila o casilla de origen cuando otra pieza igual puede llegar a la misma casilla."""
    if not otros:
        return ''
    if all(o % ancho != frm % ancho for o in otros):
        return nombre_casilla(frm)[0]
    if all(o // ancho != frm // ancho for o in otros):
        return nombre_casilla(frm)[1:]
    return nombre_casilla(frm)


def notacion(st, mv, n, movs):
    """Jugada mv (que lleva de st a n) entre las legales movs, sin el signo de jaque."""
    k, b = mv[0], st.b
    if k == 'cs':
        return '0-0a' if mv[3][0] % N == 0 else '0-0k'
    if k == 'ch':
        return simbolo(b[mv[1]]) + ' ' + name(mv[1]) + ''.join('x' + name(l) for l, _ in mv[3])
    if k == 'pr':
        p = b[mv[1]]
        return SIMBOLO[p.t] + name(mv[1]) + '=' + SIMBOLO[p.t] + "'"
    if k == 'cv':
        return name(mv[1]) + '=G'
    if k == 'gp':
        return 'G' + name(mv[1]) + "=G'"
    frm, to = mv[1], mv[2]
    p = b[frm]
    cap = k == 'ep' or (k == 'm' and b[to] is not None)
    if p.t == 'P' and not p.pr:
        s = (name(frm)[0] + 'x' if cap else '') + name(to)
    else:
        s = simbolo(p)
        otros = [m[1] for m, _ in movs if m[0] in ('m', 'ep', 'push', 'swap') and m[2] == to
                 and m[1] != frm and simbolo(b[m[1]]) == s]
        s += desambiguar(frm, otros, N, name)
        s += ' ' + ('x' if cap else '') + name(to)
    if k == 'ep':
        s += ' a.p.'
    elif not p.pr and n.b[to].pr:
        s += '=' + simbolo(n.b[to])
    return s
