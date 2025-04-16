from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from google_config import get_gspread_client, get_target_book_info
from typing import Tuple

# === スプレッドシート情報 === #
MASTER_SHEET_NAME = "マスタ"
SHIFT_MIRROR_SHEET_NAME = "勤務シフトmirror"

@st.cache_data(ttl=60)
def load_fixed_end_times(spreadsheet_id: str) -> dict:
    """
    勤務シフトmirrorシートから作業者ごとの固定終業時間を取得（キャッシュあり）。
    """
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(spreadsheet_id).worksheet(SHIFT_MIRROR_SHEET_NAME)
        shift_data = sheet.get_all_records()
        return {
            row.get("氏名"): row.get("終業時間")
            for row in shift_data
            if row.get("氏名") and row.get("終業時間")
        }
    except Exception as e:
        return {}

def get_rows_for_date(sheet, target_date_str):
    # 🔹 A列（日付列）だけを取得（APIリクエスト①）
    date_column = sheet.col_values(1)
    if not date_column or len(date_column) < 2:
        return [], []

    headers = ["日付", "ブック", "作業者", "エリア", "系統", "品種", "開始時間", "作業内容", "指示"]

    # 🔹 一致する行番号（1ベース）を抽出（※ヘッダー行 = 行1 を除外）
    matching_indices = [i + 1 for i, val in enumerate(date_column[1:], start=1) if val == target_date_str]
    if not matching_indices:
        return [], headers

    # 🔹 一括取得の範囲を決定
    start_row = min(matching_indices)
    end_row = max(matching_indices)
    cell_range = f"A{start_row}:I{end_row}"

    # 🔹 一括取得（APIリクエスト②）
    cell_data = sheet.get(cell_range)

    # 🔹 行→辞書変換（列数が足りない場合は補完）
    records = []
    for rel_i, abs_row in enumerate(range(start_row, end_row + 1)):
        if abs_row in matching_indices and rel_i < len(cell_data):
            row = cell_data[rel_i]
            padded_row = row + [""] * (len(headers) - len(row))
            record = dict(zip(headers, padded_row))
            records.append(record)

    return records, headers

def process_all_data(rows, target_str, fixed_end_times):
    tasks_by_worker = {}
    for row in rows:
        name = row.get("作業者", "").strip()
        if not name:
            continue
        tasks_by_worker.setdefault(name, []).append(row)

    for task_list in tasks_by_worker.values():
        task_list.sort(key=lambda r: datetime.strptime(
            f"{target_str} {r.get('開始時間')}", "%Y/%m/%d %H:%M") if r.get("開始時間") else datetime.max)

    records = []
    warnings = []

    for name, task_list in tasks_by_worker.items():
        for i, row in enumerate(task_list):
            start = row.get("開始時間")
            end = row.get("終了時間")

            if not start:
                continue

            try:
                start_dt = datetime.strptime(f"{target_str} {start}", "%Y/%m/%d %H:%M")
            except Exception as e:
                warnings.append(f"開始時間の変換エラー: {e} → {start}")
                continue

            if end:
                try:
                    end_dt = datetime.strptime(f"{target_str} {end}", "%Y/%m/%d %H:%M")
                except Exception as e:
                    warnings.append(f"終了時間の変換エラー: {e} → {end}")
                    continue
            elif i + 1 < len(task_list):
                next_start = task_list[i + 1].get("開始時間")
                try:
                    end_dt = datetime.strptime(f"{target_str} {next_start}", "%Y/%m/%d %H:%M")
                except:
                    end_dt = start_dt + timedelta(hours=1)
            else:
                fixed_end = fixed_end_times.get(name, "17:00")
                try:
                    end_dt = datetime.strptime(f"{target_str} {fixed_end}", "%Y/%m/%d %H:%M")
                except:
                    end_dt = start_dt + timedelta(hours=1)

            if start_dt >= end_dt:
                warnings.append(f"⚠ 作業者「{name}」の開始時間と終了時間が一致または逆転しています → {start} - {end_dt.strftime('%H:%M')}")
                continue

            area = row.get("エリア", "")
            line = row.get("系統", "")
            variety = row.get("品種", "")
            task = row.get("作業内容", "")
            instruction = row.get("指示", "")

            line1 = f"{area} - {line} {variety}".strip()
            line2 = f"{start} {task} {instruction}".strip()
            task_label = f"{line1}<br>{line2}"

            records.append({
                "作業者": name,
                "作業開始": start_dt,
                "作業終了": end_dt,
                "作業内容": task_label,
                "エリア": area,
                "ブック": row.get("ブック", "")
            })

    return pd.DataFrame(records), warnings

def load_gantt_data_for_date(target_date: datetime.date, book_type="全体", area_filter="全体") -> Tuple[pd.DataFrame, list[str], pd.DataFrame]:
    client = get_gspread_client()
    book_info = get_target_book_info("作業指示", target_date)
    sheet = client.open_by_key(book_info["spreadsheet_id"]).worksheet(book_info["sheet_name"])

    target_str = target_date.strftime("%Y/%m/%d")
    rows, _ = get_rows_for_date(sheet, target_str)

    if not rows:
        return pd.DataFrame(), [], pd.DataFrame()

    fixed_end_times = load_fixed_end_times(book_info["spreadsheet_id"])
    full_df, warnings = process_all_data(rows, target_str, fixed_end_times)
    full_df_original = full_df.copy()

    if book_type != "全体":
        full_df = full_df[full_df["ブック"] == book_type]

    if area_filter != "全体":
        full_df = full_df[full_df["エリア"] == area_filter]

    return full_df.copy(), warnings, full_df_original