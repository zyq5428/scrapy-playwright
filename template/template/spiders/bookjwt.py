import scrapy
import re
import json
from urllib.parse import urljoin
from template.items import BookjwtItem
from scrapy_playwright.page import PageMethod

BASE_URL = 'https://login3.scrape.center/'
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

class BookjwtSpider(scrapy.Spider):
    name = "bookjwt"

    def start_requests(self):
        yield scrapy.Request(
            url = LOGIN_URL,
            callback = self.simulate_login,
            meta = {
                'playwright': True,
                'playwright_context': 'login',
                'playwright_include_page': True,
                'playwright_page_init_callback': init_page,
                'playwright_page_methods': [
                    PageMethod("wait_for_selector", "input[type='password']"),
                ]
            },
            errback = self.errback_close_page,
        )

    async def simulate_login(self, response):
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

    async def scrape_index(self, response):
        storage_state = {}
        with open('cookies.json') as f:
            storage_state = json.load(f)
        for page in range(1, self.settings.get('MAX_PAGE') + 1):
            index_url = f'{BASE_URL}page/{page}'
            self.logger.debug('Get detail url: %s', index_url)
            yield scrapy.Request(
                url = index_url,
                callback = self.parse_index,
                meta = {
                    'playwright': True,
                    'playwright_context': 'index',
                    "playwright_context_kwargs": {
                        "storage_state": storage_state,
                    },
                    'playwright_include_page': True,
                    'playwright_page_init_callback': init_page,
                    'playwright_page_methods': [
                        PageMethod("wait_for_selector", ".el-card__body"),
                    ]
                },
                errback = self.errback_close_page,
            )

    async def parse_index(self, response):
        page = response.meta['playwright_page']
        storage_state = {}
        with open('cookies.json') as f:
            storage_state = json.load(f)
        books = response.css('#index .el-row .el-col-4')
        for book in books:
            href = book.css('.bottom a::attr("href")').extract_first()
            url = urljoin(BASE_URL, href)
            self.logger.debug('Get detail url: %s', url)
            yield scrapy.Request(
                url = url,
                callback = self.parse_detail,
                meta = {
                    'playwright': True,
                    'playwright_context': 'detail',
                    "playwright_context_kwargs": {
                        "storage_state": storage_state,
                    },
                    'playwright_include_page': True,
                    'playwright_page_init_callback': init_page,
                    'playwright_page_methods': [
                        PageMethod("wait_for_selector", ".item .name"),
                    ]
                },
                errback = self.errback_close_page,
            )
        await page.close()

    async def parse_detail(self, response):
        page = response.meta['playwright_page']
        await page.close()

        item = BookjwtItem()
        score = response.css('.score::text').get()
        item['score'] = float(score) if score else None
        item['name'] = response.css('h2.name::text').get()
        item['tags'] = response.css('.tags span::text').re('[^\x00-\xff]{1,10}')
        price = response.css('.info .price span::text').get()
        if price and re.search(r'\d+(\.\d*)?', price):
            item['price'] = float(re.search(r'\d+(\.\d*)?', price).group())
        item['authors'] = response.css('.info .authors::text').re('作者：(.*)')[0] \
            if response.css('.info .authors::text').get() else None
        item['published_at'] = response.css('.info .published-at::text').re('(\d{4}-\d{2}-\d{2})')[0] \
            if response.css('.info .published-at::text').get() else None
        item['isbm'] = response.css('.info .isbn::text').re('ISBN：(.*)')[0] \
            if response.css('.info .isbn::text').get() else None
        item['cover'] = response.css('img.cover::attr("src")').get()
        item['comments'] = response.css('.comments p::text').re('[^\x00-\xff].*')

        self.logger.debug('item: %s' % item)

        yield item

    async def errback_close_page(self, failure):
        page = failure.request.meta['playwright_page']
        await page.close()
