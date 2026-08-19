"""グラフの各ステップ（ノード）と、状態・分岐の定義。"""
import operator
from typing import Annotated, TypedDict
from langchain_core.messages import HumanMessage
import config
from core.models import writer, get_text, Evaluation
from core.rag import retrieve, build_system


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
    """採点は自前BERTモデルのみで行う（LLMはジャッジに使わない）。
    4軸+binaryを返す。length_okはコードで判定。"""
    from scoring.local_evaluator import get_evaluator
    s = get_evaluator().score(draft)
    print(f"[採点] 4軸 hook={s['hook']} 具体性={s['specificity']} 明確さ={s['clarity']}"
          f" 共感={s['relatability']} / binary={'good' if s['binary'] else 'bad'}")
    length_ok = len(draft) <= 140
    return Evaluation(hook=s["hook"], specificity=s["specificity"],
                      clarity=s["clarity"], relatability=s["relatability"],
                      binary=s["binary"], length_ok=length_ok)


def _score(e):
    """4軸合計スコア。最大25点（hook×2 + specificity + clarity + relatability）。"""
    return 2 * e.hook + e.specificity + getattr(e, "clarity", 3) + getattr(e, "relatability", 3)


def _candidate(draft, evaluation):
    """全案リストに貯める1件分のレコード。"""
    return {"draft": draft, "evaluation": evaluation, "score": _score(evaluation)}


# ── ノード ──
def _preview(text, n=45):
    """ログ用に本文を1行で短く表示する。"""
    return text.replace("\n", " ")[:n] + ("…" if len(text) > n else "")


def retrieve_node(state: State):
    # 添付ドキュメントから作った context が既にあれば、それを使う（既定のproduct.mdは引かない）。
    if state.get("context", "").strip():
        print(f"[1/5 検索] 添付ドキュメントの情報を使用 ({len(state['context'])}字)")
        return {}
    context = retrieve(state["theme"])
    print(f"[1/5 検索] product.mdから関連情報を取得 ({len(context)}字)")
    return {"context": context}


def generate_node(state: State):
    # まず初稿を1つだけ書く。採点は evaluate ノードが担当する。
    print(f"[2/5 生成] テーマ『{state['theme']}』で初稿を作成中...")
    draft = _write(state["theme"], state["context"], (
        f"テーマ『{state['theme']}』でXの投稿を1つ書いて。\n"
        "出力は投稿本文『だけ』。前置き・説明・「承知しました」等は書かない。140字以内。"
    ))
    print(f"[2/5 生成] 初稿({len(draft)}字): {_preview(draft)}")
    return {"draft": draft, "revisions": 0}


def _revise_hints(e):
    """採点結果(4軸+140字判定)から具体的な改善方向を作る。"""
    hints = []
    if e.hook <= 3:
        hints.append("・冒頭の一行を強くする（読者の悩みへの問いかけ／逆説／具体的な事実で引く）")
    if e.specificity <= 3:
        hints.append("・具体的な数字や固有の体験を入れて具体性を上げる")
    if getattr(e, "clarity", 5) <= 3:
        hints.append("・主張を1つに絞る（前置き・散らかり・メタ文を削除）")
    if getattr(e, "relatability", 5) <= 3:
        hints.append("・読者（個人開発者）の悩みや感情に直接触れる")
    if not e.length_ok:
        hints.append("・140字以内に必ず収める")
    if not hints:
        hints.append("・フック・具体性・明確さ・共感を全体的に磨く")
    return "\n".join(hints)


def revise_node(state: State):
    n = state["revisions"] + 1
    print(f"[4/5 修正{n}回目] 書き直し中...")
    draft = _write(state["theme"], state["context"], (
        "次のX投稿を改善して書き直してください。\n"
        "出力は投稿本文『だけ』。前置き・説明・コメント・「承知しました」等は一切書かない。140字以内。\n\n"
        f"現在の投稿:\n{state['draft']}\n\n"
        "改善の方向:\n" + _revise_hints(state["evaluation"])
    ))
    print(f"[4/5 修正{n}回目] 新しい案({len(draft)}字): {_preview(draft)}")
    return {"draft": draft, "revisions": n}


def evaluate_node(state: State):
    # 書かれた案を採点し、後で選べるよう候補として貯める。
    e = _evaluate(state["draft"])
    pen = " ⚠140字超" if not e.length_ok else ""
    print(f"[3/5 採点] hook={e.hook} 具体性={e.specificity} 明確さ={getattr(e,'clarity','?')}"
          f" 共感={getattr(e,'relatability','?')} → 合計{_score(e)}点 / 合格{config.PASS_TOTAL}点{pen}")
    return {"evaluation": e, "candidates": [_candidate(state["draft"], e)]}


def finalize_node(state: State):
    """貯めた全案の中から一番点数の高い案を最終採用する。"""
    scores = [c["score"] for c in state["candidates"]]
    best = max(state["candidates"], key=lambda c: c["score"])
    print(f"[5/5 確定] 全{len(scores)}案のスコア {scores} → 最良 {best['score']}点 を採用")
    print(f"[5/5 確定] 最終案: {_preview(best['draft'], 60)}")
    return {"draft": best["draft"], "evaluation": best["evaluation"]}


def should_continue(state: State):
    e = state["evaluation"]
    score = _score(e)
    passed = score >= config.PASS_TOTAL and e.length_ok
    if passed:
        print(f"[判定] {score}点 ≥ 合格{config.PASS_TOTAL}点 かつ140字内 → 確定へ")
        return "end"
    if state["revisions"] >= config.MAX_REVISIONS:
        reason = f"{score}点" + ("" if e.length_ok else "・140字超")
        print(f"[判定] {reason}(不合格) だが修正上限{config.MAX_REVISIONS}回に到達 → 確定へ")
        return "end"
    parts = []
    if score < config.PASS_TOTAL:
        parts.append(f"{score}点 < {config.PASS_TOTAL}点")
    if not e.length_ok:
        parts.append("140字超")
    print(f"[判定] {' かつ '.join(parts)} → 書き直しへ (修正{state['revisions']}/{config.MAX_REVISIONS})")
    return "revise"