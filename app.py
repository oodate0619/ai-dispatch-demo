import streamlit as st
import pandas as pd
import random
import folium
from streamlit_folium import st_folium
from streamlit_mic_recorder import speech_to_text

# --- ページ設定 ---
st.set_page_config(page_title="AI配車アシスタント - デモ", layout="wide")

st.title("🚛 配車最適化AIアシスタント (Prototype Ver.2)")
st.markdown("現場の状況とスタッフの相性をAIが計算し、**「地図」**と**「根拠スコア」**で最適なルートを提案します。")

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
            "担当者": None, # AI割り当て用
            "適合スコア": 0 # AI計算用
        })
    return pd.DataFrame(staff_data), pd.DataFrame(site_data)

if 'df_staff' not in st.session_state:
    st.session_state.df_staff, st.session_state.df_site = generate_dummy_data()

# --- 2. 簡易AIロジックエンジン (デモ用Pythonロジック) ---
# ※実際の運用ではここが数理最適化エンジンになりますが、デモではルールベースで挙動を再現します
def run_optimization_logic(instruction, df_site, df_staff):
    df_site_new = df_site.copy()
    
    # デモ用の簡易ルール分岐
    if "新人" in instruction or "田中" in instruction:
        # 新人ケアモード: 田中に簡単な案件、残りをベテランへ
        df_site_new.loc[df_site_new["作業難易度"] == "低", "担当者"] = "田中(C)"
        df_site_new.loc[df_site_new["作業難易度"] != "低", "担当者"] = random.choice(["佐藤(A)", "鈴木(B)"])
        logic_comment = "新人(田中)に対し、難易度「低」かつストレス「低い」現場を優先的に割り当てました。"
    
    elif "雨" in instruction or "安全" in instruction:
        # 安全重視: ランダムだが近場想定（デモではランダム割り当てで再現）
        assignments = ["佐藤(A)", "鈴木(B)", "田中(C)"]
        df_site_new["担当者"] = df_site_new.apply(lambda x: random.choice(assignments), axis=1)
        logic_comment = "雨天のため、各拠点から移動距離が最短になるようルートを再計算しました。"
    
    else:
        # 通常/トラブル対応: ベテランに負荷を寄せる
        df_site_new.loc[df_site_new["作業難易度"] == "高(要交渉)", "担当者"] = "佐藤(A)"
        remaining = df_site_new[df_site_new["担当者"].isnull()].index
        for i in remaining:
            df_site_new.at[i, "担当者"] = random.choice(["鈴木(B)", "田中(C)"])
        logic_comment = "スキルレベルと現場難易度のマッチングを最適化しました。"

    # 欠損がある場合の埋め合わせ & スコア計算
    for index, row in df_site_new.iterrows():
        if pd.isnull(row["担当者"]):
            df_site_new.at[index, "担当者"] = "佐藤(A)" # デフォルト
        
        # 適合スコアの演出 (ランダムだがそれっぽく)
        base_score = random.randint(75, 95)
        if row["担当者"] == "佐藤(A)" and row["作業難易度"] == "高(要交渉)":
            base_score = 98 # ベテランのハマり役
        if row["担当者"] == "田中(C)" and row["作業難易度"] == "高(要交渉)":
            base_score = 40 # 新人には荷が重い
        
        df_site_new.at[index, "適合スコア"] = base_score

    return df_site_new, logic_comment

# --- 3. 可視化機能 (Map & Logic) ---
def render_map(df_site, df_staff):
    # 地図の中心を計算
    center_lat = df_site["緯度"].mean()
    center_lon = df_site["経度"].mean()
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    # スタッフごとの色定義
    color_map = {row["名前"]: row["色"] for _, row in df_staff.iterrows()}

    for _, row in df_site.iterrows():
        assignee = row["担当者"]
        color = color_map.get(assignee, "gray")
        
        # ツールチップの内容
        tooltip_text = f"<b>{row['現場名']}</b><br>担当: {assignee}<br>難度: {row['作業難易度']}"
        
        folium.Marker(
            [row["緯度"], row["経度"]],
            popup=tooltip_text,
            tooltip=row["現場名"],
            icon=folium.Icon(color=color, icon="wrench", prefix="fa")
        ).add_to(m)
    
    return m

# --- 4. 生成AI (LLM) ラッパー ---
def get_ai_explanation(user_instruction, df_result, logic_text, api_key):
    # データフレームをテキスト化（結果を渡して解説させる）
    result_text = df_result[["現場名", "作業難易度", "担当者", "適合スコア"]].to_json(orient="records", force_ascii=False)

    system_prompt = f"""
    あなたは熟練の配車担当者です。
    ユーザーの指示「{user_instruction}」に基づき、Pythonエンジンが以下の配置を行いました。
    
    # 計算結果データ
    {result_text}
    
    # 配置ロジック
    {logic_text}
    
    この結果をユーザーに報告してください。
    特に「なぜその人をそこに配置したか」を、スコアや難易度を引用して論理的に説明してください。
    """

    if not api_key:
        import time
        time.sleep(1)
        return f"""
**(模擬回答)**
指示に基づき、ルートを再構築しました。

**🚚 今回の配置ポイント ({logic_text})**

* **佐藤(A)さん** (赤ピン): 
    * 難所である「中央ビル」などを担当。適合スコア98%で、トラブル対応も万全です。
* **田中(C)さん** (緑ピン): 
    * 「青葉区マンション」など、難易度「低」の現場に集中させました。無理なく経験を積めます。
        """
    else:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "結果を分かりやすく報告して。"}
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"エラー: {str(e)}"

# --- 5. UI構築 ---

# サイドバー
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1995/1995493.png", width=100) # デモ用アイコン
    st.write("### 設定")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    if not openai_api_key:
        st.info("🔑 キー未入力時は模擬モードで動作")
    
    st.divider()
    st.write("**凡例 (担当カラー)**")
    st.markdown("🔴 **佐藤(ベテラン)**")
    st.markdown("🔵 **鈴木(中堅)**")
    st.markdown("🟢 **田中(新人)**")

# Expander (データ参照)
with st.expander("📋 【参照データ】現在の要員リストと現場リストを見る"):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("要員 (Staff)")
        st.dataframe(st.session_state.df_staff[["名前", "スキル", "性格"]], hide_index=True)
    with col2:
        st.subheader("現場 (Sites)")
        st.dataframe(st.session_state.df_site[["現場名", "作業難易度", "対人ストレス"]], hide_index=True)
    
    if st.button("🔄 データをリセット"):
        st.session_state.df_staff, st.session_state.df_site = generate_dummy_data()
        st.rerun()

# チャット履歴表示
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "おはようございます。本日の配置条件を指示してください。"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        # アシスタントのメッセージに含まれる場合、過去の地図や表も再表示したいが、
        # Streamlitの仕様上、履歴内のコンポーネント再描画は複雑になるため、
        # 最新の結果のみを下に大きく表示するスタイルをとります。

# 入力エリア
st.write("### 👇 指示を入力 (タップまたは音声)")
col_btn1, col_btn2, col_btn3 = st.columns(3)
user_input = None

with col_btn1:
    if st.button("☔️ 雨天・安全重視モード"):
        user_input = "雨なので移動距離を短く、安全優先で。"
with col_btn2:
    if st.button("🔰 新人(田中)ケアモード"):
        user_input = "田中くんは新人だから、簡単な現場だけ割り当てて。"
with col_btn3:
    if st.button("⚡️ トラブル対応モード"):
        user_input = "佐藤さんが急なクレーム対応で1件行けなくなった。調整して。"

st.write("🎙 **音声入力:**")
audio_text = speech_to_text(language='ja', start_prompt="録音開始", stop_prompt="録音終了", just_once=True, key="rec")
if audio_text:
    user_input = audio_text

chat_input_text = st.chat_input("具体的な指示を入力...")
if chat_input_text:
    user_input = chat_input_text

# --- 実行ロジック ---
if user_input:
    # 1. ユーザー入力を表示
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 2. AI処理中表示
    with st.chat_message("assistant"):
        with st.spinner("AIが最適ルート計算と相性診断を行っています..."):
            
            # A. Pythonロジックで計算 (Level 3: Logic)
            df_optimized, logic_comment = run_optimization_logic(
                user_input, st.session_state.df_site, st.session_state.df_staff
            )
            
            # B. LLMで解説生成 (Level 1: Chat)
            response_text = get_ai_explanation(user_input, df_optimized, logic_comment, openai_api_key)
            st.markdown(response_text)
            
            # C. 地図と詳細データの表示 (Level 2 & 3: Visual)
            st.divider()
            st.subheader("🗺️ AI配置シミュレーション結果")
            
            col_map, col_data = st.columns([1, 1])
            
            with col_map:
                st.markdown("**▼ ルート可視化** (ピンの色＝担当者)")
                map_obj = render_map(df_optimized, st.session_state.df_staff)
                st_folium(map_obj, height=300, width="100%")
            
            with col_data:
                st.markdown("**▼ マッチング根拠 (AIスコア)**")
                # スコアをプログレスバーで可視化
                for _, row in df_optimized.iterrows():
                    score = int(row["適合スコア"])
                    st.write(f"**{row['現場名']}** → {row['担当者']}")
                    color = "red" if score < 60 else "green"
                    st.progress(score / 100, text=f"適合率: {score}%")
                    
            st.caption("※適合率は、スキル・移動距離・過去のトラブル履歴から算出しています。")

    # 3. 履歴保存
    st.session_state.messages.append({"role": "assistant", "content": response_text})
    # データフレームの状態を更新（次回の計算ベースにするため）
    st.session_state.df_site = df_optimized