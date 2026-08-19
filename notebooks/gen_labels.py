"""学習データ(labels.jsonl)を生成する。
各行: {"text","hook","specificity","clarity","relatability","binary"}

スコア基準(scoring_rubric.md 準拠):
  hook        : 冒頭がスクロールを止める力（逆説・問い・衝撃の事実=5 / 名乗り開始=1）
  specificity : 数字・固有の体験・情景（数字+具体的前後=5 / 抽象的機能説明=1-2）
  clarity     : 1メッセージに絞られ迷わず読める（1つの主張=5 / メタ文・散らかり=1）
  relatability: 読者(個人開発者)の悩み・感情に刺さる（直接的な痛み=5 / 発信者視点だけ=1）
  binary      : 自分なら投稿する/伸びそう=1、そうでない=0
"""
import json

# ── プロダクト定義 ──────────────────────────────────────────────────────────
# g1_spec: G1テンプレでのspecificity（featに具体的な数字や動詞があるか）
# g4_spec: G4テンプレでのspecificity（struggleの具体度）
P = [
    dict(name="FocusFlow", domain="タスク管理", feat="起動0.5秒", benefit="開いた瞬間に書ける",
         pain="多機能ツールに疲れる", before="通知に振り回されていた", change="通知を1日1回にした",
         n=12, result="毎日開くようになった", struggle="機能を削る判断ができなかった",
         lesson="削るのは足すより難しい", detail="キーボードだけで完結",
         f1="起動0.5秒", f2="キーボード完結", f3="通知1日1回",
         g1_spec=5, g4_spec=4),

    dict(name="QuickNote", domain="メモ", feat="3タップで記録", benefit="思いついた瞬間を逃さない",
         pain="メモアプリを開くのが面倒", before="紙とアプリが散らばっていた", change="入口を1つに絞った",
         n=8, result="記録が続くようになった", struggle="同期の実装で1週間溶かした",
         lesson="まず自分が毎日使うか", detail="オフラインでも書ける",
         f1="3タップ記録", f2="オフライン対応", f3="全文検索",
         g1_spec=5, g4_spec=5),  # "1週間" は具体的

    dict(name="SlimHabit", domain="習慣化", feat="1日10秒で記録", benefit="続く仕組みになった",
         pain="習慣が三日坊主になる", before="アプリが多機能すぎて挫折", change="記録を1タップにした",
         n=15, result="30日続いた", struggle="ゲーミフィケーションを盛りすぎた",
         lesson="機能より摩擦をなくす", detail="ストリーク表示だけ",
         f1="1タップ記録", f2="ストリーク", f3="リマインド",
         g1_spec=5, g4_spec=4),

    dict(name="CodeSnap", domain="コード共有", feat="貼るだけ3秒", benefit="URLがすぐ出る",
         pain="コードの共有が地味に面倒", before="Gistを毎回開いていた", change="貼るだけにした",
         n=5, result="共有が一瞬になった", struggle="シンタックスハイライトで沼った",
         lesson="コア体験だけ磨く", detail="言語自動判定",
         f1="3秒共有", f2="言語自動判定", f3="有効期限設定",
         g1_spec=5, g4_spec=4),

    dict(name="BudgetZero", domain="家計簿", feat="レシート撮影1秒", benefit="入力の手間が消えた",
         pain="家計簿が続かない", before="手入力が面倒で放置", change="撮るだけにした",
         n=20, result="3ヶ月続いた", struggle="OCRの精度に苦しんだ",
         lesson="完璧より続けやすさ", detail="週次で自動集計",
         f1="レシート撮影", f2="自動集計", f3="予算アラート",
         g1_spec=5, g4_spec=4),

    dict(name="ReadLater", domain="読書管理", feat="オフライン完全対応", benefit="電波がなくても読める",
         pain="積読が消化できない", before="タブを開きっぱなしだった", change="1画面にまとめた",
         n=3, result="消化率が上がった", struggle="同期の競合解決が難しかった",
         lesson="使う場面から逆算する", detail="読了時間の予測",
         f1="オフライン保存", f2="読了予測", f3="タグ整理",
         g1_spec=4, g4_spec=4),  # "オフライン対応"は数字なし

    dict(name="MoodLog", domain="気分記録", feat="1日10秒", benefit="振り返りが習慣になった",
         pain="自分の状態が分からない", before="日記が続かなかった", change="絵文字1タップにした",
         n=10, result="毎晩続くようになった", struggle="グラフを作り込みすぎた",
         lesson="入力の軽さが全て", detail="週の推移をグラフ化",
         f1="1タップ記録", f2="推移グラフ", f3="振り返り通知",
         g1_spec=5, g4_spec=4),

    dict(name="TinyCRM", domain="顧客管理", feat="項目を12個に絞った", benefit="迷わず入力できる",
         pain="CRMが重くて使わなくなる", before="Excelで管理して破綻した", change="項目を絞った",
         n=30, result="毎日入力するようになった", struggle="機能要望に流されかけた",
         lesson="足すより絞る勇気", detail="次アクションだけ強調",
         f1="12項目のみ", f2="次アクション表示", f3="CSV出力",
         g1_spec=5, g4_spec=3),  # "流されかけた" は抽象的

    dict(name="DevTimer", domain="作業計測", feat="ショートカット完結", benefit="計測を意識せず使える",
         pain="作業時間が見えない", before="ストップウォッチを忘れる", change="自動で計測にした",
         n=7, result="1日の内訳が見えた", struggle="バックグラウンド計測でバグった",
         lesson="意識させない設計", detail="日次で内訳表示",
         f1="自動計測", f2="ショートカット", f3="日次レポート",
         g1_spec=4, g4_spec=5),  # "バグった" は具体的なエラー体験

    dict(name="PlantCare", domain="植物管理", feat="水やり通知が的確", benefit="枯らさなくなった",
         pain="植物をよく枯らす", before="水やりを忘れていた", change="種類別の通知にした",
         n=4, result="半年枯らしていない", struggle="種類ごとの周期データ集めが大変",
         lesson="1つの困りごとに集中", detail="日照メモも残せる",
         f1="種類別通知", f2="日照メモ", f3="成長記録",
         g1_spec=3, g4_spec=4),  # "的確" は定性的

    dict(name="MealPlan", domain="献立", feat="冷蔵庫から自動提案", benefit="献立を考えなくていい",
         pain="毎日の献立がしんどい", before="毎晩スーパーで悩んでいた", change="在庫から提案にした",
         n=25, result="悩む時間がゼロになった", struggle="レシピDBの整備が重かった",
         lesson="面倒の一番濃い所を狙う", detail="買い物リストも生成",
         f1="在庫から提案", f2="買い物リスト", f3="栄養バランス",
         g1_spec=4, g4_spec=4),

    dict(name="SleepTrack", domain="睡眠", feat="起きるだけで記録", benefit="つけ忘れがなくなった",
         pain="睡眠リズムが乱れる", before="記録が続かなかった", change="操作をゼロにした",
         n=6, result="リズムが整ってきた", struggle="端末センサーの扱いに苦戦",
         lesson="操作ゼロが最強", detail="週の平均を表示",
         f1="自動記録", f2="週平均", f3="就寝リマインド",
         g1_spec=4, g4_spec=4),
]

# ── アーキタイプ定義 ─────────────────────────────────────────────────────────
# スコアの根拠:
#
# G1 `{pain}——そんな経験ありませんか？〜だから{name}を作った。{feat}、{benefit}。`
#   hook=4: 問いかけ形式は強いが「そんな経験ありませんか?」はやや定型句
#   specificity: プロダクトの feat 具体度による（g1_spec）
#   clarity=4: 3要素(痛み→商品→機能+効果)が詰まっており、5ではなく4
#   relatability=5: 「僕もそうでした」で共感を最大化
#
# G2 `前は{before}。{name}を作って{feat}になった。変えたのは{change}だけ。`
#   hook=4: before状態から入る、良いが疑問文ほど強くない
#   specificity=5: before/after + 「変えたのは〜だけ」で非常に具体的
#   clarity=5: 3拍子の流れが完全にクリーン
#   relatability=4: before状態は共感できるが感情への直撃度はG1より低い
#
# G3 `「機能は多いほど良い」は嘘だった。{name}は機能を{n}個削って〜`
#   hook=5: 逆説的な引用開始は最強クラス
#   specificity=5: 具体的な数字({n}個) + 結果がある
#   clarity=5: 主張→証拠→教訓の3拍子が完璧
#   relatability=4: 開発者の思い込みに刺さるが全員ではない
#
# G4 `{name}開発でつまずいた。{struggle}。〜学んだのは「{lesson}」。`
#   hook=4: 失敗談は引きが強いが「開発でつまずいた」は定型句
#   specificity: struggle の具体度による（g4_spec）
#   clarity=4: クリアだが「同じ個人開発者に届け」が蛇足感
#   relatability=5: 開発者の失敗談は最も共感を呼ぶ
#
# M1 `{name}は{feat}の{domain}アプリです。{detail}も地味に便利。`
#   hook=2: 商品名からの開始、やや引きがある末尾だけマシ
#   specificity=3: 機能説明はあるが文脈なし（なぜ必要かが不明）
#   clarity=4: 極めてクリア（ただし空疎）
#   relatability=1: 発信者の「自分のアプリ」視点だけで読者感情に触れない
#
# M2 `{pain}——それ、しんどいですよね。{name}でその悩みが少しでも減らせたら〜`
#   hook=3: 痛みで始まるが「少しでも減らせたら」で失速
#   specificity=1: 解決策が一切具体的でない
#   clarity=3: 痛みは明確だが解決策が曖昧
#   relatability=4: 痛みへの共感は高い
#
# B1 `{name}というアプリを作りました。{domain}に特化したシンプルなアプリです。ぜひ〜`
#   hook=1: 「作りました」以下の最悪の開始
#   specificity=1: 内容が何もない
#   clarity=3: 空っぽだが文章は通じる
#   relatability=1: 読者の感情に一切触れない
#
# B2 `{name}の特徴：{f1}、{f2}、{f3}。{domain}がもっと捗ります。`
#   hook=2: 機能リストは説明的、引きは弱い
#   specificity=3: 3つの機能名はあるが文脈・体験がない
#   clarity=4: リスト形式で整理されている
#   relatability=1: 読者の感情に一切触れない

ARCHETYPES = [
    ("G1", lambda p: (
        f"{p['pain']}——そんな経験ありませんか？僕もそうでした。だから{p['name']}を作った。{p['feat']}、{p['benefit']}。#個人開発",
        dict(hook=4, specificity=p["g1_spec"], clarity=4, relatability=5, binary=1))),

    ("G2", lambda p: (
        f"前は{p['before']}。{p['name']}を作って{p['feat']}になった。変えたのは{p['change']}だけ。#buildinpublic",
        dict(hook=4, specificity=5, clarity=5, relatability=4, binary=1))),

    ("G3", lambda p: (
        f"「機能は多いほど良い」は嘘だった。{p['name']}は機能を{p['n']}個削って、逆に{p['result']}。削るのは足すより難しい。",
        dict(hook=5, specificity=5, clarity=5, relatability=4, binary=1))),

    ("G4", lambda p: (
        f"{p['name']}開発でつまずいた。{p['struggle']}。何日も悩んで学んだのは「{p['lesson']}」。同じ個人開発者に届け。",
        dict(hook=4, specificity=p["g4_spec"], clarity=4, relatability=5, binary=1))),

    ("M1", lambda p: (
        f"{p['name']}は{p['feat']}の{p['domain']}アプリです。{p['detail']}も地味に便利。",
        dict(hook=2, specificity=3, clarity=4, relatability=1, binary=0))),

    ("M2", lambda p: (
        f"{p['pain']}——それ、しんどいですよね。{p['name']}でその悩みが少しでも減らせたらと思って作っています。",
        dict(hook=3, specificity=1, clarity=3, relatability=4, binary=0))),

    ("B1", lambda p: (
        f"{p['name']}というアプリを作りました。{p['domain']}に特化したシンプルなアプリです。ぜひ使ってみてください。",
        dict(hook=1, specificity=1, clarity=3, relatability=1, binary=0))),

    ("B2", lambda p: (
        f"{p['name']}の特徴：{p['f1']}、{p['f2']}、{p['f3']}。{p['domain']}がもっと捗ります。使ってみてね。",
        dict(hook=2, specificity=3, clarity=4, relatability=1, binary=0))),
]

rows = []
for name, fn in ARCHETYPES:
    for p in P:
        text, labels = fn(p)
        rows.append({"text": text, **labels})

# ── 手作り例 20件 ────────────────────────────────────────────────────────────
# テンプレでは再現しにくいニュアンスと点数のばらつきを追加する。
# good 10件: hook/specificity/relatabilityの組み合わせを変えた良い投稿
# bad  10件: 各軸の典型的な失敗パターン

HANDCRAFTED = [
    # ── good ──
    # G: hook強+specificity高+全軸高（最良パターン）
    dict(text="「マーケティングは後からでいい」を信じて3本のアプリを消した。誰にも届かないまま。だから今は最初の1人を見つけることから始めている。",
         hook=5, specificity=4, clarity=5, relatability=5, binary=1),

    # G: 逆説+数字（G3派生だが独自）
    dict(text="翌朝デプロイ→0ダウンロード→放置。この流れを3回繰り返してやっと学んだ。『出す前に届ける準備をする』こと。",
         hook=5, specificity=5, clarity=5, relatability=5, binary=1),

    # G: 問い+自己開示（hook強・specificity低め）
    dict(text="コードは書けるのにXの投稿は1文字も進まない。怖いのは批評じゃなくて無視されることだと気づいた。",
         hook=5, specificity=3, clarity=5, relatability=5, binary=1),

    # G: 具体的な before/after +感情（個人エピソード型）
    dict(text="毎晩スーパーで「今日何作ろう」と20分悩んでいた。年間120時間。MealPlanを作ってゼロになった。",
         hook=4, specificity=5, clarity=5, relatability=5, binary=1),

    # G: 問い+解答の2拍子（短くてパンチあり）
    dict(text="個人開発でAppStoreに出しても誰も気づかない。告知ゼロのリリースは、森の中で叫ぶのと同じだった。",
         hook=5, specificity=3, clarity=5, relatability=5, binary=1),

    # G: 具体的な比較+洞察
    dict(text="3日で作ったプロトタイプが、3ヶ月かけたプロダクトより反応が良かった。完成度より『刺さるかどうか』が先だと気づいた。",
         hook=5, specificity=4, clarity=5, relatability=5, binary=1),

    # G: 問題の発見+具体的な解決（hook=4・まとまり良）
    dict(text="習慣化アプリを作って分かった。一番の摩擦は記録じゃなくてアプリを開くことだった。SlimHabitは1タップにして摩擦だけ消した。",
         hook=4, specificity=4, clarity=5, relatability=5, binary=1),

    # G: 感情的な告白（hook高・specificity低め・relatability最高）
    dict(text="「良いものを作ったのに誰にも知られず終わる」…この悔しさ、個人開発者なら分かるはず。だから作った。届けるところまでを、あきらめない。",
         hook=5, specificity=2, clarity=5, relatability=5, binary=1),

    # G: before/after+数字（明確な定量効果）
    dict(text="タスク管理ツールを5個乗り換えた。問題はツールじゃなくて『開くコスト』だった。FocusFlowは起動0.5秒にしてその問題だけ解いた。",
         hook=4, specificity=5, clarity=5, relatability=5, binary=1),

    # G: OCR開発+妻の反応（specificity=5・感情あり）
    dict(text="レシートを撮るだけで家計簿が付く——作るのに3週間かかったけど、妻が『続けられる』と言ってくれた。OCR精度との格闘は、その一言で報われた。",
         hook=4, specificity=5, clarity=5, relatability=4, binary=1),

    # ── bad ──
    # B: バージョンアップ告知（hook=1・情報ゼロ）
    dict(text="SlimHabitをアップデートしました。バグ修正と機能改善を行いました。よろしくお願いします。",
         hook=1, specificity=2, clarity=4, relatability=1, binary=0),

    # B: 同調圧力型（具体性ゼロ・感情だけ）
    dict(text="個人開発者の皆さん、日々の開発お疲れ様です。私もコツコツ頑張っています。一緒に頑張りましょう！",
         hook=1, specificity=1, clarity=3, relatability=2, binary=0),

    # B: 機能の羅列+clarity低（3つの文脈なし説明）
    dict(text="MoodLogは気分記録アプリです。毎日の気分を記録することで自己理解が深まり、週次での振り返りも可能で、メンタルヘルスの改善にも役立ちます。",
         hook=1, specificity=3, clarity=2, relatability=2, binary=0),

    # B: 一般論（フック・具体性・共感がすべて欠如）
    dict(text="良いアプリを作るためには、ユーザーのことを考えることが大切です。日々の努力を積み重ねていきたいと思います。",
         hook=1, specificity=1, clarity=3, relatability=1, binary=0),

    # B: ダウンロードお願い型（最も典型的な悪手）
    dict(text="CodeSnapというコード共有ツールを作りました。エンジニアの皆さんに使ってもらえると嬉しいです。よろしくお願いします！",
         hook=1, specificity=2, clarity=3, relatability=1, binary=0),

    # B: 痛みはあるが解決策が完全に曖昧
    dict(text="植物を育てるのって難しいですよね。PlantCareはそんな悩みを解決するアプリです。詳しくはプロフのリンクから。",
         hook=2, specificity=1, clarity=3, relatability=3, binary=0),

    # B: メタ文（clarity=1の典型。モデルが生成したような前置き）
    dict(text="はい、承知いたしました。以下に投稿案を作成します。FocusFlowはタスク管理アプリで、色々な機能があって便利で、ぜひ使ってほしいと思っていて、あと通知もあります。",
         hook=1, specificity=2, clarity=1, relatability=1, binary=0),

    # B: 散らかった長文（clarity=1・要素が多すぎ）
    dict(text="えー、今日はですね、私が作ったQuickNoteというアプリについて、まあ色々あるんですけど、とにかくメモができて、あと検索もできて、それで、うーん、まあ使ってみてください、はい。",
         hook=1, specificity=2, clarity=1, relatability=1, binary=0),

    # B: 悩み打ち明けだけ（アクションなし・specificity=1）
    dict(text="最近はマーケティングの重要性を感じています。まだ模索中ですが、何かアドバイスがあればぜひ教えてください。",
         hook=1, specificity=1, clarity=3, relatability=2, binary=0),

    # B: ダウンロードが伸びない系（フック=1、共感を求めているが共感できない）
    dict(text="先週リリースしたReadLaterですが、まだダウンロードが少ないです。もし良ければ試してみてください。フィードバックも歓迎です。",
         hook=1, specificity=2, clarity=3, relatability=1, binary=0),
]

rows.extend(HANDCRAFTED)

# ── 書き出し ─────────────────────────────────────────────────────────────────
OUT = "/Users/riki/dev/marketing_agent/notebooks/labels.jsonl"
with open(OUT, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ── サマリ ────────────────────────────────────────────────────────────────────
import statistics as st
n = len(rows)
good = sum(1 for r in rows if r["binary"] == 1)
print(f"生成: {n}件 (good {good} / bad {n-good})")
for ax in ["hook", "specificity", "clarity", "relatability"]:
    vals = [r[ax] for r in rows]
    print(f"  {ax:12}: 平均{st.mean(vals):.2f}  分散{st.variance(vals):.2f}  min{min(vals)} max{max(vals)}")

print("\n--- アーキタイプ別サマリ ---")
for arch_name, _ in ARCHETYPES:
    sub = [r for r in rows[:len(ARCHETYPES)*len(P)]
           if rows.index(r) % len(P) == 0 or True]  # 全行を見る
arch_rows = rows[:len(ARCHETYPES) * len(P)]
for ai, (arch_name, _) in enumerate(ARCHETYPES):
    sub = arch_rows[ai*len(P):(ai+1)*len(P)]
    scores = {ax: round(st.mean(r[ax] for r in sub), 1) for ax in ["hook","specificity","clarity","relatability"]}
    b = sum(r["binary"] for r in sub)
    print(f"  {arch_name}: hook={scores['hook']} spec={scores['specificity']} clar={scores['clarity']} rel={scores['relatability']} binary={b}/{len(P)}")

print("\n--- サンプル3件 ---")
for r in [rows[0], rows[48], rows[-1]]:
    print(json.dumps(r, ensure_ascii=False))
