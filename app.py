import streamlit as st
import json
import re
import anthropic
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# ── 페이지 설정 ───────────────────────────────────────────
st.set_page_config(
    page_title="김태유 진로지도",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f8f9fa; }
.main-title { font-size:26px; font-weight:700; color:#1a1a2e; margin-bottom:4px; }
.sub-title  { font-size:14px; color:#6c757d; margin-bottom:20px; }
.school-card {
    background:white; border-radius:12px; padding:18px;
    box-shadow:0 2px 8px rgba(0,0,0,.07); margin-bottom:12px;
    border-left:4px solid #378ADD;
}
.fit-high { background:#e8f5e9; color:#2e7d32; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.fit-mid  { background:#fff3e0; color:#e65100; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.fit-low  { background:#ffebee; color:#c62828; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.source-link { font-size:11px; color:#378ADD; }
.stTabs [data-baseweb="tab-list"] { gap:8px; }
.stTabs [data-baseweb="tab"] { background:white; border-radius:8px 8px 0 0; padding:8px 20px; font-weight:500; }
.stTabs [aria-selected="true"] { background:#378ADD !important; color:white !important; }
div[data-testid="metric-container"] { background:white; border-radius:10px; padding:12px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
</style>
""", unsafe_allow_html=True)

# ── 학생 프로필 상수 ──────────────────────────────────────
IB_HL = ["화학", "영어A", "히스토리"]
IB_SL = ["한국어", "일본어", "수학"]

ROW_LABELS = {
    "country":      "국가",
    "school":       "학교",
    "major":        "전공",
    "acceptance":   "합격율 (TO/지원자)",
    "fitScore":     "적성 적합도",
    "minIB":        "최소 IB 점수",
    "requirements": "우대조건 (HL/SL 요건)",
    "tuition":      "연간 학비",
    "dorm":         "기숙사 유무",
    "living":       "연간 생활비",
    "scholarship":  "국제학생 장학금",
    "intlRatio":    "국제학생 비율",
    "schedule":     "지원 일정",
    "documents":    "필요 서류",
    "earlyApp":     "얼리 지원 가능",
}

# ── 세션 상태 ────────────────────────────────────────────
if "schools" not in st.session_state:
    st.session_state.schools = []
if "status" not in st.session_state:
    st.session_state.status = ""

# ── AI 데이터 수집 ───────────────────────────────────────
def fetch_school_data(country: str, school: str, major: str, api_key: str) -> dict:
    prompt = f"""You are a university admissions data expert. For the following university and major, provide detailed admissions data for an IB student.

University: {school}
Country: {country or 'Unknown'}
Major/Program: {major}
Student IB Profile: HL Chemistry, HL English A, HL History, SL Korean, SL Japanese, SL Math

Return ONLY a valid JSON object (no markdown, no explanation) with these exact keys:
{{
  "country": "국가명 (한국어)",
  "school": "학교명",
  "major": "전공명",
  "acceptance": "합격율 또는 TO/지원자수 예: ~15% (2023)",
  "fitScore": 숫자 0-100,
  "fitBreakdown": {{
    "chemistry": 숫자 0-100,
    "englishA": 숫자 0-100,
    "history": 숫자 0-100,
    "math": 숫자 0-100,
    "overall": 숫자 0-100
  }},
  "minIB": "최소 요구 IB 점수 예: 38/45",
  "requirements": "HL/SL 특정 과목 요건 설명",
  "tuition": "연간 학비 (현지 통화 및 원화 환산)",
  "dorm": "있음/없음/선택가능",
  "living": "연간 생활비 예상",
  "scholarship": "국제학생 대상 주요 장학금 이름과 금액",
  "intlRatio": "국제학생 비율 예: ~30%",
  "schedule": {{
    "applicationOpen": "YYYY-MM 형식 또는 null",
    "earlyDeadline": "YYYY-MM 형식 또는 null",
    "regularDeadline": "YYYY-MM 형식 또는 null",
    "resultDate": "YYYY-MM 형식 또는 null"
  }},
  "documents": "필요 서류 목록 (쉼표 구분)",
  "earlyApp": "가능/불가/Rolling",
  "sourceUrl": "학교 공식 입학처 URL",
  "sourceNote": "데이터 기준 연도 또는 주의사항"
}}"""

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1200,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    text = ""
    for block in response.content:
        if block.type == "text":
            text += block.text

    cleaned = re.sub(r"```json|```", "", text).strip()
    return json.loads(cleaned)


# ── 헤더 ─────────────────────────────────────────────────
st.markdown('<div class="main-title">🎓 김태유 진로지도</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-title">IB HL: {" · ".join(IB_HL)} &nbsp;|&nbsp; SL: {" · ".join(IB_SL)}</div>',
    unsafe_allow_html=True,
)

# ── API Key 사이드바 ──────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        help="https://console.anthropic.com 에서 발급",
    )
    st.caption("API 키는 브라우저 세션에만 저장되며 서버에 기록되지 않습니다.")
    st.divider()
    st.markdown("**학교 관리**")
    if st.button("🗑️ 전체 삭제", use_container_width=True):
        st.session_state.schools = []
        st.rerun()
    st.divider()
    st.caption(f"등록 학교: **{len(st.session_state.schools)}개**")

# ── 탭 ───────────────────────────────────────────────────
tab_a, tab_b, tab_c = st.tabs(["📋 표 A — 학교 데이터", "📊 표 B — 적성 분석", "📅 표 C — 지원 일정"])


# ════════════════════════════════════════════════════════
# 표 A
# ════════════════════════════════════════════════════════
with tab_a:

    # ── 학교 추가 폼 ────────────────────────────────────
    with st.expander("➕ 학교 추가 (AI 자동 입력)", expanded=(len(st.session_state.schools) == 0)):
        col1, col2, col3 = st.columns([1, 2, 2])
        with col1:
            country_sel = st.selectbox(
                "국가",
                ["", "영국", "미국", "캐나다", "호주", "네덜란드", "독일", "일본", "홍콩", "싱가포르", "기타"],
            )
        with col2:
            school_inp = st.text_input("학교명", placeholder="예: University of Oxford")
        with col3:
            major_inp = st.text_input("전공", placeholder="예: Chemistry")

        fetch_btn = st.button(
            "✨ AI로 데이터 자동 입력",
            type="primary",
            disabled=(not school_inp or not major_inp),
        )

        if fetch_btn:
            if not api_key:
                st.error("사이드바에서 Anthropic API Key를 먼저 입력해주세요.")
            else:
                with st.spinner(f"🔍 {school_inp} — {major_inp} 정보를 검색 중입니다..."):
                    try:
                        data = fetch_school_data(country_sel, school_inp, major_inp, api_key)
                        st.session_state.schools.append(data)
                        st.session_state.status = f"✅ '{data['school']} — {data['major']}' 추가 완료"
                        st.success(st.session_state.status)
                        st.rerun()
                    except Exception as e:
                        fallback = {
                            "country": country_sel or "—", "school": school_inp, "major": major_inp,
                            "acceptance": "—", "fitScore": 50,
                            "fitBreakdown": {"chemistry": 50, "englishA": 50, "history": 50, "math": 50, "overall": 50},
                            "minIB": "—", "requirements": "—", "tuition": "—", "dorm": "—",
                            "living": "—", "scholarship": "—", "intlRatio": "—",
                            "schedule": {"applicationOpen": None, "earlyDeadline": None, "regularDeadline": None, "resultDate": None},
                            "documents": "—", "earlyApp": "—", "sourceUrl": "", "sourceNote": "수동 입력 필요",
                        }
                        st.session_state.schools.append(fallback)
                        st.warning(f"⚠️ 기본 항목으로 추가됨. 일부 데이터는 수동으로 입력하세요. (오류: {e})")
                        st.rerun()

    # ── 데이터 표시 ─────────────────────────────────────
    if not st.session_state.schools:
        st.info("아직 등록된 학교가 없습니다. 위에서 학교를 추가해보세요!")
    else:
        # 요약 메트릭
        scores = [s.get("fitScore", 0) for s in st.session_state.schools]
        ibs = [s.get("minIB", "—") for s in st.session_state.schools]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("등록 학교", f"{len(st.session_state.schools)}개")
        m2.metric("평균 적성 점수", f"{sum(scores)//len(scores)}점" if scores else "—")
        m3.metric("최고 적성 학교", st.session_state.schools[scores.index(max(scores))]["school"] if scores else "—")
        m4.metric("최저 IB 요구 학교", sorted(st.session_state.schools, key=lambda x: x.get("minIB","99/45"))[0]["school"])

        st.divider()

        # 컬럼형 카드 (2열)
        for i in range(0, len(st.session_state.schools), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(st.session_state.schools):
                    break
                s = st.session_state.schools[idx]
                fit = s.get("fitScore", 50)
                fit_cls = "fit-high" if fit >= 70 else ("fit-mid" if fit >= 45 else "fit-low")

                with col:
                    with st.container():
                        hdr_col, del_col = st.columns([5, 1])
                        with hdr_col:
                            st.markdown(f"**{s['school']}** &nbsp; <span class='{fit_cls}'>{fit}점</span>", unsafe_allow_html=True)
                            st.caption(f"{s.get('country','—')} | {s.get('major','—')}")
                        with del_col:
                            if st.button("🗑️", key=f"del_{idx}", help="삭제"):
                                st.session_state.schools.pop(idx)
                                st.rerun()

                        rows = []
                        for key, label in ROW_LABELS.items():
                            if key in ("school", "country", "major", "fitScore"):
                                continue
                            val = s.get(key, "—")
                            if key == "schedule":
                                sc = val if isinstance(val, dict) else {}
                                parts = []
                                if sc.get("applicationOpen"): parts.append(f"접수 {sc['applicationOpen']}")
                                if sc.get("earlyDeadline"):   parts.append(f"얼리 {sc['earlyDeadline']}")
                                if sc.get("regularDeadline"): parts.append(f"마감 {sc['regularDeadline']}")
                                if sc.get("resultDate"):       parts.append(f"결과 {sc['resultDate']}")
                                val = " / ".join(parts) if parts else "—"
                            rows.append({"항목": label, "내용": str(val)})

                        df = pd.DataFrame(rows)
                        st.dataframe(df, hide_index=True, use_container_width=True, height=460)

                        if s.get("sourceUrl"):
                            st.markdown(f"🔗 [공식 입학처]({s['sourceUrl']})  ·  {s.get('sourceNote','')}", unsafe_allow_html=False)
                        elif s.get("sourceNote"):
                            st.caption(s["sourceNote"])
                        st.divider()


# ════════════════════════════════════════════════════════
# 표 B — 적성 분석
# ════════════════════════════════════════════════════════
with tab_b:
    st.subheader("📊 IB 과목 적성 분석")
    st.caption("HL: 화학 · 영어A · 히스토리 / SL: 한국어 · 일본어 · 수학 기반 분석")

    if not st.session_state.schools:
        st.info("표 A에서 학교를 추가하면 분석 그래프가 표시됩니다.")
    else:
        DIMS = ["화학(HL)", "영어A(HL)", "히스토리(HL)", "수학(SL)", "종합"]
        DIM_KEYS = ["chemistry", "englishA", "history", "math", "overall"]
        COLORS = px.colors.qualitative.Set2

        # 레이더 차트 (전체 비교)
        fig_radar = go.Figure()
        for i, s in enumerate(st.session_state.schools):
            bd = s.get("fitBreakdown", {})
            vals = [bd.get(k, s.get("fitScore", 50)) for k in DIM_KEYS]
            vals_closed = vals + [vals[0]]
            dims_closed = DIMS + [DIMS[0]]
            fig_radar.add_trace(go.Scatterpolar(
                r=vals_closed, theta=dims_closed,
                fill="toself", name=f"{s['school']} — {s['major']}",
                line_color=COLORS[i % len(COLORS)], opacity=0.7,
            ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            title="학교별 IB 과목 적합도 레이더 차트",
            height=480, margin=dict(t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        st.divider()

        # 학교별 바 차트
        st.subheader("학교별 상세 적합도")
        for i, s in enumerate(st.session_state.schools):
            bd = s.get("fitBreakdown", {})
            vals = [bd.get(k, s.get("fitScore", 50)) for k in DIM_KEYS]
            overall = vals[-1]
            fit_label = "🟢 높음" if overall >= 70 else ("🟡 보통" if overall >= 45 else "🔴 낮음")

            with st.expander(f"**{s['school']}** — {s['major']}  |  종합 {overall}점 {fit_label}", expanded=(i == 0)):
                fig_bar = go.Figure(go.Bar(
                    x=vals, y=DIMS, orientation="h",
                    marker_color=[COLORS[i % len(COLORS)]] * len(DIMS),
                    text=[f"{v}점" for v in vals], textposition="outside",
                ))
                fig_bar.update_layout(
                    height=280, margin=dict(l=10, r=60, t=10, b=10),
                    xaxis=dict(range=[0, 110], showgrid=True, gridcolor="#f0f0f0"),
                    yaxis=dict(autorange="reversed"),
                    plot_bgcolor="white", paper_bgcolor="white",
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        # 종합 비교 막대
        st.divider()
        st.subheader("전체 학교 종합 점수 비교")
        labels = [f"{s['school']}\n{s['major']}" for s in st.session_state.schools]
        scores_all = [s.get("fitScore", 50) for s in st.session_state.schools]
        bar_colors = ["#378ADD" if sc >= 70 else ("#EF9F27" if sc >= 45 else "#E24B4A") for sc in scores_all]

        fig_cmp = go.Figure(go.Bar(
            x=labels, y=scores_all, marker_color=bar_colors,
            text=[f"{sc}점" for sc in scores_all], textposition="outside",
        ))
        fig_cmp.update_layout(
            height=320, margin=dict(t=20, b=20),
            yaxis=dict(range=[0, 115], title="적성 점수"),
            plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_cmp, use_container_width=True)


# ════════════════════════════════════════════════════════
# 표 C — 지원 일정
# ════════════════════════════════════════════════════════
with tab_c:
    st.subheader("📅 지원 일정 타임라인")

    if not st.session_state.schools:
        st.info("표 A에서 학교를 추가하면 일정이 표시됩니다.")
    else:
        MONTHS = [f"{m}월" for m in range(1, 13)]

        EVENT_TYPES = {
            "applicationOpen": ("접수", "#378ADD"),
            "earlyDeadline":   ("얼리", "#7F77DD"),
            "regularDeadline": ("마감", "#D85A30"),
            "resultDate":      ("결과", "#639922"),
        }

        legend_cols = st.columns(4)
        for col, (etype, (label, color)) in zip(legend_cols, EVENT_TYPES.items()):
            col.markdown(
                f'<span style="background:{color};color:white;padding:3px 10px;border-radius:6px;font-size:12px">{label}</span>',
                unsafe_allow_html=True,
            )

        st.write("")

        for year in [2025, 2026]:
            st.markdown(f"#### {year}년")
            rows = []
            for s in st.session_state.schools:
                sc = s.get("schedule", {}) or {}
                row = {"학교": f"{s['school']} — {s['major']}"}
                for m in range(1, 13):
                    mo = f"{year}-{m:02d}"
                    cell = ""
                    for etype, (label, _) in EVENT_TYPES.items():
                        if sc.get(etype) == mo:
                            cell = label
                            break
                    row[MONTHS[m - 1]] = cell
                rows.append(row)

            df_tl = pd.DataFrame(rows)

            def color_cell(val):
                for etype, (label, color) in EVENT_TYPES.items():
                    if val == label:
                        return f"background-color:{color};color:white;font-weight:600;text-align:center;border-radius:4px"
                return ""

            styled = df_tl.style.applymap(color_cell, subset=MONTHS)
            st.dataframe(styled, use_container_width=True, hide_index=True, height=min(60 + 38 * len(rows), 500))
            st.write("")

        # 마감일 목록
        st.divider()
        st.subheader("📌 마감일 정리")
        deadlines = []
        for s in st.session_state.schools:
            sc = s.get("schedule", {}) or {}
            for etype, (label, color) in EVENT_TYPES.items():
                date = sc.get(etype)
                if date:
                    deadlines.append({
                        "날짜": date, "구분": label,
                        "학교": s["school"], "전공": s["major"],
                    })

        if deadlines:
            df_dl = pd.DataFrame(deadlines).sort_values("날짜").reset_index(drop=True)
            st.dataframe(df_dl, use_container_width=True, hide_index=True)
        else:
            st.caption("일정 데이터가 있는 학교를 추가하면 여기에 정리됩니다.")
