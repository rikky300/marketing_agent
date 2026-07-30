"""投稿物DBを見る: 人間評価 vs judge の一致率と、エンゲージメント記入状況。
実行: python analyze_posts.py
"""
import config
from posts import ENGAGEMENT_COLS, agreement_summary, load_df


def main():
    df = load_df()
    if len(df) == 0:
        print("まだ投稿がありません（data/posts.csv が空）。UIで生成してください。")
        return

    rated = df[df["label"].isin(["good", "bad"])]
    has_eng = df["impressions"].notna().sum()
    print("=" * 46)
    print(f"  投稿 {len(df)} 件 / 評価済み {len(rated)} 件 / エンゲージ記入 {has_eng} 件")
    print("=" * 46)

    s = agreement_summary(df)
    if s["n"] == 0:
        print("まだ👍/👎評価がありません。")
    else:
        print(f"合格しきい値 THRESHOLD = {config.THRESHOLD}")
        print(f"👍(good) {s['up']} 件 / 👎(bad) {s['down']} 件")
        print(f"👍 の平均 auto_score : {s['mean_score_up']}")
        print(f"👎 の平均 auto_score : {s['mean_score_down']}")
        print("-" * 46)
        print(f"一致率(judge合否 == good/bad) : {s['agreement_rate']}")
        print(f"judge適合率(合格のうち good)  : {s['judge_precision']}")
        print("-" * 46)
        cell = {("pass", "good"): 0, ("pass", "bad"): 0, ("fail", "good"): 0, ("fail", "bad"): 0}
        for _, r in rated.iterrows():
            j = "pass" if r["auto_score"] >= config.THRESHOLD else "fail"
            cell[(j, r["label"])] += 1
        print("              人間good   人間bad")
        print(f"  judge合格      {cell[('pass','good')]:>5}   {cell[('pass','bad')]:>5}")
        print(f"  judge不合格    {cell[('fail','good')]:>5}   {cell[('fail','bad')]:>5}")
        if s["n"] < 20:
            print("※ 件数が少ないと数字は不安定。20件以上を目安に。")

    print("=" * 46)
    if has_eng == 0:
        cols = ", ".join(ENGAGEMENT_COLS)
        print(f"エンゲージメント列（{cols}）は未記入。投稿後に data/posts.csv へ入力する。")


if __name__ == "__main__":
    main()
