import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from load_gantt_data import load_gantt_data_for_date
from load_shift_data import load_shift_data_for_date, find_unassigned_workers

# === ページ設定 === #
st.set_page_config(layout="wide")

# === セッション状態の初期化 === #
if "print_mode" not in st.session_state:
    st.session_state.print_mode = False

# === 印刷用切り替えボタン === #
if st.button("🖥️ 画面切替"):
    st.session_state.print_mode = not st.session_state.print_mode

# === ターゲット日付の設定 === #
target_date_default = datetime.today().date() + timedelta(days=1)
target_date = target_date_default

# === データ取得 === #
with st.spinner("データを読み込み中..."):
    try:
        _, _, full_df_original = load_gantt_data_for_date(target_date_default)
        book_options = ["全体"] + sorted(full_df_original["ブック"].dropna().unique().tolist())
        area_options = ["全体"] + sorted(full_df_original["エリア"].dropna().unique().tolist())
    except Exception:
        full_df_original = None
        book_options = ["全体"]
        area_options = ["全体"]
        st.warning("この日付には予定がありません。別の日付を選択してください。")

# === 印刷モードでない場合のみフィルター表示 === #
if not st.session_state.print_mode:
    with st.expander("🔍 フィルター設定", expanded=True):
        col1, col2, col3 = st.columns([2, 3, 3])
        with col1:
            target_date = st.date_input("📅 表示する日付", value=target_date_default)
        with col2:
            book_type = st.radio("📘 ブック選択", options=book_options, horizontal=True)
        with col3:
            area_filter = st.radio("🗂️ エリア選択", options=area_options, horizontal=True)
else:
    # 印刷モードでは初期値を使用
    book_type = "全体"
    area_filter = "全体"

# === フィルタ適用後のデータ取得 === #
df, warnings, full_df = load_gantt_data_for_date(target_date, book_type=book_type, area_filter=area_filter)

# === タイトルと未割当の表示 === #
if st.session_state.print_mode:
    st.markdown(f"<h2 style='text-align:center'>{target_date.strftime('%Y/%m/%d')} の{book_type}作業指示</h2>", unsafe_allow_html=True)
else:
    spacer1, title_col, popover_col = st.columns([1, 4, 1])
    with title_col:
        st.markdown(f"<h3 style='text-align:center'>{target_date.strftime('%Y/%m/%d')} の{book_type}タイムライン</h3>", unsafe_allow_html=True)
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

# === 警告表示（印刷モードでは非表示） === #
if warnings and not st.session_state.print_mode:
    for w in warnings:
        st.warning(w)

# === チャート描画 === #
if not df.empty:
    fig = go.Figure()
    workers = df["作業者"].unique().tolist()
    worker_ypos = {name: i for i, name in enumerate(workers)}
    bar_height = 0.8

    area_colors = {
        "A-1": "#6baed6", "B-1": "#9ecae1",
        "A-2": "#fc9272", "B-2": "#fcae91",
        "A-3": "#74c476", "B-3": "#a1d99b",
        "A-4": "#ffd92f", "前室": "#a6761d", "選果室": "#984ea3"
    }
    default_color = "#cccccc"
    def get_area_color(area):
        area = area.strip()
        return area_colors.get(area, default_color)

    for _, row in df.iterrows():
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
    if not st.session_state.print_mode:
        st.info("指定された日付の作業データが見つかりませんでした。")
