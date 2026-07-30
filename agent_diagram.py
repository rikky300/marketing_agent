"""AIエージェント部署の設計図。

Streamlit 単体で描画できるよう、外部CSSクラスに依存しないインラインSVGにしてある。
app.py からボタンで開いたときにこの HTML を components.html で表示する。
配色: 紫 = 生成AI(Gemini)を使うエージェント / グレー = 人間・検索・決定。
"""

# ── 配色（ライトテーマ基準。白背景の上に描くので暗色でも読める） ──
_PURPLE_FILL, _PURPLE_LINE, _PURPLE_TITLE, _PURPLE_SUB = "#EEEDFE", "#534AB7", "#26215C", "#534AB7"
_GRAY_FILL, _GRAY_LINE, _GRAY_TITLE, _GRAY_SUB = "#F1EFE8", "#5F5E5A", "#2C2C2A", "#5F5E5A"
_LABEL = "#5F5E5A"


def _card(x, y, w, h, title, func, action, kind):
    fill, line, tc, sc = (
        (_PURPLE_FILL, _PURPLE_LINE, _PURPLE_TITLE, _PURPLE_SUB) if kind == "ai"
        else (_GRAY_FILL, _GRAY_LINE, _GRAY_TITLE, _GRAY_SUB)
    )
    cx = x + w / 2
    return f"""
<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{line}" stroke-width="1.5"/>
<text x="{cx}" y="{y + 26}" text-anchor="middle" font-size="14" font-weight="500" fill="{tc}">{title}</text>
<text x="{cx}" y="{y + 47}" text-anchor="middle" font-size="12" fill="{sc}">{func}</text>
<text x="{cx}" y="{y + 68}" text-anchor="middle" font-size="12" fill="{sc}">{action}</text>"""


def _arrow(x1, y1, x2, y2):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{_GRAY_LINE}" stroke-width="1.5" marker-end="url(#ar)"/>')


def _label(x, y, text, anchor="start"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="12" fill="{_LABEL}">{text}</text>'


_SVG = f"""
<svg width="100%" viewBox="0 0 680 712" xmlns="http://www.w3.org/2000/svg" role="img"
     style="font-family:'Hiragino Sans','Noto Sans JP',-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;">
<title>AIエージェント部署の設計</title>
<desc>生成AIを使う草案ライターと採点担当を紫、テーマ入力・リサーチ・決定・人間の投稿をグレーで示し、
should_continue の判定で最大3回まわる採点ループを描いたワークフロー図</desc>
<defs>
  <marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="{_GRAY_LINE}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>

<rect x="270" y="18" width="140" height="32" rx="16" fill="{_GRAY_FILL}" stroke="{_GRAY_LINE}" stroke-width="1.5"/>
<text x="340" y="38" text-anchor="middle" font-size="12" fill="{_GRAY_TITLE}">テーマ入力</text>
{_arrow(340, 50, 340, 64)}

{_card(190, 66, 300, 78, "リサーチ担当", "retrieve_node", "ChromaDB をテーマで検索", "human")}
{_arrow(340, 144, 340, 174)}

{_card(190, 176, 300, 78, "草案ライター", "generate_node / revise_node", "writer(Gemini) で投稿を生成・修正", "ai")}
{_arrow(340, 254, 340, 284)}
{_label(400, 273, "書いたら採点")}

{_card(190, 286, 300, 78, "採点担当", "evaluate_node", "judge(Gemini) で採点し候補に貯める", "ai")}
{_arrow(340, 364, 340, 394)}

<rect x="240" y="396" width="200" height="34" rx="8" fill="{_GRAY_FILL}" stroke="{_GRAY_LINE}" stroke-width="1.5"/>
<text x="340" y="417" text-anchor="middle" font-size="12" fill="{_GRAY_TITLE}">should_continue（判定）</text>
{_arrow(340, 430, 340, 464)}
{_label(352, 452, "合格8点 / 上限3回")}

<path d="M240 413 L95 413 L95 215 L184 215" fill="none" stroke="{_GRAY_LINE}" stroke-width="1.5" marker-end="url(#ar)"/>
{_label(132, 266, "不合格", "middle")}
{_label(132, 284, "書き直し", "middle")}

{_card(190, 466, 300, 78, "決定担当", "finalize_node", "候補から最高 score を採用", "human")}
{_arrow(340, 544, 340, 574)}

{_card(190, 576, 300, 78, "あなた（人間）", "投稿担当", "受け取って X に投稿", "human")}

<rect x="200" y="680" width="14" height="14" rx="3" fill="{_PURPLE_FILL}" stroke="{_PURPLE_LINE}" stroke-width="1.5"/>
{_label(222, 691, "AI（生成・採点）")}
<rect x="390" y="680" width="14" height="14" rx="3" fill="{_GRAY_FILL}" stroke="{_GRAY_LINE}" stroke-width="1.5"/>
{_label(412, 691, "人間・検索・決定")}
</svg>"""

# 白背景の上に置いて、ダークテーマでも確実に読めるようにする。
DIAGRAM_HTML = f'<div style="background:#ffffff;border-radius:12px;padding:8px;">{_SVG}</div>'

# 画像ファイルの場所（app.py / README / CLAUDE から参照する）
DIAGRAM_PNG = "assets/agent_dept.png"


def _build_png():
    """SVG から PNG を書き出す。図を変えたら `python agent_diagram.py` で再生成する。
    cairosvg はここでしか使わない（ビルド専用。実行時・requirements には不要）。"""
    import os
    import cairosvg
    os.makedirs(os.path.dirname(DIAGRAM_PNG), exist_ok=True)
    cairosvg.svg2png(bytestring=_SVG.encode("utf-8"), write_to=DIAGRAM_PNG,
                     output_width=1360, output_height=1424, background_color="white")
    print(f"wrote {DIAGRAM_PNG} ({os.path.getsize(DIAGRAM_PNG)} bytes)")


if __name__ == "__main__":
    _build_png()
