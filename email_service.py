import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_email(to_email: str, otp: str) -> bool:
    sender_email = "kumaratul032005@gmail.com"
    app_password = os.getenv("GMAIL_APP_PASSWORD") 

    if not app_password:
        print("CRITICAL ERROR: GMAIL_APP_PASSWORD not found in .env")
        return False

    message = MIMEMultipart()
    message["From"] = f"CodeReview Support <{sender_email}>"
    message["To"] = to_email
    message["Subject"] = f"{otp} is your CodeReview OTP"

    # Premium version of your original design
    html_content = f"""
    <div style="background-color: #f4f7f9; padding: 50px 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
      <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 500px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); overflow: hidden;">
        <tr>
          <td style="padding: 40px 0; text-align: center; background-color: #ffffff;">
            <h1 style="margin: 0; color: #1a1a1a; font-size: 28px; font-weight: 800; letter-spacing: -1px;">CodeReview</h1>
            <div style="height: 3px; width: 40px; background-color: #22bc66; margin: 10px auto 0;"></div>
          </td>
        </tr>
        
        <tr>
          <td style="padding: 0 40px 40px 40px; text-align: center;">
            <p style="color: #51545e; font-size: 16px; line-height: 24px; margin: 0;">
                Hello, <br>
                We received a request to reset your password. Use the verification code below to proceed:
            </p>

            <div style="
                margin: 35px 0;
                padding: 20px;
                background-color: #f9fafb;
                border-radius: 8px;
                border: 1px solid #edf2f7;
            ">
              <span style="
                font-family: 'Courier New', Courier, monospace;
                font-size: 36px;
                letter-spacing: 10px;
                font-weight: bold;
                color: #22bc66;
                display: block;
              ">
                {otp}
              </span>
            </div>

            <p style="font-size: 14px; color: #74787e; margin-bottom: 30px;">
              This code is valid for <b>10 minutes</b> and can only be used once.
            </p>

            <hr style="border: none; border-top: 1px solid #edf2f7; margin: 30px 0;">

            <p style="font-size: 12px; color: #b0adc5; line-height: 18px; margin: 0;">
              If you didn't request this, you can ignore this email. Your password will stay safe.
            </p>
          </td>
        </tr>

        <tr>
          <td style="padding: 20px; background-color: #fafbfc; text-align: center; border-top: 1px solid #edf2f7;">
            <p style="font-size: 11px; color: #b0adc5; margin: 0; text-transform: uppercase; letter-spacing: 1px;">
              Sent by CodeReview Security Team
            </p>
          </td>
        </tr>
      </table>
    </div>
    """
    message.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, to_email, message.as_string())
        print(f"✅ OTP Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"❌ SMTP Failure: {e}")
        return False