"""
Streamlit UI。ブラウザからテーマを選んで投稿を生成する。
実行: streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="SNSマーケティングAgent",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container { padding: 1.5rem 1rem; max-width: 680px; }
.stTextArea textarea { font-size: 1rem; line-height: 1.7; }
.stButton button { width: 100%; font-size: 1rem; padding: 0.6rem; }
.copy-btn {
    display: inline-block;
    background: #1a1a1a;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 0.4rem 1.2rem;
    font-size: 0.9rem;
    cursor: pointer;
    margin-top: 0.5rem;
}
.copy-btn:hover { background: #333; }
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

from graph import app as agent

PRESET_THEMES = [
    "開発の裏側",
    "このツールで解決したい課題",
    "新しく作っている機能",
    "個人開発でつまずいたこと",
    "どんな人に使ってほしいか",
]

for key, default in [("result", None), ("logs", []), ("running", False)]:
    if key not in st.session_state:
        st.session_state[key] = default

st.title("SNS マーケティング Agent")
st.caption("プロダクト情報をもとに、Xの投稿案を自動生成します")
st.divider()

st.subheader("テーマ")
preset = st.selectbox("プリセットから選ぶ", ["（自由入力）"] + PRESET_THEMES)
free_input = st.text_input("または自由に入力", placeholder="例: リリースのお知らせ")

if preset != "（自由入力）":
    theme = preset
elif free_input.strip():
    theme = free_input.strip()
else:
    theme = PRESET_THEMES[0]

if st.button("投稿を生成する", type="primary", disabled=st.session_state.running):
    st.session_state.result = None
    st.session_state.logs = []
    st.session_state.running = True

    with st.spinner(f"『{theme}』で投稿を生成中..."):
        logs = []
        for step in agent.stream(
            {"theme": theme, "context": "", "draft": "", "evaluation": None, "revisions": 0},
            stream_mode="updates",
        ):
            node_name = list(step.keys())[0]
            update = list(step.values())[0]

            if node_name == "retrieve":
                logs.append("[検索] 関連情報を取得")
            elif node_name == "generate":
                e = update.get("evaluation")
                s = (e.hook + e.specificity) if e else "?"
                logs.append(f"[生成] 3案から最良を選択 → {s}点")
            elif node_name == "revise":
                n = update.get("revisions", "?")
                logs.append(f"[修正{n}回目] コメントを反映して書き直し")
            elif node_name == "evaluate":
                e = update.get("evaluation")
                s = (e.hook + e.specificity) if e else "?"
                logs.append(f"[採点] {s}点")

            if update.get("draft"):
                st.session_state.result = update

        st.session_state.logs = logs
        st.session_state.running = False
    st.rerun()

if st.session_state.result:
    result = st.session_state.result
    e = result.get("evaluation")
    draft = result.get("draft", "")
    revisions = result.get("revisions", 0)

    st.divider()
    st.subheader("完成した投稿")

    st.text_area("Xに貼り付けてください", value=draft, height=180, key="draft_area")

    escaped = draft.replace("`", "\\`").replace("$", "\\$")
    st.markdown(f"""
<button class="copy-btn" onclick="
  navigator.clipboard.writeText(`{escaped}`)
    .then(() => this.textContent = 'コピーしました')
    .catch(() => this.textContent = 'コピー失敗')
  setTimeout(() => this.textContent = 'コピー', 2000)
">コピー</button>
""", unsafe_allow_html=True)

    char_count = len(draft)
    st.progress(min(char_count / 140, 1.0))
    if char_count > 140:
        st.warning(f"{char_count}字 — 140字を超えています。投稿前に調整してください。")
    else:
        st.caption(f"文字数: {char_count} / 140")

    if e:
        st.markdown(f"""
<div class="score-row">
  <span class="badge">フック {e.hook} / 5</span>
  <span class="badge">具体性 {e.specificity} / 5</span>
  <span class="badge">修正 {revisions} 回</span>
</div>
""", unsafe_allow_html=True)
        st.info(f"改善コメント: {e.comment}")

    if st.session_state.logs:
        with st.expander("生成ログ"):
            for log in st.session_state.logs:
                st.markdown(f'<div class="log-line">{log}</div>', unsafe_allow_html=True)