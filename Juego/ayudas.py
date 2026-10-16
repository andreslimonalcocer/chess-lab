"""Ayudas durante la partida: piezas colgadas o amenazadas y amenaza de mate.

Funciona con cualquier variante (Ajedrez Extendido o genérica) usando solo sus jugadas legales: se le da el turno al
rival (como si pasaras) y se mira qué capturas tendría y si podrías recapturar en esa casilla.
"""
import motor as M

REY = 100.0


def valor(v, st, sq):
    """Valor en peones de la pieza de sq (el Rey vale mucho: nunca se ofrece)."""
    t, c, pr = v.pieza(st, sq)
    if t == v.rey:
        return REY
    if v.id == 'extendido':
        return M.VAL[t][1 if pr else 0]
    return float(v.m.valor.get(t, 1.0))


def perdidas(v, antes, despues, color):
    """Casillas en las que había una pieza de color que ya no está (también capturas en cadena o al paso)."""
    out = []
    for sq in range(v.ancho * v.alto):
        p = v.pieza(antes, sq)
        if p is not None and p[1] == color:
            q = v.pieza(despues, sq)
            if q is None or q[1] != color:
                out.append(sq)
    return out


def amenazas(v, st, color):
    """Lo que el rival podría hacer si fuera su turno: [(casilla, peones que pierdes, descripción)], de la
    peor a la menos grave, y si tiene mate en una ('mate', descripción). Vacío si estás en jaque (eso ya se
    ve en el tablero)."""
    if v.en_jaque(st, color):
        return []
    s = st.copy()
    s.turn = 1 - color
    s.ep = None
    try:
        movs = v.legal(s)
    except Exception:
        return []
    peor = {}
    for mv, n in movs:
        if v.en_jaque(n, color) and not v.legal(n):
            return [('mate', 0, v.descripcion(s, mv))]
        if not v.es_captura(s, mv):
            continue
        destino = v.destino(mv)
        atacante = valor(v, s, mv[1])
        respuestas = v.legal(n)
        for sq in perdidas(v, s, n, color):
            pierdes = valor(v, s, sq)
            recaptura = destino is not None and any(
                v.destino(m2) == destino and v.es_captura(n, m2) for m2, _ in respuestas)
            neto = pierdes - atacante if recaptura else pierdes
            if neto >= 0.75 and neto > peor.get(sq, (0,))[0]:
                peor[sq] = (neto, v.descripcion(s, mv))
    return sorted(((sq, neto, d) for sq, (neto, d) in peor.items()), key=lambda x: -x[1])


def texto(v, st, color, lista, maximo=2):
    """Aviso corto para el panel."""
    if not lista:
        return ''
    if lista[0][0] == 'mate':
        return '⚠ Cuidado: el rival amenaza mate (%s).' % lista[0][2].lower()
    partes = []
    for sq, neto, _ in lista[:maximo]:
        t, _, pr = v.pieza(st, sq)
        partes.append('%s en %s' % (v.nombre_pieza(t, pr), v.nombre_casilla(sq)))
    return '⚠ Atención: %s %s en peligro.' % (' y '.join(partes), 'está' if len(partes) == 1 else 'están')
