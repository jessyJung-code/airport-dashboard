from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


DATA_PATH = Path("IOC_event_23-25.xlsx")

YEAR_COLOR = {"2023": "#378ADD", "2024": "#1D9E75", "2025": "#BA7517"}
PALETTE = ["#378ADD", "#EF9F27", "#1D9E75", "#E24B4A", "#7F77DD", "#D85A30", "#888780", "#D4537E"]
LOC_COLORS = ["#378ADD", "#1D9E75", "#EF9F27", "#E24B4A", "#7F77DD"]

MAJOR_GRADES = ["일반", "관심", "주의", "경계", "심각"]
TIME_BINS = [-1, 3, 7, 11, 15, 19, 23]
TIME_LABELS = ["00-03시", "04-07시", "08-11시", "12-15시", "16-19시", "20-23시"]
TOP_LOCS = ["제1여객터미널", "제2여객터미널", "기동지역및이동지역", "탑승동A", "부대건물"]
TOP_N_CLASS = 10

SHEET_MAP = {
    "2023": "23년도 사건사고 데이터",
    "2024": "24년도 사건사고 데이터",
    "2025": "25년도 사건사고 데이터",
}


st.set_page_config(
    page_title="공항 비정상 상황 사건사고 대시보드",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data
def load_data(filepath: Path) -> Dict[str, pd.DataFrame]:
    xl = pd.read_excel(filepath, sheet_name=None)
    frames: Dict[str, pd.DataFrame] = {}
    for year, sheet in SHEET_MAP.items():
        if sheet not in xl:
            st.error(f"❌ '{sheet}' 시트를 찾을 수 없습니다. 파일을 확인해 주세요.")
            st.stop()
        df = xl[sheet].copy()
        date_col = "발생일시▼" if "발생일시▼" in df.columns else "발생일시"
        df["발생일시_dt"] = pd.to_datetime(df[date_col], errors="coerce")
        df["월"] = df["발생일시_dt"].dt.month
        df["hour"] = df["발생일시_dt"].dt.hour
        df["time_block"] = pd.cut(df["hour"], bins=TIME_BINS, labels=TIME_LABELS)
        df["위기대"] = df["위기유형"].str.split(">").str[0].str.strip()
        df["위치대"] = df["발생위치(대/중/소)"].str.split(">").str[0].str.strip()
        df["grade_grp"] = df["이벤트등급"].apply(lambda x: x if x in MAJOR_GRADES else "기타")
        frames[year] = df
    return frames


def _delta_str(current: int, base: int) -> tuple[str, str]:
    """(delta 문자열, delta_color) 반환 — base=0 이면 비교 불가."""
    if base == 0:
        return "기준 연도", "off"
    diff = current - base
    rate = diff / base * 100
    arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "")
    sign  = "+" if diff > 0 else ""
    label = f"{arrow} {sign}{diff:,}건 ({sign}{rate:.1f}%)"
    color = "normal" if diff >= 0 else "inverse"
    return label, color


def render_kpi(
    df_cur: pd.DataFrame,
    year: str,
    base_year: Optional[str],
    frames: Dict[str, pd.DataFrame],
) -> None:
    """KPI 카드 4개 — base_year 대비 증감률 표시."""
    col_accent = YEAR_COLOR[year]
    total = len(df_cur)
    g_general       = int((df_cur["grade_grp"] == "일반").sum())
    g_interest      = int((df_cur["grade_grp"] == "관심").sum())
    g_above_caution = int(df_cur["grade_grp"].isin(["주의", "경계", "심각"]).sum())

    # 기준 연도 데이터
    if base_year and base_year != year and base_year in frames:
        df_base        = frames[base_year]
        base_total     = len(df_base)
        base_general   = int((df_base["grade_grp"] == "일반").sum())
        base_interest  = int((df_base["grade_grp"] == "관심").sum())
        base_above     = int(df_base["grade_grp"].isin(["주의", "경계", "심각"]).sum())
        base_label     = f"vs {base_year}"
    else:
        base_total = base_general = base_interest = base_above = 0
        base_label = "기준 연도"

    d_total,   c_total   = _delta_str(total,           base_total)
    d_general, c_general = _delta_str(g_general,       base_general)
    d_inter,   c_inter   = _delta_str(g_interest,      base_interest)
    d_above,   c_above   = _delta_str(g_above_caution, base_above)

    # base_year == year 이면 모두 "기준 연도"
    if not base_year or base_year == year:
        d_total = d_general = d_inter = d_above = "기준 연도"

    # 색상 구분 레이블 (헤더에 기준연도 표기)
    compare_note = f"&nbsp;`vs {base_year}`" if base_year and base_year != year else ""
    st.markdown(
        f"<span style='font-size:13px;color:gray;'>기준 연도 비교{compare_note}</span>",
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 발생 건수", f"{total:,}건",           d_total)
    k2.metric("일반 등급",   f"{g_general:,}건",        d_general)
    k3.metric("관심 등급",   f"{g_interest:,}건",       d_inter)
    k4.metric("주의 이상",   f"{g_above_caution:,}건",  d_above)


def render_year(
    df: pd.DataFrame,
    year: str,
    base_year: Optional[str],
    frames: Dict[str, pd.DataFrame],
) -> None:
    col = YEAR_COLOR[year]

    # ── AOMS 분류 필터 ────────────────────────────────────────
    AOMS_COL = "AOMS 내 분류"
    aoms_options = ["전체"]
    if AOMS_COL in df.columns:
        aoms_options += sorted(df[AOMS_COL].dropna().unique().tolist())

    fa, fb = st.columns([2, 8])
    with fa:
        aoms_filter = st.radio(
            "🔍 AOMS 분류",
            options=aoms_options,
            horizontal=True,
            key=f"aoms_{year}",
            help="'이벤트' 또는 '상황'만 선택하면 해당 분류 데이터만 모든 차트에 반영됩니다.",
        )

    # 필터 적용 — 이후 모든 차트는 필터된 df 사용
    if aoms_filter != "전체" and AOMS_COL in df.columns:
        df = df[df[AOMS_COL] == aoms_filter].copy()

    # 필터 결과 요약 배지
    with fb:
        total_all = len(frames[year])
        filtered_n = len(df)
        badge_color = (
            "#378ADD" if aoms_filter == "전체"
            else "#1D9E75" if aoms_filter == "이벤트"
            else "#E24B4A"
        )
        st.markdown(
            f"<div style='margin-top:6px;'>"
            f"<span style='background:{badge_color}22;color:{badge_color};"
            f"border:1px solid {badge_color}66;border-radius:12px;"
            f"padding:3px 12px;font-size:13px;font-weight:500;'>"
            f"{'전체' if aoms_filter == '전체' else aoms_filter} &nbsp;"
            f"<b>{filtered_n:,}건</b>"
            f"{'&nbsp;/ 전체 ' + f'{total_all:,}건' if aoms_filter != '전체' else ''}"
            f"</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── KPI ──────────────────────────────────────────────────
    render_kpi(df, year, base_year, frames)
    st.markdown("---")

    # ── ① 월별  /  ② 등급 도넛 ──────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### ① 월별 발생 건수")
        monthly = df.groupby("월").size().reindex(range(1, 13), fill_value=0).reset_index()
        monthly.columns = ["월", "건수"]
        monthly["월명"] = monthly["월"].apply(lambda x: f"{x}월")
        fig1 = px.bar(monthly, x="월명", y="건수", color_discrete_sequence=[col], text="건수")
        fig1.update_traces(textposition="outside", textfont_size=11)
        fig1.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=10), showlegend=False,
            xaxis=dict(title="", tickfont=dict(size=11)),
            yaxis=dict(title="건수", tickfont=dict(size=11)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig1.update_xaxes(showgrid=False)
        fig1.update_yaxes(gridcolor="rgba(128,128,128,0.12)")
        st.plotly_chart(fig1, use_container_width=True)

    with c2:
        st.markdown("##### ② 이벤트 등급 분포")
        grade_cnt = df["이벤트등급"].value_counts().reset_index()
        grade_cnt.columns = ["등급", "건수"]
        fig2 = px.pie(grade_cnt, names="등급", values="건수", color_discrete_sequence=PALETTE, hole=0.55)
        fig2.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
        fig2.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=10), showlegend=True,
            legend=dict(orientation="v", font=dict(size=10)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── ③ 위기유형  /  ④ 위치 ────────────────────────────────
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("##### ③ 위기 유형 분포")
        crisis_cnt = df["위기대"].value_counts().reset_index()
        crisis_cnt.columns = ["유형", "건수"]
        fig3 = px.pie(crisis_cnt, names="유형", values="건수", color_discrete_sequence=PALETTE, hole=0.55)
        fig3.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
        fig3.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=10), showlegend=True,
            legend=dict(orientation="v", font=dict(size=10)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig3, use_container_width=True)

    with c4:
        st.markdown("##### ④ 발생 위치 Top 8")
        loc_cnt = df["위치대"].value_counts().head(8).reset_index()
        loc_cnt.columns = ["위치", "건수"]
        fig4 = px.bar(
            loc_cnt, y="위치", x="건수", orientation="h",
            color_discrete_sequence=[col], text="건수",
        )
        fig4.update_traces(textposition="outside", textfont_size=11)
        fig4.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=10), showlegend=False,
            yaxis=dict(title="", tickfont=dict(size=11), categoryorder="total ascending"),
            xaxis=dict(title="건수", tickfont=dict(size=11)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig4.update_xaxes(gridcolor="rgba(128,128,128,0.12)")
        fig4.update_yaxes(showgrid=False)
        st.plotly_chart(fig4, use_container_width=True)

    # ── ⑤ 시간대 꺾은선  /  ⑥ 시간대×위치 ──────────────────
    c5, c6 = st.columns(2)
    with c5:
        st.markdown("##### ⑤ 시간대별 발생 건수 (0~23시)")
        hourly = df.groupby("hour").size().reindex(range(24), fill_value=0).reset_index()
        hourly.columns = ["시간", "건수"]
        hourly["시간명"] = hourly["시간"].apply(lambda x: f"{x}시")
        fill_col = (
            "rgba(55,138,221,0.20)" if col == "#378ADD"
            else "rgba(29,158,117,0.20)" if col == "#1D9E75"
            else "rgba(186,117,23,0.20)"
        )
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(
            x=hourly["시간명"], y=hourly["건수"],
            mode="lines+markers",
            line=dict(color=col, width=2.5),
            marker=dict(size=5, color=col),
            fill="tozeroy", fillcolor=fill_col, name="건수",
        ))
        fig5.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=10), showlegend=False,
            xaxis=dict(
                title="", tickfont=dict(size=10), tickmode="array",
                tickvals=[hourly["시간명"].iloc[i] for i in range(0, 24, 4)],
            ),
            yaxis=dict(title="건수", tickfont=dict(size=11)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig5.update_xaxes(showgrid=False)
        fig5.update_yaxes(gridcolor="rgba(128,128,128,0.12)")
        st.plotly_chart(fig5, use_container_width=True)

    with c6:
        st.markdown("##### ⑥ 시간대 구간 × 주요 위치")
        tb_loc = (
            df[df["위치대"].isin(TOP_LOCS)]
            .groupby(["time_block", "위치대"], observed=True)
            .size().reset_index(name="건수")
        )
        fig6 = px.bar(
            tb_loc, x="time_block", y="건수", color="위치대",
            color_discrete_sequence=LOC_COLORS, barmode="stack",
        )
        fig6.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
            xaxis=dict(title="", tickfont=dict(size=10)),
            yaxis=dict(title="건수", tickfont=dict(size=11)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig6.update_xaxes(showgrid=False)
        fig6.update_yaxes(gridcolor="rgba(128,128,128,0.12)")
        st.plotly_chart(fig6, use_container_width=True)

    # ── ⑦ 시간대×위기유형  /  ⑧ 시간대×등급 ─────────────────
    c7, c8 = st.columns(2)
    with c7:
        st.markdown("##### ⑦ 시간대 구간 × 위기 유형")
        tb_crisis = (
            df.groupby(["time_block", "위기대"], observed=True)
            .size().reset_index(name="건수")
        )
        fig7 = px.bar(
            tb_crisis, x="time_block", y="건수", color="위기대",
            color_discrete_sequence=PALETTE, barmode="stack",
        )
        fig7.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
            xaxis=dict(title="", tickfont=dict(size=10)),
            yaxis=dict(title="건수", tickfont=dict(size=11)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig7.update_xaxes(showgrid=False)
        fig7.update_yaxes(gridcolor="rgba(128,128,128,0.12)")
        st.plotly_chart(fig7, use_container_width=True)

    with c8:
        st.markdown("##### ⑧ 시간대 구간 × 이벤트 등급")
        grade_order = ["일반", "관심", "주의", "경계", "심각", "기타"]
        tb_grade = (
            df.groupby(["time_block", "grade_grp"], observed=True)
            .size().reset_index(name="건수")
        )
        tb_grade["grade_grp"] = pd.Categorical(
            tb_grade["grade_grp"], categories=grade_order, ordered=True
        )
        tb_grade = tb_grade.sort_values("grade_grp")
        fig8 = px.bar(
            tb_grade, x="time_block", y="건수", color="grade_grp",
            color_discrete_sequence=PALETTE, barmode="stack",
            category_orders={"grade_grp": grade_order},
        )
        fig8.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(title="등급", orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
            xaxis=dict(title="", tickfont=dict(size=10)),
            yaxis=dict(title="건수", tickfont=dict(size=11)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig8.update_xaxes(showgrid=False)
        fig8.update_yaxes(gridcolor="rgba(128,128,128,0.12)")
        st.plotly_chart(fig8, use_container_width=True)

    # ── ⑨ 분류기준 Top N  /  ⑩ 분류기준×시간대 히트맵 ────────
    st.markdown("---")
    c9, c10 = st.columns(2)

    with c9:
        st.markdown(f"##### ⑨ 분류 기준별 발생 건수 Top {TOP_N_CLASS}")
        cls_cnt = df["분류 기준"].value_counts().head(TOP_N_CLASS).reset_index()
        cls_cnt.columns = ["분류 기준", "건수"]
        cls_cnt = cls_cnt.sort_values("건수", ascending=True)
        fig9 = px.bar(
            cls_cnt, y="분류 기준", x="건수", orientation="h",
            color_discrete_sequence=[col], text="건수",
        )
        fig9.update_traces(textposition="outside", textfont_size=10)
        fig9.update_layout(
            height=380, margin=dict(t=10, b=10, l=10, r=60), showlegend=False,
            yaxis=dict(title="", tickfont=dict(size=10)),
            xaxis=dict(title="건수", tickfont=dict(size=11)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig9.update_xaxes(gridcolor="rgba(128,128,128,0.12)")
        fig9.update_yaxes(showgrid=False)
        st.plotly_chart(fig9, use_container_width=True)

    with c10:
        st.markdown(f"##### ⑩ 분류 기준별 × 시간대 발생 건수 (Top {TOP_N_CLASS} 히트맵)")
        top_classes = df["분류 기준"].value_counts().head(TOP_N_CLASS).index.tolist()
        df_top = df[df["분류 기준"].isin(top_classes)].copy()
        heatmap_df = (
            df_top.groupby(["분류 기준", "time_block"], observed=True)
            .size().reset_index(name="건수")
        )
        pivot = (
            heatmap_df.pivot(index="분류 기준", columns="time_block", values="건수")
            .reindex(columns=TIME_LABELS).fillna(0).astype(int)
        )
        pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=True).index]
        colorscale = {"#378ADD": "Blues", "#1D9E75": "Greens", "#BA7517": "Oranges"}.get(col, "Blues")
        fig10 = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=colorscale,
            text=pivot.values,
            texttemplate="%{text}",
            textfont=dict(size=10),
            hoverongaps=False,
            showscale=True,
            colorbar=dict(thickness=12, len=0.8, tickfont=dict(size=10)),
        ))
        fig10.update_layout(
            height=380, margin=dict(t=10, b=10, l=10, r=10),
            xaxis=dict(title="", tickfont=dict(size=10), side="bottom"),
            yaxis=dict(title="", tickfont=dict(size=10)),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig10, use_container_width=True)

    # ── 원시 데이터 ───────────────────────────────────────────
    with st.expander(f"📄 {year}년 원시 데이터 보기"):
        disp_cols = ["발생일시_dt", "이벤트명칭", "이벤트등급", "위기대", "위치대", "분류 기준"]
        disp_cols = [c for c in disp_cols if c in df.columns]
        st.dataframe(
            df[disp_cols].rename(columns={"발생일시_dt": "발생일시"}),
            use_container_width=True, height=300,
        )


# ── 파일 존재 확인 ───────────────────────────────────────────
if not DATA_PATH.exists():
    st.error(
        f"❌ 데이터 파일을 찾을 수 없습니다.\n\n경로: `{DATA_PATH}`\n\n"
        "파일 위치를 확인하고 `DATA_PATH` 변수를 수정해 주세요."
    )
    st.stop()

# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ✈️ 공항 사건사고")
    st.markdown("---")
    st.markdown("**데이터 파일**")
    st.code(str(DATA_PATH), language=None)
    st.markdown("**분석 기간**")
    st.markdown("2023년 1월 ~ 2025년 12월")
    st.markdown("**총 사건 건수**")
    st.markdown("**14,699건**")

# ── 데이터 로드 ──────────────────────────────────────────────
with st.spinner("데이터를 불러오는 중..."):
    frames = load_data(DATA_PATH)

# ── 헤더 + 기준 연도 선택 ────────────────────────────────────
st.markdown("## ✈️ 공항 비정상 상황 사건사고 대시보드 (2023~2025)")

all_years = list(SHEET_MAP.keys())   # ["2023", "2024", "2025"]

col_title, col_selector = st.columns([3, 1])
with col_selector:
    base_year = st.selectbox(
        "📊 KPI 비교 기준 연도",
        options=all_years,
        index=0,                          # 기본값: 2023
        help="선택한 연도 대비 증감 건수와 증감률을 KPI 카드에 표시합니다.",
    )

st.markdown("---")

# ── 연도별 탭 렌더링 ─────────────────────────────────────────
tab2023, tab2024, tab2025 = st.tabs(["📋 2023년", "📋 2024년", "📋 2025년"])

with tab2023:
    render_year(frames["2023"], "2023", base_year, frames)
with tab2024:
    render_year(frames["2024"], "2024", base_year, frames)
with tab2025:
    render_year(frames["2025"], "2025", base_year, frames)

st.markdown("---")
st.markdown(
    "<div style='text-align:center;font-size:12px;color:gray;'>"
    " @ Copyright 2026. Incheon International Airport Corporation 정책연구팀. All rights reseved. "
    "※ 출처: IOC, 공항 비정상 상황 사건사고 데이터 (2023.01~2025.12)"
    "</div>",
    unsafe_allow_html=True,
)