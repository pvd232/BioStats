from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, KeepTogether, Flowable, NextPageTemplate,
    HRFlowable
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import simpleSplit
from xml.sax.saxutils import escape
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "prior/Human_DNA_Transcription_First_Principles_Primer.pdf"
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

PAGE_W, PAGE_H = letter
MARGIN_X = 0.67 * inch
MARGIN_TOP = 0.65 * inch
MARGIN_BOTTOM = 0.60 * inch

INK = HexColor("#17324D")
MUTED = HexColor("#53697A")
TEAL = HexColor("#007C83")
CYAN = HexColor("#DDF4F3")
BLUE = HexColor("#2B6CB0")
PALE_BLUE = HexColor("#EAF2FB")
GOLD = HexColor("#E5A93D")
PALE_GOLD = HexColor("#FFF3D7")
CORAL = HexColor("#D65A4A")
PALE_CORAL = HexColor("#FDE9E5")
GREEN = HexColor("#3F8554")
PALE_GREEN = HexColor("#E9F5EC")
PURPLE = HexColor("#6D5AA8")
PALE_PURPLE = HexColor("#EEEAF8")
LINE = HexColor("#CCD8E0")
LIGHT = HexColor("#F5F8FA")
WHITE = colors.white


FONT_DIR = "/System/Library/Fonts/Supplemental"
pdfmetrics.registerFont(TTFont("Primer", f"{FONT_DIR}/Arial.ttf"))
pdfmetrics.registerFont(TTFont("Primer-Bold", f"{FONT_DIR}/Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Primer-Italic", f"{FONT_DIR}/Arial Italic.ttf"))
pdfmetrics.registerFont(TTFont("Primer-BoldItalic", f"{FONT_DIR}/Arial Bold Italic.ttf"))
pdfmetrics.registerFontFamily(
    "Primer", normal="Primer", bold="Primer-Bold",
    italic="Primer-Italic", boldItalic="Primer-BoldItalic"
)


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="PrimerTitle", fontName="Primer-Bold", fontSize=27, leading=30,
    textColor=INK, spaceAfter=12
))
styles.add(ParagraphStyle(
    name="PrimerSubtitle", fontName="Primer", fontSize=12.5, leading=18,
    textColor=MUTED, spaceAfter=8
))
styles.add(ParagraphStyle(
    name="H1x", fontName="Primer-Bold", fontSize=20, leading=24,
    textColor=INK, spaceBefore=2, spaceAfter=11, keepWithNext=True
))
styles.add(ParagraphStyle(
    name="H2x", fontName="Primer-Bold", fontSize=13.5, leading=17,
    textColor=TEAL, spaceBefore=12, spaceAfter=6, keepWithNext=True
))
styles.add(ParagraphStyle(
    name="H3x", fontName="Primer-Bold", fontSize=10.8, leading=14,
    textColor=INK, spaceBefore=8, spaceAfter=3, keepWithNext=True
))
styles.add(ParagraphStyle(
    name="Bodyx", fontName="Primer", fontSize=9.25, leading=13.4,
    textColor=INK, spaceAfter=6
))
styles.add(ParagraphStyle(
    name="BodySmall", fontName="Primer", fontSize=8.1, leading=11.3,
    textColor=INK, spaceAfter=4
))
styles.add(ParagraphStyle(
    name="Captionx", fontName="Primer-Italic", fontSize=7.5, leading=10,
    textColor=MUTED, alignment=TA_CENTER, spaceBefore=3, spaceAfter=8
))
styles.add(ParagraphStyle(
    name="Callout", fontName="Primer", fontSize=9, leading=13,
    textColor=INK, leftIndent=8, rightIndent=8, spaceAfter=0
))
styles.add(ParagraphStyle(
    name="CalloutTitle", fontName="Primer-Bold", fontSize=9, leading=12,
    textColor=TEAL, spaceAfter=3
))
styles.add(ParagraphStyle(
    name="TableHead", fontName="Primer-Bold", fontSize=7.6, leading=9.4,
    textColor=WHITE
))
styles.add(ParagraphStyle(
    name="TableBody", fontName="Primer", fontSize=7.4, leading=9.6,
    textColor=INK
))
styles.add(ParagraphStyle(
    name="Mono", fontName="Courier", fontSize=8.1, leading=11,
    textColor=INK
))
styles.add(ParagraphStyle(
    name="TOCHeading", fontName="Primer-Bold", fontSize=10, leading=14,
    textColor=INK
))
styles.add(ParagraphStyle(
    name="Question", fontName="Primer-Bold", fontSize=9.3, leading=13,
    textColor=INK, leftIndent=14, firstLineIndent=-14, spaceAfter=5
))


def P(text, style="Bodyx"):
    return Paragraph(text, styles[style])


def callout(title, body, fill=CYAN, stripe=TEAL):
    inner = [
        [Paragraph(title, styles["CalloutTitle"])],
        [Paragraph(body, styles["Callout"])]
    ]
    t = Table(inner, colWidths=[6.45 * inch], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.5, stripe),
        ("LINEBEFORE", (0, 0), (0, -1), 4, stripe),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
    ]))
    return KeepTogether([t])


def table(rows, widths, header=True):
    data = []
    for r_i, row in enumerate(rows):
        data.append([
            Paragraph(str(cell), styles["TableHead" if header and r_i == 0 else "TableBody"])
            for cell in row
        ])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    cmd = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        cmd += [("BACKGROUND", (0, 0), (-1, 0), INK)]
        if len(rows) > 1:
            cmd += [("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT])]
    t.setStyle(TableStyle(cmd))
    return t


class PrimerDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        frame = Frame(
            MARGIN_X, MARGIN_BOTTOM,
            PAGE_W - 2 * MARGIN_X, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0
        )
        self.addPageTemplates([
            PageTemplate(id="Cover", frames=[frame], onPage=draw_cover_background),
            PageTemplate(id="Body", frames=[frame], onPage=draw_header_footer),
        ])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style = flowable.style.name
            if style == "H1x":
                text = flowable.getPlainText()
                key = "h1-%s" % self.seq.nextf("h1")
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=0, closed=False)
                self.notify("TOCEntry", (0, text, self.page, key))
            elif style == "H2x":
                text = flowable.getPlainText()
                key = "h2-%s" % self.seq.nextf("h2")
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=1, closed=False)
                self.notify("TOCEntry", (1, text, self.page, key))


def draw_cover_background(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(TEAL)
    canvas.circle(PAGE_W - 0.6 * inch, PAGE_H - 0.7 * inch, 1.8 * inch, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.circle(PAGE_W - 0.15 * inch, PAGE_H - 0.25 * inch, 0.85 * inch, fill=1, stroke=0)
    canvas.setFillColor(GOLD)
    canvas.rect(0, 0, PAGE_W, 0.16 * inch, fill=1, stroke=0)
    canvas.restoreState()


def draw_header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_X, PAGE_H - 0.42 * inch, PAGE_W - MARGIN_X, PAGE_H - 0.42 * inch)
    canvas.setFont("Primer-Bold", 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN_X, PAGE_H - 0.30 * inch, "HUMAN DNA TRANSCRIPTION - FIRST PRINCIPLES")
    canvas.setFont("Primer", 7.2)
    canvas.drawRightString(PAGE_W - MARGIN_X, 0.34 * inch, str(doc.page))
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN_X, 0.49 * inch, PAGE_W - MARGIN_X, 0.49 * inch)
    canvas.restoreState()


def fit_text(c, text, x, y, max_width, font="Primer", size=8, color=INK, align="left"):
    while size > 5.6 and stringWidth(text, font, size) > max_width:
        size -= 0.2
    c.setFont(font, size)
    c.setFillColor(color)
    if align == "center":
        c.drawCentredString(x, y, text)
    elif align == "right":
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)


class ChemistryFlowable(Flowable):
    def __init__(self, width=6.45 * inch, height=2.08 * inch):
        super().__init__()
        self.width, self.height = width, height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(LIGHT)
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        centers = [(0.9, "Phosphate", "negative charge", PALE_GOLD, GOLD),
                   (2.55, "Sugar", "directional scaffold", PALE_BLUE, BLUE),
                   (4.2, "Base", "sequence letter", PALE_GREEN, GREEN),
                   (5.65, "Nucleotide", "one monomer", PALE_PURPLE, PURPLE)]
        for i, (xin, title, sub, fill, stroke) in enumerate(centers):
            x = xin * inch
            c.setFillColor(fill)
            c.setStrokeColor(stroke)
            if title == "Phosphate":
                c.circle(x, 1.12 * inch, 0.28 * inch, fill=1, stroke=1)
                fit_text(c, "PO₄", x, 1.07 * inch, 0.45 * inch, "Primer-Bold", 9, stroke, "center")
            elif title == "Sugar":
                pts = [
                    (x - .28*inch, .96*inch), (x - .10*inch, 1.34*inch),
                    (x + .31*inch, 1.27*inch), (x + .34*inch, .88*inch),
                    (x - .06*inch, .74*inch)
                ]
                path = c.beginPath()
                path.moveTo(*pts[0])
                for p in pts[1:]:
                    path.lineTo(*p)
                path.close()
                c.drawPath(path, fill=1, stroke=1)
                fit_text(c, "ribose", x, 1.02*inch, .55*inch, "Primer-Bold", 8, stroke, "center")
            elif title == "Base":
                c.roundRect(x - .34*inch, .84*inch, .68*inch, .52*inch, 5, fill=1, stroke=1)
                fit_text(c, "A / C / G / T(U)", x, 1.04*inch, .62*inch, "Primer-Bold", 7, stroke, "center")
            else:
                c.roundRect(x - .55*inch, .73*inch, 1.1*inch, .78*inch, 8, fill=1, stroke=1)
                fit_text(c, "phosphate +", x, 1.20*inch, .95*inch, "Primer", 7, stroke, "center")
                fit_text(c, "sugar + base", x, .98*inch, .95*inch, "Primer-Bold", 8, stroke, "center")
        # connectors
        c.setStrokeColor(MUTED)
        c.setLineWidth(1.2)
        for xa, xb in [(1.28, 2.15), (2.94, 3.82), (4.58, 5.05)]:
            c.line(xa*inch, 1.1*inch, xb*inch, 1.1*inch)
            c.line((xb-.08)*inch, 1.15*inch, xb*inch, 1.1*inch)
            c.line((xb-.08)*inch, 1.05*inch, xb*inch, 1.1*inch)
        for xin, title, sub, fill, stroke in centers:
            x = xin * inch
            fit_text(c, title, x, .43*inch, 1.25*inch, "Primer-Bold", 8.6, INK, "center")
            fit_text(c, sub, x, .20*inch, 1.32*inch, "Primer", 7, MUTED, "center")


class DuplexFlowable(Flowable):
    def __init__(self, width=6.45 * inch, height=2.25 * inch):
        super().__init__()
        self.width, self.height = width, height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(LIGHT)
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        left, right = .63*inch, w-.63*inch
        y1, y2 = 1.52*inch, .72*inch
        c.setStrokeColor(BLUE)
        c.setLineWidth(5)
        c.line(left, y1, right, y1)
        c.setStrokeColor(CORAL)
        c.line(left, y2, right, y2)
        seq1 = ["A", "C", "G", "T", "A", "A", "G", "C"]
        seq2 = ["T", "G", "C", "A", "T", "T", "C", "G"]
        xs = [left + i*(right-left)/7 for i in range(8)]
        for x, a, b in zip(xs, seq1, seq2):
            c.setStrokeColor(LINE)
            c.setLineWidth(1)
            c.line(x, y2+4, x, y1-4)
            fit_text(c, a, x, y1-.04*inch, .35*inch, "Primer-Bold", 9, WHITE, "center")
            fit_text(c, b, x, y2-.04*inch, .35*inch, "Primer-Bold", 9, WHITE, "center")
        fit_text(c, "5′", left-.38*inch, y1-.04*inch, .3*inch, "Primer-Bold", 10, BLUE)
        fit_text(c, "3′", right+.10*inch, y1-.04*inch, .3*inch, "Primer-Bold", 10, BLUE)
        fit_text(c, "3′", left-.38*inch, y2-.04*inch, .3*inch, "Primer-Bold", 10, CORAL)
        fit_text(c, "5′", right+.10*inch, y2-.04*inch, .3*inch, "Primer-Bold", 10, CORAL)
        fit_text(c, "coding-like direction: 5′ → 3′", w/2, 1.93*inch, 3*inch, "Primer-Bold", 8, BLUE, "center")
        fit_text(c, "opposite strand: 3′ → 5′ across the same physical direction", w/2, .25*inch, 4.6*inch, "Primer-Bold", 8, CORAL, "center")


class GeneMapFlowable(Flowable):
    def __init__(self, width=6.45 * inch, height=3.38 * inch):
        super().__init__()
        self.width, self.height = width, height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(LIGHT)
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        x0, x1 = .35*inch, w-.32*inch
        top_y = 2.58*inch
        bot_y = 2.04*inch
        # background zones
        c.setFillColor(PALE_GOLD)
        c.roundRect(.40*inch, 1.70*inch, 2.05*inch, 1.18*inch, 5, fill=1, stroke=0)
        c.setFillColor(PALE_GREEN)
        c.roundRect(2.48*inch, 1.70*inch, 3.55*inch, 1.18*inch, 5, fill=1, stroke=0)
        fit_text(c, "PROMOTER - recruits and orients machinery", 1.42*inch, 2.72*inch, 1.8*inch, "Primer-Bold", 7.2, GOLD, "center")
        fit_text(c, "TRANSCRIBED REGION", 4.22*inch, 2.72*inch, 2.8*inch, "Primer-Bold", 7.2, GREEN, "center")
        # strands
        c.setStrokeColor(BLUE); c.setLineWidth(3)
        c.line(x0, top_y, x1, top_y)
        c.setStrokeColor(CORAL)
        c.line(x0, bot_y, x1, bot_y)
        fit_text(c, "5′", .12*inch, top_y-.04*inch, .24*inch, "Primer-Bold", 9, BLUE)
        fit_text(c, "3′", w-.24*inch, top_y-.04*inch, .24*inch, "Primer-Bold", 9, BLUE)
        fit_text(c, "3′", .12*inch, bot_y-.04*inch, .24*inch, "Primer-Bold", 9, CORAL)
        fit_text(c, "5′", w-.24*inch, bot_y-.04*inch, .24*inch, "Primer-Bold", 9, CORAL)
        # labels along sequence
        positions = [
            (.70, "BRE", PURPLE), (1.35, "TATAAA", GOLD),
            (2.58, "+1", TEAL), (3.18, "5′ UTR", BLUE),
            (4.06, "ATG", GREEN), (5.28, "TAA", CORAL)
        ]
        for xin, lab, col in positions:
            x = xin*inch
            c.setStrokeColor(col); c.setLineWidth(1)
            c.line(x, bot_y-.10*inch, x, top_y+.10*inch)
            fit_text(c, lab, x, 1.78*inch, .75*inch, "Primer-Bold", 7.8, col, "center")
        # Pol II and arrow
        c.setFillColor(TEAL); c.setStrokeColor(TEAL)
        c.roundRect(2.42*inch, 2.31*inch, .55*inch, .48*inch, 7, fill=1, stroke=0)
        fit_text(c, "Pol II", 2.695*inch, 2.49*inch, .48*inch, "Primer-Bold", 7.2, WHITE, "center")
        c.setLineWidth(2.2); c.line(2.92*inch, 3.05*inch, 5.95*inch, 3.05*inch)
        c.line(5.82*inch, 3.13*inch, 5.95*inch, 3.05*inch)
        c.line(5.82*inch, 2.97*inch, 5.95*inch, 3.05*inch)
        fit_text(c, "transcription →", 4.45*inch, 3.10*inch, 1.8*inch, "Primer-Bold", 8, TEAL, "center")
        # RNA
        c.setStrokeColor(PURPLE); c.setLineWidth(3)
        c.line(2.58*inch, 1.31*inch, 5.85*inch, 1.31*inch)
        fit_text(c, "5′", 2.35*inch, 1.27*inch, .25*inch, "Primer-Bold", 9, PURPLE)
        fit_text(c, "pre-mRNA grows 5′ → 3′", 4.25*inch, 1.05*inch, 2.7*inch, "Primer-Bold", 8, PURPLE, "center")
        # definition strip
        fit_text(c, "top = coding DNA (matches RNA except T/U)", .45*inch, .55*inch, 2.9*inch, "Primer-Bold", 7.7, BLUE)
        fit_text(c, "bottom = template DNA (read 3′ → 5′)", 3.65*inch, .55*inch, 2.5*inch, "Primer-Bold", 7.7, CORAL)
        fit_text(c, "TATA recruits machinery. RNA begins at +1. Translation begins later at ATG/AUG.", w/2, .23*inch, 5.8*inch, "Primer-Italic", 7.5, MUTED, "center")


class StagesFlowable(Flowable):
    def __init__(self, width=6.45*inch, height=2.35*inch):
        super().__init__()
        self.width, self.height = width, height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        stages = [
            ("1", "INITIATION", "Promoter recognition\nDNA opening\nFirst RNA bonds", TEAL, CYAN),
            ("2", "ELONGATION", "Pol II reads 3′ → 5′\nRNA grows 5′ → 3′\nProcessing begins", BLUE, PALE_BLUE),
            ("3", "TERMINATION", "RNA is cleaved\nPoly(A) machinery acts\nPol II disengages", CORAL, PALE_CORAL),
        ]
        gap = .15*inch
        bw = (w-2*gap)/3
        for i, (n, title, body, col, fill) in enumerate(stages):
            x = i*(bw+gap)
            c.setFillColor(fill); c.setStrokeColor(col); c.setLineWidth(1)
            c.roundRect(x, .15*inch, bw, 1.95*inch, 8, fill=1, stroke=1)
            c.setFillColor(col)
            c.circle(x+.28*inch, 1.79*inch, .16*inch, fill=1, stroke=0)
            fit_text(c, n, x+.28*inch, 1.73*inch, .2*inch, "Primer-Bold", 8, WHITE, "center")
            fit_text(c, title, x+.55*inch, 1.73*inch, bw-.65*inch, "Primer-Bold", 9, col)
            yy = 1.30*inch
            for line in body.split("\n"):
                fit_text(c, "• " + line, x+.18*inch, yy, bw-.35*inch, "Primer", 7.7, INK)
                yy -= .31*inch
            if i < 2:
                c.setStrokeColor(MUTED); c.setLineWidth(1.5)
                ax = x+bw+.02*inch
                c.line(ax, 1.14*inch, ax+gap-.04*inch, 1.14*inch)
                c.line(ax+gap-.10*inch, 1.20*inch, ax+gap-.04*inch, 1.14*inch)
                c.line(ax+gap-.10*inch, 1.08*inch, ax+gap-.04*inch, 1.14*inch)


class ProcessingFlowable(Flowable):
    def __init__(self, width=6.45*inch, height=3.08*inch):
        super().__init__()
        self.width, self.height = width, height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(LIGHT); c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        # pre-mRNA
        fit_text(c, "PRE-mRNA (nucleus)", .25*inch, 2.74*inch, 1.5*inch, "Primer-Bold", 8, MUTED)
        x = 1.55*inch; y = 2.72*inch
        parts = [
            (.70, "EXON 1", GREEN), (.65, "INTRON", GOLD),
            (.70, "EXON 2", GREEN), (.70, "INTRON", GOLD),
            (.70, "EXON 3", GREEN)
        ]
        for width_in, lab, col in parts:
            c.setFillColor(col); c.setStrokeColor(col)
            c.roundRect(x, y-.16*inch, width_in*inch, .34*inch, 3, fill=1, stroke=0)
            fit_text(c, lab, x+width_in*inch/2, y-.04*inch, width_in*inch-.06*inch, "Primer-Bold", 6.8, WHITE, "center")
            x += width_in*inch+.05*inch
        # process labels
        steps = [("5′ CAP", .65, TEAL), ("SPLICING", 2.80, GOLD), ("CLEAVAGE + POLY(A)", 4.65, PURPLE)]
        for lab, xin, col in steps:
            fit_text(c, lab, xin*inch, 2.16*inch, 1.25*inch, "Primer-Bold", 7.4, col, "center")
            c.setStrokeColor(col); c.setLineWidth(1.3)
            c.line(xin*inch, 2.02*inch, xin*inch, 1.69*inch)
            c.line((xin-.06)*inch, 1.77*inch, xin*inch, 1.69*inch)
            c.line((xin+.06)*inch, 1.77*inch, xin*inch, 1.69*inch)
        # mature
        fit_text(c, "MATURE mRNA", .25*inch, 1.31*inch, 1.5*inch, "Primer-Bold", 8, MUTED)
        fit_text(c, "m⁷G", 1.42*inch, 1.26*inch, .35*inch, "Primer-Bold", 8, TEAL)
        x = 1.80*inch; y = 1.31*inch
        for width_in, lab in [(.85, "EXON 1"), (.85, "EXON 2"), (.85, "EXON 3")]:
            c.setFillColor(GREEN)
            c.roundRect(x, y-.16*inch, width_in*inch, .34*inch, 3, fill=1, stroke=0)
            fit_text(c, lab, x+width_in*inch/2, y-.04*inch, width_in*inch-.06*inch, "Primer-Bold", 6.8, WHITE, "center")
            x += width_in*inch
        c.setStrokeColor(PURPLE); c.setLineWidth(3)
        c.line(x, y, x+.65*inch, y)
        fit_text(c, "AAAA…", x+.33*inch, y+.10*inch, .65*inch, "Primer-Bold", 7.5, PURPLE, "center")
        fit_text(c, "5′", 1.55*inch, .83*inch, .3*inch, "Primer-Bold", 8, TEAL)
        fit_text(c, "3′", x+.70*inch, .83*inch, .3*inch, "Primer-Bold", 8, PURPLE)
        fit_text(c, "introns removed; selected exons ligated", w/2, .45*inch, 4.5*inch, "Primer-Italic", 8, MUTED, "center")
        fit_text(c, "Exons are retained in mature RNA and may contain UTR or protein-coding sequence.", w/2, .18*inch, 5.8*inch, "Primer-Bold", 7.4, INK, "center")


class TranslationFlowable(Flowable):
    def __init__(self, width=6.45*inch, height=2.75*inch):
        super().__init__()
        self.width, self.height = width, height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(LIGHT); c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        y = 1.70*inch
        # mRNA
        c.setStrokeColor(PURPLE); c.setLineWidth(3)
        c.line(.62*inch, y, 5.85*inch, y)
        fit_text(c, "5′ cap", .18*inch, y-.04*inch, .55*inch, "Primer-Bold", 7.5, TEAL)
        fit_text(c, "3′", 5.94*inch, y-.04*inch, .3*inch, "Primer-Bold", 8, PURPLE)
        codons = [("AUG", GREEN), ("GCU", BLUE), ("AAA", BLUE), ("UGA", CORAL)]
        x = 1.63*inch
        for lab, col in codons:
            c.setFillColor(col); c.roundRect(x, y-.18*inch, .60*inch, .38*inch, 3, fill=1, stroke=0)
            fit_text(c, lab, x+.30*inch, y-.04*inch, .54*inch, "Primer-Bold", 8.5, WHITE, "center")
            x += .70*inch
        # ribosome
        c.setFillColor(PALE_GOLD); c.setStrokeColor(GOLD); c.setLineWidth(1.2)
        c.ellipse(2.15*inch, 1.20*inch, 3.65*inch, 2.27*inch, fill=1, stroke=1)
        c.setFillColor(GOLD)
        c.ellipse(2.38*inch, 1.46*inch, 3.42*inch, 2.08*inch, fill=1, stroke=0)
        fit_text(c, "80S ribosome", 2.90*inch, 1.95*inch, 1.3*inch, "Primer-Bold", 7.6, INK, "center")
        # peptide
        aas = [("Met", GREEN), ("Ala", BLUE), ("Lys", BLUE)]
        x = 2.48*inch
        for i, (aa, col) in enumerate(aas):
            c.setFillColor(col); c.circle(x, 2.42*inch, .18*inch, fill=1, stroke=0)
            fit_text(c, aa, x, 2.38*inch, .32*inch, "Primer-Bold", 6.6, WHITE, "center")
            if i < len(aas)-1:
                c.setStrokeColor(MUTED); c.setLineWidth(1.2)
                c.line(x+.18*inch, 2.42*inch, x+.52*inch, 2.42*inch)
            x += .70*inch
        # labels
        fit_text(c, "5′ UTR", 1.10*inch, 1.18*inch, .8*inch, "Primer-Bold", 7.5, MUTED, "center")
        fit_text(c, "start", 1.93*inch, 1.18*inch, .6*inch, "Primer-Bold", 7.3, GREEN, "center")
        fit_text(c, "codons read 5′ → 3′", 3.10*inch, .78*inch, 2.2*inch, "Primer-Bold", 8, BLUE, "center")
        fit_text(c, "stop", 4.31*inch, 1.18*inch, .6*inch, "Primer-Bold", 7.3, CORAL, "center")
        fit_text(c, "3′ UTR + poly(A) tail", 5.20*inch, 1.18*inch, 1.3*inch, "Primer-Bold", 7.2, MUTED, "center")
        fit_text(c, "The ribosome translates RNA; it never reads the promoter, introns already removed, or genomic DNA directly.", w/2, .27*inch, 5.8*inch, "Primer-Italic", 7.7, MUTED, "center")


class CoordinateFlowable(Flowable):
    def __init__(self, width=6.45*inch, height=2.35*inch):
        super().__init__()
        self.width, self.height = width, height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(LIGHT); c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        mid = 3.22*inch
        c.setStrokeColor(LINE); c.line(mid, .25*inch, mid, 2.05*inch)
        # forward
        fit_text(c, "FORWARD-STRAND GENE", 1.60*inch, 1.93*inch, 2.7*inch, "Primer-Bold", 8, BLUE, "center")
        c.setStrokeColor(BLUE); c.setLineWidth(3)
        c.line(.42*inch, 1.35*inch, 2.82*inch, 1.35*inch)
        fit_text(c, "5′", .16*inch, 1.31*inch, .3*inch, "Primer-Bold", 8, BLUE)
        fit_text(c, "3′", 2.87*inch, 1.31*inch, .3*inch, "Primer-Bold", 8, BLUE)
        fit_text(c, "lower coordinate", .42*inch, .95*inch, 1.2*inch, "Primer", 7, MUTED)
        fit_text(c, "higher coordinate", 2.82*inch, .95*inch, 1.2*inch, "Primer", 7, MUTED, "right")
        fit_text(c, "transcript 5′ → 3′", 1.62*inch, .53*inch, 2.2*inch, "Primer-Bold", 8, TEAL, "center")
        # reverse
        fit_text(c, "REVERSE-STRAND GENE", 4.84*inch, 1.93*inch, 2.7*inch, "Primer-Bold", 8, CORAL, "center")
        c.setStrokeColor(CORAL); c.setLineWidth(3)
        c.line(3.62*inch, 1.35*inch, 6.03*inch, 1.35*inch)
        fit_text(c, "3′", 3.34*inch, 1.31*inch, .3*inch, "Primer-Bold", 8, CORAL)
        fit_text(c, "5′", 6.08*inch, 1.31*inch, .3*inch, "Primer-Bold", 8, CORAL)
        fit_text(c, "lower coordinate", 3.62*inch, .95*inch, 1.2*inch, "Primer", 7, MUTED)
        fit_text(c, "higher coordinate", 6.03*inch, .95*inch, 1.2*inch, "Primer", 7, MUTED, "right")
        fit_text(c, "transcript 5′ ← 3′", 4.84*inch, .53*inch, 2.2*inch, "Primer-Bold", 8, TEAL, "center")


class OrientationChoiceFlowable(Flowable):
    def __init__(self, width=6.45*inch, height=3.25*inch):
        super().__init__()
        self.width, self.height = width, height

    def draw_panel(self, c, x, title, points_right=True):
        pw = 3.05*inch
        c.setFillColor(LIGHT); c.setStrokeColor(LINE)
        c.roundRect(x, .12*inch, pw, 2.85*inch, 7, fill=1, stroke=1)
        fit_text(c, title, x+pw/2, 2.68*inch, pw-.25*inch, "Primer-Bold", 8.5,
                 BLUE if points_right else CORAL, "center")
        left, right = x+.32*inch, x+pw-.32*inch
        y_top, y_bottom = 1.82*inch, 1.29*inch
        # promoter and gene regions
        c.setFillColor(PALE_GOLD)
        px = left if points_right else right-.72*inch
        c.roundRect(px, 1.03*inch, .72*inch, 1.08*inch, 4, fill=1, stroke=0)
        fit_text(c, "PROMOTER", px+.36*inch, 1.98*inch, .64*inch, "Primer-Bold", 6.5, GOLD, "center")
        c.setFillColor(PALE_GREEN)
        gx = left+.84*inch if points_right else left
        gw = 1.56*inch
        c.roundRect(gx, 1.03*inch, gw, 1.08*inch, 4, fill=1, stroke=0)
        fit_text(c, "GENE", gx+gw/2, 1.98*inch, gw-.1*inch, "Primer-Bold", 6.8, GREEN, "center")
        # strands
        c.setStrokeColor(BLUE); c.setLineWidth(3)
        c.line(left, y_top, right, y_top)
        c.setStrokeColor(CORAL)
        c.line(left, y_bottom, right, y_bottom)
        if points_right:
            ends = [("5′", left-.20*inch, y_top, BLUE), ("3′", right+.06*inch, y_top, BLUE),
                    ("3′", left-.20*inch, y_bottom, CORAL), ("5′", right+.06*inch, y_bottom, CORAL)]
            template_y = y_bottom
            coding_y = y_top
            arrow_x1, arrow_x2 = left+.62*inch, right-.08*inch
        else:
            ends = [("5′", left-.20*inch, y_top, BLUE), ("3′", right+.06*inch, y_top, BLUE),
                    ("3′", left-.20*inch, y_bottom, CORAL), ("5′", right+.06*inch, y_bottom, CORAL)]
            template_y = y_top
            coding_y = y_bottom
            arrow_x1, arrow_x2 = right-.62*inch, left+.08*inch
        for lab, ex, ey, col in ends:
            fit_text(c, lab, ex, ey-.04*inch, .23*inch, "Primer-Bold", 7.7, col)
        c.setStrokeColor(TEAL); c.setLineWidth(2)
        c.line(arrow_x1, 2.34*inch, arrow_x2, 2.34*inch)
        if points_right:
            c.line(arrow_x2-.10*inch, 2.41*inch, arrow_x2, 2.34*inch)
            c.line(arrow_x2-.10*inch, 2.27*inch, arrow_x2, 2.34*inch)
        else:
            c.line(arrow_x2+.10*inch, 2.41*inch, arrow_x2, 2.34*inch)
            c.line(arrow_x2+.10*inch, 2.27*inch, arrow_x2, 2.34*inch)
        fit_text(c, "transcription", x+pw/2, 2.39*inch, 1.1*inch, "Primer-Bold", 7, TEAL, "center")
        fit_text(c, "TEMPLATE", x+pw/2, template_y-.30*inch, 1.1*inch, "Primer-Bold", 7.3, CORAL if points_right else BLUE, "center")
        fit_text(c, "coding", x+pw/2, coding_y+.12*inch, .75*inch, "Primer-Italic", 6.8, BLUE if points_right else CORAL, "center")
        direction = "bottom runs 3′ → 5′ downstream" if points_right else "top runs 3′ → 5′ downstream"
        fit_text(c, direction, x+pw/2, .40*inch, pw-.25*inch, "Primer-Bold", 7, INK, "center")

    def draw(self):
        c = self.canv
        self.draw_panel(c, 0, "PROMOTER FACES RIGHT", True)
        self.draw_panel(c, 3.40*inch, "PROMOTER FACES LEFT", False)


def section(title):
    return [PageBreak(), P(title, "H1x")]


story = []

# Cover
story += [
    NextPageTemplate("Cover"),
    Spacer(1, 1.05*inch),
    Paragraph("HUMAN DNA<br/>TRANSCRIPTION", ParagraphStyle(
        "CoverTitle", parent=styles["PrimerTitle"], fontSize=31, leading=34, textColor=WHITE
    )),
    Paragraph("An organic chemistry and biochemistry primer from first principles",
              ParagraphStyle("CoverSub", parent=styles["PrimerSubtitle"], fontSize=15, leading=21, textColor=CYAN)),
    Spacer(1, .36*inch),
    Table([[
        Paragraph(
            "<b>Purpose</b><br/>Supplementary material for Section 2, “Biological Foundations,” "
            "of <i>Gene, Transcript, Protein, and Perturbation Identifier Systems</i>.",
            ParagraphStyle("CoverBox", fontName="Primer", fontSize=10.5, leading=15, textColor=INK)
        )
    ]], colWidths=[5.5*inch], style=TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), WHITE),
        ("BOX", (0,0), (-1,-1), .8, CYAN),
        ("LEFTPADDING", (0,0), (-1,-1), 14),
        ("RIGHTPADDING", (0,0), (-1,-1), 14),
        ("TOPPADDING", (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
    ])),
    Spacer(1, .42*inch),
    Paragraph(
        "Chemistry → DNA and chromatin → gene regulation → RNA polymerase II → "
        "RNA processing → translation → biological identifiers",
        ParagraphStyle("CoverRoad", fontName="Primer-Bold", fontSize=11, leading=16, textColor=PALE_GOLD)
    ),
    Spacer(1, 2.55*inch),
    Paragraph("Human / eukaryotic emphasis · illustrated study edition",
              ParagraphStyle("CoverFoot", fontName="Primer", fontSize=9, leading=12, textColor=CYAN)),
    NextPageTemplate("Body"),
    PageBreak(),
]

# Contents
story += [
    P("How to use this primer", "H1x"),
    P(
        "This supplement starts below the level of “DNA is information.” It builds the necessary chemistry, "
        "then develops human gene architecture, transcriptional regulation, RNA polymerase II catalysis, RNA processing, "
        "and translation as one connected molecular system."
    ),
    callout(
        "The biological arc",
        "<b>Regulatory DNA and chromatin govern recruitment of RNA polymerase II. Pol II produces a pre-mRNA; "
        "capping, splicing, and 3′-end processing create a mature mRNA; a ribosome then translates its selected "
        "coding sequence into a polypeptide.</b>",
        PALE_GOLD, GOLD
    ),
    Spacer(1, 10),
    P("Contents", "H2x"),
]
toc = TableOfContents()
toc.levelStyles = [
    ParagraphStyle("TOC1", fontName="Primer-Bold", fontSize=9, leading=13,
                   leftIndent=0, firstLineIndent=0, textColor=INK, spaceBefore=3),
    ParagraphStyle("TOC2", fontName="Primer", fontSize=8, leading=11,
                   leftIndent=15, firstLineIndent=0, textColor=MUTED),
]
story += [toc, Spacer(1, 10)]
story += [
    callout(
        "Scope boundary",
        "The examples describe a typical <b>human protein-coding gene transcribed by RNA polymerase II</b>. "
        "Human biology contains important exceptions: many promoters lack TATA boxes, genes can use multiple "
        "start sites, some introns are retained, and many transcripts do not encode proteins.",
        PALE_BLUE, BLUE
    )
]

# 1 chemistry
story += section("1. The minimum organic chemistry")
story += [
    P("1.1 Carbon scaffolds and functional groups", "H2x"),
    P(
        "Organic molecules are built largely from carbon because carbon can form four stable covalent bonds. "
        "DNA and RNA use a five-carbon sugar as a scaffold. The prime marks in 1′, 2′, 3′, 4′, and 5′ distinguish "
        "sugar-carbon positions from positions in the nitrogenous base."
    ),
    ChemistryFlowable(),
    P("A nucleotide is a three-part monomer: a nitrogenous base, a pentose sugar, and one or more phosphate groups.", "Captionx"),
    P("1.2 The few chemical interactions that do most of the work", "H2x"),
    table([
        ["Interaction", "What it is", "Role here"],
        ["Covalent bond", "Electron-sharing bond; relatively strong", "Builds each sugar-phosphate backbone and holds each base to its sugar"],
        ["Hydrogen bond", "Directional attraction involving partially charged atoms", "Helps A pair with T (or U), and G pair with C"],
        ["Electrostatic interaction", "Attraction or repulsion between charges", "Phosphate makes nucleic acids negatively charged; proteins and ions help manage that charge"],
        ["Hydrophobic / stacking effects", "Bases favor stacking away from water", "Stabilize the interior of the double helix"],
    ], [1.15*inch, 2.2*inch, 3.1*inch]),
    P("1.3 DNA versus RNA", "H2x"),
    table([
        ["Feature", "DNA", "RNA"],
        ["Sugar", "2′-deoxyribose: H at the 2′ carbon", "Ribose: OH at the 2′ carbon"],
        ["Bases", "A, C, G, T", "A, C, G, U"],
        ["Typical cellular form", "Long, double-stranded information store", "Often single-stranded; can fold and catalyze"],
        ["Chemical consequence", "Less prone to backbone hydrolysis", "2′-OH increases reactivity and structural versatility"],
    ], [1.35*inch, 2.5*inch, 2.6*inch]),
    callout(
        "Nucleoside versus nucleotide",
        "<b>Nucleoside = base + sugar.</b> <b>Nucleotide = base + sugar + phosphate.</b> "
        "ATP is therefore a ribonucleoside triphosphate; dATP is the corresponding deoxyribonucleotide used for DNA synthesis."
    ),
]

# 2 polarity
story += section("2. Why 5′ and 3′ direction exist")
story += [
    P("2.1 The phosphodiester backbone", "H2x"),
    P(
        "Inside a nucleic-acid strand, a phosphate bridges the 3′ oxygen of one sugar to the 5′ carbon of the next. "
        "Because the two ends expose different sugar positions, the chain is chemically polar: one end is called 5′ "
        "and the other 3′. A standard free 3′ end carries a hydroxyl group (3′-OH), while a 5′ terminus commonly carries phosphate."
    ),
    callout(
        "Why synthesis is 5′ → 3′",
        "Polymerases form a new phosphodiester bond by using the growing chain’s <b>3′-OH</b> to attack the "
        "alpha phosphate of an incoming nucleoside triphosphate. The incoming nucleotide is therefore added to "
        "the 3′ end, so the product lengthens in the 5′ → 3′ direction.",
        PALE_GREEN, GREEN
    ),
    P("2.2 Antiparallel means opposite chemistry across the same space", "H2x"),
    DuplexFlowable(),
    P(
        "Both strands can be written from their own 5′ end to their own 3′ end, but those paths point in opposite "
        "physical directions. Saying “to the right” is spatial; saying “5′ → 3′” is chemical. Keep the two ideas separate."
    ),
    P("2.3 Linear and circular chromosomes", "H2x"),
    P(
        "A human chromosome is one long linear double-stranded DNA molecule (before replication). Each constituent "
        "strand is continuous but finite, so it has one 5′ end and one 3′ end. Telomeres protect the chromosome ends "
        "and include specialized overhang structures. Covalently closed circular DNA, common in bacteria and plasmids, "
        "has no free ends, yet it still has local 5′ → 3′ polarity around the circle."
    ),
]

# 3 gene anatomy
story += section("3. The anatomy of a human protein-coding gene")
story += [
    P("3.1 One integrated map", "H2x"),
    GeneMapFlowable(),
    P("A simplified TATA-containing promoter. Real human promoters use varied combinations of core elements.", "Captionx"),
    P("3.2 Three distinct molecular landmarks", "H2x"),
    table([
        ["Landmark", "What it controls", "Usually copied into RNA?", "Key point"],
        ["Promoter / TATA region", "Recruitment and orientation of transcription machinery", "Upstream promoter bases remain outside the transcript", "A binding platform for transcription"],
        ["Transcription start site (+1)", "First nucleotide incorporated into RNA", "Yes - it is the first one", "Defines RNA’s 5′ boundary"],
        ["Translation start codon (usually AUG)", "Where the ribosome begins the protein", "Yes", "Occurs downstream, often after a 5′ UTR"],
    ], [1.35*inch, 2.1*inch, 1.25*inch, 1.75*inch]),
    P("3.3 Promoter elements in more color", "H2x"),
    table([
        ["Element", "Approximate position", "What it contributes"],
        ["BRE", "Often near a TATA box", "A TFIIB-recognition element that helps orient and stabilize the preinitiation machinery"],
        ["TATA box", "Often ~25-30 bp upstream of +1", "Bound by TBP within TFIID; TBP bends the DNA and helps establish a geometric landmark"],
        ["Inr", "Overlaps +1", "An initiator motif that can help specify the start region, including at promoters without a TATA box"],
        ["DPE", "Downstream of +1 in some promoters", "A downstream core-promoter element that can cooperate with Inr"],
        ["CpG-rich promoter", "Often spans a broader start region", "Common in human genes; frequently lacks a canonical TATA box and may use dispersed start sites"],
    ], [1.05*inch, 1.45*inch, 3.95*inch]),
    callout(
        "What “recognition” means",
        "Proteins recognize the double helix through atomic contacts, shape, and electrostatic pattern. Because the promoter’s "
        "motifs, spacing, and partner proteins are asymmetric, the assembled "
        "complex has an orientation. That orientation determines which direction is downstream.",
        PALE_PURPLE, PURPLE
    ),
    P("3.4 Human promoters are diverse", "H2x"),
    P(
        "The TATA-containing promoter is a clean teaching example, but many human promoters lack a canonical TATA box. "
        "Some have focused initiation at one dominant start site; others have a broad cluster of start sites, often in "
        "CpG-rich regions. A single gene can use alternative promoters in different tissues or conditions, producing "
        "transcripts with different first exons and 5′ UTRs."
    ),
    table([
        ["Promoter pattern", "Typical architecture", "Biological consequence"],
        ["Focused", "One dominant TSS; may contain TATA or another positioning element", "A comparatively precise RNA 5′ boundary"],
        ["Broad / dispersed", "Several nearby TSSs; often CpG-rich", "A family of closely related 5′ ends"],
        ["Alternative promoters", "Distinct promoter regions at one locus", "Tissue- or state-specific first exons and transcript isoforms"],
    ], [1.35*inch, 2.55*inch, 2.55*inch]),
    P("3.5 The preinitiation machinery", "H2x"),
    table([
        ["Component", "Working role"],
        ["TFIID (TBP + TAFs)", "Recognizes core-promoter features and nucleates assembly; TBP bends TATA-containing DNA"],
        ["TFIIB", "Bridges promoter-bound factors to Pol II and helps position the active complex"],
        ["Pol II + TFIIF", "Brings the RNA-synthesizing enzyme into the assembling complex"],
        ["TFIIE + TFIIH", "Support DNA opening, start-site melting, and CTD phosphorylation"],
        ["Mediator", "Communicates regulatory inputs from activators and enhancers to the Pol II machinery"],
    ], [1.55*inch, 4.90*inch]),
]

# 4 regulation
story += section("4. Promoters, enhancers, chromatin, and direction")
story += [
    P("4.1 Promoter versus enhancer", "H2x"),
    table([
        ["Feature", "Promoter", "Enhancer"],
        ["Primary job", "Provides a local platform for transcription initiation near one or more start sites", "Raises the probability or rate of transcription from a compatible promoter"],
        ["Typical location", "Near the transcription start site", "Can be upstream, downstream, or intronic; sometimes far away in linear sequence"],
        ["Orientation behavior", "Core architecture helps position Pol II and choose a direction", "Many enhancers can function in either orientation, although genomic context still matters"],
        ["Bound factors", "General transcription factors, Pol II, promoter-specific factors", "Sequence-specific activators and coactivators"],
    ], [1.2*inch, 2.55*inch, 2.7*inch]),
    P("4.2 How a distant enhancer can influence a promoter", "H2x"),
    P(
        "DNA is flexible and folded in three dimensions. Enhancer-bound activators can communicate with promoter-bound "
        "machinery through chromatin looping, coactivators such as Mediator, and local transcriptional hubs. Enhancers do "
        "not usually dictate the RNA sequence directly; they influence whether and how often initiation succeeds."
    ),
    callout(
        "Cis and trans",
        "<b>Cis-regulatory elements</b> are DNA sites acting through their genomic context on the same DNA molecule, "
        "such as promoters and enhancers. <b>Trans-acting factors</b> are diffusible molecules, such as transcription-factor "
        "proteins, that can bind many loci.",
        PALE_BLUE, BLUE
    ),
    P("4.3 Chromatin is the access layer", "H2x"),
    P(
        "Human DNA is wrapped around histones in nucleosomes. A promoter sequence can exist but remain poorly accessible. "
        "Chromatin-remodeling complexes, histone modifications, DNA methylation, and transcription factors help establish "
        "cell-type-specific access. This is why the same genome can support a neuron, hepatocyte, and lymphocyte with very "
        "different transcription programs."
    ),
    P("4.4 Promoter architecture establishes direction", "H2x"),
    P(
        "At a defined gene, promoter architecture and bound factors favor a preinitiation complex with a defined orientation. "
        "The strand running 3′ → 5′ in the downstream direction becomes the template. Human promoters can show divergent "
        "initiation; the two directions have distinct start-site architectures and often unequal productive outcomes."
    ),
]

# 5 reaction chemistry
story += section("5. The reaction chemistry and fidelity of RNA synthesis")
story += [
    P("5.1 Substrate selection in the Pol II active site", "H2x"),
    P(
        "RNA polymerase II uses ATP, CTP, GTP, and UTP as substrates. An incoming ribonucleoside triphosphate enters the "
        "active site and samples the exposed DNA template base. Watson-Crick geometry favors A-U and G-C pairing. Correct "
        "base pairing aligns the reactants for catalysis, coupling sequence recognition to bond formation."
    ),
    table([
        ["Reactant / participant", "Chemical role", "Immediate outcome"],
        ["RNA 3′-OH", "Nucleophile on the growing RNA chain", "Forms the next phosphodiester bond"],
        ["Incoming NTP", "Carries the selected base and a triphosphate", "Contributes one nucleotide to RNA"],
        ["Mg²⁺ ions", "Coordinate phosphates and catalytic groups", "Lower the activation barrier and organize the active site"],
        ["Pyrophosphate", "Leaving group from the incoming NTP", "Its release and hydrolysis help drive synthesis forward"],
    ], [1.45*inch, 2.65*inch, 2.35*inch]),
    P("5.2 The two-metal-ion reaction", "H2x"),
    P(
        "Pol II uses a conserved two-metal-ion catalytic strategy. One magnesium ion helps activate the RNA 3′-OH; another "
        "stabilizes negative charge on the NTP phosphates and leaving group. The 3′ oxygen attacks the NTP’s alpha phosphate, "
        "forming a phosphodiester bond and releasing pyrophosphate. Repetition of this cycle lengthens the RNA one nucleotide "
        "at a time."
    ),
    callout(
        "Compact polarity rule",
        "Each nucleotide is added to the RNA’s 3′-OH, so RNA synthesis proceeds 5′ → 3′ while Pol II traverses its DNA "
        "template in the complementary 3′ → 5′ direction.",
        PALE_GREEN, GREEN
    ),
    P("5.3 The transcription bubble and DNA topology", "H2x"),
    P(
        "Pol II locally unwinds a short stretch of DNA, producing a transcription bubble. Within the enzyme, a short RNA-DNA "
        "hybrid helps stabilize the nascent transcript; behind the enzyme, the DNA strands re-anneal and RNA exits through a "
        "separate channel. Moving along helical DNA creates torsional stress, so topoisomerases help relieve supercoiling."
    ),
    P("5.4 Fidelity, pausing, and proofreading", "H2x"),
    P(
        "Correct base-pair geometry, active-site closure, and kinetic checkpoints make incorporation selective. A mismatch can "
        "slow Pol II, promote backtracking, and expose the RNA 3′ end for cleavage before synthesis resumes. Transcription "
        "errors are usually transient because they alter individual RNA molecules rather than the underlying genome, but they "
        "can still affect the proteins made from those molecules."
    ),
]

# 6 stages
story += section("6. The three stages of RNA polymerase II transcription")
story += [
    StagesFlowable(),
    P("6.1 Initiation: choose, open, and launch", "H2x"),
    P(
        "Sequence-specific activators and chromatin regulators make the locus permissive. TFIID (including TBP and TAFs), "
        "TFIIA, TFIIB, Pol II with TFIIF, TFIIE, TFIIH, and Mediator assemble into a preinitiation complex. TFIIH helps open "
        "DNA near +1 and phosphorylates the C-terminal domain (CTD) of Pol II. After synthesizing short RNAs and clearing the "
        "promoter, Pol II enters productive elongation."
    ),
    callout(
        "TATA functions as a binding landmark",
        "At a TATA-containing promoter, TBP binds the double-stranded TATA region. This helps position Pol II downstream, "
        "where RNA synthesis begins at +1.",
        PALE_GOLD, GOLD
    ),
    P("6.2 Elongation: processive RNA synthesis", "H2x"),
    P(
        "Pol II maintains a small transcription bubble. A short RNA-DNA hybrid exists inside the enzyme, while DNA behind "
        "the polymerase re-anneals. Incoming ATP, CTP, GTP, and UTP pair with the exposed template base; catalysis joins each "
        "new nucleotide to the RNA’s 3′ end. Elongation factors regulate pausing, proofreading, chromatin passage, and speed."
    ),
    P("6.3 Termination: define the RNA end and release the machine", "H2x"),
    P(
        "For most human protein-coding transcripts, the RNA is cleaved downstream of a polyadenylation signal, commonly "
        "AAUAAA or a variant. Poly(A) polymerase adds a non-templated poly(A) tail to the new 3′ end. Pol II usually continues "
        "transcribing for a distance before termination mechanisms dismantle the elongation complex. Therefore the translation "
        "stop codon, transcript cleavage site, and Pol II termination site are different landmarks."
    ),
]

# 7 processing
story += section("7. Pre-mRNA processing: cap, splice, cleave, polyadenylate")
story += [
    ProcessingFlowable(),
    P("7.1 The 5′ cap", "H2x"),
    P(
        "Soon after the RNA 5′ end emerges, it receives a 7-methylguanosine cap through an unusual 5′-to-5′ linkage. "
        "The cap protects RNA, helps coordinate splicing and nuclear export, and later recruits translation-initiation factors."
    ),
    P("7.2 Splicing", "H2x"),
    P(
        "The spliceosome recognizes signals around intron boundaries, including a 5′ splice site, branch point, polypyrimidine "
        "tract, and 3′ splice site. It performs two transesterification reactions: the intron forms a lariat intermediate, and "
        "the flanking exons are covalently joined."
    ),
    table([
        ["Term", "Precise meaning", "Functional scope"],
        ["Exon", "Segment retained in a particular mature transcript", "May contain UTR sequence, CDS, or both"],
        ["Intron", "Transcribed segment removed from that RNA during splicing", "Can contain regulatory information and processing signals"],
        ["Coding sequence (CDS)", "Mature-transcript region translated from start codon through stop codon", "Occupies selected portions of one or more exons"],
        ["5′ / 3′ UTR", "Exonic mature-RNA sequence outside the CDS", "Regulates RNA behavior while remaining outside the main protein sequence"],
    ], [1.35*inch, 2.75*inch, 2.35*inch]),
    P("7.3 Cleavage and polyadenylation", "H2x"),
    P(
        "Cleavage defines the mature transcript’s 3′ end. Poly(A) polymerase then adds adenosines without using a DNA template. "
        "The tail supports stability, export, and translation, and its length can change over the RNA’s lifetime."
    ),
    callout(
        "Processing is coupled to transcription",
        "The Pol II CTD acts like a moving landing platform for capping, splicing, and 3′-end-processing factors. These events "
        "are often co-transcriptional rather than a neat sequence that begins only after Pol II stops."
    ),
]

# 8 splicing and isoforms
story += section("8. Alternative splicing and transcript isoforms")
story += [
    P("8.1 One locus can produce several mature RNAs", "H2x"),
    P(
        "A gene may use alternative promoters, transcription start sites, splice donors, splice acceptors, internal exons, "
        "and polyadenylation sites. Each distinct mature RNA structure is a transcript isoform. Alternative structure can alter "
        "only a UTR, alter the protein sequence, shift the reading frame, introduce a premature stop, or yield a noncoding RNA."
    ),
    table([
        ["Mechanism", "Structural change", "Possible consequence"],
        ["Exon skipping", "An internal exon is included or omitted", "Protein segment gained/lost; reading frame may change"],
        ["Alternative 5′ or 3′ splice site", "Exon boundary moves", "A few bases or amino acids gained/lost"],
        ["Mutually exclusive exons", "One of two alternatives is selected", "Tissue-specific protein region"],
        ["Intron retention", "An intron remains in mature RNA", "Regulation, nuclear retention, altered protein, or decay"],
        ["Alternative promoter", "Different first exon / 5′ end", "Different 5′ UTR or N terminus"],
        ["Alternative polyadenylation", "Different 3′ cleavage site", "Different 3′ UTR or C terminus"],
    ], [1.5*inch, 2.2*inch, 2.75*inch]),
    P("8.2 Codons and exon junctions", "H2x"),
    P(
        "Ribosomal codons are consecutive triplets in the mature mRNA coding sequence after ordinary introns have "
        "been removed. A codon may span an exon-exon junction: one or two of its bases can come from one exon and the "
        "remaining bases from the next. The ribosome sees a continuous mature RNA and has no awareness of the former intron."
    ),
    P(
        "<font name='Courier'>pre-mRNA:  ... A G | intron | G C U ...</font><br/>"
        "<font name='Courier'>mature RNA:... A G G C U ...</font><br/>"
        "Depending on the established reading frame, <font name='Courier'>AGG</font> can be one codon assembled across the exon junction."
    ),
    callout(
        "Gene, transcript, and protein are different objects",
        "A <b>gene</b> is a locus-level entity. A <b>transcript</b> is one RNA structure. A <b>protein</b> is one translated "
        "amino-acid sequence. A gene can have many transcripts; multiple transcripts can encode the same protein; some transcripts "
        "encode no protein.",
        PALE_PURPLE, PURPLE
    ),
]

# 9 translation
story += section("9. From mature mRNA to the ribosome")
story += [
    TranslationFlowable(),
    P("9.1 Two distinct processes: transcription and translation", "H2x"),
    table([
        ["Process", "Machine", "Template", "Product", "Main location in human cells"],
        ["Transcription", "RNA polymerase II", "One DNA strand", "pre-mRNA / RNA", "Nucleus"],
        ["Translation", "Ribosome + tRNAs", "Mature mRNA", "Polypeptide", "Cytosol or rough ER surface"],
    ], [1.25*inch, 1.35*inch, 1.35*inch, 1.35*inch, 1.15*inch]),
    P("9.2 Codons and reading frame", "H2x"),
    P(
        "A codon is a three-nucleotide unit read in mRNA’s 5′ → 3′ direction. The selected start codon establishes how all "
        "downstream bases are partitioned into triplets. There are 64 codons: 61 specify amino acids and three - UAA, UAG, UGA - "
        "are stop codons. Because more than one codon can specify the same amino acid, the code is degenerate."
    ),
    P("9.3 The start codon and Kozak context", "H2x"),
    P(
        "The small ribosomal subunit and initiation factors bind near the 5′ cap and usually scan toward the 3′ end. An AUG in "
        "a favorable Kozak context is selected; methionyl-tRNA pairs with AUG; the large subunit joins. Not every AUG in an mRNA "
        "is used as the start."
    ),
    P("9.4 Elongation and stop codons", "H2x"),
    P(
        "For each codon, a tRNA anticodon base-pairs with the mRNA and delivers the corresponding amino acid. The ribosome catalyzes "
        "peptide-bond formation and advances one codon. At UAA, UAG, or UGA, no ordinary tRNA inserts an amino acid; release factors "
        "promote polypeptide release."
    ),
    callout(
        "Three distinct stopping landmarks",
        "A <b>stop codon</b> ends translation; a <b>polyadenylation signal</b> helps specify RNA cleavage; a "
        "<b>transcription termination region</b> is where Pol II disengages. Each belongs to a different molecular event.",
        PALE_CORAL, CORAL
    ),
]

# 10 worked example
story += section("10. One worked example from DNA to peptide")
story += [
    P("10.1 The DNA locus", "H2x"),
    P(
        "Below, the promoter points transcription to the right. The top strand is therefore the coding strand and the bottom "
        "strand is the template because the bottom runs 3′ → 5′ in the direction Pol II travels."
    ),
    P(
        "<font name='Courier'>                       promoter        +1</font><br/>"
        "<font name='Courier'>Coding DNA:   5′-...TATAAA...-G C T A T G G A A | intron | A C C T A A-3′</font><br/>"
        "<font name='Courier'>Template DNA: 3′-...ATATTT...-C G A T A C C T T | intron | T G G A T T-5′</font><br/>"
        "<font name='Courier'>                                    Pol II →</font>"
    ),
    P("10.2 Transcription makes pre-mRNA", "H2x"),
    P(
        "<font name='Courier'>pre-mRNA: 5′-G C U A U G G A A | intron RNA | A C C U A A-3′</font><br/>"
        "The RNA matches the coding DNA from +1 onward except U replaces T. It is complementary and antiparallel to the template."
    ),
    P("10.3 Processing makes mature mRNA", "H2x"),
    P(
        "<font name='Courier'>mature mRNA: cap-5′-G C U A U G G A A A C C U A A-3′-poly(A)</font><br/>"
        "The intron has been removed. For illustration, the selected AUG begins after a short 5′ UTR."
    ),
    P("10.4 Translation partitions the coding region", "H2x"),
    P(
        "<font name='Courier'>5′ UTR | AUG | GAA | ACC | UAA | 3′ UTR</font><br/>"
        "<font name='Courier'>       | Met | Glu | Thr | Stop|</font>"
    ),
    table([
        ["Landmark", "Sequence in this example", "Who uses it?"],
        ["TATA box", "TATAAA in double-stranded promoter DNA", "TBP / TFIID and the preinitiation machinery"],
        ["+1", "G, the first transcribed base", "Pol II begins RNA synthesis"],
        ["Start codon", "AUG in mature mRNA", "Ribosome begins translation"],
        ["Stop codon", "UAA in mature mRNA", "Release factors end translation"],
        ["Poly(A) tail", "A residues added enzymatically after cleavage", "RNA-processing and RNA-binding proteins"],
    ], [1.35*inch, 2.75*inch, 2.35*inch]),
    callout(
        "Scale and scope of the example",
        "Real genes can span thousands to millions of bases, contain many introns, use alternative starts and ends, and be "
        "regulated by multiple enhancers. The compact sequence highlights molecular logic at a study-friendly scale."
    ),
]

# 11 nomenclature
story += section("11. A precise vocabulary for starts, ends, and sequences")
story += [
    table([
        ["Preferred term", "Definition", "Related landmark"],
        ["Transcription start site (TSS, +1)", "First DNA position copied into an RNA", "Located downstream of core-promoter elements"],
        ["Promoter", "DNA region where factors and polymerase assemble for initiation", "Positions transcription relative to the TSS"],
        ["Enhancer", "Regulatory DNA element that can increase promoter output", "Communicates with compatible promoters"],
        ["Template sequence", "DNA sequence Pol II base-pairs against and reads 3′ → 5′", "Determines the complementary RNA sequence"],
        ["Coding strand sequence", "Non-template DNA sequence matching RNA except T/U", "Shares the RNA’s 5′ → 3′ sequence order"],
        ["Coding sequence (CDS)", "Mature-transcript interval from start codon through stop codon", "Occupies translated portions of exons"],
        ["Start codon", "Usually AUG in mRNA; establishes translation frame", "Occurs downstream of the TSS"],
        ["Stop codon", "UAA, UAG, or UGA; ends translation", "Precedes the 3′ UTR"],
        ["Polyadenylation signal", "RNA motif helping direct cleavage and poly(A) addition", "Located upstream of the cleavage site"],
        ["Transcription termination site / region", "Region where Pol II disengages", "Typically downstream of RNA cleavage"],
    ], [1.75*inch, 3.05*inch, 1.65*inch]),
    P("11.1 “Coding strand” versus “coding sequence”", "H2x"),
    P(
        "These phrases sound similar but live at different levels. The <b>coding strand</b> is one entire DNA strand’s role "
        "relative to a gene. The <b>coding sequence</b> is only the portion of a mature transcript that a ribosome translates. "
        "The coding strand also contains promoter DNA, UTR-corresponding DNA, introns, and flanking sequence beyond the CDS."
    ),
    P("11.2 “Start sequence” and “stop sequence”", "H2x"),
    P(
        "Precision comes from naming the relevant landmark. For transcription, use promoter, core-promoter motif, TSS, "
        "polyadenylation signal, cleavage site, or termination region. For translation, use start codon or stop codon."
    ),
]

# 12 crosswalk
story += section("12. Crosswalk to “2. Biological Foundations”")
story += [
    P(
        "The monograph uses molecular biology to motivate why identifiers must distinguish loci, transcripts, proteins, "
        "coordinates, and experimental targets. The chemistry and process described above supply the causal reasons."
    ),
    table([
        ["Monograph section", "Foundation supplied by this primer", "Identifier consequence"],
        ["2.1 DNA as polymer", "Polarity, complementarity, antiparallel strands", "Every sequence and interval needs strand-aware interpretation"],
        ["2.3 Meaning of gene", "One locus can produce multiple RNAs", "Gene ID is not interchangeable with transcript ID"],
        ["2.4 Promoters / enhancers", "Regulatory DNA can lie outside mature transcript sequence", "A perturbation target may be regulatory rather than exonic"],
        ["2.5 Transcription", "Template-directed 5′ → 3′ RNA synthesis", "Transcript sequence depends on strand, TSS, and processing"],
        ["2.6 RNA processing", "Exon choice and RNA ends define isoforms", "Each transcript structure requires its own record"],
        ["2.7 Isoforms", "UTR-only and CDS-changing differences have different outcomes", "Transcript isoform and protein isoform are separate object types"],
        ["2.8 Translation", "Ribosome reads the mature CDS in codons", "Only coding transcripts map to ordinary protein products"],
        ["2.12 cDNA", "Reverse transcriptase copies processed RNA into DNA", "Mature-RNA-derived cDNA usually lacks genomic introns"],
        ["2.15 Object graph", "Locus → transcripts → possible proteins", "Database joins must preserve object type and release"],
    ], [1.15*inch, 2.85*inch, 2.45*inch]),
    P("12.1 A minimal biological object graph", "H2x"),
    callout(
        "Coordinate interval ⊇ gene locus → transcript model(s) → translated protein sequence(s)",
        "Promoters and enhancers regulate edges into transcription. Splicing and RNA-end choices branch one locus into "
        "transcript models. Start/stop codons and reading frames determine which transcripts yield which proteins. Assays "
        "observe molecules and map those observations back onto this graph.",
        PALE_GREEN, GREEN
    ),
]

# 13 variants
story += section("13. How sequence changes propagate through gene expression")
story += [
    P("13.1 Location determines molecular consequence", "H2x"),
    P(
        "A DNA variant has no single universal effect. Its consequence depends on the molecular feature it changes, the cell "
        "type in which that feature is active, and the transcript isoform under consideration. The same one-base substitution "
        "can be silent in one context and consequential in another."
    ),
    table([
        ["Variant location", "Primary molecular effect", "Possible downstream observation"],
        ["Promoter / enhancer", "Changes factor binding or chromatin recruitment", "Altered transcription rate, timing, or cell-type specificity"],
        ["Transcription start region", "Changes TSS selection", "Different 5′ UTR or first exon"],
        ["Splice donor, branch point, or acceptor", "Changes splice-site recognition", "Exon skipping, cryptic splice use, or intron retention"],
        ["5′ UTR", "Changes RNA structure or ribosome recruitment", "Altered translation efficiency"],
        ["Protein-coding sequence", "Changes a codon or reading frame", "Synonymous, missense, nonsense, or frameshift outcome"],
        ["3′ UTR", "Changes RNA-binding or miRNA sites", "Altered localization, stability, or translation"],
        ["Polyadenylation region", "Changes cleavage-site choice", "Different 3′ end and 3′ UTR length"],
    ], [1.55*inch, 2.45*inch, 2.45*inch]),
    P("13.2 Coding consequences", "H2x"),
    table([
        ["Class", "Sequence-level event", "Protein-level consequence"],
        ["Synonymous", "Codon changes to another specifying the same amino acid", "Protein sequence preserved; RNA-level effects remain possible"],
        ["Missense", "Codon changes to one specifying another amino acid", "One amino-acid substitution"],
        ["Nonsense", "Sense codon becomes a stop codon", "Premature termination and possible nonsense-mediated decay"],
        ["Frameshift", "Insertion or deletion changes the triplet grouping", "Downstream amino-acid sequence changes, often followed by an early stop"],
        ["In-frame indel", "Insertion or deletion is a multiple of three bases", "Amino acids added or removed while the downstream frame is preserved"],
    ], [1.20*inch, 2.70*inch, 2.55*inch]),
    P("13.3 Why transcript identity matters", "H2x"),
    P(
        "A genomic variant may fall in the CDS of one transcript, a UTR of another, and an intron of a third. Consequence "
        "statements therefore require a transcript model and annotation release, not merely a gene symbol. This is one of the "
        "central reasons the monograph treats gene, transcript, protein, and coordinate identifiers as distinct object types."
    ),
]

# 14 cheat sheet
story += section("14. One-page transcription cheat sheet")
story += [
    StagesFlowable(),
    table([
        ["Question", "Answer"],
        ["What is a nucleotide?", "Base + sugar + phosphate"],
        ["What gives a nucleic acid polarity?", "Asymmetric 3′-to-5′ phosphodiester backbone"],
        ["What controls Pol II recruitment?", "Promoters, enhancers, transcription factors, Mediator, and chromatin"],
        ["What are the three transcription stages?", "Initiation, elongation, termination"],
        ["What is +1?", "First nucleotide transcribed"],
        ["What is the core synthesis rule?", "Template traversed 3′ → 5′; RNA synthesized 5′ → 3′"],
        ["What is an exon?", "Sequence retained in a mature transcript"],
        ["What is an intron?", "Transcribed sequence removed during splicing"],
        ["How is pre-mRNA processed?", "5′ capping, splicing, 3′ cleavage and polyadenylation"],
        ["What does the ribosome read?", "Mature mRNA 5′ → 3′ in codons"],
        ["What defines the translated region?", "Selected AUG start codon through a UAA, UAG, or UGA stop codon"],
        ["Why can one gene produce several RNAs?", "Alternative promoters, splicing, and 3′-end choices"],
        ["Why are gene and transcript IDs distinct?", "A locus can have multiple transcript structures and protein outcomes"],
    ], [2.25*inch, 4.2*inch]),
]

# 15 self-check
story += section("15. Self-check and answer key")
story += [
    P("Try answering without looking back.", "Bodyx"),
    P("1. What chemical components distinguish a nucleotide from a nucleoside?", "Question"),
    P("2. How do a promoter and an enhancer contribute differently to transcription?", "Question"),
    P("3. What role does a TATA box play, and where does RNA synthesis begin?", "Question"),
    P("4. Name the three stages of Pol II transcription and the defining event in each.", "Question"),
    P("5. What three major processing events convert pre-mRNA toward mature mRNA?", "Question"),
    P("6. How can exons contribute to both UTRs and the protein-coding sequence?", "Question"),
    P("7. Distinguish +1, AUG, UAA, and AAUAAA.", "Question"),
    P("8. Why can two transcript isoforms from one gene encode the same protein?", "Question"),
    HRFlowable(width="100%", thickness=.7, color=LINE, spaceBefore=8, spaceAfter=9),
    P("Answer key", "H2x"),
    P(
        "<b>1.</b> A nucleoside is base + sugar; a nucleotide also includes phosphate. "
        "<b>2.</b> A promoter locally assembles initiation machinery near a TSS; an enhancer raises output from a compatible "
        "promoter through regulatory factors and three-dimensional communication. "
        "<b>3.</b> TATA is a promoter-binding element; RNA synthesis begins downstream at +1. "
        "<b>4.</b> Initiation assembles and launches Pol II; elongation extends RNA; termination releases the transcription complex. "
        "<b>5.</b> 5′ capping, splicing, and 3′ cleavage/polyadenylation. "
        "<b>6.</b> Exon means retained in mature RNA, so exonic sequence can lie before, within, or after the CDS. "
        "<b>7.</b> +1 starts transcription; AUG usually starts translation; UAA is a translation stop codon; AAUAAA commonly "
        "helps direct 3′ cleavage/polyadenylation. "
        "<b>8.</b> Their differences may lie only in UTRs, or their different RNA structures may retain the same CDS."
    ),
]

# 16 glossary
story += section("16. Compact glossary")
glossary = [
    ("3′-OH", "Hydroxyl group at a nucleic-acid strand’s 3′ end; the site of nucleotide addition."),
    ("Antiparallel", "Opposite strand polarities across the same physical direction."),
    ("Coding strand", "DNA strand matching the RNA sequence except T/U; paired with the template strand copied by Pol II."),
    ("Codon", "Three-base unit read by the ribosome in mature mRNA."),
    ("Core promoter", "DNA around a TSS that supports assembly and positioning of basic transcription machinery."),
    ("CTD", "C-terminal domain of Pol II; a regulated platform for transcription and RNA-processing factors."),
    ("Enhancer", "Cis-regulatory DNA element that can increase transcription from a compatible promoter."),
    ("Exon", "Segment retained in a specific mature RNA."),
    ("Intron", "Transcribed segment removed during splicing in a specific RNA-processing path."),
    ("Mediator", "Large coactivator complex linking regulatory factors with Pol II machinery."),
    ("Open reading frame", "Reading frame that continues without an in-frame stop over a defined interval."),
    ("Pol II", "Human RNA polymerase primarily responsible for pre-mRNAs and several noncoding RNAs."),
    ("Promoter", "DNA region where factors assemble to initiate transcription."),
    ("Template strand", "DNA strand read by Pol II 3′ → 5′."),
    ("Transcript isoform", "One particular mature RNA structure associated with a locus."),
    ("TSS / +1", "First nucleotide incorporated into an RNA transcript."),
    ("UTR", "Mature-RNA region outside the main translated coding sequence."),
]
rows = [["Term", "Working definition"]] + [[a, b] for a, b in glossary]
story += [table(rows, [1.45*inch, 5.0*inch])]

# 17 references
story += section("17. Sources and further reading")
refs = [
    ("1", "<i>Gene, Transcript, Protein, and Perturbation Identifier Systems</i>, Section 2, “Biological Foundations.” Companion document supplied for this primer."),
    ("2", "Alberts B, et al. <i>Molecular Biology of the Cell</i>. “From DNA to RNA.” NCBI Bookshelf. https://www.ncbi.nlm.nih.gov/books/NBK26887/"),
    ("3", "Cooper GM. <i>The Cell: A Molecular Approach</i>. “Eukaryotic RNA Polymerases and General Transcription Factors.” NCBI Bookshelf. https://www.ncbi.nlm.nih.gov/books/NBK9935/"),
    ("4", "Cooper GM. <i>The Cell: A Molecular Approach</i>. “RNA Processing and Turnover.” NCBI Bookshelf. https://www.ncbi.nlm.nih.gov/books/NBK9864/"),
    ("5", "Cooper GM. <i>The Cell: A Molecular Approach</i>. “Translation of mRNA.” NCBI Bookshelf. https://www.ncbi.nlm.nih.gov/books/NBK9849/"),
    ("6", "National Human Genome Research Institute. Genetics Glossary entries: Promoter, Exon, Intron, Codon, Stop Codon, Ribosome, and Antisense. https://www.genome.gov/genetics-glossary"),
    ("7", "Allen BL, Taatjes DJ. The Mediator complex as a master regulator of transcription by RNA polymerase II. <i>Nature Reviews Molecular Cell Biology</i>. 2022;23:767-784. doi:10.1038/s41580-022-00498-3."),
]
story += [
    P(
        "This is an explanatory study aid, not a substitute for the annotation definitions or release-specific conventions "
        "used by GENCODE, Ensembl, RefSeq, HGNC, or other identifier authorities."
    )
]
for num, ref in refs:
    story.append(Table([[
        Paragraph(num, ParagraphStyle("RefNum", fontName="Primer-Bold", fontSize=8.2, textColor=TEAL)),
        Paragraph(ref, styles["BodySmall"])
    ]], colWidths=[.28*inch, 6.17*inch], style=TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ])))
story += [
    Spacer(1, 12),
    callout(
        "End state",
        "You are ready for Section 2 when you can trace one base from template DNA into pre-mRNA, through splicing into "
        "mature mRNA, and then locate whether that base belongs to a UTR, a codon, or no mature transcript at all.",
        PALE_GOLD, GOLD
    )
]


doc = PrimerDocTemplate(
    OUTPUT,
    pagesize=letter,
    rightMargin=MARGIN_X,
    leftMargin=MARGIN_X,
    topMargin=MARGIN_TOP,
    bottomMargin=MARGIN_BOTTOM,
    title="Human DNA Transcription: A First-Principles Primer",
    author="OpenAI Codex",
    subject="Supplementary material for Biological Foundations",
)
doc.multiBuild(story)
print(OUTPUT)
