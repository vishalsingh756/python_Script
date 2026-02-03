# Event Discovery & Tracking Tool - Architecture & Codebase Documentation

## Overview
The Event Discovery & Tracking Tool is a web scraping automation system that discovers, tracks, and manages events from BookMyShow across 7 major Indian cities. The system is designed to be reliable, scalable, and resilient to website changes.

---

## 1. DATA EXTRACTION

### 1.1 Platforms Used
Currently, the system supports:
- **Primary**: BookMyShow (https://in.bookmyshow.com)
- **Future**: Expandable to other platforms (Eventbrite, Insider, etc.)

### 1.2 Data Fields Collected
Each event record contains the following fields:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `event_id` | String | Unique hash-based identifier | `a7f3b2c1` |
| `event_name` | String | Name of the event | `John Mayer Solo Live in Mumbai 2026` |
| `event_date` | String | Event date (attempts to parse multiple formats) | `15 Feb 2026` or `TBD` |
| `event_time` | String | Event time (extracted if available) | `7:00 PM` |
| `venue` | String | Venue/Location name | `NCPA Mumbai` or `Various Venues` |
| `city` | String | City name (normalized) | `Mumbai`, `Delhi`, `Bangalore` |
| `category` | String | Event category | `Music`, `Theatre`, `Comedy`, `General` |
| `url` | String | Direct BookMyShow event link | `https://in.bookmyshow.com/events/...` |
| `platform` | String | Data source | `BookMyShow` |
| `status` | String | Event status (computed) | `Active`, `Upcoming`, `Expired` |
| `last_updated` | String | Last scrape timestamp | `2026-02-03 14:30:45` |

### 1.3 Data Extraction Flow

```
BookMyShow Website
    ↓
HTTP Request (curl-cffi → cloudscraper → requests)
    ↓
HTML Parser (BeautifulSoup)
    ↓
Regex Pattern Matching (/events/[^/]+/ET\d+)
    ↓
Event Link Extraction
    ↓
Field Parsing (name, date, venue from parent container text)
    ↓
Event Object Creation
    ↓
Storage (Excel or Google Sheets)
```

### 1.4 HTTP Client Priority Chain
The system uses a fallback mechanism for robust requests:

1. **curl-cffi** (Primary)
   - Mimics Chrome 120 browser
   - Best for CloudFlare/anti-bot bypassing
   - Impersonates real browser requests
   
2. **cloudscraper** (Secondary)
   - Handles CloudFlare challenges
   - Maintains session state
   
3. **requests with HTTPAdapter** (Tertiary)
   - Standard library with retry logic (3 retries)
   - Backoff factor: 1 second
   - Status codes for retry: [429, 500, 502, 503, 504]

### 1.5 Fallback Scrapers for Dynamic Content

If primary HTTP extraction yields no events:

1. **Playwright Scraper** (Browser-rendered)
   - Launches headless Chromium
   - Waits for `networkidle` to ensure JS rendering
   - Extracts from rendered DOM
   
2. **Selenium Scraper** (Browser with WebDriver)
   - Uses `webdriver-manager` for Chrome driver
   - Headless mode with anti-detection flags
   - 3-second wait for JS rendering

---

## 2. CITY SELECTION LOGIC

### 2.1 City Mapping
The system maintains a CITIES dictionary mapping user-friendly names to BookMyShow city codes:

```python
CITIES = {
    'mumbai': 'mumbai',
    'delhi': 'ncr',              # National Capital Region code
    'bangalore': 'bengaluru',    # Updated city name
    'hyderabad': 'hyderabad',
    'pune': 'pune',
    'kolkata': 'kolkata',
    'chennai': 'chennai'
}
```

### 2.2 City URL Construction
Given a city, URLs are built dynamically:

```
https://in.bookmyshow.com/explore/events-{city_code}
```

Examples:
- Mumbai: `https://in.bookmyshow.com/explore/events-mumbai`
- Delhi: `https://in.bookmyshow.com/explore/events-ncr`
- Bangalore: `https://in.bookmyshow.com/explore/events-bengaluru`

### 2.3 User Input Handling
Users can select cities via:
- **Numeric choice** (1-7): Direct selection from menu
- **City name**: Case-insensitive, auto-normalized to lowercase
- **Default**: Falls back to 'Mumbai' if empty input

```python
if choice.isdigit() and 1 <= int(choice) <= 7:
    city = cities[int(choice) - 1]  # Map to city name
else:
    city = choice.lower() if choice else 'Mumbai'  # Normalize
```

---

## 3. DATA STORAGE

### 3.1 Storage Options

#### Option A: Excel (Default)
- **Format**: `.xlsx` (Office Open XML)
- **Location**: `output/events_{city}_{YYYYMMDD}.xlsx`
- **Library**: `openpyxl`, `pandas`
- **Advantages**: 
  - Local storage, no credentials needed
  - Easy to share and open
  - Automatic deduplication

#### Option B: Google Sheets
- **Requires**: `credentials.json` (service account key)
- **Scope**: 
  - `https://spreadsheets.google.com/feeds`
  - `https://www.googleapis.com/auth/drive`
- **Fallback**: Reverts to Excel if Google authentication fails

### 3.2 Sheet Structure

**Column Order:**
```
A: event_id
B: event_name
C: event_date
D: event_time
E: venue
F: city
G: category
H: url
I: platform
J: status
K: last_updated
```

**Data Types:**
- Strings: event fields, URLs
- DateTime: Extracted from various formats

### 3.3 Deduplication Strategy

**Primary Key**: `event_id`
- Generated using hash of (event_name, event_date, venue, city)
- Ensures same event is not stored multiple times

**Deduplication Logic**:
```python
# When merging old + new data
df_combined = pd.concat([df_existing, df_new], ignore_index=True)
df_combined = df_combined.drop_duplicates(subset=['event_id'], keep='first')
```

**Duplicate Resolution**:
- `keep='first'`: Retains older timestamp
- Rationale: First occurrence is most accurate capture

### 3.4 Expiry Handling

**Status Determination** (`_determine_status()`):

```
Event Date < Today
  ↓
Status = "Expired"

Event Date within 7 days from today
  ↓
Status = "Active"

Event Date > 7 days from future
  ↓
Status = "Upcoming"

Date parsing fails
  ↓
Status = "Active" (conservative default)
```

**Date Format Support** (in order of parsing):
1. `%Y-%m-%d` (ISO format: 2026-02-03)
2. `%d %b %Y` (Full text: 03 Feb 2026)
3. `%d/%m/%Y` (Slash format: 03/02/2026)
4. `%b %d, %Y` (Comma format: Feb 03, 2026)

**On Each Scrape Run**:
- Status is recomputed for all events
- Ensures accurate active/expired classification
- Prevents stale status from being stored

---

## 4. AUTOMATION

### 4.1 Current Scheduling Architecture

**Manual Run** (Current Implementation):
```bash
python .\event_scraper.py
```
- Interactive: Prompts user to select city
- Single-run: Processes one city per execution
- Output: Saved immediately to Excel

### 4.2 Scheduler Integration (`scheduler.py`)

The `scheduler.py` file enables automated periodic runs:

**Setup Steps**:
```python
from apscheduler.schedulers.background import BackgroundScheduler
from event_scraper import EventScraper

scheduler = BackgroundScheduler()

# Run daily at 9:00 AM
scheduler.add_job(
    func=lambda: EventScraper('mumbai').scrape_and_save(),
    trigger="cron",
    hour=9,
    minute=0,
    id='mumbai_daily'
)

scheduler.start()
```

**Available Schedules**:
- **Daily**: `hour=9, minute=0`
- **Hourly**: `minute=0` (run at start of every hour)
- **Every 6 hours**: `hour='*/6'`
- **Weekly**: `day_of_week='mon', hour=9`

### 4.3 Update Logic

**On Each Scrape**:
1. Fetch fresh data from BookMyShow
2. Load existing Excel file (if exists)
3. Concatenate old + new dataframes
4. **Remove duplicates** by event_id (keep first entry)
5. **Recompute status** for all events
6. Sort by `last_updated` descending
7. Save merged dataset

**Result**: 
- New events are added
- Duplicate scrapes don't multiply data
- Status is always current

### 4.4 Data Freshness Strategy

| Component | Update Frequency | Method |
|-----------|------------------|--------|
| Event discovery | Daily | Scraper runs |
| Status updates | Per-run | Recompute from date |
| Expiry flagging | Per-run | Status field |
| Last updated | Per-run | Timestamp |

---

## 5. SCALABILITY & RELIABILITY

### 5.1 Handling Site Changes

**Problem**: BookMyShow updates HTML structure frequently
**Solutions Implemented**:

#### A. Flexible Selectors
```python
# Generic patterns instead of specific classes
event_links = soup.find_all('a', href=re.compile(r'/events/[^/]+/ET\d+'))
```

Benefits:
- Regex on href attributes (stable)
- Independent of CSS class names (frequently change)
- Matches event IDs (ET prefix is stable)

#### B. Multiple Fallback Mechanisms
1. **HTML parsing** → Extract links from static HTML
2. **Playwright** → Render JS if HTML is incomplete
3. **Selenium** → Alternative JS rendering
4. Graceful degradation: returns partial data instead of failing

#### C. Regex Pattern-Based Parsing
Instead of relying on HTML structure:
```python
# Extract from href: /events/john-mayer-solo-live-in-mumbai-2026/ET00464841
match = re.search(r'/events/([^/]+)/', href)
event_name = match.group(1).replace('-', ' ').title()
```

Benefits:
- Works even if HTML container structure changes
- Event names and IDs are stable

### 5.2 Error Handling & Resilience

**Layered Error Catching**:

```
Try: HTTP request (primary method)
  ├─ Catch: Network error → Try next fallback
  ├─ Catch: 403/404 → Try cloudscraper
  └─ Catch: 5xx → Retry with backoff (3 attempts)
    
Try: Browser scraping (Playwright)
  ├─ Catch: Browser not installed → Try Selenium
  └─ Catch: Render timeout → Skip, continue
    
Try: Selenium fallback
  └─ Catch: Driver error → Return empty results gracefully
```

**Graceful Degradation**:
- Partial scrapes accepted (e.g., 10 events instead of 30)
- Empty results don't crash: Creates Excel with 0 rows
- Missing fields use defaults: "TBD", "Various Venues", "General"

### 5.3 Rate Limiting & Politeness

**Implementation**:
```python
time.sleep(0.3)  # Between processing each event
time.sleep(2)    # Between category requests (deprecated)
```

**Headers**:
- Mimics real Chrome browser
- Includes Referer, Accept-Language, User-Agent
- Prevents IP blocking

**Retry Strategy**:
```python
status_forcelist = [429, 500, 502, 503, 504]
Retry(total=3, backoff_factor=1)  # Wait 1s, 2s, 4s between retries
```

### 5.4 Data Validation

**Validation Checks**:

| Field | Validation |
|-------|-----------|
| event_id | Unique within dataset |
| event_name | Not empty (skip if missing) |
| event_date | Attempt 4 formats, default "TBD" |
| url | Must start with http(s) or be relative |
| city | Mapped from CITIES dict |

**Skipping Invalid Rows**:
```python
if not event_name:
    return None  # Skip this event card
    
# Continue processing only if passed basic checks
```

### 5.5 Performance Optimization

**Limits Applied**:
```python
for link in event_links[:30]:  # Max 30 events per run
```

**Reasons**:
- BookMyShow loads events in batches
- Processing 30 events = ~15-20 seconds (includes sleep delays)
- Balance between data completeness and performance

**Threading Consideration**:
- Currently single-threaded (safe for shared Excel files)
- Could be parallelized for Playwright/Selenium scrapers

### 5.6 Monitoring & Logging

**Current Output**:
```
============================================================
Event Discovery & Tracking Tool for Pixie
============================================================

Available cities:
1. Mumbai
...

Select city (1-7) or enter city name: 1

Scraping events for: Mumbai

Fetching events from BookMyShow...
Trying https://in.bookmyshow.com/explore/events-mumbai...
Found 30 event links

Found 30 events
Created events_mumbai_20260203.xlsx with 30 events

Data saved to: output/events_mumbai_20260203.xlsx

============================================================
```

**Enhancement Opportunities**:
1. Log to file: `events_scraper.log`
2. Error tracking: Failed URLs, timeouts
3. Performance metrics: Scrape duration, events/sec
4. Success rate: Percentage of events successfully parsed

---

## 6. DEPENDENCY MANAGEMENT

### 6.1 Core Dependencies

```
requests==2.31.0            # HTTP client
beautifulsoup4==4.12.2      # HTML parsing
pandas==2.1.4               # Data manipulation
openpyxl==3.1.2            # Excel I/O
curl-cffi                   # Anti-bot HTTP client (best)
cloudscraper                # CloudFlare bypass
selenium==4.40.0            # Browser automation
webdriver-manager==4.0.2    # ChromeDriver management
playwright==1.58.0          # Browser automation (alternative)
lxml==4.9.3                 # XML/HTML parsing
gspread==5.12.0            # Google Sheets API
oauth2client==4.1.3        # Google OAuth
APScheduler==3.10.4        # Job scheduling
```

### 6.2 Optional Dependencies

- **Playwright browsers**: Install via `playwright install chromium`
- **Google credentials**: Place `credentials.json` in project root
- **Chrome/Chromium**: System requirement for Selenium

---

## 7. FOLDER STRUCTURE

```
d:\pixie photo\
├── src/
│   └── event_scraper.py         # Main scraper class
├── output/                       # Generated Excel files
│   ├── events_mumbai_20260203.xlsx
│   ├── events_delhi_20260203.xlsx
│   └── events_bangalore_20260203.xlsx
├── scheduler.py                  # Scheduled automation
├── requirements.txt              # Python dependencies
├── ARCHITECTURE.md               # This file
└── README.md                     # Quick start guide
```

---

## 8. FUTURE ENHANCEMENTS

### 8.1 Planned Features
1. **Multi-platform support**: Eventbrite, Insider, BookMyEventz
2. **Filtering**: By price range, time, category
3. **Notifications**: Email alerts for new events
4. **Analytics**: Event trends, popularity metrics
5. **Database backend**: SQLite/PostgreSQL instead of Excel
6. **Web dashboard**: View and filter events in browser
7. **API endpoint**: Expose events via REST API

### 8.2 Reliability Improvements
1. **Distributed scraping**: Multiple workers for parallel cities
2. **Proxy rotation**: Use proxy pool to avoid IP bans
3. **Stale data detection**: Alert when no new events found
4. **Health checks**: Monitor scraper success rate

---

## 9. TROUBLESHOOTING

### Issue: "403 Forbidden" errors
**Solution**: The system now uses `curl-cffi` which handles this. If it persists:
1. Update `curl-cffi`: `pip install --upgrade curl-cffi`
2. Try Selenium fallback: Ensure Chrome is installed
3. Check IP: BookMyShow may throttle your IP

### Issue: "No events found"
**Solution**: 
1. Check internet connection
2. Verify BookMyShow website is accessible
3. Check if city spelling is correct
4. Enable debug logging to see actual HTTP errors

### Issue: Excel file locked/slow to open
**Solution**:
1. Reduce event limit in scraper (change `[:30]` to `[:10]`)
2. Use separate Excel files per city (already implemented)
3. Consider database backend for large datasets

---

## 10. CODE EXAMPLES

### 10.1 Running from Command Line
```bash
# Interactive (prompts for city)
python src/event_scraper.py

# Programmatic (single city)
python -c "from src.event_scraper import EventScraper; scraper = EventScraper('mumbai'); events = scraper.scrape_bookmyshow(); scraper.save_to_excel(events)"
```

### 10.2 Extending the Scraper
```python
class EventScraper:
    # Add new city
    CITIES = {
        ...
        'pune': 'pune',
        'ahmedabad': 'ahmedabad'  # New city
    }
    
    # Add new platform
    def scrape_eventbrite(self) -> List[Dict]:
        # Implement scraper for Eventbrite
        pass
```

---

## 11. PERFORMANCE METRICS

**Typical Execution Time** (per city):
- Page load + parsing: 3-5 seconds
- Event extraction (30 events): 10-15 seconds
- Excel save + dedup: 2-3 seconds
- **Total**: ~15-25 seconds per city

**Data Volume**:
- Events per city: 30 (configurable)
- Event record size: ~500 bytes
- File size (100 events): ~50-100 KB

---

## 12. CONTACT & SUPPORT

For issues, enhancements, or platform additions, refer to the codebase structure and follow the existing patterns for consistency.

