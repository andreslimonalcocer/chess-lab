"""Elementos visuales compartidos: colores, temas de tablero, estilos e imágenes de piezas."""
import os, shutil, sys
import tkinter as tk
from tkinter import ttk, font as tkfont

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None

FONDO = '#2B2622'
FONDO_OSCURO = '#1E1916'
TARJETA = '#2F2721'
FONDO_NEGRAS = '#D4C3A1'  # base clara para que las piezas negras se vean sobre los fondos oscuros
BORDE = '#5A4636'
ORO = '#E2C27A'
TEXTO = '#EDE6DA'
TEXTO_SUAVE = '#C9B99C'
MARCA, MARCA_CADENA = '#2E5E2A', '#C8521F'

# nombre visible, casilla clara, casilla oscura
TEMAS = {
    'madera': ('Madera', '#EEDCB8', '#B88A62'),
    'nogal': ('Nogal', '#D9B58C', '#7A5236'),
    'verde': ('Torneo', '#EEEED2', '#769656'),
    'azul': ('Azul', '#DEE3E6', '#8CA2AD'),
    'marmol': ('Mármol', '#E8E6E1', '#9E9A93'),
    'coral': ('Coral', '#F1E0D6', '#C77B6B'),
}


def mezcla(c1, c2, f):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02X%02X%02X' % tuple(round(x + (y - x) * f) for x, y in zip(a, b))


def colores_tema(tema):
    """(clara, oscura, última clara, última oscura, selección clara, selección oscura)."""
    _, clara, oscura = TEMAS.get(tema, TEMAS['madera'])
    return (clara, oscura, mezcla(clara, '#F0E050', 0.5), mezcla(oscura, '#E0C830', 0.45),
            mezcla(clara, '#8FD060', 0.55), mezcla(oscura, '#6FB040', 0.55))


class Imagenes:
    """Imágenes de piezas escaladas (con Pillow si está disponible), con caché por tamaño."""

    def __init__(self):
        self.fuentes, self.cache = {}, {}
        self.imagetk = True

    def get(self, ruta, tam):
        clave = (ruta, tam)
        img = self.cache.get(clave)
        if img is None:
            if Image is not None:
                if ruta not in self.fuentes:
                    try:
                        self.fuentes[ruta] = Image.open(ruta).convert('RGBA')
                    except OSError:  # una imagen que falta no debe romper la interfaz
                        self.fuentes[ruta] = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                escalada = self.fuentes[ruta].resize((tam, tam), Image.LANCZOS)
                img = None
                if self.imagetk:
                    try:
                        img = ImageTk.PhotoImage(escalada)
                    except Exception:  # Tk enlazado de forma estática (Python portátil): sin ImageTk
                        self.imagetk = False
                if img is None:  # Pillow escala y Tk recibe un PNG
                    import base64, io
                    buf = io.BytesIO()
                    escalada.save(buf, 'PNG')
                    img = tk.PhotoImage(data=base64.b64encode(buf.getvalue()))
            else:
                try:
                    img = tk.PhotoImage(file=ruta).subsample(max(1, round(256 / tam)))
                except tk.TclError:
                    img = tk.PhotoImage(width=tam, height=tam)
            self.cache[clave] = img
        return img

    def limpiar(self, conservar):
        if len(self.cache) > 600:
            self.cache = {k: v for k, v in self.cache.items() if k[1] in conservar}


# ---------------------------------------------------------------------- procesos y archivos
# En Windows, los procesos de la computadora no deben abrir una ventana de consola.
PROCESO = {'creationflags': 0x08000000} if os.name == 'nt' else {}


def abrir_archivo(ruta):
    """Abre un archivo con la aplicación predeterminada del sistema (PDF, etc.)."""
    import subprocess, sys
    try:
        if os.name == 'nt':
            os.startfile(ruta)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', ruta])
        else:
            subprocess.Popen(['xdg-open', ruta], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


# ---------------------------------------------------------------------- tamaño de la interfaz
# Tk con Xft no aplica «tk scaling» a las letras, así que el tamaño se escala aquí: todas las
# fuentes (familia, tamaño, ...) que se pasan a los widgets, al lienzo y a los estilos.
ESCALA = 1.0


def escalar_fuente(f):
    if ESCALA != 1.0 and isinstance(f, tuple) and len(f) >= 2 and isinstance(f[1], (int, float)) and f[1] > 0:
        return (f[0], max(6, int(round(f[1] * ESCALA)))) + tuple(f[2:])
    return f


def px(n):
    """Medida en píxeles ajustada al tamaño de la interfaz."""
    return int(round(n * ESCALA))


def activar_escala(escala):
    global ESCALA
    if ESCALA == 1.0 and escala != 1.0:
        options, formato = tk.Misc._options, ttk._format_optdict

        def _options(self, cnf, kw=None):
            if isinstance(cnf, dict) and 'font' in cnf:
                cnf = dict(cnf, font=escalar_fuente(cnf['font']))
            if kw and 'font' in kw:
                kw = dict(kw, font=escalar_fuente(kw['font']))
            return options(self, cnf, kw)

        def _format_optdict(optdict, *args, **kw):
            if 'font' in optdict:
                optdict = dict(optdict, font=escalar_fuente(optdict['font']))
            return formato(optdict, *args, **kw)
        tk.Misc._options = _options
        ttk._format_optdict = _format_optdict
    ESCALA = escala


def configurar(root):
    """Fuentes y estilos ttk. Devuelve (letra, letra_serif)."""
    familias = {f.lower(): f for f in tkfont.families(root)}  # sin distinguir mayúsculas
    letra = next((familias[f.lower()] for f in ('Cantarell', 'Noto Sans', 'DejaVu Sans', 'Liberation Sans', 'Arial')
                  if f.lower() in familias), 'TkDefaultFont')
    serif = next((familias[f.lower()] for f in ('Liberation Serif', 'Noto Serif', 'DejaVu Serif', 'Times New Roman')
                  if f.lower() in familias), letra)
    for nombre in ('TkDefaultFont', 'TkTextFont', 'TkMenuFont', 'TkHeadingFont', 'TkCaptionFont'):
        try:
            tkfont.nametofont(nombre).configure(family=letra, size=px(10))
        except tk.TclError:
            pass
    st = ttk.Style()
    if 'clam' in st.theme_names():
        st.theme_use('clam')
    st.configure('Panel.TFrame', background=FONDO)
    st.configure('Panel.TLabel', background=FONDO, foreground=TEXTO)
    st.configure('Titulo.TLabel', background=FONDO, foreground='#F3E2BE', font=(serif, 18, 'bold'))
    st.configure('Estado.TLabel', background=FONDO, foreground='#FFFFFF', font=(letra, 12, 'bold'))
    st.configure('Sub.TLabel', background=FONDO, foreground=TEXTO_SUAVE, font=(letra, 9, 'bold'))
    st.configure('Error.TLabel', background=FONDO, foreground='#F0A060')
    st.configure('Panel.TCheckbutton', background=FONDO, foreground=TEXTO)
    st.configure('Panel.TRadiobutton', background=FONDO, foreground=TEXTO)
    for estilo in ('Panel.TCheckbutton', 'Panel.TRadiobutton'):
        st.map(estilo, background=[('active', FONDO)], foreground=[('active', '#FFFFFF')])
    st.configure('Pestana.TButton', background='#3D3530', foreground=TEXTO_SUAVE, borderwidth=0,
                 font=(letra, 10, 'bold'), padding=(3, 6))
    st.map('Pestana.TButton', background=[('active', '#4A4039')])
    st.configure('PestanaActiva.TButton', background='#C9A46A', foreground=FONDO, borderwidth=0,
                 font=(letra, 10, 'bold'), padding=(3, 6))
    st.map('PestanaActiva.TButton', background=[('active', '#D6B47C')])
    st.configure('Comenzar.TButton', font=(letra, 11, 'bold'), padding=(8, 8))
    st.configure('Menu.TButton', background='#3D3530', foreground=ORO, borderwidth=0,
                 font=(letra, 9, 'bold'), padding=(8, 4))
    st.map('Menu.TButton', background=[('active', '#4A4039')])
    st.configure('Panel.TNotebook', background=FONDO, borderwidth=0)
    st.configure('Panel.TNotebook.Tab', background='#3D3530', foreground=TEXTO_SUAVE, padding=(10, 5),
                 font=(letra, 10, 'bold'))
    st.map('Panel.TNotebook.Tab', background=[('selected', '#C9A46A')], foreground=[('selected', FONDO)])
    st.configure('Panel.TSpinbox', arrowsize=12)
    return letra, serif


def buscar_pypy():
    """PyPy para la computadora: el del paquete autónomo (carpeta runtime/pypy junto a Juego), o uno instalado
    (pypy3 o pypy en el PATH, o ~/.local/bin/pypy3). None si no hay."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    propio = os.path.join(raiz, 'runtime', 'pypy')
    candidatos = [os.path.join(propio, 'pypy3.exe'), os.path.join(propio, 'pypy.exe'),
                  os.path.join(propio, 'bin', 'pypy3'), os.path.join(propio, 'bin', 'pypy')]
    candidatos += [shutil.which('pypy3'), shutil.which('pypy'), os.path.expanduser('~/.local/bin/pypy3')]
    for exe in candidatos:
        if exe and os.path.isfile(exe) and os.access(exe, os.X_OK):
            return exe
    return None


def base_clara(cv, x0, y0, x1, y1, radio=6, **kw):
    """Rectángulo redondeado claro detrás de piezas negras dibujadas sobre un fondo oscuro."""
    r = min(radio, (x1 - x0) / 2, (y1 - y0) / 2)
    puntos = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1, x0, y1,
              x0, y1 - r, x0, y0 + r, x0, y0]
    return cv.create_polygon(puntos, smooth=True, fill=kw.get('fill', FONDO_NEGRAS), outline=kw.get('outline', ''))
