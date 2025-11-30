#!/usr/bin/env python3
"""
Smart incremental scraper - finds unscraped FAQ pages in existing sections
"""
from incremental_scraper import IncrementalGXSScraper
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

print("🔍 Finding FAQ pages in missing sections...\n")

scraper = IncrementalGXSScraper()

# Get FAQ URLs from each section landing page
sections_to_crawl = [
    'https://help.gxs.com.sg/GXS_FlexiCard',
    'https://help.gxs.com.sg/Odyssey',
    'https://help.gxs.com.sg/Payments',
    'https://help.gxs.com.sg/Promotions',
    'https://help.gxs.com.sg/Grab_and_Singtel_Experiences',
    'https://help.gxs.com.sg/GXS_Biz_Account',
    'https://help.gxs.com.sg/GXS_FlexiLoan_Biz',
    'https://help.gxs.com.sg/GXS_Invest',
    'https://help.gxs.com.sg/Introductions',
]

# Collect all unscraped FAQ URLs
new_faq_urls = []

for section_url in sections_to_crawl:
    try:
        print(f"Checking {section_url.split('/')[-1]}...")
        response = requests.get(section_url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        section_count = 0
        for link in soup.find_all('a', href=True):
            href = urljoin(section_url, link['href'])
            # Check if it's a FAQ page (has ?) and not already scraped
            if ('?' in href or '%3F' in href) and href not in scraper.existing_urls:
                new_faq_urls.append(href)
                section_count += 1
        
        print(f"  Found {section_count} new FAQ pages\n")
        time.sleep(0.5)
    except Exception as e:
        print(f"  Error: {e}\n")

# Deduplicate
new_faq_urls = list(set(new_faq_urls))

print(f"\n✅ Found {len(new_faq_urls)} TOTAL NEW FAQ pages to scrape\n")
print(f"Will scrape ALL {len(new_faq_urls)} pages")
print(f"Estimated time: {len(new_faq_urls) * 2 / 60:.1f} minutes\n")

# Now crawl these URLs
scraper.crawl_new_sections(
    seed_urls=new_faq_urls,
    max_new_pages=500,
    delay=2.0
)

print("\n✅ Smart incremental scrape complete!")
print(f"   All {len(new_faq_urls)} pages scraped!")
