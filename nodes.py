"""グラフの各ステップ（ノード）と、状態・分岐の定義。"""
from typing import TypedDict
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


# ── 小さな道具 ──
def _generate_drafts(theme, context, n):
    system = build_system(context)
    human = HumanMessage(content=f"テーマ『{theme}』でXの投稿を1つ書いて。140字以内。")
    return [get_text(writer.invoke([system, human])).strip() for _ in range(n)]


def _evaluate(draft):
    prompt = f"次のX投稿を、辛口の編集者として採点してください。\n\n投稿:\n{draft}"
    return judge.invoke(prompt)


def _score(e):
    total = e.hook + e.specificity
    if not e.length_ok:
        total -= 5
    return total


# ── ノード ──
def retrieve_node(state: State):
    context = retrieve(state["theme"])
    print("[検索] 関連情報を取得")
    return {"context": context}


def generate_node(state: State):
    drafts = _generate_drafts(state["theme"], state["context"], config.NUM_DRAFTS)
    best_d, best_e, best_s = None, None, -999
    for d in drafts:
        e = _evaluate(d)
        if _score(e) > best_s:
            best_d, best_e, best_s = d, e, _score(e)
    print(f"[生成] {config.NUM_DRAFTS}案から最良を選択 → {best_s}点")
    return {"draft": best_d, "evaluation": best_e, "revisions": 0}


def revise_node(state: State):
    n = state["revisions"] + 1
    print(f"[修正{n}回目] コメントを反映して書き直し中...")
    system = build_system(state["context"])
    human = HumanMessage(content=(
        "次の投稿を、編集者のコメントを踏まえて140字以内で書き直してください。\n\n"
        f"現在の投稿:\n{state['draft']}\n\n"
        f"編集者のコメント:\n{state['evaluation'].comment}"
    ))
    return {"draft": get_text(writer.invoke([system, human])).strip(), "revisions": n}


def evaluate_node(state: State):
    e = _evaluate(state["draft"])
    print(f"[採点] {_score(e)}点")
    return {"evaluation": e}


def should_continue(state: State):
    if _score(state["evaluation"]) >= config.THRESHOLD:
        return "end"
    if state["revisions"] >= config.MAX_REVISIONS:
        return "end"
    return "revise"