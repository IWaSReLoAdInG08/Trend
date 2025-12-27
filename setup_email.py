"""
Complete Email Integration Setup
=================================

Your email: vermashivanshu83@gmail.com

STEP 1: Create Gmail App Password
----------------------------------
1. Visit: https://myaccount.google.com/apppasswords
2. Sign in with your Google account (vermashivanshu83@gmail.com)
3. Select App: "Mail"
4. Select Device: "Windows Computer"
5. Click "Generate"
6. Copy the 16-character password (format: "xxxx xxxx xxxx xxxx")

STEP 2: Set Environment Variables
----------------------------------
Once you have your App Password, run these commands:

PowerShell:
-----------
$env:EMAIL_SENDER="vermashivanshu83@gmail.com"
$env:EMAIL_RECEIVER="vermashivanshu83@gmail.com"
$env:EMAIL_PASSWORD="your-16-char-password-here"
$env:SMTP_SERVER="smtp.gmail.com"
$env:SMTP_PORT="587"

STEP 3: Test
------------
python fetch_news.py

You'll receive news updates via:
✓ Telegram: @trend_08_bot
✓ Email: vermashivanshu83@gmail.com

That's it! 🎉
"""

import os

def check_config():
    """Check if email is configured"""
    required = {
        'EMAIL_SENDER': os.environ.get('EMAIL_SENDER'),
        'EMAIL_RECEIVER': os.environ.get('EMAIL_RECEIVER'),
        'EMAIL_PASSWORD': os.environ.get('EMAIL_PASSWORD'),
        'SMTP_SERVER': os.environ.get('SMTP_SERVER'),
        'SMTP_PORT': os.environ.get('SMTP_PORT'),
    }
    
    print("\nEmail Configuration Status:")
    print("=" * 50)
    for key, value in required.items():
        status = "✓ SET" if value else "✗ MISSING"
        display = "****" if key == 'EMAIL_PASSWORD' and value else (value or "Not set")
        print(f"{key:20s}: {status:10s} ({display})")
    
    all_set = all(required.values())
    print("=" * 50)
    if all_set:
        print("✓ Email is fully configured and ready!")
    else:
        print("✗ Missing configuration - see instructions above")
    
    return all_set

if __name__ == "__main__":
    print(__doc__)
    check_config()
