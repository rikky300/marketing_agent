"""グラフの各ステップ（ノード）と、状態・分岐の定義。"""
import operator
from typing import Annotated, TypedDict
from langchain_core.messages import HumanMessage
import config
from models import writer, judge, get_text, Evaluation
from rag import retrieve, build_system


# ── 状態：ノード間で持ち回るデータ ──
class State(TypedDict):
    theme: str
    context: str
    draft: str
    evaluation: Evaluation
    revisions: int
    # 生成・修正の過程で作られた全案を貯めておく（reducer で追記していく）。
    # 最後に finalize でこの中から一番点数の高い案を採用する。
    candidates: Annotated[list, operator.add]


# ── 小さな道具 ──
def _write(theme, context, instruction):
    """コピーライター役。指示文を渡して投稿を1つ書かせる。"""
    system = build_system(context)
    human = HumanMessage(content=instruction)
    return get_text(writer.invoke([system, human])).strip()


def _evaluate(draft):
    prompt = f"次のX投稿を、辛口の編集者として採点してください。\n\n投稿:\n{draft}"
    return judge.invoke(prompt)


def _score(e):
    total = e.hook + e.specificity
    if not e.length_ok:
        total -= 5
    return total


def _candidate(draft, evaluation):
    """全案リストに貯める1件分のレコード。"""
    return {"draft": draft, "evaluation": evaluation, "score": _score(evaluation)}


# ── ノード ──
def retrieve_node(state: State):
    context = retrieve(state["theme"])
    print("[検索] 関連情報を取得")
    return {"context": context}


def generate_node(state: State):
    # まず初稿を1つだけ書く。採点は evaluate ノードが担当する。
    draft = _write(state["theme"], state["context"],
                   f"テーマ『{state['theme']}』でXの投稿を1つ書いて。140字以内。")
    print("[生成] 初稿を作成")
    return {"draft": draft, "revisions": 0}


def revise_node(state: State):
    n = state["revisions"] + 1
    print(f"[修正{n}回目] コメントを反映して書き直し中...")
    draft = _write(state["theme"], state["context"], (
        "次の投稿を、編集者のコメントを踏まえて140字以内で書き直してください。\n\n"
        f"現在の投稿:\n{state['draft']}\n\n"
        f"編集者のコメント:\n{state['evaluation'].comment}"
    ))
    return {"draft": draft, "revisions": n}


def evaluate_node(state: State):
    # 書かれた案を採点し、後で選べるよう候補として貯める。
    e = _evaluate(state["draft"])
    print(f"[採点] {_score(e)}点")
    return {"evaluation": e, "candidates": [_candidate(state["draft"], e)]}


def finalize_node(state: State):
    """貯めた全案の中から一番点数の高い案を最終採用する。"""
    best = max(state["candidates"], key=lambda c: c["score"])
    print(f"[確定] 全{len(state['candidates'])}案から最良を採用 → {best['score']}点")
    return {"draft": best["draft"], "evaluation": best["evaluation"]}


def should_continue(state: State):
    if _score(state["evaluation"]) >= config.THRESHOLD:
        return "end"
    if state["revisions"] >= config.MAX_REVISIONS:
        return "end"
    return "revise"