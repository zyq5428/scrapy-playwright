# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class TemplateItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class BookjwtItem(scrapy.Item):
    collection = 'bookjwt'

    score = scrapy.Field()
    name = scrapy.Field()
    tags = scrapy.Field()
    price = scrapy.Field()
    authors = scrapy.Field()
    published_at = scrapy.Field()
    isbm = scrapy.Field()
    cover = scrapy.Field()
    comments = scrapy.Field()
    image_paths = scrapy.Field()

class MovieScrollItem(scrapy.Item):
    collection = 'MovieScroll'

    score = scrapy.Field()
    name = scrapy.Field()
    categories = scrapy.Field()
    published_at = scrapy.Field()
    cover = scrapy.Field()
    image_paths = scrapy.Field()

class NbaItem(scrapy.Item):
    collection = 'NBA'

    name = scrapy.Field()
    height = scrapy.Field()
    weight = scrapy.Field()
    cover = scrapy.Field()
    image_paths = scrapy.Field()