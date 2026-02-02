import os
import re
import json
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


#================= PREPROCESSING FUNCTION =================




#================= TRANSLATOR =================
class Translator:
    def __init__(self, from_lang="vi", to_lang="en"):
        self.from_lang = from_lang
        self.to_lang = to_lang
    
    async def gg_translate(sentence):
        async with Translator() as translator:
            result = await translator.translate(sentence, src=self.from_lang, dest=self.to_lang)
            return result

    async def run_gg_translate(sentence):
        translated_sentence_result = await gg_translate(sentence)
        return translated_sentence_result.text
    
    async def row_translation(row_sentences):
        tasks = [run_gg_translate(sen) for sen in row_sentences]
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
        if "giờ trước" in time:
            continue
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
        top_k_sentences = bm25_retriever(
            query=item["title"],
            content=item["main_content"],
            k=5,
        )   
        for i, sen in enumerate(top_k_sentences):
            item[f"relative_sen_{i}"] = sen
            
        #-- Return item
        return item

    
    
    




