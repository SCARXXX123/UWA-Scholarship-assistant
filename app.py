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
# 计算北京时间周数，确保每周一早上自动重载
now_bj = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
current_week_key = now_bj.strftime("%Y-W%W")

@st.cache_data(ttl=3600)
def load_data(week_key):
    try:
        if not os.path.exists("uwa_for_ai_analysis.csv"):
            return pd.DataFrame()
        df = pd.read_csv("uwa_for_ai_analysis.csv")
        # 标记外部链接或爬取失败的项目
        df['is_external'] = df['Content_For_AI'].str.contains("EXTERNAL|LOAD_FAILED|SPECIAL", na=False)
        return df
    except Exception as e:
        st.error(f"加载数据库失败: {e}")
        return pd.DataFrame()

# ================= 3. UI 界面设计 =================
st.set_page_config(page_title="UWA Scholarship AI", page_icon="🎓", layout="wide")

df = load_data(current_week_key)

# --- 侧边栏 ---
with st.sidebar:
    st.title("⚙️ 系统信息")
    if not df.empty and os.path.exists("uwa_for_ai_analysis.csv"):
        mtime = os.path.getmtime("uwa_for_ai_analysis.csv")
        last_update = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        st.success(f"📅 同步周期: {current_week_key}")
        st.info(f"📄 数据更新于:\n{last_update}")
    else:
        st.error("❌ 未发现数据文件")
    st.divider()
    st.caption("AI 建议仅供参考，具体请以官网为准。")

st.title("🎓 UWA 奖学金智能助手/UWA Scholarship Assistant")
st.markdown("---")

# 创建两个标签页
tab1, tab2 = st.tabs(["🔍 AI 智能匹配建议", "🌐 全部奖学金索引"])

# --- Tab 1: AI 智能匹配 (侧边长条布局) ---
with tab1:
    if df.empty:
        st.warning("⚠️ 数据库为空，请检查爬虫任务。")
    else:
        # 比例 [1.2, 2] 让左侧有足够的宽度延伸，同时右侧显示结果更宽敞
        col_input, col_res = st.columns([1.2, 2]) 

        with col_input:
            st.subheader("👤 您的个人背景")
            
            level = st.selectbox("学习阶段", [
                "Undergraduate (本科)", 
                "Postgraduate (授课型硕士)", 
                "HDR (博士/研究型硕士)"
            ])
            
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
            
            major = st.text_input("专业关键词", value="Information Technology")
            
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
            
            is_intl = st.checkbox("我是国际学生 (International Student)", value=True)
            
            st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
            
            # 增加垂直高度，满足你对“竖着长”的要求
            user_query = st.text_area(
                "补充信息 (详细背景描述)/Background Details", 
                placeholder="在此输入您的 GPA、原籍国、科研经历、特长等.../Enter your GPA,nationality,research experience,habit...",
                height=450  # 极长的垂直空间
            )

            st.markdown("<br>", unsafe_allow_html=True)
            run_btn = st.button("开始 AI 智能匹配", type="primary", use_container_width=True)

        with col_res:
            if run_btn:
                with st.spinner("🤖 AI 正在分析..."):
                    normal_df = df[~df['is_external']]
                    external_df = df[df['is_external']]

                    # 匹配逻辑
                    match_normal = normal_df[
                        normal_df['Content_For_AI'].str.contains(major, case=False, na=False) | 
                        normal_df['Title'].str.contains(major, case=False, na=False)
                    ]
                    
                    if match_normal.empty:
                        # 没搜到专业，用国际生通用奖学金保底
                        match_normal = normal_df[normal_df['Content_For_AI'].str.contains("International", case=False, na=False)].head(5)
                        st.info("💡 暂无直接匹配专业，为您推荐通用奖学金：")

                    match_ext = external_df[external_df['Title'].str.contains(major, case=False, na=False)].head(3)

                    if not match_normal.empty:
                        context_text = "\n\n".join([f"【{row['Title']}】\n{row['Content_For_AI']}" for _, row in match_normal.head(8).iterrows()])
                        
                        try:
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": "你是一位专业的西澳大学奖学金顾问。请根据资料给出针对性建议。"},
                                    {"role": "user", "content": f"背景: {level}, 专业: {major}, 国际生: {is_intl}。补充: {user_query}\n\n参考资料:\n{context_text}"}
                                ]
                            )
                            st.markdown("### ✨ AI 智能分析报告")
                            st.markdown(response.choices[0].message.content)
                            
                            st.divider()
                            st.markdown("#### 📚 参考原文清单")
                            for _, row in match_normal.iterrows():
                                with st.expander(f"📌 {row['Title']}"):
                                    st.markdown(f"**🔗 链接:** [{row['Link']}]({row['Link']})")
                                    st.code(row['Content_For_AI'], language="text")
                        except Exception as e:
                            st.error(f"AI 调用失败: {e}")
                    
                    if not match_ext.empty:
                        st.warning("🔗 发现可能相关的外部链接")
                        for _, row in match_ext.iterrows():
                            st.markdown(f"- **[{row['Title']}]({row['Link']})**")

# --- Tab 2: 全部索引 ---
with tab2:
    st.subheader("📋 UWA 奖学金数据库全清单/All Scholarships")
    
    # 顶部的搜索框
    search_all = st.text_input("🔍 在全库中搜索 (如：Global, Master, Engineering...)", "")
    
    display_df = df.copy()
    if search_all:
        display_df = display_df[
            display_df['Title'].str.contains(search_all, case=False, na=False) |
            display_df['Content_For_AI'].str.contains(search_all, case=False, na=False)
        ]

    # 使用 dataframe 展示，并配置链接列
    st.dataframe(
        display_df[['Title', 'Link', 'is_external']],
        column_config={
            "Title": "奖学金项目名称",
            "Link": st.column_config.LinkColumn("详情链接"),
            "is_external": "特殊链接"
        },
        use_container_width=True,
        hide_index=True
    )
