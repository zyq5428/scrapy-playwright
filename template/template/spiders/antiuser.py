import scrapy
import threading
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
        self.user_lock = threading.Lock()
        self.login_lock = threading.Lock()

    def choose_user(self, cur_user):
        self.user_lock.acquire()

        if cur_user == self.username:
            if len(self.account) == 0:
                sys.exit(1)
            self.username = self.account[-1][0]
            self.password = self.account[-1][1]
            self.account = self.account[0:-1]
            self.logger.info('Current user: %s, pwd: %s', self.username, self.password)

        self.user_lock.release()

    def start_requests(self):
        self.choose_user(self.username)
        urls = []
        for n in range(1, self.settings.get('MAX_PAGE') + 1):
            index_url = f'{BASE_URL}page/{n}'
            self.logger.info('Get index url: %s', index_url)
            urls.append(index_url)
        yield scrapy.Request(
            url = LOGIN_URL,
            callback = self.parse_login,
            meta = {
                'playwright': True,
                'playwright_context': self.username,
                'playwright_include_page': True,
                'playwright_page_init_callback': init_page,
                'playwright_page_methods': [
                    PageMethod('wait_for_selector', 'input[type="text"]'),
                ],
            },
            cb_kwargs = {
                'username': self.username,
                'password': self.password,
                'urls': urls,
                'callback': self.parse_index,
            },
            dont_filter = True,
            errback = self.errback_close_page,
        )

    async def parse_login(self, response, username, password, urls, callback):
        page = response.meta['playwright_page']
        try:
            self.logger.info('Start logging...')
            await page.locator('input[type="text"]').fill(username)
            await page.locator('input[type="password"]').fill(password)
            await page.locator("form").get_by_role("button", name="登录").click()
            await page.wait_for_load_state("networkidle")
            user = page.get_by_text(username)
            await user.wait_for()
            self.logger.info('The switching user is: %s', username)
            # In order to obtain the token of JWT
            await page.goto(BASE_URL)
            await page.wait_for_load_state("networkidle")
            # save storage_state to file
            storage = await page.context.storage_state(path=username)
            self.logger.debug('Cookies is saved to %s: \n %s', username, storage)
            # await page.screenshot(path="./image/login_succeed.png", full_page=True)
        except Exception as e:
            self.logger.error('login failed', exc_info=True)

        storage_state = {}
        with open(username) as f:
            storage_state = json.load(f)
        for url in urls:
            self.logger.info('New user crawl url: %s', url)
            yield scrapy.Request(
                url = url,
                callback = callback,
                meta = {
                    'playwright': True,
                    'playwright_context': username,
                    "playwright_context_kwargs": {
                        "storage_state": storage_state,
                    },
                    'playwright_include_page': True,
                    'playwright_page_init_callback': init_page,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'networkidle',
                    },
                },
                dont_filter = True,
                errback = self.errback_close_page,
            )

        await page.close()
        self.logger.info('The login page are closed')

    async def parse_index(self, response):
        page = response.meta['playwright_page']
        html = await page.content()
        doc = pq(html)

        storage_state = {}
        with open(self.username) as f:
            storage_state = json.load(f)

        books = doc('#index .el-row .el-col-4')
        for book in books.items():
            href = book('.bottom a').attr('href')
            url = urljoin(BASE_URL, href)
            self.logger.info('Get detail url: %s', url)
            yield scrapy.Request(
                url = url,
                callback = self.parse_detail,
                meta = {
                    'playwright': True,
                    'playwright_context': self.username,
                    "playwright_context_kwargs": {
                        "storage_state": storage_state,
                    },
                    'playwright_include_page': True,
                    'playwright_page_init_callback': init_page,
                    'playwright_page_goto_kwargs': {
                        'wait_until': 'networkidle',
                    },
                },
                errback = self.errback_close_page,
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
            self.logger.error('Users click frequently, Current user is: %s', username)
            if username == self.username:
                self.choose_user(username)
            self.login_lock.acquire()
            if os.path.exists(self.username):
                self.logger.info('use user: %s to crawl url: %s', self.username, response.url)
                storage_state = {}
                with open(self.username) as f:
                    storage_state = json.load(f)
                yield scrapy.Request(
                    url = response.url,
                    callback = self.parse_detail,
                    meta = {
                        'playwright': True,
                        'playwright_context': self.username,
                        "playwright_context_kwargs": {
                            "storage_state": storage_state,
                        },
                        'playwright_include_page': True,
                        'playwright_page_init_callback': init_page,
                        'playwright_page_goto_kwargs': {
                            'wait_until': 'networkidle',
                        },
                    },
                    dont_filter = True,
                    errback = self.errback_close_page,
                )
            else:
                self.logger.info('Nend login new user: %s', self.username)
                urls = [response.url]
                yield scrapy.Request(
                    url = LOGIN_URL,
                    callback = self.parse_login,
                    meta = {
                        'playwright': True,
                        'playwright_context': self.username,
                        'playwright_include_page': True,
                        'playwright_page_init_callback': init_page,
                        'playwright_page_goto_kwargs': {
                            'wait_until': 'networkidle',
                        },
                    },
                    cb_kwargs = {
                        'username': self.username,
                        'password': self.password,
                        'urls': urls,
                        'callback': self.parse_detail,
                    },
                    dont_filter = True,
                    errback = self.errback_close_page,
                )
            self.login_lock.release()
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

            self.logger.debug('item: %s' % item)

            yield item
        await page.close()

    async def errback_close_page(self, failure):
        page = failure.request.meta['playwright_page']
        await page.close()
