# Source - https://stackoverflow.com/a
# Posted by ggorlen, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-20, License - CC BY-SA 4.0

import os
import time
import json
import aiohttp
import asyncio
import pandas as pd
from tqdm import tqdm
from vnstock import Quote
from vnstock import Trading
from bs4 import BeautifulSoup
from urllib.request import urlopen, Request
from playwright.async_api import async_playwright



#---- Load json
def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        json_content = json.load(file)
        return json_content
    
#---- Save json
def save_json(path, content):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(content, file, ensure_ascii=False, indent=3)


class StockHistoryCrawler():
    def __init__(self, symbol='VNINDEX', source='VCI'):
        self.quote = Quote(symbol=symbol, source=source)
        self.trading = Trading(symbol=symbol, source=source)

    def crawling_history(self, start_date, end_date):
        history_df = quote.history(start=start_date, end=end_date)
        history_df["time"] = pd.to_datetime(history_df["time"])
        history_df = history_df[(history_df["time"] >= start_date) & (history_df["time"] <= end_date)]
        return history_df


#---- Crawler: Crawling the URL to news
class NewsCrawler():
    def __init__(self):
        pass
    
    def get_page_url(self, page_id):
        url_template = "https://vn.investing.com/indices/vn-news/{page_id}"
        url = url_template.format(page_id=page_id)
        return url
    
    async def request_url(self, session, url, max_retries=3):
        # hdr = {'User-Agent': 'Mozilla/5.0'}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        for attempt in range(max_retries):
            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status==200:
                        return await response.text()
                    else:
                        print("Request OKE but status failed")
                        return None
            except asyncio.TimeoutError:
                print(f"Timeout on attempt {attempt + 1}/{max_retries} for {url}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
        return None
    
    
    async def parse_news_details_in_page(self, source_content):
        source_soup = BeautifulSoup(source_content, "html.parser")
        all_news_html = source_soup.find_all("div", class_="block w-full sm:flex-1")
        page_news_items = []
        for new_html in all_news_html:
            item_title_html = new_html.find("a", class_="block text-base font-bold leading-5 hover:underline sm:text-base sm:leading-6 md:text-lg md:leading-7")
            item_url = item_title_html.get("href", "")
            title = item_title_html.text
            item_posted_time = new_html.find("li", class_="ml-2").text
            
            #-- preprocessing
            if "•" in item_posted_time:
                item_posted_time = item_posted_time.replace("•", "")
            
            #-- set variables
            item = {
                "item_url": item_url.strip(), 
                "title": title.strip(),
                "time": item_posted_time.strip(),
            }
            page_news_items.append(item)
        return page_news_items
    
    
    async def crawling_news_urls(self, session, page_url):
        html_content = await self.request_url(session, page_url)
        if html_content is not None:
            page_news_items = await self.parse_news_details_in_page(source_content=html_content)
            return page_news_items
        else:
            print("Page doesn't exist")
            return []
        

#---- PlaywrightCrawler: Crawling News Content
class PlaywrightCrawler():
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.url = None
    
    async def initialize(self):
        """Initialize the playwright instance and browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 600, 'height': 600},
            locale='vi-VN',
            timezone_id='Asia/Ho_Chi_Minh',
            extra_http_headers={
                'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        
    async def get_page_content(self, page):
        return await page.content()
    
    
    async def parse_news_details(self, html):
        soup = BeautifulSoup(html, "html.parser")
        
        #-- Date posted
        posted_date_html = soup.find("div", class_="flex flex-col gap-2 text-warren-gray-700 md:flex-row md:items-center md:gap-0")
        posted_date_html = posted_date_html.find("div", class_="flex flex-row items-center")
        posted_date_str = posted_date_html.text
        
        #-- Main texts
        main_content_html = soup.find("div", class_="article_WYSIWYG__O0uhw article_articlePage__UMz3q text-[18px] leading-8")
        all_content_lines = main_content_html.find_all("p")
        main_content = ""
        for line in all_content_lines:
            main_content += line.text.strip() + " \n "
        
        #-- Combined
        news_detail_dict = {
            "posted_date": posted_date_str,
            "main_content": main_content,
        }
        return news_detail_dict
        
    
    async def get_news_details (self, url, attempts=3):
        for attempt in range(attempts):
            try:
                page = await self.context.new_page()
                await page.goto(url, wait_until='domcontentloaded', timeout=500000)
                await asyncio.sleep(3)
                
                page_html = await self.get_page_content(page)
                news_detail_dict = await self.parse_news_details(html=page_html)
                return news_detail_dict
            except Exception as e:
                print(f"Attempt {attempt + 1}/{attempts} failed for {url}: {e}")
                if attempt < attempts - 1:
                    await asyncio.sleep(0.5)
            finally:
                if page:
                    await page.close()
        return None
    
    
    async def close(self):
        """Close browser and playwright"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


        
#====================== Main function ==================
async def main():
    # Init Instance
    news_url_crawler = NewsCrawler()
    stock_crawler = StockHistoryCrawler()
    content_crawler = PlaywrightCrawler()
    await content_crawler.initialize()
    
    # Configuration
    batch_size = 10
    time_wait = 0.5
    max_pages = 1001
    stop_crawling = False

    # Start Crawling news URL
    # Crawling with asynchronous
    save_path_template = r"C:\APAC\all_projects\finetuning-airflow-project\projects\newest_crawl\save\all_news_item_{page_id}.json"
    async with aiohttp.ClientSession(trust_env=True) as session:
        for start_page_id in tqdm(range(0, max_pages, batch_size)):
            if stop_crawling:
                print("Stop Crawling")
                break
            
            batch_page_ids = list(range(start_page_id, start_page_id+batch_size))
            batch_page_urls = [news_url_crawler.get_page_url(page_id=page_id+1) for page_id in batch_page_ids]
            batch_save_paths = [save_path_template.format(page_id=page_id) for page_id in batch_page_ids]

            tasks = []
            tasks_save_paths = []
            for page_url, save_path in zip(batch_page_urls, batch_save_paths):
                if os.path.isfile(save_path):
                    continue
                #-- Crawling news url with Request and BeutifulSoup
                tasks.append(news_url_crawler.crawling_news_urls(session=session, page_url=page_url))
                tasks_save_paths.append(save_path)
            
            if not tasks:
                continue
            
            try:
                batch_news_items = await asyncio.gather(*tasks)
            except Exception as e:
                print(f"Error {e} when crawling batch of ids")
                continue
            
            #-- After crawling urls of news, we use that url to parse for the content using Playwright
            for page_news_items, page_save_path in zip(batch_news_items, tasks_save_paths):
                news_urls = []
                news_titles = []
                news_times = []
                for item in page_news_items:
                    news_urls.append(item["item_url"])
                    news_titles.append(item["title"])
                    news_times.append(item["time"])
                    
                content_tasks = []
                for url in news_urls:
                    content_tasks.append(content_crawler.get_news_details(url))
                    news_details = await asyncio.gather(*content_tasks)
                    page_details = [
                        {
                            "title": title,
                            "time": time,
                            **detail,
                        }
                        for title, time, detail in zip(news_titles, news_times, news_details) if detail is not None
                    ]
                    
                    #-- Save json dictionary after parsing news content
                    save_json(
                        path=save_path, 
                        content=page_details
                    )    
            await asyncio.sleep(0.5)
            
    # Crawling stock history
    start_date = "2021-12-01"
    end_date = "2026-01-22"
    history_df = stock_crawler.crawling_history(
        start_date=start_date,
        end_date=end_date
    )
    history_df.to_csv("./history_df.csv")
        


if __name__=="__main__":
    asyncio.run(main())
    print("Crawling completed!")
    
    