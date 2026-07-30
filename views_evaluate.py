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
_LOCKED = ["id", "created_at", "theme", "draft", "hook", "specificity", "length_ok",
           "auto_score", "revisions", "char_count", "initial_score", "final_from", "rated_at"]
# 表で見せる列の順番（人間が編集する列を前に寄せる）
_ORDER = ["theme", "draft", "auto_score", "hook", "specificity",
          "label", "human_hook", "human_specificity", "human_grounded",
          "impressions", "likes", "reposts", "replies", "bookmarks",
          "posted", "url", "notes", "revisions", "final_from"]
# 保存時に "" を null に戻す文字列列
_STR_EDIT = ["label", "human_grounded", "url", "notes", "posted"]


def _dashboard(df):
    st.subheader("ダッシュボード（改善余地を見る）")

    # 1) judge vs 人間(good/bad)
    s = posts.agreement_summary(df)
    st.markdown("**① judge は人間と合っているか（good/bad）**")
    if s["n"] == 0:
        st.caption("まだ good/bad 評価がありません。")
    else:
        c = st.columns(4)
        c[0].metric("一致率", s["agreement_rate"])
        c[1].metric("judge適合率", s["judge_precision"] if s["judge_precision"] is not None else "—")
        c[2].metric("👍平均score", s["mean_score_up"] if s["mean_score_up"] is not None else "—")
        c[3].metric("👎平均score", s["mean_score_down"] if s["mean_score_down"] is not None else "—")
        st.caption(f"n={s['n']}（👍{s['up']}/👎{s['down']}）｜👎平均が👍平均を上回ったら judge は当てにならない赤信号")

    # 2) 軸別のズレ（judge の rubric をどの軸で直すか）
    ab = posts.axis_bias(df)
    st.markdown("**② どの軸がズレているか（人間版スコアとの差）**")
    if ab["hook"]["n"] == 0 and ab["specificity"]["n"] == 0:
        st.caption("人間版 hook/具体性 の入力がまだありません。")
    else:
        c = st.columns(2)
        for i, (name, key) in enumerate([("フック", "hook"), ("具体性", "specificity")]):
            a = ab[key]
            if a["n"]:
                c[i].metric(f"{name} judge−人間", a["mean_diff"], help="＋=judgeが甘い / −=judgeが辛い")
                c[i].caption(f"平均ズレ幅 {a['mean_abs']}（n={a['n']}）")
            else:
                c[i].caption(f"{name}: 入力なし")

    # 3) 事実性（judge が見ていない軸）
    g = posts.grounded_summary(df)
    st.markdown("**③ 事実に忠実か（judge が採点していない盲点）**")
    if g["n"] == 0:
        st.caption("事実性(ok/ng)の入力がまだありません。")
    else:
        c = st.columns(3)
        c[0].metric("事実NG率", g["ng_rate"])
        c[1].metric("NG件数", g["ng"])
        c[2].metric("高得点なのにNG", g["ng_but_pass"], help="judge合格なのに事実NG＝一番危険")
        st.caption(f"n={g['n']}｜『高得点なのにNG』が出るなら、採点軸に事実性を足す価値がある")

    # 4) revise ループの価値
    rv = posts.revise_value(df)
    st.markdown("**④ reviseループは効いているか**")
    if rv["n"] == 0:
        st.caption("データがありません。")
    else:
        c = st.columns(4)
        c[0].metric("改善した割合", rv["improved_rate"])
        c[1].metric("平均スコア改善", rv["mean_delta"])
        c[2].metric("最終=初稿 / 修正", f"{rv['final_initial']} / {rv['final_revised']}")
        c[3].metric("平均修正回数", rv["mean_revisions"])
        st.caption(f"n={rv['n']}｜最終がほぼ『初稿』なら、reviseループはコストに見合っていない")

    # 5) THRESHOLD の妥当性
    ts = posts.threshold_summary(df)
    st.markdown("**⑤ 合格しきい値は妥当か**")
    if ts["n"] == 0:
        st.caption("データがありません。")
    else:
        c = st.columns(2)
        c[0].metric(f"pass率（≥{config.THRESHOLD}）", ts["pass_rate"])
        c[1].metric("pass中の人間good率", ts["passed_good_rate"] if ts["passed_good_rate"] is not None else "—")
        st.caption("pass率が高いのに人間good率が低いなら、THRESHOLDを上げるか judge を厳しくする")

    # 6) エンゲージメント（後で埋める）
    has_eng = int(df["impressions"].notna().sum())
    st.markdown("**⑥ 実エンゲージメント（投稿後に記入）**")
    st.caption(f"記入済み {has_eng}/{len(df)} 件。溜まったら『auto_score は実際の伸びを予測できるか』を検証する。")


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
            "auto_score": st.column_config.NumberColumn("auto", disabled=True),
            "hook": st.column_config.NumberColumn("J:hook", disabled=True),
            "specificity": st.column_config.NumberColumn("J:具体", disabled=True),
            "label": st.column_config.SelectboxColumn("評価", options=["", "good", "bad"]),
            "human_hook": st.column_config.NumberColumn("人:hook", min_value=1, max_value=5, step=1),
            "human_specificity": st.column_config.NumberColumn("人:具体", min_value=1, max_value=5, step=1),
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

    df = posts.load_df()
    if len(df) == 0:
        st.info("まだ投稿がありません。『生成』ページで投稿を作ってください。")
        return

    _dashboard(df)
    st.divider()
    _editor(df)
