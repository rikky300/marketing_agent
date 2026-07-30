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
NUM_DRAFTS = 3       # 1回に生成する案の数
THRESHOLD = 8        # 合格とみなす合計点
MAX_REVISIONS = 3    # 最大の書き直し回数

# チャンク分割
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50