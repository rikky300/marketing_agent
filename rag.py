"""保存済みDBを読んで検索。埋め込みのやり直しはしない。"""
import os
from langchain_chroma import Chroma
from langchain_core.messages import SystemMessage
import config
from models import embeddings

# DBが無ければ、先に index.py を実行するよう促す
if not os.path.exists(config.CHROMA_DIR):
    raise SystemExit(f"'{config.CHROMA_DIR}' がありません。先に `python index.py` を実行してください。")

# 保存済みのChromaを開く（from_textsではないので再ベクトル化しない）
_db = Chroma(
    embedding_function=embeddings,
    collection_name=config.COLLECTION,
    persist_directory=config.CHROMA_DIR,
)
_retriever = _db.as_retriever(search_kwargs={"k": config.TOP_K})

with open(config.PLAYBOOK_FILE, encoding="utf-8") as f:
    PLAYBOOK = f.read()

def retrieve(query):
    docs = _retriever.invoke(query)
    return "\n---\n".join(d.page_content for d in docs)

def build_system(context):
    return SystemMessage(content=(
        "あなたは個人開発者のSNS運用を支援する編集者です。"
        "以下のアプリ情報『だけ』を根拠に、事実に反しない投稿を書いてください。\n"
        "その際、後半の『伸びる投稿の型』のいずれかに沿わせて、引きを強くしてください。\n\n"
        "=== アプリ情報 ===\n" + context + "\n\n"
        "=== 伸びる投稿の型 ===\n" + PLAYBOOK
    ))