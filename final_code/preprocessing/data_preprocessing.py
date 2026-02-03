import os
import re
import json
import time
import bm25s
import asyncio
import pandas as pd
import numpy as np
from tqdm import tqdm
from googletrans import Translator


#================= FUNCTION =================
def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        json_content = json.load(file)
        return json_content

def save_json(path, content):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(content, file, ensure_ascii=False, indent=3)
          
def load_npy(path):
    npy_file = np.load(path, allow_pickle=True)
    if hasattr(npy_file, 'item') and npy_file.size == 1:
        return npy_file.item()
    return npy_file


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
    

async def main():
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

