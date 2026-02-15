import streamlit as st
import pandas as pd
import random
import folium
from streamlit_folium import st_folium
from streamlit_mic_recorder import speech_to_text

# --- ページ設定 ---
st.set_page_config(page_title="AI配車アシスタント - デモ", layout="wide")

st.title("🚛 配車最適化AIアシスタント (Prototype Ver.3)")
st.markdown("現場の状況とスタッフの相性をAIが計算し、最適なルートを可視化します。")

# --- 1. データ生成セクション ---
def generate_dummy_data():
    staff_data = [
        {"ID": "A", "名前": "佐藤(A)", "スキル": "ベテラン", "性格": "慎重・確実", "色": "red", "アイコン": "user"},
        {"ID": "B", "名前": "鈴木(B)", "スキル": "中堅", "性格": "社交的", "色": "blue", "アイコン": "user"},
        {"ID": "C", "名前": "田中(C)", "スキル": "新人", "性格": "内向的", "色": "green", "アイコン": "user-graduate"}
    ]
    # 横浜周辺のサンプル座標
    locations = [
        {"現場名": "青葉区マンション", "lat": 35.55, "lon": 139.53},
        {"現場名": "中央ビル", "lat": 35.45, "lon": 139.63},
        {"現場名": "港北倉庫", "lat": 35.52, "lon": 139.60},
        {"現場名": "緑区役所", "lat": 35.51, "lon": 139.54},
        {"現場名": "南ショッピングモール", "lat": 35.42, "lon": 139.60}
    ]
    difficulties = ["低", "中", "高(要交渉)"]
    stress_levels = ["普通", "高い(管理人が厳しい)", "低い"]
    
    site_data = []
    for loc in locations:
        site_data.append({
            "現場名": loc["現場名"],
            "緯度": loc["lat"],
            "経度": loc["lon"],
            "作業難易度": random.choice(difficulties),
            "対人ストレス": random.choice(stress_levels),
            "担当者": "未定", 
            "適合スコア": 0 
        })
    return pd.DataFrame(staff_data), pd.DataFrame(site_data)

if 'df_staff' not in st.session_state:
    st.session_state.df_staff, st.session_state.df_site = generate_dummy_data()

# --- 2. 簡易AIロジックエンジン ---
def run_optimization_logic(instruction, df_site, df_staff):
    df_site_new = df_site.copy()
    
    if "新人" in instruction or "田中" in instruction:
        df_site_new.loc[df_site_new["作業難易度"] == "低", "担当者"] = "田中(C)"
        df_site_new.loc[df_site_new["作業難易度"] != "低", "担当者"] = random.choice(["佐藤(A)", "鈴木(B)"])
        logic_comment = "新人(田中)に対し、難易度「低」かつストレス「低い」現場を優先的に割り当てました。"
    
    elif "雨" in instruction or "安全" in instruction:
        assignments = ["佐藤(A)", "鈴木(B)", "田中(C)"]
        df_site_new["担当者"] = df_site_new.apply(lambda x: random.choice(assignments), axis=1)
        logic_comment = "雨天のため、各拠点から移動距離が最短になるようルートを再計算しました。"
    
    else:
        df_site_new.loc[df_site_new["作業難易度"] == "高(要交渉)", "担当者"] = "佐藤(A)"
        remaining = df_site_new[df_site_new["担当者"] == "未定"].index
        # 未定があれば埋める（初期状態からの更新時など）
        for i in df_site_new.index:
             if df_site_new.at[i, "担当者"] == "未定":
                  df_site_new.at[i, "担当者"] = random.choice(["佐藤(A)", "鈴木(B)", "田中(C)"])

        logic_comment = "スキルレベルと現場難易度のマッチングを最適化しました。"

    # スコア計算
    for index, row in df_site_new.iterrows():
        base_score = random.randint(75, 95)
        if row["担当者"] == "佐藤(A)" and row["作業難易度"] == "高(要交渉)":
            base_score = 98 
        if row["担当者"] == "田中(C)" and row["作業難易度"] == "高(要交渉)":
            base_score = 40 
        df_site_new.at[index, "適合スコア"] = base_score

    return df_site_new, logic_comment

# --- 3. 可視化機能 ---
def render_map(df_site, df_staff):
    center_lat = df_site["緯度"].mean()
    center_lon = df_site["経度"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    color_map = {row["名前"]: row["色"] for _, row in df_staff.iterrows()}

    for _, row in df_site.iterrows():
        assignee = row["担当者"]
        color = color_map.get(assignee, "gray")
        if assignee == "未定": color = "gray"
        
        folium.Marker(
            [row["緯度"], row["経度"]],
            popup=f"{row['現場名']}: {assignee}",
            tooltip=f"{row['現場名']}({assignee})",
            icon=folium.Icon(color=color, icon="wrench", prefix="fa")
        ).add_to(m)
    return m

# --- 4. UI構築：地図エリア (ここを常時表示に変更) ---
st.divider()
st.subheader("🗺️ リアルタイム配車状況")
col_map, col_data = st.columns([3, 2])

with col_map:
    # 現在のセッションステートにあるデータで地図を描画
    map_obj = render_map(st.session_state.df_site, st.session_state.df_staff)
    # returned_objects=[] を指定することで、地図操作によるリロードループを防ぎます
    st_folium(map_obj, height=350, width="100%", returned_objects=[])

with col_data:
    st.markdown("**▼ 現在の担当割り当て**")
    for _, row in st.session_state.df_site.iterrows():
        score = int(row["適合スコア"]) if row["担当者"] != "未定" else 0
        assignee = row["担当者"]
        
        # スコアバーの表示
        if assignee != "未定":
             st.write(f"**{row['現場名']}** → {assignee}")
             color = "red" if score < 60 else "green"
             st.progress(score / 100, text=f"適合率: {score}%")
        else:
             st.write(f"**{row['現場名']}** → (未割当)")

# --- サイドバー設定 ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1995/1995493.png", width=100)
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    st.divider()
    st.write("**凡例 (担当カラー)**")
    st.markdown("🔴 **佐藤(ベテラン)**")
    st.markdown("🔵 **鈴木(中堅)**")
    st.markdown("🟢 **田中(新人)**")
    if st.button("🔄 データをリセット"):
        st.session_state.df_staff, st.session_state.df_site = generate_dummy_data()
        st.rerun()

# --- チャットインターフェース ---
st.divider()
st.subheader("💬 AIへの指示")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "配置条件を指示してください。「雨だから安全優先で」「新人をケアして」などが可能です。"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 入力エリア
col_btn1, col_btn2, col_btn3 = st.columns(3)
user_input = None

with col_btn1:
    if st.button("☔️ 雨天・安全重視"):
        user_input = "雨なので移動距離を短く、安全優先で。"
with col_btn2:
    if st.button("🔰 新人(田中)ケア"):
        user_input = "田中くんは新人だから、簡単な現場だけ割り当てて。"
with col_btn3:
    if st.button("⚡️ トラブル対応"):
        user_input = "佐藤さんが急なクレーム対応で1件行けなくなった。調整して。"

audio_text = speech_to_text(language='ja', start_prompt="🎙 音声入力開始", stop_prompt="終了", just_once=True, key="rec")
if audio_text:
    user_input = audio_text

chat_input_text = st.chat_input("指示を入力...")
if chat_input_text:
    user_input = chat_input_text

# --- 実行ロジック ---
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 計算処理
    df_optimized, logic_comment = run_optimization_logic(
        user_input, st.session_state.df_site, st.session_state.df_staff
    )
    
    # LLM解説生成
    response_text = ""
    if not openai_api_key:
        response_text = f"模擬回答: 指示を受け、「{logic_comment}」という方針で再配置しました。（上の地図が更新されました）"
    else:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            prompt = f"配車担当者として、次の変更内容を短く報告して: {logic_comment}"
            res = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = res.choices[0].message.content
        except:
            response_text = f"再配置しました: {logic_comment}"

    # データの更新と履歴保存
    st.session_state.df_site = df_optimized
    st.session_state.messages.append({"role": "assistant", "content": response_text})
    
    # 最後にリランして、上の地図を最新状態に書き換える
    st.rerun()
