import streamlit as st
from google import genai
import pandas as pd
from PIL import Image
import json
import re

# 1. アプリのタイトル設定
st.title("🎁 ギフト集計・箱空け最適化 ツール")
st.write("スクショからギフト状況を読み取り、選択した箱レベルに応じたパターン別の最適解を算出します。")
st.write("📊 パターンA：期限が近いものを優先して消費します。")
st.write("📊 パターンB：期限を気にせず、ロスを最小限にする効率的な組み合わせです。")
st.write("📊 パターンC：2日以内に切れてしまうギフトを特に優先して消費します。")
st.write("📊 パターンD：細かいギフトやマスタ外の星粒ギフトも含めた総合的な最適解です。")

# 2. APIキーの設定（サイドバー）
st.sidebar.header("⚙️ 設定")
api_key = st.sidebar.text_input("Gemini APIキーを入力", type="password")

# ①〜⑩の固定マスター定義
MASTER_GIFTS = [
    {"id": 1, "name": "ウサギ風船", "star": 200},
    {"id": 2, "name": "月の湧水", "star": 100},
    {"id": 3, "name": "愛の花", "star": 50},
    {"id": 4, "name": "虹", "star": 50},
    {"id": 5, "name": "星の瓶", "star": 38},
    {"id": 6, "name": "誓約結晶", "star": 518},
    {"id": 7, "name": "記憶結晶", "star": 308},
    {"id": 8, "name": "宝冠結晶", "star": 158},
    {"id": 9, "name": "時間結晶", "star": 50},
    {"id": 10, "name": "満月結晶", "star": 50},
]

# ポイントギフトの除外マスタ
EXCLUDE_POINT_GIFTS = [
    "花菖蒲",
    "ばら",
    "アジサイ",
    "デイジー",
    "夢世界の鍵",
    "ももソーダ",
    "プリンプリン",
    "宇宙の祝福",
    "Starry Sky",
    "Starry Rose"
]

# 箱レベルごとの必要人気度定義
BOX_POPULARITY_MAP = {
    5: 15000,
    6: 45000,
    7: 75000,
    8: 115000
}

# 3. 画像の複数枚アップロード機能
uploaded_files = st.file_uploader(
    "スクリーンショットを選択してください（複数選択可）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

# セッション状態の初期化
if "raw_inventory" not in st.session_state:
    st.session_state.raw_inventory = None

if "unknown_gifts_input" not in st.session_state:
    st.session_state.unknown_gifts_input = {}

if uploaded_files:
    st.success(f"{len(uploaded_files)}枚の画像がアップロードされました！")
    
    with st.expander("📸 アップロード画像一覧"):
        for i, file in enumerate(uploaded_files):
            st.image(file, caption=f"{i+1}番目: {file.name}", width=200)

    # 最初に画像を解析して在庫を読み込むボタン
    if st.button("📥 画像から在庫を読み込む"):
        if not api_key:
            st.error("サイドバーに Gemini APIキーを入力してください。")
        else:
            try:
                client = genai.Client(api_key=api_key)
                raw_inventory = {}
                progress_bar = st.progress(0)
                status_text = st.empty()

                master_names = [mg["name"] for mg in MASTER_GIFTS]

                for i, file in enumerate(uploaded_files):
                    status_text.text(f"{i+1}/{len(uploaded_files)}枚目の画像を解析中... ({file.name})")
                    image = Image.open(file)
                    
                    prompt = f"""
                    この画像はSNSアプリ「GRAVITY」のギフト所持・受取画面のスクショです。
                    対象として探すべき主要ギフト名（これら以外にも画像に映っている星粒ギフトがあれば含めてください。ただし、以下の除外リストにあるポイントギフトは絶対に含めないでください）:
                    主要ギフト: {', '.join(master_names)}
                    除外すべきポイントギフト: {', '.join(EXCLUDE_POINT_GIFTS)}
                    
                    読み取る項目:
                    - gift_name: ギフト名
                    - total_count: 総所持数
                    - nearest_expiry: 直近で切れる日付（例: "2026-06-05" や "明日" など。ない場合は "なし"）
                    - nearest_count: その直近期限の個数（ない場合は 0）
                    
                    必ず以下のJSONフォーマットのリスト形式だけで出力してください。他の文章は一切書かないでください。
                    [
                      {{"gift_name": "ギフト名", "total_count": 0, "nearest_expiry": "日付", "nearest_count": 0}}
                    ]
                    """
                    
                    response = client.models.generate_content(
                        model='gemini-flash-latest',
                        contents=[image, prompt]
                    )
                    
                    text = response.text
                    text = re.sub(r"```json|```", "", text).strip()
                    parsed_data = json.loads(text)
                    
                    for item in parsed_data:
                        g_name = item.get("gift_name")
                        if g_name:
                            # ポイントギフトは強制除外
                            if g_name in EXCLUDE_POINT_GIFTS:
                                continue
                            
                            if g_name not in raw_inventory:
                                raw_inventory[g_name] = {
                                    "total_count": int(item.get("total_count", 0)),
                                    "nearest_expiry": item.get("nearest_expiry", "なし"),
                                    "nearest_count": int(item.get("nearest_count", 0))
                                }

                    progress_bar.progress((i + 1) / len(uploaded_files))

                status_text.text("在庫の読み込みが完了しました！")
                progress_bar.progress(100)
                st.session_state.raw_inventory = raw_inventory
                st.session_state.unknown_gifts_input = {} # リセット

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

# すでに在庫が読み込まれている場合の表示と次のステップ
if st.session_state.raw_inventory:
    st.markdown("---")
    st.subheader("📦 現在のギフト在庫一覧")
    
    master_names = [mg["name"] for mg in MASTER_GIFTS]
    raw_inventory = st.session_state.raw_inventory

    # 不明な（マスタ外かつポイントでもない）ギフトの検出
    unknown_gifts = [g_name for g_name in raw_inventory.keys() if g_name not in master_names]

    # 在庫一覧のテーブルを作成して表示（マスター分）
    inventory_rows = []
    for mg in MASTER_GIFTS:
        g_info = raw_inventory.get(mg["name"], {"total_count": 0, "nearest_expiry": "なし", "nearest_count": 0})
        inventory_rows.append({
            "ギフト名": mg["name"],
            "総所持数": g_info["total_count"],
            "直近期限": g_info["nearest_expiry"] if g_info["nearest_expiry"] != "なし" else "-",
            "直近期限の個数": g_info["nearest_count"]
        })
    df_inventory = pd.DataFrame(inventory_rows)
    st.dataframe(df_inventory, use_container_width=True)

    # 不明なギフトがある場合は追加で表示＆ヒアリング
    if unknown_gifts:
        st.markdown("---")
        st.subheader("❓ マスタ外の星粒ギフト検出")
        st.write("マスタに登録されていない新しい星粒ギフトが見つかりました。以下のギフトについて設定を行ってください。")
        st.info("※空白や数字以外が入力された場合は、今回の計算・リストから除外されます。")

        for u_name in unknown_gifts:
            u_info = raw_inventory[u_name]
            st.write(f"**ギフト名: {u_name}** (総所持数: {u_info['total_count']}個 / 直近期限: {u_info['nearest_expiry']})")
            
            user_star_input = st.text_input(
                f"1個あたり、星粒数はいくつですか？（{u_name}）",
                value=str(st.session_state.unknown_gifts_input.get(u_name, "")),
                key=f"unknown_{u_name}"
            )
            
            # 入力値を保存
            st.session_state.unknown_gifts_input[u_name] = user_star_input

    st.markdown("---")
    st.subheader("🎯 箱レベルの選択")
    box_input_raw = st.text_input("どの箱空けに参加しますか？（箱レベルを半角または全角の数字1桁で入力してください 例: 5, 6, 7, 8）", value="")

    if box_input_raw:
        # 全角数字を半角に変換
        box_input_normalized = box_input_raw.translate(str.maketrans('０１２３４５６７８９', '0123456789')).strip()
        
        if box_input_normalized.isdigit() and len(box_input_normalized) == 1:
            box_level = int(box_input_normalized)
            
            if box_level in BOX_POPULARITY_MAP:
                target_popularity = BOX_POPULARITY_MAP[box_level]
                st.success(f"箱レベル {box_level}（必要人気度: {target_popularity:,}）が選択されました。")
                
                st.write(f"箱レベル {box_level} のキラ値や人気度に到達する最適解を以下のＡ～Ｄのパターンで計算して表示します。")
                
                if st.button("🚀 最適解を計算する"):
                    try:
                        # 有効な未知ギフトの確定（星粒数が正しく入力されたもののみ採用）
                        valid_extra_gifts = []
                        for u_name in unknown_gifts:
                            val_str = st.session_state.unknown_gifts_input.get(u_name, "").strip()
                            # 全角数字を半角に置換
                            val_str_normalized = val_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                            if val_str_normalized.isdigit():
                                star_val = int(val_str_normalized)
                                if star_val > 0:
                                    u_info = raw_inventory[u_name]
                                    valid_extra_gifts.append({
                                        "name": u_name,
                                        "star": star_val,
                                        "total": u_info["total_count"],
                                        "expiry": u_info["nearest_expiry"],
                                        "nearest_count": u_info["nearest_count"]
                                    })

                        # --- 最適化ロジック (パターン A, B, C, D) ---
                        def calculate_plan(mode):
                            # ベースマスターの展開
                            plan_data = []
                            for mg in MASTER_GIFTS:
                                g_info = raw_inventory.get(mg["name"], {"total_count": 0, "nearest_expiry": "なし", "nearest_count": 0})
                                total = g_info["total_count"]
                                expiry = g_info["nearest_expiry"]
                                n_count = g_info["nearest_count"]
                                
                                plan_data.append({
                                    "name": mg["name"],
                                    "star_1": mg["star"],
                                    "kira_1": mg["star"] * 5,
                                    "pop_1": mg["star"] * 25,
                                    "total": total,
                                    "expiry": expiry,
                                    "nearest_count": n_count
                                })

                            # パターンDの場合のみ有効な未知ギフトを追加
                            if mode == 'D':
                                for eg in valid_extra_gifts:
                                    plan_data.append({
                                        "name": eg["name"],
                                        "star_1": eg["star"],
                                        "kira_1": eg["star"] * 5,
                                        "pop_1": eg["star"] * 25,
                                        "total": eg["total"],
                                        "expiry": eg["expiry"],
                                        "nearest_count": eg["nearest_count"]
                                    })

                            # モード別の有効期限処理
                            for item in plan_data:
                                expiry = item["expiry"]
                                n_count = item["nearest_count"]
                                total = item["total"]

                                if mode == 'B':
                                    item['effective_n'] = 0
                                    item['expiry_label'] = "-"
                                elif mode == 'C':
                                    if any(w in str(expiry) for w in ["今日", "明日", "2日", "24時間", "48時間", "0日", "1日"]):
                                        item['effective_n'] = min(n_count, total)
                                        item['expiry_label'] = expiry
                                    else:
                                        item['effective_n'] = 0
                                        item['expiry_label'] = expiry if expiry != "なし" else "-"
                                else: # A or D
                                    item['effective_n'] = min(n_count, total)
                                    item['expiry_label'] = expiry if expiry != "なし" else "-"

                            # 消費計算の実行
                            current_pop = 0
                            
                            # 期限優先モード (A, C, D) の場合、まず期限分を消費
                            if mode in ['A', 'C', 'D']:
                                for item in plan_data:
                                    if current_pop >= target_popularity:
                                        break
                                    take = item['effective_n']
                                    if take > 0:
                                        add_pop = take * item["pop_1"]
                                        item['consumed_nearest'] = take
                                        current_pop += add_pop
                                    else:
                                        item['consumed_nearest'] = 0
                            else:
                                for item in plan_data:
                                    item['consumed_nearest'] = 0

                            # 残りでターゲット人気度を満たす
                            for item in plan_data:
                                if current_pop >= target_popularity:
                                    break
                                
                                already_used = item['consumed_nearest']
                                remaining_stock = item["total"] - already_used
                                
                                if remaining_stock <= 0:
                                    item['consumed_other'] = 0
                                    continue
                                    
                                deficit_pop = target_popularity - current_pop
                                pop_per_one = item["pop_1"]
                                needed_count = (deficit_pop + pop_per_one - 1) // pop_per_one
                                take_other = min(needed_count, remaining_stock)
                                
                                item['consumed_other'] = take_other
                                current_pop += take_other * pop_per_one

                            # 結果テーブルの構築
                            table_rows = []
                            total_star_sum = 0
                            total_kira_sum = 0
                            total_pop_sum = 0

                            for item in plan_data:
                                c_total = item.get('consumed_nearest', 0) + item.get('consumed_other', 0)
                                if c_total <= 0 and mode != 'D': # 在庫0のものは基本表示しないがDの場合は柔軟に
                                    pass
                                
                                s_val = c_total * item["star_1"]
                                k_val = c_total * item["kira_1"]
                                p_val = c_total * item["pop_1"]

                                total_star_sum += s_val
                                total_kira_sum += k_val
                                total_pop_sum += p_val

                                table_rows.append({
                                    "ギフト名": item["name"],
                                    "投げる個数": c_total,
                                    "星粒数": s_val,
                                    "キラ値": k_val,
                                    "人気度": p_val,
                                    "有効期限": item['expiry_label'],
                                    "有効期限数": item.get('consumed_nearest', 0),
                                    "左記以外の個数": item.get('consumed_other', 0)
                                })

                            df_result = pd.DataFrame(table_rows)
                            diff_pop = total_pop_sum - target_popularity
                            
                            return {
                                "df": df_result,
                                "total_star": total_star_sum,
                                "total_kira": total_kira_sum,
                                "total_pop": total_pop_sum,
                                "target_pop": target_popularity,
                                "diff_pop": diff_pop
                            }

                        plan_a = calculate_plan('A')
                        plan_b = calculate_plan('B')
                        plan_c = calculate_plan('C')
                        plan_d = calculate_plan('D')

                        # --- 結果表示 ---
                        def display_result_block(title, desc, plan):
                            st.subheader(title)
                            st.caption(desc)
                            st.dataframe(plan["df"], use_container_width=True)
                            st.markdown(f"**【合計】 星粒数: {plan['total_star']:,} | キラ値: {plan['total_kira']:,} | 人気度: {plan['total_pop']:,}**")
                            st.markdown(f"🎯 目標人気度: {plan['target_pop']:,}")
                            
                            if plan['diff_pop'] < 0:
                                st.error(f"⚠️ 【不足しています！】目標まであと **{abs(plan['diff_pop']):,}** 人気度足りません！手持ちの在庫が不足しています。")
                            else:
                                st.markdown(f"📈 オーバー人気度: **+{plan['diff_pop']:,}**")

                        st.markdown("---")
                        display_result_block("📊 パターンA：直近期限・個数優先 消費プラン", "ロスを避け、期限が近いものを優先して消費します。", plan_a)
                        st.markdown("---")
                        display_result_block("📊 パターンB：期限無視・最少数＆最少種類 消費プラン", "期限を気にせず、オーバーを最小限にする効率的な組み合わせです。", plan_b)
                        st.markdown("---")
                        display_result_block("📊 パターンC：2日以内期限 優先 消費プラン", "48時間以内に切れてしまうギフトを特に手厚く優先して消費します。", plan_c)
                        st.markdown("---")
                        display_result_block("📊 パターンD：細かいギフト＆未知の星粒ギフト含めた総合プラン", "マスタ外の追加ギフトや細かいギフトも含めて柔軟に最適化します。", plan_d)

                    except Exception as e:
                        st.error(f"エラーが発生しました: {e}")
            else:
                st.error("⚠️ 有効な箱レベル（5, 6, 7, 8）を入力してください。")
        else:
            st.error("⚠️ 半角または全角の数字「1桁」で入力してください。")