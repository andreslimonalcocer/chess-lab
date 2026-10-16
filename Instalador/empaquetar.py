"""Crea un .zip del juego para llevarlo a otra computadora (Windows, macOS o Linux).

Incluye el juego, el motor y el simulador, las tablas de finales (también las de dos piezas, ~2.4 GB sin
comprimir; --sin-tablas-dos las deja fuera), las piezas, el reglamento y los instaladores; deja
fuera los datos personales (partidas, perfil, ajustes, bitácoras) y los resultados de las
simulaciones. En la otra computadora: descomprimir y ejecutar el instalador de su sistema.

    python3 empaquetar.py [--salida Ajedrez.zip] [--con-datos]
"""
import argparse, os, re, shutil, time, zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETAS = ['Juego', 'Simulador', 'Piezas', 'Reglas', 'Instalador']
PERSONALES = {'partidas', 'bitacoras', 'simulaciones', 'perfil.json', 'ajustes.json', 'mis_problemas.json',
              'disenos'}
NUNCA = {'__pycache__', 'volumen', '.git', 'descargas'}


def tabla_de_dos(nombre):
    """¿Es una tabla de finales de dos piezas (KBNK.dtm, KRpRK.dtm…)? Pesan cientos de MB cada una."""
    m = re.fullmatch(r'K(.+)K\.dtm', nombre)
    return bool(m) and len(m.group(1).replace('p', '')) >= 2


def incluir(rel, con_datos, tablas_dos=True):
    partes = rel.split(os.sep)
    if partes[0] == 'Simulador' and 'tablas' in partes and tabla_de_dos(partes[-1]) and not tablas_dos:
        return False  # sin ellas, se construyen allá con Simulador/pasos/tablas_dos_piezas.sh
    if NUNCA & set(partes) or rel.endswith(('.pyc', '.ico')):
        return False
    if partes[0] == 'Juego' and len(partes) > 1 and partes[1] in PERSONALES:
        return con_datos
    if partes[0] == 'Simulador' and rel.endswith('.jsonl'):  # resultados de las simulaciones
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--salida', default=os.path.join(RAIZ, 'Ajedrez_%s.zip' % time.strftime('%Y%m%d')))
    ap.add_argument('--con-datos', action='store_true', help='incluye partidas, perfil, ajustes y bitácoras')
    ap.add_argument('--sin-tablas-dos', action='store_true',
                    help='deja fuera las tablas de finales de dos piezas (~2.4 GB sin comprimir, ~420 MB en el .zip)')
    a = ap.parse_args()
    n = 0
    with zipfile.ZipFile(a.salida, 'w', zipfile.ZIP_DEFLATED) as z:
        for carpeta in CARPETAS:
            for base, dirs, archivos in os.walk(os.path.join(RAIZ, carpeta)):
                dirs[:] = [d for d in dirs if d not in NUNCA]
                for f in archivos:
                    ruta = os.path.join(base, f)
                    rel = os.path.relpath(ruta, RAIZ)
                    if incluir(rel, a.con_datos, not a.sin_tablas_dos):
                        info = zipfile.ZipInfo.from_file(ruta, os.path.join('Ajedrez', rel))
                        info.compress_type = zipfile.ZIP_DEFLATED
                        if f.endswith(('.sh', '.command')):
                            info.external_attr = 0o755 << 16
                        with open(ruta, 'rb') as fh, z.open(info, 'w', force_zip64=True) as dest:
                            shutil.copyfileobj(fh, dest, 1 << 20)  # por partes: las tablas pesan cientos de MB
                        n += 1
        for f in ('LICENSE', 'README.md'):  # la licencia (GPL v3) acompaña siempre al juego
            if os.path.exists(os.path.join(RAIZ, f)):
                z.write(os.path.join(RAIZ, f), os.path.join('Ajedrez', f))
                n += 1
    print('%d archivos en %s (%.1f MB)' % (n, a.salida, os.path.getsize(a.salida) / 1e6))


if __name__ == '__main__':
    main()
