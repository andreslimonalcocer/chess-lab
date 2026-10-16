"""Cambia el dibujo de una pieza en el reglamento en PDF, sin rehacer el documento.

El reglamento tiene dos clases de imágenes con piezas:
  - las de la tabla de piezas (una imagen por pieza): se sustituyen enteras;
  - los diagramas (un tablero de 11 × 11 ya dibujado, con las piezas pintadas al 94 % de la casilla): en cada
    casilla se busca la pieza vieja (blanca o negra, normal o extendida); donde está, se borra con el color de
    fondo de la casilla y se pinta la nueva en el mismo sitio y tamaño.

    python3 reemplazar_pieza.py ORIGEN.pdf DESTINO.pdf VIEJAS NUEVAS [--nombre arzobispo]

VIEJAS y NUEVAS son carpetas con blancas/png/ y negras/png/ (como Piezas/ o una copia de las imágenes anteriores)
que tienen NOMBRE.png y NOMBRE_promocionado.png. Necesita PyMuPDF, NumPy y Pillow.
"""
import argparse, io, os, sys

import numpy as np
import pymupdf as fitz
from PIL import Image

ESCALA = 0.94     # tamaño de la pieza respecto de la casilla en los diagramas
UMBRAL = 6.0      # error medio (de 0 a 255) por debajo del cual la casilla tiene la pieza vieja


def imagen(doc, xref):
    """La imagen del PDF como matriz RGB (y su alfa, si tiene máscara)."""
    pix = fitz.Pixmap(doc, xref)
    if pix.n - pix.alpha != 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)
    return a[:, :, :3].astype(float)


def tablero(a):
    """(x0, y0, casilla) del tablero de 11 × 11 dentro de un diagrama, o None si no lo parece."""
    oscuro = a.sum(2) < 735
    cols = np.where(oscuro.mean(0) > 0.6)[0]
    filas = np.where(oscuro.mean(1) > 0.6)[0]
    if len(cols) < 100 or len(filas) < 100:
        return None
    x0, x1, y0, y1 = cols[0], cols[-1] + 1, filas[0], filas[-1] + 1
    cx, cy = (x1 - x0) / 11, (y1 - y0) / 11
    if abs(cx - cy) > 2:
        return None
    return x0, y0, (cx + cy) / 2


class Piezas:
    def __init__(self, carpeta, nombre):
        self.rutas = {(c, p): os.path.join(carpeta, lado, 'png', nombre + ('_promocionado' if p else '') + '.png')
                      for c, lado in ((0, 'blancas'), (1, 'negras')) for p in (False, True)}
        self.cache = {}

    def rgba(self, clave, tam):
        k = (clave, tam)
        if k not in self.cache:
            im = Image.open(self.rutas[clave]).convert('RGBA').resize((tam, tam), Image.LANCZOS)
            self.cache[k] = np.asarray(im).astype(float)
        return self.cache[k]


def componer(fondo, p):
    al = p[:, :, 3:] / 255
    return p[:, :, :3] * al + fondo * (1 - al)


def parchear_diagrama(a, viejas, nuevas):
    """Repinta la pieza en el diagrama. Devuelve (nueva matriz, casillas cambiadas)."""
    t = tablero(a)
    if t is None:
        return a, 0
    x0, y0, c = t
    tam = int(round(c * ESCALA))
    out = a.copy()
    cambios = 0
    for fila in range(11):
        for col in range(11):
            cx, cy = x0 + (col + 0.5) * c, y0 + (fila + 0.5) * c
            celda = a[int(y0 + fila * c) + 2:int(y0 + (fila + 1) * c) - 2, int(x0 + col * c) + 2:int(x0 + (col + 1) * c) - 2]
            fondo = np.median(np.concatenate([celda[:3].reshape(-1, 3), celda[-3:].reshape(-1, 3)]), 0)
            mejor = None
            for clave in viejas.rutas:
                p = viejas.rgba(clave, tam)
                esperado = componer(fondo, p)
                for dx in (-1, 0, 1):
                    for dy in (-2, -1, 0, 1):
                        xa, ya = int(round(cx - tam / 2)) + dx, int(round(cy - tam / 2)) + dy
                        rec = a[ya:ya + tam, xa:xa + tam]
                        if rec.shape[:2] != (tam, tam):
                            continue
                        visible = p[:, :, 3] > 30  # se compara solo donde se ve la pieza
                        e = np.abs(rec - esperado)[visible].mean()
                        if mejor is None or e < mejor[0]:
                            mejor = (e, clave, xa, ya)
            if mejor is None or mejor[0] > UMBRAL:
                continue
            _, clave, xa, ya = mejor
            vieja = viejas.rgba(clave, tam)
            rec = out[ya:ya + tam, xa:xa + tam]
            # se borra la pieza vieja (y su borde suavizado) con el color de fondo y se pinta la nueva
            borrar = np.maximum.reduce([np.roll(np.roll(vieja[:, :, 3] > 0, i, 0), j, 1)
                                        for i in (-1, 0, 1) for j in (-1, 0, 1)])
            rec[borrar] = fondo
            out[ya:ya + tam, xa:xa + tam] = componer(rec, nuevas.rgba(clave, tam))
            cambios += 1
    return out, cambios


def png(matriz, alfa=None):
    m = np.clip(np.round(matriz), 0, 255).astype(np.uint8)
    im = Image.fromarray(m, 'RGB') if alfa is None else Image.fromarray(np.dstack([m, alfa]), 'RGBA')
    b = io.BytesIO()
    im.save(b, 'PNG', optimize=True)
    return b.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('origen')
    ap.add_argument('destino')
    ap.add_argument('viejas')
    ap.add_argument('nuevas')
    ap.add_argument('--nombre', default='arzobispo')
    a = ap.parse_args()
    viejas, nuevas = Piezas(a.viejas, a.nombre), Piezas(a.nuevas, a.nombre)
    doc = fitz.open(a.origen)
    hechas = set()
    tabla = diagramas = casillas = 0
    for pagina in doc:
        for info in pagina.get_images(full=True):
            xref, smask, w, h = info[0], info[1], info[2], info[3]
            if xref in hechas:
                continue
            hechas.add(xref)
            if w == h == 256 and smask:  # una pieza de la tabla: se compara con las viejas tal cual
                rgb = imagen(doc, xref)
                alfa = np.frombuffer(fitz.Pixmap(doc, smask).samples, np.uint8).reshape(h, w)
                for clave, ruta in viejas.rutas.items():
                    v = viejas.rgba(clave, 256)
                    if np.abs(v[:, :, 3] - alfa).mean() < 2 and np.abs((v[:, :, :3] - rgb)[alfa > 30]).mean() < 3:
                        nueva = Image.open(nuevas.rutas[clave]).convert('RGBA').resize((256, 256), Image.LANCZOS)
                        b = io.BytesIO()
                        nueva.save(b, 'PNG')
                        pagina.replace_image(xref, stream=b.getvalue())
                        tabla += 1
                        break
            elif w > 600 and h > 600:  # un diagrama
                a_ = imagen(doc, xref)
                nueva, n = parchear_diagrama(a_, viejas, nuevas)
                if n:
                    pagina.replace_image(xref, stream=png(nueva))
                    diagramas += 1
                    casillas += n
    doc.save(a.destino, garbage=4, deflate=True)
    print('Tabla de piezas: %d imágenes; diagramas: %d (%d casillas). Guardado en %s'
          % (tabla, diagramas, casillas, a.destino))


if __name__ == '__main__':
    sys.exit(main())
