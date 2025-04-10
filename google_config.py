import streamlit as st
import gspread
import json
from datetime import datetime, date

def get_gspread_client():
    credentials_dict = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"])
    return gspread.service_account_from_dict(credentials_dict)

# 指定したブック名と日付から、GSSIDブックの中から有効な書き込み先を取得
def get_target_book_info(book_type: str, target_date: date) -> dict:
    client = get_gspread_client()
    
    # GSSIDシートを開く
    gssid_book = client.open_by_key("1_IC8ykDpc91eUjfi9muJEjF8W4hE4y5SuxSyWvTGrKI")
    gssid_sheet = gssid_book.worksheet("GSSID")
    records = gssid_sheet.get_all_records()

    for row in records:
        if row["ブック"] == book_type:
            try:
                start = datetime.strptime(row["開始日"], "%Y/%m/%d").date()
                end = datetime.strptime(row["終了日"], "%Y/%m/%d").date()
                if start <= target_date <= end:
                    return {
                        "spreadsheet_id": row["ID"],
                        "sheet_name": row["シート"],
                        "range": row["範囲"]
                    }
            except Exception as e:
                print(f"日付の解析に失敗しました: {e}")
                continue

    raise ValueError(f"{book_type} に対応する有効なブックが見つかりません。")
