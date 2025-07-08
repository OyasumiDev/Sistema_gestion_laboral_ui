# app/helpers/sort_helpers.py
import pandas as pd 
import flet as ft
from datetime import datetime
from typing import Optional

class SortHelper:
    def __init__(self, default_key: str = "", asc: bool = True):
        self.sort_key = default_key
        self.sort_asc = asc

    def toggle_sort(self, new_key: str):
        if self.sort_key == new_key:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_key = new_key
            self.sort_asc = True

    def get_icon(self, column_key: str) -> str:
        if self.sort_key == column_key:
            return "▲" if self.sort_asc else "▼"
        return "⇅"

    def sort_dataframe(self, df, numeric_columns: list = None):
        if self.sort_key:
            ascending = self.sort_asc
            if numeric_columns and self.sort_key in numeric_columns:
                df[self.sort_key] = pd.to_numeric(df[self.sort_key], errors='coerce')
            df = df.sort_values(by=self.sort_key, ascending=ascending)
        return df
