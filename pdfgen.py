"""Pure-pip PDF output (reportlab). Works on Windows without extra installs."""
from datetime import date
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from money import inr

_FONTS = [("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
          ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
          ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
          ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf")]
_cache = {}

def _fonts():
    """Returns (regular, bold, rupee_symbol). Falls back to 'Rs.' if no font has the rupee glyph."""
    if _cache: return _cache["f"]
    for reg, bold in _FONTS:
        if Path(reg).exists() and Path(bold).exists():
            try:
                f = TTFont("IA", reg)
                pdfmetrics.registerFont(f); pdfmetrics.registerFont(TTFont("IA-B", bold))
                sym = "₹" if 0x20B9 in f.face.charToGlyph else "Rs."
                _cache["f"] = ("IA", "IA-B", sym); return _cache["f"]
            except Exception:
                continue
    _cache["f"] = ("Helvetica", "Helvetica-Bold", "Rs."); return _cache["f"]

def fdate(s): return date.fromisoformat(str(s)).strftime("%d %b %Y")

def render_invoice_pdf(path, biz, inv):
    reg, bold, sym = _fonts(); NAVY = colors.HexColor("#1f3a5f")
    S = lambda **k: ParagraphStyle("x", fontName=k.pop("font", reg), fontSize=k.pop("size", 9.5), leading=k.pop("lead", 13), **k)
    c, t = inv["client"], inv["totals"]
    P = lambda txt, **k: Paragraph(txt, S(**k))
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm,
                            title=inv["number"], author=biz.get("name", ""))
    story = []
    left = [P(f"<b>{biz.get('name','')}</b>", size=13, lead=17, font=bold),
            P(f"{biz.get('address','')}, {biz.get('state','')}<br/>GSTIN: {biz.get('gstin','-')}<br/>{biz.get('email','')} {biz.get('phone','')}", textColor=colors.HexColor("#555555"))]
    right = [P("INVOICE", size=22, lead=26, font=bold, textColor=NAVY, alignment=2),
             P(f"<b>{inv['number']}</b><br/>Date: {fdate(inv['date'])}<br/>Due: <b>{fdate(inv['due'])}</b><br/>Status: {inv.get('status','Draft')}", alignment=2)]
    story += [Table([[left, right]], colWidths=[95*mm, 79*mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")]), Spacer(1, 8*mm)]
    bill = [P("BILL TO", size=8, textColor=colors.grey), P(f"<b>{c.get('name','')}</b>", size=11, font=bold),
            P("<br/>".join(x for x in [c.get("address", ""), c.get("state", ""), f"GSTIN: {c['gstin']}" if c.get("gstin") else "", c.get("email", "")] if x))]
    story += [Table([[bill]], colWidths=[174*mm], style=[("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#cccccc")),
                                                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafafa")), ("LEFTPADDING", (0, 0), (-1, -1), 8)]), Spacer(1, 6*mm)]
    rows = [["#", "Description", "Qty", f"Rate ({sym})", f"Amount ({sym})"]]
    for n, i in enumerate(inv["items"], 1):
        q = f"{i['qty']:g} {i.get('unit','')}".strip()
        rows.append([str(n), Paragraph(i["desc"], S()), q, inr(i["rate"]), inr(i["amount"])])
    story += [Table(rows, colWidths=[10*mm, 80*mm, 25*mm, 29*mm, 30*mm], repeatRows=1, style=[
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), bold),
        ("FONTNAME", (0, 1), (-1, -1), reg), ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 1), (-1, -1), .4, colors.HexColor("#dddddd")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]), Spacer(1, 6*mm)]
    tax = ([[f"CGST {inv['gst_percent']/2:g}%", inr(t["cgst"])], [f"SGST {inv['gst_percent']/2:g}%", inr(t["sgst"])]]
           if inv["same_state"] else [[f"IGST {inv['gst_percent']:g}%", inr(t["igst"])]])
    tot = Table([["Subtotal", inr(t["subtotal"])]] + tax + [[f"TOTAL ({sym})", inr(t["total"])]], colWidths=[40*mm, 38*mm], style=[
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 0), (-1, -1), reg), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("FONTNAME", (0, -1), (-1, -1), bold), ("FONTSIZE", (0, -1), (-1, -1), 12), ("LINEABOVE", (0, -1), (-1, -1), 1.2, NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)])
    pay = [P("<b>Payment details</b>", font=bold)] + [P(x) for x in
           ([f"UPI: {biz['upi']}"] if biz.get("upi") else []) + str(biz.get("bank", "")).splitlines()]
    story += [Table([[pay, tot]], colWidths=[94*mm, 80*mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("BOX", (0, 0), (0, 0), .5, colors.HexColor("#cccccc")), ("LEFTPADDING", (0, 0), (0, 0), 8)]),
              Spacer(1, 12*mm), P("Thank you for your business.", alignment=1, textColor=colors.grey)]
    doc.build(story)
