# AgentMark

「作れたけど、広めるのが苦手」な個人開発者のための、X（旧Twitter）投稿自動生成AIエージェント。プロダクト情報を渡すと、生成 → 自前BERTモデルで自動採点 → 基準未達なら自己修正、を繰り返して1本に仕上げる。作者自身が最初のユーザーで、実際にこのエージェントで自分の投稿を作っている。

ダウンロードしてローカルで動かすアプリ（公開ホスティングはしていない。理由は[コンセプト](#コンセプト-ローカルで育てるagentmark)を参照）。

---

# 使い方

## まとめて実行する（推奨・1行）

ダウンロード方法(git clone / ZIP) × OS(macOS・Linux / Windows) の4パターン。貼り付けるとAPIキーの入力だけ求められ、そのままアプリが起動する。

### git cloneの場合

macOS / Linux:

```bash
cd ~ && git clone https://github.com/rikky300/marketing_agent.git && cd marketing_agent && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && echo -n "Google AI StudioのAPIキーを貼り付けてEnter: " && read -s KEY && echo && echo "GOOGLE_API_KEY=$KEY" > .env && python notebooks/train_evaluator.py && python index.py && streamlit run app.py
```

Windows (PowerShell):

```powershell
cd ~; git clone https://github.com/rikky300/marketing_agent.git; cd marketing_agent; python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt; $secure = Read-Host "Google AI StudioのAPIキーを貼り付けてEnter" -AsSecureString; $KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)); Set-Content -Path .env -Value "GOOGLE_API_KEY=$KEY" -Encoding ascii; python notebooks/train_evaluator.py; python index.py; streamlit run app.py
```

### ZIPダウンロードの場合

ブラウザの標準設定のままなら `~/Downloads`（Windowsは `~\Downloads`）に`marketing_agent-main`という名前で展開される。下のコマンドはそれを前提に、まずそのフォルダへ`cd`してから始まる。違う場所に展開した場合はコマンド先頭の`cd`のパスを書き換えること（そのままだと「フォルダが無い」で安全に止まるだけなので、間違えても実害は無い）。

macOS / Linux:

```bash
cd ~/Downloads/marketing_agent-main && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && echo -n "Google AI StudioのAPIキーを貼り付けてEnter: " && read -s KEY && echo && echo "GOOGLE_API_KEY=$KEY" > .env && python notebooks/train_evaluator.py && python index.py && streamlit run app.py
```

Windows (PowerShell):

```powershell
cd ~\Downloads\marketing_agent-main; python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt; $secure = Read-Host "Google AI StudioのAPIキーを貼り付けてEnter" -AsSecureString; $KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)); Set-Content -Path .env -Value "GOOGLE_API_KEY=$KEY" -Encoding ascii; python notebooks/train_evaluator.py; python index.py; streamlit run app.py
```

Windows PowerShellは`;`区切りだと1つのコマンドが失敗しても後続が実行され続けるので、実行中に赤いエラーが出たら一度止めて内容を確認すること。`.venv\Scripts\Activate.ps1`がスクリプト実行ポリシーでブロックされる場合は、`Set-ExecutionPolicy -Scope Process RemoteSigned`を先に実行しておくとよい。

## 個別に実行する

1行版がうまくいかない場合や、各ステップの内容を確認したい場合はこちら。

1. **ダウンロード** — `git clone https://github.com/rikky300/marketing_agent.git`、または GitHubの`Code → Download ZIP`
2. **環境構築**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows(PowerShell): .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   torch等を含むため初回は数分・合計2GB前後かかる（採点モデル用・埋め込みモデル用）。
3. **APIキーを設定**
   ```bash
   echo "GOOGLE_API_KEY=" > .env
   ```
   [Google AI Studio](https://aistudio.google.com/apikey)でキーを発行し、`.env`の`=`の後ろに貼り付ける（生成に使うGemini用のみでよい。埋め込みはローカルモデルなのでキー不要）。
4. **採点モデルを学習する**
   ```bash
   python notebooks/train_evaluator.py
   ```
   同梱の`notebooks/labels.jsonl`（116件）でBERTを学習し、`local/models/post_evaluator/`に保存する（Colab/Jupyter不要。CPUのみでも数分）。採点はこのモデルのみで行う設計のため、これが無いと生成ループが止まる。GPU環境で学習したい場合は`notebooks/post_evaluator.ipynb`（Colab版）も同梱。
5. **起動**
   ```bash
   python index.py
   streamlit run app.py
   ```
   `http://localhost:8501`が自動的に開く。「① 生成」で投稿を作り、「② 評価」で採点精度や👍/👎の内訳を確認できる。CLIだけで試す場合は`python main.py`。

## 2回目以降の起動

初回セットアップ済みなら、venvの有効化とアプリ起動だけでよい（パッケージの再インストール・採点モデルの再学習・ベクトルDBの再作成は不要）。

git cloneした場合（macOS / Linux）:

```bash
cd ~/marketing_agent && source .venv/bin/activate && streamlit run app.py
```

git cloneした場合（Windows PowerShell）:

```powershell
cd ~\marketing_agent; .venv\Scripts\Activate.ps1; streamlit run app.py
```

ZIPでダウンロードした場合（macOS / Linux）:

```bash
cd ~/Downloads/marketing_agent-main && source .venv/bin/activate && streamlit run app.py
```

ZIPでダウンロードした場合（Windows PowerShell）:

```powershell
cd ~\Downloads\marketing_agent-main; .venv\Scripts\Activate.ps1; streamlit run app.py
```

終了はターミナルで`Ctrl + C`。product.mdを更新した時だけ、起動前に`python index.py`を挟んでベクトルDBを作り直す。

## 自分のプロダクトに使う場合

同梱の`product.md`はAgentMark自身の製品情報（サンプル兼、作者の実利用データ）。

1. `product.md`を自分のプロダクトの内容に書き換える（特徴・ターゲット・開発の背景など）
2. `python index.py`でベクトルDBを作り直す
3. （任意）`playbook.md`（伸びる投稿の型）を編集して生成のトーンを調整する
4. 書き換えた`product.md`を誤って上流にpushしないよう注意する。git管理下のままにしたい場合は`git update-index --skip-worktree product.md`で追跡から外せる（ZIPダウンロードならそもそもgit管理外なので不要）

---

# このプロジェクトについて

## 背景・なぜ作ったか

個人開発をしていて、いつも同じところでつまずいていた——「作る」のはできても「広める」のが苦手で、良いものを作っても誰にも知られずに終わる。生成AIで「作る」ハードルはどんどん下がっているのに、「広める」はまだ手つかず。それなら、その部分こそAIエージェントに任せられるはず、というのがこのプロジェクトの出発点。

汎用的に「バズる投稿を書いて」と頼むのではなく、**自分のプロダクト固有の情報に基づいて**投稿を作り、**書きっぱなしにせず採点して直す**ところまでをエージェントにやらせている。

## コンセプト：ローカルで育てるAgentMark

公開Webサービスにはせず、あえてローカル環境だけで動かしている。理由は2つ。

1. **使うほど自分専用に育つ** — 手元で使い続けるたびに、自分の投稿・良い/悪い評価・実際のエンゲージメントがローカルに貯まる。そのデータで採点モデル（BERT）を再学習し、汎用の「それっぽい採点」から「自分の審美眼に近い採点」へ育てていく
2. **公開する前に、まず信頼できる形にする** — LLM-as-a-Judgeの採点をそのまま信用せず、自前モデル・人間評価・実エンゲージメントを突き合わせて検証してから、初めて他の人にも使える形にする

今のAgentMarkは「テーマを渡すと1投稿を作る」ワークフロー型のエージェント1体。将来は、リサーチ・ライティング・採点・分析・戦略提案を専門分業する複数エージェントに分割し、1つの**「AIマーケティング部署」**として機能させることを最終的なゴールに見据えている。

```
現在地 ── ローカルで「1投稿を作る」ワークフロー型エージェント
   │       generate → evaluate → revise の自己修正ループ(LangGraph)
   ↓
次   ── ローカルで採点モデルを自分のデータに特化させる
   │       人間評価を貯める → BERTファインチューニング → judge/自前モデル/人間の一致を検証
   ↓
先   ── 生成品質・採点精度が安定したら、複数エージェントに分業してマーケティング部署化
           リサーチ担当・ライター・編集(採点)・分析担当、を連携させて運用する
```

## 実際の生成結果

テーマ「どんな人に使ってほしいか」を渡したときの、実際の生成ログ（`data/posts.csv`に記録）。

> 「せっかく作ったアプリ、誰にも知られず埋もれていませんか？」マーケティングで消耗する個人開発者のあなたへ。
>
> AgentMarkは、あなたのプロダクト情報から投稿案を自動生成。さらにAIが採点・修正を繰り返し、刺さる文章に進化させます。「良いもの」を「届く」に変えませんか？

自動採点8点（合格）・人間評価👍good。

## 主な機能

- プロダクト情報をRAGで参照して投稿を生成（ChromaDB）。他プロダクトでも、README/LP/PDF/URL/直接入力から投稿を作れる
- 1案ずつ「生成 → 採点 → 書き直し」を繰り返す自己修正ループ（LangGraph）。全案から一番点数の高い案を最終採用
- 採点は自前学習のBERTモデルのみで行う（LLMはジャッジに使わない。生成はGeminiを使う）
- テーマはプリセットから選ぶか自由入力。文字数カウント・コピーボタン付きのWebUI（Streamlit）
- 投稿を👍/👎評価して蓄積し、採点モデルの精度検証・再学習に使う評価ダッシュボード
- AIエージェント部署の設計図をUIから確認できる

## アーキテクチャ

各ノードを「マーケティング部署の担当者」に見立てた設計図。紫が生成AI（Gemini/BERT）を使う担当、グレーが人間・検索・決定。

![AIエージェント部署の設計](assets/agent_dept.png)

```
START
  → retrieve   : テーマでベクトルDBを検索し、関連情報をcontextに載せる
  → generate   : 初稿を1つ書く（Gemini）
  → evaluate   : 採点して候補リストに貯める（自前BERT）
  → should_continue 判定:
        合格ライン(18点)以上 かつ 140字以内 → finalize へ
        修正3回に到達            → finalize へ（不合格でも打ち切り）
        それ以外                → revise: 採点コメントをもとに書き直し → evaluate へ戻る
  → finalize   : 貯めた全案の中から一番点数の高い案を最終採用
END
```

初稿も修正稿も必ず採点を通す逐次ループで、途中の最高点が最終案になるとは限らない——全候補から一番良い案を選ぶ。

## 採点の仕組み — LLM Judgeから自前MLモデルへ

投稿は4軸で採点する: **hook**（冒頭の引きの強さ）・**specificity**（具体性）・**clarity**（明確さ・一貫性）・**relatability**（共感・自分ごと化）、それに総合の**binary**（good/bad）。合計点`2*hook + specificity + clarity + relatability`（最大25点）が合格ライン18点を超え、かつ140字以内なら合格。

このプロジェクトの技術的な核心は「採点をどう信用できるものにするか」。最初はGemini(LLM-as-a-Judge)に構造化出力で採点させていたが、手軽な反面、基準がブレやすくコスト・待ち時間もかかり（投稿1本でGeminiを最大8回呼ぶ計算）、「LLMが良いと言った投稿をLLMが採点して合格にする」自己参照ループにもなる。そこで人間の評価データを貯めて**`cl-tohoku/bert-base-japanese-v3`をファインチューニングした自前モデル**に採点を完全移行した。**現在、採点はこの自前BERTモデルのみで行い、LLMはジャッジとして一切使わない**（生成そのものはGeminiを使う）。

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

損失は回帰4軸のMSE＋分類のCrossEntropyの合成、最適化はAdamW（lr=2e-5）。学習は`python notebooks/train_evaluator.py`一発でローカル完結（同じ構成のColab版もある）。判断基準の検証は継続中で、評価タブでLLM judge時代の記録・自前モデル・人間評価の一致度や軸別のズレを確認できる。

## 技術スタック

| 役割 | 使用技術 |
|---|---|
| LLM・生成 | Gemini 2.5 Flash |
| エージェント | LangGraph |
| RAG | LangChain + ChromaDB |
| 埋め込み | ローカル埋め込みモデル（`intfloat/multilingual-e5-small`, sentence-transformers。API課金なし） |
| 採点 | 自前ファインチューニングBERT（`cl-tohoku/bert-base-japanese-v3`, PyTorch）。LLMはジャッジに使わない |
| UI | Streamlit（ローカル実行のみ） |

## ファイル構成

```
marketing_agent/
├── app.py                  Streamlitアプリ本体（① 生成 / ② 評価 をタブで切替）
├── main.py                 CLIエントリポイント
├── index.py                ベクトル化専用。product.md更新時だけ実行
├── analyze_posts.py        投稿物DBの集計をCLIで見る
├── config.py               全設定を一箇所に集約(モデル名・パス・閾値)
├── product.md / playbook.md  プロダクト情報 / 伸びる投稿の型(RAGの参照元)
│
├── core/                   エージェント本体(LangGraph)
│   ├── nodes.py            各ノード(retrieve/generate/evaluate/revise/finalize)とState
│   ├── graph.py            ノードとエッジをつないでappを組み立てる
│   ├── models.py           AIモデルの窓口・採点スキーマ(Evaluation)
│   ├── rag.py              検索(ChromaDB) + 添付ドキュメント用の in-memory 検索
│   └── sources.py          添付ソース読取(PDF/テキスト/URL)
│
├── ui/                     Streamlit UI
│   ├── views_generate.py   生成ページ(4ステップのウィザード)
│   ├── views_evaluate.py   評価ダッシュボード(採点精度・軸ズレ・投稿一覧の編集)
│   ├── ui_common.py        set_page_config + CSS
│   └── agent_diagram.py    部署の設計図(SVG生成 + PNG書き出し)
│
├── scoring/                採点・投稿物DB
│   ├── posts.py            投稿物DB(CSV)の読み書き・集計
│   └── local_evaluator.py  自前BERTモデルのローカル推論
│
├── data/posts.csv          投稿物DB本体(1投稿=1行。使うほど貯まっていく)
├── docs/scoring_rubric.md  採点ルーブリック(4軸+binaryの定義)
├── notebooks/              BERTファインチューニング
│   ├── train_evaluator.py  コマンドでローカル学習(Colab不要)
│   ├── post_evaluator.ipynb  同じ内容のColab版(GPUを使いたい時)
│   ├── gen_labels.py       学習データ(labels.jsonl)の生成スクリプト
│   └── labels.jsonl        学習データ本体(116件)
│
└── local/                  Git管理外。生成物・DL物をまとめて格納
    ├── chroma_db/          ベクトルDB(index.py実行で生成)
    └── models/             採点モデルの重み(「採点モデルを学習する」参照)
```

## 今後の展望

- [ ] 人間評価を100件以上貯めて、BERTモデルを本番データで再学習
- [ ] LLM judge・自前モデル・人間評価の一致率を検証し、生成ループの採点を自前モデルに切り替え
- [ ] 事実忠実性（プロダクト情報への忠実さ）を採点する軸を追加
- [ ] 伸びた投稿をplaybookに追記するフィードバックループ
- [ ] 生成品質・採点精度が安定したら、リサーチ・ライティング・採点・分析を専門分業する複数エージェントに分割し、AIマーケティング部署として運用する
- [ ] マーケティング部署として十分な実用性が持てた場合、Web上での運用を視野に知れて収益化を図りたい
