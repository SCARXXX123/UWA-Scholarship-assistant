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

# ================= 2. 数据加载与同步信息 =================
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

# ================= 3. 语言包配置 =================
I18N = {
    "Chinese": {
        "nav_sidebar": "⚙️ 系统设置",
        "lang_btn": "切换至 English",
        "sync_week": "📅 同步周期",
        "last_update": "📄 数据更新于",
        "main_title": "🎓 UWA 奖学金智能助手",
        "tab_match": "🔍 AI 智能匹配",
        "tab_index": "🌐 全部索引",
        "sub_bg": "👤 您的个人背景",
        "lbl_level": "学习阶段",
        "lbl_faculty": "所属学院 (Faculty/School)",
        "lbl_major": "专业关键词 (Major)",
        "lbl_intl": "我是国际学生 (International Student)",
        "lbl_extra": "详细背景描述 (GPA、经历等)",
        "placeholder_faculty": "例如：Engineering / Business School / Science...",
        "placeholder_extra": "请描述您的 GPA、原籍、具体科研或获奖经历等...",
        "btn_run": "🚀 让 AI 全权决策匹配",
        "report_title": "✨ AI 深度决策分析报告",
        "original_data": "查看 AI 扫描的数据池",
        "db_title": "📋 奖学金数据库全清单",
        "search_db": "🔍 搜索...",
        "no_db": "⚠️ 未发现数据库",
        "scanning": "🤖 正在深度分析中..."
    },
    "English": {
        "nav_sidebar": "⚙️ Settings",
        "lang_btn": "Switch to 中文",
        "sync_week": "📅 Sync Week",
        "last_update": "📄 Last Updated",
        "main_title": "🎓 UWA Scholarship Assistant",
        "tab_match": "🔍 AI Matching",
        "tab_index": "🌐 Full Index",
        "sub_bg": "👤 Your Background",
        "lbl_level": "Study Level",
        "lbl_faculty": "Faculty/School",
        "lbl_major": "Major Keywords",
        "lbl_intl": "International Student",
        "lbl_extra": "Detailed Background (GPA, Exp, etc.)",
        "placeholder_faculty": "e.g., Engineering / Law School / ABLE...",
        "placeholder_extra": "Describe your GPA, research, awards, origin in detail...",
        "btn_run": "🚀 Start AI Matching",
        "report_title": "✨ AI Deep Analysis Report",
        "original_data": "View raw data scanned by AI",
        "db_title": "📋 All Scholarships List",
        "search_db": "🔍 Search...",
        "no_db": "⚠️ Database not found.",
        "scanning": "🤖 Analyzing based on your full profile..."
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
    st.divider()
    if not df.empty:
        st.success(f"{texts['sync_week']}: {current_week_key}")
        st.info(f"{texts['last_update']}:\n{last_sync_time}")

st.title(texts["main_title"])
st.markdown("---")

tab1, tab2 = st.tabs([texts["tab_match"], texts["tab_index"]])

with tab1:
    col_input, col_res = st.columns([1, 1.5])
    with col_input:
        st.subheader(texts["sub_bg"])
        level = st.selectbox(texts["lbl_level"], ["Undergraduate", "Postgraduate", "HDR"])
        
        # 变更为手动输入
        faculty = st.text_input(texts["lbl_faculty"], placeholder=texts["placeholder_faculty"])
        
        major = st.text_input(texts["lbl_major"], value="Data Science")
        is_intl = st.toggle(texts["lbl_intl"], value=True)
        user_query = st.text_area(texts["lbl_extra"], height=350, placeholder=texts["placeholder_extra"])
        
        run_btn = st.button(texts["btn_run"], type="primary", use_container_width=True)

    with col_res:
        result_container = st.empty()
        if run_btn:
            with result_container.container():
                if df.empty:
                    st.error(texts["no_db"])
                else:
                    with st.spinner(texts["scanning"]):
                        # 扫描逻辑：综合专业和学院词频
                        df['relevance'] = (
                            df['Content_For_AI'].str.contains(major, case=False, na=False).astype(int) * 3 + 
                            df['Content_For_AI'].str.contains(faculty, case=False, na=False).astype(int)
                        )
                        # 选取前 25 条相关性最高的
                        context_df = df.sort_values(by='relevance', ascending=False).head(25)
                        
                        all_data_text = ""
                        for _, row in context_df.iterrows():
                            all_data_text += f"### 项目: {row['Title']}\n{row['Content_For_AI']}\n\n"

                        system_prompt = f"""
                        You are a professional UWA Scholarship Expert. Respond in {st.session_state.lang}.
                        
                        CRITICAL DECISION RULES:
                        1. LEVEL & FACULTY: Rigorously check if the scholarship is restricted to a specific Faculty or School (e.g., {faculty}). If it is for a different Faculty, it's NOT a match.
                        2. ELIGIBILITY: Assess GPA, Residency, and Course Level. Be honest and strict.
                        3. NO [BRACKETS]. Use Emojis and bold headers for a modern look.
                        
                        STRUCTURE:
                        - 🏆 **最推荐的项目 / Top Recommendations**
                        - 🔍 **背景深度测评 / Profile Assessment** (Include Faculty and Level check)
                        - 💡 **专家建议 / Pro Tips**
                        """

                        try:
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": f"User: Level={level}, Faculty={faculty}, Major={major}, Intl={is_intl}\nDetails: {user_query}\n\nCandidate Pool:\n{all_data_text}"}
                                ]
                            )
                            st.markdown(f"### {texts['report_title']}")
                            st.markdown(response.choices[0].message.content)
                            
                            with st.expander(texts["original_data"]):
                                for _, row in context_df.iterrows():
                                    st.write(f"📌 {row['Title']} ({row['Link']})")
                        except Exception as e:
                            st.error(f"AI Error: {e}")

with tab2:
    st.subheader(texts["db_title"])
    search_all = st.text_input(texts["search_db"], "")
    display_df = df.copy()
    if search_all:
        display_df = display_df[display_df['Title'].str.contains(search_all, case=False, na=False)]
    st.dataframe(display_df[['Title', 'Link']], use_container_width=True, hide_index=True)
