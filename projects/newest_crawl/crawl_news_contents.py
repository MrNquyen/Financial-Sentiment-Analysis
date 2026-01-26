import os
import json
import asyncio
from tqdm import tqdm
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

#---- Load json
def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        json_content = json.load(file)
        return json_content
    
#---- Save json
def save_json(path, content):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(content, file, ensure_ascii=False, indent=3)
        


# Playwright
class PlaywrightScrolling():
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
            
            
def get_id_from_path(path):
    template = "all_news_item_"
    basename = os.path.basename(path)
    basename = basename.split(".")[0]
    page_id = basename.replace(template, "")
    return page_id

            
async def main():
    # url = "https://vn.investing.com/news/stock-market-news/2001-doc-gi-truoc-gio-giao-dich-chung-khoan-2514598"
    # cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{quote(target_url)}"
    
    scroller = PlaywrightScrolling()
    await scroller.initialize()
    
    #-- Configuration
    time_wait = 0.5
    
    #-- Parsing news
    # page_urls_dir = r"C:\APAC\all_projects\finetuning-airflow-project\projects\newest_crawl\save_news_urls"
    page_urls_dir = r"F:\UNIVERSITY\Project\Sentiment-Analysis-Airflow\Financial-Sentiment-Analysis\projects\newest_crawl\save_news_urls"
    page_urls_paths = [os.path.join(page_urls_dir, file_name) for file_name in os.listdir(page_urls_dir)]
    for page_urls_path in tqdm(page_urls_paths):
        try:
            # save_content_dir = r"C:\APAC\all_projects\finetuning-airflow-project\projects\newest_crawl\save_news_contents"
            save_content_dir = r"F:\UNIVERSITY\Project\Sentiment-Analysis-Airflow\Financial-Sentiment-Analysis\projects\newest_crawl\save_news_contents"
            save_id = get_id_from_path(page_urls_path)
            save_path = os.path.join(save_content_dir, f"all_news_content_{save_id}.json")
            page_urls_json = load_json(page_urls_path)
            
            #~ Gather
            if os.path.isfile(save_path):
                continue
            
            news_urls = []
            news_titles = []
            news_times = []
            for item in page_urls_json:
                news_urls.append(item["item_url"])
                news_titles.append(item["title"])
                news_times.append(item["time"])
                
            tasks = []
            for url in news_urls:
                tasks.append(scroller.get_news_details(url))
                
            news_details = await asyncio.gather(*tasks)
            page_details = [
                {
                    "title": title,
                    "time": time,
                    **detail,
                }
                for title, time, detail in zip(news_titles, news_times, news_details) if detail is not None
            ]
            
            #-- Save parsing news contents
            save_json(
                path=save_path, 
                content=page_details
            )    
        except Exception as e:
            print(f"Error is: {e}")
        await asyncio.sleep(time_wait)
    await scroller.close()


if __name__=="__main__":
    asyncio.run(main())