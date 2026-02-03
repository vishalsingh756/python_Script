"""
Scheduler for automated event scraping
Runs the event scraper at regular intervals
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging
import sys
import os

# Add src folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from event_scraper import EventScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('event_scraper.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def scrape_job(city: str = 'mumbai'):
    """
    Job function to scrape events
    
    Args:
        city: City to scrape
    """
    try:
        logger.info(f"Starting scrape job for {city}")
        
        scraper = EventScraper(city=city, use_sheets=False)
        events = scraper.scrape_bookmyshow()
        
        logger.info(f"Found {len(events)} events")
        
        # Create output folder if needed
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Save to Excel
        filename = os.path.join(output_dir, f"events_{city}_{datetime.now().strftime('%Y%m%d')}.xlsx")
        scraper.save_to_excel(events, filename)
        
        logger.info(f"Data saved to {filename}")
        logger.info("Scrape job completed successfully")
        
    except Exception as e:
        logger.error(f"Error in scrape job: {str(e)}", exc_info=True)


def main():
    """Main scheduler function"""
    scheduler = BlockingScheduler()
    
    # Schedule configurations
    cities = ['mumbai', 'delhi', 'bangalore']
    
    # Run daily at 9 AM for each city
    for city in cities:
        scheduler.add_job(
            scrape_job,
            CronTrigger(hour=9, minute=0),
            args=[city],
            id=f'scrape_{city}',
            name=f'Scrape events for {city}',
            replace_existing=True
        )
        logger.info(f"Scheduled daily scrape for {city} at 9:00 AM")
    
    # Also run every 6 hours for Mumbai (high-volume city)
    scheduler.add_job(
        scrape_job,
        CronTrigger(hour='*/6'),
        args=['mumbai'],
        id='scrape_mumbai_frequent',
        name='Frequent scrape for Mumbai',
        replace_existing=True
    )
    logger.info("Scheduled 6-hourly scrape for Mumbai")
    
    logger.info("Scheduler started. Press Ctrl+C to exit.")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
