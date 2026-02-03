#!/usr/bin/env python
"""
Main Entry Point for Event Discovery & Tracking Tool
Runs the interactive scraper with option to enable scheduling
"""

import sys
import os
import time
from datetime import datetime

# Add src folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from event_scraper import EventScraper


def print_header():
    """Print project header"""
    print("\n" + "=" * 70)
    print(" " * 15 + "EVENT DISCOVERY & TRACKING TOOL")
    print(" " * 20 + "For Pixie Events")
    print("=" * 70 + "\n")


def run_interactive():
    """Run interactive scraper"""
    print_header()
    
    print("Available cities:")
    cities = ['Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Pune', 'Kolkata', 'Chennai']
    for i, city in enumerate(cities, 1):
        print(f"  {i}. {city}")
    
    choice = input("\nSelect city (1-7) or enter city name: ").strip()
    
    if choice.isdigit() and 1 <= int(choice) <= len(cities):
        city = cities[int(choice) - 1]
    else:
        city = choice if choice else 'Mumbai'
    
    print(f"\n{'='*70}")
    print(f"Scraping events for: {city}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    # Create scraper and scrape events
    scraper = EventScraper(city=city, use_sheets=False)
    
    print("Fetching events from BookMyShow...")
    events = scraper.scrape_bookmyshow()
    
    # Fallback to browser scraping if no events found
    if not events:
        print("\nNo events found via HTTP requests; trying browser-rendered scraping...")
        browser_events = scraper.scrape_bookmyshow_browser()
        if browser_events:
            events = browser_events
    
    print(f"\nTotal events found: {len(events)}")
    
    # Create output folder if needed
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    # Save to Excel
    filename = os.path.join(output_dir, f"events_{city.lower()}_{datetime.now().strftime('%Y%m%d')}.xlsx")
    scraper.save_to_excel(events, filename)
    
    print(f"\n{'='*70}")
    print(f"✅ Data saved to: {filename}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")


def run_all_cities():
    """Scrape all cities in sequence"""
    print_header()
    
    cities_map = {
        'mumbai': 'Mumbai',
        'delhi': 'Delhi',
        'bangalore': 'Bangalore',
        'hyderabad': 'Hyderabad',
        'pune': 'Pune',
        'kolkata': 'Kolkata',
        'chennai': 'Chennai'
    }
    
    print(f"Scraping all cities: {', '.join(cities_map.values())}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")
    
    total_events = 0
    
    for city_code, city_name in cities_map.items():
        try:
            print(f"\n[{city_name}] Starting scrape...")
            start = time.time()
            
            scraper = EventScraper(city=city_code, use_sheets=False)
            events = scraper.scrape_bookmyshow()
            
            if not events:
                events = scraper.scrape_bookmyshow_browser()
            
            # Create output folder
            output_dir = os.path.join(os.path.dirname(__file__), 'output')
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            filename = os.path.join(output_dir, f"events_{city_code}_{datetime.now().strftime('%Y%m%d')}.xlsx")
            scraper.save_to_excel(events, filename)
            
            elapsed = time.time() - start
            total_events += len(events)
            
            print(f"[{city_name}] ✅ Completed in {elapsed:.1f}s - Found {len(events)} events")
            
            time.sleep(1)  # Brief pause between cities
            
        except Exception as e:
            print(f"[{city_name}] ❌ Error: {str(e)}")
    
    print(f"\n{'='*70}")
    print(f"✅ All cities processed!")
    print(f"Total events collected: {total_events}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")


def show_menu():
    """Show main menu"""
    print_header()
    
    print("Options:")
    print("  1. Scrape single city (interactive)")
    print("  2. Scrape all cities")
    print("  3. Schedule automated scraping")
    print("  4. View help/documentation")
    print("  5. Exit")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == '1':
        run_interactive()
    elif choice == '2':
        confirm = input("\nThis will scrape all 7 cities. Continue? (y/n): ").strip().lower()
        if confirm == 'y':
            run_all_cities()
    elif choice == '3':
        print("\n" + "=" * 70)
        print("To run the scheduler, use:")
        print("  python scripts/scheduler.py")
        print("\nThis will run automated scraping at:")
        print("  • Daily at 9:00 AM for Mumbai, Delhi, Bangalore")
        print("  • Every 6 hours for Mumbai")
        print("=" * 70 + "\n")
    elif choice == '4':
        show_help()
    elif choice == '5':
        print("\nExiting... Goodbye! 👋\n")
        sys.exit(0)
    else:
        print("\n❌ Invalid option. Please try again.\n")


def show_help():
    """Show help documentation"""
    print("\n" + "=" * 70)
    print("HELP & DOCUMENTATION")
    print("=" * 70)
    
    help_text = """
PROJECT STRUCTURE:
  src/event_scraper.py      - Main scraper module
  scripts/scheduler.py      - Automated scheduling
  output/                   - Generated Excel files
  ARCHITECTURE.md           - Detailed documentation
  
QUICK START:
  1. Interactive: python main.py
  2. All cities: Select option 2 from menu
  3. Automated:  python scripts/scheduler.py
  
FEATURES:
  • Scrapes BookMyShow for events
  • 7 supported cities (Mumbai, Delhi, Bangalore, Hyderabad, Pune, Kolkata, Chennai)
  • Automatic deduplication
  • Real-time status tracking (Active/Upcoming/Expired)
  • Excel export with automatic merging
  
REQUIREMENTS:
  • Python 3.8+
  • See requirements.txt for all dependencies
  
TROUBLESHOOTING:
  • Check ARCHITECTURE.md section 9 for common issues
  • Ensure Chrome/Chromium is installed for fallback scrapers
  • Verify internet connection to BookMyShow
  
For more details, see: ARCHITECTURE.md
"""
    
    print(help_text)
    input("Press Enter to continue...")


def main():
    """Main entry point"""
    try:
        show_menu()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
