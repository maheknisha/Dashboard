import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template
from ..config import Config

def send_otp_email(email, otp, name="User"):
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = "Your OTP Code"
        message["From"] = Config.EMAIL_USER
        message["To"] = email

        # Render HTML template
        html_content = render_template(
            "otp_email.html",
            otp=otp,
            name=name
        )

        message.attach(MIMEText(html_content, "html"))

        server = smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT)
        server.starttls()
        server.login(Config.EMAIL_USER, Config.EMAIL_PASS)
        server.sendmail(
            Config.EMAIL_USER,
            email,
            message.as_string()
        )
        server.quit()

        print(f"✅ OTP email sent to {email}")
        return True

    except Exception as e:
        print("❌ Error sending email:", e)
        return False

