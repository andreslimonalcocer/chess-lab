"""Ventana «Simular» del Laboratorio: la computadora juega la variante contra sí misma
(Simulador/simular_variante.py) para ver si está equilibrada o para medir el valor de una pieza
con duelos. Los resultados y las bitácoras quedan en la carpeta 'simulaciones'."""
import json, os, queue, re, shutil, subprocess, sys, threading
import tkinter as tk
from tkinter import ttk, messagebox

from interfaz import FONDO, TEXTO, PROCESO

AQUI = os.path.dirname(os.path.abspath(__file__))
SIMULADOR = os.path.join(os.path.dirname(AQUI), 'Simulador', 'simular_variante.py')
CARPETA = os.path.join(AQUI, 'simulaciones')


from interfaz import buscar_pypy  # noqa: E402  (también lo usan otros módulos desde aquí)


class VentanaSimular:
    def __init__(self, app, cfg):
        self.app, self.cfg = app, cfg
        self.proc, self.cola = None, queue.Queue()
        base = re.sub(r'[^a-z0-9]+', '_', cfg.get('nombre', 'variante').lower()).strip('_') or 'variante'
        os.makedirs(CARPETA, exist_ok=True)
        self.ruta_cfg = os.path.join(CARPETA, base + '.json')
        self.salida = os.path.join(CARPETA, base + '.jsonl')
        self.ruta_bitacora = os.path.join(CARPETA, base + '_bitacora.jsonl')
        top = self.top = tk.Toplevel(app.root)
        top.title('Simular — ' + cfg.get('nombre', 'variante'))
        top.configure(bg=FONDO)
        top.geometry('720x600')
        top.protocol('WM_DELETE_WINDOW', self.cerrar)
        f = ttk.Frame(top, style='Panel.TFrame', padding=14)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Simular «%s»' % cfg.get('nombre', ''), style='Titulo.TLabel').pack(anchor='w')
        ttk.Label(f, style='Panel.TLabel', wraplength=680, justify='left', text=(
            'La computadora juega la variante contra sí misma. El autojuego muestra si un bando tiene ventaja '
            'y cómo terminan las partidas; el duelo da la pieza X a un bando y la Y al otro, en la misma '
            'casilla, para saber cuál vale más.')).pack(anchor='w', pady=(2, 8))
        opciones = ttk.Frame(f, style='Panel.TFrame')
        opciones.pack(fill='x')
        self.modo = tk.StringVar(value='partidas')
        ttk.Radiobutton(opciones, text='Autojuego', value='partidas', variable=self.modo, style='Panel.TRadiobutton',
                        command=self.cambio_modo).grid(row=0, column=0, sticky='w')
        ttk.Radiobutton(opciones, text='Duelo:', value='duelo', variable=self.modo, style='Panel.TRadiobutton',
                        command=self.cambio_modo).grid(row=1, column=0, sticky='w')
        tipos = [t for t, d in sorted(cfg['piezas'].items(), key=lambda kv: kv[1]['nombre'])
                 if not d.get('real')]
        self.nombres = {'%s (%s)' % (cfg['piezas'][t]['nombre'], t): t for t in tipos}
        valores = list(self.nombres)
        self.cmb_x = ttk.Combobox(opciones, values=valores, width=22)
        self.cmb_y = ttk.Combobox(opciones, values=valores, width=22)
        if valores:
            self.cmb_x.set(valores[0])
            self.cmb_y.set(valores[min(1, len(valores) - 1)])
        self.cmb_x.grid(row=1, column=1, sticky='w', padx=(4, 4))
        ttk.Label(opciones, text='contra', style='Panel.TLabel').grid(row=1, column=2)
        self.cmb_y.grid(row=1, column=3, sticky='w', padx=(4, 0))
        ttk.Label(opciones, text='(puedes sumar piezas con «+», p. ej. R+P)', style='Panel.TLabel').grid(
            row=2, column=1, columnspan=3, sticky='w', padx=(4, 0))
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(10, 0))
        self.partidas = tk.IntVar(value=20)
        self.prof = tk.IntVar(value=2)
        self.procesos = tk.IntVar(value=max(1, (os.cpu_count() or 2) // 2))
        for txt, var, desde, hasta in (('Partidas', self.partidas, 2, 2000), ('Profundidad', self.prof, 1, 6),
                                       ('Procesos', self.procesos, 1, os.cpu_count() or 1)):
            ttk.Label(fila, text=txt, style='Panel.TLabel').pack(side='left')
            ttk.Spinbox(fila, from_=desde, to=hasta, textvariable=var, width=6).pack(side='left', padx=(4, 16))
        self.btn = ttk.Button(fila, text='Iniciar', style='Comenzar.TButton', command=self.iniciar)
        self.btn.pack(side='right')
        self.barra = ttk.Progressbar(f)
        self.barra.pack(fill='x', pady=(10, 4))
        marco = ttk.Frame(f, style='Panel.TFrame')
        marco.pack(fill='both', expand=True)
        self.txt = tk.Text(marco, bg='#1E1B18', fg=TEXTO, font=('DejaVu Sans Mono', 9), relief='flat', wrap='word')
        barra = ttk.Scrollbar(marco, command=self.txt.yview)
        self.txt.configure(yscrollcommand=barra.set)
        barra.pack(side='right', fill='y')
        self.txt.pack(side='left', fill='both', expand=True)
        abajo = ttk.Frame(f, style='Panel.TFrame')
        abajo.pack(fill='x', pady=(8, 0))
        self.btn_ver = ttk.Button(abajo, text='Ver partidas…', command=self.ver_partidas)
        self.btn_ver.pack(side='left')
        ttk.Label(abajo, text='Resultados en ' + os.path.relpath(self.salida, AQUI), style='Panel.TLabel').pack(
            side='left', padx=8)
        ttk.Button(abajo, text='Cerrar', command=self.cerrar).pack(side='right')
        if not buscar_pypy():
            self.escribir('Aviso: PyPy no está instalado; la simulación será varias veces más lenta.\n')
        self.cambio_modo()

    def cambio_modo(self):
        estado = ['!disabled'] if self.modo.get() == 'duelo' else ['disabled']
        self.cmb_x.state(estado)
        self.cmb_y.state(estado)

    def escribir(self, texto):
        self.txt.insert('end', texto)
        self.txt.see('end')

    def _grupo(self, cmb):
        texto = cmb.get().strip()
        return '+'.join(self.nombres.get(p.strip(), p.strip()) for p in texto.split('+'))

    def iniciar(self):
        if self.proc is not None:  # detener
            self.proc.kill()
            return
        try:
            n, prof, procesos = self.partidas.get(), self.prof.get(), self.procesos.get()
        except tk.TclError:
            messagebox.showerror('Simular', 'Revisa los números.', parent=self.top)
            return
        with open(self.ruta_cfg, 'w', encoding='utf-8') as fh:
            json.dump(self.cfg, fh, ensure_ascii=False)
        cmd = [buscar_pypy() or sys.executable, '-u', SIMULADOR, self.modo.get(), self.ruta_cfg]
        if self.modo.get() == 'duelo':
            x, y = self._grupo(self.cmb_x), self._grupo(self.cmb_y)
            if not x or not y:
                messagebox.showerror('Simular', 'Elige las dos piezas del duelo.', parent=self.top)
                return
            cmd += [x, y]
        cmd += ['--partidas', str(n), '--profundidad', str(prof), '--procesos', str(procesos),
                '--salida', self.salida, '--bitacora', self.ruta_bitacora]
        self.barra.configure(maximum=n if self.modo.get() == 'partidas' else 2 * max(1, (n + 1) // 2), value=0)
        self.txt.delete('1.0', 'end')
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                                         **PROCESO)
        except OSError as e:
            messagebox.showerror('Simular', 'No se pudo iniciar el simulador:\n%s' % e, parent=self.top)
            return
        self.btn.configure(text='Detener')
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
        terminado = False
        try:
            while True:
                linea = self.cola.get_nowait()
                if linea is None:
                    terminado = True
                    break
                m = re.match(r'\[(\d+)/(\d+)\]', linea)
                if m:
                    self.barra.configure(value=int(m.group(1)), maximum=int(m.group(2)))
                self.escribir(linea)
        except queue.Empty:
            pass
        if terminado:
            codigo = self.proc.returncode
            self.proc = None
            self.btn.configure(text='Iniciar')
            if codigo not in (0, None):
                self.escribir('\nSimulación detenida.\n')
            return
        self.top.after(150, self.sondear)

    def ver_partidas(self):
        if not os.path.exists(self.ruta_bitacora):
            messagebox.showinfo('Simular', 'Todavía no hay partidas simuladas de esta variante.', parent=self.top)
            return
        self.cerrar()
        self.app.abrir_bitacora(self.ruta_bitacora)

    def cerrar(self):
        if self.proc is not None:
            if not messagebox.askyesno('Simular', 'La simulación sigue corriendo. ¿Detenerla?', parent=self.top):
                return
            self.proc.kill()
            self.proc = None
        self.top.destroy()
