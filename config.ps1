# config.ps1 - Interaktive Config-UI fuer termino_clean
#
# Was es kann:
#   - Mail-Provider switchen (yahoo-smtp / uni-graz-ews)
#   - Sheet-Provider switchen (google / unicloud)
#   - Calendar-Provider switchen (none / unicloud-caldav / uni-graz-ews)
#   - Keyring-Secrets setzen/aendern
#   - Study-Metadaten aendern (study_name, study_location, booking_list)
#
# Schreibt mit utf8NoBOM, damit Python's json.tool keine Warnings produziert.

Set-Location $PSScriptRoot

function Read-Config {
    if (-not (Test-Path "config.json")) {
        Write-Host "[ERR] config.json fehlt" -ForegroundColor Red; exit 1
    }
    return Get-Content "config.json" -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Write-Config($cfg) {
    # 1) Backup
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item "config.json" "config.backup.$ts.json"
    Write-Host "[INFO] Backup: config.backup.$ts.json" -ForegroundColor DarkGray

    # 2) JSON-text bauen (mit Indent)
    $json = $cfg | ConvertTo-Json -Depth 10

    # 3) Direkt mit .NET-File-Write (PowerShell Out-File schreibt BOM auch bei -Encoding UTF8;
    #    erst PS 7's utf8NoBOM ist sauber. .NET WriteAllText ist UTF-8 ohne BOM by default.)
    [System.IO.File]::WriteAllText(
        (Join-Path $PWD "config.json"),
        $json,
        [System.Text.UTF8Encoding]::new($false)   # $false = no BOM
    )

    # 4) Pretty-print durch python's json.tool fuer lesbares Diff
    $tmp = Join-Path $PWD "config.pretty.json"
    & python -m json.tool config.json $tmp 2>&1 | Out-Null
    if (Test-Path $tmp) {
        Move-Item -Force $tmp config.json
    }

    Write-Host "[OK] config.json gespeichert" -ForegroundColor Green
}

function Show-Menu([string]$title, [string[]]$options, [int]$current = -1) {
    Write-Host ""
    Write-Host "===== $title =====" -ForegroundColor Cyan
    for ($i = 0; $i -lt $options.Count; $i++) {
        $marker = if ($i -eq $current) { "[*]" } else { "[ ]" }
        Write-Host "  $($i + 1)) $marker $($options[$i])"
    }
    Write-Host "  q) zurueck"
    $choice = Read-Host "Auswahl"
    if ($choice -eq "q") { return -1 }
    $n = 0
    if ([int]::TryParse($choice, [ref]$n) -and $n -ge 1 -and $n -le $options.Count) {
        return $n - 1
    }
    return -1
}

function Set-MailProvider($cfg) {
    $current = if ($cfg.mail_provider) { $cfg.mail_provider.type } else { "none" }
    $opts = @("yahoo-smtp (legacy, Yahoo-App-PW)", "uni-graz-ews (EWS via VPN)")
    $curIdx = if ($current -eq "yahoo-smtp") { 0 } elseif ($current -eq "uni-graz-ews") { 1 } else { -1 }

    $idx = Show-Menu "Mail-Provider waehlen" $opts $curIdx
    if ($idx -lt 0) { return $cfg }

    $type = @("yahoo-smtp", "uni-graz-ews")[$idx]
    $defaultUser = if ($type -eq "yahoo-smtp") { "your-mail@yahoo.com" } else { "your-mail@your-uni.at" }
    $cur = if ($cfg.mail_provider) { $cfg.mail_provider.username } else { "" }
    if (-not $cur) { $cur = $defaultUser }
    $newUser = Read-Host "Username (Enter = $cur)"
    if (-not $newUser) { $newUser = $cur }

    $cfg | Add-Member -NotePropertyName mail_provider `
        -NotePropertyValue ([pscustomobject]@{ type = $type; username = $newUser }) -Force
    return $cfg
}

function Set-SheetProvider($cfg) {
    $current = if ($cfg.sheet_provider) { $cfg.sheet_provider.type } else { "google" }
    $opts = @("google (Google Sheets)", "unicloud (uniCLOUD xlsx)")
    $curIdx = if ($current -eq "google") { 0 } elseif ($current -eq "unicloud") { 1 } else { -1 }

    $idx = Show-Menu "Sheet-Provider waehlen" $opts $curIdx
    if ($idx -lt 0) { return $cfg }

    if ($idx -eq 0) {
        $cfg | Add-Member -NotePropertyName sheet_provider `
            -NotePropertyValue ([pscustomobject]@{ type = "google" }) -Force
    } else {
        $cur = $cfg.sheet_provider
        $user = Read-Host "uniCLOUD username (Enter = $($cur.username))"
        if (-not $user) { $user = $cur.username }
        $path = Read-Host "xlsx-Pfad (Enter = $($cur.xlsx_path))"
        if (-not $path) { $path = $cur.xlsx_path }
        $cfg | Add-Member -NotePropertyName sheet_provider -NotePropertyValue ([pscustomobject]@{
            type = "unicloud"; username = $user; xlsx_path = $path
            main_sheet = "Zeittabelle"; info_sheet = "information"
        }) -Force
    }
    return $cfg
}

function Set-CalendarProvider($cfg) {
    $current = if ($cfg.calendar_provider) { $cfg.calendar_provider.type } else { "none" }
    $opts = @("none (kein Kalender)", "unicloud-caldav (uniCLOUD)", "uni-graz-ews (Outlook via VPN)")
    $curIdx = switch ($current) { "none" {0} "unicloud-caldav" {1} "uni-graz-ews" {2} default {-1} }

    $idx = Show-Menu "Kalender-Provider waehlen" $opts $curIdx
    if ($idx -lt 0) { return $cfg }

    switch ($idx) {
        0 {
            $cfg | Add-Member -NotePropertyName calendar_provider `
                -NotePropertyValue ([pscustomobject]@{ type = "none" }) -Force
        }
        1 {
            $user = Read-Host "Nextcloud-Username (z.B. your-username_edu)"
            $calName = Read-Host "Kalender-Name (Enter = Termino)"
            if (-not $calName) { $calName = "Termino" }
            $cfg | Add-Member -NotePropertyName calendar_provider -NotePropertyValue ([pscustomobject]@{
                type = "unicloud-caldav"; username = $user; calendar_name = $calName
            }) -Force
        }
        2 {
            $user = Read-Host "EWS-Username (z.B. your-mail@your-uni.at)"
            $cfg | Add-Member -NotePropertyName calendar_provider -NotePropertyValue ([pscustomobject]@{
                type = "uni-graz-ews"; username = $user
            }) -Force
        }
    }
    return $cfg
}

function Set-StudyMetadata($cfg) {
    $cur = $cfg.study_name
    $new = Read-Host "study_name (Enter = $cur)"
    if ($new) { $cfg.study_name = $new }
    $cur = $cfg.study_location
    $new = Read-Host "study_location (Enter = $cur)"
    if ($new) { $cfg.study_location = $new }
    $cur = $cfg.booking_list
    $new = Read-Host "booking_list (Enter = $cur)"
    if ($new) { $cfg.booking_list = $new }
    return $cfg
}

function Set-KeyringSecret {
    Write-Host ""
    Write-Host "===== Keyring-Secret setzen =====" -ForegroundColor Cyan
    Write-Host "  1) termino-pw           (termino.gv.at Passwort)"
    Write-Host "  2) yahoo-app-pw         (Yahoo App-Passwort)"
    Write-Host "  3) unicloud-app-pw      (Nextcloud App-Passwort)"
    Write-Host "  4) uni-login-pw         (Uni-Login fuer EWS+VPN)"
    Write-Host "  q) zurueck"
    $c = Read-Host "Auswahl"
    switch ($c) {
        "1" { python -m utils.secrets set termino-pw }
        "2" { python -m utils.secrets set yahoo-app-pw }
        "3" { python -m utils.secrets set unicloud-app-pw }
        "4" {
            $email = Read-Host "Uni-Email"
            python -m utils.secrets set --email $email --vpn
        }
    }
}

function Show-CurrentConfig($cfg) {
    Write-Host ""
    Write-Host "===== AKTUELLE KONFIGURATION =====" -ForegroundColor Yellow
    Write-Host ("  Studienname     : {0}" -f $cfg.study_name)
    Write-Host ("  Studienort      : {0}" -f $cfg.study_location)
    Write-Host ("  Buchungsliste   : {0}" -f $cfg.booking_list)
    Write-Host ""
    Write-Host ("  Mail-Provider   : {0} -> {1}" -f $cfg.mail_provider.type, $cfg.mail_provider.username)
    Write-Host ("  Sheet-Provider  : {0} -> {1}" -f $cfg.sheet_provider.type, $cfg.sheet_provider.xlsx_path)
    Write-Host ("  Calendar-Prov.  : {0}" -f $cfg.calendar_provider.type)
    if ($cfg.calendar_provider.username) {
        Write-Host ("                    {0}" -f $cfg.calendar_provider.username)
    }
}

# ===== Main Loop =====
$cfg = Read-Config
while ($true) {
    Show-CurrentConfig $cfg
    Write-Host ""
    Write-Host "===== AKTION =====" -ForegroundColor Cyan
    Write-Host "  1) Mail-Provider aendern"
    Write-Host "  2) Sheet-Provider aendern"
    Write-Host "  3) Kalender-Provider aendern"
    Write-Host "  4) Studien-Metadaten aendern (Name/Ort/Buchungsliste)"
    Write-Host "  5) Keyring-Secret setzen"
    Write-Host "  s) Aenderungen speichern (bleibt im Menue)"
    Write-Host "  x) Speichern + beenden"
    Write-Host "  q) Abbrechen ohne speichern"
    $c = Read-Host "Auswahl"

    switch ($c) {
        "1" { $cfg = Set-MailProvider $cfg }
        "2" { $cfg = Set-SheetProvider $cfg }
        "3" { $cfg = Set-CalendarProvider $cfg }
        "4" { $cfg = Set-StudyMetadata $cfg }
        "5" { Set-KeyringSecret }
        "s" {
            Write-Config $cfg
            # reload to pick up any reformatting
            $cfg = Read-Config
        }
        "x" {
            Write-Config $cfg
            Write-Host ""
            Write-Host "Beendet." -ForegroundColor Green
            exit 0
        }
        "q" {
            Write-Host ""
            Write-Host "Abgebrochen - keine Aenderungen gespeichert." -ForegroundColor Yellow
            exit 0
        }
        default {
            Write-Host "Ungueltige Auswahl: '$c'" -ForegroundColor Red
        }
    }
}
