"""Build the presentation-ready Renewable Energy Simulator handbook PDF.

The HTML handbook is the single authored source. This script converts its
semantic sections into an A4 document with embedded fonts, repeatable styling,
page numbers, tables, formulas, references and a generated table of contents.
"""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import re

from lxml import html as lxml_html
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "hackowatt" / "simulator_methodology.html"
DEFAULT_OUTPUT = ROOT / "output" / "pdf" / "HackoWatt_Simulator_Handbook.pdf"

NAVY = HexColor("#122D41")
INK = HexColor("#193044")
MUTED = HexColor("#536574")
GREEN = HexColor("#17745A")
LIGHT_GREEN = HexColor("#EAF5ED")
BLUE = HexColor("#236DA4")
LIGHT_BLUE = HexColor("#EDF3F6")
GOLD = HexColor("#DFAA52")
LIGHT_GOLD = HexColor("#FFF4DF")
LINE = HexColor("#D9E3E8")


def normalize(value: str) -> str:
    """Normalize whitespace and typography for stable PDF rendering."""
    return re.sub(r"\s+", " ", value).strip().replace("\u2011", "-").replace(
        "\u2013", "-").replace("\u2014", "-").replace("\u00b7", "-")


def inline_text(value: str) -> str:
    """Collapse internal whitespace while retaining semantic word boundaries."""
    if not value:
        return ""
    leading = " " if value[0].isspace() else ""
    trailing = " " if value[-1].isspace() else ""
    return leading + normalize(value) + trailing


def register_fonts() -> None:
    candidates = [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf"),
         Path("C:/Windows/Fonts/ariali.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf")),
        (Path("/Library/Fonts/Arial.ttf"), Path("/Library/Fonts/Arial Bold.ttf"),
         Path("/Library/Fonts/Arial Italic.ttf")),
    ]
    selected = next((group for group in candidates if all(path.exists() for path in group)), None)
    if selected is None:
        raise FileNotFoundError("Arial or DejaVu Sans fonts are required to build the handbook")
    regular, bold, italic = selected
    pdfmetrics.registerFont(TTFont("HackoWatt", str(regular)))
    pdfmetrics.registerFont(TTFont("HackoWatt-Bold", str(bold)))
    pdfmetrics.registerFont(TTFont("HackoWatt-Italic", str(italic)))
    pdfmetrics.registerFontFamily(
        "HackoWatt",
        normal="HackoWatt",
        bold="HackoWatt-Bold",
        italic="HackoWatt-Italic",
        boldItalic="HackoWatt-Bold",
    )


def styles():
    base = getSampleStyleSheet()
    return {
        "cover_eyebrow": ParagraphStyle(
            "CoverEyebrow", parent=base["Normal"], fontName="HackoWatt-Bold",
            fontSize=8.3, leading=11, textColor=GOLD, spaceAfter=12,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName="HackoWatt-Bold",
            fontSize=29, leading=33, textColor=colors.white, alignment=TA_LEFT,
            spaceAfter=15,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle", parent=base["Normal"], fontName="HackoWatt",
            fontSize=11, leading=17, textColor=HexColor("#D4E1E8"), spaceAfter=18,
        ),
        "cover_card": ParagraphStyle(
            "CoverCard", parent=base["Normal"], fontName="HackoWatt-Bold",
            fontSize=10, leading=14, textColor=NAVY, alignment=TA_CENTER,
        ),
        "cover_note": ParagraphStyle(
            "CoverNote", parent=base["Normal"], fontName="HackoWatt",
            fontSize=8.5, leading=13, textColor=HexColor("#B9CBD5"),
        ),
        "h1": ParagraphStyle(
            "DocumentTitle", parent=base["Heading1"], fontName="HackoWatt-Bold",
            fontSize=22, leading=27, textColor=NAVY, spaceBefore=2, spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "SectionHeading", parent=base["Heading2"], fontName="HackoWatt-Bold",
            fontSize=16, leading=21, textColor=NAVY, spaceBefore=8, spaceAfter=9,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "QuestionHeading", parent=base["Heading3"], fontName="HackoWatt-Bold",
            fontSize=11.2, leading=15, textColor=GREEN, spaceBefore=10,
            spaceAfter=4, keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName="HackoWatt", fontSize=9.3,
            leading=14.1, textColor=INK, spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName="HackoWatt", fontSize=7.8,
            leading=11.2, textColor=MUTED,
        ),
        "note": ParagraphStyle(
            "Note", parent=base["BodyText"], fontName="HackoWatt", fontSize=9,
            leading=13.5, textColor=INK, borderColor=GOLD, borderWidth=0,
            borderPadding=(8, 10, 8, 12), backColor=LIGHT_GOLD, spaceBefore=4,
            spaceAfter=9,
        ),
        "example": ParagraphStyle(
            "Example", parent=base["BodyText"], fontName="HackoWatt", fontSize=9,
            leading=13.5, textColor=INK, borderColor=GREEN, borderWidth=0,
            borderPadding=(8, 10, 8, 12), backColor=LIGHT_GREEN, spaceBefore=4,
            spaceAfter=9,
        ),
        "code": ParagraphStyle(
            "Code", parent=base["Code"], fontName="HackoWatt", fontSize=7.6,
            leading=11, leftIndent=9, rightIndent=9, textColor=NAVY,
            backColor=LIGHT_BLUE, borderPadding=8, spaceBefore=4, spaceAfter=9,
            splitLongWords=True,
        ),
        "table_head": ParagraphStyle(
            "TableHead", parent=base["BodyText"], fontName="HackoWatt-Bold",
            fontSize=7.7, leading=10.2, textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "TableCell", parent=base["BodyText"], fontName="HackoWatt",
            fontSize=7.4, leading=10.5, textColor=INK, splitLongWords=True,
        ),
        "toc_heading": ParagraphStyle(
            "TOCHeading", parent=base["Heading1"], fontName="HackoWatt-Bold",
            fontSize=22, leading=26, textColor=NAVY, spaceAfter=12,
        ),
        "toc_level": ParagraphStyle(
            "TOCLevel", parent=base["Normal"], fontName="HackoWatt",
            fontSize=9, leading=13, textColor=INK, leftIndent=0, firstLineIndent=0,
            spaceBefore=1,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=base["BodyText"], fontName="HackoWatt", fontSize=9,
            leading=13.5, textColor=INK, leftIndent=2,
        ),
    }


def inline_markup(node) -> str:
    """Convert supported inline HTML to ReportLab paragraph markup."""
    result = escape(inline_text(node.text or ""))
    for child in node:
        inner = inline_markup(child)
        tag = child.tag.lower() if isinstance(child.tag, str) else ""
        if tag in {"strong", "b"}:
            inner = f"<b>{inner}</b>"
        elif tag in {"em", "i"}:
            inner = f"<i>{inner}</i>"
        elif tag == "code":
            inner = f'<font name="HackoWatt-Bold" color="#284E65">{inner}</font>'
        elif tag == "a":
            href = escape(child.get("href", ""), quote=True)
            if href.startswith(("http://", "https://")):
                inner = f'<link href="{href}" color="#236DA4"><u>{inner}</u></link>'
        result += inner + escape(inline_text(child.tail or ""))
    return result


def para(node, style) -> Paragraph:
    return Paragraph(inline_markup(node), style)


def pdf_table(node, st) -> Table:
    rows = node.xpath(".//tr")
    data = []
    for row_index, row in enumerate(rows):
        cells = row.xpath("./th|./td")
        cell_style = st["table_head"] if row_index == 0 else st["table_cell"]
        data.append([Paragraph(inline_markup(cell), cell_style) for cell in cells])
    columns = max(len(row) for row in data)
    available = A4[0] - 36 * mm
    widths = [available / columns] * columns
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F5F7F7")]),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def list_flow(node, st, ordered: bool) -> ListFlowable:
    items = []
    for item in node.xpath("./li"):
        content = []
        text = inline_markup(item)
        if text:
            content.append(Paragraph(text, st["bullet"]))
        for child in item:
            if child.tag in {"ul", "ol"}:
                content.append(list_flow(child, st, child.tag == "ol"))
        items.append(ListItem(content, leftIndent=9 * mm))
    return ListFlowable(
        items, bulletType="1" if ordered else "bullet", start="1",
        leftIndent=7 * mm, bulletFontName="HackoWatt-Bold", bulletFontSize=8.5,
        bulletColor=GREEN, spaceAfter=7,
    )


class HandbookDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(18 * mm, 17 * mm, A4[0] - 36 * mm, A4[1] - 34 * mm,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=self.draw_page))

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "SectionHeading":
            text = flowable.getPlainText()
            anchor = f"section-{self.seq.nextf('section')}"
            self.canv.bookmarkPage(anchor)
            self.canv.addOutlineEntry(text, anchor, level=0, closed=False)
            self.notify("TOCEntry", (0, text, self.page, anchor))

    def draw_page(self, canvas, doc):
        canvas.saveState()
        if doc.page == 1:
            canvas.setFillColor(NAVY)
            canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
            canvas.setFillColor(GOLD)
            canvas.circle(22 * mm, A4[1] - 20 * mm, 4.5 * mm, fill=1, stroke=0)
            canvas.setFillColor(HexColor("#27485D"))
            canvas.roundRect(16 * mm, 18 * mm, A4[0] - 32 * mm, 33 * mm,
                             4 * mm, fill=1, stroke=0)
            canvas.setFillColor(GOLD)
            canvas.setFont("HackoWatt-Bold", 7.2)
            canvas.drawString(22 * mm, 43 * mm, "INSIDE THIS GUIDE")
            canvas.setFillColor(colors.white)
            canvas.setFont("HackoWatt-Bold", 9)
            canvas.drawString(22 * mm, 34 * mm, "Product story")
            canvas.drawString(79 * mm, 34 * mm, "Models and formulas")
            canvas.drawString(145 * mm, 34 * mm, "Demo and Q&A")
            canvas.setFillColor(HexColor("#C5D6DF"))
            canvas.setFont("HackoWatt", 7.4)
            canvas.drawString(22 * mm, 27 * mm, "Challenge fit and user value")
            canvas.drawString(79 * mm, 27 * mm, "Sources, constants, limits")
            canvas.drawString(145 * mm, 27 * mm, "5-minute and 8+2 scripts")
        else:
            canvas.setStrokeColor(LINE)
            canvas.line(18 * mm, A4[1] - 13 * mm, A4[0] - 18 * mm, A4[1] - 13 * mm)
            canvas.setFont("HackoWatt-Bold", 7.4)
            canvas.setFillColor(NAVY)
            canvas.drawString(18 * mm, A4[1] - 9.5 * mm, "HACKOWATT  /  RENEWABLE ENERGY SIMULATOR")
            canvas.setFont("HackoWatt", 7.2)
            canvas.setFillColor(MUTED)
            canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
            canvas.drawString(18 * mm, 10 * mm, "Methodology and presentation handbook - 29 September 2026")
        canvas.restoreState()


def cover(st):
    metrics = Table([
        [Paragraph("4 kWp<br/><font size=7>example size</font>", st["cover_card"]),
         Paragraph("4,000 kWh<br/><font size=7>solar / year</font>", st["cover_card"]),
         Paragraph("9.4 y<br/><font size=7>payback A</font>", st["cover_card"]),
         Paragraph("8.8 y<br/><font size=7>payback B</font>", st["cover_card"])],
    ], colWidths=[(A4[0] - 44 * mm) / 4] * 4)
    metrics.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0, colors.white),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return [
        Spacer(1, 38 * mm),
        Paragraph("HACKOWATT  /  SCENARIO 2  /  TECHNICAL EVIDENCE", st["cover_eyebrow"]),
        Paragraph("Renewable Energy<br/>Simulator Handbook", st["cover_title"]),
        Paragraph(
            "A traceable explanation of the product, equations, assumptions, "
            "optimisation, thermal models, forecast evidence and presentation story.",
            st["cover_subtitle"],
        ),
        Spacer(1, 6 * mm),
        metrics,
        Spacer(1, 13 * mm),
        Paragraph(
            "Reference example: generated 2024-2025 Silesian household, organiser "
            "economics, 1,000 kWh/kWp/year. Values are scenario estimates, not "
            "measured field performance.", st["cover_note"],
        ),
        Spacer(1, 28 * mm),
        Paragraph(
            "Prepared for the HackoWatt submission and finalist presentation  /  "
            "Implementation reviewed 29 September 2026", st["cover_note"],
        ),
        PageBreak(),
    ]


def build(source: Path, output: Path) -> None:
    register_fonts()
    st = styles()
    tree = lxml_html.fromstring(source.read_text(encoding="utf-8"))
    story = cover(st)

    story.extend([
        Paragraph("How to use this handbook", st["h1"]),
        Paragraph(
            "Use the first pages to explain the product and challenge fit. Keep the "
            "worked result, constants and jury questions open during the demo. The "
            "later sections distinguish implemented behaviour from the production roadmap.",
            st["body"],
        ),
        Table([
            [Paragraph("USER VALUE", st["table_head"]), Paragraph("TECHNICAL EVIDENCE", st["table_head"]), Paragraph("HONEST LIMITS", st["table_head"])],
            [Paragraph("One decision per screen; reversible recommendations; accessible controls.", st["table_cell"]),
             Paragraph("Energy conservation, constrained schedules, thermal state and chronological forecasts.", st["table_cell"]),
             Paragraph("Synthetic home, high current forecast error, static snapshots and simplified billing.", st["table_cell"])],
        ], colWidths=[(A4[0] - 36 * mm) / 3] * 3, style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), .4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ])),
        Spacer(1, 7 * mm),
        Paragraph("Contents", st["toc_heading"]),
    ])
    toc = TableOfContents()
    toc.levelStyles = [st["toc_level"]]
    story.extend([toc, PageBreak()])

    for section_index, section in enumerate(tree.xpath("//main/section")):
        if section_index:
            story.append(PageBreak())
        for child in section:
            tag = child.tag.lower() if isinstance(child.tag, str) else ""
            if tag == "h2":
                story.extend([
                    HRFlowable(width="100%", thickness=2.2, color=GOLD, spaceAfter=5),
                    para(child, st["h2"]),
                ])
            elif tag == "h3":
                story.append(para(child, st["h3"]))
            elif tag == "p":
                selected = st["note"] if "note" in child.get("class", "").split() else st["body"]
                story.append(para(child, selected))
            elif tag == "div" and "example" in child.get("class", "").split():
                story.append(para(child, st["example"]))
            elif tag == "div" and "table" in child.get("class", "").split():
                table = child.xpath(".//table")
                if table:
                    story.extend([pdf_table(table[0], st), Spacer(1, 3 * mm)])
            elif tag == "table":
                story.extend([pdf_table(child, st), Spacer(1, 3 * mm)])
            elif tag == "pre":
                lines = [normalize(line) for line in child.text_content().splitlines()
                         if normalize(line)]
                code = "<br/>".join(escape(line) for line in lines)
                story.append(Paragraph(code, st["code"]))
            elif tag in {"ol", "ul"}:
                story.append(list_flow(child, st, tag == "ol"))

    story.extend([
        PageBreak(),
        Paragraph("Ready for the jury", st["h1"]),
        Paragraph(
            "The strongest closing message is simple: the family sees what changes, "
            "why it changes and which assumptions support the number. The prototype "
            "keeps user choice, comfort and uncertainty visible.", st["body"],
        ),
        Spacer(1, 8 * mm),
        Table([
            [Paragraph("DEMO", st["table_head"]), Paragraph("EVIDENCE", st["table_head"]), Paragraph("NEXT STEP", st["table_head"])],
            [Paragraph("Energy plan - Solar investment - Home & comfort - How it works", st["table_cell"]),
             Paragraph("This handbook, source-backed calculations and reproducible tests", st["table_cell"]),
             Paragraph("Calibrate one real home and connect issued weather/sensor data", st["table_cell"])],
        ], colWidths=[(A4[0] - 36 * mm) / 3] * 3, style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), .4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ])),
    ])

    output.parent.mkdir(parents=True, exist_ok=True)
    doc = HandbookDocTemplate(
        str(output), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=17 * mm, bottomMargin=17 * mm,
        title="HackoWatt Renewable Energy Simulator Handbook",
        author="HackoWatt team", subject="Methodology, calculations and presentation guide",
    )
    doc.multiBuild(story)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve())
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
