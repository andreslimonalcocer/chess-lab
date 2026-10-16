# Instalador para Windows: comprueba Python (con Tkinter), instala Pillow y crea accesos directos
# en el escritorio y en el menú Inicio.
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
$juego = Join-Path $raiz 'Juego'
Write-Host "Carpeta del juego: $raiz"

$py = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue) }
if (-not $py) {
    Write-Host 'No encontré Python 3. Intentando instalarlo con winget...'
    try { winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements }
    catch { Write-Host 'Descárgalo de https://www.python.org/downloads/windows/ (marca «Add python.exe to PATH»).'; exit 1 }
    Write-Host 'Python instalado. Cierra esta ventana y vuelve a ejecutar el instalador.'
    exit 0
}
$exe = $py.Source
$args0 = @()
if ($py.Name -like 'py*.exe' -and $py.Name -notlike 'python*') { $args0 = @('-3') }

& $exe @args0 -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Tu Python no tiene Tkinter. Reinstala Python desde python.org con la opción «tcl/tk and IDLE».'
    exit 1
}
& $exe @args0 -c "import PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Instalando Pillow (mejora el dibujo de las piezas)...'
    & $exe @args0 -m pip install --user pillow
}

# pythonw.exe: abre el juego sin ventana de consola
$pythonw = & $exe @args0 -c "import sys, os; print(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))"
$icono = Join-Path $juego 'ajedrez.ico'
& $exe @args0 -c "from PIL import Image; Image.open(r'$raiz\Piezas\blancas\png\rey.png').save(r'$icono', sizes=[(64,64),(32,32),(16,16)])" 2>$null

$shell = New-Object -ComObject WScript.Shell
foreach ($carpeta in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $acceso = $shell.CreateShortcut((Join-Path $carpeta 'Ajedrez.lnk'))
    $acceso.TargetPath = $pythonw
    $acceso.Arguments = '"' + (Join-Path $juego 'ajedrez.py') + '"'
    $acceso.WorkingDirectory = $juego
    if (Test-Path $icono) { $acceso.IconLocation = $icono }
    $acceso.Description = 'Ajedrez clásico, 11x11, Capablanca, gótico y variantes propias'
    $acceso.Save()
}
Write-Host 'Listo: hay un acceso directo «Ajedrez» en el escritorio y en el menú Inicio.'
if (-not (Get-Command pypy3 -ErrorAction SilentlyContinue)) {
    Write-Host 'Sugerencia: instala PyPy (https://pypy.org/download.html) y agrega su carpeta al PATH;'
    Write-Host 'la computadora piensa varias veces más rápido con él.'
}
