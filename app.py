import streamlit as st
import pandas as pd
import random
import folium
from streamlit_folium import st_folium
from streamlit_mic_recorder import speech_to_text

# --- ページ設定 ---
st.set_page_config(page_title="AI配車アシスタント", layout="wide")
st.title("🚛 配車最適化AIアシスタント (Final Ver)")

# --- 1. データ生成と「自動修復」セクション ---
def generate_dummy_data():
    # スタッフデータ
    staff_data = [
        {"ID": "A", "名前": "佐藤(A)", "スキル": "ベテラン", "色": "red"},
        {"ID": "B", "名前": "鈴木(B)", "スキル": "中堅", "色": "blue"},
        {"ID": "C", "名前": "田中(C)", "スキル": "新人", "色": "green"}
    ]
    # 事務所（横浜駅周辺）
    office = {"現場名": "🏢 事務所(START)", "lat": 35.4658, "lon": 139.6223}
    
    # 現場データ
    locations = [
        {"現場名": "青葉区マンション", "lat": 35.55, "lon": 139.53},
        {"現場名": "中央ビル", "lat": 35.45, "lon": 139.63},
        {"現場名": "港北倉庫", "lat": 35.52, "lon": 139.60},
        {"現場名": "緑区役所", "lat": 35.51, "lon": 139.54},
        {"現場名": "南モール", "lat": 35.42, "lon": 139.60}
    ]
    
    site_data = []
    for loc in locations:
        site_data.append({
            "現場名": loc["現場名"],
            "緯度": loc["lat"],
            "経度": loc["lon"],
            "作業難易度": random.choice(["低", "中", "高"]),
            "担当者": "未定", 
            "適合スコア": 0,
            "訪問順": 0
        })
    return pd.DataFrame(staff_data), pd.DataFrame(site_data), office

# ★重要: 古いデータが残っていたら強制的にリセットする処理
if 'office' not in st.session_state or 'df_site' not in st.session_state:
    st.session_state.df_staff, st.session_state.df_site, st.session_state.office = generate_dummy_data()

# もし古いデータのせいで「訪問順」列がない場合もリセット
if "訪問順" not in st.session_state.df_site.columns:
    st.session_state.df_staff, st.session_state.df_site, st.session_state.office = generate_dummy_data()
    st.rerun()

# --- 2. AIロジック ---
def run_optimization(instruction, df_site):
    df = df_site.copy()
    # 簡易ルール
    if "新人" in instruction:
        df.loc[df["作業難易度"] == "低", "担当者"] = "田中(C)"
        df.loc[df["作業難易度"] != "低", "担当者"] = random.choice(["佐藤(A)", "鈴木(B)"])
    elif "雨" in instruction:
        df["担当者"] = df.apply(lambda x: random.choice(["佐藤(A)", "鈴木(B)", "田中(C)"]), axis=1)
    else:
        # デフォルト割り当て
        for i in df.index:
            if df.at[i, "担当者"] == "未定":
                df.at[i, "担当者"] = random.choice(["佐藤(A)", "鈴木(B)"])
    
    # 順序とスコアの付与
    for name in ["佐藤(A)", "鈴木(B)", "田中(C)"]:
        mask = df["担当者"] == name
        count = df[mask].shape[0]
        if count > 0:
            df.loc[mask, "訪問順"] = range(1, count + 1)
            # スコア適当付与
            df.loc[mask, "適合スコア"] = [random.randint(80, 100) for _ in range(count)]
            
    return df

# --- 3. 地図描画（線とツールチップ） ---
def render_map(df_site, df_staff, office):
    # 地図の中心
    m = folium.Map(location=[35.50, 139.60], zoom_start=11)
    
    # 事務所マーカー
    folium.Marker(
        [office["lat"], office["lon"]],
        tooltip="事務所 (出発地)",
        icon=folium.Icon(color="black", icon="building", prefix="fa")
    ).add_to(m)

    color_map = {row["名前"]: row["色"] for _, row in df_staff.iterrows()}

    # ルート線を描く
    for _, staff in df_staff.iterrows():
        name = staff["名前"]
        color = staff["色"]
        # その人の担当現場を取得（順番通りに）
        my_sites = df_site[df_site["担当者"] == name].sort_values("訪問順")
        
        if not my_sites.empty:
            # 座標リスト: 事務所 -> 現場1 -> 現場2...
            points = [[office["lat"], office["lon"]]]
            for _, site in my_sites.iterrows():
                points.append([site["緯度"], site["経度"]])
            
            # 線を引く
            folium.PolyLine(
                points, color=color, weight=5, opacity=0.8,
                tooltip=f"{name} のルート"
            ).add_to(m)

    # 現場マーカー
    for _, row in df_site.iterrows():
        assignee = row["担当者"]
        color = color_map.get(assignee, "gray")
        
        # ツールチップ（マウスオーバーで出る文字）
        if assignee == "未定":
            tip_text = f"{row['現場名']} (未定)"
        else:
            tip_text = f"【{row['訪問順']}番目】{row['現場名']} ({assignee})"

        folium.Marker(
            [row["緯度"], row["経度"]],
            tooltip=tip_text,  # これがマウスホバーで出ます
            icon=folium.Icon(color=color, icon="wrench", prefix="fa")
        ).add_to(m)
        
    return m

# --- 4. 画面レイアウト ---

# A. 地図エリア（最上部に配置）
st.subheader("🗺️ リアルタイム ルートマップ")
map_obj = render_map(st.session_state.df_site, st.session_state.df_staff, st.session_state.office)
st_folium(map_obj, height=350, width="100%", returned_objects=[])

# B. データ参照エリア（地図のすぐ下）
st.info("👇 以下のバーを押すと、詳細データを確認できます")
with st.expander("📋 【詳細データ】要員リスト・現場リストを見る"):
    tab1, tab2 = st.tabs(["要員リスト", "現場リスト"])
    with tab1:
        st.dataframe(st.session_state.df_staff, hide_index=True)
    with tab2:
        st.dataframe(st.session_state.df_site, hide_index=True)
    
    if st.button("🔄 データをリセットして最初から"):
        st.session_state.clear()
        st.rerun()

# C. チャットエリア
st.divider()
st.subheader("💬 AIへの配車指示")

# 履歴表示
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "条件を入力してください。（例：雨なので安全優先で）"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 入力ボタン類
c1, c2, c3 = st.columns(3)
user_input = None
if c1.button("☔️ 雨天モード"): user_input = "雨なので安全優先で"
if c2.button("🔰 新人ケア"): user_input = "新人に簡単な現場を"
if c3.button("⚡️ トラブル"): user_input = "トラブル発生、配置変更"

# 音声入力
audio = speech_to_text(language='ja', start_prompt="🎙 音声入力", stop_prompt="停止", just_once=True, key="rec")
if audio: user_input = audio

# テキスト入力
text = st.chat_input("指示を入力...")
if text: user_input = text

# 実行
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 処理実行
    new_df = run_optimization(user_input, st.session_state.df_site)
    st.session_state.df_site = new_df
    
    msg = "了解しました。ルートを再計算し、地図上のラインを引き直しました。"
    st.session_state.messages.append({"role": "assistant", "content": msg})
    st.rerun()
