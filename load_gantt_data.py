from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from google_config import get_gspread_client

# === スプレッドシート情報 === #
MASTER_BOOK_ID = "1qMenVuJtfylLvcuXBTYTfx3z3aLQeHis343XvOGA5KI"
MASTER_SHEET_NAME = "マスタ"
SHIFT_MIRROR_SHEET_NAME = "勤務シフトmirror"

def load_fixed_end_times(sheet) -> dict:
    """
    勤務シフトmirrorシートから作業者ごとの固定終業時間を辞書として返す。
    {"佐藤栄記": "17:00", ...}
    """
    try:
        shift_data = sheet.worksheet(SHIFT_MIRROR_SHEET_NAME).get_all_records()
        return {
            row.get("氏名"): row.get("終業時間")
            for row in shift_data
            if row.get("氏名") and row.get("終業時間")
        }
    except Exception as e:
        print(f"勤務シフトmirrorの取得エラー: {e}")
        return {}

def process_all_data(rows, target_str, fixed_end_times):
    """
    与えられた全データ（フィルタ前）から終了時間処理やラベル構築を行い、
    フィルタ前後の DataFrame 両方を返す。
    """
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

            # ラベル構築（2段組）
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

def load_gantt_data_for_date(target_date: datetime.date, book_type="全体", area_filter="全体") -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    """
    指定された日付・ブック・エリアに基づいて作業データを取得し、
    ガントチャート用のDataFrame、警告リスト、全データ（full_df）を返す。
    """
    client = get_gspread_client()
    book = client.open_by_key(st.secrets["MASTER_BOOK_ID"])
    sheet = book.worksheet(MASTER_SHEET_NAME)
    all_data = sheet.get_all_records()

    fixed_end_times = load_fixed_end_times(book)
    target_str = target_date.strftime("%Y/%m/%d")
    rows = [row for row in all_data if row.get("日付") == target_str]

    full_df, warnings = process_all_data(rows, target_str, fixed_end_times)
    full_df_original = full_df.copy()

    if book_type != "全体":
        full_df = full_df[full_df["ブック"] == book_type]

    if area_filter != "全体":
        full_df = full_df[full_df["エリア"] == area_filter]

    return full_df.copy(), warnings, full_df_original
