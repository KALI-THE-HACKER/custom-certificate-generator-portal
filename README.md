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
