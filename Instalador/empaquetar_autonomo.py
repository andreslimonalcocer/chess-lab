"""Paquete autónomo del juego: no necesita tener Python ni PyPy instalados.

Junta el juego con un Python portátil que incluye Tkinter (python-build-standalone) y con PyPy para la
computadora, ambos del sistema elegido, más Pillow si se puede descargar, y todas las tablas de finales (también
las de dos piezas; --sin-tablas-dos las deja fuera). Se arma desde cualquier sistema
(solo descarga y copia archivos); cada paquete sirve para su sistema:

    python3 empaquetar_autonomo.py --plataforma windows      # Ajedrez_windows_AAAAMMDD.zip (~500 MB)
    python3 empaquetar_autonomo.py --plataforma mac-arm      # .tar.xz (~300 MB), Mac con Apple Silicon (M1…)
    python3 empaquetar_autonomo.py --plataforma mac-intel
    python3 empaquetar_autonomo.py --plataforma linux
    python3 empaquetar_autonomo.py --todas

En la otra computadora: descomprimir en una carpeta propia (no en «Archivos de programa») y abrir
Ajedrez.bat (Windows), Ajedrez.command (macOS) o ajedrez.sh (Linux). Las descargas se guardan en
Instalador/descargas/ y se verifican con sus sumas SHA-256 oficiales.
"""
import argparse, hashlib, io, os, re, shutil, subprocess, sys, tarfile, tempfile, time, urllib.request, zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from empaquetar import RAIZ, CARPETAS, NUNCA, incluir  # noqa: E402

DESCARGAS = os.path.join(AQUI, 'descargas')
PBS = 'https://github.com/astral-sh/python-build-standalone/releases/download/20260924/'
PYTHON = 'cpython-3.12.14+20260924-%s-install_only_stripped.tar.gz'  # sin símbolos de depuración
PYPY = 'https://downloads.python.org/pypy/'
# sumas SHA-256 publicadas en https://www.pypy.org/checksums.html
PYPY_SHA = {
    'pypy3.10-v7.3.17-win64.zip': 'cab794a03ddda26238c72942ea6f225612e0dc17c76cac6652da83a95024e6e8',
    'pypy3.10-v7.3.17-linux64.tar.bz2': 'fdcdb9b24f1a7726003586503fdeb264fd68fc37fbfcea022dcfe825a7fee18b',
    'pypy3.10-v7.3.17-macos_arm64.tar.bz2': 'a050e25e8d686853dd5afc363e55625165825dacfb55f8753d8225ebe417cfd2',
    'pypy3.10-v7.3.17-macos_x86_64.tar.bz2': '6c2c5f2300d7564e711421b4968abd63243cb96f76e363975dd648ebf4a362ee',
}
PLATAFORMAS = {
    # nombre: (python, pypy, plataforma de pip para Pillow, carpeta site-packages dentro de python/)
    'windows': ('x86_64-pc-windows-msvc', 'pypy3.10-v7.3.17-win64.zip', 'win_amd64', 'Lib/site-packages'),
    'mac-arm': ('aarch64-apple-darwin', 'pypy3.10-v7.3.17-macos_arm64.tar.bz2', 'macosx_11_0_arm64',
                'lib/python3.12/site-packages'),
    'mac-intel': ('x86_64-apple-darwin', 'pypy3.10-v7.3.17-macos_x86_64.tar.bz2', 'macosx_10_13_x86_64',
                  'lib/python3.12/site-packages'),
    'linux': ('x86_64-unknown-linux-gnu', 'pypy3.10-v7.3.17-linux64.tar.bz2', 'manylinux_2_28_x86_64',
              'lib/python3.12/site-packages'),
}

LANZADOR_WINDOWS = r'''@echo off
rem Abre el Ajedrez con el Python incluido (no hace falta instalar nada).
cd /d "%~dp0Juego"
start "" "%~dp0runtime\python\pythonw.exe" ajedrez.py %*
'''
LANZADOR_MAC = '''#!/bin/sh
# Abre el Ajedrez con el Python incluido. La primera vez, macOS puede pedir permiso: clic derecho > Abrir.
cd "$(dirname "$0")"
xattr -dr com.apple.quarantine . 2>/dev/null   # los archivos descargados quedan marcados en cuarentena
cd Juego && exec ../runtime/python/bin/python3 ajedrez.py "$@"
'''
LANZADOR_LINUX = '''#!/bin/sh
# Abre el Ajedrez. Si el sistema tiene Python con Tkinter, lo usa (su Tk dibuja las letras con las fuentes del
# sistema); si no, el Python incluido. La computadora usa siempre el PyPy incluido.
cd "$(dirname "$0")/Juego"
if [ -x /usr/bin/python3 ] && /usr/bin/python3 -c 'import tkinter' 2>/dev/null; then
    exec /usr/bin/python3 ajedrez.py "$@"
fi
exec ../runtime/python/bin/python3 ajedrez.py "$@"
'''
LEEME = '''AJEDREZ — PAQUETE AUTÓNOMO (%(plat)s)

No necesitas instalar Python ni PyPy: vienen incluidos en la carpeta runtime.

1. Deja esta carpeta en un lugar donde puedas escribir (por ejemplo, Documentos); el juego guarda ahí tus
   partidas, tu perfil y tus ajustes.
2. Ábrelo con: %(lanzador)s
   macOS: la primera vez, clic derecho sobre Ajedrez.command > Abrir (el sistema avisa de que no es de la
   App Store). Linux: también puedes ejecutar sh ajedrez.sh desde una terminal.
3. El idioma (español o inglés) se cambia en Ajustes. F1 abre la ayuda.

------------------------------------------------------------------------------------------------------------
CHESS — STANDALONE PACKAGE (%(plat)s)

You don't need to install Python or PyPy: they are included in the runtime folder.

1. Keep this folder somewhere you can write to (for example, Documents); the game saves your games, profile
   and settings there.
2. Open it with: %(lanzador)s
   macOS: the first time, right-click Ajedrez.command > Open (the system warns that it is not from the App
   Store). Linux: you can also run sh ajedrez.sh from a terminal.
3. Change the language (Spanish or English) in Settings. F1 opens the help.
'''


def descargar(url, nombre=None, sha=None):
    """Descarga url en Instalador/descargas (si no estaba) y comprueba su SHA-256. Devuelve la ruta."""
    os.makedirs(DESCARGAS, exist_ok=True)
    ruta = os.path.join(DESCARGAS, nombre or url.rsplit('/', 1)[-1])
    if not os.path.exists(ruta):
        print('  descargando %s…' % url, flush=True)
        tmp = ruta + '.part'
        with urllib.request.urlopen(url, timeout=60) as r, open(tmp, 'wb') as f:
            shutil.copyfileobj(r, f, 1 << 20)
        os.replace(tmp, ruta)
    if sha:
        h = hashlib.sha256()
        with open(ruta, 'rb') as f:
            for bloque in iter(lambda: f.read(1 << 20), b''):
                h.update(bloque)
        if h.hexdigest() != sha:
            os.remove(ruta)
            raise SystemExit('La suma SHA-256 de %s no coincide: descarga dañada o alterada (borrada).' % ruta)
    return ruta


def sha_python(nombre):
    sumas = descargar(PBS + 'SHA256SUMS', 'python-build-standalone-20260924-SHA256SUMS')
    for linea in open(sumas, encoding='utf-8'):
        partes = linea.split()
        if len(partes) == 2 and partes[1] == nombre:
            return partes[0]
    raise SystemExit('No encontré la suma SHA-256 de %s.' % nombre)


def pillow(plataforma):
    """Las ruedas de Pillow para la plataforma (o [] si no se pudieron descargar: el juego funciona sin él)."""
    destino = os.path.join(DESCARGAS, 'pillow-' + plataforma)
    ruedas = [os.path.join(destino, f) for f in os.listdir(destino)] if os.path.isdir(destino) else []
    if ruedas:
        return ruedas
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'download', 'pillow', '--only-binary=:all:', '--no-deps',
                        '--platform', plataforma, '--python-version', '3.12', '-d', destino, '-q'], check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        print('  (sin Pillow: %s; las piezas se verán algo menos nítidas)' % e)
        return []
    return [os.path.join(destino, f) for f in os.listdir(destino) if f.endswith('.whl')]


class Paquete:
    """Escribe el paquete como .zip (Windows: el Explorador lo abre) o .tar.xz (macOS y Linux: conserva enlaces y
    permisos, y comprime las tablas de finales a la mitad que el .zip)."""

    def __init__(self, ruta, es_zip):
        self.es_zip = es_zip
        self.f = zipfile.ZipFile(ruta, 'w', zipfile.ZIP_DEFLATED) if es_zip else tarfile.open(ruta, 'w:xz')
        self.n = 0

    def de_disco(self, nombre, origen, ejecutable=False):
        """Un archivo del disco, copiado por partes (las tablas de finales pesan cientos de MB)."""
        self.n += 1
        if self.es_zip:
            info = zipfile.ZipInfo.from_file(origen, nombre)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if ejecutable else 0o644) << 16
            with open(origen, 'rb') as fh, self.f.open(info, 'w', force_zip64=True) as dest:
                shutil.copyfileobj(fh, dest, 1 << 20)
        else:
            info = self.f.gettarinfo(origen, nombre)
            info.mode = 0o755 if ejecutable else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            with open(origen, 'rb') as fh:
                self.f.addfile(info, fh)

    def archivo(self, nombre, datos, ejecutable=False):
        self.n += 1
        if self.es_zip:
            info = zipfile.ZipInfo(nombre, time.localtime()[:6])
            info.external_attr = (0o755 if ejecutable else 0o644) << 16
            self.f.writestr(info, datos, zipfile.ZIP_DEFLATED)
        else:
            info = tarfile.TarInfo(nombre)
            info.size, info.mode, info.mtime = len(datos), 0o755 if ejecutable else 0o644, time.time()
            self.f.addfile(info, io.BytesIO(datos))

    def de_tar(self, origen, prefijo_viejo, prefijo_nuevo):
        """Copia el contenido de un .tar.* cambiando su carpeta raíz (enlaces y permisos incluidos)."""
        with tarfile.open(origen) as t:
            for m in t.getmembers():
                if not m.name.startswith(prefijo_viejo):
                    continue
                nombre = prefijo_nuevo + m.name[len(prefijo_viejo):]
                if self.es_zip:
                    if m.isfile():
                        self.archivo(nombre, t.extractfile(m).read(), bool(m.mode & 0o111))
                    continue
                m.name = nombre
                if m.islnk() and m.linkname.startswith(prefijo_viejo):
                    m.linkname = prefijo_nuevo + m.linkname[len(prefijo_viejo):]
                self.f.addfile(m, t.extractfile(m) if m.isfile() else None)
                self.n += 1

    def de_zip(self, origen, prefijo_viejo, prefijo_nuevo):
        with zipfile.ZipFile(origen) as z:
            for info in z.infolist():
                if info.is_dir() or not info.filename.startswith(prefijo_viejo):
                    continue
                self.archivo(prefijo_nuevo + info.filename[len(prefijo_viejo):], z.read(info))

    def cerrar(self):
        self.f.close()


def armar(plat, salida_dir, tablas_dos=True):
    py_arq, pypy_nombre, pip_plat, site = PLATAFORMAS[plat]
    print('== %s' % plat, flush=True)
    py_nombre = PYTHON % py_arq
    python = descargar(PBS + py_nombre.replace('+', '%2B'), py_nombre, sha_python(py_nombre))
    pypy = descargar(PYPY + pypy_nombre, sha=PYPY_SHA[pypy_nombre])
    ruedas = pillow(pip_plat)
    es_zip = plat == 'windows'
    ruta = os.path.join(salida_dir, 'Ajedrez_%s_%s.%s' % (plat, time.strftime('%Y%m%d'), 'zip' if es_zip else 'tar.xz'))
    p = Paquete(ruta, es_zip)
    # el juego, como en empaquetar.py (sin datos personales ni resultados de simulaciones)
    for carpeta in CARPETAS:
        for base, dirs, archivos in os.walk(os.path.join(RAIZ, carpeta)):
            dirs[:] = [d for d in dirs if d not in NUNCA and d not in ('descargas', 'dist')]
            for f in archivos:
                origen = os.path.join(base, f)
                rel = os.path.relpath(origen, RAIZ)
                if incluir(rel, False, tablas_dos) and not f.startswith('Ajedrez_'):
                    p.de_disco('Ajedrez/' + rel.replace(os.sep, '/'), origen, f.endswith(('.sh', '.command')))
    for f in ('LICENSE', 'README.md'):  # la licencia (GPL v3) acompaña siempre al juego
        if os.path.exists(os.path.join(RAIZ, f)):
            p.de_disco('Ajedrez/' + f, os.path.join(RAIZ, f), False)
    # Python portátil (con Tkinter) y PyPy
    p.de_tar(python, 'python/', 'Ajedrez/runtime/python/')
    raiz_pypy = pypy_nombre.replace('.zip', '').replace('.tar.bz2', '') + '/'
    if pypy_nombre.endswith('.zip'):
        p.de_zip(pypy, raiz_pypy, 'Ajedrez/runtime/pypy/')
    else:
        p.de_tar(pypy, raiz_pypy, 'Ajedrez/runtime/pypy/')
    for rueda in ruedas:  # una rueda es un .zip que se descomprime tal cual en site-packages
        p.de_zip(rueda, '', 'Ajedrez/runtime/python/%s/' % site)
    # lanzadores y leeme
    lanzador = {'windows': ('Ajedrez.bat', LANZADOR_WINDOWS.replace('\n', '\r\n')),
                'linux': ('ajedrez.sh', LANZADOR_LINUX)}.get(plat, ('Ajedrez.command', LANZADOR_MAC))
    p.archivo('Ajedrez/' + lanzador[0], lanzador[1].encode(), True)
    texto = LEEME % {'plat': plat, 'lanzador': lanzador[0]}
    p.archivo('Ajedrez/LEEME - README.txt', texto.replace('\n', '\r\n' if es_zip else '\n').encode('utf-8'))
    p.cerrar()
    print('  %d archivos en %s (%.0f MB)%s' % (p.n, ruta, os.path.getsize(ruta) / 1e6,
                                               '' if ruedas else ' · sin Pillow'), flush=True)
    return ruta


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--plataforma', choices=sorted(PLATAFORMAS))
    ap.add_argument('--todas', action='store_true', help='los cuatro paquetes')
    ap.add_argument('--salida', default=os.path.join(RAIZ, 'dist'), help='carpeta de los paquetes (dist/)')
    ap.add_argument('--sin-tablas-dos', action='store_true',
                    help='deja fuera las tablas de finales de dos piezas (~2.4 GB sin comprimir)')
    a = ap.parse_args()
    if not a.plataforma and not a.todas:
        ap.error('elige --plataforma o --todas')
    os.makedirs(a.salida, exist_ok=True)
    for plat in (sorted(PLATAFORMAS) if a.todas else [a.plataforma]):
        armar(plat, a.salida, not a.sin_tablas_dos)


if __name__ == '__main__':
    main()
