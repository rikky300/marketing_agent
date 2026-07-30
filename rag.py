"""保存済みDBを読んで検索。埋め込みのやり直しはしない。playbook読込とシステムメッセージ組立も担う。"""
import os
from pathlib import Path
from langchain_chroma import Chroma
from langchain_core.messages import SystemMessage
import config
from models import embeddings


def _ensure_db():
    """chroma_dbがなければindex.pyの処理を実行してDBを作る。"""
    if not Path(config.CHROMA_DIR).exists():
        print(f"'{config.CHROMA_DIR}' が見つかりません。ベクトル化を開始します...")
        # index.pyと同じ処理をここで直接実行
        import shutil
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        with open(config.PRODUCT_FILE, encoding="utf-8") as f:
            raw = f.read()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
        chunks = splitter.split_text(raw)
        print(f"{config.PRODUCT_FILE} を {len(chunks)} チャンクに分割してベクトル化")

        Chroma.from_texts(
            texts=chunks,
            embedding=embeddings,
            collection_name=config.COLLECTION,
            persist_directory=config.CHROMA_DIR,
        )
        print("ベクトルDB作成完了")


_ensure_db()

_db = Chroma(
    embedding_function=embeddings,
    collection_name=config.COLLECTION,
    persist_directory=config.CHROMA_DIR,
)
_retriever = _db.as_retriever(search_kwargs={"k": config.TOP_K})

with open(config.PLAYBOOK_FILE, encoding="utf-8") as f:
    PLAYBOOK = f.read()


def retrieve(query):
    """テーマに関連するチャンクを検索して、つなげた文字列で返す。"""
    docs = _retriever.invoke(query)
    return "\n---\n".join(d.page_content for d in docs)


def build_system(context):
    """検索した情報と投稿の型を差し込んだシステムメッセージを作る。"""
    return SystemMessage(content=(
        "あなたは個人開発者のSNS運用を支援する編集者です。"
        "以下のアプリ情報『だけ』を根拠に、事実に反しない投稿を書いてください。\n"
        "その際、後半の『伸びる投稿の型』のいずれかに沿わせて、引きを強くしてください。\n\n"
        "=== アプリ情報 ===\n" + context + "\n\n"
        "=== 伸びる投稿の型 ===\n" + PLAYBOOK
    ))