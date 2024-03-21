import asyncio
from playwright.async_api import async_playwright
from urllib.parse import urljoin
from pyquery import PyQuery as pq
import time
import json
import re
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

# Setting
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36'
BASE_URL = 'https://spa13.scrape.center/'
LOGIN_URL = 'https://login3.scrape.center/login'
DETAIL_URL = 'https://login3.scrape.center/detail/1491325'
USERNAME = 'admin'
PASSWORD = 'admin'
COOKIE_FILE = 'cookies.json'
INDEX_FILE_NAME = 'index.html'
DETAIL_FILE_NAME = 'detail.html'

'''
程序作用: 爬取指定页面,返回页面代码源文档+
参数: page_obj (页面对象), url (爬取页面地址)
返回值: page_obj.content() (页面代码源文档)
'''
async def scrape_api(page_obj, url):
    # Remove webdriver detection
    js = """
    Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});
    """
    await page_obj.add_init_script(js)
    # Images are not allowed to be loaded
    await page_obj.route(re.compile(r"(\.png)|(\.jpg)"), lambda route: route.abort())

    logging.info('Scraping %s...', url)
    try:
        await page_obj.goto(url)
        await page_obj.wait_for_load_state("networkidle")
        return await page_obj.content()
    except Exception as e:
        logging.error('error occurred while scraping %s', url, exc_info=True)

'''
程序作用: 完成网站模拟登录,并保存cookies
参数: page_obj (页面对象), url (爬取页面地址)
返回值: storage (登录后的cookies, 字典类型)
'''
async def simulate_login(url):
    async with async_playwright() as playwright:
        chromium = playwright.chromium
        browser = await chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        try:
            logging.info('Start logging in %s...', url)
            await page.goto(url)
            await page.wait_for_load_state("networkidle")
            await page.locator('input[type="text"]').fill(USERNAME)
            await page.locator('input[type="password"]').fill(PASSWORD)
            await page.locator("form").get_by_role("button", name="登录").click()
            await page.wait_for_load_state("networkidle")
            username = page.get_by_text(USERNAME)
            await username.wait_for()
            # In order to obtain the token of JWT
            await page.reload()
            await page.wait_for_load_state("networkidle")
            # save storage_state to file
            storage = await context.storage_state(path=COOKIE_FILE)
            logging.info('Cookies is saved to %s: \n %s', COOKIE_FILE, storage)
            await page.close()
            await context.close()
            await browser.close()
            return storage
        except Exception as e:
            logging.error('error occurred while scraping %s', url, exc_info=True)

async def main():
    # await simulate_login(BASE_URL)

    async with async_playwright() as playwright:
        chromium = playwright.chromium
        browser = await chromium.launch(headless=False)
        # browser = await chromium.launch()
        # context = await browser.new_context(user_agent=USER_AGENT, storage_state=COOKIE_FILE)
        context = await browser.new_context(user_agent=USER_AGENT)
        page_obj = await context.new_page()
        html = await scrape_api(page_obj, BASE_URL)
        with open(INDEX_FILE_NAME, 'w', encoding='utf-8') as f:
            f.write(html)
        # html = await scrape_api(page_obj, DETAIL_URL)
        # with open(DETAIL_FILE_NAME, 'w', encoding='utf-8') as f:
        #     f.write(html)
        await page_obj.close()
        await context.close()
        await browser.close()

if __name__ == '__main__':
    start_time = time.time()
    asyncio.run(main())
    end_time = time.time()
    print('程序运行时间为:', end_time - start_time)