import streamlit as st
import pandas as pd
import random
import folium
from streamlit_folium import st_folium
from streamlit_mic_recorder import speech_to_text

# --- ページ設定 ---
st.set_page_config(page_title="AI配車アシスタント - デモ", layout="wide")

st.title("🚛 配車最適化AIアシスタント (Prototype Final)")
st.markdown("現場データと地図を統合し、**「最適なルート」**と**「訪問順序」**を可視化します。")

# --- 1. データ生成セクション ---
def generate_dummy_data():
    staff_data = [
        {"ID": "A", "名前": "佐藤(A)", "スキル": "ベテラン", "性格": "慎重・確実", "色": "red", "アイコン": "user"},
        {"ID": "B", "名前": "鈴木(B)", "スキル": "中堅", "性格": "社交的", "色": "blue", "アイコン": "user"},
        {"ID": "C", "名前": "田中(C)", "スキル": "新人", "性格": "内向的", "色": "green", "アイコン": "user-graduate"}
    ]
    # 事務所（横浜駅周辺）
    office = {"現場名": "🏢 事務所(出発)", "lat": 35.4658, "lon": 139.6223, "担当者": "ALL"}
    
    # 現場座標
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
            "適合スコア": 0,
            "訪問順": 0
        })
    return pd.DataFrame(staff_data), pd.DataFrame(site_data), office

# セッション初期化
if 'df_staff' not in st.session_state:
    st.session_state.df_staff, st.session_state.df_site, st.session_state.office = generate_dummy_data()

# --- 2. AIロジックエンジン ---
def run_optimization_logic(instruction, df_site, df_staff):
    df_site_new = df_site.copy()
    
    # 簡易ロジック
    if "新人" in instruction or "田中" in instruction:
        df_site_new.loc[df_site_new["作業難易度"] == "低", "担当者"] = "田中(C)"
        df_site_new.loc[df_site_new["作業難易度"] != "低", "担当者"] = random.choice(["佐藤(A)", "鈴木(B)"])
        logic_comment = "新人(田中)に対し、難易度「低」現場を優先割り当て。"
    elif "雨" in instruction or "安全" in instruction:
        assignments = ["佐藤(A)", "鈴木(B)", "田中(C)"]
        df_site_new["担当者"] = df_site_new.apply(lambda x: random.choice(assignments), axis=1)
        logic_comment = "雨天考慮：移動距離が最短になるようルート再計算済。"
    else:
        df_site_new.loc[df_site_new["作業難易度"] == "高(要交渉)", "担当者"] = "佐藤(A)"
        for i in df_site_new.index:
             if df_site_new.at[i, "担当者"] == "未定":
                  df_site_new.at[i, "担当者"] = random.choice(["佐藤(A)", "鈴木(B)", "田中(C)"])
        logic_comment = "スキルと難易度の最適マッチングを実行。"

    # スコア計算と訪問順序の付与（擬似的に付与）
    for index, row in df_site_new.iterrows():
        base_score = random.randint(75, 95)
        if row["担当者"] == "佐藤(A)" and row["作業難易度"] == "高(要交渉)": base_score = 99
        if row["担当者"] == "田中(C)" and row["作業難易度"] == "高(要交渉)": base_score = 45
        df_site_new.at[index, "適合スコア"] = base_score
    
    # 担当者ごとに簡易的な訪問順序(1,2...)を割り振る
    for name in ["佐藤(A)", "鈴木(B)", "田中(C)"]:
        mask = df_site_new["担当者"] == name
        count = df_site_new[mask].shape[0]
        if count > 0:
            # 上から順に1, 2...と振る
            df_site_new.loc[mask, "訪問順"] = range(1, count + 1)

    return df_site_new, logic_comment

# --- 3. 高度な地図可視化 (ルート線付き) ---
def render_advanced_map(df_site, df_staff, office):
    center_lat = df_site["緯度"].mean()
    center_lon = df_site["経度"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

    # 1. 事務所マーカー
    folium.Marker(
        [office["lat"], office["lon"]],
        popup="事務所(START)",
        tooltip="🏢 事務所",
        icon=folium.Icon(color="black", icon="building", prefix="fa")
    ).add_to(m)

    # 色情報の辞書化
    color_map = {row["名前"]: row["色"] for _, row in df_staff.iterrows()}

    # 2. 担当者ごとにルート線を描画
    for staff_name, color in color_map.items():
        # その担当者の現場を取得
        assigned_sites = df_site[df_site["担当者"] == staff_name].sort_values("訪問順")
        
        if len(assigned_sites) > 0:
            # ルート座標リスト: 事務所 -> 現場1 -> 現場2 -> ...
            route_coords = [[office["lat"], office["lon"]]]
            for _, site in assigned_sites.iterrows():
                route_coords.append([site["緯度"], site["経度"]])
            
            # 線を引く (PolyLine)
            folium.PolyLine(
                route_coords,
                color=color,
                weight=5,
                opacity=0.7,
                tooltip=f"{staff_name} のルート"
            ).add_to(m)

    # 3. 現場マーカー配置
    for _, row in df_site.iterrows():
        assignee = row["担当者"]
        color = color_map.get(assignee, "gray")
        if assignee == "未定": color = "gray"
        
        # 訪問順があれば表示
        order_str = f"順序{row['訪問順']}" if row['訪問順'] > 0 else "未定"
        
        folium.Marker(
            [row["緯度"], row["経度"]],
            popup=f"<b>{row['現場名']}</b><br>担当: {assignee}<br>{order_str}",
            tooltip=f"{order_str}: {row['現場名']}", # カーソル合わせると順番が出る
            icon=folium.Icon(color=color, icon="wrench", prefix="fa")
        ).add_to(m)
        
    return m

# --- 4. UI構築：地図エリア ---
st.divider()
st.subheader("🗺️ リアルタイム配車状況 & ルート")
st.caption("※線は担当者ごとの移動ルート（事務所発）を表しています。")

col_map, col_data = st.columns([3, 2])

with col_map:
    map_obj = render_advanced_map(st.session_state.df_site, st.session_state.df_staff, st.session_state.office)
    st_folium(map_obj, height=400, width="100%", returned_objects=[])

with col_data:
    st.markdown("**▼ AIスコア分析**")
    for _, row in st.session_state.df_site.iterrows():
        assignee = row["担当者"]
        if assignee != "未定":
             score = int(row["適合スコア"])
             color = "red" if score < 60 else "green"
             # 担当者名と順序を表示
             st.write(f"**{row['訪問順']}. {row['現場名']}** → {assignee}")
             st.progress(score / 100, text=f"適合率: {score}%")

# --- 5. データ参照エリア (復活機能) ---
st.write("")
with st.expander("📋 【詳細データ】要員リストと現場リストをタップして確認"):
    tab1, tab2 = st.tabs(["要員リスト (Staff)", "現場リスト (Site)"])
    with tab1:
        st.dataframe(st.session_state.df_staff, hide_index=True)
    with tab2:
        st.dataframe(st.session_state.df_site, hide_index=True)
    
    if st.button("🔄 データをリセット"):
        st.session_state.df_staff, st.session_state.df_site, _ = generate_dummy_data()
        st.rerun()

# --- サイドバー ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1995/1995493.png", width=100)
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    st.divider()
    st.write("**ルート凡例**")
    st.markdown("⬛️ **事務所 (START)**")
    st.markdown("🟥 **佐藤ルート (ベテラン)**")
    st.markdown("🟦 **鈴木ルート (中堅)**")
    st.markdown("🟩 **田中ルート (新人)**")

# --- チャットインターフェース ---
st.divider()
st.subheader("💬 AIへの指示")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "配置条件を指示してください。「雨だから安全優先で」「新人をケアして」などが可能です。"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

col_btn1, col_btn2, col_btn3 = st.columns(3)
user_input = None

with col_btn1:
    if st.button("☔️ 雨天・安全重視"): user_input = "雨なので移動距離を短く、安全優先で。"
with col_btn2:
    if st.button("🔰 新人(田中)ケア"): user_input = "田中くんは新人だから、簡単な現場だけ割り当てて。"
with col_btn3:
    if st.button("⚡️ トラブル対応"): user_input = "佐藤さんが急なクレーム対応で1件行けなくなった。調整して。"

audio_text = speech_to_text(language='ja', start_prompt="🎙 音声入力開始", stop_prompt="終了", just_once=True, key="rec")
if audio_text: user_input = audio_text

chat_input_text = st.chat_input("指示を入力...")
if chat_input_text: user_input = chat_input_text

# --- 実行ロジック ---
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    df_optimized, logic_comment = run_optimization_logic(
        user_input, st.session_state.df_site, st.session_state.df_staff
    )
    
    response_text = ""
    if not openai_api_key:
        response_text = f"模擬回答: 指示を受け、「{logic_comment}」という方針でルートを再構築しました。（地図にルート線が表示されました）"
    else:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_api_key)
            prompt = f"配車担当者として、次の変更内容を短く報告して: {logic_comment}"
            res = client.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            response_text = res.choices[0].message.content
        except:
            response_text = f"再配置しました: {logic_comment}"

    st.session_state.df_site = df_optimized
    st.session_state.messages.append({"role": "assistant", "content": response_text})
    st.rerun()
