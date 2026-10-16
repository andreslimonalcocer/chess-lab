"""Actualiza el reglamento en PDF con el nombre oficial «Ajedrez Extendido» y el término «extensión» (antes
«Ajedrez 11 × 11» y «promoción»), sin rehacer el documento: cada línea que contiene un término se reescribe en
su sitio con las mismas fuentes, tamaño, color y alineación; los diagramas, tablas y demás páginas quedan
intactos. El tamaño del tablero («11 × 11 casillas») no cambia.

    python3 actualizar_reglamento.py ORIGEN.pdf DESTINO.pdf

Necesita PyMuPDF y las fuentes Liberation Serif (las del documento original).
"""
import difflib, glob, os, re, sys

import pymupdf as fitz

REGLAS = [  # en orden: las frases antes que las palabras sueltas
    (r'\bAJEDREZ 11 × 11\b', 'AJEDREZ EXTENDIDO'),
    (r'\bAjedrez 11 × 11\b', 'Ajedrez Extendido'),
    (r'\b([Ss])istema de promoción\b', r'\1istema de extensiones'),
    (r'\bformas de promoción\b', 'formas de extensión'),
    (r'\bderecho a promocionar\b', 'derecho de extensión'),
    (r'\bNo promociona\b', 'No se extiende'),
    (r'\bValor promocionada\b', 'Valor de la forma extendida'),
    (r'\b(puede|pueden|va a) promocionar\b', r'\1 extenderse'),
    (r'\bpromocionar\b', 'extender'),
    (r'\bpromociona\b', 'se extiende'),
    (r'\bpromocionadas\b', 'extendidas'),
    (r'\bpromocionados\b', 'extendidos'),
    (r'\bpromocionada\b', 'extendida'),
    (r'\bpromocionado\b', 'extendido'),
    (r'\bPromociones\b', 'Extensiones'),
    (r'\bpromociones\b', 'extensiones'),
    (r'\bPromoción\b', 'Extensión'),
    (r'\bpromoción\b', 'extensión'),
]
MARGEN_IZQ, MARGEN_DER = 68.0, 527.3


def cambiar(texto):
    for patron, nuevo in REGLAS:
        texto = re.sub(patron, nuevo, texto)
    return texto


def fuentes():
    """Liberation Serif del sistema, por estilo."""
    archivos = {}
    for estilo, nombre in (('', 'Regular'), ('-Bold', 'Bold'), ('-Italic', 'Italic'), ('-BoldItalic', 'BoldItalic')):
        cand = glob.glob('/usr/share/fonts/**/LiberationSerif-%s.ttf' % nombre, recursive=True)
        if not cand:
            sys.exit('No encuentro LiberationSerif-%s.ttf' % nombre)
        archivos[estilo] = fitz.Font(fontfile=cand[0])
    return archivos


def estilo_de(nombre):
    b, i = 'Bold' in nombre, 'Italic' in nombre
    return '-BoldItalic' if b and i else '-Bold' if b else '-Italic' if i else ''


def palabras(linea):
    """[(texto, x0, x1, baseline, estilo, tamaño, color)] de una línea, separadas por espacios."""
    out, actual = [], None
    for s in linea['spans']:
        for c in s['chars']:
            if c['c'] == ' ':
                actual = None
                continue
            if actual is None:
                actual = [c['c'], c['origin'][0], c['bbox'][2], c['origin'][1], estilo_de(s['font']), s['size'], s['color']]
                out.append(actual)
            else:
                actual[0] += c['c']
                actual[2] = c['bbox'][2]
    return [tuple(p) for p in out]


def segmentos(ps):
    """Partes de una línea separadas por huecos grandes (columnas, encabezados, celdas)."""
    out, seg = [], []
    for p in ps:
        if seg and p[1] - seg[-1][2] > 3.5 * p[5] * 0.25 * 2.4:
            out.append(seg)
            seg = []
        seg.append(p)
    if seg:
        out.append(seg)
    return out


def main(origen, destino):
    F = fuentes()
    doc = fitz.open(origen)
    cambios = 0
    for np, page in enumerate(doc):
        nuevas = []
        for b in page.get_text('rawdict')['blocks']:
            for l in b.get('lines', []):
                for seg in segmentos(palabras(l)):
                    viejo = [p[0] for p in seg]
                    nuevo = cambiar(' '.join(viejo)).split(' ')
                    if nuevo == viejo:
                        continue
                    nuevas.append((seg, nuevo))
        if not nuevas:
            continue
        for seg, _ in nuevas:  # franja fina sobre la línea: no toca las vecinas
            base, tam = seg[0][3], seg[0][5]
            page.add_redact_annot(fitz.Rect(seg[0][1] - 0.3, base - 0.55 * tam, seg[-1][2] + 0.3, base - 0.15 * tam))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        escritores = {}
        for seg, nuevo in nuevas:
            viejo = [p[0] for p in seg]
            # cada palabra nueva toma el estilo de la palabra vieja que le corresponde
            fmt, sm = [], difflib.SequenceMatcher(None, viejo, nuevo)
            for op, i1, i2, j1, j2 in sm.get_opcodes():
                for k in range(j2 - j1):
                    fmt.append(seg[min(i1 + k, i2 - 1) if op == 'equal' or i2 > i1 else max(0, i1 - 1)])
            x0, x1, base = seg[0][1], seg[-1][2], seg[0][3]
            anchos = [F[f[4]].text_length(w, fontsize=f[5]) for w, f in zip(nuevo, fmt)]
            espacio = F[fmt[0][4]].text_length(' ', fontsize=fmt[0][5])
            natural = sum(anchos) + espacio * (len(nuevo) - 1)
            cursiva = all(f[4] in ('-Italic', '-BoldItalic') for f in fmt)
            escala = 1.0
            if np == 0 or (cursiva and abs(x0 - MARGEN_IZQ) > 2):       # centrada (portada y pies de diagrama)
                centro = (x0 + x1) / 2
                hueco = espacio
                x = centro - natural / 2
            elif x1 >= MARGEN_DER - 1.5 and len(nuevo) > 1:              # justificada: el mismo ancho
                hueco = (x1 - x0 - sum(anchos)) / (len(nuevo) - 1)
                if hueco < 0.6 * espacio:                                  # no cabe: letra un poco más pequeña
                    escala = (x1 - x0 - 0.6 * espacio * (len(nuevo) - 1)) / sum(anchos)
                    anchos = [a * escala for a in anchos]
                    hueco = (x1 - x0 - sum(anchos)) / (len(nuevo) - 1)
                x = x0
            else:                                                          # alineada a la izquierda
                hueco, x = espacio, x0
            for w, f, a in zip(nuevo, fmt, anchos):
                color = f[6]
                tw = escritores.setdefault(color, fitz.TextWriter(page.rect))
                tw.append((x, base), w, font=F[f[4]], fontsize=f[5] * escala)
                x += a + hueco
            cambios += 1
        for color, tw in escritores.items():
            tw.write_text(page, color=((color >> 16) / 255, ((color >> 8) & 255) / 255, (color & 255) / 255))
    meta = doc.metadata
    meta['title'] = cambiar(meta.get('title') or '')
    doc.set_metadata(meta)
    doc.subset_fonts()
    doc.save(destino, garbage=4, deflate=True)
    print('%d líneas actualizadas en %s' % (cambios, destino))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
