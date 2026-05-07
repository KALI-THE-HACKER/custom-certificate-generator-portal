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

# 3. Run the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

---

## Project Structure

```text
wecctf26/
├── main.py                      # FastAPI app & PDF generation logic
├── config.json                  # Centralized configuration file for customizing events
├── requirements.txt
├── data/
│   ├── participants.csv         # Database for participants (updated dynamically)
│   └── sample_participants.csv  # Dummy data template
├── static/
│   ├── assets/
│   │   └── logo.png             # Logo
│   └── css/
│       └── style.css            # Stylesheets
└── templates/
    ├── base.html                # Global layout with Dark Mode
    ├── index.html               # Participant login form
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

## Features

1. **Dual Templates**: The system automatically serves `winner_cert.pdf` (with position) for top 3 teams, and `participation_cert.pdf` for everyone else.
2. **Persistent Names**: Users can only set their certificate name once. It is securely locked and appended to the CSV file automatically.
3. **Live PDF Previews**: Renders the personalized PDF inside the browser using an `iframe`.
4. **General Purpose UI**: Fully customizable via `config.json`.

---

## Modifying Certificate Logic

### Updating PDF Templates
Swap out `participation_cert.pdf` and `winner_cert.pdf` in the `templates/certificate-templates/` directory.

### Adjusting Text Overlay Coordinates
Open `main.py` and modify the X/Y coordinates in `fill_certificate_pdf()`. The app uses `reportlab` to precisely draw text over the existing template before flattening it.

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
