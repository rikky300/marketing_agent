"""本体。テーマを選んで投稿を作り、完成した投稿を表示する。
   実行: python main.py （事前に一度 python index.py でDBを作っておくこと）"""
import config
from graph import app

PRESET_THEMES = [
    "開発の裏側",
    "このツールで解決したい課題",
    "新しく作っている機能",
    "個人開発でつまずいたこと",
    "どんな人に使ってほしいか",
]


def choose_theme():
    print("投稿のテーマを選んでください")
    for i, t in enumerate(PRESET_THEMES, 1):
        print(f"  {i}. {t}")
    raw = input("番号を入力、または自由に入力（Enterで1番）: ").strip()
    if raw == "":
        return PRESET_THEMES[0]
    if raw.isdigit() and 1 <= int(raw) <= len(PRESET_THEMES):
        return PRESET_THEMES[int(raw) - 1]
    return raw


def main():
    theme = choose_theme()
    print(f"\n『{theme}』で投稿を作成します...\n")

    result = app.invoke(
        {"theme": theme, "context": "", "draft": "", "evaluation": None, "revisions": 0})

    post = result["draft"]
    e = result["evaluation"]

    print("\n" + "=" * 42)
    print("  完成した投稿（下の本文をコピーして貼り付け）")
    print("=" * 42 + "\n")
    print(post)
    print("\n" + "-" * 42)
    print(f"文字数 {len(post)} / フック{e.hook}・具体性{e.specificity} / 修正{result['revisions']}回")
    print("=" * 42)


if __name__ == "__main__":
    main()