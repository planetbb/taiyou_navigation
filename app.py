import streamlit as st
import json
import re
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from google import genai  # 최신 공식 Google GenAI 라이브러리
from google.genai import types

# ── 페이지 설정 ───────────────────────────────────────────
st.set_page_config(
    page_title="김태유 진로지도",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
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
.stTabs [data-baseweb="tab-list"] { gap:8px; }
.stTabs [data-baseweb="tab"] { background:white; border-radius:8px 8px 0 0; padding:8px 20px; font-weight:500; }
.stTabs [aria-selected="true"] { background:#378ADD !important; color:white !important; }
div[data-testid="metric-container"] { background:white; border-radius:10px; padding:12px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
</style>
""", unsafe_allow_html=True)

# ── 학생 프로필 및 라벨 상수 ──────────────────────────────
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

# ── 헬퍼 함수: 안전한 IB 점수 파싱 ───────────────────────
def parse_ib_score(school_dict):
    min_ib = school_dict.get("minIB", "—")
    match = re.search(r"(\d+)", str(min_ib))
    return int(match.group(1)) if match else 99

# ── Gemini 정보 추출 함수 ────────────────────────────────
def fetch_school_data_via_gemini(api_key, country, school, major):
    # 최신 규격 Client 초기화
    client = genai.Client(api_key=api_key)
    
    system_instruction = """You are an expert college admissions consultant. 
Analyze the requested university and major based on the latest 2026/2027 admissions guidelines.
Provide your response strictly in JSON format matching the schema requested. Do not include any explanation outside the JSON object."""

    user_prompt = f"""Target University: {school} in {country}, Major: {major}.
Evaluate suitability assuming the student's IB choices are (HL: 화학, 영어A, 히스토리 / SL: 한국어, 일본어, 수학).

Fill all the fields below accurately based on 2026/2027 international student requirements. 
Return the exact JSON structure:
{{
    "country": "국가명",
    "school": "정확한 학교 영문명",
    "major": "정확한 학과 영문명",
    "acceptance": "합격률 정보 (예: ~15%)",
    "fitScore": 80, 
    "fitBreakdown": {{
        "chemistry": 90,
        "englishA": 80,
        "history": 70,
        "math": 60,
        "overall": 80
    }},
    "minIB": "합격자 평균 또는 최소 요건 IB 점수 (예: 38/45)",
    "requirements": "HL/SL 특정 과목 요구 조건 상세 기술 (한국어로 작성)",
    "tuition": "국제학생 기준 연간 학비 (현지 화폐 및 원화 환산)",
    "dorm": "기숙사 제공 여부 및 조건 (한국어로 작성)",
    "living": "연간 예상 생활비 (한국어로 작성)",
    "scholarship": "국제학생 신청 가능 장학금 종류 (한국어로 작성)",
    "intlRatio": "국제학생 비율 (예: ~30%)",
    "schedule": {{
        "applicationOpen": "YYYY-MM",
        "earlyDeadline": "YYYY-MM", 
        "regularDeadline": "YYYY-MM",
        "resultDate": "YYYY-MM"
    }},
    "documents": "필요 제출 서류 목록 (에세이, 추천서 등 고유 시험 여부 포함)",
    "earlyApp": "얼리 지원 가능 여부 (가능/불가)",
    "sourceUrl": "공식 입학처 웹사이트 주소",
    "sourceNote": "데이터 출처 및 기준 연도 (예: 2026 공식 요강 기준)"
}}"""

    try:
        # Structured Output을 강제하고 실시간 처리에 적합한 gemini-2.5-flash 모델 사용
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json", # JSON 출력 강제 안전장치
                temperature=0.2
            ),
        )
        
        # 받아온 텍스트 데이터를 JSON 객체로 파싱
        result = json.loads(response.text)
        return result
    except Exception as e:
        st.error(f"Gemini API 연동 중 에러가 발생했습니다: {str(e)}")
        return None

# ── 세션 상태 초기화 ──────────────────────────────────────
if "schools" not in st.session_state:
    st.session_state.schools = []

# ── 헤더 및 대시보드 타이틀 ──────────────────────────────
st.markdown('<div class="main-title">🎓 김태유 진로지도 스마트 대시보드 (Gemini 무료판)</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-title">학생 IB 매칭 정보 ── HL: {" · ".join(IB_HL)} | SL: {" · ".join(IB_SL)}</div>',
    unsafe_allow_html=True,
)

# ── 사이드바 ⚙️ 설정 (Gemini API 키 입력창 배치) ────────────────
with st.sidebar:
    st.header("⚙️ API 및 데이터 설정")
    gemini_key = st.text_input("Gemini API Key 입력", type="password", help="AI Studio에서 발급받은 AIzaSy... 키를 입력하세요.")
    if gemini_key:
        st.success("🔑 Gemini API Key 연동 완료")
    else:
        st.warning("⚠️ 자동 스크리닝을 위해 Gemini API 키를 입력해 주세요.")
    
    st.divider()
    if st.button("🗑️ 전체 데이터 초기화", use_container_width=True):
        st.session_state.schools = []
        st.rerun()
    st.caption(f"현재 분석된 대학교: **{len(st.session_state.schools)}개**")

# ── 메인 탭 구성 ──────────────────────────────────────────
tab_a, tab_b, tab_c = st.tabs(["📋 표 A — AI 검색 및 학교 데이터", "📊 표 B — 적성 분석", "📅 표 C — 지원 일정"])

# ════════════════════════════════════════════════════════
# 📋 표 A — Gemini 자동 검색 및 데이터 뷰
# ════════════════════════════════════════════════════════
with tab_a:
    st.subheader("🔍 신규 대학교 실시간 검색 및 스크리닝")
    
    col1, col2, col3 = st.columns([1, 2, 2])
    with col1:
        country_inp = st.text_input("국가", placeholder="예: 영국, 미국")
    with col2:
        school_inp = st.text_input("학교명 (영문 권장)", placeholder="예: UCL, Toronto")
    with col3:
        major_inp = st.text_input("희망 전공 (영문 권장)", placeholder="예: Computer Science, Chemistry")

    search_btn = st.button("🚀 Gemini AI 분석 및 자동 입력 시작", type="primary")

    if search_btn:
        if not gemini_key:
            st.error("사이드바에 Gemini API Key를 먼저 입력해 주세요!")
        elif not (country_inp and school_inp and major_inp):
            st.error("국가, 학교, 학과 항목을 모두 채워야 검색이 가능합니다.")
        else:
            with st.spinner(f"✨ Gemini가 {school_inp} 입학 전형을 실시간 분석 중입니다..."):
                fetched_data = fetch_school_data_via_gemini(gemini_key, country_inp, school_inp, major_inp)
                if fetched_data:
                    st.session_state.schools.append(fetched_data)
                    st.success(f"🎉 {school_inp} ({major_inp}) 데이터 생성 및 반영 성공!")
                    st.rerun()

    st.divider()

    if not st.session_state.schools:
        st.info("💡 국가, 학교, 학과를 기입하고 버튼을 누르면 구글 Gemini가 입학 요강을 추적해 모든 표의 내용을 자동으로 채워줍니다.")
    else:
        # 요약 메트릭 영역
        scores = [s.get("fitScore", 0) for s in st.session_state.schools]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("등록 학교", f"{len(st.session_state.schools)}개")
        m2.metric("평균 적성 매칭도", f"{sum(scores)//len(scores)}점" if scores else "—")
        m3.metric("최우수 매칭 학교", st.session_state.schools[scores.index(max(scores))]["school"] if scores else "—")
        
        sorted_by_ib = sorted(st.session_state.schools, key=parse_ib_score)
        m4.metric("진입 장벽 최저 학교", sorted_by_ib[0]["school"] if sorted_by_ib else "—")

        st.divider()

        # 2열 카드 레이아웃
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
                        hdr_col, del_col = st.columns([6, 1])
                        with hdr_col:
                            st.markdown(f"📊 **{s['school']}** &nbsp; <span class='{fit_cls}'>매칭도 {fit}점</span>", unsafe_allow_html=True)
                            st.caption(f"{s.get('country','—')} | {s.get('major','—')}")
                        with del_col:
                            if st.button("🗑️", key=f"del_{s['school']}_{idx}"):
                                st.session_state.schools.pop(idx)
                                st.rerun()

                        rows = []
                        for key, label in ROW_LABELS.items():
                            if key in ("school", "country", "major", "fitScore"):
                                continue
                            val = s.get(key, "—")
                            if key == "schedule" and isinstance(val, dict):
                                parts = []
                                if val.get("applicationOpen"): parts.append(f"오픈 {val['applicationOpen']}")
                                if val.get("earlyDeadline"):   parts.append(f"얼리 {val['earlyDeadline']}")
                                if val.get("regularDeadline"): parts.append(f"마감 {val['regularDeadline']}")
                                val = " / ".join(parts) if parts else "—"
                            rows.append({"항목": label, "상세 세부 데이터": str(val)})

                        df = pd.DataFrame(rows)
                        st.dataframe(df, hide_index=True, use_container_width=True, height=440)
                        
                        if s.get("sourceUrl"):
                            st.caption(f"🔗 [공식 입학처 바로가기]({s['sourceUrl']}) | {s.get('sourceNote','')}")
                        st.divider()

# ════════════════════════════════════════════════════════
# 📊 표 B — 과목 매칭 및 적성 분석
# ════════════════════════════════════════════════════════
with tab_b:
    st.subheader("🎯 학생 맞춤형 IB 과목 적합도 스크리닝")
    
    if not st.session_state.schools:
        st.info("분석할 대학교 데이터가 없습니다. 표 A에서 학교를 먼저 검색해 주세요.")
    else:
        DIMS = ["화학(HL)", "영어A(HL)", "히스토리(HL)", "수학(SL)", "종합 적합도"]
        DIM_KEYS = ["chemistry", "englishA", "history", "math", "overall"]
        COLORS = px.colors.qualitative.Set2

        # 1. 종합 레이더 차트
        fig_radar = go.Figure()
        for i, s in enumerate(st.session_state.schools):
            bd = s.get("fitBreakdown", {})
            vals = [bd.get(k, s.get("fitScore", 50)) for k in DIM_KEYS]
            fig_radar.add_trace(go.Scatterpolar(
                r=vals + [vals[0]], 
                theta=DIMS + [DIMS[0]],
                fill="toself", 
                name=f"{s['school']}",
                line_color=COLORS[i % len(COLORS)], 
                opacity=0.6,
            ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            title="목표 대학 전공별 과목 정합성 비교",
            height=460,
            legend=dict(orientation="h", yanchor="bottom", y=-0.3),
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        st.divider()

        # 2. 대학별 가로 바 차트 데이터
        st.subheader("대학별 요구 과목 매칭 상세")
        for i, s in enumerate(st.session_state.schools):
            bd = s.get("fitBreakdown", {})
            vals = [bd.get(k, s.get("fitScore", 50)) for k in DIM_KEYS]
            overall = vals[-1]
            fit_label = "🟢 안정권" if overall >= 70 else ("🟡 매칭 노력 필요" if overall >= 45 else "🔴 고위험 지원")

            with st.expander(f"📌 {s['school']} — {s['major']} (종합 평점: {overall}점 | {fit_label})"):
                fig_bar = go.Figure(go.Bar(
                    x=vals, y=DIMS, orientation="h",
                    marker_color=[COLORS[i % len(COLORS)]] * len(DIMS),
                    text=[f"{v}점" for v in vals], textposition="outside",
                ))
                fig_bar.update_layout(
                    height=260, margin=dict(l=10, r=60, t=10, b=10),
                    xaxis=dict(range=[0, 115], showgrid=True, gridcolor="#f0f0f0"),
                    yaxis=dict(autorange="reversed"),
                    plot_bgcolor="white",
                )
                st.plotly_chart(fig_bar, use_container_width=True)

# ════════════════════════════════════════════════════════
# 📅 표 C — 원서 접수 및 마감 타임라인
# ════════════════════════════════════════════════════════
with tab_c:
    st.subheader("📅 입학 전형 일정 관리 매트릭스")

    if not st.session_state.schools:
        st.info("데이터가 없습니다. 표 A에서 학교를 먼저 검색해 주세요.")
    else:
        MONTHS = [f"{m}월" for m in range(1, 13)]
        EVENT_TYPES = {
            "applicationOpen": ("접수", "#378ADD"),
            "earlyDeadline":   ("얼리", "#7F77DD"),
            "regularDeadline": ("마감", "#D85A30"),
            "resultDate":      ("결과", "#639922"),
        }

        l_cols = st.columns(4)
        for col, (etype, (label, color)) in zip(l_cols, EVENT_TYPES.items()):
            col.markdown(f'<span style="background:{color};color:white;padding:4px 12px;border-radius:6px;font-size:12px;font-weight:600;">{label} 일정</span>', unsafe_allow_html=True)

        st.write("")

        # 2026-2027 입시 마일스톤 생성 
        for year in [2026, 2027]:
            st.markdown(f"#### 📅 {year}년도 입형 마일스톤")
            rows = []
            for s in st.session_state.schools:
                sc = s.get("schedule", {}) or {}
                row = {"목표 학교/전공": f"{s['school']} — {s['major']}"}
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

            styled = df_tl.style.map(color_cell, subset=MONTHS)
            st.dataframe(styled, use_container_width=True, hide_index=True)
            st.write("")
