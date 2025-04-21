import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
from pytz import timezone  # 追加
from load_gantt_data import load_gantt_data_for_date
from load_shift_data import load_shift_data_for_date, find_unassigned_workers
from google_config import get_target_book_info

# === ページ設定 === #
st.set_page_config(layout="wide")

# === セッションステートに target_date を保存（日本時間で） === #
japan = timezone("Asia/Tokyo")
if "target_date" not in st.session_state:
    st.session_state.target_date = datetime.now(japan).date()

# === 先にカラム設定 target_date を定義しておく === #
date_col, title_col, popover_col = st.columns([1, 4, 1])
with date_col:
    st.session_state.target_date = st.date_input("📅 表示する日付", value=st.session_state.target_date)
target_date = st.session_state.target_date

# === GSSIDからマスタのスプレッドシート情報を取得 === #
try:
    master_info = get_target_book_info("作業指示", target_date)
    master_spreadsheet_id = master_info["spreadsheet_id"]
    master_sheet_name = master_info["sheet_name"]
except Exception as e:
    st.error(f"マスタブックの取得に失敗しました: {e}")
    st.stop()

# === 初回データ読み込み（フィルタ候補決定） === #
try:
    with st.spinner("データを読み込み中..."):
        _, _, full_df_original = load_gantt_data_for_date(
            target_date,
            book_type="全体",
            area_filter="全体"
        )

    if full_df_original.empty:
        st.warning("指定された日付に対応するデータが存在しません")
        st.stop()

    book_options = ["全体"] + sorted(full_df_original["ブック"].dropna().unique().tolist())
    area_options = ["全体"] + sorted(full_df_original["エリア"].dropna().unique().tolist())

except Exception as e:
    st.error(f"データ読み込みに失敗しました: {e}")
    st.stop()

# === 日付後の残りのフィルター設定 === #
with st.expander("🔍 フィルター設定", expanded=True):
    col1, col2 = st.columns([1, 1])
    with col1:
        book_type = st.radio("📘 ブック選択", options=book_options, horizontal=True)
    with col2:
        area_filter = st.radio("🧭 エリア選択", options=area_options, horizontal=True)

# === フィルタ適用データ取得 === #
df, warnings, full_df = load_gantt_data_for_date(target_date, book_type=book_type, area_filter=area_filter)

with title_col:
    area_suffix = f"（{area_filter}）" if area_filter != "全体" else ""
    st.markdown(
        f"<h3 style='text-align:center'>{target_date.strftime('%Y/%m/%d')} の{book_type}タイムライン{area_suffix}</h3>",
        unsafe_allow_html=True
    )

with popover_col:
    with st.popover("未割当の作業者を表示"):
        working_names = load_shift_data_for_date(target_date)
        assigned_names = df["作業者"].unique().tolist() if not df.empty else []
        unassigned = find_unassigned_workers(full_df, working_names)

        if unassigned:
            st.error("未割当の作業者:")
            for name in unassigned:
                st.write(f"・{name}")
        else:
            st.success("全員に作業が割り当てられています！")

# === 警告表示 === #
if warnings:
    for w in warnings:
        st.warning(w)

# === チャート描画 === #
if not df.empty:
    fig = go.Figure()
    workers = df["作業者"].unique().tolist()
    worker_ypos = {name: i for i, name in enumerate(workers)}
    bar_height = 0.8

    area_colors = {
        "A-1": "#80C8FF",
        "B-1": "#B3DEFF",
        "A-2": "#FF9999",
        "B-2": "#FFCCCC",
        "A-3": "#AADDAA",
        "B-3": "#CCFFCC",
        "A-4": "#FFEB3B",
        "前室": "#E0C68C",
        "選果室": "#A3B7FF",
        "機械室": "#CCCCCC",
        "休憩室": "#FFFFFF",
        "事務室": "#FFCC99"
    }

    default_color = "#ffffff"
    def get_area_color(area):
        return area_colors.get(area.strip(), default_color)

    for _, row in df.iterrows():
        print(row)  # 👈 まずはこれで休憩が存在しているか確認
        name = row["作業者"]
        y_center = worker_ypos[name]
        y0 = y_center - bar_height / 2
        y1 = y_center + bar_height / 2
        start = row["作業開始"]
        end = row["作業終了"]
        area = row.get("エリア", "")
        color = get_area_color(area)

        fig.add_trace(go.Scatter(
            x=[start, end, end, start, start],
            y=[y0, y0, y1, y1, y0],
            fill="toself",
            mode="lines",
            fillcolor=color,
            line=dict(color="black", width=1),
            hoverinfo="text",
            text=row["作業内容"],
            name=""
        ))

        mid_time = start + (end - start) / 2
        fig.add_trace(go.Scatter(
            x=[mid_time],
            y=[y_center],
            mode="text",
            text=[row["作業内容"]],
            textposition="middle center",
            textfont=dict(size=14, color="black"),
            showlegend=False,
            hoverinfo="skip"
        ))

    fig.update_yaxes(
        tickvals=list(worker_ypos.values()),
        ticktext=list(worker_ypos.keys()),
        title="",
        showgrid=True,
        gridcolor="LightGray",
        tickfont=dict(size=16, color="black")
    )

    start_range = full_df["作業開始"].min()
    end_range = full_df["作業終了"].max()
    fig.update_xaxes(
        type='date',
        range=[start_range, end_range],
        tickformat="%H:%M",
        dtick=3600000,
        side="top",
        ticks="inside",
        ticklen=6,
        tickfont=dict(size=16, color="black"),
        showgrid=True,
        gridcolor="LightGray"
    )

    bar_height_px = 60
    min_height = 450
    num_workers = len(workers)
    chart_height = max(min_height, num_workers * bar_height_px)

    fig.update_layout(
        height=chart_height,
        width=1500,
        margin=dict(l=40, r=40, t=60, b=40),
        font=dict(size=14),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("指定された日付の作業データが見つかりませんでした。")
