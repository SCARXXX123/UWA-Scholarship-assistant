import streamlit as st
import pandas as pd
from openai import OpenAI
import os
import datetime

# ================= 1. AI 配置 =================
api_key = st.secrets.get("DEEPSEEK_API_KEY") or os.environ.get('DEEPSEEK_API_KEY')
if not api_key:
    api_key = "sk-9b3837671dbd4f159ab69e86138753ba"

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ================= 2. 数据加载 =================
now_bj = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
current_week_key = now_bj.strftime("%Y-W%W")

@st.cache_data(ttl=3600)
def load_data(week_key):
    if not os.path.exists("uwa_for_ai_analysis.csv"):
        return pd.DataFrame(), "None"
    df = pd.read_csv("uwa_for_ai_analysis.csv")
    mtime = os.path.getmtime("uwa_for_ai_analysis.csv")
    last_update = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
    return df, last_update

# ================= 3. 语言包 =================
I18N = {
    "Chinese": {
        "nav_sidebar": "⚙️ 系统设置", "lang_btn": "Switch to English",
        "sync_week": "📅 同步周期", "last_update": "📄 数据更新于",
        "main_title": "🎓 UWA 奖学金智能助手", "tab_match": "🔍 AI 智能分析",
        "tab_index": "🌐 数据索引", "sub_bg": "👤 个人背景信息",
        "lbl_level": "学习阶段", "lbl_faculty": "所属学院 (Faculty/School)",
        "lbl_major": "专业关键词 (Major)", "lbl_intl": "身份类型",
        "lbl_extra": "其他背景/GPA/经历", "btn_run": "🔥 开启全库智能扫描",
        "scanning": "🤖 正在检索专业项目及全校通用项目...",
        "db_title": "📋 奖学金数据库", "search_db": "搜索..."
    },
    "English": {
        "nav_sidebar": "⚙️ Settings", "lang_btn": "切换至中文",
        "sync_week": "📅 Sync Week", "last_update": "📄 Last Updated",
        "main_title": "🎓 UWA Scholarship AI", "tab_match": "🔍 AI Analysis",
        "tab_index": "🌐 Data Index", "sub_bg": "👤 Profile",
        "lbl_level": "Level", "lbl_faculty": "Faculty/School",
        "lbl_major": "Major", "lbl_intl": "Residency",
        "lbl_extra": "Extra (GPA, Awards, etc.)", "btn_run": "🔥 Run Deep AI Scan",
        "scanning": "🤖 Matching specialized and general scholarships...",
        "db_title": "📋 Database", "search_db": "Search..."
    }
}

# ================= 4. UI 界面 =================
st.set_page_config(page_title="UWA Scholarship AI", page_icon="🎓", layout="wide")
if 'lang' not in st.session_state: st.session_state.lang = 'Chinese'
def toggle_lang(): st.session_state.lang = 'English' if st.session_state.lang == 'Chinese' else 'Chinese'

df, last_sync_time = load_data(current_week_key)
texts = I18N[st.session_state.lang]

with st.sidebar:
    st.title(texts["nav_sidebar"])
    st.button(texts["lang_btn"], on_click=toggle_lang)
    if not df.empty:
        st.success(f"{texts['sync_week']}: {current_week_key}")
        st.info(f"{texts['last_update']}:\n{last_sync_time}")

st.title(texts["main_title"])
tab1, tab2 = st.tabs([texts["tab_match"], texts["tab_index"]])

with tab1:
    col_input, col_res = st.columns([1, 1.5])
    with col_input:
        st.subheader(texts["sub_bg"])
        level = st.selectbox(texts["lbl_level"], ["Undergraduate", "Postgraduate", "HDR"])
        faculty = st.text_input(texts["lbl_faculty"], placeholder="e.g. Engineering")
        major = st.text_input(texts["lbl_major"], value="Information Technology")
        intl_status = st.radio(texts["lbl_intl"], ["International Student", "Domestic Student"], index=0)
        user_query = st.text_area(texts["lbl_extra"], height=280)
        run_btn = st.button(texts["btn_run"], type="primary", use_container_width=True)

    with col_res:
        result_container = st.empty()
        if run_btn:
            with result_container.container():
                with st.spinner(texts["scanning"]):
                    # --- 【核心逻辑改进】 ---
                    # 1. 匹配专业或学院的项目
                    spec_match = df[df['Content_For_AI'].str.contains(f"{major}|{faculty}", case=False, na=False)]
                    # 2. 匹配“不限专业”的通用项目
                    gen_keywords = "any field|all disciplines|all courses|all faculties|any course|not restricted"
                    gen_match = df[df['Content_For_AI'].str.contains(gen_keywords, case=False, na=False)]
                    
                    # 合并并去重，取前 30 条以确保覆盖面
                    combined_df = pd.concat([spec_match, gen_match]).drop_duplicates().head(30)
                    
                    all_data_text = ""
                    for i, row in combined_df.iterrows():
                        all_data_text += f"--- [ID:{i}] {row['Title']} ---\nContent: {row['Content_For_AI']}\nLink: {row['Link']}\n\n"

                    # --- 更加锐利的 Prompt ---
                    target_lang = st.session_state.lang
                    system_prompt = f"""
                    你是一名在西澳大学(UWA)负责奖学金审核的首席顾问。请用{target_lang}回复。
                    
                    你的用户身份是：{intl_status}，学历：{level}，学院：{faculty}，专业：{major}。
                    
                    你的核心任务：
                    1. 优先搜索不限制专业学院的奖学金：忽略名字里的限制，优先看内容是否提到 "all disciplines" 或 "International Student Award"。绝对不能因为用户填了{major}和{faculty}就忽略掉这些普适性大奖。
                    2.根据用户给出的{faculty}和{major}寻找有无专门给这个专业或学院的学生的奖学金。
                    3. 外部链接模糊比对：对于标记为 'External Link Only' 的项目，即便没有详情，也要根据标题进行联想。例如标题带 'Engineering'，而用户专业是 {major}，则必须告知用户：“这个链接看起来高度相关，建议官网确认。”
                    4. 针对高GPA的关怀：如果用户提到 GPA/WAM > 80，必须主动提及 UWA 经典的 "Global Excellence Scholarship"，解释其自动发放的机制。
                    5. 区分“当下申请”与“未来关注”：Close 的项目也要查询，只要符合要求就列出，作为明年或下学期的目标。
                    6. 诚实告知不符项：若无完全匹配，解释是因为身份、学历还是专业限制。
                    
                    
                    输出模版：
                    🔥 **核心匹配结果 (The Verdict)** - 符合就推，不符合就直说，别磨叽。
                    🔍 **背景硬伤分析 (Reality Check)** - 为什么这波数据里有些项目你申请不了？
                    🔗 **外部链接指路 (External Leads)** - 哪怕没有完美匹配，也要给用户 1-2 个官网方向。
                    💡 **给高分学霸的特别建议** - 针对 GPA 表现给出的具体申奖策略。
                    """
                    try:
                        response = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": f"背景: {level}, 学院: {faculty}, 专业: {major}, 身份: {intl_status}\n额外信息: {user_query}\n\n候选池:\n{all_data_text}"}
                            ]
                        )
                        st.markdown(response.choices[0].message.content)
                        with st.expander("🔗 原始参考列表"):
                            st.table(combined_df[['Title', 'Link']])
                    except Exception as e:
                        st.error(f"AI Error: {e}")

with tab2:
    st.subheader(texts["db_title"])
    search = st.text_input(texts["search_db"])
    d_df = df[df['Title'].str.contains(search, case=False, na=False)] if search else df
    st.dataframe(d_df[['Title', 'Link']], use_container_width=True)
