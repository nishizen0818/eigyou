import pandas as pd
import streamlit as st
import re

st.set_page_config(page_title="商品分類別売上集計", layout="wide")
st.title("📊 商品分類別 売上集計システム")

# --- ① ファイルアップロード ---
st.header("① ファイルアップロード")

class_file = st.file_uploader("🔼 分類わけファイル (.xlsx)", type=["xlsx", "xls"], key="class_file_uploader")
data_file = st.file_uploader("🔼 商品データファイル (.xlsx)", type=["xlsx", "xls"], key="data_file_uploader")

if class_file and data_file:
    try:
        # --- ② 分類ファイル読み込み ---
        df_class = pd.read_excel(class_file)
        df_class['優先フラグ'] = df_class['優先度'].fillna('').apply(lambda x: 1 if str(x).strip() == '〇' else 0)
        df_class['キーワード長'] = df_class['キーワード'].astype(str).apply(
            lambda x: sum(len(k.strip()) for k in str(x).split('・')) if pd.notna(x) else 0
        )
        df_class = df_class.sort_values(['優先フラグ', 'キーワード長'], ascending=[False, False])
        st.success("✅ 分類わけファイル読み込み完了")

        # --- ③ 商品データ読み込み ---
        df_data = pd.read_excel(data_file, header=0)
        st.success("✅ 商品データファイル読み込み完了")

        # --- ④ 商品名列検出と分類処理 ---
        product_cols = [col for col in df_data.columns if '商品' in str(col)]
        if product_cols:
            product_col = product_cols[0]
            df_data['商品名'] = df_data[product_col]
        else:
            st.error("❌ 『商品名』を含む列が見つかりません。")
            st.stop()

        def classify(name):
            if pd.isna(name):
                return '未分類'
            for _, row in df_class.iterrows():
                keywords = str(row['キーワード']).split('・')
                if any(k.strip() in str(name) for k in keywords):
                    return row['分類']
            return '未分類'

        df_data['分類'] = df_data['商品名'].apply(classify)

        # --- 分類済みデータの表示 ---
        st.header("② 分類済みデータのプレビュー")
        preview_cols = ['商品名', '分類'] + [col for col in df_data.columns if '個数' in str(col) or '金額' in str(col)]
        preview_cols = [col for col in preview_cols if col in df_data.columns]

        if not df_data.empty and preview_cols:
            st.dataframe(df_data[preview_cols], use_container_width=True, key="classified_data_preview")
        else:
            st.info("分類後のプレビューデータがありません。")

        # --- ⑤ 年・個数・金額ペア抽出 ---
        records = []
        for col in df_data.columns:
            match = re.match(r'(\d{4})年\d+月_個数', col)
            if match:
                year = int(match.group(1))
                amt_col = col.replace('個数', '金額')
                if amt_col in df_data.columns:
                    temp = df_data[['分類', col, amt_col]].copy()
                    temp.columns = ['分類', '個数', '金額']
                    temp['個数'] = pd.to_numeric(temp['個数'], errors='coerce').fillna(0)
                    temp['金額'] = pd.to_numeric(temp['金額'], errors='coerce').fillna(0)
                    temp['年'] = year
                    records.append(temp)

        if not records:
            st.error("❌ 年別の個数・金額列が見つかりませんでした。")
            st.stop()

        # --- ⑥ 集計と前年比 ---
        df_all = pd.concat(records)
        df_all = df_all.dropna(subset=['分類']).groupby(['分類', '年']).sum(numeric_only=True).reset_index()

        if df_all.empty:
            st.info("集計するデータがありません。")
            st.stop()

        df_all['前年金額'] = df_all.groupby('分類')['金額'].shift(1)
        df_all['金額_前年比'] = df_all.apply(
            lambda row: f"{(row['金額'] / row['前年金額'] * 100):.1f}%"
            if pd.notnull(row['前年金額']) and row['前年金額'] != 0 else
            (f"{100.0:.1f}%" if row['金額'] != 0 else "0.0%"),
            axis=1
        )
        df_all.drop(columns=['前年金額'], inplace=True)

        # --- ⑦ ピボット展開 ---
        def pivotify(df, column):
            p = df.pivot(index='分類', columns='年', values=column)
            p.columns = [f"{y}年_{column}" for y in p.columns]
            return p

        df_result = pd.concat([
            pivotify(df_all, '個数'),
            pivotify(df_all, '金額'),
            pivotify(df_all, '金額_前年比')
        ], axis=1).reset_index()

        # --- ⑧ 欠損値補完 ---
        for col in df_result.columns:
            if col.endswith('前年比'):
                df_result[col] = df_result[col].replace('', '100.0%')
            else:
                df_result[col] = df_result[col].fillna(0)

        # --- ⑨ 列順整列 ---
        all_years = sorted(df_all['年'].unique(), reverse=True)
        col_order = ['分類']
        for y in all_years:
            col_order += [f"{y}年_個数", f"{y}年_金額", f"{y}年_金額_前年比"]
        df_result = df_result[[col for col in col_order if col in df_result.columns]]

        # --- ⑩ 集計結果の表示（CSV出力なし） ---
        st.header("③ 集計結果プレビュー")
        if not df_result.empty:
            st.dataframe(df_result, use_container_width=True, key="final_summary_dataframe")
        else:
            st.info("集計結果が生成されませんでした。データを確認してください。")

    except Exception as e:
        st.error(f"⚠️ エラーが発生しました：\n\n{e}")
else:
    st.info("📂 分類ファイルとデータファイルの両方をアップロードしてください。")

# --- メインメニューへのリンク（ページ遷移） ---
st.markdown("---")
st.page_link("分析ツールまとめ.py", label="メインメニューに戻る🏠", icon="🏠")