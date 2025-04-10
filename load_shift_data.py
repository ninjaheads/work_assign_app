import streamlit as st
from datetime import datetime
from google_config import get_gspread_client
import pandas as pd

# === シフト表のスプレッドシートID === #
SHIFT_BOOK_ID = "1gl0ayUS_zKN8P-D5DNTNOP96ZUk33FNOvAsKAg9JH9M"

def get_shift_sheet_for_date(target_date: datetime.date) -> str:
    """
    対象日から対応するシート名を返す（例: 2025年4月）
    """
    year = target_date.year
    month = target_date.month
    return f"{year}年{month}月"

def load_shift_data_for_date(target_date: datetime.date) -> list[str]:
    """
    指定された日付に出勤予定の作業者（氏名）リストを返す
    勤務種別が「日勤」のみを出勤とみなす
    """
    client = get_gspread_client()
    sheet_name = get_shift_sheet_for_date(target_date)
    book = client.open_by_key(st.secrets["SHIFT_BOOK_ID"])
    worksheet = book.worksheet(sheet_name)

    all_data = worksheet.get_all_records(head=4)  # 4行目をヘッダーとする

    # Windows互換のため lstrip で先頭ゼロを除去
    target_str = f"{target_date.strftime('%m').lstrip('0')}/{target_date.strftime('%d').lstrip('0')}"
    target_col_prefix = f"{target_str} ("

    # 日付列を特定
    if not all_data or len(all_data[0]) == 0:
        return []

    headers = list(all_data[0].keys())
    date_columns = [col for col in headers if col.startswith(target_col_prefix)]
    if not date_columns:
        return []  # 日付列が見つからない

    date_col = date_columns[0]  # 該当日付列

    # 出勤者を抽出（"日勤" のみ）
    working_names = [
        row["氏名"]
        for row in all_data
        if row.get(date_col) == "日勤" and row.get("氏名")
    ]
    return working_names

def find_unassigned_workers(df: pd.DataFrame, working_names: list[str]) -> list[str]:
    """
    出勤しているが、マスタに割り当てられていない作業者を返す。

    Parameters:
    - df: マスタデータ（その日の作業が入っているデータフレーム）
    - working_names: シフト上の出勤者（名前のリスト）

    Returns:
    - 割り当てられていない作業者の名前リスト
    """
    assigned_names = df["作業者"].dropna().unique().tolist()
    unassigned = [name for name in working_names if name not in assigned_names]
    return unassigned
