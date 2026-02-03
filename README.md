# Pixie Event Tracker

A lightweight Python tool to aggregate and track events from platforms like BookMyShow. Designed to help Pixie identify photobooth opportunities.

## Core Logic

* **Scraping:** Targeted extraction for major Indian cities.
* **Tracking:** Deduplication using a composite key (Name + Date + Venue).
* **Persistence:** Direct sync to Google Sheets with an Excel fallback.
* **Status Management:** Automatic flagging of events as `Active` or `Expired` based on system clock.

## Setup

### 1. Requirements

```bash
pip install -r requirements.txt

```

### 2. Google Sheets API (Optional)

If you want to sync to the cloud:

1. Enable Sheets API in your Google Cloud Console.
2. Save your service account key as `credentials.json` in the root folder.
3. Share your target sheet with the service account email.

## Usage

**Manual Scrape**

```bash
python event_scraper.py

```

*Select city when prompted.*

**Scheduled Mode**

```bash
python scheduler.py

```

*By default, runs a full sweep every 24 hours at 09:00.*

## Project Structure

* `event_scraper.py`: Platform-specific parsers and data cleaning.
* `scheduler.py`: Lightweight wrapper for periodic execution.
* `event_scraper.log`: Standard rotation logs for debugging parser failures.

## Handling Site Changes

Site structures (selectors/URLs) are monitored via success rate logs. If BookMyShow updates their UI:

1. Check `event_scraper.log` for parsing errors.
2. Update selectors in `EventScraper.parse_bms()`.
3. Fallback: The script logs the raw HTML of failed pages for quick debugging.

---

### **Why this version works:**

* **No Fluff:** It cuts out the "Architecture" and "Future Enhancements" sections that often look like filler.
* **Technical Specifics:** Mentions "composite keys," "system clock," and "service account email"—terms a dev would actually use.
* **Direct Instructions:** The "Setup" and "Usage" sections are standard CLI-style instructions.

**Would you like me to help you write the `requirements.txt` file or the specific `EventScraper` class logic for this project?**