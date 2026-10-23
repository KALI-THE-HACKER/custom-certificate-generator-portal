"""
Email Service for sending OTP verification emails via SMTP.
Supports Gmail, Zoho, Outlook, and custom SMTP servers using App Passwords.
"""

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


def get_smtp_settings() -> dict:
    """Retrieve SMTP and email verification settings from environment."""
    return {
        "enabled": os.getenv("EMAIL_VERIFICATION_ENABLED", "true").lower() in ("true", "1", "yes"),
        "debug": os.getenv("EMAIL_DEBUG", "false").lower() in ("true", "1", "yes"),
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
        "from_name": os.getenv("SMTP_FROM_NAME", "Certificate Portal").strip(),
        "from_email": os.getenv("SMTP_FROM_EMAIL", "").strip() or os.getenv("SMTP_USER", "").strip(),
        "otp_expiry_minutes": int(os.getenv("OTP_EXPIRY_MINUTES", "10")),
        "otp_cooldown_seconds": int(os.getenv("OTP_COOLDOWN_SECONDS", "60")),
    }


def send_otp_email(to_email: str, otp_code: str, event_name: str) -> Tuple[bool, Optional[str]]:
    """
    Send a one-time verification code (OTP) to the specified email address.
    
    Returns:
        (success: bool, error_message: Optional[str])
    """
    settings = get_smtp_settings()
    
    # Debug / Console Log output
    if settings["debug"] or not settings["user"] or not settings["password"]:
        print(f"\n{'='*60}")
        print(f" [EMAIL DEBUG] OTP for {to_email}: {otp_code}")
        print(f" Event: {event_name}")
        print(f" Expiry: {settings['otp_expiry_minutes']} minutes")
        print(f"{'='*60}\n")
    
    # If credentials are not configured
    if not settings["user"] or not settings["password"]:
        if settings["debug"]:
            # Allow developer testing even without live SMTP credentials
            return True, None
        return False, "SMTP credentials are not configured in .env. Please set SMTP_USER and SMTP_PASSWORD."
    
    sender_name = settings["from_name"]
    sender_email = settings["from_email"]
    subject = f"{otp_code} is your verification code for {event_name}"
    
    # Create multipart MIME email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = to_email
    
    expiry_min = settings["otp_expiry_minutes"]
    
    # Plain text version
    text_content = f"""Hello,

Your verification code for {event_name} certificate generation is:

{otp_code}

This code will expire in {expiry_min} minutes.

If you did not request this certificate, you can safely ignore this email.

Best regards,
{sender_name}
"""
    
    # HTML version with modern styling matching dark theme
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verification Code</title>
</head>
<body style="margin: 0; padding: 0; background-color: #050505; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #050505; padding: 40px 10px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 520px; background-color: #0a0a0a; border: 1px solid #222222; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
          <!-- Header -->
          <tr>
            <td style="padding: 30px 40px; text-align: center; border-bottom: 1px solid #1f2937; background: linear-gradient(180deg, #111827 0%, #0a0a0a 100%);">
              <h1 style="margin: 0; font-size: 22px; font-weight: 700; color: #60a5fa; letter-spacing: -0.5px;">
                {event_name}
              </h1>
              <p style="margin: 6px 0 0 0; font-size: 13px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;">
                Certificate Verification
              </p>
            </td>
          </tr>
          
          <!-- Content -->
          <tr>
            <td style="padding: 36px 40px; text-align: center;">
              <p style="margin: 0 0 20px 0; font-size: 15px; color: #e2e8f0; line-height: 1.5;">
                Use the verification code below to confirm your identity and claim your certificate:
              </p>
              
              <!-- OTP Box -->
              <div style="margin: 28px 0; padding: 18px 24px; background: #0f172a; border: 1px solid #3b82f6; border-radius: 8px; display: inline-block;">
                <span style="font-family: 'Courier New', Courier, monospace; font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #60a5fa; padding-left: 8px;">
                  {otp_code}
                </span>
              </div>
              
              <p style="margin: 20px 0 0 0; font-size: 13px; color: #94a3b8;">
                ⏱️ This code will expire in <strong>{expiry_min} minutes</strong>.
              </p>
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td style="padding: 20px 40px; background-color: #030712; border-top: 1px solid #1f2937; text-align: center;">
              <p style="margin: 0; font-size: 12px; color: #64748b; line-height: 1.5;">
                If you did not request this verification code, please ignore this email.<br>
                &copy; {event_name}. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    
    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    
    try:
        host = settings["host"]
        port = settings["port"]
        use_tls = settings["use_tls"]
        user = settings["user"]
        password = settings["password"]
        
        # SSL connection (typically port 465)
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            # STARTTLS connection (typically port 587 or 25)
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                if use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                server.login(user, password)
                server.send_message(msg)
                
        return True, None
        
    except smtplib.SMTPAuthenticationError as e:
        err_msg = "SMTP authentication failed. Please verify your SMTP_USER and App Password in .env."
        print(f"[SMTP ERROR] {err_msg}: {e}")
        if settings["debug"]:
            return True, None
        return False, err_msg
    except Exception as e:
        err_msg = f"Failed to send email: {str(e)}"
        print(f"[SMTP ERROR] {err_msg}")
        if settings["debug"]:
            return True, None
        return False, err_msg
