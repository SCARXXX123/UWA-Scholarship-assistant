import streamlit as st
import pandas as pd
from openai import OpenAI
import os
import datetime

# ================= 1. 密钥与 AI 配置 =================
api_key = st.secrets.get("DEEPSEEK_API_KEY") or os.environ.get('DEEPSEEK_API_KEY')
if not api_key:
    api_key = "sk-9b3837671dbd4f159ab69e86138753ba"

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ================= 2. 数据处理逻辑 =================
now_bj = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
current_week_key = now_bj.strftime("%Y-W%W")

@st.cache_data(ttl=3600)
def load_data(week_key):
    try:
        if not os.path.exists("uwa_for_ai_analysis.csv"):
            return pd.DataFrame()
        df = pd.read_csv("uwa_for_ai_analysis.csv")
        df['is_external'] = df['Content_For_AI'].str.contains("EXTERNAL|LOAD_FAILED|SPECIAL", na=False)
        return df
    except Exception as e:
        st.error(f"Error loading database: {e}")
        return pd.DataFrame()

# ================= 3. UI 界面设计 =================
st.set_page_config(page_title="UWA Scholarship AI", page_icon="🎓", layout="wide")

df = load_data(current_week_key)

# --- 语言切换逻辑 ---
if 'lang' not in st.session_state:
    st.session_state.lang = 'English'

def toggle_lang():
    st.session_state.lang = 'Chinese' if st.session_state.lang == 'English' else 'English'

# --- 侧边栏 ---
with st.sidebar:
    st.title("⚙️ System / 系统")
    st.button("🌐 Switch Language / 切换语言", on_click=toggle_lang)
    curr_l = st.session_state.lang
    
    st.write(f"**Current Language:** {curr_l}")
    if not df.empty:
        st.success("✅ Database Connected")
        st.caption(f"Sync Week: {current_week_key}")
    st.divider()
    st.caption("AI suggestions are for reference only. Please verify on the official UWA website.")

# --- 标题动态化 ---
main_title = "🎓 UWA Scholarship Assistant" if curr_l == 'English' else "🎓 UWA 奖学金智能助手"
st.title(main_title)
st.markdown("---")

tab_names = ["🔍 AI Matching", "🌐 Full Index"] if curr_l == 'English' else ["🔍 AI 智能匹配", "🌐 全部索引"]
tab1, tab2 = st.tabs(tab_names)

# --- Tab 1: AI 智能匹配 ---
with tab1:
    if df.empty:
        st.warning("Database is empty. Please check GitHub Actions.")
    else:
        col_input, col_res = st.columns([1.2, 2]) 

        with col_input:
            st.subheader("👤 Background" if curr_l == 'English' else "👤 个人背景")
            
            level = st.selectbox(
                "Study Level / 学习阶段", 
                ["Undergraduate", "Postgraduate (Coursework)", "HDR (PhD/Research)"]
            )
            major = st.text_input("Major Keywords / 专业关键词", value="Information Technology")
            is_intl = st.checkbox("International Student / 国际学生", value=True)
            
            user_query = st.text_area(
                "Details (GPA, Origin, Exp...) / 详细背景描述", 
                placeholder="Type here...",
                height=400 
            )

            run_btn_text = "Match Now" if curr_l == 'English' else "开始匹配"
            run_btn = st.button(run_btn_text, type="primary", use_container_width=True)

        with col_res:
            result_container = st.empty()
            
            if run_btn:
                with result_container.container():
                    with st.spinner("Analyzing..." if curr_l == 'English' else "正在分析..."):
                        normal_df = df[~df['is_external']]
                        external_df = df[df['is_external']]

                        # 1. 内部数据匹配
                        match_normal = normal_df[
                            normal_df['Content_For_AI'].str.contains(major, case=False, na=False) | 
                            normal_df['Title'].str.contains(major, case=False, na=False)
                        ].head(8)
                        
                        # 2. 外部链接模糊比对
                        # 简单逻辑：提取包含专业关键词的外部链接
                        match_ext = external_df[
                            external_df['Title'].str.contains(major, case=False, na=False)
                        ].head(3)

                        if match_normal.empty:
                            match_normal = normal_df[normal_df['Content_For_AI'].str.contains("International", case=False, na=False)].head(5)

                        # --- 构造 Prompt (全英文指令确保 AI 逻辑稳定) ---
                        prompt_lang = "Chinese" if curr_l == 'Chinese' else "English"
                        
                        system_prompt = f"""
                        You are a professional UWA Scholarship Consultant.
                        Your goal is to provide a rigorous and honest assessment based on provided data.

                        CRITICAL INSTRUCTIONS:
                        1. LANGUAGE: Output EVERYTHING in {prompt_lang}.
                        2. ELIGIBILITY CHECK: Be strict. If the user's GPA or background clearly does NOT meet the requirements in the data, explicitly state "Qualifications Not Met" for that specific item and explain why.
                        3. STRUCTURE:
                           - # [Recommended Scholarships]: List 1-3 specific names if they fit. If none fit, state clearly.
                           - # [Detailed Analysis]: Analyze Eligibility vs User Profile.
                           - # [Final Verdict]: Give a "High/Medium/Low" match score and reason.
                        4. HONESTY: Do not encourage the user if their background is insufficient. Give realistic advice.
                        """

                        context_text = "\n\n".join([f"TITLE: {row['Title']}\nCONTENT: {row['Content_For_AI']}" for _, row in match_normal.iterrows()])

                        try:
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": f"User Background: {level}, Major: {major}, Intl: {is_intl}. Extra Info: {user_query}\n\nScholarship Data:\n{context_text}"}
                                ]
                            )
                            
                            st.markdown(f"### ✨ {'Analysis Report' if curr_l == 'English' else '分析报告'}")
                            st.markdown(response.choices[0].message.content)
                            
                            # --- 外部链接区 (模糊比对输出) ---
                            st.divider()
                            ext_title = "🔗 External/Special Links" if curr_l == 'English' else "🔗 外部/特殊相关链接"
                            st.markdown(f"#### {ext_title}")
                            
                            if not match_ext.empty:
                                st.info("The following external links match your major keywords. Please check manually:" if curr_l == 'English' else "以下外部链接与您的专业关键词匹配，请手动核对：")
                                for _, row in match_ext.iterrows():
                                    st.markdown(f"- **[{row['Title']}]({row['Link']})**")
                            else:
                                no_ext_msg = "No specific external links matched your major today." if curr_l == 'English' else "今日暂无与您专业直接相关的外部特殊链接。"
                                st.write(no_ext_msg)

                            # --- 参考原文 ---
                            st.divider()
                            st.markdown(f"#### 📚 {'Reference Data' if curr_l == 'English' else '参考原文清单'}")
                            for _, row in match_normal.iterrows():
                                with st.expander(f"📌 {row['Title']}"):
                                    st.markdown(f"**Link:** [{row['Link']}]({row['Link']})")
                                    st.code(row['Content_For_AI'], language="text")

                        except Exception as e:
                            st.error(f"AI Error: {e}")

# --- Tab 2: 全部索引 ---
with tab2:
    st.subheader("📋 Scholarship List / 奖学金全清单")
    search_all = st.text_input("🔍 Search / 搜索", "")
    display_df = df.copy()
    if search_all:
        display_df = display_df[display_df['Title'].str.contains(search_all, case=False, na=False)]
    st.dataframe(display_df[['Title', 'Link', 'is_external']], use_container_width=True, hide_index=True)
