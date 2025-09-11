# File: kerala_police_crawler/items.py

import scrapy

class UrlItem(scrapy.Item):
    url = scrapy.Field()
    status_code = scrapy.Field()
    content_type = scrapy.Field()
    title = scrapy.Field()
    depth = scrapy.Field()



