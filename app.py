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

# --- 5年DPS CAGRを result に追加（apply不使用・安定版） ---
# code,fiscal_year,dps_regular_adj が df にある前提

# 年度順に並んでいる前提だが、念のため
tmp = df.sort_values(["code", "fiscal_year"]).copy()

# 各銘柄の「最後の6年分」を取り出す（5年CAGRには6点必要）
tail6 = tmp.groupby("code", as_index=False).tail(6)

# 6年未満は自然に落ちる（CAGR計算できない）
counts = tail6.groupby("code")["fiscal_year"].count()
valid_codes = set(counts[counts >= 6].index.astype(str))
tail6 = tail6[tail6["code"].astype(str).isin(valid_codes)]

# 各銘柄の oldest（5年前）と latest を取る
first_last = (
    tail6.groupby("code")
         .agg(past=("dps_regular_adj", "first"),
              latest=("dps_regular_adj", "last"))
         .reset_index()
)

# CAGR計算（past<=0 は除外）
first_last["DPS_CAGR_5Y"] = (first_last["latest"] / first_last["past"]) ** (1/5) - 1
first_last.loc[first_last["past"] <= 0, "DPS_CAGR_5Y"] = pd.NA

# resultへ結合
result = result.merge(first_last[["code", "DPS_CAGR_5Y"]], on="code", how="left")
result["DPS_CAGR_5Y"] = (result["DPS_CAGR_5Y"] * 100).round(2)

# UI
# --- フィルター/UI ---
# =========================
# UI（ここから下を置き換え）
# =========================

# result が空ならここで止める（骨組みCSVの段階で落ちない）
if result.empty:
    st.warning("配当データ（dps_regular_adj）が未入力のため、ランキングを計算できません。CSVに配当実績を入れると表示されます。")
    st.stop()

# max_streak（スライダー範囲）
max_streak = int(result["連続増配年数"].max())
max_streak = max(0, max_streak)
st.caption(f"データ内の最大連続増配年数：{max_streak} 年")

# default_min を必ず範囲内に収める
default_min = 3
default_min = min(max(default_min, 0), max_streak)

min_years = st.slider(
    "最低連続増配年数",
    min_value=0,
    max_value=max_streak,
    value=default_min
)

markets = ["ALL"] + sorted([m for m in result["market"].dropna().unique().tolist() if str(m) != ""])
market_sel = st.selectbox("市場", markets)

filtered = result.copy()
if market_sel != "ALL":
    filtered = filtered[filtered["market"] == market_sel]

filtered = filtered[filtered["連続増配年数"] >= min_years].copy()

cols = ["code", "name", "market", "連続増配年数"]
if "DPS_CAGR_5Y" in filtered.columns:
    cols.append("DPS_CAGR_5Y")

# 並び替え：連続増配年数 → CAGR（ある場合）
sort_cols = ["連続増配年数"] + (["DPS_CAGR_5Y"] if "DPS_CAGR_5Y" in cols else [])
filtered = filtered[cols].sort_values(sort_cols, ascending=[False] * len(sort_cols))

st.dataframe(filtered, use_container_width=True)

# デバッグ
with st.expander("デバッグ（必要なときだけ開く）"):
    st.write("データ行数:", len(df))
    st.write("銘柄数:", df["code"].nunique())
    st.write(df.head(20))
