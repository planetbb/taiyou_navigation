import streamlit as st
import json
import re
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

# ── 세션 상태 초기화 (초기 가상 데이터 탑재) ──────────────────
if "schools" not in st.session_state:
    st.session_state.schools = [
        {
            "country": "영국",
            "school": "University of Oxford",
            "major": "Chemistry",
            "acceptance": "~16% (2024)",
            "fitScore": 85,
            "fitBreakdown": {"chemistry": 95, "englishA": 80, "history": 70, "math": 85, "overall": 85},
            "minIB": "39/45",
            "requirements": "화학 HL 필수 (7점 권장), 수학 SL 6점 이상",
            "tuition": "£44,240 (약 7,500만원)",
            "dorm": "있음 (1학년 보장)",
            "living": "약 £14,000 / 년",
            "scholarship": "Palgrave Brown Scholarship (일부 지원)",
            "intlRatio": "~40%",
            "schedule": {"applicationOpen": "2026-09", "earlyDeadline": "2026-10", "regularDeadline": "2026-10", "resultDate": "2027-01"},
            "documents": "UCAS Application, Personal Statement, 추천서, 옥스퍼드 자체 시험(TSA/HAT)",
            "earlyApp": "가능 (UCAS Early)",
            "sourceUrl": "https://www.ox.ac.uk/admissions",
            "sourceNote": "2026학년도 입학 요강 기준"
        },
        {
            "country": "미국",
            "school": "UC Berkeley",
            "major": "Chemical Science",
            "acceptance": "~11.5% (2024)",
            "fitScore": 75,
            "fitBreakdown": {"chemistry": 90, "englishA": 75, "history": 65, "math": 80, "overall": 75},
            "minIB": "38/45",
            "requirements": "HL 과목 중 과학/수학 우대, 토플 100점 이상 필수",
            "tuition": "$48,500 (약 6,500만원)",
            "dorm": "선택 가능",
            "living": "약 $20,000 / 년",
            "scholarship": "Berkeley International Scholarship (성적 우수)",
            "intlRatio": "~24%",
            "schedule": {"applicationOpen": "2026-08", "earlyDeadline": None, "regularDeadline": "2026-11", "resultDate": "2027-03"},
            "documents": "UC Application, 에세이 (PIQs), 고교 성적표",
            "earlyApp": "불가 (Regular Only)",
            "sourceUrl": "https://admissions.berkeley.edu",
            "sourceNote": "UC 계열 공통 요강 기준"
        }
    ]

# ── 헤더 및 대시보드 타이틀 ──────────────────────────────
st.markdown('<div class="main-title">🎓 김태유 진로지도 대시보드 (데모 모드)</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-title">IB HL 요약: {" · ".join(IB_HL)} &nbsp;|&nbsp; SL 요약: {" · ".join(IB_SL)}</div>',
    unsafe_allow_html=True,
)

# ── 사이드바 ⚙️ 설정 ──────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 데이터 관리")
    st.info("💡 현재 API 연결 없이 가상 데이터로 구동 중인 데모 화면입니다.")
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
    # API가 없으므로 수동 입력 양식으로 대체 변경 가능하지만, UI 유지를 위해 알림 처리
    with st.expander("➕ 새 학교 수동 추가 (데모 전용)", expanded=False):
        col1, col2, col3 = st.columns([1, 2, 2])
        with col1:
            country_sel = st.selectbox("국가 선택", ["", "영국", "미국", "캐나다", "기타"])
        with col2:
            school_inp = st.text_input("학교명", placeholder="예: UCL")
        with col3:
            major_inp = st.text_input("희망 전공", placeholder="예: History")

        if st.button("➕ 샘플 포맷으로 추가", type="primary", disabled=(not school_inp or not major_inp)):
            mock_new = {
                "country": country_sel or "기타", "school": school_inp, "major": major_inp,
                "acceptance": "~20%", "fitScore": 65,
                "fitBreakdown": {"chemistry": 60, "englishA": 70, "history": 85, "math": 50, "overall": 65},
                "minIB": "36/45", "requirements": "지원 전공 관련 HL 요건 확인 필요", "tuition": "기타 통화", "dorm": "있음", "living": "—", "scholarship": "—", "intlRatio": "—",
                "schedule": {"applicationOpen": "2026-09", "earlyDeadline": None, "regularDeadline": "2027-01", "resultDate": "2027-04"},
                "documents": "자기소개서, 추천서", "earlyApp": "가능", "sourceUrl": "", "sourceNote": "수동 추가 데이터"
            }
            st.session_state.schools.append(mock_new)
            st.rerun()

    if not st.session_state.schools:
        st.info("현재 등록된 학교가 없습니다. 새로고침 시 기본 데모 데이터가 다시 로드됩니다.")
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
                            if st.button("🗑️", key=f"del_{s['school']}_{s['major']}_{idx}"):
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
                        st.divider()

# ════════════════════════════════════════════════════════
# 📊 표 B — 과목 매칭 및 적성 분석
# ════════════════════════════════════════════════════════
with tab_b:
    st.subheader("🎯 학생 맞춤형 IB 과목 적합도 스크리닝")
    
    if not st.session_state.schools:
        st.info("분석할 대학교 데이터가 없습니다.")
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
        st.info("데이터가 없습니다.")
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

        # 하드코딩 대신 현재 시점 기준 연도로 동적 루프 구성
        current_year = 2026
        for year in [current_year, current_year + 1]:
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
