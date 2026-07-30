"""
生成アプリ（デプロイ対象）。Xの投稿案を生成する。評価機能は含めない。
実行: streamlit run app.py
評価ダッシュボードは別アプリ eval_app.py（ローカル専用）。
"""
import ui_common

ui_common.setup_page("マーケティングAgent")

import views_generate

views_generate.render()
