"""Análisis de una partida con la computadora: evaluación de cada posición, jugadas dudosas y
errores, y la mejor jugada en cada caso.

Para cada posición k se pide a la computadora la mejor jugada y su evaluación E[k] (desde el bando
que mueve). La jugada que se hizo en k vale -E[k+1] (la evaluación de la posición siguiente, vista
desde el otro bando), así que su pérdida es E[k] + E[k+1]: cuánto peor fue que la mejor.
"""
import tkinter as tk
from tkinter import ttk

from interfaz import FONDO, BORDE, ORO, TEXTO, TEXTO_SUAVE

TOPE = 30.0  # las evaluaciones de mate se recortan a ±30 peones para calcular pérdidas
# (pérdida mínima en peones, símbolo, nombre)
CLASES = [(3.0, '??', 'error grave'), (1.5, '?', 'error'), (0.7, '?!', 'imprecisión')]
PROFUNDIDADES = [('Rápido (profundidad 2)', 2, 0), ('Normal (profundidad 3)', 3, 0), ('Profundo (profundidad 4)', 4, 15)]


def recortar(e):
    return max(-TOPE, min(TOPE, e))


class Analizador:
    """Pide a la computadora (proceso ia.py) la evaluación de cada posición de una partida."""

    def __init__(self, juego, prof, tiempo, al_avanzar=None, al_terminar=None):
        self.j, self.prof, self.tiempo = juego, prof, tiempo
        self.al_avanzar, self.al_terminar = al_avanzar, al_terminar
        e = juego.repro_todo
        self.estados, self.hist, self.notas = e['estados'], e['hist'], e['notas']
        self.n = len(self.notas)
        self.res = [None] * (self.n + 1)   # por posición: {'idx', 'nota', 'eval'} (desde el que mueve)
        self.info = [None] * self.n        # por jugada: {'perdida', 'clase', 'simbolo', 'mejor'}
        self.k, self.id, self.terminado, self.cancelado = 0, None, False, False
        self._movs = None
        self.avanzar()

    def avanzar(self):
        v = self.j.v
        while self.k <= self.n:
            st = self.estados[self.k]
            movs = v.legal(st)
            if not movs:  # posición final: mate o ahogado, sin preguntar a la computadora
                self.res[self.k] = {'idx': None, 'nota': '', 'eval': -TOPE if v.en_jaque(st, st.turn) else 0.0}
                self.k += 1
                continue
            self._movs = movs
            self.id = self.j.ia.pedir(v.spec, self.j.inicio, self.hist[:self.k], self.prof, self.tiempo, 0.0)
            return
        self.terminar()

    def recibir(self, r):
        if self.cancelado or r.get('id') != self.id:
            return
        st, movs = self.estados[self.k], self._movs
        idx = r['idx']
        mv, n = movs[idx]
        ev = r.get('eval')
        self.res[self.k] = {'idx': idx, 'nota': self.j.v.notacion(st, mv, n, movs),
                            'eval': recortar(ev if ev is not None else 0.0)}
        self.k += 1
        if self.al_avanzar:
            self.al_avanzar(self.k, self.n + 1)
        self.avanzar()

    def terminar(self):
        for i in range(self.n):
            mejor, siguiente = self.res[i], self.res[i + 1]
            jugada = self.hist[i]
            perdida = 0.0 if jugada == mejor['idx'] else max(0.0, mejor['eval'] + siguiente['eval'])
            clase = next(((s, nombre) for minimo, s, nombre in CLASES if perdida >= minimo), ('', ''))
            self.info[i] = {'perdida': perdida, 'simbolo': clase[0], 'clase': clase[1],
                            'mejor': mejor['nota'] if jugada != mejor['idx'] else ''}
        self.terminado = True
        if self.al_terminar:
            self.al_terminar()

    def cancelar(self):
        if not self.terminado:
            self.cancelado = True
            self.j.ia.cancelar()

    def eval_blancas(self, k):
        """Evaluación de la posición k a favor de las blancas (None si aún no se calcula)."""
        r = self.res[k]
        if r is None:
            return None
        return r['eval'] if self.estados[k].turn == 0 else -r['eval']

    def resumen(self, color):
        """{clase: cantidad} y pérdida media de las jugadas de un bando."""
        jugadas = [self.info[i] for i in range(self.n) if self.estados[i].turn == color]
        cuenta = {nombre: sum(1 for x in jugadas if x['clase'] == nombre) for _, _, nombre in CLASES}
        media = sum(x['perdida'] for x in jugadas) / len(jugadas) if jugadas else 0.0
        return cuenta, media


MINIMO_ERROR = 1.5  # errores (?) y errores graves (??) de tus partidas se convierten en problemas


def errores_como_problemas(juego, an):
    """Tus errores (pérdida de 1.5 peones o más) de una partida tuya contra la computadora, como problemas:
    la posición antes del error, la jugada que hiciste y la mejor según el análisis."""
    import hashlib, json
    r = juego.repro_reg or {}
    if r.get('origen') != 'partida' or r.get('dos_jugadores') or an.prof < 3:
        return []
    color = {'blancas': 0, 'negras': 1}.get(r.get('humano'))
    if color is None:
        return []
    v, out = juego.v, []
    for i, x in enumerate(an.info):
        mejor = an.res[i]
        if (an.estados[i].turn != color or x is None or x['perdida'] < MINIMO_ERROR or mejor is None
                or mejor['idx'] is None or abs(mejor['eval']) >= TOPE):
            continue
        clave = json.dumps([v.spec, juego.inicio, an.hist[:i]], sort_keys=True)
        out.append({'id': 'mio:' + hashlib.sha1(clave.encode()).hexdigest()[:12], 'tipo': 'tactico',
                    'personal': True, 'tema': 'tu error', 'variante': v.spec, 'variante_nombre': v.nombre,
                    'inicio': juego.inicio, 'hist': an.hist[:i], 'turno': color, 'solucion': mejor['nota'],
                    'solucion_idx': mejor['idx'], 'mejor_eval': mejor['eval'], 'gana': round(x['perdida'], 1),
                    'margen': 0, 'jugaste': an.notas[i], 'prof': an.prof,
                    'origen': 'Tu partida del %s, jugada %d' % ((r.get('fecha') or '')[:10], i // 2 + 1)})
    return out


def guardar_errores(juego, an):
    import partidas as PG
    try:
        return PG.agregar_mis_problemas(errores_como_problemas(juego, an))
    except (OSError, ValueError):
        return 0


class VentanaAnalisis:
    """Ventana con el progreso, el resumen por bando, la gráfica de evaluación y los errores."""

    def __init__(self, app, juego, prof, tiempo):
        self.app, self.j = app, juego
        top = self.top = tk.Toplevel(app.root)
        top.title('Análisis de la partida')
        top.configure(bg=FONDO)
        top.geometry('640x620')
        top.protocol('WM_DELETE_WINDOW', self.cerrar)
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Análisis de la partida', style='Titulo.TLabel').pack(anchor='w')
        self.lbl = ttk.Label(f, style='Panel.TLabel', text='Analizando…')
        self.lbl.pack(anchor='w', pady=(4, 2))
        self.barra = ttk.Progressbar(f, maximum=juego.repro_todo and len(juego.repro_todo['estados']) or 1)
        self.barra.pack(fill='x', pady=(0, 8))
        self.lbl_resumen = ttk.Label(f, style='Panel.TLabel', justify='left')
        self.lbl_resumen.pack(anchor='w')
        ttk.Label(f, text='EVALUACIÓN (arriba: ventaja de las blancas · clic para ir a esa jugada)',
                  style='Sub.TLabel').pack(anchor='w', pady=(10, 2))
        self.cv = tk.Canvas(f, height=170, bg='#1E1B18', highlightthickness=0, cursor='hand2')
        self.cv.pack(fill='x')
        self.cv.bind('<Button-1>', self.clic_grafica)
        self.cv.bind('<Configure>', lambda e: self.dibujar())
        ttk.Label(f, text='JUGADAS DUDOSAS Y ERRORES (clic para verlas en el tablero)',
                  style='Sub.TLabel').pack(anchor='w', pady=(10, 2))
        marco = ttk.Frame(f, style='Panel.TFrame')
        marco.pack(fill='both', expand=True)
        self.lista = tk.Listbox(marco, bg='#1E1B18', fg=TEXTO, font=('DejaVu Sans Mono', 10), relief='flat',
                                selectbackground='#4A3E33', activestyle='none')
        barra = ttk.Scrollbar(marco, command=self.lista.yview)
        self.lista.configure(yscrollcommand=barra.set)
        barra.pack(side='right', fill='y')
        self.lista.pack(side='left', fill='both', expand=True)
        self.lista.bind('<<ListboxSelect>>', self.clic_lista)
        self.errores = []
        self.an = Analizador(juego, prof, tiempo, self.avance, self.listo)
        juego.analizador = self.an

    def avance(self, k, total):
        self.barra.configure(value=k)
        self.lbl.configure(text='Analizando: posición %d de %d…' % (k, total))
        self.dibujar()

    def listo(self):
        an = self.an
        self.barra.configure(value=self.barra['maximum'])
        self.lbl.configure(text='Análisis terminado (%d jugadas).' % an.n)
        lineas = []
        for color, nombre in ((0, 'Blancas'), (1, 'Negras')):
            cuenta, media = an.resumen(color)
            lineas.append('%s: %d errores graves, %d errores, %d imprecisiones · pérdida media %.2f por jugada'
                          % (nombre, cuenta['error grave'], cuenta['error'], cuenta['imprecisión'], media))
        self.lbl_resumen.configure(text='\n'.join(lineas))
        self.errores = []
        self.lista.delete(0, 'end')
        for i, x in enumerate(an.info):
            if x['simbolo']:
                numero = '%d.%s' % (i // 2 + 1, '' if an.estados[i].turn == 0 else '..')
                self.lista.insert('end', '%-6s %-16s %-3s pierde %4.1f · mejor: %s' % (
                    numero, an.notas[i], x['simbolo'], x['perdida'], x['mejor']))
                self.errores.append(i)
        if not self.errores:
            self.lista.insert('end', 'Ninguna jugada dudosa: ¡partida muy precisa!')
        n = guardar_errores(self.j, an)
        if n:
            self.lbl.configure(text='Análisis terminado (%d jugadas). %d de tus errores se agregaron a Problemas › '
                                    '«Mis errores» para que los practiques.' % (an.n, n))
        self.dibujar()
        self.j.actualizar_panel()

    def dibujar(self):
        cv, an = self.cv, self.an
        cv.delete('all')
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 20 or an.n == 0:
            return
        tope = 8.0
        y = lambda e: h / 2 - (max(-tope, min(tope, e)) / tope) * (h / 2 - 8)
        x = lambda k: 8 + (w - 16) * k / max(1, an.n)
        cv.create_line(0, h / 2, w, h / 2, fill=BORDE)
        puntos = [(x(k), y(an.eval_blancas(k))) for k in range(an.n + 1) if an.res[k] is not None]
        if len(puntos) > 1:
            cv.create_polygon([(puntos[0][0], h / 2)] + puntos + [(puntos[-1][0], h / 2)], fill='#3A332C', outline='')
            cv.create_line(puntos, fill=ORO, width=2)
        if an.terminado:
            colores = {'??': '#E05050', '?': '#E09040', '?!': '#D8C060'}
            for i, info in enumerate(an.info):
                if info['simbolo']:
                    px, py = x(i + 1), y(an.eval_blancas(i + 1))
                    cv.create_oval(px - 4, py - 4, px + 4, py + 4, fill=colores[info['simbolo']], outline='')
        k = self.j.repro_pos
        cv.create_line(x(k), 0, x(k), h, fill=TEXTO_SUAVE, dash=(2, 3))

    def clic_grafica(self, ev):
        w = self.cv.winfo_width()
        k = round((ev.x - 8) / max(1, w - 16) * self.an.n)
        self.ir(max(0, min(self.an.n, k)))

    def clic_lista(self, ev):
        sel = self.lista.curselection()
        if sel and sel[0] < len(self.errores):
            self.ir(self.errores[sel[0]] + 1)  # la posición tras la jugada dudosa

    def ir(self, k):
        self.j.pausado = True
        self.j.ir_a_jugada(k)
        self.dibujar()

    def cerrar(self):
        self.an.cancelar()
        self.top.destroy()
