# AgentMark

個人開発者のための、X（旧Twitter）投稿を作る AI エージェント。
**生成 → ファインチューニングした BERT で採点 → 基準未達なら書き直し** を繰り返し、一番点の高い案を採用する。

## 背景
- 個人開発で「作る」はできても「広める」が苦手
- 汎用の「バズる投稿を書いて」ではなく、自分のプロダクトの情報に基づいて書き、採点して直すところまで任せたい
- 公開ホスティングはせずローカルで動かす（自分の評価データで採点モデルを育てるため）

## 構成
![architecture](docs/architecture.png)

- 検索: プロダクト情報を ChromaDB に索引（埋め込みはローカルの multilingual-e5-small）
- 生成・書き直し: Gemini 2.5 Flash
- 採点: ファインチューニングした BERT（cl-tohoku/bert-base-japanese-v3）。LLM は採点に使わない
- 判定: 25 点中 18 点以上・140 字以内で合格、または書き直し 3 回で終了 → 全候補から最高点を採用
- 育てる: 投稿に 👍/👎 を付けて蓄積し、採点モデルを再学習

## 採点モデル
- LLM-as-a-Judge をやめた理由: 基準がぶれる・遅い・LLM が書いたものを LLM が合格にする自己参照
- BERT の [CLS] から 4 軸の回帰（hook・具体性・明確さ・共感、1〜5）＋ good/bad の分類
- 損失は 4 軸の MSE ＋ 分類の CrossEntropy（同梱のラベル 116 件で学習）

## 使い方
```bash
pip install -r requirements.txt
echo "GOOGLE_API_KEY=<Google AI Studio のキー>" > .env
python notebooks/train_evaluator.py   # 採点モデルの学習（CPU で数分）
python index.py && streamlit run app.py
```

## 今後
- 人の評価を 100 件以上貯めて再学習し、人の評価との一致を検証
- リサーチ・執筆・採点・分析を分担する複数エージェントへ
