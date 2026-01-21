import os
import bs4
import json
import requests

#========= FUNCTIONS ==========
def request_html(url):
    response = requests.get(url)
    return response


def load_url(page_id):
    url_template = "https://www.investing.com/equities/nvidia-corp-news/{page_id}"
    return url_template.format(page_id=page_id)


def parse_new_url(html_content):
    return


#========= MAIN ==========
if __name__=="__main__":
    #-- Load all pages
    i = 1
    while True:
        page_url = load_url(i)
        response = request_html(page_url)
        if not response.status_code == 200:
            break
        i += 1
        
        


