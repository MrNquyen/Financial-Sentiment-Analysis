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
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, accuracy_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV

#=================== TRAINING AND COMPARE ===============
class BaselineModel:
    def __init__(
        self,
        model_name,
        data_path
    ):
        self.df = pd.read_csv(data_path)
        self.model_name = model_name
        self.df.columns = ["label", "title"]
        self.load_model_class()

    def load_model_class(self):
        if self.model_name=="svc":
            self.model_class = SVC
        elif self.model_name=="lr":
            self.model_class = LogisticRegression
        elif self.model_name=="knn":
            self.model_class = KNeighborsClassifier
        elif self.model_name=="rf":
            self.model_class = RandomForestClassifier

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
            self.model_class(),
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
    