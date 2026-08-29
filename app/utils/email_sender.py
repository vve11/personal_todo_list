import smtplib
from email.message import EmailMessage

from app.config import Config


def send_email(to_addr: str, subject: str, body: str):
    if not Config.SMTP_HOST:
        return False, "SMTP not configured (set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS)"

    from_addr = Config.SMTP_FROM or Config.SMTP_USER or "todo@localhost"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=20) as smtp:
            smtp.ehlo()
            if Config.SMTP_TLS:
                smtp.starttls()
                smtp.ehlo()
            if Config.SMTP_USER and Config.SMTP_PASS:
                smtp.login(Config.SMTP_USER, Config.SMTP_PASS)
            smtp.send_message(msg)
    except OSError as exc:
        return False, f"Email failed: {exc}"
    return True, "sent"
