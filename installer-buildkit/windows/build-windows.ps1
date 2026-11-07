$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install --upgrade pip
python -m pip install -r windows/requirements-build.txt

$OpenSslCommand = Get-Command openssl -ErrorAction Stop
$OpenSslBin = Split-Path -Parent $OpenSslCommand.Source
$OpenSslHome = Split-Path -Parent $OpenSslBin
if (!(Test-Path (Join-Path $OpenSslBin 'openssl.exe'))) { throw 'OpenSSL 3 executable not found.' }

if (Test-Path 'build') { Remove-Item 'build' -Recurse -Force }
if (Test-Path 'dist') { Remove-Item 'dist' -Recurse -Force }
pyinstaller --noconfirm --clean --windowed --onedir --name 'sl4m3d Signer' --add-data 'linux\source-portable\app\assets;assets' linux\source-portable\app\src\signer.py

$Bundle = Join-Path (Get-Location) 'dist\sl4m3d Signer\openssl'
New-Item -ItemType Directory -Force -Path $Bundle | Out-Null
Copy-Item (Join-Path $OpenSslHome '*') $Bundle -Recurse -Force
$BundledOpenSsl = Join-Path $Bundle 'bin\openssl.exe'
if (!(Test-Path $BundledOpenSsl)) { throw 'Bundled OpenSSL executable missing after copy.' }

$Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (!$Iscc) { $Iscc = Get-Command ISCC -ErrorAction SilentlyContinue }
if (!$Iscc) { throw 'Inno Setup 6 (ISCC.exe) is required.' }
& $Iscc.Source 'windows\installer.iss'
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
$Installer = Get-ChildItem 'windows\output\*.exe' | Select-Object -First 1
if (!$Installer) { throw 'Installer EXE was not generated.' }
Get-FileHash $Installer.FullName -Algorithm SHA256
Write-Host "BUILT: $($Installer.FullName)"
