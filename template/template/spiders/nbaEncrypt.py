import scrapy
import re
import json
from urllib.parse import urljoin
from template.items import NbaItem
from scrapy_playwright.page import PageMethod
from pyquery import PyQuery as pq

BASE_URL = 'https://spa13.scrape.center/'

# Bypass Webdriver detection
js = """
Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});
"""
async def init_page(page, request):
    await page.add_init_script(js)

class NbaencryptSpider(scrapy.Spider):
    name = "nbaEncrypt"

    def start_requests(self):
        yield scrapy.Request(
            url = BASE_URL,
            callback = self.parse_index,
            meta = {
                'playwright': True,
                'playwright_context': 'index',
                'playwright_include_page': True,
                'playwright_page_init_callback': init_page,
                'playwright_page_methods': [
                    PageMethod("wait_for_selector", "div.el-card"),
                ]
            },
            errback = self.errback_close_page,
        )

    async def parse_index(self, response):
        page = response.meta['playwright_page']

        for item in response.css('div.el-card'):
            nbaitem = NbaItem()
            nbaitem['name'] = item.css('.name::text').re('[^\x00-\xff].*')[0]
            nbaitem['height'] = item.css('.height span::text').get()
            nbaitem['weight'] = item.css('.weight span::text').get()
            # nbaitem['cover'] = item.css('.image::attr("src")').get()
            # self.logger.info('NBA info is : %s', nbaitem)
            yield nbaitem

        await page.close()

    async def errback_close_page(self, failure):
        page = failure.request.meta['playwright_page']
        await page.close()
