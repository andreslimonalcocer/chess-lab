"""Sección de reglas de cada variante: texto, diagramas y ventana para consultarlas.

Los diagramas de movimiento de cada pieza se calculan con el propio motor (la pieza en el
centro del tablero vacío), así que siempre coinciden con las reglas reales, también para las
piezas creadas en el Laboratorio. El Ajedrez Extendido incluye además el texto de su reglamento
oficial y los ejemplos principales del PDF.
"""
import copy, os, re, subprocess
import tkinter as tk
from tkinter import ttk

import motor as M
import generico as G
import variantes as V
from interfaz import FONDO, BORDE, ORO, TEXTO, TEXTO_SUAVE, colores_tema, mezcla

# Convenciones de los diagramas (como en el reglamento): tipo -> (color, significado)
MARCAS = {
    'movcap': ('#4E9A3A', 'Movimiento y captura'),
    'mov': ('#4A86C5', 'Movimiento sin capturar'),
    'esp': ('#9C7DC9', 'Solo en condiciones especiales'),
    'cap': ('#D9534F', 'Captura'),
    'prom': ('#E8B923', 'Añadida por la extensión'),
    'cadena': ('#E8873A', 'Solo con la cadena de saltos'),
    'jaque': ('#A01010', 'Rey en jaque o casilla atacada'),
    'bloq': ('#8C8C8C', 'Bloqueada por un Guardián'),
}
PDF = os.path.join(V.RAIZ, 'Reglas', 'Ajedrez Extendido - Reglamento oficial.pdf')


def sq11(nombre):
    return M.sqn(nombre)


class Diagrama:
    def __init__(self, ancho, alto, piezas=(), marcas=None, numeros=None, flechas=(), texto=''):
        self.ancho, self.alto = ancho, alto
        self.piezas = list(piezas)          # (casilla, ruta de la imagen)
        self.marcas = dict(marcas or {})    # casilla -> tipo de marca
        self.numeros = dict(numeros or {})  # casilla -> número (orden de los saltos, distancias)
        self.flechas = list(flechas)        # [(de, a), ...]
        self.texto = texto


# ====================================================================== patrones de movimiento
def clasificar(mov, cap, cadena=(), especiales=()):
    marcas = {}
    for s in set(mov) | set(cap):
        marcas[s] = 'movcap' if (s in mov and s in cap) else ('mov' if s in mov else 'cap')
    for s in cadena:
        if marcas.get(s) in (None, 'mov'):
            marcas[s] = 'cadena'  # se puede mover sin capturar, pero solo captura con la cadena
    for s in especiales:
        marcas[s] = 'esp'
    return marcas


def patron_extendido(t, pr, sq):
    """Casillas de movimiento, de captura y de cadena de una pieza del Ajedrez Extendido sola en el tablero."""
    def estado(rival=None, reyes=False):
        st = M.empty_state()
        M.put(st, sq, t, 0, pr=pr, moved=True)
        if rival is not None:
            M.put(st, rival, 'P', 1, moved=True)
        if reyes:  # la cadena comprueba el jaque: Reyes lejos de las líneas de la pieza
            M.put(st, M.sqn('a2'), 'K', 0)
            M.put(st, M.sqn('k9'), 'K', 1)
        return st
    mov = {m[2] for m in M.pseudo(estado()) if m[0] == 'm'}
    cap, cadena = set(), set()
    for s in range(M.N * M.N):
        if s == sq or (t == 'CE' and pr and s in (M.sqn('a2'), M.sqn('k9'))):
            continue
        if any(m[0] == 'm' and m[2] == s for m in M.pseudo(estado(s))):
            cap.add(s)
        if t == 'CE' and pr:
            st = estado(s, reyes=True)
            if any(s in caps for mv, _ in M.centinela_chains(st, sq) for _, caps in mv[3]):
                cadena.add(s)
    esp = []
    if t == 'P' and not pr:
        esp = [sq + 2 * M.N]
    if t == 'G' and not pr:
        esp = [sq + 3 * M.N]
    return mov, cap, cadena - cap, esp


def patron_generico(motor, t, sq):
    W = motor.W

    def estado(rival=None):
        st = motor.construir([[sq, t, 0]], 0)
        st.b[sq] = motor.pieza(t, 0, True, None if t in motor.peones else sq // W)
        if rival is not None:
            otro = next((x for x in motor.defs if x not in motor.real and x not in motor.peones), t)
            st.b[rival] = motor.pieza(otro, 1)
        st.rey = [None, None]
        return st
    mov = {m[2] for m in motor.pseudo(estado()) if m[0] in ('m', 'ch')}
    cap = set()
    for s in range(motor.W * motor.H):
        if s != sq and any(m[0] in ('m', 'ch') and m[2] == s and s in motor.capturadas(estado(s), m)
                           for m in motor.pseudo(estado(s))):
            cap.add(s)
    esp = []
    if t in motor.peones and motor.reglas['doble_paso'] and sq + 2 * W < W * motor.H:
        esp = [sq + 2 * W]
    return mov, cap, (), esp


def diagrama_pieza(v, t, pr=False, sq=None, base=None, texto=''):
    """Diagrama del movimiento de una pieza; con 'base', marca en dorado lo que añade la extensión."""
    W, H = v.ancho, v.alto
    if sq is None:
        sq = ((H - 1) // 2) * W + (W - 1) // 2
    if isinstance(v, V.Extendido):
        mov, cap, cadena, esp = patron_extendido(t, pr, sq)
    else:
        mov, cap, cadena, esp = patron_generico(v.m, t, sq)
    marcas = clasificar(mov, cap, cadena, esp)
    if base is not None:
        for s in marcas:
            if s not in base and marcas[s] in ('movcap', 'mov', 'cap'):
                marcas[s] = 'prom'
    return Diagrama(W, H, [(sq, v.imagen(t, 0, pr))], marcas, texto=texto), marcas


def par_promocion(v, t, nombre, sq=None, pie=''):
    """Diagramas de la forma base y de la extendida (Ajedrez Extendido)."""
    d1, base = diagrama_pieza(v, t, False, sq, texto=nombre + pie)
    d2, _ = diagrama_pieza(v, t, True, sq, base=base,
                           texto=v.nombre_pieza(t, True)[0].upper() + v.nombre_pieza(t, True)[1:] + pie)
    return d1, d2


# ====================================================================== contenido: Ajedrez Extendido
def _e(piezas, marcas=None, numeros=None, flechas=(), texto=''):
    """Diagrama de ejemplo del Ajedrez Extendido. piezas: 'Ct+f6', 'p:g6' (negra), ...; marcas: {'g6': 'cap'}."""
    v = V.Extendido()
    simbolos = {'R': 'K', 'D': 'Q', 'T': 'R', 'A': 'B', 'C': 'N', 'Az': 'CA', 'Ch': 'CH', 'Ct': 'CE',
                'G': 'G', 'P': 'P'}
    lista = []
    for p in piezas.split():
        color = 1 if p.startswith('n:') else 0
        p = p[2:] if p[1] == ':' else p
        pr = '+' in p
        simbolo, casilla = re.match(r'(.+?)([a-k]\d{1,2})$', p.replace('+', '')).groups()
        lista.append((sq11(casilla), v.imagen(simbolos[simbolo], color, pr)))
    return Diagrama(11, 11, lista, {sq11(k): t for k, t in (marcas or {}).items()},
                    {sq11(k): n for k, n in (numeros or {}).items()},
                    [(sq11(a), sq11(b)) for a, b in flechas], texto)


def contenido_extendido():
    v = V.Extendido()
    ini = v.inicial()
    pos0 = Diagrama(11, 11, [(sq, v.imagen(*v.pieza(ini, sq))) for sq in range(121) if v.pieza(ini, sq)],
                    texto='Diagrama 1. Posición inicial.')
    f6 = sq11('f6')
    dist = Diagrama(11, 11, [(f6, v.imagen('CE', 0, False))],
                    numeros={s: max(abs(s % 11 - 5), abs(s // 11 - 5)) for s in range(121)
                             if 0 < max(abs(s % 11 - 5), abs(s // 11 - 5)) <= 3},
                    texto='Distancia desde f6: cada casilla indica a qué distancia está (uno, dos o tres).')
    rey, _ = diagrama_pieza(v, 'K', texto='Movimiento y captura del Rey.')
    secciones = [
        ('Introducción', [
            ('p', 'El Ajedrez Extendido es una variante de tablero ampliado (11 × 11) de la familia iniciada por José Raúl '
                  'Capablanca en la década de 1920 y continuada por el Ajedrez Gótico de Ed Trice y el Grand Chess '
                  'de Christian Freeling. Conserva la estructura del ajedrez tradicional e incorpora el Arzobispo y '
                  'el Canciller de Capablanca, con alcance limitado; dos piezas propias, la Catapulta y el Guardián; '
                  'un Caballo de alcance ampliado, y un sistema de extensiones en el que cada pieza, salvo el Rey, '
                  'dispone de una forma mejorada.'),
            ('p', 'Cláusula general. En todo lo que este reglamento no disponga expresamente, rigen las reglas del '
                  'ajedrez tradicional (Leyes del Ajedrez de la FIDE).'),
            ('h', 'Artículo 1. Naturaleza y objetivo'),
            ('lista', ['1.1 La partida se juega entre dos jugadores sobre un tablero de 11 × 11 casillas. '
                       'Las blancas hacen la primera jugada.',
                       '1.2 El objetivo es dar jaque mate al Rey adversario: atacarlo de modo que el adversario no '
                       'disponga de ninguna jugada legal para evitar su captura.',
                       '1.3 El Rey está «en jaque» cuando lo ataca una o más piezas adversarias. Ningún jugador '
                       'puede hacer una jugada que deje a su propio Rey en jaque.',
                       '1.4 Cuando ninguno puede dar mate, la partida se resuelve conforme al Artículo 7.']),
            ('h', 'Convenciones de los diagramas'),
            ('p', 'La pieza cuyo movimiento se describe aparece en blanco en el centro del tablero (f6). En los '
                  'ejemplos, las piezas blancas son propias y las negras, adversarias. Los números indican el '
                  'orden de los saltos. Las formas extendidas se distinguen por la base y la estrella doradas.'),
            ('leyenda', list(MARCAS)),
        ]),
        ('Tablero y posición inicial', [
            ('lista', ['2.1 El tablero tiene 121 casillas en 11 columnas (a–k) y 11 filas (1–11), contadas desde '
                       'las blancas.',
                       '2.2 Por tener un número impar de columnas, las cuatro esquinas son del mismo color; el '
                       'tablero se coloca con las esquinas claras.',
                       '2.3 Cada jugador tiene 22 piezas: Rey, Dama, dos Torres, dos Alfiles, dos Caballos, '
                       'Arzobispo, Canciller, Catapulta, tres Guardianes y ocho peones.',
                       '2.4 Primera fila de las blancas, de a a k: Torre, Caballo, Alfil, Arzobispo, Dama, Rey, '
                       'Catapulta, Canciller, Caballo, Alfil y Torre. Peones en a2–d2 y h2–k2; Guardianes en e2, '
                       'f2 y g2.',
                       '2.5 Las negras ocupan las filas 11 y 10 en la misma disposición.',
                       '2.6 Ningún peón ni Guardián queda indefenso al inicio (Apéndice B) y los dos Alfiles de '
                       'cada jugador ocupan casillas de distinto color.']),
            ('diagramas', [pos0]),
        ]),
        ('Movimiento en general', [
            ('lista', ['3.1 Ninguna pieza puede moverse a una casilla ocupada por una pieza propia, salvo el '
                       'intercambio del Guardián (4.10.3).',
                       '3.2 Al moverse a una casilla con una pieza adversaria, la captura. Excepciones: el empuje '
                       'del Guardián (4.10.4) y las capturas múltiples de la Catapulta extendida (4.8.5).',
                       '3.3 Direcciones rectas: las cuatro ortogonales y las cuatro diagonales. La distancia entre '
                       'dos casillas es el mayor entre la diferencia de columnas y la de filas (los pasos que '
                       'daría un Rey).',
                       '3.4 Las piezas de desplazamiento (Dama, Torre, Alfil y esos componentes del Canciller y '
                       'del Arzobispo) no pueden atravesar casillas ocupadas.',
                       '3.5 Las piezas de salto (Caballo, Catapulta, el componente de Caballo del Arzobispo, del '
                       'Canciller y de la Dama extendida, y los saltos de la Torre y el Alfil extendidos) '
                       'llegan aunque haya piezas en medio, salvo lo dispuesto para la Catapulta (4.8.6) y el '
                       'bloqueo de saltos del Guardián (4.10.7).',
                       '3.6 Una pieza ataca una casilla cuando podría capturar en ella.',
                       '3.7 Toda pieza, excepto el Rey, tiene una forma extendida (Artículo 5).']),
            ('diagramas', [dist]),
        ]),
        ('El Rey', [
            ('lista', ['4.1.1 Se mueve a cualquier casilla adyacente que no esté atacada, y captura igual.',
                       '4.1.2 Enroque: el Rey se desplaza cuatro casillas hacia la Torre y la Torre se coloca en la '
                       'casilla contigua que el Rey acaba de cruzar. Hacia la columna a: Rey de f1 a b1, Torre de a1 '
                       'a c1. Hacia la columna k: Rey de f1 a j1, Torre de k1 a i1. Como el Rey está en la columna '
                       'central, ambos enroques recorren la misma distancia: se nombran por el flanco, no por '
                       'corto o largo.',
                       '4.1.3 No se puede enrocar si el Rey o la Torre ya se movieron, si hay piezas entre ambos, si '
                       'el Rey está en jaque, si debe cruzar una casilla atacada o si quedaría en jaque.',
                       '4.1.4 El Rey no puede dar jaque al Rey adversario.',
                       '4.1.5 El Rey no tiene forma extendida.']),
            ('diagramas', [rey,
                           _e('Rf1 Ta1 Tk1', {'b1': 'mov', 'j1': 'mov'},
                              texto='Enroque: el Rey en f1 llega a b1 o a j1.')]),
            ('diagramas', [_e('Rb1 Tc1', texto='Tras el enroque hacia la columna a: Rey en b1, Torre en c1.'),
                           _e('Rf1 Tk1 n:Th8', {'h1': 'jaque'}, flechas=[('h8', 'h1')],
                              texto='Enroque impedido: la Torre de h8 ataca h1, que el Rey tendría que cruzar.')]),
        ]),
        ('La Dama', [
            ('lista', ['4.2.1 Se mueve por su columna, su fila o sus diagonales, sin límite, y captura igual.',
                       '4.2.2 Forma extendida: añade el salto tradicional del Caballo (5.3).']),
            ('diagramas', list(par_promocion(v, 'Q', 'Dama'))),
        ]),
        ('La Torre', [
            ('lista', ['4.3.1 Se mueve por su columna o su fila, sin límite, y captura igual.',
                       '4.3.2 Forma extendida: además puede desplazarse una, dos o tres casillas en diagonal, '
                       'saltando las piezas intermedias, y capturar en esas casillas. Solo cuenta como salto si '
                       'pasa por encima de alguna pieza (4.10.7).']),
            ('diagramas', list(par_promocion(v, 'R', 'Torre'))),
            ('diagramas', [_e('T+f6 n:Ph8 n:Ri9', {'i9': 'jaque'}, flechas=[('f6', 'i9')],
                              texto='Jaque por salto: aunque el peón de h8 se interpone, la Torre extendida '
                                    'salta tres casillas y da jaque al Rey en i9.')]),
        ]),
        ('El Alfil', [
            ('lista', ['4.4.1 Se mueve por sus diagonales, sin límite, y captura igual. Siempre en casillas del '
                       'mismo color.',
                       '4.4.2 Forma extendida: además puede desplazarse una, dos o tres casillas en dirección '
                       'ortogonal, saltando, y capturar en esas casillas; deja de estar limitado a un color.']),
            ('diagramas', list(par_promocion(v, 'B', 'Alfil'))),
            ('diagramas', [_e('A+f6 n:Pf7 n:Rf9', {'f9': 'jaque'}, flechas=[('f6', 'f9')],
                              texto='Jaque por salto: el Alfil extendido salta el peón de f7 y da jaque al Rey '
                                    'en f9.')]),
        ]),
        ('El Caballo', [
            ('lista', ['4.5.1 Salta dos casillas en una dirección ortogonal y una en la perpendicular (salto '
                       'tradicional), o tres y una (salto largo): 16 destinos. Captura igual.',
                       '4.5.2 El componente de Caballo del Arzobispo, del Canciller y de la Dama extendida es '
                       'siempre el salto tradicional.',
                       '4.5.3 Forma extendida: añade los saltos de tres y dos, hasta 24 casillas. No incluye los '
                       'de dos y dos, que coinciden con las diagonales.']),
            ('diagramas', list(par_promocion(v, 'N', 'Caballo'))),
        ]),
        ('El Arzobispo', [
            ('lista', ['4.6.1 Combina el salto tradicional del Caballo con el movimiento del Alfil limitado a '
                       'cinco casillas, y captura igual.',
                       '4.6.2 Forma extendida: su movimiento de Alfil deja de estar limitado.']),
            ('p', 'Desde el centro, el límite de cinco casillas coincide con el borde, así que los dos diagramas '
                  'son iguales; desde la esquina a1 se aprecia lo que añade la extensión.'),
            ('diagramas', list(par_promocion(v, 'CA', 'Arzobispo'))),
            ('diagramas', list(par_promocion(v, 'CA', 'Arzobispo', sq11('a1'), ' en a1'))),
        ]),
        ('El Canciller', [
            ('lista', ['4.7.1 Combina el salto tradicional del Caballo con el movimiento de la Torre limitado a '
                       'cinco casillas, y captura igual.',
                       '4.7.2 Forma extendida: su movimiento de Torre deja de estar limitado.']),
            ('diagramas', list(par_promocion(v, 'CH', 'Canciller'))),
            ('diagramas', list(par_promocion(v, 'CH', 'Canciller', sq11('a1'), ' en a1'))),
        ]),
        ('La Catapulta', [
            ('lista', ['4.8.1 Movimiento: a cualquier casilla a distancia uno o dos (24 casillas), aunque haya '
                       'piezas en medio.',
                       '4.8.2 Captura: solo en las 16 casillas a distancia exactamente dos; nunca en las adyacentes.',
                       '4.8.3 Salto extendido: en cualquier dirección recta, si la casilla adyacente y las '
                       'siguientes están ocupadas sin huecos (por piezas de cualquier color), puede saltar a la '
                       'primera casilla vacía tras la secuencia. Las piezas saltadas se quedan.',
                       '4.8.4 En su forma base, el salto extendido es solo un movimiento: no captura, no ataca, no '
                       'da jaque y puede pasar sobre cualquier pieza, incluido el Rey.']),
            ('diagramas', [diagrama_pieza(v, 'CE', texto='Catapulta: movimiento (verde) y captura.')[0],
                           _e('Ctf6 Pg6 Ph6', {'i6': 'mov'}, flechas=[('f6', 'i6')],
                              texto='Salto extendido: con piezas propias en g6 y h6, la Catapulta salta a i6.')]),
        ]),
        ('Catapulta extendida', [
            ('p', '4.8.5 Conserva el movimiento de la forma base, incluido el salto extendido, y captura así:'),
            ('lista', ['(a) Captura simple en las ocho casillas a distancia dos que no están en dirección recta '
                       '(patrón del Caballo).',
                       '(b) Las ocho casillas adyacentes y las ocho a distancia dos en dirección recta solo se '
                       'capturan con una cadena de saltos.',
                       '(c) Primer salto (opcional): un salto recto de dos casillas, que captura las piezas '
                       'adversarias de la casilla intermedia y de la de llegada (captura doble), o un salto '
                       'extendido, que captura todas las adversarias de la secuencia y deja las propias.',
                       '(d) Saltos sucesivos (obligatorios mientras haya capturas): saltos rectos de dos casillas '
                       'sobre una pieza adversaria, terminando en casilla vacía. El salto extendido solo puede ser '
                       'el primero. Si hay varias continuaciones, el jugador elige.',
                       '(e) Bloqueo: el primer salto no lo impiden las piezas del camino; si su llegada tiene una '
                       'pieza propia, continúa como salto extendido. En los saltos sucesivos, cualquier pieza en '
                       'la casilla de llegada impide el salto y la cadena termina.',
                       '(f) Las piezas capturadas se retiran tras cada salto.',
                       '(g) El jaque se produce al final. Si tras un salto el Rey adversario queda en jaque, ese '
                       'salto es el último.',
                       '(h) La cadena termina si no quedan capturas o si la única continuación dejaría al propio '
                       'Rey en jaque. Ningún salto puede caer en una casilla bloqueada por un Guardián adversario.',
                       '(i) Una pieza adversaria en una casilla bloqueada por un Guardián de su bando está protegida '
                       'y no se captura al ser saltada; el primer salto puede hacerse entonces como movimiento.',
                       '(j) Si el primer salto pasa sobre piezas propias, es un movimiento y la cadena continúa '
                       'desde la llegada si hay capturas.']),
            ('p', '4.8.6 El Rey adversario no puede ser saltado: bloquea cualquier salto que deba pasar sobre él. '
                  'La Catapulta extendida da jaque al Rey en cualquiera de sus casillas de captura excepto las '
                  'adyacentes; si el Rey forma parte de la secuencia de un salto extendido, solo está en jaque '
                  'cuando está a dos casillas.'),
            ('diagramas', [diagrama_pieza(v, 'CE', True, texto='Catapulta extendida: captura.')[0],
                           _e('Ct+f6 n:Pg6 n:Ph6', {'g6': 'cap', 'h6': 'movcap'}, {'h6': 1}, [('f6', 'h6')],
                              texto='Captura doble: el salto de f6 a h6 captura los peones de g6 y h6.')]),
            ('diagramas', [_e('Ct+f6 n:Pg6 n:Ph6 n:Ph7 n:Ph8',
                              {'g6': 'cap', 'h6': 'cap', 'h7': 'cap', 'h8': 'cap', 'i6': 'movcap', 'g8': 'movcap',
                               'i8': 'movcap'}, {'i6': 1, 'g8': 2, 'i8': 3}, [('f6', 'i6'), ('i6', 'g8'), ('g8', 'i8')],
                              texto='(1) Salto extendido de f6 a i6, capturando g6 y h6. (2) De i6 a g8, capturando '
                                    'h7. (3) De g8 a i8, capturando h8.'),
                           _e('Ct+f6 n:Pg6 n:Ph6 n:Gi7', {'h6': 'bloq', 'j6': 'bloq', 'h8': 'bloq', 'j8': 'bloq',
                                                          'i7': 'cap', 'i6': 'mov', 'i8': 'movcap'},
                              {'i6': 1, 'i8': 2}, [('f6', 'i6'), ('i6', 'i8')],
                              texto='Con el Guardián en i7, el peón de h6 está protegido: el salto a i6 se hace sin '
                                    'capturar y la cadena captura al Guardián, terminando en i8.')]),
            ('diagramas', [_e('Ct+f6 n:Rh6', {'h6': 'jaque'},
                              texto='Jaque: el Rey en h6 está a dos casillas, donde caería un salto recto.'),
                           _e('Ct+f6 Pg6 n:Ph6 n:Ri6', {}, texto='Sin jaque: el Rey en i6 está a tres casillas; '
                                                                 'solo bloquea el salto extendido.')]),
        ]),
        ('El Peón', [
            ('lista', ['4.9.1 Avanza una casilla si está vacía. Mientras no haya avanzado ni haya sido empujado, '
                       'puede avanzar dos desde su fila inicial. El intercambio con un Guardián no le quita esa '
                       'facultad.',
                       '4.9.2 Captura en las dos casillas en diagonal inmediatamente delante. Puede capturar al '
                       'paso (4.11).',
                       '4.9.3 Al llegar a la última fila se extiende automáticamente: se mueve y captura una casilla '
                       'en cualquier dirección, como el Rey, sin ser Rey. El peón extendido no puede ser '
                       'empujado. Por 5.4, un peón también puede convertirse en Guardián.']),
            ('diagramas', [diagrama_pieza(v, 'P', texto='Peón: movimiento y captura. El segundo avance solo es '
                                                        'posible desde la fila inicial.')[0],
                           diagrama_pieza(v, 'P', True, texto='Peón extendido.')[0]]),
        ]),
        ('El Guardián', [
            ('lista', ['4.10.1 Avance: hasta dos casillas en su columna, por casillas vacías. Los Guardianes '
                       'iniciales (y los creados de un peón que no se había movido) pueden avanzar tres en su '
                       'primer avance desde su fila de inicio.',
                       '4.10.2 Desplazamiento lateral: una casilla a la izquierda o a la derecha, si está vacía.',
                       '4.10.3 Intercambio: puede cambiar su posición con un peón propio lateralmente adyacente, '
                       'pero no deshacer un intercambio con el mismo peón.',
                       '4.10.4 Empuje: si delante tiene un peón adversario sin extender, puede empujarlo una '
                       'casilla hacia atrás y ocupar su lugar (si la casilla de retroceso está libre). El peón '
                       'empujado pierde el doble avance.',
                       '4.10.5 Captura en las cuatro casillas en diagonal inmediata, hacia adelante o hacia atrás. '
                       'Puede capturar al paso.',
                       '4.10.6 Bloqueo de jaque: puede moverse sin capturar a una de sus casillas de captura si y '
                       'solo si con ello bloquea un jaque a su Rey.',
                       '4.10.7 Bloqueo de saltos: ninguna pieza adversaria puede caer mediante un salto en sus cuatro '
                       'casillas diagonales, ni para moverse ni para capturar. Las piezas propias en ellas están a '
                       'salvo de capturas por salto y el Rey propio no recibe jaque de una pieza que salta. Las '
                       'piezas de desplazamiento, el Rey y los peones no se ven afectados.',
                       '4.10.8 Forma extendida: se mueve y captura hasta dos casillas en cualquier dirección recta '
                       '(la intermedia debe estar vacía). No puede empujar ni bloquear saltos.']),
            ('diagramas', list(par_promocion(v, 'G', 'Guardián'))),
            ('diagramas', [_e('Gf6 Pg6', {'g6': 'mov'}, flechas=[('f6', 'g6')],
                              texto='Intercambio: el Guardián de f6 y el peón propio de g6 cambian de lugar.'),
                           _e('Gf6 n:Pf7', {'f7': 'mov', 'f8': 'mov'}, flechas=[('f7', 'f8')],
                              texto='Empuje: el Guardián ocupa f7 y el peón adversario retrocede a f8.')]),
            ('diagramas', [_e('n:Ai9 Rd4 Gg5', {'d4': 'jaque', 'f6': 'mov'}, flechas=[('g5', 'f6')],
                              texto='Bloqueo de jaque: el Alfil de i9 da jaque al Rey en d4; el Guardián puede ir a f6 '
                                    'porque corta la línea del jaque.'),
                           _e('Gf6 Pg7 n:Ci8', {'e5': 'bloq', 'g5': 'bloq', 'e7': 'bloq', 'g7': 'bloq'},
                              texto='Bloqueo de saltos: el Caballo de i8 no puede capturar el peón de g7 ni caer en '
                                    'ninguna casilla gris.')]),
            ('diagramas', [_e('n:Ci6 Rf5', {'f5': 'jaque'}, texto='Sin Guardián: el Caballo de i6 da jaque con el '
                                                                 'salto largo.'),
                           _e('n:Ci6 Rf5 Ge4', {'f5': 'bloq', 'd5': 'bloq', 'd3': 'bloq', 'f3': 'bloq'},
                              texto='Con el Guardián en e4, f5 queda bloqueada y no hay jaque.')]),
        ]),
        ('Captura al paso', [
            ('lista', ['4.11.1 Si un peón o Guardián, en su primer avance desde su fila de inicio, avanza dos '
                       'casillas (o tres, el Guardián) y queda junto a un peón o Guardián adversario en la misma '
                       'fila, este puede capturarlo solo en la jugada siguiente, moviéndose en diagonal a la casilla '
                       'que quedó detrás de la pieza capturada.',
                       '4.11.2 Los avances posteriores de dos casillas del Guardián no permiten la captura al paso.']),
            ('diagramas', [_e('Pf8 n:Pg8', {'g8': 'cap', 'g9': 'movcap'}, flechas=[('f8', 'g9')],
                              texto='El peón negro avanzó de g10 a g8; el peón de f8 lo captura al paso moviéndose '
                                    'a g9.'),
                           _e('Gd7 n:Ge7', {'e7': 'cap', 'e8': 'movcap'}, flechas=[('d7', 'e8')],
                              texto='El Guardián negro avanzó tres casillas, de e10 a e7; el Guardián de d7 lo '
                                    'captura al paso en e8.')]),
        ]),
        ('Extensión', [
            ('lista', ['5.1 Toda pieza, excepto el Rey, tiene una forma extendida. Cada pieza solo se extiende '
                       'una vez.',
                       '5.2 Por llegada: el peón o el Guardián que alcanza la última fila se extiende '
                       'automáticamente, en la misma jugada.',
                       '5.3 Por captura: Dama, Arzobispo, Canciller y Catapulta, al haber capturado la pieza '
                       'adversaria del mismo tipo. Torre, Alfil y Caballo, al haber capturado las dos; y solo una '
                       'de las dos propias puede extenderse. La pieza debe estar en el tablero.',
                       '5.4 Por acumulación: por cada cuatro peones adversarios capturados, un peón propio puede '
                       'convertirse en Guardián; por cada cinco Guardianes adversarios capturados, un Guardián '
                       'propio puede extenderse. Nadie puede tener más de cinco Guardianes.',
                       '5.5 Las extensiones de 5.3 y 5.4 son por sí mismas la jugada del turno. El derecho se '
                       'conserva hasta que se ejerce. En el juego, la pieza que puede extenderse lleva una '
                       'estrella dorada.']),
            ('tabla', ['Pieza', 'Condición', 'Forma extendida'], [
                ['Peón', 'Llegar a la última fila', 'Se mueve y captura como el Rey'],
                ['Guardián', 'Última fila, o capturar 5 Guardianes', 'Hasta dos casillas en cualquier dirección'],
                ['Torre', 'Capturar las dos Torres', '+1 a 3 casillas en diagonal, con salto'],
                ['Alfil', 'Capturar los dos Alfiles', '+1 a 3 casillas en ortogonal, con salto'],
                ['Caballo', 'Capturar los dos Caballos', '+ saltos de tres y dos'],
                ['Dama', 'Capturar la Dama', '+ salto tradicional del Caballo'],
                ['Arzobispo', 'Capturar el Arzobispo', 'Alfil sin límite'],
                ['Canciller', 'Capturar el Canciller', 'Torre sin límite'],
                ['Catapulta', 'Capturar la Catapulta', 'Captura simple y en cadena'],
                ['Rey', '—', 'No se extiende']]),
        ]),
        ('Fin de la partida', [
            ('lista', ['6.1 Una jugada es legal solo si, al terminar, el Rey propio no queda en jaque.',
                       '7.1 Jaque mate: gana quien da mate.',
                       '7.2 Ahogado: si el jugador en turno no tiene jugadas legales y no está en jaque, la partida '
                       'es tablas (sin desempate por puntos).',
                       '7.3 Triple repetición de la misma posición, con el mismo jugador en turno y los mismos '
                       'derechos.',
                       '7.4 Regla de las 50 jugadas: 50 jugadas de cada jugador sin capturas, avances de peón o '
                       'Guardián (incluido el empuje) ni extensiones.',
                       '7.5 Material insuficiente para dar mate.',
                       '7.6 Desempate por puntos: en los casos 7.3, 7.4 y 7.5 gana quien haya acumulado más puntos '
                       'por las piezas adversarias capturadas (Apéndice A, según su forma al capturarlas). Si hay '
                       'igualdad, tablas. En el juego, el «Marcador de puntos» lleva esta cuenta.']),
        ]),
        ('Valores y notación', [
            ('h', 'Apéndice A. Valores de las piezas'),
            ('tabla', ['Pieza', 'Base', 'Extendida'], [
                ['Peón', '1', '2'], ['Guardián', '2', '3.5'], ['Alfil', '3', '6.5'], ['Caballo', '3.5', '6'],
                ['Catapulta', '5', '9.5'], ['Torre', '5', '8'], ['Arzobispo', '5', '6'], ['Canciller', '6', '8'],
                ['Dama', '9', '10.5'], ['Rey', '—', '—']]),
            ('h', 'Apéndice C. Notación'),
            ('lista', ['Símbolos: R Rey, D Dama, T Torre, A Alfil, C Caballo, Az Arzobispo, Ch Canciller, Ct '
                       'Catapulta, G Guardián, P Peón. Las formas extendidas llevan un apóstrofo (D\').',
                       'Cada jugada: símbolo y casilla de llegada (Ct h3); las de peón, solo la casilla.',
                       '«x» captura, «+» jaque, «#» mate, «0-0a» y «0-0k» enroques, «a.p.» captura al paso.',
                       'Extensión por llegada: e11=P\'. Por captura o acumulación: Cc3=C\' o d4=G.',
                       'Cadena de la Catapulta: casillas de llegada separadas por «x» (Ct\' f6xi6xg8xi8).',
                       'El empuje y el intercambio del Guardián se anotan como un movimiento ordinario.']),
        ]),
    ]
    return secciones


# ====================================================================== contenido: variantes genéricas
INTRO = {
    'clasico': 'El ajedrez tradicional, según las Leyes del Ajedrez de la FIDE.',
    'capablanca': 'Propuesto por José Raúl Capablanca en la década de 1920 para evitar el «agotamiento» del '
                  'ajedrez: un tablero de 10 × 8 con dos piezas nuevas, el Arzobispo (Alfil + Caballo) y el '
                  'Canciller (Torre + Caballo).',
    'gotico': 'Ideado por Ed Trice, usa las piezas y el tablero del Ajedrez Capablanca con otra posición '
              'inicial, en la que todos los peones están protegidos desde el principio.',
}
TEXTO_PIEZA = {
    'K': 'Se mueve una casilla en cualquier dirección y captura del mismo modo.',
    'Q': 'Se mueve por su columna, su fila o sus diagonales, sin límite de distancia.',
    'R': 'Se mueve por su columna o su fila, sin límite de distancia.',
    'B': 'Se mueve por sus diagonales, sin límite de distancia; siempre en casillas del mismo color.',
    'N': 'Salta dos casillas en una dirección ortogonal y una en la perpendicular, aunque haya piezas en medio.',
    'CA': 'Combina el Alfil y el Caballo: se desliza en diagonal sin límite o salta como el Caballo.',
    'CH': 'Combina la Torre y el Caballo: se desliza en línea recta sin límite o salta como el Caballo.',
    'AM': 'Combina la Dama y el Caballo: la pieza más poderosa del catálogo.',
    'H': 'Se mueve como el Rey, una casilla en cualquier dirección, pero no es una pieza real: puede ser '
         'capturado sin que se pierda la partida.',
    'CM': 'Salta tres casillas en una dirección ortogonal y una en la perpendicular.',
}


def _describir_movs(d):
    """Texto de los movimientos de una pieza de una variante genérica (para las reglas), ya traducido: cada
    parte se traduce por separado."""
    from idioma import tr as T
    partes = []
    cond_txt = {'primera': ' (solo en su primer avance, desde su fila de inicio)',
                'jaque': ' (solo para tapar un jaque a su Rey)'}
    dirs_txt = {'orto': 'en línea recta (columnas y filas)', 'diag': 'en diagonal',
                'todas': 'en línea recta y en diagonal'}
    for m in d.get('movs', []):
        extra = T(cond_txt[m['cond']]) if m.get('cond') in cond_txt else ''
        if m.get('come'):
            extra += T(', capturando las piezas adversarias que salta')
        if 'salto' in m:
            a, b = m['salto']
            if m.get('repite'):
                partes.append(T('repite el salto de %d y %d casillas en la misma dirección mientras caiga en casillas '
                                'vacías%s') % (a, b, extra))
            else:
                partes.append(T('salta %d y %d casillas (en todas las direcciones)%s') % (a, b, extra))
        elif 'casillas' in m:
            grupos = {}
            for e in m['casillas']:
                salta = e[3] if len(e) > 3 and e[3] is not None else m.get('salta')
                cond = e[4] if len(e) > 4 and e[4] else m.get('cond')
                grupos.setdefault((e[2], bool(salta), cond), []).append(e)
            for (modo, salta, cond), lista in sorted(grupos.items(), key=lambda x: (MODO_ORDEN.index(x[0][0]),
                                                                                   x[0][1], x[0][2] or '')):
                que = T({'ambos': 'para mover y capturar', 'mov': 'solo para mover', 'cap': 'solo para capturar'}[modo])
                como = T('saltando lo que haya en medio' if salta else 'con el camino libre')
                c = T(cond_txt[cond]) if cond in cond_txt else ''
                partes.append((T('1 casilla concreta %s, %s%s') % (que, como, c)) if len(lista) == 1
                              else (T('%d casillas concretas %s, %s%s') % (len(lista), que, como, c)))
            if m.get('come'):
                partes[-1] += T('; al saltar en línea recta captura las piezas adversarias que salta')
        elif 'dirs' in m:
            alc = m.get('alcance', 0)
            texto = '%s %s %s' % (T('salta' if m.get('salta') else 'se desliza'), T(dirs_txt[m['dirs']]),
                                  T('sin límite') if not alc else T('hasta %d casilla%s' % (alc, 's' if alc > 1 else '')))
            if m.get('modo', 'ambos') != 'ambos':
                texto += T(' (solo para mover)' if m['modo'] == 'mov' else ' (solo para capturar)')
            partes.append(texto + extra)
        elif 'pantalla' in m:
            donde = T(dirs_txt.get(m['pantalla'], 'en las direcciones indicadas') if isinstance(m['pantalla'], str)
                      else 'en las direcciones indicadas')
            if m.get('come'):
                texto = T('captura saltando %s sobre una pieza adversaria%s y cae en la casilla justo detrás, que debe '
                          'estar vacía') % (donde, T(' que esté a su lado') if m.get('pegada') else '')
            else:
                texto = T({'justo': 'salta %s sobre la primera pieza que encuentra (de cualquier color) y cae en la '
                                    'casilla justo detrás',
                           'libre': 'salta %s sobre la primera pieza que encuentra y cae en cualquier casilla detrás de '
                                    'ella, hasta la siguiente pieza',
                           'primera': 'salta %s sobre la primera pieza que encuentra y llega a la primera pieza que '
                                      'hay detrás'}[m.get('tras', 'justo')]) % donde
                modo = m.get('modo', 'ambos')
                texto += T({'ambos': ' (vacía, o capturando)', 'mov': ' (sin capturar)', 'cap': ', capturándola'}[modo])
                if m.get('pegada'):
                    texto += T('; la pieza saltada tiene que estar a su lado')
            partes.append(texto)
        elif 'secuencia' in m:
            partes.append(T('si la casilla de al lado y las siguientes %s están ocupadas, sin huecos, por al menos %d '
                            'piezas, salta a la primera casilla vacía tras la fila%s') % (
                              T(dirs_txt[m['secuencia']]), m.get('minimo', 2),
                              T(', capturando las adversarias') if m.get('come') else T(' (sin capturar)')))
        elif 'cadena' in m:
            partes.append(T('captura en cadena %s: saltos rectos de dos casillas sobre piezas adversarias que las '
                            'capturan (el primero captura también en la casilla de llegada%s); sigue saltando mientras '
                            'pueda capturar, el Rey adversario no se puede saltar y la cadena termina si da jaque') % (
                              T(dirs_txt[m['cadena']]), T(' o puede ser sobre una fila de piezas') if m.get('fila', True)
                              else ''))
        elif 'empuje' in m:
            partes.append(T('empuja una pieza adversaria (%s) que tenga al lado y ocupa su lugar, si la casilla de '
                            'detrás está vacía') % ', '.join(T(x) for x in m.get('_nombres', m.get('tipos', []))))
        elif 'intercambio' in m:
            partes.append(T('puede intercambiar su lugar con una pieza propia (%s) que tenga al lado, sin deshacer '
                            'enseguida un intercambio con la misma pieza') % ', '.join(
                T(x) for x in m.get('_nombres', m.get('tipos', []))))
        elif 'camino' in m:
            partes.append(T('recorre caminos que cambian de dirección; cualquier pieza en el camino la bloquea'))
    texto = ', '.join(partes) + '.' if partes else ''
    return texto[:1].upper() + texto[1:]


MODO_ORDEN = ['ambos', 'mov', 'cap']


def _propiedades(v, t, d):
    """Bloques de texto con lo que no es movimiento: bloqueo de saltos, avance de peón, forma extendida,
    conversión y puntos."""
    m, cfg = v.m, v.cfg
    nombre = lambda x: cfg['piezas'][x]['nombre']
    out = []
    if d.get('aura'):
        out.append(('p', 'Bloqueo de saltos: ninguna pieza adversaria puede caer mediante un salto en las casillas '
                         'que la rodean (%d), ni para moverse ni para capturar; las piezas propias en ellas no se '
                         'capturan al ser saltadas.' % len(d['aura'])))
    if d.get('como_peon'):
        out.append(('p', 'Avanza como un peón: sus avances en recto cuentan para la regla de las 50 jugadas, '
                         'conserva su primer avance aunque se mueva de lado, y captura y puede ser capturada al '
                         'paso.'))
    e = d.get('extension') or {}
    if e.get('pieza') in cfg['piezas']:
        como = []
        if e.get('llegada'):
            como.append('al llegar a la última fila (automáticamente, en la misma jugada)')
        if e.get('captura'):
            n = e['captura']
            if e.get('repetir'):
                como.append('por cada pieza adversaria de su tipo capturada, una propia puede extenderse' if n == 1
                            else 'por cada %d piezas adversarias de su tipo capturadas, una propia puede extenderse' % n)
            elif n == 1:
                como.append('tras haber capturado la pieza adversaria del mismo tipo (solo una de las propias se '
                            'extiende)')
            else:
                como.append('tras haber capturado %d piezas adversarias del mismo tipo (solo una de las propias se '
                            'extiende)' % n)
        out.append(('p', 'Forma extendida: se convierte en %s %s.%s' % (
            nombre(e['pieza']), ' o '.join(como),
            ' Extenderse por captura es la jugada del turno; el derecho se conserva hasta que se usa.'
            if e.get('captura') else '')))
    c = d.get('conversion') or {}
    if c.get('pieza') in cfg['piezas']:
        out.append(('p', 'Conversión: por cada %d piezas de su tipo capturadas al adversario, una propia puede '
                         'convertirse en %s (es la jugada del turno).' % (c['captura'], nombre(c['pieza']))))
    if d.get('base') in cfg['piezas']:
        out.append(('p', 'Es la forma extendida de %s.' % nombre(d['base'])))
    if m.reglas.get('desempate') and not d.get('real'):
        out.append(('p', 'Puntos para el desempate: %g.' % m.puntos[t]))
    return out


def contenido_generico(v):
    m, cfg, r = v.m, v.cfg, v.m.reglas
    W, H = v.ancho, v.alto
    nombre = lambda t: cfg['piezas'][t]['nombre']
    ini = v.inicial()
    pos0 = Diagrama(W, H, [(sq, v.imagen(*v.pieza(ini, sq))) for sq in range(W * H) if v.pieza(ini, sq)],
                    texto='Posición inicial.')
    fila = [nombre(p[2]) for p in sorted(cfg['posicion'], key=lambda p: p[0]) if p[1] == 0 and p[3] == 0]
    piezas_txt = ', '.join(fila)
    if any(p[3] == 0 and p[1] > 0 and not cfg['piezas'][p[2]].get('peon') for p in cfg['posicion']) or \
            len(fila) != W or fila != [nombre(p[2]) for p in sorted(cfg['posicion'], key=lambda p: p[0])
                                       if p[1] == H - 1 and p[3] == 1]:  # no es simétrica: se ve en el diagrama
        piezas_txt = ''
    objetivo = ('dar jaque mate al Rey adversario: atacarlo de modo que no tenga ninguna jugada legal para evitar '
                'su captura. Nadie puede hacer una jugada que deje a su propio Rey en jaque.'
                if m.mate else 'capturar al Rey adversario. No existe el jaque: el Rey puede quedar atacado y '
                               'la partida termina en cuanto es capturado.')
    secciones = [('Introducción', [
        ('p', INTRO.get(cfg.get('id')) or cfg.get('descripcion') or 'Variante creada en el Laboratorio.'),
        ('p', 'Se juega en un tablero de %d columnas y %d filas. Las blancas mueven primero. El objetivo es %s'
              % (W, H, objetivo)),
        ('p', 'Primera fila de las blancas, de izquierda a derecha: %s. Las negras se colocan igual, en el lado '
              'opuesto.' % piezas_txt if piezas_txt else 'La posición inicial se muestra en el diagrama.'),
        ('diagramas', [pos0]),
        ('h', 'Convenciones de los diagramas'),
        ('p', 'La pieza cuyo movimiento se describe aparece en blanco en el centro del tablero.'),
        ('leyenda', ['movcap', 'mov', 'esp', 'cap', 'jaque']),
    ])]
    orden = []  # cada pieza seguida de su forma extendida
    for t in v.paleta:
        if cfg['piezas'][t].get('base') not in cfg['piezas']:
            orden.append(t)
            orden += [x for x in v.paleta if cfg['piezas'][x].get('base') == t]
    orden += [t for t in v.paleta if t not in orden]
    for t in orden:
        d = cfg['piezas'][t]
        bloques = []
        if d.get('peon'):
            promo = ', '.join(nombre(x) for x in m.promo)
            pasos = m.pasos_peon
            if d.get('berolina'):
                txt = ['Avanza una casilla en diagonal hacia adelante si está vacía; no retrocede.',
                       'Captura en la casilla inmediatamente delante, en recto.']
                if r['doble_paso']:
                    txt.append('Desde su fila inicial puede avanzar dos casillas en diagonal si ambas están vacías.')
            else:
                txt = ['Avanza una casilla hacia adelante si está vacía; no retrocede.',
                       'Captura en las dos casillas en diagonal inmediatamente delante.']
                if r['doble_paso']:
                    txt.append('Desde su fila inicial puede avanzar dos casillas si ambas están vacías.' if pasos == 2
                               else 'Desde su fila inicial puede avanzar hasta %d casillas si están vacías.' % pasos)
            if r['al_paso']:
                txt.append('Captura al paso: si un peón adversario avanza dos casillas y queda a su lado, puede '
                           'capturarlo en la jugada siguiente como si hubiera avanzado una.')
            zona = m.zona
            if promo:
                donde = 'Al llegar a la última fila' if zona == 1 else 'Al llegar a una de las %d últimas filas' % zona
                frase = '%s se convierte, a elección del jugador, en: %s.' % (donde, promo)
                if zona > 1 and r.get('promocion_opcional'):
                    frase += ' Antes de la última fila puede seguir siendo peón.'
                if r.get('promocion_capturadas'):
                    frase += (' Solo puede convertirse en una pieza propia que ya haya sido capturada; si no hay '
                              'ninguna, no puede entrar en la última fila.')
                txt.append(frase)
            elif t not in m.ext_llegada:
                txt.append('En esta variante el peón no promociona.')
            bloques.append(('lista', txt))
        else:
            dn = copy.deepcopy(d)
            for mv in dn.get('movs', []):  # nombres de las piezas que se empujan o intercambian
                if 'tipos' in mv:
                    mv['_nombres'] = [nombre(x) for x in mv['tipos'] if x in cfg['piezas']]
            bloques.append(('p', TEXTO_PIEZA.get(t) if t in G.CATALOGO and d.get('movs') == G.CATALOGO[t]['movs']
                            else _describir_movs(dn)))
            if d.get('real'):
                bloques.append(('p', 'Es la pieza real: ' + ('no puede moverse a una casilla atacada.' if m.mate
                                                              else 'si la capturan, se pierde la partida.')))
            if d.get('enroca') and r['enroque']:
                bloques.append(('p', 'Participa en el enroque con el Rey.'))
            if t in m.promo:
                bloques.append(('p', 'Un peón que llega a la última fila puede convertirse en %s.' % d['nombre']))
        bloques += _propiedades(v, t, d)
        bloques.append(('p', 'Valor aproximado: %s.' % ('—' if d.get('real') else '%g' % m.valor[t])))
        bloques.append(('diagramas', [diagrama_pieza(v, t, texto=d['nombre'] + ': movimiento y captura.')[0]]))
        secciones.append((d['nombre'], bloques))
    especiales = []
    if r['enroque'] and any(d.get('enroca') for d in cfg['piezas'].values()) and v.rey:
        k = r['pasos_enroque']
        if isinstance(k, (list, tuple)):
            cuanto = '%d casillas hacia la Torre de la columna a o %d hacia la otra' % tuple(k[:2])
        else:
            cuanto = '1 casilla hacia una Torre' if k == 1 else '%d casillas hacia una Torre' % k
        especiales.append(('p', 'Enroque: el Rey se desplaza %s y la Torre se coloca en '
                                'la casilla contigua que el Rey acaba de cruzar. No es posible si el Rey o la Torre '
                                'ya se movieron, si hay piezas entre ambos, si el Rey está en jaque o si debe cruzar '
                                'o terminar en una casilla atacada.' % cuanto))
        enr = _diagrama_enroque(v)
        if enr:
            especiales.append(('diagramas', [enr]))
    if not especiales:
        especiales.append(('p', 'Esta variante no tiene enroque.'))
    secciones.append(('Movimientos especiales', especiales))
    fin = ['Jaque mate: gana quien da mate.' if m.mate else 'Gana quien captura al Rey adversario.',
           'Ahogado (el jugador en turno no tiene jugadas): ' + ('tablas.' if r['ahogado'] == 'tablas'
                                                                  else 'gana quien ahoga.')]
    if r['repeticion']:
        fin.append('Tablas por triple repetición de la misma posición.')
    if r['cincuenta']:
        fin.append('Tablas por la regla de las 50 jugadas: 50 jugadas de cada bando sin capturas ni movimientos '
                   'de peón%s.' % (' ni extensiones' if m.con_ext or m.ext_llegada else ''))
    if r['material']:
        fin.append('Tablas por material insuficiente para dar mate.')
    if r.get('desempate'):
        fin.append('Desempate por puntos: en las tablas por repetición, por la regla de las 50 jugadas o por '
                   'material insuficiente, gana quien haya capturado más puntos (el valor de cada pieza para el '
                   'desempate se indica en su sección).')
    secciones.append(('Fin de la partida', [('lista', fin)]))
    return secciones


def _diagrama_enroque(v):
    st = v.inicial()
    W = v.ancho
    rey = st.rey[0]
    if rey is None:
        return None
    vacia = v.m.construir([[s, *v.pieza(st, s)[:2]] for s in range(W * v.alto)
                           if v.pieza(st, s) and s // W == 0 and (v.pieza(st, s)[0] in v.m.real or
                                                                  v.pieza(st, s)[0] in v.m.enroca)], 0)
    destinos = [mv for mv in v.m.pseudo(vacia) if mv[0] == 'cs']
    if not destinos:
        return None
    piezas = [(s, v.imagen(*v.pieza(vacia, s))) for s in range(W * v.alto) if v.pieza(vacia, s)]
    return Diagrama(W, v.alto, piezas, {mv[2]: 'mov' for mv in destinos},
                    flechas=[(rey, mv[2]) for mv in destinos],
                    texto='Enroque: casillas a las que llega el Rey.')


def contenido(v):
    return contenido_extendido() if isinstance(v, V.Extendido) else contenido_generico(v)


# ====================================================================== ventana
class VentanaReglas:
    ANCHO_TEXTO = 700

    def __init__(self, app, variante, seccion=None):
        self.app, self.v, self.img, self.letra = app, variante, app.img, app.letra
        top = self.top = tk.Toplevel(app.root)
        top.title('Reglas — ' + variante.nombre)
        top.configure(bg=FONDO)
        top.geometry('%dx%d' % (min(1120, app.root.winfo_screenwidth() - 80),
                                min(860, app.root.winfo_screenheight() - 100)))
        self.colores = colores_tema(variante.tema)
        try:
            self.secciones = contenido(variante)
        except Exception as e:  # una variante a medio diseñar no debe impedir ver el resto
            self.secciones = [('Reglas', [('p', 'No se pudieron generar las reglas de esta variante: %s' % e)])]

        nav = ttk.Frame(top, style='Panel.TFrame', padding=(12, 14, 8, 12), width=240)
        nav.pack(side='left', fill='y')
        nav.pack_propagate(False)
        ttk.Label(nav, text='Reglas', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(nav, text=variante.nombre, style='Panel.TLabel', wraplength=210).pack(anchor='w', pady=(0, 10))
        self.botones = []
        for i, (titulo, _) in enumerate(self.secciones):
            b = ttk.Button(nav, text=titulo, style='Pestana.TButton', command=lambda i=i: self.mostrar(i))
            b.pack(fill='x', pady=1)
            self.botones.append(b)
        if isinstance(variante, V.Extendido) and os.path.exists(PDF):
            ttk.Button(nav, text='Abrir el reglamento (PDF)', command=self.abrir_pdf).pack(side='bottom', fill='x')

        cuerpo = tk.Frame(top, bg=FONDO)
        cuerpo.pack(side='left', fill='both', expand=True)
        self.cv = tk.Canvas(cuerpo, bg=FONDO, highlightthickness=0)
        barra = ttk.Scrollbar(cuerpo, command=self.cv.yview)
        self.cv.configure(yscrollcommand=barra.set)
        barra.pack(side='right', fill='y')
        self.cv.pack(side='left', fill='both', expand=True)
        self.interior = tk.Frame(self.cv, bg=FONDO)
        self.cv.create_window(24, 16, window=self.interior, anchor='nw')
        self.interior.bind('<Configure>', lambda e: self.cv.configure(scrollregion=self.cv.bbox('all')))
        for ev in ('<Button-4>', '<Button-5>', '<MouseWheel>'):
            top.bind(ev, self._rueda)  # la ventana está en las bindtags de todos sus widgets
        self.mostrar(next((i for i, (t, _) in enumerate(self.secciones) if t == seccion), 0))

    def _rueda(self, ev):
        paso = -1 if (getattr(ev, 'num', 0) == 4 or getattr(ev, 'delta', 0) > 0) else 1
        self.cv.yview_scroll(paso * 3, 'units')

    def abrir_pdf(self):
        from interfaz import abrir_archivo
        abrir_archivo(PDF)

    def mostrar(self, i):
        for k, b in enumerate(self.botones):
            b.configure(style='PestanaActiva.TButton' if k == i else 'Pestana.TButton')
        for w in self.interior.winfo_children():
            w.destroy()
        titulo, bloques = self.secciones[i]
        tk.Label(self.interior, text=titulo, bg=FONDO, fg='#F3E2BE', font=(self.app.serif, 22, 'bold')).pack(
            anchor='w', pady=(0, 8))
        usadas = []
        for tipo, dato, *resto in bloques:
            if tipo == 'p':
                self._parrafo(dato)
            elif tipo == 'h':
                tk.Label(self.interior, text=dato, bg=FONDO, fg=ORO, font=(self.letra, 12, 'bold')).pack(
                    anchor='w', pady=(12, 4))
            elif tipo == 'lista':
                for item in dato:
                    self._parrafo(item, sangria=True)
            elif tipo == 'tabla':
                self._tabla(dato, resto[0])
            elif tipo == 'leyenda':
                self._leyenda(dato)
            elif tipo == 'diagramas':
                fila = tk.Frame(self.interior, bg=FONDO)
                fila.pack(anchor='w', pady=(10, 6))
                for d in dato:
                    self._diagrama(fila, d)
                    for t in d.marcas.values():
                        if t not in usadas:
                            usadas.append(t)
        if usadas and not any(b[0] == 'leyenda' for b in bloques):
            self._leyenda(usadas)
        self.cv.yview_moveto(0)

    def _parrafo(self, texto, sangria=False):
        tk.Label(self.interior, text=('•  ' if sangria and not texto[:1].isdigit() and not texto.startswith('(')
                                      else '') + texto, bg=FONDO, fg=TEXTO, font=(self.letra, 11),
                 wraplength=self.ANCHO_TEXTO - (20 if sangria else 0), justify='left').pack(
            anchor='w', padx=(20 if sangria else 0, 0), pady=(2, 2))

    def _tabla(self, cabecera, filas):
        t = tk.Frame(self.interior, bg=BORDE)
        t.pack(anchor='w', pady=(8, 8))
        for j, txt in enumerate(cabecera):
            tk.Label(t, text=txt, bg='#4A3E33', fg='#F3E2BE', font=(self.letra, 10, 'bold'), anchor='w',
                     padx=8, pady=4).grid(row=0, column=j, sticky='nsew', padx=(0, 1), pady=(0, 1))
        for i, fila in enumerate(filas, 1):
            for j, txt in enumerate(fila):
                tk.Label(t, text=txt, bg='#2F2721' if i % 2 else '#352C25', fg=TEXTO, font=(self.letra, 10),
                         anchor='w', padx=8, pady=3).grid(row=i, column=j, sticky='nsew', padx=(0, 1), pady=(0, 1))

    def _leyenda(self, tipos):
        f = tk.Frame(self.interior, bg=FONDO)
        f.pack(anchor='w', pady=(8, 4))
        for i, t in enumerate(tipos):
            color, texto = MARCAS[t]
            c = tk.Canvas(f, width=18, height=18, bg=FONDO, highlightthickness=0)
            c.create_rectangle(2, 2, 16, 16, fill=color, outline='')
            c.grid(row=i // 2, column=(i % 2) * 2, padx=(0, 6), pady=2)
            tk.Label(f, text=texto, bg=FONDO, fg=TEXTO_SUAVE, font=(self.letra, 10)).grid(
                row=i // 2, column=(i % 2) * 2 + 1, sticky='w', padx=(0, 30))

    def _diagrama(self, padre, d):
        cont = tk.Frame(padre, bg=FONDO)
        cont.pack(side='left', anchor='n', padx=(0, 28))
        s = max(14, min(30, 300 // max(d.ancho, d.alto)))
        m = 16
        cv = tk.Canvas(cont, width=d.ancho * s + m + 4, height=d.alto * s + m + 4, bg=FONDO, highlightthickness=0)
        cv.pack(anchor='w')
        clara, oscura = self.colores[:2]
        x0, y0 = m, 2
        cv.create_rectangle(x0 - 2, y0 - 2, x0 + d.ancho * s + 2, y0 + d.alto * s + 2, fill=BORDE, outline='')
        for sq in range(d.ancho * d.alto):
            c, r = sq % d.ancho, d.alto - 1 - sq // d.ancho
            x, y = x0 + c * s, y0 + r * s
            base = clara if (sq % d.ancho + sq // d.ancho) % 2 == 0 else oscura
            if sq in d.marcas:
                base = mezcla(base, MARCAS[d.marcas[sq]][0], 0.72)
            cv.create_rectangle(x, y, x + s, y + s, fill=base, outline='')
        fuente = (self.letra, max(7, s // 3))
        for c in range(d.ancho):
            cv.create_text(x0 + c * s + s / 2, y0 + d.alto * s + 8, text=G.LETRAS[c], fill=TEXTO_SUAVE, font=fuente)
        for r in range(d.alto):
            cv.create_text(x0 - 8, y0 + (d.alto - 1 - r) * s + s / 2, text=str(r + 1), fill=TEXTO_SUAVE, font=fuente)
        centro = lambda sq: (x0 + (sq % d.ancho) * s + s / 2, y0 + (d.alto - 1 - sq // d.ancho) * s + s / 2)
        for sq, ruta in d.piezas:
            cv.create_image(*centro(sq), image=self.img.get(ruta, int(s * 0.92)))
        for a, b in d.flechas:
            (xa, ya), (xb, yb) = centro(a), centro(b)
            cv.create_line(xa, ya, xb, yb, fill='#1F3F6E', width=max(2, s // 9), arrow='last',
                           arrowshape=(s * 0.4, s * 0.48, s * 0.18))
        for sq, n in d.numeros.items():
            x, y = centro(sq)
            r = s * 0.24
            cv.create_oval(x + s / 2 - 2 * r - 1, y - s / 2 + 1, x + s / 2 - 1, y - s / 2 + 2 * r + 1, fill='#1F3F6E',
                           outline='')
            cv.create_text(x + s / 2 - r - 1, y - s / 2 + r + 1, text=str(n), fill='white',
                           font=(self.letra, max(7, int(r * 1.2)), 'bold'))
        if d.texto:
            tk.Label(cont, text=d.texto, bg=FONDO, fg=TEXTO_SUAVE, font=(self.letra, 10, 'italic'),
                     wraplength=d.ancho * s + m, justify='left').pack(anchor='w', pady=(4, 0))
