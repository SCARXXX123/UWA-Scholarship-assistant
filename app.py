import streamlit as st
import pandas as pd
from openai import OpenAI
import os
import datetime

# ================= 1. 密钥与 AI 配置 =================
# 建议在 Streamlit Cloud 后台 Secrets 设置 DEEPSEEK_API_KEY
api_key = st.secrets.get("DEEPSEEK_API_KEY") or os.environ.get('DEEPSEEK_API_KEY')

# 备用 Key（请注意安全，项目上线后建议仅保留 Secrets 方式）
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
        if not os.path.exists("uwa_for_ai_analysis.csv"):
            return pd.DataFrame()
        df = pd.read_csv("uwa_for_ai_analysis.csv")
        # 标记外部/异常链接
        df['is_external'] = df['Content_For_AI'].str.contains("EXTERNAL|LOAD_FAILED|SPECIAL", na=False)
        return df
    except Exception as e:
        st.error(f"加载 CSV 失败: {e}")
        return pd.DataFrame()

# ================= 3. UI 界面设计 =================
st.set_page_config(page_title="UWA Scholarship AI", page_icon="🎓", layout="wide")

# 侧边栏：显示更新时间与系统状态
with st.sidebar:
    st.title("⚙️ 系统信息")
    if os.path.exists("uwa_for_ai_analysis.csv"):
        mtime = os.path.getmtime("uwa_for_ai_analysis.csv")
        last_update = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        st.success(f"📅 数据同步时间:\n{last_update}")
    else:
        st.error("❌ 未发现数据文件")
    
    st.divider()
    st.caption("注：AI 建议仅供参考，具体要求请以官网原文为准。")

st.title("🎓 UWA 奖学金智能匹配系统")
st.markdown("---")

df = load_data()

# 创建标签页
tab1, tab2 = st.tabs(["🔍 AI 智能匹配建议", "🌐 全部奖学金索引"])

# --- Tab 1: AI 智能匹配 ---
with tab1:
    if df.empty:
        st.warning("⚠️ 数据库为空，请检查爬虫任务是否成功运行并生成了 uwa_for_ai_analysis.csv")
    else:
        col_input, col_res = st.columns([1, 2])

        with col_input:
            st.subheader("👤 您的个人背景")
            level = st.selectbox("学习阶段", ["Undergraduate", "Postgraduate", "HDR"])
            major = st.text_input("专业 (关键词)", value="Information Technology")
            faculty = st.text_input("学院 (可选)", value="School of Physics, Mathematics and Computing")
            is_intl = st.checkbox("我是国际学生", value=True)
            user_query = st.text_area("补充信息 (如 GPA、特长等)", placeholder="例如：WAM 85, 有社团领导经历...")

            run_btn = st.button("开始 AI 智能匹配", type="primary", use_container_width=True)

        with col_res:
            if run_btn:
                with st.spinner("🤖 AI 正在全球检索并分析最适合您的方案..."):
                    # 分离数据
                    normal_df = df[~df['is_external']]
                    external_df = df[df['is_external']]

                    # 匹配逻辑 1: 尝试匹配专业关键词
                    match_normal = normal_df[
                        normal_df['Content_For_AI'].str.contains(major, case=False, na=False) | 
                        normal_df['Title'].str.contains(major, case=False, na=False)
                    ]
                    
                    # 匹配逻辑 2: 如果专业没搜到，拿“国际生”或“通用”奖学金保底，确保 AI 有东西说
                    is_fallback = False
                    if match_normal.empty:
                        is_fallback = True
                        match_normal = normal_df[
                            normal_df['Content_For_AI'].str.contains("International", case=False, na=False)
                        ].head(5)
                    else:
                        match_normal = match_normal.head(8)

                    # 匹配外部链接 (模糊推荐)
                    match_ext = external_df[
                        external_df['Title'].str.contains(major, case=False, na=False)
                    ].head(5)

                    # --- 执行 AI 分析 ---
                    if not match_normal.empty:
                        context_pieces = []
                        for _, row in match_normal.iterrows():
                            context_pieces.append(f"【项目名称：{row['Title']}】\n详情内容：{row['Content_For_AI']}")
                        
                        context_text = "\n\n".join(context_pieces)

                        try:
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": "你是一位专业的西澳大学奖学金顾问。请根据提供的资料给出针对性建议。必须提到具体奖学金名称。如果资料是保底推荐，请告知用户这些是通用型奖学金。"},
                                    {"role": "user", "content": f"用户背景: {level}, 专业: {major}, 国际生: {is_intl}。补充: {user_query}。\n\n资料库内容:\n{context_text}"}
                                ]
                            )
                            
                            if is_fallback:
                                st.info("💡 未发现专业直接匹配的项目，已为您筛选出 UWA 通用型奖学金供参考：")
                            
                            st.markdown("### ✨ AI 申请建议报告")
                            st.write(response.choices[0].message.content)

                            # --- 展示原文参考 (核心功能：Title + 链接 + 内容) ---
                            st.divider()
                            st.markdown("#### 📚 参考奖学金原文清单")
                            for _, row in match_normal.iterrows():
                                with st.expander(f"📌 {row['Title']}"):
                                    st.markdown(f"**🔗 官网直达:** [{row['Link']}]({row['Link']})")
                                    st.markdown("**📄 详细内容摘要:**")
                                    st.write(row['Content_For_AI'])

                        except Exception as e:
                            st.error(f"AI 调用失败: {e}")
                    else:
                        st.error("😿 抱歉，数据库中暂无任何可匹配的奖学金信息。")

                    # --- 展示外部链接模糊匹配 ---
                    if not match_ext.empty:
                        st.divider()
                        st.warning("🔗 发现可能相关的外部/特殊奖学金 (建议手动核对链接)")
                        for _, row in match_ext.iterrows():
                            st.markdown(f"- **[{row['Title']}]({row['Link']})**")

# --- Tab 2: 全部索引 ---
with tab2:
    st.subheader("📋 UWA 奖学金数据库全清单")
    
    search_all = st.text_input("🔍 全局搜索 (输入关键词，如 'Global', 'Research', 'Master' 等)", "")
    
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
            "is_external": "特殊/外部页面"
        },
        use_container_width=True,
        hide_index=True
    )
