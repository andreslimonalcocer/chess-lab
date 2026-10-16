"""Genera los diseños de piezas adicionales (SVG y PNG de 256 px, blancas y negras), con el mismo trazo que el
juego original de piezas:

  estilos/clasico/     Rey, Dama, Torre, Alfil, Caballo y Peón de estilo clásico (tipo Staunton).
  estilos/capablanca/  Arzobispo (Alfil + Caballo) y Canciller (Torre + Caballo) como en el Ajedrez Capablanca.
  estilos/staunton1-3/ Rey, Dama, Arzobispo (media luna) y Canciller con silueta Staunton, en tres diseños.
  estilos/anterior/    El Arzobispo anterior (media luna sobre cuerpo recto).
  estilos/diagrama/    Las ocho piezas como en los diagramas de los libros (Arzobispo y Canciller incluidos) y el Guardián.
  estilos/yelmo, centinela, garita, escudo, cometa/  Otros diseños del Guardián (y staunton1/, con escudo).
  estilos/fundibulo, mangonel, onagro/  Otros diseños de la Catapulta (y staunton1/ y diagrama/).
  blancas/, negras/    También el Arzobispo del juego (copa en media luna con bola, como la pieza 3D).
  predisenos/          Las piezas mágicas del Laboratorio (Juego/piezas_magicas.py): Amazona, Camello, Saltamontes,
                       Jinete nocturno, León, Rosa... y algunas creaciones propias.
  partes/              Cuerpos, remates, adornos y letras con los que el diseñador del Laboratorio arma
                       piezas propias (las superpone en el juego, sin necesitar este script).

Cada pieza completa tiene su forma promocionada (_promocionado: base y estrella doradas). Necesita ImageMagick
(«magick») para pasar los SVG a PNG; el juego solo usa los PNG.

    python3 generar_disenos.py            # todo
    python3 generar_disenos.py --muestra  # además, una hoja de muestra (muestra_disenos.png)
"""
import argparse, os, shutil, subprocess, sys, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
COLORES = {'blancas': {'F': '#F8F4EA', 'S': '#1C1C1C', 'D': '#1C1C1C'},
           'negras': {'F': '#2A2A2A', 'S': '#000000', 'D': '#E9E2D4'}}
ORO = '#D4A017'
BASE = '<rect x="18" y="84" width="64" height="10" rx="4" fill="{F}"/>'
BASE_DORADA = '<rect x="18" y="84" width="64" height="10" rx="4" fill="%s"/>' % ORO
ESTRELLA = ('<polygon points="83.0,5.0 85.6,11.4 92.5,11.9 87.3,16.4 88.9,23.1 83.0,19.5 77.1,23.1 78.7,16.4 '
            '73.5,11.9 80.4,11.4" fill="%s"/>' % ORO)
COLLAR = '<rect x="34" y="40" width="32" height="7" rx="2" fill="{F}"/>'

# ---------------------------------------------------------------------- cuerpos (hasta el collar, y = 40)
CUERPOS = {
    'recto': '<path d="M33 84 L38 46 L62 46 L67 84 Z" fill="{F}"/>' + COLLAR,
    'clasico': ('<path d="M29 84 Q36 76 39 64 Q41 54 40 46 L60 46 Q59 54 61 64 Q64 76 71 84 Z" fill="{F}"/>'
                '<path d="M37 70 Q50 73 63 70" fill="none" stroke="{D}" stroke-width="1.6"/>' + COLLAR),
    'ancho': '<path d="M26 84 Q30 62 40 46 L60 46 Q70 62 74 84 Z" fill="{F}"/>' + COLLAR,
    'esbelto': ('<path d="M39 84 L43 46 L57 46 L61 84 Z" fill="{F}"/>'
                '<rect x="38" y="40" width="24" height="7" rx="2" fill="{F}"/>'),
    'escalonado': ('<path d="M30 84 L32 68 L38 68 L39 46 L61 46 L62 68 L68 68 L70 84 Z" fill="{F}"/>'
                   + COLLAR),
    'barril': '<path d="M35 84 Q27 66 38 46 L62 46 Q73 66 65 84 Z" fill="{F}"/>' + COLLAR,
}

# ---------------------------------------------------------------------- remates (sobre el collar)
CABEZA_CABALLO = ('<path d="M41 41 Q39 30 45 21 L48 11 L53 20 Q67 23 69 36 L63 41 Z" fill="{F}"/>'
                  '<circle cx="58" cy="28" r="2.4" fill="{D}" stroke="none"/>')
REMATES = {
    'cruz': ('<path d="M37 40 Q37 22 50 20 Q63 22 63 40 Z" fill="{F}"/>'
             '<rect x="46.5" y="3" width="7" height="19" fill="{F}"/><rect x="40" y="8" width="20" height="7" fill="{F}"/>'),
    'corona': ('<path d="M36 40 L31 15 L42 28 L45 11 L50 26 L55 11 L58 28 L69 15 L64 40 Z" fill="{F}"/>'
               '<circle cx="31" cy="12" r="4" fill="{F}"/><circle cx="45" cy="8" r="4" fill="{F}"/>'
               '<circle cx="55" cy="8" r="4" fill="{F}"/><circle cx="69" cy="12" r="4" fill="{F}"/>'),
    'almenas': ('<path d="M36 40 L36 30 L64 30 L64 40 Z" fill="{F}"/>'
                '<path d="M30 31 L30 12 L38 12 L38 20 L46 20 L46 12 L54 12 L54 20 L62 20 L62 12 L70 12 L70 31 Z" fill="{F}"/>'),
    'mitra': ('<path d="M50 9 Q70 25 62 40 L38 40 Q30 25 50 9 Z" fill="{F}"/><circle cx="50" cy="7" r="4" fill="{F}"/>'
              '<path d="M52 18 L58 31" fill="none" stroke="{D}" stroke-width="2"/>'),
    'caballo': CABEZA_CABALLO,
    'bola': '<rect x="44" y="34" width="12" height="7" fill="{F}"/><circle cx="50" cy="24" r="13" fill="{F}"/>',
    'luna': ('<rect x="45" y="29" width="10" height="12" fill="{F}"/>'
             '<path d="M31 10 A19 19 0 0 0 69 10 A23 15 0 0 1 31 10 Z" fill="{F}"/>'),
    'sello': ('<rect x="35" y="31" width="30" height="8" rx="3" fill="{F}"/><rect x="45" y="20" width="10" height="12" fill="{F}"/>'
              '<path d="M34 21 Q34 7 50 7 Q66 7 66 21 Z" fill="{F}"/>'),
    'amazona': (CABEZA_CABALLO + '<path d="M43 14 L41 4 L46 9 L49 2 L52 9 L57 4 L55 14 Z" fill="{F}"/>'),
    'unicornio': (CABEZA_CABALLO + '<path d="M51 17 L60 2 L56 19 Z" fill="{F}"/>'),
    'camello': ('<path d="M30 41 Q28 32 35 30 Q39 16 46 28 Q51 16 57 28 Q61 27 63 30 L66 17 Q68 10 75 11 L79 15 '
                'Q77 19 72 19 L69 34 Q67 41 62 41 Z" fill="{F}"/><circle cx="73" cy="14" r="1.6" fill="{D}" stroke="none"/>'),
    'elefante': ('<ellipse cx="34" cy="24" rx="9" ry="12" fill="{F}"/><ellipse cx="66" cy="24" rx="9" ry="12" fill="{F}"/>'
                 '<circle cx="50" cy="24" r="13" fill="{F}"/>'
                 '<path d="M47 30 Q46 40 50 41 Q54 40 53 30" fill="{F}"/>'
                 '<circle cx="45" cy="21" r="1.8" fill="{D}" stroke="none"/><circle cx="55" cy="21" r="1.8" fill="{D}" stroke="none"/>'),
    'canon': ('<path d="M30 30 L64 14 L69 23 L35 39 Z" fill="{F}"/><rect x="64" y="13" width="7" height="11" rx="2" '
              'transform="rotate(-25 67 18)" fill="{F}"/><circle cx="42" cy="34" r="7" fill="{F}"/>'
              '<circle cx="42" cy="34" r="2" fill="{D}" stroke="none"/>'),
    'dragon': ('<path d="M35 40 L30 14 L40 24 L44 8 L51 22 L58 8 L61 24 L71 14 L65 40 Z" fill="{F}"/>'
               '<circle cx="45" cy="31" r="2" fill="{D}" stroke="none"/><circle cx="55" cy="31" r="2" fill="{D}" stroke="none"/>'),
    'consejero': ('<path d="M36 40 Q35 19 50 17 Q65 19 64 40 Z" fill="{F}"/>'
                  '<path d="M50 17 Q56 4 68 6 Q60 11 53 19" fill="{F}"/>'
                  '<path d="M38 31 L62 31" fill="none" stroke="{D}" stroke-width="1.8"/>'),
    'resorte': ('<rect x="38" y="35" width="24" height="5" rx="2" fill="{F}"/>'
                '<path d="M42 35 L58 29 L42 23 L58 17 L42 11 L58 5" fill="none" stroke="{S}" stroke-width="3.6"/>'),
    'mago': ('<ellipse cx="50" cy="38" rx="20" ry="4" fill="{F}"/><path d="M36 37 L52 4 L64 37 Z" fill="{F}"/>'
             '<circle cx="51" cy="22" r="2.6" fill="{D}" stroke="none"/>'),
    'arquero': ('<path d="M38 7 Q72 23 38 39" fill="none" stroke="{S}" stroke-width="4"/>'
                '<path d="M38 7 Q72 23 38 39" fill="none" stroke="{F}" stroke-width="1.6"/>'
                '<path d="M38 7 L38 39" fill="none" stroke="{S}" stroke-width="1.4"/>'
                '<path d="M30 23 L66 23" fill="none" stroke="{S}" stroke-width="2"/><path d="M66 23 L60 19 L60 27 Z" fill="{F}"/>'),
    'ojo': ('<path d="M28 26 Q50 6 72 26 Q50 46 28 26 Z" fill="{F}"/><circle cx="50" cy="26" r="7" fill="{D}" stroke="none"/>'
            '<rect x="45" y="37" width="10" height="4" fill="{F}"/>'),
    'lanza': ('<rect x="47" y="16" width="6" height="25" fill="{F}"/><path d="M50 2 L58 18 L42 18 Z" fill="{F}"/>'
              '<rect x="42" y="22" width="16" height="4" rx="1" fill="{F}"/>'),
    'llama': ('<path d="M50 4 Q65 20 61 32 Q59 41 50 41 Q40 41 38 31 Q36 21 46 13 Q46 23 52 25 Q55 16 50 4 Z" fill="{F}"/>'),
    'rayo': '<path d="M55 3 L37 25 L49 25 L43 41 L65 17 L53 17 Z" fill="{F}"/>',
    'estrella': ('<rect x="45" y="33" width="10" height="8" fill="{F}"/><polygon points="50,4 55,16 68,17 58,25 61,37 50,31 '
                 '39,37 42,25 32,17 45,16" fill="{F}"/>'),
    'yelmo': ('<path d="M36 40 L36 22 Q36 8 50 8 Q64 8 64 22 L64 40 Z" fill="{F}"/>'
              '<path d="M40 24 L60 24 M50 24 L50 34" fill="none" stroke="{D}" stroke-width="2.4"/>'),
    'diamante': '<path d="M50 4 L66 22 L50 40 L34 22 Z" fill="{F}"/><path d="M34 22 L66 22" fill="none" stroke="{D}" stroke-width="1.6"/>',
}
# remates de las piezas mágicas (el catálogo de Juego/piezas_magicas.py)
LUNA_PEQ = '<path d="M72 4 A9 9 0 1 0 80 18 A7 7 0 1 1 72 4 Z" fill="{F}"/>'
OREJA = '<path d="M47 14 L49 6 L53 13 Z" fill="{F}"/>'
REMATES_MAGICOS = {
    'turbante': ('<path d="M33 40 Q30 21 50 17 Q70 21 67 40 Z" fill="{F}"/>'
                 '<path d="M35 31 Q50 23 65 31 M34 37 Q50 29 66 37" fill="none" stroke="{D}" stroke-width="1.8"/>'
                 '<path d="M50 17 Q47 8 53 4 Q52 10 56 12 Q53 14 50 17 Z" fill="{F}"/><circle cx="50" cy="25" r="2.6" fill="{D}" stroke="none"/>'),
    'torre_asedio': ('<path d="M38 41 L40 12 L60 12 L62 41 Z" fill="{F}"/><path d="M36 13 L36 5 L42 5 L42 9 L47 9 L47 5 L53 5 '
                     'L53 9 L58 9 L58 5 L64 5 L64 13 Z" fill="{F}"/>'
                     '<path d="M41 20 L59 20 M41 28 L59 28 M41 35 L59 35" fill="none" stroke="{D}" stroke-width="1.6"/>'
                     '<path d="M60 25 L72 25" fill="none" stroke="{S}" stroke-width="4"/>'),
    'lampara': ('<path d="M30 34 Q30 25 46 25 L58 25 Q66 25 74 18 Q72 30 62 34 Z" fill="{F}"/>'
                '<path d="M30 30 Q22 30 24 22 Q26 18 32 22" fill="none" stroke="{S}" stroke-width="3"/>'
                '<rect x="40" y="34" width="20" height="7" rx="2" fill="{F}"/><path d="M50 25 Q50 18 54 16 Q52 21 56 22 Z" fill="{F}"/>'
                '<path d="M46 21 L58 21" fill="none" stroke="{S}" stroke-width="2.4"/>'),
    'tres_bolas': ('<rect x="46" y="35" width="8" height="6" fill="{F}"/><circle cx="50" cy="30" r="6" fill="{F}"/>'
                   '<circle cx="50" cy="18" r="5.5" fill="{F}"/><circle cx="50" cy="7" r="5" fill="{F}"/>'),
    'tres_diagonal': ('<rect x="44" y="35" width="12" height="6" fill="{F}"/><circle cx="40" cy="29" r="6" fill="{F}"/>'
                      '<circle cx="51" cy="18" r="5.5" fill="{F}"/><circle cx="62" cy="7" r="5" fill="{F}"/>'),
    'cebra': (CABEZA_CABALLO + '<path d="M44 34 L50 28 M43 27 L50 21 M47 19 L52 15 M56 35 L62 31 M58 40 L65 34" fill="none" '
              'stroke="{S}" stroke-width="2.2"/>'),
    'jirafa': ('<path d="M41 41 L46 18 L44 10 Q48 4 56 6 L64 9 Q66 13 60 14 L54 15 L52 41 Z" fill="{F}"/>'
               '<path d="M47 6 L46 1 M52 5 L52 0" fill="none" stroke="{S}" stroke-width="2.4"/><circle cx="46" cy="0.8" r="1.6" fill="{F}"/>'
               '<circle cx="52" cy="0.2" r="1.6" fill="{F}"/><circle cx="57" cy="10" r="1.5" fill="{D}" stroke="none"/>'
               '<circle cx="48" cy="27" r="2" fill="{D}" stroke="none"/><circle cx="49" cy="35" r="2" fill="{D}" stroke="none"/>'
               '<circle cx="49" cy="20" r="1.6" fill="{D}" stroke="none"/>'),
    'antilope': ('<path d="M42 41 Q40 30 44 24 Q42 16 50 14 Q58 16 56 24 Q60 30 58 41 Z" fill="{F}"/>'
                 '<path d="M46 16 Q38 8 36 1 M54 16 Q62 8 64 1" fill="none" stroke="{S}" stroke-width="3.2"/>'
                 '<circle cx="46" cy="24" r="1.6" fill="{D}" stroke="none"/><circle cx="54" cy="24" r="1.6" fill="{D}" stroke="none"/>'),
    'nu': ('<path d="M40 41 Q38 30 42 22 Q44 14 50 14 Q56 14 58 22 Q62 30 60 41 Z" fill="{F}"/>'
           '<path d="M43 18 Q30 18 30 8 Q33 12 40 14 M57 18 Q70 18 70 8 Q67 12 60 14" fill="{F}"/>'
           '<path d="M46 34 Q50 41 54 34" fill="none" stroke="{D}" stroke-width="1.8"/>'
           '<circle cx="45" cy="24" r="1.6" fill="{D}" stroke="none"/><circle cx="55" cy="24" r="1.6" fill="{D}" stroke="none"/>'),
    'bisonte': ('<path d="M30 41 Q26 28 34 20 Q40 10 52 12 Q66 14 68 26 Q70 36 64 41 Z" fill="{F}"/>'
                '<path d="M36 18 Q30 14 31 8 Q35 13 40 14 M62 16 Q68 12 67 6 Q63 11 58 13" fill="{F}"/>'
                '<circle cx="45" cy="26" r="1.8" fill="{D}" stroke="none"/><circle cx="57" cy="26" r="1.8" fill="{D}" stroke="none"/>'
                '<path d="M44 34 Q51 38 58 34" fill="none" stroke="{D}" stroke-width="1.8"/>'),
    'okapi': (CABEZA_CABALLO + OREJA + '<path d="M42 39 L48 35 M42 34 L47 30" fill="none" stroke="{S}" stroke-width="2.2"/>'),
    'bufalo': ('<path d="M38 41 Q36 30 42 24 Q46 20 50 20 Q54 20 58 24 Q64 30 62 41 Z" fill="{F}"/>'
               '<path d="M42 24 Q26 26 22 12 Q30 20 44 19 M58 24 Q74 26 78 12 Q70 20 56 19" fill="{F}"/>'
               '<circle cx="45" cy="29" r="1.6" fill="{D}" stroke="none"/><circle cx="55" cy="29" r="1.6" fill="{D}" stroke="none"/>'),
    'ardilla': ('<path d="M56 41 Q74 38 70 20 Q68 6 56 8 Q64 14 62 24 Q60 34 52 36 Z" fill="{F}"/>'
                '<path d="M34 41 Q32 30 38 24 Q36 16 42 14 L44 9 L47 15 Q52 18 50 26 Q54 34 50 41 Z" fill="{F}"/>'
                '<circle cx="44" cy="20" r="1.6" fill="{D}" stroke="none"/>'),
    'kirin': ('<path d="M40 41 Q38 30 44 23 L42 14 Q50 11 56 15 Q64 18 66 26 L60 29 Q58 35 60 41 Z" fill="{F}"/>'
              '<path d="M47 13 L52 1 L52 13 Z" fill="{F}"/><path d="M40 22 Q34 26 36 32 M38 30 Q32 34 34 40" fill="none" '
              'stroke="{S}" stroke-width="2.4"/><circle cx="56" cy="20" r="1.8" fill="{D}" stroke="none"/>'),
    'fenix': ('<path d="M44 41 Q42 30 46 24 Q44 16 50 12 Q56 16 54 24 Q58 30 56 41 Z" fill="{F}"/>'
              '<path d="M46 26 Q30 22 26 6 Q36 16 46 20 Z M54 26 Q70 22 74 6 Q64 16 54 20 Z" fill="{F}"/>'
              '<path d="M50 12 Q46 6 50 1 Q50 6 54 6 Q52 9 50 12" fill="{F}"/><circle cx="48" cy="17" r="1.4" fill="{D}" stroke="none"/>'
              '<path d="M54 15 L60 16 L54 18" fill="{F}"/>'),
    'centauro': (CABEZA_CABALLO + '<rect x="46" y="1" width="5" height="11" fill="{F}"/><rect x="43" y="3.5" width="11" height="4.5" fill="{F}"/>'),
    'nocturno': (LUNA_PEQ + CABEZA_CABALLO),
    'camello_luna': (REMATES['camello'] + '<path d="M26 4 A8 8 0 1 0 33 17 A6 6 0 1 1 26 4 Z" fill="{F}"/>'),
    'cebra_luna': (LUNA_PEQ + CABEZA_CABALLO + '<path d="M44 34 L50 28 M43 27 L50 21 M56 35 L62 31" fill="none" stroke="{S}" '
                   'stroke-width="2.2"/>'),
    'bede': ('<path d="M50 9 Q70 25 62 40 L38 40 Q30 25 50 9 Z" fill="{F}"/><circle cx="50" cy="7" r="4" fill="{F}"/>'
             '<path d="M42 30 L58 30 M50 22 L50 38" fill="none" stroke="{D}" stroke-width="2"/>'),
    'varano': ('<path d="M30 40 Q34 30 44 30 L58 28 Q66 22 72 24 L76 22 L74 28 Q68 32 60 34 L46 38 Q40 42 30 40 Z" fill="{F}"/>'
               '<path d="M30 40 Q22 36 24 26 Q26 20 32 22 Q28 26 30 32" fill="none" stroke="{S}" stroke-width="3"/>'
               '<path d="M44 30 L40 24 M54 29 L52 22 M46 37 L44 41 M58 33 L60 38" fill="none" stroke="{S}" stroke-width="2.6"/>'
               '<circle cx="70" cy="25" r="1.2" fill="{D}" stroke="none"/>'),
    'emperatriz': (CABEZA_CABALLO + '<path d="M40 16 L40 6 L44 10 L48 3 L52 10 L56 6 L56 16 Z" fill="{F}"/>'),
    'princesa': (CABEZA_CABALLO + '<path d="M42 15 Q48 8 56 13" fill="none" stroke="{S}" stroke-width="3"/>'
                 '<circle cx="49" cy="8" r="2.4" fill="{F}"/>'),
    'caballo_alado': (CABEZA_CABALLO + '<path d="M60 26 Q72 16 80 20 Q74 22 76 28 Q70 26 70 32 Q66 28 62 32 Z" fill="{F}"/>'),
    'caballo_corona': (CABEZA_CABALLO + '<path d="M41 15 L40 5 L45 10 L48 2 L51 10 L56 5 L55 15 Z" fill="{F}"/>'),
    'insecto': ('<ellipse cx="50" cy="28" rx="7" ry="12" fill="{F}"/><circle cx="50" cy="13" r="5" fill="{F}"/>'
                '<path d="M45 32 L32 20 L30 40 M55 32 L68 20 L70 40" fill="none" stroke="{S}" stroke-width="3"/>'
                '<path d="M47 9 Q42 2 36 2 M53 9 Q58 2 64 2" fill="none" stroke="{S}" stroke-width="2"/>'
                '<path d="M45 24 L55 24 M45 31 L55 31" fill="none" stroke="{D}" stroke-width="1.4"/>'),
    'resorte_torre': ('<rect x="38" y="36" width="24" height="5" rx="2" fill="{F}"/>'
                      '<path d="M42 36 L58 31 L42 26 L58 21" fill="none" stroke="{S}" stroke-width="3.4"/>'
                      '<path d="M38 21 L38 6 L43 6 L43 11 L48 11 L48 6 L52 6 L52 11 L57 11 L57 6 L62 6 L62 21 Z" fill="{F}"/>'),
    'resorte_mitra': ('<rect x="38" y="36" width="24" height="5" rx="2" fill="{F}"/>'
                      '<path d="M42 36 L58 31 L42 26 L58 21" fill="none" stroke="{S}" stroke-width="3.4"/>'
                      '<path d="M50 4 Q62 13 58 21 L42 21 Q38 13 50 4 Z" fill="{F}"/>'),
    'leon': ('<circle cx="50" cy="24" r="16" fill="{F}"/>'
             '<path d="M34 24 L28 20 L34 18 L30 12 L37 13 L36 6 L42 10 L45 3 L50 8 L55 3 L58 10 L64 6 L63 13 L70 12 L66 18 '
             'L72 20 L66 24" fill="{F}"/><circle cx="50" cy="26" r="9" fill="{F}"/>'
             '<circle cx="46" cy="24" r="1.6" fill="{D}" stroke="none"/><circle cx="54" cy="24" r="1.6" fill="{D}" stroke="none"/>'
             '<path d="M47 30 L50 32 L53 30" fill="none" stroke="{D}" stroke-width="1.6"/>'),
    'vao': ('<path d="M32 36 L58 8 L66 15 L40 41 Z" fill="{F}"/><rect x="58" y="4" width="8" height="12" rx="2" '
            'transform="rotate(45 62 10)" fill="{F}"/><circle cx="40" cy="34" r="7" fill="{F}"/>'
            '<path d="M40 27 L40 41 M33 34 L47 34" fill="none" stroke="{D}" stroke-width="1.6"/>'),
    'leo': ('<path d="M30 32 L64 16 L69 25 L35 41 Z" fill="{F}"/><rect x="64" y="15" width="7" height="11" rx="2" '
            'transform="rotate(-25 67 20)" fill="{F}"/><circle cx="42" cy="36" r="5" fill="{F}"/>'
            '<path d="M38 18 L36 6 L42 12 L46 3 L50 12 L56 6 L54 18 Z" fill="{F}"/>'),
    'langosta': ('<ellipse cx="50" cy="29" rx="6" ry="12" fill="{F}"/><circle cx="50" cy="14" r="5" fill="{F}"/>'
                 '<path d="M46 22 Q28 14 26 30 Q36 26 46 28 Z M54 22 Q72 14 74 30 Q64 26 54 28 Z" fill="{F}"/>'
                 '<path d="M47 10 Q44 2 38 1 M53 10 Q56 2 62 1" fill="none" stroke="{S}" stroke-width="2"/>'),
    'mao': ('<circle cx="50" cy="24" r="16" fill="{F}"/><circle cx="50" cy="24" r="12" fill="none" stroke="{D}" stroke-width="1.6"/>'
            '<path d="M43 34 Q42 26 46 20 L47 14 L51 19 Q58 20 59 27 L55 30 L52 34 Z" fill="{D}" stroke="none"/>'),
    'moa': ('<path d="M38 41 Q34 30 44 28 L50 28 L52 14 Q52 6 58 6 Q64 6 66 10 L60 11 L57 14 L56 30 Q62 34 58 41 Z" fill="{F}"/>'
            '<circle cx="58" cy="9" r="1.4" fill="{D}" stroke="none"/>'),
    'elefante_disco': ('<circle cx="50" cy="24" r="16" fill="{F}"/><circle cx="50" cy="24" r="12" fill="none" stroke="{D}" stroke-width="1.6"/>'
                       '<circle cx="50" cy="22" r="6" fill="{D}" stroke="none"/><ellipse cx="42" cy="22" rx="3.5" ry="5" fill="{D}" stroke="none"/>'
                       '<ellipse cx="58" cy="22" rx="3.5" ry="5" fill="{D}" stroke="none"/><path d="M49 26 Q48 33 51 34" fill="none" stroke="{D}" stroke-width="2.4"/>'),
    'grifo': ('<path d="M40 41 Q36 28 44 20 Q46 10 56 10 Q64 11 66 16 L74 20 L66 22 Q64 28 58 30 L58 41 Z" fill="{F}"/>'
              '<path d="M44 26 Q30 20 28 6 Q36 12 46 16 Z" fill="{F}"/><circle cx="58" cy="16" r="1.8" fill="{D}" stroke="none"/>'),
    'aanca': ('<path d="M42 41 Q40 30 46 24 Q44 14 52 12 Q60 12 62 18 L70 19 L62 22 Q60 28 56 30 L56 41 Z" fill="{F}"/>'
              '<path d="M44 30 Q30 30 26 16 Q34 22 44 24 M44 36 Q28 38 22 26 Q32 32 44 32" fill="{F}"/>'
              '<path d="M52 12 Q50 4 56 2 Q54 7 58 9" fill="{F}"/><circle cx="55" cy="17" r="1.6" fill="{D}" stroke="none"/>'),
    'rosa': ('<rect x="47" y="30" width="6" height="11" fill="{F}"/><path d="M53 35 Q62 30 64 36 Q58 40 53 37 Z" fill="{F}"/>'
             '<circle cx="50" cy="18" r="13" fill="{F}"/>'
             '<path d="M50 18 m-6 0 a6 6 0 1 0 6 -6 a3 3 0 1 1 -3 3 M44 13 Q50 6 58 12 M42 22 Q48 30 58 25" fill="none" '
             'stroke="{D}" stroke-width="1.6"/>'),
    'khon': ('<path d="M36 41 L64 41 L60 34 L40 34 Z M40 34 L60 34 L56 26 L44 26 Z M44 26 L56 26 L53 17 L47 17 Z" fill="{F}"/>'
             '<path d="M47 17 L53 17 L50 2 Z" fill="{F}"/>'),
    'teja_oro': ('<path d="M38 41 L36 16 L50 6 L64 16 L62 41 Z" fill="{F}"/>'
                 '<path d="M43 20 L57 20 M50 20 L50 36 M42 28 L58 28 M41 36 L59 36" fill="none" stroke="{D}" stroke-width="2"/>'),
    'teja_caballo': ('<path d="M38 41 L36 16 L50 6 L64 16 L62 41 Z" fill="{F}"/>'
                     '<path d="M44 37 Q43 30 46 24 L47 19 L50 23 Q56 24 57 29 L53 31 L51 37 Z" fill="{D}" stroke="none"/>'),
    'corneta': ('<path d="M30 30 Q30 14 50 14 Q66 14 66 26 Q66 34 56 34 Q48 34 48 26 Q48 20 54 20" fill="none" stroke="{S}" stroke-width="6"/>'
                '<path d="M30 30 Q30 14 50 14 Q66 14 66 26 Q66 34 56 34 Q48 34 48 26 Q48 20 54 20" fill="none" stroke="{F}" stroke-width="2.4"/>'
                '<path d="M24 41 L36 26 L40 30 Z" fill="{F}"/><rect x="45" y="35" width="10" height="6" fill="{F}"/>'),
    'discos': ('<rect x="46" y="36" width="8" height="5" fill="{F}"/><ellipse cx="50" cy="30" rx="18" ry="6" fill="{F}"/>'
               '<ellipse cx="50" cy="23" rx="18" ry="6" fill="{F}"/><ellipse cx="50" cy="23" rx="10" ry="3" fill="none" '
               'stroke="{D}" stroke-width="1.4"/>'),
}
# ---------------------------------------------------------------------- estilos Staunton (Rey, Dama, Arzobispo, Canciller)
# cuerpo Staunton: base acampanada, anillo y collar
CUERPO_STAUNTON = ('<path d="M26 84 Q26 76 35 74 Q39 72 40.5 65 Q42.5 56 43 50 L57 50 Q57.5 56 59.5 65 Q61 72 65 74 Q74 76 74 84 Z" fill="{F}"/>'
          '<path d="M32 76 Q50 80 68 76" fill="none" stroke="{D}" stroke-width="1.6"/>'
          '<ellipse cx="50" cy="49" rx="13" ry="3.6" fill="{F}"/>')
CUELLO_STAUNTON = '<path d="M44 47 Q45.5 41 46.5 37 L53.5 37 Q54.5 41 56 47 Z" fill="{F}"/>'
_STAUNTON = {
    # ---- Rey
    'rey_1': CUERPO_STAUNTON + '<path d="M43 47 Q38 36 35 27 L65 27 Q62 36 57 47 Z" fill="{F}"/><ellipse cx="50" cy="27" rx="15.5" ry="3.4" fill="{F}"/>'
             '<path d="M47 24 L47 15 L41.5 15 L41.5 9.5 L47 9.5 L47 3.5 L53 3.5 L53 9.5 L58.5 9.5 L58.5 15 L53 15 L53 24 Z" fill="{F}"/>',
    'rey_2': CUERPO_STAUNTON + '<path d="M43 47 Q39 38 37 30 L63 30 Q61 38 57 47 Z" fill="{F}"/><ellipse cx="50" cy="30" rx="13.5" ry="3" fill="{F}"/>'
             '<path d="M39 29 Q39 18 50 17 Q61 18 61 29 Z" fill="{F}"/><circle cx="50" cy="15" r="3.4" fill="{F}"/>'
             '<path d="M48 13 L48 8 L44 8 L44 4.5 L48 4.5 L48 1 L52 1 L52 4.5 L56 4.5 L56 8 L52 8 L52 13 Z" fill="{F}"/>',
    'rey_3': CUERPO_STAUNTON + CUELLO_STAUNTON + '<path d="M36 37 L34 22 Q42 26 46 20 Q50 14 54 20 Q58 26 66 22 L64 37 Z" fill="{F}"/>'
             '<path d="M37 31 L63 31" fill="none" stroke="{D}" stroke-width="1.6"/><circle cx="50" cy="15" r="4.6" fill="{F}"/>'
             '<path d="M48.5 11 L48.5 6 L45 6 L45 3 L48.5 3 L48.5 0.5 L51.5 0.5 L51.5 3 L55 3 L55 6 L51.5 6 L51.5 11 Z" fill="{F}"/>',
    # ---- Dama
    'dama_1': CUERPO_STAUNTON + '<path d="M43 47 Q38 36 35 25 L65 25 Q62 36 57 47 Z" fill="{F}"/>'
              '<path d="M35 26 L33 17 L38.5 21 L41 15 L45 20.5 L50 14 L55 20.5 L59 15 L61.5 21 L67 17 L65 26 Z" fill="{F}"/>'
              '<ellipse cx="50" cy="26" rx="15" ry="3" fill="{F}"/><circle cx="50" cy="10" r="5" fill="{F}"/>',
    'dama_2': CUERPO_STAUNTON + '<path d="M43 47 Q38 36 36 27 L64 27 Q62 36 57 47 Z" fill="{F}"/><ellipse cx="50" cy="27" rx="14.5" ry="3" fill="{F}"/>'
              '<path d="M36 27 L31 12 L41 21 L44 8 L50 20 L56 8 L59 21 L69 12 L64 27 Z" fill="{F}"/>'
              '<circle cx="31" cy="10" r="3.2" fill="{F}"/><circle cx="44" cy="6" r="3.2" fill="{F}"/><circle cx="56" cy="6" r="3.2" fill="{F}"/>'
              '<circle cx="69" cy="10" r="3.2" fill="{F}"/><circle cx="50" cy="16" r="3" fill="{F}"/>',
    'dama_3': CUERPO_STAUNTON + '<path d="M43 47 Q39 38 37 30 L63 30 Q61 38 57 47 Z" fill="{F}"/><ellipse cx="50" cy="30" rx="13.5" ry="3" fill="{F}"/>'
              '<path d="M38 29 Q37 16 50 14 Q63 16 62 29 Z" fill="{F}"/>'
              '<path d="M40 22 Q50 18 60 22 M44 15.5 L44 28 M56 15.5 L56 28 M50 14 L50 28" fill="none" stroke="{D}" stroke-width="1.5"/>'
              '<circle cx="50" cy="9" r="4.6" fill="{F}"/>',
    # ---- Arzobispo (como la pieza 3D: copa en media luna con una bola)
    'arzobispo_1': CUERPO_STAUNTON + CUELLO_STAUNTON + '<path d="M27 13 Q27 39 50 39 Q73 39 73 13 Q66 25 50 25 Q34 25 27 13 Z" fill="{F}"/>'
                   '<path d="M33 31 Q50 37 67 31" fill="none" stroke="{D}" stroke-width="1.5"/>'
                   '<path d="M46.5 25.5 Q47 21 48 20 L52 20 Q53 21 53.5 25.5 Z" fill="{F}"/><circle cx="50" cy="15.5" r="5.2" fill="{F}"/>',
    'arzobispo_2': CUERPO_STAUNTON + CUELLO_STAUNTON + '<path d="M31 13 Q31 36 50 38 Q69 36 69 13 Q62 26 50 26 Q38 26 31 13 Z" fill="{F}"/>'
                   '<path d="M50 26 Q42 18 50 6 Q58 18 50 26 Z" fill="{F}"/><path d="M50 12 L53 19" fill="none" stroke="{D}" stroke-width="1.6"/>',
    'arzobispo_3': CUERPO_STAUNTON + CUELLO_STAUNTON + '<path d="M29 15 Q31 37 50 38 Q69 37 71 15 Q63 27 50 27 Q37 27 29 15 Z" fill="{F}"/>'
                   '<path d="M43 27 Q42 19 46 14 L47 8 L50 12 Q57 13 58 19 L55 21 L53 27 Z" fill="{F}"/>'
                   '<circle cx="51.5" cy="16" r="1.4" fill="{D}" stroke="none"/>',
    # ---- Canciller
    'canciller_1': CUERPO_STAUNTON + '<path d="M40 48 L40 26 L60 26 L60 48 Z" fill="{F}"/>'
                   '<path d="M37 27 L37 17 L42.5 17 L42.5 21 L47 21 L47 17 L53 17 L53 21 L57.5 21 L57.5 17 L63 17 L63 27 Z" fill="{F}"/>'
                   '<path d="M47 17 Q47 11 50 10 Q53 11 53 17" fill="{F}"/><circle cx="50" cy="7" r="4.4" fill="{F}"/>',
    'canciller_2': CUERPO_STAUNTON + CUELLO_STAUNTON + '<path d="M35 38 L33 24 Q50 30 67 24 L65 38 Z" fill="{F}"/>'
                   '<path d="M33 24 L33 14 L39 14 L39 19 L45 19 L45 14 L55 14 L55 19 L61 19 L61 14 L67 14 L67 24 Q50 30 33 24 Z" fill="{F}"/>'
                   '<path d="M47 14 L47 9 L53 9 L53 14 Z" fill="{F}"/><circle cx="50" cy="6" r="3.8" fill="{F}"/>',
    'canciller_3': CUERPO_STAUNTON + '<path d="M40 48 L40 26 L60 26 L60 48 Z" fill="{F}"/>'
                   '<path d="M37 27 L37 17 L42.5 17 L42.5 21 L47 21 L47 17 L53 17 L53 21 L57.5 21 L57.5 17 L63 17 L63 27 Z" fill="{F}"/>'
                   '<path d="M43 18 Q42 11 46 6 L47 1 L50 5 Q57 6 58 12 L55 14 L53 18 Z" fill="{F}"/>'
                   '<circle cx="51.5" cy="9" r="1.4" fill="{D}" stroke="none"/>',
}
# el Arzobispo del juego (desde octubre de 2026): como la pieza 3D de Capablanca, copa gruesa en media luna con una
# bola en el centro, sobre un cuerpo alto con base ancha escalonada y collar con un aro debajo
CUERPO_ALTO = ('<path d="M24 84 Q24 78 31 77 L31 76 Q38 74 40 66 Q42 57 43.5 51 L56.5 51 Q58 57 60 66 Q62 74 69 76 L69 77 '
               'Q76 78 76 84 Z" fill="{F}"/><path d="M30 79.5 L70 79.5" fill="none" stroke="{D}" stroke-width="1.5"/>'
               '<ellipse cx="50" cy="51" rx="9" ry="2.6" fill="{F}"/><ellipse cx="50" cy="47.5" rx="14" ry="3.6" fill="{F}"/>')
ARZOBISPO = (CUERPO_ALTO + '<path d="M44.5 46 Q46 41 46.5 38 L53.5 38 Q54 41 55.5 46 Z" fill="{F}"/>'
             '<path d="M27 14 Q26 39 50 39.5 Q74 39 73 14 Q68 26 50 27 Q32 26 27 14 Z" fill="{F}"/>'
             '<path d="M47 27 Q47.5 23 48.3 22 L51.7 22 Q52.5 23 53 27 Z" fill="{F}"/><circle cx="50" cy="17" r="5.6" fill="{F}"/>')
# el Arzobispo anterior (media luna sobre un cuerpo recto): queda como estilo «Media luna anterior»
ARZOBISPO_ANTERIOR = ('<path d="M33 84 L38 46 L62 46 L67 84 Z" fill="{F}"/><rect x="34" y="40" width="32" height="7" rx="2" '
                      'fill="{F}"/><rect x="45" y="29" width="10" height="12" fill="{F}"/>'
                      '<path d="M31 10 A19 19 0 0 0 69 10 A23 15 0 0 1 31 10 Z" fill="{F}"/>')
# estilo -> {pieza: dibujo}: Staunton 1, 2 y 3 (Ajustes > Piezas)
STAUNTON = {'staunton%d' % k: {p: _STAUNTON['%s_%d' % (p, k)] for p in ('rey', 'dama', 'arzobispo', 'canciller')}
            for k in (1, 2, 3)}

# ---------------------------------------------------------------------- estilo «Diagrama»
# Las piezas de los diagramas de los libros (contorno fino; el Arzobispo, Caballo sobre el pie del Alfil; el
# Canciller, Caballo sobre una Torre invertida). En coordenadas de 45 × 45; el Caballo y el Alfil siguen el juego de
# Colin M. L. Burnett (licencia BSD; ver LEEME.txt). {F} relleno, {L} contorno, {d} detalles, {m} crin (solo negras).
COLORES_DIAGRAMA = {'blancas': {'F': '#FFFFFF', 'L': '#000000', 'd': '#000000', 'm': 'none'},
                    'negras': {'F': '#000000', 'L': '#000000', 'd': '#FFFFFF', 'm': '#FFFFFF'}}
# Caballo de diagrama (mirando a la izquierda): orejas, ojo, ollar, boca y crin
CABALLO_DIAGRAMA = ('<path d="M22 10 C32.5 11 38.5 18 38 39 L15 39 C15 30 25 32.5 23 18" fill="{F}"/>'
           '<path d="M24 18 C24.4 20.9 18.6 25.4 16 27 C13 29 13.2 31.3 11 31 C10 30.1 12.4 28 11 28 C10 28 11.2 29.2 10 30 '
           'C9 30 5.9 31 6 26 C6 24 12 14 12 14 C12 14 13.9 12.1 14 10.5 C13.3 9.5 13.5 8.5 13.5 7.5 C14.5 6.5 16.5 10 16.5 10 '
           'L18.5 10 C18.5 10 19.3 8 21 7 C22 7 22 10 22 10" fill="{F}"/>'
           '<path d="M9.5 25.5 A0.5 0.5 0 1 1 8.5 25.5 A0.5 0.5 0 1 1 9.5 25.5 Z" fill="{d}" stroke="{d}"/>'
           '<path d="M15 15.5 A0.5 1.5 0 1 1 14 15.5 A0.5 1.5 0 1 1 15 15.5 Z" transform="matrix(0.866 0.5 -0.5 0.866 9.693 -5.173)" '
           'fill="{d}" stroke="{d}"/>'
           '<path d="M24.55 10.4 L24.1 11.85 L24.6 12 C27.75 13 30.25 14.49 32.5 18.75 C34.75 23.01 35.75 29.06 35.25 39 '
           'L35.2 39.5 L37.45 39.5 L37.5 39 C38 28.94 36.62 22.15 34.25 17.66 C31.88 13.17 28.46 11.02 25.06 10.5 Z" '
           'fill="{m}" stroke="none"/>')


def _cabeza_diagrama(dx, dy, s, base=33):
    """El Caballo, más pequeño y cortado en 'base', para el Arzobispo y el Canciller."""
    return ('<g transform="translate(%g %g) scale(%g)">' % (dx, dy, s) +
            '<path d="M22 10 C32.5 11 38.5 18 38 %d L15 %d C15 30 25 32.5 23 18" fill="{F}"/>' % (base, base) +
            CABALLO_DIAGRAMA.split('</path>')[0].split('<path d="M22 10 C32.5 11 38.5 18 38 39 L15 39 C15 30 25 32.5 23 18" fill="{F}"/>')[1] +
            '</g>')


# pie del Alfil: cinta ondulada, larga y delgada
CINTA_DIAGRAMA = ('<path d="M6.5 38 C10 36 15 36.8 18.5 36.6 C20.5 36.4 21.8 35.6 22.5 34.8 C23.2 35.6 24.5 36.4 26.5 36.6 '
         'C30 36.8 35 36 38.5 38 C38.5 39 37.8 39.6 37 39.2 C33.5 38 30 38.6 26.5 38.6 C24.5 38.6 23.3 38.1 22.5 37.4 '
         'C21.7 38.1 20.5 38.6 18.5 38.6 C15 38.6 11.5 38 8 39.2 C7.2 39.6 6.5 39 6.5 38 Z" fill="{F}"/>')
# Torre invertida (pie del Canciller), baja: la placa arriba, del mismo ancho que la base del Caballo que encaja en
# ella (x 12.75 a 32.25 con el Caballo a escala 0.85, centrado en 22.5), un cuerpo corto y las almenas en el suelo
TORRE_INVERTIDA_DIAGRAMA = ('<path d="M12.75 31.5 L32.25 31.5 L32.25 33.5 L12.75 33.5 Z" fill="{F}"/>'
                   '<path d="M14.8 33.5 L30.2 33.5 L29.9 36 L15.1 36 Z" fill="{F}"/>'
                   '<path d="M15.1 36 L13.5 36.8 L13.5 39 L16.8 39 L16.8 37.8 L20.8 37.8 L20.8 39 L24.2 39 L24.2 37.8 '
                   'L28.2 37.8 L28.2 39 L31.5 39 L31.5 36.8 L29.9 36 Z" fill="{F}"/>'
                   '<path d="M13.7 32.5 L31.3 32.5 M14.4 36.7 L30.6 36.7" fill="none" stroke="{d}" stroke-width="0.8"/>')
DIAGRAMA = {
    'peon': ('<path d="M17.5 21.5 Q19.5 20 22.5 20 Q25.5 20 27.5 21.5 Q25 23.5 25.5 28 Q30 31 31.5 38 L13.5 38 Q15 31 19.5 28 '
             'Q20 23.5 17.5 21.5 Z" fill="{F}"/><circle cx="22.5" cy="14" r="5" fill="{F}"/>'),
    'torre': ('<path d="M9 39 L36 39 L36 36 L9 36 Z" fill="{F}"/><path d="M12 36 L12 32 L33 32 L33 36 Z" fill="{F}"/>'
              '<path d="M14 32 L14.5 17 L30.5 17 L31 32 Z" fill="{F}"/>'
              '<path d="M14.5 17 L11 14 L11 9 L15 9 L15 11 L20 11 L20 9 L25 9 L25 11 L30 11 L30 9 L34 9 L34 14 L30.5 17 Z" fill="{F}"/>'
              '<path d="M12 14 L33 14 M14.5 29.5 L30.5 29.5" fill="none" stroke="{d}" stroke-width="1"/>'),
    'alfil': (CINTA_DIAGRAMA + '<path d="M15 32 C17.5 34.5 27.5 34.5 30 32 C30.5 30.5 30 30 30 30 C30 27.5 27.5 26 27.5 26 '
              'C33 24.5 33.5 14.5 22.5 10.5 C11.5 14.5 12 24.5 17.5 26 C17.5 26 15 27.5 15 30 C15 30 14.5 30.5 15 32 Z" fill="{F}"/>'
              '<circle cx="22.5" cy="8" r="2.5" fill="{F}"/>'
              '<path d="M17.5 26 L27.5 26 M15 30 L30 30 M22.5 15.5 L22.5 20.5 M20 18 L25 18" fill="none" stroke="{d}" stroke-width="1"/>'),
    'caballo': CABALLO_DIAGRAMA,
    'dama': ('<path d="M9 26 L6.5 13.5 L14 24.5 L14.5 10.5 L19.5 24 L22.5 10 L25.5 24 L30.5 10.5 L31 24.5 L38.5 13.5 L36 26 '
             'C29 24.5 16 24.5 9 26 Z" fill="{F}"/>'
             '<circle cx="6" cy="12" r="2.4" fill="{F}"/><circle cx="14" cy="9" r="2.4" fill="{F}"/><circle cx="22.5" cy="8" r="2.4" fill="{F}"/>'
             '<circle cx="31" cy="9" r="2.4" fill="{F}"/><circle cx="39" cy="12" r="2.4" fill="{F}"/>'
             '<path d="M9 26 C9.5 28.5 11 29 11.5 31 C11 33 10.5 34.5 11 36 C10 37.3 11 38.5 11 38.5 C17.5 39.7 27.5 39.7 34 38.5 '
             'C34 38.5 35 37.3 34 36 C34.5 34.5 34 33 33.5 31 C34 29 35.5 28.5 36 26 C29 24.5 16 24.5 9 26 Z" fill="{F}"/>'
             '<path d="M11.5 31 C17.5 29.5 27.5 29.5 33.5 31 M11 36 C17.5 34.8 27.5 34.8 34 36" fill="none" stroke="{d}" stroke-width="1"/>'),
    'rey': ('<path d="M22.5 11.6 L22.5 5.5 M19.8 8 L25.2 8" fill="none" stroke="{L}" stroke-width="1.5"/>'
            '<path d="M22.5 25 C22.5 25 27 17.5 25.5 14.5 C24.8 12.8 23.8 12 22.5 12 C21.2 12 20.2 12.8 19.5 14.5 '
            'C18 17.5 22.5 25 22.5 25 Z" fill="{F}"/>'
            '<path d="M12.5 37.5 C18 40.5 27 40.5 32.5 37.5 L32.5 30.5 C32.5 30.5 41 26 38.5 20 C35 13.5 25.5 16.5 22.5 24 '
            'C19.5 16.5 10 13.5 6.5 20 C4 26 12.5 30.5 12.5 30.5 Z" fill="{F}"/>'
            '<path d="M12.5 30.5 C18 27.5 27 27.5 32.5 30.5 M12.5 34 C18 31.5 27 31.5 32.5 34 M12.5 37.5 C18 35 27 35 32.5 37.5" '
            'fill="none" stroke="{d}" stroke-width="1"/>'),
    # Arzobispo: el Caballo sobre el pie del Alfil; Canciller: el Caballo sobre una Torre invertida
    # la base del Caballo (x 13.07 a 31.93, a escala 0.82) centrada en 22.5 y del mismo ancho que el collar
    'arzobispo': CINTA_DIAGRAMA + _cabeza_diagrama(0.77, 0.52, 0.82, 39) +
                 '<path d="M13.07 32.5 L31.93 32.5 L31.93 34 C27 35.6 18 35.6 13.07 34 Z" fill="{F}"/>'
                 '<path d="M14 33.6 L31 33.6" fill="none" stroke="{d}" stroke-width="0.8"/>',
    'canciller': _cabeza_diagrama(0, 2.6, 0.85, 34) + TORRE_INVERTIDA_DIAGRAMA,
}


def svg_diagrama(el, lado, dorada=False):
    c = COLORES_DIAGRAMA[lado]
    el = el.replace('{F}', c['F']).replace('{L}', c['L']).replace('{d}', c['d']).replace('{m}', c['m'])
    extra = ''
    if dorada:  # sin base: estrella y una barra doradas
        extra = (ESTRELLA.replace('fill="%s"' % ORO, 'fill="%s" stroke="#6B4A0E" stroke-width="1.5"' % ORO) +
                 '<rect x="22" y="91" width="56" height="5" rx="2.5" fill="%s" stroke="#6B4A0E" stroke-width="1.2"/>' % ORO)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">'
            '<g transform="translate(2 2) scale(2.13)" stroke="%s" stroke-width="1.5" stroke-linejoin="round" '
            'stroke-linecap="round">%s</g>%s</svg>' % (c['L'], el, extra))

# ---------------------------------------------------------------------- estilos del Guardián (Ajustes > Piezas)
_ESCUDO_CRUZ = ('<path d="M34 16 L66 16 L66 30 Q66 43 50 50 Q34 43 34 30 Z" fill="{F}"/>'
               '<path d="M37.5 19.5 L62.5 19.5 L62.5 30 Q62.5 40.5 50 46 Q37.5 40.5 37.5 30 Z" fill="none" stroke="{D}" stroke-width="1.4"/>'
               '<path d="M50 21 L50 44 M40 29 L60 29" fill="none" stroke="{D}" stroke-width="2.2"/>')
_GUARDIAN = {
    # 1. el actual en cuerpo Staunton: cabeza en bola y escudo con cruz delante
    'staunton_escudo': CUERPO_STAUNTON + CUELLO_STAUNTON + '<circle cx="50" cy="12" r="8" fill="{F}"/>' +
        _ESCUDO_CRUZ.replace('16', '22').replace('19.5', '25.5').replace('M50 21', 'M50 27').replace('L50 44', 'L50 50')
        .replace('Q66 43 50 50 Q34 43 34 30', 'Q66 49 50 56 Q34 49 34 36').replace('L66 30', 'L66 36').replace('L34 30', 'L34 36')
        .replace('Q62.5 40.5 50 46 Q37.5 40.5 37.5 30', 'Q62.5 46.5 50 52 Q37.5 46.5 37.5 36').replace('L62.5 30', 'L62.5 36')
        .replace('M40 29 L60 29', 'M40 35 L60 35'),
    # 2. yelmo de caballero (gran yelmo con visera en cruz)
    'yelmo': CUERPO_STAUNTON + CUELLO_STAUNTON + '<path d="M36 38 L36 18 Q36 6 50 6 Q64 6 64 18 L64 38 Z" fill="{F}"/>'
             '<path d="M39 22 L61 22 M50 22 L50 33" fill="none" stroke="{D}" stroke-width="2.6"/>'
             '<path d="M44 27 L44 29 M56 27 L56 29" fill="none" stroke="{D}" stroke-width="2"/>'
             '<path d="M50 6 Q53 1 58 2 Q54 4 52 7" fill="{F}"/>',
    # 3. centinela con lanza: cabeza con casco y escudo, lanza al lado
    'lanza': CUERPO_STAUNTON + '<path d="M66 84 L66 12" fill="none" stroke="{S}" stroke-width="4.5"/>'
             '<path d="M66 84 L66 12" fill="none" stroke="{F}" stroke-width="1.6"/><path d="M66 2 L71 13 L61 13 Z" fill="{F}"/>' + CUELLO_STAUNTON +
             '<path d="M41 33 Q41 18 50 18 Q59 18 59 33 Z" fill="{F}"/><path d="M38 33 L62 33" fill="none" stroke="{S}" stroke-width="3.4"/>'
             '<path d="M50 18 L50 12" fill="none" stroke="{S}" stroke-width="2.6"/><circle cx="50" cy="10" r="2.6" fill="{F}"/>',
    # 4. torre de guardia con escudo (garita)
    'garita': CUERPO_STAUNTON + '<path d="M38 48 L38 22 L62 22 L62 48 Z" fill="{F}"/>'
              '<path d="M35 23 L50 8 L65 23 Z" fill="{F}"/><circle cx="50" cy="7" r="2.6" fill="{F}"/>'
              '<path d="M44 30 L56 30 L56 38 Q56 43 50 46 Q44 43 44 38 Z" fill="none" stroke="{D}" stroke-width="1.8"/>'
              '<path d="M50 32 L50 43 M46 36 L54 36" fill="none" stroke="{D}" stroke-width="1.6"/>',
    # 5. escudo grande con una estrella (sin cabeza: el escudo es la pieza)
    'escudo_grande': '<path d="M34 84 Q36 76 42 74 L58 74 Q64 76 66 84 Z" fill="{F}"/>'
                     '<path d="M27 10 Q50 2 73 10 L73 36 Q73 60 50 72 Q27 60 27 36 Z" fill="{F}"/>'
                     '<path d="M32 14 Q50 8 68 14 L68 36 Q68 56 50 66 Q32 56 32 36 Z" fill="none" stroke="{D}" stroke-width="1.6"/>'
                     '<polygon points="50,20 54.5,32 67,32.5 57,40 60.5,52 50,45 39.5,52 43,40 33,32.5 45.5,32" fill="{D}" stroke="none"/>',
    # 6. el actual (bola y escudo) pero con escudo de cometa y una cruz griega
    'cometa': '<path d="M33 84 L38 46 L62 46 L67 84 Z" fill="{F}"/><circle cx="50" cy="14" r="9" fill="{F}"/>'
              '<path d="M33 27 Q50 22 67 27 Q67 54 50 78 Q33 54 33 27 Z" fill="{F}"/>'
              '<path d="M50 32 L50 58 M41 40 L59 40" fill="none" stroke="{D}" stroke-width="3"/>'
              '<path d="M37 30.5 Q50 26.5 63 30.5" fill="none" stroke="{D}" stroke-width="1.4"/>',
}
# 7. para el estilo «Diagrama» (contorno fino, coordenadas de 45)
GUARDIAN_DIAGRAMA = ('<path d="M14 39 L31 39 L30 35.5 L15 35.5 Z" fill="{F}"/>'
            '<path d="M12 15 Q22.5 11.5 33 15 L33 24 Q33 32 22.5 37 Q12 32 12 24 Z" fill="{F}"/>'
            '<path d="M22.5 17 L22.5 33 M16 22.5 L29 22.5" fill="none" stroke="{d}" stroke-width="1.6"/>'
            '<circle cx="22.5" cy="9" r="4.5" fill="{F}"/>')
# estilo -> dibujo (el de «Diagrama» va aparte, en GUARDIAN_DIAGRAMA)
GUARDIAN = {'staunton1': _GUARDIAN['staunton_escudo'], 'yelmo': _GUARDIAN['yelmo'], 'centinela': _GUARDIAN['lanza'],
            'garita': _GUARDIAN['garita'], 'escudo': _GUARDIAN['escudo_grande'], 'cometa': _GUARDIAN['cometa']}

# ---------------------------------------------------------------------- estilos de la Catapulta (Ajustes > Piezas)
_CATAPULTA = {
    # 1. el brazo con cuchara y piedra del juego, sobre el cuerpo Staunton
    'staunton': CUERPO_STAUNTON + '<path d="M45 47 Q46 28 35 19 L40 13 Q56 23 56 47 Z" fill="{F}"/>'
                '<path d="M17 11 Q18 25 30 24 Q40 22 40 14 Z" fill="{F}"/><circle cx="28" cy="11" r="6.5" fill="{F}"/>',
    # 2. trebuchet: pórtico, brazo largo inclinado con contrapeso y honda
    'trebuchet': CUERPO_STAUNTON + '<path d="M37 48 L50 22 L63 48" fill="none" stroke="{S}" stroke-width="5"/>'
                 '<path d="M37 48 L50 22 L63 48" fill="none" stroke="{F}" stroke-width="2"/>'
                 '<path d="M24 8 L70 34" fill="none" stroke="{S}" stroke-width="5.5"/><path d="M24 8 L70 34" fill="none" stroke="{F}" stroke-width="2.2"/>'
                 '<rect x="64" y="32" width="12" height="11" rx="1.5" fill="{F}"/><circle cx="50" cy="22" r="3" fill="{F}"/>'
                 '<path d="M24 8 Q20 18 24 26" fill="none" stroke="{S}" stroke-width="1.8"/><circle cx="24" cy="28" r="4" fill="{F}"/>',
    # 3. mangonel con ruedas: armazón bajo, ruedas y brazo con cuchara
    'ruedas': '<path d="M33 84 L38 50 L62 50 L67 84 Z" fill="{F}"/>'
              '<rect x="26" y="40" width="48" height="10" rx="2" fill="{F}"/>'
              '<circle cx="34" cy="50" r="7" fill="{F}"/><circle cx="34" cy="50" r="2" fill="{D}" stroke="none"/>'
              '<circle cx="66" cy="50" r="7" fill="{F}"/><circle cx="66" cy="50" r="2" fill="{D}" stroke="none"/>'
              '<path d="M56 41 L32 13" fill="none" stroke="{S}" stroke-width="5.5"/><path d="M56 41 L32 13" fill="none" stroke="{F}" stroke-width="2.2"/>'
              '<path d="M20 12 Q22 23 32 21 Q40 18 38 11 Z" fill="{F}"/><circle cx="29" cy="9" r="5.5" fill="{F}"/>'
              '<path d="M58 41 L58 30 L64 30" fill="none" stroke="{S}" stroke-width="2.6"/>',
    # 4. ballesta de asedio (balista): arco sobre el collar con una flecha
    'balista': CUERPO_STAUNTON + CUELLO_STAUNTON + '<path d="M28 30 Q50 14 72 30" fill="none" stroke="{S}" stroke-width="5"/>'
               '<path d="M28 30 Q50 14 72 30" fill="none" stroke="{F}" stroke-width="2"/>'
               '<path d="M28 30 L50 36 L72 30" fill="none" stroke="{S}" stroke-width="1.6"/>'
               '<rect x="44" y="20" width="12" height="18" rx="2" fill="{F}"/><path d="M50 37 L50 4" fill="none" stroke="{S}" stroke-width="2.6"/>'
               '<path d="M50 1 L54 9 L46 9 Z" fill="{F}"/>',
    # 5. piedra en vuelo: brazo levantado y la piedra lanzada en arco (sugiere el salto)
    'lanzamiento': '<path d="M33 84 L38 46 L62 46 L67 84 Z" fill="{F}"/><rect x="34" y="40" width="32" height="7" rx="2" fill="{F}"/>'
                   '<path d="M45 41 Q46 26 41 18 L47 14 Q56 25 56 41 Z" fill="{F}"/>'
                   '<path d="M37 16 Q38 8 47 8 Q50 13 47 17 Q42 19 37 16 Z" fill="{F}"/>'
                   '<path d="M47 8 Q58 -2 70 6" fill="none" stroke="{S}" stroke-width="1.8" stroke-dasharray="3 3"/>'
                   '<circle cx="73" cy="10" r="6" fill="{F}"/>',
    # 6. onagro: brazo vertical con honda y un contrapeso de cuerdas en la base
    'onagro': CUERPO_STAUNTON + '<rect x="37" y="38" width="26" height="11" rx="2" fill="{F}"/>'
              '<path d="M41 43 L59 43" fill="none" stroke="{D}" stroke-width="1.6"/>'
              '<path d="M50 40 L50 12" fill="none" stroke="{S}" stroke-width="5.5"/><path d="M50 40 L50 12" fill="none" stroke="{F}" stroke-width="2.2"/>'
              '<path d="M50 12 Q42 4 34 10" fill="none" stroke="{S}" stroke-width="1.8"/>'
              '<path d="M50 12 Q58 4 66 10" fill="none" stroke="{S}" stroke-width="1.8"/>'
              '<path d="M31 9 Q34 16 41 13 Q36 6 31 9 Z" fill="{F}"/><circle cx="34" cy="7" r="4.5" fill="{F}"/>',
}
# 7. para el estilo «Diagrama» (contorno fino, coordenadas de 45)
CATAPULTA_DIAGRAMA = ('<path d="M12 39 L33 39 L31.5 35 L13.5 35 Z" fill="{F}"/>'
            '<path d="M15 35 L17 25 L28 25 L30 35 Z" fill="{F}"/>'
            '<path d="M20 25 Q21 16 15.5 11 L18 8.5 Q25.5 14 25 25 Z" fill="{F}"/>'
            '<path d="M7 7.5 Q7.5 13.5 13 13 Q18 12 18 8 Z" fill="{F}"/><circle cx="12" cy="6.5" r="3.4" fill="{F}"/>'
            '<path d="M17 30 L28 30" fill="none" stroke="{d}" stroke-width="1"/>')
# estilo -> dibujo (el de «Diagrama» va aparte, en CATAPULTA_DIAGRAMA)
CATAPULTA = {'staunton1': _CATAPULTA['staunton'], 'fundibulo': _CATAPULTA['trebuchet'],
             'mangonel': _CATAPULTA['ruedas'], 'onagro': _CATAPULTA['onagro']}

# ---------------------------------------------------------------------- adornos (sobre el cuerpo)
ADORNOS = {
    'banda': '<path d="M38 58 L62 58 M37 64 L63 64" fill="none" stroke="{D}" stroke-width="2"/>',
    'punto': '<circle cx="50" cy="64" r="4.5" fill="{D}" stroke="none"/>',
    'rombo': '<path d="M50 55 L57 65 L50 75 L43 65 Z" fill="none" stroke="{D}" stroke-width="2"/>',
    'cruz': '<path d="M50 56 L50 74 M42 63 L58 63" fill="none" stroke="{D}" stroke-width="2.6"/>',
    'estrella': ('<polygon points="50,55 52.9,61.8 60,62.3 54.6,67 56.2,74 50,70.2 43.8,74 45.4,67 40,62.3 47.1,61.8" '
                 'fill="{D}" stroke="none"/>'),
    'ondas': '<path d="M38 60 Q44 56 50 60 Q56 64 62 60 M38 68 Q44 64 50 68 Q56 72 62 68" fill="none" stroke="{D}" stroke-width="1.8"/>',
    'escudo': ('<path d="M42 55 L58 55 L58 64 Q58 72 50 76 Q42 72 42 64 Z" fill="none" stroke="{D}" stroke-width="1.8"/>'),
    'circulo': '<circle cx="50" cy="65" r="8" fill="none" stroke="{D}" stroke-width="2"/>',
    'aspas': '<path d="M43 57 L57 73 M57 57 L43 73" fill="none" stroke="{D}" stroke-width="2.6"/>',
    'flechas': ('<path d="M41 72 L50 58 L59 72" fill="none" stroke="{D}" stroke-width="2.4"/>'
                '<path d="M45 61 L50 56 L55 61" fill="none" stroke="{D}" stroke-width="2.4"/>'),
    'luna': '<path d="M48 57 A8 8 0 1 0 56 70 A6.5 6.5 0 1 1 48 57 Z" fill="{D}" stroke="none"/>',
}
REMATES.update(REMATES_MAGICOS)
LETRAS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def letra(c):
    return ('<text x="50" y="75" font-family="DejaVu Sans" font-weight="bold" font-size="20" text-anchor="middle" '
            'fill="{D}" stroke="none">%s</text>' % c)


# ---------------------------------------------------------------------- piezas completas
# (cuerpo, remate, adorno)
CLASICO = {'rey': ('clasico', 'cruz', None), 'dama': ('clasico', 'corona', None), 'torre': ('clasico', 'almenas', None),
           'alfil': ('clasico', 'mitra', None), 'peon': ('clasico', 'bola', None)}
# el Caballo clásico es una silueta completa (cabeza, cuello y crin), no una cabeza sobre el collar
CABALLO_CLASICO = ('<path d="M29 84 Q29 70 35 62 Q38 56 36 52 Q29 51 26 45 Q24 39 30 35 L44 22 Q45 13 50 7 L54 16 '
                   'Q68 20 73 36 Q77 52 69 64 Q64 72 71 84 Z" fill="{F}"/>'
                   '<circle cx="46" cy="27" r="2.6" fill="{D}" stroke="none"/>'
                   '<circle cx="30.5" cy="40" r="1.4" fill="{D}" stroke="none"/>'
                   '<path d="M56 17 Q66 23 69 34 M58 26 Q64 31 66 40 M58 36 Q62 42 63 50" fill="none" stroke="{D}" '
                   'stroke-width="1.6"/>'
                   '<path d="M33 76 Q50 80 67 76" fill="none" stroke="{D}" stroke-width="1.6"/>')
PREDISENOS = {'amazona': ('recto', 'amazona', None), 'unicornio': ('recto', 'unicornio', None),
              'camello': ('recto', 'camello', None), 'elefante': ('ancho', 'elefante', None),
              'canon': ('escalonado', 'canon', None), 'dragon': ('barril', 'dragon', None),
              'consejero': ('recto', 'consejero', 'banda'), 'saltamontes': ('esbelto', 'resorte', None),
              'mago': ('recto', 'mago', 'estrella'), 'arquero': ('recto', 'arquero', None),
              'centinela': ('ancho', 'ojo', None), 'lanza': ('esbelto', 'lanza', None),
              'llama': ('barril', 'llama', None), 'rayo': ('recto', 'rayo', 'punto'),
              'estrella': ('recto', 'estrella', None), 'yelmo': ('clasico', 'yelmo', 'cruz'),
              'diamante': ('esbelto', 'diamante', None), 'hombre': ('clasico', 'bola', 'escudo')}
# las piezas mágicas del catálogo (cuerpo según su familia)
PREDISENOS.update({
    'saltamontes': ('escalonado', 'insecto', None),
    'visir': ('recto', 'turbante', None), 'dabbaba': ('recto', 'torre_asedio', None),
    'alibaba': ('recto', 'lampara', 'estrella'), 'tres_saltador': ('recto', 'tres_bolas', None),
    'tripper': ('recto', 'tres_diagonal', None), 'cebra': ('recto', 'cebra', None), 'jirafa': ('recto', 'jirafa', None),
    'antilope': ('recto', 'antilope', None), 'nu': ('recto', 'nu', None), 'bisonte': ('ancho', 'bisonte', None),
    'okapi': ('recto', 'okapi', 'ondas'), 'bufalo': ('ancho', 'bufalo', None), 'ardilla': ('recto', 'ardilla', None),
    'kirin': ('recto', 'kirin', 'punto'), 'fenix': ('recto', 'fenix', None), 'centauro': ('clasico', 'centauro', None),
    'jinete_nocturno': ('esbelto', 'nocturno', None), 'jinete_camello': ('esbelto', 'camello_luna', None),
    'jinete_cebra': ('esbelto', 'cebra_luna', None), 'bede': ('esbelto', 'bede', 'luna'),
    'waran': ('esbelto', 'varano', 'luna'), 'emperatriz': ('clasico', 'emperatriz', None),
    'princesa': ('clasico', 'princesa', None), 'caballo_dragon': ('clasico', 'caballo_alado', None),
    'caballo_coronado': ('clasico', 'caballo_corona', 'cruz'), 'saltamontes_torre': ('escalonado', 'resorte_torre', None),
    'saltamontes_alfil': ('escalonado', 'resorte_mitra', None), 'leon': ('escalonado', 'leon', None),
    'vao': ('escalonado', 'vao', None), 'leo': ('escalonado', 'leo', None), 'langosta': ('escalonado', 'langosta', None),
    'mao': ('barril', 'mao', None), 'moa': ('barril', 'moa', None), 'elefante_chino': ('barril', 'elefante_disco', None),
    'grifo': ('barril', 'grifo', None), 'aanca': ('barril', 'aanca', None), 'rosa': ('barril', 'rosa', None),
    'khon': ('ancho', 'khon', None), 'general_oro': ('ancho', 'teja_oro', None), 'keima': ('ancho', 'teja_caballo', None),
    'courier': ('ancho', 'corneta', None), 'peon_berolina': ('clasico', 'bola', 'aspas'),
    'peon_damas': ('clasico', 'discos', None),
})


def capablanca():
    """Arzobispo (mitra + cabeza de Caballo) y Canciller (almenas + cabeza de Caballo), uno junto al otro."""
    caballo_der = ('<path d="M52 41 Q51 31 56 24 L59 15 L63 23 Q73 26 74 37 L69 41 Z" fill="{F}"/>'
                   '<circle cx="65" cy="29" r="2.2" fill="{D}" stroke="none"/>')
    mitra_izq = ('<path d="M39 10 Q53 23 48 41 L30 41 Q25 23 39 10 Z" fill="{F}"/><circle cx="39" cy="8" r="3.4" fill="{F}"/>'
                 '<path d="M41 18 L45 29" fill="none" stroke="{D}" stroke-width="1.8"/>')
    torre_izq = ('<path d="M29 41 L29 28 L48 28 L48 41 Z" fill="{F}"/>'
                 '<path d="M26 29 L26 14 L32 14 L32 20 L37 20 L37 14 L42 14 L42 20 L47 20 L47 14 L51 14 L51 29 Z" fill="{F}"/>')
    collar = '<rect x="27" y="40" width="46" height="7" rx="2" fill="{F}"/>'
    cuerpo = '<path d="M30 84 L36 46 L64 46 L70 84 Z" fill="{F}"/>'
    return {'arzobispo': cuerpo + mitra_izq + caballo_der + collar,
            'canciller': cuerpo + torre_izq + caballo_der + collar}


def svg(elementos, colores):
    cuerpo = elementos.replace('{F}', colores['F']).replace('{S}', colores['S']).replace('{D}', colores['D'])
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100"><g stroke="%s" '
            'stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round">%s</g></svg>' % (colores['S'], cuerpo))


def pieza(cuerpo, remate, adorno):
    return CUERPOS[cuerpo] + REMATES[remate] + (ADORNOS[adorno] if adorno else '')


class Generador:
    def __init__(self):
        self.tmp = tempfile.mkdtemp()
        self.lote = []  # (svg, png)

    def guardar(self, carpeta, nombre, elementos, completa):
        """SVG y PNG de las dos colores; si es una pieza completa, también la forma promocionada."""
        for lado, colores in COLORES.items():
            variantes = [('', elementos + BASE)]
            if completa:
                variantes.append(('_promocionado', elementos + BASE + BASE_DORADA + ESTRELLA))
            for sufijo, el in variantes:
                d_svg = os.path.join(AQUI, carpeta, lado, 'svg')
                d_png = os.path.join(AQUI, carpeta, lado, 'png')
                os.makedirs(d_svg, exist_ok=True)
                os.makedirs(d_png, exist_ok=True)
                ruta = os.path.join(d_svg, nombre + sufijo + '.svg')
                with open(ruta, 'w', encoding='utf-8') as f:
                    f.write(svg(el, colores))
                self.lote.append((ruta, os.path.join(d_png, nombre + sufijo + '.png')))

    def diagrama(self, nombre, elementos):
        """Una pieza del estilo «Diagrama» (con su forma extendida), de los dos colores."""
        for lado in COLORES_DIAGRAMA:
            d_svg = os.path.join(AQUI, 'estilos', 'diagrama', lado, 'svg')
            d_png = os.path.join(AQUI, 'estilos', 'diagrama', lado, 'png')
            os.makedirs(d_svg, exist_ok=True)
            os.makedirs(d_png, exist_ok=True)
            for sufijo, dorada in (('', False), ('_promocionado', True)):
                ruta = os.path.join(d_svg, nombre + sufijo + '.svg')
                with open(ruta, 'w', encoding='utf-8') as f:
                    f.write(svg_diagrama(elementos, lado, dorada))
                self.lote.append((ruta, os.path.join(d_png, nombre + sufijo + '.png')))

    def parte(self, nombre, elementos):
        """Una capa del diseñador (sin base): PNG transparente de cada color."""
        for lado, colores in COLORES.items():
            d = os.path.join(AQUI, 'partes', lado)
            os.makedirs(d, exist_ok=True)
            ruta = os.path.join(self.tmp, '%s_%s.svg' % (lado, nombre))
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(svg(elementos, colores))
            self.lote.append((ruta, os.path.join(d, nombre + '.png')))

    def convertir(self):
        for i, (s, p) in enumerate(self.lote, 1):
            subprocess.run(['magick', '-background', 'none', '-density', '384', s, '-resize', '256x256', p], check=True)
            if i % 50 == 0:
                print('  %d de %d' % (i, len(self.lote)), flush=True)
        shutil.rmtree(self.tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--muestra', action='store_true', help='crea muestra_disenos.png con todo lo generado')
    ap.add_argument('--solo', nargs='*', help='solo estos prediseños (sin estilos ni partes)')
    ap.add_argument('--staunton', action='store_true', help='solo los estilos Staunton')
    ap.add_argument('--arzobispo', action='store_true', help='solo el Arzobispo del juego y el anterior')
    ap.add_argument('--diagrama', action='store_true', help='solo el estilo «Diagrama»')
    ap.add_argument('--guardian', action='store_true', help='solo los estilos del Guardián')
    ap.add_argument('--catapulta', action='store_true', help='solo los estilos de la Catapulta')
    a = ap.parse_args()
    if not shutil.which('magick'):
        sys.exit('Hace falta ImageMagick (magick).')
    g = Generador()
    if a.catapulta:
        for estilo, el in CATAPULTA.items():
            g.guardar('estilos/' + estilo, 'catapulta', el, True)
        g.diagrama('catapulta', CATAPULTA_DIAGRAMA)
        g.convertir()
        return
    if a.guardian:
        for estilo, el in GUARDIAN.items():
            g.guardar('estilos/' + estilo, 'guardian', el, True)
        g.diagrama('guardian', GUARDIAN_DIAGRAMA)
        g.convertir()
        return
    if a.diagrama:
        for nombre, el in DIAGRAMA.items():
            g.diagrama(nombre, el)
        g.convertir()
        return
    if a.arzobispo:
        g.guardar('', 'arzobispo', ARZOBISPO, True)
        g.guardar('estilos/anterior', 'arzobispo', ARZOBISPO_ANTERIOR, True)
        g.convertir()
        return
    if a.staunton:
        for estilo, piezas in STAUNTON.items():
            for nombre, el in piezas.items():
                g.guardar('estilos/' + estilo, nombre, el, True)
        g.convertir()
        return
    if a.solo is not None:
        for nombre in a.solo or PREDISENOS:
            g.guardar('predisenos', nombre, pieza(*PREDISENOS[nombre]), True)
        print('Convirtiendo %d imágenes…' % len(g.lote), flush=True)
        g.convertir()
        return
    for nombre, receta in CLASICO.items():
        g.guardar('estilos/clasico', nombre, pieza(*receta), True)
    g.guardar('estilos/clasico', 'caballo', CABALLO_CLASICO, True)
    for nombre, el in capablanca().items():
        g.guardar('estilos/capablanca', nombre, el, True)
    for estilo, piezas in STAUNTON.items():
        for nombre, el in piezas.items():
            g.guardar('estilos/' + estilo, nombre, el, True)
    g.guardar('', 'arzobispo', ARZOBISPO, True)
    g.guardar('estilos/anterior', 'arzobispo', ARZOBISPO_ANTERIOR, True)
    for nombre, el in DIAGRAMA.items():
        g.diagrama(nombre, el)
    for estilo, el in GUARDIAN.items():
        g.guardar('estilos/' + estilo, 'guardian', el, True)
    g.diagrama('guardian', GUARDIAN_DIAGRAMA)
    for estilo, el in CATAPULTA.items():
        g.guardar('estilos/' + estilo, 'catapulta', el, True)
    g.diagrama('catapulta', CATAPULTA_DIAGRAMA)
    for nombre, receta in PREDISENOS.items():
        g.guardar('predisenos', nombre, pieza(*receta), True)
    for nombre, el in CUERPOS.items():
        g.parte('cuerpo_' + nombre, el)
    for nombre, el in REMATES.items():
        g.parte('remate_' + nombre, el)
    for nombre, el in ADORNOS.items():
        g.parte('adorno_' + nombre, el)
    for c in LETRAS:
        g.parte('letra_' + c, letra(c))
    g.parte('base', BASE)
    g.parte('base_dorada', BASE_DORADA)
    g.parte('estrella', ESTRELLA)
    print('Convirtiendo %d imágenes…' % len(g.lote), flush=True)
    g.convertir()
    if a.muestra:
        imgs = []
        for carpeta in ('estilos/clasico', 'estilos/capablanca', 'predisenos'):
            for lado in ('blancas', 'negras'):
                d = os.path.join(AQUI, carpeta, lado, 'png')
                imgs += [os.path.join(d, f) for f in sorted(os.listdir(d)) if not f.endswith('_promocionado.png')]
        subprocess.run(['magick', 'montage'] + imgs + ['-tile', '13x', '-geometry', '96x96+3+3', '-background',
                                                       '#B58863', os.path.join(AQUI, 'muestra_disenos.png')], check=True)
    print('Listo.')


if __name__ == '__main__':
    main()
