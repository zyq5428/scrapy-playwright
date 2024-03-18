import scrapy
import re
import json
from urllib.parse import urljoin
from template.items import MovieScrollItem
from scrapy_playwright.page import PageMethod

BASE_URL = 'https://spa3.scrape.center/'

# Bypass Webdriver detection
js = """
Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});
"""
async def init_page(page, request):
    await page.add_init_script(js)

class MoviescrollSpider(scrapy.Spider):
    name = "movieScroll"

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
                    # PageMethod("evaluate", "window.scrollTo(0, document.body.scrollHeight)"),
                    # PageMethod("wait_for_selector", "div.el-card:nth-child(100)"),  # 10 per page
                ]
            },
            errback = self.errback_close_page,
        )

    async def parse_index(self, response):
        page = response.meta['playwright_page']
        await page.mouse.wheel(0, 100)
        card = page.locator("div.el-card:nth-child(100)")
        await card.wait_for()
        screenshot = await page.screenshot(path="./image/" + "web.png", full_page=True)

    async def errback_close_page(self, failure):
        page = failure.request.meta['playwright_page']
        await page.close()
