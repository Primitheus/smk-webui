param([switch]$NoAutoStart)
$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $source 'SMK WebUI.exe'))) { throw 'Extract the full app package before installing.' }
$target = Join-Path $env:LOCALAPPDATA 'Programs\SMK WebUI'
if ([IO.Path]::GetFullPath($source) -eq [IO.Path]::GetFullPath($target)) { throw 'Run Install from the extracted download folder.' }
function Stop-InstalledApp {
    param([string]$AppFolder)
    $session = $null
    try { $session = Invoke-RestMethod 'http://127.0.0.1:8765/api/session' -TimeoutSec 2 } catch { }
    if ($session -and $session.app -eq 'SMK WebUI') {
        Invoke-RestMethod 'http://127.0.0.1:8765/api/quit' -Method Post -ContentType 'application/json' -Headers @{'X-SMK-Token'=$session.token} -Body '{}' -TimeoutSec 5 | Out-Null
    }
    $prefix = [IO.Path]::GetFullPath($AppFolder).TrimEnd('\') + '\'
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        $running = @(Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -and $_.ProcessName -in @('python','pythonw','SMK WebUI') })
        if (-not $running.Count) { return }
        if ([DateTime]::UtcNow -ge $deadline) { throw 'SMK WebUI is still running. Close it before continuing.' }
        Start-Sleep -Milliseconds 250
    } while ($true)
}
Stop-InstalledApp -AppFolder $target

$wasInstalled = Test-Path -LiteralPath (Join-Path $target 'SMK WebUI.exe')
New-Item -ItemType Directory -Path $target -Force | Out-Null
foreach ($name in @('app','runtime','SMK WebUI.exe','README.md','LICENSE','Uninstall.ps1')) {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination $target -Recurse -Force
}
if ((Test-Path -LiteralPath (Join-Path $source 'data')) -and -not (Test-Path -LiteralPath (Join-Path $target 'data'))) {
    Copy-Item -LiteralPath (Join-Path $source 'data') -Destination $target -Recurse
}
$exe = Join-Path $target 'SMK WebUI.exe'
$menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'SMK WebUI.lnk'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($menu)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = $target
$shortcut.IconLocation = $exe
$shortcut.Save()
$run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
New-Item -Path $run -Force | Out-Null
if ($NoAutoStart) { Remove-ItemProperty -Path $run -Name SMKWebUI -ErrorAction SilentlyContinue }
elseif (-not $wasInstalled -or (Get-ItemProperty -Path $run -Name SMKWebUI -ErrorAction SilentlyContinue)) { New-ItemProperty -Path $run -Name SMKWebUI -Value ('"' + $exe + '" --background') -PropertyType String -Force | Out-Null }
$uninstall = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SMKWebUI'
New-Item -Path $uninstall -Force | Out-Null
New-ItemProperty -Path $uninstall -Name DisplayName -Value 'SMK WebUI' -Force | Out-Null
New-ItemProperty -Path $uninstall -Name DisplayIcon -Value $exe -Force | Out-Null
New-ItemProperty -Path $uninstall -Name UninstallString -Value ('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $target 'Uninstall.ps1') + '"') -Force | Out-Null
Write-Host "Installed: $target"
Start-Process -FilePath $exe -WorkingDirectory $target -WindowStyle Hidden
