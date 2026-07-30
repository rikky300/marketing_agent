"""
評価ダッシュボード（ローカル専用）。デプロイはしない。
見たいときだけ手元で実行する: streamlit run eval_app.py

生成アプリ(app.py)とは別プロセス。投稿物DB(data/posts.csv)を読んで、
judgeの妥当性・軸別ズレ・事実性・reviseループ等を評価し、一覧を編集する。
"""
import ui_common

ui_common.setup_page("AgentMark 評価（ローカル）", layout="wide", max_width="1100px")

import views_evaluate

views_evaluate.render()
