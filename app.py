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

# ── CSS (최적화 및 가독성 유지) ───────────────────────────
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

# ── 세션 상태 초기화 ──────────────────────────────────────
if "schools" not in st.session_state:
    st.session_state.schools = []

# ── AI 데이터 수집 함수 ───────────────────────────────────
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
  "fitScore": 0-100,
  "fitBreakdown": {{ "chemistry": 0-100, "englishA": 0-100, "history": 0-100, "math": 0-100, "overall": 0-100 }},
  "minIB": "최소 요구 IB 점수 예: 38/45",
  "requirements": "HL/SL 특정 과목 요건 설명",
  "tuition": "연간 학비 (현지 통화 및 원화 환산)",
  "dorm": "있음/없음/선택가능",
  "living": "연간 생활비 예상",
  "scholarship": "국제학생 대상 주요 장학금 이름과 금액",
  "intlRatio": "국제학생 비율 예: ~30%",
  "schedule": {{ "applicationOpen": "YYYY-MM or null", "earlyDeadline": "YYYY-MM or null", "regularDeadline": "YYYY-MM or null", "resultDate": "YYYY-MM or null" }},
  "documents": "필요 서류 목록",
  "earlyApp": "가능/불가/Rolling",
  "sourceUrl": "학교 공식 입학처 URL",
  "sourceNote": "데이터 기준 연도 또는 주의사항"
}}"""

    client = anthropic.Anthropic(api_key=api_key)
    # 완벽한 JSON 추출을 위해 assistant prefill(응답 시작 지정)을 도입하는 것이 좋습니다.
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        tools=[{"type": "web_search_20250305"}],  # 도구 이름 선언 최적화
        messages=[
            {"role": "user", "content": prompt}
        ],
    )
    
    text = "".join([block.text for block in response.content if block.type == "text"])
    cleaned = re.sub(r"```json|```", "", text).strip()
    return json.loads(cleaned)

# ── 헤더 및 대시보드 타이틀 ──────────────────────────────
st.markdown('<div class="main-title">🎓 김태유 진로지도 대시보드</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-title">IB HL 요약: {" · ".join(IB_HL)} &nbsp;|&nbsp; SL 요약: {" · ".join(IB_SL)}</div>',
    unsafe_allow_html=True,
)

# ── 사이드바 ⚙️ 설정 ──────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정 및 관리")
    api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")
    st.caption("API 키는 현재 세션에만 임시로 유지됩니다.")
    st.divider()
    
    if st.button("🗑️ 전체 학교 삭제", use_container_width=True):
        st.session_state.schools = []
        st.rerun()
    st.divider()
    st.caption(f"현재 등록된 학교 목록: **{len(st.session_state.schools)}개**")

# ── 메인 탭 구성 ──────────────────────────────────────────
tab_a, tab_b, tab_c = st.tabs(["📋 표 A — 학교 데이터", "📊 표 B — 적성 분석", "📅 표 C — 지원 일정"])

# ════════════════════════════════════════════════════════
# 📋 표 A — 학교 데이터 관리 및 카드뷰
# ════════════════════════════════════════════════════════
with tab_a:
    with st.expander("➕ AI 기반 지원 학교 등록", expanded=(len(st.session_state.schools) == 0)):
        col1, col2, col3 = st.columns([1, 2, 2])
        with col1:
            country_sel = st.selectbox("국가 선택", ["", "영국", "미국", "캐나다", "호주", "네덜란드", "독일", "일본", "홍콩", "싱가포르", "기타"])
        with col2:
            school_inp = st.text_input("학교명 (영어 추천)", placeholder="예: University of Oxford")
        with col3:
            major_inp = st.text_input("희망 전공", placeholder="예: Chemistry")

        fetch_btn = st.button("✨ AI 입학 정보 실시간 탐색 및 등록", type="primary", disabled=(not school_inp or not major_inp))

        if fetch_btn:
            if not api_key:
                st.error("사이드바에서 API Key를 먼저 입력해주세요.")
            else:
                with st.spinner(f"🔍 {school_inp} — {major_inp} 데이터 수집 및 분석 중..."):
                    try:
                        data = fetch_school_data(country_sel, school_inp, major_inp, api_key)
                        st.session_state.schools.append(data)
                        st.toast(f"✅ {data['school']} 등록 완료!")
                        st.rerun()
                    except Exception as e:
                        # Fallback 구조 유지
                        fallback = {
                            "country": country_sel or "—", "school": school_inp, "major": major_inp,
                            "acceptance": "—", "fitScore": 50,
                            "fitBreakdown": {"chemistry": 50, "englishA": 50, "history": 50, "math": 50, "overall": 50},
                            "minIB": "—", "requirements": "—", "tuition": "—", "dorm": "—", "living": "—", "scholarship": "—", "intlRatio": "—",
                            "schedule": {"applicationOpen": None, "earlyDeadline": None, "regularDeadline": None, "resultDate": None},
                            "documents": "—", "earlyApp": "—", "sourceUrl": "", "sourceNote": "수동 확인 필요"
                        }
                        st.session_state.schools.append(fallback)
                        st.warning(f"⚠️ 검색 중 일부 누락이 발생하여 기본 포맷으로 추가되었습니다. (오류: {e})")
                        st.rerun()

    if not st.session_state.schools:
        st.info("현재 등록된 학교가 없습니다. 상단에서 타겟 학교를 추가해 보세요.")
    else:
        # 요약 메트릭 영역 (에러 안전 조치 완료)
        scores = [s.get("fitScore", 0) for s in st.session_state.schools]
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("등록 학교", f"{len(st.session_state.schools)}개")
        m2.metric("평균 적성 매칭도", f"{sum(scores)//len(scores)}점" if scores else "—")
        m3.metric("최우수 매칭 학교", st.session_state.schools[scores.index(max(scores))]["school"] if scores else "—")
        
        # 안전하게 정렬 후 최저 요구 점수 학교 연산
        sorted_by_ib = sorted(st.session_state.schools, key=parse_ib_score)
        m4.metric("진입 장벽 최저 학교", sorted_by_ib[0]["school"] if sorted_by_ib else "—")

        st.divider()

        # 2열 카드 및 표 레이아웃
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
                            # 고유 ID 기반 Key 처리로 UI 크래시 예방
                            if st.button("🗑️", key=f"del_{s['school']}_{s['major']}_{idx}", help="삭제"):
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
                            st.markdown(f"🔗 [공식 입학처 바로가기]({s['sourceUrl']}) · {s.get('sourceNote','')}")
                        st.divider()

# ════════════════════════════════════════════════════════
# 📊 표 B — 과목 매칭 및 적성 분석
# ════════════════════════════════════════════════════════
with tab_b:
    st.subheader("🎯 학생 맞춤형 IB 과목 적합도 스크리닝")
    
    if not st.session_state.schools:
        st.info("분석할 대학교 데이터가 부족합니다. '표 A' 탭에서 학교를 등록해 주세요.")
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
                name=f"{s['school']} ({s['major']})",
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

        # 2. 학교별 가로 바 차트 데이터
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
        st.info("학교 데이터를 등록하면 동적 연도별 타임라인 스케줄러가 활성화됩니다.")
    else:
        MONTHS = [f"{m}월" for m in range(1, 13)]
        EVENT_TYPES = {
            "applicationOpen": ("접수", "#378ADD"),
            "earlyDeadline":   ("얼리", "#7F77DD"),
            "regularDeadline": ("마감", "#D85A30"),
            "resultDate":      ("결과", "#639922"),
        }

        # 범례 표시
        l_cols = st.columns(4)
        for col, (etype, (label, color)) in zip(l_cols, EVENT_TYPES.items()):
            col.markdown(f'<span style="background:{color};color:white;padding:4px 12px;border-radius:6px;font-size:12px;font-weight:600;">{label} 일정</span>', unsafe_allow_html=True)

        st.write("")

        # 2025 ~ 2026 타임라인 (map 함수 가독성 버그 수정 완료)
        current_year = datetime.now().year
        for year in [current_year - 1, current_year]:
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

            # 중요: Pandas 최신 호환성을 위해 applymap 대신 map 사용
            styled = df_tl.style.map(color_cell, subset=MONTHS)
            st.dataframe(styled, use_container_width=True, hide_index=True)
            st.write("")

        # 정렬된 데드라인 요약 리스트
        st.divider()
        st.subheader("📌 타임라인 순 마감 일정 직관 요약")
        deadlines = []
        for s in st.session_state.schools:
            sc = s.get("schedule", {}) or {}
            for etype, (label, color) in EVENT_TYPES.items():
                date = sc.get(etype)
                if date:
                    deadlines.append({"예정 날짜": date, "전형 구분": label, "대학교": s["school"], "지원학과": s["major"]})

        if deadlines:
            df_dl = pd.DataFrame(deadlines).sort_values("예정 날짜").reset_index(drop=True)
            st.dataframe(df_dl, use_container_width=True, hide_index=True)