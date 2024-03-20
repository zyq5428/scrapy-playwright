import scrapy
import re
import json
from urllib.parse import urljoin
from template.items import MovieScrollItem
from scrapy_playwright.page import PageMethod
from pyquery import PyQuery as pq

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
                ]
            },
            errback = self.errback_close_page,
        )

    async def parse_index(self, response):
        page = response.meta['playwright_page']

        # scroll the page to the end
        pre_name = ''
        cur_name = await page.locator('.el-card .m-b-sm').nth(-1).text_content()
        while (cur_name != pre_name):
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.mouse.wheel(0, 10000)
            await page.wait_for_timeout(3000)
            pre_name = cur_name
            cur_name = await page.locator('.el-card .m-b-sm').nth(-1).text_content()
        # screenshot = await page.screenshot(path="./image/" + "web.png", full_page=True)

        # parse index html
        html = await page.content()
        doc = pq(html)
        for item in doc('.el-card.item').items():
            movieitem = MovieScrollItem()
            movieitem['name'] = item('.m-b-sm').text()
            score = item('.score').text()
            score = float(score) if score else None
            movieitem['score'] = score
            movieitem['categories'] = [tag.text() for tag in item('.categories button span').items()]
            movieitem['cover'] = item('.cover').attr('src')
            yield movieitem

            # self.logger.info('movie name is : %s', movieitem)

    async def errback_close_page(self, failure):
        page = failure.request.meta['playwright_page']
        await page.close()
