# data_loader.py - Data loading and processing functions

import pandas as pd
from app.core.config import MAX_COLLEGES

def load_csv(file_path):
    """Load college data from CSV file"""
    return pd.read_csv(file_path)

def get_colleges_to_process(df, limit=None):
    """Get colleges to process, optionally limited to first N"""
    if limit is None:
        limit = MAX_COLLEGES
    return df.head(limit)

def validate_csv_columns(df):
    """Validate that required columns exist in the CSV"""
    required_columns = ['College Name', 'Weblink']
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns in CSV: {missing_columns}")

    return True