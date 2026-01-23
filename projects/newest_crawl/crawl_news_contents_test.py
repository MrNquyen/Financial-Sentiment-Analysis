# Source - https://stackoverflow.com/a
# Posted by ggorlen, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-20, License - CC BY-SA 4.0

from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
import pandas as pd
import os
import json
import aiohttp
import asyncio
import time
from tqdm import tqdm


#---- Load json
def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        json_content = json.load(file)
        return json_content
    
#---- Save json
def save_json(path, content):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(content, file, ensure_ascii=False, indent=3)


#---- Crawler
class Crawler():
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
        
        
async def main():
    crawler = Crawler()
    all_news_items = []
    max_pages = 1001
    
    batch_size = 10
    stop_crawling = False
    page_url = "https://vn.investing.com/news/stock-market-news/2001-doc-gi-truoc-gio-giao-dich-chung-khoan-2514598"
    async with aiohttp.ClientSession(trust_env=True) as session:
        if stop_crawling:
            print("Stop Crawling")
        
        html = await crawler.crawling_news_urls(session=session, page_url=page_url)
        print(html)
        await asyncio.sleep(0.5)
    


if __name__=="__main__":
    asyncio.run(main())
    print("Crawling completed!")
    
    