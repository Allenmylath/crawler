# File: crawler/spiders/text_content_spider.py

import scrapy
import json
import os
from urllib.parse import urlparse
import re
from datetime import datetime

class TextContentSpider(scrapy.Spider):
    name = 'text_content'
    
    # Document extensions to skip
    document_extensions = {
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'txt', 'csv', 'zip', 'rar', 'tar', 'gz'
    }
    
    def __init__(self, urls_file='urls.json', output_file='content.json'):
        self.urls_file = urls_file
        self.output_file = output_file
        self.results = []
        
    def start_requests(self):
        """Read URLs from JSON file and create requests"""
        try:
            with open(self.urls_file, 'r', encoding='utf-8') as f:
                urls_data = json.load(f)
            
            # Handle different JSON structures
            if isinstance(urls_data, list):
                # If it's a list of URL objects
                urls = [item.get('url', item) if isinstance(item, dict) else item for item in urls_data]
            elif isinstance(urls_data, dict):
                # If it's a single object or has URLs in a specific key
                urls = urls_data.get('urls', [urls_data.get('url', '')])
            else:
                urls = []
            
            for url in urls:
                if url and self.should_process_url(url):
                    yield scrapy.Request(
                        url=url,
                        callback=self.parse,
                        errback=self.handle_error,
                        meta={'original_url': url}
                    )
                elif url:
                    # Log skipped URLs (document files)
                    self.results.append({
                        'url': url,
                        'title': None,
                        'text_content': None,
                        'content_type': 'document (skipped)',
                        'error': 'skipped_document',
                        'status_code': None,
                        'extracted_at': datetime.now().isoformat()
                    })
                    
        except FileNotFoundError:
            self.logger.error(f"URLs file {self.urls_file} not found")
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON in {self.urls_file}")
    
    def should_process_url(self, url):
        """Check if URL should be processed (not a document)"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        if '.' in path:
            extension = path.split('.')[-1].split('?')[0]  # Remove query params
            if extension in self.document_extensions:
                return False
        
        return True
    
    def parse(self, response):
        """Extract text content from HTML pages"""
        url = response.meta.get('original_url', response.url)
        
        # Check content type
        content_type = response.headers.get('Content-Type', b'').decode('utf-8').lower()
        
        # Only process HTML content
        if 'text/html' not in content_type and 'application/xhtml' not in content_type:
            result = {
                'url': url,
                'title': None,
                'text_content': None,
                'content_type': content_type,
                'error': 'not_html_content',
                'status_code': response.status,
                'extracted_at': datetime.now().isoformat()
            }
        else:
            # Extract title
            title = response.css('title::text').get()
            if title:
                title = title.strip()
            
            # Extract all visible text
            # Remove script and style elements first
            text_content = self.extract_visible_text(response)
            
            result = {
                'url': url,
                'title': title,
                'text_content': text_content,
                'content_type': content_type,
                'error': 'none',
                'status_code': response.status,
                'extracted_at': datetime.now().isoformat()
            }
        
        self.results.append(result)
        return result
    
    def extract_visible_text(self, response):
        """Extract all visible text from the page"""
        # Remove script and style elements
        for script in response.css('script'):
            script.remove()
        for style in response.css('style'):
            style.remove()
        
        # Get all text content
        text_elements = response.css('*::text').getall()
        
        # Clean and filter text
        cleaned_text = []
        for text in text_elements:
            text = text.strip()
            if text and not text.isspace():
                cleaned_text.append(text)
        
        # Join with spaces and clean up extra whitespace
        full_text = ' '.join(cleaned_text)
        # Replace multiple spaces/newlines with single space
        full_text = re.sub(r'\s+', ' ', full_text)
        
        return full_text.strip()
    
    def handle_error(self, failure):
        """Handle request errors"""
        url = failure.request.meta.get('original_url', failure.request.url)
        
        # Extract error information
        if hasattr(failure.value, 'response') and failure.value.response:
            status_code = failure.value.response.status
            error = str(status_code)
        else:
            status_code = None
            error = str(failure.value)
        
        result = {
            'url': url,
            'title': None,
            'text_content': None,
            'content_type': None,
            'error': error,
            'status_code': status_code,
            'extracted_at': datetime.now().isoformat()
        }
        
        self.results.append(result)
        self.logger.error(f"Error processing {url}: {error}")
        
        return result
    
    def closed(self, reason):
        """Save results to JSON file when spider closes"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved {len(self.results)} results to {self.output_file}")
            
            # Print summary
            successful = len([r for r in self.results if r['error'] == 'none'])
            errors = len(self.results) - successful
            self.logger.info(f"Summary: {successful} successful, {errors} errors/skipped")
            
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")
