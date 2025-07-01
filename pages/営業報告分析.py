# 営業報告分析.py
import streamlit as st
import pandas as pd
import re
from collections import Counter
from datetime import datetime
import openpyxl # openpyxlをインポート

# 定数
KINIKI_AREAS = ["大阪", "奈良", "京都", "滋賀", "兵庫", "三重", "和歌山"]
VALID_CATEGORIES = ["駅", "高速", "空港", "一般店", "量販店", "商社"]

# ページ設定
st.set_page_config(layout="wide")
st.title("📊 営業報告分析システム")

# ファイルアップローダー
uploaded_file = st.file_uploader("Excelファイル（.xlsx）をアップロード", type="xlsx")

if uploaded_file:
    try:
        # openpyxlでワークブックを読み込み、非表示シートを特定
        workbook = openpyxl.load_workbook(uploaded_file, read_only=True)
        visible_sheet_names = []
        for sheet_name in workbook.sheetnames:
            ws = workbook[sheet_name]
            if ws.sheet_state == 'visible':
                visible_sheet_names.append(sheet_name)

        # pandas.ExcelFileオブジェクトを作成
        xls = pd.ExcelFile(uploaded_file)

        # 表示されているシート名のみを対象とする
        # ただし、xls.sheet_namesにvisible_sheet_namesに含まれていないシート名が含まれる可能性もあるため、共通のシート名を取得
        sheet_names = [s for s in xls.sheet_names if s in visible_sheet_names]

        # シートの分離
        log_sheet = "操作履歴"
        # log_sheetも表示されているシートのみを対象とする
        if log_sheet in sheet_names:
            main_sheets = [s for s in sheet_names if s != log_sheet]
            # 操作履歴データの読み込みと前処理
            df_log = pd.read_excel(xls, sheet_name=log_sheet)
            df_log["日時"] = pd.to_datetime(df_log["日時"], errors="coerce")
        else:
            # 操作履歴シートがない場合、空のDataFrameを作成
            df_log = pd.DataFrame(columns=["日時", "シート名", "操作タイプ", "対象UUID", "ステータスの変更", "商品ステータス"])
            main_sheets = sheet_names # log_sheetがなければ、全ての表示シートをメインシートとする


        # 主要データの読み込みと結合
        df_list = []
        for sheet in main_sheets:
            df_tmp = pd.read_excel(xls, sheet_name=sheet)
            df_tmp["シート名"] = sheet
            # シート名から担当者と種別を抽出
            # "_"がない場合は"不明"を割り当てる
            if "_" in sheet:
                df_tmp["担当者"], df_tmp["種別"] = sheet.split("_")
            else:
                df_tmp["担当者"] = "不明" # 「不明」として割り当てる
                df_tmp["種別"] = "不明"   # 「不明」として割り当てる
            df_list.append(df_tmp)

        df = pd.concat(df_list, ignore_index=True)
        df["記入日"] = pd.to_datetime(df["記入日"], errors="coerce")

        # 地域データの正規化
        # 空欄または"その他："で始まる場合は「未分類」として集計
        df["地域"] = df["地域"].apply(lambda x: "未分類" if pd.isna(x) or str(x).strip() == "" or str(x).startswith("その他：") else x)
        df["地域"] = df["地域"].apply(lambda x: "その他" if x not in KINIKI_AREAS and x != "未分類" else x)


        # カテゴリの抽出 (採用・不採用理由から)
        df["カテゴリ"] = df["採用・不採用理由"].apply(
            lambda x: re.findall(r"【(.*?)】", str(x))[0].split("・") if re.findall(r"【(.*?)】", str(x)) else [])

        # Streamlitのセッションステートに変数を初期化
        if 'df_filtered_display' not in st.session_state:
            st.session_state.df_filtered_display = None
        if 'df_log_filtered_display' not in st.session_state:
            st.session_state.df_log_filtered_display = None

        # サイドバーの訪問データフィルターフォーム
        with st.sidebar.form("main_filter_form"):
            st.markdown("### 🎛 訪問データの絞り込み")

            # 担当者フィルタから「不明」を除外
            persons_all = sorted(df["担当者"].dropna().unique())
            persons = [p for p in persons_all if p != "不明"]

            # 種別フィルタから「不明」を除外
            types_all = sorted(df["種別"].dropna().unique())
            types = [t for t in types_all if t != "不明"]

            # 地域に「未分類」を追加
            areas_raw = df["地域"].dropna().unique().tolist()
            areas = sorted(list(set(areas_raw + ["未分類"]))) # setを使って重複を削除してからソート

            cats = sorted([c for c in df["大分類"].dropna().unique() if c in VALID_CATEGORIES])

            selected_persons = st.multiselect("担当者", persons, default=persons)
            selected_types = st.multiselect("種別", types, default=types)
            selected_areas = st.multiselect("地域", areas, default=areas)
            selected_categories = st.multiselect("大分類", cats, default=cats)

            # 記入日の最小値と最大値を取得し、NaTがないかチェック
            min_date = df["記入日"].min()
            max_date = df["記入日"].max()

            # 日付範囲が有効な場合のみdate_inputに設定
            if pd.isna(min_date) or pd.isna(max_date):
                st.warning("「記入日」データに有効な日付が見つかりませんでした。日付フィルターは利用できません。")
                start_date = None
                end_date = None
            else:
                start_date, end_date = st.date_input("記入日", [min_date, max_date])

            submitted_main = st.form_submit_button("🔍 訪問データを絞り込む")

        # サイドバーの操作履歴フィルターフォーム
        with st.sidebar.form("log_filter_form"):
            st.markdown("### 📋 操作履歴の絞り込み")
            log_sheets = sorted(df_log["シート名"].dropna().unique())
            selected_logs = st.multiselect("シート名", log_sheets, default=log_sheets)

            # 操作日時の最小値と最大値を取得し、NaTがないかチェック
            log_min_date = df_log["日時"].min()
            log_max_date = df_log["日時"].max()

            if pd.isna(log_min_date) or pd.isna(log_max_date):
                st.warning("「操作日時」データに有効な日付が見つかりませんでした。日付フィルターは利用できません。")
                log_start = None
                log_end = None
            else:
                log_start, log_end = st.date_input("操作日時", [log_min_date, log_max_date])

            submitted_log = st.form_submit_button("📌 操作履歴を絞り込む")

        # 訪問データのフィルター処理とセッションステートへの保存
        if submitted_main:
            if start_date and end_date: # 日付が有効な場合のみフィルターを適用
                df_filtered_calc = df[
                    df["担当者"].isin(selected_persons) &
                    df["種別"].isin(selected_types) &
                    df["地域"].isin(selected_areas) &
                    df["大分類"].isin(selected_categories) &
                    df["記入日"].between(pd.to_datetime(start_date), pd.to_datetime(end_date), inclusive="both")
                ]
            else: # 日付が無効な場合は日付フィルターなしで適用
                df_filtered_calc = df[
                    df["担当者"].isin(selected_persons) &
                    df["種別"].isin(selected_types) &
                    df["地域"].isin(selected_areas) &
                    df["大分類"].isin(selected_categories)
                ]
            st.session_state.df_filtered_display = df_filtered_calc

        # 操作履歴のフィルター処理とセッションステートへの保存
        if submitted_log:
            if log_start and log_end: # 日付が有効な場合のみフィルターを適用
                df_log_filtered_result_calc = df_log[
                    df_log["シート名"].isin(selected_logs) &
                    df_log["日時"].between(pd.to_datetime(log_start), pd.to_datetime(log_end), inclusive="both")
                ].copy()
            else: # 日付が無効な場合は日付フィルターなしで適用
                df_log_filtered_result_calc = df_log[
                    df_log["シート名"].isin(selected_logs)
                ].copy()

            # ステータス変更の抽出ヘルパー関数
            def extract_changed(val):
                if pd.isna(val) or "→" not in str(val): # str(val)を追加してNaNでもエラーにならないように
                    return None
                from_, to_ = str(val).split("→")
                return to_.strip() if from_.strip() != to_.strip() else None

            df_log_filtered_result_calc["変更後ステータス"] = df_log_filtered_result_calc["ステータスの変更"].apply(extract_changed)
            df_log_filtered_result_calc["変更後商品ステータス"] = df_log_filtered_result_calc["商品ステータス"].apply(extract_changed)
            st.session_state.df_log_filtered_display = df_log_filtered_result_calc

        # 訪問データ分析結果の表示 (セッションステートにデータがあれば表示)
        if st.session_state.df_filtered_display is not None:
            df_filtered_to_display = st.session_state.df_filtered_display
            st.subheader("📈 訪問データ分析")

            # データが空の場合のハンドリング
            if df_filtered_to_display.empty:
                st.info("選択されたフィルター条件に合致する訪問データがありません。")
            else:
                uuid_df = df_filtered_to_display.drop_duplicates("UUID")
                status_counts = uuid_df["ステータス"].value_counts()
                product_count = df_filtered_to_display["商品名"].notna().sum()
                result_counts = df_filtered_to_display["結果"].value_counts()

                st.markdown("#### ステータス（UUID単位）")
                for s in ["アポ", "訪問予定", "検討中", "完了"]:
                    st.write(f"- {s}：{status_counts.get(s, 0)} 件")

                st.markdown("#### 商品ステータス（商品単位）")
                for s in ["採用", "不採用", "返答待ち"]:
                    val = result_counts.get(s, 0)
                    rate = val / product_count if product_count else 0
                    st.write(f"- {s}：{val} 件（{rate:.1%}）")

                # 採用・不採用理由カテゴリの集計
                df_saiyo = df_filtered_to_display[df_filtered_to_display["結果"] == "採用"]
                df_fusaiyo = df_filtered_to_display[df_filtered_to_display["結果"] == "不採用"]
                cat_saiyo = Counter(sum(df_saiyo["カテゴリ"], []))
                cat_fusaiyo = Counter(sum(df_fusaiyo["カテゴリ"], []))

                df_saiyo_cat = pd.DataFrame(cat_saiyo.items(), columns=["カテゴリ", "件数"])
                df_fusaiyo_cat = pd.DataFrame(cat_fusaiyo.items(), columns=["カテゴリ", "件数"])

                if not df_saiyo_cat.empty:
                    df_saiyo_cat["割合"] = (df_saiyo_cat["件数"] / df_saiyo_cat["件数"].sum() * 100).round(1).astype(str) + "%"
                if not df_fusaiyo_cat.empty:
                    df_fusaiyo_cat["割合"] = (df_fusaiyo_cat["件数"] / df_fusaiyo_cat["件数"].sum() * 100).round(1).astype(str) + "%"

                st.markdown("#### 採用理由カテゴリ")
                if not df_saiyo_cat.empty:
                    st.dataframe(df_saiyo_cat.sort_values("件数", ascending=False), use_container_width=True)
                else:
                    st.write("該当するデータがありません。")

                st.markdown("#### 不採用理由カテゴリ")
                if not df_fusaiyo_cat.empty:
                    st.dataframe(df_fusaiyo_cat.sort_values("件数", ascending=False), use_container_width=True)
                else:
                    st.write("該当するデータがありません。")

                if st.checkbox("📂 訪問データのフィルター後データを見る", key="view_filtered_visit_data"):
                    st.dataframe(df_filtered_to_display, use_container_width=True)

        # 操作履歴の分析結果の表示 (セッションステートにデータがあれば表示)
        if st.session_state.df_log_filtered_display is not None:
            df_log_filtered_result_to_display = st.session_state.df_log_filtered_display
            st.subheader("📘 操作履歴の分析結果")

            # データが空の場合のハンドリング
            if df_log_filtered_result_to_display.empty:
                st.info("選択されたフィルター条件に合致する操作履歴データがありません。")
            else:
                uuid_filtered_result = df_log_filtered_result_to_display.drop_duplicates("対象UUID")

                op_counts_result = uuid_filtered_result["操作タイプ"].value_counts()
                status_counts_result = uuid_filtered_result["変更後ステータス"].dropna().value_counts()
                result_counts_result = uuid_filtered_result["変更後商品ステータス"].dropna().value_counts()

                st.markdown("#### 操作タイプ（UUID単位）")
                for op in ["新規提案", "編集", "削除"]:
                    st.write(f"- {op}：{op_counts_result.get(op, 0)} 件")

                st.markdown("#### ステータス変更後（UUID単位）")
                for s in ["アポ", "訪問予定", "検討中", "完了"]:
                    st.write(f"- {s}：{status_counts_result.get(s, 0)} 件")

                st.markdown("#### 商品ステータス変更後（UUID単位）")
                for r in ["採用", "不採用", "返答待ち"]:
                    st.write(f"- {r}：{result_counts_result.get(r, 0)} 件")

                if st.checkbox("📂 操作履歴のフィルター後データを見る", key="view_filtered_log_data"):
                    st.dataframe(df_log_filtered_result_to_display, use_container_width=True)

    except Exception as e:
        st.error(f"エラーが発生しました：{e}")

# ホーム画面に戻るリンクを一番下に追加
st.markdown("---")
st.page_link("分析ツールまとめ.py", label="メインメニューに戻る🏠", icon="🏠")
