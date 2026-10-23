"""
WEC CTF'26 Certificate Generator
FastAPI SSR Application
"""

import csv
import io
import json
from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import base64
import secrets
import time

from email_service import send_otp_email, get_smtp_settings

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

def load_winners() -> dict[str, dict]:
    """Load winners CSV into a dict keyed by lowercase email."""
    winners = {}
    csv_path = DATA_DIR / "winners.csv"
    if not csv_path.exists():
        return winners
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row.get("email", "").strip().lower()
            if email:
                pos_val = row.get("position", "").strip() or row.get("team_place", "").strip()
                track_val = row.get("track", "").strip()
                winners[email] = {
                    "team_name": row.get("team_name", "").strip(),
                    "position": pos_val,
                    "track": track_val,
                    "certificate_name": row.get("certificate_name", "").strip(),
                }
    return winners


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
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_winner_label(position: Optional[Union[str, int]] = None, track: Optional[str] = None) -> str:
    pos_str = str(position).strip() if position is not None else ""
    trk_str = str(track).strip() if track is not None else ""

    try:
        val = int(float(pos_str))
        pos_label = ordinal(val)
    except (ValueError, TypeError):
        pos_label = pos_str

    if pos_label.lower() == "winner":
        pos_label = "Winner"
    elif pos_label.lower() in ["runner up", "runner-up"]:
        pos_label = "Runner Up"
    elif pos_label.lower() == "1st runner up":
        pos_label = "1st Runner Up"
    elif pos_label.lower() == "2nd runner up":
        pos_label = "2nd Runner Up"

    if trk_str and pos_label:
        if pos_label.lower() in trk_str.lower():
            return trk_str
        if trk_str.lower() in pos_label.lower():
            return pos_label
        if pos_label == "Winner":
            return f"{trk_str} Winner"
        if pos_label in ["Runner Up", "1st Runner Up", "2nd Runner Up"]:
            return f"{trk_str} {pos_label}"
        return f"{pos_label} - {trk_str}"
    elif trk_str:
        return trk_str
    elif pos_label:
        return pos_label
    return "Winner"


def _update_csv_certificate_name(csv_path: Path, email: str, name: str):
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


def save_certificate_name(email: str, name: str):
    _update_csv_certificate_name(DATA_DIR / "winners.csv", email, name)
    _update_csv_certificate_name(DATA_DIR / "participants.csv", email, name)


# ── OTP & Verification Store ──────────────────────────────────────────────────

# In-memory store for pending OTP verifications:
# clean_email -> {"otp": str, "name": str, "created_at": float, "attempts": int, "last_sent_at": float}
otp_store: dict[str, dict] = {}


def generate_otp() -> str:
    """Generate a secure 6-digit numeric OTP."""
    return f"{secrets.randbelow(900000) + 100000}"


def render_certificate_view(request: Request, clean_email: str, name: str):
    """Resolve participant/winner status and render certificate preview."""
    winners = load_winners()
    participants = load_participants()

    if clean_email in winners:
        record = winners[clean_email]
        if not record.get("certificate_name") and clean_email in participants:
            record["certificate_name"] = participants[clean_email].get("certificate_name", "")
        cert_type = "winner"
        position = record.get("position", "")
        track = record.get("track", "")
        position_label = format_winner_label(position, track)
    elif clean_email in participants:
        record = participants[clean_email]
        pos = record["position"]
        track = ""
        is_top3 = isinstance(pos, int) and pos <= 3
        cert_type = "winner" if is_top3 else "participation"
        position_label = ordinal(pos) if is_top3 else None
        position = pos
    else:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "error": config.get("error_message", "No registration found for this email. Please use the email you registered for the event with."),
                "prefill_email": clean_email,
                "prefill_name": name,
            },
        )

    if record.get("certificate_name"):
        name = record["certificate_name"]
    else:
        save_certificate_name(clean_email, name)
        record["certificate_name"] = name

    team_name = record["team_name"]

    return templates.TemplateResponse(
        request,
        "certificate.html",
        {
            "name": name,
            "team_name": team_name,
            "position": position,
            "position_label": position_label,
            "track": track,
            "cert_type": cert_type,
            "email": clean_email,
        },
    )


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
    winners = load_winners()
    participants = load_participants()

    # Validate that email exists in database
    if clean_email not in winners and clean_email not in participants:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "error": config.get("error_message", "No registration found for this email. Please use the email you registered for the event with."),
                "prefill_email": email,
                "prefill_name": name,
            },
        )

    smtp_settings = get_smtp_settings()

    # If email verification is disabled in .env, bypass directly to certificate
    if not smtp_settings["enabled"]:
        return render_certificate_view(request, clean_email, name)

    # Check cooldown if an OTP was recently sent
    cooldown_seconds = smtp_settings["otp_cooldown_seconds"]
    if clean_email in otp_store:
        elapsed = time.time() - otp_store[clean_email].get("last_sent_at", 0)
        if elapsed < cooldown_seconds:
            remaining = int(cooldown_seconds - elapsed)
            return templates.TemplateResponse(
                request,
                "verify_otp.html",
                {
                    "email": clean_email,
                    "error": f"A verification code was already sent. Please wait {remaining}s before requesting a new one.",
                    "cooldown_remaining": remaining,
                },
            )

    # Generate and store OTP
    code = generate_otp()
    otp_store[clean_email] = {
        "otp": code,
        "name": name.strip(),
        "created_at": time.time(),
        "attempts": 0,
        "last_sent_at": time.time(),
    }

    event_title = config.get("event_name", "Event")
    success, err = send_otp_email(clean_email, code, event_title)

    if not success:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "error": err or "Failed to send verification email. Please check your SMTP settings or try again.",
                "prefill_email": email,
                "prefill_name": name,
            },
        )

    return templates.TemplateResponse(
        request,
        "verify_otp.html",
        {
            "email": clean_email,
            "cooldown_remaining": cooldown_seconds,
        },
    )


@app.post("/verify-otp", response_class=HTMLResponse)
async def verify_otp(
    request: Request,
    email: str = Form(...),
    otp: str = Form(...),
):
    clean_email = email.strip().lower()
    clean_otp = otp.strip()
    smtp_settings = get_smtp_settings()
    expiry_seconds = smtp_settings["otp_expiry_minutes"] * 60

    if clean_email not in otp_store:
        return templates.TemplateResponse(
            request,
            "verify_otp.html",
            {
                "email": clean_email,
                "error": "No verification request found or the code has expired. Please request a new code.",
                "cooldown_remaining": 0,
            },
        )

    entry = otp_store[clean_email]

    # Check expiration
    if time.time() - entry["created_at"] > expiry_seconds:
        del otp_store[clean_email]
        return templates.TemplateResponse(
            request,
            "verify_otp.html",
            {
                "email": clean_email,
                "error": "Verification code has expired. Please request a new code.",
                "cooldown_remaining": 0,
            },
        )

    # Check attempts limit (max 5)
    if entry["attempts"] >= 5:
        del otp_store[clean_email]
        return templates.TemplateResponse(
            request,
            "verify_otp.html",
            {
                "email": clean_email,
                "error": "Too many failed attempts. For security reasons, please request a new verification code.",
                "cooldown_remaining": 0,
            },
        )

    # Verify matching OTP
    if clean_otp != entry["otp"]:
        entry["attempts"] += 1
        remaining_attempts = 5 - entry["attempts"]
        return templates.TemplateResponse(
            request,
            "verify_otp.html",
            {
                "email": clean_email,
                "error": f"Invalid verification code. ({remaining_attempts} attempts remaining)",
                "cooldown_remaining": max(0, int(smtp_settings["otp_cooldown_seconds"] - (time.time() - entry["last_sent_at"]))),
            },
        )

    # Success: consume OTP and render certificate view
    stored_name = entry.get("name", "")
    del otp_store[clean_email]

    return render_certificate_view(request, clean_email, stored_name)


@app.post("/resend-otp", response_class=HTMLResponse)
async def resend_otp(
    request: Request,
    email: str = Form(...),
):
    clean_email = email.strip().lower()
    winners = load_winners()
    participants = load_participants()

    if clean_email not in winners and clean_email not in participants:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"error": config.get("error_message", "No registration found for this email.")},
        )

    smtp_settings = get_smtp_settings()
    cooldown_seconds = smtp_settings["otp_cooldown_seconds"]

    # Check cooldown
    if clean_email in otp_store:
        elapsed = time.time() - otp_store[clean_email].get("last_sent_at", 0)
        if elapsed < cooldown_seconds:
            remaining = int(cooldown_seconds - elapsed)
            return templates.TemplateResponse(
                request,
                "verify_otp.html",
                {
                    "email": clean_email,
                    "error": f"Please wait {remaining}s before requesting a new code.",
                    "cooldown_remaining": remaining,
                },
            )
        name = otp_store[clean_email].get("name", "")
    else:
        rec = winners.get(clean_email) or participants.get(clean_email, {})
        name = rec.get("certificate_name") or rec.get("member_name", "")

    code = generate_otp()
    otp_store[clean_email] = {
        "otp": code,
        "name": name,
        "created_at": time.time(),
        "attempts": 0,
        "last_sent_at": time.time(),
    }

    event_title = config.get("event_name", "Event")
    success, err = send_otp_email(clean_email, code, event_title)

    if not success:
        return templates.TemplateResponse(
            request,
            "verify_otp.html",
            {
                "email": clean_email,
                "error": err or "Failed to resend code. Please try again.",
                "cooldown_remaining": 0,
            },
        )

    return templates.TemplateResponse(
        request,
        "verify_otp.html",
        {
            "email": clean_email,
            "success": "A new verification code has been sent to your email.",
            "cooldown_remaining": cooldown_seconds,
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
    position: Optional[str] = Query(default=None),
    cert_type: str = "participation",
    track: Optional[str] = Query(default=None),
):
    """Fill PDF certificate template with participant details."""
    position_label = format_winner_label(position, track) if cert_type == "winner" else None
    pdf_buf = fill_certificate_pdf(name, team_name, position_label, cert_type, track)
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
    position: Optional[str] = Query(default=None),
    cert_type: str = Query(default="participation"),
    track: Optional[str] = Query(default=None),
):
    """Generate PDF and return as base64 for preview embedding."""
    try:
        position_label = format_winner_label(position, track) if cert_type == "winner" else None
        pdf_buf = fill_certificate_pdf(name, team_name, position_label, cert_type, track)
        pdf_buf.seek(0)
        pdf_bytes = pdf_buf.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        return {"pdf_base64": pdf_base64}
    except Exception as e:
        return {"error": str(e), "pdf_base64": ""}


# ── Certificate PDF builder ──────────────────────────────────────────────────

def fill_certificate_pdf(
    name: str,
    team_name: str,
    position_label: Optional[str] = None,
    cert_type: str = "participation",
    track: Optional[str] = None,
) -> io.BytesIO:
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
    c.setFillColor(TEXT_COLOR)
    font_size = 12
    while font_size > 8 and c.stringWidth(name, "Helvetica", font_size) > (580 - 264 - 10):
        font_size -= 0.5
    c.setFont("Helvetica", font_size)
    x = (264 + 580) / 2  # center of field
    y = 295  # middle of field
    c.drawCentredString(x, y, name)
    
    if cert_type == "winner":
        # Draw team position / track
        winner_label = format_winner_label(position_label, track)
        font_size = 11
        while font_size > 7 and c.stringWidth(winner_label, "Helvetica", font_size) > 140:
            font_size -= 0.5
        c.setFont("Helvetica", font_size)
        x = (148 + 296) / 2  # center of field
        y = 158  # middle of field
        c.drawCentredString(x, y, winner_label)
    
    # Draw team name
    if team_name:
        font_size = 11
        while font_size > 7 and c.stringWidth(team_name, "Helvetica", font_size) > 140:
            font_size -= 0.5
        c.setFont("Helvetica", font_size)
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


