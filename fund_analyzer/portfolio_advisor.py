"""
资产配置与投资建议模块 - 组合分析、再平衡、定投策略
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

from config import TARGET_ALLOCATION, RISK_FREE_RATE, MONTHLY_INVESTMENT_BASE, BENCHMARK
from data_fetcher import get_fund_info
from technical_analysis import calc_risk_metrics


_RC_PARAMS = {
    'font.sans-serif': ['PingFang HK', 'Heiti TC', 'STHeiti', 'Arial Unicode MS'],
    'axes.unicode_minus': False,
}

_FUND_TYPE_SHOCK_FACTOR = {
    "股票型": 1.0,
    "混合型": 0.7,
    "债券型": 0.2,
    "指数型": 0.9,
    "QDII": 0.8,
    "货币型": 0.02,
}


def _get_fund_type(code):
    """获取基金类型，返回字符串"""
    info = get_fund_info(code)
    if not info:
        return "混合型"
    for k, v in info.items():
        if "类型" in k or "类别" in k:
            return str(v)
    return "混合型"


def _map_fund_type_to_target(fund_type, target_allocation):
    """将基金类型映射到目标配置中的类别"""
    for type_key in target_allocation:
        if type_key in fund_type:
            return type_key
    return "混合型"


def analyze_portfolio(nav_data_dict, portfolio_config, output_dir=""):
    """
    分析当前投资组合整体情况
    nav_data_dict: {code: nav_df}
    portfolio_config: config.PORTFOLIO
    返回 dict
    """
    values = {}
    total_value = 0
    latest_date = None

    for code, cfg in portfolio_config.items():
        nav_df = nav_data_dict.get(code)
        if nav_df is None or nav_df.empty:
            continue
        latest_nav = nav_df["nav"].iloc[-1]
        shares = cfg.get("shares", 0)
        market_value = latest_nav * shares
        values[code] = {
            "name": cfg.get("name", code),
            "nav": latest_nav,
            "shares": shares,
            "market_value": market_value,
            "cost": cfg.get("cost", 0),
        }
        total_value += market_value
        if latest_date is None or nav_df["date"].iloc[-1] > latest_date:
            latest_date = nav_df["date"].iloc[-1]

    if total_value == 0:
        return {"error": "无有效持仓数据"}

    for code in values:
        values[code]["weight"] = values[code]["market_value"] / total_value
        cost = values[code]["cost"]
        if cost and cost > 0:
            values[code]["return_pct"] = (values[code]["nav"] - cost) / cost
            values[code]["profit"] = (values[code]["nav"] - cost) * values[code]["shares"]
        else:
            values[code]["return_pct"] = 0
            values[code]["profit"] = 0

    # 计算组合收益率序列（按权重加权）
    aligned_returns = None
    for code, nav_df in nav_data_dict.items():
        if nav_df.empty or code not in values:
            continue
        df = nav_df[["date", "nav"]].copy()
        df["daily_return"] = df["nav"].pct_change()
        df = df[["date", "daily_return"]].dropna()
        df = df.rename(columns={"daily_return": code})
        if aligned_returns is None:
            aligned_returns = df
        else:
            aligned_returns = pd.merge(aligned_returns, df, on="date", how="inner")

    if aligned_returns is not None and len(aligned_returns) > 30:
        aligned_returns = aligned_returns.sort_values("date").dropna()
        weights = {code: values[code]["weight"] for code in values if code in aligned_returns.columns}
        weight_sum = sum(weights.values())
        if weight_sum > 0:
            for code in weights:
                weights[code] /= weight_sum

        portfolio_daily = pd.Series(0.0, index=aligned_returns.index)
        for code, w in weights.items():
            if code in aligned_returns.columns:
                portfolio_daily += aligned_returns[code] * w

        portfolio_nav = (1 + portfolio_daily).cumprod()
        portfolio_df = pd.DataFrame({
            "date": aligned_returns["date"],
            "nav": portfolio_nav.values
        })

        risk = calc_risk_metrics(portfolio_df)
        total_return = portfolio_nav.iloc[-1] - 1
        annual_return = portfolio_daily.mean() * 252
    else:
        risk = {}
        total_return = 0
        annual_return = 0
        portfolio_df = pd.DataFrame()

    result = {
        "total_value": round(total_value, 2),
        "latest_date": str(latest_date) if latest_date else "",
        "holdings": values,
        "portfolio_return": round(total_return * 100, 2),
        "portfolio_annual_return": round(annual_return * 100, 2),
        "risk": risk,
    }

    if output_dir:
        plot_portfolio_allocation(result, output_dir)
        if not portfolio_df.empty:
            plot_portfolio_vs_benchmark(portfolio_df, nav_data_dict, output_dir)

    return result


def plot_portfolio_allocation(portfolio_result, output_dir):
    """
    绘制持仓配比饼图
    """
    os.makedirs(output_dir, exist_ok=True)
    holdings = portfolio_result.get("holdings", {})
    if not holdings:
        return

    labels = [h["name"] for h in holdings.values()]
    sizes = [h["market_value"] for h in holdings.values()]

    with plt.rc_context(rc=_RC_PARAMS):
        plt.style.use("seaborn-v0_8-whitegrid")
        fig, ax = plt.subplots(figsize=(8, 8))
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, autopct="%1.1f%%", startangle=90,
            colors=colors, textprops={"fontsize": 10}
        )
        ax.set_title("当前持仓市值占比", fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(output_dir, "portfolio_allocation.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)


def plot_portfolio_vs_benchmark(portfolio_df, nav_data_dict, output_dir):
    """
    绘制组合净值与各基金净值对比图
    """
    os.makedirs(output_dir, exist_ok=True)
    with plt.rc_context(rc=_RC_PARAMS):
        plt.style.use("seaborn-v0_8-whitegrid")
        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(portfolio_df["date"], (portfolio_df["nav"] / portfolio_df["nav"].iloc[0] - 1) * 100,
                label="组合", linewidth=2, color="black")

        colors = plt.cm.tab10(np.linspace(0, 1, len(nav_data_dict)))
        for idx, (code, nav_df) in enumerate(nav_data_dict.items()):
            if nav_df.empty:
                continue
            nav_df = nav_df.sort_values("date").reset_index(drop=True)
            normalized = (nav_df["nav"] / nav_df["nav"].iloc[0] - 1) * 100
            ax.plot(nav_df["date"], normalized, label=code, linewidth=0.8,
                    alpha=0.7, color=colors[idx])

        ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
        ax.set_title("组合与各基金累计收益对比 (%)", fontsize=14, fontweight="bold")
        ax.set_xlabel("日期")
        ax.set_ylabel("累计收益率 (%)")
        ax.legend(loc="upper left")
        fig.tight_layout()
        fig.savefig(os.path.join(output_dir, "portfolio_comparison.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)


def rebalance_advice(portfolio_result, target_allocation=TARGET_ALLOCATION):
    """
    再平衡建议
    target_allocation: 大类资产目标配置比例
    返回 list of dict
    """
    holdings = portfolio_result.get("holdings", {})
    total_value = portfolio_result.get("total_value", 0)
    advice = []

    if not holdings or total_value == 0:
        return advice

    # 获取每只基金的类型并映射到目标配置类别
    fund_type_map = {}
    for code in holdings:
        fund_type = _get_fund_type(code)
        fund_type_map[code] = _map_fund_type_to_target(fund_type, target_allocation)

    # 按类型分组计算当前权重
    type_current_weight = {}
    for code, h in holdings.items():
        t = fund_type_map[code]
        type_current_weight[t] = type_current_weight.get(t, 0) + h["weight"]

    # 计算每只基金的目标权重
    for code, h in holdings.items():
        t = fund_type_map[code]
        type_target = target_allocation.get(t, 0) / 100
        funds_in_type = sum(1 for c in fund_type_map if fund_type_map[c] == t)
        fund_target_weight = type_target / funds_in_type if funds_in_type > 0 else 0

        current_weight = h["weight"]
        deviation = current_weight - fund_target_weight
        if abs(deviation) > 0.05:  # 偏离超过5%
            action = "减持" if deviation > 0 else "增持"
            target_value = total_value * fund_target_weight
            diff = abs(h["market_value"] - target_value)
            advice.append({
                "code": code,
                "name": h["name"],
                "current_weight": round(current_weight * 100, 1),
                "target_weight": round(fund_target_weight * 100, 1),
                "action": action,
                "amount": round(diff, 2),
                "reason": f"当前占比{current_weight*100:.1f}%，目标{fund_target_weight*100:.1f}%（{t}类目标{type_target*100:.0f}%），偏离{abs(deviation)*100:.1f}%",
            })

    return advice


def get_dca_strategy(nav_data_dict, benchmark_code="sh000300"):
    """
    基于估值的定投策略建议
    返回 dict
    """
    from data_fetcher import get_index_pe

    pe_df = get_index_pe(benchmark_code)
    if pe_df.empty:
        return {"error": "无法获取估值数据"}

    pe_col = None
    for c in pe_df.columns:
        if "滚动市盈率" in str(c) and "等权" not in str(c) and "中位数" not in str(c):
            pe_col = c
            break
    if not pe_col:
        for c in pe_df.columns:
            if "静态市盈率" in str(c) and "等权" not in str(c) and "中位数" not in str(c):
                pe_col = c
                break
    if not pe_col:
        for c in pe_df.columns:
            if "市盈率" in str(c) or "PE" in str(c):
                pe_col = c
                break

    if not pe_col:
        return {"error": "无法解析PE数据"}

    pe_series = pd.to_numeric(pe_df[pe_col], errors="coerce").dropna()
    if len(pe_series) == 0:
        return {"error": "PE数据无效"}

    current_pe = float(pe_series.iloc[0])
    pe_history = pe_series.tolist()
    percentile = sum(1 for p in pe_history if p < current_pe) / len(pe_history) * 100

    if percentile < 20:
        multiplier = 2.0
        comment = "当前估值处于历史低位，建议双倍定投，积极布局。"
    elif percentile < 40:
        multiplier = 1.5
        comment = "当前估值偏低，建议1.5倍定投，逐步建仓。"
    elif percentile < 60:
        multiplier = 1.0
        comment = "当前估值处于中性区间，保持常规定投。"
    elif percentile < 80:
        multiplier = 0.7
        comment = "当前估值偏高，建议减少定投金额，谨慎追加。"
    else:
        multiplier = 0.3
        comment = "当前估值处于历史高位，建议大幅缩减定投，考虑逐步止盈。"

    return {
        "current_pe": round(current_pe, 2),
        "pe_percentile": round(percentile, 1),
        "base_amount": MONTHLY_INVESTMENT_BASE,
        "suggested_amount": round(MONTHLY_INVESTMENT_BASE * multiplier),
        "multiplier": multiplier,
        "comment": comment,
    }


def stress_test(nav_data_dict, portfolio_config, scenarios=None):
    """
    压力测试
    scenarios: dict {场景名: 冲击比例}
    """
    if scenarios is None:
        scenarios = {
            "2008年金融危机 (-40%)": -0.4,
            "2015年股灾 (-30%)": -0.3,
            "2020年疫情 (-20%)": -0.2,
            "2018年贸易战 (-25%)": -0.25,
        }

    fund_values = {}
    total_value = 0
    for code, cfg in portfolio_config.items():
        nav_df = nav_data_dict.get(code)
        if nav_df is None or nav_df.empty:
            continue
        latest_nav = nav_df["nav"].iloc[-1]
        shares = cfg.get("shares", 0)
        market_value = latest_nav * shares
        fund_type = _get_fund_type(code)
        fund_values[code] = {
            "market_value": market_value,
            "name": cfg.get("name", code),
            "type": fund_type,
        }
        total_value += market_value

    results = []
    for name, shock in scenarios.items():
        loss = 0
        for code, fv in fund_values.items():
            type_factor = 0.7
            for type_key, factor in _FUND_TYPE_SHOCK_FACTOR.items():
                if type_key in fv["type"]:
                    type_factor = factor
                    break
            loss += fv["market_value"] * abs(shock) * type_factor
        remaining = total_value - loss
        results.append({
            "scenario": name,
            "current_value": round(total_value, 2),
            "estimated_loss": round(loss, 2),
            "remaining_value": round(remaining, 2),
            "loss_pct": round(-loss / total_value * 100, 2) if total_value > 0 else 0,
        })

    return results


def generate_portfolio_advice(nav_data_dict, portfolio_config, fundamental_result, output_dir=""):
    """
    生成完整的资产配置建议
    """
    portfolio = analyze_portfolio(nav_data_dict, portfolio_config, output_dir)
    rebalance = rebalance_advice(portfolio)
    dca = get_dca_strategy(nav_data_dict, benchmark_code=BENCHMARK)
    stress = stress_test(nav_data_dict, portfolio_config)

    cycle = fundamental_result.get("cycle", "复苏")
    cycle_advice = fundamental_result.get("allocation", {})

    return {
        "portfolio": portfolio,
        "rebalance": rebalance,
        "dca": dca,
        "stress_test": stress,
        "cycle": cycle,
        "cycle_advice": cycle_advice,
    }
