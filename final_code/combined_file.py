import os
import time
import json
import re
import asyncio

import aiohttp
import bm25s
import numpy as np
import pandas as pd
from tqdm import tqdm
from bs4 import BeautifulSoup
from googletrans import Translator
from playwright.async_api import async_playwright
from transformers import pipeline
from vnstock import Quote, Trading
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import RandomizedSearchCV



#---- Load json
def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        json_content = json.load(file)
        return json_content
    
#---- Save json
def save_json(path, content):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(content, file, ensure_ascii=False, indent=3)

#---- Load numpy
def load_npy(path):
    npy_file = np.load(path, allow_pickle=True)
    if hasattr(npy_file, 'item') and npy_file.size == 1:
        return npy_file.item()
    return npy_file


#============== CRAWLING DATA ================
class StockHistoryCrawler():
    def __init__(self, symbol='VNINDEX', source='VCI'):
        self.quote = Quote(symbol=symbol, source=source)
        self.trading = Trading(symbol=symbol, source=source)

    def crawling_history(self, start_date, end_date):
        history_df = self.quote.history(start=start_date, end=end_date)
        history_df["time"] = pd.to_datetime(history_df["time"])
        history_df = history_df[(history_df["time"] >= start_date) & (history_df["time"] <= end_date)]
        return history_df


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


async def crawling():
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
        

#================= TRANSLATOR =================
class EnTranslator:
    def __init__(self, from_lang="vi", to_lang="en"):
        self.from_lang = from_lang
        self.to_lang = to_lang
    
    async def gg_translate(self, sentence):
        async with Translator() as translator:
            result = await translator.translate(sentence, src=self.from_lang, dest=self.to_lang)
            return result

    async def run_gg_translate(self, sentence):
        translated_sentence_result = await self.gg_translate(sentence)
        return translated_sentence_result.text
    
    async def row_translation(self, row_sentences):
        tasks = [self.run_gg_translate(sen) for sen in row_sentences]
        translated_sentences = await asyncio.gather(*tasks)
        return translated_sentences
    
    
#================= PREPROCESSOR =================
class Preprocessor:
    def __init__(self):
        pass
    
    def clean_text(
        self,
        text,
        methods=['rmv_link', 'rmv_punc', 'lower', 'rmv_space'],
        custom_punctuation = '!"#$%&\'()*+,.-:;<=>?@[\\]^_/`{|}~”“',
    ):
        cleaned_text = text
        for method in methods:
            if method == 'rmv_link':
                # Remove link
                cleaned_text = re.sub('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', cleaned_text)
                cleaned_text = "".join(cleaned_text)
            elif method == 'rmv_punc':
                # Remove punctuation
                cleaned_text = re.sub('[%s]' % re.escape(custom_punctuation), '' , cleaned_text)
            elif method == 'lower':
                # Lowercase
                cleaned_text = cleaned_text.lower()
            elif method == 'rmv_space':
                # Remove extra space
                cleaned_text = re.sub(' +', ' ', cleaned_text)
                cleaned_text = cleaned_text.strip()
        return cleaned_text
    
    
    def bm25_retriever(self, query, content, k=12):
        """
            This function retrieve top_k sentence related to query sentence
        """
        corpus = content.split(".")

        #-- Retriever
        retriever = bm25s.BM25(corpus=corpus)
        retriever.index(bm25s.tokenize(corpus))
    
        #-- Retriever all relevant content
        results, scores = retriever.retrieve(bm25s.tokenize(query), k=min(k, len(corpus)))
        return results[0]
    
    
    def preprocessing(self, item):
        item["title"] = self.clean_text(
            text=item["title"],
            custom_punctuation="#$}{!)("
        )

        #-- Date time Processing
        time = item["time"]
        posted_date = item["posted_date"]
        posted_date = posted_date.replace("Ngày đăng", "")
        item["posted_date"] = posted_date.strip()

        #-- Content Processing
        item["main_content"] = item["main_content"].replace("Vietstock - ", "")
        item["main_content"] = item["main_content"].replace("\n", " ")
        item["main_content"] = self.clean_text(
            text=item["main_content"],
            custom_punctuation="#$}{!)("
        )
        item["main_content"] = item["main_content"].replace(item["title"], "")
        
        #-- Retrieve relevant sentence using BM25
        top_k_sentences = self.bm25_retriever(
            query=item["title"],
            content=item["main_content"],
            k=5,
        )   
        for i, sen in enumerate(top_k_sentences):
            item[f"relative_sen_{i}"] = sen
            
        #-- Return item
        return item
    

async def preprocessing_data():
    preprocessor = Preprocessor()
    translator = EnTranslator()

    #-- Configuration
    contents_dir = r"F:\UNIVERSITY\Project\Sentiment-Analysis-Airflow\Financial-Sentiment-Analysis\projects\newest_crawl\save_news_contents"
    save_path = r"F:\UNIVERSITY\Project\Sentiment-Analysis-Airflow\Financial-Sentiment-Analysis\projects\data\save_translation\{id}.npy"
    
    #-- Load data
    all_contents_paths = [os.path.join(contents_dir, name) for name in os.listdir(contents_dir)]
    all_contents_jsons = [load_json(path) for path in tqdm(all_contents_paths)]
    merge_contents_json = [item for items in all_contents_jsons for item in items]
    
    #-- Preprocessing
    processed_merge_contents_json = []
    for idx, item in tqdm(enumerate(merge_contents_json)):
        item = preprocessor.preprocessing(item)
        processed_merge_contents_json.append(item)

    #-- Convert to df
    data = {
        "title": [],
        "posted_date": [],
        "main_content": [],
    }
    for item in processed_merge_contents_json:
        for k in item.keys():
            if k not in data:
                data[k] = []
            data[k].append(item[k])
    df = pd.DataFrame(data)
    df["posted_date"] = pd.to_datetime(df['posted_date'], format='%H:%M %d/%m/%Y')
    df = df.sort_values(["posted_date"], ascending=True)
    columns = df.columns


    #-- Translating
    need_translated_columns = [
        col_name 
        for col_name in columns 
        if ("relative_sen" in col_name)
    ]
    translated_columns = [f"translated_{col_name}" for col_name in need_translated_columns]

    attempts = 3
    for i, rows in tqdm(df.iterrows()):
        row_id = rows["Unnamed: 0"]
        row_save_path = save_path.format(id=row_id)
        if os.path.isfile(row_save_path):
            continue
        rows_values = rows[need_translated_columns].values
        translated_data = {col_name: None for col_name in translated_columns}
        
        #-- Translation
        for attempt in range(attempts):
            try:
                translated_rows = await translator.row_translation(rows_values)
                for i, col_name in enumerate(need_translated_columns):
                    trans_col_name = f"translated_{col_name}"
                    translated_data[trans_col_name] = translated_rows[i]
                    np.save(row_save_path, translated_data)
                break
            except Exception as e:
                print(f"ID: {row_id} - Try: {attempt}")
                print(e)
                time.sleep(2)


#=================== TRAINING AND COMPARE ===============
class RandomForestModel:
    def __init__(
        self,
        data_path
    ):
        self.df = pd.read_csv(data_path)
        self.df.columns = ["label", "title"]


    def clean_text(
        self,
        text,
        methods=['rmv_link', 'rmv_punc', 'lower', 'rmv_space'],
        custom_punctuation = '!"#$%&\'()*+,.-:;<=>?@[\\]^_/`{|}~”“',
    ):
        cleaned_text = text
        for method in methods:
            if method == 'rmv_link':
                # Remove link
                cleaned_text = re.sub('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', cleaned_text)
                cleaned_text = "".join(cleaned_text)
            elif method == 'rmv_punc':
                # Remove punctuation
                cleaned_text = re.sub('[%s]' % re.escape(custom_punctuation), '' , cleaned_text)
            elif method == 'lower':
                # Lowercase
                cleaned_text = cleaned_text.lower()
            elif method == 'rmv_space':
                # Remove extra space
                cleaned_text = re.sub(' +', ' ', cleaned_text)
                cleaned_text = cleaned_text.strip()
        return cleaned_text
        
    #-- Preprocessing
    def preprocessing_text(self, text):
        text = text.replace("'s", "")
        text = re.sub(r'[^a-zA-Z0-9\s\.,!?\-\%\$€£]', ' ', text)
        text = self.clean_text(
            text=text,
            custom_punctuation="#$}{!)(?|-#$%&<=>?@[\\]^_/`{|}~”“"
        )
        return text
    
    def preprocessing_label(self, label):
        label2id = {
            "positive": 1,
            "negative": 0,
            "neutral": 2,
        }
        return label2id[label]
    
    
    #-- Train_test_split
    def df_train_test_split(self, df):
        X, y = df["title"], df["label"]
        self.X_train, self.X_test, self.y_train, self.y_test = self.train_test_split(X, y, test_size=0.2, random_state=42)
        
    
    #-- Feature Extraction
    def feature_embedding(self):
        if not self.vectorizer:
            self.vectorizer = TfidfVectorizer()
        self.X_train_transform = self.vectorizer.fit_transform(self.X_train)
        self.X_test_transform = self.vectorizer.transform(self.X_test)
    
    
    #-- Training
    def train(self):
        param_grid = {
            'n_estimators': [100, 200],
            'max_depth': [None, 10, 20, 30, 40, 50],
            'min_samples_split': [2, 5],
            'max_features': ["sqrt", "log2"],
            'min_samples_leaf': [1, 2],
            'bootstrap': [True, False]
        }
        random_search = RandomizedSearchCV(
            RandomForestClassifier(),
            param_grid
        )
        random_search.fit(self.X_train_transform, self.y_train)
        self.best_model = random_search.best_estimator_
    
    
    #-- Testing on test set
    def test(self):
        predictions = self.best_model.predict(self.X_test_transform)
        return predictions
     
    
    
#============== FINBERT ===============
class FinBert:
    def __init__(self, data_path):
        self.load_model()
        self.df = pd.read_csv(data_path)
        self.device = "cpu"

    def load_model(self):
        """
            Load FinBERT model
        """
        self.pipe = pipeline("text-classification", model="ProsusAI/finbert").to(self.device)
        
        
    def sentiment_analysis(self, texts):
        """
        Running FinBERT sentiment analysis

        Args:
            texts (list): list of texts

        Returns:
            list: 
        """
        label2id = {"negative": 0, "positive": 1, "neutral": 2}
        max_length = 512
        results = self.pipe(
            texts,
            truncation=True,
            max_length=max_length,
            padding=True,
            batch_size=16
        )
        labels = [item["label"] for item in results]
        scores = [item["score"] for item in results]
        
        label_ids = [str(label2id[label]) for label in labels]
        return label_ids, scores
    

def training_and_testing():
    data_path = r"F:\UNIVERSITY\Project\Sentiment-Analysis-Airflow\Financial-Sentiment-Analysis\project_2_training\data\all-data.csv"
    rf_model = RandomForestModel(data_path)
    rf_model = rf_model.train()
    pred = rf_model.test()
    return pred


#=============== MAIN ====================
if __name__=="__main__":
    asyncio.run(crawling())
    print("Crawling completed!")
    
    asyncio.run(preprocessing_data())
    print("Preprocessing completed!")
    
    training_and_testing()
    print("Training and testing completed!")










