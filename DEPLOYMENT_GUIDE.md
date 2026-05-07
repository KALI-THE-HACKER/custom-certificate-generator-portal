# Deployment Guide - Custom Path Support

This guide explains how to deploy the Certificate Generator application on any path, including `/` (root), `/certificate`, `/events/certs`, or any other custom endpoint.

---

## Quick Start

### Deploy on Root (`/`)
```bash
python3 deploy.py set-root
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Deploy on `/certificate`
```bash
python3 deploy.py set /certificate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Deploy on `/events/certificates`
```bash
python3 deploy.py set /events/certificates
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## How It Works

The application uses three key mechanisms to support deployment on any path:

### 1. Configuration-Based (`config.json`)
The `app_prefix` field in `config.json` specifies the deployment path:
```json
{
  "app_prefix": "/certificate",
  ...
}
```

### 2. FastAPI Root Path
The application sets FastAPI's `root_path` parameter based on `app_prefix`. This tells the ASGI server where the app is mounted and ensures proper routing.

### 3. Dynamic URL Generation
All templates use a `url_for()` function that automatically prepends the app prefix:
```jinja2
<!-- In base.html -->
<link rel="stylesheet" href="{{ url_for('/static/css/style.css') }}">

<!-- In index.html -->
<form method="post" action="{{ url_for('/generate') }}">

<!-- In certificate.html -->
<a href="{{ url_for('/download-certificate') }}?...">
```

---

## Configuration Methods

### Method 1: Using the Deployment Tool (Recommended)
```bash
# Show current configuration
python3 deploy.py show

# Set a specific path
python3 deploy.py set /certificate

# Set to root
python3 deploy.py set-root

# Example with nested path
python3 deploy.py set /api/events/certs
```

### Method 2: Manual Configuration
Edit `config.json` directly:
```json
{
  "app_prefix": "/certificate",
  "event_name": "WEC CTF'26",
  ...
}
```

---

## Deployment Scenarios

### Scenario 1: Single Domain, Root Path

**Use Case**: `https://certificates.company.com/`

**Configuration**:
```bash
python3 deploy.py set-root
```

**Nginx**:
```nginx
server {
    listen 80;
    server_name certificates.company.com;
    
    location / {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

### Scenario 2: Subpath on Shared Domain

**Use Case**: `https://company.com/certificate`

**Configuration**:
```bash
python3 deploy.py set /certificate
```

**Nginx**:
```nginx
server {
    listen 80;
    server_name company.com;
    
    location /certificate/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**Important**: Note the trailing slash in both `location` and `proxy_pass`.

---

### Scenario 3: Nested Subpath

**Use Case**: `https://company.com/events/certificates`

**Configuration**:
```bash
python3 deploy.py set /events/certificates
```

**Nginx**:
```nginx
location /events/certificates/ {
    proxy_pass http://localhost:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

---

### Scenario 4: Docker Deployment

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

# Build argument for deployment path
ARG APP_PREFIX=""
ENV APP_PREFIX=$APP_PREFIX

# Update config.json with the prefix
RUN python3 -c "import json; cfg = json.load(open('config.json')); cfg['app_prefix'] = '${APP_PREFIX}'; json.dump(cfg, open('config.json', 'w'), indent=2)"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build for root**:
```bash
docker build -t cert-gen:latest .
docker run -p 8000:8000 cert-gen:latest
```

**Build for subpath**:
```bash
docker build --build-arg APP_PREFIX=/certificate -t cert-gen:subpath .
docker run -p 8000:8000 cert-gen:subpath
```

---

### Scenario 5: Docker Compose with Reverse Proxy

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      args:
        APP_PREFIX: /certificate
    ports:
      - "8000:8000"
    environment:
      - APP_PREFIX=/certificate

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - app
```

**nginx.conf**:
```nginx
events {
    worker_connections 1024;
}

http {
    server {
        listen 80;
        server_name localhost;
        
        location /certificate/ {
            proxy_pass http://app:8000/;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

**Run**:
```bash
docker-compose up
# Visit: http://localhost/certificate/
```

---

## Advanced Topics

### Setting via Environment Variable

Create a startup script that reads an environment variable:

**start.sh**:
```bash
#!/bin/bash

# Set app_prefix from environment variable (default to root)
APP_PREFIX="${APP_PREFIX:=}"

# Update config.json
python3 -c "
import json
with open('config.json', 'r') as f:
    config = json.load(f)
config['app_prefix'] = '$APP_PREFIX'
with open('config.json', 'w') as f:
    json.dump(config, f, indent=2)
"

echo "Deployment path: /$APP_PREFIX"

# Start the app
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Usage**:
```bash
chmod +x start.sh
APP_PREFIX=/certificate ./start.sh
```

---

### Multiple Deployments on Same Server

Run multiple instances of the app on different ports with different prefixes:

```bash
# Terminal 1: Root deployment on port 8000
python3 deploy.py set-root
uvicorn main:app --port 8000

# Terminal 2: Subpath deployment on port 8001
python3 deploy.py set /certificate
uvicorn main:app --port 8001

# Terminal 3: Another subpath on port 8002
python3 deploy.py set /events/certificates
uvicorn main:app --port 8002
```

**Nginx Config**:
```nginx
upstream app_root {
    server localhost:8000;
}

upstream app_certificate {
    server localhost:8001;
}

upstream app_events {
    server localhost:8002;
}

server {
    listen 80;
    server_name company.com;
    
    location / {
        proxy_pass http://app_root/;
    }
    
    location /certificate/ {
        proxy_pass http://app_certificate/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    location /events/certificates/ {
        proxy_pass http://app_events/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## Testing Your Deployment

### Test Configuration
```bash
# Show current configuration
python3 deploy.py show
```

### Test URLs
```bash
# Home page
curl http://localhost:8000/

# Generate endpoint (if on subpath, adjust URL accordingly)
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=test@example.com&name=Test User"

# Static files
curl http://localhost:8000/static/css/style.css
```

### Test Behind Proxy
```bash
# With Nginx running locally
curl http://localhost/certificate/
```

---

## Troubleshooting

### CSS/JS not loading
- Check that `app_prefix` in `config.json` matches your deployment path
- Verify static files are being served: `http://domain/app_prefix/static/...`
- Check browser console for 404 errors

### Form submission fails
- Ensure the form action uses `{{ url_for('/generate') }}`
- Check that the form is submitting to the correct path

### Reverse proxy issues
- Always use trailing slashes consistently: `location /path/` and `proxy_pass http://...;`
- Check proxy headers: `X-Forwarded-For`, `X-Forwarded-Proto`, `Host`
- Verify the app can read its own configuration after deployment

### Reset to defaults
```bash
python3 deploy.py set-root
# This resets app_prefix to empty string (root deployment)
```

---

## Summary

The Certificate Generator now supports deployment on any path thanks to:

1. **Configurable `app_prefix`** in `config.json`
2. **FastAPI's `root_path`** for proper ASGI routing
3. **Dynamic URL generation** using `url_for()` in all templates
4. **Helper tools** for easy configuration (`deploy.py`)

Choose your deployment path and the application will automatically adapt all URLs!

