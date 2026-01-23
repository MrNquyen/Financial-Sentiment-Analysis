# Source - https://stackoverflow.com/a
# Posted by ggorlen, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-20, License - CC BY-SA 4.0

from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
import pandas as pd
import os
import json
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
    
    def request_url(self, url):
        hdr = {'User-Agent': 'Mozilla/5.0'}
        req = Request(url, headers=hdr)
        res = urlopen(req)
        return res
    
    def get_html_content(self, response):
        return response.read().decode('utf-8')
    
    
    def parse_news_details_in_page(self, source_content):
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
    
    
    def crawling_news_urls(self, page_url):
        response = self.request_url(page_url)
        if response.status==200:
            html_content = self.get_html_content(response=response)
            page_news_items = self.parse_news_details_in_page(source_content=html_content)
            return page_news_items
        else:
            print("Page doesn't exist")
            return []
        

if __name__=="__main__":
    crawler = Crawler()
    all_news_items = []
    max_pages = 10001
    # max_pages = 1
    for page_id in tqdm(range(max_pages)):
        page_url = crawler.get_page_url(page_id=page_id+1)
        save_path = rf"C:\APAC\all_projects\finetuning-airflow-project\projects\newest_crawl\save\all_news_item_{page_id}.json"
        if os.path.isfile(save_path):
            continue
        
        page_news_items = crawler.crawling_news_urls(page_url=page_url)
        all_news_items.extend(page_news_items)
        if not page_news_items:
            print("Stop Crawling")
            break
        
        save_json(
            path=save_path,
            content=page_news_items
        )
        time.sleep(0.5)
        
    
    