"""Efectos de sonido del juego.

Los sonidos se sintetizan la primera vez y se guardan como WAV en la carpeta 'sonidos'.
Para usar otros sonidos basta con reemplazar esos archivos (mismo nombre).
Se reproducen sin bloquear la interfaz: en Linux con pw-play, paplay o aplay; en macOS con afplay;
en Windows con winsound. El volumen se aplica con copias escaladas de los WAV (carpeta sonidos/volumen).
"""
import math, os, random, shutil, struct, subprocess, sys, wave

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sonidos')
FRECUENCIA = 44100


def _golpe(t, tono, caida, ruido, rng):
    """Golpe de madera: tono grave que se apaga rápido más un chasquido de ruido."""
    env = math.exp(-t / caida)
    s = 0.65 * math.sin(2 * math.pi * tono * t) + 0.35 * math.sin(2 * math.pi * tono * 2.7 * t)
    return env * s + ruido * math.exp(-t / 0.004) * (rng.random() * 2 - 1)


def _movimiento():
    rng = random.Random(1)
    return [_golpe(i / FRECUENCIA, 210, 0.018, 0.5, rng) for i in range(int(0.09 * FRECUENCIA))]


def _captura():
    rng = random.Random(2)
    n = int(0.17 * FRECUENCIA)
    out = []
    for i in range(n):
        t = i / FRECUENCIA
        s = _golpe(t, 150, 0.03, 0.9, rng)
        if t > 0.035:
            s += 0.8 * _golpe(t - 0.035, 260, 0.022, 0.6, rng)
        out.append(s)
    return out


def _jaque():
    out = []
    for i in range(int(0.42 * FRECUENCIA)):
        t = i / FRECUENCIA
        s = 0.0
        for inicio, f in ((0.0, 880.0), (0.13, 1174.7)):
            if t >= inicio:
                u = t - inicio
                env = min(1.0, u / 0.004) * math.exp(-u / 0.11)
                s += env * (math.sin(2 * math.pi * f * u) + 0.3 * math.sin(2 * math.pi * 2 * f * u))
        out.append(s)
    return out


SINTESIS = {'movimiento': _movimiento, 'captura': _captura, 'jaque': _jaque}


def _guardar(ruta, muestras, volumen=0.55):
    pico = max(abs(x) for x in muestras) or 1.0
    datos = b''.join(struct.pack('<h', int(32767 * volumen * x / pico)) for x in muestras)
    with wave.open(ruta, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FRECUENCIA)
        w.writeframes(datos)


class Sonidos:
    def __init__(self):
        self.activo = True
        self.volumen = 100  # %
        self.winsound = None
        if sys.platform.startswith('win'):
            try:
                import winsound
                self.winsound = winsound
            except ImportError:
                pass
        self.reproductor = next((p for p in ('pw-play', 'paplay', 'aplay', 'afplay') if shutil.which(p)), None)
        self.archivos = {}
        try:
            os.makedirs(CARPETA, exist_ok=True)
            for nombre, sintetizar in SINTESIS.items():
                ruta = os.path.join(CARPETA, nombre + '.wav')
                if not os.path.exists(ruta):
                    _guardar(ruta, sintetizar())
                self.archivos[nombre] = ruta
        except OSError:
            self.reproductor = self.winsound = None

    def _archivo(self, nombre):
        """El WAV con el volumen elegido (se crea la primera vez a partir del original)."""
        ruta = self.archivos[nombre]
        vol = max(0, min(100, int(self.volumen)))
        if vol == 100:
            return ruta
        copia = os.path.join(CARPETA, 'volumen', '%s_%d.wav' % (nombre, vol))
        if not os.path.exists(copia):
            try:
                os.makedirs(os.path.dirname(copia), exist_ok=True)
                with wave.open(ruta, 'rb') as w:
                    params, datos = w.getparams(), w.readframes(w.getnframes())
                if params.sampwidth != 2:
                    return ruta
                f = (vol / 100.0) ** 2  # el oído percibe el volumen de forma logarítmica
                n = len(datos) // 2
                muestras = struct.unpack('<%dh' % n, datos[:2 * n])
                with wave.open(copia, 'wb') as w:
                    w.setparams(params)
                    w.writeframes(struct.pack('<%dh' % n, *(int(x * f) for x in muestras)))
            except (OSError, wave.Error, struct.error):
                return ruta
        return copia

    def tocar(self, nombre):
        if not (self.activo and self.volumen > 0 and nombre in self.archivos):
            return
        ruta = self._archivo(nombre)
        if self.winsound is not None:
            try:
                self.winsound.PlaySound(ruta, self.winsound.SND_FILENAME | self.winsound.SND_ASYNC)
            except RuntimeError:
                pass
            return
        if not self.reproductor:
            return
        args = [self.reproductor] + (['-q'] if self.reproductor == 'aplay' else []) + [ruta]
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
