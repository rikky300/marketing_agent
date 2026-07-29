from dotenv import load_dotenv
from typing import TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings  # ★RAG
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.vectorstores import InMemoryVectorStore  # ★RAG
from langchain_text_splitters import RecursiveCharacterTextSplitter  # ★RAG
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END

load_dotenv()

# ── 設定 ──
THRESHOLD = 8
MAX_REVISIONS = 3
THEME = "開発の裏側"
PRODUCT_FILE = "product.md"   # ★RAG 読み込むドキュメント
EMBED_MODEL = "gemini-embedding-001"


# ── Geminiの応答から本文を安全に取り出す ──
def get_text(response):
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


# ── ★RAG 検索の準備（起動時に1回だけ）──
embeddings = GoogleGenerativeAIEmbeddings(model=EMBED_MODEL)

def build_retriever(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks = splitter.split_text(raw)
    print(f"[準備] {path} を {len(chunks)} チャンクに分割してベクトル化")
    store = InMemoryVectorStore.from_texts(chunks, embedding=embeddings)
    return store.as_retriever(search_kwargs={"k": 3})

retriever = build_retriever(PRODUCT_FILE)


# ── 採点結果の形 ──
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


# ── モデル2つ ──
writer = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.9)
judge = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0).with_structured_output(Evaluation)


# ── ★RAG 検索した情報を差し込んだシステムメッセージを作る ──
def build_system(context):
    return SystemMessage(content=(
        "あなたは個人開発者のSNS運用を支援する編集者です。"
        "以下のアプリ情報『だけ』を根拠に、事実に反しない投稿を書いてください。\n\n"
        "=== アプリ情報 ===\n" + context
    ))


def generate_drafts(theme, context, n=3):
    system = build_system(context)
    human = HumanMessage(content=f"テーマ『{theme}』でXの投稿を1つ書いて。140字以内。")
    drafts = []
    for _ in range(n):
        r = writer.invoke([system, human])
        drafts.append(get_text(r).strip())
    return drafts


def evaluate(draft):
    prompt = f"次のX投稿を、辛口の編集者として採点してください。\n\n投稿:\n{draft}"
    return judge.invoke(prompt)


def score_of(e):
    total = e.hook + e.specificity
    if not e.length_ok:
        total -= 5
    return total


# ── State ──
class State(TypedDict):
    theme: str
    context: str          # ★RAG 検索で取り出した関連情報
    draft: str
    evaluation: Evaluation
    revisions: int


# ── ノード ──
def retrieve_node(state: State):   # ★RAG 新しいノード
    docs = retriever.invoke(state["theme"])
    context = "\n---\n".join(d.page_content for d in docs)
    print(f"[検索] テーマに関連する情報を {len(docs)} チャンク取得")
    return {"context": context}


def generate_node(state: State):
    drafts = generate_drafts(state["theme"], state["context"], 3)
    best_d, best_e, best_score = None, None, -999
    for d in drafts:
        e = evaluate(d)
        if score_of(e) > best_score:
            best_d, best_e, best_score = d, e, score_of(e)
    print(f"[生成] 3案から最良を選択 → {best_score}点")
    return {"draft": best_d, "evaluation": best_e, "revisions": 0}


def revise_node(state: State):
    n = state["revisions"] + 1
    print(f"[修正{n}回目] コメントを反映して書き直し中...")
    system = build_system(state["context"])   # ★RAG 同じ関連情報を使う
    human = HumanMessage(content=(
        "次の投稿を、編集者のコメントを踏まえて140字以内で書き直してください。\n\n"
        f"現在の投稿:\n{state['draft']}\n\n"
        f"編集者のコメント:\n{state['evaluation'].comment}"
    ))
    r = writer.invoke([system, human])
    return {"draft": get_text(r).strip(), "revisions": n}


def evaluate_node(state: State):
    e = evaluate(state["draft"])
    print(f"[採点] {score_of(e)}点")
    return {"evaluation": e}


def should_continue(state: State):
    if score_of(state["evaluation"]) >= THRESHOLD:
        return "end"
    if state["revisions"] >= MAX_REVISIONS:
        return "end"
    return "revise"


# ── グラフ ──
graph = StateGraph(State)
graph.add_node("retrieve", retrieve_node)   # ★RAG
graph.add_node("generate", generate_node)
graph.add_node("revise", revise_node)
graph.add_node("evaluate", evaluate_node)

graph.add_edge(START, "retrieve")           # ★RAG まず検索から始める
graph.add_edge("retrieve", "generate")      # ★RAG
graph.add_conditional_edges("generate", should_continue, {"revise": "revise", "end": END})
graph.add_edge("revise", "evaluate")
graph.add_conditional_edges("evaluate", should_continue, {"revise": "revise", "end": END})

app = graph.compile()


# ── 実行 ──
result = app.invoke({"theme": THEME, "context": "", "draft": "", "evaluation": None, "revisions": 0})

e = result["evaluation"]
print("\n===== 最終案 =====")
print(result["draft"])
print(f"[フック{e.hook} / 具体性{e.specificity} / 文字数OK={e.length_ok} / 修正{result['revisions']}回]")
print(f"コメント: {e.comment}")