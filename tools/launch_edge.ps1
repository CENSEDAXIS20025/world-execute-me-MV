<#
  launch_edge.ps1 -- start a headless Chromium browser with the DevTools
  Protocol enabled, then print the page's webSocketDebuggerUrl.

  Extracted from the session that built world.execute(me)-MV.html
  (session-4e991631, turn 1 steps 14 / 21 / 22).

  This is step 1 of the visual feedback loop: it makes the animation
  drivable and screenshottable from a script, which is what let the model
  actually look at its own output instead of writing blind.

  NOTE: this file is ASCII-only on purpose. Windows PowerShell 5.1 decodes
  BOM-less .ps1 files using the system ANSI codepage, so non-ASCII comments
  can corrupt parsing.

  Usage:
    powershell -File launch_edge.ps1 -HtmlPath "C:\path\world.execute(me)-MV.html"
    powershell -File launch_edge.ps1 -HtmlPath ... -Port 9334 -WindowSize 1600,900
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$HtmlPath,
  [int]$Port = 9334,
  [string]$WindowSize = '1280,720',
  [string]$ProfileDir = "$env:TEMP\_mv_cdp_profile",
  [int]$WaitSeconds = 5
)

$ErrorActionPreference = 'Stop'

if(-not (Test-Path -LiteralPath $HtmlPath)){ throw "Html not found: $HtmlPath" }

# --- locate a Chromium-family browser ---
$candidates = @(
  'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
  'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
)
$browser = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if(-not $browser){ throw 'No Edge/Chrome found in the usual locations.' }
Write-Host "browser: $browser"

if(Test-Path -LiteralPath $ProfileDir){
  Remove-Item -LiteralPath $ProfileDir -Recurse -Force -ErrorAction SilentlyContinue
}

# file:// URL needs forward slashes
$uri = 'file:///' + ($HtmlPath -replace '\\','/')

$flags = @(
  '--headless=new',
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  '--autoplay-policy=no-user-gesture-required',   # let <audio>.play() work headless
  "--remote-debugging-port=$Port",
  "--user-data-dir=$ProfileDir",
  "--window-size=$WindowSize",
  $uri
)

Start-Process -FilePath $browser -ArgumentList $flags -WindowStyle Hidden
Write-Host "started; waiting $WaitSeconds s for the devtools endpoint ..."
Start-Sleep -Seconds $WaitSeconds

try {
  $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json" -TimeoutSec 5
  $page = $targets | Where-Object { $_.type -eq 'page' -and $_.url -like '*file*' } | Select-Object -First 1
  if(-not $page){ $page = $targets | Where-Object { $_.type -eq 'page' } | Select-Object -First 1 }
  Write-Host ''
  Write-Host "webSocketDebuggerUrl: $($page.webSocketDebuggerUrl)"
  Write-Host "url                 : $($page.url)"
} catch {
  Write-Host "devtools endpoint not reachable on port $Port : $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
