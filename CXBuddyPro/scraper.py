"""
GXS Help Center Web Scraper
Crawls https://help.gxs.com.sg/ and extracts content for vector store embedding.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import json
import os
from datetime import datetime
from typing import Set, List, Dict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GXSHelpScraper:
    def __init__(self, base_url: str = "https://help.gxs.com.sg/"):
        self.base_url = base_url
        self.visited_urls: Set[str] = set()
        self.scraped_content: List[Dict] = []
        self.output_dir = "gxs_help_content"
        self.min_words = 20  # Minimum words to consider valid content
        self.prioritize_question_pages = True  # Follow FAQ question links first
        
    def is_likely_answer_page(self, url: str, soup: BeautifulSoup) -> bool:
        """
        Detect if a page is likely an FAQ answer page (not just an index).
        Answer pages typically have question marks in the URL or title.
        """
        # Check URL for question indicators
        url_lower = url.lower()
        has_question_in_url = '%3f' in url_lower or '?' in url_lower
        
        # Check title for question
        title = soup.find('title')
        title_text = title.get_text() if title else ""
        has_question_in_title = '?' in title_text
        
        # Check for common FAQ patterns
        is_answer_page = has_question_in_url or has_question_in_title
        
        return is_answer_page
    
    def is_valid_url(self, url: str) -> bool:
        """Check if URL belongs to GXS help center"""
        parsed = urlparse(url)
        return parsed.netloc == urlparse(self.base_url).netloc
    
    def extract_text_content(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract meaningful text content from a help page"""
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get page title
        title = soup.find('title')
        title_text = title.get_text().strip() if title else "Untitled"
        
        # Get main content (adjust selectors based on actual GXS site structure)
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
        
        if main_content:
            # Get all text
            text = main_content.get_text(separator='\n', strip=True)
        else:
            # Fallback to body
            text = soup.get_text(separator='\n', strip=True)
        
        # Clean up excessive whitespace
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        cleaned_text = '\n'.join(lines)
        
        return {
            'url': url,
            'title': title_text,
            'content': cleaned_text,
            'scraped_at': datetime.now().isoformat(),
            'word_count': len(cleaned_text.split())
        }
    
    def get_links(self, soup: BeautifulSoup, current_url: str) -> tuple[List[str], List[str]]:
        """
        Extract all valid links from the page.
        Returns: (priority_links, regular_links)
        Priority links are those likely to be FAQ answer pages.
        """
        priority_links = []
        regular_links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(current_url, href)
            
            # Only include GXS help center URLs
            if self.is_valid_url(full_url):
                # Remove fragments but keep query params (they often contain question IDs)
                if '#' in full_url:
                    full_url = full_url.split('#')[0]
                
                # Prioritize links that look like FAQ questions
                link_text = link.get_text().strip()
                is_likely_faq = '?' in link_text or '?' in href or '%3F' in href
                
                if is_likely_faq:
                    priority_links.append(full_url)
                else:
                    regular_links.append(full_url)
        
        # Remove duplicates while preserving order
        priority_links = list(dict.fromkeys(priority_links))
        regular_links = list(dict.fromkeys(regular_links))
        
        return priority_links, regular_links
    
    def scrape_page(self, url: str) -> tuple[bool, List[str], List[str]]:
        """
        Scrape a single page.
        Returns: (success, priority_links, regular_links)
        """
        try:
            logger.info(f"Scraping: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract content
            page_data = self.extract_text_content(soup, url)
            
            # Check if this is an answer page
            is_answer = self.is_likely_answer_page(url, soup)
            
            # Only save if we got meaningful content
            # Be more lenient with answer pages (they're what we want!)
            min_threshold = self.min_words if not is_answer else 15
            
            if page_data['word_count'] > min_threshold:
                page_data['is_answer_page'] = is_answer
                self.scraped_content.append(page_data)
                page_type = "❓ FAQ ANSWER" if is_answer else "📄 PAGE"
                logger.info(f"✓ {page_type}: Extracted {page_data['word_count']} words from: {page_data['title']}")
            else:
                logger.warning(f"⚠ Skipped (too short): {page_data['title']} ({page_data['word_count']} words)")
            
            # Get links for crawling (separated by priority)
            priority_links, regular_links = self.get_links(soup, url)
            
            return True, priority_links, regular_links
            
        except Exception as e:
            logger.error(f"✗ Failed to scrape {url}: {str(e)}")
            return False, [], []
    
    def crawl(self, max_pages: int = 200, delay: float = 2.0):
        """
        Crawl the help center starting from base_url.
        Uses priority queue to visit FAQ answer pages first.
        """
        # Two queues: priority (FAQ answers) and regular
        priority_queue = [self.base_url]
        regular_queue = []
        
        pages_scraped = 0
        
        while pages_scraped < max_pages:
            # Prefer priority queue (FAQ answers)
            if priority_queue:
                url = priority_queue.pop(0)
            elif regular_queue:
                url = regular_queue.pop(0)
            else:
                # No more URLs to visit
                break
            
            # Skip if already visited
            if url in self.visited_urls:
                continue
            
            self.visited_urls.add(url)
            success, new_priority_links, new_regular_links = self.scrape_page(url)
            
            if success:
                pages_scraped += 1
                
                # Add new links to appropriate queues
                for link in new_priority_links:
                    if link not in self.visited_urls and link not in priority_queue:
                        priority_queue.append(link)
                
                for link in new_regular_links:
                    if link not in self.visited_urls and link not in regular_queue:
                        regular_queue.append(link)
            
            # Be respectful - add delay between requests
            time.sleep(delay)
            
        logger.info(f"\n{'='*60}")
        logger.info(f"Crawling complete!")
        logger.info(f"Pages visited: {len(self.visited_urls)}")
        logger.info(f"Content extracted: {len(self.scraped_content)} pages")
        
        # Count answer pages vs regular pages
        answer_pages = sum(1 for item in self.scraped_content if item.get('is_answer_page', False))
        logger.info(f"  - FAQ Answer pages: {answer_pages}")
        logger.info(f"  - Regular pages: {len(self.scraped_content) - answer_pages}")
        logger.info(f"{'='*60}\n")
    
    def save_to_files(self):
        """Save scraped content to individual text files for vector store"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Count answer pages
        answer_pages = sum(1 for item in self.scraped_content if item.get('is_answer_page', False))
        
        # Save metadata
        metadata = {
            'scraped_at': datetime.now().isoformat(),
            'base_url': self.base_url,
            'pages_scraped': len(self.scraped_content),
            'faq_answer_pages': answer_pages,
            'regular_pages': len(self.scraped_content) - answer_pages,
            'total_words': sum(item['word_count'] for item in self.scraped_content),
            'avg_words_per_page': round(sum(item['word_count'] for item in self.scraped_content) / len(self.scraped_content)) if self.scraped_content else 0
        }
        
        with open(f"{self.output_dir}/metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        # Save each page as a separate text file
        for idx, item in enumerate(self.scraped_content, 1):
            # Create safe filename from title
            safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in item['title'])
            safe_title = safe_title[:100]  # Limit length
            
            filename = f"{self.output_dir}/page_{idx:03d}_{safe_title}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"Title: {item['title']}\n")
                f.write(f"URL: {item['url']}\n")
                f.write(f"Scraped: {item['scraped_at']}\n")
                f.write(f"\n{'='*80}\n\n")
                f.write(item['content'])
        
        # Save consolidated file for vector store
        with open(f"{self.output_dir}/gxs_help_consolidated.txt", 'w', encoding='utf-8') as f:
            for item in self.scraped_content:
                f.write(f"\n\n{'='*100}\n")
                f.write(f"SOURCE: {item['url']}\n")
                f.write(f"TITLE: {item['title']}\n")
                f.write(f"{'='*100}\n\n")
                f.write(item['content'])
        
        logger.info(f"✓ Saved {len(self.scraped_content)} files to {self.output_dir}/")
        logger.info(f"✓ Created consolidated file: gxs_help_consolidated.txt")
        logger.info(f"✓ Metadata saved to metadata.json")


def main():
    """Run the scraper"""
    scraper = GXSHelpScraper(base_url="https://help.gxs.com.sg/")
    
    print("\n" + "="*80)
    print("GXS Help Center Scraper".center(80))
    print("="*80 + "\n")
    
    # Crawl with conservative settings for testing
    # max_pages: limit to avoid overwhelming on first run
    # delay: be respectful to the server
    scraper.crawl(max_pages=200, delay=2.0)
    
    # Save results
    scraper.save_to_files()
    
    print("\n" + "="*80)
    print("Scraping Complete!".center(80))
    print("="*80 + "\n")
    print(f"Next steps:")
    print(f"1. Review the content in '{scraper.output_dir}/' directory")
    print(f"2. Upload 'gxs_help_consolidated.txt' to Azure OpenAI for embeddings")
    print(f"3. Update the vector_store_id in config.json")
    print("\n")


if __name__ == "__main__":
    main()
