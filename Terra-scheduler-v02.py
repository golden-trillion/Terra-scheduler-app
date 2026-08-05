import streamlit as st
import pandas as pd
import io
import json
import re
from datetime import datetime, time, timedelta

# 1. 페이지 기본 설정 (전체 파일에서 단 한 번만 최상단에 실행)
st.set_page_config(page_title="가변형 팀 매칭 시스템 Pro", layout="wide")

# -------------------------------------------------------------------
# 🔒 보안 인증 로직 (Streamlit Secrets 연동)
# -------------------------------------------------------------------
def check_password():
    """Secrets에 설정된 비밀번호와 입력값을 비교하여 접근을 제어합니다."""
    def password_entered():
        # Streamlit Secrets에 저장된 APP_PASSWORD와 비교 (기본값: "1234")
        if st.session_state["password_input"] == st.secrets.get("APP_PASSWORD", "1234"):
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("### 🔒 가변형 팀 매칭 시스템 Pro")
        st.text_input(
            "접근 비밀번호를 입력하세요", 
            type="password", 
            on_change=password_entered, 
            key="password_input"
        )
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("### 🔒 가변형 팀 매칭 시스템 Pro")
        st.text_input(
            "접근 비밀번호를 입력하세요", 
            type="password", 
            on_change=password_entered, 
            key="password_input"
        )
        st.error("❌ 비밀번호가 올바르지 않습니다.")
        return False
    else:
        return True

# 인증 실패 시 이하 메인 프로그램 실행 중단
if not check_password():
    st.stop()

# -------------------------------------------------------------------
# 🎈 메인 프로그램 영역 (비밀번호 인증 성공 시 실행)
# -------------------------------------------------------------------

# 2. CSS 스타일
st.markdown("""
<style>
    /* 팝업창을 감싸는 컨테이너 */
    .tooltip { 
        position: relative; 
        display: block; 
        cursor: pointer; 
        margin-bottom: 5px; 
        z-index: 10; 
    }
    
    /* 실제 정보가 나타나는 팝업창 (z-index를 최상단으로 설정) */
    .tooltip .tooltiptext {
        visibility: hidden; 
        width: 300px; 
        background-color: #222; 
        color: #fff;
        text-align: left; 
        border-radius: 8px; 
        padding: 12px; 
        position: absolute;
        z-index: 999999 !important; 
        bottom: 120%; 
        left: 50%; 
        margin-left: -150px;
        opacity: 0; 
        transition: opacity 0.2s; 
        font-size: 11px; 
        line-height: 1.5; 
        box-shadow: 0px 8px 30px rgba(0,0,0,0.8);
        word-break: keep-all; 
        pointer-events: none; 
        border: 1px solid #555;
    }
    
    .tooltip:hover .tooltiptext { 
        visibility: visible; 
        opacity: 1; 
    }

    /* 고정 수업 레이어 스타일 */
    .fixed-title {
        background: rgba(255,255,255,0.2) !important; 
        color: #FFD700 !important; 
        text-align: center;
        font-weight: bold; 
        padding: 2px; 
        margin-bottom: 5px; 
        border-radius: 3px; 
        font-size: 11px;
    }

    .sub-mark {
        display: inline-block; border-radius: 50%; width: 28px; height: 18px;
        text-align: center; line-height: 18px; font-size: 10px; font-weight: bold; color: #333; margin-left: 3px;
        border: 1px solid rgba(0,0,0,0.1);
    }
    table { table-layout: fixed; width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #ddd; overflow: hidden; height: 40px; position: relative; }
    .time-col { background:#f8f9fa; font-size: 11px; color: #666; text-align: center; width: 100px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# 3. 유틸리티 함수
def get_total_min(t):
    h = t.hour
    if h < 5: h += 24
    return h * 60 + t.minute

def add_minutes(t, mins):
    total = get_total_min(t) + mins
    new_h = (total // 60) % 24
    new_m = total % 60
    return time(new_h, new_m)

def parse_time_to_ui(t):
    h = t.hour
    ampm = "오후" if h >= 12 else "오전"
    h12 = h if h <= 12 else h - 12
    if h12 == 0: h12 = 12
    return ampm, h12, t.minute

def make_time(ampm, h12, m):
    h24 = int(h12)
    if ampm == "오후" and h24 < 12: h24 += 12
    if ampm == "오전" and h24 == 12: h24 = 0
    return time(h24, int(m))

def get_badge_html(school, grade, is_dark=False):
    prefix, color = ("?", "#6c757d")
    if "초등" in school: prefix, color = ("초", "#28a745")
    elif "중학" in school: prefix, color = ("중", "#4A90E2")
    elif "고등" in school: prefix, color = ("고", "#E83E8C")
    g_num = ''.join(filter(str.isdigit, str(grade)))
    border = "border: 1px solid white;" if is_dark else ""
    return f'<span style="background:{color}; color:white; border-radius:12px; padding:2px 8px; font-size:10px; font-weight:bold; margin-right:5px; {border}">{prefix}{g_num}</span>'

def schedule_to_text(sch_dict):
    parts = []
    for day, slots in sch_dict.items():
        nums = [re.sub(r'[^0-9]', '', s) for s in slots]
        nums = [n for n in nums if n]
        if nums: parts.append(f"{day}:{','.join(nums)}")
    return " / ".join(parts)

def text_to_schedule(text):
    sch_dict = {}
    if not text or pd.isna(text): return sch_dict
    days_data = str(text).split('/')
    for item in days_data:
        if ':' in item:
            day, slots_raw = item.split(':')
            day = day.strip()
            nums = slots_raw.replace(' ', '').split(',')
            sch_dict[day] = [f"{n.strip()}교시" for n in nums if n.strip()]
    return sch_dict

# 4. 초기 상태 설정
ALL_DAYS = ["월", "화", "수", "목", "금", "토", "일"]
SUBJECT_INFO = {
    "중1내신": {"short": "1", "color": "#E2E2E2"}, "중2내신": {"short": "2", "color": "#E2E2E2"},
    "중3내신": {"short": "3", "color": "#E2E2E2"}, "통합과학1": {"short": "통1", "color": "#FFC6FF"},
    "통합과학2": {"short": "통2", "color": "#FFC6FF"}, "물리학": {"short": "물", "color": "#A7D8FF"},
    "화학": {"short": "화", "color": "#FFEB9C"}, "생명과학": {"short": "생", "color": "#C6EFCE"},
    "지구과학": {"short": "지", "color": "#CFD9F3"}, "물올초급": {"short": "Ph초", "color": "#FFBFBF"},
    "물올중급": {"short": "Ph중", "color": "#FFBFBF"}, "물올": {"short": "Ph", "color": "#FFBFBF"}
}

if 'students' not in st.session_state: st.session_state.students = []
if 'fixed_slots' not in st.session_state: st.session_state.fixed_slots = {d: [] for d in ALL_DAYS}
if 'editing_index' not in st.session_state: st.session_state.editing_index = None

if 'daily_slots_info' not in st.session_state:
    default_setup = [
        {"label": "1교시", "start": time(9, 0), "end": time(11, 30)},
        {"label": "2교시", "start": time(11, 30), "end": time(14, 0)},
        {"label": "3교시", "start": time(14, 0), "end": time(16, 30)},
        {"label": "4교시", "start": time(17, 0), "end": time(19, 30)},
        {"label": "5교시", "start": time(19, 30), "end": time(22, 0)},
        {"label": "6교시", "start": time(22, 30), "end": time(1, 0)},
    ]
    st.session_state.daily_slots_info = {d: [s.copy() for s in default_setup] for d in ALL_DAYS}

# 5. 사이드바 제어판
with st.sidebar:
    st.header("⚙ 시스템 통합 관리")
    t_days = st.multiselect("활성 요일", ALL_DAYS, default=ALL_DAYS)

    with st.expander("⏰ 시간표 틀 수정 (추가/삭제/연쇄이동)", expanded=False):
        sel_day = st.selectbox("수정 요일", t_days)
        slots = st.session_state.daily_slots_info[sel_day]
        for i in range(len(slots)):
            st.markdown(f"**[{slots[i]['label']}] 설정**")
            c_nm, c_del = st.columns([4, 1])
            slots[i]['label'] = c_nm.text_input(f"명칭", slots[i]['label'], key=f"nm_{sel_day}_{i}")
            if c_del.button("🗑️", key=f"del_{sel_day}_{i}"):
                slots.pop(i); st.rerun()
            s_ap, s_h, s_m = parse_time_to_ui(slots[i]['start'])
            c1, c2, c3 = st.columns(3)
            new_s_ap = c1.selectbox("시작 AM/PM", ["오전", "오후"], index=0 if s_ap=="오전" else 1, key=f"sap_{sel_day}_{i}")
            new_s_h = c2.selectbox("시작 시", list(range(1, 13)), index=s_h-1, key=f"sh_{sel_day}_{i}")
            new_s_m = c3.selectbox("시작 분", [f"{m:02d}" for m in range(0, 60, 5)], index=s_m//5, key=f"sm_{sel_day}_{i}")
            slots[i]['start'] = make_time(new_s_ap, new_s_h, new_s_m)
            e_ap, e_h, e_m = parse_time_to_ui(slots[i]['end'])
            c4, c5, c6 = st.columns(3)
            new_e_ap = c4.selectbox("종료 AM/PM", ["오전", "오후"], index=0 if e_ap=="오전" else 1, key=f"eap_{sel_day}_{i}")
            new_e_h = c5.selectbox("종료 시", list(range(1, 13)), index=e_h-1, key=f"eh_{sel_day}_{i}")
            new_e_m = c6.selectbox("종료 분", [f"{m:02d}" for m in range(0, 60, 5)], index=e_m//5, key=f"em_{sel_day}_{i}")
            new_end = make_time(new_e_ap, new_e_h, new_e_m)
            if new_end != slots[i]['end']:
                diff = get_total_min(new_end) - get_total_min(slots[i]['end'])
                slots[i]['end'] = new_end
                for j in range(i + 1, len(slots)):
                    slots[j]['start'] = add_minutes(slots[j]['start'], diff)
                    slots[j]['end'] = add_minutes(slots[j]['end'], diff)
                st.rerun()
            st.divider()
        if len(slots) < 10:
            if st.button("➕ 교시 추가"):
                last_end = slots[-1]['end'] if slots else time(9, 0)
                slots.append({"label": f"{len(slots)+1}교시", "start": last_end, "end": add_minutes(last_end, 150)})
                st.rerun()

    with st.expander("📌 고정(기존) 수업 지정", expanded=False):
        for d in t_days:
            opts = [s['label'] for s in st.session_state.daily_slots_info[d]]
            st.session_state.fixed_slots[d] = st.multiselect(f"{d} 고정교시", opts, default=st.session_state.fixed_slots.get(d, []))

    st.subheader("👤 학생 관리")
    is_edit = st.session_state.editing_index is not None
    with st.form("st_form", clear_on_submit=True):
        ed = st.session_state.students[st.session_state.editing_index] if is_edit else None
        f_name = st.text_input("이름", value=ed["이름"] if is_edit else "")
        f_school = st.text_input("학교", value=ed["학교"] if is_edit else "")
        f_grade = st.selectbox("학년", [f"{i}학년" for i in range(1, 7)], index=int(''.join(filter(str.isdigit, str(ed["학년"] if ed else "1"))))-1)
        f_subs = st.multiselect("과목", list(SUBJECT_INFO.keys()), default=ed["과목"] if is_edit else [])
        f_mom_tel = st.text_input("어머니 전화번호", value=ed.get("어머니 전화번호","") if is_edit else "")
        f_std_tel = st.text_input("학생 전화번호", value=ed.get("학생 전화번호","") if is_edit else "")
        f_wish = st.text_area("어머니 희망사항", value=ed.get("어머니 희망사항","") if is_edit else "")
        f_etc = st.text_area("비고", value=ed.get("비고","") if is_edit else "")
        f_sched = {}
        for d in t_days:
            opts = [s['label'] for s in st.session_state.daily_slots_info[d]]
            sel = st.multiselect(f"{d} 가능 교시", opts, default=ed["schedule"].get(d, []) if ed else [])
            if sel: f_sched[d] = sel
        if st.form_submit_button("✅ 정보 저장"):
            if f_name:
                data = {"이름": f_name, "학교": f_school, "학년": f_grade, "과목": f_subs, "어머니 전화번호": f_mom_tel, "학생 전화번호": f_std_tel, "어머니 희망사항": f_wish, "비고": f_etc, "schedule": f_sched}
                if is_edit: st.session_state.students[st.session_state.editing_index] = data
                else: st.session_state.students.append(data)
                st.session_state.editing_index = None
                st.rerun()

    st.divider()
    with st.expander("📂 전체 백업 및 복구", expanded=True):
        df_st = pd.DataFrame([
            {
                "이름": s['이름'], "학교": s['학교'], "학년": s['학년'], "과목": ",".join(s['과목']),
                "어머니 전화번호": s.get('어머니 전화번호',''), "학생 전화번호": s.get('학생 전화번호',''),
                "어머니 희망사항": s.get('어머니 희망사항',''), "비고": s.get('비고',''),
                "가능시간": schedule_to_text(s['schedule']) 
            } for s in st.session_state.students
        ])
        time_rows = [{"요일": d, "교시": s['label'], "시작": s['start'].strftime("%H:%M"), "종료": s['end'].strftime("%H:%M")} for d, sls in st.session_state.daily_slots_info.items() for s in sls]
        df_tm = pd.DataFrame(time_rows)
        df_fx = pd.DataFrame([{"요일": d, "고정": ",".join(v)} for d, v in st.session_state.fixed_slots.items()])
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            df_st.to_excel(writer, sheet_name='Students', index=False)
            df_tm.to_excel(writer, sheet_name='Times', index=False)
            df_fx.to_excel(writer, sheet_name='Fixed', index=False)
        st.download_button("📥 전체 데이터 백업", data=out.getvalue(), file_name="matching_backup.xlsx")
        up = st.file_uploader("📥 백업파일 업로드", type=["xlsx"])
        if up and st.button("🚀 전체 복구 실행"):
            try:
                sdf = pd.read_excel(up, sheet_name='Students').fillna("")
                st.session_state.students = [
                    {
                        "이름": r['이름'], "학교": r['학교'], "학년": r['학년'], "과목": str(r['과목']).split(','),
                        "어머니 전화번호": r['어머니 전화번호'], "학생 전화번호": r['학생 전화번호'],
                        "어머니 희망사항": r['어머니 희망사항'], "비고": r['비고'],
                        "schedule": text_to_schedule(r['가능시간']) 
                    } for _, r in sdf.iterrows()
                ]
                tdf = pd.read_excel(up, sheet_name='Times').fillna("")
                new_sl = {d: [] for d in ALL_DAYS}
                for _, r in tdf.iterrows():
                    new_sl[r['요일']].append({"label":r['교시'], "start":datetime.strptime(r['시작'], "%H:%M").time(), "end":datetime.strptime(r['종료'], "%H:%M").time()})
                st.session_state.daily_slots_info = new_sl
                fdf = pd.read_excel(up, sheet_name='Fixed').fillna("")
                for _, r in fdf.iterrows(): st.session_state.fixed_slots[r['요일']] = str(r['고정']).split(',') if r['고정'] else []
                st.success("복구 완료!"); st.rerun()
            except Exception as e: st.error(f"오류: {e}")

# 6. 메인 화면 출력
st.title("📅 가변형 팀 매칭 시스템 Pro")

def draw_table(t_days):
    min_m, max_m = 9*60, (24+1)*60
    for d in t_days:
        for s in st.session_state.daily_slots_info[d]:
            min_m, max_m = min(min_m, get_total_min(s['start'])), max(max_m, get_total_min(s['end']))
    time_steps = range((min_m // 30) * 30, ((max_m // 30) + 1) * 30, 30)
    html = '<table><tr style="background:#333; color:white;"><th style="width:100px;">시간</th>'
    for d in t_days: html += f'<th>{d}</th>'
    html += '</tr>'
    skips = {d: 0 for d in t_days}
    for m in time_steps:
        h = (m // 60) % 24
        ampm = "AM" if (m // 60) < 12 or (m // 60) >= 24 else "PM"
        display_h = h if h <= 12 else h - 12
        if display_h == 0: display_h = 12
        html += f'<tr><td class="time-col">{ampm} {display_h:02d}:{m%60:02d}</td>'
        for d in t_days:
            if skips[d] > 0: skips[d] -= 1; continue
            slot = next((s for s in st.session_state.daily_slots_info[d] if get_total_min(s['start']) == m), None)
            if slot:
                rowspan = max(1, (get_total_min(slot['end']) - get_total_min(slot['start'])) // 30)
                skips[d] = rowspan - 1
                is_f = slot['label'] in st.session_state.fixed_slots.get(d, [])
                avail = [s for s in st.session_state.students if d in s['schedule'] and slot['label'] in s['schedule'][d]]
                bg, txt = ("#4B0082", "white") if is_f else ("white", "#333")
                html += f'<td rowspan="{rowspan}" style="background:{bg}; color:{txt}; vertical-align:top; padding:5px; border:2px solid #fff; border-bottom:1px solid #ddd;">'
                html += f'<div class="{"fixed-title" if is_f else ""}" style="font-size:10px; color:{"#FFD700" if is_f else "#888"}; font-weight:bold;">{slot["label"]}</div>'
                for s in avail:
                    marks = "".join([f'<span class="sub-mark" style="background:{SUBJECT_INFO.get(sub, {"color":"#eee"})["color"]};">{SUBJECT_INFO.get(sub, {"short":sub[:1]})["short"]}</span>' for sub in s['과목']])
                    t_info = f"☎ 모: {s.get('어머니 전화번호','')}<br>☎ 학: {s.get('학생 전화번호','')}<br>💬 희망: {s.get('어머니 희망사항','')}<br>📝 비고: {s.get('비고','')}"
                    html += f'<div class="tooltip" style="font-size:12px; margin-bottom:4px;">{get_badge_html(s["학교"], s["학년"], is_f)}<b>{s["이름"]}</b>{marks}<span class="tooltiptext">{t_info}</span></div>'
                html += '</td>'
            else: html += '<td style="background:#fafafa;"></td>'
        html += '</tr>'
    st.markdown(html + '</table>', unsafe_allow_html=True)

draw_table(t_days)
