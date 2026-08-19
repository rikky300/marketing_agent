"""AgentMark ローカルアプリ。「生成」と「評価」をタブで切り替える。
実行: streamlit run app.py → http://localhost:8501 が自動で開く
"""
import streamlit as st

from ui import ui_common

ui_common.setup_page("AgentMark", layout="wide", max_width="900px")

from ui import views_evaluate, views_generate

tab_generate, tab_evaluate = st.tabs(["① 生成", "② 評価"])
with tab_generate:
    views_generate.render()
with tab_evaluate:
    views_evaluate.render()
