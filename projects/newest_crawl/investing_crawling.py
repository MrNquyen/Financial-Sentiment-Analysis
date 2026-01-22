# Source - https://stackoverflow.com/a
# Posted by ggorlen, modified by community. See post 'Timeline' for change history
# Retrieved 2026-01-20, License - CC BY-SA 4.0

from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm

class Crawler():
    def __init__(self):
        pass
    
    def load_page_url(self, page_id):
        url_template = "https://www.investing.com/equities/nvidia-corp-news/{page_id}"
        url = url_template.format(page_id=page_id)
        return url
    
    def request_url(self, url):
        hdr = {'User-Agent': 'Mozilla/5.0'}
        req = Request(url, headers=hdr)
        res = urlopen(req)
        return res
    
    def get_html_content(self, response):
        return res.read().decode('utf-8')
    
    
    def parse_thumnail_details_in_source(source_content):
        source_soup = BeautifulSoup(source_content)
        all_news_html = source_soup.find_all("div", class_="block w-full sm:flex-1")
        all_news_items = []
        for new_html in tqdm(all_news_html):
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
            all_news_items.append(item)
        return all_news_items
    
    
    def crawling_news_urls(self, page_url):
        response = self.request_url(page_url)
        if response.status==200:
            pass
        else:
            print("Stop ")
        self.get_html_content()
        
    
    