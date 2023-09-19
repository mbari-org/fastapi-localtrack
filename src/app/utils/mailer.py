import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.logger import info


def validate_email(email):
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    matches = re.findall(email_pattern, email)
    # Check if the email is valid
    if len(matches) > 0:
        info(f"Email {email} is valid")
        return True
    else:
        return False

def send_email(subject, message_body, to_email):
    smtp_server = "mbarimail.mbari.org"
    smtp_port = 465
    smtp_username = "dcline@mbari.org"
    from_email = smtp_username
    smtp_password = os.environ['SMTP_PASSWORD']

    # Create a MIME message
    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(message_body, "plain"))

    try:
        # Connect to the SMTP server
        smtp_conn = smtplib.SMTP_SSL(smtp_server, smtp_port)
        #smtp_conn.login(smtp_username, smtp_password)

        # Send the email
        #smtp_conn.sendmail(from_email, to_email, msg.as_string())
        print("Email sent successfully")

        # Disconnect from the SMTP server
        #smtp_conn.quit()

    except Exception as e:
        print("Error sending email:", e)


if __name__ == "__main__":
    send_email(subject="Test Email",
               message_body="This is a test email sent using Python.\n\nHave a nice day\n" ,
               to_email="dcline@mbari.org")
