# AgentMark

**「作れたけど、広めるのが苦手」な個人開発者のための、X（旧Twitter）投稿自動生成AIエージェント。**

プロダクト情報を渡してテーマを選ぶだけで、投稿案をAIが生成→自動採点→基準に届かなければ自己修正、を繰り返して1本に仕上げる。作者自身が最初のユーザーで、このエージェントで自分のプロダクトの投稿を作りながら開発している。

🔗 **公開中のアプリ**: https://agentmarkth.streamlit.app

---

## 背景・なぜ作ったか

個人開発をしていて、いつも同じところでつまずいていた。「作る」のはできても「広める」のが苦手で、良いものを作っても誰にも知られずに終わる。

生成AIのおかげで「作る」のハードルはどんどん下がっているのに、「広める」はまだ手つかずの領域だと感じた。それなら、その部分こそAIエージェントに任せられるはず——というのがこのプロジェクトの出発点。

汎用的に「バズる投稿を書いて」と頼むのではなく、**自分のプロダクト固有の情報に基づいて**投稿を作り、**書きっぱなしにせず採点して直す**ところまでをエージェントにやらせている。

現在は「LLMに採点させて自己修正ループを回す」段階から一歩進めて、**人間の評価データを貯めてBERTを自前でファインチューニングし、採点器そのものを自分の審美眼に近づける**フェーズに取り組んでいる（詳細は[採点の仕組み](#採点の仕組み-llm-judgeから自前mlモデルへ)を参照）。

---

## 実際の生成結果

テーマ「どんな人に使ってほしいか」を渡したときの、実際の生成ログ（`data/posts.csv` に記録）。

> **どんな人に使ってほしいか**
>
> 「せっかく作ったアプリ、誰にも知られず埋もれていませんか？」マーケティングで消耗する個人開発者のあなたへ。
>
> AgentMarkは、あなたのプロダクト情報から投稿案を自動生成。さらにAIが採点・修正を繰り返し、刺さる文章に進化させます。「良いもの」を「届く」に変えませんか？

自動採点 8点（合格）・人間評価 👍good。この投稿を含め、AgentMarkが生成した投稿の一部は実際に作者のXアカウントに投稿されている。

---

## 主な機能

- プロダクト情報をRAGで参照して投稿を生成（ChromaDB）。他プロダクトでも、README/LP/PDF/URL/直接入力から投稿を作れる
- 1案ずつ「生成 → 採点 → 書き直し」を繰り返す自己修正ループ（LangGraph）
- ループ中に作った全案から一番点数の高い案を最終採用
- 採点はLLM-as-a-Judge（Gemini）と、自前学習のBERTモデルの2方式に対応（設定で切替）
- テーマはプリセットから選ぶか自由入力。文字数カウント・コピーボタン付きのWebUI（Streamlit）
- 投稿を人間が👍/👎評価して蓄積し、採点モデルの精度検証・再学習に使うローカル専用の評価ダッシュボード
- AIエージェント部署の設計図をUIから確認できる

---

## アーキテクチャ

各ノードを「マーケティング部署の担当者」に見立てた設計図。紫が生成AI（Gemini/BERT）を使う担当、グレーが人間・検索・決定。

![AIエージェント部署の設計](assets/agent_dept.png)

### 処理フロー（LangGraph）

```
START
  → retrieve   : テーマでベクトルDBを検索し、関連情報をcontextに載せる
  → generate   : 初稿を1つ書く（Gemini）
  → evaluate   : 採点して候補リストに貯める（BERT / Gemini judge）
  → should_continue 判定:
        合格ライン(18点)以上 かつ 140字以内 → finalize へ
        修正3回に到達            → finalize へ（不合格でも打ち切り）
        それ以外                → revise: 採点コメントをもとに書き直し → evaluate へ戻る
  → finalize   : 貯めた全案の中から一番点数の高い案を最終採用
END
```

「1案ずつ生成→採点→書き直し」の逐次ループで、初稿も修正稿も必ず採点を通す。途中の最高点が最終案になるとは限らない ——全候補から一番良い案を選ぶ。

---

## 採点の仕組み — LLM Judgeから自前MLモデルへ

投稿は4軸で採点する: **hook**（冒頭の引きの強さ）・**specificity**（具体性）・**clarity**（明確さ・一貫性）・**relatability**（共感・自分ごと化）、それに総合の **binary**（good/bad）。合計点 `2*hook + specificity + clarity + relatability`（最大25点）が合格ライン18点を超え、かつ140字以内なら合格。

このプロジェクトの技術的な核心は「採点をどう信用できるものにするか」という点にある。

1. **現行: LLM-as-a-Judge（Gemini）** — 構造化出力で4軸+binaryを採点。手軽だが、基準がブレやすく、コスト・待ち時間もかかる（投稿1本でGeminiを最大8回呼ぶ）
2. **開発中: 自前BERTファインチューニング** — `cl-tohoku/bert-base-japanese-v3` の上に5つのヘッド（4回帰＋1分類）を乗せ、人間の評価データで学習。判断基準:
   - LLM judge vs 自前モデル vs 人間評価の一致度を検証
   - 生成アプリで👍/👎を集め、投稿物DB（`data/posts.csv`）に蓄積
   - 一定件数貯まったらそのデータでBERTを再学習し、Gemini judgeとの一致率を比較
   - 十分な精度が出たら、生成ループの採点をBERTに切り替える（`config.USE_LOCAL_EVALUATOR`）

```
投稿テキスト
  ↓ BertTokenizer
BERT (cl-tohoku/bert-base-japanese-v3)
  ↓ [CLS]トークンの768次元ベクトル
  ├─ hook_head         → Linear(768→1) + sigmoid → 1〜5
  ├─ specificity_head  → Linear(768→1) + sigmoid → 1〜5
  ├─ clarity_head      → Linear(768→1) + sigmoid → 1〜5
  ├─ relatability_head → Linear(768→1) + sigmoid → 1〜5
  └─ binary_head       → Linear(768→2) → good/bad
```

損失は回帰4軸のMSE＋分類のCrossEntropyの合成、最適化はAdamW（lr=2e-5）。学習・評価は`notebooks/post_evaluator.ipynb`（Google Colab）で行う。モデル未配置・依存未インストールの環境（Streamlit Cloud等）では自動でGemini judgeにフォールバックする。

---

## 技術スタック

| 役割 | 使用技術 |
|---|---|
| LLM・生成 | Gemini 2.5 Flash |
| エージェント | LangGraph |
| RAG | LangChain + ChromaDB |
| 埋め込み | Google Generative AI Embeddings |
| 採点（現行） | Gemini 2.5 Flash 構造化出力（LLM-as-a-Judge） |
| 採点（開発中） | BERT（`cl-tohoku/bert-base-japanese-v3`）ファインチューニング（PyTorch） |
| UI | Streamlit |
| デプロイ | Streamlit Cloud |

---

## ファイル構成

```
marketing_agent/
├── config.py              全設定を一箇所に集約(モデル名・パス・閾値)
├── models.py               AIモデルの窓口・採点スキーマ(Evaluation)
├── index.py                ベクトル化専用。product.md更新時だけ実行
├── rag.py                  検索(ChromaDB) + 添付ドキュメント用の in-memory 検索
├── sources.py               添付ソース読取(PDF/テキスト/URL)
├── nodes.py                 各ノード(retrieve/generate/evaluate/revise/finalize)とState
├── graph.py                 ノードとエッジをつないでLangGraphのappを組み立てる
├── main.py                  CLIエントリポイント
│
├── app.py                   【デプロイ対象】生成アプリ(Streamlit)
├── eval_app.py               【ローカル専用】評価アプリ
├── views_generate.py         生成ページ本体
├── views_evaluate.py         評価ダッシュボード本体
├── agent_diagram.py          部署の設計図(SVG生成 + PNG書き出し)
│
├── posts.py                  投稿物DB(CSV)の読み書き・集計
├── data/posts.csv             投稿物DB本体(1投稿=1行)
├── product.md / playbook.md   プロダクト情報 / 伸びる投稿の型(RAGの参照元)
│
├── local_evaluator.py         自前BERTモデルのローカル推論
├── notebooks/post_evaluator.ipynb  BERTファインチューニング(Colab)
└── notebooks/gen_labels.py    学習データ(labels.jsonl)の生成スクリプト
```

---

## セットアップ

### 1. クローンして環境構築

```bash
git clone https://github.com/rikky300/marketing_agent.git
cd marketing_agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. APIキーを設定

`.env` を作成し、[Google AI Studio](https://aistudio.google.com/apikey) で発行したキーを書く。

```
GOOGLE_API_KEY=あなたのキー
```

### 3. プロダクト情報を書く

`product.md` に自分のアプリの情報（特徴・ターゲット・開発の背景など）を書く。

### 4. ベクトルDBを作成して起動

```bash
python index.py          # product.md 更新時は再実行
streamlit run app.py     # WebUI（生成のみ）
python main.py           # CLI
```

### ローカルで評価ダッシュボード・自前採点モデルを使う場合

```bash
pip install -r requirements-local.txt   # torch等・約2GB
streamlit run eval_app.py               # 評価ダッシュボード(ローカル専用)
```

---

## デプロイ（Streamlit Cloud）

GitHubにpushすると自動で再デプロイされる。`.env` / `chroma_db/` / `models/` は `.gitignore` で除外。Settings → Secrets に `GOOGLE_API_KEY` を設定すればよい。Streamlit Cloudはファイルシステムが毎回リセットされるため、ベクトルDBは初回起動時に自動生成される（`rag.py`）。評価データ（`data/posts.csv`）はCloud側から書き戻せないため、蓄積はローカル実行 → commit/pushが前提。

---

## 今後の展望

- [ ] 人間評価を100件以上貯めて、BERTモデルを本番データで再学習
- [ ] LLM judge・自前モデル・人間評価の一致率を検証し、生成ループの採点を自前モデルに切り替え
- [ ] 事実忠実性（プロダクト情報への忠実さ）を採点する軸を追加
- [ ] 伸びた投稿をplaybookに追記するフィードバックループ
- [ ] 推論サーバーをCloud Runに分離し、認証・課金を付けて他ユーザーに開放

---

## 開発の経緯

1個のファイルで生成→採点→表示を実装 → 採点をPydantic構造化出力（LLM-as-a-Judge）で実装 → 採点基準をルーブリック化 → LangGraphで自己修正ループを実装 → RAG追加（InMemory→ChromaDB） → 役割ごとにファイル分割 → Streamlit UIを実装してデプロイ → 生成フローを「1案ずつ生成→採点→書き直し」の逐次ループに変更 → 投稿物DBと評価アプリを分離 → 添付ソース（PDF/URL/手入力）から生成できるように拡張 → BERT採点モデルのファインチューニング環境をColabで構築（現在ここ）
