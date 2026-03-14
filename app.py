import streamlit as st
import pandas as pd
from openai import OpenAI
import os

# ================= 1. 密钥与 AI 配置 =================
# 提醒：部署时请在后台设置 DEEPSEEK_API_KEY 环境变量
api_key_from_env = os.environ.get('DEEPSEEK_API_KEY', "sk-9b3837671dbd4f159ab69e86138753ba")

client = OpenAI(
    api_key=api_key_from_env,
    base_url="https://api.deepseek.com"
)


# ================= 2. 数据处理逻辑 =================
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("uwa_for_ai_analysis.csv")
        # 标记哪些是外部/异常链接，方便后续分类展示
        df['is_external'] = df['Content_For_AI'].str.contains("EXTERNAL|LOAD_FAILED|SPECIAL", na=False)
        return df
    except:
        st.error("数据加载失败，请检查 uwa_for_ai_analysis.csv 是否存在。")
        return pd.DataFrame()


# ================= 3. UI 界面设计 =================
st.set_page_config(page_title="UWA Scholarship AI", page_icon="🎓", layout="wide")

st.title("🎓 UWA 奖学金智能匹配与索引系统")

df = load_data()

# 创建标签页
tab1, tab2 = st.tabs(["🔍 AI 匹配建议", "🌐 外部/特殊奖学金汇总"])

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

        run_btn = st.button("开始匹配", type="primary", use_container_width=True)

    with col_res:
        if run_btn:
            if df.empty:
                st.warning("暂无数据，请检查 CSV 文件。")
            else:
                with st.spinner("正在全局检索并生成分析报告..."):
                    # 分类检索：正常内容用于 AI 分析，外部内容用于链接展示
                    normal_df = df[~df['is_external']]
                    external_df = df[df['is_external']]

                    # 匹配逻辑
                    match_normal = normal_df[
                        normal_df['Content_For_AI'].str.contains(major, case=False, na=False)].head(5)
                    match_ext = external_df[external_df['Title'].str.contains(major, case=False, na=False)].head(5)

                    # AI 分析部分
                    context_text = "\n\n".join(match_normal['Content_For_AI'].tolist())

                    try:
                        response = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[
                                {"role": "system",
                                 "content": "你是一位专业的西澳大学顾问。请根据提供的奖学金信息，结合用户背景给出具体的申请建议。"},
                                {"role": "user",
                                 "content": f"背景:{level}, {major}, 国际生:{is_intl}。资料:\n{context_text}"}
                            ]
                        )
                        st.markdown("### ✨ AI 申请建议")
                        st.write(response.choices[0].message.content)

                        # 展示正常链接
                        st.markdown("#### 🔗 官网直达链接")
                        for _, row in match_normal.iterrows():
                            st.markdown(f"- **[{row['Title']}]({row['Link']})**")

                        # --- 结合外部链接展示 ---
                        if not match_ext.empty:
                            st.markdown("---")
                            st.warning("💡 发现以下可能相关的外部/特殊奖学金 (AI 无法读取正文，建议手动查看)：")
                            for _, row in match_ext.iterrows():
                                st.markdown(f"- **[{row['Title']}]({row['Link']})**")

                    except Exception as e:
                        st.error(f"AI 响应失败: {e}")
        else:
            st.info("请在左侧填写信息并点击“开始匹配”。")

# --- Tab 2: 外部链接汇总 ---
with tab2:
    st.subheader("📋 外部链接与非标准页面清单")
    st.markdown("这些奖学金通常由第三方机构、协会或特定捐赠者提供，跳转至非 UWA 官网或为 PDF 附件。")

    # 只显示外部数据
    ext_all = df[df['is_external']]

    search_ext = st.text_input("🔍 搜索外部奖学金名称", "")
    if search_ext:
        ext_all = ext_all[ext_all['Title'].str.contains(search_ext, case=False)]

    st.dataframe(
        ext_all[['Title', 'Link', 'Content_For_AI']],
        column_config={
            "Title": "奖学金名称",
            "Link": st.column_config.LinkColumn("直达链接"),
            "Content_For_AI": "说明"
        },
        use_container_width=True,
        hide_index=True
    )

# --- 底部 ---
st.markdown("---")
st.caption("UWA Scholarship Scraper v1.0 | 每日自动更新")