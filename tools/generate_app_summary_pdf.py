from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "pdf"
OUTPUT_PDF = OUTPUT_DIR / "gestion_clf_app_summary.pdf"

PAGE_W = 612
PAGE_H = 792
MARGIN_X = 34
TOP_Y = 756


def pdf_escape(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap_text(text, width):
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)


class PdfCanvas:
    def __init__(self):
        self.ops = []

    def rect(self, x, y, w, h, fill_rgb=None, stroke_rgb=None, line_width=1):
        if fill_rgb:
            self.ops.append(f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg")
        if stroke_rgb:
            self.ops.append(f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG")
        self.ops.append(f"{line_width} w")
        if fill_rgb and stroke_rgb:
            self.ops.append(f"{x} {y} {w} {h} B")
        elif fill_rgb:
            self.ops.append(f"{x} {y} {w} {h} f")
        else:
            self.ops.append(f"{x} {y} {w} {h} S")

    def text(self, x, y, text, size=10, font="F1", rgb=(0, 0, 0)):
        safe = pdf_escape(text)
        self.ops.append("BT")
        self.ops.append(f"/{font} {size} Tf")
        self.ops.append(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg")
        self.ops.append(f"1 0 0 1 {x} {y} Tm")
        self.ops.append(f"({safe}) Tj")
        self.ops.append("ET")

    def circle(self, x, y, r, rgb=(0, 0, 0)):
        c = 0.5522847498 * r
        self.ops.append(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg")
        self.ops.append(
            f"{x + r} {y} m "
            f"{x + r} {y + c} {x + c} {y + r} {x} {y + r} c "
            f"{x - c} {y + r} {x - r} {y + c} {x - r} {y} c "
            f"{x - r} {y - c} {x - c} {y - r} {x} {y - r} c "
            f"{x + c} {y - r} {x + r} {y - c} {x + r} {y} c f"
        )

    def render(self):
        return "\n".join(self.ops).encode("latin-1", errors="replace")


def draw_lines(pdf, x, y, lines, size=9, leading=11, font="F1", rgb=(0.13, 0.19, 0.25)):
    cursor = y
    for line in lines:
        pdf.text(x, cursor, line, size=size, font=font, rgb=rgb)
        cursor -= leading
    return cursor


def draw_bullets(pdf, x, y, items, wrap_width, size=8.3, leading=9.7, bullet_rgb=(0.06, 0.48, 0.37)):
    cursor = y
    for item in items:
        lines = wrap_text(item, wrap_width)
        pdf.circle(x + 3, cursor + 2, 1.9, rgb=bullet_rgb)
        cursor = draw_lines(pdf, x + 12, cursor, lines, size=size, leading=leading)
        cursor -= 3
    return cursor


def draw_section_header(pdf, x, y, width, label):
    pdf.rect(x, y - 4, width, 15, fill_rgb=(0.09, 0.20, 0.30))
    pdf.text(x + 7, y, label, size=10.2, font="F2", rgb=(1, 1, 1))
    return y - 22


def build_content():
    what_it_is = [
        "CLF Sistema de Gestion is a Python/Tkinter desktop app for commercial operations, centered on quotations, inventory, purchases, invoicing, and account tracking.",
        "Repo evidence also shows multi-company selection, per-company databases, PDF generation, and document linkage workflows.",
    ]
    who_its_for = [
        "Primary user/persona: an internal sales, operations, or admin user at a trading company who needs to quote, buy, receive, invoice, and follow collections from one desktop system.",
    ]
    features = [
        "Role-based login with a central users database and seeded first-use admin account.",
        "Company selector with stored company metadata and separate database paths.",
        "Quotation, delivery, and account-status workflows with PDF output for quotations.",
        "Inventory controls with stock movements, low-stock alerts, and ABC analysis.",
        "Purchase and supplier management backed by company-level records.",
        "CFDI XML import/parsing plus invoice-to-quotation or invoice-to-purchase linking.",
        "Dashboard KPIs and a linkage center for missing clients, suppliers, products, or invoice relationships.",
    ]
    architecture = [
        "UI shell: `main.py` starts Tkinter and loads sections from `ui/` and `modules/`.",
        "Startup flow: login in `ui/login.py`, then company selection in `selector_empresa.py`, then `SistemaGestion`.",
        "Data: `db_init.py` boots the SQLite company schema; `db_connection.py` switches between SQLite and PostgreSQL from `config.json`.",
        "Documents: quotation PDFs are handled in `ui/generador_pdf_cly.py`; CFDI XML parsing lives in `modules/facturacion.py`; missing links are detected in `modules/vinculacion.py`.",
        "Data flow: user action in Tkinter -> DB read/write -> optional PDF/XML document processing -> refreshed dashboard/section views.",
    ]
    run_steps = [
        "Open `Gestion-CLF/`.",
        "Use a local Python 3 installation. Dependency manifest or install guide: Not found in repo.",
        "Run `python main.py`.",
        "On first use, sign in with `admin / admin123`, then choose a company.",
    ]
    return what_it_is, who_its_for, features, architecture, run_steps


def write_pdf(path, content_bytes):
    objects = []

    def add_object(data):
        if isinstance(data, str):
            data = data.encode("latin-1", errors="replace")
        objects.append(data)

    add_object("<< /Type /Catalog /Pages 2 0 R >>")
    add_object("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    add_object(
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
        f"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> "
        f"/Contents 6 0 R >>"
    )
    add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    add_object(f"<< /Length {len(content_bytes)} >>\nstream\n".encode("latin-1") + content_bytes + b"\nendstream")

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("latin-1"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("latin-1")
    )
    path.write_bytes(pdf)


def build_pdf():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf = PdfCanvas()

    pdf.rect(0, 0, PAGE_W, PAGE_H, fill_rgb=(0.93, 0.96, 0.98))
    pdf.rect(24, 28, PAGE_W - 48, PAGE_H - 56, fill_rgb=(1, 1, 1))

    pdf.text(MARGIN_X, TOP_Y, "CLF Sistema de Gestion", size=20, font="F2", rgb=(0.09, 0.20, 0.30))
    pdf.text(MARGIN_X, TOP_Y - 18, "One-page repo-backed application summary", size=8.2, font="F1", rgb=(0.26, 0.35, 0.43))
    pdf.rect(452, 739, 126, 18, fill_rgb=(0.11, 0.30, 0.43))
    pdf.text(468, 745, "Evidence from repo only", size=7.2, font="F2", rgb=(1, 1, 1))

    col_gap = 18
    col_w = (PAGE_W - (MARGIN_X * 2) - col_gap) / 2
    left_x = MARGIN_X
    right_x = MARGIN_X + col_w + col_gap

    what_it_is, who_its_for, features, architecture, run_steps = build_content()

    left_y = 710
    left_y = draw_section_header(pdf, left_x, left_y, col_w, "What It Is")
    left_y = draw_lines(pdf, left_x, left_y, [line for p in what_it_is for line in wrap_text(p, 57)], size=8.5, leading=10.0)
    left_y -= 6

    left_y = draw_section_header(pdf, left_x, left_y, col_w, "Who It's For")
    left_y = draw_lines(pdf, left_x, left_y, [line for p in who_its_for for line in wrap_text(p, 57)], size=8.5, leading=10.0)
    left_y -= 6

    left_y = draw_section_header(pdf, left_x, left_y, col_w, "How To Run")
    draw_bullets(pdf, left_x, left_y, run_steps, wrap_width=51, size=8.2, leading=9.5, bullet_rgb=(0.06, 0.48, 0.37))

    right_y = 710
    right_y = draw_section_header(pdf, right_x, right_y, col_w, "What It Does")
    right_y = draw_bullets(pdf, right_x, right_y, features, wrap_width=48, size=8.1, leading=9.2, bullet_rgb=(0.10, 0.29, 0.55))
    right_y -= 2

    right_y = draw_section_header(pdf, right_x, right_y, col_w, "How It Works")
    draw_bullets(pdf, right_x, right_y, architecture, wrap_width=48, size=8.0, leading=9.0, bullet_rgb=(0.76, 0.49, 0.00))

    pdf.text(MARGIN_X, 42, "If key setup details were not directly evidenced in the repo, they are marked as Not found in repo.", size=7.4, font="F1", rgb=(0.26, 0.35, 0.43))

    write_pdf(OUTPUT_PDF, pdf.render())


if __name__ == "__main__":
    build_pdf()
