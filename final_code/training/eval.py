import os
import joblib

import numpy as np
import pandas as pd
from tqdm import tqdm
import seaborn as sns
from transformers import pipeline
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix


def cal_metrics(y_true, y_pred):
    macro_f1score = f1_score(y_true, y_pred, average="macro")
    micro_f1score = f1_score(y_true, y_pred, average="micro")
    accuracy = accuracy_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred)
    return macro_f1score, micro_f1score, accuracy, cm