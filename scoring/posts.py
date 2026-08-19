"""投稿物DB（CSV）。生成された投稿を1行=1投稿で貯めていく。

列は「生成時の情報 → 人間の good/bad → 投稿情報 → 実エンゲージメント」の順。
生成時に行を作り(add_post)、👍/👎は後から同じ行に upsert(set_label)、
エンゲージメントは投稿後にしか分からないので列だけ用意して空(null)のまま置く。

保存先: data/posts.csv。ローカルで使い続けるほどこのファイルにデータが貯まり、
それが採点モデル(BERT)の再学習データになって、使うほど自分専用に育っていく。
"""
import os
from datetime import datetime

import pandas as pd

import config

POSTS_FILE = "data/posts.csv"

# 生成時に埋まる列 / 人間評価の列 / 投稿・エンゲージメントの列（後入力・初期はnull）
COLUMNS = [
    # 生成時に自動で埋まる
    "id", "created_at", "theme", "draft",
    "hook", "specificity", "clarity", "relatability", "binary",
    "length_ok", "auto_score", "revisions", "char_count",
    "initial_score", "final_from",
    # 人間評価（評価ページで後から入力）
    "label", "rated_at",
    "human_hook", "human_specificity", "human_clarity", "human_relatability", "human_grounded",
    # 投稿・実エンゲージメント（投稿後に手入力。初期は空=null）
    "posted", "posted_at", "url",
    "impressions", "likes", "reposts", "replies", "bookmarks", "notes",
]
ENGAGEMENT_COLS = ["impressions", "likes", "reposts", "replies", "bookmarks"]
# 評価ページで人間が編集する列
HUMAN_COLS = ["label", "human_hook", "human_specificity", "human_clarity", "human_relatability", "human_grounded"]

# 空のCSV列を pandas が float 扱いして文字列代入で落ちるのを防ぐため、型を明示する
_STR_COLS = ["id", "created_at", "theme", "draft", "length_ok", "final_from",
             "label", "rated_at", "human_grounded", "posted", "posted_at", "url", "notes"]
_NUM_COLS = ["hook", "specificity", "clarity", "relatability", "binary",
             "auto_score", "revisions", "char_count", "initial_score",
             "human_hook", "human_specificity", "human_clarity", "human_relatability",
             "impressions", "likes", "reposts", "replies", "bookmarks"]


def _ensure():
    os.makedirs(os.path.dirname(POSTS_FILE), exist_ok=True)
    if not os.path.exists(POSTS_FILE):
        pd.DataFrame(columns=COLUMNS).to_csv(POSTS_FILE, index=False)


def load_df() -> pd.DataFrame:
    _ensure()
    df = pd.read_csv(POSTS_FILE, dtype={"id": str})
    for c in COLUMNS:            # 列が欠けていても落ちないよう補完（スキーマ進化に耐える）
        if c not in df.columns:
            df[c] = pd.NA
    for c in _STR_COLS:         # 空列でも文字列を入れられるよう object 型にそろえる
        df[c] = df[c].astype("object")
    for c in _NUM_COLS:         # 数値列は数値に（空は NaN）
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[COLUMNS]


def save_df(df: pd.DataFrame):
    _ensure()
    df[COLUMNS].to_csv(POSTS_FILE, index=False)


def compute_auto_score(hook, specificity, clarity, relatability):
    """nodes._score と同じ定義。2*hook + specificity + clarity + relatability（最大25点）。
    length_ok はハード条件なのでスコアには含めない（should_continue で別途判定）。"""
    return 2 * hook + specificity + clarity + relatability


def add_post(rec: dict):
    """生成直後に1行作る。judge項目は埋め、label/engagement は空(null)のまま。"""
    df = load_df()
    if (df["id"] == str(rec["id"])).any():
        return  # 同じ生成を二重に記録しない
    row = {c: rec.get(c, pd.NA) for c in COLUMNS}
    row["id"] = str(rec["id"])
    row["created_at"] = datetime.now().isoformat(timespec="seconds")
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_df(df)


def set_label(post_id: str, label: str):
    """👍=good / 👎=bad をその投稿行に upsert する。"""
    df = load_df()
    m = df["id"] == str(post_id)
    if not m.any():
        return
    df.loc[m, "label"] = label
    df.loc[m, "rated_at"] = datetime.now().isoformat(timespec="seconds")
    save_df(df)


def agreement_summary(df=None) -> dict:
    """judge(auto_score) と 人間評価(good/bad) の一致度をまとめる。

    - judge の合否 = auto_score >= THRESHOLD
    - agreement_rate = (judge合格 かつ good) または (judge不合格 かつ bad) の割合
    - judge_precision = judge が合格にした中で、人間も good だった割合
    """
    df = load_df() if df is None else df
    rated = df[df["label"].isin(["good", "bad"])]
    n = len(rated)
    if n == 0:
        return {"n": 0}

    is_good = rated["label"] == "good"
    is_pass = rated["auto_score"] >= config.PASS_TOTAL
    passed = rated[is_pass]

    def mean(s):
        return round(float(s.mean()), 2) if len(s) else None

    return {
        "n": int(n),
        "up": int(is_good.sum()),
        "down": int((~is_good).sum()),
        "mean_score_up": mean(rated.loc[is_good, "auto_score"]),
        "mean_score_down": mean(rated.loc[~is_good, "auto_score"]),
        "agreement_rate": round(float((is_pass == is_good).mean()), 2),
        "judge_precision": (round(float((passed["label"] == "good").mean()), 2)
                            if len(passed) else None),
    }


def axis_bias(df=None) -> dict:
    """BERTモデル と 人間 の軸別スコア差。mean_diff>0 はモデルが甘い（人間より高くつけがち）。"""
    df = load_df() if df is None else df
    out = {}
    pairs = [("hook", "human_hook"), ("specificity", "human_specificity"),
             ("clarity", "human_clarity"), ("relatability", "human_relatability")]
    for j, h in pairs:
        sub = df[df[h].notna() & df[j].notna()]
        if len(sub):
            diff = sub[j] - sub[h]
            out[j] = {"n": int(len(sub)),
                      "mean_diff": round(float(diff.mean()), 2),
                      "mean_abs": round(float(diff.abs().mean()), 2)}
        else:
            out[j] = {"n": 0}
    return out


def grounded_summary(df=None) -> dict:
    """事実忠実性(ok/ng)。judge が見ていない軸。高得点なのに ng は特に重要。"""
    df = load_df() if df is None else df
    sub = df[df["human_grounded"].isin(["ok", "ng"])]
    n = len(sub)
    if n == 0:
        return {"n": 0}
    ng = sub[sub["human_grounded"] == "ng"]
    ng_but_pass = ng[ng["auto_score"] >= config.PASS_TOTAL]
    return {"n": int(n), "ng": int(len(ng)),
            "ng_rate": round(len(ng) / n, 2), "ng_but_pass": int(len(ng_but_pass))}


def revise_value(df=None) -> dict:
    """reviseループの効き。改善率・平均Δ・finalが初稿/修正どちらか・平均修正回数。"""
    df = load_df() if df is None else df
    sub = df[df["initial_score"].notna() & df["auto_score"].notna()]
    n = len(sub)
    if n == 0:
        return {"n": 0}
    delta = sub["auto_score"] - sub["initial_score"]
    ff = df["final_from"].value_counts(dropna=True).to_dict()
    return {"n": int(n),
            "improved_rate": round(float((delta > 0).mean()), 2),
            "mean_delta": round(float(delta.mean()), 2),
            "final_initial": int(ff.get("initial", 0)),
            "final_revised": int(ff.get("revised", 0)),
            "mean_revisions": round(float(sub["revisions"].mean()), 2)}


def threshold_summary(df=None) -> dict:
    """THRESHOLD の妥当性。pass率と、pass した中で人間も good だった割合。"""
    df = load_df() if df is None else df
    scored = df[df["auto_score"].notna()]
    n = len(scored)
    if n == 0:
        return {"n": 0}
    passed = scored[scored["auto_score"] >= config.PASS_TOTAL]
    rated_pass = passed[passed["label"].isin(["good", "bad"])]
    good_rate = (round(float((rated_pass["label"] == "good").mean()), 2)
                 if len(rated_pass) else None)
    return {"n": int(n), "pass_rate": round(len(passed) / n, 2),
            "passed_good_rate": good_rate}
