# Event Discovery & Tracking Tool

A production-ready tool for Pixie to automatically discover and track events from BookMyShow and District platforms.

## Features

- **Multi-platform scraping**: BookMyShow (District can be added)
- **City selection**: Support for 7+ major Indian cities
- **Smart deduplication**: Unique event IDs prevent duplicates
- **Auto status updates**: Marks events as Active, Upcoming, or Expired
- **Dual storage**: Excel files or Google Sheets
- **Automated scheduling**: Runs at configurable intervals
- **Error handling**: Robust logging and graceful failures

## Quick Start

### Prerequisites

- Python 3.8+
- pip package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd event-tracker
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) For Google Sheets:
   - Create a Google Cloud project
   - Enable Google Sheets API
   - Download credentials.json
   - Place in project root

### Usage

#### Manual Run

```bash
python event_scraper.py
```

Follow the prompts to select a city.

#### Scheduled Automation

```bash
python scheduler.py
```

This runs the scraper:
- Daily at 9 AM for all cities
- Every 6 hours for Mumbai (configurable)

#### Using Cron (Linux/Mac)

Edit crontab:
```bash
crontab -e
```

Add entries:
```
0 9 * * * /usr/bin/python3 /path/to/event_scraper.py mumbai
0 9 * * * /usr/bin/python3 /path/to/event_scraper.py delhi
```

## Data Structure

### Excel/Sheets Columns

| Column | Description | Example |
|--------|-------------|---------|
| event_id | Unique identifier | a7b3c4d5e6f7g8h9 |
| event_name | Event title | Sunburn Festival 2026 |
| event_date | Event date | 2026-03-15 |
| venue | Location | MMRDA Grounds |
| city | City name | Mumbai |
| category | Event type | Music Shows |
| url | Event URL | https://... |
| platform | Source platform | BookMyShow |
| status | Current status | Active |
| last_updated | Last update time | 2026-02-03 14:30:00 |

## Architecture

### Deduplication Strategy

1. Generate unique `event_id` from: name + date + venue + city
2. On update: Sort by `last_updated`, keep latest
3. Remove duplicates based on `event_id`

### Status Logic

- **Expired**: Event date < today
- **Active**: Event within next 7 days
- **Upcoming**: Event beyond 7 days

### Error Handling

- Retry logic with exponential backoff
- Graceful degradation (Google Sheets → Excel)
- Comprehensive logging to file and console

## Scalability

### Current Limitations

- Rate limiting: 2-second delay between requests
- No proxy rotation (add for large-scale)
- Single-threaded (can parallelize)

### Future Enhancements

1. **Multi-threading**: Scrape multiple cities concurrently
2. **Proxy support**: Rotate IPs for higher throughput
3. **API integration**: Use official APIs where available
4. **Database storage**: PostgreSQL/MongoDB for scale
5. **Notification system**: Alert on new high-value events
6. **ML categorization**: Auto-detect photobooth suitability

## Handling Site Changes

### Monitoring

- Log all parsing failures
- Track success rate per platform
- Alert on dramatic drops

### Adaptation

1. Use flexible CSS selectors (regex patterns)
2. Multiple fallback extraction methods
3. Quarterly selector review and update
4. Consider headless browser (Selenium) for JS-heavy sites

## Project Structure

```
event-tracker/
├── event_scraper.py      # Main scraper logic
├── scheduler.py          # Automation scheduler
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── credentials.json     # (Optional) Google Sheets auth
└── event_scraper.log    # Auto-generated log file
```

## Testing

Run manual test:
```bash
python -c "from event_scraper import EventScraper; s = EventScraper('mumbai'); events = s.scrape_bookmyshow(); print(f'Found {len(events)} events')"
```

## Troubleshooting

**Issue**: No events found
- Check internet connection
- Verify city name spelling
- Check if website structure changed

**Issue**: Google Sheets authentication fails
- Ensure credentials.json is present
- Verify API is enabled in Google Cloud Console

**Issue**: Rate limiting errors
- Increase delay between requests
- Consider using proxies

## License

Proprietary - Pixie Internal Use Only

## Contact

For questions or issues, contact the development team.
