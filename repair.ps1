# repair.ps1 - Reparieren von Sandbox-FUSE-Truncations und fehlenden Packages
#
# Was es macht:
#   1) python -c -Skript schreibt sheet_providers.py mit garantiert sauberem
#      Inhalt neu (loest IndentationError am Ende der Datei)
#   2) pip install caldav icalendar (fehlte trotz requirements.txt-Eintrag)
#   3) Test-Run zur Verifikation

Set-Location $PSScriptRoot

Write-Host ""
Write-Host "=== 1) sheet_providers.py von Grund auf neu schreiben ===" -ForegroundColor Cyan

$cleanSrc = @'
# -*- coding: utf-8 -*-
"""utils.sheet_providers - Sheet-source abstraction (Google + uniCLOUD)."""
from __future__ import annotations
import abc
import csv
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional
import requests
from utils.secrets import get_secret
from utils.unicloud import UniCloudClient

log = logging.getLogger(__name__)

MAIN_CSV = "google_spreadsheet.csv"
INFO_CSV = "google_spreadsheet_information.csv"


class SheetProviderError(RuntimeError):
    pass


class SheetProvider(abc.ABC):
    @abc.abstractmethod
    def fetch(self, env_data: dict, config_data: dict, data_dir: Path) -> None: ...


class GoogleSheetProvider(SheetProvider):
    """Wraps the original download_g_s logic for Google Sheets."""

    def fetch(self, env_data: dict, config_data: dict, data_dir: Path) -> None:
        url = env_data.get("google_spreadsheet_url")
        if not url:
            raise SheetProviderError("google: env_data['google_spreadsheet_url'] missing")
        spreadsheet_id = url.split("/d/")[1].split("/")[0]
        info_sheet_name = config_data["information"]

        page = requests.get(f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
        html = page.text
        idx = html.find("resizeApp")
        if idx == -1:
            raise SheetProviderError("could not parse Google edit page")
        cleaned = re.sub(r"[^\w\s,]", "", html[idx:])
        cleaned = re.sub(r"\b\d{1,8}\b", "", cleaned)
        cleaned = re.sub(r"\b\w{21,}\b", "", cleaned)
        pattern = rf"(\d+)\s*,*\s*{re.escape(info_sheet_name)}"
        match = re.search(pattern, cleaned)

        data_dir.mkdir(parents=True, exist_ok=True)
        main_resp = requests.get(
            f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
        )
        if main_resp.status_code != 200:
            raise SheetProviderError(f"Google main export failed: HTTP {main_resp.status_code}")
        (data_dir / MAIN_CSV).write_bytes(main_resp.content)
        print(f"File saved as '{MAIN_CSV}'")

        if match:
            info_resp = requests.get(
                f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
                f"/export?format=csv&id={spreadsheet_id}&gid={match.group(1)}"
            )
            if info_resp.status_code == 200:
                (data_dir / INFO_CSV).write_bytes(info_resp.content)
                print(f"File saved as '{INFO_CSV}'")
            else:
                raise SheetProviderError(f"Google info export failed: HTTP {info_resp.status_code}")
        else:
            raise SheetProviderError(f"Could not locate gid for sheet '{info_sheet_name}'")


class UniCloudSheetProvider(SheetProvider):
    """Downloads xlsx from uniCLOUD and splits its two sheets into CSVs."""

    def __init__(self, username, xlsx_path, main_sheet=None, info_sheet="information"):
        if not username:
            raise ValueError("UniCloudSheetProvider needs username")
        if not xlsx_path:
            raise ValueError("UniCloudSheetProvider needs xlsx_path")
        self.username = username
        self.xlsx_path = xlsx_path
        self.main_sheet = main_sheet
        self.info_sheet = info_sheet

    def fetch(self, env_data: dict, config_data: dict, data_dir: Path) -> None:
        try:
            from openpyxl import load_workbook
        except ImportError as e:
            raise SheetProviderError(
                "openpyxl missing; run: pip install -r requirements.txt"
            ) from e

        client = UniCloudClient(username=self.username)
        data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            local_xlsx = Path(tmp) / "sheet.xlsx"
            client.download(self.xlsx_path, local_xlsx)
            log.info("downloaded %s (%d bytes)", self.xlsx_path, local_xlsx.stat().st_size)

            wb = load_workbook(local_xlsx, data_only=True, read_only=True)
            sheet_names = wb.sheetnames

            main_name = self.main_sheet or sheet_names[0]
            if main_name not in sheet_names:
                raise SheetProviderError(
                    f"Main sheet '{main_name}' not found. Available: {sheet_names}"
                )
            if self.info_sheet not in sheet_names:
                raise SheetProviderError(
                    f"Info sheet '{self.info_sheet}' not found. Available: {sheet_names}"
                )

            _dump_sheet_as_csv(wb[main_name], data_dir / MAIN_CSV)
            print(f"uniCLOUD sheet '{main_name}' saved as '{MAIN_CSV}'")
            _dump_sheet_as_csv(wb[self.info_sheet], data_dir / INFO_CSV)
            print(f"uniCLOUD sheet '{self.info_sheet}' saved as '{INFO_CSV}'")
            wb.close()


def _serialize_cell(cell) -> str:
    """openpyxl cell -> CSV-string. Handles Excel time-of-day-on-1900-epoch glitch."""
    import datetime as _dt
    if cell is None:
        return ""
    if isinstance(cell, _dt.time) and not isinstance(cell, _dt.datetime):
        return cell.strftime("%H:%M")
    if isinstance(cell, _dt.datetime):
        if cell.year <= 1900:
            return cell.strftime("%H:%M")
        if cell.hour == 0 and cell.minute == 0 and cell.second == 0:
            return cell.strftime("%d.%m.%Y")
        return cell.strftime("%d.%m.%Y %H:%M")
    if isinstance(cell, _dt.date):
        return cell.strftime("%d.%m.%Y")
    return str(cell)


def _dump_sheet_as_csv(worksheet, out_path: Path) -> None:
    """Write all rows of a worksheet to CSV (UTF-8, comma-separated)."""
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for row in worksheet.iter_rows(values_only=True):
            writer.writerow([_serialize_cell(c) for c in row])


def make_sheet_provider(config_data: dict) -> SheetProvider:
    sp = config_data.get("sheet_provider")
    if not sp:
        return GoogleSheetProvider()
    ptype = sp.get("type")
    if ptype == "google":
        return GoogleSheetProvider()
    if ptype == "unicloud":
        return UniCloudSheetProvider(
            username=sp["username"],
            xlsx_path=sp["xlsx_path"],
            main_sheet=sp.get("main_sheet"),
            info_sheet=sp.get("info_sheet", "information"),
        )
    raise SheetProviderError(f"Unknown sheet_provider type: {ptype!r}")
'@

# Force-write die Datei nativ ueber NTFS (umgeht FUSE-Cache komplett)
Set-Content -Path "utils\sheet_providers.py" -Value $cleanSrc -Encoding UTF8
$lineCount = (Get-Content "utils\sheet_providers.py" | Measure-Object -Line).Lines
Write-Host "[OK] sheet_providers.py neu geschrieben - $lineCount Zeilen"

Write-Host ""
Write-Host "=== 2) Syntax-Check ===" -ForegroundColor Cyan
$check = python -c "import ast; ast.parse(open('utils/sheet_providers.py').read()); print('syntax OK')"
Write-Host $check

Write-Host ""
Write-Host "=== 3) Fehlende Python-Packages installieren ===" -ForegroundColor Cyan
pip install caldav icalendar 2>&1 | Select-Object -Last 3

Write-Host ""
Write-Host "=== 4) Tests erneut laufen ===" -ForegroundColor Cyan
$output = python -m unittest discover -s tests 2>&1 | Out-String
$failsAndOk = $output -split "`n" | Select-String -Pattern "^(Ran|OK|FAILED|ERROR:|FAIL:)"
$failsAndOk | ForEach-Object { Write-Host $_ }

Write-Host ""
Write-Host "[FERTIG]" -ForegroundColor Green
Write-Host "Wenn alles 'OK' zeigt: .\dev.ps1 commit"
