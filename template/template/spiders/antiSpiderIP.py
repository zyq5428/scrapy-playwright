import scrapy
import re
import json
from urllib.parse import urljoin
from template.items import BookjwtItem
from scrapy_playwright.page import PageMethod

BASE_URL = 'https://antispider5.scrape.center/'
LOGIN_URL = 'https://login3.scrape.center/login'
USERNAME = 'admin'
PASSWORD = 'admin'
COOKIE_FILE = 'cookies.json'

# Bypass Webdriver detection
js = """
Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});
"""
async def init_page(page, request):
    await page.add_init_script(js)

class AntispiderSpider(scrapy.Spider):
    name = "antiSpiderIP"

    def start_requests(self):
        yield scrapy.Request(
            url = LOGIN_URL,
            callback = self.parse_index,
            meta = {
                'playwright': True,
                'playwright_context': 'login',
                "playwright_context_kwargs": {
                    "proxy": {
                        "server": "http://myproxy.com:3128",
                        "username": "user",
                        "password": "pass",
                    },
                },
                'playwright_include_page': True,
                'playwright_page_init_callback': init_page,
                'playwright_page_methods': [
                    PageMethod("wait_for_selector", ".el-row"),
                ]
            },
            errback = self.errback_close_page,
        )

    async def parse_index(self, response):
        page = response.meta['playwright_page']
        title = re.search(r'center\/(.*)', response.url).group(1)
        try:
            self.logger.info('Start logging in %s...', response.url)
            await page.locator('input[type="text"]').fill(USERNAME)
            await page.locator('input[type="password"]').fill(PASSWORD)
            await page.locator("form").get_by_role("button", name="登录").click()
            await page.wait_for_load_state("networkidle")
            username = page.get_by_text(USERNAME)
            await username.wait_for()
            # In order to obtain the token of JWT
            await page.goto(BASE_URL)
            await page.wait_for_load_state("networkidle")
            # save storage_state to file
            storage = await page.context.storage_state(path=COOKIE_FILE)
            self.logger.debug('Cookies is saved to %s: \n %s', COOKIE_FILE, storage)
            # screenshot = await page.screenshot(path="./image/" + title + "_succeed.png", full_page=True)
        except Exception as e:
            self.logger.error('error occurred while login %s', response.url, exc_info=True)

        yield scrapy.Request(
            url = BASE_URL,
            callback = self.scrape_index,
            meta = {
                'playwright': True,
                'playwright_context': 'login',
                'playwright_page_init_callback': init_page,
                'playwright_page_methods': [
                    PageMethod("wait_for_selector", ".el-card__body"),
                ]
            },
            errback = self.errback_close_page,
        )
        await page.close()
        self.logger.info('The login page are closed')

    async def errback_close_page(self, failure):
        page = failure.request.meta['playwright_page']
        await page.close()
