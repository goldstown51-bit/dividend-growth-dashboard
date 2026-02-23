import streamlit as st
import pandas as pd

st.title("📈 連続増配ランキング（全市場横断）")

df = pd.read_csv("data/dividend_history.csv")

# 必須列チェック
required = {"code", "fiscal_year", "dps_regular_adj"}
missing = required - set(df.columns)
if missing:
    st.error(f"CSVに必要な列がありません: {', '.join(sorted(missing))}")
    st.stop()

# 型を整える
df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce")
df["dps_regular_adj"] = pd.to_numeric(df["dps_regular_adj"], errors="coerce")

# name/market は無くても動くように補完
if "name" not in df.columns:
    df["name"] = df["code"].astype(str)
if "market" not in df.columns:
    df["market"] = ""

df = df.dropna(subset=["code", "fiscal_year", "dps_regular_adj"])
df = df.sort_values(["code", "fiscal_year"])

def calc_consecutive_growth(group: pd.DataFrame) -> int:
    dps = group["dps_regular_adj"].tolist()
    years = 0
    for i in range(len(dps) - 1, 0, -1):
        if dps[i] > dps[i - 1]:
            years += 1
        else:
            break
    return years

# ★ここを堅牢に：applyの結果を「値列」にして列名をあとで付ける
applied = df.groupby(["code", "name", "market"], dropna=False).apply(calc_consecutive_growth)

result = applied.reset_index()
result.columns = ["code", "name", "market", "連続増配年数"]

min_years = st.slider("最低連続増配年数", 0, 30, 3)
filtered = result[result["連続増配年数"] >= min_years].copy()
filtered = filtered.sort_values(["連続増配年数", "code"], ascending=[False, True])

st.dataframe(filtered, use_container_width=True)
