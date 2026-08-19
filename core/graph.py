"""ノードとエッジをつないでグラフ（app）を組み立てる。"""
from langgraph.graph import StateGraph, START, END
from core.nodes import (
    State, retrieve_node, generate_node, revise_node, evaluate_node,
    finalize_node, should_continue,
)


def build_app():
    g = StateGraph(State)
    g.add_node("retrieve", retrieve_node)
    g.add_node("generate", generate_node)
    g.add_node("revise", revise_node)
    g.add_node("evaluate", evaluate_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    # 書いたら必ず採点する（初稿も修正稿も evaluate を通す）。
    g.add_edge("generate", "evaluate")
    g.add_edge("revise", "evaluate")
    # 採点後に判定。合格 or 上限に達したら finalize で全案から最良を採用する。
    g.add_conditional_edges("evaluate", should_continue, {"revise": "revise", "end": "finalize"})
    g.add_edge("finalize", END)
    return g.compile()


app = build_app()