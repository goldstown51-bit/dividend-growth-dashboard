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

# 型整形
df["code"] = df["code"].astype(str)
df["fiscal_year"] = pd.to_numeric(df["fiscal_year"], errors="coerce")
df["dps_regular_adj"] = pd.to_numeric(df["dps_regular_adj"], errors="coerce")

# name/market が無ければ補完
if "name" not in df.columns:
    df["name"] = df["code"]
if "market" not in df.columns:
    df["market"] = ""

# 欠損除外
df = df.dropna(subset=["fiscal_year", "dps_regular_adj"])
df = df.sort_values(["code", "fiscal_year"])

# --- 連続増配年数の計算（apply不使用） ---
# 前年DPS
df["prev_dps"] = df.groupby("code")["dps_regular_adj"].shift(1)
# 増配フラグ（前年比で増えているか）
df["is_growth"] = df["dps_regular_adj"] > df["prev_dps"]

# 各銘柄の「直近年度」を特定
latest_year = df.groupby("code")["fiscal_year"].max().rename("latest_year")
df = df.merge(latest_year, on="code", how="left")

# 直近から遡るために、直近年度との差（0,1,2...）を作る
df["from_latest"] = (df["latest_year"] - df["fiscal_year"]).astype(int)

# 直近側から並ぶように（0が最新）
df = df.sort_values(["code", "from_latest"])

# 連続増配：最新から見て is_growth が True の連続数
# Trueが続く間だけ数えるために、最初のFalseが出た位置で打ち切り
def consecutive_true_count(s: pd.Series) -> int:
    # s: 最新から古い順の is_growth
    count = 0
    for v in s.tolist():
        if v is True:
            count += 1
        else:
            break
    return count

# 最新年(差0)は prev_dps が無いので is_growth は False/NaN になりがち
# 連続増配年数は「増配が起きた回数」なので、差1以降だけ見ればOK
df_for_count = df[df["from_latest"] >= 1]

result = (
    df_for_count.groupby("code")["is_growth"]
    .apply(consecutive_true_count)
    .reset_index()
    .rename(columns={"is_growth": "連続増配年数"})
)

# name/market を付与（銘柄マスタが無い前提で、最新の行から拾う）
meta = (
    df.sort_values(["code", "fiscal_year"])
      .groupby("code", as_index=False)[["code", "name", "market"]]
      .tail(1)
      .set_index("code")
)
result = result.join(meta, on="code")

# --- 5年DPS CAGRを result に追加（安全版） ---
def dps_cagr_5y(group: pd.DataFrame) -> float:
    g = group.sort_values("fiscal_year")
    if len(g) < 6:
        return float("nan")
    latest = float(g.iloc[-1]["dps_regular_adj"])
    past = float(g.iloc[-6]["dps_regular_adj"])  # 5年前
    if past <= 0:
        return float("nan")
    return (latest / past) ** (1/5) - 1

cagr_series = df.groupby("code").apply(dps_cagr_5y)

# pandasの挙動差を吸収：SeriesでもDataFrameでもOKにする
cagr = cagr_series.reset_index()
# 2列目の名前が何でも、最後の列をCAGRとして扱う
cagr = cagr.rename(columns={cagr.columns[-1]: "DPS_CAGR_5Y"})

result = result.merge(cagr[["code", "DPS_CAGR_5Y"]], on="code", how="left")
result["DPS_CAGR_5Y"] = (result["DPS_CAGR_5Y"] * 100).round(2)  # %

# UI
# --- フィルター/UI ---
max_streak = int(result["連続増配年数"].max()) if len(result) else 0
default_min = 3 if max_streak >= 3 else max_streak

min_years = st.slider("最低連続増配年数", 0, max(0, max_streak), default_min)

markets = ["ALL"] + sorted([m for m in result["market"].dropna().unique().tolist() if str(m) != ""])
market_sel = st.selectbox("市場", markets)

filtered = result.copy()
if market_sel != "ALL":
    filtered = filtered[filtered["market"] == market_sel]

filtered = filtered[filtered["連続増配年数"] >= min_years].copy()

# 列が無い場合でも落ちないように
cols = ["code", "name", "market", "連続増配年数"]
if "DPS_CAGR_5Y" in filtered.columns:
    cols.append("DPS_CAGR_5Y")

filtered = filtered[cols].sort_values(
    ["連続増配年数"] + (["DPS_CAGR_5Y"] if "DPS_CAGR_5Y" in cols else []),
    ascending=[False] * len(cols[3:])
)

st.dataframe(filtered, use_container_width=True)

# デバッグ表示（必要ならON）
with st.expander("デバッグ（必要なときだけ開く）"):
    st.write("データ行数:", len(df))
    st.write(df.head(20))
