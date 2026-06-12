# -*- coding: utf-8 -*-
"""
utils.run_report
================

Sammelt strukturierten Bericht ueber einen Daily-Run und liefert
sowohl einen knappen Console-Summary als auch einen ausfuehrlichen
HTML-Bericht der per Mail an die Studienleitung geschickt wird.

Design
------
Ein RunReport-Objekt wird einmal pro Lauf in main.py erzeugt.
Jeder Task ruft report.add_phase(name, status, details, count=...).
Warnings/Errors gehen separat ueber report.add_warning() bzw
report.add_error() rein - sie tauchen sowohl im Summary als auch im
Mail-Report auf.

Am Ende des Runs:

- ``report.to_console_summary()`` gibt eine kurze textbasierte
  Zusammenfassung, max 20 Zeilen - das ist was der User in PowerShell
  sieht. Knapp und professionell.
- ``report.to_html()`` gibt einen vollstaendigen HTML-Bericht, der
  per Mail (mit Tabellen, Counts, allen Warnings) zurueck an die
  Studienleitung geht.
- ``report.send(sender, env_data, config_data)`` packt beide zusammen
  und schickt die Mail.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class PhaseReport:
    name: str
    status: str           # "ok" | "warning" | "error" | "skipped"
    details: str = ""     # short one-liner
    count: int = 0        # primary metric (e.g. mails sent, slots inserted)
    extras: dict = field(default_factory=dict)


@dataclass
class RunReport:
    """In-memory log of one daily run, used for the end-of-run mail."""
    started: datetime = field(default_factory=datetime.now)
    finished: Optional[datetime] = None
    phases: List[PhaseReport] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    # Full traceback for an unexpected crash, rendered as an escaped <pre> in
    # the HTML mail so a post-mortem has the source location - not just the
    # exception type. Empty on a clean run.
    error_detail: str = ""

    # ---- collection helpers ---------------------------------------------

    def add_phase(
        self,
        name: str,
        status: str = "ok",
        details: str = "",
        count: int = 0,
        **extras,
    ) -> None:
        self.phases.append(
            PhaseReport(name=name, status=status, details=details,
                        count=count, extras=extras)
        )

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def set_error_detail(self, detail: str) -> None:
        """Attach a full traceback (or other long error text) to the report."""
        self.error_detail = detail or ""

    def finalize(self) -> None:
        if self.finished is None:
            self.finished = datetime.now()

    # ---- output formats -------------------------------------------------

    def _status_icon(self, status: str) -> str:
        return {
            "ok":      "[OK]",
            "warning": "[!!]",
            "error":   "[XX]",
            "skipped": "[--]",
        }.get(status, "[??]")

    def to_console_summary(self) -> str:
        """Short textual summary for stdout (~10-20 lines, all ASCII)."""
        self.finalize()
        lines = []
        lines.append("=" * 56)
        lines.append(f" TERMINO DAILY RUN - {self.started:%d.%m.%Y %H:%M}")
        lines.append("=" * 56)
        for p in self.phases:
            icon = self._status_icon(p.status)
            head = f"{icon} {p.name:30s}"
            if p.count:
                head += f"  ({p.count})"
            if p.details:
                head += f"  {p.details}"
            lines.append(head)
        lines.append("-" * 56)
        if self.errors:
            lines.append(f"  Errors  : {len(self.errors)}")
        if self.error_detail:
            last = next(
                (ln for ln in reversed(self.error_detail.splitlines())
                 if ln.strip()),
                "",
            )
            if last:
                lines.append(f"  Cause   : {last.strip()}")
        if self.warnings:
            lines.append(f"  Warnings: {len(self.warnings)}")
        dur = (self.finished - self.started).total_seconds()
        lines.append(f"  Duration: {dur:.0f}s")
        if not self.errors and not self.warnings:
            lines.append("  All phases OK.")
        return "\n".join(lines)

    def to_html(self, study_name: str = "Termino") -> str:
        """Long-form HTML report, used as the mail body."""
        self.finalize()
        rows = []
        for p in self.phases:
            colour = {
                "ok":      "#d4edda",
                "warning": "#fff3cd",
                "error":   "#f8d7da",
                "skipped": "#e2e3e5",
            }.get(p.status, "#ffffff")
            rows.append(
                f'<tr style="background:{colour}">'
                f'<td>{p.name}</td>'
                f'<td>{p.status.upper()}</td>'
                f'<td>{p.count or ""}</td>'
                f'<td>{p.details}</td>'
                "</tr>"
            )
        warns_html = ""
        if self.warnings:
            warns_html = ("<h3>Warnings</h3><ul>"
                          + "".join(f"<li>{w}</li>" for w in self.warnings)
                          + "</ul>")
        errs_html = ""
        if self.errors:
            errs_html = ("<h3>Errors</h3><ul>"
                         + "".join(f"<li>{e}</li>" for e in self.errors)
                         + "</ul>")
        detail_html = ""
        if self.error_detail:
            detail_html = (
                "<h3>Traceback</h3>"
                "<pre style='background:#f8d7da;padding:8px;border-radius:4px;"
                "white-space:pre-wrap;font-size:0.85em'>"
                + html.escape(self.error_detail)
                + "</pre>"
            )
        dur = (self.finished - self.started).total_seconds()
        return (
            "<html><body style='font-family:sans-serif'>"
            f"<h2>{study_name} - Daily Run Report</h2>"
            f"<p><b>Started:</b> {self.started:%d.%m.%Y %H:%M:%S}<br>"
            f"<b>Finished:</b> {self.finished:%d.%m.%Y %H:%M:%S}<br>"
            f"<b>Duration:</b> {dur:.0f}s</p>"
            "<table border='1' cellpadding='6' cellspacing='0' "
            "style='border-collapse:collapse'>"
            "<tr><th>Phase</th><th>Status</th><th>Count</th><th>Details</th></tr>"
            + "".join(rows) + "</table>"
            + warns_html + errs_html + detail_html
            + "<p style='color:#888;font-size:0.85em'>"
            "automatisch generierter Bericht vom Termino-Skript</p>"
            "</body></html>"
        )

    def has_failures(self) -> bool:
        return bool(self.errors) or any(
            p.status == "error" for p in self.phases
        )

    def send(self, sender, env_data: dict, config_data: dict) -> bool:
        """Send the report as an HTML mail. Returns True on success.

        Prefers config_data['mail_provider']['username'] (the active mail
        account) over env_data['mail'] (which is the legacy Yahoo fallback
        in many setups - we don't want to spam that address).
        """
        from utils.mail_senders import OutgoingMail
        self.finalize()
        mail_cfg = config_data.get("mail_provider") or {}
        to_addr = (
            mail_cfg.get("username")
            or env_data.get("mail", "")
        )
        if not to_addr:
            return False
        study = config_data.get("study_name", "Termino")
        status_word = "ERRORS" if self.has_failures() else "OK"
        subject = (
            f"[{status_word}] {study} Daily Run "
            f"{self.started:%d.%m.%Y}"
        )
        try:
            sender.send(OutgoingMail(
                to=to_addr,
                subject=subject,
                body=self.to_html(study_name=study),
                body_is_html=True,
                from_address=to_addr,
            ))
            self._sent_to = to_addr  # remember for the caller's print
            return True
        except Exception as e:
            print(f"  ! report mail failed: {e}")
            return False

    @property
    def sent_to(self) -> str:
        """Returns the address the report was actually sent to."""
        return getattr(self, "_sent_to", "")
