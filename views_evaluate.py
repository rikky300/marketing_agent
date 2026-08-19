"""評価ページ。溜まった投稿を人間が評価し、ワークフローのどこに改善余地があるかを見る。

ここでの評価はループには組み込まない（自動では使わない）。
次の改善（rubric・軸追加・THRESHOLD・reviseループ等）を判断するための可視化。
"""
import pandas as pd
import streamlit as st

import config
import posts
from agent_diagram import DIAGRAM_PNG

# 生成時に自動で埋まる列（表では編集不可にする）
_LOCKED = ["id", "created_at", "theme", "draft",
           "hook", "specificity", "clarity", "relatability", "binary",
           "length_ok", "auto_score", "revisions", "char_count", "initial_score", "final_from", "rated_at"]
# 表で見せる列の順番（人間が編集する列を前に寄せる）
_ORDER = ["theme", "draft", "auto_score",
          "hook", "specificity", "clarity", "relatability", "binary",
          "label", "human_hook", "human_specificity", "human_clarity", "human_relatability", "human_grounded",
          "impressions", "likes", "reposts", "replies", "bookmarks",
          "posted", "url", "notes", "revisions", "final_from"]
# 保存時に "" を null に戻す文字列列
_STR_EDIT = ["label", "human_grounded", "url", "notes", "posted"]


def _no_data(msg="まだデータがありません"):
    st.caption(msg)


def _dashboard(df):
    st.subheader("ダッシュボード")

    # ① 採点精度
    s = posts.agreement_summary(df)
    st.markdown("**① 採点精度**")
    if s["n"] == 0:
        _no_data("👍/👎 の評価がまだありません")
    else:
        c = st.columns(4)
        c[0].metric("一致率", s["agreement_rate"])
        c[1].metric("適合率", s["judge_precision"] or "—")
        c[2].metric("👍 平均", s["mean_score_up"] or "—")
        c[3].metric("👎 平均", s["mean_score_down"] or "—")
        st.caption(f"n={s['n']}（👍{s['up']} / 👎{s['down']}）　👎平均 > 👍平均 なら採点モデルを見直す")

    st.divider()

    # ② 軸ズレ
    ab = posts.axis_bias(df)
    st.markdown("**② 軸ズレ（モデル − 人間）**")
    pairs = [("フック", "hook"), ("具体性", "specificity"), ("明確さ", "clarity"), ("共感", "relatability")]
    if all(ab[key]["n"] == 0 for _, key in pairs):
        _no_data("一覧で「人:hook〜人:共感」を入力してください")
    else:
        c = st.columns(4)
        for i, (name, key) in enumerate(pairs):
            a = ab[key]
            if a["n"]:
                c[i].metric(name, a["mean_diff"], help="＋=モデルが甘め　−=モデルが辛め")
                c[i].caption(f"±{a['mean_abs']}　n={a['n']}")
            else:
                c[i].caption(f"{name}　未入力")

    st.divider()

    # ③ 事実性
    g = posts.grounded_summary(df)
    st.markdown("**③ 事実性**")
    if g["n"] == 0:
        _no_data("一覧で「事実」列を ok/ng で入力してください")
    else:
        c = st.columns(3)
        c[0].metric("NG率", g["ng_rate"])
        c[1].metric("NG件数", g["ng"])
        c[2].metric("高得点+NG", g["ng_but_pass"], help="採点が合格なのに事実NGは盲点")
        if g["ng_but_pass"]:
            st.caption("高得点+NG が出ている → 事実性を採点軸に追加する価値あり")

    st.divider()

    # ④ reviseループ
    rv = posts.revise_value(df)
    st.markdown("**④ reviseループ**")
    if rv["n"] == 0:
        _no_data()
    else:
        c = st.columns(4)
        c[0].metric("改善率", rv["improved_rate"])
        c[1].metric("平均Δ", rv["mean_delta"])
        c[2].metric("初稿採用 / 修正採用", f"{rv['final_initial']} / {rv['final_revised']}")
        c[3].metric("平均修正回数", rv["mean_revisions"])
        if rv["final_initial"] > rv["final_revised"]:
            st.caption("初稿採用が多い → reviseループのコスト対効果を確認")

    st.divider()

    # ⑤ 合格ライン
    ts = posts.threshold_summary(df)
    st.markdown(f"**⑤ 合格ライン（{config.PASS_TOTAL}点）**")
    if ts["n"] == 0:
        _no_data()
    else:
        c = st.columns(2)
        c[0].metric("pass率", ts["pass_rate"])
        c[1].metric("pass中のgood率", ts["passed_good_rate"] or "—")
        if ts["passed_good_rate"] is not None and ts["passed_good_rate"] < 0.6:
            st.caption("pass中のgood率が低い → PASS_TOTAL を上げるかモデルを再学習")

    st.divider()

    # ⑥ エンゲージメント
    has_eng = int(df["impressions"].notna().sum())
    st.markdown("**⑥ エンゲージメント**")
    st.caption(f"記入済み {has_eng} / {len(df)} 件　投稿後に一覧から手入力")


def _editor(df_full):
    st.subheader("投稿一覧（その場で評価・エンゲージメントを記入）")

    colf1, colf2 = st.columns(2)
    only_unrated = colf1.toggle("未評価のみ表示", value=False)
    themes = ["（すべて）"] + sorted(t for t in df_full["theme"].dropna().unique())
    theme_sel = colf2.selectbox("テーマで絞る", themes)

    view = df_full
    if only_unrated:
        view = view[~view["label"].isin(["good", "bad"])]
    if theme_sel != "（すべて）":
        view = view[view["theme"] == theme_sel]

    if len(view) == 0:
        st.caption("該当する投稿がありません。")
        return

    # 表示用に文字列列の NaN を "" にする（セレクトボックスが空を扱えるように）
    disp = view.copy()
    for c in _STR_EDIT + ["posted_at", "final_from"]:
        disp[c] = disp[c].fillna("")

    edited = st.data_editor(
        disp,
        key="posts_editor",
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_order=_ORDER,
        column_config={
            **{c: st.column_config.Column(disabled=True) for c in _LOCKED},
            "draft": st.column_config.TextColumn("投稿", width="large", disabled=True),
            "theme": st.column_config.TextColumn("テーマ", disabled=True),
            "auto_score": st.column_config.NumberColumn("score", disabled=True),
            "hook": st.column_config.NumberColumn("B:hook", disabled=True),
            "specificity": st.column_config.NumberColumn("B:具体", disabled=True),
            "clarity": st.column_config.NumberColumn("B:明確", disabled=True),
            "relatability": st.column_config.NumberColumn("B:共感", disabled=True),
            "binary": st.column_config.NumberColumn("B:good?", disabled=True),
            "label": st.column_config.SelectboxColumn("評価", options=["", "good", "bad"]),
            "human_hook": st.column_config.NumberColumn("人:hook", min_value=1, max_value=5, step=1),
            "human_specificity": st.column_config.NumberColumn("人:具体", min_value=1, max_value=5, step=1),
            "human_clarity": st.column_config.NumberColumn("人:明確", min_value=1, max_value=5, step=1),
            "human_relatability": st.column_config.NumberColumn("人:共感", min_value=1, max_value=5, step=1),
            "human_grounded": st.column_config.SelectboxColumn("事実", options=["", "ok", "ng"]),
            "impressions": st.column_config.NumberColumn("imp", min_value=0),
            "likes": st.column_config.NumberColumn("いいね", min_value=0),
            "reposts": st.column_config.NumberColumn("RP", min_value=0),
            "replies": st.column_config.NumberColumn("返信", min_value=0),
            "bookmarks": st.column_config.NumberColumn("BM", min_value=0),
            "posted": st.column_config.SelectboxColumn("投稿済", options=["", "yes", "no"]),
            "url": st.column_config.TextColumn("URL"),
            "notes": st.column_config.TextColumn("メモ", width="medium"),
            "final_from": st.column_config.TextColumn("最終", disabled=True),
        },
    )

    if st.button("保存する", type="primary"):
        for c in _STR_EDIT:
            edited[c] = edited[c].replace("", pd.NA)
        df_full.loc[edited.index, edited.columns] = edited
        posts.save_df(df_full)
        st.success(f"{len(edited)} 件を保存しました。")


def render():
    st.title("評価")
    st.caption("溜まった投稿を評価し、ワークフローのどこを直すか判断するためのページ")
    st.divider()

    # 「何を評価しているか」の参照として、ワークフロー設計をここに置く
    with st.expander("AIエージェント部署の設計（何を評価しているか）"):
        st.image(DIAGRAM_PNG, use_container_width=True)
        st.caption("紫 = AIが処理（草案ライター=Gemini / 採点担当=自前BERT4軸） / グレー = 人間・検索・決定。"
                   "採点の妥当性・reviseループの効き・しきい値を、このページで評価する。")

    df = posts.load_df()
    if len(df) == 0:
        st.info("まだ投稿がありません。『生成』ページで投稿を作ってください。")
        return

    _dashboard(df)
    st.divider()
    _editor(df)
