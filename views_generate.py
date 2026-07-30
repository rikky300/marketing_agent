"""生成ページ（デプロイ対象）。テーマを選んで投稿を作り、コピーする。
評価(採点表示・👍/👎・ダッシュボード)は含めない。それは別アプリ eval_app.py。"""
import hashlib
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from graph import app as agent
import posts
import rag
import sources

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


def _get_store(source_text):
    """添付テキストの in-memory ベクトルストアをセッションにキャッシュする（再埋め込みを避ける）。"""
    h = hashlib.sha1(source_text.encode("utf-8")).hexdigest()
    if st.session_state.get("_src_hash") != h:
        st.session_state["_src_hash"] = h
        st.session_state["_src_store"] = rag.build_store(source_text)
    return st.session_state["_src_store"]


def _context_for(source_text, theme):
    """添付テキストから context を作る。添付が無ければ空文字（＝既定のproduct.mdを使う）。"""
    if not source_text:
        return ""
    if rag.is_short(source_text):
        return source_text                      # 短ければ全文をそのまま
    return rag.search_store(_get_store(source_text), theme)  # 長ければ検索


def _run_agent(theme, context):
    """エージェントを回して final_state とログを返す。context があれば添付ドキュメントを使う。"""
    logs = []
    final_state = {}
    for step in agent.stream(
        {"theme": theme, "context": context, "draft": "", "evaluation": None,
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


def _save_generated(run_id, theme, fs):
    """生成結果を投稿物DBに1行追加。initial_score / final_from も記録する。
    theme は明示的に渡す（stream_mode='updates' では final_state に theme が入らないため）。"""
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
        "theme": theme,
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

    st.subheader("製品情報（任意）")
    up = st.file_uploader("PDF / テキスト(.txt/.md) をアップロード", type=["pdf", "txt", "md"])
    src_url = st.text_input("またはURL", placeholder="https://...")
    pasted = st.text_area("または製品情報を直接入力",
                          placeholder="製品の説明・特徴・誰向けか などを貼り付け", height=120)
    st.caption("ファイル / URL / 直接入力 のどれかで指定できます（優先順: ファイル → URL → 手入力）。"
               "指定すると、その製品情報『だけ』を使って生成。未指定ならサンプル(既定のproduct.md)で生成。"
               "入力内容のベクトルは保存しません。")

    st.subheader("テーマ")
    preset = st.selectbox("プリセットから選ぶ", ["（自由入力）"] + PRESET_THEMES)
    free_input = st.text_input("または自由に入力", placeholder="例: リリースのお知らせ")
    theme = _pick_theme(preset, free_input)

    if st.button("投稿を生成する", type="primary", disabled=st.session_state.running):
        # 添付ソースを読み取る（失敗したら生成しない）
        try:
            source_text, source_label = sources.extract_source(up, src_url, pasted)
        except Exception as ex:
            st.error(f"製品情報の読み取りに失敗しました: {ex}")
            st.stop()
        if source_text is not None and not source_text.strip():
            st.error("テキストを抽出できませんでした（スキャンPDF等の可能性）。別のファイル/URLを試してください。")
            st.stop()

        st.session_state.result = None
        st.session_state.logs = []
        st.session_state.running = True
        with st.spinner(f"『{theme}』で投稿を生成中..."):
            context = _context_for(source_text, theme)
            final_state, logs = _run_agent(theme, context)
            st.session_state.result = final_state if final_state.get("draft") else None
            st.session_state.logs = logs
            st.session_state.source_label = source_label
            st.session_state.running = False
            # この生成を一意に識別（投稿物DBの行id）。評価は eval_app.py で後から行う。
            st.session_state.run_id = datetime.now().isoformat(timespec="seconds")
            if st.session_state.result:
                _save_generated(st.session_state.run_id, theme, st.session_state.result)
        st.rerun()

    if not st.session_state.result:
        return

    draft = st.session_state.result.get("draft", "")

    st.divider()
    st.subheader("完成した投稿")
    src_label = st.session_state.get("source_label")
    st.caption(f"参照した製品情報: {src_label}" if src_label else "参照した製品情報: サンプル（既定のproduct.md）")
    st.text_area("Xに貼り付けてください", value=draft, height=180, key="draft_area")
    _copy_button(draft)

    char_count = len(draft)
    st.progress(min(char_count / 140, 1.0))
    if char_count > 140:
        st.warning(f"{char_count}字 — 140字を超えています。投稿前に調整してください。")
    else:
        st.caption(f"文字数: {char_count} / 140")
