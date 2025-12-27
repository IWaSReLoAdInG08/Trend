import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_email():
    """Test email sending with current configuration"""
    
    sender = os.environ.get('EMAIL_SENDER')
    receiver = os.environ.get('EMAIL_RECEIVER')
    password = os.environ.get('EMAIL_PASSWORD')
    smtp_server = os.environ.get('SMTP_SERVER')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    
    print(f"Testing email configuration:")
    print(f"From: {sender}")
    print(f"To: {receiver}")
    print(f"SMTP: {smtp_server}:{smtp_port}")
    print(f"Password: {'*' * len(password) if password else 'NOT SET'}")
    print("-" * 50)
    
    if not all([sender, receiver, password, smtp_server]):
        print("❌ Missing configuration!")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = receiver
        msg['Subject'] = "🔔 TrendRadar Test - Email Working!"
        
        body = """
        ✅ Success! Your TrendRadar email notifications are working!
        
        You'll now receive news updates at this email address.
        
        - TrendRadar Bot
        """
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect and send
        print("Connecting to SMTP server...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        
        print("Logging in...")
        server.login(sender, password)
        
        print("Sending test email...")
        server.send_message(msg)
        server.quit()
        
        print("✅ Email sent successfully!")
        print(f"Check your inbox: {receiver}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_email()
