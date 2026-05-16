"""
技术分析模块 - 收益率、风险指标、均线分析、图表绘制
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

from config import RISK_FREE_RATE


_RC_PARAMS = {
    'font.sans-serif': ['PingFang HK', 'Heiti TC', 'STHeiti', 'Arial Unicode MS'],
    'axes.unicode_minus': False,
}


def calc_returns(nav_df):
    """
    计算多周期收益率
    nav_df: 包含 date, nav 列的DataFrame
    返回 dict: {周期: 收益率}
    """
    if nav_df.empty or len(nav_df) < 2:
        return {}

    nav_df = nav_df.sort_values("date").reset_index(drop=True)
    latest = nav_df["nav"].iloc[-1]
    result = {}

    periods = {
        "1月": 21,
        "3月": 63,
        "6月": 126,
        "1年": 252,
        "3年": 756,
        "5年": 1260,
        "10年": 2520,
    }

    for label, days in periods.items():
        if len(nav_df) > days:
            past = nav_df["nav"].iloc[-(days + 1)]
            result[label] = (latest - past) / past
        else:
            result[label] = None

    # 成立以来/回望期内年化收益率
    first = nav_df["nav"].iloc[0]
    n_days = len(nav_df) - 1  # 实际交易日数
    if n_days > 30:
        result["总收益率"] = (latest - first) / first
        result["年化收益率"] = (latest / first) ** (252 / n_days) - 1

    return result


def calc_risk_metrics(nav_df):
    """
    计算风险指标
    返回 dict
    """
    if nav_df.empty or len(nav_df) < 30:
        return {}

    nav_df = nav_df.sort_values("date").reset_index(drop=True)
    nav_df["daily_return"] = nav_df["nav"].pct_change()
    daily_returns = nav_df["daily_return"].dropna()

    # 波动率（年化）
    volatility = daily_returns.std() * np.sqrt(252)

    # 最大回撤
    cummax = nav_df["nav"].cummax()
    drawdown = (nav_df["nav"] - cummax) / cummax
    max_drawdown = drawdown.min()
    max_dd_end_idx = drawdown.idxmin()
    max_dd_start_idx = nav_df["nav"].iloc[:max_dd_end_idx].idxmax()
    max_dd_start_date = nav_df.loc[max_dd_start_idx, "date"]
    max_dd_end_date = nav_df.loc[max_dd_end_idx, "date"]

    # 下行波动率（只计算负收益的标准差）
    downside_returns = daily_returns[daily_returns < 0]
    downside_vol = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0

    # 夏普比率
    annual_return = daily_returns.mean() * 252
    sharpe = (annual_return - RISK_FREE_RATE) / volatility if volatility > 0 else 0

    # 索提诺比率
    sortino = (annual_return - RISK_FREE_RATE) / downside_vol if downside_vol > 0 else 0

    # 卡玛比率
    camma = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

    # 在险价值 VaR (95%)
    var_95 = np.percentile(daily_returns, 5)

    return {
        "年化波动率": volatility,
        "最大回撤": max_drawdown,
        "最大回撤起始": max_dd_start_date,
        "最大回撤结束": max_dd_end_date,
        "下行波动率": downside_vol,
        "夏普比率": sharpe,
        "索提诺比率": sortino,
        "卡玛比率": camma,
        "日VaR(95%)": var_95,
        "日收益率均值": daily_returns.mean(),
        "日收益率标准差": daily_returns.std(),
    }


def calc_moving_averages(nav_df):
    """
    计算均线及金叉死叉信号
    返回 DataFrame（含均线列和信号列）
    """
    if nav_df.empty or len(nav_df) < 250:
        return nav_df

    nav_df = nav_df.sort_values("date").reset_index(drop=True).copy()
    nav_df["ma20"] = nav_df["nav"].rolling(window=20).mean()
    nav_df["ma60"] = nav_df["nav"].rolling(window=60).mean()
    nav_df["ma120"] = nav_df["nav"].rolling(window=120).mean()
    nav_df["ma250"] = nav_df["nav"].rolling(window=250).mean()

    nav_df["ma20_above_ma60"] = nav_df["ma20"] > nav_df["ma60"]
    nav_df["golden_cross"] = (nav_df["ma20_above_ma60"] == True) & (nav_df["ma20_above_ma60"].shift(1) == False)
    nav_df["death_cross"] = (nav_df["ma20_above_ma60"] == False) & (nav_df["ma20_above_ma60"].shift(1) == True)

    return nav_df


def plot_nav_trend(nav_df, fund_name, output_path):
    """
    绘制基金净值走势与均线图
    """
    if nav_df.empty:
        return

    df = calc_moving_averages(nav_df)
    with plt.rc_context(rc=_RC_PARAMS):
        plt.style.use("seaborn-v0_8-whitegrid")
        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(df["date"], df["nav"], label="净值", linewidth=1.2, color="#1f77b4")
        if "ma20" in df.columns:
            ax.plot(df["date"], df["ma20"], label="MA20", linewidth=0.8, alpha=0.7, color="orange")
            ax.plot(df["date"], df["ma60"], label="MA60", linewidth=0.8, alpha=0.7, color="green")
            ax.plot(df["date"], df["ma120"], label="MA120", linewidth=0.8, alpha=0.7, color="red")

        golden = df[df["golden_cross"] == True]
        death = df[df["death_cross"] == True]
        ax.scatter(golden["date"], golden["nav"], marker="^", color="red", s=50, zorder=5, label="金叉")
        ax.scatter(death["date"], death["nav"], marker="v", color="green", s=50, zorder=5, label="死叉")

        ax.set_title(f"{fund_name} 净值走势", fontsize=14, fontweight="bold")
        ax.set_xlabel("日期")
        ax.set_ylabel("单位净值")
        ax.legend(loc="upper left")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)


def plot_drawdown(nav_df, fund_name, output_path):
    """
    绘制回撤图
    """
    if nav_df.empty:
        return

    df = nav_df.sort_values("date").reset_index(drop=True).copy()
    cummax = df["nav"].cummax()
    drawdown = (df["nav"] - cummax) / cummax * 100

    with plt.rc_context(rc=_RC_PARAMS):
        plt.style.use("seaborn-v0_8-whitegrid")
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.fill_between(df["date"], drawdown, 0, color="crimson", alpha=0.4)
        ax.plot(df["date"], drawdown, color="crimson", linewidth=0.8)
        ax.set_title(f"{fund_name} 回撤走势 (%)", fontsize=14, fontweight="bold")
        ax.set_xlabel("日期")
        ax.set_ylabel("回撤幅度 (%)")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)


def plot_rolling_return(nav_df, fund_name, output_path, window=252):
    """
    滚动年化收益率图
    """
    if nav_df.empty or len(nav_df) < window:
        return

    df = nav_df.sort_values("date").reset_index(drop=True).copy()
    df["rolling_return"] = df["nav"].pct_change(window)
    # 将window日收益率年化
    df["rolling_return"] = (1 + df["rolling_return"]) ** (252 / window) - 1

    with plt.rc_context(rc=_RC_PARAMS):
        plt.style.use("seaborn-v0_8-whitegrid")
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(df["date"], df["rolling_return"] * 100, color="steelblue", linewidth=1)
        ax.axhline(y=0, color="black", linestyle="--", linewidth=0.5)
        ax.set_title(f"{fund_name} 滚动年化收益率 ({window}日)", fontsize=14, fontweight="bold")
        ax.set_xlabel("日期")
        ax.set_ylabel("滚动年化收益率 (%)")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)


def analyze_fund_technical(nav_df, fund_name="", output_dir=""):
    """
    对单只基金进行完整技术分析
    返回 dict 包含所有指标
    """
    result = {
        "returns": calc_returns(nav_df),
        "risk": calc_risk_metrics(nav_df),
    }

    if output_dir and fund_name:
        os.makedirs(output_dir, exist_ok=True)
        safe_name = fund_name.replace(" ", "_").replace("/", "_")
        plot_nav_trend(nav_df, fund_name, os.path.join(output_dir, f"{safe_name}_trend.png"))
        plot_drawdown(nav_df, fund_name, os.path.join(output_dir, f"{safe_name}_drawdown.png"))
        plot_rolling_return(nav_df, fund_name, os.path.join(output_dir, f"{safe_name}_rolling.png"))

    return result


def compare_funds_risk_return(nav_dict, output_path):
    """
    绘制多只基金的风险收益散点图
    nav_dict: {基金名: nav_df}
    """
    data = []
    for name, df in nav_dict.items():
        if df.empty or len(df) < 30:
            continue
        returns = calc_returns(df)
        risk = calc_risk_metrics(df)
        if returns and risk:
            data.append({
                "name": name,
                "annual_return": returns.get("年化收益率", 0) * 100,
                "volatility": risk.get("年化波动率", 0) * 100,
            })

    if not data:
        return

    plot_df = pd.DataFrame(data)
    with plt.rc_context(rc=_RC_PARAMS):
        plt.style.use("seaborn-v0_8-whitegrid")
        fig, ax = plt.subplots(figsize=(10, 7))

        for _, row in plot_df.iterrows():
            ax.scatter(row["volatility"], row["annual_return"], s=120, alpha=0.7)
            ax.annotate(row["name"], (row["volatility"], row["annual_return"]),
                        textcoords="offset points", xytext=(5, 5), fontsize=9)

        ax.axhline(y=0, color="black", linestyle="--", linewidth=0.5)
        ax.axvline(x=0, color="black", linestyle="--", linewidth=0.5)
        ax.set_title("基金风险收益分布", fontsize=14, fontweight="bold")
        ax.set_xlabel("年化波动率 (%)")
        ax.set_ylabel("年化收益率 (%)")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
