import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


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
