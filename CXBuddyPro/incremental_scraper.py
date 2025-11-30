"""
Incremental scraper for GXS Help Centre - only scrapes new pages not in existing collection
"""
import requests
from bs4 import BeautifulSoup
import time
import os
import glob
from datetime import datetime
from urllib.parse import urljoin, urlparse
from collections import deque

class IncrementalGXSScraper:
    def __init__(self, output_dir='gxs_help_content'):
        self.base_url = 'https://help.gxs.com.sg/'
        self.output_dir = output_dir
        self.scraped_content = []
        
        # Load already scraped URLs
        self.existing_urls = self._load_existing_urls()
        print(f"✅ Loaded {len(self.existing_urls)} already-scraped URLs")
        
    def _load_existing_urls(self):
        """Load URLs that have already been scraped"""
        existing = set()
        if not os.path.exists(self.output_dir):
            return existing
            
        for file in glob.glob(f'{self.output_dir}/page_*.txt'):
            try:
                with open(file, 'r') as f:
                    lines = f.readlines()
                    url_line = [l for l in lines if l.startswith('URL:')]
                    if url_line:
                        url = url_line[0].replace('URL:', '').strip()
                        existing.add(url)
            except Exception as e:
                print(f"Warning: Could not read {file}: {e}")
        
        return existing
    
    def is_valid_url(self, url):
        """Check if URL is valid GXS help centre URL"""
        parsed = urlparse(url)
        return (parsed.netloc == 'help.gxs.com.sg' and 
                not url.endswith(('.pdf', '.jpg', '.png', '.gif')))
    
    def is_likely_answer_page(self, url, soup):
        """Detect if this is a FAQ answer page"""
        # Check if URL or title contains a question mark
        if '?' in url or '%3F' in url:
            return True
        
        title = soup.find('title')
        if title and '?' in title.get_text():
            return True
        
        # Check if it's a specific article (not a category/section page)
        if any(keyword in url for keyword in ['/articles/', '/hc/en-sg/articles/']):
            return True
            
        return False
    
    def scrape_page(self, url):
        """Scrape a single page"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else 'No Title'
            
            # Extract main content
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if main_content:
                # Remove navigation, footer, scripts
                for tag in main_content.find_all(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()
                
                text = main_content.get_text(separator='\n', strip=True)
                
                # Clean up excessive whitespace
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                content = '\n'.join(lines)
                
                word_count = len(content.split())
                
                # Get all links for crawling
                links = []
                for link in soup.find_all('a', href=True):
                    abs_url = urljoin(url, link['href'])
                    if self.is_valid_url(abs_url):
                        links.append(abs_url)
                
                # Determine if this is a priority (answer) page
                is_answer = self.is_likely_answer_page(url, soup)
                
                # Split links into priority and regular
                priority_links = [l for l in links if self.is_likely_answer_page(l, soup)]
                regular_links = [l for l in links if l not in priority_links]
                
                return {
                    'url': url,
                    'title': title_text,
                    'content': content,
                    'word_count': word_count,
                    'is_answer_page': is_answer,
                    'priority_links': list(set(priority_links)),
                    'regular_links': list(set(regular_links))
                }
            
        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")
            return None
    
    def save_page(self, page_data, page_num):
        """Save page content to file"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Sanitize filename
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' 
                           for c in page_data['title'])
        safe_title = safe_title[:100]  # Limit length
        
        filename = f"{self.output_dir}/page_{page_num:03d}_{safe_title}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Title: {page_data['title']}\n")
            f.write(f"URL: {page_data['url']}\n")
            f.write(f"Scraped: {datetime.now().isoformat()}\n")
            f.write(f"Word Count: {page_data['word_count']}\n")
            f.write(f"Is FAQ Answer: {page_data['is_answer_page']}\n")
            f.write("\n" + "="*80 + "\n\n")
            f.write(page_data['content'])
    
    def crawl_new_sections(self, seed_urls, max_new_pages=200, delay=2.0):
        """
        Crawl starting from seed URLs, only scraping pages not in existing collection
        Uses priority queue to prioritize FAQ answer pages
        """
        print(f"\n🚀 Starting incremental crawl from {len(seed_urls)} seed URLs...")
        print(f"   Will scrape up to {max_new_pages} NEW pages")
        print(f"   Delay: {delay}s between requests\n")
        
        # Two queues: priority for answer pages, regular for others
        priority_queue = deque(seed_urls)
        regular_queue = deque()
        visited = set(self.existing_urls)  # Start with existing URLs
        new_pages_scraped = 0
        
        # Find starting page number
        existing_files = glob.glob(f'{self.output_dir}/page_*.txt')
        if existing_files:
            # Extract numbers from filenames like "page_123_title.txt"
            nums = []
            for f in existing_files:
                basename = os.path.basename(f)
                parts = basename.split('_')
                if len(parts) >= 2 and parts[1].isdigit():
                    nums.append(int(parts[1]))
            
            if nums:
                page_counter = max(nums) + 1
            else:
                page_counter = 1
        else:
            page_counter = 1
        
        while (priority_queue or regular_queue) and new_pages_scraped < max_new_pages:
            # Prioritize answer pages
            if priority_queue:
                current_url = priority_queue.popleft()
                queue_type = "PRIORITY"
            else:
                current_url = regular_queue.popleft()
                queue_type = "REGULAR"
            
            if current_url in visited:
                continue
            
            visited.add(current_url)
            
            # Check if already scraped
            if current_url in self.existing_urls:
                print(f"⏭️  Skipping (already scraped): {current_url[:80]}...")
                continue
            
            print(f"🔍 [{new_pages_scraped+1}/{max_new_pages}] ({queue_type}) Scraping: {current_url[:80]}...")
            
            page_data = self.scrape_page(current_url)
            
            if page_data and page_data['word_count'] >= 15:
                self.save_page(page_data, page_counter)
                self.scraped_content.append(page_data)
                page_counter += 1
                new_pages_scraped += 1
                
                marker = "📄 FAQ" if page_data['is_answer_page'] else "📁 NAV"
                print(f"   ✅ {marker} | {page_data['word_count']} words | {page_data['title'][:60]}")
                
                # Add new links to appropriate queues
                for link in page_data['priority_links']:
                    if link not in visited:
                        priority_queue.append(link)
                
                for link in page_data['regular_links']:
                    if link not in visited:
                        regular_queue.append(link)
            
            time.sleep(delay)
        
        print(f"\n✅ Incremental crawl complete!")
        print(f"   📊 NEW pages scraped: {new_pages_scraped}")
        print(f"   📊 TOTAL pages now: {len(self.existing_urls) + new_pages_scraped}")
        
        # Save metadata
        self._save_metadata(new_pages_scraped)
    
    def _save_metadata(self, new_pages):
        """Save crawl metadata"""
        answer_pages = sum(1 for p in self.scraped_content if p.get('is_answer_page', False))
        regular_pages = len(self.scraped_content) - answer_pages
        total_words = sum(p.get('word_count', 0) for p in self.scraped_content)
        
        metadata = {
            'incremental_scrape_date': datetime.now().isoformat(),
            'new_pages_scraped': new_pages,
            'new_faq_answer_pages': answer_pages,
            'new_regular_pages': regular_pages,
            'new_total_words': total_words,
            'total_pages_in_collection': len(self.existing_urls) + new_pages
        }
        
        import json
        with open(f'{self.output_dir}/incremental_metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n📊 Incremental Scrape Statistics:")
        print(f"   - New FAQ answer pages: {answer_pages}")
        print(f"   - New regular pages: {regular_pages}")
        print(f"   - New words: {total_words:,}")


if __name__ == '__main__':
    # Seed URLs for ALL missing sections (we only have Emergencies, Savings, FlexiLoan)
    seed_urls = [
        'https://help.gxs.com.sg/GXS_Debit_Card',
        'https://help.gxs.com.sg/GXS_FlexiCard',
        'https://help.gxs.com.sg/Odyssey',
        'https://help.gxs.com.sg/Payments',
        'https://help.gxs.com.sg/Introductions',
        'https://help.gxs.com.sg/Promotions',
        'https://help.gxs.com.sg/Grab_and_Singtel_Experiences',
        'https://help.gxs.com.sg/GXS_Biz_Account',
        'https://help.gxs.com.sg/GXS_FlexiLoan_Biz',
        'https://help.gxs.com.sg/GXS_Invest',
    ]
    
    print(f"📋 Will scrape {len(seed_urls)} missing sections:")
    for i, url in enumerate(seed_urls, 1):
        section = url.split('/')[-1].replace('_', ' ')
        print(f"  {i:2d}. {section}")
    print()
    
    scraper = IncrementalGXSScraper()
    scraper.crawl_new_sections(
        seed_urls=seed_urls,
        max_new_pages=300,  # Scrape up to 300 new pages (10 sections ~30 pages each)
        delay=2.0
    )
    
    print("\n🎉 Incremental scrape complete!")
    print("   Next step: Re-index vector store with new content")
