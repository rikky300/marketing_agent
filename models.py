"""AIモデルの窓口と、採点結果の型をまとめる。"""
from dotenv import load_dotenv
load_dotenv()  # .env のAPIキーを読み込む（どのファイルから実行してもここで確実に）

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, Field
import config

# 文章をベクトルに変換するモデル（検索用）
embeddings = GoogleGenerativeAIEmbeddings(model=config.EMBED_MODEL)

# 投稿を書くモデル（多様性のため temperature 高め）
writer = ChatGoogleGenerativeAI(model=config.CHAT_MODEL, temperature=0.9)


class Evaluation(BaseModel):
    """SNS投稿を辛口の編集者として採点した結果。"""
    hook: int = Field(description=(
        "冒頭一行が読み手のスクロールを止める力。1〜5の整数。"
        "5=最初の一行で『自分のことだ』と思わせ続きを読みたくなる。"
        "3=悪くないが平凡。1=説明から入り引きが無い。"
        "『ありきたり』『平凡』な冒頭は2以下にすること。"
    ))
    specificity: int = Field(description=(
        "具体性。1〜5の整数。5=数字や固有の体験があり情景が浮かぶ。"
        "3=一部具体的だが抽象語も混じる。1=抽象的で中身が薄い。"
    ))
    length_ok: bool = Field(description="全体が140字以内に収まっているか")
    comment: str = Field(description="最も効く改善点を一つだけ、短い日本語で")


# 採点するモデル（ブレないよう temperature 0、決まった形 Evaluation で返す）
judge = ChatGoogleGenerativeAI(model=config.CHAT_MODEL, temperature=0).with_structured_output(Evaluation)


def get_text(response):
    """Geminiの応答から本文テキストを取り出す（文字列でもリストでも対応）。"""
    content = response.content
    if isinstance(content, str):
        return content
    parts = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and "text" in item:
            parts.append(item["text"])
    return "".join(parts)