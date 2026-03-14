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
@st.cache_data(ttl=3600)
def load_data():
    if not os.path.exists("uwa_for_ai_analysis.csv"):
        return pd.DataFrame()
    return pd.read_csv("uwa_for_ai_analysis.csv")

# ================= 3. UI 界面 =================
st.set_page_config(page_title="UWA Scholarship AI", page_icon="🎓", layout="wide")
df = load_data()

# 语言状态管理
if 'lang' not in st.session_state: st.session_state.lang = 'Chinese'
def toggle_lang(): st.session_state.lang = 'Chinese' if st.session_state.lang == 'English' else 'English'

with st.sidebar:
    st.title("⚙️ Settings")
    st.button("🌐 切换语言 / Switch Language", on_click=toggle_lang)
    curr_l = st.session_state.lang
    st.divider()
    st.caption("当前模式：全数据 AI 智能决策模式")

st.title("🎓 UWA 奖学金智能助手" if curr_l == 'Chinese' else "🎓 UWA Scholarship Assistant")

tab1, tab2 = st.tabs(["🔍 AI 匹配", "🌐 数据索引"])

with tab1:
    col_input, col_res = st.columns([1, 1.5]) # 调整比例
    
    with col_input:
        st.subheader("👤 您的信息")
        # 仅保留最基础的输入，不参与 Python 过滤，只作为背景发给 AI
        level = st.selectbox("学习阶段", ["Undergraduate", "Postgraduate", "HDR"])
        major = st.text_input("专业关键词", value="Information Technology")
        is_intl = st.toggle("我是国际学生", value=True)
        user_query = st.text_area("详细背景 (GPA/原籍/经历等)", height=300, 
                                 placeholder="把你的背景一股脑写在这里，让 AI 帮你挑...")
        
        run_btn = st.button("🚀 让 AI 全权筛选", type="primary", use_container_width=True)

    with col_res:
        result_container = st.empty()
        if run_btn:
            with result_container.container():
                if df.empty:
                    st.error("数据库丢失，请检查文件。")
                else:
                    with st.spinner("🤖 正在全库扫描并决策中..."):
                        # --- 不再做任何物理过滤，直接按专业相关性排个序，取前 15-20 条给 AI ---
                        # 这里的排序只是为了不超出 AI 的字数限制（Token）
                        df['relevance'] = df['Content_For_AI'].str.contains(major, case=False, na=False)
                        context_df = df.sort_values(by='relevance', ascending=False).head(20)
                        
                        # 把这 20 条奖学金的所有信息打包
                        all_data_text = ""
                        for _, row in context_df.iterrows():
                            all_data_text += f"--- 项目: {row['Title']} ---\n{row['Content_For_AI']}\n\n"

                        # --- 强大的 System Prompt，赋予 AI 全权 ---
                        target_lang = "Chinese" if curr_l == 'Chinese' else "English"
                        system_prompt = f"""
                        You are the ULTIMATE UWA Scholarship Expert. 
                        Your job is to screen the provided data and find matches.
                        
                        CRITICAL RULES:
                        1. FULL DECISION POWER: You decide if the user is eligible. Read the 'Level', 'Residency', and 'Academic requirements' in the data carefully.
                        2. REJECT IRRELEVANT ITEMS: If a scholarship is for Undergrads and user is Postgrad, IGNORE it. Do not even mention it as a negative case unless it's a near-miss.
                        3. BE HUMAN: Use Emojis, bold text, and clear sections. No [brackets].
                        4. LANGUAGE: Always respond in {target_lang}.
                        
                        RESPONSE STRUCTURE:
                        - 🏆 **最推荐的项目** (If any)
                        - 🔍 **匹配度深度测评** (Explain why you picked them or why they fit/don't fit)
                        - 💡 **避坑指南 & 建议** (Next steps)
                        """

                        try:
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": f"用户背景: {level}, 专业: {major}, 国际生: {is_intl}。补充: {user_query}\n\n候选奖学金池:\n{all_data_text}"}
                                ]
                            )
                            st.markdown("### ✨ AI 深度决策分析")
                            st.markdown(response.choices[0].message.content)
                            
                            with st.expander("查看 AI 扫描的原始数据池"):
                                st.write(context_df[['Title', 'Link']])
                        except Exception as e:
                            st.error(f"AI 调用失败: {e}")

with tab2:
    st.subheader("📋 原始数据库")
    st.dataframe(df[['Title', 'Link']], use_container_width=True)
