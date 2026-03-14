import streamlit as st
import pandas as pd
from openai import OpenAI
import os
import datetime

# ================= 1. 密钥与 AI 配置 =================
# 建议在 Streamlit Cloud 后台 Secrets 设置 DEEPSEEK_API_KEY
api_key = st.secrets.get("DEEPSEEK_API_KEY") or os.environ.get('DEEPSEEK_API_KEY')

# 备用 Key
if not api_key:
    api_key = "sk-9b3837671dbd4f159ab69e86138753ba"

client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

# ================= 2. 数据处理与定时刷新逻辑 =================

# 核心：计算一个“周钩子”，确保每周一早上刷新缓存
# 北京时间是 UTC+8
now_bj = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
# 生成类似 "2023-W45" 的字符串。每周一凌晨这个值都会变，从而强制 st.cache_data 失效重读
current_week_key = now_bj.strftime("%Y-W%W")

@st.cache_data(ttl=3600)  # 每小时额外检查一次
def load_data(week_key):
    try:
        if not os.path.exists("uwa_for_ai_analysis.csv"):
            return pd.DataFrame()
        # 加载最新的 CSV 文件
        df = pd.read_csv("uwa_for_ai_analysis.csv")
        # 标记外部/异常链接 (排除掉爬虫标记为 EXTERNAL 或 LOAD_FAILED 的条目)
        df['is_external'] = df['Content_For_AI'].str.contains("EXTERNAL|LOAD_FAILED|SPECIAL", na=False)
        return df
    except Exception as e:
        st.error(f"加载数据库失败: {e}")
        return pd.DataFrame()

# ================= 3. UI 界面设计 =================
st.set_page_config(page_title="UWA Scholarship AI", page_icon="🎓", layout="wide")

# 加载数据（传入 week_key 确保每周自动刷新）
df = load_data(current_week_key)

# 侧边栏：显示更新时间与系统状态
with st.sidebar:
    st.title("⚙️ 系统信息")
    if not df.empty and os.path.exists("uwa_for_ai_analysis.csv"):
        mtime = os.path.getmtime("uwa_for_ai_analysis.csv")
        last_update = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        st.success(f"📅 数据库同步周: {current_week_key}")
        st.info(f"📄 文件最后更新:\n{last_update}")
    else:
        st.error("❌ 未发现数据文件，请检查 GitHub Actions")
    
    st.divider()
    st.caption("注：AI 匹配基于爬虫采集的官网实时数据，建议申请前点击原文链接核实。")

st.title("🎓 UWA 奖学金智能匹配系统")
st.markdown("---")

# 创建标签页
tab1, tab2 = st.tabs(["🔍 AI 智能匹配建议", "🌐 全部奖学金索引"])

# --- Tab 1: AI 智能匹配 ---
with tab1:
    if df.empty:
        st.warning("⚠️ 数据库暂无数据。请确保 GitHub 仓库中存在 uwa_for_ai_analysis.csv 文件。")
    else:
        col_input, col_res = st.columns([1, 2])

        with col_input:
            st.subheader("👤 您的个人背景")
            level = st.selectbox("学习阶段", ["Undergraduate", "Postgraduate", "HDR"])
            major = st.text_input("专业关键词", value="Information Technology")
            is_intl = st.checkbox("我是国际学生 (International Student)", value=True)
            user_query = st.text_area("其他信息 (如 GPA、国家、特长等)", placeholder="例如：来自中国，WAM 80, 申请 2026 录取...")

            run_btn = st.button("开始 AI 智能匹配", type="primary", use_container_width=True)

        with col_res:
            if run_btn:
                with st.spinner("🤖 AI 正在检索最新奖学金库并生成报告..."):
                    # 分离标准数据和外部链接数据
                    normal_df = df[~df['is_external']]
                    external_df = df[df['is_external']]

                    # 1. 匹配逻辑：优先搜索专业关键词
                    match_normal = normal_df[
                        normal_df['Content_For_AI'].str.contains(major, case=False, na=False) | 
                        normal_df['Title'].str.contains(major, case=False, na=False)
                    ]
                    
                    # 2. 保底逻辑：如果专业没搜到，推荐“国际学生”通用奖学金
                    is_fallback = False
                    if match_normal.empty:
                        is_fallback = True
                        match_normal = normal_df[
                            normal_df['Content_For_AI'].str.contains("International", case=False, na=False)
                        ].head(5)
                    else:
                        match_normal = match_normal.head(8) # 限制给 AI 的参考量

                    # 3. 外部链接模糊匹配
                    match_ext = external_df[
                        external_df['Title'].str.contains(major, case=False, na=False)
                    ].head(3)

                    # --- 执行 AI 分析 ---
                    if not match_normal.empty:
                        context_pieces = []
                        for _, row in match_normal.iterrows():
                            context_pieces.append(f"【项目：{row['Title']}】\n详情：{row['Content_For_AI']}")
                        
                        context_text = "\n\n".join(context_pieces)

                        try:
                            response = client.chat.completions.create(
                                model="deepseek-chat",
                                messages=[
                                    {"role": "system", "content": "你是一位专业的西澳大学(UWA)奖学金顾问。请根据提供的资料给出针对性申请建议。必须列出奖学金全称。如果匹配结果是通用的，请告知用户这是保底推荐。"},
                                    {"role": "user", "content": f"用户背景: {level}, 专业: {major}, 国际生: {is_intl}。补充: {user_query}。\n\n数据库提取内容:\n{context_text}"}
                                ]
                            )
                            
                            if is_fallback:
                                st.info("💡 未发现专业直接匹配的项目，已为您筛选出 UWA 国际生通用奖学金：")
                            
                            st.markdown("### ✨ AI 智能分析报告")
                            st.markdown(response.choices[0].message.content)

                            # --- 展示原文参考 (解决“不动了”的问题，直接列出原文) ---
                            st.divider()
                            st.markdown("#### 📚 关联奖学金原文 (点击展开)")
                            for _, row in match_normal.iterrows():
                                with st.expander(f"📌 {row['Title']}"):
                                    st.markdown(f"**🔗 官网直达:** [{row['Link']}]({row['Link']})")
                                    st.markdown("**📄 采集到的详细信息:**")
                                    st.code(row['Content_For_AI'], language="text")

                        except Exception as e:
                            st.error(f"AI 调用失败，请检查密钥或网络: {e}")
                    else:
                        st.error("😿 数据库中暂未发现可匹配的信息，请尝试更换专业关键词。")

                    # --- 展示外部/特殊链接 ---
                    if not match_ext.empty:
                        st.markdown("---")
                        st.warning("🔗 发现可能相关的外部/特殊奖学金 (需手动查看)")
                        for _, row in match_ext.iterrows():
                            st.markdown(f"- **[{row['Title']}]({row['Link']})**")

# --- Tab 2: 全部索引 ---
with tab2:
    st.subheader("📋 奖学金数据库索引 (实时同步)")
    
    search_all = st.text_input("🔍 全局搜索奖学金名称或内容", "")
    
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
            "Link": st.column_config.LinkColumn("查看详情", width="medium"),
            "is_external": "特殊/外部页面"
        },
        use_container_width=True,
        hide_index=True
    )
