"""
Streamlit UI エントリ。サイドバーで「生成」「評価」ページを切り替える。
実行: streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="マーケティングAgent",
    layout="centered",
    initial_sidebar_state="auto",
)

# 全ページ共通のスタイル
st.markdown("""
<style>
.block-container { padding: 1.5rem 1rem; max-width: 780px; }
.stTextArea textarea { font-size: 1rem; line-height: 1.7; }
.stButton button { width: 100%; font-size: 1rem; padding: 0.6rem; }
.score-row { display: flex; gap: 0.6rem; flex-wrap: wrap; margin: 0.5rem 0; }
.badge {
    background: #f4f4f4;
    border-radius: 4px;
    padding: 0.25rem 0.7rem;
    font-size: 0.82rem;
    color: #333;
}
.log-line { font-family: monospace; font-size: 0.82rem; color: #555; padding: 2px 0; }
</style>
""", unsafe_allow_html=True)

import views_generate
import views_evaluate

pages = [
    st.Page(views_generate.render, title="生成", icon="✍️", url_path="generate", default=True),
    st.Page(views_evaluate.render, title="評価", icon="📊", url_path="evaluate"),
]
st.navigation(pages).run()
