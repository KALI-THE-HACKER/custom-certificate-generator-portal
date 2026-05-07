"""
WEC CTF'26 Certificate Generator
FastAPI SSR Application
"""

import csv
import io
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import base64

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "static" / "assets"
TEMPLATES_DIR = BASE_DIR / "templates"
CONFIG_PATH = BASE_DIR / "config.json"

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

config = load_config()

# Get app prefix from config (e.g., "" for root, "/certificate" for /certificate endpoint)
APP_PREFIX = config.get("app_prefix", "").rstrip("/")

app = FastAPI(
    title=f"{config.get('event_short_name', 'Event')} Certificate Generator",
    root_path=APP_PREFIX
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Helper function to generate URLs with the correct app prefix
def url_for(path: str) -> str:
    """Generate a URL with the correct app prefix."""
    if not path.startswith("/"):
        path = "/" + path
    return f"{APP_PREFIX}{path}"

# Add helper functions to template context
templates.env.globals['config'] = config
templates.env.globals['url_for'] = url_for


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_participants() -> dict[str, dict]:
    """Load participants CSV into a dict keyed by lowercase email."""
    participants = {}
    csv_path = DATA_DIR / "participants.csv"
    if not csv_path.exists():
        return participants
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row.get("email", "").strip().lower()
            if email:
                pos_str = row.get("team_place", "").strip()
                try:
                    position = int(float(pos_str)) if pos_str else 99
                except ValueError:
                    position = 99
                
                participants[email] = {
                    "team_name": row.get("team_name", "").strip(),
                    "position": position,
                    "certificate_name": row.get("certificate_name", "").strip(),
                }
    return participants


def ordinal(n: int) -> str:
    suffixes = {1: "st", 2: "nd", 3: "rd"}
    return f"{n}{suffixes.get(n if n <= 3 else 0, 'th')}"


def save_certificate_name(email: str, name: str):
    csv_path = DATA_DIR / "participants.csv"
    if not csv_path.exists():
        return
    rows = []
    fieldnames = []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        if "certificate_name" not in fieldnames:
            fieldnames.append("certificate_name")
        for row in reader:
            if row.get("email", "").strip().lower() == email:
                row["certificate_name"] = name
            rows.append(row)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"error": None},
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    email: str = Form(...),
    name: str = Form(...),
):
    clean_email = email.strip().lower()
    participants = load_participants()
    record = participants.get(clean_email)

    if not record:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "error": config.get("error_message", "No registration found for this email. Please use the email you registered for the event with."),
                "prefill_email": email,
                "prefill_name": name,
            },
        )

    if record.get("certificate_name"):
        name = record["certificate_name"]
    else:
        save_certificate_name(clean_email, name)
        record["certificate_name"] = name

    position = record["position"]
    team_name = record["team_name"]
    cert_type = "winner" if position <= 3 else "participation"
    position_label = ordinal(position) if position <= 3 else None

    return templates.TemplateResponse(
        request,
        "certificate.html",
        {
            "name": name,
            "team_name": team_name,
            "position": position,
            "position_label": position_label,
            "cert_type": cert_type,
            "email": email,
        },
    )


@app.get("/templates-preview", response_class=HTMLResponse)
async def templates_preview(request: Request):
    """Design preview page – swap out template HTML here to update designs."""
    return templates.TemplateResponse(
        request,
        "templates_preview.html",
        {},
    )


@app.get("/download-certificate")
async def download_certificate(
    name: str,
    team_name: str,
    position: int,
    cert_type: str,
):
    """Fill PDF certificate template with participant details."""
    position_label = ordinal(position) if position <= 3 else None
    pdf_buf = fill_certificate_pdf(name, team_name, position_label, cert_type)
    pdf_buf.seek(0)
    safe_name = "".join(c if c.isalnum() else "_" for c in name)
    event_short = config.get("event_short_name", "Event").replace(" ", "_").replace("'", "")
    filename = f"{event_short}_{safe_name}_certificate.pdf"
    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/preview-certificate")
async def preview_certificate(
    name: str = Query(...),
    team_name: str = Query(...),
    position: int = Query(default=99),
    cert_type: str = Query(default="participation"),
):
    """Generate PDF and return as base64 for preview embedding."""
    try:
        position_label = ordinal(position) if position <= 3 else None
        pdf_buf = fill_certificate_pdf(name, team_name, position_label, cert_type)
        pdf_buf.seek(0)
        pdf_bytes = pdf_buf.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        return {"pdf_base64": pdf_base64}
    except Exception as e:
        return {"error": str(e), "pdf_base64": ""}


# ── Certificate PDF builder ──────────────────────────────────────────────────

def fill_certificate_pdf(name: str, team_name: str, position_label: Optional[str], cert_type: str = "participation") -> io.BytesIO:
    """
    Use your PDF template and overlay the participant data with visible text.
    This ensures the data shows in all PDF readers.
    """
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.colors import HexColor
    from PyPDF2 import PdfReader as PyPdfReader, PdfWriter as PyPdfWriter
    
    if cert_type == "winner":
        template_path = TEMPLATES_DIR / "certificate-templates" / "winner_cert.pdf"
    else:
        template_path = TEMPLATES_DIR / "certificate-templates" / "participation_cert.pdf"
        
    # Fallback for root templates
    if not template_path.exists() and cert_type == "participation":
        fallback_path = TEMPLATES_DIR / "participation_cert.pdf"
        if fallback_path.exists():
            template_path = fallback_path

    if not template_path.exists():
        raise HTTPException(status_code=500, detail=f"Certificate template not found: {template_path}")
    
    # Create an overlay with ReportLab
    overlay_buffer = io.BytesIO()
    
    # Use landscape A4 dimensions (same as template)
    c = rl_canvas.Canvas(overlay_buffer, pagesize=landscape(A4))
    
    # Coordinates from the debug output (field positions in the PDF)
    # participant_name: Rect: ['264', '277', '580', '316']
    # team_position: Rect: ['148', '147', '296', '170']
    # team_name: Rect: ['601', '146', '749', '169']
    
    # Colors from original template
    TEXT_COLOR = HexColor("#424242")  # Dark gray text
    
    # Draw participant name (center aligned in field)
    c.setFont("Helvetica", 12)
    c.setFillColor(TEXT_COLOR)
    x = (264 + 580) / 2  # center of field
    y = 295  # middle of field
    c.drawCentredString(x, y, name)
    
    if cert_type == "winner":
        # Draw team position
        c.setFont("Helvetica", 11)
        x = (148 + 296) / 2  # center of field
        y = 158  # middle of field
        c.drawCentredString(x, y, position_label or "Winner")
    
    # Draw team name
    c.setFont("Helvetica", 11)
    x = (601 + 749) / 2  # center of field
    y = 157  # middle of field
    c.drawCentredString(x, y, team_name)
    
    c.save()
    overlay_buffer.seek(0)
    
    # Now merge the overlay with the template using PyPDF2
    template_reader = PyPdfReader(str(template_path))
    overlay_reader = PyPdfReader(overlay_buffer)
    
    # Get the first page from both
    template_page = template_reader.pages[0]
    overlay_page = overlay_reader.pages[0]
    
    # Merge them
    template_page.merge_page(overlay_page)
    
    # Write to output
    output_buffer = io.BytesIO()
    writer = PyPdfWriter()
    writer.add_page(template_page)
    writer.write(output_buffer)
    output_buffer.seek(0)
    
    return output_buffer


