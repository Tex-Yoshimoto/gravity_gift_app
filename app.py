import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import json
import re

# 1. アプリのタイトル設定
st.title("🎁 GRAVITY ギフト最適化・集計ツール")
st.write("スクショからギフト状況を読み取り、目標人気度（15,000）に向けたパターン別（A・B・C）の最適解を算出します。")

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

# 3. 画像の複数枚アップロード機能
uploaded_files = st.file_uploader(
    "スクリーンショットを選択してください（複数選択可）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"{len(uploaded_files)}枚の画像がアップロードされました！")
    
    with st.expander("📸 アップロード画像一覧"):
        for i, file in enumerate(uploaded_files):
            st.image(file, caption=f"{i+1}番目: {file.name}", width=200)

    if st.button("🚀 最適解を計算する"):
        if not api_key:
            st.error("サイドバーに Gemini APIキーを入力してください。")
        else:
            try:
                # 安定版のAPI設定
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash-latest')
                
                raw_inventory = {}
                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, file in enumerate(uploaded_files):
                    status_text.text(f"{i+1}/{len(uploaded_files)}枚目の画像を解析中... ({file.name})")
                    image = Image.open(file)
                    
                    prompt = """
                    この画像はSNSアプリ「GRAVITY」のギフト所持・受取画面のスクショです。
                    対象ギフト名: ウサギ風船, 月の湧水, 愛の花, 虹, 星の瓶, 誓約結晶, 記憶結晶, 宝冠結晶, 時間結晶, 満月結晶
                    
                    読み取る項目:
                    - gift_name: ギフト名
                    - total_count: 総所持数
                    - nearest_expiry: 直近で切れる日付（例: "2026-06-05" や "明日" など。ない場合は "なし"）
                    - nearest_count: その直近期限の個数（ない場合は 0）
                    
                    必ず以下のJSONフォーマットのリスト形式だけで出力してください。他の文章は一切書かないでください。
                    [
                      {"gift_name": "ギフト名", "total_count": 0, "nearest_expiry": "日付", "nearest_count": 0}
                    ]
                    """
                    
                    response = model.generate_content([image, prompt])
                    
                    text = response.text
                    text = re.sub(r"```json|```", "", text).strip()
                    parsed_data = json.loads(text)
                    
                    for item in parsed_data:
                        g_name = item.get("gift_name")
                        if g_name:
                            if g_name not in raw_inventory:
                                raw_inventory[g_name] = {
                                    "total_count": int(item.get("total_count", 0)),
                                    "nearest_expiry": item.get("nearest_expiry", "なし"),
                                    "nearest_count": int(item.get("nearest_count", 0))
                                }

                    progress_bar.progress((i + 1) / len(uploaded_files))

                status_text.text("最適化計算を実行中...")

                # --- 5. 最適化ロジック (パターン A, B, C) ---
                TARGET_POPULARITY = 15000

                def calculate_plan(mode):
                    plan_data = []
                    for mg in MASTER_GIFTS:
                        g_info = raw_inventory.get(mg["name"], {"total_count": 0, "nearest_expiry": "なし", "nearest_count": 0})
                        total = g_info["total_count"]
                        expiry = g_info["nearest_expiry"]
                        n_count = g_info["nearest_count"]
                        
                        if mode == 'B':
                            effective_n_count = 0
                            expiry_label = "-"
                        elif mode == 'C':
                            if any(w in str(expiry) for w in ["今日", "明日", "2日", "24時間", "48時間", "0日", "1日"]):
                                effective_n_count = min(n_count, total)
                                expiry_label = expiry
                            else:
                                effective_n_count = 0
                                expiry_label = expiry if expiry != "なし" else "-"
                        else:
                            effective_n_count = min(n_count, total)
                            expiry_label = expiry if expiry != "なし" else "-"

                        plan_data.append({
                            "name": mg["name"],
                            "star_1": mg["star"],
                            "kira_1": mg["star"] * 5,
                            "pop_1": mg["star"] * 25,
                            "total": total,
                            "expiry": expiry_label,
                            "nearest_count": effective_n_count,
                            "other_count": 0,
                            "consumed_total": 0
                        })

                    current_pop = 0
                    
                    if mode in ['A', 'C']:
                        for item in plan_data:
                            if current_pop >= TARGET_POPULARITY:
                                break
                            take = min(item["nearest_count"], item["total"])
                            if take > 0:
                                add_pop = take * item["pop_1"]
                                item["nearest_count"] = take
                                current_pop += add_pop

                    for item in plan_data:
                        if current_pop >= TARGET_POPULARITY:
                            break
                        
                        already_used = item["nearest_count"]
                        remaining_stock = item["total"] - already_used
                        
                        if remaining_stock <= 0:
                            continue
                            
                        deficit_pop = TARGET_POPULARITY - current_pop
                        pop_per_one = item["pop_1"]
                        needed_count = (deficit_pop + pop_per_one - 1) // pop_per_one
                        take_other = min(needed_count, remaining_stock)
                        
                        item["other_count"] = take_other
                        current_pop += take_other * pop_per_one

                    table_rows = []
                    total_star_sum = 0
                    total_kira_sum = 0
                    total_pop_sum = 0

                    for item in plan_data:
                        c_total = item["nearest_count"] + item["other_count"]
                        s_val = c_total * item["star_1"]
                        k_val = c_total * item["kira_1"]
                        p_val = c_total * item["pop_1"]

                        total_star_sum += s_val
                        total_kira_sum += k_val
                        total_pop_sum += p_val

                        table_rows.append({
                            "ギフト名": item["name"],
                            "期限": item["expiry"],
                            "その期限の個数": item["nearest_count"],
                            "それ以外に消費する個数": item["other_count"],
                            "今回消費する個数": c_total,
                            "星粒数": s_val,
                            "キラ値": k_val,
                            "人気度": p_val
                        })

                    df_result = pd.DataFrame(table_rows)
                    diff_pop = total_pop_sum - TARGET_POPULARITY
                    
                    return {
                        "df": df_result,
                        "total_star": total_star_sum,
                        "total_kira": total_kira_sum,
                        "total_pop": total_pop_sum,
                        "target_pop": TARGET_POPULARITY,
                        "diff_pop": diff_pop
                    }

                plan_a = calculate_plan('A')
                plan_b = calculate_plan('B')
                plan_c = calculate_plan('C')

                status_text.text("計算が完了しました！")
                progress_bar.progress(100)

                # --- 6. 結果表示 ---
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

                display_result_block("📊 パターンA：直近期限・個数優先 消費プラン", "ロスを避け、期限が近いものを優先して消費します。", plan_a)
                st.markdown("---")
                display_result_block("📊 パターンB：期限無視・最少数＆最少種類 消費プラン", "期限を気にせず、オーバーを最小限にする効率的な組み合わせです。", plan_b)
                st.markdown("---")
                display_result_block("📊 パターンC：2日以内期限 優先 消費プラン", "48時間以内に切れてしまうギフトを特に手厚く優先して消費します。", plan_c)

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")