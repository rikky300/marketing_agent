# SNS マーケティング Agent

個人開発者向けの、SNS投稿を自動生成するAIエージェント。

プロダクトのドキュメントを読み込んでおくと、テーマを選ぶだけでXの投稿案を自動で作る。複数案を生成して自動採点し、基準に届かなければ改善コメントをもとに書き直す。作れたけど広めるのが苦手な個人開発者向けに作った。自分自身が最初のユーザー。

---

## 機能

- プロダクト情報をRAGで参照して投稿を生成(ChromaDB)
- 1案ずつ「生成→採点→書き直し」を繰り返す自己修正ループ(LangGraph + LLM-as-a-Judge)
- ループ中に作った全案から一番点数の高い案を最終採用
- テーマはプリセットから選ぶか自由入力
- 文字数カウント・コピーボタン付きのWebUI(Streamlit)
- AIエージェント部署の設計をUIからボタン一つで図として確認できる

---

## 技術スタック

| 役割 | 使用技術 |
|---|---|
| LLM | Gemini 2.5 Flash |
| エージェント | LangGraph |
| RAG | LangChain + ChromaDB |
| UI | Streamlit |
| 埋め込み | Google Generative AI Embeddings |

---

## ファイル構成

```
marketing_agent/
├── config.py       設定(モデル名・パス・閾値)を一箇所に集約
├── models.py       AIモデルの窓口・採点スキーマ(Evaluation)
├── index.py        ベクトル化専用。product.md更新時だけ実行
├── rag.py          保存済みDBを開いて検索・システムメッセージ組立
├── nodes.py        各ノード(retrieve/generate/evaluate/revise/finalize)と分岐(should_continue)
├── graph.py        ノードとエッジをつないでLangGraphのappを組み立てる
├── main.py         CLIから実行するエントリポイント
├── app.py          StreamlitのUIエントリポイント
├── agent_diagram.py エージェント部署の設計図(SVG生成 + assets/agent_dept.png 書き出し)
├── product.md      プロダクト情報(RAGの参照元)
└── playbook.md     伸びる投稿の型(全読み込みでプロンプトに差し込む)
```

---

## 処理フロー

```
[起動時・product.md更新時]
product.md → チャンク分割 → 埋め込みAPI → chroma_db/ に保存

[投稿1本ごと]
テーマ入力
  → retrieve: ChromaDBを検索して関連情報を取得
  → generate: 初稿を1つ書く
  → evaluate: 採点して候補に貯める
  → should_continue 判定:
        合格点(8点)以上 or 書き直し3回に到達 → finalize へ
        それ以外 → revise: コメントをもとに書き直し → evaluate へ戻る
  → finalize: 貯めた全案から一番点数の高い案を採用
  → 完成した投稿を表示(人間が確認してXに投稿)
```

---

## AIエージェント部署の設計

各ノードを「マーケティング部署の担当者」に見立てた設計図。UIの「AIエージェント部署の設計を見る」ボタンからも表示できる。
紫が生成AI(Gemini)を使うエージェント、グレーが人間・検索・決定。

![AIエージェント部署の設計](assets/agent_dept.png)

---

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/rikky300/marketing_agent.git
cd marketing_agent
```

### 2. 仮想環境を作成して有効化

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. ライブラリをインストール

```bash
pip install -r requirements.txt
```

### 4. APIキーを設定

`.env` ファイルを作成して、Google AI StudioのAPIキーを書く。

```
GOOGLE_API_KEY=あなたのキー
```

キーは https://aistudio.google.com/apikey で発行できる。

### 5. プロダクト情報を書く

`product.md` にあなたのアプリの情報を書く。

```markdown
# アプリ名

一言説明。

## 特徴
- 特徴1
- 特徴2

## 誰のためか
ターゲットの説明。

## なぜ作ったか
開発の背景。
```

### 6. ベクトルDBを作成

```bash
python index.py
```

`chroma_db/` フォルダが生成されれば成功。product.md を更新したときは再実行する。

### 7. 起動

```bash
# WebUI
streamlit run app.py

# CLI
python main.py
```

---

## Streamlit Cloudへのデプロイ

1. GitHubにpush(`.env` と `chroma_db/` は `.gitignore` で除外)
2. [share.streamlit.io](https://share.streamlit.io) でリポジトリを接続
3. Settings → Secrets に以下を追加

```toml
GOOGLE_API_KEY = "あなたのキー"
```

4. Deployを押す。初回起動時にベクトルDBが自動生成される。

---

## 注意事項

- `product.md` を編集したら `python index.py` を再実行すること
- `.env` はGitにコミットしないこと
- Gemini APIは無料枠あり。投稿1本の生成でGeminiを最大8回前後呼ぶ