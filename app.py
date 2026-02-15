import streamlit as st
import pandas as pd
import random
import folium
from streamlit_folium import st_folium
from streamlit_mic_recorder import speech_to_text

# --- ページ設定 ---
st.set_page_config(page_title="AI配車アシスタント", layout="wide")
st.title("🚛 配車最適化AIアシスタント (Final+)")

# --- 1. データ生成と「自動修復」セクション ---
def generate_dummy_data():
    staff_data = [
        {"ID": "A", "名前": "佐藤(A)", "スキル": "ベテラン", "色": "red"},
        {"ID": "B", "名前": "鈴木(B)", "スキル": "中堅", "色": "blue"},
        {"ID": "C", "名前": "田中(C)", "スキル": "新人", "色": "green"}
    ]
    office = {"現場名": "🏢 事務所(START)", "lat": 35.4658, "lon": 139.6223}
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

# セッション初期化（キャッシュ切れ対策）
if 'office' not in st.session_state or 'df_site' not in st.session_state:
    st.session_state.df_staff, st.session_state.df_site, st.session_state.office = generate_dummy_data()
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
        for i in df.index:
            if df.at[i, "担当者"] == "未定":
                df.at[i, "担当者"] = random.choice(["佐藤(A)", "鈴木(B)"])
    
    # 順序とスコア付与
    for name in ["佐藤(A)", "鈴木(B)", "田中(C)"]:
        mask = df["担当者"] == name
        count = df[mask].shape[0]
        if count > 0:
            df.loc[mask, "訪問順"] = range(1, count + 1)
            df.loc[mask, "適合スコア"] = [random.randint(80, 100) for _ in range(count)]
    return df

# --- 3. 地図描画 ---
def render_map(df_site, df_staff, office):
    m = folium.Map(location=[35.50, 139.60], zoom_start=11)
    folium.Marker([office["lat"], office["lon"]], tooltip="事務所", icon=folium.Icon(color="black", icon="building", prefix="fa")).add_to(m)
    color_map = {row["名前"]: row["色"] for _, row in df_staff.iterrows()}

    for _, staff in df_staff.iterrows():
        name = staff["名前"]
        my_sites = df_site[df_site["担当者"] == name].sort_values("訪問順")
        if not my_sites.empty:
            points = [[office["lat"], office["lon"]]]
            for _, site in my_sites.iterrows():
                points.append([site["緯度"], site["経度"]])
            folium.PolyLine(points, color=staff["色"], weight=5, opacity=0.8, tooltip=f"{name}ルート").add_to(m)

    for _, row in df_site.iterrows():
        assignee = row["担当者"]
        color = color_map.get(assignee, "gray")
        tip_text = f"{row['現場名']} (未定)" if assignee == "未定" else f"【{row['訪問順']}】{row['現場名']} ({assignee})"
        folium.Marker([row["緯度"], row["経度"]], tooltip=tip_text, icon=folium.Icon(color=color, icon="wrench", prefix="fa")).add_to(m)
    return m

# --- 4. 画面レイアウト ---
st.subheader("🗺️ リアルタイム ルートマップ")
map_obj = render_map(st.session_state.df_site, st.session_state.df_staff, st.session_state.office)
st_folium(map_obj, height=350, width="100%", returned_objects=[])

st.info("👇 以下のバーを押すと、詳細データを確認できます")
with st.expander("📋 【詳細データ】要員リスト・現場リストを見る"):
    tab1, tab2 = st.tabs(["要員リスト", "現場リスト"])
    with tab1: st.dataframe(st.session_state.df_staff, hide_index=True)
    with tab2: st.dataframe(st.session_state.df_site, hide_index=True)
    if st.button("🔄 リセット"):
        st.session_state.clear()
        st.rerun()

st.divider()
st.subheader("💬 AIへの配車指示")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "条件を入力してください。（例：雨なので安全優先で）"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"]) # Markdown対応に変更

col1, col2, col3 = st.columns(3)
user_input = None
if col1.button("☔️ 雨天モード"): user_input = "雨なので安全優先で"
if col2.button("🔰 新人ケア"): user_input = "新人に簡単な現場を"
if col3.button("⚡️ トラブル"): user_input = "トラブル発生、配置変更"

audio = speech_to_text(language='ja', start_prompt="🎙 音声入力", stop_prompt="停止", just_once=True, key="rec")
if audio: user_input = audio

text = st.chat_input("指示を入力...")
if text: user_input = text

# --- 実行ロジック（ここに追加実装しました） ---
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 計算
    new_df = run_optimization(user_input, st.session_state.df_site)
    st.session_state.df_site = new_df
    
    # ★追加機能: テキスト要約の生成
    summary_text = "指示通りに再配車しました。\n\n**【担当割り当て結果】**"
    for name in ["佐藤(A)", "鈴木(B)", "田中(C)"]:
        # その担当者の現場を抽出
        my_sites = new_df[new_df["担当者"] == name]["現場名"].tolist()
        if my_sites:
            sites_str = " → ".join(my_sites)
            # アイコンで色分けを表現
            icon = "🔴" if "佐藤" in name else "🔵" if "鈴木" in name else "🟢"
            summary_text += f"\n- {icon} **{name}**: {sites_str}"
        else:
             summary_text += f"\n- ⚪ **{name}**: (担当なし)"

    st.session_state.messages.append({"role": "assistant", "content": summary_text})
    st.rerun()
