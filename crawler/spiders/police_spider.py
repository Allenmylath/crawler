# File: crawler/spiders/police_spider.py

import scrapy
import json
from urllib.parse import urljoin, urlparse
from datetime import datetime


class PoliceSpider(scrapy.Spider):
    name = 'kerala_police'
    allowed_domains = ['thuna.keralapolice.gov.in']
    start_urls = ['https://thuna.keralapolice.gov.in/']

    # File extensions to exclude (images, scripts, styles)
    excluded_extensions = {
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico',
        'js', 'css',
        'woff', 'woff2', 'ttf', 'eot', 'otf'
    }

    # File extensions to treat as documents (yield but don't follow)
    document_extensions = {
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'txt', 'csv', 'xml', 'json', 'zip', 'rar'
    }

    def __init__(self):
        self.found_urls = set()
        self.url_data = []  # Store full metadata for output

    def parse(self, response):
        current_url = response.url
        self.found_urls.add(current_url)

        item = {
            'url': current_url,
            'status_code': response.status,
            'content_type': response.headers.get('Content-Type', b'').decode('utf-8'),
            'title': response.css('title::text').get(),
            'depth': response.meta.get('depth', 0)
        }
        self.url_data.append(item)
        yield item

        links = response.css('a::attr(href)').getall()

        for link in links:
            if link:
                absolute_url = urljoin(response.url, link.strip())
                cleaned_url = self.clean_url(absolute_url)

                if self.should_follow_url(cleaned_url):
                    if cleaned_url not in self.found_urls:
                        if self.is_document_url(cleaned_url):
                            self.found_urls.add(cleaned_url)
                            doc_item = {
                                'url': cleaned_url,
                                'status_code': 'document',
                                'content_type': 'document',
                                'title': 'Document Link',
                                'depth': response.meta.get('depth', 0) + 1
                            }
                            self.url_data.append(doc_item)
                            yield doc_item
                        else:
                            yield response.follow(
                                cleaned_url,
                                callback=self.parse,
                                dont_filter=False
                            )

    def clean_url(self, url):
        """Remove fragments from URL"""
        if '#' in url:
            url = url.split('#')[0]
        return url.rstrip('/')

    def should_follow_url(self, url):
        """Only follow URLs within thuna.keralapolice.gov.in"""
        parsed = urlparse(url)

        if parsed.netloc != 'thuna.keralapolice.gov.in':
            return False

        path = parsed.path.lower()
        if '.' in path:
            extension = path.split('.')[-1].split('?')[0]
            if extension in self.excluded_extensions:
                return False

        return True

    def is_document_url(self, url):
        """Check if URL points to a document file"""
        parsed = urlparse(url)
        path = parsed.path.lower()

        if '.' in path:
            extension = path.split('.')[-1].split('?')[0]
            return extension in self.document_extensions

        return False

    def closed(self, reason):
        """Save collected URLs to urls.json when crawl finishes"""
        output = {
            'crawled_at': datetime.now().isoformat(),
            'start_url': self.start_urls[0],
            'total_urls': len(self.url_data),
            'urls': self.url_data
        }

        with open('urls.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Saved {len(self.url_data)} URLs to urls.json")
        self.logger.info(f"Crawl finished. Reason: {reason}")
