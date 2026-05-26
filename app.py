import streamlit as st
import json
import re
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import time
from datetime import datetime
from google import genai
from google.genai import types
import gspread

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
    "fitscore":     "적성 적합도",
    "minib":        "최소 IB 점수",
    "requirements": "우대조건 (HL/SL 요건)",
    "tuition":      "연간 학비",
    "dorm":         "기숙사 유무",
    "living":       "연간 생활비",
    "scholarship":  "국제학생 장학금",
    "intlratio":    "국제학생 비율",
    "schedule":     "지원 일정",
    "documents":    "필요 서류",
    "earlyapp":     "얼리 지원 가능",
}

SPREADSHEET_ID = "1D5htK-ueN4yI-gJVc4xLB60aa3FhVeweYN9DNwjRqkE"

# ── 4. 🔍 gspread 인증 및 구글 시트 데이터 제어 함수 ──────────────────
def get_gspread_client():
    try:
        creds_dict = dict(st.secrets["google_credentials"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        return gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"구글 인증 연동 실패: {str(e)}")
        return None

def load_schools_from_sheets():
    gc = get_gspread_client()
    if not gc: return []
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.get_worksheet(0)
        records = worksheet.get_all_records()
        
        if not records: return []
        
        schools_list = []
        for row in records:
            r = {str(k).strip().lower(): v for k, v in row.items()}
            
            # 구글 시트의 빈 행이나 의미 없는 공백 행 필터링
            if not r.get("school") or r.get("school") == "—" or r.get("school").strip() == "":
                continue

            try:
                fit_breakdown = json.loads(r.get("fitbreakdown", "{}")) if r.get("fitbreakdown") else {}
                schedule = json.loads(r.get("schedule", "{}")) if r.get("schedule") else {}
            except:
                fit_breakdown = {}
                schedule = {}

            # 로드 시점 1차 방어선
            raw_fit = r.get("fitscore", 50.0)
            try:
                fit_val = float(raw_fit)
            except:
                fit_val = 50.0

            schools_list.append({
                "country": r.get("country", "—"),
                "school": r.get("school", "—"),
                "major": r.get("major", "—"),
                "acceptance": r.get("acceptance", "—"),
                "fitscore": fit_val,
                "fitbreakdown": fit_breakdown,
                "minib": r.get("minib", "—"),
                "requirements": r.get("requirements", "—"),
                "tuition": r.get("tuition", "—"),
                "dorm": r.get("dorm", "—"),
                "living": r.get("living", "—"),
                "scholarship": r.get("scholarship", "—"),
                "intlratio": r.get("intlratio", "—"),
                "schedule": schedule,
                "documents": r.get("documents", "—"),
                "earlyapp": r.get("earlyapp", "—"),
                "sourceurl": r.get("sourceurl", ""),
                "sourcenote": r.get("sourcenote", "")
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
        worksheet.clear() 
        
        headers = list(ROW_LABELS.keys()) + ["fitbreakdown", "sourceurl", "sourcenote"]
        if not schools_list:
            worksheet.append_row(headers)
            return
            
        rows = [headers]
        for s in schools_list:
            if not isinstance(s, dict) or not s.get("school"): continue
            rows.append([
                s.get("country", ""), 
                s.get("school", ""), 
                s.get("major", ""), 
                s.get("acceptance", ""),
                s.get("fitscore", 50.0), 
                json.dumps(s.get("fitbreakdown", {}), ensure_ascii=False),
                s.get("minib", ""), 
                s.get("requirements", ""), 
                s.get("tuition", ""), 
                s.get("dorm", ""),
                s.get("living", ""), 
                s.get("scholarship", ""), 
                s.get("intlratio", ""),
                json.dumps(s.get("schedule", {}), ensure_ascii=False), 
                s.get("documents", ""),
                s.get("earlyapp", ""), 
                s.get("sourceurl", ""), 
                s.get("sourcenote", "")
            ])
        worksheet.update(range_name='A1', values=rows)
    except Exception as e:
        st.error(f"구글 시트 저장 오류: {str(e)}")

# ── 5. 세션 데이터 초기 로드 ──────────────────────────────────
if "schools" not in st.session_state:
    st.session_state.schools = load_schools_from_sheets()

def parse_ib_score(school_dict):
    if not isinstance(school_dict, dict): return 99
    min_ib = school_dict.get("minib", "—")
    match = re.search(r"(\d+)", str(min_ib))
    return int(match.group(1)) if match else 99

# ── 6. Gemini 정보 추출 함수 (자동 재시도 및 백업 모델 전환 설계) ──────────────────────
def fetch_school_data_via_gemini(api_key, country, school, major):
    client = genai.Client(api_key=api_key)
    system_instruction = (
        "You are an expert college admissions consultant. Analyze data based on the latest guidelines "
        "and reply strictly in JSON format matching the schema keys in ROW_LABELS. "
        "Ensure all data fields are fully provided in Korean language where appropriate."
    )
    user_prompt = (
        f"Target University: {school} in {country}, Major: {major}. "
        f"IB choices: HL(화학, 영어A, 히스토리), SL(한국어, 일본어, 수학). "
        f"Return JSON with keys matching the required schema exactly."
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            target_model = 'gemini-2.5-flash' if attempt < 2 else 'gemini-1.5-flash'
            
            response = client.models.generate_content(
                model=target_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.2
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "503" in error_msg:
                if attempt < max_retries - 1:
                    time.sleep(3)  
                    continue
            st.error(f"Gemini API 에러 (시도 {attempt+1}/{max_retries}): {error_msg}")
            return None

# ── 7. 헤더 타이틀 ──────────────────────────────────────────
st.markdown('<div class="main-title">🎓 김태유 진로지도 대시보드</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-title">IB 매칭 조합 ── HL: {" · ".join(IB_HL)} | SL: {" · ".join(IB_SL)}</div>', unsafe_allow_html=True)

# ── 8. 사이드바 ⚙️ 설정 ──────────────────────────────────────
with st.sidebar: # <-- 지난 에러 수정 완료
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
                    normalized_data = {}
                    normalized_data["country"] = country_inp.strip()
                    normalized_data["school"] = school_inp.strip()
                    normalized_data["major"] = major_inp.strip()
                    
                    for raw_k, raw_v in fetched_data.items():
                        clean_k = str(raw_k).strip().lower().replace("_", "").replace(" ", "")
                        
                        if clean_k in ("acceptance", "acceptancerate"): normalized_data["acceptance"] = raw_v
                        elif clean_k in ("fitscore", "score"):
                            try:
                                normalized_data["fitscore"] = float(raw_v)
                            except:
                                normalized_data["fitscore"] = 50.0
                        elif clean_k in ("minib", "ibscore", "minimumib"): normalized_data["minib"] = raw_v
                        elif clean_k in ("requirements", "requirement", "courserequirements"): normalized_data["requirements"] = raw_v
                        elif clean_k in ("tuition", "tuitionfee"): normalized_data["tuition"] = raw_v
                        elif clean_k in ("dorm", "dormitory", "housing"): normalized_data["dorm"] = raw_v
                        elif clean_k in ("living", "livingcost", "livingcosts"): normalized_data["living"] = raw_v
                        elif clean_k in ("scholarship", "scholarships"): normalized_data["scholarship"] = raw_v
                        elif clean_k in ("intlratio", "internationalratio", "studentratio"): normalized_data["intlratio"] = raw_v
                        elif clean_k in ("schedule", "dates"): normalized_data["schedule"] = raw_v
                        elif clean_k in ("documents", "document", "requireddocuments"): normalized_data["documents"] = raw_v
                        elif clean_k in ("earlyapp", "earlyapplication"): normalized_data["earlyapp"] = raw_v
                        elif clean_k in ("fitbreakdown", "breakdown"): normalized_data["fitbreakdown"] = raw_v
                        elif clean_k in ("sourceurl", "url"): normalized_data["sourceurl"] = raw_v
                        elif clean_k in ("sourcenote", "note"): normalized_data["sourcenote"] = raw_v

                    for target_k in ROW_LABELS.keys():
                        if target_k not in normalized_data:
                            orig_val = next((v for k, v in fetched_data.items() if k.lower().replace(" ","").replace("_","") == target_k), "—")
                            normalized_data[target_k] = orig_val

                    if "fitbreakdown" not in normalized_data or not isinstance(normalized_data["fitbreakdown"], dict):
                        normalized_data["fitbreakdown"] = {"chemistry": 50.0, "englisha": 50.0, "history": 50.0, "math": 50.0, "overall": 50.0}
                    if "schedule" not in normalized_data or not isinstance(normalized_data["schedule"], dict):
                        normalized_data["schedule"] = {"applicationopen": "—", "earlydeadline": "—", "regulardeadline": "—", "resultdate": "—"}

                    st.session_state.schools.append(normalized_data)
                    save_schools_to_sheets(st.session_state.schools)
                    st.success(f"🎉 {school_inp} 데이터가 규격에 맞게 변환되어 구글 시트에 영구 저장되었습니다!")
                    st.rerun()

    st.divider()

    if not st.session_state.schools:
        st.info("💡 상단에 타겟 학교를 입력하면 구글 시트에 자동으로 누적 데이터베이스가 구축됩니다.")
    else:
        scores = []
        for s in st.session_state.schools:
            if isinstance(s, dict):
                try:
                    scores.append(float(s.get("fitscore", 0.0)))
                except:
                    scores.append(0.0)
            else:
                scores.append(0.0)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("누적 등록 학교", f"{len(st.session_state.schools)}개")
        
        # ── 🛠️ [정수분할 에러 수정 완료] 실수 연산 후 반올림 ──
        if scores:
            avg_score = round(sum(scores) / len(scores), 2)
        else:
            avg_score = 0.0
        m2.metric("평균 매칭도", f"{avg_score}점" if scores else "—")
        
        best_school = "—"
        if scores and max(scores) > 0:
            try:
                best_idx = scores.index(max(scores))
                best_obj = st.session_state.schools[best_idx]
                if isinstance(best_obj, dict):
                    best_school = best_obj.get("school", "—")
            except:
                best_school = "—"
        m3.metric("최우수 매칭", best_school)
        
        lowest_school = "—"
        try:
            sorted_by_ib = sorted(st.session_state.schools, key=parse_ib_score)
            if sorted_by_ib and isinstance(sorted_by_ib[0], dict):
                lowest_school = sorted_by_ib[0].get("school", "—")
        except:
            lowest_school = "—"
        m4.metric("진입장벽 최저 학교", lowest_school)

        st.divider()

        # 대학별 상세 데이터 카드 출력
        for i in range(0, len(st.session_state.schools), 2):
            cols = st.columns(2)
            for j, col in enumerate(cols):
                idx = i + j
                if idx >= len(st.session_state.schools): break
                s = st.session_state.schools[idx]
                if not isinstance(s, dict) or not s.get("school") or s.get("school") == "—": continue
                
                # ── 🛠️ [TypeError 캐스팅 에러 방어 완료] ──
                raw_fit = s.get("fitscore", 50.0)
                try:
                    fit = float(raw_fit)
                except (TypeError, ValueError):
                    fit = 50.0
                    
                fit_cls = "fit-high" if fit >= 70 else ("fit-mid" if fit >= 45 else "fit-low")
                sch_name = s.get("school", "—")

                with col:
                    with st.container():
                        hdr_col, del_col = st.columns([6, 1])
                        with hdr_col:
                            st.markdown(f"📊 **{sch_name}** &nbsp; <span class='{fit_cls}'>매칭도 {fit}점</span>", unsafe_allow_html=True)
                            st.caption(f"{s.get('country','—')} | {s.get('major','—')}")
                        with del_col:
                            if st.button("🗑️", key=f"del_{sch_name}_{idx}"):
                                st.session_state.schools.pop(idx)
                                save_schools_to_sheets(st.session_state.schools)
                                st.rerun()

                        rows = []
                        for key, label in ROW_LABELS.items():
                            if key in ("school", "country", "major", "fitscore"): continue
                            val = s.get(key, "—")
                            if key == "schedule" and isinstance(val, dict):
                                parts = []
                                if val.get("applicationopen"): parts.append(f"오픈 {val['applicationopen']}")
                                if val.get("earlydeadline"):   parts.append(f"얼리 {val['earlydeadline']}")
                                if val.get("regulardeadline"): parts.append(f"마감 {val['regulardeadline']}")
                                val = " / ".join(parts) if parts else "—"
                            rows.append({"항목": label, "상세 세부 데이터": str(val)})

                        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=400)
                        if s.get("sourceurl"):
                            st.caption(f"🔗 [공식 입학처 바로가기]({s['sourceurl']}) | {s.get('sourcenote','')}")
                        st.divider()

# ── 📊 표 B — 과목 매칭 및 적성 분석 ───────────────────────
with tab_b:
    st.subheader("🎯 학생 맞춤형 IB 과목 적합도 스크리닝")
    if not st.session_state.schools:
        st.info("시트에 저장된 대학 데이터가 없습니다.")
    else:
        DIMS = ["화학(HL)", "영어A(HL)", "히스토리(HL)", "수학(SL)", "종합 적합도"]
        DIM_KEYS = ["chemistry", "englisha", "history", "math", "overall"]
        COLORS = px.colors.qualitative.Set2

        fig_radar = go.Figure()
        for i, s in enumerate(st.session_state.schools):
            if not isinstance(s, dict) or not s.get("school") or s.get("school") == "—": continue
            bd = s.get("fitbreakdown", {})
            vals = []
            for k in DIM_KEYS:
                try:
                    vals.append(float(bd.get(k, s.get("fitscore", 50.0))))
                except:
                    vals.append(50.0)
            fig_radar.add_trace(go.Scatterpolar(
                r=vals + [vals[0]], theta=DIMS + [DIMS[0]], fill="toself", 
                name=f"{s.get('school', '—')}", line_color=COLORS[i % len(COLORS)], opacity=0.6,
            ))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=460)
        st.plotly_chart(fig_radar, use_container_width=True)

# ── 📅 표 C — 원서 접수 및 마감 타임라인 ──────────────────────
with tab_c:
    st.subheader("📅 입학 전형 일정 관리 매트릭스")
    if not st.session_state.schools:
        st.info("시트에 저장된 대학 데이터가 없습니다.")
    else:
        MONTHS = [f"{m}월" for m in range(1, 13)]
        EVENT_TYPES = {"applicationopen": ("접수", "#378ADD"), "earlydeadline": ("얼리", "#7F77DD"), "regulardeadline": ("마감", "#D85A30"), "resultdate": ("결과", "#639922")}

        for year in [2026, 2027]:
            st.markdown(f"#### 📅 {year}년도 입시 마일스톤")
            timeline_rows = []
            for s in st.session_state.schools:
                if not isinstance(s, dict) or not s.get("school") or s.get("school") == "—": continue
                sc = s.get("schedule", {}) or {}
                r_data = {"목표 학교/전공": f"{s.get('school','—')} — {s.get('major','—')}"}
                for m in range(1, 13):
                    mo = f"{year}-{m:02d}"
                    cell = ""
                    for etype, (label, _) in EVENT_TYPES.items():
                        if isinstance(sc, dict) and sc.get(etype) == mo:
                            cell = label
                            break
                    r_data[MONTHS[m - 1]] = cell
                timeline_rows.append(r_data)

            def color_cell(val):
                for etype, (label, color) in EVENT_TYPES.items():
                    if val == label: return f"background-color:{color};color:white;font-weight:600;text-align:center;"
                return ""

            if timeline_rows:
                st.dataframe(pd.DataFrame(timeline_rows).style.map(color_cell, subset=MONTHS), use_container_width=True, hide_index=True)
            else:
                st.info("일정 전형 데이터가 존재하지 않습니다.")
