"""Bitácoras: registro de todas las jugadas de una partida, para analizarla o reproducirla.

Un archivo de bitácora tiene una partida por línea (JSON). Cada partida:
  {"formato": "bitacora-ajedrez", "version": 1, "origen": "simulador" | "espectador",
   "fecha": "2026-10-04 18:30:00", "variante": {"tipo": "extendido"} | {"tipo": "generica", "config": {...}},
   "inicio": null | {"piezas": [...], "turno": 0},
   "blancas": {...}, "negras": {...},          # nivel o profundidad de cada computadora
   "jugadas": [{"i": 12, "j": "G e5", "e": 0.21, "p": 4, "azar": true}, ...],
   "resultado": "blancas" | "negras" | "tablas", "motivo": "jaque mate", ...}
En cada jugada: i = índice de la jugada en la lista de jugadas legales (motor.legal o el motor de la
variante), con lo que la partida se reproduce exactamente; j = notación (Apéndice C), con + o #;
e = evaluación de la computadora a favor de las blancas (positiva: mejor para las blancas);
m = en lugar de e cuando la computadora ve un mate: jugadas hasta el mate (+ blancas, - negras);
p = profundidad alcanzada; azar = jugada inicial al azar (simulador).
El juego de escritorio reproduce estas bitácoras: ./jugar.sh --bitacora archivo.jsonl
"""
import json, math, time

MATE = 100000  # como en busqueda.py y generico.py

FORMATO = 'bitacora-ajedrez'


def nuevo(origen, variante=None, inicio=None, **extra):
    r = {'formato': FORMATO, 'version': 1, 'origen': origen, 'fecha': time.strftime('%Y-%m-%d %H:%M:%S'),
         'variante': variante or {'tipo': 'extendido'}, 'inicio': inicio, 'jugadas': []}
    r.update(extra)
    return r


def jugada(idx, notacion, turno, puntaje=None, profundidad=None, azar=False):
    """Una jugada de la bitácora; puntaje es la evaluación desde el bando que mueve (turno)."""
    j = {'i': idx, 'j': notacion}
    if puntaje is not None:
        a_favor = puntaje if turno == 0 else -puntaje  # positivo: mejor para las blancas
        if abs(a_favor) > MATE / 2:  # mate visto: jugadas hasta el mate, + si lo dan las blancas
            j['m'] = int(math.copysign((round(MATE - abs(a_favor)) + 1) // 2, a_favor))
        else:
            j['e'] = round(a_favor, 2)
    if profundidad is not None:
        j['p'] = profundidad
    if azar:
        j['azar'] = True
    return j


def escribir(archivo, registro):
    archivo.write(json.dumps(registro, ensure_ascii=False) + '\n')
    archivo.flush()


def leer(ruta):
    """Lista de partidas de un archivo de bitácora."""
    partidas = []
    with open(ruta, encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            r = json.loads(linea)
            if r.get('formato') != FORMATO:
                raise ValueError('%s no es un archivo de bitácora' % ruta)
            partidas.append(r)
    return partidas


def resumen(r):
    """Texto corto para elegir una partida."""
    partes = []
    if 'semilla' in r:
        partes.append('semilla %d' % r['semilla'])
    partes.append('%d jugadas' % ((len(r['jugadas']) + 1) // 2))
    if r.get('resultado'):
        partes.append('%s (%s)' % (r['resultado'], r.get('motivo', '')))
    return ' · '.join(partes)
