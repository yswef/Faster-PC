"""
مولّد تقارير PDF احترافية باللغة العربية لكل أقسام التطبيق
باستخدام PySide6 (QPdfWriter + QTextDocument) بدون الحاجة لمكتبات خارجية.
"""

from __future__ import annotations

from datetime import datetime
import html
from typing import Iterable

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

from src.version import APP_NAME, APP_VERSION


def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def build_report_html(
    title: str,
    subtitle: str = "",
    summary_items: Iterable[tuple[str, str]] = (),
    headers: Iterable[str] = (),
    rows: Iterable[Iterable[object]] = (),
    notes: str = "",
) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cards_html = ""
    summary_list = list(summary_items)
    if summary_list:
        cells = "".join(
            f"""
            <td style="background:#f4f6f9; border:1px solid #dce1e7; border-radius:6px; padding:8px 12px; width:{100 // max(1, len(summary_list))}%;">
                <div style="font-size:10px; color:#5a6270;">{_esc(k)}</div>
                <div style="font-size:14px; font-weight:bold; color:#1f2937; margin-top:2px;">{_esc(v)}</div>
            </td>
            """
            for k, v in summary_list
        )
        cards_html = f'<table width="100%" cellspacing="6" cellpadding="0" style="margin-bottom:14px;"><tr>{cells}</tr></table>'

    headers_list = list(headers)
    rows_list = list(rows)
    table_html = ""
    if headers_list:
        th = "".join(
            f'<th style="background:#1e293b; color:#ffffff; padding:8px; text-align:right; font-size:11px; border:1px solid #334155;">{_esc(h)}</th>'
            for h in headers_list
        )
        body_rows = []
        for idx, row in enumerate(rows_list):
            bg = "#ffffff" if idx % 2 == 0 else "#f8fafc"
            tds = "".join(
                f'<td style="padding:6px 8px; border:1px solid #e2e8f0; font-size:10.5px; color:#1e293b;">{_esc(cell)}</td>'
                for cell in row
            )
            body_rows.append(f'<tr style="background:{bg};">{tds}</tr>')
        table_html = f"""
        <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse; margin-top:8px;">
            <thead><tr>{th}</tr></thead>
            <tbody>{''.join(body_rows)}</tbody>
        </table>
        """

    notes_html = (
        f'<div style="margin-top:14px; padding:10px; background:#fef9c3; border:1px solid #fde047; border-radius:6px; font-size:11px; color:#713f12;">{_esc(notes)}</div>'
        if notes
        else ""
    )

    return f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head><meta charset="utf-8"></head>
    <body style="font-family:'Segoe UI','Tahoma','Arial',sans-serif; color:#111827; direction:rtl;">
        <div style="border-bottom:3px solid #27ae60; padding-bottom:10px; margin-bottom:14px;">
            <table width="100%">
                <tr>
                    <td style="text-align:right;">
                        <div style="font-size:20px; font-weight:bold; color:#1e293b;">{APP_NAME} — {_esc(title)}</div>
                        <div style="font-size:11px; color:#64748b; margin-top:2px;">{_esc(subtitle)}</div>
                    </td>
                    <td style="text-align:left; font-size:10px; color:#64748b;">
                        <div>الإصدار: {APP_VERSION}</div>
                        <div>التاريخ: {now_str}</div>
                    </td>
                </tr>
            </table>
        </div>
        {cards_html}
        {table_html}
        {notes_html}
        <div style="margin-top:18px; border-top:1px solid #e2e8f0; padding-top:8px; font-size:9.5px; color:#94a3b8; text-align:center;">
            تم إنشاء هذا التقرير تلقائياً بواسطة {APP_NAME} v{APP_VERSION}
        </div>
    </body>
    </html>
    """


def export_pdf_report(
    file_path: str,
    title: str,
    subtitle: str = "",
    summary_items: Iterable[tuple[str, str]] = (),
    headers: Iterable[str] = (),
    rows: Iterable[Iterable[object]] = (),
    notes: str = "",
) -> str:
    html_content = build_report_html(
        title=title,
        subtitle=subtitle,
        summary_items=summary_items,
        headers=headers,
        rows=rows,
        notes=notes,
    )
    writer = QPdfWriter(file_path)
    layout = QPageLayout(
        QPageSize(QPageSize.A4),
        QPageLayout.Portrait,
        QMarginsF(12, 12, 12, 12),
        QPageLayout.Millimeter,
    )
    writer.setPageLayout(layout)
    writer.setTitle(f"{APP_NAME} - {title}")

    doc = QTextDocument()
    doc.setHtml(html_content)
    # ملاءمة عرض المستند مع عرض الصفحة القابل للطباعة
    page_rect = writer.pageLayout().paintRectPoints()
    doc.setPageSize(QSizeF(page_rect.width(), page_rect.height()))
    doc.print_(writer)
    return file_path


__all__ = ["build_report_html", "export_pdf_report"]
