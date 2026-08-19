"""生成アプリ（デプロイ対象）。1画面1意思決定のウィザード。
  ① 製品情報 → ② テーマ → ③ 生成 → ④ 結果(コピー＋👍/👎)
評価ダッシュボード・内部採点は出さない（それはローカル eval_app.py）。"""
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

_STEPS = ["product", "theme", "generate", "result"]
_STEP_LABELS = {"product": "製品情報", "theme": "テーマ", "generate": "生成", "result": "完成"}


# ── 小さな道具 ──
def _goto(step):
    st.session_state.wiz_step = step
    st.rerun()


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
        return source_text
    return rag.search_store(_get_store(source_text), theme)


def _run_agent(theme, context):
    """エージェントを回して final_state を返す。context があれば添付ドキュメントを使う。"""
    final_state = {}
    for step in agent.stream(
        {"theme": theme, "context": context, "draft": "", "evaluation": None,
         "revisions": 0, "candidates": []},
        stream_mode="updates",
    ):
        # ノードが {} を返す（retrieve_node のスキップ等）と updates ストリームは None を流すので弾く
        for upd in step.values():
            if upd:
                final_state.update(upd)
    return final_state


def _save_generated(run_id, theme, fs):
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
        "id": run_id, "theme": theme, "draft": d,
        "hook": ev.hook if ev else None,
        "specificity": ev.specificity if ev else None,
        "clarity": getattr(ev, "clarity", None) if ev else None,
        "relatability": getattr(ev, "relatability", None) if ev else None,
        "binary": getattr(ev, "binary", None) if ev else None,
        "length_ok": ev.length_ok if ev else None,
        "auto_score": (posts.compute_auto_score(
            ev.hook, ev.specificity,
            getattr(ev, "clarity", 3), getattr(ev, "relatability", 3))
                       if ev else None),
        "revisions": fs.get("revisions", 0),
        "char_count": len(d),
        "initial_score": initial_score, "final_from": final_from,
    })


def _copy_button(draft):
    # st.markdown 内の onclick は除去されるため components.html(iframe)で。clipboard不可環境向けに execCommand も。
    components.html(f"""
    <button id="copyBtn" style="
    width:100%; background:#1a1a1a; color:white; border:none; border-radius:6px;
    padding:0.6rem; font-size:1rem; cursor:pointer;">コピー</button>
    <script>
    const text = {json.dumps(draft)};
    const btn = document.getElementById('copyBtn');
    btn.addEventListener('click', async () => {{
        let ok = false;
        try {{ await navigator.clipboard.writeText(text); ok = true; }}
        catch (e) {{
        const ta = document.createElement('textarea');
        ta.value = text; ta.style.position='fixed'; ta.style.opacity='0';
        document.body.appendChild(ta); ta.focus(); ta.select();
        try {{ ok = document.execCommand('copy'); }} catch (e2) {{ ok = false; }}
        document.body.removeChild(ta);
        }}
        btn.textContent = ok ? 'コピーしました' : 'コピー失敗';
        setTimeout(() => {{ btn.textContent = 'コピー'; }}, 2000);
    }});
    </script>
    """, height=52)


def _source_label():
    return st.session_state.get("src_label") or "サンプル（既定のproduct.md）"


# ── 各ステップ ──
def _step_product():
    st.header("① 製品情報を入れる")
    st.write("あなたの製品情報をもとに投稿を作ります。ファイル・URL・直接入力のどれかでどうぞ。")
    up = st.file_uploader("PDF / テキスト(.txt/.md) をアップロード", type=["pdf", "txt", "md"], key="wiz_up")
    url = st.text_input("またはURL", placeholder="https://...", key="wiz_url")
    pasted = st.text_area("または製品情報を直接入力",
                          placeholder="製品の説明・特徴・誰向けか などを貼り付け", height=160, key="wiz_pasted")
    st.caption("優先順: ファイル → URL → 手入力。何も入れなければサンプルで試せます。"
               "入力内容のベクトルは保存しません。")

    if st.button("次へ →", type="primary"):
        try:
            src_text, src_label = sources.extract_source(up, url, pasted)
        except Exception as ex:
            st.error(f"読み取りに失敗しました: {ex}")
            return
        if src_text is not None and not src_text.strip():
            st.error("テキストを抽出できませんでした（スキャンPDF等の可能性）。別のファイル/URLを試してください。")
            return
        st.session_state.src_text = src_text
        st.session_state.src_label = src_label
        _goto("theme")


def _step_theme():
    st.header("② テーマを選ぶ")
    st.caption(f"製品情報: {_source_label()}")
    preset = st.selectbox("プリセットから選ぶ", ["（自由入力）"] + PRESET_THEMES, key="wiz_preset")
    free_input = st.text_input("または自由に入力", placeholder="例: リリースのお知らせ", key="wiz_free")

    c1, c2 = st.columns([1, 2])
    if c1.button("← 戻る"):
        _goto("product")
    if c2.button("次へ →", type="primary"):
        st.session_state.theme = _pick_theme(preset, free_input)
        _goto("generate")


def _step_generate():
    st.header("③ 生成する")
    st.write(f"**製品情報**: {_source_label()}")
    st.write(f"**テーマ**: {st.session_state.get('theme', '')}")

    c1, c2 = st.columns([1, 2])
    if c1.button("← 戻る"):
        _goto("theme")
    if c2.button("投稿を生成する", type="primary"):
        with st.spinner(f"『{st.session_state.theme}』で投稿を生成中..."):
            context = _context_for(st.session_state.get("src_text"), st.session_state.theme)
            fs = _run_agent(st.session_state.theme, context)
            st.session_state.result = fs if fs.get("draft") else None
            st.session_state.run_id = datetime.now().isoformat(timespec="seconds")
            st.session_state.rated_run = None
            if st.session_state.result:
                _save_generated(st.session_state.run_id, st.session_state.theme, st.session_state.result)
        if st.session_state.result:
            _goto("result")
        else:
            st.error("生成に失敗しました。もう一度お試しください。")


def _step_result():
    if not st.session_state.get("result"):
        _goto("generate")
        return

    st.header("④ 完成")
    draft = st.session_state.result.get("draft", "")
    st.caption(f"参照: {_source_label()} ・ テーマ: {st.session_state.get('theme', '')}")
    st.text_area("Xに貼り付けてください", value=draft, height=180, key="draft_area")
    _copy_button(draft)

    char_count = len(draft)
    st.progress(min(char_count / 140, 1.0))
    if char_count > 140:
        st.warning(f"{char_count}字 — 140字を超えています。投稿前に調整してください。")
    else:
        st.caption(f"文字数: {char_count} / 140")

    # 評価は👍/👎だけ（内部スコアは出さない）。posts.csv に保存。
    run_id = st.session_state.get("run_id", "")
    rated = run_id != "" and st.session_state.get("rated_run") == run_id
    st.markdown("**この投稿どうでした?**")
    c1, c2 = st.columns(2)
    if c1.button("👍 良い", disabled=rated, use_container_width=True):
        posts.set_label(run_id, "good")
        st.session_state.rated_run = run_id
        st.rerun()
    if c2.button("👎 いまいち", disabled=rated, use_container_width=True):
        posts.set_label(run_id, "bad")
        st.session_state.rated_run = run_id
        st.rerun()
    if rated:
        st.caption("ありがとうございます ✓")

    st.divider()
    b1, b2, b3 = st.columns(3)
    if b1.button("もう一度生成"):
        _goto("generate")
    if b2.button("テーマを変える"):
        _goto("theme")
    if b3.button("最初から"):
        for k in ("src_text", "src_label", "theme", "result"):
            st.session_state[k] = None
        _goto("product")


def render():
    if "wiz_step" not in st.session_state:
        st.session_state.wiz_step = "product"

    st.title("マーケティング Agent")
    step = st.session_state.wiz_step
    i = _STEPS.index(step)
    st.progress((i + 1) / len(_STEPS))
    st.caption(f"ステップ {i + 1} / {len(_STEPS)}：{_STEP_LABELS[step]}")
    st.divider()

    {"product": _step_product, "theme": _step_theme,
     "generate": _step_generate, "result": _step_result}[step]()
