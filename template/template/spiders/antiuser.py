import scrapy
import sys
import os
import re
import json
from urllib.parse import urljoin
from template.items import AntiUserItem
from scrapy_playwright.page import PageMethod
from pyquery import PyQuery as pq

BASE_URL = 'https://antispider7.scrape.center/'
LOGIN_URL = 'https://antispider7.scrape.center/login'
USERNAME = 'admin'
PASSWORD = 'admin'
COOKIE_FILE = 'cookies.json'

ACCOUNT = [
    ['herozhou1', 'asdfgh'], ['herozhou2', 'asdfgh'], ['herozhou3', 'asdfgh'], 
    ['herozhou4', 'asdfgh'], ['herozhou5', 'asdfgh'], ['herozhou6', 'asdfgh'], 
    ['herozhou7', 'asdfgh'], ['herozhou8', 'asdfgh'], ['herozhou9', 'asdfgh'], 
    ['herozhou10', 'asdfgh'],
]

ERROR_STR = '403 Forbidden.'

# Bypass Webdriver detection
js = """
Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});
"""
async def init_page(page, request):
    await page.add_init_script(js)

class AntiuserSpider(scrapy.Spider):
    name = "antiuser"
    handle_httpstatus_list = [403]

    def __init__(self, name=None, **kwargs):
        super().__init__(name, **kwargs)
        global ACCOUNT
        global USERNAME
        global PASSWORD
        self.account = ACCOUNT
        self.username = USERNAME
        self.password = PASSWORD

    def start_requests(self):
        yield scrapy.Request(
            url = LOGIN_URL,
            callback = self.parse_login,
            meta = {
                'playwright': True,
                'playwright_context': 'login',
                'playwright_include_page': True,
                'playwright_page_init_callback': init_page,
                'playwright_page_methods': [
                    PageMethod('wait_for_selector', 'input[type="text"]'),
                ]
            },
            errback = self.errback_close_page,
        )

    def choose_user(self):
        if len(self.account) == 0:
            sys.exit(1)
        self.username = self.account[-1][0]
        self.password = self.account[-1][1]
        self.account = self.account[0:-1]
        self.logger.info('Current user: %s,pwd: %s', self.username, self.password)


    async def login(self, page):
        # await page.screenshot(path="./image/login.png", full_page=True)
        self.choose_user()
        try:
            self.logger.info('Start logging...')
            await page.locator('input[type="text"]').fill(self.username)
            await page.locator('input[type="password"]').fill(self.password)
            await page.locator("form").get_by_role("button", name="登录").click()
            await page.wait_for_load_state("networkidle")
            username = page.get_by_text(self.username)
            await username.wait_for()
            self.logger.info('The switching user is: %s', self.username)
            # In order to obtain the token of JWT
            await page.goto(BASE_URL)
            await page.wait_for_load_state("networkidle")
            # save storage_state to file
            storage = await page.context.storage_state(path=self.username)
            self.logger.debug('Cookies is saved to %s: \n %s', self.username, storage)
            # await page.screenshot(path="./image/login_succeed.png", full_page=True)
        except Exception as e:
            self.logger.error('login failed', exc_info=True)

    async def relogin(self, response, url, username):
        page = response.meta['playwright_page']
        # repeat_url = response.meta['url']
        # self.logger.info('repeat url is: %s', repeat_url)
        if username == self.username:
            await self.login(page)
        else:
            await page.wait_for_timeout(10000)
        storage_state = {}
        with open('cookies.json') as f:
            storage_state = json.load(f)
        self.logger.info('Recrawl the site: %s', url)
        yield scrapy.Request(
            url = url,
            callback = self.parse_index,
            meta = {
                'playwright': True,
                'playwright_context': 'parse_detail',
                "playwright_context_kwargs": {
                    "storage_state": storage_state,
                },
                'playwright_include_page': True,
                'playwright_page_init_callback': init_page,
                'playwright_page_methods': [
                    PageMethod("wait_for_selector", ".logo"),
                ]
            },
            dont_filter = True,
            errback = self.errback_close_page,
        )
        await page.close()
        self.logger.info('The login page are closed')

    async def parse_login(self, response):
        page = response.meta['playwright_page']
        await self.login(page)

        storage_state = {}
        with open('cookies.json') as f:
            storage_state = json.load(f)
        for n in range(1, self.settings.get('MAX_PAGE') + 1):
            index_url = f'{BASE_URL}page/{n}'
            self.logger.info('Get index url: %s', index_url)
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
        await page.close()
        self.logger.info('The login page are closed')

    async def parse_index(self, response):
        page = response.meta['playwright_page']
        storage_state = {}
        with open('cookies.json') as f:
            storage_state = json.load(f)
        books = response.css('#index .el-row .el-col-4')
        for book in books:
            href = book.css('.bottom a::attr("href")').extract_first()
            url = urljoin(BASE_URL, href)
            self.logger.info('Get detail url: %s', url)
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
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'networkidle',
                    },
                    # 'playwright_page_methods': [
                    #     PageMethod("wait_for_selector", ".el-card__body"),
                    # ],
                },
                # errback = self.errback_close_page,
                errback = self.errback_error_code,
            )
        await page.close()

    async def parse_detail(self, response):
        page = response.meta['playwright_page']
        await page.locator('.m-t.el-row div.el-card__body h2').first.wait_for()
        h2 = await page.locator('.m-t.el-row div.el-card__body h2').first.text_content()
        username = await page.locator('.login .logout').text_content()
        username = re.search(r'(\b.*\b)', username).group(1)
        self.logger.info('url: %s, h2: %s, username: %s', response.url, h2, username)
        if h2 == ERROR_STR:
            self.logger.error('Users click frequently, Current user is: %s', self.username)
            yield scrapy.Request(
                url = response.url,
                callback = self.relogin,
                meta = {
                    'playwright': True,
                    'playwright_context': 'relogin',
                    'playwright_include_page': True,
                    'playwright_page_init_callback': init_page,
                    'playwright_page_methods': [
                        PageMethod('wait_for_selector', 'input[type="text"]'),
                    ],
                },
                cb_kwargs = {
                    'url': response.url,
                    'username': username,
                },
                dont_filter = True,
                errback = self.errback_close_page,
            )
        else:
            item = AntiUserItem()
            html = await page.content()
            doc = pq(html)
            score = doc('.score').text()
            item['score'] = float(score) if score else None
            item['name'] = doc('h2.name').text()
            item['tags'] = [item.text() for item in doc('.tags span').items()]
            price = doc('.info .price span').text()
            if price and re.search(r'\d+(\.\d*)?', price):
                item['price'] = float(re.search(r'\d+(\.\d*)?', price).group())
            item['authors'] = re.search(r'作者：(.*)', doc('.info .authors').text()).group(1) \
                if doc('.info .authors').text() else None
            item['published_at'] = re.search(r'(\d{4}-\d{2}-\d{2})', doc('.info .published-at').text()).group(1) \
                if doc('.info .published-at').text() else None
            item['isbm'] = re.search(r'ISBN：(.*)', doc('.info .isbn').text()).group(1) \
                if doc('.info .isbn').text() else None
            item['cover'] = doc('img.cover').attr('src')
            item['comments'] = [item.text() for item in doc('.comments p').items()]

            self.logger.info('item: %s' % item)

            yield item
        await page.close()

    async def errback_close_page(self, failure):
        page = failure.request.meta['playwright_page']
        await page.close()

    async def errback_error_code(self, failure):
        self.logger.error(repr(failure))
        page = failure.request.meta['playwright_page']
        await page.close()
