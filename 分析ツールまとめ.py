import streamlit as st

st.set_page_config(
    page_title="メインメニュー",
    page_icon="🏠",
    layout="centered"
)

st.title("ようこそ！データ分析アプリケーションへ")
st.write("以下から見たい分析ページを選択してください。")

st.markdown("---")  # 区切り線

# 各ページへのリンクを設置
st.page_link("pages/営業報告分析.py", label="営業報告分析📊", icon="📊")
st.page_link("pages/卸営業数値分析.py", label="卸営業数値分析📈", icon="📈")
st.page_link("pages/アイテム別集計.py", label="アイテム別集計📦", icon="📦")

st.markdown("---")
st.info("💡 各リンクをクリックすると、それぞれの分析ページに移動します。")