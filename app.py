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

# ================= 2. 数据处理与定时刷新 =================
now_bj = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
current_week_key = now_bj.strftime("%Y-W%W")

@st.cache_data(ttl=3600)
def load_data(week_key):
    try:
        if not os.path.exists("uwa_for_ai_analysis.csv"): return pd.DataFrame()
        df = pd.read_csv("uwa_for_ai_analysis.csv")
        df['is_external'] = df['Content_For_AI'].str.contains("EXTERNAL|LOAD_FAILED|SPECIAL", na=False)
        return df
    except Exception as e:
        st.error(f"加载失败: {e}"); return pd.DataFrame()

# ================= 3. UI 界面设计 =================
st.set_page_config(page_title="UWA Scholarship AI", page_icon="🎓", layout="wide")
df = load_data(current_week_key)

# 侧边栏
with st.sidebar:
    st.title("⚙️ 系统信息")
    if not df.empty:
        st.success(f"📅 同步周: {current_week_key}")
        st.info(f"📄 文件更新于: \n{datetime.datetime.fromtimestamp(os.path.getmtime('uwa_for_ai_analysis.csv')).strftime('%Y-%m-%d %H:%M:%S')}")
    st.divider()
    st.caption("AI 建议仅供参考")

st.title("🎓 UWA 奖学金智能匹配系统")
st.markdown("---")

tab1, tab2 = st.tabs(["🔍 AI 智能匹配建议", "🌐 全部奖学金索引"])

with tab1:
    if df.empty:
        st.warning("⚠️ 数据库为空")
    else:
        # --- 核心布局修改：适当调大左侧比例，让它有空间垂直伸展 ---
        col_input, col_res = st.columns([1.2, 2]) 

        with col_input:
            st.subheader("👤 您的个人背景")
            
            # 增加这些组件的垂直间距感
            level = st.selectbox("学习阶段", [
                "Undergraduate (本科)", 
                "Postgraduate (授课型硕士)", 
                "HDR (博士/研究型硕士)"
            ])
            
            st.markdown("<br>", unsafe_allow_html=True) # 增加物理间距
            
            major = st.text_input("专业关键词", value="Information Technology")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            is_intl = st.checkbox("我是国际学生", value=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 【关键修改】大幅增加高度（Height），让它在竖直方向上“长”出来
            user_query = st.text_area(
                "补充信息 (详细描述您的 GPA、背景、需求等)", 
                placeholder="在此输入您的详细背景...",
                height=400  # 这里直接拉长到 400 像素，确保它在页面上非常醒目
            )

            st.markdown("<br>", unsafe_allow_html=True)
            run_btn = st.button("开始 AI 智能匹配", type="primary", use_container_width=True)

        with col_res:
            if run_btn:
                # 结果显示逻辑保持不变...
                with st.spinner("🤖 AI 分析中..."):
                    normal_df = df[~df['is_external']]
                    match_normal = normal_df[normal_df['Content_For_AI'].str.contains(major, case=False, na=False) | normal_df['Title'].str.contains(major, case=False, na=False)]
                    if match_normal.empty:
                        match_normal = normal_df[normal_df['Content_For_AI'].str.contains("International", case=False, na=False)].head(5)
                    
                    if not match_normal.empty:
                        context_text = "\n\n".join([f"【{row['Title']}】\n{row['Content_For_AI']}" for _, row in match_normal.head(8).iterrows()])
                        try:
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": "你是一位专业的西澳大学奖学金顾问。"},
                                    {"role": "user", "content": f"背景: {level}, 专业: {major}, 补充: {user_query}\n\n资料:\n{context_text}"}
                                ]
                            )
                            st.markdown("### ✨ AI 智能分析报告")
                            st.markdown(response.choices[0].message.content)
                            st.divider()
                            st.markdown("#### 📚 参考原文")
                            for _, row in match_normal.iterrows():
                                with st.expander(f"📌 {row['Title']}"):
                                    st.markdown(f"**🔗 链接:** [{row['Link']}]({row['Link']})")
                                    st.code(row['Content_For_AI'], language="text")
                        except Exception as e:
                            st.error(f"AI 调用失败: {e}")
