import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import Config

logger = logging.getLogger("edutrack.email")

def send_enquiry_notification(enquiry_data):
    """
    Sends an email notification to the administrator when a new institutional enquiry is received.
    Handles network and SMTP errors gracefully so that saved MySQL enquiries are never lost.
    Returns (bool success, str message).
    """
    admin_email = Config.ADMIN_EMAIL
    smtp_host = Config.SMTP_HOST
    smtp_port = Config.SMTP_PORT
    smtp_user = Config.SMTP_USERNAME
    smtp_pass = Config.SMTP_PASSWORD
    from_email = Config.SMTP_FROM_EMAIL or admin_email

    # If SMTP credentials are not configured, log and return graceful status
    if not smtp_user or not smtp_pass:
        logger.info("SMTP credentials not fully configured; notification logged to console only.")
        print(f"[DEVELOPMENT NOTIFICATION] New enquiry saved: {enquiry_data.get('full_name')} from {enquiry_data.get('college_name')} ({enquiry_data.get('phone_number')})")
        return True, "Enquiry received successfully (simulation mode)."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[EduTrack] New Institutional Enquiry: {enquiry_data.get('college_name')}"
        msg["From"] = f"EduTrack Alerts <{from_email}>"
        msg["To"] = admin_email
        msg["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

        plain_text = f"""
New Institutional Enquiry Received on EduTrack
--------------------------------------------------
College / Institution: {enquiry_data.get('college_name')}
Contact Person:        {enquiry_data.get('full_name')}
Phone Number:          {enquiry_data.get('phone_number')}
Email Address:         {enquiry_data.get('email_address') or 'Not provided'}
Message:
{enquiry_data.get('message') or 'No message attached'}

Submission Time:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #090A0C; color: #F5F5F0; margin: 0; padding: 24px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #141619; border: 1px solid #292D30; border-radius: 8px; padding: 32px; }}
            .header {{ border-bottom: 2px solid #C8F169; padding-bottom: 16px; margin-bottom: 24px; }}
            .brand {{ font-size: 22px; font-weight: 700; color: #C8F169; letter-spacing: -0.5px; }}
            .tagline {{ font-size: 13px; color: #A1A1AA; margin-top: 4px; }}
            .title {{ font-size: 18px; font-weight: 600; color: #F5F5F0; margin-bottom: 20px; }}
            .field-row {{ margin-bottom: 14px; line-height: 1.5; }}
            .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: #717780; display: block; }}
            .value {{ font-size: 15px; color: #F5F5F0; font-weight: 500; margin-top: 2px; }}
            .message-box {{ background-color: #1B1E21; border-left: 3px solid #C8F169; padding: 12px 16px; border-radius: 4px; margin-top: 6px; font-size: 14px; color: #E4E4E7; }}
            .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #292D30; font-size: 12px; color: #717780; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <div class="brand">EduTrack</div>
              <div class="tagline">Academic Performance, Made Visible.</div>
            </div>
            <div class="title">New Institutional Partnership Enquiry</div>
            
            <div class="field-row">
              <span class="label">Institution / College</span>
              <div class="value">{enquiry_data.get('college_name')}</div>
            </div>
            
            <div class="field-row">
              <span class="label">Contact Person</span>
              <div class="value">{enquiry_data.get('full_name')}</div>
            </div>

            <div class="field-row">
              <span class="label">Phone Number</span>
              <div class="value">{enquiry_data.get('phone_number')}</div>
            </div>

            <div class="field-row">
              <span class="label">Email Address</span>
              <div class="value">{enquiry_data.get('email_address') or 'Not provided'}</div>
            </div>

            <div class="field-row">
              <span class="label">Notes / Message</span>
              <div class="message-box">{enquiry_data.get('message') or 'No custom message.'}</div>
            </div>

            <div class="footer">
              This is an automated notification from EduTrack Portal. You can manage and mark this enquiry as contacted inside the Admin Portal.
            </div>
          </div>
        </body>
        </html>
        """

        part1 = MIMEText(plain_text, "plain")
        part2 = MIMEText(html_content, "html")
        msg.attach(part1)
        msg.attach(part2)

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.ehlo()
        if smtp_port == 587:
            server.starttls()
            server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(from_email, [admin_email], msg.as_string())
        server.quit()

        logger.info(f"Notification email dispatched to {admin_email} for enquiry {enquiry_data.get('full_name')}")
        return True, "Notification sent."
    except Exception as err:
        logger.error(f"SMTP delivery failed: {err}")
        # Failure is captured without disrupting user
        return False, f"Email delivery error: {str(err)}"
