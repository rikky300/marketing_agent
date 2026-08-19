"""ベクトル化専用。product.md を更新したら実行してDBを作り直す。  実行: python index.py"""
import os, shutil
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
import config
from core.models import embeddings

def main():
    # 作り直しのたびに古いDBを消して、重複を防ぐ
    if os.path.exists(config.CHROMA_DIR):
        shutil.rmtree(config.CHROMA_DIR)
        print("既存のベクトルDBを削除して作り直します")

    with open(config.PRODUCT_FILE, encoding="utf-8") as f:
        raw = f.read()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
    chunks = splitter.split_text(raw)
    print(f"{config.PRODUCT_FILE} を {len(chunks)} チャンクに分割")

    # ここで埋め込みAPIを呼び、結果を chroma_db フォルダに保存する
    Chroma.from_texts(
        texts=chunks,
        embedding=embeddings,
        collection_name=config.COLLECTION,
        persist_directory=config.CHROMA_DIR,
    )
    print(f"ベクトルDBを '{config.CHROMA_DIR}/' に保存しました")

if __name__ == "__main__":
    main()