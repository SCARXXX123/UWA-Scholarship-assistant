import streamlit as st
import pandas as pd
from openai import OpenAI
import os
import datetime

# ================= 1. AI 配置 =================
# 优先从 Secrets 读取，本地开发则读取环境变量
api_key = st.secrets.get("DEEPSEEK_API_KEY") or os.environ.get('DEEPSEEK_API_KEY')

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ================= 2. 数据加载 =================
# 西澳大学 (UWA) 所在地珀斯时区为 UTC+8
now_perth = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
current_week_key = now_perth.strftime("%Y-W%W")

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
        "nav_sidebar": "⚙️ 系统设置", 
        "lang_btn": "Switch to English",
        "sync_week": "📅 同步周期", 
        "last_update": "📄 数据更新于",
        "main_title": "🎓 UWA 奖学金智能助手", 
        "tab_match": "🔍 AI 智能分析",
        "tab_index": "🌐 数据索引", 
        "sub_bg": "👤 个人背景信息",
        "lbl_level": "当前身份 (Student Status)", 
        "level_opts": [
            "准本科生 - 高中升大学 (Future Undergraduate)", 
            "在读本科生 (Current Undergraduate)", 
            "准研究生 - 本科升研 (Future Postgraduate)", 
            "在读研究生 (Current Postgraduate)", 
            "高等学位研究 - 博士/研入 (HDR - PhD/Research)"
        ],
        "lbl_faculty": "所属学院 (Faculty/School)", 
        "lbl_major": "专业关键词 (Major)", 
        "lbl_intl": "身份类型",
        "lbl_extra": "其他背景/GPA/经历", 
        "btn_run": "🔥 开启全库智能扫描",
        "scanning": "🤖 正在检索并深度思考匹配方案...",
        "db_title": "📋 奖学金数据库", 
        "search_db": "搜索...",
        "model_sel": "选择 AI 大脑", 
        "model_help": "reasoner 模型（R1）更擅长处理复杂的入学资格逻辑"
    },
    "English": {
        "nav_sidebar": "⚙️ Settings", 
        "lang_btn": "切换至中文",
        "sync_week": "📅 Sync Week", 
        "last_update": "📄 Last Updated",
        "main_title": "🎓 UWA Scholarship AI", 
        "tab_match": "🔍 AI Analysis",
        "tab_index": "🌐 Data Index", 
        "sub_bg": "👤 Profile",
        "lbl_level": "Student Status", 
        "level_opts": [
            "Future Student - Undergraduate (Commencing)", 
            "Current Undergraduate Student", 
            "Future Student - Postgraduate (Commencing)", 
            "Current Postgraduate Student", 
            "Higher Degree by Research (HDR)"
        ],
        "lbl_faculty": "Faculty/School", 
        "lbl_major": "Major", 
        "lbl_intl": "Residency",
        "lbl_extra": "Extra (GPA, Awards, etc.)", 
        "btn_run": "🔥 Run Deep AI Scan",
        "scanning": "🤖 Thinking and matching scholarships...",
        "db_title": "📋 Database", 
        "search_db": "Search...",
        "model_sel": "AI Model", 
        "model_help": "Reasoner model (R1) is better for complex eligibility logic"
    }
}

# ================= 4. UI 界面 =================
st.set_page_config(page_title="UWA Scholarship AI", page_icon="🎓", layout="wide")

if 'lang' not in st.session_state: st.session_state.lang = 'Chinese'
def toggle_lang(): 
    st.session_state.lang = 'English' if st.session_state.lang == 'Chinese' else 'Chinese'

df, last_sync_time = load_data(current_week_key)
texts = I18N[st.session_state.lang]

with st.sidebar:
    st.title(texts["nav_sidebar"])
    st.button(texts["lang_btn"], on_click=toggle_lang)
    
    # 模型选择
    model_choice = st.selectbox(
        texts["model_sel"], 
        ["deepseek-chat", "deepseek-reasoner"], 
        help=texts["model_help"]
    )
    
    if not df.empty:
        st.divider()
        st.success(f"{texts['sync_week']}: {current_week_key}")
        st.info(f"{texts['last_update']}:\n{last_sync_time}")

st.title(texts["main_title"])
tab1, tab2 = st.tabs([texts["tab_match"], texts["tab_index"]])

with tab1:
    col_input, col_res = st.columns([1, 1.5])
    with col_input:
        st.subheader(texts["sub_bg"])
        level = st.selectbox(texts["lbl_level"], texts["level_opts"])
        faculty = st.text_input(texts["lbl_faculty"], placeholder="e.g. Engineering")
        major = st.text_input(texts["lbl_major"], placeholder="Information Technology")
        intl_status = st.radio(texts["lbl_intl"], ["International Student", "Domestic Student"], index=0)
        user_query = st.text_area(texts["lbl_extra"], height=250)
        run_btn = st.button(texts["btn_run"], type="primary", use_container_width=True)

    with col_res:
        if run_btn:
            if not api_key:
                st.error("API Key missing! Please configure it in Streamlit Secrets.")
                st.stop()
                
            with st.spinner(texts["scanning"]):
                # 1. 提取全量数据
                all_items = df.copy() 
                all_data_text = ""
                for i, row in all_items.iterrows():
                    ext_tag = "[External Link]" if row.get('is_external', False) else ""
                    all_data_text += f"--- {ext_tag} ID:{i} {row['Title']} ---\nContent: {row['Content_For_AI']}\nLink: {row['Link']}\n\n"

                # 2. 构建 Prompt
                target_lang = st.session_state.lang
                system_prompt = f"""
                你是一名在西澳大学(UWA)负责奖学金审核的首席顾问。请用{target_lang}回复。
                你的用户身份是：{intl_status}，学历：{level}，学院：{faculty}，专业：{major}。
                
                你的核心任务：
                1. 优先搜索普适性奖学金：忽略名字限制，寻找内容提到 "all disciplines" 或 "International Student Award" 的项目。
                2. 专业/学院精准匹配：根据 {faculty} 和 {major} 寻找定向奖学金。
                3. 外部链接模糊比对：对于标记为 'External Link Only' 的项目，根据标题联想并建议。
                4. 高GPA策略：如果提到 GPA/WAM > 80，必须解释 Global Excellence Scholarship 的自动发放机制。
                5. 状态宽容：Closed 的项目也要列出作为未来参考。
                6. 身份硬性过滤：严禁向 International Student 推荐只给 Domestic 的项目，反之亦然。
                7. 学历阶段匹配：确保推荐的项目符合用户的学习阶段({level})。
                
                输出模板（Markdown格式）：
                🔥 **核心匹配结果 (The Verdict)**
                🔍 **背景硬伤分析 (Reality Check)**
                🔗 **外部链接指路 (External Leads)**
                💡 **给高分学霸的特别建议**
                """

                try:
                    # 3. 调用 AI (支持流式输出)
                    placeholder = st.empty()
                    full_response = ""
                    
                    # 针对 Reasoner 模型的特殊处理（有些版本不支持 System Role，则合并到 User）
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"用户背景: {level}, {faculty}, {major}, {intl_status}\n补充描述: {user_query}\n\n数据库:\n{all_data_text}"}
                    ]
                    
                    response = client.chat.completions.create(
                        model=model_choice,
                        messages=messages,
                        stream=True
                    )
                    
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            full_response += chunk.choices[0].delta.content
                            placeholder.markdown(full_response + "▌")
                    
                    placeholder.markdown(full_response)
                            
                except Exception as e:
                    st.error(f"AI 调用出错: {e}")

with tab2:
    st.subheader(texts["db_title"])
    search = st.text_input(texts["search_db"])
    d_df = df[df['Title'].str.contains(search, case=False, na=False)] if search else df
    st.dataframe(d_df[['Title', 'Link']], use_container_width=True)
