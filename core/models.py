"""AIモデルの窓口と、採点結果の型をまとめる。"""
from dotenv import load_dotenv
load_dotenv()  # .env のAPIキーを読み込む（どのファイルから実行してもここで確実に）

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from pydantic import BaseModel, Field
import config

# 文章をベクトルに変換するモデル（検索用）。API課金が発生しないよう、ローカルにDLして動かす
# multilingual-e5系は "query: " / "passage: " のprefixを付けると検索精度が上がる仕様のため付与する
embeddings = HuggingFaceEmbeddings(
    model_name=config.EMBED_MODEL,
    encode_kwargs={"prompt": "passage: "},
    query_encode_kwargs={"prompt": "query: "},
)

# 投稿を書くモデル（多様性のため temperature 高め）
writer = ChatGoogleGenerativeAI(model=config.CHAT_MODEL, temperature=0.9)


class Evaluation(BaseModel):
    """投稿の採点結果（scoring_rubric.md の4軸+binary）。自前BERTモデルが埋める。"""
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
    clarity: int = Field(description=(
        "明確さ・一貫性。1〜5の整数。5=主張が1つに絞られ迷わず読める。"
        "3=概ね分かるがやや冗長/要素が多い。1=散らかる・冗長・"
        "『承知しました』等のメタ文や指示文が混入している。"
    ))
    relatability: int = Field(description=(
        "共感・自分ごと化。1〜5の整数。5=読者(個人開発者)の悩み・感情に刺さる。"
        "3=一般論としては分かる。1=発信者視点だけで読者の感情に触れない。"
    ))
    binary: int = Field(description="総合good/bad。良い(自分なら投稿する/伸びそう)なら1、そうでなければ0。")
    length_ok: bool = Field(description="全体が140字以内に収まっているか")


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