"""Laboratorio: diseño de variantes propias (tablero, piezas, reglas y posición inicial).

Las variantes se describen como en generico.py y se guardan en la carpeta 'laboratorio'.
"""
import copy, json, re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import generico as G
import variantes as V
from interfaz import px, FONDO, BORDE, ORO, TEXTO, TEXTO_SUAVE, TEMAS, colores_tema, base_clara

NOMBRE_IMAGEN = {'rey': 'Rey', 'dama': 'Dama', 'torre': 'Torre', 'alfil': 'Alfil', 'caballo': 'Caballo',
                 'arzobispo': 'Arzobispo', 'canciller': 'Canciller', 'catapulta': 'Catapulta',
                 'guardian': 'Guardián', 'peon': 'Peón'}
def _bases():
    """[(nombre, clave de generico.PRESETS)] para «Partir de»: las del menú, el Ajedrez Extendido, sus versiones de
    10 × 10, las de «Más variantes» y el tablero vacío."""
    import presets
    claves = ['clasico', 'extendido_lab', 'capablanca', 'capablanca10', 'gotico', 'gotico10'] + presets.OTRAS
    out = [(G.PRESETS[k]['nombre'].replace(' (Laboratorio)', ''), k) for k in claves]
    return out + [('Tablero vacío', None)]


BASES = _bases()


EXTENSION = '.variante.json'


def leer_variante(ruta):
    """La configuración de una variante exportada (o un .json del Laboratorio). ValueError si no sirve."""
    try:
        with open(ruta, encoding='utf-8') as f:
            datos = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError('No se pudo leer el archivo: %s' % e)
    cfg = datos.get('variante') if isinstance(datos, dict) and datos.get('formato') == 'variante-ajedrez' else datos
    if not isinstance(cfg, dict) or not all(k in cfg for k in ('ancho', 'alto', 'piezas', 'posicion', 'reglas')):
        raise ValueError('El archivo no contiene una variante de ajedrez.')
    try:
        G.Motor(cfg).inicial()
    except Exception as e:
        raise ValueError('La variante del archivo tiene un error: %s' % e)
    cfg['id'] = 'laboratorio'
    cfg.setdefault('nombre', 'Variante importada')
    cfg['descripcion'] = 'Variante creada en el Laboratorio.'
    return cfg


def _vacia():
    cfg = copy.deepcopy(G.PRESETS['clasico'])
    cfg['posicion'] = [p for p in cfg['posicion'] if p[2] == 'K']
    cfg['piezas'] = {'K': cfg['piezas']['K']}
    cfg['reglas']['promocion'] = []
    return cfg


class Laboratorio:
    def __init__(self, app, cfg=None):
        self.app, self.root, self.img, self.letra = app, app.root, app.img, app.letra
        self.cfg = copy.deepcopy(cfg) if cfg else copy.deepcopy(G.PRESETS['clasico'])
        self.cfg.setdefault('nombre', 'Mi variante')
        if not cfg:
            from idioma import tr
            self.cfg['nombre'] = tr('Mi variante')
        self.cfg['id'] = 'laboratorio'
        self.cfg['descripcion'] = 'Variante creada en el Laboratorio.'
        self.herr, self.arr, self.oculta = None, None, None
        self.sel_pieza = None
        self.S, self.ox, self.oy = 40, 0, 0
        self.frame = tk.Frame(self.root, bg=FONDO)
        self.construir()
        self.recargar()

    # ------------------------------------------------------------------ interfaz
    def construir(self):
        self.canvas = tk.Canvas(self.frame, bg=FONDO, highlightthickness=0)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.root.after_idle(self.dibujar))
        self.canvas.bind('<Button-1>', self.clic)
        self.canvas.bind('<B1-Motion>', self.arrastrar)
        self.canvas.bind('<ButtonRelease-1>', self.soltar)
        self.canvas.bind('<Button-3>', lambda e: self.poner(self.casilla_en(e.x, e.y), borrar=True))

        panel = ttk.Frame(self.frame, style='Panel.TFrame', padding=(10, 12, 14, 12), width=px(390))
        panel.pack(side='right', fill='y')
        panel.pack_propagate(False)
        arriba = ttk.Frame(panel, style='Panel.TFrame')
        arriba.pack(fill='x')
        ttk.Button(arriba, text='← Menú', style='Menu.TButton', command=self.app.menu).pack(side='right')
        ttk.Label(arriba, text='Laboratorio', style='Titulo.TLabel').pack(side='left')
        ttk.Label(panel, text='Diseña tu variante: tablero, piezas, reglas y posición inicial.',
                  style='Panel.TLabel', wraplength=px(360)).pack(anchor='w', pady=(2, 8))

        abajo = ttk.Frame(panel, style='Panel.TFrame')
        abajo.pack(side='bottom', fill='x', pady=(8, 0))
        ttk.Label(abajo, text='NOMBRE DE LA VARIANTE', style='Sub.TLabel').pack(anchor='w')
        self.var_nombre = tk.StringVar(value=self.cfg['nombre'])
        self.var_nombre.trace_add('write', lambda *x: self._renombrar())
        ttk.Entry(abajo, textvariable=self.var_nombre).pack(fill='x', pady=(2, 6))
        self.lbl_error = ttk.Label(abajo, style='Error.TLabel', wraplength=px(360), justify='left')
        self.lbl_error.pack(anchor='w', fill='x')
        fila = ttk.Frame(abajo, style='Panel.TFrame')
        fila.pack(fill='x', pady=(4, 0))
        ttk.Button(fila, text='Guardar', command=self.guardar).pack(side='left', expand=True, fill='x', padx=(0, 2))
        ttk.Button(fila, text='Ver reglas', command=self.ver_reglas).pack(side='left', expand=True, fill='x', padx=(0, 2))
        ttk.Button(fila, text='Simular…', command=self.simular).pack(side='left', expand=True, fill='x')
        fila = ttk.Frame(abajo, style='Panel.TFrame')
        fila.pack(fill='x', pady=(4, 0))
        ttk.Button(fila, text='Exportar variante…', command=self.exportar).pack(
            side='left', expand=True, fill='x', padx=(0, 2))
        ttk.Button(fila, text='Importar variante…', command=self.importar).pack(side='left', expand=True, fill='x')
        ttk.Button(abajo, text='Jugar ▶', style='Comenzar.TButton', command=self.jugar).pack(fill='x', pady=(6, 0))

        self.nb = ttk.Notebook(panel, style='Panel.TNotebook')
        self.nb.pack(fill='both', expand=True)
        self.tab_tablero = self._tab('Tablero')
        self.tab_piezas = self._tab('Piezas')
        self.tab_reglas = self._tab('Reglas')
        self.tab_posicion = self._tab('Posición')
        self.construir_tablero()
        self.construir_piezas()
        self.construir_posicion()

    def _tab(self, texto):
        f = ttk.Frame(self.nb, style='Panel.TFrame', padding=(4, 10, 4, 4))
        self.nb.add(f, text=texto)
        return f

    def construir_tablero(self):
        f = self.tab_tablero
        ttk.Label(f, text='PARTIR DE', style='Sub.TLabel').pack(anchor='w')
        self.cmb_base = ttk.Combobox(f, state='readonly')
        self.cmb_base.pack(fill='x', pady=(2, 12))
        self.cmb_base.bind('<<ComboboxSelected>>', self.cargar_base)
        ttk.Label(f, text='TAMAÑO', style='Sub.TLabel').pack(anchor='w')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 12))
        self.var_ancho, self.var_alto = tk.IntVar(), tk.IntVar()
        for txt, var in (('Columnas', self.var_ancho), ('Filas', self.var_alto)):
            ttk.Label(fila, text=txt, style='Panel.TLabel').pack(side='left')
            ttk.Spinbox(fila, from_=5, to=12, width=4, textvariable=var, state='readonly',
                        command=self.redimensionar).pack(side='left', padx=(4, 16))
        ttk.Label(f, text='ESTILO DEL TABLERO', style='Sub.TLabel').pack(anchor='w')
        self.cv_temas = tk.Canvas(f, height=2 * 74, width=360, bg=FONDO, highlightthickness=0, cursor='hand2')
        self.cv_temas.pack(anchor='w', pady=(4, 12))
        self.cv_temas.bind('<Button-1>', self.clic_tema)
        ttk.Label(f, text='Las variantes guardadas aparecen en «Partir de». Cambiar el tamaño conserva '
                          'las piezas que caben; en «Posición» puedes recolocarlas.',
                  style='Panel.TLabel', wraplength=350, justify='left').pack(anchor='w')

    def construir_piezas(self):
        f = self.tab_piezas
        ttk.Label(f, text='PIEZAS DE LA VARIANTE', style='Sub.TLabel').pack(anchor='w')
        self.cv_piezas = tk.Canvas(f, width=360, height=300, bg='#25201C', highlightthickness=0)
        self.cv_piezas.pack(fill='both', expand=True, pady=(2, 6))
        self.cv_piezas.bind('<Button-1>', self.clic_lista)
        self.cv_piezas.bind('<Double-Button-1>', lambda e: self.editar_pieza())
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x')
        self.btn_catalogo = ttk.Button(fila, text='Del catálogo ▾', command=self.menu_catalogo)
        self.btn_catalogo.pack(side='left', expand=True, fill='x', padx=(0, 2))
        ttk.Button(fila, text='Nueva pieza', command=lambda: self.editar_pieza(nueva=True)).pack(
            side='left', expand=True, fill='x', padx=(0, 2))
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 0))
        ttk.Button(fila, text='Editar', command=self.editar_pieza).pack(side='left', expand=True, fill='x', padx=(0, 2))
        ttk.Button(fila, text='Quitar', command=self.quitar_pieza).pack(side='left', expand=True, fill='x')

    def construir_reglas(self):
        marco = self.tab_reglas
        for w in marco.winfo_children():
            w.destroy()
        # con desplazamiento: hay más reglas de las que caben
        cv = tk.Canvas(marco, bg=FONDO, highlightthickness=0, width=350)
        barra = ttk.Scrollbar(marco, command=cv.yview)
        cv.configure(yscrollcommand=barra.set)
        barra.pack(side='right', fill='y')
        cv.pack(side='left', fill='both', expand=True)
        f = ttk.Frame(cv, style='Panel.TFrame')
        cv.create_window(0, 0, window=f, anchor='nw')
        f.bind('<Configure>', lambda e: cv.configure(scrollregion=cv.bbox('all')))
        for w in (cv, f):
            w.bind('<Button-4>', lambda e: cv.yview_scroll(-2, 'units'))
            w.bind('<Button-5>', lambda e: cv.yview_scroll(2, 'units'))
            w.bind('<MouseWheel>', lambda e: cv.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
        r = self.cfg['reglas']
        for k, v in G.REGLAS_BASE.items():
            r.setdefault(k, v)
        self.vars_reglas = {}

        def var(clave, tipo=tk.BooleanVar, valor=None):
            v = tipo(value=r[clave] if valor is None else valor)
            v.trace_add('write', lambda *a: self.cambio_regla(clave, v))
            self.vars_reglas[clave] = v
            return v

        def sub(texto, arriba=0):
            ttk.Label(f, text=texto, style='Sub.TLabel').pack(anchor='w', pady=(arriba, 0))

        sub('OBJETIVO')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 8))
        v = var('objetivo', tk.StringVar)
        for txt, val in (('Jaque mate', 'mate'), ('Capturar al rey', 'capturar_rey')):
            ttk.Radiobutton(fila, text=txt, value=val, variable=v, style='Panel.TRadiobutton').pack(side='left', padx=(0, 14))
        sub('SI UN BANDO NO PUEDE MOVER (AHOGADO)')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 8))
        v = var('ahogado', tk.StringVar)
        for txt, val in (('Tablas', 'tablas'), ('Gana quien ahoga', 'victoria')):
            ttk.Radiobutton(fila, text=txt, value=val, variable=v, style='Panel.TRadiobutton').pack(side='left', padx=(0, 14))
        sub('MOVIMIENTOS ESPECIALES')
        pasos = r['pasos_enroque']
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 0))
        ttk.Checkbutton(fila, text='Enroque; el rey avanza', variable=var('enroque'),
                        style='Panel.TCheckbutton').pack(side='left')
        if isinstance(pasos, (list, tuple)):  # distinto a cada lado (Jano)
            ttk.Label(fila, text='%d casillas hacia la columna a y %d hacia la otra' % tuple(pasos[:2]),
                      style='Panel.TLabel').pack(side='left', padx=4)
        else:
            ttk.Spinbox(fila, from_=1, to=5, width=3, state='readonly',
                        textvariable=var('pasos_enroque', tk.IntVar)).pack(side='left', padx=4)
            ttk.Label(fila, text='casillas', style='Panel.TLabel').pack(side='left')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x')
        ttk.Checkbutton(fila, text='Primer avance del peón: hasta', variable=var('doble_paso'),
                        style='Panel.TCheckbutton').pack(side='left')
        ttk.Spinbox(fila, from_=2, to=4, width=3, state='readonly', textvariable=var('pasos_peon', tk.IntVar)).pack(
            side='left', padx=4)
        ttk.Label(fila, text='casillas', style='Panel.TLabel').pack(side='left')
        ttk.Checkbutton(f, text='Captura al paso', variable=var('al_paso'),
                        style='Panel.TCheckbutton').pack(anchor='w', pady=(0, 8))
        sub('EL PEÓN PROMOCIONA A')
        cont = ttk.Frame(f, style='Panel.TFrame')
        cont.pack(fill='x', pady=(2, 4))
        self.vars_promo = {}
        candidatas = [t for t in self._ordenadas() if not self._def(t).get('real') and not self._def(t).get('peon')]
        for i, t in enumerate(candidatas):
            v = tk.BooleanVar(value=t in r['promocion'])
            v.trace_add('write', lambda *a: self.cambio_promocion())
            self.vars_promo[t] = v
            ttk.Checkbutton(cont, text=self._def(t)['nombre'], variable=v, style='Panel.TCheckbutton').grid(
                row=i // 3, column=i % 3, sticky='w', padx=(0, 10))
        if not candidatas:
            ttk.Label(cont, text='(agrega piezas para elegir)', style='Panel.TLabel').grid(row=0, column=0)
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x')
        ttk.Label(fila, text='En las últimas', style='Panel.TLabel').pack(side='left')
        ttk.Spinbox(fila, from_=1, to=4, width=3, state='readonly', textvariable=var('zona_promocion', tk.IntVar)).pack(
            side='left', padx=4)
        ttk.Label(fila, text='filas', style='Panel.TLabel').pack(side='left')
        ttk.Checkbutton(f, text='Antes de la última fila, promocionar es opcional', variable=var('promocion_opcional'),
                        style='Panel.TCheckbutton').pack(anchor='w')
        ttk.Checkbutton(f, text='Solo a piezas propias ya capturadas (Gran Ajedrez)',
                        variable=var('promocion_capturadas'), style='Panel.TCheckbutton').pack(anchor='w')
        ttk.Label(f, text='Las formas extendidas y las conversiones de cada pieza se eligen al editarla (pestaña '
                          '«Propiedades y extensión»).', style='Panel.TLabel', wraplength=330,
                  justify='left').pack(anchor='w', pady=(2, 8))
        sub('LA PARTIDA TERMINA EN TABLAS POR')
        for clave, txt in (('repeticion', 'Triple repetición'), ('cincuenta', 'Regla de las 50 jugadas'),
                           ('material', 'Material insuficiente')):
            ttk.Checkbutton(f, text=txt, variable=var(clave), style='Panel.TCheckbutton').pack(anchor='w')
        ttk.Checkbutton(f, text='…salvo desempate por puntos: gana quien capturó más (Ajedrez Extendido)',
                        variable=var('desempate'), style='Panel.TCheckbutton', ).pack(anchor='w', pady=(4, 0))

    def construir_posicion(self):
        f = self.tab_posicion
        ttk.Label(f, text='Elige una pieza y haz clic en el tablero. Arrastra para mover; suelta fuera del '
                          'tablero o usa clic derecho para quitar.', style='Panel.TLabel', wraplength=350,
                  justify='left').pack(anchor='w', pady=(0, 8))
        self.paleta = tk.Canvas(f, width=360, height=200, bg=FONDO, highlightthickness=0, cursor='hand2')
        self.paleta.pack(anchor='w')
        self.paleta.bind('<Button-1>', self.clic_paleta)
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(6, 0))
        self.btn_goma = ttk.Button(fila, text='Goma', command=lambda: self.elegir('borrar'))
        self.btn_goma.pack(side='left', expand=True, fill='x', padx=(0, 2))
        ttk.Button(fila, text='Vaciar', command=self.vaciar).pack(side='left', expand=True, fill='x')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 0))
        ttk.Button(fila, text='Colocación automática', command=self.autocolocar).pack(
            side='left', expand=True, fill='x', padx=(0, 2))
        ttk.Button(fila, text='Blancas → negras', command=self.espejo).pack(side='left', expand=True, fill='x')
        ttk.Label(f, text='«Blancas → negras» copia en espejo la mitad de las blancas para el otro bando.',
                  style='Panel.TLabel', wraplength=350, justify='left').pack(anchor='w', pady=(8, 0))

    # ------------------------------------------------------------------ estado
    def _def(self, t):
        return self.cfg['piezas'][t]

    def _ordenadas(self, extendidas=False):
        """Tipos de pieza, del rey a los peones; las formas extendidas (con 'base') solo si se piden."""
        d = self.cfg['piezas']
        return sorted((t for t in d if extendidas or not d[t].get('base')),
                      key=lambda t: (not d[t].get('real'), bool(d[t].get('peon')),
                                     -(d[t].get('valor') or 0), d[t]['nombre']))

    def recargar(self):
        """Refresca toda la interfaz a partir de self.cfg."""
        self.var_ancho.set(self.cfg['ancho'])
        self.var_alto.set(self.cfg['alto'])
        self.var_nombre.set(self.cfg['nombre'])
        nombres = [n for n, _ in BASES] + ['Guardada: ' + c['nombre'] for c in V.guardadas()]
        self.cmb_base.configure(values=nombres)
        self.cmb_base.set('Elige una base…')
        if self.herr not in (None, 'borrar') and self.herr[0] not in self.cfg['piezas']:
            self.herr = None
        if self.sel_pieza not in self.cfg['piezas']:
            self.sel_pieza = None
        self.construir_reglas()
        self.dibujar_temas()
        self.dibujar_lista()
        self.dibujar_paleta()
        self.dibujar()

    def cargar_base(self, ev=None):
        i = self.cmb_base.current()
        nombre = self.var_nombre.get()
        if i < len(BASES):
            clave = BASES[i][1]
            cfg = copy.deepcopy(G.PRESETS[clave]) if clave else _vacia()
            cfg['nombre'] = nombre
        else:
            cfg = copy.deepcopy(V.guardadas()[i - len(BASES)])
        cfg['id'] = 'laboratorio'
        cfg['descripcion'] = 'Variante creada en el Laboratorio.'
        self.cfg = cfg
        self.recargar()

    def _renombrar(self):
        self.cfg['nombre'] = self.var_nombre.get().strip() or 'Mi variante'
        self.dibujar()

    def cambio_regla(self, clave, var):
        try:
            self.cfg['reglas'][clave] = var.get()
        except tk.TclError:
            pass

    def cambio_promocion(self):
        self.cfg['reglas']['promocion'] = [t for t, v in self.vars_promo.items() if v.get()]

    def redimensionar(self):
        W0, H0 = self.cfg['ancho'], self.cfg['alto']
        W, H = self.var_ancho.get(), self.var_alto.get()
        nueva = []
        for c, r, t, col in self.cfg['posicion']:
            if r >= H0 / 2:
                r += H - H0  # las piezas de arriba siguen pegadas al borde superior
            if 0 <= c < W and 0 <= r < H:
                nueva.append([c, r, t, col])
        self.cfg.update(ancho=W, alto=H, posicion=nueva)
        self.dibujar()

    # ------------------------------------------------------------------ temas
    def dibujar_temas(self):
        cv = self.cv_temas
        cv.delete('all')
        for i, (clave, (nombre, clara, oscura)) in enumerate(TEMAS.items()):
            x, y = (i % 3) * 120, (i // 3) * 74
            if self.cfg.get('tema', 'madera') == clave:
                cv.create_rectangle(x + 2, y + 2, x + 116, y + 70, outline=ORO, width=2)
            for k in range(4):
                for j in range(3):
                    cv.create_rectangle(x + 12 + k * 22, y + 8 + j * 14, x + 34 + k * 22, y + 22 + j * 14,
                                        fill=clara if (k + j) % 2 == 0 else oscura, outline='')
            cv.create_text(x + 59, y + 60, text=nombre, fill=TEXTO, font=(self.letra, 9, 'bold'))

    def clic_tema(self, ev):
        i = int(ev.y // 74) * 3 + int(ev.x // 120)
        claves = list(TEMAS)
        if 0 <= ev.x < 360 and 0 <= i < len(claves):
            self.cfg['tema'] = claves[i]
            self.dibujar_temas()
            self.dibujar()

    # ------------------------------------------------------------------ piezas
    def dibujar_lista(self):
        cv = self.cv_piezas
        cv.delete('all')
        self.filas_lista = self._ordenadas()
        for i, t in enumerate(self.filas_lista):
            d = self._def(t)
            y = i * 46
            if t == self.sel_pieza:
                cv.create_rectangle(0, y, 360, y + 46, fill='#4A3E33', outline='')
            cv.create_image(26, y + 23, image=self.img.get(V.ruta_imagen(d['imagen'], 0, d.get('dorada')), 38))
            cv.create_text(54, y + 15, text=d['nombre'], anchor='w', fill='#F3E2BE', font=(self.letra, 11, 'bold'))
            etiquetas = [('Rey' if d.get('real') else 'Peón' if d.get('peon') else ''), _describir(d)]
            if d.get('enroca'):
                etiquetas.append('enroca')
            ext = (d.get('extension') or {}).get('pieza')
            if ext in self.cfg['piezas']:
                etiquetas.append('se extiende')
            conv = (d.get('conversion') or {}).get('pieza')
            if conv in self.cfg['piezas']:
                etiquetas.append('se convierte en ' + self._def(conv)['nombre'])
            cv.create_text(54, y + 33, text=' · '.join(e for e in etiquetas if e), anchor='w', fill=TEXTO_SUAVE,
                           font=(self.letra, 8), width=230)
            valor = d.get('valor')
            cv.create_text(350, y + 23, anchor='e', fill=ORO, font=(self.letra, 10, 'bold'),
                           text='' if d.get('real') else '%g' % (valor if valor is not None else 0))
        cv.configure(scrollregion=(0, 0, 360, len(self.filas_lista) * 46))

    def clic_lista(self, ev):
        i = int(self.cv_piezas.canvasy(ev.y) // 46)
        if 0 <= i < len(self.filas_lista):
            self.sel_pieza = self.filas_lista[i]
            self.dibujar_lista()

    def menu_catalogo(self):
        import piezas_magicas as PM
        from idioma import tr
        m = tk.Menu(self.root, tearoff=0)
        libres = [t for t in G.CATALOGO if t not in self.cfg['piezas']]
        clasicas = tk.Menu(m, tearoff=0)
        for t in libres:
            d = G.CATALOGO[t]
            clasicas.add_command(label='%s  (%s)' % (d['nombre'], _describir(d) or 'peón'),
                                 command=lambda t=t: self.agregar(t, copy.deepcopy(G.CATALOGO[t])))
        if not libres:
            clasicas.add_command(label='Ya están todas', state='disabled')
        m.add_cascade(label='Piezas clásicas', menu=clasicas)
        for cat, titulo, _ in PM.CATEGORIAS:
            sub = tk.Menu(m, tearoff=0)
            for clave in PM.claves(cat):
                sub.add_command(label='%s  —  %s' % (tr(PM.nombre(clave)), tr(PM.descripcion(clave))[:70]),
                                command=lambda c=clave: self.agregar_magica(c))
            m.add_cascade(label=titulo, menu=sub)
        b = self.btn_catalogo
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def _tipo_libre(self, base):
        base = re.sub(r'[^A-Z0-9]', '', base.upper())[:3] or 'X'
        t, n = base, 2
        while t in self.cfg['piezas'] or t + '+' in self.cfg['piezas']:
            t, n = '%s%d' % (base, n), n + 1
        return t

    def agregar_magica(self, clave):
        """Añade una pieza del catálogo de piezas mágicas (con su forma extendida, si la tiene)."""
        d = __import__('disenos').pieza_prediseno(clave)
        t = self._tipo_libre(d.get('simbolo') or clave)
        ext = d.pop('_ext_def', None)
        if ext is not None and d.get('extension'):
            ext['base'] = t
            d['extension']['pieza'] = t + '+'
            self.cfg['piezas'][t + '+'] = ext
        elif d.get('extension'):
            d.pop('extension')
        for m in d.get('movs', []):  # empujes e intercambios con peones: los de esta variante
            if ('empuje' in m or 'intercambio' in m) and not any(x in self.cfg['piezas'] for x in m.get('tipos', [])):
                m['tipos'] = [x for x, y in self.cfg['piezas'].items() if y.get('peon')]
        if d.get('peon'):
            self.agregar(t, d)
            return
        self.agregar(t, d)

    def agregar(self, t, d):
        self.cfg['piezas'][t] = d
        self.sel_pieza = t
        if not d.get('real') and not d.get('peon') and t not in self.cfg['reglas']['promocion']:
            if 'P' in self.cfg['piezas'] or any(x.get('peon') for x in self.cfg['piezas'].values()):
                self.cfg['reglas']['promocion'].append(t)
        self.recargar()

    def quitar_pieza(self):
        t = self.sel_pieza
        if t is None:
            return
        if self._def(t).get('real') and sum(1 for d in self.cfg['piezas'].values() if d.get('real')) == 1:
            messagebox.showinfo('Laboratorio', 'La variante necesita una pieza real (el rey).', parent=self.root)
            return
        quitar = {t} | {x for x, d in self.cfg['piezas'].items() if d.get('base') == t}
        self._quitar_tipos(quitar)
        self.recargar()

    def _quitar_tipos(self, quitar):
        """Quita esos tipos de pieza y lo que los menciona (posición, promoción, extensiones, conversiones...)."""
        for x in quitar:
            self.cfg['piezas'].pop(x, None)
        self.cfg['posicion'] = [p for p in self.cfg['posicion'] if p[2] not in quitar]
        self.cfg['reglas']['promocion'] = [x for x in self.cfg['reglas']['promocion'] if x not in quitar]
        for d in self.cfg['piezas'].values():
            if (d.get('extension') or {}).get('pieza') in quitar:
                d.pop('extension')
            if (d.get('conversion') or {}).get('pieza') in quitar:
                d.pop('conversion')
            for m in d.get('movs', []):
                if 'tipos' in m:
                    m['tipos'] = [x for x in m['tipos'] if x not in quitar]

    def editar_pieza(self, nueva=False):
        if not nueva and self.sel_pieza is None:
            return
        if nueva:
            n = 1
            while 'X%d' % n in self.cfg['piezas']:
                n += 1
            t = 'X%d' % n
            # tablero vacío: la pieza no tiene movimientos hasta que los elijas (o partas de un prediseño)
            d = {'nombre': 'Pieza nueva', 'simbolo': 'N%d' % n, 'imagen': 'pre:diamante', 'dorada': False,
                 'valor': None, 'movs': []}
        else:
            t, d = self.sel_pieza, copy.deepcopy(self._def(self.sel_pieza))
        EditorPieza(self, t, d, nueva)

    def pieza_editada(self, t, d, nueva, ext=None):
        """Guarda la pieza editada y su forma extendida ('t+', o se quita si ya no tiene)."""
        if d.get('real'):  # solo una pieza real por variante
            for x, otra in self.cfg['piezas'].items():
                if x != t and otra.get('real'):
                    otra['real'] = False
        clave_ext = t + '+'
        if ext is not None:
            ext = copy.deepcopy(ext)
            ext['base'] = t
            self.cfg['piezas'][clave_ext] = ext
        elif clave_ext in self.cfg['piezas'] and self._def(clave_ext).get('base') == t:
            self.cfg['piezas'][t] = d
            self._quitar_tipos({clave_ext})
        if nueva:
            self.agregar(t, d)
        else:
            self.cfg['piezas'][t] = d
            if d.get('real') or d.get('peon'):
                self.cfg['reglas']['promocion'] = [x for x in self.cfg['reglas']['promocion'] if x != t]
            self.recargar()

    # ------------------------------------------------------------------ posición
    def dibujar_paleta(self):
        cv = self.paleta
        cv.delete('all')
        tipos = self._ordenadas()
        self.paleta_tipos = tipos
        filas = (len(tipos) + 5) // 6
        cv.configure(height=max(1, 2 * filas) * 48)
        for c in (0, 1):
            for i, t in enumerate(tipos):
                x, y = (i % 6) * 60, (c * filas + i // 6) * 48
                if self.herr == (t, c):
                    cv.create_rectangle(x + 1, y + 1, x + 59, y + 47, fill='#C9A46A', outline='')
                elif c == 1:
                    base_clara(cv, x + 5, y + 3, x + 55, y + 45)
                d = self._def(t)
                cv.create_image(x + 30, y + 24, image=self.img.get(V.ruta_imagen(d['imagen'], c, d.get('dorada')), 42))
        self.btn_goma.configure(style='PestanaActiva.TButton' if self.herr == 'borrar' else 'TButton')

    def clic_paleta(self, ev):
        filas = (len(self.paleta_tipos) + 5) // 6
        col, fila = int(ev.x // 60), int(ev.y // 48)
        c, i = (fila // filas if filas else 0), (fila % filas if filas else 0) * 6 + col
        if 0 <= col < 6 and c in (0, 1) and i < len(self.paleta_tipos):
            self.elegir((self.paleta_tipos[i], c))

    def elegir(self, herr):
        self.herr = herr
        self.dibujar_paleta()
        self.nb.select(self.tab_posicion)

    def _mapa(self):
        W = self.cfg['ancho']
        return {r * W + c: (t, col) for c, r, t, col in self.cfg['posicion']}

    def _guardar_mapa(self, mapa):
        W = self.cfg['ancho']
        self.cfg['posicion'] = [[sq % W, sq // W, t, col] for sq, (t, col) in sorted(mapa.items())]
        self.dibujar()

    def poner(self, sq, borrar=False):
        if sq is None:
            return
        mapa = self._mapa()
        if borrar or self.herr == 'borrar':
            mapa.pop(sq, None)
        elif self.herr is None:
            self.lbl_error.configure(text='Elige primero una pieza en la pestaña «Posición».')
            self.nb.select(self.tab_posicion)
            return
        else:
            t, c = self.herr
            if mapa.get(sq) == (t, c):
                del mapa[sq]
            else:
                if self._def(t).get('real'):
                    mapa = {s: v for s, v in mapa.items() if not (v[1] == c and self._def(v[0]).get('real'))}
                mapa[sq] = (t, c)
        self.lbl_error.configure(text='')
        self._guardar_mapa(mapa)

    def vaciar(self):
        self.cfg['posicion'] = []
        self.dibujar()

    def espejo(self):
        H = self.cfg['alto']
        blancas = [p for p in self.cfg['posicion'] if p[3] == 0 and p[1] < H / 2]
        self.cfg['posicion'] = blancas + [[c, H - 1 - r, t, 1] for c, r, t, _ in blancas]
        self.dibujar()

    def autocolocar(self):
        cfg, W, H = self.cfg, self.cfg['ancho'], self.cfg['alto']
        tipos = self._ordenadas()
        reyes = [t for t in tipos if self._def(t).get('real')]
        peones = [t for t in tipos if self._def(t).get('peon')]
        otras = [t for t in tipos if t not in reyes and t not in peones]
        fila = None
        for base in G.PRESETS.values():  # si encaja una posición conocida, se usa
            orden = [p[2] for p in sorted(base['posicion'], key=lambda p: p[0]) if p[1] == 0 and p[3] == 0]
            if len(orden) == W and set(orden) <= set(cfg['piezas']):
                fila = orden
                break
        if fila is None:
            fila = [None] * W
            if reyes:
                fila[W // 2] = reyes[0]
            huecos = sorted((i for i in range(W) if fila[i] is None), key=lambda i: -abs(i - (W - 1) / 2))
            enroque = [t for t in otras if self._def(t).get('enroca')]
            resto = [t for t in otras if t not in enroque] or enroque
            secuencia = enroque * 2 + [t for t in resto for _ in (0, 1)]
            while secuencia and len(secuencia) < len(huecos):
                secuencia += resto
            for i, t in zip(huecos, secuencia):
                fila[i] = t
        pos = []
        for c, t in enumerate(fila):
            if t:
                pos += [[c, 0, t, 0], [c, H - 1, t, 1]]
        if peones and H >= 5:
            for c in range(W):
                pos += [[c, 1, peones[0], 0], [c, H - 2, peones[0], 1]]
        cfg['posicion'] = pos
        self.dibujar()

    # ------------------------------------------------------------------ tablero
    def xy(self, sq):
        W, H = self.cfg['ancho'], self.cfg['alto']
        return self.ox + (sq % W) * self.S, self.oy + (H - 1 - sq // W) * self.S

    def casilla_en(self, x, y):
        W, H = self.cfg['ancho'], self.cfg['alto']
        if x < self.ox or y < self.oy:
            return None
        c, r = int((x - self.ox) // self.S), int((y - self.oy) // self.S)
        if not (0 <= c < W and 0 <= r < H):
            return None
        return (H - 1 - r) * W + c

    def dibujar(self):
        cv = self.canvas
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 50:
            return
        W, H = self.cfg['ancho'], self.cfg['alto']
        S = self.S = max(20, int(min(w / (W + 0.9), (h - 40) / (H + 0.9))))
        self.ox, self.oy = (w - W * S) // 2, (h - H * S) // 2 + 10
        cv.delete('all')
        cv.create_text(w / 2, self.oy - S * 0.55 - 8, text='%s · %d × %d' % (self.var_nombre.get(), W, H),
                       fill=ORO, font=(self.app.serif, 16, 'bold'))
        clara, oscura = colores_tema(self.cfg.get('tema', 'madera'))[:2]
        cv.create_rectangle(self.ox - 3, self.oy - 3, self.ox + W * S + 3, self.oy + H * S + 3, fill=BORDE, outline='')
        mapa = self._mapa()
        tam = int(S * 0.9)
        fuente = (self.letra, max(8, S // 6), 'bold')
        for sq in range(W * H):
            x, y = self.xy(sq)
            cv.create_rectangle(x, y, x + S, y + S, outline='',
                                fill=clara if (sq % W + sq // W) % 2 == 0 else oscura)
            if sq in mapa and sq != self.oculta:
                t, c = mapa[sq]
                d = self._def(t)
                cv.create_image(x + S / 2, y + S / 2, image=self.img.get(V.ruta_imagen(d['imagen'], c, d.get('dorada')), tam))
        for i in range(W):
            cv.create_text(self.ox + i * S + S / 2, self.oy + H * S + S * 0.25, text=G.LETRAS[i], fill='#D8C7A8', font=fuente)
        for i in range(H):
            cv.create_text(self.ox - S * 0.25, self.oy + i * S + S / 2, text=str(H - i), fill='#D8C7A8', font=fuente)

    def clic(self, ev):
        sq = self.casilla_en(ev.x, ev.y)
        if sq is not None and sq in self._mapa():
            self.arr = {'desde': sq, 'x': ev.x, 'y': ev.y, 'activo': False}
        else:
            self.poner(sq)

    def arrastrar(self, ev):
        a = self.arr
        if a is None:
            return
        if not a['activo']:
            if abs(ev.x - a['x']) + abs(ev.y - a['y']) < 5:
                return
            a['activo'] = True
            self.oculta = a['desde']
            self.dibujar()
            t, c = self._mapa()[a['desde']]
            d = self._def(t)
            self.canvas.create_image(ev.x, ev.y, tags='arrastre', image=self.img.get(
                V.ruta_imagen(d['imagen'], c, d.get('dorada')), int(self.S * 0.9)))
            self.canvas.configure(cursor='fleur')
        self.canvas.coords('arrastre', ev.x, ev.y)

    def soltar(self, ev):
        a, self.arr = self.arr, None
        if a is None:
            return
        if not a['activo']:
            self.poner(a['desde'])
            return
        self.oculta = None
        self.canvas.configure(cursor='')
        mapa = self._mapa()
        pieza = mapa.pop(a['desde'])
        destino = self.casilla_en(ev.x, ev.y)
        if destino is not None:
            mapa[destino] = pieza
        self._guardar_mapa(mapa)

    # ------------------------------------------------------------------ guardar y jugar
    def _validar(self):
        cfg = self.cfg
        cfg['nombre'] = self.var_nombre.get().strip() or 'Mi variante'
        reales = {t for t, d in cfg['piezas'].items() if d.get('real')}
        for c in (0, 1):
            n = sum(1 for p in cfg['posicion'] if p[3] == c and p[2] in reales)
            if n != 1:
                return 'Cada bando necesita exactamente una pieza real (rey) en el tablero.'
            if not any(p[3] == c and p[2] not in reales for p in cfg['posicion']):
                return 'Cada bando necesita al menos una pieza además del rey.'
        try:
            m = G.Motor(cfg)
            st = m.inicial()
        except Exception as e:  # una definición incompleta no debe cerrar la aplicación
            return 'La variante tiene un error: %s' % e
        if m.mate and m.en_jaque(st, 1):
            return 'El rey negro empieza en jaque: cambia la posición inicial.'
        if not m.legal(st):
            return 'Las blancas no tienen ninguna jugada en la posición inicial.'
        return None

    def guardar(self):
        aviso = self._validar()
        ruta = V.guardar(copy.deepcopy(self.cfg))
        self.lbl_error.configure(text='Guardada en %s.%s' % (ruta.split('/Juego/')[-1],
                                                              (' Antes de jugar: ' + aviso) if aviso else ''))
        self.cmb_base.configure(values=[n for n, _ in BASES] + ['Guardada: ' + c['nombre'] for c in V.guardadas()])

    def exportar(self):
        """Guarda la variante en un archivo para compartirla (se abre con «Importar variante…»)."""
        error = self._validar()
        if error and not messagebox.askyesno('Exportar', 'La variante aún tiene un problema:\n%s\n\n¿Exportarla de '
                                             'todos modos?' % error, parent=self.root):
            return
        nombre = re.sub(r'[^\w]+', '_', self.cfg['nombre']).strip('_') or 'variante'
        ruta = filedialog.asksaveasfilename(parent=self.root, title='Exportar variante', defaultextension=EXTENSION,
                                            initialfile=nombre + EXTENSION,
                                            filetypes=[('Variante de ajedrez', '*' + EXTENSION),
                                                       ('JSON', '*.json'), ('Todos los archivos', '*')])
        if not ruta:
            return
        datos = {'formato': 'variante-ajedrez', 'version': 1, 'variante': copy.deepcopy(self.cfg)}
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        self.lbl_error.configure(text='Exportada en %s. Compártela: se abre con «Importar variante…».' % ruta)

    def importar(self):
        ruta = filedialog.askopenfilename(parent=self.root, title='Importar variante',
                                          filetypes=[('Variante de ajedrez', '*' + EXTENSION + ' *.json'),
                                                     ('Todos los archivos', '*')])
        if not ruta:
            return
        try:
            cfg = leer_variante(ruta)
        except ValueError as e:
            messagebox.showerror('Importar variante', str(e), parent=self.root)
            return
        nombres = {c['nombre'] for c in V.guardadas()}
        base, k = cfg['nombre'], 2
        while cfg['nombre'] in nombres:  # no se sobrescribe una variante tuya con el mismo nombre
            cfg['nombre'] = '%s (%d)' % (base, k)
            k += 1
        self.cfg = cfg
        V.guardar(copy.deepcopy(cfg))
        self.recargar()
        self.lbl_error.configure(text='Importada y guardada como «%s». Ya puedes jugarla, simularla o editarla.'
                                 % cfg['nombre'])

    def ver_reglas(self):
        from reglas import VentanaReglas
        self.cfg['nombre'] = self.var_nombre.get().strip() or 'Mi variante'
        VentanaReglas(self.app, V.Generica(copy.deepcopy(self.cfg)))

    def simular(self):
        error = self._validar()
        if error:
            self.lbl_error.configure(text=error)
            return
        from simulacion import VentanaSimular
        VentanaSimular(self.app, copy.deepcopy(self.cfg))

    def jugar(self):
        error = self._validar()
        if error:
            self.lbl_error.configure(text=error)
            return
        cfg = copy.deepcopy(self.cfg)
        self.app.jugar(V.Generica(cfg), volver=lambda: self.app.laboratorio(cfg))


def _describir(d):
    return '' if d.get('peon') else G.describir_movs(d)


from editor_piezas import EditorPieza  # noqa: E402  (el editor de piezas vive en su propio módulo)
