"""Ajustes generales del juego (ajustes.json): tema del tablero para todas las variantes, sonido y
volumen, tamaño de la interfaz, animación de las piezas, barra de evaluación y ayudas durante la partida."""
import json, os
import tkinter as tk
from tkinter import ttk

from interfaz import FONDO, BORDE, ORO, TEXTO_SUAVE, TEMAS

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ajustes.json')
POR_DEFECTO = {'tema': None,         # None: cada variante con su propio tema
               'idioma': 'es',       # 'es' o 'en' (idioma.py)
               'piezas': {},         # estilo de la imagen de cada pieza (disenos.py): {'rey': 'clasico', ...}
               'sonido': True, 'volumen': 80,
               'escala': 100,        # tamaño de la interfaz, en %
               'animacion': True, 'barra_eval': False,
               'pensar': True,       # la computadora piensa durante tu turno (Ajedrez Extendido)
               'ayudas': True,       # botones «Pista» y «¿Por qué?» en la partida
               'avisos': False,      # avisar de piezas en peligro y amenazas de mate
               'libro': True,        # la computadora juega del libro de aperturas (Ajedrez Extendido)
               'tablero10': []}      # variantes del menú que se juegan en 10 × 10 (Capablanca, gótico)
ESCALAS = [90, 100, 110, 125]


def cargar():
    d = dict(POR_DEFECTO)
    try:
        with open(RUTA, encoding='utf-8') as f:
            d.update({k: v for k, v in json.load(f).items() if k in POR_DEFECTO})
    except (OSError, ValueError):
        pass
    return d


def guardar(d):
    try:
        with open(RUTA, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


class VentanaAjustes:
    ALTO = 46  # alto de cada fila de la galería de piezas

    def __init__(self, app):
        self.app = app
        a = app.ajustes
        top = self.top = tk.Toplevel(app.root)
        top.title('Ajustes')
        top.configure(bg=FONDO)
        top.transient(app.root)
        top.resizable(False, False)
        f = ttk.Frame(top, style='Panel.TFrame', padding=18)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Ajustes', style='Titulo.TLabel').pack(anchor='w', pady=(0, 8))

        ttk.Label(f, text='TABLERO', style='Sub.TLabel').pack(anchor='w')
        self.tema = tk.StringVar(value=a['tema'] or '')
        self.cv = tk.Canvas(f, width=560, height=96, bg=FONDO, highlightthickness=0, cursor='hand2')
        self.cv.pack(anchor='w', pady=(4, 2))
        self.cv.bind('<Button-1>', self.clic_tema)
        ttk.Label(f, text='«Cada variante» usa el estilo propio de cada una (y el que elijas en el Laboratorio).',
                  style='Panel.TLabel').pack(anchor='w', pady=(0, 12))

        ttk.Label(f, text='PIEZAS (CLIC PARA ELEGIR EL DISEÑO DE CADA UNA)', style='Sub.TLabel').pack(anchor='w')
        import disenos
        self.D = disenos
        self.estilos = dict(a.get('piezas') or {})
        filas = max(len(e) for e in disenos.ESTILOS.values())
        self.cv_piezas = tk.Canvas(f, width=70 * len(disenos.ESTILOS), height=filas * self.ALTO + 30, bg=FONDO,
                                   highlightthickness=0, cursor='hand2')
        self.cv_piezas.pack(anchor='w', pady=(4, 2))
        self.cv_piezas.bind('<Button-1>', self.clic_pieza)
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(anchor='w', pady=(0, 12))
        ttk.Button(fila, text='Todas del Ajedrez Extendido', command=lambda: self.todas_piezas({})).pack(side='left')
        ttk.Button(fila, text='Clásicas y de Capablanca', command=lambda: self.todas_piezas(
            {n: e[1] for n, e in disenos.ESTILOS.items()})).pack(side='left', padx=6)
        ttk.Button(fila, text='Diagrama', command=lambda: self.todas_piezas(
            {n: 'diagrama' for n, e in disenos.ESTILOS.items() if 'diagrama' in e})).pack(side='left', padx=(0, 6))
        for k in (1, 2, 3):
            ttk.Button(fila, text='Staunton %d' % k, command=lambda k=k: self.todas_piezas(
                {n: ('staunton%d' % k if 'staunton%d' % k in e else e[1]) for n, e in disenos.ESTILOS.items()})).pack(
                side='left', padx=(0, 4))
        ttk.Label(f, text='SONIDO', style='Sub.TLabel').pack(anchor='w')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 12))
        self.sonido = tk.BooleanVar(value=a['sonido'])
        ttk.Checkbutton(fila, text='Activado', variable=self.sonido, style='Panel.TCheckbutton').pack(side='left')
        ttk.Label(fila, text='Volumen', style='Panel.TLabel').pack(side='left', padx=(24, 6))
        self.volumen = tk.IntVar(value=a['volumen'])
        ttk.Scale(fila, from_=0, to=100, variable=self.volumen, length=220,
                  command=lambda x: self.lbl_vol.configure(text='%d %%' % float(x))).pack(side='left')
        self.lbl_vol = ttk.Label(fila, text='%d %%' % a['volumen'], style='Panel.TLabel', width=6)
        self.lbl_vol.pack(side='left', padx=6)
        ttk.Button(fila, text='Probar', command=self.probar).pack(side='left')

        ttk.Label(f, text='IDIOMA', style='Sub.TLabel').pack(anchor='w')
        import idioma
        self.idioma = ttk.Combobox(f, state='readonly', width=14, values=[n for _, n in idioma.IDIOMAS])
        self.idioma.current([c for c, _ in idioma.IDIOMAS].index(a['idioma']) if a['idioma'] in dict(idioma.IDIOMAS) else 0)
        self.idioma.pack(anchor='w', pady=(2, 12))
        ttk.Label(f, text='INTERFAZ', style='Sub.TLabel').pack(anchor='w')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 4))
        ttk.Label(fila, text='Tamaño del texto y de los controles (al volver a abrir el juego)',
                  style='Panel.TLabel').pack(side='left')
        self.escala = ttk.Combobox(fila, state='readonly', width=8, values=['%d %%' % e for e in ESCALAS])
        self.escala.current(ESCALAS.index(a['escala']) if a['escala'] in ESCALAS else 1)
        self.escala.pack(side='left', padx=8)
        self.animacion = tk.BooleanVar(value=a['animacion'])
        ttk.Checkbutton(f, text='Animar el movimiento de las piezas', variable=self.animacion,
                        style='Panel.TCheckbutton').pack(anchor='w', pady=(4, 0))
        self.pensar = tk.BooleanVar(value=a['pensar'])
        ttk.Checkbutton(f, text='La computadora piensa durante tu turno (responde más rápido en el Ajedrez Extendido)',
                        variable=self.pensar, style='Panel.TCheckbutton').pack(anchor='w', pady=(2, 0))
        self.libro = tk.BooleanVar(value=a['libro'])
        ttk.Checkbutton(f, text='La computadora varía sus aperturas con el libro (Ajedrez Extendido, si existe '
                                'libro_aperturas.json)', variable=self.libro,
                        style='Panel.TCheckbutton').pack(anchor='w', pady=(2, 0))
        self.barra = tk.BooleanVar(value=a['barra_eval'])
        ttk.Checkbutton(f, text='Mostrar la barra de evaluación al empezar', variable=self.barra,
                        style='Panel.TCheckbutton').pack(anchor='w', pady=(2, 0))

        ttk.Label(f, text='AYUDA DURANTE LA PARTIDA', style='Sub.TLabel').pack(anchor='w', pady=(12, 0))
        self.ayudas = tk.BooleanVar(value=a['ayudas'])
        ttk.Checkbutton(f, text='Botones «Pista» y «¿Por qué jugó eso?»', variable=self.ayudas,
                        style='Panel.TCheckbutton').pack(anchor='w', pady=(2, 0))
        self.avisos = tk.BooleanVar(value=a['avisos'])
        ttk.Checkbutton(f, text='Avisar de piezas en peligro y de amenazas de mate', variable=self.avisos,
                        style='Panel.TCheckbutton').pack(anchor='w', pady=(2, 0))
        ttk.Label(f, text='Una partida en la que usas una pista o recibes un aviso no cuenta para tu Elo.',
                  style='Panel.TLabel').pack(anchor='w', pady=(2, 0))
        b = ttk.Frame(f, style='Panel.TFrame')
        b.pack(fill='x', pady=(16, 0))
        ttk.Button(b, text='Restablecer', command=self.restablecer).pack(side='left')
        ttk.Button(b, text='Cancelar', command=top.destroy).pack(side='right')
        ttk.Button(b, text='Guardar', style='Comenzar.TButton', command=self.aceptar).pack(side='right', padx=6)
        self.dibujar_temas()
        self.dibujar_piezas()
        top.wait_visibility()
        top.grab_set()

    def opciones(self):
        return [('', 'Cada variante', None)] + [(k, n, (c, o)) for k, (n, c, o) in TEMAS.items()]

    def dibujar_temas(self):
        cv = self.cv
        cv.delete('all')
        for i, (clave, nombre, colores) in enumerate(self.opciones()):
            x = i * 80
            elegido = clave == self.tema.get()
            cv.create_rectangle(x + 2, 2, x + 74, 74, outline=ORO if elegido else BORDE, width=3 if elegido else 1)
            for k in range(16):
                c, r = k % 4, k // 4
                if colores:
                    col = colores[(c + r) % 2]
                else:  # «cada variante»: un poco de cada tema
                    col = list(TEMAS.values())[(c + r * 4) % len(TEMAS)][1 + (c + r) % 2]
                cv.create_rectangle(x + 8 + c * 15, 8 + r * 15, x + 23 + c * 15, 23 + r * 15, fill=col, outline='')
            cv.create_text(x + 38, 86, text=nombre, fill=ORO if elegido else TEXTO_SUAVE,
                           font=(self.app.letra, 9, 'bold'))

    def dibujar_piezas(self):
        cv, D = self.cv_piezas, self.D
        cv.delete('all')
        A = self.ALTO
        filas = max(len(e) for e in D.ESTILOS.values())
        for i, (nombre, estilos) in enumerate(D.ESTILOS.items()):
            x = i * 70
            elegido = self.estilos.get(nombre, 'moderno')
            for k, estilo in enumerate(estilos):
                y = k * A
                sel = estilo == elegido
                cv.create_rectangle(x + 8, y + 2, x + 58, y + A - 2, outline=ORO if sel else BORDE,
                                    width=3 if sel else 1, fill='#B58863')
                cv.create_image(x + 33, y + A / 2, image=self.app.img.get(D.ruta_estilo(nombre, estilo), A - 8))
            cv.create_text(x + 33, filas * A + 8, text=nombre.capitalize().replace('Peon', 'Peón').replace(
                'Guardian', 'Guardián'), fill=TEXTO_SUAVE,
                           font=(self.app.letra, 8, 'bold'))
            cv.create_text(x + 33, filas * A + 21, text=D.NOMBRE_ESTILO[elegido], fill=ORO, font=(self.app.letra, 8))

    def clic_pieza(self, ev):
        nombres = list(self.D.ESTILOS)
        i, k = ev.x // 70, ev.y // self.ALTO
        if 0 <= i < len(nombres) and k < len(self.D.ESTILOS[nombres[i]]):
            self.estilos[nombres[i]] = self.D.ESTILOS[nombres[i]][k]
            self.dibujar_piezas()

    def todas_piezas(self, estilos):
        self.estilos = dict(estilos)
        self.dibujar_piezas()

    def clic_tema(self, ev):
        i = ev.x // 80
        ops = self.opciones()
        if 0 <= i < len(ops):
            self.tema.set(ops[i][0])
            self.dibujar_temas()

    def probar(self):
        s = self.app.sonidos
        activo, vol = s.activo, s.volumen
        s.activo, s.volumen = True, self.volumen.get()
        s.tocar('captura')
        s.activo, s.volumen = activo, vol

    def restablecer(self):
        d = POR_DEFECTO
        self.tema.set('')
        self.sonido.set(d['sonido'])
        self.volumen.set(d['volumen'])
        self.lbl_vol.configure(text='%d %%' % d['volumen'])
        self.escala.current(ESCALAS.index(d['escala']))
        self.animacion.set(d['animacion'])
        self.barra.set(d['barra_eval'])
        self.pensar.set(d['pensar'])
        self.ayudas.set(d['ayudas'])
        self.avisos.set(d['avisos'])
        self.libro.set(d['libro'])
        self.idioma.current(0)
        self.todas_piezas({})
        self.dibujar_temas()

    def aceptar(self):
        import idioma
        nuevos = {'idioma': idioma.IDIOMAS[max(0, self.idioma.current())][0], 'tema': self.tema.get() or None, 'sonido': self.sonido.get(), 'volumen': int(self.volumen.get()),
                  'escala': ESCALAS[self.escala.current()], 'animacion': self.animacion.get(),
                  'barra_eval': self.barra.get(), 'pensar': self.pensar.get(),
                  'ayudas': self.ayudas.get(), 'avisos': self.avisos.get(), 'libro': self.libro.get(),
                  'piezas': {k: v for k, v in self.estilos.items() if v != 'moderno'}}
        self.top.destroy()
        self.app.aplicar_ajustes(nuevos)
