"""
Event Discovery & Tracking Tool for Pixie
Scrapes event data from BookMyShow and stores in Google Sheets
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import re
from typing import List, Dict, Optional
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openpyxl import load_workbook
import os

# Try to import curl_cffi for better anti-bot handling
try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False


class EventScraper:
    """Main class for scraping and managing event data"""
    
    CITIES = {
        'mumbai': 'mumbai',
        'delhi': 'ncr',
        'bangalore': 'bengaluru',
        'hyderabad': 'hyderabad',
        'pune': 'pune',
        'kolkata': 'kolkata',
        'chennai': 'chennai'
    }
    
    def __init__(self, city: str = 'mumbai', use_sheets: bool = False):
        """
        Initialize scraper
        
        Args:
            city: City to scrape events for
            use_sheets: Whether to use Google Sheets (True) or Excel (False)
        """
        self.city = city.lower()
        self.city_code = self.CITIES.get(self.city, 'mumbai')
        self.use_sheets = use_sheets
        # More complete headers to mimic a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/117.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.google.com/',
            'Connection': 'keep-alive',
            'DNT': '1'
        }

        # Use a session with retries
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

        # cloudscraper will be used as a fallback if available to bypass simple anti-bot checks
        self._cloudscraper_available = False
        try:
            import cloudscraper  # type: ignore
            self._cloudscraper_available = True
        except Exception:
            self._cloudscraper_available = False
        
    def scrape_bookmyshow(self) -> List[Dict]:
        """
        Scrape events from BookMyShow using the actual /explore endpoint
        
        Returns:
            List of event dictionaries
        """
        events = []
        
        # BookMyShow actual URL pattern for events in a city
        url = f"https://in.bookmyshow.com/explore/events-{self.city_code}"
        
        try:
            print(f"Trying {url}...")
            response = self._get(url, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for event links with the pattern /events/event-name/ET00...
            event_links = soup.find_all('a', href=re.compile(r'/events/[^/]+/ET\d+'))
            
            print(f"Found {len(event_links)} event links")
            
            for link in event_links[:30]:  # Limit to 30 events
                try:
                    href = link.get('href', '')
                    if href and href.startswith('/'):
                        href = f"https://in.bookmyshow.com{href}"
                    
                    # Extract event name from href
                    match = re.search(r'/events/([^/]+)/', href)
                    event_name = match.group(1).replace('-', ' ').title() if match else 'Unknown Event'
                    
                    # Try to get more details from the link's parent container
                    parent = link.find_parent(['div', 'article'])
                    date = 'TBD'
                    venue = 'Various Venues'
                    category = 'General'
                    
                    if parent:
                        text = parent.get_text(strip=True)
                        lines = [l.strip() for l in text.splitlines() if l.strip()]
                        
                        # Try to extract date from text (look for patterns like "15 Feb" or dates)
                        for line in lines:
                            if re.search(r"\d{1,2}\s+[A-Za-z]{3,9}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}", line):
                                date = line
                                break
                    
                    event = {
                        'event_name': event_name,
                        'event_date': date,
                        'venue': venue,
                        'city': self.city.capitalize(),
                        'category': category,
                        'url': href,
                        'platform': 'BookMyShow',
                        'status': self._determine_status(date),
                        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'event_id': self._generate_event_id(event_name, date, venue)
                    }
                    
                    events.append(event)
                    time.sleep(0.3)  # Small delay between processing
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"Error scraping BookMyShow: {str(e)}")
            
        return events

    def scrape_bookmyshow_browser(self, max_events: int = 50) -> List[Dict]:
        """
        Fallback scraper that uses a real browser (Playwright) to render JavaScript
        and extract event data. This helps when URL patterns are dynamic and
        server-side routing or JS is required to build links.
        """
        events = []

        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            print("Playwright not installed. Install with 'pip install playwright' and run 'playwright install'.")
            return events

        base_url = f"https://in.bookmyshow.com/{self.city_code}"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=self.headers.get('User-Agent'))
                page = context.new_page()

                # Navigate to the city landing page and wait for event tiles to render
                page.goto(base_url, wait_until='networkidle', timeout=30000)

                # Try to click or navigate to the events section if present
                # Many BookMyShow pages render event sections inside the landing page
                # We'll look for event card selectors and extract data
                selectors = [
                    "div[class*='card']",
                    "article",
                    "a[class*='__event']",
                    "div[class*='EventCard']",
                ]

                found_cards = []
                for sel in selectors:
                    try:
                        cards = page.query_selector_all(sel)
                        if cards:
                            found_cards = cards
                            break
                    except Exception:
                        continue

                for card in found_cards[:max_events]:
                    try:
                        # Extract text content and link
                        text = card.inner_text()
                        link_el = card.query_selector('a[href]')
                        href = link_el.get_attribute('href') if link_el else ''
                        if href and not href.startswith('http'):
                            href = f"https://in.bookmyshow.com{href}"

                        # Heuristics to pick name/date/venue from the text blob
                        lines = [l.strip() for l in text.splitlines() if l.strip()]
                        name = lines[0] if lines else 'Unknown Event'
                        date = 'TBD'
                        venue = 'Various Venues'

                        # Find a line that looks like a date
                        for ln in lines[1:4]:
                            if re.search(r"\d{1,2}\s+[A-Za-z]{3,9}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}", ln):
                                date = ln
                                break

                        for ln in lines[-3:]:
                            if len(ln) < 60 and not re.search(r"\d{1,2}", ln):
                                venue = ln
                                break

                        event = {
                            'event_name': name,
                            'event_date': date,
                            'venue': venue,
                            'city': self.city.capitalize(),
                            'category': 'General',
                            'url': href or base_url,
                            'platform': 'BookMyShow',
                            'status': self._determine_status(date),
                            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'event_id': self._generate_event_id(name, date, venue)
                        }

                        events.append(event)
                    except Exception:
                        continue

                try:
                    context.close()
                    browser.close()
                except Exception:
                    pass

        except Exception as e:
            print(f"Browser scraping failed: {str(e)}")

        return events

    def scrape_bookmyshow_selenium(self, max_events: int = 50) -> List[Dict]:
        """
        Fallback scraper using Selenium WebDriver. This will attempt to use a
        locally installed Chrome/Chromium and the webdriver-manager to obtain
        a compatible driver. Useful when Playwright cannot be installed.
        """
        events = []

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service as ChromeService
            from selenium.webdriver.common.by import By
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
        except Exception:
            print("Selenium or webdriver-manager not installed. Install with 'pip install selenium webdriver-manager'.")
            return events

        base_url = f"https://in.bookmyshow.com/{self.city_code}"

        try:
            options = Options()
            options.headless = True
            options.add_argument(f"--user-agent={self.headers.get('User-Agent')}")
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')

            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(30)
            driver.get(base_url)

            # Allow some time for JS to render
            time.sleep(3)

            selectors = [
                "div[class*='card']",
                "article",
                "a[class*='__event']",
                "div[class*='EventCard']",
            ]

            found_elements = []
            for sel in selectors:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                    if elems:
                        found_elements = elems
                        break
                except Exception:
                    continue

            for el in found_elements[:max_events]:
                try:
                    text = el.text
                    link_el = None
                    try:
                        link_el = el.find_element(By.CSS_SELECTOR, 'a[href]')
                    except Exception:
                        pass

                    href = link_el.get_attribute('href') if link_el else ''
                    if href and not href.startswith('http'):
                        href = f"https://in.bookmyshow.com{href}"

                    lines = [l.strip() for l in text.splitlines() if l.strip()]
                    name = lines[0] if lines else 'Unknown Event'
                    date = 'TBD'
                    venue = 'Various Venues'

                    for ln in lines[1:4]:
                        if re.search(r"\d{1,2}\s+[A-Za-z]{3,9}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}", ln):
                            date = ln
                            break

                    for ln in lines[-3:]:
                        if len(ln) < 60 and not re.search(r"\d{1,2}", ln):
                            venue = ln
                            break

                    event = {
                        'event_name': name,
                        'event_date': date,
                        'venue': venue,
                        'city': self.city.capitalize(),
                        'category': 'General',
                        'url': href or base_url,
                        'platform': 'BookMyShow',
                        'status': self._determine_status(date),
                        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'event_id': self._generate_event_id(name, date, venue)
                    }

                    events.append(event)
                except Exception:
                    continue

            try:
                driver.quit()
            except Exception:
                pass

        except Exception as e:
            print(f"Selenium scraping failed: {str(e)}")

        return events
    
    def _parse_event_card(self, card, category: str, platform: str) -> Optional[Dict]:
        """
        Parse individual event card
        
        Args:
            card: BeautifulSoup element
            category: Event category
            platform: Platform name
            
        Returns:
            Event dictionary or None
        """
        try:
            # Extract event name
            name_elem = card.find(['h2', 'h3', 'a'], class_=re.compile('title|name|heading'))
            event_name = name_elem.get_text(strip=True) if name_elem else None
            
            # Extract date
            date_elem = card.find(['span', 'div', 'time'], class_=re.compile('date|time'))
            event_date = date_elem.get_text(strip=True) if date_elem else 'TBD'
            
            # Extract venue
            venue_elem = card.find(['span', 'div'], class_=re.compile('venue|location|place'))
            venue = venue_elem.get_text(strip=True) if venue_elem else 'Various Venues'
            
            # Extract URL
            link_elem = card.find('a', href=True)
            url = link_elem['href'] if link_elem else ''
            if url and not url.startswith('http'):
                url = f"https://in.bookmyshow.com{url}"
            
            if not event_name:
                return None
            
            # Determine status
            status = self._determine_status(event_date)
            
            return {
                'event_name': event_name,
                'event_date': event_date,
                'venue': venue,
                'city': self.city.capitalize(),
                'category': category.replace('-', ' ').title(),
                'url': url,
                'platform': platform,
                'status': status,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'event_id': self._generate_event_id(event_name, event_date, venue)
            }
            
        except Exception as e:
            print(f"Error parsing event card: {str(e)}")
            return None

    def _get(self, url: str, timeout: int = 10):
        """
        Robust GET with curl_cffi (best anti-bot) then cloudscraper, then requests.
        """
        # Try curl_cffi first (best for anti-bot and CloudFlare)
        if HAS_CURL_CFFI:
            try:
                resp = cffi_requests.get(url, headers=self.headers, timeout=timeout, impersonate="chrome120")
                resp.raise_for_status()
                return resp
            except Exception as e:
                print(f"curl_cffi failed: {e}, trying cloudscraper...")
        
        # Try cloudscraper next
        try:
            if self._cloudscraper_available:
                import cloudscraper  # type: ignore
                scraper = cloudscraper.create_scraper()
                resp = scraper.get(url, headers=self.headers, timeout=timeout)
            else:
                resp = self.session.get(url, timeout=timeout)

            resp.raise_for_status()
            return resp
        except Exception as e:
            # Final attempt: plain requests with session
            try:
                resp = self.session.get(url, timeout=timeout)
                resp.raise_for_status()
                return resp
            except Exception as final_error:
                raise final_error
    
    def _generate_event_id(self, name: str, date: str, venue: str) -> str:
        """Generate unique event ID"""
        unique_string = f"{name}_{date}_{venue}_{self.city}".lower()
        return str(hash(unique_string))[:16]
    
    def _determine_status(self, event_date: str) -> str:
        """
        Determine event status based on date
        
        Args:
            event_date: Event date string
            
        Returns:
            Status: Active, Expired, or Upcoming
        """
        try:
            # Parse various date formats
            today = datetime.now()
            
            # Try different date formats
            date_formats = ['%Y-%m-%d', '%d %b %Y', '%d/%m/%Y', '%b %d, %Y']
            
            for fmt in date_formats:
                try:
                    event_dt = datetime.strptime(event_date, fmt)
                    if event_dt < today:
                        return 'Expired'
                    elif event_dt <= today + timedelta(days=7):
                        return 'Active'
                    else:
                        return 'Upcoming'
                except:
                    continue
            
            # If date parsing fails, default to Active
            return 'Active'
            
        except:
            return 'Active'
    
    def save_to_excel(self, events: List[Dict], filename: str = 'events_data.xlsx'):
        """
        Save events to Excel with deduplication
        
        Args:
            events: List of event dictionaries
            filename: Output filename
        """
        df_new = pd.DataFrame(events)
        
        if df_new.empty:
            print("No events to save")
            return
        
        # Check if file exists
        if os.path.exists(filename):
            # Load existing data
            df_existing = pd.read_excel(filename)
            
            # Merge and deduplicate based on event_id
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            
            # Update existing events or add new ones
            df_combined = df_combined.sort_values('last_updated', ascending=False)
            df_combined = df_combined.drop_duplicates(subset=['event_id'], keep='first')
            
            # Update status for all events
            df_combined['status'] = df_combined['event_date'].apply(self._determine_status)
            
            df_combined.to_excel(filename, index=False)
            print(f"Updated {len(df_combined)} events in {filename}")
        else:
            # Create new file
            df_new.to_excel(filename, index=False)
            print(f"Created {filename} with {len(df_new)} events")
    
    def save_to_google_sheets(self, events: List[Dict], sheet_name: str = 'Pixie Events'):
        """
        Save events to Google Sheets
        
        Args:
            events: List of event dictionaries
            sheet_name: Name of the Google Sheet
        """
        # Note: Requires credentials.json file
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
            client = gspread.authorize(creds)
            
            # Open or create sheet
            try:
                sheet = client.open(sheet_name).sheet1
            except:
                sheet = client.create(sheet_name).sheet1
            
            df_new = pd.DataFrame(events)
            
            # Get existing data
            existing_data = sheet.get_all_records()
            
            if existing_data:
                df_existing = pd.DataFrame(existing_data)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined = df_combined.drop_duplicates(subset=['event_id'], keep='first')
            else:
                df_combined = df_new
            
            # Update status
            df_combined['status'] = df_combined['event_date'].apply(self._determine_status)
            
            # Clear and update sheet
            sheet.clear()
            sheet.update([df_combined.columns.values.tolist()] + df_combined.values.tolist())
            
            print(f"Updated Google Sheet with {len(df_combined)} events")
            
        except Exception as e:
            print(f"Error updating Google Sheets: {str(e)}")
            print("Falling back to Excel...")
            self.save_to_excel(events)



def main():
    """Main execution function"""
    print("=" * 60)
    print("Event Discovery & Tracking Tool for Pixie")
    print("=" * 60)
    
    # Get city from user
    print("\nAvailable cities:")
    cities = ['Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Pune', 'Kolkata', 'Chennai']
    for i, city in enumerate(cities, 1):
        print(f"{i}. {city}")
    
    choice = input("\nSelect city (1-7) or enter city name: ").strip()
    
    if choice.isdigit() and 1 <= int(choice) <= len(cities):
        city = cities[int(choice) - 1]
    else:
        city = choice if choice else 'Mumbai'
    
    print(f"\nScraping events for: {city}")
    
    # Initialize scraper
    scraper = EventScraper(city=city, use_sheets=False)
    
    # Scrape events
    print("\nFetching events from BookMyShow...")
    events = scraper.scrape_bookmyshow()

    # If no events found via requests (404/403 patterns), try a browser-rendered scrape
    if not events:
        print("\nNo events found via HTTP requests; trying browser-rendered scraping...")
        browser_events = scraper.scrape_bookmyshow_browser()
        if browser_events:
            events = browser_events
    
    print(f"\nFound {len(events)} events")
    
    # Create output folder if it doesn't exist
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    # Save to Excel
    filename = os.path.join(output_dir, f"events_{city.lower()}_{datetime.now().strftime('%Y%m%d')}.xlsx")
    scraper.save_to_excel(events, filename)
    
    print(f"\nData saved to: {filename}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
