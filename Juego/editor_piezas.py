"""Editor de piezas del Laboratorio: movimientos casilla por casilla en un tablero vacío (saltando o con el camino
libre, con condiciones), líneas rectas y diagonales, combinación con otras piezas, movimientos especiales
(pantallas, filas de piezas, cadenas, jinetes, piezas torcidas, empujes e intercambios), propiedades (bloqueo de
saltos, avance de peón), la forma extendida y sus reglas, el catálogo de piezas mágicas, la galería de imágenes y
el diseñador de imágenes propias."""
import copy
import tkinter as tk
from tkinter import ttk, messagebox

import generico as G
import variantes as V
import disenos as DS
from interfaz import FONDO, BORDE, ORO, TEXTO, TEXTO_SUAVE, colores_tema, base_clara

COLOR_MODO = {'ambos': '#3E8E41', 'mov': '#3B6FB6', 'cap': '#C0392B'}
NOMBRE_MODO = [('ambos', 'Mueve y captura'), ('mov', 'Solo mueve'), ('cap', 'Solo captura')]
IMAGENES_JUEGO = ['rey', 'dama', 'torre', 'alfil', 'caballo', 'arzobispo', 'canciller', 'catapulta', 'guardian', 'peon']
R = 5  # el tablero del editor va de -5 a 5 alrededor de la pieza


def galeria(cv, items, tam, columnas, img, al_elegir, elegido=None, pie=True):
    """Dibuja una cuadrícula de imágenes con su nombre; items: [(clave, ruta_png, texto)]."""
    cv.delete('all')
    alto_celda = tam + (18 if pie else 6)
    for k, (clave, ruta, texto) in enumerate(items):
        x, y = (k % columnas) * (tam + 10) + 4, (k // columnas) * alto_celda + 4
        tag = 'g%d' % k
        cv.create_rectangle(x - 2, y - 2, x + tam + 2, y + tam + 2, outline=ORO if clave == elegido else BORDE,
                            width=3 if clave == elegido else 1, tags=tag, fill='#3A322B')
        cv.create_image(x + tam / 2, y + tam / 2, image=img(ruta, tam - 6), tags=tag)
        if pie:
            cv.create_text(x + tam / 2, y + tam + 9, text=texto, fill=TEXTO_SUAVE, font=('Sans', 8), tags=tag,
                           width=tam + 8)
        cv.tag_bind(tag, '<Button-1>', lambda e, c=clave: al_elegir(c))
        cv.tag_bind(tag, '<Enter>', lambda e: cv.configure(cursor='hand2'))
        cv.tag_bind(tag, '<Leave>', lambda e: cv.configure(cursor=''))
    filas = (len(items) + columnas - 1) // columnas
    cv.configure(scrollregion=(0, 0, columnas * (tam + 10), filas * alto_celda + 8))


def con_barra(padre, ancho, alto):
    marco = ttk.Frame(padre, style='Panel.TFrame')
    cv = tk.Canvas(marco, width=ancho, height=alto, bg=FONDO, highlightthickness=0)
    barra = ttk.Scrollbar(marco, command=cv.yview)
    cv.configure(yscrollcommand=barra.set)
    barra.pack(side='right', fill='y')
    cv.pack(side='left', fill='both', expand=True)
    cv.bind('<Button-4>', lambda e: cv.yview_scroll(-2, 'units'))
    cv.bind('<Button-5>', lambda e: cv.yview_scroll(2, 'units'))
    cv.bind('<MouseWheel>', lambda e: cv.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
    return marco, cv


# ====================================================================== editor de piezas
CONDICIONES = [(None, 'Siempre'), ('primera', 'Solo en su primer avance'), ('jaque', 'Solo para tapar un jaque')]
INSIGNIA = {'primera': '1', 'jaque': 'J'}
AURAS = [('', 'Ninguna', []), ('diag', 'Sus cuatro diagonales (como el Guardián)', [[1, 1], [-1, 1], [1, -1], [-1, -1]]),
         ('orto', 'Sus cuatro casillas en recto', [[1, 0], [-1, 0], [0, 1], [0, -1]]),
         ('todas', 'Las ocho casillas de alrededor',
          [[dc, dr] for dc in (-1, 0, 1) for dr in (-1, 0, 1) if (dc, dr) != (0, 0)])]
ESPECIALES = [('pantalla', 'Salto sobre una pieza (pantalla)'), ('secuencia', 'Salto sobre una fila de piezas'),
              ('cadena', 'Capturas en cadena'), ('jinete', 'Salto repetido (jinete)'),
              ('torcido', 'Movimiento torcido'), ('empuje', 'Empujar piezas adversarias'),
              ('intercambio', 'Intercambiarse con piezas propias')]
DIRECCIONES = [('todas', 'Recto y diagonal'), ('orto', 'Recto'), ('diag', 'Diagonal')]
TRAS = [('justo', 'Cae justo detrás (Saltamontes)'), ('libre', 'Cae en cualquier casilla detrás (León)'),
        ('primera', 'Captura la primera pieza detrás (Cañón)')]


def tipo_especial(m):
    """Clave de ESPECIALES de un componente especial."""
    if 'salto' in m:
        return 'jinete'
    if 'camino' in m:
        return 'torcido'
    for k in ('pantalla', 'secuencia', 'cadena', 'empuje', 'intercambio'):
        if k in m:
            return k
    return None


def describir_especial(m, nombres):
    """Texto de un componente especial para la lista del editor."""
    k = tipo_especial(m)
    d = {x: t for x, t in DIRECCIONES}
    if k == 'jinete':
        return 'Jinete: repite el salto %d-%d%s' % (m['salto'][0], m['salto'][1],
                                                   ' (hasta %d)' % m['alcance'] if m.get('alcance') else '')
    if k == 'torcido':
        if m.get('torcido'):
            t = m['torcido']
            return 'Torcido: un paso %s y luego %s%s' % ('recto' if t[0] == 'orto' else 'en diagonal',
                                                        'en diagonal' if t[1] == 'diag' else 'en recto',
                                                        ' sin límite' if not t[2] else (' %d' % t[2] if t[2] > 1 else ''))
        return 'Recorridos propios (%d)' % len(m['camino'])
    if k == 'pantalla':
        dirs = m['pantalla'] if isinstance(m['pantalla'], str) else None
        donde = d.get(dirs, 'direcciones propias')
        if m.get('come'):
            return 'Pantalla (%s): la captura y cae detrás (Langosta)' % donde.lower()
        return 'Pantalla (%s): %s' % (donde.lower(), dict(TRAS)[m.get('tras', 'justo')].lower())
    if k == 'secuencia':
        return 'Fila de piezas (%s, al menos %d)%s' % (d[m['secuencia']].lower(), m.get('minimo', 2),
                                                     ': captura las adversarias' if m.get('come') else '')
    if k == 'cadena':
        return 'Cadena de capturas (%s)' % d[m['cadena']].lower()
    if k in ('empuje', 'intercambio'):
        tipos = ', '.join(nombres.get(t, t) for t in m.get('tipos') or []) or 'ninguna pieza'
        return ('Empuja: %s' if k == 'empuje' else 'Se intercambia con: %s') % tipos
    return str(m)


class EditorPieza:
    """Crear o modificar una pieza: nombre, imagen, tipo, valor, movimientos (casilla por casilla, líneas, piezas
    combinadas y movimientos especiales), propiedades y su forma extendida."""

    def __init__(self, lab, t, d, nueva, padre=None):
        self.lab, self.t, self.d, self.nueva = lab, t, copy.deepcopy(d), nueva
        self.padre = padre  # el editor de la pieza base, si esta es su forma extendida
        self.img = lambda ruta, tam: lab.img.get(ruta, tam)
        top = self.top = tk.Toplevel(padre.top if padre else lab.root)
        top.title('Forma extendida' if padre else ('Nueva pieza' if nueva else 'Editar pieza'))
        top.transient(padre.top if padre else lab.root)
        top.configure(bg=FONDO)
        top.geometry('1260x800')
        f = ttk.Frame(top, style='Panel.TFrame', padding=12)
        f.pack(fill='both', expand=True)

        # ---- prediseños (piezas mágicas)
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x')
        ttk.Label(fila, text='PARTIR DE UNA PIEZA DEL CATÁLOGO (imagen y movimientos; luego puedes cambiarlos)',
                  style='Sub.TLabel').pack(side='left')
        import piezas_magicas as PM
        self.categorias = [(None, 'Todas')] + [(c, n) for c, n, _ in PM.CATEGORIAS]
        self.cmb_categoria = ttk.Combobox(fila, state='readonly', width=26, values=[n for _, n in self.categorias])
        self.cmb_categoria.current(0)
        self.cmb_categoria.pack(side='right')
        self.cmb_categoria.bind('<<ComboboxSelected>>', lambda e: self.dibujar_predisenos())
        self.cv_pre = tk.Canvas(f, height=92, bg=FONDO, highlightthickness=0)
        barra = ttk.Scrollbar(f, orient='horizontal', command=self.cv_pre.xview)
        self.cv_pre.configure(xscrollcommand=barra.set)
        self.cv_pre.pack(fill='x', pady=(2, 0))
        barra.pack(fill='x', pady=(0, 6))
        self.dibujar_predisenos()

        cuerpo = ttk.Frame(f, style='Panel.TFrame')
        cuerpo.pack(fill='both', expand=True)
        izq = ttk.Frame(cuerpo, style='Panel.TFrame', width=270)
        izq.pack(side='left', fill='y', padx=(0, 12))
        izq.pack_propagate(False)
        self.nb = ttk.Notebook(cuerpo, style='Panel.TNotebook', width=420)
        self.nb.pack(side='left', fill='y', padx=(0, 12))
        der = ttk.Frame(cuerpo, style='Panel.TFrame')
        der.pack(side='left', fill='both', expand=True)

        def etiqueta(p, txt, arriba=8):
            ttk.Label(p, text=txt, style='Sub.TLabel').pack(anchor='w', pady=(arriba, 2))
        self.etiqueta = etiqueta

        # ---- datos de la pieza
        self.v_nombre = tk.StringVar()
        self.v_simbolo = tk.StringVar()
        self.v_dorada = tk.BooleanVar()
        self.v_tipo = tk.StringVar()
        self.v_enroca = tk.BooleanVar()
        self.v_valor = tk.StringVar()
        self.v_berolina = tk.BooleanVar()
        etiqueta(izq, 'NOMBRE', 0)
        ttk.Entry(izq, textvariable=self.v_nombre, width=26).pack(anchor='w')
        etiqueta(izq, 'SÍMBOLO (NOTACIÓN)')
        ttk.Entry(izq, textvariable=self.v_simbolo, width=6).pack(anchor='w')
        etiqueta(izq, 'IMAGEN')
        self.cv_img = tk.Canvas(izq, width=200, height=84, bg=FONDO, highlightthickness=0)
        self.cv_img.pack(anchor='w')
        fila = ttk.Frame(izq, style='Panel.TFrame')
        fila.pack(anchor='w', fill='x', pady=(2, 0))
        ttk.Button(fila, text='Elegir imagen…', command=self.elegir_imagen).pack(side='left', padx=(0, 4))
        ttk.Button(fila, text='Diseñar…', command=self.disenar).pack(side='left')
        ttk.Checkbutton(izq, text='Versión dorada (base y estrella)', variable=self.v_dorada,
                        style='Panel.TCheckbutton', command=self.actualizar).pack(anchor='w', pady=(4, 0))
        if padre is None:
            etiqueta(izq, 'TIPO')
            for txt, val in (('Pieza normal', 'normal'), ('Rey (jaque y mate)', 'real'),
                             ('Peón (avanza y promociona)', 'peon')):
                ttk.Radiobutton(izq, text=txt, value=val, variable=self.v_tipo, style='Panel.TRadiobutton',
                                command=self.actualizar).pack(anchor='w')
            ttk.Checkbutton(izq, text='Peón de Berolina',
                            variable=self.v_berolina, style='Panel.TCheckbutton',
                            command=self.actualizar).pack(anchor='w', padx=(18, 0))
        ttk.Checkbutton(izq, text='Enroca con el rey (como la Torre)', variable=self.v_enroca,
                        style='Panel.TCheckbutton').pack(anchor='w', pady=(6, 0))
        etiqueta(izq, 'VALOR (PARA LA COMPUTADORA)')
        fila = ttk.Frame(izq, style='Panel.TFrame')
        fila.pack(anchor='w')
        ttk.Spinbox(fila, from_=0.5, to=30, increment=0.25, width=6, textvariable=self.v_valor).pack(side='left')
        ttk.Button(fila, text='Sugerir', command=lambda: self.v_valor.set('%g' % self._sugerido())).pack(
            side='left', padx=6)
        self.lbl_resumen = ttk.Label(izq, style='Panel.TLabel', wraplength=255, justify='left')
        self.lbl_resumen.pack(anchor='w', pady=(10, 0))

        self.construir_movimientos(self._pestana('Movimientos'))
        self.construir_especiales(self._pestana('Especiales'))
        self.construir_propiedades(self._pestana('Propiedades y extensión'))

        # ---- tablero vacío
        self.c = 44
        lado = (2 * R + 1) * self.c
        self.cv = tk.Canvas(der, width=lado, height=lado, bg=FONDO, highlightthickness=0, cursor='hand2')
        self.cv.pack(anchor='n')
        self.cv.bind('<Button-1>', self.clic)
        ley = tk.Canvas(der, width=lado, height=86, bg=FONDO, highlightthickness=0)
        ley.pack(anchor='n', pady=(4, 0))
        x = 0
        for modo, txt in NOMBRE_MODO:
            ley.create_rectangle(x + 2, 4, x + 16, 18, fill=COLOR_MODO[modo], outline='')
            ley.create_text(x + 22, 11, text=txt, anchor='w', fill=TEXTO, font=(lab.letra, 9))
            x += 150
        ley.create_rectangle(2, 26, 16, 40, fill='', outline=TEXTO, width=2)
        ley.create_text(22, 33, text='casilla elegida a mano', anchor='w', fill=TEXTO, font=(lab.letra, 9))
        ley.create_oval(200, 27, 212, 39, fill=TEXTO_SUAVE, outline='')
        ley.create_text(218, 33, text='por una línea, una pieza combinada o un recorrido', anchor='w', fill=TEXTO,
                        font=(lab.letra, 9))
        self._marca_salto(ley, 2, 46, 14)
        ley.create_text(22, 53, text='llega saltando', anchor='w', fill=TEXTO, font=(lab.letra, 9))
        for k, (cond, txt) in enumerate(((c, t) for c, t in CONDICIONES if c)):
            ley.create_oval(150 + k * 175, 46, 164 + k * 175, 60, fill='#E9DCC0', outline='')
            ley.create_text(157 + k * 175, 53, text=INSIGNIA[cond], fill='#2A2A2A', font=(lab.letra, 8, 'bold'))
            ley.create_text(170 + k * 175, 53, text=txt.lower(), anchor='w', fill=TEXTO, font=(lab.letra, 9))
        ley.create_text(2, 76, text='▲ arriba es adelante (para las negras, al revés)', anchor='w', fill=TEXTO_SUAVE,
                        font=(lab.letra, 9))

        botones = ttk.Frame(f, style='Panel.TFrame')
        botones.pack(fill='x', pady=(8, 0))
        ttk.Button(botones, text='Cancelar', command=top.destroy).pack(side='right', padx=(6, 0))
        ttk.Button(botones, text='Guardar forma extendida' if padre else 'Guardar pieza', style='Comenzar.TButton',
                   command=self.guardar).pack(side='right')
        self.cargar(self.d)
        top.update_idletasks()
        top.wait_visibility()
        top.grab_set()

    def _pestana(self, texto):
        f = ttk.Frame(self.nb, style='Panel.TFrame', padding=(6, 8, 6, 4))
        self.nb.add(f, text=texto)
        return f

    # ------------------------------------------------------------------ pestañas
    def construir_movimientos(self, p):
        etiqueta = self.etiqueta
        etiqueta(p, 'COMBINAR CON (SUMA SUS MOVIMIENTOS)', 0)
        marco = ttk.Frame(p, style='Panel.TFrame')
        marco.pack(anchor='w', fill='x', pady=(2, 0))
        self.fuentes = self._fuentes()
        self.v_combina = {}
        for k, (clave, nombre, _) in enumerate(self.fuentes):
            v = tk.BooleanVar()
            self.v_combina[clave] = v
            ttk.Checkbutton(marco, text=nombre, variable=v, style='Panel.TCheckbutton',
                            command=self.actualizar).grid(row=k // 3, column=k % 3, sticky='w', padx=(0, 6))

        etiqueta(p, 'LÍNEAS RECTAS Y DIAGONALES')
        self.lineas = {}
        for dirs, txt in (('orto', 'Recta'), ('diag', 'Diagonal')):
            v = {'activo': tk.BooleanVar(), 'alcance': tk.IntVar(value=1), 'sin_limite': tk.BooleanVar(),
                 'salta': tk.BooleanVar(), 'come': tk.BooleanVar()}
            fila = ttk.Frame(p, style='Panel.TFrame')
            fila.pack(anchor='w', fill='x', pady=1)
            ttk.Checkbutton(fila, text=txt, variable=v['activo'], style='Panel.TCheckbutton', width=9,
                            command=self.actualizar).pack(side='left')
            ttk.Spinbox(fila, from_=1, to=15, width=3, state='readonly', textvariable=v['alcance'],
                        command=self.actualizar).pack(side='left')
            ttk.Label(fila, text='casillas', style='Panel.TLabel').pack(side='left', padx=(3, 6))
            ttk.Checkbutton(fila, text='(sin límite)', variable=v['sin_limite'], style='Panel.TCheckbutton',
                            command=self.actualizar).pack(side='left')
            fila2 = ttk.Frame(p, style='Panel.TFrame')
            fila2.pack(anchor='w', fill='x', padx=(22, 0))
            v['modo'] = ttk.Combobox(fila2, state='readonly', width=15, values=[n for _, n in NOMBRE_MODO])
            v['cond'] = ttk.Combobox(fila2, state='readonly', width=22, values=[n for _, n in CONDICIONES])
            v['modo'].pack(side='left')
            v['modo'].current(0)
            v['modo'].bind('<<ComboboxSelected>>', lambda e: self.actualizar())
            v['cond'].pack(side='left', padx=(6, 0))
            v['cond'].current(0)
            v['cond'].bind('<<ComboboxSelected>>', lambda e: self.actualizar())
            fila3 = ttk.Frame(p, style='Panel.TFrame')
            fila3.pack(anchor='w', fill='x', padx=(22, 0), pady=(0, 3))
            ttk.Checkbutton(fila3, text='Salta las piezas en medio', variable=v['salta'], style='Panel.TCheckbutton',
                            command=self.actualizar).pack(side='left')
            ttk.Checkbutton(fila3, text='y captura las que salta', variable=v['come'], style='Panel.TCheckbutton',
                            command=self.actualizar).pack(side='left', padx=(6, 0))
            self.lineas[dirs] = v

        etiqueta(p, 'CASILLAS (CLIC EN EL TABLERO)')
        ttk.Label(p, text='Elige el pincel y haz clic en el tablero; un clic con el mismo pincel quita la casilla. '
                          'Una casilla puede llevar a la vez una marca normal y otra con condición.',
                  style='Panel.TLabel', wraplength=400, justify='left').pack(anchor='w')
        self.v_pincel = tk.StringVar(value='ambos')
        fila = ttk.Frame(p, style='Panel.TFrame')
        fila.pack(anchor='w', pady=(2, 0))
        for modo, txt in NOMBRE_MODO:
            ttk.Radiobutton(fila, text=txt, value=modo, variable=self.v_pincel,
                            style='Panel.TRadiobutton').pack(side='left', padx=(0, 8))
        self.v_pincel_salta = tk.BooleanVar(value=True)
        fila = ttk.Frame(p, style='Panel.TFrame')
        fila.pack(anchor='w', pady=(2, 0))
        ttk.Label(fila, text='Llega:', style='Panel.TLabel').pack(side='left', padx=(0, 4))
        ttk.Radiobutton(fila, text='saltando', value=True, variable=self.v_pincel_salta,
                        style='Panel.TRadiobutton').pack(side='left', padx=(0, 8))
        ttk.Radiobutton(fila, text='por camino libre', value=False,
                        variable=self.v_pincel_salta, style='Panel.TRadiobutton').pack(side='left')
        fila = ttk.Frame(p, style='Panel.TFrame')
        fila.pack(anchor='w', pady=(2, 0))
        ttk.Label(fila, text='Condición:', style='Panel.TLabel').pack(side='left', padx=(0, 4))
        self.cmb_pincel_cond = ttk.Combobox(fila, state='readonly', width=24, values=[n for _, n in CONDICIONES])
        self.cmb_pincel_cond.current(0)
        self.cmb_pincel_cond.pack(side='left')
        fila = ttk.Frame(p, style='Panel.TFrame')
        fila.pack(anchor='w', pady=(2, 0))
        ttk.Label(fila, text='Al marcar, también:', style='Panel.TLabel').pack(side='left', padx=(0, 4))
        self.cmb_simetria = ttk.Combobox(fila, state='readonly', width=24, values=[
            'solo esa casilla', 'su reflejo izquierda-derecha', 'las 4 rotaciones', 'las 8 simetrías'])
        self.cmb_simetria.current(3)
        self.cmb_simetria.pack(side='left')
        self.v_come_casillas = tk.BooleanVar()
        ttk.Checkbutton(p, text='Al saltar en línea recta, captura las piezas adversarias que salta',
                        variable=self.v_come_casillas, style='Panel.TCheckbutton',
                        command=self.actualizar).pack(anchor='w', pady=(4, 0))
        ttk.Button(p, text='Quitar todas las casillas', command=self.limpiar).pack(anchor='w', pady=(4, 0))

    def construir_especiales(self, p):
        ttk.Label(p, text='Movimientos que no se dibujan casilla por casilla: saltar sobre otras piezas, capturas '
                          'en cadena, jinetes, piezas torcidas, empujes e intercambios.', style='Panel.TLabel',
                  wraplength=400, justify='left').pack(anchor='w')
        self.lista_esp = tk.Listbox(p, height=12, bg='#25201C', fg=TEXTO, selectbackground='#5A4636',
                                    highlightthickness=0, relief='flat', activestyle='none')
        self.lista_esp.pack(fill='x', pady=(6, 4))
        self.lista_esp.bind('<Double-Button-1>', lambda e: self.editar_especial())
        fila = ttk.Frame(p, style='Panel.TFrame')
        fila.pack(fill='x')
        self.btn_anadir = ttk.Button(fila, text='Añadir ▾', command=self.menu_especiales)
        self.btn_anadir.pack(side='left', expand=True, fill='x', padx=(0, 2))
        ttk.Button(fila, text='Editar', command=self.editar_especial).pack(side='left', expand=True, fill='x',
                                                                          padx=(0, 2))
        ttk.Button(fila, text='Quitar', command=self.quitar_especial).pack(side='left', expand=True, fill='x')
        ttk.Label(p, style='Panel.TLabel', wraplength=400, justify='left', text=(
            'Ejemplos: la Catapulta salta a una o dos casillas (casillas «saltando») y salta filas de piezas; su '
            'forma extendida añade capturas en cadena. El Guardián se empuja, se intercambia con peones, avanza '
            'tres en su primer avance (casillas con condición) y bloquea los saltos (pestaña Propiedades).')).pack(
            anchor='w', pady=(10, 0))

    def construir_propiedades(self, p):
        etiqueta = self.etiqueta
        etiqueta(p, 'BLOQUEO DE SALTOS (AURA)', 0)
        ttk.Label(p, text='Ninguna pieza adversaria puede caer saltando en estas casillas, y las piezas propias en '
                          'ellas no se capturan al ser saltadas.', style='Panel.TLabel', wraplength=400,
                  justify='left').pack(anchor='w')
        self.cmb_aura = ttk.Combobox(p, state='readonly', width=40, values=[n for _, n, _ in AURAS])
        self.cmb_aura.current(0)
        self.cmb_aura.pack(anchor='w', pady=(2, 0))
        self.v_como_peon = tk.BooleanVar()
        ttk.Checkbutton(p, text='Avanza como un peón: sus avances en recto cuentan para la regla de las 50 jugadas, '
                                'conserva el primer avance si se mueve de lado y captura y puede ser capturada al '
                                'paso', variable=self.v_como_peon, style='Panel.TCheckbutton').pack(anchor='w',
                                                                                                    pady=(6, 0))
        fila = ttk.Frame(p, style='Panel.TFrame')
        fila.pack(anchor='w', pady=(6, 0))
        ttk.Label(fila, text='Puntos para el desempate:', style='Panel.TLabel').pack(side='left')
        self.v_puntos = tk.StringVar()
        ttk.Spinbox(fila, from_=0, to=30, increment=0.5, width=6, textvariable=self.v_puntos).pack(side='left', padx=6)
        ttk.Label(fila, text='(vacío: su valor)', style='Panel.TLabel').pack(side='left')
        self.v_llegada = tk.BooleanVar()
        self.v_captura = tk.IntVar(value=0)
        self.v_repetir = tk.BooleanVar()
        self.v_conv_n = tk.IntVar(value=4)
        self.cmb_conv = None
        if self.padre is not None:
            ttk.Label(p, text='Esta es la forma extendida de otra pieza: no se puede extender otra vez.',
                      style='Panel.TLabel', wraplength=400, justify='left').pack(anchor='w', pady=(14, 0))
            return
        etiqueta(p, 'FORMA EXTENDIDA', 14)
        self.lbl_ext = ttk.Label(p, style='Panel.TLabel', wraplength=400, justify='left')
        self.lbl_ext.pack(anchor='w', fill='x')
        fila = ttk.Frame(p, style='Panel.TFrame')
        fila.pack(anchor='w', pady=(2, 0))
        ttk.Button(fila, text='Crear o editar la forma extendida…', command=self.editar_extension).pack(side='left')
        ttk.Button(fila, text='Quitar', command=self.quitar_extension).pack(side='left', padx=(4, 0))
        ttk.Label(p, text='Se extiende (si tiene forma extendida):', style='Panel.TLabel').pack(anchor='w', pady=(6, 0))
        ttk.Checkbutton(p, text='Al llegar a la última fila, en la misma jugada', variable=self.v_llegada,
                        style='Panel.TCheckbutton').pack(anchor='w', padx=(12, 0))
        fila = ttk.Frame(p, style='Panel.TFrame')
        fila.pack(anchor='w', padx=(12, 0))
        ttk.Label(fila, text='Tras capturar', style='Panel.TLabel').pack(side='left')
        ttk.Spinbox(fila, from_=0, to=10, width=3, state='readonly', textvariable=self.v_captura).pack(side='left', padx=4)
        ttk.Label(fila, text='de su tipo (0 = no); cuesta el turno', style='Panel.TLabel').pack(side='left')
        ttk.Radiobutton(p, text='Solo una de las propias se extiende así', value=False, variable=self.v_repetir,
                        style='Panel.TRadiobutton').pack(anchor='w', padx=(24, 0))
        ttk.Radiobutton(p, text='Cada vez que se juntan esas capturas, se extiende otra', value=True,
                        variable=self.v_repetir, style='Panel.TRadiobutton').pack(anchor='w', padx=(24, 0))
        etiqueta(p, 'CONVERSIÓN EN OTRA PIEZA', 14)
        fila = ttk.Frame(p, style='Panel.TFrame')
        fila.pack(anchor='w')
        ttk.Label(fila, text='Por cada', style='Panel.TLabel').pack(side='left')
        ttk.Spinbox(fila, from_=1, to=10, width=3, state='readonly', textvariable=self.v_conv_n).pack(side='left', padx=4)
        ttk.Label(fila, text='capturas de su tipo, una propia se convierte en:', style='Panel.TLabel').pack(side='left')
        self.conversiones = [(None, 'Ninguna')] + [(x, d['nombre']) for x, d in self.lab.cfg['piezas'].items()
                                                   if x != self.t and not d.get('real') and not d.get('base')]
        self.cmb_conv = ttk.Combobox(p, state='readonly', width=30, values=[n for _, n in self.conversiones])
        self.cmb_conv.current(0)
        self.cmb_conv.pack(anchor='w', padx=(12, 0), pady=(2, 0))
        ttk.Label(p, text='(como en el Ajedrez Extendido: cada cuatro peones adversarios capturados, un peón propio '
                          'puede convertirse en Guardián)', style='Panel.TLabel', wraplength=400,
                  justify='left').pack(anchor='w', pady=(2, 0))

    # ------------------------------------------------------------------ datos
    def _fuentes(self):
        """Piezas con las que se puede combinar: las de la variante y las del catálogo (sin peones)."""
        out, vistos = [], set()
        for t, d in self.lab.cfg['piezas'].items():
            if t != self.t and not d.get('peon') and d.get('movs') and not d.get('base'):
                out.append((t, d['nombre'], d))
                vistos.add(d['nombre'])
        for t, d in G.CATALOGO.items():
            if not d.get('peon') and d['nombre'] not in vistos:
                out.append(('cat:' + t, d['nombre'], d))
        return out

    def cargar(self, d):
        """Pone en el editor una definición de pieza."""
        self.imagen = d.get('imagen', 'peon')
        self.receta = d.get('diseno')
        self.v_nombre.set(d.get('nombre', 'Pieza'))
        self.v_simbolo.set(d.get('simbolo', ''))
        self.v_dorada.set(d.get('dorada', False))
        self.v_tipo.set('real' if d.get('real') else 'peon' if d.get('peon') else 'normal')
        self.v_berolina.set(bool(d.get('berolina')))
        self.v_enroca.set(d.get('enroca', False))
        self.v_valor.set('' if d.get('valor') is None else '%g' % d['valor'])
        fuentes = {clave for clave, _, _ in self.fuentes}
        combina = {m['de'] for m in d.get('movs', []) if m.get('de') in fuentes}
        for clave, v in self.v_combina.items():
            v.set(clave in combina)
        self.casillas = {}   # (dc, dr, condición) -> (modo, salta)
        self.especiales = []
        for v in self.lineas.values():
            v['activo'].set(False)
            v['alcance'].set(1)
            v['sin_limite'].set(False)
            v['salta'].set(False)
            v['come'].set(False)
            v['modo'].current(0)
            v['cond'].current(0)
        come = False
        conds = [c for c, _ in CONDICIONES]
        for m in d.get('movs', []):
            if m.get('de') in combina:
                continue
            cond = m.get('cond')
            if 'salto' in m and not m.get('repite'):  # salto clásico: sus 8 casillas, saltando
                for dc, dr in G.saltos_simetricos(*m['salto']):
                    self.casillas[(dc, dr, cond)] = (m.get('modo', 'ambos'), True)
            elif 'casillas' in m:
                for e in m['casillas']:
                    dc, dr, modo = e[0], e[1], e[2]
                    salta = e[3] if len(e) > 3 and e[3] is not None else m.get('salta')
                    c = e[4] if len(e) > 4 and e[4] else cond
                    if salta is None:  # sin indicarlo: en línea recta, con camino libre; las demás, saltando
                        salta = not (dc == 0 or dr == 0 or abs(dc) == abs(dr))
                    if max(abs(dc), abs(dr)) <= R:
                        self.casillas[(dc, dr, c)] = (modo, bool(salta))
                come = come or bool(m.get('come'))
            elif 'dirs' in m:
                for dirs in (('orto', 'diag') if m['dirs'] == 'todas' else (m['dirs'],)):
                    v = self.lineas[dirs]
                    v['activo'].set(True)
                    v['sin_limite'].set(not m.get('alcance'))
                    v['alcance'].set(m.get('alcance') or 1)
                    v['modo'].current([x for x, _ in NOMBRE_MODO].index(m.get('modo', 'ambos')))
                    v['cond'].current(conds.index(cond) if cond in conds else 0)
                    v['salta'].set(bool(m.get('salta')))
                    v['come'].set(bool(m.get('come')))
            else:
                self.especiales.append(copy.deepcopy(m))
        self.v_come_casillas.set(come)
        aura = d.get('aura') or []
        self.cmb_aura.current(next((k for k, (_, _, a) in enumerate(AURAS) if sorted(map(tuple, a)) ==
                                    sorted(map(tuple, aura))), 0))
        self.v_como_peon.set(bool(d.get('como_peon')))
        self.v_puntos.set('' if d.get('puntos') is None else '%g' % d['puntos'])
        e = d.get('extension') or {}
        self.ext_def = None
        if self.padre is None:
            ext = self.lab.cfg['piezas'].get(e.get('pieza')) if e.get('pieza') else None
            self.ext_def = copy.deepcopy(ext) if ext else None
            if self.ext_def is None and d.get('_ext_def'):
                self.ext_def = copy.deepcopy(d['_ext_def'])
            self.v_llegada.set(bool(e.get('llegada')))
            self.v_captura.set(int(e.get('captura') or 0))
            self.v_repetir.set(bool(e.get('repetir')))
            c = d.get('conversion') or {}
            self.v_conv_n.set(int(c.get('captura') or 4))
            if self.cmb_conv is not None:
                self.cmb_conv.current(next((k for k, (x, _) in enumerate(self.conversiones) if x == c.get('pieza')), 0))
        self.dibujar_especiales()
        self.actualizar()

    def _propios(self):
        """Componentes propios (líneas, casillas y especiales), sin las piezas combinadas."""
        movs = []
        conds = [c for c, _ in CONDICIONES]
        for dirs, v in self.lineas.items():
            if v['activo'].get():
                m = {'dirs': dirs, 'alcance': 0 if v['sin_limite'].get() else int(v['alcance'].get())}
                modo = NOMBRE_MODO[max(0, v['modo'].current())][0]
                if modo != 'ambos':
                    m['modo'] = modo
                if v['salta'].get():
                    m['salta'] = True
                    if v['come'].get():
                        m['come'] = True
                cond = conds[max(0, v['cond'].current())]
                if cond:
                    m['cond'] = cond
                movs.append(m)
        if len(movs) == 2 and {k: v for k, v in movs[0].items() if k != 'dirs'} == \
                {k: v for k, v in movs[1].items() if k != 'dirs'}:
            movs = [dict(movs[0], dirs='todas')]
        if self.casillas:
            entradas = []
            for (dc, dr, cond), (modo, salta) in sorted(self.casillas.items(), key=lambda x: (x[0][2] or '', x[0][:2])):
                e = [dc, dr, modo, bool(salta)]
                if cond:
                    e.append(cond)
                entradas.append(e)
            m = {'casillas': entradas}
            if self.v_come_casillas.get():
                m['come'] = True
            movs.append(m)
        return movs + copy.deepcopy(self.especiales)

    def _combinados(self):
        movs = []
        for clave, _, d in self.fuentes:
            if self.v_combina[clave].get():
                for m in d.get('movs', []):
                    m = {k: v for k, v in m.items() if k != 'de'}
                    m['de'] = clave
                    movs.append(m)
        return movs

    def _definicion(self):
        quitar = ('real', 'peon', 'enroca', 'diseno', 'berolina', 'aura', 'como_peon', 'puntos', 'extension',
                  'conversion', '_ext_def')
        d = {k: v for k, v in self.d.items() if k not in quitar}
        d.update(nombre=self.v_nombre.get().strip() or 'Pieza', simbolo=self.v_simbolo.get().strip()[:3],
                 imagen=self.imagen, dorada=self.v_dorada.get())
        if self.receta:
            d['diseno'] = self.receta
        tipo = self.v_tipo.get() if self.padre is None else 'normal'
        if tipo == 'real':
            d['real'] = True
        if tipo == 'peon':
            d['peon'] = True
            if self.v_berolina.get():
                d['berolina'] = True
        if self.v_enroca.get() and tipo != 'real':
            d['enroca'] = True
        d['movs'] = [] if tipo == 'peon' else self._propios() + self._combinados()
        aura = AURAS[max(0, self.cmb_aura.current())][2]
        if aura and tipo != 'peon':
            d['aura'] = copy.deepcopy(aura)
        if self.v_como_peon.get() and tipo == 'normal':
            d['como_peon'] = True
        try:
            d['valor'] = 0 if tipo == 'real' else 1 if tipo == 'peon' else round(float(self.v_valor.get()), 2)
        except ValueError:
            d['valor'] = None
        try:
            if self.v_puntos.get().strip():
                d['puntos'] = round(float(self.v_puntos.get()), 2)
        except ValueError:
            pass
        if self.padre is None and tipo != 'real':
            if self.ext_def is not None and (self.v_llegada.get() or self.v_captura.get() > 0):
                e = {'pieza': self.t + '+'}
                if self.v_llegada.get():
                    e['llegada'] = True
                if self.v_captura.get() > 0:
                    e['captura'] = int(self.v_captura.get())
                    if self.v_repetir.get():
                        e['repetir'] = True
                d['extension'] = e
            if self.cmb_conv is not None and self.cmb_conv.current() > 0:
                d['conversion'] = {'pieza': self.conversiones[self.cmb_conv.current()][0],
                                   'captura': int(self.v_conv_n.get())}
        return d

    def _sugerido(self):
        d = self._definicion()
        d.pop('valor', None)
        return G.valor_sugerido(d, self.lab.cfg['ancho'], self.lab.cfg['alto'])

    # ------------------------------------------------------------------ dibujo
    def actualizar(self):
        self.cv_img.delete('all')
        base_clara(self.cv_img, 86, 2, 162, 78)
        for c in (0, 1):
            self.cv_img.create_image(40 + c * 84, 40, image=self.img(V.ruta_imagen(self.imagen, c, self.v_dorada.get()), 76))
        self.dibujar()
        d = self._definicion()
        if d.get('peon'):
            texto = ('Peón de Berolina: avanza en diagonal (dos casillas la primera vez) y captura en recto hacia '
                     'adelante.' if d.get('berolina') else
                     'Peón: avanza una casilla (dos desde su fila inicial) y captura en diagonal hacia adelante.')
        else:
            texto = G.describir_movs(d) or 'Todavía no tiene movimientos.'
        sugerido = '' if d.get('peon') or d.get('real') else '\nValor sugerido: %g' % self._sugerido()
        self.lbl_resumen.configure(text=texto + sugerido)
        if self.padre is None and hasattr(self, 'lbl_ext'):
            resumen = G.describir_movs(self.ext_def) if self.ext_def else ''
            if len(resumen) > 150:
                resumen = resumen[:147] + '…'
            from idioma import tr
            self.lbl_ext.configure(text=('«%s»: %s' % (tr(self.ext_def['nombre']), resumen or tr('sin movimientos')))
                                   if self.ext_def else
                                   'No tiene forma extendida.')

    def xy(self, dc, dr):
        return (dc + R) * self.c, (R - dr) * self.c

    def _marca_salto(self, cv, x, y, tam):
        """Pequeño arco: la casilla se alcanza saltando."""
        cv.create_arc(x, y, x + tam, y + tam * 1.4, start=20, extent=140, style='arc', outline='#FFFFFF', width=2)
        cv.create_line(x + tam * 0.86, y + tam * 0.35, x + tam, y + tam * 0.68, fill='#FFFFFF', width=2)

    def dibujar(self):
        cv, c = self.cv, self.c
        cv.delete('all')
        clara, oscura = colores_tema(self.lab.cfg.get('tema', 'madera'))[:2]
        peon = self.v_tipo.get() == 'peon' and self.padre is None
        # lo que aportan las líneas, las piezas combinadas y los recorridos (con la pieza en el centro)
        otros = {}
        if not peon:
            d = {'movs': [m for m in self._propios() if 'casillas' not in m] + self._combinados()}
            centro = R * (2 * R + 1) + R
            otros = G.destinos_vacio(d, 2 * R + 1, 2 * R + 1, centro)
        for dr in range(-R, R + 1):
            for dc in range(-R, R + 1):
                x, y = self.xy(dc, dr)
                cv.create_rectangle(x, y, x + c, y + c, outline='', fill=clara if (dc + dr) % 2 == 0 else oscura)
                if (dc, dr) == (0, 0):
                    cv.create_image(x + c / 2, y + c / 2, image=self.img(V.ruta_imagen(self.imagen, 0, self.v_dorada.get()), c - 6))
                    continue
                if not peon:
                    base = self.casillas.get((dc, dr, None))
                    if base:
                        modo, salta = base
                        cv.create_rectangle(x + 4, y + 4, x + c - 4, y + c - 4, fill=COLOR_MODO[modo], outline=TEXTO,
                                            width=2)
                        if salta:
                            self._marca_salto(cv, x + 6, y + 6, c * 0.32)
                    for k, cond in enumerate(('primera', 'jaque')):
                        e = self.casillas.get((dc, dr, cond))
                        if not e:
                            continue
                        modo, salta = e
                        if not base:
                            cv.create_rectangle(x + 5, y + 5, x + c - 5, y + c - 5, fill='', outline=COLOR_MODO[modo],
                                                width=3, dash=(4, 2))
                            if salta:
                                self._marca_salto(cv, x + 6, y + 6, c * 0.32)
                        r = c * 0.17
                        cx, cy = x + c - r - 3 - k * (2 * r + 2), y + c - r - 3
                        cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=COLOR_MODO[modo], outline='#F3E2BE')
                        cv.create_text(cx, cy, text=INSIGNIA[cond], fill='#FFFFFF', font=(self.lab.letra, 8, 'bold'))
                sq = (R + dr) * (2 * R + 1) + (R + dc)
                if sq in otros:
                    r = c * 0.16
                    cv.create_oval(x + c / 2 - r, y + c / 2 - r, x + c / 2 + r, y + c / 2 + r,
                                   fill=COLOR_MODO[otros[sq]], outline='#F3E2BE' if (dc, dr, None) in self.casillas else '')
        if peon:
            ber = self.v_berolina.get()
            for dc, txt, modo in ((0, '×' if ber else '↑', 'cap' if ber else 'mov'),
                                  (-1, '↖' if ber else '×', 'mov' if ber else 'cap'),
                                  (1, '↗' if ber else '×', 'mov' if ber else 'cap')):
                x, y = self.xy(dc, 1)
                cv.create_text(x + c / 2, y + c / 2, text=txt, fill=COLOR_MODO[modo], font=(self.lab.letra, 20, 'bold'))

    def dibujar_especiales(self):
        nombres = {t: d['nombre'] for t, d in self.lab.cfg['piezas'].items()}
        self.lista_esp.delete(0, 'end')
        for m in self.especiales:
            self.lista_esp.insert('end', describir_especial(m, nombres))
        if not self.especiales:
            self.lista_esp.insert('end', '(ninguno)')

    # ------------------------------------------------------------------ interacción
    def simetricas(self, dc, dr):
        k = max(0, self.cmb_simetria.current())
        if k == 0:
            return {(dc, dr)}
        if k == 1:
            return {(dc, dr), (-dc, dr)}
        if k == 2:
            return {(dc, dr), (-dr, dc), (-dc, -dr), (dr, -dc)}
        return {(sx * a, sy * b) for a, b in ((dc, dr), (dr, dc)) for sx in (1, -1) for sy in (1, -1)}

    def clic(self, ev):
        if self.v_tipo.get() == 'peon' and self.padre is None:
            return
        dc, dr = int(ev.x // self.c) - R, R - int(ev.y // self.c)
        if (dc, dr) == (0, 0) or max(abs(dc), abs(dr)) > R:
            return
        modo, salta = self.v_pincel.get(), bool(self.v_pincel_salta.get())
        cond = CONDICIONES[max(0, self.cmb_pincel_cond.current())][0]
        if cond == 'jaque':
            modo = 'mov'  # tapar un jaque es moverse
        quitar = self.casillas.get((dc, dr, cond)) == (modo, salta)
        for s in self.simetricas(dc, dr):
            if s == (0, 0):
                continue
            if quitar:
                self.casillas.pop(s + (cond,), None)
            else:
                self.casillas[s + (cond,)] = (modo, salta)
        self.actualizar()

    def limpiar(self):
        self.casillas = {}
        self.actualizar()

    def menu_especiales(self):
        m = tk.Menu(self.top, tearoff=0)
        for clave, txt in ESPECIALES:
            m.add_command(label=txt, command=lambda c=clave: DialogoEspecial(self, c, None, self._especial_nuevo))
        b = self.btn_anadir
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def _especial_nuevo(self, comp):
        self.especiales.append(comp)
        self.dibujar_especiales()
        self.actualizar()

    def editar_especial(self):
        sel = self.lista_esp.curselection()
        if not sel or sel[0] >= len(self.especiales):
            return
        i = sel[0]
        m = self.especiales[i]

        def guardado(comp):
            self.especiales[i] = comp
            self.dibujar_especiales()
            self.actualizar()
        if tipo_especial(m) == 'torcido' and not m.get('torcido'):
            messagebox.showinfo('Movimientos especiales', 'Estos recorridos vienen de una pieza del catálogo y no se '
                                'editan aquí; puedes quitarlos o dejarlos.', parent=self.top)
            return
        DialogoEspecial(self, tipo_especial(m), m, guardado)

    def quitar_especial(self):
        sel = self.lista_esp.curselection()
        if sel and sel[0] < len(self.especiales):
            del self.especiales[sel[0]]
            self.dibujar_especiales()
            self.actualizar()

    def editar_extension(self):
        if self.ext_def is None:
            d = self._definicion()
            for k in ('extension', 'conversion', 'real', 'peon', 'berolina'):
                d.pop(k, None)
            if not d['movs']:
                d['movs'] = [{'dirs': 'todas', 'alcance': 1}]  # un punto de partida para la forma extendida
            d.update(nombre=d['nombre'] + ' extendida', dorada=True, simbolo=(d.get('simbolo') or '')[:2] + "'",
                     valor=None, base=self.t)
        else:
            d = copy.deepcopy(self.ext_def)
        EditorPieza(self.lab, self.t + '+', d, self.ext_def is None, padre=self)

    def forma_extendida_editada(self, d):
        d['base'] = self.t
        for k in ('extension', 'conversion', 'real', 'peon', 'berolina'):
            d.pop(k, None)
        self.ext_def = d
        if not self.v_llegada.get() and self.v_captura.get() == 0:
            if self.v_tipo.get() == 'peon':
                self.v_llegada.set(True)
            else:
                self.v_captura.set(1)
        self.actualizar()

    def quitar_extension(self):
        self.ext_def = None
        self.actualizar()

    def dibujar_predisenos(self):
        import piezas_magicas as PM
        from idioma import tr
        categoria = self.categorias[max(0, self.cmb_categoria.current())][0]
        disponibles = set(DS.predisenos_disponibles())
        items = []
        for n in PM.claves(categoria):
            imagen = PM.imagen(n)
            if imagen.startswith('pre:') and imagen[4:] not in disponibles:
                imagen = 'peon'
            items.append((n, V.ruta_imagen(imagen, 0, n.endswith('_extendida') or n.endswith('_extendido')),
                          tr(PM.nombre(n))))
        cv = self.cv_pre
        cv.delete('all')
        for k, (clave, ruta, texto) in enumerate(items):
            x = k * 74 + 4
            tag = 'p%d' % k
            cv.create_rectangle(x, 2, x + 68, 70, outline=BORDE, fill='#3A322B', tags=tag)
            cv.create_image(x + 34, 36, image=self.img(ruta, 60), tags=tag)
            cv.create_text(x + 34, 81, text=texto, fill=TEXTO_SUAVE, font=('Sans', 7), tags=tag, width=72)
            cv.tag_bind(tag, '<Button-1>', lambda e, c=clave: self.usar_prediseno(c))
            cv.tag_bind(tag, '<Enter>', lambda e: cv.configure(cursor='hand2'))
            cv.tag_bind(tag, '<Leave>', lambda e: cv.configure(cursor=''))
        cv.configure(scrollregion=(0, 0, len(items) * 74 + 8, 90))
        cv.xview_moveto(0)

    def usar_prediseno(self, nombre):
        import piezas_magicas as PM
        if not self.nueva and not messagebox.askyesno(
                'Prediseño', 'Se reemplazarán el nombre, la imagen y los movimientos de la pieza. ¿Continuar?',
                parent=self.top):
            return
        d = DS.pieza_prediseno(nombre)
        if self.padre is not None:  # la forma extendida conserva su relación con la pieza base
            d['dorada'] = True
            d.pop('peon', None)
        self.cargar(d)
        self.lbl_resumen.configure(text=PM.descripcion(nombre) + '\n\n' + self.lbl_resumen.cget('text'))

    def elegir_imagen(self):
        GaleriaImagenes(self, lambda imagen, receta: self._imagen_elegida(imagen, receta))

    def disenar(self):
        VentanaDiseno(self.lab, self.receta, lambda imagen, receta: self._imagen_elegida(imagen, receta),
                      padre=self.top)

    def _imagen_elegida(self, imagen, receta):
        self.imagen, self.receta = imagen, receta
        self.actualizar()

    def guardar(self):
        d = self._definicion()
        if d.get('valor') is None:
            d['valor'] = self._sugerido()
        if not d['movs'] and not d.get('peon'):
            messagebox.showinfo('Pieza', 'La pieza necesita al menos un movimiento.', parent=self.top)
            return
        if self.padre is None and self.ext_def is not None and 'extension' not in d:
            if not messagebox.askyesno('Forma extendida', 'La pieza tiene forma extendida, pero ninguna regla para '
                                       'extenderse (llegar a la última fila o capturar). ¿Guardarla sin extensión?',
                                       parent=self.top):
                self.nb.select(2)
                return
        self.top.destroy()
        if self.padre is not None:
            self.padre.forma_extendida_editada(d)
        else:
            self.lab.pieza_editada(self.t, d, self.nueva, self.ext_def if 'extension' in d else None)


# ====================================================================== movimientos especiales
class DialogoEspecial:
    """Crear o editar un movimiento especial (pantalla, fila de piezas, cadena, jinete, torcido, empuje,
    intercambio)."""

    def __init__(self, editor, tipo, comp, al_guardar):
        self.editor, self.tipo, self.al_guardar = editor, tipo, al_guardar
        comp = copy.deepcopy(comp) or {}
        self.comp = comp
        top = self.top = tk.Toplevel(editor.top)
        top.title(dict(ESPECIALES)[tipo])
        top.configure(bg=FONDO)
        top.transient(editor.top)
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=dict(ESPECIALES)[tipo], style='Titulo.TLabel').pack(anchor='w')
        texto = {
            'pantalla': 'La pieza avanza en línea hasta la primera pieza que encuentra (la pantalla), de cualquier '
                        'color, y salta por encima de ella.',
            'secuencia': 'Si la casilla de al lado y las siguientes en línea están ocupadas, sin huecos, salta a la '
                         'primera casilla vacía detrás de la fila (el salto extendido de la Catapulta).',
            'cadena': 'Saltos rectos de dos casillas que capturan la pieza saltada (y la de llegada, en el primero) '
                      'o, en el primero, una fila de piezas; sigue saltando mientras pueda capturar, y la cadena '
                      'termina si da jaque (la Catapulta extendida).',
            'jinete': 'Repite un salto en la misma dirección mientras las casillas en las que cae estén vacías '
                      '(el Jinete nocturno repite el salto del Caballo).',
            'torcido': 'Da un paso (que debe estar vacío) y luego sigue en otra dirección, alejándose. El Mao es un '
                       'Caballo que se bloquea: un paso recto y otro en diagonal.',
            'empuje': 'Si en una de estas direcciones hay una pieza adversaria de estos tipos al lado, la empuja una '
                      'casilla (si está vacía) y ocupa su lugar.',
            'intercambio': 'Cambia su lugar con una pieza propia de estos tipos que esté al lado, en estas '
                           'direcciones; no puede deshacer enseguida el intercambio con la misma pieza.',
        }[tipo]
        ttk.Label(f, text=texto, style='Panel.TLabel', wraplength=460, justify='left').pack(anchor='w', pady=(4, 10))
        self.campos = {}
        getattr(self, 'campos_' + tipo)(f, comp)
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(12, 0))
        ttk.Button(fila, text='Cancelar', command=top.destroy).pack(side='right', padx=(6, 0))
        ttk.Button(fila, text='Aceptar', style='Comenzar.TButton', command=self.aceptar).pack(side='right')
        top.wait_visibility()
        top.grab_set()

    # ---- ayudas para los campos
    def combo(self, f, clave, titulo, opciones, actual):
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(anchor='w', fill='x', pady=2)
        ttk.Label(fila, text=titulo, style='Panel.TLabel', width=22).pack(side='left')
        cmb = ttk.Combobox(fila, state='readonly', width=36, values=[n for _, n in opciones])
        cmb.current(next((k for k, (x, _) in enumerate(opciones) if x == actual), 0))
        cmb.pack(side='left')
        self.campos[clave] = (cmb, opciones)

    def valor_combo(self, clave):
        cmb, opciones = self.campos[clave]
        return opciones[max(0, cmb.current())][0]

    def casilla(self, f, clave, texto, actual):
        v = tk.BooleanVar(value=bool(actual))
        ttk.Checkbutton(f, text=texto, variable=v, style='Panel.TCheckbutton').pack(anchor='w', pady=2)
        self.campos[clave] = v

    def numero(self, f, clave, titulo, desde, hasta, actual, nota=''):
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(anchor='w', fill='x', pady=2)
        ttk.Label(fila, text=titulo, style='Panel.TLabel', width=22).pack(side='left')
        v = tk.IntVar(value=actual)
        ttk.Spinbox(fila, from_=desde, to=hasta, width=4, state='readonly', textvariable=v).pack(side='left')
        if nota:
            ttk.Label(fila, text=nota, style='Panel.TLabel').pack(side='left', padx=6)
        self.campos[clave] = v

    def direcciones(self, f, actuales):
        """Rejilla de 3 × 3 con las ocho direcciones (vistas desde las blancas: arriba es adelante)."""
        ttk.Label(f, text='Direcciones (arriba es adelante):', style='Panel.TLabel').pack(anchor='w', pady=(4, 2))
        rejilla = ttk.Frame(f, style='Panel.TFrame')
        rejilla.pack(anchor='w')
        flechas = {(-1, 1): '↖', (0, 1): '↑', (1, 1): '↗', (-1, 0): '←', (1, 0): '→', (-1, -1): '↙', (0, -1): '↓',
                   (1, -1): '↘'}
        self.vars_dir = {}
        for dr in (1, 0, -1):
            for dc in (-1, 0, 1):
                if (dc, dr) == (0, 0):
                    ttk.Label(rejilla, text='●', style='Panel.TLabel').grid(row=1, column=1, padx=6)
                    continue
                v = tk.BooleanVar(value=[dc, dr] in actuales or (dc, dr) in actuales)
                ttk.Checkbutton(rejilla, text=flechas[(dc, dr)], variable=v, style='Panel.TCheckbutton').grid(
                    row=1 - dr, column=dc + 1, padx=4, pady=1)
                self.vars_dir[(dc, dr)] = v

    def tipos(self, f, actuales):
        ttk.Label(f, text='Piezas a las que se aplica:', style='Panel.TLabel').pack(anchor='w', pady=(6, 2))
        marco = ttk.Frame(f, style='Panel.TFrame')
        marco.pack(anchor='w')
        self.vars_tipos = {}
        piezas = [(t, d) for t, d in self.editor.lab.cfg['piezas'].items() if not d.get('real')]
        for k, (t, d) in enumerate(piezas):
            v = tk.BooleanVar(value=t in actuales)
            ttk.Checkbutton(marco, text=d['nombre'], variable=v, style='Panel.TCheckbutton').grid(
                row=k // 3, column=k % 3, sticky='w', padx=(0, 8))
            self.vars_tipos[t] = v

    # ---- cada tipo
    def campos_pantalla(self, f, c):
        self.combo(f, 'dirs', 'Dirección:', DIRECCIONES, c.get('pantalla') if isinstance(c.get('pantalla'), str) else 'todas')
        self.combo(f, 'tras', 'Detrás de la pantalla:', TRAS, c.get('tras', 'justo'))
        self.combo(f, 'modo', 'Al caer:', NOMBRE_MODO, c.get('modo', 'ambos'))
        self.casilla(f, 'come', 'Captura la pantalla y cae justo detrás, en una casilla vacía (la Langosta; las '
                                'opciones de arriba no cuentan)', c.get('come'))
        self.casilla(f, 'pegada', 'La pantalla tiene que estar al lado de la pieza', c.get('pegada'))

    def campos_secuencia(self, f, c):
        self.combo(f, 'dirs', 'Dirección:', DIRECCIONES, c.get('secuencia', 'todas'))
        self.numero(f, 'minimo', 'Piezas en la fila, al menos:', 1, 6, c.get('minimo', 2))
        self.casilla(f, 'come', 'Captura las piezas adversarias de la fila (el rey adversario no se salta)', c.get('come'))

    def campos_cadena(self, f, c):
        self.combo(f, 'dirs', 'Dirección:', DIRECCIONES, c.get('cadena', 'todas'))
        self.casilla(f, 'fila', 'El primer salto puede ser sobre una fila de piezas', c.get('fila', True))

    def campos_jinete(self, f, c):
        a, b = (c.get('salto') or [1, 2])
        self.numero(f, 'a', 'Salto: casillas a un lado', 0, 4, a)
        self.numero(f, 'b', 'y al otro', 1, 5, b, '(Caballo: 1 y 2)')
        self.numero(f, 'alcance', 'Saltos como máximo:', 0, 10, c.get('alcance', 0), '(0 = sin límite)')
        self.combo(f, 'modo', 'Al caer:', NOMBRE_MODO, c.get('modo', 'ambos'))

    def campos_torcido(self, f, c):
        t = c.get('torcido') or ['orto', 'diag', 1, False]
        self.combo(f, 'primero', 'Primer paso:', [('orto', 'Recto'), ('diag', 'En diagonal')], t[0])
        self.numero(f, 'alcance', 'Luego, casillas:', 0, 10, t[2], '(0 = sin límite)')
        self.casilla(f, 'para', 'También puede detenerse en la casilla del primer paso (como el Grifo)', t[3])
        self.combo(f, 'modo', 'Al llegar:', NOMBRE_MODO, c.get('modo', 'ambos'))

    def campos_empuje(self, f, c):
        self.direcciones(f, c.get('empuje') or [[0, 1]])
        self.tipos(f, c.get('tipos') or ([x for x, d in self.editor.lab.cfg['piezas'].items() if d.get('peon')]))

    def campos_intercambio(self, f, c):
        self.direcciones(f, c.get('intercambio') or [[1, 0], [-1, 0]])
        self.tipos(f, c.get('tipos') or ([x for x, d in self.editor.lab.cfg['piezas'].items() if d.get('peon')]))

    def aceptar(self):
        t = self.tipo
        if t == 'pantalla':
            comp = {'pantalla': self.valor_combo('dirs')}
            if self.campos['come'].get():
                comp['come'] = True
            else:
                comp['tras'] = self.valor_combo('tras')
                if self.valor_combo('modo') != 'ambos':
                    comp['modo'] = self.valor_combo('modo')
            if self.campos['pegada'].get():
                comp['pegada'] = True
        elif t == 'secuencia':
            comp = {'secuencia': self.valor_combo('dirs'), 'minimo': int(self.campos['minimo'].get())}
            if self.campos['come'].get():
                comp['come'] = True
        elif t == 'cadena':
            comp = {'cadena': self.valor_combo('dirs'), 'fila': bool(self.campos['fila'].get())}
        elif t == 'jinete':
            comp = {'salto': [int(self.campos['a'].get()), int(self.campos['b'].get())], 'repite': True}
            if self.campos['alcance'].get():
                comp['alcance'] = int(self.campos['alcance'].get())
            if self.valor_combo('modo') != 'ambos':
                comp['modo'] = self.valor_combo('modo')
        elif t == 'torcido':
            import piezas_magicas as PM
            primero = self.valor_combo('primero')
            luego = 'diag' if primero == 'orto' else 'orto'
            alcance, para = int(self.campos['alcance'].get()), bool(self.campos['para'].get())
            comp = {'camino': PM._torcidos(primero, luego, alcance, para), 'torcido': [primero, luego, alcance, para]}
            if self.valor_combo('modo') != 'ambos':
                comp['modo'] = self.valor_combo('modo')
        else:  # empuje, intercambio
            dirs = [[dc, dr] for (dc, dr), v in self.vars_dir.items() if v.get()]
            tipos = [x for x, v in self.vars_tipos.items() if v.get()]
            if not dirs or not tipos:
                messagebox.showinfo(dict(ESPECIALES)[t], 'Elige al menos una dirección y una pieza.', parent=self.top)
                return
            comp = {t: dirs, 'tipos': tipos}
        self.top.destroy()
        self.al_guardar(comp)


# ====================================================================== galería de imágenes
class GaleriaImagenes:
    """Elegir la imagen de una pieza: las del juego (en el estilo de los ajustes), prediseños y tus diseños."""

    def __init__(self, editor, al_elegir):
        self.editor, self.al_elegir = editor, al_elegir
        top = self.top = tk.Toplevel(editor.top)
        top.title('Imagen de la pieza')
        top.configure(bg=FONDO)
        top.geometry('760x620')
        top.transient(editor.top)
        f = ttk.Frame(top, style='Panel.TFrame', padding=12)
        f.pack(fill='both', expand=True)
        marco, self.cv = con_barra(f, 720, 520)
        marco.pack(fill='both', expand=True)
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(8, 0))
        ttk.Button(fila, text='Diseñar una nueva…', command=self.disenar).pack(side='left')
        ttk.Button(fila, text='Cerrar', command=top.destroy).pack(side='right')
        self.dibujar()
        top.wait_visibility()
        top.grab_set()

    def dibujar(self):
        cv, img = self.cv, self.editor.img
        cv.delete('all')
        y = 4
        secciones = [('DEL JUEGO', [(i, V.ruta_imagen(i, 0), None) for i in IMAGENES_JUEGO]),
                     ('PREDISEÑOS', [('pre:' + n, V.ruta_imagen('pre:' + n, 0), None)
                                     for n in DS.predisenos_disponibles()]),
                     ('MIS DISEÑOS', [('diseno:' + x['id'], V.ruta_imagen('diseno:' + x['id'], 0), x['receta'])
                                      for x in DS.biblioteca()])]
        self.recetas = {}
        for titulo, items in secciones:
            cv.create_text(4, y + 8, text=titulo, anchor='w', fill=TEXTO_SUAVE, font=('Sans', 9, 'bold'))
            y += 22
            if not items:
                cv.create_text(4, y + 8, text='Todavía no hay ninguno: pulsa «Diseñar una nueva…».', anchor='w',
                               fill=TEXTO_SUAVE, font=('Sans', 9))
                y += 26
            for k, (clave, ruta, receta) in enumerate(items):
                self.recetas[clave] = receta
                x, yy = (k % 9) * 78 + 4, y + (k // 9) * 78
                tag = 'i_' + clave.replace(':', '_')
                elegido = clave == self.editor.imagen
                cv.create_rectangle(x, yy, x + 70, yy + 70, outline=ORO if elegido else BORDE, width=3 if elegido else 1,
                                    fill='#3A322B', tags=tag)
                cv.create_image(x + 35, yy + 35, image=img(ruta, 62), tags=tag)
                cv.tag_bind(tag, '<Button-1>', lambda e, c=clave: self.elegir(c))
            y += ((len(items) + 8) // 9) * 78 + 10
        cv.configure(scrollregion=(0, 0, 720, y))

    def elegir(self, clave):
        self.top.destroy()
        self.al_elegir(clave, self.recetas.get(clave))

    def disenar(self):
        self.top.destroy()
        self.editor.disenar()


# ====================================================================== diseñador de imágenes
class VentanaDiseno:
    """Arma la imagen de una pieza con un cuerpo, un remate, un adorno y una letra."""
    TAM = 64

    def __init__(self, lab, receta, al_guardar, padre=None):
        self.lab, self.al_guardar = lab, al_guardar
        self.receta = dict(receta or {'cuerpo': 'recto', 'remate': 'estrella', 'adorno': None, 'letra': None})
        self.cache = {}
        top = self.top = tk.Toplevel(padre or lab.root)
        top.title('Diseñar una pieza')
        top.configure(bg=FONDO)
        top.geometry('1100x720')
        if padre is not None:
            top.transient(padre)
        f = ttk.Frame(top, style='Panel.TFrame', padding=12)
        f.pack(fill='both', expand=True)
        izq = ttk.Frame(f, style='Panel.TFrame')
        izq.pack(side='left', fill='both', expand=True)
        der = ttk.Frame(f, style='Panel.TFrame', width=300)
        der.pack(side='right', fill='y', padx=(12, 0))
        der.pack_propagate(False)
        self.lienzos = {}
        for grupo, titulo, alto in (('cuerpo', 'CUERPO', 92), ('remate', 'REMATE (LA CABEZA)', 290),
                                    ('adorno', 'ADORNO', 92)):
            ttk.Label(izq, text=titulo, style='Sub.TLabel').pack(anchor='w', pady=(6, 2))
            marco, cv = con_barra(izq, 740, alto)
            marco.pack(fill='x')
            self.lienzos[grupo] = cv
        fila = ttk.Frame(izq, style='Panel.TFrame')
        fila.pack(anchor='w', pady=(8, 0))
        ttk.Label(fila, text='LETRA SOBRE EL CUERPO', style='Sub.TLabel').pack(side='left', padx=(0, 8))
        self.cmb_letra = ttk.Combobox(fila, state='readonly', width=10, values=['Ninguna'] + list(DS.LETRAS))
        self.cmb_letra.set(self.receta.get('letra') or 'Ninguna')
        self.cmb_letra.pack(side='left')
        self.cmb_letra.bind('<<ComboboxSelected>>', lambda e: self.cambiar('letra', None if self.cmb_letra.get() == 'Ninguna'
                                                                          else self.cmb_letra.get()))
        ttk.Label(der, text='Vista previa', style='Titulo.TLabel').pack(anchor='w')
        self.cv_prev = tk.Canvas(der, width=280, height=300, bg='#B58863', highlightthickness=0)
        self.cv_prev.pack(anchor='w', pady=(6, 8))
        ttk.Label(der, text='NOMBRE DEL DISEÑO', style='Sub.TLabel').pack(anchor='w')
        self.v_nombre = tk.StringVar(value='Mi diseño')
        ttk.Entry(der, textvariable=self.v_nombre).pack(fill='x', pady=(2, 8))
        ttk.Label(der, text='Se guarda en tus diseños y queda disponible para cualquier pieza. Las variantes que '
                            'lo usan llevan la receta, así que al compartirlas se rehace solo.', style='Panel.TLabel',
                  wraplength=280, justify='left').pack(anchor='w')
        ttk.Button(der, text='Cancelar', command=top.destroy).pack(side='bottom', fill='x', pady=(6, 0))
        ttk.Button(der, text='Guardar diseño', style='Comenzar.TButton', command=self.guardar).pack(side='bottom', fill='x')
        self.dibujar()
        top.wait_visibility()
        top.grab_set()

    def miniatura(self, receta, color=0, dorada=False, tam=64):
        """La pieza compuesta, escalada como las demás (se compone una vez en un archivo temporal)."""
        import os, tempfile
        clave = (tuple(sorted((k, v or '') for k, v in receta.items())), color, dorada)
        ruta = self.cache.get(clave)
        if ruta is None:
            if not hasattr(self, 'tmp'):
                self.tmp = tempfile.mkdtemp(prefix='ajedrez_disenos_')
            ruta = self.cache[clave] = os.path.join(self.tmp, '%d.png' % len(self.cache))
            DS.componer(receta, color, dorada, ruta, root=self.top)
        return self.lab.img.get(ruta, tam)

    def dibujar(self):
        for grupo, cv in self.lienzos.items():
            cv.delete('all')
            opciones = DS.PARTES[grupo] if grupo != 'adorno' else [None] + DS.PARTES['adorno']
            for k, nombre in enumerate(opciones):
                receta = dict(self.receta, **{grupo: nombre})
                x, y = (k % 10) * 72 + 4, (k // 10) * 72 + 4
                tag = '%s_%s' % (grupo, nombre)
                elegido = self.receta.get(grupo) == nombre
                cv.create_rectangle(x, y, x + 66, y + 66, outline=ORO if elegido else BORDE, width=3 if elegido else 1,
                                    fill='#3A322B', tags=tag)
                cv.create_image(x + 33, y + 33, image=self.miniatura(receta), tags=tag)
                cv.tag_bind(tag, '<Button-1>', lambda e, g=grupo, n=nombre: self.cambiar(g, n))
            cv.configure(scrollregion=(0, 0, 720, ((len(opciones) + 9) // 10) * 72 + 8))
        cv = self.cv_prev
        cv.delete('all')
        cv.create_image(70, 70, image=self.miniatura(self.receta, 0, False, 128))
        cv.create_image(210, 70, image=self.miniatura(self.receta, 1, False, 128))
        cv.create_image(70, 210, image=self.miniatura(self.receta, 0, True, 128))
        cv.create_image(210, 210, image=self.miniatura(self.receta, 1, True, 128))
        cv.create_text(140, 290, text='normal (arriba) y dorada (abajo)', fill='#2A2A2A', font=('Sans', 8))

    def cambiar(self, grupo, nombre):
        self.receta[grupo] = nombre
        self.dibujar()

    def guardar(self):
        receta = {k: v for k, v in self.receta.items() if v}
        imagen = DS.guardar_diseno(self.v_nombre.get().strip() or 'Mi diseño', receta, root=self.top)
        self.top.destroy()
        self.al_guardar(imagen, receta)
