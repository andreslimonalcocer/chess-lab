"""Ventanas del menú: partidas guardadas, perfil del jugador, problemas e importar partidas."""
import os, queue, re, subprocess, sys, threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import partidas as PG
from interfaz import FONDO, BORDE, ORO, TEXTO, TEXTO_SUAVE, PROCESO


def dibujar_tablero(cv, app, v, st, marcas=(), girado=False, texto=''):
    """Vista previa de una posición en un lienzo: casillas con el tema elegido, piezas, coordenadas, la
    última jugada resaltada y un texto debajo. Usa las mismas imágenes (en caché) que el tablero del juego."""
    from interfaz import colores_tema
    cv.delete('all')
    w, h = cv.winfo_width(), cv.winfo_height()
    if w < 50 or v is None or st is None:
        return
    W, H = v.ancho, v.alto
    pie = 26 if texto else 4
    S = max(8, int(min((w - 22) / W, (h - 18 - pie) / H)))
    ox, oy = (w - W * S) // 2 + 8, 4
    clara, oscura, ult_c, ult_o = colores_tema(app.tema(v))[:4]
    cv.create_rectangle(ox - 2, oy - 2, ox + W * S + 2, oy + H * S + 2, fill=BORDE, outline='')
    tam = max(6, int(S * 0.9))
    fuente = ('Sans', max(7, S // 4))
    for sq in range(W * H):
        c, r = sq % W, sq // W
        x = ox + ((W - 1 - c) if girado else c) * S
        y = oy + (r if girado else (H - 1 - r)) * S
        es_clara = (c + r) % 2 == 0
        col = (ult_c if es_clara else ult_o) if sq in marcas else (clara if es_clara else oscura)
        cv.create_rectangle(x, y, x + S, y + S, fill=col, outline='')
        p = v.pieza(st, sq)
        if p is not None:
            cv.create_image(x + S / 2, y + S / 2, image=app.img.get(v.imagen(*p), tam))
    from generico import LETRAS
    for i in range(W):
        c = W - 1 - i if girado else i
        cv.create_text(ox + i * S + S / 2, oy + H * S + 8, text=LETRAS[c], fill=TEXTO_SUAVE, font=fuente)
    for i in range(H):
        r = i if girado else H - 1 - i
        cv.create_text(ox - 8, oy + i * S + S / 2, text=str(r + 1), fill=TEXTO_SUAVE, font=fuente)
    if texto:
        cv.create_text(w / 2, oy + H * S + 18 + 6, text=texto, fill=TEXTO, font=('Sans', 10, 'bold'), width=w - 10)


def posicion_de_problema(p):
    """(variante, posición, casillas de la última jugada) de un problema (con caché por id)."""
    if p['id'] in _POSICIONES:
        return _POSICIONES[p['id']]
    import variantes as V
    v = V.crear(p.get('variante') or {'tipo': 'extendido'})
    ini = p.get('inicio')
    st = v.inicial() if ini is None else v.construir(ini['piezas'], ini['turno'])
    marcas = ()
    for i in p['hist']:
        movs = v.legal(st)
        mv, st = movs[i]
        marcas = v.casillas(mv)
    _POSICIONES[p['id']] = (v, st, marcas)
    return _POSICIONES[p['id']]


_POSICIONES = {}


class PartidasGuardadas:
    """Base de tus partidas: filtrar por variante, resultado, rival y fecha; continuar, reproducir, analizar,
    exportar (varias a la vez) o borrar."""
    RESULTADOS = ['Todos', 'Ganadas', 'Perdidas', 'Tablas', 'Sin terminar', 'Dos jugadores']
    FECHAS = [('Cualquier fecha', None), ('Hoy', 1), ('Últimos 7 días', 7), ('Últimos 30 días', 30),
              ('Últimos 365 días', 365)]

    def __init__(self, app):
        self.app = app
        top = self.top = tk.Toplevel(app.root)
        top.title('Partidas guardadas')
        top.configure(bg=FONDO)
        top.geometry('1040x600')
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Partidas guardadas', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(f, text='Tus partidas contra la computadora (y entre dos personas) se guardan solas, jugada a jugada. '
                          'Filtra, ordena con un clic en el encabezado y selecciona varias con Ctrl o Mayús para '
                          'exportarlas juntas.', style='Panel.TLabel', wraplength=1000, justify='left').pack(
            anchor='w', pady=(2, 8))
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(0, 6))
        self.filtros = {}
        for clave, txt, ancho in (('variante', 'Variante', 20), ('resultado', 'Resultado', 13), ('rival', 'Rival', 16),
                                  ('fecha', 'Fecha', 16)):
            ttk.Label(fila, text=txt, style='Panel.TLabel').pack(side='left', padx=(0, 4))
            c = ttk.Combobox(fila, state='readonly', width=ancho)
            c.pack(side='left', padx=(0, 14))
            c.bind('<<ComboboxSelected>>', lambda e: self.mostrar())
            self.filtros[clave] = c
        self.filtros['resultado'].configure(values=self.RESULTADOS)
        self.filtros['resultado'].current(0)
        self.filtros['fecha'].configure(values=[x[0] for x in self.FECHAS])
        self.filtros['fecha'].current(0)
        ttk.Label(fila, text='Buscar', style='Panel.TLabel').pack(side='left', padx=(0, 4))
        self.buscar = tk.StringVar()
        self.buscar.trace_add('write', lambda *x: self.mostrar())
        ttk.Entry(fila, textvariable=self.buscar, width=14).pack(side='left')
        cols = ('fecha', 'variante', 'color', 'rival', 'jugadas', 'estado')
        marco = ttk.Frame(f, style='Panel.TFrame')
        marco.pack(fill='both', expand=True)
        self.tabla = ttk.Treeview(marco, columns=cols, show='headings', selectmode='extended')
        self.orden = ('fecha', True)
        for c, txt, ancho in zip(cols, ('Fecha', 'Variante', 'Juegas con', 'Rival', 'Jugadas', 'Estado'),
                                 (130, 150, 90, 130, 70, 330)):
            self.tabla.heading(c, text=txt, command=lambda c=c: self.ordenar(c))
            self.tabla.column(c, width=ancho, anchor='w')
        barra = ttk.Scrollbar(marco, command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        barra.pack(side='right', fill='y')
        self.tabla.pack(side='left', fill='both', expand=True)
        self.tabla.bind('<Double-Button-1>', lambda e: self.abrir('principal'))
        self.lbl_resumen = ttk.Label(f, style='Panel.TLabel')
        self.lbl_resumen.pack(anchor='w', pady=(6, 0))
        botones = ttk.Frame(f, style='Panel.TFrame')
        botones.pack(fill='x', pady=(8, 0))
        for txt, accion in (('Continuar', 'continuar'), ('Reproducir', 'reproducir'), ('Analizar', 'analizar'),
                            ('Borrar', 'borrar')):
            ttk.Button(botones, text=txt, command=lambda a=accion: self.abrir(a)).pack(side='left', padx=(0, 4))
        ttk.Button(botones, text='Exportar…', command=self.exportar).pack(side='left', padx=(12, 4))
        ttk.Button(botones, text='Cerrar', command=top.destroy).pack(side='right')
        self.cargar()

    @staticmethod
    def resultado_para_ti(r):
        if not r.get('resultado'):
            return 'Sin terminar'
        if r.get('dos_jugadores'):
            return 'Dos jugadores'
        if r['resultado'] == 'tablas':
            return 'Tablas'
        return 'Ganadas' if r['resultado'] == r.get('humano') else 'Perdidas'

    @staticmethod
    def rival(r):
        return 'otra persona' if r.get('dos_jugadores') else (r.get('computadora') or {}).get('nivel', '?')

    def cargar(self):
        self.todas = PG.listar()
        variantes = sorted({r.get('variante_nombre', '?') for _, r in self.todas})
        rivales = sorted({self.rival(r) for _, r in self.todas})
        self.filtros['variante'].configure(values=['Todas'] + variantes)
        self.filtros['rival'].configure(values=['Todos'] + rivales)
        for c, val in (('variante', 'Todas'), ('rival', 'Todos')):
            if self.filtros[c].get() not in self.filtros[c].cget('values'):
                self.filtros[c].set(val)
        self.mostrar()

    def filtradas(self):
        import time as T
        var, res, riv = (self.filtros[c].get() for c in ('variante', 'resultado', 'rival'))
        dias = self.FECHAS[max(0, self.filtros['fecha'].current())][1]
        desde = T.strftime('%Y-%m-%d', T.localtime(T.time() - (dias - 1) * 86400)) if dias else ''
        texto = self.buscar.get().strip().lower()
        out = []
        for ruta, r in self.todas:
            if var not in ('Todas', r.get('variante_nombre', '?')) or riv not in ('Todos', self.rival(r)):
                continue
            if res != 'Todos' and self.resultado_para_ti(r) != res:
                continue
            if desde and r.get('fecha', '')[:10] < desde:
                continue
            if texto and texto not in ' '.join([r.get('motivo', ''), r.get('variante_nombre', ''), self.rival(r)] +
                                               [j.get('j', '') for j in r.get('jugadas', [])]).lower():
                continue
            out.append((ruta, r))
        return out

    def ordenar(self, col):
        self.orden = (col, not self.orden[1] if self.orden[0] == col else col in ('fecha', 'jugadas'))
        self.mostrar()

    def mostrar(self):
        self.tabla.delete(*self.tabla.get_children())
        self.items = {}
        filas = []
        for ruta, r in self.filtradas():
            estado = ('%s (%s)' % (r['resultado'], r.get('motivo', ''))) if r.get('resultado') else 'sin terminar'
            if r.get('puntuada'):
                estado += ' · Elo %d → %d' % (r['puntuada']['antes'], r['puntuada']['despues'])
            elif r.get('ayudas'):
                estado += ' · con ayudas'
            filas.append(((r.get('fecha', '')[:16], r.get('variante_nombre', '?'), r.get('humano', '?'), self.rival(r),
                           (len(r.get('jugadas', [])) + 1) // 2, estado), ruta, r))
        col, desc = self.orden
        k = ('fecha', 'variante', 'color', 'rival', 'jugadas', 'estado').index(col)
        filas.sort(key=lambda x: x[0][k], reverse=desc)
        for valores, ruta, r in filas:
            self.items[self.tabla.insert('', 'end', values=valores)] = (ruta, r)
        cuenta = {x: sum(1 for _, _, r in filas if self.resultado_para_ti(r) == x)
                  for x in ('Ganadas', 'Perdidas', 'Tablas')}
        jugadas = sum(cuenta.values())
        puntos = cuenta['Ganadas'] + cuenta['Tablas'] / 2
        self.lbl_resumen.configure(text='%d partidas · %d ganadas, %d perdidas, %d tablas%s' % (
            len(filas), cuenta['Ganadas'], cuenta['Perdidas'], cuenta['Tablas'],
            (' · %.0f %% de los puntos' % (100 * puntos / jugadas)) if jugadas else ''))

    def seleccion(self):
        return [self.items[i] for i in self.tabla.selection() if i in self.items]

    def exportar(self):
        """Exporta las partidas seleccionadas (o todas las que muestra el filtro) en un solo archivo de texto."""
        import textos as TX, time as T
        elegidas = self.seleccion() or [self.items[i] for i in self.tabla.get_children()]
        if not elegidas:
            return
        ruta = filedialog.asksaveasfilename(parent=self.top, title='Exportar %d partidas' % len(elegidas),
                                            defaultextension='.txt',
                                            initialfile='partidas_%s.txt' % T.strftime('%Y%m%d_%H%M'),
                                            filetypes=[('Texto', '*.txt'), ('Todos los archivos', '*')])
        if not ruta:
            return
        textos, fallidas = [], 0
        for _, r in elegidas:
            try:
                textos.append(TX.texto_de_registro(r))
            except Exception:
                fallidas += 1
        with open(ruta, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(textos))
        messagebox.showinfo('Exportar', 'Se exportaron %d partidas%s.' % (
            len(textos), (' (%d no se pudieron leer)' % fallidas) if fallidas else ''), parent=self.top)

    def abrir(self, accion):
        sel = self.seleccion()
        if not sel:
            return
        if accion == 'borrar':
            if messagebox.askyesno('Borrar', '¿Borrar %s?' % ('esta partida' if len(sel) == 1 else
                                                               'las %d partidas seleccionadas' % len(sel)),
                                   parent=self.top):
                for ruta, _ in sel:
                    os.remove(ruta)
                self.cargar()
            return
        ruta, r = sel[0]
        if accion == 'principal':
            accion = 'reproducir' if r.get('resultado') else 'continuar'
        if accion == 'continuar' and r.get('resultado'):
            messagebox.showinfo('Partidas', 'Esa partida ya terminó; puedes reproducirla o analizarla.', parent=self.top)
            return
        self.top.destroy()
        if accion == 'continuar':
            self.app.reanudar(ruta, r)
        else:
            self.app.reproducir(r, ruta, analizar=accion == 'analizar')


class Perfil:
    """Tu Elo en cada variante, su evolución, tus resultados por nivel y el nivel sugerido."""

    def __init__(self, app, niveles_por_variante):
        self.app = app
        top = self.top = tk.Toplevel(app.root)
        top.title('Mi perfil')
        top.configure(bg=FONDO)
        top.geometry('760x600')
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Mi perfil', style='Titulo.TLabel').pack(anchor='w')
        perfil = PG.cargar_perfil()
        if not perfil['variantes']:
            ttk.Label(f, text='Todavía no hay partidas puntuadas.\n\nEl Elo se calcula en las variantes cuyos niveles '
                              'están calibrados en Elo (por ahora, el Ajedrez Extendido tras correr '
                              'Simulador/calibrar_elo.py). Cuentan las partidas desde la posición inicial, '
                              'terminadas y sin usar «Deshacer».', style='Panel.TLabel', wraplength=700,
                      justify='left').pack(anchor='w', pady=10)
        for vid, d in perfil['variantes'].items():
            caja = ttk.Frame(f, style='Panel.TFrame')
            caja.pack(fill='both', expand=True, pady=(10, 0))
            hist = d['historial']
            g = sum(1 for x in hist if x['puntos'] == 1)
            e = sum(1 for x in hist if x['puntos'] == 0.5)
            ttk.Label(caja, text='%s: %d Elo' % (d.get('nombre', vid), d['elo']), style='Estado.TLabel').pack(anchor='w')
            sugerido = ''
            niveles = niveles_por_variante.get(vid)
            if niveles:
                cerca = min(niveles, key=lambda n: abs(n[4] - d['elo']))
                sugerido = ' · nivel sugerido: %s' % cerca[0]
            provisional = ' (provisional: menos de 20 partidas)' if d['partidas'] < 20 else ''
            ttk.Label(caja, text='%d partidas: %d ganadas, %d tablas, %d perdidas%s%s' % (
                d['partidas'], g, e, len(hist) - g - e, provisional, sugerido), style='Panel.TLabel').pack(anchor='w')
            cv = tk.Canvas(caja, height=150, bg='#1E1B18', highlightthickness=0)
            cv.pack(fill='x', pady=(6, 4))
            cv.bind('<Configure>', lambda ev, cv=cv, hist=hist: self.grafica(cv, hist))
            por_nivel = {}
            for x in hist:
                p = por_nivel.setdefault(x['nivel'], [0, 0, 0])
                p[0 if x['puntos'] == 1 else 1 if x['puntos'] == 0.5 else 2] += 1
            if por_nivel:
                ttk.Label(caja, text='Contra cada nivel: ' + ' · '.join(
                    '%s %d/%d/%d' % (n, *v) for n, v in sorted(por_nivel.items())), style='Panel.TLabel',
                    wraplength=700).pack(anchor='w')
        ttk.Button(f, text='Cerrar', command=top.destroy).pack(side='bottom', anchor='e')

    @staticmethod
    def grafica(cv, hist):
        cv.delete('all')
        w, h = cv.winfo_width(), cv.winfo_height()
        if not hist or w < 20:
            return
        valores = [hist[0]['elo_antes']] + [x['elo_despues'] for x in hist]
        lo, hi = min(valores) - 30, max(valores) + 30
        x = lambda i: 30 + (w - 50) * i / max(1, len(valores) - 1)
        y = lambda v: h - 15 - (h - 30) * (v - lo) / (hi - lo)
        for v in range(int(lo // 100 + 1) * 100, int(hi) + 1, 100):
            cv.create_line(30, y(v), w - 10, y(v), fill=BORDE, dash=(2, 4))
            cv.create_text(26, y(v), text=str(v), anchor='e', fill=TEXTO_SUAVE, font=('Sans', 8))
        puntos = [(x(i), y(v)) for i, v in enumerate(valores)]
        if len(puntos) > 1:
            cv.create_line(puntos, fill=ORO, width=2)
        for i, (px, py) in enumerate(puntos[1:]):
            r = hist[i]['puntos']
            cv.create_oval(px - 3, py - 3, px + 3, py + 3, outline='',
                           fill='#6FB040' if r == 1 else '#C8C8C8' if r == 0.5 else '#D05050')


def es_de_variante(problema, v):
    """¿El problema es de la variante v? (las del Laboratorio se reconocen por su nombre)."""
    spec = problema.get('variante') or {'tipo': 'extendido'}
    if v.id == 'extendido':
        return spec.get('tipo', 'extendido') == 'extendido'
    return spec.get('tipo') == 'generica' and spec.get('config', {}).get('nombre') == v.cfg.get('nombre')


class Problemas:
    """Problemas de mate en N y tácticos sacados de las bitácoras (Simulador/extraer_problemas.py) y tus errores
    (del análisis de tus partidas), de una variante. Cada problema tiene un Elo (su dificultad) y el primer
    intento de cada uno mueve tu Elo de problemas."""
    ORDENES = ['Para mi nivel', 'Variante y tipo', 'Más fáciles primero', 'Más difíciles primero']

    def __init__(self, app, variante=None):
        self.app, self.variante = app, variante
        top = self.top = tk.Toplevel(app.root)
        top.title('Problemas' + (' — ' + variante.nombre if variante else ''))
        top.configure(bg=FONDO)
        top.geometry('1260x640')
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        arriba = ttk.Frame(f, style='Panel.TFrame')
        arriba.pack(fill='x')
        ttk.Label(arriba, text='Problemas' + (' · ' + variante.nombre if variante else ''),
                  style='Titulo.TLabel').pack(side='left')
        ttk.Button(arriba, text='Estadísticas…', command=self.estadisticas).pack(side='right')
        ttk.Button(arriba, text='★ Problema del día', command=self.del_dia).pack(side='right', padx=6)
        self.lbl_elo = ttk.Label(arriba, style='Estado.TLabel')
        self.lbl_elo.pack(side='right', padx=12)
        ttk.Label(f, text='Posiciones reales de tus partidas y de las simulaciones: mates forzados (da mate en las '
                          'jugadas indicadas; la computadora defiende lo mejor posible) y tácticas (encuentra la '
                          'única jugada que gana material). A la derecha, la posición de cada problema.',
                  style='Panel.TLabel', wraplength=820, justify='left').pack(anchor='w', pady=(2, 8))
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(0, 6))
        self.cmb_var = ttk.Combobox(fila, state='readonly', width=24)
        if variante is None:  # sin variante fija: se elige aquí
            ttk.Label(fila, text='Variante', style='Panel.TLabel').pack(side='left')
            self.cmb_var.pack(side='left', padx=(6, 16))
        self.cmb_var.bind('<<ComboboxSelected>>', lambda e: self.cargar())
        ttk.Label(fila, text='Tipo', style='Panel.TLabel').pack(side='left')
        self.cmb_n = ttk.Combobox(fila, state='readonly', width=14,
                                  values=['Todos', 'Mate en 1', 'Mate en 2', 'Mate en 3', 'Tácticos', 'Mis errores'])
        self.cmb_n.current(0)
        self.cmb_n.pack(side='left', padx=6)
        self.cmb_n.bind('<<ComboboxSelected>>', lambda e: self.cargar())
        ttk.Label(fila, text='Orden', style='Panel.TLabel').pack(side='left', padx=(10, 0))
        self.cmb_orden = ttk.Combobox(fila, state='readonly', width=20, values=self.ORDENES)
        self.cmb_orden.current(0)
        self.cmb_orden.pack(side='left', padx=6)
        self.cmb_orden.bind('<<ComboboxSelected>>', lambda e: self.cargar())
        self.solo_pend = tk.BooleanVar(value=False)
        ttk.Checkbutton(fila, text='Solo sin resolver', variable=self.solo_pend, style='Panel.TCheckbutton',
                        command=self.cargar).pack(side='left', padx=12)
        cuerpo = ttk.Frame(f, style='Panel.TFrame')
        cuerpo.pack(fill='both', expand=True)
        self.vista = tk.Canvas(cuerpo, width=430, bg=FONDO, highlightthickness=0)
        self.vista.pack(side='right', fill='y', padx=(12, 0))
        self.vista.bind('<Configure>', lambda e: self.previsualizar())
        cols = ('variante', 'mate', 'dificultad', 'juegan', 'origen', 'estado')
        self.tabla = ttk.Treeview(cuerpo, columns=cols, show='headings', selectmode='browse')
        for c, txt, ancho in zip(cols, ('Variante', 'Problema', 'Dificultad', 'Juegan', 'Origen', 'Estado'),
                                 (120, 220, 75, 65, 240, 80)):
            self.tabla.heading(c, text=txt)
            self.tabla.column(c, width=ancho, anchor='w')
        self.tabla.pack(side='left', fill='both', expand=True)
        self.tabla.bind('<Double-Button-1>', lambda e: self.resolver())
        self.tabla.bind('<<TreeviewSelect>>', lambda e: self.previsualizar())
        self.log = tk.Text(f, height=5, bg='#1E1B18', fg=TEXTO, font=('DejaVu Sans Mono', 9), relief='flat')
        b = ttk.Frame(f, style='Panel.TFrame')
        b.pack(side='bottom', fill='x', pady=(8, 0))
        ttk.Button(b, text='Resolver', style='Comenzar.TButton', command=self.resolver).pack(side='left')
        self.btn_buscar = ttk.Button(b, text='Buscar problemas en mis bitácoras', command=self.buscar)
        self.btn_buscar.pack(side='left', padx=6)
        self.tacticos = tk.BooleanVar(value=False)
        ttk.Checkbutton(b, text='Tácticos (más lento)', variable=self.tacticos,
                        style='Panel.TCheckbutton').pack(side='left')
        ttk.Button(b, text='Cerrar', command=self.cerrar).pack(side='right')
        self.proc, self.cola = None, queue.Queue()
        self.cargar()

    def cargar(self):
        todos = PG.cargar_problemas()
        if self.variante is not None:
            todos = [p for p in todos if es_de_variante(p, self.variante)]
        variantes = sorted({p.get('variante_nombre', '?') for p in todos})
        actual = self.cmb_var.get()
        self.cmb_var.configure(values=['Todas'] + variantes)
        self.cmb_var.set(actual if actual in variantes else 'Todas')
        resueltos = PG.problemas_resueltos()
        n = self.cmb_n.get()
        elo, puntuados = PG.elo_problemas()
        self.lbl_elo.configure(text='Tu Elo de problemas: %d%s' % (
            elo, (' (%d puntuados)' % puntuados) if puntuados else ' (aún sin puntuar)'))
        self.todos = todos
        criterio = self.cmb_orden.get()
        if criterio == 'Para mi nivel':
            orden = lambda p: (abs(PG.elo_problema(p) - elo), p['id'])
        elif criterio == 'Más fáciles primero':
            orden = lambda p: (PG.elo_problema(p), p['id'])
        elif criterio == 'Más difíciles primero':
            orden = lambda p: (-PG.elo_problema(p), p['id'])
        else:
            orden = lambda p: (p.get('variante_nombre', ''), p.get('tipo', 'mate'), p.get('mate_en', 0), -p.get('gana', 0))
        self.lista = [p for p in sorted(todos, key=orden)
                      if self.cmb_var.get() in ('Todas', p.get('variante_nombre'))
                      and self._tipo_ok(p, n)
                      and not (self.solo_pend.get() and p['id'] in resueltos)]
        self.tabla.delete(*self.tabla.get_children())
        for i, p in enumerate(self.lista):
            self.tabla.insert('', 'end', iid=str(i), values=(
                p.get('variante_nombre', '?'), self.describir(p), PG.elo_problema(p),
                'blancas' if p['turno'] == 0 else 'negras',
                p.get('origen', ''), '✓ resuelto' if p['id'] in resueltos else ''))
        if self.lista:
            self.tabla.selection_set('0')
            self.tabla.see('0')
        else:
            self.vista.delete('all')
        if not todos:
            self.tabla.insert('', 'end', iid='vacio', values=(
                'Todavía no hay problemas.', '', '', '', 'Pulsa «Buscar problemas en mis bitácoras» (salen de las '
                'partidas y simulaciones de esta variante).', ''))

    def previsualizar(self):
        sel = self.tabla.selection()
        if not sel or sel[0] == 'vacio' or not hasattr(self, 'lista'):
            return
        p = self.lista[int(sel[0])]
        try:
            v, st, marcas = posicion_de_problema(p)
        except Exception:  # un problema de otra versión de las reglas: sin vista previa
            self.vista.delete('all')
            return
        juegan = 'blancas' if p['turno'] == 0 else 'negras'
        texto = '%s · juegan las %s' % (self.describir(p), juegan)
        dibujar_tablero(self.vista, self.app, v, st, marcas, girado=p['turno'] == 1, texto=texto)

    @staticmethod
    def _tipo_ok(p, filtro):
        tactico = p.get('tipo') == 'tactico'
        if filtro == 'Todos':
            return True
        if filtro == 'Mis errores':
            return bool(p.get('personal'))
        if filtro == 'Tácticos':
            return tactico and not p.get('personal')
        return not tactico and filtro == 'Mate en %d' % p['mate_en']

    @staticmethod
    def describir(p):
        if p.get('personal'):
            return 'Tu error: jugaste %s (perdía %.1f)' % (p.get('jugaste', '?'), p.get('gana', 0))
        if p.get('tipo') == 'tactico':
            return 'Táctica: %s (gana %.1f)' % (p.get('tema', '?'), p.get('gana', 0))
        return 'Mate en %d' % p['mate_en']

    def resolver(self):
        sel = self.tabla.selection()
        if not sel or sel[0] == 'vacio':
            return
        p = self.lista[int(sel[0])]
        self.cerrar()
        self.app.resolver(p, self.lista)

    def del_dia(self):
        """El problema del día: uno sin resolver cerca de tu Elo, el mismo durante todo el día."""
        elo, _ = PG.elo_problemas()
        p = PG.problema_del_dia(self.todos, elo)
        if p is None:
            messagebox.showinfo('Problema del día', 'No quedan problemas sin resolver.', parent=self.top)
            return
        self.cerrar()
        self.app.resolver(p, [p])

    def estadisticas(self):
        """Tus resultados por tema: intentados, resueltos al primer intento y resueltos alguna vez."""
        filas = PG.estadisticas_problemas(self.todos)
        top = tk.Toplevel(self.top)
        top.title('Estadísticas de problemas')
        top.configure(bg=FONDO)
        top.geometry('640x420')
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        elo, n = PG.elo_problemas()
        ttk.Label(f, text='Estadísticas de problemas', style='Titulo.TLabel').pack(anchor='w')
        historial = (PG.cargar_perfil().get('elo_problemas') or {}).get('historial', [])
        maximo = max([e for _, e in historial] or [elo])
        ttk.Label(f, style='Panel.TLabel', text='Tu Elo de problemas: %d (máximo %d) · %d problemas puntuados. Solo el '
                  'primer intento de cada problema cuenta; ver la solución antes de intentarlo cuenta como fallo.' % (
                      elo, maximo, n), wraplength=600, justify='left').pack(anchor='w', pady=(2, 8))
        cols = ('cat', 'int', 'primero', 'alguna')
        t = ttk.Treeview(f, columns=cols, show='headings')
        for c, txt, ancho in zip(cols, ('Tema', 'Intentados', 'Al primer intento', 'Resueltos'), (230, 90, 140, 100)):
            t.heading(c, text=txt)
            t.column(c, width=ancho, anchor='w')
        t.pack(fill='both', expand=True)
        total = [0, 0, 0]
        for cat, a, b, c in filas:
            t.insert('', 'end', values=(cat, a, '%d (%.0f %%)' % (b, 100 * b / a), c))
            total = [total[0] + a, total[1] + b, total[2] + c]
        if total[0]:
            t.insert('', 'end', values=('TOTAL', total[0], '%d (%.0f %%)' % (total[1], 100 * total[1] / total[0]),
                                        total[2]))
        else:
            t.insert('', 'end', values=('Todavía no has intentado ningún problema.', '', '', ''))
        ttk.Button(f, text='Cerrar', command=top.destroy).pack(anchor='e', pady=(8, 0))

    def buscar(self):
        if self.proc is not None:
            return
        script = os.path.join(os.path.dirname(PG.AQUI), 'Simulador', 'extraer_problemas.py')
        from simulacion import buscar_pypy
        self.log.pack(fill='x', pady=(6, 0), before=self.tabla)
        self.log.delete('1.0', 'end')
        try:
            extra = ['--tacticos', '--max', '400'] if self.tacticos.get() else ['--max-mate', '3']
            self.proc = subprocess.Popen([buscar_pypy() or sys.executable, '-u', script] + extra +
                                         ['--procesos', str(max(1, (os.cpu_count() or 2) // 2))],
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                         **PROCESO)
        except OSError as e:
            messagebox.showerror('Problemas', str(e), parent=self.top)
            return
        self.btn_buscar.state(['disabled'])
        threading.Thread(target=self._leer, args=(self.proc,), daemon=True).start()
        self.sondear()

    def _leer(self, proc):
        for linea in proc.stdout:
            self.cola.put(linea)
        proc.wait()
        self.cola.put(None)

    def sondear(self):
        if not self.top.winfo_exists():
            return
        try:
            while True:
                linea = self.cola.get_nowait()
                if linea is None:
                    self.proc = None
                    self.btn_buscar.state(['!disabled'])
                    self.cargar()
                    return
                self.log.insert('end', linea)
                self.log.see('end')
        except queue.Empty:
            pass
        self.top.after(200, self.sondear)

    def cerrar(self):
        if self.proc is not None:
            self.proc.kill()
            self.proc = None
        self.top.destroy()


class ImportarPartida:
    """Pega (o abre) una partida en texto y la reproduce, con la opción de analizarla."""

    def __init__(self, app):
        self.app = app
        top = self.top = tk.Toplevel(app.root)
        top.title('Importar partida')
        top.configure(bg=FONDO)
        top.geometry('760x520')
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Importar partida', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(f, text='Pega una partida exportada desde el juego (botón «Exportar…») o ábrela de un archivo. '
                          'Las jugadas se escriben en la notación del juego; el encabezado [Variante "..."] indica '
                          'la variante.', style='Panel.TLabel', wraplength=720, justify='left').pack(anchor='w',
                                                                                                pady=(2, 8))
        self.txt = tk.Text(f, font=('DejaVu Sans Mono', 10), height=16)
        self.txt.pack(fill='both', expand=True)
        try:
            pegado = app.root.clipboard_get()
            if '[Variante' in pegado:
                self.txt.insert('1.0', pegado)
        except tk.TclError:
            pass
        self.error = ttk.Label(f, style='Error.TLabel', wraplength=720, justify='left')
        self.error.pack(anchor='w', pady=(4, 0))
        b = ttk.Frame(f, style='Panel.TFrame')
        b.pack(fill='x', pady=(8, 0))
        ttk.Button(b, text='Abrir archivo…', command=self.abrir).pack(side='left')
        # un archivo exportado desde «Partidas guardadas» puede traer varias: se elige cuál
        self.cmb_partida = ttk.Combobox(b, state='readonly', width=46)
        self.txt.bind('<<Modified>>', self._modificado)
        self.partes = []
        self._modificado()
        ttk.Button(b, text='Cerrar', command=top.destroy).pack(side='right')
        ttk.Button(b, text='Reproducir y analizar', command=lambda: self.importar(True)).pack(side='right', padx=6)
        ttk.Button(b, text='Reproducir', style='Comenzar.TButton', command=self.importar).pack(side='right')

    def abrir(self):
        ruta = filedialog.askopenfilename(parent=self.top, title='Abrir partida',
                                          filetypes=[('Texto', '*.txt *.pgn'), ('Todos los archivos', '*')])
        if ruta:
            with open(ruta, encoding='utf-8', errors='replace') as fh:
                self.txt.delete('1.0', 'end')
                self.txt.insert('1.0', fh.read())

    @staticmethod
    def separar(texto):
        """Las partidas de un texto: cada una empieza en su encabezado [Variante "..."]."""
        inicios = [m.start() for m in re.finditer(r'^\[Variante ', texto, re.M)]
        if len(inicios) < 2:
            return [texto]
        return [texto[a:b] for a, b in zip(inicios, inicios[1:] + [len(texto)])]

    def _modificado(self, ev=None):
        self.txt.edit_modified(False)
        self.partes = self.separar(self.txt.get('1.0', 'end'))
        if len(self.partes) < 2:
            self.cmb_partida.pack_forget()
            return
        nombres = []
        for k, t in enumerate(self.partes, 1):
            enc = dict(re.findall(r'\[(\w+)\s+"([^"]*)"\]', t))
            nombres.append('Partida %d · %s · %s vs %s · %s' % (k, enc.get('Fecha', '')[:10], enc.get('Blancas', '?'),
                                                                 enc.get('Negras', '?'), enc.get('Resultado', '*')))
        actual = self.cmb_partida.current()
        self.cmb_partida.configure(values=nombres)
        self.cmb_partida.current(actual if 0 <= actual < len(nombres) else 0)
        self.cmb_partida.pack(side='left', padx=8)

    def importar(self, analizar=False):
        import textos as TX
        import bitacora as BIT
        texto = self.txt.get('1.0', 'end')
        if len(self.partes) > 1:
            texto = self.partes[max(0, self.cmb_partida.current())]
        try:
            v, inicio, jugadas, enc = TX.leer_partida(texto)
        except ValueError as e:
            self.error.configure(text=str(e))
            return
        if not jugadas:
            self.error.configure(text='No encontré jugadas.')
            return
        st = v.inicial() if inicio is None else v.construir(inicio['piezas'], inicio['turno'])
        r = BIT.nuevo('importada', v.spec, inicio, variante_nombre=v.nombre,
                      blancas={'nivel': enc.get('Blancas', '?')}, negras={'nivel': enc.get('Negras', '?')})
        for k, (i, nota) in enumerate(jugadas):
            r['jugadas'].append(BIT.jugada(i, nota, (st.turn + k) % 2))
        res = {'1-0': 'blancas', '0-1': 'negras', '1/2-1/2': 'tablas'}.get(enc.get('Resultado'))
        if res:
            r.update(resultado=res, motivo=enc.get('Motivo', ''))
        self.top.destroy()
        self.app.reproducir(r, '(partida importada)', analizar=analizar)


class Finales:
    """Elige un final de Rey y una o dos piezas contra Rey (en cualquier variante con tablas) para practicarlo o
    para ver cómo da mate la computadora."""

    def __init__(self, app, variante=None):
        import practica_finales as F
        import variantes as V
        self.app, self.F, self.V = app, F, V
        self.proc, self.cola = None, queue.Queue()
        top = self.top = tk.Toplevel(app.root)
        top.title('Finales')
        top.configure(bg=FONDO)
        top.geometry('1300x680')
        top.protocol('WM_DELETE_WINDOW', self.cerrar)
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        arriba = ttk.Frame(f, style='Panel.TFrame')
        arriba.pack(fill='x')
        ttk.Label(arriba, text='Finales de Rey y piezas contra Rey', style='Titulo.TLabel').pack(side='left')
        if variante is not None:  # desde la pantalla de una variante: solo sus finales
            self.variantes = [variante]
            top.title('Finales — ' + variante.nombre)
        else:
            self.variantes = V.todas() + [V.Generica(c) for c in V.guardadas()]
            self.variantes = [v for v in self.variantes if v.id == 'extendido' or self._aplicable(v)]
        self.cmb = ttk.Combobox(arriba, state='readonly', width=28, values=[v.nombre for v in self.variantes])
        self.cmb.current(next((k for k, v in enumerate(self.variantes) if v.id == 'extendido'), 0))
        self.cmb.bind('<<ComboboxSelected>>', lambda e: self.cargar())
        if variante is None:
            self.cmb.pack(side='right')
            ttk.Label(arriba, text='Variante', style='Panel.TLabel').pack(side='right', padx=6)
        else:
            ttk.Label(arriba, text=variante.nombre, style='Estado.TLabel').pack(side='right')
        ttk.Label(f, style='Panel.TLabel', wraplength=920, justify='left', text=(
            'La computadora juega estos finales a la perfección con tablas exactas: da el mate más corto o, '
            'defendiéndose, resiste lo máximo posible. Practica dando mate (o defendiéndote) y el panel te dirá si '
            'cada jugada fue perfecta, o mira cómo lo hace ella. La computadora también usa estas tablas en sus '
            'partidas.')).pack(anchor='w', pady=(4, 8))
        cuerpo = ttk.Frame(f, style='Panel.TFrame')
        cuerpo.pack(fill='both', expand=True)
        cols = ('pieza', 'mate', 'inicio', 'largo')
        self.tabla = ttk.Treeview(cuerpo, columns=cols, show='headings', selectmode='browse', height=18)
        for c, txt, ancho in zip(cols, ('Piezas', '¿Se fuerza el mate?', 'Desde el inicio', 'El más largo'),
                                 (230, 170, 120, 100)):
            self.tabla.heading(c, text=txt)
            self.tabla.column(c, width=ancho, anchor='w')
        self.vista = tk.Canvas(cuerpo, width=360, bg=FONDO, highlightthickness=0)
        self.vista.pack(side='right', fill='y', padx=(12, 0))
        self.vista.bind('<Configure>', lambda e: self.previsualizar())
        self.tabla.pack(side='left', fill='both', expand=True)
        self.tabla.bind('<Double-Button-1>', lambda e: self.comenzar())
        opciones = ttk.Frame(cuerpo, style='Panel.TFrame', padding=(16, 0, 0, 0))
        opciones.pack(side='left', fill='y')
        ttk.Label(opciones, text='QUÉ QUIERES HACER', style='Sub.TLabel').pack(anchor='w')
        self.modo = tk.StringVar(value='atacar')
        for txt, val in (('Practicar: das mate (blancas)', 'atacar'), ('Practicar: te defiendes (Rey negro)', 'defender'),
                         ('Ver a la computadora dar mate', 'ver')):
            ttk.Radiobutton(opciones, text=txt, value=val, variable=self.modo, style='Panel.TRadiobutton').pack(
                anchor='w', pady=1)
        ttk.Label(opciones, text='POSICIÓN', style='Sub.TLabel').pack(anchor='w', pady=(14, 0))
        self.posicion = tk.StringVar(value='inicial')
        ttk.Radiobutton(opciones, text='Casillas iniciales de la variante', value='inicial',
                        variable=self.posicion, style='Panel.TRadiobutton').pack(anchor='w', pady=1)
        ttk.Radiobutton(opciones, text='Al azar:', value='aleatoria', variable=self.posicion,
                        style='Panel.TRadiobutton').pack(anchor='w', pady=1)
        self.dificultad = ttk.Combobox(opciones, state='readonly', width=28, values=[d[0] for d in F.DIFICULTADES])
        self.dificultad.current(1)
        self.dificultad.pack(anchor='w', padx=(22, 0))
        self.dificultad.bind('<<ComboboxSelected>>', lambda e: self.posicion.set('aleatoria'))
        ttk.Label(opciones, text='COLOR DEL ALFIL', style='Sub.TLabel').pack(anchor='w', pady=(14, 0))
        self.color = ttk.Combobox(opciones, state='readonly', width=28, values=[c[0] for c in F.COLORES_ALFIL])
        self.color.current(0)
        self.color.pack(anchor='w', padx=(22, 0))
        self.color.bind('<<ComboboxSelected>>', lambda e: self.previsualizar())
        self.lbl_color = ttk.Label(opciones, style='Panel.TLabel', wraplength=230, justify='left')
        self.lbl_color.pack(anchor='w', padx=(22, 0))
        self.tabla.bind('<<TreeviewSelect>>', lambda e: self.cambio_seleccion())
        ttk.Label(opciones, text='TABLAS', style='Sub.TLabel').pack(anchor='w', pady=(14, 0))
        self.btn_construir = ttk.Button(opciones, text='Construir las que faltan', command=self.construir)
        self.btn_construir.pack(anchor='w', pady=(2, 0))
        self.pares = tk.BooleanVar(value=False)
        ttk.Checkbutton(opciones, text='Incluir pares de piezas (más lento)', variable=self.pares,
                        style='Panel.TCheckbutton').pack(anchor='w')
        self.aviso = ttk.Label(opciones, style='Error.TLabel', wraplength=300, justify='left')
        self.aviso.pack(anchor='w', pady=(8, 0))
        b = ttk.Frame(f, style='Panel.TFrame')
        b.pack(fill='x', pady=(10, 0))
        ttk.Button(b, text='Comenzar', style='Comenzar.TButton', command=self.comenzar).pack(side='left')
        ttk.Button(b, text='Cerrar', command=self.cerrar).pack(side='right')
        self.cargar()

    @staticmethod
    def _aplicable(v):
        import tablas_genericas as TG
        return TG.aplicable(v.cfg) and bool(TG.piezas_posibles(v.cfg))

    def variante(self):
        return self.variantes[self.cmb.current()]

    def cargar(self):
        v = self.variante()
        self.practica = self.F.para(v)
        self.tabla.delete(*self.tabla.get_children())
        self.items = {}
        faltan = 0
        for cfg, nombre, hay, info in self.practica.opciones():
            faltan += not hay
            if not info:
                mate, ini, largo = '?', '', ''
            elif info['ganadas'] < 0.005:
                mate, ini, largo = 'no (tablas)', '—', '—'
            else:
                pct = 100 * info['ganadas']
                mate = 'sí' if pct > 99.9 else 'en el %.0f %% de los casos' % pct
                ini = ('mate en %d' % info['inicio']) if info.get('inicio') else 'no'
                largo = '%d jugadas' % info['maximo'] if info.get('maximo') else '—'
            iid = self.tabla.insert('', 'end', values=(nombre + ('' if hay else '  (sin tabla)'), mate, ini, largo))
            self.items[iid] = (cfg, nombre, hay)
        if self.tabla.get_children():
            self.tabla.selection_set(self.tabla.get_children()[0])
        self.cambio_seleccion()
        es11 = v.id == 'extendido'
        self.btn_construir.state(['disabled'] if es11 or self.proc else ['!disabled'])
        if es11:
            self.aviso.configure(text=('Faltan %d tablas del Ajedrez Extendido. Constrúyelas con:\npypy3 Simulador/finales.py '
                                       '--guardar-tablas' % faltan) if faltan else '')
        else:
            self.aviso.configure(text=('Faltan %d tablas: pulsa «Construir las que faltan» (segundos o pocos '
                                       'minutos).' % faltan) if faltan else '')

    def previsualizar(self):
        """La posición inicial del final elegido (con el color del Alfil, si se eligió)."""
        if not hasattr(self, 'items') or not hasattr(self, 'color'):
            return
        sel = self.tabla.selection()
        if not sel or sel[0] not in self.items:
            self.vista.delete('all')
            return
        cfg, nombre, hay = self.items[sel[0]]
        cfg = dict(cfg, posicion='inicial')
        if self.practica.alfiles(cfg) == 1:
            cfg['color_alfil'] = self.F.COLORES_ALFIL[self.color.current()][1]
        v = self.variante()
        try:
            ini = self.practica.posicion(cfg)
            st = v.construir(ini['piezas'], ini['turno'])
        except Exception:
            self.vista.delete('all')
            return
        texto = '%s · posición inicial' % nombre
        if hay:
            w = self.practica.valor(st)
            if w and w[0] == 'gana':
                texto += ' · mate en %d' % ((w[1] + 1) // 2)
            elif w:
                texto += ' · tablas'
        dibujar_tablero(self.vista, self.app, v, st, texto=texto)

    def cambio_seleccion(self):
        """El color del Alfil solo se elige si el final tiene exactamente un Alfil (con dos, van en colores
        distintos: con dos del mismo color no hay mate)."""
        self.previsualizar()
        sel = self.tabla.selection()
        n = self.practica.alfiles(self.items[sel[0]][0]) if sel and sel[0] in self.items else 0
        self.color.state(['!disabled'] if n == 1 else ['disabled'])
        self.lbl_color.configure(text={0: '', 1: 'En el Ajedrez Extendido las cuatro esquinas son claras.' if
                                       self.variante().id == 'extendido' else '',
                                       2: 'Dos Alfiles: siempre en colores distintos.'}.get(n, ''))

    def construir(self):
        if self.proc is not None:
            return
        v = self.variante()
        import tablas_genericas as TG
        os.makedirs(TG.CARPETA, exist_ok=True)
        ruta = os.path.join(TG.CARPETA, '_variante_%s.json' % re.sub(r'[^a-z0-9]+', '_', v.nombre.lower()))
        import json as _json
        with open(ruta, 'w', encoding='utf-8') as fh:
            _json.dump(v.cfg, fh, ensure_ascii=False)
        script = os.path.join(os.path.dirname(PG.AQUI), 'Simulador', 'finales_variante.py')
        from simulacion import buscar_pypy
        cmd = [buscar_pypy() or sys.executable, '-u', script, ruta] + (['--pares'] if self.pares.get() else [])
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                         bufsize=1, **PROCESO)
        except OSError as e:
            messagebox.showerror('Finales', str(e), parent=self.top)
            self.proc = None
            return
        self.btn_construir.state(['disabled'])
        threading.Thread(target=self._leer, args=(self.proc,), daemon=True).start()
        self.sondear()

    def _leer(self, proc):
        for linea in proc.stdout:
            self.cola.put(linea)
        proc.wait()
        self.cola.put(None)

    def sondear(self):
        if not self.top.winfo_exists():
            return
        try:
            while True:
                linea = self.cola.get_nowait()
                if linea is None:
                    self.proc = None
                    self.cargar()
                    return
                self.aviso.configure(text='Construyendo… ' + linea.strip()[:120])
        except queue.Empty:
            pass
        self.top.after(200, self.sondear)

    def comenzar(self):
        sel = self.tabla.selection()
        if not sel:
            return
        cfg, nombre, hay = self.items[sel[0]]
        if not hay:
            self.aviso.configure(text='Ese final no tiene su tabla todavía.')
            return
        _, lo, hi = self.F.DIFICULTADES[self.dificultad.current()]
        v = self.variante()
        cfg = dict(cfg, nombre=nombre, modo=self.modo.get(), posicion=self.posicion.get(), dificultad=(lo, hi))
        if self.practica.alfiles(cfg) == 1:
            etiqueta, color = self.F.COLORES_ALFIL[self.color.current()]
            if color:
                cfg['color_alfil'] = color
                cfg['nombre'] = '%s (Alfil de %s)' % (nombre, etiqueta.lower())
        if v.id != 'extendido':
            cfg['variante'] = v.spec
        self.cerrar()
        self.app.iniciar_final(cfg)

    def cerrar(self):
        if self.proc is not None:
            self.proc.kill()
            self.proc = None
        self.top.destroy()


class Lecciones:
    """«Aprende a jugar» (Ajedrez Extendido): lecciones cortas por pieza y por regla especial, con ejercicios en el tablero."""

    def __init__(self, app):
        import lecciones as L
        import variantes as V
        self.app, self.L, self.v = app, L, V.Extendido()
        top = self.top = tk.Toplevel(app.root)
        top.title('Aprende a jugar — Ajedrez Extendido')
        top.configure(bg=FONDO)
        top.geometry('1180x640')
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Aprende a jugar', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(f, style='Panel.TLabel', wraplength=1100, justify='left', text=(
            'Lecciones cortas, una por pieza y por cada regla especial del Ajedrez Extendido. Cada ejercicio te pide algo '
            'concreto (mover, capturar, saltar, extender, dar mate) y se comprueba al hacer la jugada; el bando '
            'negro no responde. Las casillas del objetivo se marcan en el tablero.')).pack(anchor='w', pady=(4, 8))
        cuerpo = ttk.Frame(f, style='Panel.TFrame')
        cuerpo.pack(fill='both', expand=True)
        cols = ('leccion', 'ejercicios', 'hechos')
        self.tabla = ttk.Treeview(cuerpo, columns=cols, show='headings', selectmode='browse', height=16)
        for c, txt, ancho in zip(cols, ('Lección', 'Ejercicios', 'Completados'), (250, 90, 110)):
            self.tabla.heading(c, text=txt)
            self.tabla.column(c, width=ancho, anchor='w')
        self.vista = tk.Canvas(cuerpo, width=360, bg=FONDO, highlightthickness=0)
        self.vista.pack(side='right', fill='y', padx=(12, 0))
        self.vista.bind('<Configure>', lambda e: self.previsualizar())
        self.tabla.pack(side='left', fill='both', expand=True)
        self.tabla.bind('<Double-Button-1>', lambda e: self.comenzar())
        self.tabla.bind('<<TreeviewSelect>>', lambda e: self.previsualizar())
        lado = ttk.Frame(cuerpo, style='Panel.TFrame', padding=(16, 0, 0, 0), width=300)
        lado.pack(side='left', fill='y')
        lado.pack_propagate(False)
        ttk.Label(lado, text='LA REGLA', style='Sub.TLabel').pack(anchor='w')
        self.lbl_regla = ttk.Label(lado, style='Panel.TLabel', wraplength=280, justify='left')
        self.lbl_regla.pack(anchor='w', pady=(2, 8), fill='x')
        ttk.Button(lado, text='Comenzar', style='Comenzar.TButton', command=self.comenzar).pack(
            side='bottom', fill='x')
        ttk.Button(lado, text='Ver la regla completa', command=self.ver_regla).pack(side='bottom', fill='x',
                                                                                     pady=(0, 6))
        try:
            import reglas
            self.reglas = {t: b for t, b in reglas.contenido_extendido()}
        except Exception:
            self.reglas = {}
        self.cargar()

    def cargar(self):
        hechas = PG.lecciones_hechas()
        self.tabla.delete(*self.tabla.get_children())
        primera = None
        for i, lec in enumerate(self.L.LECCIONES):
            n, h = len(lec['tareas']), min(hechas.get(lec['id'], 0), len(lec['tareas']))
            self.tabla.insert('', 'end', iid=str(i), values=(
                lec['titulo'], n, ('✓ todos' if h >= n else '%d de %d' % (h, n))))
            if primera is None and h < n:
                primera = i
        self.tabla.selection_set(str(primera or 0))
        self.tabla.see(str(primera or 0))

    def seleccion(self):
        sel = self.tabla.selection()
        return int(sel[0]) if sel else None

    def previsualizar(self):
        i = self.seleccion()
        if i is None:
            return
        lec = self.L.LECCIONES[i]
        k = min(PG.lecciones_hechas().get(lec['id'], 0), len(lec['tareas']) - 1)
        t = lec['tareas'][k]
        st = self.L.estado(self.v, t)
        dibujar_tablero(self.vista, self.app, self.v, st, self.L.casillas_objetivo(t),
                        texto='Ejercicio %d de %d' % (k + 1, len(lec['tareas'])))
        bloques = self.reglas.get(lec['regla'], [])
        textos = [x for tipo, dato, *_ in bloques if tipo in ('lista', 'p')
                  for x in (dato if tipo == 'lista' else [dato])]
        texto = '\n\n'.join(textos[:4])
        self.lbl_regla.configure(text=texto[:900] + ('…' if len(texto) > 900 else ''))

    def ver_regla(self):
        i = self.seleccion()
        if i is None:
            return
        from reglas import VentanaReglas
        VentanaReglas(self.app, self.v, self.L.LECCIONES[i]['regla'])

    def comenzar(self):
        i = self.seleccion()
        if i is None:
            return
        lec = self.L.LECCIONES[i]
        k = PG.lecciones_hechas().get(lec['id'], 0)
        self.top.destroy()
        self.app.leccion(i, k if k < len(lec['tareas']) else 0)


class Aperturas:
    """Explorador de aperturas del Ajedrez Extendido: qué se jugó en cada posición y cómo terminó, más la evaluación del
    libro de aperturas de la computadora. Doble clic en una jugada para avanzar."""

    SEGUIR = ['la jugada más jugada', 'la mejor del libro', 'nada (se detiene)']

    def __init__(self, app, hist=None):
        import aperturas as AP
        import variantes as V
        self.app, self.AP, self.v = app, AP, V.Extendido()
        top = self.top = tk.Toplevel(app.root)
        top.title('Explorador de aperturas — Ajedrez Extendido')
        top.configure(bg=FONDO)
        top.geometry('1240x660')
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        arriba = ttk.Frame(f, style='Panel.TFrame')
        arriba.pack(fill='x')
        ttk.Label(arriba, text='Explorador de aperturas', style='Titulo.TLabel').pack(side='left')
        self.sim, self.mias = tk.BooleanVar(value=True), tk.BooleanVar(value=True)
        for txt, var in (('Mis partidas y espectador', self.mias), ('Simulaciones', self.sim)):
            ttk.Checkbutton(arriba, text=txt, variable=var, style='Panel.TCheckbutton',
                            command=self.recargar).pack(side='right', padx=6)
        self.libro = AP.cargar_libro()
        nota_libro = ('El libro (profundidad %s, %d posiciones) da la evaluación de cada jugada para el bando que '
                      'mueve.' % (self.libro.get('prof'), len(self.libro.get('posiciones', {})))
                      if self.libro else 'Aún no hay libro de aperturas: créalo con pypy3 Simulador/libro_aperturas.py.')
        ttk.Label(f, style='Panel.TLabel', wraplength=1180, justify='left', text=(
            'Doble clic en una jugada para avanzar. «▶ Reproducir» recorre la línea jugada a jugada y, al terminarla, '
            'puede seguir por la jugada más jugada o por la mejor del libro. «Puntos» es el porcentaje de puntos que '
            'sacó el bando que mueve con esa jugada. Ojo: las simulaciones empiezan con 4 medias jugadas al azar '
            'para variar, así que en las primeras jugadas sus números dicen cómo le fue a cada salida, no lo que '
            'elegiría la computadora (columna «Al azar»). ' + nota_libro)).pack(anchor='w', pady=(4, 6))
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(0, 2))
        for txt, cmd in (('⏮', lambda: self.mover_a(0)), ('◀', lambda: self.mover_a(self.pos - 1)),
                         ('▶', self.adelante)):
            ttk.Button(fila, text=txt, width=3, command=cmd).pack(side='left', padx=(0, 2))
        self.btn_reproducir = ttk.Button(fila, text='▶ Reproducir', command=self.alternar)
        self.btn_reproducir.pack(side='left', padx=(6, 2))
        ttk.Label(fila, text='Velocidad', style='Panel.TLabel').pack(side='left', padx=(10, 4))
        self.velocidad = tk.DoubleVar(value=1.2)
        ttk.Scale(fila, from_=3.0, to=0.3, variable=self.velocidad, length=110).pack(side='left')
        ttk.Label(fila, text='Al terminar, seguir por', style='Panel.TLabel').pack(side='left', padx=(12, 4))
        self.cmb_seguir = ttk.Combobox(fila, state='readonly', width=22, values=self.SEGUIR)
        self.cmb_seguir.current(1 if self.libro else 0)
        self.cmb_seguir.pack(side='left')
        ttk.Button(fila, text='Abrir en el tablero', command=self.abrir_tablero).pack(side='right')
        self.lbl_camino = ttk.Label(f, style='Estado.TLabel', wraplength=1180, justify='left')
        self.lbl_camino.pack(anchor='w', pady=(2, 6))
        cuerpo = ttk.Frame(f, style='Panel.TFrame')
        cuerpo.pack(fill='both', expand=True)
        self.vista = tk.Canvas(cuerpo, width=430, bg=FONDO, highlightthickness=0)
        self.vista.pack(side='right', fill='y', padx=(12, 0))
        self.vista.bind('<Configure>', lambda e: self.dibujar())
        cols = ('jugada', 'n', 'blancas', 'tablas', 'negras', 'puntos', 'libro', 'azar')
        self.tabla = ttk.Treeview(cuerpo, columns=cols, show='headings', selectmode='browse')
        for c, txt, ancho in zip(cols, ('Jugada', 'Partidas', 'Ganan blancas', 'Tablas', 'Ganan negras', 'Puntos',
                                        'Libro', 'Al azar'), (90, 70, 95, 70, 95, 70, 70, 70)):
            self.tabla.heading(c, text=txt)
            self.tabla.column(c, width=ancho, anchor='w')
        barra = ttk.Scrollbar(cuerpo, command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        barra.pack(side='right', fill='y')
        self.tabla.pack(side='left', fill='both', expand=True)
        self.tabla.bind('<Double-Button-1>', lambda e: self.avanzar())
        self.tabla.bind('<Return>', lambda e: self.avanzar())
        self.tabla.bind('<<TreeviewSelect>>', lambda e: self.dibujar())
        self.lbl_total = ttk.Label(f, style='Panel.TLabel')
        self.lbl_total.pack(anchor='w', pady=(6, 0))
        for tecla, accion in (('<Left>', lambda e: self.mover_a(self.pos - 1)), ('<Right>', lambda e: self.adelante()),
                              ('<Home>', lambda e: self.mover_a(0)), ('<End>', lambda e: self.mover_a(len(self.camino))),
                              ('<space>', lambda e: self.alternar())):
            top.bind(tecla, accion)
        top.protocol('WM_DELETE_WINDOW', self.cerrar)
        self.hist, self.camino, self.pos, self.reproduciendo, self.prox = [], list(hist or []), 0, False, None
        self.recargar(hist or [])

    def recargar(self, hist=None):
        self.top.configure(cursor='watch')
        self.top.update_idletasks()
        self.arbol, self.total = self.AP.construir(self.sim.get(), self.mias.get())
        self.top.configure(cursor='')
        self.mover_a(len(self.hist) if hist is None else len(hist))

    def mover_a(self, pos):
        """Muestra la posición tras las primeras pos jugadas de la línea (la línea completa se conserva)."""
        self.ir(self.camino[:max(0, min(pos, len(self.camino)))])

    def ir(self, hist):
        """Muestra la posición tras hist (solo hasta donde sean jugadas legales)."""
        st, notas, marcas = self.v.inicial(), [], ()
        valida, k = [], 0
        for i in self.camino:  # toda la línea, para mostrar también lo que sigue
            movs = self.v.legal(st)
            if not 0 <= i < len(movs):
                break
            mv, n = movs[i]
            notas.append(self.v.notacion(st, mv, n, movs))
            if k < len(hist):
                marcas = self.v.casillas(mv)
                self.ultima_captura = self.v.es_captura(st, mv)
                self.st = n
                valida.append(i)
            st = n
            k += 1
        if not hist:
            self.st = self.v.inicial()
        self.camino = self.camino[:len(notas)]
        self.hist, self.pos, self.marcas = valida, len(valida), marcas
        st = self.st
        partes = []
        for k, nota in enumerate(notas):
            if k == self.pos:
                partes.append('   ▸')
            partes.append(('%d. %s' % (k // 2 + 1, nota)) if k % 2 == 0 else (('%d… %s' % (k // 2 + 1, nota))
                                                                                if k == self.pos else nota))
        self.lbl_camino.configure(text=(' '.join(partes) if notas else 'Posición inicial') +
                                  ('' if self.pos == len(notas) else '   (lo que sigue de la línea)'))
        self.filas = self.AP.filas(self.arbol, self.libro, self.hist, st.turn)
        self.tabla.delete(*self.tabla.get_children())
        pct = lambda a, n: ('%.0f %%' % (100.0 * a / n)) if n else ''
        for k, x in enumerate(self.filas):
            n = x['n']
            self.tabla.insert('', 'end', iid=str(k), values=(
                x['nota'], n or '', pct(x['b'], n), pct(x['t'], n), pct(x['ng'], n),
                ('%.0f %%' % x['puntos']) if x['puntos'] is not None else '',
                ('%+.2f' % x['libro']) if x['libro'] is not None else '', pct(x['azar'], n)))
        en_pos = sum(x['n'] for x in self.filas)
        self.lbl_total.configure(text='%d partidas en total · %d llegaron a esta posición%s' % (
            self.total, en_pos, '' if self.filas else ' · ninguna jugada registrada ni en el libro desde aquí'))
        if self.filas:
            self.tabla.selection_set('0')
        self.dibujar()

    def avanzar(self, idx=None):
        """Juega la jugada elegida en la tabla (o idx); si no es la que seguía en la línea, la línea cambia."""
        if idx is None:
            sel = self.tabla.selection()
            if not sel:
                return False
            idx = self.filas[int(sel[0])]['idx']
        if not (self.pos < len(self.camino) and self.camino[self.pos] == idx):
            self.camino = self.camino[:self.pos] + [idx]
        self.mover_a(self.pos + 1)
        return True

    def siguiente(self, criterio=None):
        """La jugada con la que seguir al final de la línea: la más jugada o la mejor del libro (None si no hay)."""
        criterio = self.cmb_seguir.current() if criterio is None else criterio
        if criterio == 1:
            del_libro = [x for x in self.filas if x['libro'] is not None]
            if del_libro:
                return max(del_libro, key=lambda x: x['libro'])['idx']
        if criterio in (0, 1) and self.filas:
            return self.filas[0]['idx']  # la más jugada (o, sin partidas, la primera del libro)
        return None

    def adelante(self, criterio=0):
        """Siguiente jugada de la línea; al final, la más jugada (o según el criterio de la reproducción)."""
        if self.pos < len(self.camino):
            self.mover_a(self.pos + 1)
            return True
        idx = self.siguiente(criterio)
        return idx is not None and self.avanzar(idx)

    def alternar(self):
        self.reproduciendo = not self.reproduciendo
        self.btn_reproducir.configure(text='⏸ Pausa' if self.reproduciendo else '▶ Reproducir')
        if self.reproduciendo:
            if self.pos >= len(self.camino) and self.siguiente() is None:
                self.mover_a(0)  # la línea ya terminó: empieza de nuevo
            self.paso()

    def paso(self):
        self.prox = None
        if not self.reproduciendo or not self.top.winfo_exists():
            return
        if not self.adelante(self.cmb_seguir.current()):
            self.reproduciendo = False
            self.btn_reproducir.configure(text='▶ Reproducir')
            return
        self.app.sonidos.tocar('captura' if getattr(self, 'ultima_captura', False) else 'movimiento')
        self.prox = self.top.after(int(1000 * self.velocidad.get()), self.paso)

    def abrir_tablero(self):
        """La línea en el tablero grande, como una partida para reproducir y analizar."""
        import bitacora as BIT
        if not self.camino:
            return
        st, r = self.v.inicial(), BIT.nuevo('importada', self.v.spec, None, variante_nombre=self.v.nombre,
                                            blancas={'nivel': 'Explorador de aperturas'},
                                            negras={'nivel': 'Explorador de aperturas'})
        for i in self.camino:
            movs = self.v.legal(st)
            mv, n = movs[i]
            r['jugadas'].append(BIT.jugada(i, self.v.notacion(st, mv, n, movs), st.turn))
            st = n
        self.cerrar()
        self.app.reproducir(r, '(apertura)')

    def cerrar(self):
        self.reproduciendo = False
        if self.prox is not None:
            self.top.after_cancel(self.prox)
        self.top.destroy()

    def dibujar(self):
        if not hasattr(self, 'st'):
            return
        sel = self.tabla.selection()
        marcas = self.marcas
        if self.reproduciendo:  # mientras se reproduce, la última jugada (no la elegida en la tabla)
            sel = ()
        texto = 'Juegan las %s' % ('blancas' if self.st.turn == 0 else 'negras')
        if sel and hasattr(self, 'filas') and int(sel[0]) < len(self.filas):
            x = self.filas[int(sel[0])]
            movs = self.v.legal(self.st)
            if x['idx'] < len(movs):
                marcas = self.v.casillas(movs[x['idx']][0])
                texto += ' · resaltada: %s' % x['nota']
        dibujar_tablero(self.vista, self.app, self.v, self.st, marcas, texto=texto)


class MasVariantes:
    """«Más variantes»: Gran Ajedrez, Jano, Embajada, Shatranj, Makruk... para jugarlas, ver sus reglas o abrirlas
    en el Laboratorio como base de una variante propia."""

    def __init__(self, app):
        import variantes as V
        self.app = app
        self.variantes = V.otras()
        top = self.top = tk.Toplevel(app.root)
        top.title('Más variantes')
        top.configure(bg=FONDO)
        top.geometry('1060x600')
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Más variantes', style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(f, style='Panel.TLabel', wraplength=1000, justify='left', text=(
            'Variantes históricas y modernas, con sus reglas. Puedes jugarlas contra la computadora o abrirlas en el '
            'Laboratorio para usarlas como base de tu propia variante.')).pack(anchor='w', pady=(4, 8))
        cuerpo = ttk.Frame(f, style='Panel.TFrame')
        cuerpo.pack(fill='both', expand=True)
        cols = ('variante', 'tablero')
        self.tabla = ttk.Treeview(cuerpo, columns=cols, show='headings', selectmode='browse', height=16)
        for c, txt, ancho in zip(cols, ('Variante', 'Tablero'), (230, 80)):
            self.tabla.heading(c, text=txt)
            self.tabla.column(c, width=ancho, anchor='w')
        for i, v in enumerate(self.variantes):
            self.tabla.insert('', 'end', iid=str(i), values=(v.nombre, '%d × %d' % (v.ancho, v.alto)))
        self.vista = tk.Canvas(cuerpo, width=380, bg=FONDO, highlightthickness=0)
        self.vista.pack(side='right', fill='y', padx=(12, 0))
        self.vista.bind('<Configure>', lambda e: self.previsualizar())
        self.tabla.pack(side='left', fill='both', expand=True)
        self.tabla.bind('<Double-Button-1>', lambda e: self.jugar())
        self.tabla.bind('<<TreeviewSelect>>', lambda e: self.previsualizar())
        lado = ttk.Frame(cuerpo, style='Panel.TFrame', padding=(16, 0, 0, 0), width=300)
        lado.pack(side='left', fill='y')
        lado.pack_propagate(False)
        ttk.Label(lado, text='LA VARIANTE', style='Sub.TLabel').pack(anchor='w')
        self.lbl = ttk.Label(lado, style='Panel.TLabel', wraplength=280, justify='left')
        self.lbl.pack(anchor='w', pady=(2, 8), fill='x')
        ttk.Button(lado, text='Jugar', style='Comenzar.TButton', command=self.jugar).pack(side='bottom', fill='x')
        ttk.Button(lado, text='Abrir en el Laboratorio', command=self.laboratorio).pack(side='bottom', fill='x',
                                                                                         pady=(0, 6))
        ttk.Button(lado, text='Ver reglas', command=self.reglas).pack(side='bottom', fill='x', pady=(0, 6))
        self.tabla.selection_set('0')
        self.tabla.focus('0')

    def variante(self):
        sel = self.tabla.selection()
        return self.variantes[int(sel[0])] if sel else None

    def previsualizar(self):
        v = self.variante()
        if v is None:
            return
        piezas = {}
        for c, r, t, col in v.cfg['posicion']:
            piezas[t] = piezas.get(t, 0) + 1
        nombres = sorted({v.nombre_pieza(t) for t in piezas if not v.cfg['piezas'][t].get('peon')})
        self.lbl.configure(text='%s\n\n%d × %d · %d piezas\nPiezas: %s.' % (
            v.resumen, v.ancho, v.alto, sum(piezas.values()), ', '.join(nombres)))
        dibujar_tablero(self.vista, self.app, v, v.inicial(), texto=v.nombre)

    def jugar(self):
        v = self.variante()
        if v is not None:
            self.top.destroy()
            self.app.jugar(v)

    def reglas(self):
        v = self.variante()
        if v is not None:
            from reglas import VentanaReglas
            VentanaReglas(self.app, v)

    def laboratorio(self):
        import copy
        v = self.variante()
        if v is not None:
            cfg = copy.deepcopy(v.cfg)
            self.top.destroy()
            self.app.laboratorio(cfg)
