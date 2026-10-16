"""Idioma de la interfaz: español (el del código) o inglés.

La traducción se hace en el punto en que un texto llega a la pantalla: etiquetas, botones, casillas, títulos de
ventana, textos de los lienzos, encabezados y filas de las tablas, listas desplegables, menús, diálogos y
selectores de archivo. Así el código sigue escrito en español y solo hace falta el catálogo (idioma_en.py):

  - textos fijos: 'Girar' -> 'Flip';
  - plantillas con datos: 'Tu turno (%s).' -> 'Your turn (%s).'; lo que ocupa cada %s también se traduce
    ('blancas' -> 'White'), los números quedan igual; si el inglés necesita otro orden, usa {1}, {2}...;
  - textos compuestos: se traducen por líneas, por partes separadas con ' · ' y por oraciones.

Las listas desplegables muestran el texto traducido pero devuelven al código el original (get, cget('values')),
así la lógica que compara con textos en español sigue funcionando.

Para probar la cobertura: AJEDREZ_FALTANTES=archivo.txt anota los textos que no encontró en el catálogo.
"""
import os, re
import tkinter as tk
from tkinter import ttk

IDIOMAS = [('es', 'Español'), ('en', 'English')]
IDIOMA = 'es'
_exactos, _plantillas, _cache, _inverso = None, None, {}, {}
_FALTANTES = os.environ.get('AJEDREZ_FALTANTES')
_vistos = set()

_ESPEC = re.compile(r'%(?:\(\w+\))?[-+ #0]*\d*(?:\.\d+)?[sdifgrx%]')
_NUMERO = r'(\s*[-+]?\d+(?:[.,]\d+)?(?:e[-+]?\d+)?|[-+]?inf|nan)'


def establecer(codigo):
    global IDIOMA
    IDIOMA = codigo if codigo in dict(IDIOMAS) else 'es'
    _cache.clear()


def _cargar():
    """Separa el catálogo en textos fijos y plantillas (con su expresión regular y su ancla)."""
    global _exactos, _plantillas
    try:
        from idioma_en import EN
    except ImportError:
        EN = {}
    _exactos, _plantillas = {}, []
    completo = dict(EN)
    for es, en in EN.items():  # también sin los espacios de los extremos (para las partes de un texto compuesto)
        if es.strip() != es and es.strip():
            completo.setdefault(es.strip(), en.strip())
        for prefijo in (' · ', ', '):
            if es.startswith(prefijo) and len(es) > len(prefijo):
                completo.setdefault(es[len(prefijo):].strip(), en.strip()[len(prefijo.strip()):].strip())
    for es, en in completo.items():
        if not en:
            continue
        if not _ESPEC.search(es.replace('%%', '')):
            _exactos[es.replace('%%', '%')] = en.replace('%%', '%')
            continue
        partes, tipos, pos = [], [], 0
        for m in _ESPEC.finditer(es):
            partes.append(re.escape(es[pos:m.start()]))
            c = m.group()[-1]
            if c == '%':
                partes.append('%')
            elif c in 'sr':
                partes.append('(.*?)')
                tipos.append('s')
            else:
                partes.append(_NUMERO)
                tipos.append('n')
            pos = m.end()
        partes.append(re.escape(es[pos:]))
        literales = [x for x in _ESPEC.split(es) if x]
        if not any(x.strip() for x in literales):
            continue  # solo marcadores ('%s', '%s%s'): coincidiría con cualquier texto
        ancla = max(literales, key=len)
        destino = _ESPEC.sub(lambda m: '%' if m.group() == '%%' else '\0', en)
        _plantillas.append((len(''.join(literales)), ancla, re.compile(''.join(partes), re.S), tipos, destino))
    _plantillas.sort(key=lambda x: -x[0])  # las más específicas primero
    for es, en in _exactos.items():
        _inverso.setdefault(en, es)


def _llenar(destino, valores):
    if '{1}' in destino:
        for k, v in enumerate(valores, 1):
            destino = destino.replace('{%d}' % k, v)
        return destino.replace('\0', '')
    partes = destino.split('\0')
    out = [partes[0]]
    for k, resto in enumerate(partes[1:]):
        out.append(valores[k] if k < len(valores) else '')
        out.append(resto)
    return ''.join(out)


def _traducir(s, anotar=True):
    if s in _exactos:
        return _exactos[s]
    varias_lineas = '\n' in s
    for _, ancla, rx, tipos, destino in _plantillas:
        if ancla not in s or (varias_lineas and '\n' not in rx.pattern and '\\n' not in rx.pattern):
            continue  # una plantilla de una línea no abarca un texto de varias
        m = rx.fullmatch(s)
        if m and s not in m.groups():
            valores = [tr(g, False) if t == 's' else g for g, t in zip(m.groups(), tipos)]
            return _llenar(destino, valores)
    # textos compuestos: espacios alrededor, líneas, partes con ' · ', viñetas y oraciones
    nucleo = s.strip()
    if nucleo != s and nucleo:
        i = s.index(nucleo)
        return s[:i] + tr(nucleo, anotar) + s[i + len(nucleo):]
    if '\n' in s:
        return '\n'.join(tr(x, anotar) for x in s.split('\n'))
    if ' · ' in s:
        return ' · '.join(tr(x, anotar) for x in s.split(' · '))
    for viñeta in ('•  ', '• ', '- ', '⚠ '):
        if s.startswith(viñeta) and len(s) > len(viñeta):
            return viñeta + tr(s[len(viñeta):], anotar)
    oraciones = re.split(r'(?<=[.!?…])\s+(?=[¡¿«"(A-ZÁÉÍÓÚÑ0-9])', s)
    if len(oraciones) > 1:
        return ' '.join(tr(x, anotar) for x in oraciones)
    if s.endswith('.') and len(s) > 1:  # 'Alfil, Caballo.' -> partes sin el punto final
        r = tr(s[:-1], False)
        if r != s[:-1]:
            return r + '.'
    if ', ' in s:
        partes = [tr(x, False) for x in s.split(', ')]
        if partes != s.split(', '):
            return ', '.join(partes)
    if anotar and _FALTANTES and re.search(r'[A-Za-zÁÉÍÓÚáéíóúñÑ]{3}', s) and s not in _vistos:
        _vistos.add(s)
        try:
            with open(_FALTANTES, 'a', encoding='utf-8') as f:
                f.write(s.replace('\n', '\\n') + '\n')
        except OSError:
            pass
    return s


def tr(s, anotar=True):
    """El texto s en el idioma elegido (igual si es español o no está en el catálogo)."""
    if IDIOMA == 'es' or not isinstance(s, str) or not s:
        return s
    if _exactos is None:
        _cargar()
    r = _cache.get(s)
    if r is None:
        r = _cache[s] = _traducir(s, anotar)
    return r


def original(s):
    """El texto en español de una traducción fija (para las listas desplegables)."""
    if IDIOMA == 'es' or not isinstance(s, str):
        return s
    if _exactos is None:
        _cargar()
    return _inverso.get(s, s)


# ---------------------------------------------------------------------- puntos de salida de la interfaz
_CON_TEXTO = (ttk.Label, ttk.Button, ttk.Checkbutton, ttk.Radiobutton, ttk.Labelframe, ttk.Menubutton,
              tk.Label, tk.Button, tk.Checkbutton, tk.Radiobutton, tk.LabelFrame, tk.Message, tk.Menubutton)


def _texto_kw(widget, kw):
    if 'text' in kw and isinstance(kw['text'], str):
        widget.__dict__['_texto_es'] = kw['text']
        kw['text'] = tr(kw['text'])
    if isinstance(widget, ttk.Combobox) and 'values' in kw:
        kw['values'] = _valores_combo(widget, kw['values'])


def _valores_combo(widget, valores):
    if isinstance(valores, str):
        valores = widget.tk.splitlist(valores)
    valores = list(valores)
    traducidos = [tr(v) if isinstance(v, str) else v for v in valores]
    widget.__dict__['_valores_es'] = valores
    widget.__dict__['_mapa_es'] = dict(zip(traducidos, valores))
    return traducidos


def instalar():
    """Intercepta los puntos en que el texto llega a la pantalla (una sola vez)."""
    if getattr(tk, '_idioma_instalado', False):
        return
    tk._idioma_instalado = True
    from tkinter import messagebox, commondialog

    for cls in _CON_TEXTO + (ttk.Combobox,):
        init = cls.__init__

        def nuevo_init(self, *a, __init=init, **kw):
            if 'text' in kw or 'values' in kw:
                _texto_kw(self, kw)
            __init(self, *a, **kw)
        cls.__init__ = nuevo_init

    configure = tk.Misc.configure

    def nuevo_configure(self, cnf=None, **kw):
        if isinstance(cnf, dict) and ('text' in cnf or 'values' in cnf):
            kw.update(cnf)
            cnf = None
        if isinstance(self, _CON_TEXTO + (ttk.Combobox,)):
            _texto_kw(self, kw)
        return configure(self, cnf, **kw)
    tk.Misc.configure = tk.Misc.config = nuevo_configure

    setitem = tk.Misc.__setitem__

    def nuevo_setitem(self, clave, valor):
        if clave == 'text' and isinstance(self, _CON_TEXTO):
            self.__dict__['_texto_es'] = valor
            valor = tr(valor)
        elif clave == 'values' and isinstance(self, ttk.Combobox):
            valor = _valores_combo(self, valor)
        setitem(self, clave, valor)
    tk.Misc.__setitem__ = nuevo_setitem

    # listas desplegables: el código lee y escribe el texto original
    get, set_, cget = ttk.Combobox.get, ttk.Combobox.set, tk.Misc.cget
    def nuevo_get(self):
        valor = get(self)
        return self.__dict__.get('_mapa_es', {}).get(valor) or original(valor)
    ttk.Combobox.get = nuevo_get
    ttk.Combobox.set = lambda self, valor: set_(self, tr(valor))

    def nuevo_cget(self, clave):
        if clave == 'values' and isinstance(self, ttk.Combobox) and '_valores_es' in self.__dict__:
            return tuple(self.__dict__['_valores_es'])
        return cget(self, clave)
    tk.Misc.cget = nuevo_cget
    ttk.Combobox.cget = nuevo_cget
    ttk.Combobox.__getitem__ = nuevo_cget

    create_text = tk.Canvas.create_text

    def nuevo_create_text(self, *a, **kw):
        if 'text' in kw:
            kw['text'] = tr(kw['text'])
        return create_text(self, *a, **kw)
    tk.Canvas.create_text = nuevo_create_text

    itemconfigure = tk.Canvas.itemconfigure

    def nuevo_itemconfigure(self, item, cnf=None, **kw):
        if 'text' in kw:
            kw['text'] = tr(kw['text'])
        return itemconfigure(self, item, cnf, **kw)
    tk.Canvas.itemconfigure = tk.Canvas.itemconfig = nuevo_itemconfigure

    titulo = tk.Wm.wm_title
    tk.Wm.wm_title = tk.Wm.title = lambda self, string=None: titulo(self, tr(string) if string else string)

    heading = ttk.Treeview.heading

    def nuevo_heading(self, column, option=None, **kw):
        if 'text' in kw:
            kw['text'] = tr(kw['text'])
        return heading(self, column, option, **kw)
    ttk.Treeview.heading = nuevo_heading

    def _valores(kw):
        if 'values' in kw and kw['values'] is not None:
            kw['values'] = [tr(v) if isinstance(v, str) else v for v in kw['values']]
        if 'text' in kw:
            kw['text'] = tr(kw['text'])

    insert = ttk.Treeview.insert

    def nuevo_insert(self, parent, index, iid=None, **kw):
        _valores(kw)
        return insert(self, parent, index, iid, **kw)
    ttk.Treeview.insert = nuevo_insert

    item = ttk.Treeview.item

    def nuevo_item(self, it, option=None, **kw):
        _valores(kw)
        return item(self, it, option, **kw)
    ttk.Treeview.item = nuevo_item

    lb_insert = tk.Listbox.insert
    tk.Listbox.insert = lambda self, index, *elementos: lb_insert(self, index, *[tr(e) for e in elementos])

    for nombre in ('add_command', 'add_checkbutton', 'add_radiobutton', 'add_cascade'):
        metodo = getattr(tk.Menu, nombre)

        def nuevo(self, cnf={}, __m=metodo, **kw):
            if 'label' in kw:
                kw['label'] = tr(kw['label'])
            return __m(self, cnf, **kw)
        setattr(tk.Menu, nombre, nuevo)

    nb_add, nb_tab = ttk.Notebook.add, ttk.Notebook.tab

    def nuevo_add(self, child, **kw):
        if 'text' in kw:
            kw['text'] = tr(kw['text'])
        return nb_add(self, child, **kw)
    ttk.Notebook.add = nuevo_add

    def nuevo_tab(self, tab_id, option=None, **kw):
        if 'text' in kw:
            kw['text'] = tr(kw['text'])
        return nb_tab(self, tab_id, option, **kw)
    ttk.Notebook.tab = nuevo_tab

    show = messagebox._show

    def nuevo_show(title=None, message=None, _icon=None, _type=None, **options):
        if 'detail' in options:
            options['detail'] = tr(options['detail'])
        return show(tr(title), tr(message), _icon, _type, **options)
    messagebox._show = nuevo_show

    dialogo = commondialog.Dialog.__init__

    def nuevo_dialogo(self, master=None, **options):
        if 'title' in options:
            options['title'] = tr(options['title'])
        if options.get('filetypes'):
            options['filetypes'] = [(tr(d), p) for d, p in options['filetypes']]
        dialogo(self, master, **options)
    commondialog.Dialog.__init__ = nuevo_dialogo
