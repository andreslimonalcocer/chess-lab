"""Ayuda dentro de la app: el manual (tecla F1) y las descripciones que aparecen al dejar el ratón sobre un
botón (tooltips)."""
import tkinter as tk
from tkinter import ttk

from interfaz import FONDO, ORO, TEXTO, TEXTO_SUAVE
from idioma import tr

SECCIONES = [
    ('Primeros pasos', [
        'El menú principal tiene cuatro variantes: Ajedrez clásico (8×8), Ajedrez Extendido (11×11, con '
        'Catapulta y Guardianes), Ajedrez Capablanca y Ajedrez gótico (10×8, con Arzobispo y Canciller). Haz clic en '
        'una tarjeta para jugar o en «Ver reglas» para leer sus reglas.',
        'Capablanca y gótico se pueden jugar también en 10×10: elige el tamaño en su tarjeta.',
        '«Más variantes» abre otras variantes históricas y modernas: Gran Ajedrez, Jano, Embajada, Ajedrez moderno, '
        'Courier, Shatranj, Makruk, Los Álamos, Gardner, Berolina, Knightmate, Ajedrez de los saltamontes y Casi ajedrez.',
        'Si es tu primera vez con el Ajedrez Extendido, empieza por «Aprende a jugar» (enlace dorado del menú): lecciones '
        'cortas, una por pieza y por regla especial, con ejercicios en el tablero.',
        'El Laboratorio (tarjeta ancha del menú) sirve para diseñar tus propias variantes.',
        'Abajo en el menú: Partidas guardadas, Mi perfil (tu Elo), Importar partida, Ajustes, Ayuda y Reproducir '
        'bitácora. Si cerraste a media partida, arriba a la izquierda aparece «▶ Continuar partida».',
        'Pulsa F1 en cualquier pantalla para abrir esta ayuda en la sección que corresponde. Deja el ratón sobre un '
        'botón para ver qué hace.',
    ]),
    ('Jugar una partida', [
        'Al entrar a una variante eliges el rival (la computadora u otra persona en este equipo), tu color, el nivel '
        'y, si quieres, un reloj (de 3+2 a 60+30). Con niveles calibrados, la dificultad se elige en Elo.',
        'Para mover: arrastra la pieza, o haz clic en ella y luego en la casilla. Punto verde: casilla libre; aro '
        'verde: captura; naranja: cadena de la Catapulta. Si a una casilla se llega de varias formas, aparece un menú.',
        'En el Ajedrez Extendido, las piezas que pueden extenderse llevan una estrella dorada: selecciónala y pulsa el botón del '
        'panel (cuesta el turno). El marcador de puntos decide el desempate por puntos.',
        '«Deshacer» (Ctrl+Z) retira tu última jugada y la de la computadora; la partida deja de contar para tu Elo.',
        'Cada partida se guarda sola, jugada a jugada. Al terminar puedes analizarla.',
    ]),
    ('Ayudas durante la partida', [
        'Se activan en Ajustes. «Pista» marca en oro la pieza y la casilla de la mejor jugada, con la idea que sigue.',
        '«¿Por qué?» explica la última jugada de la computadora: qué hace, qué amenaza, su evaluación y la '
        'continuación que esperaba.',
        'Los avisos marcan en rojo tus piezas en peligro y avisan si el rival amenaza mate en una.',
        'La barra de evaluación (casilla del panel) muestra a la izquierda del tablero quién va mejor.',
        'Una partida en la que usas pistas, «¿Por qué?» o avisos no cuenta para tu Elo.',
    ]),
    ('Revisar y analizar', [
        'Mientras juegas, haz clic en una jugada de la lista (o usa ← → e Inicio) para ver esa posición; el tablero '
        'se enmarca en azul. Esc, Fin o un clic en el tablero vuelven a la posición actual.',
        'El análisis evalúa cada posición de la partida: gráfica de la evaluación y jugadas marcadas con ?! '
        '(imprecisión), ? (error) y ?? (error grave), con la mejor jugada en cada caso.',
        'Tus errores de las partidas analizadas se convierten en problemas («Mis errores» en Problemas).',
    ]),
    ('Aprende a jugar', [
        'Lecciones del Ajedrez Extendido por pieza y por regla especial: enroque, salto largo del Caballo, Catapulta, '
        'captura en cadena, Guardián, extensiones y jaque mate.',
        'Cada ejercicio tiene un objetivo marcado en oro y se comprueba al jugar; si no era eso, te explica qué '
        'hiciste y vuelve a la posición. «Pista» selecciona la pieza correcta; «La regla» abre el reglamento.',
    ]),
    ('Entrenamiento', [
        'Arma cualquier posición: elige una pieza de la paleta y haz clic en el tablero (otra vez o clic derecho para '
        'quitarla); arrastra para moverla. «Práctica rápida» arma una posición con una pieza.',
        'Elige tu color y el nivel y pulsa «Comenzar»: haces la primera jugada y la computadora responde. Cada bando '
        'necesita su Rey.',
        '«Copiar posición» y «Pegar posición…» intercambian posiciones en texto.',
    ]),
    ('Problemas', [
        'Mates en 1, 2 o 3, problemas tácticos (una sola jugada gana material) y tus propios errores.',
        'Cada problema tiene una dificultad y el primer intento de cada uno mueve tu Elo de problemas; ver la solución '
        'antes de intentarlo cuenta como fallo. Prueba el «Problema del día» y mira tus «Estadísticas…».',
        '«Buscar problemas en mis bitácoras» agrega problemas nuevos de tus partidas y simulaciones.',
    ]),
    ('Finales', [
        'Finales de Rey y una o dos piezas contra Rey, que la computadora juega a la perfección con tablas exactas.',
        'Practica dando mate o defendiéndote: el panel dice si cada jugada fue perfecta. «Pista» muestra la mejor '
        'jugada. O mira cómo da mate la computadora.',
    ]),
    ('Aperturas', [
        'En el Ajedrez Extendido, el explorador muestra qué se jugó en cada posición y cómo terminó, más la evaluación del libro '
        'de aperturas de la computadora. Doble clic para avanzar.',
        'Con el libro activado en Ajustes, la computadora varía sus primeras jugadas.',
        '«▶ Reproducir» pasa la línea jugada a jugada (⏮ ◀ ▶ o las flechas para recorrerla a mano) y, al terminarla, '
        'puede seguir por la jugada más jugada o por la mejor del libro. «Abrir en el tablero» la lleva al tablero '
        'grande para reproducirla o analizarla.',
    ]),
    ('Espectador y bitácoras', [
        'En el Espectador juegan dos computadoras: elige sus niveles y la velocidad. «Pausa» y «Paso ▶» controlan la '
        'partida, que se guarda en una bitácora.',
        '«Abrir bitácora…» reproduce partidas guardadas (también las de las simulaciones), con análisis.',
        '«Exportar…» copia o guarda la posición o la partida en texto; «Importar partida…» las abre.',
    ]),
    ('Partidas guardadas y Elo', [
        'Partidas guardadas: filtra por variante, resultado, rival y fecha; continúa, reproduce, analiza, exporta '
        'varias a la vez o bórralas.',
        'Mi perfil: tu Elo en cada variante calibrada, su evolución, tus resultados por nivel y el nivel sugerido. '
        'Cuentan las partidas desde la posición inicial, sin «Deshacer» ni ayudas.',
    ]),
    ('Laboratorio', [
        'Diseña una variante: tamaño del tablero (5 a 12), piezas del catálogo o nuevas, reglas (objetivo, enroque, '
        'promoción, tablas) y posición inicial. Puedes partir de cualquier variante predefinida, incluido el Ajedrez '
        'Extendido completo.',
        'Al crear una pieza se abre un tablero vacío: marca casilla por casilla dónde mueve y captura (o solo mueve, o '
        'solo captura), si llega saltando o por camino libre y si solo vale en su primer avance o para tapar un jaque. '
        'Combínala con otras piezas (el Arzobispo es Alfil + Caballo) y agrega líneas rectas o diagonales con alcance '
        'o sin límite, que pueden saltar y capturar lo que saltan.',
        'Pestaña «Especiales»: saltos sobre una pieza (Saltamontes, León, Cañón, Langosta), sobre una fila de piezas '
        '(la Catapulta), capturas en cadena (la Catapulta extendida), jinetes, piezas torcidas, empujes e '
        'intercambios (el Guardián).',
        'Pestaña «Propiedades y extensión»: bloqueo de saltos (el aura del Guardián), avance como peón, puntos para '
        'el desempate, la forma extendida de la pieza y cuándo se extiende (al llegar a la última fila o tras '
        'capturar), y la conversión en otra pieza.',
        'El catálogo tiene más de sesenta piezas mágicas de la literatura, cada una con su imagen: saltadores '
        '(Camello, Cebra, Jirafa...), jinetes, compuestas, saltadoras sobre pantalla, torcidas, históricas y las del '
        'Ajedrez Extendido.',
        'La imagen se elige entre las del juego, los prediseños y tus diseños; «Diseñar…» arma una propia con un '
        'cuerpo, un remate, un adorno y una letra.',
        '«Jugar» la abre como cualquier variante; «Simular…» la pone a jugar contra sí misma o enfrenta dos piezas.',
        '«Exportar variante…» la guarda en un archivo para compartirla; «Importar variante…» abre una que te '
        'compartieron.',
    ]),
    ('Ajustes', [
        'Tema del tablero, diseño de las piezas, sonido y volumen, idioma (español o inglés), tamaño de la interfaz, '
        'animación, barra de evaluación, que la computadora piense durante tu turno, ayudas durante la partida y '
        'libro de aperturas.',
        'Piezas: para cada una eliges su diseño; por ejemplo, el Rey y la Dama clásicos del ajedrez y el Arzobispo '
        'y el Canciller de Capablanca. Vale para todas las variantes.',
    ]),
    ('Atajos de teclado', [
        'F1: esta ayuda.  Ctrl+N: partida nueva.  Ctrl+Z: deshacer.  Ctrl+E: entrenamiento.',
        'Esc: quitar la selección o volver a la posición actual.  ← →: recorrer la partida.  Inicio y Fin: ir al '
        'principio o a la posición actual.',
    ]),
]

# sección del manual para cada pantalla o modo
SECCION_DE_MODO = {'partida': 'Jugar una partida', 'entrenamiento': 'Entrenamiento', 'editor': 'Entrenamiento',
                   'espectador': 'Espectador y bitácoras', 'reproduccion': 'Revisar y analizar',
                   'problema': 'Problemas', 'final': 'Finales', 'leccion': 'Aprende a jugar'}

# descripciones de los botones y casillas (por su texto en español)
TOOLTIPS = {
    '← Menú': 'Volver al menú principal (la partida en curso se guarda).',
    'Reglas': 'Abrir las reglas de esta variante en otra ventana.',
    'Partida': 'Jugar contra la computadora o contra otra persona.',
    'Entrenamiento': 'Armar una posición y practicarla contra la computadora (Ctrl+E).',
    'Espectador': 'Ver jugar a dos computadoras.',
    'Finales': 'Practicar finales de Rey y piezas contra Rey.',
    'Problemas': 'Mates, problemas tácticos y tus errores.',
    'Aprender': 'Lecciones del Ajedrez Extendido, pieza por pieza.',
    'Aperturas': 'Explorador de aperturas: qué se jugó y cómo terminó.',
    'Nueva partida': 'Empezar una partida nueva (Ctrl+N).',
    'Deshacer': 'Retirar tu última jugada (Ctrl+Z). La partida deja de contar para tu Elo.',
    'Girar': 'Dar la vuelta al tablero.',
    'Exportar…': 'Copiar o guardar la posición o la partida en texto.',
    'Pista': 'Muestra una buena jugada (la partida deja de contar para tu Elo).',
    '¿Por qué?': 'Explica la última jugada de la computadora.',
    'Sonido': 'Activar o silenciar los sonidos.',
    'Barra de evaluación': 'Mostrar quién va mejor según la computadora.',
    'Reintentar': 'Volver a la posición inicial del ejercicio.',
    'Ver solución': 'Mostrar la solución (si no lo has intentado, cuenta como fallo).',
    'Siguiente problema ▶': 'Pasar al siguiente problema sin resolver.',
    'Siguiente ▶': 'Pasar al siguiente ejercicio.',
    'Lecciones…': 'Elegir otra lección.',
    'La regla': 'Abrir el reglamento en la sección de esta lección.',
    'Editar posición': 'Llevar la posición actual al editor.',
    'Reiniciar ejercicio': 'Volver a la posición que armaste.',
    'Reiniciar entrenamiento': 'Dejar el editor con solo los dos Reyes.',
    'Comenzar': 'Empezar con esta posición.',
    'Abrir bitácora…': 'Reproducir una partida guardada en una bitácora.',
    'Analizar partida': 'La computadora evalúa cada jugada y marca los errores.',
    '▶ Reanudar': 'Seguir la partida.',
    '◀ Atrás': 'Retroceder una jugada.',
    'Paso ▶': 'Avanzar una jugada.',
    'Forma extendida': 'Colocar la forma extendida (dorada) de la pieza.',
    'Goma': 'Quitar piezas del tablero con un clic.',
    'Copiar posición': 'Copiar la posición en texto (formato tipo FEN).',
    'Pegar posición…': 'Cargar una posición en texto.',
    'Exportar variante…': 'Guardar la variante en un archivo para compartirla.',
    'Importar variante…': 'Abrir una variante que te compartieron.',
    'Simular…': 'Poner a la computadora a jugar esta variante contra sí misma.',
    'Jugar ▶': 'Jugar esta variante.',
    'Guardar': 'Guardar la variante en el Laboratorio.',
    'Ver reglas': 'Ver las reglas generadas para esta variante.',
    '★ Problema del día': 'Un problema sin resolver cercano a tu Elo, el mismo todo el día.',
    'Estadísticas…': 'Tus resultados por tema.',
    'Buscar problemas en mis bitácoras': 'Buscar problemas nuevos en tus partidas y simulaciones.',
    'Resolver': 'Abrir el problema elegido.',
    'Solo sin resolver': 'Ocultar los problemas que ya resolviste.',
    'Elegir imagen…': 'Elegir la imagen entre las del juego, los prediseños y tus diseños.',
    'Diseñar…': 'Armar una imagen propia con un cuerpo, un remate, un adorno y una letra.',
    'Quitar todas las casillas': 'Borrar las casillas marcadas a mano en el tablero.',
    'Guardar pieza': 'Guardar la pieza en la variante.',
    'Todas del Ajedrez Extendido': 'Usar el diseño original del juego en todas las piezas.',
    'Clásicas y de Capablanca': 'Rey, Dama, Torre, Alfil, Caballo y Peón clásicos; Arzobispo y Canciller de Capablanca.',
    'Nueva pieza': 'Crear una pieza: en un tablero vacío o a partir de un prediseño.',
}


class Tooltip:
    """Descripción que aparece al dejar el ratón sobre un control."""

    def __init__(self, widget, texto, espera=650):
        self.w, self.texto, self.espera = widget, texto, espera
        self.id, self.top = None, None
        widget.bind('<Enter>', self.programar, add='+')
        widget.bind('<Leave>', self.ocultar, add='+')
        widget.bind('<ButtonPress>', self.ocultar, add='+')

    def programar(self, ev=None):
        self.ocultar()
        self.id = self.w.after(self.espera, self.mostrar)

    def mostrar(self):
        if not self.w.winfo_exists():
            return
        x = self.w.winfo_rootx() + 10
        y = self.w.winfo_rooty() + self.w.winfo_height() + 4
        self.top = tk.Toplevel(self.w)
        self.top.wm_overrideredirect(True)
        self.top.wm_geometry('+%d+%d' % (x, y))
        tk.Label(self.top, text=self.texto, bg='#3A322B', fg=TEXTO, relief='solid', borderwidth=1, wraplength=320,
                 justify='left', padx=8, pady=5, font=('Sans', 9)).pack()

    def ocultar(self, ev=None):
        if self.id is not None:
            self.w.after_cancel(self.id)
            self.id = None
        if self.top is not None:
            self.top.destroy()
            self.top = None


def poner_tooltips(raiz):
    """Agrega la descripción a los botones y casillas de raiz (y sus hijos) que tengan una."""
    pila = [raiz]
    while pila:
        w = pila.pop()
        try:
            pila.extend(w.winfo_children())
        except tk.TclError:
            continue
        if getattr(w, '_con_tooltip', False) or not isinstance(w, (ttk.Button, ttk.Checkbutton, tk.Button)):
            continue
        try:
            texto = getattr(w, '_texto_es', None) or w.cget('text')
        except tk.TclError:
            continue
        if texto in TOOLTIPS:
            Tooltip(w, TOOLTIPS[texto])
            w._con_tooltip = True


class VentanaManual:
    """El manual del juego: secciones a la izquierda y su texto a la derecha."""

    def __init__(self, app, seccion=None):
        self.app = app
        top = self.top = tk.Toplevel(app.root)
        top.title('Ayuda')
        top.configure(bg=FONDO)
        top.geometry('960x640')
        nav = ttk.Frame(top, style='Panel.TFrame', padding=(12, 14, 8, 12), width=250)
        nav.pack(side='left', fill='y')
        nav.pack_propagate(False)
        ttk.Label(nav, text='Ayuda', style='Titulo.TLabel').pack(anchor='w', pady=(0, 8))
        self.botones = []
        for i, (titulo, _) in enumerate(SECCIONES):
            b = ttk.Button(nav, text=titulo, style='Pestana.TButton', command=lambda i=i: self.mostrar(i))
            b.pack(fill='x', pady=1)
            self.botones.append(b)
        self.txt = tk.Text(top, bg=FONDO, fg=TEXTO, relief='flat', wrap='word', padx=24, pady=18,
                           font=(app.letra, 11), spacing1=4, spacing3=6, cursor='arrow')
        self.txt.tag_configure('titulo', font=(app.serif, 20, 'bold'), foreground='#F3E2BE', spacing3=12)
        self.txt.tag_configure('punto', lmargin1=4, lmargin2=22)
        barra = ttk.Scrollbar(top, command=self.txt.yview)
        self.txt.configure(yscrollcommand=barra.set)
        barra.pack(side='right', fill='y')
        self.txt.pack(side='left', fill='both', expand=True)
        self.mostrar(next((i for i, (t, _) in enumerate(SECCIONES) if t == seccion), 0))

    def mostrar(self, i):
        for k, b in enumerate(self.botones):
            b.configure(style='PestanaActiva.TButton' if k == i else 'Pestana.TButton')
        titulo, parrafos = SECCIONES[i]
        self.txt.configure(state='normal')
        self.txt.delete('1.0', 'end')
        self.txt.insert('end', tr(titulo) + '\n', 'titulo')
        for p in parrafos:
            self.txt.insert('end', '•  ' + tr(p) + '\n', 'punto')
        self.txt.configure(state='disabled')
