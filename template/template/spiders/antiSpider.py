import scrapy


class AntispiderSpider(scrapy.Spider):
    name = "antiSpider"
    allowed_domains = ["scrape.center"]
    start_urls = ["https://scrape.center"]

    def parse(self, response):
        pass
