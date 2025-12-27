import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sender = "vermashivanshu83@gmail.com"
receiver = "vermashivanshu83@gmail.com"  
password = "ismgbdbkxquzhfix"

print("Testing Gmail SMTP with SSL (port 465)...")
print(f"From: {sender}")
print(f"To: {receiver}")
print("-" * 50)

try:
    # Create simple message
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = "TrendRadar News Update - Test"
    
    body = """Success! Your TrendRadar email notifications are working!

You'll now receive news updates at this address.

- TrendRadar Bot"""
    
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    # Try SSL on port 465
    print("Connecting via SSL to smtp.gmail.com:465...")
    server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10)
    
    # Login
    print("Logging in...")
    server.login(sender, password)
    print("Login successful!")
    
    # Send
    print("Sending email...")
    text = msg.as_string()
    server.sendmail(sender, receiver, text)
    server.quit()
    
    print("\n✅ SUCCESS! Email sent via SSL!")
    print(f"Check your inbox: {receiver}")
    print("\nEmail notifications are now working!")
    
except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}")
    print(f"Details: {str(e)}")
    print("\nThis might be a network/firewall issue blocking SMTP ports.")
