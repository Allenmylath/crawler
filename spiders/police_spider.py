# File: kerala_police_crawler/spiders/police_spider.py

import scrapy
from urllib.parse import urljoin, urlparse
import re

class PoliceSpider(scrapy.Spider):
    name = 'kerala_police'
    allowed_domains = ['keralapolice.gov.in']
    start_urls = ['https://keralapolice.gov.in/']
    
    # File extensions to exclude (images, scripts, styles)
    excluded_extensions = {
        # Images
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico',
        # Scripts and styles  
        'js', 'css',
        # Other assets we might want to skip
        'woff', 'woff2', 'ttf', 'eot', 'otf'
    }
    
    # File extensions to specifically include (documents)
    document_extensions = {
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'txt', 'csv', 'xml', 'json', 'zip', 'rar'
    }
    
    def __init__(self):
        self.found_urls = set()
        
    def parse(self, response):
        # Add current URL to found URLs
        current_url = response.url
        self.found_urls.add(current_url)
        
        # Yield current URL
        yield {
            'url': current_url,
            'status_code': response.status,
            'content_type': response.headers.get('Content-Type', b'').decode('utf-8'),
            'title': response.css('title::text').get(),
            'depth': response.meta.get('depth', 0)
        }
        
        # Extract all links from <a> tags
        links = response.css('a::attr(href)').getall()
        
        for link in links:
            if link:
                # Convert relative URLs to absolute
                absolute_url = urljoin(response.url, link.strip())
                
                # Clean URL (remove fragments and some query params)
                cleaned_url = self.clean_url(absolute_url)
                
                # Check if URL is valid and should be followed
                if self.should_follow_url(cleaned_url):
                    if cleaned_url not in self.found_urls:
                        # Check if it's a document or a page to crawl
                        if self.is_document_url(cleaned_url):
                            # For documents, just yield the URL info without following
                            self.found_urls.add(cleaned_url)
                            yield {
                                'url': cleaned_url,
                                'status_code': 'document',
                                'content_type': 'document',
                                'title': 'Document Link',
                                'depth': response.meta.get('depth', 0) + 1
                            }
                        else:
                            # For regular pages, follow the link
                            yield response.follow(
                                cleaned_url, 
                                callback=self.parse,
                                dont_filter=False
                            )
    
    def clean_url(self, url):
        """Clean URL by removing fragments and unnecessary query parameters"""
        # Remove fragment (everything after #)
        if '#' in url:
            url = url.split('#')[0]
        
        # Remove common tracking parameters
        parsed = urlparse(url)
        # For now, keep all query parameters, but you can filter specific ones if needed
        
        return url.rstrip('/')
    
    def should_follow_url(self, url):
        """Check if URL should be followed based on domain and file type"""
        parsed = urlparse(url)
        
        # Must be in allowed domain
        if parsed.netloc not in self.allowed_domains:
            return False
        
        # Get file extension
        path = parsed.path.lower()
        if '.' in path:
            extension = path.split('.')[-1].split('?')[0]  # Remove query params
            
            # Skip excluded extensions
            if extension in self.excluded_extensions:
                return False
        
        return True
    
    def is_document_url(self, url):
        """Check if URL points to a document file"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        if '.' in path:
            extension = path.split('.')[-1].split('?')[0]  # Remove query params
            return extension in self.document_extensions
        
        return False


