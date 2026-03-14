import streamlit as st
import pandas as pd
from openai import OpenAI
import os
import datetime

# ================= 1. 密钥与 AI 配置 =================
# 优先从 Streamlit Secrets 读取，本地运行则尝试环境变量
api_key = st.secrets.get("DEEPSEEK_API_KEY") or os.environ.get('DEEPSEEK_API_KEY')

# 如果都没有，则使用你之前的硬编码（建议仅用于紧急调试，随后删除）
if not api_key:
    api_key = "sk-9b3837671dbd4f159ab69e86138753ba"

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

# ================= 2. 数据处理逻辑 =================
@st.cache_data
def load_data():
    try:
        # 确保路径正确
        df = pd.read_csv("uwa_for_ai_analysis.csv")
        # 标记哪些是外部/异常链接
        df['is_external'] = df['Content_For_AI'].str.contains("EXTERNAL|LOAD_FAILED|SPECIAL", na=False)
        return df
    except Exception as e:
        st.error(f"数据加载失败: {e}")
        return pd.DataFrame()

# ================= 3. UI 界面设计 =================
st.set_page_config(page_title="UWA Scholarship AI", page_icon="🎓", layout="wide")

# 侧边栏：显示更新时间
if os.path.exists("uwa_for_ai_analysis.csv"):
    mtime = os.path.getmtime("uwa_for_ai_analysis.csv")
    last_update = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
    st.sidebar.info(f"📅 数据更新于: {last_update}")

st.title("🎓 UWA 奖学金智能匹配系统")
st.markdown("---")

df = load_data()

# 创建标签页
tab1, tab2 = st.tabs(["🔍 AI 智能匹配建议", "🌐 全部奖学金索引"])

# --- Tab 1: AI 智能匹配 ---
with tab1:
    col_input, col_res = st.columns([1, 2])

    with col_input:
        st.subheader("👤 您的个人背景")
        level = st.selectbox("学习阶段", ["Undergraduate", "Postgraduate", "HDR"])
        major = st.text_input("专业 (关键词)", value="Information Technology")
        faculty = st.text_input("学院", value="School of Physics, Mathematics and Computing")
        is_intl = st.checkbox("我是国际学生", value=True)
        user_query = st.text_area("补充信息 (选填)", placeholder="例如：GPA 6.5, 课外活动丰富...")

        run_btn = st.button("开始 AI 智能匹配", type="primary", use_container_width=True)

    with col_res:
        if run_btn:
            if df.empty:
                st.warning("暂无数据，请检查 CSV 文件是否已同步。")
            else:
                with st.spinner("🤖 AI 正在阅读奖学金简章并生成分析报告..."):
                    # 分离数据
                    normal_df = df[~df['is_external']]
                    external_df = df[df['is_external']]

                    # 1. 核心匹配逻辑：匹配专业关键词
                    # 匹配正常奖学金
                    match_normal = normal_df[
                        normal_df['Content_For_AI'].str.contains(major, case=False, na=False) | 
                        normal_df['Title'].str.contains(major, case=False, na=False)
                    ].head(8)
                    
                    # 匹配外部奖学金（仅比对 Title）
                    match_ext = external_df[
                        external_df['Title'].str.contains(major, case=False, na=False)
                    ].head(5)

                    # 2. 调用 AI
                    if not match_normal.empty:
                        # 构建上下文：包含标题以供 AI 引用
                        context_pieces = []
                        for _, row in match_normal.iterrows():
                            context_pieces.append(f"【奖学金标题: {row['Title']}】\n内容详情: {row['Content_For_AI']}")
                        
                        context_text = "\n\n".join(context_pieces)

                        try:
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": "你是一位专业的西澳大学(UWA)奖学金顾问。请根据提供的奖学金原文内容，结合用户背景给出具体的申请建议。要求：1. 必须明确提到奖学金的全称；2. 分析用户是否符合申请资格；3. 给出行动建议。"},
                                    {"role": "user", "content": f"用户背景: {level}, 专业: {major}, 国际生: {is_intl}。补充信息: {user_query}。\n\n参考资料:\n{context_text}"}
                                ]
                            )
                            
                            st.markdown("### ✨ AI 申请建议报告")
                            st.write(response.choices[0].message.content)

                            # --- 展示原文 Title 与链接 ---
                            st.markdown("---")
                            st.markdown("#### 🔗 参考奖学金原文 (点击展开)")
                            for _, row in match_normal.iterrows():
                                with st.expander(f"📌 {row['Title']}"):
                                    st.markdown(f"**官网链接:** [点击前往]({row['Link']})")
                                    st.write(row['Content_For_AI'])

                        except Exception as e:
                            st.error(f"AI 响应失败: {e}")
                    else:
                        st.info("💡 在标准奖学金库中未发现直接匹配。请查看下方的外部/特殊项目推荐。")

                    # --- 外部/模糊匹配推荐 ---
                    if not match_ext.empty:
                        st.markdown("---")
                        st.warning("🌟 发现可能相关的外部或特殊奖学金 (建议手动核对)")
                        for _, row in match_ext.iterrows():
                            st.markdown(f"**[{row['Title']}]({row['Link']})**")
                            st.caption(f"说明: {row['Content_For_AI']}")

# --- Tab 2: 全部索引 ---
with tab2:
    st.subheader("📋 奖学金数据库全清单")
    
    search_all = st.text_input("🔍 搜索任意关键词 (名称、内容、要求...)", "")
    
    display_df = df.copy()
    if search_all:
        display_df = display_df[
            display_df['Title'].str.contains(search_all, case=False, na=False) |
            display_df['Content_For_AI'].str.contains(search_all, case=False, na=False)
        ]

    st.dataframe(
        display_df[['Title', 'Link', 'is_external']],
        column_config={
            "Title": "奖学金名称",
            "Link": st.column_config.LinkColumn("详情链接"),
            "is_external": "是否为外部/特殊页面"
        },
        use_container_width=True,
        hide_index=True
    )

# --- 底部 ---
st.markdown("---")
st.caption("UWA Scholarship Assistant | Powered by DeepSeek AI & Playwright Crawler")
