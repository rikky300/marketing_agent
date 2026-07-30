"""ノードとエッジをつないでグラフ（app）を組み立てる。"""
from langgraph.graph import StateGraph, START, END
from nodes import (
    State, retrieve_node, generate_node, revise_node, evaluate_node, should_continue,
)


def build_app():
    g = StateGraph(State)
    g.add_node("retrieve", retrieve_node)
    g.add_node("generate", generate_node)
    g.add_node("revise", revise_node)
    g.add_node("evaluate", evaluate_node)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_conditional_edges("generate", should_continue, {"revise": "revise", "end": END})
    g.add_edge("revise", "evaluate")
    g.add_conditional_edges("evaluate", should_continue, {"revise": "revise", "end": END})
    return g.compile()


app = build_app()