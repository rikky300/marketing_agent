"""
Streamlit UI。ブラウザからテーマを選んで投稿を生成する。
実行: streamlit run app.py
（事前に python index.py でベクトルDBを作っておくこと）
"""
import streamlit as st
from graph import app as agent, build_app
from nodes import State

import os, subprocess, sys
from pathlib import Path
import config

# chroma_db がなければ index.py を実行してDBを作る（Streamlit Cloud対応）
if not Path(config.CHROMA_DIR).exists():
    subprocess.run([sys.executable, "index.py"], check=True)
# ── ページ設定 ──
st.set_page_config(
    page_title="SNSマーケティングAgent",
    page_icon="✍️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── スマホ対応のカスタムCSS ──
st.markdown("""
<style>
/* スマホ幅でも読みやすいように調整 */
.block-container { padding: 1.5rem 1rem; max-width: 680px; }
.stTextArea textarea { font-size: 1rem; line-height: 1.7; }
.stButton button { width: 100%; font-size: 1rem; padding: 0.6rem; }
/* コピーボタン */
.copy-btn {
    display: inline-block;
    background: #0f62fe;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 0.4rem 1rem;
    font-size: 0.9rem;
    cursor: pointer;
    margin-top: 0.5rem;
}
.copy-btn:hover { background: #0353e9; }
/* スコアバッジ */
.score-row { display: flex; gap: 0.75rem; flex-wrap: wrap; margin: 0.5rem 0; }
.badge {
    background: #f0f4ff;
    border-radius: 20px;
    padding: 0.3rem 0.8rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: #1a3c6e;
}
/* ログ行 */
.log-line { font-family: monospace; font-size: 0.82rem; color: #444; padding: 2px 0; }
/* グラフ図のノード */
.flow-wrap { display:flex; align-items:center; gap:0; flex-wrap:wrap; margin:0.5rem 0; }
.flow-node {
    background:#e8f4ff; border:1.5px solid #4a9eff; border-radius:8px;
    padding:0.35rem 0.75rem; font-size:0.82rem; font-weight:600; color:#1a5fb4;
    white-space:nowrap;
}
.flow-node.active { background:#dff5e3; border-color:#2e7d32; color:#2e7d32; }
.flow-node.cond {
    background:#fff8e1; border:1.5px dashed #f9a825;
    border-radius:20px; color:#7a5700;
}
.flow-arrow { font-size:1.1rem; color:#888; padding:0 2px; }
</style>
""", unsafe_allow_html=True)

PRESET_THEMES = [
    "開発の裏側",
    "このツールで解決したい課題",
    "新しく作っている機能",
    "個人開発でつまずいたこと",
    "どんな人に使ってほしいか",
]

# ── session_state 初期化 ──
for key, default in [("result", None), ("logs", []), ("running", False)]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── ヘッダー ──
st.title("✍️ SNSマーケティングAgent")
st.caption("プロダクト情報をもとに、Xの投稿案を自動生成します")


# ── エージェントの構造タブ ──
tab_gen, tab_flow = st.tabs(["📝 投稿を作る", "🔀 エージェントの構造"])

# ═══════════════════════════════════════════
# TAB 1: 投稿生成
# ═══════════════════════════════════════════
with tab_gen:
    st.subheader("テーマ")

    preset = st.selectbox("プリセットから選ぶ", ["（自由入力）"] + PRESET_THEMES)
    free_input = st.text_input("または自由に入力", placeholder="例: リリースのお知らせ")

    if preset != "（自由入力）":
        theme = preset
    elif free_input.strip():
        theme = free_input.strip()
    else:
        theme = PRESET_THEMES[0]

    # 生成ボタン
    if st.button("🚀 投稿を生成する", type="primary", disabled=st.session_state.running):
        st.session_state.result = None
        st.session_state.logs = []
        st.session_state.running = True

        with st.spinner(f"『{theme}』で投稿を生成中..."):
            # stream でログを拾いながら、最後に invoke で確実に最終状態を取る
            logs = []
            last_revisions = 0
            for step in agent.stream(
                {"theme": theme, "context": "", "draft": "", "evaluation": None, "revisions": 0},
                stream_mode="updates",
            ):
                node_name = list(step.keys())[0]
                update = list(step.values())[0]

                if node_name == "retrieve":
                    logs.append("🔍 [検索] 関連情報を取得")
                elif node_name == "generate":
                    e = update.get("evaluation")
                    s = (e.hook + e.specificity) if e else "?"
                    logs.append(f"✏️ [生成] 3案から最良を選択 → {s}点")
                elif node_name == "revise":
                    n = update.get("revisions", "?")
                    last_revisions = n
                    logs.append(f"🔄 [修正{n}回目] コメントを反映して書き直し")
                elif node_name == "evaluate":
                    e = update.get("evaluation")
                    s = (e.hook + e.specificity) if e else "?"
                    logs.append(f"⭐ [採点] {s}点")

                # 最終状態をキャプチャ（draft が入っているステップを上書きし続ける）
                if update.get("draft"):
                    st.session_state.result = update

            st.session_state.logs = logs
            st.session_state.running = False
        st.rerun()

    # ── 結果表示 ──
    if st.session_state.result:
        result = st.session_state.result
        e = result.get("evaluation")
        draft = result.get("draft", "")
        revisions = result.get("revisions", 0)

        st.divider()
        st.subheader("✅ 完成した投稿")

        # 投稿本文
        st.text_area("Xに貼り付けてください", value=draft, height=180, key="draft_area")

        # コピーボタン（JavaScriptでクリップボードにコピー）
        escaped = draft.replace("`", "\\`").replace("$", "\\$")
        st.markdown(f"""
<button class="copy-btn" onclick="
  navigator.clipboard.writeText(`{escaped}`)
    .then(() => this.textContent = '✅ コピーしました')
    .catch(() => this.textContent = '❌ コピー失敗')
  setTimeout(() => this.textContent = '📋 コピー', 2000)
">📋 コピー</button>
""", unsafe_allow_html=True)

        # 文字数バー
        char_count = len(draft)
        color = "normal" if char_count <= 140 else "inverse"
        st.progress(min(char_count / 140, 1.0))
        if char_count > 140:
            st.warning(f"⚠️ {char_count}字 — 140字を超えています。投稿前に調整してください。")
        else:
            st.caption(f"文字数: {char_count} / 140")

        # スコアバッジ
        if e:
            st.markdown(f"""
<div class="score-row">
  <span class="badge">フック {e.hook} / 5</span>
  <span class="badge">具体性 {e.specificity} / 5</span>
  <span class="badge">修正 {revisions} 回</span>
</div>
""", unsafe_allow_html=True)
            st.info(f"💬 改善コメント: {e.comment}")

        # 生成ログ（折りたたみ）
        if st.session_state.logs:
            with st.expander("生成ログ（どう作られたか）"):
                for log in st.session_state.logs:
                    st.markdown(f'<div class="log-line">{log}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════
# TAB 2: エージェントの構造
# ═══════════════════════════════════════════
with tab_flow:
    st.subheader("このエージェントの処理フロー")
    st.caption("各ノードが何をしているか、どう繋がっているかを示します")

    # フロー図（HTML/CSS）
    st.markdown("""
<div style="background:#fafafa;border-radius:10px;padding:1.2rem;margin-bottom:1rem;">

<b style="font-size:0.8rem;color:#888;letter-spacing:.05em;">起動時 / product.md 更新時（index.py）</b>
<div class="flow-wrap" style="margin-top:0.5rem;">
  <div class="flow-node">📄 product.md 読込</div>
  <div class="flow-arrow">→</div>
  <div class="flow-node">✂️ チャンク分割</div>
  <div class="flow-arrow">→</div>
  <div class="flow-node" style="background:#fef3e2;border-color:#e8a000;color:#7a4800;">
    ☁️ 埋め込みAPI<br><small style="font-weight:400;">Google へ通信</small>
  </div>
  <div class="flow-arrow">→</div>
  <div class="flow-node">💾 chroma_db/ に保存</div>
</div>

</div>

<div style="background:#fafafa;border-radius:10px;padding:1.2rem;">

<b style="font-size:0.8rem;color:#888;letter-spacing:.05em;">実行時（main.py / app.py）</b>
<div class="flow-wrap" style="margin-top:0.5rem;">
  <div class="flow-node active">▶ START</div>
  <div class="flow-arrow">→</div>
  <div class="flow-node">🔍 retrieve<br><small style="font-weight:400">テーマで検索</small></div>
  <div class="flow-arrow">→</div>
  <div class="flow-node" style="background:#fef3e2;border-color:#e8a000;color:#7a4800;">
    ✏️ generate<br><small style="font-weight:400;">3案生成＋採点<br>☁️ Gemini×6回</small>
  </div>
  <div class="flow-arrow">→</div>
  <div class="flow-node cond">判定<br><small>基準超えた?</small></div>
</div>

<div style="display:flex;gap:1.5rem;margin:0.5rem 0 0.5rem 8rem;flex-wrap:wrap;">
  <div style="display:flex;flex-direction:column;align-items:center;gap:4px;">
    <span style="font-size:0.75rem;color:#2e7d32;font-weight:600;">Yes（合格）</span>
    <div class="flow-arrow" style="transform:rotate(90deg)">→</div>
    <div class="flow-node active">⏹ END</div>
  </div>
  <div style="display:flex;flex-direction:column;align-items:center;gap:4px;">
    <span style="font-size:0.75rem;color:#c62828;font-weight:600;">No（改善）</span>
    <div class="flow-arrow" style="transform:rotate(90deg)">→</div>
    <div class="flow-node" style="background:#fef3e2;border-color:#e8a000;color:#7a4800;">
      🔄 revise<br><small style="font-weight:400;">コメント反映<br>☁️ Gemini×1回</small>
    </div>
    <div class="flow-arrow" style="transform:rotate(90deg)">→</div>
    <div class="flow-node" style="background:#fef3e2;border-color:#e8a000;color:#7a4800;">
      ⭐ evaluate<br><small style="font-weight:400;">再採点<br>☁️ Gemini×1回</small>
    </div>
    <div class="flow-arrow" style="transform:rotate(90deg)">→</div>
    <div class="flow-node cond">判定<br><small>基準超えた?<br>上限に達した?</small></div>
  </div>
</div>

</div>
""", unsafe_allow_html=True)

    st.divider()

    # ファイル構成の説明
    st.subheader("ファイル構成")
    st.markdown("""
| ファイル | 役割 |
|---|---|
| `config.py` | モデル名・パス・閾値など全設定を一箇所に |
| `models.py` | AIモデルの窓口・採点スキーマ(`Evaluation`) |
| `index.py` | **ベクトル化専用**。product.md更新時だけ実行 |
| `rag.py` | 保存済みDBを開いて検索・システムメッセージ組立 |
| `nodes.py` | グラフの各ステップ(retrieve/generate/revise/evaluate)と分岐 |
| `graph.py` | ノードとエッジをつないでLangGraphのappを組み立てる |
| `main.py` | CLIから実行するエントリポイント |
| `app.py` | **このファイル**。StreamlitのUIエントリポイント |
""")

    st.divider()

    # APIコストの説明
    st.subheader("☁️ API通信が発生する箇所")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**埋め込みAPI（Google）**
- `index.py` 実行時のみ
- product.md → ベクトル変換
- 起動時・毎回の実行では発生しない
""")
    with col2:
        st.markdown("""
**生成API（Gemini Flash）**
- 投稿1本ごとに最大8回前後
- 3案生成×3回 + 採点×3回
- 修正があれば +1〜2回
- 現在は無料枠内で運用可能
""")