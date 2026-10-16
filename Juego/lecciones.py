"""«Aprende a jugar»: lecciones interactivas del Ajedrez Extendido.

Cada lección explica una pieza o una regla (con el texto del reglamento) y propone ejercicios: una
posición, una instrucción y un objetivo que se comprueba con el motor del juego al hacer la jugada
(mover una pieza, capturar, llegar a una casilla, captura en cadena, extensión, enroque o mate). Solo
juegan las blancas: el bando negro no responde.
"""
import re

import motor as M

SIMBOLOS = {'R': 'K', 'D': 'Q', 'T': 'R', 'A': 'B', 'C': 'N', 'Az': 'CA', 'Ch': 'CH', 'Ct': 'CE', 'G': 'G',
            'P': 'P'}


def posicion(texto):
    """'Rf1 Ta1 n:Rf11 Ct+f6' -> [[casilla, tipo, color, promocionada]] (n: negras, + promocionada)."""
    piezas = []
    for parte in texto.split():
        color = 0
        if parte.startswith('n:'):
            color, parte = 1, parte[2:]
        # 'Ch' es el Canciller solo si sigue una casilla: 'Ch7' es un Caballo en h7
        k = 2 if parte[:2] in ('Az', 'Ch', 'Ct') and re.fullmatch(r'\+?[a-k]\d{1,2}', parte[2:]) else 1
        sim, resto = parte[:k], parte[k:]
        pr = resto.startswith('+')
        piezas.append([M.sqn(resto.lstrip('+')), SIMBOLOS[sim], color, pr])
    return piezas


def tarea(texto, piezas, objetivo, **extra):
    d = {'texto': texto, 'piezas': posicion(piezas), 'objetivo': objetivo}
    d.update(extra)
    return d


LECCIONES = [
    {'id': 'rey', 'titulo': 'El Rey', 'regla': 'El Rey', 'tareas': [
        tarea('Mueve tu Rey a cualquier casilla vecina.', 'Rf4 n:Rf11', {'tipo': 'mover', 'de': 'f4'}),
        tarea('Captura el peón que está junto a tu Rey.', 'Rf4 n:Pg4 n:Rf11', {'tipo': 'capturar', 'en': 'g4'}),
        tarea('Enroca: selecciona el Rey y elige el enroque hacia la columna a o hacia la k (el Rey y la '
              'Torre no deben haberse movido).', 'Rf1 Ta1 Tk1 n:Rf11', {'tipo': 'enroque'}),
    ]},
    {'id': 'torre', 'titulo': 'La Torre', 'regla': 'La Torre', 'tareas': [
        tarea('La Torre se mueve en recto (columnas y filas), sin límite. Captura el Caballo de f10.',
              'Rb1 Tf2 n:Cf10 n:Rk11', {'tipo': 'capturar', 'en': 'f10'}),
    ]},
    {'id': 'alfil', 'titulo': 'El Alfil', 'regla': 'El Alfil', 'tareas': [
        tarea('El Alfil se mueve en diagonal, sin límite. Captura la Torre de j11.', 'Rf1 Ab3 n:Tj11 n:Ra10',
              {'tipo': 'capturar', 'en': 'j11'}),
    ]},
    {'id': 'dama', 'titulo': 'La Dama', 'regla': 'La Dama', 'tareas': [
        tarea('La Dama combina la Torre y el Alfil: se mueve sin límite en recto y en diagonal. Captura en '
              'diagonal, como el Alfil, el peón de b2 (el peón de j10 protege a su Rey).',
              'Rf1 Df6 n:Pb2 n:Pj10 n:Rk11', {'tipo': 'capturar', 'en': 'b2'}),
        tarea('Ahora captura en recto, como la Torre, la Torre de h4.', 'Rf1 Dc4 n:Th4 n:Rk11',
              {'tipo': 'capturar', 'en': 'h4'}),
    ]},
    {'id': 'caballo', 'titulo': 'El Caballo', 'regla': 'El Caballo', 'tareas': [
        tarea('Salto tradicional (dos y una): captura el peón de g7.', 'Rf1 Ce6 n:Pg7 n:Rk11',
              {'tipo': 'capturar', 'en': 'g7'}),
        tarea('Salto largo (tres y una), propio del Ajedrez Extendido: captura el peón de f9.', 'Rf1 Ce6 n:Pf9 n:Rk11',
              {'tipo': 'capturar', 'en': 'f9'}),
    ]},
    {'id': 'arzobispo', 'titulo': 'El Arzobispo', 'regla': 'El Arzobispo', 'tareas': [
        tarea('El Arzobispo salta como Caballo: captura el peón de g8.', 'Rf1 Azf6 n:Pg8 n:Rj11',
              {'tipo': 'capturar', 'en': 'g8'}),
        tarea('Y se mueve como Alfil, hasta cinco casillas: captura el Caballo de j10.', 'Rf1 Aze5 n:Cj10 n:Ra11',
              {'tipo': 'capturar', 'en': 'j10'}),
    ]},
    {'id': 'canciller', 'titulo': 'El Canciller', 'regla': 'El Canciller', 'tareas': [
        tarea('El Canciller salta como Caballo: captura el peón de e8.', 'Rf1 Chf6 n:Pe8 n:Rk11',
              {'tipo': 'capturar', 'en': 'e8'}),
        tarea('Y se mueve como Torre, hasta cinco casillas: captura el Alfil de a6.', 'Rk1 Chf6 n:Aa6 n:Rk11',
              {'tipo': 'capturar', 'en': 'a6'}),
    ]},
    {'id': 'catapulta', 'titulo': 'La Catapulta', 'regla': 'La Catapulta', 'tareas': [
        tarea('La Catapulta se mueve a cualquier casilla a distancia uno o dos, aunque haya piezas en medio. '
              'Muévela.', 'Rf1 Ctf6 n:Rk11', {'tipo': 'mover', 'de': 'f6'}),
        tarea('Solo captura a distancia exactamente dos, nunca en las casillas vecinas. Captura la Torre de h8 '
              '(el peón de g7, vecino, no se puede capturar).', 'Rf1 Ctf6 n:Pg7 n:Th8 n:Rk11',
              {'tipo': 'capturar', 'en': 'h8'}),
        tarea('Salto extendido: con piezas en g6 y h6 seguidas, la Catapulta salta a la primera casilla vacía '
              'detrás. Llévala a i6.', 'Rf1 Ctf6 Pg6 Ph6 n:Rk11', {'tipo': 'casilla', 'a': 'i6'}),
    ]},
    {'id': 'catapulta_prom', 'titulo': 'La Catapulta extendida', 'regla': 'Catapulta extendida', 'tareas': [
        tarea('Captura simple: en las ocho casillas a distancia dos que no están en línea recta (el patrón del '
              'Caballo) captura como siempre. Captura el Caballo de h7.', 'Rf1 Ct+f6 n:Ch7 n:Rk11',
              {'tipo': 'capturar', 'en': 'h7'}),
        tarea('Captura doble: el salto recto de dos casillas captura la pieza del medio y la de llegada. Captura '
              'los peones de g6 y h6 de un solo salto.', 'Rf1 Ct+f6 n:Pg6 n:Ph6 n:Rk11',
              {'tipo': 'cadena', 'minimo': 2}),
        tarea('Captura en cadena: tras el primer salto sigue saltando sobre piezas adversarias mientras pueda. '
              'Captura los cuatro peones en una sola jugada (f6 → i6 → g8 → i8).',
              'Rf1 Ct+f6 n:Pg6 n:Ph6 n:Ph7 n:Ph8 n:Ra11', {'tipo': 'cadena', 'minimo': 4}),
        tarea('Las piezas vecinas solo se capturan con una cadena: salta sobre el Caballo de g6 hasta h6 y sigue '
              'sobre el peón de h7 hasta h8.', 'Rf1 Ct+f6 n:Cg6 n:Ph7 n:Ra11', {'tipo': 'cadena', 'minimo': 2}),
    ]},
    {'id': 'peon', 'titulo': 'El Peón', 'regla': 'El Peón', 'tareas': [
        tarea('Desde su fila inicial el peón puede avanzar dos casillas. Avanza el peón de c2 hasta c4.',
              'Rf1 Pc2 n:Rf11', {'tipo': 'casilla', 'a': 'c4'}),
        tarea('Captura en diagonal hacia adelante: captura el Caballo de d5.', 'Rf1 Pc4 n:Cd5 n:Rk11',
              {'tipo': 'capturar', 'en': 'd5'}),
        tarea('Al llegar a la última fila se extiende solo: lleva el peón a b11.', 'Rf1 Pb10 n:Rk9',
              {'tipo': 'casilla', 'a': 'b11'}),
    ]},
    {'id': 'guardian', 'titulo': 'El Guardián', 'regla': 'El Guardián', 'tareas': [
        tarea('En su primer avance, el Guardián inicial puede avanzar hasta tres casillas. Llévalo de f2 a f5.',
              'Rk1 Gf2 n:Rk11', {'tipo': 'casilla', 'a': 'f5'}),
        tarea('Captura en sus cuatro diagonales vecinas, también hacia atrás: captura el Caballo de e5.',
              'Rk1 Gf6 n:Ce5 n:Rk11', {'tipo': 'capturar', 'en': 'e5'}),
        tarea('Empuje: si delante tiene un peón adversario, puede empujarlo una casilla hacia atrás y ocupar su '
              'lugar. Empuja el peón de f7.', 'Rk1 Gf6 n:Pf7 n:Rk11', {'tipo': 'casilla', 'a': 'f7'}),
        tarea('Bloqueo de jaque: sin capturar, el Guardián puede ir a una de sus casillas diagonales solo si así '
              'tapa un jaque a su Rey. El Alfil de i9 da jaque: bloquéalo con el Guardián.',
              'Rd4 Gg5 n:Ai9 n:Rk11', {'tipo': 'casilla', 'a': 'f6'}, jaque=True),
        tarea('Bloqueo de saltos: ninguna pieza adversaria puede caer de un salto en las cuatro casillas '
              'diagonales del Guardián. El Caballo de i8 amenaza tu Torre de g7: protégela con el Guardián.',
              'Rk1 Tg7 Gf5 n:Ci8 n:Ra11', {'tipo': 'proteger', 'en': 'g7'}),
    ]},
    {'id': 'al_paso', 'titulo': 'Captura al paso', 'regla': 'Captura al paso', 'tareas': [
        tarea('El peón negro acaba de avanzar dos casillas, de g10 a g8, y quedó junto a tu peón. Solo en esta '
              'jugada puedes capturarlo al paso: mueve tu peón a g9.', 'Rf1 Pf8 n:Pg10 n:Rk11',
              {'tipo': 'alpaso', 'a': 'g9'}, previa=('g10', 'g8')),
        tarea('También vale para el Guardián: el Guardián negro avanzó tres casillas, de e10 a e7. Captúralo al '
              'paso con tu Guardián, moviéndolo a e8.', 'Rk1 Gd7 n:Ge10 n:Ra11',
              {'tipo': 'alpaso', 'a': 'e8'}, previa=('e10', 'e7')),
    ]},
    {'id': 'promocion', 'titulo': 'Extensión por captura', 'regla': 'Extensión', 'tareas': [
        tarea('Ya capturaste las dos Torres adversarias: una de tus Torres puede extenderse (cuesta el turno). '
              'Selecciona la Torre y pulsa el botón de extensión del panel.', 'Rf1 Tc3 n:Rk11',
              {'tipo': 'promocion'}, capturas={'R': 2}),
        tarea('Por cada cuatro peones adversarios capturados, un peón propio puede convertirse en Guardián. '
              'Selecciona el peón y conviértelo.', 'Rf1 Pc4 n:Rk11', {'tipo': 'convertir'}, peones=4),
    ]},
    {'id': 'promocionadas1', 'titulo': 'Extendidas: Dama, Torre, Alfil y Caballo', 'regla': 'Extensión',
     'tareas': [
        tarea('La Dama extendida añade el salto tradicional del Caballo. Captura el Caballo de g8 saltando.',
              'Rf1 D+f6 n:Cg8 n:Pj10 n:Rk11', {'tipo': 'capturar', 'en': 'g8'}),
        tarea('La Torre extendida también se desplaza una, dos o tres casillas en diagonal, saltando lo que haya '
              'en medio. Captura el Caballo de h8 saltando tu Caballo de g7.', 'Rf1 T+f6 Cg7 n:Ch8 n:Ra11',
              {'tipo': 'capturar', 'en': 'h8'}),
        tarea('El Alfil extendido también se desplaza una, dos o tres casillas en recto, saltando. Captura el '
              'Caballo de f8 saltando tu peón de f7.', 'Rb1 A+f6 Pf7 n:Cf8 n:Rj11',
              {'tipo': 'capturar', 'en': 'f8'}),
        tarea('El Caballo extendido añade los saltos de tres y dos. Captura la Torre de i8.',
              'Rf1 C+f6 n:Ti8 n:Ra11', {'tipo': 'capturar', 'en': 'i8'}),
    ]},
    {'id': 'promocionadas2', 'titulo': 'Extendidas: Arzobispo, Canciller, Peón y Guardián', 'regla': 'Extensión',
     'tareas': [
        tarea('El Arzobispo extendido se mueve como Alfil sin límite de distancia. Captura la Torre de j10, '
              'a siete casillas.', 'Rf1 Az+c3 n:Tj10 n:Ra11', {'tipo': 'capturar', 'en': 'j10'}),
        tarea('El Canciller extendido se mueve como Torre sin límite. Captura la Torre de j5, a nueve casillas.',
              'Rf1 Ch+a5 n:Tj5 n:Rk11', {'tipo': 'capturar', 'en': 'j5'}),
        tarea('El peón extendido se mueve y captura una casilla en cualquier dirección, como el Rey (también '
              'hacia atrás). Captura el Caballo de g5.', 'Rb1 P+f6 n:Cg5 n:Rk11', {'tipo': 'capturar', 'en': 'g5'}),
        tarea('El Guardián extendido se mueve y captura hasta dos casillas en cualquier dirección recta. '
              'Captura el Caballo de h8.', 'Rb1 G+f6 n:Ch8 n:Ra11', {'tipo': 'capturar', 'en': 'h8'}),
    ]},
    {'id': 'mate', 'titulo': 'Jaque mate', 'regla': 'Fin de la partida', 'tareas': [
        tarea('El objetivo de la partida es el jaque mate: el Rey adversario está atacado y no tiene escapatoria. '
              'Da mate en una jugada con la Dama.', 'Rf9 Dc1 n:Rf11', {'tipo': 'mate'}),
        tarea('Mate con la Torre en una jugada (el Rey blanco cubre la salida).', 'Rf9 Tk2 n:Rf11', {'tipo': 'mate'}),
    ]},
]


def _previa(v, t):
    """(posición antes, índice, jugada, posición después) de la jugada negra que precede al ejercicio."""
    st = v.construir(t['piezas'], 1)
    for k, (mv, n) in enumerate(v.legal(st)):
        if mv[1] == M.sqn(t['previa'][0]) and v.destino(mv) == M.sqn(t['previa'][1]):
            return st, k, mv, n
    raise ValueError('la jugada previa %s-%s no es legal' % t['previa'])


def estado(v, t):
    """La posición de una tarea (con los derechos de extensión que pida y la jugada negra previa)."""
    if t.get('previa'):
        st = _previa(v, t)[3]
    else:
        st = v.construir(t['piezas'], t.get('turno', 0))
    for tipo, n in t.get('capturas', {}).items():
        st.capT[0][tipo] = n
    if t.get('peones'):
        st.capP[0] = t['peones']
    return st


def previa(v, t):
    """(posición antes, índice de la jugada, jugada) si el ejercicio parte de una jugada negra, o None."""
    if not t.get('previa'):
        return None
    st, k, mv, _ = _previa(v, t)
    return st, k, mv


def cumple(v, st, mv, n, objetivo):
    """¿La jugada mv (de st a n) cumple el objetivo?"""
    tipo = objetivo['tipo']
    destino = v.destino(mv)
    if tipo == 'mover':
        return mv[1] == M.sqn(objetivo['de']) and destino is not None
    if tipo == 'capturar':
        return v.es_captura(st, mv) and (destino == M.sqn(objetivo['en']) if 'en' in objetivo else True)
    if tipo == 'casilla':
        return destino == M.sqn(objetivo['a'])
    if tipo == 'cadena':
        if mv[0] != 'ch':
            return False
        capturadas = sum(1 for sq in range(121) if st.b[sq] is not None and st.b[sq].c == 1 and n.b[sq] is None)
        return capturadas >= objetivo.get('minimo', 2)
    if tipo == 'alpaso':
        return mv[0] == 'ep' and destino == M.sqn(objetivo['a'])
    if tipo == 'proteger':  # la pieza sigue ahí y ninguna jugada negra puede capturarla
        sq = M.sqn(objetivo['en'])
        if n.b[sq] is None or n.b[sq].c != 0:
            return False
        return not any(r.b[sq] is None or r.b[sq].c != 0 for _, r in v.legal(n))
    if tipo == 'enroque':
        return mv[0] == 'cs'
    if tipo == 'promocion':
        return mv[0] == 'pr'
    if tipo == 'convertir':
        return mv[0] == 'cv'
    if tipo == 'mate':
        return v.en_jaque(n, n.turn) and not v.legal(n)
    return False


def casillas_objetivo(t):
    o = t['objetivo']
    for k in ('en', 'a', 'de'):  # la casilla del objetivo
        if k in o:
            return {M.sqn(o[k])}
    return set()


def comprobar(v):
    """Cada tarea debe ser una posición posible (el Rey negro no empieza en jaque; el blanco solo si el ejercicio
    lo pide) y tener al menos una jugada que cumpla su objetivo. Devuelve los problemas (para las pruebas)."""
    malas = []
    for lec in LECCIONES:
        for k, t in enumerate(lec['tareas']):
            nombre = '%s, tarea %d' % (lec['titulo'], k + 1)
            try:
                st = estado(v, t)
            except ValueError as e:
                malas.append('%s: %s' % (nombre, e))
                continue
            if v.en_jaque(st, 1):
                malas.append(nombre + ': el Rey negro empieza en jaque')
            if v.en_jaque(st, 0) != bool(t.get('jaque')):
                malas.append(nombre + ': el Rey blanco ' + ('no ' if t.get('jaque') else '') + 'está en jaque')
            buenas = [mv for mv, n in v.legal(st) if cumple(v, st, mv, n, t['objetivo'])]
            if not buenas:
                malas.append(nombre + ': ninguna jugada cumple el objetivo')
    return malas
