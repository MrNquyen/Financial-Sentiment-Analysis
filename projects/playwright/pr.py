# Source - https://stackoverflow.com/a
# Posted by ggorlen, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-20, License - CC BY-SA 4.0

import json
import asyncio
from tqdm import tqdm
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


class PlaywrightScrolling():
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.url = None
    
    async def initialize(self, url, resume_page=None):
        """Initialize the playwright instance and browser"""
        self.url = url
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        if resume_page:
            self.page = resume_page
        else:
            context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            self.page = await context.new_page()
            
            # Set longer timeout and wait for network idle
            try:
                print(f"Đang truy cập: {url}")
                await self.page.goto(url, wait_until='domcontentloaded', timeout=500000)
                print("Truy cập thành công!")
            except Exception as e:
                print(f"Lỗi khi truy cập trang: {e}")
                raise
    
    
    async def scroll(self, time_sleep=2, num_trials=3):
        async def press_end():
            await self.page.keyboard.press("End")
            await asyncio.sleep(time_sleep)
        
        prev_height = await self.page.evaluate("document.body.scrollHeight")
        await press_end()
        # Check if height changed
        trial = 0
        while True:
            if trial == num_trials:
                break
            new_height = await self.page.evaluate("document.body.scrollHeight")
            if new_height == prev_height:
                trial += 1
                print(f"Cannot scroll - trial {trial}")
                await press_end()
            else:
                prev_height = new_height
                break
        
        
    async def get_page_content(self):
        return await self.page.content()
    
    async def close(self):
        """Close browser and playwright"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        
        
        
        
# BEAUTIFUL SOUP
def save_html(content, path):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def save_json(content, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)

def get_keyword_news_url(keyword="TSLA"):
    return f"https://finance.yahoo.com/quote/{keyword}/news"


def parse_thumnail_details_in_source(source_content):
    source_soup = BeautifulSoup(source_content)
    all_news_html = source_soup.find_all("li", class_="stream-item story-item yf-9xydx9")
    all_news_items = []
    for new_html in tqdm(all_news_html):
        item_title_html = new_html.find("div", class_="content yf-1u32w3i")
        
        item_url = item_title_html.find("a", "subtle-link fin-size-small titles noUnderline yf-119g04z").get("href", "")
        title = item_title_html.text
        item_posted_time = new_html.find("div", class_="footer yf-1u32w3i").text
        if item_posted_time in title:
            title = title.replace(item_posted_time, "")
        item_posted_time = item_posted_time.split("•")[-1]

        item = {
            "item_url": item_url.strip(), 
            "title": title.strip(),
            "time": item_posted_time.strip(),
        }
        all_news_items.append(item)
    return all_news_items


async def main():
    url = get_keyword_news_url(keyword="NVDA")
    scroller = PlaywrightScrolling()
    await scroller.initialize(url=url)
    
    #-- Scrolling
    for i in tqdm(range(30)):
        await scroller.scroll()
    page_content = await scroller.get_page_content()
    all_news_items = parse_thumnail_details_in_source(page_content)
    
    
    #-- Parse
    save_json({
        "all_news_items": all_news_items
    }, path="all_news_items.json")
    
    await scroller.close()


if __name__=="__main__":
    asyncio.run(main())
    
    
        
# https://www.investing.com/equities/nvidia-corp-news # Update annually