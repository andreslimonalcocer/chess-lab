#!/usr/bin/env python3
"""Ajedrez: juego de escritorio contra la computadora.

Empieza en un menú principal con cuatro variantes (clásico, Ajedrez Extendido, Capablanca y
gótico) y el Laboratorio, donde se diseñan variantes propias. Las reglas del Ajedrez Extendido vienen
de Simulador/motor.py; las demás, de generico.py. La computadora corre en un proceso aparte
(ia.py), con PyPy si está instalado.
"""
import argparse, json, math, os, queue, random, shutil, subprocess, sys, threading, time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

AQUI = os.path.dirname(os.path.abspath(__file__))
import idioma
idioma.instalar()  # antes de crear cualquier ventana: traduce lo que llega a la pantalla
import variantes as V
import bitacora as BIT
import partidas as PG
import ajustes as AJ
from generico import LETRAS
from interfaz import (activar_escala, px, PROCESO,
                      FONDO, FONDO_OSCURO, TARJETA, BORDE, ORO, TEXTO, TEXTO_SUAVE, MARCA, MARCA_CADENA, base_clara,
                      Imagenes, colores_tema, configurar, mezcla)
from sonidos import Sonidos

COLORES = V.COLORES
# (nombre, minutos, incremento en segundos)
RELOJES = [('Sin reloj', None, 0), ('3 min + 2 s', 3, 2), ('5 min + 3 s', 5, 3), ('10 min + 5 s', 10, 5),
           ('15 min + 10 s', 15, 10), ('30 min', 30, 0), ('60 min + 30 s', 60, 30)]
ANIMACION = 0.18  # segundos que tarda una pieza en deslizarse
SALTO_CADENA = 0.45  # segundos por salto en la animación de una cadena de la Catapulta
MATE = 100000  # como en busqueda.py y generico.py
ESPECTADOR = ('espectador', 'reproduccion')  # modos en que juegan dos computadoras (o una bitácora)
BITACORAS = os.path.join(AQUI, 'bitacoras')
# (nombre, profundidad máxima, segundos máximos por jugada (0 = sin límite), temperatura)
NIVELES = [('Principiante', 1, 0, 0.0), ('Fácil', 2, 0, 0.0), ('Normal', 3, 8, 0.0), ('Difícil', 4, 20, 0.0),
           ('Experto', 5, 60, 0.0)]


def niveles_elo():
    """Niveles calibrados en Elo (niveles_elo.json, de Simulador/calibrar_elo.py), o None."""
    try:
        with open(os.path.join(AQUI, 'niveles_elo.json'), encoding='utf-8') as f:
            datos = json.load(f)['niveles']
    except (OSError, ValueError, KeyError):
        return None
    if not datos:
        return None
    return [('%d Elo' % n['elo'], n['profundidad'], n.get('tiempo') or 0, n.get('temperatura', 0.0), n['elo'])
            for n in sorted(datos, key=lambda n: n['elo'])]


def niveles_para(variante):
    """(niveles, con Elo). La calibración se hizo con la computadora del Ajedrez Extendido: solo ahí valen los Elo."""
    elo = niveles_elo() if variante.id == 'extendido' else None
    if elo:
        return elo, True
    return [n + (None,) for n in NIVELES], False


from interfaz import buscar_pypy  # noqa: E402  (también lo usan otros módulos desde aquí)


class ClienteIA:
    """Comunicación con el proceso ia.py."""

    def __init__(self):
        self.exe = buscar_pypy() or sys.executable
        self.proc = None
        self.respuestas = queue.Queue()
        self.ultimo_id = 0

    @property
    def es_pypy(self):
        return 'pypy' in os.path.basename(self.exe)

    def _iniciar(self):
        try:
            self.proc = subprocess.Popen([self.exe, os.path.join(AQUI, 'ia.py')], stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, text=True, bufsize=1, **PROCESO)
        except OSError:
            if self.exe == sys.executable:
                raise
            self.exe = sys.executable
            return self._iniciar()
        threading.Thread(target=self._leer, args=(self.proc,), daemon=True).start()

    def _leer(self, proc):
        for linea in proc.stdout:
            try:
                self.respuestas.put(json.loads(linea))
            except ValueError:
                pass

    def pedir(self, variante, inicio, hist, prof, tiempo, temperatura=0.0, **extra):
        if self.proc is None or self.proc.poll() is not None:
            self._iniciar()
        self.ultimo_id += 1
        req = dict(id=self.ultimo_id, variante=variante, inicio=inicio, hist=hist, prof=prof, tiempo=tiempo,
                   temperatura=temperatura, **extra)
        self.proc.stdin.write(json.dumps(req) + '\n')
        self.proc.stdin.flush()
        return self.ultimo_id

    def vivo(self):
        return self.proc is not None and self.proc.poll() is None

    def cancelar(self):
        if self.vivo():
            self.proc.kill()
            self.proc.wait()
        self.proc = None
        self.ultimo_id += 1

    def respuesta(self):
        try:
            return self.respuestas.get_nowait()
        except queue.Empty:
            return None


# ====================================================================== aplicación
class Aplicacion:
    """Ventana principal: cambia entre el menú, una partida y el laboratorio."""

    def __init__(self, root):
        self.root = root
        root.title('Ajedrez')
        root.configure(bg=FONDO)
        try:
            self.icono = tk.PhotoImage(file=V.ruta_imagen('rey', 0))
            root.iconphoto(True, self.icono)
        except tk.TclError:
            pass
        self.ajustes = AJ.cargar()
        idioma.establecer(self.ajustes['idioma'])
        import disenos
        disenos.ESTILO.update(self.ajustes.get('piezas') or {})
        activar_escala(self.ajustes['escala'] / 100)
        self.letra, self.serif = configurar(root)
        self.img = Imagenes()
        self.ia = ClienteIA()
        self.sonidos = Sonidos()
        self.sonidos.activo, self.sonidos.volumen = self.ajustes['sonido'], self.ajustes['volumen']
        self.barra_eval = self.ajustes['barra_eval']
        self.pantalla = None
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        alto = max(600, min(sh - 100, 1000))
        root.geometry('%dx%d' % (min(sw - 60, int(alto * 1.42)), alto))
        root.minsize(900, 600)
        root.protocol('WM_DELETE_WINDOW', self.salir)
        for tecla, metodo in (('<Control-z>', 'deshacer'), ('<Control-n>', 'dialogo_nueva'),
                              ('<Control-e>', 'atajo_entrenamiento'), ('<Escape>', 'escape'),
                              ('<Left>', 'tecla_izquierda'), ('<Right>', 'tecla_derecha'),
                              ('<Home>', 'tecla_inicio'), ('<End>', 'tecla_fin')):
            root.bind(tecla, lambda e, m=metodo: getattr(self.pantalla, m, lambda: None)())
        root.bind_all('<F1>', lambda e: self.ayuda())
        # descripciones al pasar el ratón: en cada ventana nueva, al mostrarse
        from manual import poner_tooltips
        root.bind_class('Toplevel', '<Map>', lambda e: poner_tooltips(e.widget), add='+')
        root.after(100, self.sondear)
        self.menu()

    def _cambiar(self, crear):
        self.ia.cancelar()
        if self.pantalla is not None:
            self.pantalla.frame.destroy()
        self.pantalla = crear()
        self.pantalla.frame.pack(fill='both', expand=True)
        from manual import poner_tooltips
        poner_tooltips(self.pantalla.frame)

    def menu(self):
        self.root.title('Ajedrez')
        self._cambiar(lambda: MenuPrincipal(self))

    def jugar(self, variante, volver=None):
        self.root.title('Ajedrez — ' + variante.nombre)
        self._cambiar(lambda: Juego(self, variante, volver))
        self.root.after(250, self.pantalla.dialogo_nueva)

    def abrir_bitacora(self, ruta=None, numero=None):
        """Elige un archivo de bitácora (y una partida, si tiene varias) y la reproduce."""
        if ruta is None:
            ruta = filedialog.askopenfilename(
                parent=self.root, title='Abrir bitácora', initialdir=BITACORAS if os.path.isdir(BITACORAS) else AQUI,
                filetypes=[('Bitácoras', '*.jsonl *.json'), ('Todos los archivos', '*')])
            if not ruta:
                return
        try:
            partidas = BIT.leer(ruta)
        except (OSError, ValueError) as e:
            messagebox.showerror('Bitácora', 'No se pudo leer la bitácora:\n%s' % e, parent=self.root)
            return
        if not partidas:
            messagebox.showinfo('Bitácora', 'El archivo no tiene partidas.', parent=self.root)
            return
        if numero is not None:
            if not 1 <= numero <= len(partidas):
                messagebox.showerror('Bitácora', 'El archivo tiene %d partidas.' % len(partidas), parent=self.root)
                return
            self.reproducir(partidas[numero - 1], ruta, numero)
        elif len(partidas) == 1:
            self.reproducir(partidas[0], ruta, 1)
        else:
            self._elegir_partida(partidas, ruta)

    def _elegir_partida(self, partidas, ruta):
        d = tk.Toplevel(self.root)
        d.title('Elegir partida — ' + os.path.basename(ruta))
        d.transient(self.root)
        f = ttk.Frame(d, padding=12)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='La bitácora tiene %d partidas. Elige una:' % len(partidas)).pack(anchor='w', pady=(0, 6))
        lista = tk.Listbox(f, width=60, height=min(20, len(partidas)), font=('DejaVu Sans Mono', 10))
        barra = ttk.Scrollbar(f, command=lista.yview)
        lista.configure(yscrollcommand=barra.set)
        for i, p in enumerate(partidas, 1):
            lista.insert('end', '%4d. %s' % (i, BIT.resumen(p)))
        lista.selection_set(0)
        barra.pack(side='right', fill='y')
        lista.pack(side='left', fill='both', expand=True)

        def abrir(ev=None):
            sel = lista.curselection()
            if sel:
                d.destroy()
                self.reproducir(partidas[sel[0]], ruta, sel[0] + 1)
        lista.bind('<Double-Button-1>', abrir)
        d.bind('<Return>', abrir)
        ttk.Button(d, text='Reproducir', command=abrir).pack(pady=(0, 10))
        d.wait_visibility()
        d.grab_set()

    def reanudar(self, ruta, registro):
        """Continúa una partida guardada."""
        try:
            variante = V.crear(registro.get('variante') or {'tipo': 'extendido'})
        except Exception as e:
            messagebox.showerror('Partida', 'No se pudo crear la variante de la partida:\n%s' % e, parent=self.root)
            return
        self.root.title('Ajedrez — ' + variante.nombre)
        self._cambiar(lambda: Juego(self, variante))
        self.pantalla.reanudar(registro, ruta)

    def partidas_guardadas(self):
        from ventanas import PartidasGuardadas
        PartidasGuardadas(self)

    def perfil(self):
        from ventanas import Perfil
        elo = niveles_elo()
        Perfil(self, {'extendido': elo} if elo else {})

    def reproducir(self, registro, ruta, numero=1, analizar=False):
        try:
            variante = V.crear(registro.get('variante') or {'tipo': 'extendido'})
        except Exception as e:  # una variante del laboratorio que ya no es válida
            messagebox.showerror('Bitácora', 'No se pudo crear la variante de la bitácora:\n%s' % e, parent=self.root)
            return
        self.root.title('Ajedrez — %s — reproducción' % variante.nombre)
        self._cambiar(lambda: Juego(self, variante))
        self.pantalla.iniciar_reproduccion(registro, ruta, numero, analizar)

    def tema(self, variante):
        """Tema del tablero: el de los ajustes, o el propio de la variante."""
        return self.ajustes['tema'] or variante.tema

    def ayuda(self, seccion=None):
        """El manual (F1), en la sección de la pantalla actual."""
        from manual import VentanaManual, SECCION_DE_MODO
        if seccion is None:
            p = self.pantalla
            if isinstance(p, Juego):
                seccion = SECCION_DE_MODO.get(p.modo)
            elif type(p).__name__ == 'Laboratorio':
                seccion = 'Laboratorio'
        VentanaManual(self, seccion)

    def ventana_ajustes(self):
        AJ.VentanaAjustes(self)

    def aplicar_ajustes(self, nuevos):
        cambio_escala = nuevos['escala'] != self.ajustes['escala']
        cambio_idioma = nuevos['idioma'] != self.ajustes['idioma']
        self.ajustes = nuevos
        import disenos
        disenos.ESTILO.clear()
        disenos.ESTILO.update(nuevos.get('piezas') or {})
        if cambio_idioma:
            idioma.establecer(nuevos['idioma'])
        AJ.guardar(nuevos)
        self.sonidos.activo, self.sonidos.volumen = nuevos['sonido'], nuevos['volumen']
        self.barra_eval = nuevos['barra_eval']
        if cambio_escala:  # Tk conserva el tamaño de las letras ya creadas: se aplica al volver a abrir
            messagebox.showinfo('Ajustes', 'El nuevo tamaño de la interfaz se aplicará la próxima vez que abras '
                                'el juego.', parent=self.root)
        p = self.pantalla
        if cambio_idioma and not isinstance(p, MenuPrincipal):
            messagebox.showinfo('Ajustes', 'El nuevo idioma se aplica a las pantallas y ventanas que abras a partir '
                                'de ahora (esta pantalla cambia al volver al menú).', parent=self.root)
        if isinstance(p, MenuPrincipal):
            self.menu()
        elif isinstance(p, Juego):
            p.colores = colores_tema(self.tema(p.v))
            p.var_sonido.set(nuevos['sonido'])
            if p.modo in ('partida', 'entrenamiento'):  # botones y avisos de las ayudas
                p.mostrar_panel()
                p.calcular_avisos()
                p.actualizar_estado()
            p.dibujar()

    def problemas(self, variante=None):
        from ventanas import Problemas
        Problemas(self, variante)

    def _pantalla_de(self, spec):
        """La pantalla de juego actual si es de esa variante (para no salir de ella), o una nueva."""
        p = self.pantalla
        if isinstance(p, Juego) and p.v.spec == spec:
            return p
        variante = V.crear(spec)
        self.root.title('Ajedrez — ' + variante.nombre)
        self._cambiar(lambda: Juego(self, variante))
        return self.pantalla

    def resolver(self, problema, lista=None):
        """Abre un problema de mate en su variante (en la pantalla actual si es la misma variante)."""
        try:
            juego = self._pantalla_de(problema['variante'])
        except Exception as e:
            messagebox.showerror('Problemas', 'No se pudo crear la variante del problema:\n%s' % e, parent=self.root)
            return
        juego.iniciar_problema(problema, lista or [problema])

    def aperturas(self, hist=None):
        from ventanas import Aperturas
        Aperturas(self, hist)

    def lecciones(self):
        from ventanas import Lecciones
        Lecciones(self)

    def leccion(self, i, k=0):
        """Abre el ejercicio k de la lección i de «Aprende a jugar» (en el tablero del Ajedrez Extendido)."""
        self._pantalla_de(V.Extendido.spec).iniciar_leccion(i, k)

    def finales(self, variante=None):
        from ventanas import Finales
        Finales(self, variante)

    def iniciar_final(self, cfg):
        """Práctica o demostración de un final de Rey y piezas contra Rey (con las tablas exactas)."""
        self._pantalla_de(cfg.get('variante') or V.Extendido.spec).iniciar_final(cfg)

    def importar_partida(self):
        from ventanas import ImportarPartida
        ImportarPartida(self)

    def laboratorio(self, cfg=None):
        from laboratorio import Laboratorio
        self.root.title('Ajedrez — Laboratorio')
        self._cambiar(lambda: Laboratorio(self, cfg))

    def sondear(self):
        f = getattr(self.pantalla, 'sondear', None)
        if f:
            f()
        self.root.after(100, self.sondear)

    def salir(self):
        self.ia.cancelar()
        self.root.destroy()


# ====================================================================== menú principal
class MenuPrincipal:
    def __init__(self, app):
        self.app = app
        self.frame = tk.Frame(app.root, bg=FONDO_OSCURO)
        self.cv = tk.Canvas(self.frame, bg=FONDO_OSCURO, highlightthickness=0)
        self.cv.pack(fill='both', expand=True)
        self.variantes = V.predefinidas()
        self.en_10x10 = {}  # versiones de 10 × 10 (Capablanca, gótico), creadas al elegirlas
        self.cv.bind('<Configure>', lambda e: self._programar())
        self._pendiente = None

    def variante_de_tarjeta(self, v):
        """La variante que juega una tarjeta: la de 10 × 10 si así se eligió (Capablanca, gótico)."""
        if v.id in V.EN_10X10 and v.id in (self.app.ajustes.get('tablero10') or []):
            if v.id not in self.en_10x10:
                self.en_10x10[v.id] = V.predefinida(V.EN_10X10[v.id])
            return self.en_10x10[v.id]
        return v

    def cambiar_tablero(self, base, diez):
        aj = dict(self.app.ajustes)
        lista = [x for x in (aj.get('tablero10') or []) if x != base]
        if diez:
            lista.append(base)
        aj['tablero10'] = lista
        self.app.ajustes = aj
        AJ.guardar(aj)
        self.dibujar()

    def _programar(self):
        if self._pendiente:
            self.app.root.after_cancel(self._pendiente)
        self._pendiente = self.app.root.after(50, self.dibujar)

    def dibujar(self):
        self._pendiente = None
        cv, a = self.cv, self.app
        if not cv.winfo_exists():  # el menú ya se cerró (se pasó a otra pantalla antes de dibujarlo)
            return
        cv.delete('all')
        W, H = cv.winfo_width(), cv.winfo_height()
        # fondo: degradado y un tablero tenue
        for i in range(40):
            y0 = H * i / 40
            cv.create_rectangle(0, y0, W, y0 + H / 40 + 1, outline='',
                                fill=mezcla('#16120F', '#2E241D', i / 39))
        lado = 70
        for c in range(W // lado + 1):
            for r in range(H // lado + 1):
                if (c + r) % 2:
                    cv.create_rectangle(c * lado, r * lado, (c + 1) * lado, (r + 1) * lado, outline='',
                                        fill='#3A2E25', stipple='gray12')
        # medidas: título, cuatro tarjetas y la del laboratorio, centrados en vertical
        margen, hueco, alto_lab = 40, 22, 120
        ancho = min(290, (W - 2 * margen - 3 * hueco) / 4)
        alto = min(ancho - 36 + px(150), H - 330)
        bloque = px(120) + alto + hueco + alto_lab
        cy = max(50, (H - 40 - bloque) / 2 + 20)
        # título
        cv.create_text(W / 2 + 2, cy + 3, text='AJEDREZ', font=(a.serif, 50, 'bold'), fill='#0E0B09')
        cv.create_text(W / 2, cy, text='AJEDREZ', font=(a.serif, 50, 'bold'), fill=ORO)
        cv.create_line(W / 2 - 230, cy + px(42), W / 2 - 40, cy + px(42), fill=BORDE, width=2)
        cv.create_line(W / 2 + 40, cy + px(42), W / 2 + 230, cy + px(42), fill=BORDE, width=2)
        cv.create_text(W / 2, cy + px(42), text='♔', font=(a.serif, 20), fill=ORO)
        cv.create_text(W / 2, cy + px(74), text='Elige la variante que quieres jugar',
                       font=(a.letra, 13), fill=TEXTO_SUAVE)
        # tarjetas de las variantes
        x0 = (W - (4 * ancho + 3 * hueco)) / 2
        y0 = cy + px(110)
        for i, v in enumerate(self.variantes):
            self._tarjeta(i, self.variante_de_tarjeta(v), x0 + i * (ancho + hueco), y0, ancho, alto, base=v)
        total = 4 * ancho + 3 * hueco
        ancho_lab = int((total - hueco) * 0.64)
        self._tarjeta_laboratorio(x0, y0 + alto + hueco, ancho_lab, alto_lab)
        self._tarjeta_mas(x0 + ancho_lab + hueco, y0 + alto + hueco, total - ancho_lab - hueco, alto_lab)
        # pie
        b = cv.create_text(W - 30, H - 24, text='Salir', anchor='e', font=(a.letra, 11, 'bold'), fill=TEXTO_SUAVE,
                           tags='salir')
        cv.tag_bind('salir', '<Button-1>', lambda e: a.salir())
        cv.tag_bind('salir', '<Enter>', lambda e: (cv.itemconfigure(b, fill=ORO), cv.configure(cursor='hand2')))
        cv.tag_bind('salir', '<Leave>', lambda e: (cv.itemconfigure(b, fill=TEXTO_SUAVE), cv.configure(cursor='')))
        x = 30
        pendiente = PG.sin_terminar()
        if pendiente:
            r = pendiente[1]
            txt = '▶ Continuar partida (%s, jugada %d)' % (r.get('variante_nombre', '?'), (len(r['jugadas']) + 1) // 2)
            t = cv.create_text(30, 26, text=txt, anchor='w', font=(a.letra, 12, 'bold'), fill=ORO, tags='continuar')
            cv.tag_bind('continuar', '<Button-1>', lambda e: a.reanudar(*pendiente))
            cv.tag_bind('continuar', '<Enter>', lambda e: (cv.itemconfigure(t, fill='#FFFFFF'), cv.configure(cursor='hand2')))
            cv.tag_bind('continuar', '<Leave>', lambda e: (cv.itemconfigure(t, fill=ORO), cv.configure(cursor='')))
        enlaces = [('Aprende a jugar', a.lecciones, ORO), ('Ayuda (F1)', a.ayuda, TEXTO_SUAVE), ('Partidas guardadas', a.partidas_guardadas, TEXTO_SUAVE), ('Mi perfil', a.perfil, TEXTO_SUAVE), ('Importar partida…', a.importar_partida, TEXTO_SUAVE),
                   ('Ajustes', a.ventana_ajustes, TEXTO_SUAVE)]
        tam = 11 if W >= 1250 else 10
        for i, (txt, accion, color) in enumerate(enlaces):
            tag = 'enlace%d' % i
            t = cv.create_text(x, H - 24, text=txt, anchor='w', font=(a.letra, tam, 'bold'), fill=color, tags=tag)
            cv.tag_bind(tag, '<Button-1>', lambda e, f=accion: f())
            cv.tag_bind(tag, '<Enter>', lambda e, t=t: (cv.itemconfigure(t, fill='#FFFFFF'), cv.configure(cursor='hand2')))
            cv.tag_bind(tag, '<Leave>', lambda e, t=t, c=color: (cv.itemconfigure(t, fill=c), cv.configure(cursor='')))
            x = cv.bbox(t)[2] + (28 if tam == 11 else 18)
        t = cv.create_text(W - 100, H - 24, text='Reproducir bitácora…', anchor='e', font=(a.letra, 11, 'bold'),
                           fill=TEXTO_SUAVE, tags='bitacora')
        cv.tag_bind('bitacora', '<Button-1>', lambda e: a.abrir_bitacora())
        cv.tag_bind('bitacora', '<Enter>', lambda e: (cv.itemconfigure(t, fill=ORO), cv.configure(cursor='hand2')))
        cv.tag_bind('bitacora', '<Leave>', lambda e: (cv.itemconfigure(t, fill=TEXTO_SUAVE), cv.configure(cursor='')))

    def _hover(self, tag, borde, fondo):
        cv = self.cv
        cv.tag_bind(tag, '<Enter>', lambda e: (cv.itemconfigure(borde, outline=ORO, width=2),
                                               cv.itemconfigure(fondo, fill='#3A2F27'),
                                               cv.configure(cursor='hand2')))
        cv.tag_bind(tag, '<Leave>', lambda e: (cv.itemconfigure(borde, outline=BORDE, width=1),
                                               cv.itemconfigure(fondo, fill=TARJETA),
                                               cv.configure(cursor='')))

    def _tarjeta(self, i, v, x, y, w, h, base=None):
        cv, a = self.cv, self.app
        tag = 'tarjeta%d' % i
        fondo = cv.create_rectangle(x, y, x + w, y + h, fill=TARJETA, outline='', tags=tag)
        borde = cv.create_rectangle(x, y, x + w, y + h, outline=BORDE, width=1, tags=tag)
        # tablero en miniatura con la posición inicial
        espacio = min(w - 36, h - px(130))
        s = int(espacio / max(v.ancho, v.alto))
        bw, bh = s * v.ancho, s * v.alto
        bx, by = x + (w - bw) / 2, y + 18 + (espacio - bh) / 2
        clara, oscura = colores_tema(a.tema(v))[:2]
        cv.create_rectangle(bx - 3, by - 3, bx + bw + 3, by + bh + 3, fill='#5A4636', outline='', tags=tag)
        st = v.inicial()
        tam = max(8, int(s * 0.92))
        for sq in range(v.ancho * v.alto):
            c, r = sq % v.ancho, v.alto - 1 - sq // v.ancho
            qx, qy = bx + c * s, by + r * s
            cv.create_rectangle(qx, qy, qx + s, qy + s, outline='', tags=tag,
                                fill=clara if (sq % v.ancho + sq // v.ancho) % 2 == 0 else oscura)
            p = v.pieza(st, sq)
            if p:
                cv.create_image(qx + s / 2, qy + s / 2, image=a.img.get(v.imagen(*p), tam), tags=tag)
        ty = y + 18 + espacio + px(16)
        cv.create_text(x + w / 2, ty, text=v.nombre, font=(a.serif, 15, 'bold'), fill='#F3E2BE', tags=tag)
        piezas = sum(1 for sq in range(v.ancho * v.alto) if v.pieza(st, sq))
        cv.create_text(x + w / 2, ty + px(24), text='%d × %d · %d piezas' % (v.ancho, v.alto, piezas),
                       font=(a.letra, 10, 'bold'), fill=ORO, tags=tag)
        cv.create_text(x + w / 2, ty + px(44), text=v.resumen, width=w - 30, anchor='n', justify='center',
                       font=(a.letra, 9), fill=TEXTO_SUAVE, tags=tag)
        self._hover(tag, borde, fondo)
        cv.tag_bind(tag, '<Button-1>', lambda e, v=v: a.jugar(v))
        enlace = 'reglas%d' % i
        t = cv.create_text(x + w - 12, y + h - 12, text='Ver reglas', anchor='se', fill=ORO,
                           font=(a.letra, 9, 'bold', 'underline'), tags=enlace)
        cv.tag_bind(enlace, '<Button-1>', lambda e, v=v: self.reglas(v))
        cv.tag_bind(enlace, '<Enter>', lambda e: (cv.itemconfigure(t, fill='#FFFFFF'), cv.configure(cursor='hand2')))
        cv.tag_bind(enlace, '<Leave>', lambda e: (cv.itemconfigure(t, fill=ORO), cv.configure(cursor='')))
        if base is not None and base.id in V.EN_10X10:  # interruptor de tamaño: 10 × 8 o 10 × 10
            diez = v is not base
            cx = x + 12
            for k, (txt, valor) in enumerate((('%d × %d' % (base.ancho, base.alto), False), ('10 × 10', True))):
                tag_t = 'tam%d_%d' % (i, k)
                activo = valor == diez
                caja = cv.create_rectangle(cx, y + h - 26, cx + 52, y + h - 8, tags=tag_t,
                                           fill=ORO if activo else '#2A231E', outline=ORO if activo else BORDE)
                cv.create_text(cx + 26, y + h - 17, text=txt, tags=tag_t, font=(a.letra, 8, 'bold'),
                               fill='#1E1813' if activo else TEXTO_SUAVE)
                if not activo:
                    cv.tag_bind(tag_t, '<Button-1>', lambda e, b=base.id, d=valor: self.cambiar_tablero(b, d))
                    cv.tag_bind(tag_t, '<Enter>', lambda e, c=caja: (cv.itemconfigure(c, outline=ORO),
                                                                     cv.configure(cursor='hand2')))
                    cv.tag_bind(tag_t, '<Leave>', lambda e, c=caja: (cv.itemconfigure(c, outline=BORDE),
                                                                     cv.configure(cursor='')))
                cx += 58

    def _tarjeta_mas(self, x, y, w, h):
        """Tarjeta de «Más variantes»: Gran Ajedrez, Jano, Embajada, Shatranj, Makruk..."""
        cv, a = self.cv, self.app
        tag = 'mas_variantes'
        fondo = cv.create_rectangle(x, y, x + w, y + h, fill=TARJETA, outline='', tags=tag)
        borde = cv.create_rectangle(x, y, x + w, y + h, outline=BORDE, width=1, tags=tag)
        tam = int(h * 0.5)
        for k, (img, col) in enumerate((('pre:saltamontes', 0), ('canciller', 1), ('pre:consejero', 0))):
            cv.create_image(x + 24 + tam / 2 + k * tam * 0.5, y + h / 2,
                            image=a.img.get(V.ruta_imagen(img, col), tam), tags=tag)
        tx = x + 34 + tam * 1.9
        cv.create_text(tx, y + h / 2 - px(20), text='Más variantes', anchor='w', font=(a.serif, 17, 'bold'),
                       fill='#F3E2BE', tags=tag)
        cv.create_text(tx, y + h / 2 + px(14), anchor='w', width=w - (tx - x) - 40, font=(a.letra, 9),
                       fill=TEXTO_SUAVE, tags=tag,
                       text='Gran Ajedrez, Jano, Embajada, Shatranj, Makruk, Courier, Knightmate y otras %d.'
                            % (len(__import__('presets').OTRAS) - 7))
        cv.create_text(x + w - 22, y + h / 2, text='→', font=(a.serif, 22, 'bold'), fill=ORO, tags=tag)
        self._hover(tag, borde, fondo)
        from ventanas import MasVariantes
        cv.tag_bind(tag, '<Button-1>', lambda e: MasVariantes(a))

    def reglas(self, v):
        from reglas import VentanaReglas
        VentanaReglas(self.app, v)

    def _tarjeta_laboratorio(self, x, y, w, h):
        cv, a = self.cv, self.app
        tag = 'laboratorio'
        fondo = cv.create_rectangle(x, y, x + w, y + h, fill=TARJETA, outline='', tags=tag)
        borde = cv.create_rectangle(x, y, x + w, y + h, outline=BORDE, width=1, tags=tag)
        tam = int(h * 0.62)
        for k, (img, col) in enumerate((('caballo', 1), ('dama', 0), ('torre', 1))):
            cv.create_image(x + 30 + tam / 2 + k * tam * 0.55, y + h / 2,
                            image=a.img.get(V.ruta_imagen(img, col, True), tam), tags=tag)
        tx = x + 40 + tam * 2.2
        cv.create_text(tx, y + h / 2 - px(22), text='Laboratorio', anchor='w', font=(a.serif, 20, 'bold'),
                       fill='#F3E2BE', tags=tag)
        cv.create_text(tx, y + h / 2 + px(14), anchor='w', width=w - (tx - x) - 80, font=(a.letra, 10),
                       fill=TEXTO_SUAVE, tags=tag,
                       text='Crea tu propia variante: elige el tamaño y el estilo del tablero, diseña piezas con '
                            'sus movimientos, ajusta las reglas y juega contra la computadora.')
        cv.create_text(x + w - 36, y + h / 2, text='→', font=(a.serif, 26, 'bold'), fill=ORO, tags=tag)
        self._hover(tag, borde, fondo)
        cv.tag_bind(tag, '<Button-1>', lambda e: a.laboratorio())


# ====================================================================== partida y entrenamiento
class Juego:
    SESION = ('modo', 'inicio', 'estados', 'hist', 'jugadas', 'marcas', 'rep', 'humano', 'nivel', 'girado',
              'registro', 'ruta_bitacora', 'dos_jugadores', 'reloj', 'relojes', 'barra_eval', 'explicaciones')

    def __init__(self, app, variante, volver=None):
        self.app, self.v = app, variante
        self.root, self.img, self.ia, self.sonidos = app.root, app.img, app.ia, app.sonidos
        self.letra = app.letra
        self.volver = volver or app.menu  # a dónde lleva el botón «Menú»
        self.W, self.H = variante.ancho, variante.alto
        self.colores = colores_tema(app.tema(variante))
        self.NIV, self.niv_elo = niveles_para(variante)  # (nombre, prof, segundos, temperatura, elo)
        self.humano, self.nivel, self.girado = 0, len(self.NIV) // 2, False
        self.S, self.ox, self.oy = 60, 0, 0
        self.pensando = None
        self._redibujo = None
        self.modo, self.inicio = 'partida', None
        self.sesiones = {}
        self.ed, self.herr = {}, (self.v.paleta[-1], 0)
        self.arr, self.oculta = None, None  # arrastre de piezas en el editor
        # espectador: dos computadoras o una bitácora, a velocidad humana
        self.niveles, self.pausado, self.pendiente, self.paso_unico = [len(self.NIV) // 2] * 2, True, None, False
        self.t_ultima, self.ultima_eval = 0.0, None
        self.registro, self.ruta_bitacora = None, None   # bitácora que se está grabando
        self.repro, self.repro_pos, self.repro_reg = None, 0, None  # bitácora que se está reproduciendo
        self.repro_todo, self.analizador = None, None  # posiciones precalculadas y análisis de la reproducción
        self.dos_jugadores, self.girar_auto = False, False  # partida entre dos personas en este equipo
        self.reloj, self.relojes, self.reloj_opcion = None, [], 0  # reloj: {'base', 'inc', 't', 'marca'}
        self.barra_eval, self.eval_pedida = None, None  # barra de evaluación: {'e'|'m'} a favor de las blancas
        self.anim, self.sin_anim, self.anim_activa = None, False, False  # animación de la última jugada
        self.problema, self.problemas_lista, self.prob_base, self.prob_estado = None, [], 0, None
        self.final, self.final_token = None, 0  # práctica de finales: configuración y turno de las jugadas programadas
        self.leccion = None  # «Aprende a jugar»: {'i': lección, 'k': ejercicio}
        # ayudas: pista pedida {'id', 'k', 'idx', 'texto'}, avisos de peligro y lo que esperaba la computadora
        self.pista, self.avisos, self.explicaciones = None, [], {}
        self.vista_k, self.vista_base = None, None  # revisar una posición anterior sin cambiar la partida
        self.frame = tk.Frame(app.root, bg=FONDO)
        self.construir_ui()
        self.reiniciar(pedir=False)

    # ------------------------------------------------------------------ interfaz
    def construir_ui(self):
        self.canvas = tk.Canvas(self.frame, bg=FONDO, highlightthickness=0)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.bind('<Configure>', self.al_redimensionar)
        self.canvas.bind('<Button-1>', self.clic)
        self.canvas.bind('<B1-Motion>', self.arrastrar)
        self.canvas.bind('<ButtonRelease-1>', self.soltar)
        self.canvas.bind('<Button-3>', self.clic_derecho)

        panel = ttk.Frame(self.frame, style='Panel.TFrame', padding=(10, 12, 14, 12), width=px(330))
        panel.pack(side='right', fill='y')
        panel.pack_propagate(False)
        arriba = ttk.Frame(panel, style='Panel.TFrame')
        arriba.pack(fill='x')
        ttk.Button(arriba, text='← Menú', style='Menu.TButton', command=self.ir_al_menu).pack(side='left')
        ttk.Button(arriba, text='Reglas', style='Menu.TButton', command=self.ver_reglas).pack(side='right')
        ttk.Label(panel, text=self.v.nombre, style='Titulo.TLabel', wraplength=px(300)).pack(anchor='w', pady=(6, 0))
        pestanas = ttk.Frame(panel, style='Panel.TFrame')
        pestanas.pack(fill='x', pady=(8, 8))
        self.pestanas = {}
        for modo, txt in (('partida', 'Partida'), ('entrenamiento', 'Entrenamiento'), ('espectador', 'Espectador')):
            b = ttk.Button(pestanas, text=txt, style='Pestana.TButton', command=lambda m=modo: self.ir_a(m))
            b.pack(side='left', expand=True, fill='x', padx=(0, 2))
            self.pestanas[modo] = b
        # finales y problemas de esta variante (y en el 11×11, lecciones y aperturas): abren su ventana
        filas = [[('final', 'Finales', lambda: self.app.finales(self.v)),
                  ('problema', 'Problemas', lambda: self.app.problemas(self.v))]]
        if self.v.id == 'extendido':
            filas.append([('leccion', 'Aprender', self.app.lecciones),
                          ('aperturas', 'Aperturas', lambda: self.app.aperturas(
                              self.hist if self.inicio is None and self.modo != 'editor' else []))])
        for botones in filas:
            pestanas = ttk.Frame(panel, style='Panel.TFrame')
            pestanas.pack(fill='x', pady=(0, 8))
            for modo, txt, accion in botones:
                b = ttk.Button(pestanas, text=txt, style='Pestana.TButton', command=accion)
                b.pack(side='left', expand=True, fill='x', padx=(0, 2))
                self.pestanas[modo] = b
        self.construir_editor(panel)
        panel = self.marco_juego = ttk.Frame(panel, style='Panel.TFrame')
        self.lbl_info = ttk.Label(panel, style='Panel.TLabel', wraplength=px(300), justify='left')
        self.lbl_info.pack(anchor='w')
        self.construir_espectador(panel)
        self.cv_reloj = tk.Canvas(panel, width=300, height=46, bg=FONDO, highlightthickness=0)
        opciones = ttk.Frame(panel, style='Panel.TFrame')
        opciones.pack(anchor='w', fill='x', pady=(0, 6))
        self.var_sonido = tk.BooleanVar(value=self.sonidos.activo)
        ttk.Checkbutton(opciones, text='Sonido', variable=self.var_sonido, style='Panel.TCheckbutton',
                        command=lambda: setattr(self.sonidos, 'activo', self.var_sonido.get())).pack(side='left')
        self.var_barra = tk.BooleanVar(value=getattr(self.app, 'barra_eval', False))
        ttk.Checkbutton(opciones, text='Barra de evaluación', variable=self.var_barra, style='Panel.TCheckbutton',
                        command=self.cambio_barra).pack(side='left', padx=(12, 0))
        self.lbl_estado = ttk.Label(panel, style='Estado.TLabel', wraplength=px(300), justify='left')
        self.lbl_estado.pack(anchor='w', fill='x', pady=(0, 10))
        self.cv_puntos = None
        if self.v.con_puntos:
            ttk.Label(panel, text='MARCADOR DE PUNTOS', style='Sub.TLabel').pack(anchor='w')
            self.cv_puntos = tk.Canvas(panel, width=300, height=112, bg=FONDO, highlightthickness=0)
            self.cv_puntos.pack(anchor='w', pady=(4, 8))

        self.marcador = {}
        for color in (1, 0):
            ttk.Label(panel, text='CAPTURAS DE LAS ' + COLORES[color].upper(), style='Sub.TLabel').pack(anchor='w')
            fila = ttk.Frame(panel, style='Panel.TFrame')
            fila.pack(fill='x', pady=(2, 8))
            c = tk.Canvas(fila, height=52, bg=FONDO, highlightthickness=0)
            c.pack(side='left', fill='x', expand=True)
            self.marcador[color] = c

        if self.v.derechos(self.v.inicial(), 0) is not None:
            ttk.Label(panel, text='TUS EXTENSIONES DISPONIBLES', style='Sub.TLabel').pack(anchor='w')
            self.lbl_derechos = ttk.Label(panel, style='Panel.TLabel', wraplength=px(300), justify='left')
            self.lbl_derechos.pack(anchor='w', pady=(2, 4))
        else:
            self.lbl_derechos = None
        self.acciones = ttk.Frame(panel, style='Panel.TFrame')
        self.acciones.pack(fill='x', pady=(0, 8))

        self.botones = ttk.Frame(panel, style='Panel.TFrame')
        self.botones.pack(side='bottom', fill='x', pady=(8, 0))

        ttk.Label(panel, text='JUGADAS', style='Sub.TLabel').pack(anchor='w')
        marco = ttk.Frame(panel, style='Panel.TFrame')
        marco.pack(fill='both', expand=True, pady=(2, 0))
        self.txt = tk.Text(marco, width=30, font=('DejaVu Sans Mono', 10), bg='#1E1B18', fg=TEXTO,
                           relief='flat', state='disabled', wrap='none', padx=6, pady=4)
        self.txt.tag_configure('vista', background='#6B5530', foreground='#FFFFFF')
        self.txt.tag_bind('j', '<Button-1>', self.clic_lista)
        self.txt.tag_bind('j', '<Enter>', lambda e: self.txt.configure(cursor='hand2'))
        self.txt.tag_bind('j', '<Leave>', lambda e: self.txt.configure(cursor=''))
        barra = ttk.Scrollbar(marco, command=self.txt.yview)
        self.txt.configure(yscrollcommand=barra.set)
        barra.pack(side='right', fill='y')
        self.txt.pack(side='left', fill='both', expand=True)
        self.mostrar_panel()

    def construir_espectador(self, padre):
        """Controles del modo espectador (dos computadoras) y de la reproducción de bitácoras."""
        f = self.marco_espectador = ttk.Frame(padre, style='Panel.TFrame')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(6, 2))
        self.cmb_niveles = []
        for i, txt in enumerate(('Blancas', 'Negras')):
            ttk.Label(fila, text=txt, style='Sub.TLabel').grid(row=0, column=i, sticky='w', padx=(0, 6))
            c = ttk.Combobox(fila, state='readonly', width=13, values=[n[0] for n in self.NIV])
            c.current(self.niveles[i])
            c.grid(row=1, column=i, sticky='we', padx=(0, 6))
            self.cmb_niveles.append(c)
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(6, 0))
        ttk.Label(fila, text='VELOCIDAD', style='Sub.TLabel').pack(side='left')
        self.lbl_velocidad = ttk.Label(fila, style='Panel.TLabel')
        self.lbl_velocidad.pack(side='right')
        self.var_velocidad = tk.DoubleVar(value=1.5)
        self.var_velocidad.trace_add('write', lambda *x: self.lbl_velocidad.configure(
            text='%.1f s por jugada' % self.var_velocidad.get()))
        ttk.Scale(f, from_=0.2, to=5, variable=self.var_velocidad).pack(fill='x')
        self.lbl_velocidad.configure(text='1.5 s por jugada')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(6, 0))
        self.btn_comenzar = ttk.Button(fila, text='Nueva partida', command=self.comenzar_espectador)
        self.btn_comenzar.pack(side='left', expand=True, fill='x', padx=(0, 2))
        self.btn_pausa = ttk.Button(fila, text='▶ Reanudar', command=self.alternar_pausa)
        self.btn_pausa.pack(side='left', expand=True, fill='x')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 0))
        self.btn_atras = ttk.Button(fila, text='◀ Atrás', command=self.atras)
        self.btn_atras.pack(side='left', expand=True, fill='x', padx=(0, 2))
        ttk.Button(fila, text='Paso ▶', command=self.paso).pack(side='left', expand=True, fill='x')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 0))
        ttk.Button(fila, text='Abrir bitácora…', command=self.app.abrir_bitacora).pack(
            side='left', expand=True, fill='x', padx=(0, 2))
        self.btn_analizar = ttk.Button(fila, text='Analizar partida', command=self.analizar)
        self.btn_analizar.pack(side='left', expand=True, fill='x')
        self.lbl_eval = ttk.Label(f, style='Panel.TLabel', wraplength=px(300), justify='left')
        self.lbl_eval.pack(anchor='w', pady=(6, 0))
        self.lbl_bitacora = ttk.Label(f, style='Sub.TLabel', wraplength=px(300), justify='left')
        self.lbl_bitacora.pack(anchor='w', pady=(2, 6))

    def construir_editor(self, padre):
        v = self.v
        f = self.marco_editor = ttk.Frame(padre, style='Panel.TFrame')
        ttk.Label(f, text='Entrenamiento', style='Estado.TLabel').pack(anchor='w')
        ttk.Label(f, text='Coloca las piezas y pulsa «Comenzar». Tú haces la primera jugada y la '
                          'computadora continúa.', style='Panel.TLabel', wraplength=px(300),
                  justify='left').pack(anchor='w', pady=(2, 10))

        ttk.Label(f, text='PIEZAS', style='Sub.TLabel').pack(anchor='w')
        self.filas_paleta = (len(v.paleta) + 4) // 5
        self.paleta = tk.Canvas(f, width=296, height=2 * self.filas_paleta * 46, bg=FONDO,
                                highlightthickness=0, cursor='hand2')
        self.paleta.pack(anchor='w', pady=(2, 2))
        self.paleta.bind('<Button-1>', self.clic_paleta)
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x')
        self.var_prom = tk.BooleanVar(value=False)
        if v.tiene_promocionadas:
            ttk.Checkbutton(fila, text='Forma extendida', variable=self.var_prom, style='Panel.TCheckbutton',
                            command=self.dibujar_paleta).pack(side='left')
        self.btn_goma = ttk.Button(fila, text='Goma', width=7, command=lambda: self.elegir_herramienta('borrar'))
        self.btn_goma.pack(side='right')
        ttk.Label(f, text='Clic: colocar la pieza elegida (otra vez: quitarla). Arrastra una pieza del '
                          'tablero para moverla, o sácala del tablero para quitarla. Clic derecho: quitar.',
                  style='Panel.TLabel', wraplength=px(300), justify='left').pack(anchor='w', pady=(4, 10))

        ttk.Label(f, text='PRÁCTICA RÁPIDA CON UNA PIEZA', style='Sub.TLabel').pack(anchor='w')
        self.practicas = [(v.nombre_pieza(t, pr), t, pr) for t in v.paleta
                          for pr in ((False, True) if v.tiene_promocionadas and t != v.rey else (False,))]
        self.cmb_practica = ttk.Combobox(f, state='readonly', values=[p[0] for p in self.practicas])
        self.cmb_practica.set('Elige una pieza…')
        self.cmb_practica.pack(fill='x', pady=(2, 10))
        self.cmb_practica.bind('<<ComboboxSelected>>', self.practica_rapida)

        ttk.Label(f, text='POSICIÓN', style='Sub.TLabel').pack(anchor='w')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 10))
        for txt, cmd in (('Vaciar', self.ed_vaciar), ('Solo reyes', self.ed_reyes), ('Inicial', self.ed_inicial)):
            ttk.Button(fila, text=txt, command=cmd).pack(side='left', expand=True, fill='x', padx=(0, 2))
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(0, 10))
        for txt, cmd in (('Copiar posición', self.copiar_posicion_editor), ('Pegar posición…', self.pegar_posicion)):
            ttk.Button(fila, text=txt, command=cmd).pack(side='left', expand=True, fill='x', padx=(0, 2))

        ttk.Label(f, text='JUEGAS CON (MUEVES PRIMERO)', style='Sub.TLabel').pack(anchor='w')
        fila = ttk.Frame(f, style='Panel.TFrame')
        fila.pack(fill='x', pady=(2, 10))
        self.var_color = tk.IntVar(value=0)
        for i, txt in enumerate(('Blancas', 'Negras')):
            ttk.Radiobutton(fila, text=txt, value=i, variable=self.var_color, style='Panel.TRadiobutton',
                            command=self.cambio_color_editor).pack(side='left', padx=(0, 16))

        ttk.Label(f, text='NIVEL DE LA COMPUTADORA', style='Sub.TLabel').pack(anchor='w')
        self.cmb_nivel = ttk.Combobox(f, state='readonly', values=[n[0] for n in self.NIV])
        self.cmb_nivel.current(self.nivel)
        self.cmb_nivel.pack(fill='x', pady=(2, 10))

        self.lbl_error = ttk.Label(f, style='Error.TLabel', wraplength=px(300), justify='left')
        self.lbl_error.pack(anchor='w', fill='x')
        ttk.Button(f, text='Comenzar', style='Comenzar.TButton',
                   command=self.comenzar_entrenamiento).pack(side='bottom', fill='x')
        ttk.Button(f, text='Reiniciar entrenamiento', command=self.reiniciar_entrenamiento).pack(
            side='bottom', fill='x', pady=(0, 6))

    def mostrar_panel(self):
        pestana = {'partida': 'partida', 'espectador': 'espectador', 'reproduccion': 'espectador',
                   'problema': 'problema', 'final': 'final', 'leccion': 'leccion'}.get(self.modo, 'entrenamiento')
        for m, b in self.pestanas.items():
            b.configure(style='PestanaActiva.TButton' if m == pestana else 'Pestana.TButton')
        if self.modo == 'editor':
            self.marco_juego.pack_forget()
            self.marco_editor.pack(fill='both', expand=True)
            self.dibujar_paleta()
            return
        self.marco_editor.pack_forget()
        self.marco_juego.pack(fill='both', expand=True)
        if self.modo in ESPECTADOR:
            self.marco_espectador.pack(fill='x', before=self.lbl_estado)
        else:
            self.marco_espectador.pack_forget()
        if self.modo == 'partida' and self.reloj:
            self.cv_reloj.pack(anchor='w', pady=(4, 6), after=self.lbl_info)
        else:
            self.cv_reloj.pack_forget()
        for w in self.botones.winfo_children():
            w.destroy()
        if self.modo in ESPECTADOR:
            filas = [[('Exportar…', self.exportar), ('Girar', self.girar)]]
        elif self.modo == 'partida':
            filas = [[('Nueva partida', self.dialogo_nueva), ('Deshacer', self.deshacer), ('Girar', self.girar)],
                     [('Exportar…', self.exportar)] + self.botones_ayuda()]
        elif self.modo == 'final' and self.humano is None:
            filas = [[('▶ Seguir' if self.pausado else '⏸ Pausa', self.pausa_final), ('Paso ▶', self.paso_final)],
                     [('Reiniciar', self.reiniciar_final), ('Otro final…', lambda: self.app.finales(self.v)), ('Girar', self.girar)]]
        elif self.modo == 'final':
            filas = [[('Deshacer', self.deshacer), ('Pista', self.pista_final), ('Reiniciar', self.reiniciar_final)],
                     [('Otro final…', lambda: self.app.finales(self.v)), ('Girar', self.girar)]]
        elif self.modo == 'leccion':
            filas = [[('Reintentar', self.reintentar_leccion), ('Pista', self.pista_leccion),
                      ('Siguiente ▶', self.siguiente_leccion)],
                     [('Lecciones…', self.app.lecciones), ('La regla', self.regla_leccion)]]
        elif self.modo == 'problema':
            filas = [[('Reintentar', self.reintentar_problema), ('Ver solución', self.ver_solucion)],
                     [('Siguiente problema ▶', self.siguiente_problema), ('Girar', self.girar)]]
        else:
            filas = [[('Editar posición', lambda: self.abrir_editor(self.st)), ('Reiniciar ejercicio', self.reiniciar)],
                     [('Deshacer', self.deshacer), ('Girar', self.girar), ('Exportar…', self.exportar)]]
            if self.botones_ayuda():
                filas.append(self.botones_ayuda())
        for fila in filas:
            f = ttk.Frame(self.botones, style='Panel.TFrame')
            f.pack(fill='x', pady=(2, 0))
            for txt, cmd in fila:
                ttk.Button(f, text=txt, command=cmd).pack(side='left', expand=True, fill='x', padx=(0, 2))
        from manual import poner_tooltips
        poner_tooltips(self.botones)

    def detener_analisis(self):
        if self.analizador is not None:
            self.analizador.cancelar()
            v = getattr(self.analizador, 'ventana', None)
            if v is not None and v.top.winfo_exists():
                v.top.destroy()
            self.analizador = None

    def ir_al_menu(self):
        if self.modo == 'partida' and self.jugadas and not self.fin and self.registro is None:
            if not messagebox.askyesno('Volver', 'La partida en curso se perderá. ¿Volver?', parent=self.root):
                return
        self.cancelar_ia()
        self.detener_analisis()
        self.volver()

    def ver_reglas(self):
        from reglas import VentanaReglas
        VentanaReglas(self.app, self.v)

    def escape(self):
        if self.vista_activa():
            self.ver_posicion(None)
        else:
            self.deseleccionar()

    def atajo_entrenamiento(self):
        self.ir_a('entrenamiento')

    # ------------------------------------------------------------------ modos y sesiones
    def ir_a(self, modo):
        actual = {'partida': 'partida', 'espectador': 'espectador', 'reproduccion': 'espectador',
                  'problema': 'problema', 'final': 'final', 'leccion': 'leccion'}.get(self.modo, 'entrenamiento')
        if modo == actual:
            return
        self.cancelar_ia()
        self.pausado, self.pendiente = True, None
        if self.modo in ('partida', 'entrenamiento'):
            self.reloj_pausar()
            self.sesiones[actual] = {k: getattr(self, k) for k in self.SESION}
        guardada = self.sesiones.get(modo)
        if modo == 'espectador':
            self.preparar_espectador()
        elif guardada:
            for k, val in guardada.items():
                setattr(self, k, val)
            if self.reloj and not self.fin_guardado():
                self.reloj['marca'] = time.time()
            self.mostrar_panel()
            self.tras_jugada(avisar=False)
        elif modo == 'partida':  # partida nueva: sin el reloj ni el registro de una sesión anterior
            self.modo, self.inicio = 'partida', None
            self.reloj, self.relojes, self.registro, self.ruta_bitacora = None, [], None, None
            self.dos_jugadores, self.problema, self.final, self.prob_estado = False, None, None, None
            self.leccion = None
            if self.humano is None:  # venía del espectador o de ver un final: juegas con blancas
                self.humano, self.girado = 0, False
            self.mostrar_panel()
            self.reiniciar(pedir=False)
            self.dialogo_nueva()
        else:
            self.abrir_editor()

    def abrir_editor(self, desde=None):
        self.cancelar_ia()
        self.sesiones.pop('entrenamiento', None)
        if desde is not None:
            self.ed = self._piezas_de(desde)
            self.var_color.set(self.humano)
        elif not self.ed:
            self.ed_reyes(refrescar=False)
        self.cmb_nivel.current(self.nivel)
        self.modo = 'editor'
        self.mostrar_panel()
        self.refrescar_editor()

    def _piezas_de(self, st):
        return {sq: self.v.pieza(st, sq) for sq in range(self.W * self.H) if self.v.pieza(st, sq)}

    # ------------------------------------------------------------------ editor de posiciones
    def posicion_editor(self):
        return self.v.construir(self.piezas_editor(), self.var_color.get())

    def piezas_editor(self):
        return [[sq, t, c, pr] for sq, (t, c, pr) in sorted(self.ed.items())]

    def refrescar_editor(self, error=''):
        self.estados = [self.posicion_editor()]
        self.movs, self.hist, self.jugadas, self.marcas = [], [], [], []
        self.sel, self.destinos, self.fin = None, {}, None
        self.lbl_error.configure(text=error)
        self.dibujar()

    def dibujar_paleta(self):
        cv = self.paleta
        cv.delete('all')
        prom = self.var_prom.get()
        for c in (0, 1):
            for i, t in enumerate(self.v.paleta):
                x, y = (i % 5) * 59, (c * self.filas_paleta + i // 5) * 46
                if self.herr == (t, c):
                    cv.create_rectangle(x + 1, y + 1, x + 58, y + 45, fill='#C9A46A', outline='')
                elif c == 1:
                    base_clara(cv, x + 4, y + 2, x + 55, y + 44)
                cv.create_image(x + 29.5, y + 23, image=self.img.get(self.v.imagen(t, c, prom), 42))
        self.btn_goma.configure(style='PestanaActiva.TButton' if self.herr == 'borrar' else 'TButton')

    def clic_paleta(self, ev):
        col, fila = int(ev.x // 59), int(ev.y // 46)
        c, i = fila // self.filas_paleta, (fila % self.filas_paleta) * 5 + col
        if 0 <= col < 5 and c in (0, 1) and i < len(self.v.paleta):
            self.elegir_herramienta((self.v.paleta[i], c))

    def elegir_herramienta(self, herr):
        self.herr = herr
        self.dibujar_paleta()

    def clic_editor(self, sq, borrar=False):
        if sq is None:
            return
        if borrar or self.herr == 'borrar':
            self.ed.pop(sq, None)
        else:
            t, c = self.herr
            nueva = self.v.ajustar(t, c, self.var_prom.get(), sq)
            if self.ed.get(sq) == nueva:
                del self.ed[sq]
            else:
                if t == self.v.rey:
                    for s in [s for s, val in self.ed.items() if val[0] == t and val[1] == c]:
                        del self.ed[s]
                self.ed[sq] = nueva
        self.refrescar_editor()

    def _sq(self, col, fila, vista):
        """Casilla en coordenadas vistas desde el bando 'vista' (fila 0 = su primera fila)."""
        r = fila if vista == 0 else self.H - 1 - fila
        return r * self.W + col

    def reiniciar_entrenamiento(self):
        """Deja el editor como al entrar por primera vez."""
        self.sesiones.pop('entrenamiento', None)
        self.herr, self.arr, self.oculta = (self.v.paleta[-1], 0), None, None
        self.var_prom.set(False)
        self.var_color.set(0)
        self.girado = False
        self.cmb_practica.set('Elige una pieza…')
        self.cmb_nivel.current(len(self.NIV) // 2)
        self.dibujar_paleta()
        self.ed_reyes()

    def ed_vaciar(self):
        self.ed = {}
        self.refrescar_editor()

    def ed_reyes(self, refrescar=True):
        self.ed = {}
        if self.v.rey:
            self.ed = {self._sq(self.W // 2, 0, 0): (self.v.rey, 0, False),
                       self._sq(self.W // 2, 0, 1): (self.v.rey, 1, False)}
        if refrescar:
            self.refrescar_editor()

    def ed_inicial(self):
        self.ed = self._piezas_de(self.v.inicial())
        self.refrescar_editor()

    def practica_rapida(self, ev=None):
        _, t, pr = self.practicas[self.cmb_practica.current()]
        h, W, H = self.var_color.get(), self.W, self.H
        self.ed_reyes(refrescar=False)
        peon = self.v.peon
        if peon:
            for col, fila in ((1, H - 3), (3, H - 4), (W - 4, H - 4), (W - 2, H - 3)):
                self.ed[self._sq(col, fila, h)] = (peon, 1 - h, False)
        if 'G' in self.v.paleta:
            self.ed[self._sq(W // 2, H - 3, h)] = ('G', 1 - h, False)
        if t != self.v.rey:
            self.ed[self._sq(W // 2, H // 2 - 1, h)] = (t, h, pr)
        self.refrescar_editor()

    def cambio_color_editor(self):
        self.girado = self.var_color.get() == 1
        self.refrescar_editor()

    def comenzar_entrenamiento(self):
        h, v = self.var_color.get(), self.v
        if v.rey:
            reyes = [sum(1 for val in self.ed.values() if val[0] == v.rey and val[1] == c) for c in (0, 1)]
            if reyes != [1, 1]:
                self.refrescar_editor('Cada bando necesita exactamente un %s.' % v.nombre_pieza(v.rey))
                return
        st = self.posicion_editor()
        if v.en_jaque(st, 1 - h):
            self.refrescar_editor('El Rey de las %s está en jaque y el turno es tuyo: esa posición no es '
                                  'válida. Aleja o tapa la pieza que lo ataca.' % COLORES[1 - h])
            return
        self.inicio = {'piezas': self.piezas_editor(), 'turno': h}
        self.humano, self.nivel = h, self.cmb_nivel.current()
        self.modo = 'entrenamiento'
        self.mostrar_panel()
        self.reiniciar()

    def dialogo_nueva(self):
        d = tk.Toplevel(self.root)
        d.title('Nueva partida — ' + self.v.nombre)
        d.transient(self.root)
        d.resizable(False, False)
        f = ttk.Frame(d, padding=16)
        f.pack(fill='both', expand=True)
        color = tk.StringVar(value=['blancas', 'negras'][self.humano or 0])
        nivel = tk.IntVar(value=self.nivel)
        ttk.Label(f, text='Juegas con', font=(self.letra, 10, 'bold')).grid(row=0, column=0, sticky='w')
        izq = ttk.Frame(f)
        izq.grid(row=1, column=0, sticky='nw')
        for txt, val in (('Blancas', 'blancas'), ('Negras', 'negras'), ('Al azar', 'azar')):
            ttk.Radiobutton(izq, text=txt, value=val, variable=color).pack(anchor='w', padx=8)
        ttk.Label(izq, text='Rival', font=(self.letra, 10, 'bold')).pack(anchor='w', pady=(10, 0))
        rival = tk.StringVar(value='persona' if self.dos_jugadores else 'computadora')
        ttk.Radiobutton(izq, text='La computadora', value='computadora', variable=rival).pack(anchor='w', padx=8)
        ttk.Radiobutton(izq, text='Otra persona, aquí mismo', value='persona', variable=rival).pack(anchor='w', padx=8)
        girar_auto = tk.BooleanVar(value=self.girar_auto)
        ttk.Checkbutton(izq, text='Girar el tablero en cada turno', variable=girar_auto).pack(anchor='w', padx=26)
        ttk.Label(izq, text='Reloj', font=(self.letra, 10, 'bold')).pack(anchor='w', pady=(10, 0))
        cmb_reloj = ttk.Combobox(izq, values=[r[0] for r in RELOJES], state='readonly', width=16)
        cmb_reloj.current(self.reloj_opcion)
        cmb_reloj.pack(anchor='w', padx=8, pady=(2, 0))
        ttk.Label(f, text='Nivel de la computadora', font=(self.letra, 10, 'bold')).grid(
            row=0, column=1, sticky='w', padx=(24, 0))
        der = ttk.Frame(f)
        der.grid(row=1, column=1, sticky='nw')
        for i, (txt, prof, seg, temp, _) in enumerate(self.NIV):
            if prof >= 20:  # sin límite de profundidad: piensa todo el tiempo que tiene
                extra = 'piensa %d s por jugada, tan hondo como alcance' % seg
            else:
                extra = 'analiza %d media%s jugada%s' % (prof, '' if prof == 1 else 's', '' if prof == 1 else 's')
                if seg:
                    extra += ', hasta %d s' % seg
            if temp:
                extra += ', con imprecisión'
            ttk.Radiobutton(der, text='%s  (%s)' % (txt, extra), value=i, variable=nivel).pack(
                anchor='w', padx=(32, 0), pady=1)
        if not self.ia.es_pypy:
            ttk.Label(f, text='PyPy no está instalado: la computadora pensará más lento y los niveles más '
                              'altos jugarán con menos profundidad.', wraplength=420,
                      foreground='#9A4B16').grid(row=len(self.NIV) + 2, column=0, columnspan=2, sticky='w', pady=(10, 0))
        elo, n_partidas = PG.elo_jugador(self.v.id) if self.niv_elo else (None, 0)
        if elo is not None:
            nivel.set(min(range(len(self.NIV)), key=lambda i: abs(self.NIV[i][4] - elo)))
            ttk.Label(f, text='Tu Elo: %d (%d partidas). Se preselecciona el nivel más cercano.' % (elo, n_partidas),
                      font=(self.letra, 10, 'bold')).grid(row=len(self.NIV) + 4, column=0, columnspan=2,
                                                          sticky='w', pady=(6, 0))
        if self.niv_elo:
            ttk.Label(f, text='Niveles calibrados en Elo jugando la computadora contra sí misma (escala propia '
                              'del juego).', wraplength=420, foreground='#6B5B45').grid(
                row=len(self.NIV) + 3, column=0, columnspan=2, sticky='w', pady=(6, 0))

        def comenzar():
            c = color.get()
            self.humano = random.randint(0, 1) if c == 'azar' else (0 if c == 'blancas' else 1)
            self.nivel = nivel.get()
            self.dos_jugadores, self.girar_auto = rival.get() == 'persona', girar_auto.get()
            if self.dos_jugadores:
                self.humano = 0
            self.girado = self.humano == 1
            k = cmb_reloj.current()  # puede venir vacío (None o -1) si no se eligió nada
            self.reloj_opcion = k if isinstance(k, int) and 0 <= k < len(RELOJES) else 0
            _, minutos, inc = RELOJES[self.reloj_opcion]
            self.reloj = {'base': minutos * 60.0, 'inc': inc, 't': [minutos * 60.0] * 2, 'marca': None} \
                if minutos else None
            self.barra_eval = None
            d.destroy()
            if self.modo != 'partida':
                self.cancelar_ia()
                if self.modo == 'entrenamiento':
                    self.sesiones['entrenamiento'] = {k: getattr(self, k) for k in self.SESION}
                self.modo, self.inicio = 'partida', None
                self.mostrar_panel()
            self.nuevo_registro_partida()
            self.reiniciar()
            self.guardar_bitacora()

        b = ttk.Frame(f)
        b.grid(row=len(self.NIV) + 6, column=0, columnspan=2, sticky='e', pady=(16, 0))
        ttk.Button(b, text='Cancelar', command=d.destroy).pack(side='right', padx=(6, 0))
        ttk.Button(b, text='Comenzar', command=comenzar).pack(side='right')
        d.bind('<Return>', lambda e: comenzar())
        d.bind('<Escape>', lambda e: d.destroy())
        d.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - d.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - d.winfo_height()) // 3
        d.geometry('+%d+%d' % (max(0, x), max(0, y)))
        d.wait_visibility()
        d.grab_set()
        d.focus_set()

    # ------------------------------------------------------------------ espectador y bitácoras
    def _info_nivel(self, i):
        nombre, prof, seg, temp, elo = self.NIV[i]
        info = {'nivel': nombre, 'profundidad': prof, 'tiempo': seg or None, 'temperatura': temp}
        if elo is not None:
            info['elo'] = elo
        return info

    def preparar_espectador(self):
        """Pestaña Espectador: tablero inicial en pausa, a la espera de «Nueva partida»."""
        self.cancelar_ia()
        self.modo, self.inicio, self.humano = 'espectador', None, None
        self.pausado, self.pendiente, self.registro, self.repro = True, None, None, None
        self.ultima_eval = None
        self.reiniciar(pedir=False)
        self.mostrar_panel()
        self.lbl_bitacora.configure(text='Elige el nivel de cada computadora y pulsa «Nueva partida». '
                                         'Las jugadas se guardan en una bitácora.')
        self.actualizar_panel()

    def comenzar_espectador(self):
        self.cancelar_ia()
        self.modo, self.inicio, self.humano = 'espectador', None, None
        self.niveles = [c.current() for c in self.cmb_niveles]
        self.repro, self.pendiente, self.ultima_eval = None, None, None
        nivel = self._info_nivel
        from busqueda import VERSION_IA
        self.registro = BIT.nuevo('espectador', self.v.spec, None, variante_nombre=self.v.nombre,
                                  blancas=nivel(self.niveles[0]), negras=nivel(self.niveles[1]),
                                  valores_ia=VERSION_IA)
        os.makedirs(BITACORAS, exist_ok=True)
        nombre = '%s_%s.jsonl' % (time.strftime('%Y%m%d_%H%M%S'), self.v.id)
        self.ruta_bitacora = os.path.join(BITACORAS, 'espectador_' + nombre)
        self.pausado = False
        self.t_ultima = 0.0
        self.mostrar_panel()
        self.reiniciar(pedir=False)
        self.guardar_bitacora()
        self.pedir_ia()

    def _precalcular(self, registro):
        """Todas las posiciones de una bitácora, para reproducirla y saltar a cualquier jugada. Se detiene
        (con un aviso) si una jugada no coincide con las reglas actuales."""
        v = self.v
        inicio = registro.get('inicio')
        st = v.inicial() if inicio is None else v.construir(inicio['piezas'], inicio['turno'])
        e = {'estados': [st], 'notas': [], 'marcas': [], 'hist': [], 'claves': [v.clave(st)], 'metas': [],
             'sonidos': [], 'anim': []}
        aviso = None
        for k, j in enumerate(registro.get('jugadas', [])):
            movs = v.legal(st)
            if not 0 <= j['i'] < len(movs):
                aviso = 'La jugada %d de la bitácora no existe con las reglas actuales.' % (k + 1)
                break
            mv, n = movs[j['i']]
            nota = v.notacion(st, mv, n, movs)
            if nota != j['j'].rstrip('+#'):
                aviso = ('La jugada %d de la bitácora era %s, pero con las reglas actuales se anota %s. '
                         'La bitácora puede ser de otra versión de las reglas.' % (k + 1, j['j'], nota))
                break
            e['anim'].append((mv[1], v.destino(mv), mv))
            e['sonidos'].append('jaque' if j['j'][-1:] in '+#' else 'captura' if v.es_captura(st, mv) else 'movimiento')
            e['notas'].append(j['j'] if j['j'][-1:] in '+#' else nota)
            e['marcas'].append(v.casillas(mv))
            e['hist'].append(j['i'])
            e['metas'].append(self._eval_de(j))
            st = n
            e['estados'].append(st)
            e['claves'].append(v.clave(st))
        if aviso:
            messagebox.showwarning('Bitácora', aviso + ' Se muestran solo las jugadas anteriores.', parent=self.root)
        return e

    def iniciar_reproduccion(self, registro, ruta, numero=1, analizar=False):
        self.cancelar_ia()
        self.modo, self.inicio, self.humano = 'reproduccion', registro.get('inicio'), None
        self.repro_reg, self.registro, self.ruta_bitacora = registro, None, ruta
        self.pendiente, self.ultima_eval, self.analizador = None, None, None
        self.repro_todo = self._precalcular(registro)
        self.repro = registro['jugadas'][:len(self.repro_todo['notas'])]
        self.pausado, self.t_ultima = analizar, time.time()
        self.mostrar_panel()
        self.ir_a_jugada(0)
        self.lbl_bitacora.configure(text='Reproduciendo %s, partida %d: %s' % (
            os.path.basename(ruta), numero, BIT.resumen(registro)))
        if analizar:
            self.root.after(300, self.analizar)

    def ir_a_jugada(self, k):
        """Reproducción: muestra la posición tras k jugadas."""
        e = self.repro_todo
        k = max(0, min(len(e['notas']), k))
        self.anim = None
        if k == self.repro_pos + 1 and e['anim'][k - 1][1] is not None and self.app.ajustes['animacion']:
            self.anim = self.nueva_anim(e['estados'][k - 1], e['anim'][k - 1][2], e['estados'][k])
        self.estados = e['estados'][:k + 1]
        self.jugadas, self.marcas, self.hist = e['notas'][:k], e['marcas'][:k], e['hist'][:k]
        self.rep = {}
        for c in e['claves'][:k + 1]:
            self.rep[c] = self.rep.get(c, 0) + 1
        self.repro_pos = k
        self.ultima_eval = e['metas'][k - 1] if k else None
        self.tras_jugada(avisar=False, pedir=False)
        ventana = getattr(self.analizador, 'ventana', None)
        if ventana is not None and ventana.top.winfo_exists():
            ventana.dibujar()

    def analizar(self):
        """Analiza con la computadora la partida que se está reproduciendo."""
        if self.modo != 'reproduccion' or not self.repro_todo or not self.repro_todo['notas']:
            messagebox.showinfo('Análisis', 'Abre primero una partida o bitácora para analizarla.', parent=self.root)
            return
        from analisis import PROFUNDIDADES, VentanaAnalisis
        d = tk.Toplevel(self.root)
        d.title('Analizar partida')
        d.transient(self.root)
        f = ttk.Frame(d, padding=16)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='¿Con qué profundidad analizar las %d jugadas?' % len(self.repro_todo['notas'])).pack(anchor='w')
        var = tk.IntVar(value=1)
        for i, (txt, _, _) in enumerate(PROFUNDIDADES):
            ttk.Radiobutton(f, text=txt, value=i, variable=var).pack(anchor='w', padx=8)
        ttk.Label(f, text='El análisis usa la computadora; a mayor profundidad, más preciso y más lento.',
                  foreground='#6B5B45').pack(anchor='w', pady=(6, 0))

        def comenzar():
            _, prof, seg = PROFUNDIDADES[var.get()]
            d.destroy()
            if self.analizador is not None:
                self.analizador.cancelar()
            self.pausado = True
            ventana = VentanaAnalisis(self.app, self, prof, seg)
            self.analizador.ventana = ventana
        ttk.Button(f, text='Analizar', command=comenzar).pack(anchor='e', pady=(10, 0))
        d.wait_visibility()
        d.grab_set()

    def nuevo_registro_partida(self):
        from busqueda import VERSION_IA
        self.registro = BIT.nuevo('partida', self.v.spec, self.inicio, variante_nombre=self.v.nombre,
                                  humano=COLORES[self.humano], computadora=self._info_nivel(self.nivel),
                                  valores_ia=VERSION_IA)
        if self.dos_jugadores:
            self.registro.update(dos_jugadores=True, computadora=None, humano='ambos')
        if self.reloj:
            self.registro['reloj'] = {'base': self.reloj['base'], 'inc': self.reloj['inc']}
        self.ruta_bitacora = PG.nueva_ruta(self.v.id)

    def reanudar(self, registro, ruta):
        """Continúa una partida guardada desde su última jugada."""
        self.cancelar_ia()
        self.modo, self.inicio = 'partida', registro.get('inicio')
        self.humano = 1 if registro.get('humano') == 'negras' else 0
        self.girado = self.humano == 1
        self.dos_jugadores = bool(registro.get('dos_jugadores'))
        self.barra_eval = None
        nombre = (registro.get('computadora') or {}).get('nivel')
        prof = (registro.get('computadora') or {}).get('profundidad')
        self.nivel = next((i for i, n in enumerate(self.NIV) if n[0] == nombre),
                          next((i for i, n in enumerate(self.NIV) if n[1] == prof), len(self.NIV) // 2))
        self.registro, self.ruta_bitacora = registro, ruta
        e = self._precalcular(registro)
        registro['jugadas'] = registro['jugadas'][:len(e['notas'])]
        self.estados, self.jugadas, self.marcas, self.hist = e['estados'], e['notas'], e['marcas'], e['hist']
        self.rep = {}
        for c in e['claves']:
            self.rep[c] = self.rep.get(c, 0) + 1
        self.reloj = None
        if registro.get('reloj'):
            base, inc = registro['reloj']['base'], registro['reloj']['inc']
            self.relojes = [[base, base]] + [list(j.get('r') or (base, base)) for j in registro['jugadas']]
            self.reloj = {'base': base, 'inc': inc, 't': list(self.relojes[-1]), 'marca': time.time()}
            self.reloj_opcion = next((i for i, r in enumerate(RELOJES) if r[1] and r[1] * 60 == base and r[2] == inc), 0)
        self.mostrar_panel()
        self.tras_jugada()

    def puntuar(self, ganador):
        """Actualiza tu Elo si la partida cuenta: niveles calibrados, posición inicial y sin «Deshacer»."""
        r = self.registro
        if (not self.niv_elo or self.inicio is not None or r.get('deshacer') or r.get('ayudas') or r.get('puntuada')
                or self.dos_jugadores):
            return
        elo_rival = self.NIV[self.nivel][4]
        puntos = 0.5 if ganador is None else (1.0 if ganador == self.humano else 0.0)
        antes, despues = PG.registrar(self.v.id, self.v.nombre, self.NIV[self.nivel][0], elo_rival, puntos,
                                      COLORES[self.humano])
        r['puntuada'] = {'antes': antes, 'despues': despues}

    def dialogo_fin(self):
        d = tk.Toplevel(self.root)
        d.title('Fin de la partida')
        d.transient(self.root)
        f = ttk.Frame(d, padding=18)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=self.fin, wraplength=380, font=(self.letra, 11, 'bold')).pack(anchor='w')
        p = (self.registro or {}).get('puntuada')
        if p:
            ttk.Label(f, text='Tu Elo: %d → %d (%+d)' % (p['antes'], p['despues'], p['despues'] - p['antes']),
                      font=(self.letra, 11)).pack(anchor='w', pady=(8, 0))
        elif self.niv_elo and not self.dos_jugadores:
            r = self.registro or {}
            motivo = ('usaste Deshacer' if r.get('deshacer') else 'usaste ayudas (pistas o avisos)' if r.get('ayudas')
                      else 'no empezó desde la posición inicial')
            ttk.Label(f, text='Esta partida no cuenta para tu Elo (%s).' % motivo).pack(anchor='w', pady=(8, 0))
        b = ttk.Frame(f)
        b.pack(anchor='e', pady=(14, 0))
        registro, ruta = self.registro, self.ruta_bitacora

        def analizar():
            d.destroy()
            self.app.reproducir(registro, ruta, analizar=True)
        ttk.Button(b, text='Analizar partida', command=analizar).pack(side='left', padx=(0, 4))
        ttk.Button(b, text='Nueva partida', command=lambda: (d.destroy(), self.dialogo_nueva())).pack(side='left', padx=(0, 4))
        ttk.Button(b, text='Cerrar', command=d.destroy).pack(side='left')

    # ------------------------------------------------------------------ práctica de finales
    def iniciar_final(self, cfg):
        """cfg: {'t', 'pr'} (Ajedrez Extendido) o {'tipos': [...]} (otras variantes), 'nombre', 'posicion': 'inicial' |
        'aleatoria', 'dificultad': (mínimo, máximo), 'modo': 'atacar' (das mate) | 'defender' (defiendes con el
        Rey solo) | 'ver' (la computadora juega los dos bandos)}."""
        import practica_finales as F
        self.cancelar_ia()
        self.guardar_sesion()
        self.tablas_final = F.para(self.v)
        lo, hi = cfg.get('dificultad') or (1, 99)
        ini = self.tablas_final.posicion(cfg, lo, hi)
        if ini is None:
            messagebox.showerror('Finales', 'No encontré una posición para este final.', parent=self.root)
            return
        self.final = dict(cfg, inicio=ini, comentario='')
        self.modo, self.inicio = 'final', ini
        self.humano = {'atacar': 0, 'defender': 1}.get(cfg['modo'])
        self.girado = self.humano == 1
        self.dos_jugadores, self.reloj, self.registro, self.ruta_bitacora = False, None, None, None
        self.barra_eval, self.anim, self.pausado = None, None, False
        st0 = self.v.construir(ini['piezas'], ini['turno'])
        v0 = self.tablas_final.valor(st0)
        self.final['optimo'] = (v0[1] + 1) // 2 if v0 and v0[0] == 'gana' else None
        self.mostrar_panel()
        self.reiniciar()

    def reiniciar_final(self):
        """Vuelve a la posición de inicio de este final (la misma, aunque haya sido al azar)."""
        self.cancelar_ia()
        self.final['comentario'] = ''
        self.pausado = False
        self.mostrar_panel()
        self.reiniciar()

    def velocidad_final(self):
        try:
            return max(0.2, float(self.var_velocidad.get()))
        except (tk.TclError, ValueError, AttributeError):
            return 1.0

    def jugada_tabla(self, tok):
        if tok != self.final_token or self.modo != 'final' or self.fin or not self.canvas.winfo_exists():
            return
        if self.humano is None and self.pausado:
            return
        if self.humano is not None and self.st.turn == self.humano:
            return
        idx = self.tablas_final.mejor_jugada(self.st, self.movs)
        if idx is not None:
            self.jugar(idx)

    def pausa_final(self):
        self.pausado = not self.pausado
        self.mostrar_panel()
        if not self.pausado and not self.fin:
            self.pedir_ia()
        self.actualizar_panel()

    def paso_final(self):
        if self.fin:
            return
        self.pausado = True
        self.final_token += 1
        self.mostrar_panel()
        idx = self.tablas_final.mejor_jugada(self.st, self.movs)
        if idx is not None:
            self.jugar(idx)

    def pista_final(self):
        if self.fin or self.st.turn != self.humano:
            return
        idx = self.tablas_final.mejor_jugada(self.st, self.movs)
        if idx is None:
            return
        mv, n = self.movs[idx]
        self.seleccionar(mv[1])
        self.final['comentario'] = 'Pista: %s.' % self.v.notacion(self.st, mv, n, self.movs)
        self.actualizar_panel()

    def comentario_final(self, st, n):
        """Qué tan buena fue tu jugada según la tabla (se calcula antes de hacerla)."""
        antes, despues = self.tablas_final.valor(st), self.tablas_final.valor(n)
        if antes is None or despues is None:
            return ''
        if antes[0] == 'tablas':
            return 'Con esta pieza el mate no se puede forzar (tablas con buena defensa).'
        if antes[0] == 'gana':  # das mate
            if despues[0] == 'tablas':
                return '✗ ¡Ya no se puede forzar el mate! Usa «Deshacer» y prueba otra jugada.'
            perdida = (despues[1] + 2 - antes[1]) // 2
            return '✓ Jugada perfecta.' if perdida <= 0 else '△ Alarga el mate %d jugada%s.' % (
                perdida, '' if perdida == 1 else 's')
        # te defiendes
        if despues[0] == 'tablas':
            return '✓ ¡Conseguiste tablas!'
        ganada = (antes[1] - despues[1] - 1) // 2
        return '✓ La mejor defensa.' if ganada <= 0 else '△ Acorta el mate %d jugada%s.' % (
            ganada, '' if ganada == 1 else 's')

    def fin_final(self):
        r = self.v.fin(self.st, self.movs, self.rep.get(self.v.clave(self.st), 0), True)
        if r is None:
            return None
        motivo, ganador, _ = r
        jugadas = (len(self.hist) + 1) // 2
        optimo = self.final.get('optimo')
        if ganador is None:
            return '%s: tablas.' % motivo
        if self.humano is None:
            return '%s en %d jugadas, con juego perfecto de los dos bandos.' % (motivo, jugadas)
        if ganador == self.humano:
            extra = (' ¡Perfecto: el mínimo posible!' if optimo and jugadas <= optimo else
                     (' El mínimo con juego perfecto era %d.' % optimo if optimo else ''))
            return '¡%s en %d jugadas!%s' % (motivo, jugadas, extra)
        return '%s en %d jugadas.%s' % (motivo, jugadas, (' Lo máximo que se podía resistir era %d.' % optimo)
                                         if optimo and jugadas < optimo else ' ¡Resististe lo máximo posible!')

    def estado_final(self):
        if self.humano is None:
            txt = 'En pausa.' if self.pausado else 'La computadora juega los dos bandos con juego perfecto.'
        elif self.st.turn == self.humano:
            txt = 'Tu turno: %s.' % ('da mate con las blancas' if self.humano == 0 else 'defiéndete con el Rey negro')
        else:
            txt = 'Responde la computadora…'
        c = self.final.get('comentario')
        return txt + ('\n' + c if c else '')

    def info_final(self):
        f = self.final
        pieza = f.get('nombre') or self.v.nombre_pieza(f['t'], f['pr'])
        modo = {'atacar': 'das mate', 'defender': 'defiendes'}.get(f['modo'], 'la computadora juega los dos bandos')
        v = self.tablas_final.valor(self.st)
        if v is None or self.fin:
            valor = ''
        elif v[0] == 'tablas':
            valor = 'Tablas: el mate ya no se puede forzar.'
        else:  # las blancas tienen la pieza: jugadas suyas hasta el mate
            valor = 'Las blancas dan mate en %d con juego perfecto.' % (
                (v[1] + 1) // 2 if self.st.turn == 0 else v[1] // 2)
        rey = self.v.nombre_pieza(self.v.rey)
        piezas = ('%s, %s' if ' y ' in pieza else '%s y %s') % (rey, pieza)
        return 'Final: %s contra %s · %s\n%s' % (piezas, rey, modo, valor)

    # ------------------------------------------------------------------ problemas de mate
    # ------------------------------------------------------------------ revisar la partida mientras se juega
    def vista_activa(self):
        """¿Se está mostrando una posición anterior (de esta misma partida)?"""
        return (self.vista_k is not None and self.modo != 'editor' and self.vista_base is self.estados[0]
                and self.vista_k < len(self.estados) - 1)

    def ver_posicion(self, k):
        """Muestra la posición tras k medias jugadas sin cambiar la partida; None (o la última): la actual."""
        if self.modo == 'editor':
            return
        if self.modo == 'reproduccion':  # la reproducción ya navega por su bitácora
            if k is not None and self.repro_todo:
                self.pausado = True
                self.ir_a_jugada(k)
            return
        k = None if k is None or k >= len(self.estados) - 1 else max(0, k)
        if k == (self.vista_k if self.vista_activa() else None):
            return
        self.vista_k, self.vista_base = k, self.estados[0]
        self.anim = None
        if k is not None and self.sel is not None:
            self.sel, self.destinos = None, {}
            self.mostrar_acciones([])
        self.dibujar()
        self.actualizar_estado()
        self.marcar_lista()

    def marcar_lista(self):
        """Resalta en la lista la jugada que se está revisando."""
        self.txt.tag_remove('vista', '1.0', 'end')
        if self.vista_activa() and self.vista_k > 0:
            rango = self.txt.tag_ranges('j%d' % self.vista_k)
            if rango:
                self.txt.tag_add('vista', *rango)
                self.txt.see(rango[0])
                return
        self.txt.see('end')

    def clic_lista(self, ev):
        for tag in self.txt.tag_names('@%d,%d' % (ev.x, ev.y)):
            if tag.startswith('j') and tag[1:].isdigit():
                self.ver_posicion(int(tag[1:]))
                return

    def _escribiendo(self):
        """Las flechas no navegan si el foco está en un campo de texto, una lista o un control deslizante."""
        w = self.root.focus_get()
        return isinstance(w, (tk.Entry, ttk.Entry, ttk.Combobox, ttk.Scale, tk.Scale, tk.Spinbox))

    def tecla_izquierda(self):
        if self._escribiendo():
            return
        if self.modo == 'reproduccion':
            return self.atras()
        k = self.vista_k if self.vista_activa() else len(self.estados) - 1
        if k > 0:
            self.ver_posicion(k - 1)

    def tecla_derecha(self):
        if self._escribiendo():
            return
        if self.modo == 'reproduccion':
            if self.repro_todo and self.repro_pos < len(self.repro_todo['notas']):
                self.ver_posicion(self.repro_pos + 1)
            return
        if self.vista_activa():
            self.ver_posicion(self.vista_k + 1)

    def tecla_inicio(self):
        if not self._escribiendo():
            self.ver_posicion(0)

    def tecla_fin(self):
        if self._escribiendo():
            return
        if self.modo == 'reproduccion':
            if self.repro_todo:
                self.ver_posicion(len(self.repro_todo['notas']))
            return
        self.ver_posicion(None)

    # ------------------------------------------------------------------ ayudas durante la partida
    def botones_ayuda(self):
        if not self.app.ajustes.get('ayudas', True) or self.dos_jugadores:
            return []
        return [('Pista', self.pedir_pista), ('¿Por qué?', self.por_que)]

    def notas_linea(self, st, linea):
        """Notación de una línea de jugadas (índices de jugadas legales) desde st."""
        out = []
        for i in linea:
            movs = self.v.legal(st)
            if i >= len(movs):
                break
            mv, n = movs[i]
            out.append(self.v.notacion(st, mv, n, movs) + ('+' if self.v.en_jaque(n, n.turn) else ''))
            st = n
        return out

    def texto_linea_desde(self, k, notas):
        """'12… Cxd4 13. Ab5 Dd7' para jugadas que empiezan en la media jugada k."""
        out = []
        for j, nota in enumerate(notas):
            ply = k + j + self.estados[0].turn  # si la posición empezó con las negras
            if ply % 2 == 0:
                out.append('%d. %s' % (ply // 2 + 1, nota))
            else:
                out.append(('%d… %s' % (ply // 2 + 1, nota)) if j == 0 else nota)
        return ' '.join(out)

    def app_libro_prof(self):
        import aperturas
        return aperturas.cargar_libro().get('prof')

    def marcar_ayuda(self):
        """Una partida con ayudas no cuenta para el Elo."""
        if self.modo == 'partida' and self.registro is not None and not self.registro.get('ayudas'):
            self.registro['ayudas'] = True
            self.guardar_bitacora()

    def calcular_avisos(self):
        self.avisos = []
        if (self.fin or not self.app.ajustes.get('avisos') or self.modo not in ('partida', 'entrenamiento')
                or self.humano is None or self.st.turn != self.humano):
            return
        import ayudas
        try:
            self.avisos = ayudas.amenazas(self.v, self.st, self.humano)
        except Exception:
            self.avisos = []
        if self.avisos:
            self.marcar_ayuda()

    def casillas_aviso(self):
        if not self.avisos or self.avisos[0][0] == 'mate':
            return []
        return [sq for sq, _, _ in self.avisos[:2]]

    def pedir_pista(self):
        if self.fin or self.pensando or self.st.turn != self.humano or self.modo not in ('partida', 'entrenamiento'):
            return
        if self.pista and self.pista['k'] == len(self.hist):
            return  # ya pedida (o ya mostrada) en esta posición
        r = self.registro or {}
        if (self.modo == 'partida' and self.niv_elo and not r.get('ayudas') and not r.get('deshacer')
                and self.inicio is None and not messagebox.askyesno(
                    'Pista', 'Si usas una pista, esta partida ya no contará para tu Elo. ¿Quieres la pista?',
                    parent=self.root)):
            return
        self.marcar_ayuda()
        seg = 2.0 if self.ia.es_pypy else 4.0
        try:
            rid = self.ia.pedir(self.v.spec, self.inicio, self.hist, 30, seg, 0.0, linea=True)
        except OSError:
            return
        self.pista = {'id': rid, 'k': len(self.hist)}
        self.actualizar_estado()

    def respuesta_pista(self, r):
        p = self.pista
        if p['k'] != len(self.hist) or self.fin or r['idx'] >= len(self.movs):
            self.pista = None
            return
        mv, n = self.movs[r['idx']]
        nota = self.v.notacion(self.st, mv, n, self.movs)
        t, _, pr = self.v.pieza(self.st, mv[1])
        que = self.v.descripcion(self.st, mv)
        if self.v.destino(mv) is not None:  # 'tu Caballo de g1: capturar Peón en f3'
            que = 'tu %s de %s: %s' % (self.v.nombre_pieza(t, pr).lower(), self.v.nombre_casilla(mv[1]), que.lower())
        txt = 'Pista: %s (%s).' % (nota, que)
        ev = r.get('eval')
        if ev is not None and abs(ev) >= MATE / 2:
            txt += ' %s mate en %d.' % ('Llevas' if ev > 0 else 'Te dan', (round(MATE - abs(ev)) + 1) // 2)
        elif ev is not None:
            txt += ' Después quedas %+.1f.' % ev
        if r.get('linea'):
            txt += ' Idea: ' + self.texto_linea_desde(len(self.hist) + 1, self.notas_linea(n, r['linea'][:4]))
        p.update(idx=r['idx'], texto=txt)
        self.seleccionar(mv[1])

    def por_que(self):
        """Explica la última jugada de la computadora: qué hace, qué amenaza y qué esperaba después."""
        if self.modo not in ('partida', 'entrenamiento') or self.humano is None:
            return
        k = next((j for j in range(len(self.hist) - 1, -1, -1) if self.estados[j].turn != self.humano), None)
        e = self.explicaciones.get(k) if k is not None else None
        if e is None:
            messagebox.showinfo('¿Por qué jugó eso?', 'Todavía no hay una jugada de la computadora que explicar '
                                '(o se jugó antes de abrir esta partida).', parent=self.root)
            return
        import ayudas
        self.marcar_ayuda()
        antes, despues = self.estados[k], self.estados[k + 1]
        movs = self.v.legal(antes)
        mv = movs[self.hist[k]][0]
        partes = ['La computadora jugó %s: %s.' % (self.texto_linea_desde(k, [self.jugadas[k]]),
                                                     self.v.descripcion(antes, mv).lower())]
        if self.v.en_jaque(despues, despues.turn):
            partes.append('Da jaque a tu Rey.')
        amenazas = ayudas.amenazas(self.v, despues, self.humano) if not self.v.en_jaque(despues, despues.turn) else []
        if amenazas and amenazas[0][0] == 'mate':
            partes.append('Amenaza mate: %s.' % amenazas[0][2].lower())
        elif amenazas:
            sq, neto, d = amenazas[0]
            t, _, pr = self.v.pieza(despues, sq)
            partes.append('Ahora amenaza tu %s de %s (%s).' % (self.v.nombre_pieza(t, pr).lower(),
                                                                self.v.nombre_casilla(sq), d.lower()))
        ev = e.get('puntaje')
        if ev is not None and abs(ev) >= MATE / 2:
            partes.append('Ve %s en %d.' % ('mate a su favor' if ev > 0 else 'que tú das mate',
                                           (round(MATE - abs(ev)) + 1) // 2))
        elif ev is not None:
            quien = 'a su favor' if ev > 0.15 else 'a tu favor' if ev < -0.15 else 'igualada'
            partes.append('Su evaluación: %s (%s).' % (
                ('%.1f peones %s' % (abs(ev), quien)) if quien != 'igualada' else quien,
                'calculada a profundidad %d' % e['p'] if e.get('p') else
                'del libro de aperturas' if e.get('libro') else 'de su búsqueda'))
        if e.get('libro'):
            partes.append('Es una jugada de su libro de aperturas: una de las mejores según el análisis previo '
                          '(a profundidad %s), elegida al azar para variar sus partidas.' % (
                              self.app_libro_prof() or '?'))
        elif e.get('linea'):
            partes.append('Lo que esperaba después: %s.' % self.texto_linea_desde(k + 1, e['linea']))
        else:
            partes.append('No dejó una continuación calculada (jugada casi forzada o búsqueda muy corta).')
        if self.niv_elo and self.NIV[self.nivel][3]:
            partes.append('En este nivel juega con algo de azar: no siempre elige la mejor jugada que encontró.')
        messagebox.showinfo('¿Por qué jugó eso?', '\n\n'.join(partes), parent=self.root)

    # ------------------------------------------------------------------ «Aprende a jugar»
    @property
    def L(self):
        import lecciones
        return lecciones

    def tarea_leccion(self):
        return self.L.LECCIONES[self.leccion['i']]['tareas'][self.leccion['k']]

    def iniciar_leccion(self, i, k=0):
        self.cancelar_ia()
        self.guardar_sesion()
        t = self.L.LECCIONES[i]['tareas'][k]
        st = self.L.estado(self.v, t)
        self.modo, self.leccion, self.inicio = 'leccion', {'i': i, 'k': k, 'base': 0}, None
        self.estados, self.jugadas, self.marcas, self.hist = [st], [], [], []
        previa = self.L.previa(self.v, t)
        if previa is not None:  # el ejercicio parte de una jugada negra (captura al paso): se muestra
            antes, idx, mv = previa
            movs = self.v.legal(antes)
            self.estados = [antes, st]
            self.jugadas, self.marcas, self.hist = [self.v.notacion(antes, mv, st, movs)], [self.v.casillas(mv)], [idx]
            self.leccion['base'] = 1
        self.rep = {self.v.clave(x): 1 for x in self.estados}
        self.humano, self.girado = 0, False
        self.dos_jugadores, self.reloj, self.registro, self.ruta_bitacora = False, None, None, None
        self.problema, self.final, self.barra_eval, self.anim = None, None, None, None
        self.mostrar_panel()
        self.tras_jugada(pedir=False)

    def fin_leccion(self):
        """Tras la jugada del ejercicio: si cumple el objetivo, '¡Bien! …'; si no, por qué no."""
        base = self.leccion['base']
        if len(self.hist) <= base:
            return None
        st0 = self.estados[base]
        mv, n = self.v.legal(st0)[self.hist[base]]
        t = self.tarea_leccion()
        if self.L.cumple(self.v, st0, mv, n, t['objetivo']):
            lec = self.L.LECCIONES[self.leccion['i']]
            PG.marcar_leccion(lec['id'], self.leccion['k'] + 1)
            if self.leccion['k'] + 1 < len(lec['tareas']):
                return '¡Bien hecho! Siguiente ejercicio en un momento…'
            return '¡Lección «%s» completada! Pulsa «Siguiente ▶» para pasar a la próxima.' % lec['titulo']
        return 'No era eso: %s no cumple el objetivo. Vuelves a la posición en un momento…' % \
            self.v.descripcion(st0, mv).lower()

    def tras_leccion(self):
        tok = self.final_token
        lec = self.L.LECCIONES[self.leccion['i']]
        if self.fin.startswith('¡Bien'):
            self.root.after(1400, lambda: tok == self.final_token and self.siguiente_leccion())
        elif self.fin.startswith('No era'):
            self.root.after(2200, lambda: tok == self.final_token and self.reintentar_leccion())
        elif self.leccion['i'] + 1 == len(self.L.LECCIONES) and self.leccion['k'] + 1 == len(lec['tareas']):
            self.root.after(250, lambda: messagebox.showinfo(
                'Aprende a jugar', '¡Completaste todas las lecciones! Ya conoces todas las piezas y reglas '
                'especiales del Ajedrez Extendido. Prueba una partida contra la computadora o los problemas.', parent=self.root))

    def reintentar_leccion(self):
        self.iniciar_leccion(self.leccion['i'], self.leccion['k'])

    def siguiente_leccion(self):
        i, k = self.leccion['i'], self.leccion['k'] + 1
        if k >= len(self.L.LECCIONES[i]['tareas']):
            i, k = (i + 1) % len(self.L.LECCIONES), 0
        self.iniciar_leccion(i, k)

    def pista_leccion(self):
        """Selecciona la pieza que cumple el objetivo (y muestra sus destinos)."""
        if self.fin or len(self.hist) > self.leccion['base']:
            return
        t = self.tarea_leccion()
        st = self.st
        for mv, n in self.movs:
            if self.L.cumple(self.v, st, mv, n, t['objetivo']):
                self.seleccionar(mv[1])
                return

    def regla_leccion(self):
        from reglas import VentanaReglas
        VentanaReglas(self.app, self.v, self.L.LECCIONES[self.leccion['i']]['regla'])

    def guardar_sesion(self):
        """Antes de abrir un problema o un final: guarda la partida o el entrenamiento en curso, para que su
        pestaña lo recupere tal como estaba."""
        if self.modo in ('partida', 'entrenamiento'):
            self.reloj_pausar()
            self.sesiones[self.modo] = {k: getattr(self, k) for k in self.SESION}

    def iniciar_problema(self, p, lista):
        self.cancelar_ia()
        self.guardar_sesion()
        v = self.v
        self.modo, self.problema, self.problemas_lista = 'problema', p, lista
        self.inicio = p.get('inicio')
        st = v.inicial() if self.inicio is None else v.construir(self.inicio['piezas'], self.inicio['turno'])
        self.estados, self.jugadas, self.marcas, self.hist = [st], [], [], []
        self.rep = {v.clave(st): 1}
        for i in p['hist']:
            movs = v.legal(st)
            mv, n = movs[i]
            self.jugadas.append(v.notacion(st, mv, n, movs))
            self.marcas.append(v.casillas(mv))
            self.hist.append(i)
            st = n
            self.estados.append(st)
            self.rep[v.clave(st)] = self.rep.get(v.clave(st), 0) + 1
        self.humano = st.turn
        self.girado = self.humano == 1
        self.prob_base, self.prob_estado, self.prob_avisado = len(self.hist), None, False
        self.prob_check, self.prob_intentado = None, False
        self.dos_jugadores, self.reloj, self.registro, self.ruta_bitacora = False, None, None, None
        self.barra_eval, self.anim = None, None
        self.mostrar_panel()
        self.tras_jugada(pedir=False)

    def prob_restantes(self):
        """Jugadas que le quedan al jugador para dar mate."""
        hechas = (len(self.hist) - self.prob_base + 1) // 2
        return self.problema['mate_en'] - hechas

    def marcar_intento(self, resuelto):
        """Anota el intento; el primero de cada problema mueve tu Elo de problemas. Devuelve el texto del cambio."""
        p = self.problema
        primero = not self.prob_intentado
        self.prob_intentado = True
        cambio = PG.marcar_problema(p['id'], resuelto, PG.elo_problema(p) if primero else None)
        if not cambio:
            return ''
        return ' Tu Elo de problemas: %d → %d (%+d).' % (cambio[0], cambio[1], cambio[1] - cambio[0])

    def fin_problema(self):
        if self.prob_estado == 'resuelto':
            return self.fin
        if self.prob_estado:
            return self.prob_estado
        p = self.problema
        if p.get('tipo') == 'tactico':  # una sola jugada: la de la solución
            if len(self.hist) == self.prob_base:
                return None
            if self.hist[self.prob_base] == p['solucion_idx']:
                self.prob_estado = 'resuelto'
                elo = self.marcar_intento(True)
                if p.get('personal'):
                    return '¡Correcto! %s es la buena (en tu partida jugaste %s).%s' % (
                        p['solucion'], p.get('jugaste', '?'), elo)
                linea = p.get('linea') or []
                if len(linea) > 1:  # se muestra la continuación: la idea completa de la táctica
                    tok = self.final_token
                    self.root.after(900, lambda: self.continuar_linea(1, tok))
                    return '¡Correcto! %s. Mira la continuación: %s (gana unos %.1f peones).%s' % (
                        p['solucion'], self.texto_linea(), p.get('gana', 0), elo)
                return '¡Resuelto! %s gana unos %.1f peones (%s).%s' % (
                    p['solucion'], p.get('gana', 0), p.get('tema', ''), elo)
            if p.get('personal') and self.jugadas[self.prob_base].rstrip('+#') == p.get('jugaste', '').rstrip('+#'):
                self.prob_estado = ('Es la misma jugada que hiciste en la partida (perdía %.1f peones). Pulsa '
                                    '«Reintentar» o «Ver solución».%s' % (p.get('gana', 0), self.marcar_intento(False)))
                return self.prob_estado
            if p.get('personal'):  # puede haber otras jugadas buenas: lo dice la computadora
                if self.prob_check is None:
                    try:
                        self.prob_check = self.ia.pedir(self.v.spec, self.inicio, self.hist, p.get('prof', 3),
                                                        5 if self.ia.es_pypy else 10, 0.0)
                    except OSError:
                        self.prob_check = -1
                return 'Comprobando tu jugada…'
            self.prob_estado = ('No es la mejor jugada. Pulsa «Reintentar» o «Ver solución» (la buena gana unos '
                                '%.1f peones).%s' % (p.get('gana', 0), self.marcar_intento(False)))
            return self.prob_estado
        r = self.v.fin(self.st, self.movs, self.rep.get(self.v.clave(self.st), 0), True)
        if r and r[1] == self.humano:
            self.prob_estado = 'resuelto'
            elo = self.marcar_intento(True)
            return '¡Resuelto! %s en %d.%s' % (r[0], (len(self.hist) - self.prob_base + 1) // 2, elo)
        if r:
            self.prob_estado = '%s: no es la solución. Pulsa «Reintentar».%s' % (r[0], self.marcar_intento(False))
            return self.prob_estado
        if self.st.turn == self.humano and self.prob_restantes() <= 0:
            self.prob_estado = 'No diste mate en %d. Pulsa «Reintentar» o «Ver solución».%s' % (
                self.problema['mate_en'], self.marcar_intento(False))
            return self.prob_estado
        return None

    def respuesta_comprobacion(self, r):
        """Tu error convertido en problema: ¿la jugada que hiciste (distinta de la de la solución) también
        sirve? Sirve si pierde menos de 0.7 peones frente a la mejor, como en el análisis."""
        from analisis import recortar
        p = self.problema
        self.prob_check = None
        ev = r.get('eval')
        perdida = p.get('mejor_eval', 0.0) + recortar(ev if ev is not None else 0.0)
        if perdida < 0.7:
            self.prob_estado = 'resuelto'
            self.fin = ('¡Bien! Tu jugada también sirve: queda a %.1f peones de %s, la mejor según el análisis.%s' %
                        (max(0.0, perdida), p['solucion'], self.marcar_intento(True)))
        else:
            self.prob_estado = ('No es suficiente: esa jugada pierde %.1f peones frente a la mejor. Pulsa «Reintentar» o '
                                '«Ver solución».%s' % (perdida, self.marcar_intento(False)))
        self.tras_jugada(pedir=False)

    def texto_linea(self):
        """La línea principal de un problema táctico, con números de jugada."""
        p = self.problema
        linea = p.get('linea') or [{'j': p['solucion']}]
        turno, k = p['turno'], len(p['hist'])
        out = []
        for n, x in enumerate(linea):
            mueve = (turno + n) % 2
            numero = (k + n) // 2 + 1
            if mueve == 0:
                out.append('%d. %s' % (numero, x['j']))
            else:
                out.append(('%d… %s' % (numero, x['j'])) if n == 0 else x['j'])
        return ' '.join(out)

    def continuar_linea(self, n, tok):
        """Juega, con una pausa, la jugada n de la línea del problema (después de resolverlo)."""
        linea = (self.problema or {}).get('linea') or []
        if tok != self.final_token or self.modo != 'problema' or n >= len(linea):
            return
        if len(self.hist) != self.prob_base + n or linea[n]['i'] >= len(self.movs):
            return
        self.jugar(linea[n]['i'])
        self.root.after(900, lambda: self.continuar_linea(n + 1, tok))

    def respuesta_problema(self, r):
        """La defensa de la computadora: si ya no ve el mate a tiempo, la jugada no era la solución."""
        ev = r.get('eval')
        fuerza = ev is not None and ev < -MATE / 2 and (round(MATE + ev) + 1) // 2 <= self.prob_restantes()
        if not fuerza:
            movs = self.movs
            nota = self.v.notacion(self.st, movs[r['idx']][0], movs[r['idx']][1], movs)
            self.prob_estado = 'Esa jugada no fuerza el mate: la defensa %s lo evita. Pulsa «Reintentar» o ' \
                               '«Ver solución».' % nota + self.marcar_intento(False)
        self.jugar(r['idx'], {'puntaje': ev, 'p': r.get('prof')})

    def reintentar_problema(self):
        intentado = self.prob_intentado
        self.iniciar_problema(self.problema, self.problemas_lista)
        self.prob_intentado = intentado  # solo el primer intento cuenta para el Elo

    def ver_solucion(self):
        p = self.problema
        if not self.prob_intentado and self.prob_estado != 'resuelto':  # verla antes de intentarlo cuenta como fallo
            self.marcar_intento(False)
        if p.get('personal'):
            messagebox.showinfo('Solución', 'La mejor jugada según el análisis de tu partida:\n\n%s\n\nEn la partida '
                                'jugaste %s, que perdía unos %.1f peones.' % (p['solucion'], p.get('jugaste', '?'),
                                                                             p.get('gana', 0)), parent=self.root)
            if len(self.hist) == self.prob_base and not self.fin and p['solucion_idx'] < len(self.movs):
                self.seleccionar(self.movs[p['solucion_idx']][0][1])
            return
        if p.get('tipo') == 'tactico':
            texto = 'La mejor jugada es:\n\n%s\n\nTema: %s. Gana unos %.1f peones; la segunda mejor queda al menos ' \
                    '%.1f peones por debajo.' % (p['solucion'], p.get('tema', ''), p.get('gana', 0), p.get('margen', 0))
            if len(p.get('linea') or []) > 1:
                texto += '\n\nLa idea completa: %s' % self.texto_linea()
        else:
            texto = 'Desde la posición del problema, la jugada que fuerza el mate es:\n\n%s\n\nDespués, la ' \
                    'computadora defiende lo mejor posible.' % p['solucion']
        messagebox.showinfo('Solución', texto, parent=self.root)
        if len(self.hist) == self.prob_base and not self.fin:  # resaltar la pieza que mueve
            mv = self.movs[p['solucion_idx']][0] if p.get('solucion_idx', -1) < len(self.movs) else None
            if mv is not None:
                self.seleccionar(mv[1])

    def siguiente_problema(self):
        lista = self.problemas_lista
        i = next((k for k, p in enumerate(lista) if p['id'] == self.problema['id']), -1)
        resueltos = PG.problemas_resueltos()
        orden = lista[i + 1:] + lista[:i + 1]
        siguiente = next((p for p in orden if p['id'] not in resueltos and p['id'] != self.problema['id']),
                         orden[0] if orden else None)
        if siguiente is None:
            return
        if siguiente['variante'] == self.v.spec:
            self.iniciar_problema(siguiente, lista)
        else:
            self.app.resolver(siguiente, lista)

    # ------------------------------------------------------------------ exportar e importar en texto
    def _texto_partida(self):
        import textos as TX
        if self.modo == 'reproduccion' and self.repro_todo:
            notas, r = self.repro_todo['notas'], self.repro_reg or {}
        else:
            notas, r = self.jugadas, self.registro or {}
        nivel = lambda c: (c or {}).get('nivel') or ('profundidad %s' % (c or {}).get('profundidad', '?'))
        if r.get('origen') == 'importada':
            blancas, negras = nivel(r.get('blancas')), nivel(r.get('negras'))
        elif self.modo == 'espectador' or r.get('origen') in ('espectador', 'simulador'):
            blancas, negras = 'Computadora (%s)' % nivel(r.get('blancas')), 'Computadora (%s)' % nivel(r.get('negras'))
        elif self.dos_jugadores or r.get('dos_jugadores'):
            blancas, negras = 'Jugador 1', 'Jugador 2'
        else:
            compu = 'Computadora (%s)' % (nivel(r.get('computadora')) if r.get('computadora') else self.NIV[self.nivel][0])
            humano = r.get('humano') or (COLORES[self.humano] if self.humano is not None else 'blancas')
            blancas, negras = ('Tú', compu) if humano == 'blancas' else (compu, 'Tú')
        resultado = r.get('resultado')
        if not resultado and self.fin and self.modo != 'reproduccion':
            f = self.v.fin(self.st, self.movs, self.rep.get(self.v.clave(self.st), 0), self.modo == 'entrenamiento')
            resultado = f and ('tablas' if f[1] is None else COLORES[f[1]])
        enc = [('Fecha', (r.get('fecha') or time.strftime('%Y-%m-%d %H:%M'))[:16]), ('Blancas', blancas),
               ('Negras', negras), ('Motivo', r.get('motivo'))]
        return TX.partida(self.v, self.estados[0], notas, enc, resultado, self.inicio)

    def exportar(self):
        import textos as TX
        d = tk.Toplevel(self.root)
        d.title('Exportar en texto')
        d.transient(self.root)
        f = ttk.Frame(d, padding=14)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Posición actual (cópiala y pégala en el editor del Entrenamiento):',
                  font=(self.letra, 10, 'bold')).pack(anchor='w')
        pos = TX.fen(self.v, self.st)
        e = ttk.Entry(f, width=90)
        e.insert(0, pos)
        e.pack(fill='x', pady=(2, 4))
        ttk.Button(f, text='Copiar posición', command=lambda: self._copiar(pos, d)).pack(anchor='w')
        ttk.Label(f, text='Partida (la puedes importar desde el menú principal):',
                  font=(self.letra, 10, 'bold')).pack(anchor='w', pady=(12, 0))
        texto = self._texto_partida()
        t = tk.Text(f, width=90, height=16, font=('DejaVu Sans Mono', 10))
        t.insert('1.0', texto)
        t.pack(fill='both', expand=True, pady=(2, 4))
        b = ttk.Frame(f)
        b.pack(fill='x')
        ttk.Button(b, text='Copiar partida', command=lambda: self._copiar(texto, d)).pack(side='left')
        ttk.Button(b, text='Guardar partida…', command=lambda: self._guardar_texto(texto, d)).pack(side='left', padx=6)
        ttk.Button(b, text='Cerrar', command=d.destroy).pack(side='right')
        self.lbl_copiado = ttk.Label(b, text='')
        self.lbl_copiado.pack(side='left', padx=8)

    def _copiar(self, texto, ventana):
        self.root.clipboard_clear()
        self.root.clipboard_append(texto)
        try:
            self.lbl_copiado.configure(text='Copiado.')
        except tk.TclError:
            pass

    def _guardar_texto(self, texto, ventana):
        ruta = filedialog.asksaveasfilename(parent=ventana, title='Guardar partida', defaultextension='.txt',
                                            initialfile='partida_%s.txt' % time.strftime('%Y%m%d_%H%M'),
                                            filetypes=[('Texto', '*.txt'), ('Todos los archivos', '*')])
        if ruta:
            with open(ruta, 'w', encoding='utf-8') as fh:
                fh.write(texto)
            self.lbl_copiado.configure(text='Guardada.')

    def copiar_posicion_editor(self):
        import textos as TX
        self.root.clipboard_clear()
        self.root.clipboard_append(TX.fen(self.v, self.posicion_editor()))
        self.lbl_error.configure(text='Posición copiada al portapapeles.')

    def pegar_posicion(self):
        import textos as TX
        try:
            inicial = self.root.clipboard_get().strip()
        except tk.TclError:
            inicial = ''
        d = tk.Toplevel(self.root)
        d.title('Pegar posición')
        d.transient(self.root)
        f = ttk.Frame(d, padding=14)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Posición en texto (filas de arriba abajo separadas por «/», y «w» o «b» para el turno):'
                  ).pack(anchor='w')
        e = ttk.Entry(f, width=90)
        e.insert(0, inicial if '/' in inicial and '\n' not in inicial else '')
        e.pack(fill='x', pady=(4, 4))
        error = ttk.Label(f, text='', foreground='#B0402A', wraplength=600)
        error.pack(anchor='w')

        def aceptar(ev=None):
            try:
                piezas, turno = TX.leer_fen(self.v, e.get())
            except ValueError as ex:
                error.configure(text=str(ex))
                return
            d.destroy()
            self.ed = piezas
            self.var_color.set(turno)
            self.girado = turno == 1
            self.refrescar_editor('Posición pegada. Juegas con las %s (mueves primero).' % COLORES[turno])
        b = ttk.Frame(f)
        b.pack(fill='x', pady=(6, 0))
        ttk.Button(b, text='Cancelar', command=d.destroy).pack(side='right')
        ttk.Button(b, text='Colocar', command=aceptar).pack(side='right', padx=6)
        d.bind('<Return>', aceptar)
        e.focus_set()

    # ------------------------------------------------------------------ reloj
    def fin_guardado(self):
        return bool(self.v.fin(self.st, self.v.legal(self.st), self.rep.get(self.v.clave(self.st), 0), False)) \
            or bool((self.registro or {}).get('resultado'))

    def reloj_restante(self, color):
        r = self.reloj
        t = r['t'][color]
        if r['marca'] is not None and color == self.st.turn:
            t -= time.time() - r['marca']
        return t

    def reloj_pausar(self):
        r = self.reloj
        if r and r['marca'] is not None:
            r['t'][self.st.turn] -= time.time() - r['marca']
            r['marca'] = None

    def sin_tiempo(self, color):
        """Se acabó el tiempo de un bando: pierde (tablas si al rival solo le queda el Rey)."""
        self.reloj_pausar()
        self.reloj['t'][color] = 0.0
        self.cancelar_ia()
        rival = 1 - color
        solo_rey = all(p is None or p[1] != rival or p[0] == self.v.rey
                       for p in (self.v.pieza(self.st, sq) for sq in range(self.W * self.H)))
        ganador = None if solo_rey else rival
        if ganador is None:
            self.fin = 'Se acabó el tiempo de las %s, pero a las %s solo les queda el Rey. Tablas.' % (
                COLORES[color], COLORES[rival])
        else:
            self.fin = 'Se acabó el tiempo de las %s. Ganan las %s.' % (COLORES[color], COLORES[ganador])
            if not self.dos_jugadores:
                self.fin += ' ¡Ganaste!' if ganador == self.humano else ' Ganó la computadora.'
        if self.registro is not None:
            self.registro.update(resultado='tablas' if ganador is None else COLORES[ganador], motivo='tiempo agotado')
            self.puntuar(ganador)
            self.guardar_bitacora()
        self.dibujar()
        self.actualizar_panel()
        self.root.after(250, self.dialogo_fin if self.registro is not None else
                        lambda: messagebox.showinfo('Fin de la partida', self.fin, parent=self.root))

    def dibujar_reloj(self):
        cv, r = self.cv_reloj, self.reloj
        if not r or not cv.winfo_ismapped():
            return
        cv.delete('all')
        activo = None if (self.fin or r['marca'] is None) else self.st.turn
        for color, x in ((0, 0), (1, 152)):
            t = max(0.0, self.reloj_restante(color))
            txt = '%d:%02d' % (t // 60, t % 60) if t >= 20 else '%.1f' % t
            encendido = color == activo
            cv.create_rectangle(x, 1, x + 148, 45, fill='#EDE6DA' if encendido else '#352C25',
                                outline=ORO if encendido else BORDE, width=2 if encendido else 1)
            cv.create_text(x + 10, 23, text=COLORES[color].capitalize(), anchor='w',
                           fill='#5A4A3A' if encendido else TEXTO_SUAVE, font=(self.letra, 9, 'bold'))
            cv.create_text(x + 140, 23, text=txt, anchor='e', font=(self.app.serif, 20, 'bold'),
                           fill=('#C8281E' if t < 20 else '#1E1B18') if encendido else '#F3E2BE')

    # ------------------------------------------------------------------ barra de evaluación
    def cambio_barra(self):
        self.app.barra_eval = self.var_barra.get()
        if self.var_barra.get() and self.barra_eval is None and not self.fin:
            self.pedir_eval()
        self.dibujar()

    def pedir_pensar(self):
        """Contra la computadora (Ajedrez Extendido): que piense durante tu turno. No responde; se detiene sola cuando
        le llega tu jugada (ver ia.pensar)."""
        if (self.modo != 'partida' or self.dos_jugadores or self.pensando or self.st.turn != self.humano
                or self.v.spec.get('tipo') != 'extendido' or not self.app.ajustes.get('pensar', True)
                or not self.jugadas):
            return
        _, prof, seg, temp, _ = self.NIV[self.nivel]
        if not self.ia.es_pypy and seg:
            seg = seg * 2
        if self.reloj:  # el mismo tiempo que pedirá para su jugada
            resta, inc = self.reloj_restante(1 - self.humano), self.reloj['inc']
            limite = max(0.2, min(resta / 25 + inc * 0.7, resta / 3))
            seg = round(min(seg, limite) if seg else limite, 1)
        try:
            self.ia.pedir(self.v.spec, self.inicio, self.hist, prof, seg, temp, pensar=True)
        except OSError:
            pass

    def pedir_eval(self):
        """Evaluación de la posición para la barra cuando no la da la computadora rival (dos jugadores,
        o tras tu jugada mientras ella no responde)."""
        if not self.var_barra.get() or self.modo not in ('partida', 'entrenamiento') or self.pensando:
            return
        if self.modo == 'partida' and not self.dos_jugadores:
            return  # la evaluación llega con cada jugada de la computadora
        try:
            self.eval_pedida = (self.ia.pedir(self.v.spec, self.inicio, self.hist, 3, 1.5, 0.0), len(self.hist))
        except OSError:
            self.eval_pedida = None

    def eval_actual(self):
        """Evaluación a favor de las blancas para la barra: {'e': peones} o {'m': jugadas al mate}, o None."""
        if self.modo == 'reproduccion':
            an = self.analizador
            if an is not None and an.terminado:
                return {'e': an.eval_blancas(self.repro_pos)}
            return self.ultima_eval
        if self.modo == 'espectador':
            return self.ultima_eval
        return self.barra_eval

    def dibujar_barra(self, x0, y0, alto, S):
        e = self.eval_actual() or {}
        if 'm' in e:
            f, txt = (1.0 if e['m'] > 0 else 0.0), 'M%d' % abs(e['m'])
        elif e.get('e') is not None:
            f, txt = 0.5 + 0.5 * math.tanh(e['e'] / 6), '%+.1f' % e['e']
        else:
            f, txt = 0.5, ''
        ancho = S * 0.32
        x1 = x0 - S * 0.62 - ancho
        cv = self.canvas
        cv.create_rectangle(x1 - 2, y0 - 2, x1 + ancho + 2, y0 + alto + 2, fill=BORDE, outline='')
        cv.create_rectangle(x1, y0, x1 + ancho, y0 + alto, fill='#2A2420', outline='')
        blancas = alto * f
        if self.girado:  # las blancas arriba
            cv.create_rectangle(x1, y0, x1 + ancho, y0 + blancas, fill='#EDE6DA', outline='')
        else:
            cv.create_rectangle(x1, y0 + alto - blancas, x1 + ancho, y0 + alto, fill='#EDE6DA', outline='')
        cv.create_line(x1 - 3, y0 + alto / 2, x1 + ancho + 3, y0 + alto / 2, fill=ORO)
        if txt:
            arriba_blancas = (f >= 0.5) == self.girado
            cv.create_text(x1 + ancho / 2, y0 + (8 if arriba_blancas else alto - 8), text=txt,
                           fill='#1E1B18' if f >= 0.5 else '#EDE6DA', font=(self.letra, max(7, int(S / 7)), 'bold'),
                           angle=90 if ancho < 30 else 0)

    # ------------------------------------------------------------------ animación
    def nueva_anim(self, antes, mv, despues):
        """Animación de una jugada: se desliza de origen a destino; la cadena de la Catapulta, salto por salto
        (las piezas capturadas desaparecen al saltarlas)."""
        v = self.v
        destino = v.destino(mv)
        if destino is None or v.pieza(despues, destino) is None:
            return None
        ruta, caps = ruta_jugada(v, mv)
        cadena = v.es_cadena(mv)
        return {'ruta': ruta, 'caps': caps, 'salto': cadena, 'hechos': 0, 't0': time.time(),
                'previas': {sq: v.pieza(antes, sq) for c in caps for sq in c if v.pieza(antes, sq)},
                'jaque': v.en_jaque(despues, despues.turn), 'pieza': v.pieza(despues, destino),
                'dur': SALTO_CADENA * (len(ruta) - 1) if cadena else ANIMACION}

    def _animar(self):
        a = self.anim
        if a is None or not self.canvas.winfo_exists() or not self.canvas.find_withtag('anim'):
            self.anim_activa = False
            return
        t = time.time() - a['t0']
        saltos = len(a['ruta']) - 1
        if t >= a['dur']:
            self._fin_salto(a, saltos)
            if a['salto'] and a['jaque']:
                self.sonidos.tocar('jaque')
            self.anim, self.anim_activa = None, False
            self.dibujar()
            return
        tramo = a['dur'] / saltos
        i = min(saltos - 1, int(t / tramo))
        self._fin_salto(a, i)
        f = (t - i * tramo) / tramo
        if a['salto']:
            f = f * f * (3 - 2 * f)  # arranca y frena suave en cada salto
        else:
            f = 1 - (1 - f) ** 3  # frena al llegar
        (xa, ya), (xb, yb) = self.xy(a['ruta'][i]), self.xy(a['ruta'][i + 1])
        alto = math.sin(math.pi * f) * self.S * 0.55 if a['salto'] else 0  # el arco del salto
        self.canvas.coords('anim', xa + (xb - xa) * f + self.S / 2, ya + (yb - ya) * f + self.S / 2 - alto)
        self.root.after(15, self._animar)

    def _fin_salto(self, a, hasta):
        """Quita las piezas capturadas por los saltos ya completados (con su sonido)."""
        while a['hechos'] < hasta:
            if a['caps'][a['hechos']]:
                self.canvas.delete('cap%d' % a['hechos'])
                if a['salto']:
                    self.sonidos.tocar('captura')
            a['hechos'] += 1

    def ruta_ultima(self, k):
        """Ruta (casillas de salida y de llegada de cada salto) de la jugada k si fue una cadena, o None."""
        if k <= 0 or k > len(self.hist) or k >= len(self.estados):
            return None
        clave = (id(self.estados[k - 1]), self.hist[k - 1])
        if getattr(self, '_ruta_cache', (None,))[0] != clave:
            ruta = None
            try:
                mv = self.v.legal(self.estados[k - 1])[self.hist[k - 1]][0]
                if self.v.es_cadena(mv):
                    ruta = ruta_jugada(self.v, mv)[0]
            except (IndexError, AttributeError):
                pass
            self._ruta_cache = (clave, ruta)
        return self._ruta_cache[1]

    def dibujar_ruta(self, ruta, encima):
        """La cadena de la última jugada: línea por los saltos (bajo las piezas) y su número (encima)."""
        cv, S = self.canvas, self.S
        centros = [(self.xy(sq)[0] + S / 2, self.xy(sq)[1] + S / 2) for sq in ruta]
        if not encima:
            cv.create_line(*[c for p in centros for c in p], fill=MARCA_CADENA, width=max(3, S // 12),
                           dash=(6, 4), capstyle='round', joinstyle='round', arrow='last',
                           arrowshape=(S * 0.28, S * 0.32, S * 0.11))
            return
        r = max(7, S * 0.15)
        for k, sq in enumerate(ruta[1:], 1):
            x, y = self.xy(sq)
            cx, cy = x + r + 2, y + S - r - 2
            cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=MARCA_CADENA, outline='#3A2410')
            cv.create_text(cx, cy, text=str(k), fill='#FFFFFF', font=(self.letra, max(7, int(r * 1.1)), 'bold'))

    def guardar_bitacora(self):
        if not (self.registro and self.ruta_bitacora):
            return
        try:
            with open(self.ruta_bitacora, 'w', encoding='utf-8') as f:
                BIT.escribir(f, self.registro)
        except OSError:
            return
        self.lbl_bitacora.configure(text='Bitácora: ' + os.path.relpath(self.ruta_bitacora, AQUI))

    def alternar_pausa(self):
        if self.modo not in ESPECTADOR:
            return
        if self.modo == 'espectador' and self.registro is None:
            return self.comenzar_espectador()
        self.pausado = not self.pausado
        if not self.pausado and self.modo == 'espectador' and not self.fin and not self.pensando \
                and self.pendiente is None:
            self.pedir_ia()
        self.actualizar_panel()

    def paso(self):
        """Una sola jugada, con el espectador en pausa."""
        if self.modo not in ESPECTADOR or self.fin:
            return
        self.pausado = True
        if self.modo == 'reproduccion':
            if self.repro_pos < len(self.repro_todo['notas']):
                self.sonidos.tocar(self.repro_todo['sonidos'][self.repro_pos])
                self.ir_a_jugada(self.repro_pos + 1)
        elif self.registro is not None:
            if self.pendiente is not None:
                self._ejecutar_pendiente()
            elif not self.pensando:
                self.paso_unico = True
                self.pedir_ia()
        self.actualizar_panel()

    def atras(self):
        """Reproducción: deshace la última jugada (con la reproducción en pausa)."""
        if self.modo != 'reproduccion' or self.repro_pos == 0:
            return
        self.pausado = True
        self.ir_a_jugada(self.repro_pos - 1)

    @staticmethod
    def _de_bitacora(j):
        return j['i'], j

    @staticmethod
    def _eval_de(j):
        """Datos de evaluación de una jugada de bitácora para mostrarlos."""
        return {k: j[k] for k in ('e', 'm', 'p', 'azar') if k in j}

    def _ejecutar_pendiente(self):
        idx, meta = self.pendiente
        self.pendiente = None
        if idx >= len(self.movs):
            self.pausado = True
            messagebox.showerror('Bitácora', 'La jugada %d de la bitácora no existe con las reglas actuales.'
                                 % (len(self.jugadas) + 1), parent=self.root)
            return
        self.ultima_eval = meta
        self.jugar(idx, meta)

    def texto_eval(self):
        an = self.analizador
        if self.modo == 'reproduccion' and an is not None and an.terminado and self.repro_pos:
            i = self.repro_pos - 1
            x = an.info[i]
            ev = an.eval_blancas(self.repro_pos)
            txt = 'Tras %s: %+.1f para las blancas.' % (an.notas[i], ev)
            if x['simbolo']:
                txt += ' %s (%s): pierde %.1f; mejor era %s.' % (x['simbolo'], x['clase'], x['perdida'], x['mejor'])
            elif x['mejor']:
                txt += ' Buena jugada (la mejor era %s, casi igual).' % x['mejor']
            else:
                txt += ' La mejor jugada.'
            return txt
        e = self.ultima_eval
        if not e:
            return ''
        if e.get('azar'):
            return 'Última jugada: al azar (apertura variada del simulador).'
        if 'm' in e:
            txt = 'La computadora ve mate en %d para las %s.' % (abs(e['m']), 'blancas' if e['m'] > 0 else 'negras')
        elif 'e' in e and abs(e['e']) > 50000:  # bitácoras anteriores al formato «m»
            txt = 'La computadora ve mate para las %s.' % ('blancas' if e['e'] > 0 else 'negras')
        elif 'e' in e:
            v = e['e']
            txt = 'Evaluación: %+.2f (%s)' % (v, 'igualdad' if abs(v) < 0.3 else
                                              'a favor de las ' + ('blancas' if v > 0 else 'negras'))
        else:
            return ''
        return txt + (' · profundidad %d' % e['p'] if e.get('p') else '')

    # ------------------------------------------------------------------ estado de la partida
    @property
    def st(self):
        return self.estados[-1]

    def reiniciar(self, pedir=True):
        self.cancelar_ia()
        if self.inicio is None:
            self.estados = [self.v.inicial()]
        else:
            self.estados = [self.v.construir(self.inicio['piezas'], self.inicio['turno'])]
        self.hist, self.jugadas, self.marcas = [], [], []
        self.rep = {self.v.clave(self.st): 1}
        self.barra_eval, self.anim = None, None
        self.explicaciones, self.pista = {}, None
        if self.reloj and self.modo == 'partida':
            self.reloj['t'] = [self.reloj['base']] * 2
            self.relojes = [list(self.reloj['t'])]
            self.reloj['marca'] = time.time()
        self.tras_jugada(pedir=pedir)

    def jugar(self, idx, meta=None):
        """Hace la jugada idx; meta = {'puntaje', 'p'} con la evaluación de la computadora, si la hay."""
        mv, n = self.movs[idx]
        turno = self.st.turn
        if self.modo == 'final' and self.humano is not None and turno == self.humano:
            self.final['comentario'] = self.comentario_final(self.st, n)
        if self.modo == 'partida' and self.reloj:
            t = self.reloj['t']
            if self.reloj['marca'] is not None:
                t[turno] -= time.time() - self.reloj['marca']
            t[turno] += self.reloj['inc']
            self.relojes = self.relojes[:len(self.estados)] + [list(t)]
            self.reloj['marca'] = time.time()
        if meta and meta.get('puntaje') is not None:
            self.barra_eval = self._eval_de(BIT.jugada(idx, '', turno, meta['puntaje']))
        self.anim = None
        if not self.sin_anim and self.app.ajustes['animacion']:
            self.anim = self.nueva_anim(self.st, mv, n)
        self.sin_anim = False
        if self.anim and self.anim['salto']:
            pass  # cadena: suena cada captura al completar su salto (ver _animar)
        elif self.v.en_jaque(n, n.turn):
            self.sonidos.tocar('jaque')
        elif self.v.es_captura(self.st, mv):
            self.sonidos.tocar('captura')
        else:
            self.sonidos.tocar('movimiento')
        nota = self.v.notacion(self.st, mv, n, self.movs)
        if meta and meta.get('linea') is not None:  # para «¿Por qué jugó eso?»
            self.explicaciones[len(self.hist)] = {'nota': nota, 'puntaje': meta.get('puntaje'), 'p': meta.get('p'),
                                                  'linea': self.notas_linea(n, meta['linea']),
                                                  'libro': meta.get('libro')}
        if self.registro is not None and self.modo in ('espectador', 'partida'):
            e = meta or {}
            self.registro['jugadas'].append(BIT.jugada(idx, nota, turno, e.get('puntaje'), e.get('p')))
            if self.modo == 'partida' and self.reloj:
                self.registro['jugadas'][-1]['r'] = [round(x, 1) for x in self.reloj['t']]
            if self.modo == 'espectador':  # mostrar como en las bitácoras: a favor de las blancas, o mate
                self.ultima_eval = self._eval_de(self.registro['jugadas'][-1])
        self.t_ultima = time.time()
        self.jugadas.append(nota)
        self.marcas.append(self.v.casillas(mv))
        self.hist.append(idx)
        self.estados.append(n)
        k = self.v.clave(n)
        self.rep[k] = self.rep.get(k, 0) + 1
        self.tras_jugada()

    def tras_jugada(self, avisar=True, pedir=True):
        st = self.st
        if self.dos_jugadores and self.modo == 'partida':
            self.humano = st.turn
            if self.girar_auto:
                self.girado = st.turn == 1
        if not self.vista_activa():
            self.vista_k = None
        self.movs = self.v.legal(st)
        self.sel, self.destinos = None, {}
        if self.jugadas and self.jugadas[-1][-1] not in '+#':
            if self.v.en_jaque(st, st.turn):
                self.jugadas[-1] += '#' if not self.movs else '+'
                if self.registro and self.modo in ('espectador', 'partida') and \
                        len(self.registro['jugadas']) == len(self.jugadas):
                    self.registro['jugadas'][-1]['j'] = self.jugadas[-1]
        self.fin = self.evaluar_fin()
        self.calcular_avisos()
        if self.fin and self.reloj:
            self.reloj_pausar()
        if self.modo in ('espectador', 'partida') and self.registro is not None:
            if self.fin and not self.registro.get('resultado'):
                r = self.v.fin(st, self.movs, self.rep.get(self.v.clave(st), 0), False)
                self.registro.update(resultado='tablas' if r[1] is None else COLORES[r[1]], motivo=r[0])
                if self.modo == 'partida':
                    self.puntuar(r[1])
            self.guardar_bitacora()
        self.dibujar()
        self.actualizar_panel()
        if self.modo in ESPECTADOR:
            if not self.fin and self.modo == 'espectador' and pedir and not self.pausado and self.registro:
                self.pedir_ia()
        elif self.fin and avisar:
            if self.modo == 'final':
                pass  # el resultado queda en el panel
            elif self.modo == 'leccion':
                self.tras_leccion()
            elif self.modo == 'problema':
                if self.prob_estado == 'resuelto' and not self.prob_avisado:
                    self.prob_avisado = True
                    self.root.after(250, lambda: messagebox.showinfo('Problema', self.fin, parent=self.root))
            elif self.modo == 'partida' and self.registro is not None:
                self.root.after(250, self.dialogo_fin)
            else:
                self.root.after(250, lambda: messagebox.showinfo('Fin de la partida', self.fin, parent=self.root))
        elif not self.fin and st.turn != self.humano and pedir:
            self.pedir_ia()
        elif not self.fin:
            self.pedir_eval()
            self.pedir_pensar()

    def evaluar_fin(self):
        if self.modo == 'problema':
            return self.fin_problema()
        if self.modo == 'final':
            return self.fin_final()
        if self.modo == 'leccion':
            return self.fin_leccion()
        entrenamiento = self.modo == 'entrenamiento'
        r = self.v.fin(self.st, self.movs, self.rep.get(self.v.clave(self.st), 0), entrenamiento)
        if r is None:
            return None
        motivo, ganador, detalle = r
        detalle = (' ' + detalle) if detalle else ''
        if ganador is None:
            return motivo + '.' + detalle + (' Fin del ejercicio.' if entrenamiento else ' Tablas.')
        if self.humano is None or (self.dos_jugadores and self.modo == 'partida'):
            return '%s.%s Ganan las %s.' % (motivo, detalle, COLORES[ganador])
        quien = '¡Ganaste!' if ganador == self.humano else 'Ganó la computadora.'
        return '%s.%s Ganan las %s. %s' % (motivo, detalle, COLORES[ganador], quien)

    def deshacer(self):
        if self.modo == 'leccion':  # sin retirar la jugada negra con la que empieza el ejercicio
            return self.reintentar_leccion()
        if self.modo in ('editor', 'problema') or self.modo in ESPECTADOR or len(self.estados) == 1:
            return
        self.cancelar_ia()
        self._quitar()
        while len(self.estados) > 1 and self.st.turn != self.humano and not self.dos_jugadores:
            self._quitar()
        self.barra_eval, self.anim, self.pista = None, None, None
        self.explicaciones = {k: e for k, e in self.explicaciones.items() if k < len(self.hist)}
        if self.reloj and self.modo == 'partida':
            self.relojes = self.relojes[:len(self.estados)]
            if self.relojes:
                self.reloj['t'] = list(self.relojes[-1])
            self.reloj['marca'] = time.time()
        if self.modo == 'final':
            self.final['comentario'] = ''
        if self.registro is not None and self.modo == 'partida':  # la partida guardada también retrocede
            self.registro['jugadas'] = self.registro['jugadas'][:len(self.jugadas)]
            self.registro['deshacer'] = self.registro.get('deshacer', 0) + 1
            self.registro.pop('resultado', None)
            self.registro.pop('motivo', None)
        self.rep = {}
        for s in self.estados:
            k = self.v.clave(s)
            self.rep[k] = self.rep.get(k, 0) + 1
        self.tras_jugada()

    def _quitar(self):
        self.estados.pop(); self.hist.pop(); self.jugadas.pop(); self.marcas.pop()

    # ------------------------------------------------------------------ computadora
    def pedir_ia(self):
        if self.modo == 'final':  # juega con las tablas exactas: al instante, con una pausa para verlo
            espera = 500 if self.humano is not None else int(1000 * self.velocidad_final())
            tok = self.final_token
            self.root.after(espera, lambda: self.jugada_tabla(tok))
            return
        _, prof, seg, temp, _ = self.NIV[self.niveles[self.st.turn] if self.modo == 'espectador' else self.nivel]
        if self.modo == 'problema':  # la mejor defensa, con profundidad para ver el mate que queda
            prof, seg, temp = 2 * max(1, self.prob_restantes()), 30, 0.0
        if not self.ia.es_pypy and seg:
            seg = seg * 2
        if self.modo == 'partida' and self.reloj:
            resta, inc = self.reloj_restante(self.st.turn), self.reloj['inc']
            limite = max(0.2, min(resta / 25 + inc * 0.7, resta / 3))
            seg = round(min(seg, limite) if seg else limite, 1)
        try:
            extra = {'linea': True} if self.modo in ('partida', 'entrenamiento') else {}
            if self.modo in ('partida', 'espectador') and self.app.ajustes.get('libro', True):
                extra['libro'] = True
            rid = self.ia.pedir(self.v.spec, self.inicio, self.hist, prof, seg, temp, **extra)
        except OSError as e:
            messagebox.showerror('Error', 'No se pudo iniciar la computadora:\n%s' % e, parent=self.root)
            return
        self.pensando = (rid, time.time())
        self.actualizar_panel()

    def cancelar_ia(self):
        self.final_token += 1  # anula las jugadas de los finales que estaban programadas
        if self.pensando:
            self.ia.cancelar()
        self.pensando = None

    def sondear(self):
        r = self.ia.respuesta()
        while r is not None:
            if self.pensando and r.get('id') == self.pensando[0]:
                self.pensando = None
                if self.modo == 'espectador':  # se juega cuando pase el tiempo de la velocidad elegida
                    self.pendiente = (r['idx'], {'puntaje': r.get('eval'), 'p': r.get('prof')})
                    if self.paso_unico:
                        self.paso_unico = False
                        self._ejecutar_pendiente()
                elif self.modo == 'problema':
                    self.respuesta_problema(r)
                else:
                    self.jugar(r['idx'], {'puntaje': r.get('eval'), 'p': r.get('prof'), 'linea': r.get('linea'),
                                          'libro': r.get('libro')})
            elif self.pista and r.get('id') == self.pista.get('id'):
                self.respuesta_pista(r)
            elif self.modo == 'problema' and self.prob_check is not None and r.get('id') == self.prob_check:
                self.respuesta_comprobacion(r)
            elif self.eval_pedida and r.get('id') == self.eval_pedida[0]:
                if self.eval_pedida[1] == len(self.hist) and r.get('eval') is not None:
                    self.barra_eval = self._eval_de(BIT.jugada(0, '', self.st.turn, r['eval']))
                    self.dibujar()
                self.eval_pedida = None
            elif self.analizador is not None:
                self.analizador.recibir(r)
            r = self.ia.respuesta()
        if self.modo == 'partida' and self.reloj and not self.fin:
            if self.reloj['marca'] is not None and self.reloj_restante(self.st.turn) <= 0:
                self.sin_tiempo(self.st.turn)
            self.dibujar_reloj()
        if self.modo == 'espectador' and not self.fin and not self.pausado:
            if self.pendiente is not None and time.time() >= self.t_ultima + self.var_velocidad.get():
                self._ejecutar_pendiente()
        elif self.modo == 'reproduccion' and not self.pausado:
            if self.repro_pos >= len(self.repro_todo['notas']):
                self.pausado = True
                self.actualizar_panel()
            elif time.time() >= self.t_ultima + self.var_velocidad.get():
                self.sonidos.tocar(self.repro_todo['sonidos'][self.repro_pos])
                self.t_ultima = time.time()
                self.ir_a_jugada(self.repro_pos + 1)
        if self.pensando:
            if not self.ia.vivo():
                self.pensando = None
                messagebox.showerror('Error', 'El proceso de la computadora se detuvo inesperadamente. '
                                     'Usa Deshacer o Nueva partida para continuar.', parent=self.root)
            else:
                self.actualizar_estado()

    # ------------------------------------------------------------------ tablero
    def xy(self, sq):
        c, r = sq % self.W, sq // self.W
        if self.girado:
            c = self.W - 1 - c
        else:
            r = self.H - 1 - r
        return self.ox + c * self.S, self.oy + r * self.S

    def casilla_en(self, x, y):
        if x < self.ox or y < self.oy:
            return None
        c, r = int((x - self.ox) // self.S), int((y - self.oy) // self.S)
        if not (0 <= c < self.W and 0 <= r < self.H):
            return None
        if self.girado:
            c = self.W - 1 - c
        else:
            r = self.H - 1 - r
        return r * self.W + c

    def al_redimensionar(self, ev):
        if self._redibujo:
            self.root.after_cancel(self._redibujo)
        self._redibujo = self.root.after(60, self.dibujar)

    def dibujar(self):
        self._redibujo = None
        cv, v, W, H = self.canvas, self.v, self.W, self.H
        if not cv.winfo_exists():  # la pantalla ya se cerró (una jugada programada llegó tarde)
            return
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 50:
            return
        barra = self.var_barra.get() and self.modo != 'editor'
        S = max(20, int(min(w / (W + (1.9 if barra else 0.9)), h / (H + 0.9))))
        self.S, self.ox, self.oy = S, (w - W * S) // 2 + (int(S * 0.5) if barra else 0), (h - H * S) // 2
        tam = int(S * 0.9)
        self.img.limpiar({tam, 22, 42})
        cv.delete('all')
        st = self.st
        clara, oscura, ult_c, ult_o, sel_c, sel_o = self.colores
        ultima = self.marcas[-1] if self.marcas else set()
        viendo = self.vista_activa()
        if viendo:  # una posición anterior de la partida
            st = self.estados[self.vista_k]
            ultima = self.marcas[self.vista_k - 1] if self.vista_k else set()
        x0, y0 = self.ox, self.oy
        cv.create_rectangle(x0 - 3, y0 - 3, x0 + W * S + 3, y0 + H * S + 3, fill='#5A8FD0' if viendo else BORDE,
                            outline='')
        bandos = (0, 1) if self.modo == 'editor' else (st.turn,)
        jaques = {v.casilla_rey(st, c) for c in bandos if v.casilla_rey(st, c) is not None and v.en_jaque(st, c)}
        for sq in range(W * H):
            x, y = self.xy(sq)
            es_clara = (sq % W + sq // W) % 2 == 0
            if sq == self.sel and not viendo:
                col = sel_c if es_clara else sel_o
            elif sq in ultima:
                col = ult_c if es_clara else ult_o
            else:
                col = clara if es_clara else oscura
            cv.create_rectangle(x, y, x + S, y + S, fill=col, outline='')
            if sq in jaques:
                for k, c in ((0.08, '#E8A090'), (0.18, '#E06050'), (0.28, '#C8281E')):
                    cv.create_oval(x + S * k, y + S * k, x + S * (1 - k), y + S * (1 - k), fill=c, outline='')
        for sq in ([] if viendo else self.casillas_aviso()):  # piezas en peligro (ayudas)
            x, y = self.xy(sq)
            cv.create_rectangle(x + 2, y + 2, x + S - 2, y + S - 2, outline='#E0503C', width=max(3, S // 16))
        p = self.pista
        if p and p.get('idx') is not None and p['k'] == len(self.hist) and not self.fin and not viendo:
            d = self.v.destino(self.movs[p['idx']][0])
            for sq in {self.movs[p['idx']][0][1], d} - {None}:
                x, y = self.xy(sq)
                cv.create_rectangle(x + 2, y + 2, x + S - 2, y + S - 2, outline=ORO, width=max(3, S // 14))
        if self.modo == 'leccion' and not self.fin and not viendo:  # las casillas del objetivo
            for sq in self.L.casillas_objetivo(self.tarea_leccion()):
                x, y = self.xy(sq)
                cv.create_rectangle(x + 2, y + 2, x + S - 2, y + S - 2, outline=ORO, width=max(3, S // 16))
        fuente = (self.letra, max(8, S // 6), 'bold')
        for i in range(W):
            c = W - 1 - i if self.girado else i
            cv.create_text(x0 + i * S + S / 2, y0 + H * S + S * 0.25, text=LETRAS[c], fill='#D8C7A8', font=fuente)
        for i in range(H):
            r = i if self.girado else H - 1 - i
            cv.create_text(x0 - S * 0.25, y0 + i * S + S / 2, text=str(r + 1), fill='#D8C7A8', font=fuente)
        if barra:
            self.dibujar_barra(x0, y0, H * S, S)
        anim = self.anim if self.anim and time.time() - self.anim['t0'] < self.anim['dur'] and not viendo else None
        ruta = self.ruta_ultima(self.vista_k if viendo else len(self.hist))
        if ruta:
            self.dibujar_ruta(ruta, False)
        con_derecho = set()
        if not self.fin and st.turn == self.humano and not self.pensando and not viendo:
            con_derecho = {mv[1] for mv, _ in self.movs if v.destino(mv) is None}
        for sq in range(W * H):
            p = v.pieza(st, sq)
            if p is None or sq == self.oculta or (anim and sq == anim['ruta'][-1]):
                continue
            x, y = self.xy(sq)
            cv.create_image(x + S / 2, y + S / 2, image=self.img.get(v.imagen(*p), tam))
            if sq in con_derecho:
                r = S * 0.13
                cv.create_oval(x + S - 2.2 * r, y + 0.2 * r, x + S - 0.2 * r, y + 2.2 * r, fill='#E2B33C',
                               outline='#6B4A0E')
                cv.create_text(x + S - 1.2 * r, y + 1.2 * r, text='★', fill='#6B4A0E',
                               font=(self.letra, max(6, int(r * 1.2)), 'bold'))
        for sq, opciones in ({} if viendo else self.destinos).items():
            x, y = self.xy(sq)
            col = MARCA_CADENA if any(v.es_cadena(self.movs[i][0]) for i in opciones) else MARCA
            if v.pieza(st, sq) is not None:
                cv.create_oval(x + 3, y + 3, x + S - 3, y + S - 3, outline=col, width=max(3, S // 14))
            else:
                r = S * 0.16
                cv.create_oval(x + S / 2 - r, y + S / 2 - r, x + S / 2 + r, y + S / 2 + r, fill=col, outline='')
        if viendo:
            cv.create_text(x0 + W * S / 2, max(9, y0 / 2 - 1), text='Revisando la partida · Esc o clic para volver',
                           fill='#9CC3F0', font=(self.letra, max(8, min(12, S // 5)), 'bold'))
        if ruta:
            self.dibujar_ruta(ruta, True)
        if anim:
            transcurrido = time.time() - anim['t0']
            tramo = anim['dur'] / max(1, len(anim['ruta']) - 1)
            for h, caps in enumerate(anim['caps']):  # las capturadas siguen ahí hasta que las salta
                if transcurrido < (h + 1) * tramo:
                    for sq in caps:
                        if sq in anim['previas'] and sq != anim['ruta'][-1]:
                            x, y = self.xy(sq)
                            cv.create_image(x + S / 2, y + S / 2, image=self.img.get(v.imagen(*anim['previas'][sq]), tam),
                                            tags='cap%d' % h)
            x, y = self.xy(anim['ruta'][min(len(anim['ruta']) - 2, int(transcurrido / tramo))])
            cv.create_image(x + S / 2, y + S / 2, image=self.img.get(v.imagen(*anim['pieza']), tam), tags='anim')
            if not self.anim_activa:
                self.anim_activa = True
                self.root.after(15, self._animar)

    def girar(self):
        self.girado = not self.girado
        self.dibujar()

    # ------------------------------------------------------------------ interacción
    def clic(self, ev):
        if self.modo == 'editor':
            sq = self.casilla_en(ev.x, ev.y)
            if sq is not None and sq in self.ed:
                self.arr = {'desde': sq, 'x': ev.x, 'y': ev.y, 'activo': False}  # se decide al soltar
            else:
                self.clic_editor(sq)
            return
        if self.vista_activa():  # revisando una posición anterior: el clic vuelve a la partida
            self.ver_posicion(None)
            return
        if self.modo in ESPECTADOR or self.fin or self.pensando or self.st.turn != self.humano:
            return
        sq = self.casilla_en(ev.x, ev.y)
        if sq is not None and sq in self.destinos:
            opciones = self.destinos[sq]
            if len(opciones) == 1:
                self.jugar(opciones[0])
            else:
                menu = tk.Menu(self.root, tearoff=0)
                for i in opciones:
                    menu.add_command(label=self.v.descripcion(self.st, self.movs[i][0]),
                                     command=lambda i=i: self.jugar(i))
                menu.tk_popup(ev.x_root, ev.y_root)
            return
        p = self.v.pieza(self.st, sq) if sq is not None else None
        if p is not None and p[1] == self.humano:
            ya = sq == self.sel
            if not ya:
                self.seleccionar(sq)
            # se puede arrastrar; si se suelta sin moverla y ya estaba elegida, se deselecciona
            self.arr = {'desde': sq, 'x': ev.x, 'y': ev.y, 'activo': False, 'juego': True, 'ya': ya}
        else:
            self.deseleccionar()

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
            pieza = self.v.pieza(self.st, a['desde']) if a.get('juego') else self.ed[a['desde']]
            self.canvas.create_image(ev.x, ev.y, image=self.img.get(self.v.imagen(*pieza),
                                                                     int(self.S * 0.9)), tags='arrastre')
            self.canvas.configure(cursor='fleur')
        self.canvas.coords('arrastre', ev.x, ev.y)

    def soltar(self, ev):
        a, self.arr = self.arr, None
        if a is not None and a.get('juego'):
            return self.soltar_jugada(a, ev)
        if a is None or self.modo != 'editor':
            return
        if not a['activo']:
            self.clic_editor(a['desde'])
            return
        self.oculta = None
        self.canvas.configure(cursor='')
        destino = self.casilla_en(ev.x, ev.y)
        t, c, pr = self.ed.pop(a['desde'])
        if destino is not None:
            self.ed[destino] = self.v.ajustar(t, c, pr, destino)
        self.refrescar_editor()

    def soltar_jugada(self, a, ev):
        if not a['activo']:
            if a['ya']:
                self.deseleccionar()
            return
        self.oculta = None
        self.canvas.configure(cursor='')
        sq = self.casilla_en(ev.x, ev.y)
        if sq is None or sq not in self.destinos or self.fin or self.pensando or self.st.turn != self.humano:
            self.dibujar()
            return
        opciones = self.destinos[sq]
        if len(opciones) == 1:
            self.sin_anim = True  # la pieza ya está donde la soltaste
            self.jugar(opciones[0])
        else:
            self.dibujar()
            menu = tk.Menu(self.root, tearoff=0)
            for i in opciones:
                menu.add_command(label=self.v.descripcion(self.st, self.movs[i][0]), command=lambda i=i: self.jugar(i))
            menu.tk_popup(ev.x_root, ev.y_root)

    def clic_derecho(self, ev):
        if self.modo == 'editor':
            self.clic_editor(self.casilla_en(ev.x, ev.y), borrar=True)
        else:
            self.deseleccionar()

    def seleccionar(self, sq):
        self.sel, self.destinos = sq, {}
        acciones = []
        for i, (mv, _) in enumerate(self.movs):
            if mv[1] != sq:
                continue
            d = self.v.destino(mv)
            if d is None:
                acciones.append(i)
            else:
                self.destinos.setdefault(d, []).append(i)
        self.mostrar_acciones(acciones)
        self.actualizar_estado()
        self.dibujar()

    def deseleccionar(self):
        if self.sel is not None:
            self.sel, self.destinos = None, {}
            self.mostrar_acciones([])
            self.actualizar_estado()
            self.dibujar()

    def mostrar_acciones(self, acciones):
        for w in self.acciones.winfo_children():
            w.destroy()
        for i in acciones:
            ttk.Button(self.acciones, text=self.v.descripcion(self.st, self.movs[i][0]),
                       command=lambda i=i: self.jugar(i)).pack(fill='x', pady=1)

    # ------------------------------------------------------------------ panel
    def dibujar_puntos(self):
        """Marcador del desempate por puntos (7.6): puntos de cada bando, balanza y quién va arriba."""
        cv = self.cv_puntos
        if cv is None:
            return
        cv.delete('all')
        st, v = self.st, self.v
        a, b = v.puntos(st, 0), v.puntos(st, 1)
        previo = self.estados[-2] if len(self.estados) > 1 else None
        for color, x in ((0, 0), (1, 152)):
            arriba = (a > b) if color == 0 else (b > a)
            cv.create_rectangle(x, 0, x + 148, 62, fill='#352C25', outline=ORO if arriba else BORDE,
                                width=2 if arriba else 1)
            if color == 1:
                base_clara(cv, x + 4, 11, x + 44, 51)
            cv.create_image(x + 24, 31, image=self.img.get(v.imagen(v.rey or 'K', color, False), 36))
            cv.create_text(x + 46, 16, text=COLORES[color].capitalize(), anchor='w', fill=TEXTO_SUAVE,
                           font=(self.letra, 9, 'bold'))
            cv.create_text(x + 46, 40, text=_formato(v.puntos(st, color)), anchor='w', fill='#F3E2BE',
                           font=(self.app.serif, 22, 'bold'))
            if previo is not None:
                ganados = v.puntos(st, color) - v.puntos(previo, color)
                if ganados > 0:
                    cv.create_text(x + 142, 44, text='+' + _formato(ganados), anchor='e', fill='#8FD060',
                                   font=(self.letra, 11, 'bold'))
        total = a + b
        f = 0.5 if total == 0 else a / total
        cv.create_rectangle(0, 72, 300, 82, fill='#1E1B18', outline=BORDE)
        cv.create_rectangle(1, 73, 1 + 298 * f, 81, fill='#EDE6DA', outline='')
        cv.create_line(150, 70, 150, 84, fill=ORO)
        if a == b:
            txt = 'Igualados a %s puntos' % _formato(a) if a else 'Aún no hay capturas'
        else:
            txt = 'Ventaja de las %s: +%s (ganarían el desempate)' % (COLORES[0 if a > b else 1], _formato(abs(a - b)))
        cv.create_text(150, 100, text=txt, fill=ORO, font=(self.letra, 9, 'bold'))

    def actualizar_estado(self):
        st = self.st
        if self.vista_activa():
            k = self.vista_k
            donde = ('la jugada %s' % self.texto_linea_desde(k - 1, [self.jugadas[k - 1]])) if k else 'el inicio'
            self.lbl_estado.configure(text='Revisando la posición tras %s. Usa ← → para moverte; Esc, Fin o un clic '
                                           'en el tablero para volver a la posición actual.' % donde)
            return
        if self.modo in ESPECTADOR:
            return self.estado_espectador()
        if self.fin:
            txt = self.fin
        elif self.pensando:
            txt = 'La computadora está pensando… %d s' % (time.time() - self.pensando[1])
        elif self.modo == 'final':
            txt = self.estado_final()
        elif self.modo == 'leccion':
            txt = self.tarea_leccion()['texto']
        else:
            txt = (('En tu partida jugaste %s, un error. Encuentra una jugada mejor con las %%s.' %
                    self.problema.get('jugaste', '?')) if self.modo == 'problema' and self.problema.get('personal') else
                   'Encuentra la mejor jugada de las %s.' if self.modo == 'problema' and
                   self.problema.get('tipo') == 'tactico' else
                   'Da mate en %d con las %%s.' % self.prob_restantes() if self.modo == 'problema' else
                   'Turno de las %s.' if self.dos_jugadores and self.modo == 'partida' else 'Tu turno (%s).') % \
                COLORES[self.humano]
            if self.v.en_jaque(st, st.turn):
                txt += ' ¡Estás en jaque!'
            elif self.sel is None:
                txt += ' Elige una pieza.'
            if self.avisos and self.modo in ('partida', 'entrenamiento'):
                import ayudas
                txt += '\n' + ayudas.texto(self.v, st, self.humano, self.avisos)
            p = self.pista
            if p and p['k'] == len(self.hist):
                txt += '\n' + p.get('texto', 'Buscando una pista…')
        self.lbl_estado.configure(text=txt)

    def estado_espectador(self):
        st = self.st
        turno = COLORES[st.turn]
        if self.fin:
            txt = self.fin
        elif self.modo == 'reproduccion' and self.repro_todo and self.repro_pos >= len(self.repro_todo['notas']):
            r = self.repro_reg
            txt = 'Fin de la bitácora: %s (%s).' % (r.get('resultado', '—'), r.get('motivo', '—'))
        elif self.modo == 'espectador' and self.registro is None:
            txt = 'Modo espectador: dos computadoras juegan entre sí.'
        elif self.pensando:
            txt = 'Piensan las %s… %d s' % (turno, time.time() - self.pensando[1])
        elif self.pausado:
            txt = 'En pausa. Turno de las %s.' % turno
        else:
            txt = 'Turno de las %s.' % turno
        if self.v.en_jaque(st, st.turn) and not self.fin:
            txt += ' ¡Jaque!'
        self.lbl_estado.configure(text=txt)
        self.btn_pausa.configure(text='▶ Reanudar' if self.pausado else '⏸ Pausa')
        self.btn_atras.state(['!disabled'] if self.modo == 'reproduccion' else ['disabled'])
        self.btn_analizar.state(['!disabled'] if self.modo == 'reproduccion' else ['disabled'])
        self.lbl_eval.configure(text=self.texto_eval())

    def actualizar_panel(self):
        if self.modo == 'editor':
            return
        if self.modo == 'espectador':
            self.lbl_info.configure(text='Espectador · Blancas: %s · Negras: %s%s' % (
                self.NIV[self.niveles[0]][0], self.NIV[self.niveles[1]][0], '' if self.ia.es_pypy else ' · sin PyPy'))
        elif self.modo == 'reproduccion':
            r = self.repro_reg or {}
            nivel = lambda c: (c or {}).get('nivel') or ('profundidad %s' % (c or {}).get('profundidad', '?'))
            if r.get('dos_jugadores'):
                b_, n_ = 'persona', 'persona'
            elif r.get('origen') == 'partida':
                rivales = {r.get('humano'): 'tú', 'blancas' if r.get('humano') == 'negras' else 'negras':
                           nivel(r.get('computadora'))}
                b_, n_ = rivales.get('blancas', '?'), rivales.get('negras', '?')
            else:
                b_, n_ = nivel(r.get('blancas')), nivel(r.get('negras'))
            self.lbl_info.configure(text='Reproducción · Blancas: %s · Negras: %s · media jugada %d de %d' % (
                b_, n_, self.repro_pos, len(self.repro_todo['notas']) if self.repro_todo else 0))
        else:
            nombre = self.NIV[self.nivel][0]
            if self.modo == 'final':
                self.lbl_info.configure(text=self.info_final())
            elif self.modo == 'leccion':
                lec = self.L.LECCIONES[self.leccion['i']]
                self.lbl_info.configure(text='Aprende a jugar · %s · ejercicio %d de %d' % (
                    lec['titulo'], self.leccion['k'] + 1, len(lec['tareas'])))
            elif self.modo == 'problema':
                p = self.problema
                if p.get('personal'):
                    titulo = 'Tu error: encuentra una jugada mejor'
                elif p.get('tipo') == 'tactico':
                    titulo = 'Problema táctico (%s): gana material' % p.get('tema', '')
                else:
                    titulo = 'Problema: mate en %d' % p['mate_en']
                self.lbl_info.configure(text='%s · juegas con %s · dificultad %d\n%s' % (
                    titulo, COLORES[self.humano], PG.elo_problema(p), p.get('origen', '')))
            elif self.dos_jugadores and self.modo == 'partida':
                self.lbl_info.configure(text='Dos jugadores en este equipo%s' % (
                    (' · Reloj: ' + RELOJES[self.reloj_opcion or 0][0]) if self.reloj else ''))
            else:
                self.lbl_info.configure(text='%sJuegas con %s · Nivel %s%s%s' % (
                    'Entrenamiento · ' if self.modo == 'entrenamiento' else '', COLORES[self.humano], nombre,
                    (' · Reloj: ' + RELOJES[self.reloj_opcion or 0][0]) if self.reloj and self.modo == 'partida' else '',
                    '' if self.ia.es_pypy else ' · sin PyPy'))
        if self.modo in ESPECTADOR:
            self.estado_espectador()
        self.actualizar_estado()
        st = self.st
        for color, cv in self.marcador.items():
            cv.delete('all')
            x, y = 2, 2
            ancho = max(200, cv.winfo_width())
            puestas = []
            for t, pr in self.v.capturas(st, color):
                if x + 22 > ancho - 72:
                    x, y = 2, y + 24
                puestas.append((x, y, t, pr))
                x += 18
            if color == 0 and puestas:  # piezas negras: sobre una franja clara para que se vean
                for fila_y in sorted({p[1] for p in puestas}):
                    ultimo = max(p[0] for p in puestas if p[1] == fila_y)
                    base_clara(cv, 0, fila_y - 1, ultimo + 24, fila_y + 23)
            for x, y, t, pr in puestas:
                cv.create_image(x, y, image=self.img.get(self.v.imagen(t, 1 - color, pr), 22), anchor='nw')
            if self.cv_puntos is None:
                cv.create_text(ancho - 4, 13, text='%g pts' % self.v.puntos(st, color), anchor='e',
                               fill='#F3E2BE', font=(self.letra, 10, 'bold'))
        self.dibujar_puntos()
        if self.lbl_derechos is not None:
            d = self.v.derechos(st, self.humano if self.humano is not None else st.turn)
            self.lbl_derechos.configure(text=(', '.join(d) + '.\nSelecciona la pieza (★) para extenderla; '
                                              'cuesta el turno.') if d else 'Ninguna por ahora.')
        if self.sel is None:
            self.mostrar_acciones([])
        jugadas = self.jugadas
        an = self.analizador
        if self.modo == 'reproduccion' and an is not None and an.terminado:
            jugadas = [j + an.info[k]['simbolo'] for k, j in enumerate(jugadas)]
        self.txt.configure(state='normal')
        self.txt.delete('1.0', 'end')
        d = 1 if self.estados and self.estados[0].turn == 1 else 0  # la posición empezó con las negras
        lista = ['…'] * d + list(jugadas)
        for i in range(0, len(lista), 2):  # cada jugada lleva la etiqueta jK (K: medias jugadas tras ella)
            self.txt.insert('end', ('\n' if i else '') + '%3d. ' % (i // 2 + 1))
            self.txt.insert('end', '%-13s' % lista[i], ('j', 'j%d' % (i + 1 - d)) if i >= d else ())
            if i + 1 < len(lista):
                self.txt.insert('end', ' ')
                self.txt.insert('end', lista[i + 1], ('j', 'j%d' % (i + 2 - d)))
        self.txt.configure(state='disabled')
        self.marcar_lista()


def ruta_jugada(v, mv):
    """(casillas por las que pasa la pieza, capturas de cada tramo). Para la cadena de la Catapulta, cada salto
    con lo que captura; para las demás jugadas, un solo tramo."""
    if v.es_cadena(mv):
        return [mv[1]] + [llegada for llegada, _ in mv[3]], [list(caps) for _, caps in mv[3]]
    return [mv[1], v.destino(mv)], [[]]


def _formato(x):
    return '%g' % x


def main():
    ap = argparse.ArgumentParser(description='Ajedrez: juego de escritorio')
    ap.add_argument('--bitacora', '--bitácora', dest='bitacora', metavar='ARCHIVO',
                    help='reproduce una bitácora (del simulador o del modo espectador)')
    ap.add_argument('--partida', type=int, default=None,
                    help='número de partida dentro de la bitácora (si tiene varias)')
    a = ap.parse_args()
    root = tk.Tk(className='ajedrez11x11')
    app = Aplicacion(root)
    if a.bitacora:
        root.after(300, lambda: app.abrir_bitacora(os.path.abspath(a.bitacora), a.partida))
    root.mainloop()


if __name__ == '__main__':
    main()
