import streamlit as st
import json
import re
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from google import genai
from google.genai import types
import gspread  # 오리지널 구글 시트 라이브러리 사용

# ── 1. 페이지 설정 ───────────────────────────────────────────
st.set_page_config(
    page_title="김태유 진로지도",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 2. CSS 스타일 적용 ─────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f8f9fa; }
.main-title { font-size:26px; font-weight:700; color:#1a1a2e; margin-bottom:4px; }
.sub-title  { font-size:14px; color:#6c757d; margin-bottom:20px; }
.fit-high { background:#e8f5e9; color:#2e7d32; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.fit-mid  { background:#fff3e0; color:#e65100; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.fit-low  { background:#ffebee; color:#c62828; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
div[data-testid="metric-container"] { background:white; border-radius:10px; padding:12px; box-shadow:0 1px 4px rgba(0,0,0,.06); }
</style>
""", unsafe_allow_html=True)

# ── 3. 학생 프로필 및 라벨 상수 ──────────────────────────────
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

SPREADSHEET_ID = "1D5htK-ueN4yI-gJVc4xLB60aa3FhVeweYN9DNwjRqkE"

# ── 4. 🔍 gspread 인증 및 구글 시트 데이터 제어 함수 ──────────────────
def get_gspread_client():
    try:
        # Secrets에 저장된 순수 JSON 텍스트를 파싱하여 크레덴셜 생성
        creds_dict = json.loads(st.secrets["google_credentials"]["json_text"])
        return gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"구글 인증 연동 실패: {str(e)}")
        return None

def load_schools_from_sheets():
    gc = get_gspread_client()
    if not gc: return []
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0) # 첫 번째 시트 선택
        records = worksheet.get_all_records()
        
        if not records: return []
        
        schools_list = []
        for row in records:
            try:
                fit_breakdown = json.loads(row.get("fitBreakdown", "{}")) if row.get("fitBreakdown") else {}
                schedule = json.loads(row.get("schedule", "{}")) if row.get("schedule") else {}
            except:
                fit_breakdown = {}
                schedule = {}

            schools_list.append({
                "country": row.get("country", "—"),
                "school": row.get("school", "—"),
                "major": row.get("major", "—"),
                "acceptance": row.get("acceptance", "—"),
                "fitScore": int(row.get("fitScore", 50)) if str(row.get("fitScore")).isdigit() else 50,
                "fitBreakdown": fit_breakdown,
                "minIB": row.get("minIB", "—"),
                "requirements": row.get("requirements", "—"),
                "tuition": row.get("tuition", "—"),
                "dorm": row.get("dorm", "—"),
                "living": row.get("living", "—"),
                "scholarship": row.get("scholarship", "—"),
                "intlRatio": row.get("intlRatio", "—"),
                "schedule": schedule,
                "documents": row.get("documents", "—"),
                "earlyApp": row.get("earlyApp", "—"),
                "sourceUrl": row.get("sourceUrl", ""),
                "sourceNote": row.get("sourceNote", "")
            })
        return schools_list
    except Exception as e:
        return []

def save_schools_to_sheets(schools_list):
    gc = get_gspread_client()
    if not gc: return
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        
        # 1. 시트 내용 깨끗하게 비우기
        worksheet.clear() 
        
        # 2. 컬럼 헤더 세팅
        headers = list(ROW_LABELS.keys()) + ["fitBreakdown", "sourceUrl", "sourceNote"]
        
        if not schools_list:
            worksheet.append_row(headers)
            return
            
        # 3. 데이터 로우 조립
        rows = [headers]
        for s in schools_list:
            rows.append([
                s.get("country", ""), 
                s.get("school", ""), 
                s.get("major", ""), 
                s.get("acceptance", ""),
                s.get("fitScore", 50), 
                json.dumps(s.get("fitBreakdown", {}), ensure_ascii=False),
                s.get("minIB", ""), 
                s.get("requirements", ""), 
                s.get("tuition", ""), 
                s.get("dorm", ""),
                s.get("living", ""), 
                s.get("scholarship", ""), 
                s.get("intlRatio", ""),
                json.dumps(s.get("schedule", {}), ensure_ascii=False), 
                s.get("documents", ""),
                s.get("earlyApp", ""), 
                s.get("sourceUrl", ""), 
                s.get("sourceNote", "")
            ])
            
        # 4. A1 셀 기점으로 원샷 덮어쓰기 (UnsupportedOperationError 원천 해결)
        worksheet.update(range_name='A1', values=rows)
    except Exception as e:
        st.error(f"구글 시트 저장 오류: {str(e)}")

# ── 5. 세션 데이터 초기 로드 ──────────────────────────────────
if "schools" not in st.session_state:
    st.session_state.schools = load_schools_from_sheets()

def parse_ib_score(school_dict):
    min_ib = school_dict.get("minIB", "—")
    match = re.search(r"(\d+)", str(min_ib))
    return int(match.group(1)) if match else 99

# ── 6. Gemini 정보 추출 함수 ────────────────────────────────
def fetch_school_data_via_gemini(api_key, country, school, major):
    client = genai.Client(api_key=api_key)
    system_instruction = "You are an expert college admissions consultant. Analyze data based on the latest guidelines and reply strictly in JSON format matching the schema."
    user_prompt = f"Target University: {school} in {country}, Major: {major}. IB choices: HL(화학, 영어A, 히스토리), SL(한국어, 일본어, 수학). Return JSON matching dashboard specifications."

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.2
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Gemini API 에러: {str(e)}")
        return None

# ── 7. 헤더 타이틀 ──────────────────────────────────────────
st.markdown('<div class="main-title">🎓 김태유 진로지도 대시보드</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-title">IB 매칭 조합 ── HL: {" · ".join(IB_HL)} | SL: {" · ".join(IB_SL)}</div>', unsafe_allow_html=True)

# ── 8. 사이드바 ⚙️ 설정 ──────────────────────────────────────
with st.sidebar:
    st.header("⚙️ API 및 데이터 설정")
    gemini_key = st.text_input("Gemini API Key 입력", type="password")
    if gemini_key:
        st.success("🔑 Gemini API 연결 완료")
    
    st.divider()
    st.subheader("📊 데이터 가동 상태")
    
    if st.button("🔄 구글 시트 데이터 불러오기", use_container_width=True):
        st.session_state.schools = load_schools_from_sheets()
        st.success("구글 시트의 최신 데이터를 가져왔습니다!")
        st.rerun()

    if st.button("🗑️ 전체 데이터 초기화", use_container_width=True):
        st.session_state.schools = []
        save_schools_to_sheets([])
        st.success("구글 시트 및 대시보드가 초기화되었습니다.")
        st.rerun()
        
    st.caption(f"현재 로드된 대학교: **{len(st.session_state.schools)}개**")

# ── 9. 메인 탭 구성 ──────────────────────────────────────────
tab_a, tab_b, tab_c = st.tabs(["📋 표 A — AI 검색 및 학교 데이터", "📊 표 B — 적성 분석", "📅 표 C — 지원 일정"])

# ════════════════════════════════════════════════════════
# 📋 표 A — 데이터 실시간 스크리닝 및 자동 시트 적재
# ════════════════════════════════════════════════════════
with tab_a:
    st.subheader("🔍 신규 대학교 실시간 검색")
    col1, col2, col3 = st.columns([1, 2, 2])
    with col1: country_inp = st.text_input("국가", placeholder="예: 미국")
    with col2: school_inp = st.text_input("학교명", placeholder="예: Harvard")
    with col3: major_inp = st.text_input("희망 전공", placeholder="예: Chemistry")

    if st.button("🚀 Gemini 분석 및 구글 시트 자동 저장", type="primary"):
        if not gemini_key:
            st.error("사이드바에 Gemini API Key를 입력해 주세요.")
        elif not (country_inp and school_inp and major_inp):
            st.error("국가, 학교, 학과를 모두 채워주세요.")
        else:
            with st.spinner("AI가 입학 가이드라인을 분석하여 구글 시트에 실시간 기록 중입니다..."):
                fetched_data = fetch_school_data_via_gemini(gemini_key, country_inp, school_inp, major_inp)
                if fetched_data:
                    st.session_state.schools.append(fetched_data)
                    save_schools_to_sheets(st.session_state.schools)
                    st.success(f"🎉 {school_inp} 데이터가 구글 스프레드시트에 안전하게 영구 저장되었습니다!")
                    st.rerun()

    st.divider()

    if not st.session_state.schools:
        st.info("💡 상단에 타겟 학교를 입력하면 구글 시트에 자동으로 누적 데이터베이스가 구축됩니다.")
    else:
        scores = [s.get("fitScore", 0) for s in st.session_state.schools]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("누적 등록 학교", f"{len(st.session_state.schools)}개")
        m2.metric("평균 매칭도", f"{sum(scores)//len(scores)}점" if scores else "—")
        m3.metric("최우수 매칭", st.session_state.schools[scores.index(max(scores))]["school"] if scores else "—")
        sorted_by_ib = sorted(st.session_state.schools, key=parse_ib_score)
        m4.metric("진입장벽 최저 학교", sorted_by_ib[0]["school"] if sorted_by_ib else "—")

        st.divider()

        for i in range(0, len(st.session_state.schools), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(st.session_state.schools): break
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
                                save_schools_to_sheets(st.session_state.schools)
                                st.rerun()

                        rows = []
                        for key, label in ROW_LABELS.items():
                            if key in ("school", "country", "major", "fitScore"): continue
                            val = s.get(key, "—")
                            if key == "schedule" and isinstance(val, dict):
                                parts = []
                                if val.get("applicationOpen"): parts.append(f"오픈 {val['applicationOpen']}")
                                if val.get("earlyDeadline"):   parts.append(f"얼리 {val['earlyDeadline']}")
                                if val.get("regularDeadline"): parts.append(f"마감 {val['regularDeadline']}")
                                val = " / ".join(parts) if parts else "—"
                            rows.append({"항목": label, "상세 세부 데이터": str(val)})

                        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=400)
                        if s.get("sourceUrl"):
                            st.caption(f"🔗 [공식 입학처 바로가기]({s['sourceUrl']}) | {s.get('sourceNote','')}")
                        st.divider()

# ════════════════════════════════════════════════════════
# 📊 표 B — 과목 매칭 및 적성 분석
# ════════════════════════════════════════════════════════
with tab_b:
    st.subheader("🎯 학생 맞춤형 IB 과목 적합도 스크리닝")
    if not st.session_state.schools:
        st.info("시트에 저장된 대학 데이터가 없습니다.")
    else:
        DIMS = ["화학(HL)", "영어A(HL)", "히스토리(HL)", "수학(SL)", "종합 적합도"]
        DIM_KEYS = ["chemistry", "englishA", "history", "math", "overall"]
        COLORS = px.colors.qualitative.Set2

        fig_radar = go.Figure()
        for i, s in enumerate(st.session_state.schools):
            bd = s.get("fitBreakdown", {})
            vals = [bd.get(k, s.get("fitScore", 50)) for k in DIM_KEYS]
            fig_radar.add_trace(go.Scatterpolar(
                r=vals + [vals[0]], theta=DIMS + [DIMS[0]], fill="toself", 
                name=f"{s['school']}", line_color=COLORS[i % len(COLORS)], opacity=0.6,
            ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=460)
        st.plotly_chart(fig_radar, use_container_width=True)

# ════════════════════════════════════════════════════════
# 📅 표 C — 원서 접수 및 마감 타임라인
# ════════════════════════════════════════════════════════
with tab_c:
    st.subheader("📅 입학 전형 일정 관리 매트릭스")
    if not st.session_state.schools:
        st.info("시트에 저장된 대학 데이터가 없습니다.")
    else:
        MONTHS = [f"{m}월" for m in range(1, 13)]
        EVENT_TYPES = {"applicationOpen": ("접수", "#378ADD"), "earlyDeadline": ("얼리", "#7F77DD"), "regularDeadline": ("마감", "#D85A30"), "resultDate": ("결과", "#639922")}

        for year in [2026, 2027]:
            st.markdown(f"#### 📅 {year}년도 입시 마일스톤")
            timeline_rows = []
            for s in st.session_state.schools:
                sc = s.get("schedule", {}) or {}
                r_data = {"목표 학교/전공": f"{s['school']} — {s['major']}"}
                for m in range(1, 13):
                    mo = f"{year}-{m:02d}"
                    cell = ""
                    for etype, (label, _) in EVENT_TYPES.items():
                        if sc.get(etype) == mo:
                            cell = label
                            break
                    r_data[MONTHS[m - 1]] = cell
                timeline_rows.append(r_data)

            def color_cell(val):
                for etype, (label, color) in EVENT_TYPES.items():
                    if val == label: return f"background-color:{color};color:white;font-weight:600;text-align:center;"
                return ""

            st.dataframe(pd.DataFrame(timeline_rows).style.map(color_cell, subset=MONTHS), use_container_width=True, hide_index=True)
