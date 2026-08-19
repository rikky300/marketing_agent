"""ページ共通のセットアップ（set_page_config + CSS）。app.py から呼ぶ。"""
import streamlit as st

_CSS = """
<style>
/* Streamlitの余計な表示（上部ツールバー・メニュー・フッター）を隠す */
#MainMenu {{ visibility: hidden; }}
header {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
.block-container {{ padding: 1.5rem 1rem; max-width: {max_width}; }}
.stTextArea textarea {{ font-size: 1rem; line-height: 1.7; }}
.stButton button {{ width: 100%; font-size: 1rem; padding: 0.6rem; }}
.score-row {{ display: flex; gap: 0.6rem; flex-wrap: wrap; margin: 0.5rem 0; }}
.badge {{ background: #f4f4f4; border-radius: 4px; padding: 0.25rem 0.7rem; font-size: 0.82rem; color: #333; }}
.log-line {{ font-family: monospace; font-size: 0.82rem; color: #555; padding: 2px 0; }}
</style>
"""


def setup_page(title, layout="centered", max_width="780px"):
    """各アプリの最初に呼ぶ（set_page_config は最初のStreamlit命令である必要がある）。"""
    st.set_page_config(page_title=title, layout=layout, initial_sidebar_state="collapsed")
    st.markdown(_CSS.format(max_width=max_width), unsafe_allow_html=True)
