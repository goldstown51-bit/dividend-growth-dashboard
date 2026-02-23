import streamlit as st
import pandas as pd

st.title("📈 連続増配ランキング（全市場横断）")

# CSV読み込み
df = pd.read_csv("data/dividend_history.csv")

# 並び替え
df = df.sort_values(["code", "fiscal_year"])

# 連続増配年数を計算
def calc_consecutive_growth(group):
    group = group.sort_values("fiscal_year")
    growth_years = 0
    dps_list = group["dps_regular_adj"].tolist()

    for i in range(len(dps_list)-1, 0, -1):
        if dps_list[i] > dps_list[i-1]:
            growth_years += 1
        else:
            break

    return growth_years

result = (
    df.groupby(["code", "name", "market"])
    .apply(calc_consecutive_growth)
    .reset_index(name="連続増配年数")
)

# フィルター
min_years = st.slider("最低連続増配年数", 0, 20, 3)

filtered = result[result["連続増配年数"] >= min_years]

st.dataframe(
    filtered.sort_values("連続増配年数", ascending=False),
    use_container_width=True
)
