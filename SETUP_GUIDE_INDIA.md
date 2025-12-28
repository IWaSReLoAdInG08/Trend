# TrendRadar Setup Guide for Indian Market

## Quick Start Guide

### Prerequisites
- Python 3.8 or higher
- Internet connection

### Step 1: Install Dependencies

Open PowerShell in the TrendRadar folder and run:

```powershell
cd "c:\Users\SK VERMA\Desktop\TrendRadar\TrendRadar"
pip install -r requirements.txt
```

### Step 2: Configuration Overview

The project is already configured for Indian market with:

✅ **Timezone**: Asia/Kolkata (IST)  
✅ **Keywords**: Indian companies, tech startups, personalities, topics  
✅ **Platforms**: Global tech platforms (Reddit, Hacker News, GitHub Trending, Product Hunt, V2EX)

**Note**: We're using global tech platforms because:
- NewsNow API (used by TrendRadar) primarily supports Chinese platforms
- Indian news aggregators (Dailyhunt, InShorts, etc.) don't have public APIs
- Major Indian news sites have RSS feeds but require code changes to integrate

### Step 3: Configure Notifications (Optional but Recommended)

For personal use, configure at least one notification channel. Edit `config/config.yaml`:

#### Option A: Telegram (Recommended)
1. Create a Telegram bot: Talk to [@BotFather](https://t.me/botfather)
2. Get your chat ID: Talk to [@userinfobot](https://t.me/userinfobot)
3. Update in `config.yaml`:
   ```yaml
   telegram_bot_token: "YOUR_BOT_TOKEN"
   telegram_chat_id: "YOUR_CHAT_ID"
   ```

#### Option B: Email
Update in `config.yaml`:
```yaml
email_from: "your-email@gmail.com"
email_password: "your-app-password"  # Use app-specific password for Gmail
email_to: "your-email@gmail.com"
```

### Step 4: Run the Project

```powershell
python -m trendradar
```

**What happens:**
1. Fetches trending news from configured platforms
2. Filters based on your Indian keywords
3. Generates HTML report in `output/` folder
4. Sends notification (if configured)
5. Opens report in browser automatically

### Step 5: Customize Keywords

Edit `config/frequency_words.txt` to add/remove topics you care about:

```
# Add your interests
Tesla
SpaceX
Cryptocurrency

# Remove topics you don't want
# Just delete the lines
```

## Understanding the Configuration

### Platform Sources (`config/config.yaml`)

Current platforms:
- **Reddit**: Global trending discussions (tech-heavy)
- **Hacker News**: Tech news and startup discussions
- **GitHub Trending**: Trending open-source projects
- **Product Hunt**: New product launches
- **V2EX**: Tech community discussions

### Keywords (`config/frequency_words.txt`)

Keywords are grouped by topic. The system will:
- Match news containing these keywords
- Rank by relevance and frequency
- Filter out unwanted content (using `!` prefix)

**Syntax:**
- `keyword` - Basic matching
- `+keyword` - Must appear (required)
- `!keyword` - Exclude (filter out)
- `@5` - Limit to 5 results for this keyword

### Report Modes

In `config.yaml`, you can change `report_mode`:

- **`current`** (default): Shows current trending news matching your keywords
- **`incremental`**: Only shows NEW news (no repeats)
- **`daily`**: Daily summary of all matching news

## Usage

### Manual Commands

#### Fetch News Data Only (No Notifications)
```powershell
python fetch_news.py --no-notify
# or
python manage.py fetch --no-notify
```

#### Send Notifications from Existing Data
```powershell
python send_notifications.py
# or
python manage.py notify
# or
python fetch_news.py --notify-only
```

#### Full Cycle (Fetch + Notify)
```powershell
python fetch_news.py
# or
python manage.py run
```

### Automated Scheduling

#### Option 1: Separate Cron Jobs (Recommended)
- **Hourly Fetch**: Run every hour to collect news data
- **Daily Notify**: Run once daily (e.g., 11 PM) to send summary

**Windows Task Scheduler Setup:**

1. **Hourly Data Collection Task:**
   - Task Name: `TrendRadar Fetch Hourly`
   - Trigger: Every 1 hour
   - Action: Start a program
     - Program: `C:\Python310\python.exe`
     - Arguments: `C:\Users\SK VERMA\Desktop\TrendRadar\TrendRadar\fetch_news.py --no-notify`
     - Start in: `C:\Users\SK VERMA\Desktop\TrendRadar\TrendRadar`

2. **Daily Notification Task:**
   - Task Name: `TrendRadar Notify Daily`
   - Trigger: Daily at 23:00 (11 PM)
   - Action: Start a program
     - Program: `C:\Python310\python.exe`
     - Arguments: `C:\Users\SK VERMA\Desktop\TrendRadar\TrendRadar\send_notifications.py`
     - Start in: `C:\Users\SK VERMA\Desktop\TrendRadar\TrendRadar`

#### Option 2: Single Combined Task (Original)
- **Combined Task**: Fetches and sends notifications every hour
- Task Name: `TrendRadar Hourly`
- Trigger: Every 1 hour
- Action: Start a program
  - Program: `C:\Python310\python.exe`
  - Arguments: `C:\Users\SK VERMA\Desktop\TrendRadar\TrendRadar\fetch_news.py`
  - Start in: `C:\Users\SK VERMA\Desktop\TrendRadar\TrendRadar`

## Troubleshooting

### "Module not found" error
```powershell
pip install -r requirements.txt
```

### No news in report
- Check if keywords are too specific
- Try broader keywords like "India", "Technology", "AI"
- Verify internet connection

### Notification not working
- Check credentials in `config.yaml`
- Ensure `enable_notification: true`
- Test with simple keywords first

## Future Enhancements

### Adding Indian RSS Feeds (Requires Code Changes)

Major Indian news sites with RSS feeds:

**Times of India**
- Top Stories: `https://timesofindia.indiatimes.com/rssfeedstopstories.cms`
- India News: `https://timesofindia.indiatimes.com/rssfeeds/296589292.cms`

**NDTV**
- Top Stories: `https://feeds.feedburner.com/NdtvNews-TopStories`
- India: `https://feeds.feedburner.com/ndtv/Lsgd`

**Hindustan Times**
- Latest: `https://www.hindustantimes.com/feeds/rss/latestnews/rssfeed.xml`
- India: `https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml`

**India Today**
- Top Stories: `https://www.indiatoday.in/rss/home`

To integrate these, you would need to:
1. Modify `trendradar/crawler/fetcher.py` to support RSS parsing
2. Add RSS feed URLs to platform configuration
3. Handle different data formats

## Tips for Best Results

1. **Start Simple**: Use broad keywords initially
2. **Refine Gradually**: Add specific keywords based on what you see
3. **Check Daily**: Run once or twice daily for best trending coverage
4. **Adjust Timing**: If using push notifications, set appropriate time windows
5. **Monitor Output**: Check the HTML reports to see what's being captured

## Getting Help

- Check the [original project README](https://github.com/sansan0/TrendRadar)
- Review configuration examples in `config/config.yaml`
- Test with minimal keywords first

---

**Current Status**: ✅ Ready to run with global tech platforms + Indian keyword filtering
