$ErrorActionPreference = 'Stop'
$expected = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs\SMK WebUI'))
$target = [IO.Path]::GetFullPath($PSScriptRoot)
if ($target -ne $expected) { throw 'Uninstall must run from the installed app folder.' }
if ((Read-Host 'Remove SMK WebUI? Saved settings will be kept. Type YES') -ne 'YES') { exit }
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

Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name SMKWebUI -ErrorAction SilentlyContinue
Remove-Item -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SMKWebUI' -ErrorAction SilentlyContinue
$shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'SMK WebUI.lnk'
Remove-Item -LiteralPath $shortcut -ErrorAction SilentlyContinue
foreach ($name in @('app','runtime','SMK WebUI.exe','README.md','LICENSE')) {
    $path = [IO.Path]::GetFullPath((Join-Path $target $name))
    if (-not $path.StartsWith($expected + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected uninstall path.' }
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
}
Write-Host "Removed. Settings remain in $target\data"
