# General-Purpose Certificate Generator

FastAPI server-side-rendering application for generating participant certificates in PDF format using dynamic template overlays.

---

## Setup

```bash
# 1. Create a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables (SMTP / App Password)
cp .env.example .env
# Edit .env and fill in your SMTP_USER and SMTP_PASSWORD

# 4. Run the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

---

## Project Structure

```text
wecctf26/
├── main.py                      # FastAPI app, OTP flow & PDF generation logic
├── email_service.py             # SMTP email sender (supports App Passwords)
├── config.json                  # Centralized configuration file for customizing events
├── .env.example                 # Example SMTP environment variables
├── .env                         # Local environment variables & secrets (ignored by git)
├── requirements.txt
├── data/
│   ├── participants.csv         # Database for participants (updated dynamically)
│   ├── participants.csv.example # Dummy participants template
│   ├── winners.csv              # Database for winners with position & track (updated dynamically)
│   └── winners.csv.example      # Dummy winners template
├── static/
│   ├── assets/
│   │   └── logo.png             # Logo
│   └── css/
│       └── style.css            # Stylesheets
└── templates/
    ├── base.html                # Global layout with Dark Mode
    ├── index.html               # Participant login form
    ├── verify_otp.html          # Email OTP verification & resend screen
    ├── certificate.html         # Live PDF preview & download screen
    └── certificate-templates/
        ├── participation_cert.pdf # Template for participants
        └── winner_cert.pdf        # Template for top 3 winners
```

---

## Configuration (`config.json`)

The application is completely generalized. To use this generator for a different event, simply edit `config.json` at the root of the project.

It contains fields to customize:
1. **Event Details**: `event_name`, `event_short_name`, `organization_name`, `organization_url`.
2. **Copywriting**: `portal_headline`, `index_title`, `index_subtitle`, `error_message`, `copyright_text`.
3. **Theme Colors**: `theme_bg_color`, `theme_panel_color`, `theme_text_color`, `theme_primary_color`, and more!

All templates and routes will dynamically load values from this configuration file.

---

## Email Verification & SMTP Setup (`.env`)

To prevent unauthorized users from claiming certificates using another participant's email, the application includes built-in email verification via a 6-digit OTP sent over SMTP using an **App Password**.

### Environment Variables

Copy `.env.example` to `.env` and fill in your SMTP credentials:

```bash
cp .env.example .env
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `EMAIL_VERIFICATION_ENABLED` | `true` | Set to `false` to disable OTP verification and immediately issue certificates. |
| `EMAIL_DEBUG` | `true` | When `true`, OTP codes are printed to the server terminal console for easy local development without an active SMTP connection. |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server host (e.g., `smtp.gmail.com`, `smtp.zoho.in`, `smtp.office365.com`). |
| `SMTP_PORT` | `587` | Port: `587` for STARTTLS or `465` for SSL. |
| `SMTP_USE_TLS` | `true` | `true` for STARTTLS (port 587); `false` for SSL (port 465). |
| `SMTP_USER` | `""` | SMTP login username / email address. |
| `SMTP_PASSWORD` | `""` | SMTP **App Password** (see instructions below). |
| `SMTP_FROM_NAME` | `"Silicon Maze Team"` | Friendly sender name appearing in the recipient's inbox. |
| `SMTP_FROM_EMAIL` | `""` | Sender email address (defaults to `SMTP_USER` if empty). |
| `OTP_EXPIRY_MINUTES` | `10` | Lifetime of each OTP code in minutes before expiration. |
| `OTP_COOLDOWN_SECONDS`| `60` | Minimum seconds required between consecutive OTP resend requests. |

### How to Generate an App Password

> [!IMPORTANT]
> Modern email providers require an **App Password** instead of your primary account password for SMTP authentication.

#### 1. Gmail / Google Workspace
1. Go to your [Google Account](https://myaccount.google.com/) and navigate to **Security**.
2. Under "How you sign in to Google", ensure **2-Step Verification** is turned **ON**.
3. Search for or click **App passwords** (or go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
4. Enter an App name (e.g. `Certificate Generator`) and click **Create**.
5. Copy the generated 16-character password and paste it into `.env` as `SMTP_PASSWORD`. Set `SMTP_HOST=smtp.gmail.com` and `SMTP_PORT=587`.

#### 2. Zoho Mail
1. Log in to [Zoho Accounts](https://accounts.zoho.com/) and navigate to **Security** > **App Passwords**.
2. Click **Generate New Password**, enter a name (e.g. `Certificate Generator`), and copy the password.
3. Paste it into `.env` as `SMTP_PASSWORD`. Set `SMTP_HOST=smtp.zoho.in` (or `.com`) and `SMTP_PORT=587`.

#### 3. Microsoft 365 / Outlook
1. Go to Microsoft Account **Security** > **Advanced Security Options**.
2. Under **App passwords**, create a new password.
3. In `.env`, set `SMTP_HOST=smtp.office365.com` and `SMTP_PORT=587`.

---

## Participants CSV Format


The application expects `data/participants.csv` with the following columns:

```csv
email,member_name,member_id,member_score,team_name,team_id,team_place,team_score,certificate_name
h3xh7wk@gmail.com,h3xh7wk,151.0,8600.0,0xH3XCORP,94.0,1.0,8600.0,John Doe
...
```

| Column             | Description                                                  |
|--------------------|--------------------------------------------------------------|
| `email`            | Registered email (case-insensitive lookup, used for login)   |
| `team_name`        | Team name drawn onto the certificate                         |
| `team_place`       | Numeric rank (e.g. 1.0, 2.0). 1, 2, 3 → Winner cert; 4+ → Participation |
| `certificate_name` | Permanently locked name chosen by the user during first login|

---

## Winners CSV Format

The application supports `data/winners.csv` containing winners details same as participants with extra details (`position` and `track`):

```csv
email,member_name,member_id,member_score,team_name,team_id,team_place,team_score,certificate_name,position,track
alice@example.com,Alice,101.0,1000.0,Team Alpha,1.0,1.0,1000.0,Alice Smith,Winner,Overall winner
bob@example.com,Bob,102.0,1000.0,Team Alpha,1.0,1.0,1000.0,Bob Johnson,1,Overall
charlie@example.com,Charlie,103.0,900.0,Team Beta,2.0,2.0,900.0,Charlie Brown,Runner Up,Overall
david@example.com,David,104.0,800.0,Team Gamma,3.0,3.0,800.0,David Lee,Winner,Algorithms/Systems track winner
```

| Column             | Description                                                                       |
|--------------------|-----------------------------------------------------------------------------------|
| `position`         | Winner position: number (`1`, `2`) or string (`Winner`, `Runner Up`, etc.)        |
| `track`            | Event track (e.g. `Overall winner`, `Algorithms/Systems track winner`, `Overall`) |

---

## Features

1. **Email OTP Verification**: Validates identity via a secure 6-digit one-time password sent using SMTP and App Passwords (supports Gmail, Zoho, Outlook, etc.) with rate-limiting and expiration timers.
2. **Dual Templates & Winners Support**: The system automatically serves `winner_cert.pdf` (with track and position) for winners listed in `data/winners.csv` (or top 3 teams in `participants.csv`), and `participation_cert.pdf` for everyone else.
3. **Persistent Names**: Users can only set their certificate name once. It is securely locked and appended to the CSV file automatically.
4. **Live PDF Previews**: Renders the personalized PDF inside the browser using an `iframe`.
5. **General Purpose UI**: Fully customizable via `config.json`.

---

## Certificate PDF Templates & Editable Fields

### Standard Variable Names

When creating or modifying certificate templates, use the following standardized variable names for form fields:

| Variable Name | Used In | Description & Example |
| :--- | :--- | :--- |
| `participant_name` | All certificates (`participation_cert.pdf`, `winner_cert.pdf`) | Full name of the recipient (e.g. `John Doe`). Centered in the name line. |
| `team_name` | All certificates (`participation_cert.pdf`, `winner_cert.pdf`) | Name of the team (e.g. `0xH3XCORP`). |
| `team_position` | Winner certificates (`winner_cert.pdf`) | Rank or track position (e.g. `1st`, `Winner`, `1st Runner Up`, or `Algorithms/Systems track winner`). |

---

### How to Make Certificate PDF Fields Editable

You can design your certificate in design tools such as **Canva**, **Figma**, **Adobe Illustrator**, or **PowerPoint**, export it as a flat PDF, and then add editable form fields using any PDF editor:

#### Option 1: PDFescape (Free & Web-Based — Recommended)
1. Visit [PDFescape](https://www.pdfescape.com/) and choose **Upload PDF to PDFescape**.
2. Upload your certificate PDF.
3. In the top-left toolbar, click **Form Field** and select **Text** as the field type.
4. Click and drag on the certificate canvas to place the text box where the text should appear.
5. Right-click the newly created text box and select **Object Properties** (or click the wrench/settings icon).
6. In the **Name** property, enter the variable name:
   - Set to `participant_name` for the participant's name field.
   - Set to `team_name` for the team name field.
   - Set to `team_position` for the position / rank field (on winner templates).
7. Align the box properly (set alignment to **Center** if applicable).
8. Click **Save & Download PDF** (the green double-arrow icon on the left sidebar).
9. Move the exported PDF to `templates/certificate-templates/` (name it `participation_cert.pdf` or `winner_cert.pdf`).

#### Option 2: Adobe Acrobat Pro
1. Open your exported PDF in Adobe Acrobat Pro.
2. In the right sidebar or Tools menu, select **Prepare Form**.
3. Choose **Add a Text Field** from the top toolbar.
4. Drag to draw the field over the name, team, or position area.
5. In the **Field Name** box that pops up (or double-click to open Properties > **General** tab), set the name to `participant_name`, `team_name`, or `team_position`.
6. Under the **Appearance** or **Options** tab, set text alignment to **Center**.
7. Save the PDF into `templates/certificate-templates/`.

#### Option 3: LibreOffice Draw (Free & Open Source)
1. Open the PDF in LibreOffice Draw.
2. Enable form controls: **View** > **Toolbars** > **Form Controls**.
3. Click the **Text Box** tool and draw the bounding area on the certificate.
4. Right-click the box > **Control Properties...** > set the **Name** field to `participant_name`, `team_name`, or `team_position`.
5. Export by clicking **File** > **Export As** > **Export as PDF...**, ensuring that **Create PDF form** is checked.

---

### Inspecting Field Names and Coordinates

The application renders text directly over the template coordinates using ReportLab (which ensures reliable rendering across all browsers, mobile viewers, and PDF readers without form-flattening bugs).

To inspect field names and extract their exact coordinates from your PDF template, run:

```bash
python -c "
import PyPDF2
reader = PyPDF2.PdfReader('templates/certificate-templates/participation_cert.pdf')
for annot in reader.pages[0].get('/Annots', []):
    obj = annot.get_object()
    parent = obj.get('/Parent')
    p_obj = parent.get_object() if parent else None
    name = obj.get('/T') or (p_obj.get('/T') if p_obj else 'Unknown')
    print(f'Field: {name:18} Rect: {obj.get(\"/Rect\")}')
"
```

Output example:
```text
Field: participant_name   Rect: [264, 277, 580, 316]
Field: team_position      Rect: [148, 147, 296, 170]
Field: team_name          Rect: [601, 146, 749, 169]
```

---

### Adjusting Text Overlay Coordinates in `main.py`

Once you know the coordinates `[x1, y1, x2, y2]`:
- **Horizontal center**: `x = (x1 + x2) / 2`
- **Vertical center**: `y = (y1 + y2) / 2` (or adjust slightly for font baseline)
- **Maximum width**: `x2 - x1`

Open `main.py` and update the coordinates in `fill_certificate_pdf()`:

```python
# Coordinates from template inspection:
# participant_name: Rect: ['264', '277', '580', '316'] -> x=(264+580)/2, y=295
# team_position:    Rect: ['148', '147', '296', '170'] -> x=(148+296)/2, y=158
# team_name:        Rect: ['601', '146', '749', '169'] -> x=(601+749)/2, y=157
```

---

## Production Deployment

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or use Gunicorn:

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## Deploying on Custom Paths

### Overview
The application is now configured to work on any deployment path, not just `/`. This is useful when deploying behind reverse proxies or on subpaths.

### Configuration

To deploy the application on a custom path (e.g., `/certificate`, `/events/certificates`, etc.), simply update the `app_prefix` field in `config.json`:

**Example 1: Deploy on `/certificate`**
```json
{
  "app_prefix": "/certificate",
  "event_name": "WEC CTF'26",
  ...
}
```

**Example 2: Deploy on root `/`**
```json
{
  "app_prefix": "",
  "event_name": "WEC CTF'26",
  ...
}
```

**Example 3: Deploy on `/events/certificates`**
```json
{
  "app_prefix": "/events/certificates",
  "event_name": "WEC CTF'26",
  ...
}
```

### How It Works

1. **Configuration-Based**: The `app_prefix` setting in `config.json` is read on startup.
2. **FastAPI Root Path**: The application sets FastAPI's `root_path` parameter, which is used by the ASGI server for routing and reverse proxy compatibility.
3. **Dynamic URLs**: All links in templates (forms, buttons, scripts) are generated dynamically using the `url_for()` helper function, which automatically prepends the app prefix.
4. **Static Files**: CSS, images, and other static assets are served correctly regardless of the deployment path.

### Reverse Proxy Setup

#### Nginx Example
```nginx
location /certificate/ {
    proxy_pass http://localhost:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**In `config.json`, set:**
```json
{
  "app_prefix": "/certificate",
  ...
}
```

#### Apache Example
```apache
<Location /certificate/>
    ProxyPass http://localhost:8000/
    ProxyPassReverse http://localhost:8000/
    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "http"
</Location>
```

**In `config.json`, set:**
```json
{
  "app_prefix": "/certificate",
  ...
}
```

### Running with Uvicorn

When running with Uvicorn, the `root_path` is set automatically based on `config.json`:

```bash
# Will serve at http://your-domain/certificate/
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Testing Different Paths Locally

You can test different deployment paths by modifying `config.json` and restarting the server:

```bash
# Terminal 1: Start the server
source venv/bin/activate
uvicorn main:app --reload

# Terminal 2: Test different paths
curl http://localhost:8000/
curl http://localhost:8000/generate
curl http://localhost:8000/download-certificate?name=Test&team_name=Team&position=1&cert_type=winner
```

Then update `config.json` to test a subpath deployment (without actually using a reverse proxy).

---
