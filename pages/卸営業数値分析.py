import streamlit as st
import pandas as pd

# ---------------------------- ヘルパー関数 ----------------------------

def read_uploaded_file(uploaded_file):
    """
    アップロードされたExcelファイルを読み込み、シート名をキー、DataFrameを値とする辞書を返します。
    ファイルがNoneの場合は空の辞書を返します。
    """
    if uploaded_file is not None:
        return pd.read_excel(uploaded_file, sheet_name=None, header=None)
    return {}

def extract_mapping(helper_sheets):
    """
    補助データシートから、除外コード、売上修正マップ、カテゴリマップを抽出します。
    """
    exclude_codes = []
    if "削除依頼" in helper_sheets:
        # 削除依頼シートからコードを抽出し、文字列に変換してゼロ埋め
        codes = helper_sheets["削除依頼"].iloc[:, 0].dropna()
        codes = codes.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
        exclude_codes = codes.tolist()

    fix_sales_map = {}
    if "計算修正" in helper_sheets:
        # 計算修正シートからコードと修正係数を抽出し、マップを作成
        sheet = helper_sheets["計算修正"].iloc[:, :2].dropna(how="all")
        for _, row in sheet.iterrows():
            try:
                code = str(int(row[0])).zfill(4)
                factor = float(row[1])
                fix_sales_map[code] = factor
            except ValueError: # データ変換エラーをキャッチ
                st.warning(f"「計算修正」シートのデータ形式が不正です: {row.tolist()}")
                continue

    category_map = {}
    if "大分類わけ" in helper_sheets:
        # 大分類わけシートからコードとカテゴリを抽出し、マップを作成
        sheet = helper_sheets["大分類わけ"].iloc[:, :2].dropna(how="all")
        for _, row in sheet.iterrows():
            try:
                code = str(int(row[0])).zfill(4)
                category = str(row[1]).strip()
                category_map[code] = category
            except ValueError: # データ変換エラーをキャッチ
                st.warning(f"「大分類わけ」シートのデータ形式が不正です: {row.tolist()}")
                continue

    return exclude_codes, fix_sales_map, category_map

def clean_sheet(df, exclude_codes, fix_sales_map, category_map):
    """
    アップロードされた売上データをクリーニングし、必要な列を整形します。
    """
    # ヘッダー行を特定（"得意先コード"を含む行）
    header_idx = df[df.apply(lambda r: r.astype(str).str.contains("得意先コード", na=False)).any(axis=1)].index
    if len(header_idx) == 0:
        return pd.DataFrame() # ヘッダーが見つからない場合は空のDataFrameを返す
    header = header_idx[0]

    # ヘッダーを設定し、ヘッダーより前の行を削除
    df.columns = df.iloc[header]
    df = df[(header + 1):].reset_index(drop=True)

    # 必須列の存在チェック
    required_columns = {"得意先コード", "得意先名", "純売上額"}
    if not required_columns.issubset(df.columns):
        return pd.DataFrame() # 必須列が不足している場合は空のDataFrameを返す

    # 得意先コードの整形（文字列化、小数点除去、ゼロ埋め）
    df["得意先コード"] = df["得意先コード"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    # 除外コードリストに基づいて行をフィルタリング
    df = df[~df["得意先コード"].isin(exclude_codes)]

    # 純売上額の修正（計算修正マップを適用）
    df["純売上額"] = df.apply(
        lambda r: r["純売上額"] * fix_sales_map.get(r["得意先コード"], 1.0),
        axis=1
    )
    # 大分類の割り当て（カテゴリマップを適用、未分類は"未分類"）
    df["大分類"] = df["得意先コード"].map(category_map).fillna("未分類")

    # 総売上額を計算し、構成比を算出
    total_sales = df["純売上額"].sum()
    df["構成比"] = (df["純売上額"] / total_sales * 100).round(2) if total_sales != 0 else 0.0

    # 得意先コード、得意先名、大分類でグループ化し、売上額と構成比を集計
    grouped = (
        df.groupby(["得意先コード", "得意先名", "大分類"], as_index=False)
        .agg({"純売上額": "sum", "構成比": "sum"})
        .sort_values("純売上額", ascending=False)
    )

    return grouped

def compare_years(prev_df, curr_df):
    """
    前年データと今年データを比較し、差額と前年比を計算します。
    """
    merged = pd.merge(
        prev_df,
        curr_df,
        on=["得意先コード", "得意先名", "大分類"],
        how="outer", # どちらかの年にしか存在しない得意先も含む
        suffixes=("_前年", "_今年"),
    )

    # 欠損値を0で埋める
    for col in ["純売上額_前年", "純売上額_今年", "構成比_前年", "構成比_今年"]:
        merged[col] = merged[col].fillna(0)

    # 売上額を千円単位に丸める
    merged["純売上額_前年"] = (merged["純売上額_前年"] / 1000).round().astype("Int64")
    merged["純売上額_今年"] = (merged["純売上額_今年"] / 1000).round().astype("Int64")

    # 差額と前年比を計算
    merged["差額"] = merged["純売上額_今年"] - merged["純売上額_前年"]
    merged["前年比(%)"] = merged.apply(
        lambda row: round(row["純売上額_今年"] / row["純売上額_前年"] * 100, 1)
        if row["純売上額_前年"] != 0 else (100.0 if row["純売上額_今年"] != 0 else 0.0), # 前年が0の場合は今年が0でなければ100%
        axis=1
    )

    # 表示列の順序を定義
    ordered_cols = [
        "得意先コード", "得意先名", "大分類",
        "純売上額_今年", "構成比_今年",
        "純売上額_前年", "構成比_前年",
        "前年比(%)", "差額"
    ]
    return merged[ordered_cols]

def summarize_by_category(comp_df):
    """
    カテゴリ別に売上データを集計します。
    """
    cat = comp_df.groupby("大分類", as_index=False).agg({
        "純売上額_前年": "sum",
        "純売上額_今年": "sum",
        "差額": "sum"
    })
    cat["前年比(%)"] = cat.apply(
        lambda r: round(r["純売上額_今年"] / r["純売上額_前年"] * 100, 1)
        if r["純売上額_前年"] != 0 else (100.0 if r["純売上額_今年"] != 0 else 0.0),
        axis=1
    )
    return cat

# ---------------------------- Streamlit アプリ ----------------------------

st.set_page_config(page_title="卸営業数値分析システム", layout="wide")
st.title("📊 卸営業数値分析システム")

st.markdown("### Step 0: データをアップロード")
prev_file = st.file_uploader("前年データ (Excel)", type=["xlsx"], key="prev_file_uploader")
curr_file = st.file_uploader("今年データ (Excel)", type=["xlsx"], key="curr_file_uploader")
helper_file = st.file_uploader("補助データ (データ整理.xlsx)", type=["xlsx"], key="helper_file_uploader")

if prev_file and curr_file and helper_file:
    # ファイル読み込み
    prev_sheets = read_uploaded_file(prev_file)
    curr_sheets = read_uploaded_file(curr_file)
    helper_sheets = read_uploaded_file(helper_file)

    # 補助データからのマッピング抽出
    exclude_codes, fix_sales_map, category_map = extract_mapping(helper_sheets)

    # 各Excelファイルの最初のシートをデータとして使用
    # シートが存在しない場合のエラーハンドリングを追加
    if not prev_sheets:
        st.error("前年データファイルにシートが見つかりません。")
        st.stop()
    prev_sheet_df = list(prev_sheets.values())[0]

    if not curr_sheets:
        st.error("今年データファイルにシートが見つかりません。")
        st.stop()
    curr_sheet_df = list(curr_sheets.values())[0]

    # データクリーニング
    prev_clean = clean_sheet(prev_sheet_df, exclude_codes, fix_sales_map, category_map)
    curr_clean = clean_sheet(curr_sheet_df, exclude_codes, fix_sales_map, category_map)

    if prev_clean.empty or curr_clean.empty:
        st.error("ヘッダ行（得意先コードなど）が見つからない、または必須列（得意先コード、得意先名、純売上額）が不足しています。Excelの列構成をご確認ください。")
        st.stop()

    st.markdown("### Step 1: 整理後データ")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("前年整理データ")
        st.dataframe(prev_clean, use_container_width=True)
    with col2:
        st.subheader("今年整理データ")
        st.dataframe(curr_clean, use_container_width=True)

    st.markdown("### Step 2: 前年 vs 今年 比較（千円単位）")
    comp_df = compare_years(prev_clean, curr_clean)
    st.dataframe(comp_df, use_container_width=True)

    st.markdown("### Step 3: 並び替えと集計")
    option = st.selectbox(
        "並び替え基準を選んでください",
        (
            "大分類別（純売上額＿今年順）",
            "大分類別（差額ベスト順）",
            "大分類別（差額ワースト順）",
            "得意先別（純売上額＿今年順）",
            "得意先別（差額ベスト順）",
            "得意先別（差額ワースト順）",
        ),
        key="sort_option_select" # キーを追加
    )

    if option.startswith("大分類別"):
        summary_df = summarize_by_category(comp_df)
        if "純売上額順" in option:
            summary_sorted = summary_df.sort_values("純売上額_今年", ascending=False)
        elif "ベスト" in option:
            summary_sorted = summary_df.sort_values("差額", ascending=False)
        else: # ワースト順
            summary_sorted = summary_df.sort_values("差額")
        st.dataframe(summary_sorted, use_container_width=True)
        # 棒グラフの表示
        if not summary_sorted.empty:
            st.bar_chart(summary_sorted.set_index("大分類")["純売上額_今年"])
        else:
            st.info("集計するデータがありません。")
    else: # 得意先別
        if "純売上額順" in option:
            df_sorted = comp_df.sort_values("純売上額_今年", ascending=False)
        elif "ベスト" in option:
            df_sorted = comp_df.sort_values("差額", ascending=False)
        else: # ワースト順
            df_sorted = comp_df.sort_values("差額")
        st.markdown("### 得意先別：比較結果")
        if not df_sorted.empty:
            st.dataframe(df_sorted, use_container_width=True)
        else:
            st.info("集計するデータがありません。")

    st.success("分析完了！")
else:
    st.info("前年・今年・補助データの3ファイルをすべてアップロードしてください。")

# ホーム画面に戻るリンクを一番下に追加
st.markdown("---")
st.page_link("分析ツールまとめ.py", label="メインメニューに戻る🏠 ", icon="🏠")