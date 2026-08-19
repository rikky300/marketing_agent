"""全体の設定をまとめる場所。値を変えたいときはここだけ見ればいい。"""

# 生成・採点・埋め込みに使うモデル
CHAT_MODEL = "gemini-2.5-flash"
EMBED_MODEL = "gemini-embedding-001"

# ファイルとベクトルDBの場所
PRODUCT_FILE = "product.md"
PLAYBOOK_FILE = "playbook.md"
CHROMA_DIR = "chroma_db"      # ベクトルDBの保存先フォルダ
COLLECTION = "product"        # DB内のコレクション名（index.pyとrag.pyで一致させる）

# 検索・生成・ループの設定
TOP_K = 3            # 検索で取り出すチャンク数
MAX_REVISIONS = 3    # 最大の書き直し回数（初稿＋この回数まで書き直す）

# 合否ロジック（5軸）。合格 = binary==good かつ 総合得点 > PASS_TOTAL かつ 140字以内(ハード)。
# 総合得点 = 2*hook + specificity + clarity + relatability（最大25）。
PASS_TOTAL = 18

# 添付ドキュメント（PDF/テキスト/URL）の扱い
SHORT_TEXT_LIMIT = 4000  # これ以下の文字数なら埋め込みせず全文をそのまま使う
URL_TIMEOUT = 15         # URL取得のタイムアウト秒

# 自前採点モデル（BERT）。True で採点を Gemini judge からローカルモデルに切り替える。
# スコア=ローカルモデル / comment=Gemini の役割分担（BERTはcommentを生成できないため）。
# 読み込み/推論に失敗したら自動で Gemini judge にフォールバックする。
USE_LOCAL_EVALUATOR = True   # 自前モデルで採点する（torch/モデルが無いCloud等では自動でGeminiにフォールバック）
LOCAL_MODEL_DIR = "models/post_evaluator"  # 重み・トークナイザー・meta.json を置く場所
BERT_MODEL = "cl-tohoku/bert-base-japanese-v3"  # ベースにした事前学習モデル

# チャンク分割
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50