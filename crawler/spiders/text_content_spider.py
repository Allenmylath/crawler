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
    
    # CSS selectors for elements to exclude (headers, footers, navigation, etc.)
    excluded_selectors = [
        # Semantic HTML5 tags
        'header',
        'footer', 
        'nav',
        'aside',
        
        # Common class patterns
        '.header',
        '.footer',
        '.navigation',
        '.nav',
        '.navbar',
        '.sidebar',
        '.breadcrumb',
        '.breadcrumbs',
        '.menu',
        '.main-menu',
        '.top-menu',
        '.bottom-menu',
        '.copyright',
        '.social',
        '.social-media',
        '.social-links',
        
        # Common ID patterns
        '#header',
        '#footer',
        '#navigation', 
        '#nav',
        '#navbar',
        '#sidebar',
        '#menu',
        '#top-menu',
        '#bottom-menu',
        
        # Skip/advertisement areas
        '.skip',
        '.skip-link',
        '.skip-content',
        '.advertisement',
        '.ads',
        '.ad-banner',
        '.banner',
        '.promo',
        '.popup',
        '.modal',
        '.overlay',
        
        # Cookie/privacy notices
        '.cookie-notice',
        '.cookie-banner',
        '.privacy-notice',
        '.gdpr-notice',
        
        # Search and login areas (often in headers)
        '.search',
        '.search-form',
        '.search-box',
        '.login',
        '.login-form',
        '.user-menu',
        
        # Language/accessibility controls
        '.language-selector',
        '.lang-selector',
        '.accessibility-controls',
        '.text-size-controls',
        
        # Social sharing (often in footers)
        '.share',
        '.sharing',
        '.social-share',
        
        # Back to top links
        '.back-to-top',
        '.scroll-to-top',
        
        # Print/email controls
        '.print',
        '.email',
        '.print-page',
        '.email-page'
    ]
    
    def __init__(self, urls_file='urls.json', output_file='content.json', **kwargs):
        super().__init__(**kwargs)
        self.urls_file = urls_file
        self.output_file = output_file
        self.results = []
        
        # Allow custom excluded selectors via command line
        if 'excluded_selectors' in kwargs:
            custom_selectors = kwargs['excluded_selectors'].split(',')
            self.excluded_selectors.extend([s.strip() for s in custom_selectors])
        
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
                        'word_count': 0,
                        'excluded_elements_count': 0,
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
                'word_count': 0,
                'excluded_elements_count': 0,
                'extracted_at': datetime.now().isoformat()
            }
        else:
            # Extract title
            title = response.css('title::text').get()
            if title:
                title = title.strip()
            
            # Extract all visible text (excluding headers/footers)
            text_content, excluded_count = self.extract_visible_text(response)
            
            # Calculate word count
            word_count = len(text_content.split()) if text_content else 0
            
            result = {
                'url': url,
                'title': title,
                'text_content': text_content,
                'content_type': content_type,
                'error': 'none',
                'status_code': response.status,
                'word_count': word_count,
                'excluded_elements_count': excluded_count,
                'extracted_at': datetime.now().isoformat()
            }
        
        self.results.append(result)
        return result
    
    def extract_visible_text(self, response):
        """Extract all visible text from the page, excluding headers/footers"""
        # Create a copy of the response selector to avoid modifying the original
        selector = response
        
        # Count excluded elements for statistics
        excluded_count = 0
        
        # Remove excluded elements first
        for css_selector in self.excluded_selectors:
            try:
                elements = selector.css(css_selector)
                excluded_count += len(elements)
                # Remove each matching element
                for element in elements:
                    element.remove()
            except Exception as e:
                # Log but don't fail if a selector doesn't work
                self.logger.debug(f"Selector '{css_selector}' failed: {e}")
                continue
        
        # Remove script and style elements (if any remain)
        for script in selector.css('script'):
            script.remove()
        for style in selector.css('style'):
            style.remove()
        
        # Also remove comments and other non-visible elements
        for comment in selector.css('*[style*="display: none"], *[style*="display:none"]'):
            comment.remove()
        for hidden in selector.css('*[style*="visibility: hidden"], *[style*="visibility:hidden"]'):
            hidden.remove()
        
        # Get all remaining text content
        text_elements = selector.css('*::text').getall()
        
        # Clean and filter text
        cleaned_text = []
        for text in text_elements:
            text = text.strip()
            # Skip empty text, whitespace-only text, and very short text snippets
            if text and not text.isspace() and len(text) > 1:
                # Skip common navigation text patterns
                if not self.is_navigation_text(text):
                    cleaned_text.append(text)
        
        # Join with spaces and clean up extra whitespace
        full_text = ' '.join(cleaned_text)
        # Replace multiple spaces/newlines with single space
        full_text = re.sub(r'\s+', ' ', full_text)
        
        return full_text.strip(), excluded_count
    
    def is_navigation_text(self, text):
        """Check if text appears to be navigation-related"""
        # Convert to lowercase for comparison
        text_lower = text.lower().strip()
        
        # Skip very common navigation phrases
        nav_patterns = [
            'skip to content',
            'skip to main content',
            'skip navigation',
            'home',
            'contact us',
            'about us',
            'privacy policy',
            'terms of service',
            'sitemap',
            'back to top',
            'print page',
            'email page',
            'share this page',
            'follow us',
            'copyright',
            '©',
            'all rights reserved',
            'powered by',
            'website by',
            'designed by'
        ]
        
        # Skip if text matches navigation patterns
        for pattern in nav_patterns:
            if pattern in text_lower:
                return True
        
        # Skip if text is just a single character or symbol
        if len(text_lower) == 1 and not text_lower.isalnum():
            return True
            
        # Skip if text is just numbers (likely pagination)
        if text_lower.isdigit():
            return True
        
        return False
    
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
            'word_count': 0,
            'excluded_elements_count': 0,
            'extracted_at': datetime.now().isoformat()
        }
        
        self.results.append(result)
        self.logger.error(f"Error processing {url}: {error}")
        
        return result
    
    def closed(self, reason):
        """Save results to JSON file when spider closes"""
        try:
            # Calculate summary statistics
            total_urls = len(self.results)
            successful = len([r for r in self.results if r['error'] == 'none'])
            errors = len([r for r in self.results if r['error'] not in ['none', 'skipped_document']])
            skipped_documents = len([r for r in self.results if r['error'] == 'skipped_document'])
            not_html = len([r for r in self.results if r['error'] == 'not_html_content'])
            
            # Calculate content statistics
            total_words = sum(r['word_count'] for r in self.results if r['word_count'])
            total_excluded_elements = sum(r['excluded_elements_count'] for r in self.results if r['excluded_elements_count'])
            avg_words_per_page = total_words / successful if successful > 0 else 0
            avg_excluded_per_page = total_excluded_elements / successful if successful > 0 else 0
            
            # Create summary object
            summary = {
                'total_urls_processed': total_urls,
                'successful_extractions': successful,
                'errors': errors,
                'skipped_documents': skipped_documents,
                'not_html_content': not_html,
                'total_words_extracted': total_words,
                'total_excluded_elements': total_excluded_elements,
                'avg_words_per_page': round(avg_words_per_page, 1),
                'avg_excluded_elements_per_page': round(avg_excluded_per_page, 1),
                'processing_completed_at': datetime.now().isoformat(),
                'success_rate': f"{(successful/total_urls*100):.1f}%" if total_urls > 0 else "0.0%"
            }
            
            # Structure final output with results and summary
            output_data = {
                'extraction_settings': {
                    'excluded_selectors': self.excluded_selectors,
                    'document_extensions_skipped': list(self.document_extensions)
                },
                'results': self.results,
                'summary': summary
            }
            
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved {total_urls} results to {self.output_file}")
            
            # Print detailed summary
            self.logger.info(f"Summary: {successful} successful, {errors} errors, {skipped_documents} skipped documents")
            self.logger.info(f"Content stats: {total_words} total words, {total_excluded_elements} elements excluded")
            self.logger.info(f"Averages: {avg_words_per_page:.1f} words/page, {avg_excluded_per_page:.1f} excluded elements/page")
            self.logger.info(f"Success rate: {summary['success_rate']}")
            
        except Exception as e:
            self.logger.error(f"Error saving results: {e}")