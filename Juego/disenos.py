"""Imágenes de las piezas: estilos, prediseños y diseños propios.

  - Estilo de cada pieza (Ajustes): las de este juego («moderno», carpeta Piezas/blancas y negras), las
    clásicas (Piezas/estilos/clasico), para el Arzobispo y el Canciller las de Capablanca
    (Piezas/estilos/capablanca), las de los diagramas de los libros para las ocho piezas (Piezas/estilos/diagrama)
    y, para Rey, Dama, Arzobispo y Canciller, tres diseños Staunton (Piezas/estilos/staunton1-3); el Guardián
    tiene además Yelmo, Centinela, Garita, Escudo grande y Escudo de cometa, y la Catapulta, Fundíbulo, Con ruedas
    y Onagro. Vale para todas las variantes.
  - Prediseños: las piezas mágicas del Laboratorio (Piezas/predisenos), con su imagen; sus movimientos están en
    piezas_magicas.py. En la definición de una pieza, su imagen es 'pre:nombre'.
  - Diseños propios: se arman en el Laboratorio con un cuerpo, un remate y un adorno o letra (Piezas/partes) y
    se guardan en Juego/disenos/ ('diseno:id'). La receta va también en la definición de la pieza ('diseno'),
    así una variante exportada rehace sus imágenes en otra computadora.

Las imágenes generadas salen de Piezas/generar_disenos.py (SVG → PNG); aquí solo se superponen PNG con Tk.
"""
import hashlib, json, os

AQUI = os.path.dirname(os.path.abspath(__file__))
PIEZAS = os.path.join(os.path.dirname(AQUI), 'Piezas')
CARPETA = os.path.join(AQUI, 'disenos')
BIBLIOTECA = os.path.join(CARPETA, 'disenos.json')
COLORES = ('blancas', 'negras')

# estilos disponibles para cada imagen del juego (el primero es el original)
ESTILOS = {
    'rey': ['moderno', 'clasico', 'diagrama', 'staunton1', 'staunton2', 'staunton3'],
    'dama': ['moderno', 'clasico', 'diagrama', 'staunton1', 'staunton2', 'staunton3'],
    'torre': ['moderno', 'clasico', 'diagrama'], 'alfil': ['moderno', 'clasico', 'diagrama'],
    'caballo': ['moderno', 'clasico', 'diagrama'], 'peon': ['moderno', 'clasico', 'diagrama'],
    'arzobispo': ['moderno', 'capablanca', 'diagrama', 'staunton1', 'staunton2', 'staunton3', 'anterior'],
    'canciller': ['moderno', 'capablanca', 'diagrama', 'staunton1', 'staunton2', 'staunton3'],
    'guardian': ['moderno', 'staunton1', 'diagrama', 'yelmo', 'centinela', 'garita', 'escudo', 'cometa'],
    'catapulta': ['moderno', 'staunton1', 'diagrama', 'fundibulo', 'mangonel', 'onagro'],
}
NOMBRE_ESTILO = {'moderno': 'Extendido', 'clasico': 'Clásico', 'capablanca': 'Capablanca',
                 'staunton1': 'Staunton 1', 'staunton2': 'Staunton 2', 'staunton3': 'Staunton 3',
                 'anterior': 'Media luna anterior', 'diagrama': 'Diagrama', 'yelmo': 'Yelmo', 'centinela': 'Centinela',
                 'garita': 'Garita', 'escudo': 'Escudo grande', 'cometa': 'Escudo de cometa', 'fundibulo': 'Fundíbulo',
                 'mangonel': 'Con ruedas', 'onagro': 'Onagro'}
ESTILO = {}  # imagen -> estilo elegido (lo fija la aplicación con los ajustes)
# remates de las piezas mágicas (Piezas/generar_disenos.py), también disponibles en el diseñador
REMATES_MAGICOS = ['turbante', 'torre_asedio', 'lampara', 'tres_bolas', 'tres_diagonal', 'cebra', 'jirafa',
                   'antilope', 'nu', 'bisonte', 'okapi', 'bufalo', 'ardilla', 'kirin', 'fenix', 'centauro',
                   'nocturno', 'camello_luna', 'cebra_luna', 'bede', 'varano', 'emperatriz', 'princesa',
                   'caballo_alado', 'caballo_corona', 'insecto', 'resorte_torre', 'resorte_mitra', 'leon', 'vao',
                   'leo', 'langosta', 'mao', 'moa', 'elefante_disco', 'grifo', 'aanca', 'rosa', 'khon', 'teja_oro',
                   'teja_caballo', 'corneta', 'discos']
PARTES = {
    'cuerpo': ['recto', 'clasico', 'ancho', 'esbelto', 'escalonado', 'barril'],
    'remate': ['cruz', 'corona', 'almenas', 'mitra', 'caballo', 'bola', 'luna', 'sello', 'amazona', 'unicornio',
               'camello', 'elefante', 'canon', 'dragon', 'consejero', 'resorte', 'mago', 'arquero', 'ojo', 'lanza',
               'llama', 'rayo', 'estrella', 'yelmo', 'diamante'] + REMATES_MAGICOS,
    'adorno': ['banda', 'punto', 'rombo', 'cruz', 'estrella', 'ondas', 'escudo', 'circulo', 'aspas', 'flechas', 'luna'],
}
LETRAS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def ruta(archivo, color, dorada=False):
    """Archivo PNG de una imagen de pieza ('torre', 'pre:camello', 'diseno:abc123') para un color."""
    lado = COLORES[color]
    suf = '_promocionado' if dorada else ''
    if archivo.startswith('pre:'):
        base = os.path.join(PIEZAS, 'predisenos', lado, 'png', archivo[4:])
    elif archivo.startswith('diseno:'):
        base = os.path.join(CARPETA, '%s_%s' % (archivo[7:], lado))
    else:
        estilo = ESTILO.get(archivo, 'moderno')
        if estilo != 'moderno' and os.path.exists(os.path.join(PIEZAS, 'estilos', estilo, lado, 'png', archivo + '.png')):
            base = os.path.join(PIEZAS, 'estilos', estilo, lado, 'png', archivo)
        else:
            base = os.path.join(PIEZAS, lado, 'png', archivo)
    if dorada and not os.path.exists(base + suf + '.png'):
        suf = ''  # sin versión dorada (el Rey): la normal
    return base + suf + '.png'


def ruta_estilo(archivo, estilo, color=0):
    """La imagen de una pieza en un estilo concreto (para elegirlo en los ajustes)."""
    if estilo == 'moderno':
        return os.path.join(PIEZAS, COLORES[color], 'png', archivo + '.png')
    return os.path.join(PIEZAS, 'estilos', estilo, COLORES[color], 'png', archivo + '.png')


def predisenos_disponibles():
    d = os.path.join(PIEZAS, 'predisenos', 'blancas', 'png')
    if not os.path.isdir(d):
        return []
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith('.png') and not f.endswith('_promocionado.png'))


# ---------------------------------------------------------------------- diseños propios
def parte(nombre, color):
    """PNG de una capa del diseñador ('cuerpo_recto', 'remate_corona', 'letra_A', 'base', 'estrella'...)."""
    return os.path.join(PIEZAS, 'partes', COLORES[color], nombre + '.png')


def capas(receta, color, dorada):
    nombres = ['cuerpo_' + receta.get('cuerpo', 'recto'), 'remate_' + receta.get('remate', 'bola')]
    if receta.get('adorno'):
        nombres.append('adorno_' + receta['adorno'])
    if receta.get('letra'):
        nombres.append('letra_' + receta['letra'])
    nombres.append('base')
    if dorada:
        nombres += ['base_dorada', 'estrella']
    return [parte(n, color) for n in nombres]


def identificador(receta):
    texto = json.dumps({k: receta.get(k) for k in ('cuerpo', 'remate', 'adorno', 'letra')}, sort_keys=True)
    return hashlib.sha1(texto.encode()).hexdigest()[:10]


def componer(receta, color, dorada, destino=None, root=None):
    """Superpone las capas con Tk (sin Pillow). Devuelve la PhotoImage; la guarda en destino si se da."""
    import tkinter as tk
    img = tk.PhotoImage(master=root, width=256, height=256)
    for capa in capas(receta, color, dorada):
        if os.path.exists(capa):
            c = tk.PhotoImage(master=root, file=capa)
            img.tk.call(img, 'copy', c, '-compositingrule', 'overlay')
    if destino:
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        img.write(destino, format='png')
    return img


def asegurar(receta, root=None):
    """Crea (si faltan) los PNG de un diseño propio. Devuelve su imagen ('diseno:id')."""
    ident = identificador(receta)
    for color in (0, 1):
        for dorada in (False, True):
            destino = os.path.join(CARPETA, '%s_%s%s.png' % (ident, COLORES[color], '_promocionado' if dorada else ''))
            if not os.path.exists(destino):
                componer(receta, color, dorada, destino, root)
    return 'diseno:' + ident


def asegurar_cfg(cfg, root=None):
    """Rehace las imágenes de los diseños propios de una variante (p. ej., importada de otra computadora)."""
    for d in cfg.get('piezas', {}).values():
        if str(d.get('imagen', '')).startswith('diseno:') and d.get('diseno'):
            try:
                d['imagen'] = asegurar(d['diseno'], root)
            except Exception:  # sin Tk todavía o sin las partes: se verá sin imagen
                pass


def biblioteca():
    """Tus diseños guardados: [{'id', 'nombre', 'receta'}]."""
    try:
        with open(BIBLIOTECA, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def guardar_diseno(nombre, receta, root=None):
    imagen = asegurar(receta, root)
    lista = [x for x in biblioteca() if x['id'] != imagen[7:]]
    lista.append({'id': imagen[7:], 'nombre': nombre, 'receta': receta})
    os.makedirs(CARPETA, exist_ok=True)
    with open(BIBLIOTECA, 'w', encoding='utf-8') as f:
        json.dump(lista, f, ensure_ascii=False, indent=1)
    return imagen


# ---------------------------------------------------------------------- piezas prediseñadas (Laboratorio)
def pieza_prediseno(nombre):
    """Definición de pieza del Laboratorio a partir de un prediseño (el catálogo de piezas_magicas.py)."""
    import piezas_magicas as PM
    from idioma import tr
    return PM.pieza(nombre, tr(PM.nombre(nombre)))
