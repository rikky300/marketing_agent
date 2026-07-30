"""生成ページ。テーマを選んで投稿を作り、その場で👍/👎まで付けられる。"""
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import config
from graph import app as agent
import posts

PRESET_THEMES = [
    "開発の裏側",
    "このツールで解決したい課題",
    "新しく作っている機能",
    "個人開発でつまずいたこと",
    "どんな人に使ってほしいか",
]


def _pick_theme(preset, free_input):
    if preset != "（自由入力）":
        return preset
    if free_input.strip():
        return free_input.strip()
    return PRESET_THEMES[0]


def _run_agent(theme):
    """エージェントを回して final_state とログを返す。"""
    logs = []
    final_state = {}
    for step in agent.stream(
        {"theme": theme, "context": "", "draft": "", "evaluation": None,
         "revisions": 0, "candidates": []},
        stream_mode="updates",
    ):
        node_name = list(step.keys())[0]
        update = list(step.values())[0]
        # 各ノードの出力を上書きではなく累積マージする（evaluate は evaluation だけ、
        # revise は draft だけを返すため、上書きだと draft と evaluation が食い違う）。
        final_state.update(update)

        if node_name == "retrieve":
            logs.append("[検索] 関連情報を取得")
        elif node_name == "generate":
            logs.append("[生成] 初稿を作成")
        elif node_name == "revise":
            n = update.get("revisions", "?")
            logs.append(f"[修正{n}回目] コメントを反映して書き直し")
        elif node_name == "evaluate":
            e = update.get("evaluation")
            s = (e.hook + e.specificity) if e else "?"
            logs.append(f"[採点] {s}点")
        elif node_name == "finalize":
            n = len(final_state.get("candidates", []))
            logs.append(f"[確定] 全{n}案から最良を採用")
    return final_state, logs


def _save_generated(run_id, fs):
    """生成結果を投稿物DBに1行追加。initial_score / final_from も記録する。"""
    ev = fs.get("evaluation")
    d = fs.get("draft", "")
    cands = fs.get("candidates") or []
    initial_score = cands[0]["score"] if cands else None
    final_from = None
    if cands:
        best_idx = max(range(len(cands)), key=lambda i: cands[i]["score"])
        final_from = "initial" if best_idx == 0 else "revised"
    posts.add_post({
        "id": run_id,
        "theme": fs.get("theme", ""),
        "draft": d,
        "hook": ev.hook if ev else None,
        "specificity": ev.specificity if ev else None,
        "length_ok": ev.length_ok if ev else None,
        "auto_score": (posts.compute_auto_score(ev.hook, ev.specificity, ev.length_ok)
                       if ev else None),
        "revisions": fs.get("revisions", 0),
        "char_count": len(d),
        "initial_score": initial_score,
        "final_from": final_from,
    })


def _copy_button(draft):
    # Streamlit は st.markdown 内の onclick を除去するため JS が実行されない。
    # components.html は iframe 内で JS が動くのでこちらを使う。
    # clipboard API が権限で弾かれる環境向けに execCommand フォールバックも用意。
    components.html(f"""
    <button id="copyBtn" style="
    width:100%; background:#1a1a1a; color:white; border:none; border-radius:6px;
    padding:0.6rem; font-size:1rem; cursor:pointer;
    ">コピー</button>
    <script>
    const text = {json.dumps(draft)};
    const btn = document.getElementById('copyBtn');
    btn.addEventListener('click', async () => {{
        let ok = false;
        try {{
        await navigator.clipboard.writeText(text);
        ok = true;
        }} catch (e) {{
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.focus(); ta.select();
        try {{ ok = document.execCommand('copy'); }} catch (e2) {{ ok = false; }}
        document.body.removeChild(ta);
        }}
        btn.textContent = ok ? 'コピーしました' : 'コピー失敗';
        setTimeout(() => {{ btn.textContent = 'コピー'; }}, 2000);
    }});
    </script>
    """, height=52)


def render():
    for key, default in [("result", None), ("logs", []), ("running", False)]:
        if key not in st.session_state:
            st.session_state[key] = default

    st.title("マーケティング Agent")
    st.caption("プロダクト情報をもとに、Xの投稿案を自動生成します")
    st.divider()

    st.subheader("テーマ")
    preset = st.selectbox("プリセットから選ぶ", ["（自由入力）"] + PRESET_THEMES)
    free_input = st.text_input("または自由に入力", placeholder="例: リリースのお知らせ")
    theme = _pick_theme(preset, free_input)

    if st.button("投稿を生成する", type="primary", disabled=st.session_state.running):
        st.session_state.result = None
        st.session_state.logs = []
        st.session_state.running = True
        with st.spinner(f"『{theme}』で投稿を生成中..."):
            final_state, logs = _run_agent(theme)
            st.session_state.result = final_state if final_state.get("draft") else None
            st.session_state.logs = logs
            st.session_state.running = False
            # この生成を一意に識別し、評価の二重記録を防ぐ
            st.session_state.run_id = datetime.now().isoformat(timespec="seconds")
            st.session_state.rated_run = None
            if st.session_state.result:
                _save_generated(st.session_state.run_id, st.session_state.result)
        st.rerun()

    if not st.session_state.result:
        return

    result = st.session_state.result
    e = result.get("evaluation")
    draft = result.get("draft", "")
    revisions = result.get("revisions", 0)

    st.divider()
    st.subheader("完成した投稿")
    st.text_area("Xに貼り付けてください", value=draft, height=180, key="draft_area")
    _copy_button(draft)

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

    # 「自分なら投稿する?」をその場で記録（詳しい評価は評価ページで）
    if e:
        run_id = st.session_state.get("run_id", "")
        rated = run_id != "" and st.session_state.get("rated_run") == run_id
        st.markdown("**自分ならこれ投稿する?**")
        c1, c2 = st.columns(2)
        if c1.button("👍 投稿する", disabled=rated, use_container_width=True):
            posts.set_label(run_id, "good")
            st.session_state.rated_run = run_id
            st.rerun()
        if c2.button("👎 投稿しない", disabled=rated, use_container_width=True):
            posts.set_label(run_id, "bad")
            st.session_state.rated_run = run_id
            st.rerun()
        if rated:
            st.caption("評価を記録しました ✓　詳しい評価は「評価」ページで")

    if st.session_state.logs:
        with st.expander("生成ログ"):
            for log in st.session_state.logs:
                st.markdown(f'<div class="log-line">{log}</div>', unsafe_allow_html=True)
