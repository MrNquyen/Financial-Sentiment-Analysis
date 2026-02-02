import os
import re
import json
import joblib
import asyncio
import pandas as pd
import numpy as np
from tqdm import tqdm
from sklearn import metrics
from collections import Counter
from transformers import pipeline
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, accuracy_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV



class RandomForestModel:
    def __init__(
        self,
        data_path
    ):
        self.df = pd.read_csv(data_path)
        self.df.columns = ["label", "title"]
        
    #-- Preprocessing
    def preprocessing_text(self, text):
        text = text.replace("'s", "")
        text = re.sub(r'[^a-zA-Z0-9\s\.,!?\-\%\$€£]', ' ', text)
        text = clean_text(
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
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
    
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
        return best_model
    
    
    #-- Testing on test set
    def test(self):
        predictions = best_model.predict(self.X_test_transform)
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
        
        
    def sentiment_analysis(texts):
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
    