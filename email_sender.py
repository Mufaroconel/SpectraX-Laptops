import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
SUBJECT = "Your Subject Here"
BODY = "Your email body here."


def send_email(DOCUMENT_PATH):
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECIPIENT_EMAIL
        msg["Subject"] = SUBJECT

        msg.attach(MIMEText(BODY, "plain"))

        with open(DOCUMENT_PATH, "rb") as attachment:
            mime_base = MIMEBase("application", "octet-stream")
            mime_base.set_payload(attachment.read())
            encoders.encode_base64(mime_base)
            mime_base.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(DOCUMENT_PATH)}",
            )
            msg.attach(mime_base)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)

        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        server.quit()
        print(f"Email sent to {RECIPIENT_EMAIL}")
    except Exception as e:
        print(f"Failed to send email to {RECIPIENT_EMAIL}: {e}")
