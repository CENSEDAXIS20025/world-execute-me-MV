<#
  verify_html.ps1 -- integrity check for the assembled single-file MV.

  Extracted from the session that built world.execute(me)-MV.html
  (session-4e991631, turn 1 steps 39 and 40).

  It answers: did the build actually finish? Specifically --
    * the audio placeholder was replaced (otherwise the file is a dud)
    * the embedded data URI really starts with the expected MP3 header
    * the scene table exists
    * the document is closed properly
    * size + SHA256, for comparing copies of the artifact

  NOTE: ASCII-only on purpose. Windows PowerShell 5.1 decodes BOM-less .ps1
  files using the system ANSI codepage, so non-ASCII comments can break parsing.

  Usage:
    powershell -File verify_html.ps1 -Path "C:\path\world.execute(me)-MV.html"
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Path,
  [string]$Placeholder = '__AUDIO_BASE64__'
)

$ErrorActionPreference = 'Stop'
if(-not (Test-Path -LiteralPath $Path)){ throw "File not found: $Path" }

$item = Get-Item -LiteralPath $Path
$hash = Get-FileHash -LiteralPath $Path -Algorithm SHA256
$text = [System.IO.File]::ReadAllText($Path)

Write-Host "file            : $($item.FullName)"
Write-Host "size            : $($item.Length) bytes ($([math]::Round($item.Length/1MB,3)) MB)"
Write-Host "sha256          : $($hash.Hash)"
Write-Host "modified        : $($item.LastWriteTime)"
Write-Host ''
Write-Host '--- integrity ---'

$checks = [ordered]@{
  'placeholder gone'      = -not $text.Contains($Placeholder)
  'audio data uri present'= $text.Contains('data:audio/')
  'mp3 frame header'      = $text.Contains('data:audio/mpeg;base64,SUQzAwA')
  'scene table present'   = $text.Contains('const SCENES = [')
  'lyrics embedded'       = $text.Contains('LYRICS_RAW')
  'document closed'       = $text.TrimEnd().EndsWith('</html>')
}

$fail = 0
foreach($k in $checks.Keys){
  $ok = $checks[$k]
  if(-not $ok){ $fail++ }
  Write-Host ("  [{0}] {1}" -f $(if($ok){'OK'}else{'!!'}), $k)
}

Write-Host ''
if($fail -gt 0){
  Write-Host "$fail check(s) FAILED -- the build did not complete cleanly." -ForegroundColor Red
  exit 1
}
Write-Host 'all checks passed.' -ForegroundColor Green
