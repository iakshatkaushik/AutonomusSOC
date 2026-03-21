"""PDF Incident Report Generator — dark cybersec-themed PDF matching the CyberSOC dashboard.

Generates a professional PDF with:
  1. Alert Details (threat type, severity, risk score)
  2. Executive Summary
  3. Detailed AI Reasoning
  4. Evidence Chain (numbered timeline)
  5. Recommended Actions
  6. Correlated Users

Uses reportlab with custom dark color palette to match the React dashboard UI.
"""
import io
import json
import textwrap
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Line
from reportlab.graphics import renderPDF
from reportlab.platypus.flowables import Flowable


# ─── Color Palette (matches dashboard dark theme) ────────────────────────

BG_DARK       = colors.HexColor("#0B0F19")
BG_CARD       = colors.HexColor("#111827")
BG_SURFACE    = colors.HexColor("#1A2235")
BG_INPUT      = colors.HexColor("#141C2E")
BORDER_SUBTLE = colors.HexColor("#1E293B")
BORDER_ACCENT = colors.HexColor("#2D3A52")

TEXT_PRIMARY   = colors.HexColor("#E2E8F0")
TEXT_SECONDARY = colors.HexColor("#94A3B8")
TEXT_MUTED     = colors.HexColor("#526077")

ACCENT_BLUE   = colors.HexColor("#6387F1")
ACCENT_CYAN   = colors.HexColor("#22D3EE")
ACCENT_PURPLE = colors.HexColor("#A78BFA")
ACCENT_GREEN  = colors.HexColor("#4ADE80")

CRITICAL_COLOR = colors.HexColor("#F87171")
HIGH_COLOR     = colors.HexColor("#FB923C")
MEDIUM_COLOR   = colors.HexColor("#FACC15")
LOW_COLOR      = colors.HexColor("#4ADE80")

SEVERITY_COLORS = {
    "CRITICAL": CRITICAL_COLOR,
    "HIGH": HIGH_COLOR,
    "MEDIUM": MEDIUM_COLOR,
    "LOW": LOW_COLOR,
}


# ─── Custom Flowables ────────────────────────────────────────────────────

class DarkBackground(Flowable):
    """Adds a dark background to the full page."""
    def __init__(self, width, height):
        Flowable.__init__(self)
        self.width = width
        self.height = height

    def draw(self):
        self.canv.setFillColor(BG_DARK)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)


class SectionCard(Flowable):
    """A dark card container with a colored section number and title."""
    def __init__(self, number, title, width):
        Flowable.__init__(self)
        self.number = number
        self.title = title
        self.card_width = width
        self.height = 36

    def draw(self):
        c = self.canv
        # Card background
        c.setFillColor(BG_CARD)
        c.roundRect(0, 0, self.card_width, self.height, 6, fill=1, stroke=0)
        # Section number with accent
        c.setFillColor(ACCENT_CYAN)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(16, 11, f"{self.number}.")
        # Title
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(38, 11, self.title.upper())


class EvidenceItem(Flowable):
    """A single evidence chain entry with number badge."""
    def __init__(self, number, text, width):
        Flowable.__init__(self)
        self.number = number
        self.text = text
        self.card_width = width
        # Calculate height based on text length
        lines = max(1, len(text) // 80 + 1)
        self.height = max(32, 16 + lines * 14)

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(BG_SURFACE)
        c.roundRect(0, 0, self.card_width, self.height, 5, fill=1, stroke=0)
        # Border
        c.setStrokeColor(BORDER_SUBTLE)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, self.card_width, self.height, 5, fill=0, stroke=1)
        # Number badge
        c.setFillColor(ACCENT_CYAN)
        c.setFont("Courier-Bold", 9)
        c.drawString(12, self.height - 18, f"#{self.number}")
        # Text — wrap long lines
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 8.5)
        wrapped = textwrap.wrap(self.text, width=90)
        y = self.height - 18
        for line in wrapped[:4]:
            c.drawString(42, y, line)
            y -= 13


# ─── Styles ───────────────────────────────────────────────────────────────

def _make_styles():
    """Create paragraph styles for the dark-themed PDF."""
    return {
        "header_title": ParagraphStyle(
            "HeaderTitle", fontName="Helvetica-Bold", fontSize=18,
            textColor=TEXT_PRIMARY, leading=22,
        ),
        "header_subtitle": ParagraphStyle(
            "HeaderSubtitle", fontName="Helvetica", fontSize=9,
            textColor=TEXT_MUTED, leading=12,
        ),
        "alert_label": ParagraphStyle(
            "AlertLabel", fontName="Helvetica-Bold", fontSize=8,
            textColor=TEXT_MUTED, leading=10, spaceAfter=2,
        ),
        "alert_value": ParagraphStyle(
            "AlertValue", fontName="Helvetica-Bold", fontSize=13,
            textColor=TEXT_PRIMARY, leading=16,
        ),
        "section_title": ParagraphStyle(
            "SectionTitle", fontName="Helvetica-Bold", fontSize=12,
            textColor=ACCENT_CYAN, leading=16, spaceBefore=16, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body", fontName="Helvetica", fontSize=9,
            textColor=TEXT_SECONDARY, leading=15, spaceAfter=4,
        ),
        "body_bright": ParagraphStyle(
            "BodyBright", fontName="Helvetica", fontSize=9,
            textColor=TEXT_PRIMARY, leading=15, spaceAfter=4,
        ),
        "confidence": ParagraphStyle(
            "Confidence", fontName="Helvetica", fontSize=8,
            textColor=TEXT_MUTED, leading=11,
        ),
        "action_primary": ParagraphStyle(
            "ActionPrimary", fontName="Helvetica-Bold", fontSize=10,
            textColor=CRITICAL_COLOR, leading=14, spaceBefore=4,
        ),
        "action_item": ParagraphStyle(
            "ActionItem", fontName="Helvetica", fontSize=8.5,
            textColor=TEXT_SECONDARY, leading=13, leftIndent=12,
        ),
        "corr_user": ParagraphStyle(
            "CorrUser", fontName="Courier-Bold", fontSize=9,
            textColor=ACCENT_PURPLE, leading=12,
        ),
    }


# ─── Page Template ────────────────────────────────────────────────────────

def _on_page(canvas, doc):
    """Custom page background — dark fill on every page."""
    w, h = A4
    canvas.setFillColor(BG_DARK)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)
    # Footer
    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(30, 15, f"CyberSOC-Agent · Confidential Incident Report · Page {doc.page}")
    canvas.drawRightString(w - 30, 15, "Generated by Autonomous AI SOC System")


# ─── Main Generator ──────────────────────────────────────────────────────

def generate_incident_pdf(
    alert_data: dict,
    report_data: dict = None,
) -> bytes:
    """Generate a dark-themed PDF incident report.

    Args:
        alert_data: Alert dict from the API with keys:
            id, user_id, alert_type, severity, risk_score,
            description, contributing_factors, recommended_actions,
            status, created_at
        report_data: Optional investigation report dict with keys:
            summary, threat_scenario, confidence, evidence_chain,
            reasoning, recommended_action, recommended_actions_detail,
            correlated_users, llm_model

    Returns:
        PDF file as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=28, rightMargin=28,
        topMargin=28, bottomMargin=36,
    )
    styles = _make_styles()
    w = A4[0] - 56  # available width
    story = []

    now = datetime.now().strftime("%m/%d/%Y, %I:%M %p")
    alert_id = alert_data.get("id", "?")
    user_id = alert_data.get("user_id", "Unknown")
    severity = alert_data.get("severity", "MEDIUM")
    risk_score = alert_data.get("risk_score", 0)
    alert_type = alert_data.get("alert_type", "ANOMALY").replace("_", " ")
    sev_color = SEVERITY_COLORS.get(severity, TEXT_SECONDARY)

    # ═══════════════════════════════════════════════════════════════════
    # HEADER
    # ═══════════════════════════════════════════════════════════════════
    header_data = [
        [
            Paragraph("CyberSOC Incident Report", styles["header_title"]),
            Paragraph(f'<font color="{ACCENT_CYAN.hexval()}">Alert #{alert_id}</font>', ParagraphStyle(
                "AlertId", fontName="Helvetica-Bold", fontSize=16, textColor=ACCENT_CYAN,
                alignment=TA_RIGHT, leading=20
            )),
        ],
        [
            Paragraph(f"Generated: {now}", styles["header_subtitle"]),
            Paragraph(f"User: {user_id}", ParagraphStyle(
                "UserId", fontName="Helvetica", fontSize=9, textColor=TEXT_MUTED,
                alignment=TA_RIGHT, leading=12,
            )),
        ],
    ]
    header_table = Table(header_data, colWidths=[w * 0.65, w * 0.35])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    # ═══════════════════════════════════════════════════════════════════
    # 1. ALERT DETAILS
    # ═══════════════════════════════════════════════════════════════════
    story.append(SectionCard("1", "ALERT DETAILS", w))
    story.append(Spacer(1, 10))

    details_data = [[
        [Paragraph("THREAT TYPE", styles["alert_label"]),
         Paragraph(alert_type, ParagraphStyle("ThreatType", fontName="Helvetica-Bold", fontSize=13,
                   textColor=TEXT_PRIMARY, leading=16))],
        [Paragraph("SEVERITY", styles["alert_label"]),
         Paragraph(severity, ParagraphStyle("SevValue", fontName="Helvetica-Bold", fontSize=13,
                   textColor=sev_color, leading=16))],
        [Paragraph("RISK SCORE", styles["alert_label"]),
         Paragraph(f"{risk_score:.1f} / 100", ParagraphStyle("ScoreValue", fontName="Helvetica-Bold",
                   fontSize=13, textColor=TEXT_PRIMARY, leading=16))],
    ]]
    details_table = Table(details_data, colWidths=[w * 0.4, w * 0.3, w * 0.3])
    details_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_CARD),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 18))

    if report_data:
        summary = report_data.get("summary", "No summary available.")
        reasoning = report_data.get("reasoning", "")
        confidence = report_data.get("confidence", 0)
        llm_model = report_data.get("llm_model", "unknown")
        threat = report_data.get("threat_scenario", "UNKNOWN")
        evidence = report_data.get("evidence_chain", [])
        if isinstance(evidence, str):
            try: evidence = json.loads(evidence)
            except: evidence = [evidence]
        rec_action = report_data.get("recommended_action", "MONITOR")
        rec_details = report_data.get("recommended_actions_detail", [])
        if isinstance(rec_details, str):
            try: rec_details = json.loads(rec_details)
            except: rec_details = [rec_details]
        corr_users = report_data.get("correlated_users", [])
        if isinstance(corr_users, str):
            try: corr_users = json.loads(corr_users)
            except: corr_users = []

        # ═══════════════════════════════════════════════════════════════
        # 2. EXECUTIVE SUMMARY
        # ═══════════════════════════════════════════════════════════════
        story.append(SectionCard("2", "EXECUTIVE SUMMARY", w))
        story.append(Spacer(1, 8))

        # Summary card
        summary_table = Table(
            [[Paragraph(summary, styles["body_bright"])]],
            colWidths=[w - 32],
        )
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BG_CARD),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
            ("TOPPADDING", (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 4))

        # Confidence badge
        conf_pct = f"{confidence * 100:.0f}%" if confidence else "N/A"
        story.append(Paragraph(
            f'<font color="{TEXT_MUTED.hexval()}">⚡ Confidence Level: </font>'
            f'<font color="{ACCENT_CYAN.hexval()}"><b>{conf_pct}</b></font>'
            f'<font color="{TEXT_MUTED.hexval()}"> (Model: {llm_model})</font>',
            styles["confidence"],
        ))
        story.append(Spacer(1, 18))

        # ═══════════════════════════════════════════════════════════════
        # 3. DETAILED AI REASONING
        # ═══════════════════════════════════════════════════════════════
        if reasoning:
            story.append(SectionCard("3", "DETAILED AI REASONING", w))
            story.append(Spacer(1, 8))

            # Wrap long reasoning text
            reasoning_paras = reasoning.split('\n')
            reasoning_content = []
            for para in reasoning_paras:
                if para.strip():
                    reasoning_content.append(
                        [Paragraph(para.strip(), styles["body"])]
                    )

            if reasoning_content:
                reasoning_table = Table(reasoning_content, colWidths=[w - 32])
                reasoning_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), BG_CARD),
                    ("ROUNDEDCORNERS", [6, 6, 6, 6]),
                    ("TOPPADDING", (0, 0), (0, 0), 14),
                    ("BOTTOMPADDING", (-1, -1), (-1, -1), 14),
                    ("TOPPADDING", (0, 1), (0, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (0, -2), 0),
                    ("LEFTPADDING", (0, 0), (-1, -1), 16),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ]))
                story.append(reasoning_table)
            story.append(Spacer(1, 18))

        # ═══════════════════════════════════════════════════════════════
        # 4. EVIDENCE CHAIN
        # ═══════════════════════════════════════════════════════════════
        if evidence:
            story.append(SectionCard("4", "EVIDENCE CHAIN", w))
            story.append(Spacer(1, 8))

            for i, item in enumerate(evidence[:10], 1):
                text = item if isinstance(item, str) else json.dumps(item)
                story.append(EvidenceItem(i, text, w))
                story.append(Spacer(1, 4))

            story.append(Spacer(1, 14))

        # ═══════════════════════════════════════════════════════════════
        # 5 & 6. RECOMMENDED ACTIONS + CORRELATED USERS (side by side)
        # ═══════════════════════════════════════════════════════════════
        left_content = []
        right_content = []

        # Left: Recommended Actions
        left_content.append(Paragraph(
            '<font color="#22D3EE"><b>5. RECOMMENDED ACTIONS</b></font>',
            ParagraphStyle("S5", fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT_CYAN, leading=14),
        ))
        left_content.append(Spacer(1, 8))
        left_content.append(Paragraph(
            f'Primary: <b><font color="{CRITICAL_COLOR.hexval()}">{rec_action.replace("_", " ")}</font></b>',
            styles["body_bright"],
        ))
        left_content.append(Spacer(1, 6))

        for action in rec_details[:8]:
            action_text = action if isinstance(action, str) else str(action)
            left_content.append(Paragraph(
                f'<font color="{ACCENT_BLUE.hexval()}">→</font> {action_text}',
                styles["action_item"],
            ))

        # Right: Correlated Users
        right_content.append(Paragraph(
            '<font color="#22D3EE"><b>6. CORRELATED USERS</b></font>',
            ParagraphStyle("S6", fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT_CYAN, leading=14),
        ))
        right_content.append(Spacer(1, 8))

        if corr_users:
            for u in corr_users[:6]:
                u_text = u if isinstance(u, str) else str(u)
                right_content.append(Paragraph(
                    f'<font color="{ACCENT_PURPLE.hexval()}">▪ {u_text}</font>',
                    styles["corr_user"],
                ))
        else:
            right_content.append(Paragraph(
                "No correlated users identified.",
                styles["body"],
            ))

        # Build side-by-side table
        bottom_data = [[left_content, right_content]]
        bottom_table = Table(bottom_data, colWidths=[w * 0.58, w * 0.42])
        bottom_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BG_CARD),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 16),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16),
            ("LINEAFTER", (0, 0), (0, -1), 0.5, BORDER_ACCENT),
        ]))
        story.append(bottom_table)

    else:
        # No investigation report available
        story.append(SectionCard("2", "INVESTIGATION STATUS", w))
        story.append(Spacer(1, 8))
        no_report_table = Table(
            [[Paragraph(
                "No AI investigation has been run for this alert yet. "
                "Click 'Investigate with AI' on the dashboard to generate a report.",
                styles["body"],
            )]],
            colWidths=[w - 32],
        )
        no_report_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BG_CARD),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
            ("TOPPADDING", (0, 0), (-1, -1), 20),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ]))
        story.append(no_report_table)

    # Build PDF
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
