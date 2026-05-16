"""
基本面分析模块 - 宏观经济、市场估值、经济周期判断
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

from config import RISK_FREE_RATE
from data_fetcher import (
    get_macro_gdp, get_macro_cpi, get_macro_pmi, get_macro_lpr,
    get_market_index, get_index_pe
)


_RC_PARAMS = {
    'font.sans-serif': ['PingFang HK', 'Heiti TC', 'STHeiti', 'Arial Unicode MS'],
    'axes.unicode_minus': False,
}


def analyze_macro_economy():
    """
    宏观经济分析
    返回 dict: 包含GDP、CPI、PMI、LPR的最新数据与趋势
    """
    result = {}

    # GDP
    gdp_df = get_macro_gdp()
    if not gdp_df.empty:
        gdp_df = gdp_df.sort_values(gdp_df.columns[0], ascending=False).reset_index(drop=True)
        latest = gdp_df.iloc[0]
        result["gdp"] = {
            "latest_quarter": str(latest.iloc[0]),
            "gdp_yoy": float(latest["国内生产总值-同比增长"]) if "国内生产总值-同比增长" in latest else None,
            "trend": gdp_df["国内生产总值-同比增长"].head(8).tolist() if "国内生产总值-同比增长" in gdp_df.columns else [],
        }

    # CPI
    cpi_df = get_macro_cpi()
    if not cpi_df.empty:
        cpi_df = cpi_df.sort_values(cpi_df.columns[0], ascending=False).reset_index(drop=True)
        latest = cpi_df.iloc[0]
        result["cpi"] = {
            "latest_month": str(latest.iloc[0]),
            "cpi_yoy": float(latest["全国-居民消费价格指数-同比增长"]) if "全国-居民消费价格指数-同比增长" in latest else None,
            "trend": cpi_df["全国-居民消费价格指数-同比增长"].head(12).tolist() if "全国-居民消费价格指数-同比增长" in cpi_df.columns else [],
        }

    # PMI
    pmi_df = get_macro_pmi()
    if not pmi_df.empty:
        pmi_df = pmi_df.sort_values(pmi_df.columns[0], ascending=False).reset_index(drop=True)
        latest = pmi_df.iloc[0]
        result["pmi"] = {
            "latest_month": str(latest.iloc[0]),
            "pmi": float(latest["制造业-指数"]) if "制造业-指数" in latest else None,
            "trend": pmi_df["制造业-指数"].head(12).tolist() if "制造业-指数" in pmi_df.columns else [],
        }

    # LPR
    lpr_df = get_macro_lpr()
    if not lpr_df.empty:
        lpr_df = lpr_df.sort_values(lpr_df.columns[0], ascending=False).reset_index(drop=True)
        latest = lpr_df.iloc[0]
        result["lpr"] = {
            "latest_date": str(latest.iloc[0]),
            "lpr_1y": float(latest["1年期-LPR"]) if "1年期-LPR" in latest else None,
            "lpr_5y": float(latest["5年期以上-LPR"]) if "5年期以上-LPR" in latest else None,
            "trend_1y": lpr_df["1年期-LPR"].head(12).tolist() if "1年期-LPR" in lpr_df.columns else [],
        }

    return result


def analyze_market_valuation():
    """
    市场估值分析
    返回 dict: PE/PB分位点、股债性价比等
    """
    result = {}

    pe_df = get_index_pe("sh000300")
    if not pe_df.empty:
        latest = pe_df.iloc[0]
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
        if pe_col:
            pe_series = pd.to_numeric(pe_df[pe_col], errors="coerce").dropna()
            if len(pe_series) > 0:
                current_pe = float(pe_series.iloc[0])
                pe_history = pe_series.tolist()
                pe_percentile = sum(1 for p in pe_history if p < current_pe) / len(pe_history) * 100 if pe_history else 50
                result["csi300_pe"] = {
                    "current": round(current_pe, 2),
                    "percentile": round(pe_percentile, 1),
                    "history_mean": round(np.mean(pe_history), 2),
                    "history_median": round(np.median(pe_history), 2),
                }

    # 股债性价比 (ERP = 1/PE - 无风险利率)
    # 使用config中的RISK_FREE_RATE作为无风险利率
    if "csi300_pe" in result:
        current_pe = result["csi300_pe"]["current"]
        bond_yield = RISK_FREE_RATE
        erp = (1 / current_pe) - bond_yield if current_pe > 0 else 0
        result["erp"] = {
            "value": round(erp * 100, 2),
            "bond_yield": round(bond_yield * 100, 2),
            "earnings_yield": round((1 / current_pe) * 100, 2),
        }

    return result


def judge_economic_cycle(macro_data):
    """
    基于美林时钟判断经济周期
    返回 str: 复苏/过热/滞胀/衰退
    """
    gdp_yoy = macro_data.get("gdp", {}).get("gdp_yoy")
    cpi_yoy = macro_data.get("cpi", {}).get("cpi_yoy")
    pmi = macro_data.get("pmi", {}).get("pmi")

    if gdp_yoy is None or cpi_yoy is None:
        return "数据不足，无法判断"

    gdp_high = gdp_yoy > 3.0
    cpi_high = cpi_yoy > 2.0

    if gdp_high and not cpi_high:
        cycle = "复苏"
    elif gdp_high and cpi_high:
        cycle = "过热"
    elif not gdp_high and cpi_high:
        cycle = "滞胀"
    else:
        cycle = "衰退"

    # PMI作为辅助验证：仅在边界情况做单档微调
    if pmi is not None:
        if pmi > 50 and cycle == "衰退":
            cycle = "复苏"
        elif pmi < 50 and cycle == "过热":
            cycle = "滞胀"

    return cycle


def allocation_advice_by_cycle(cycle):
    """
    根据经济周期给出大类资产配置建议
    返回 dict
    """
    advice = {
        "复苏": {
            "股票": "高配 (50-70%)",
            "债券": "标配 (20-30%)",
            "商品": "低配 (5-10%)",
            "现金": "低配 (5-10%)",
            "理由": "经济上行+通胀低位，企业盈利改善，股票资产表现最佳。",
        },
        "过热": {
            "股票": "标配 (40-50%)",
            "债券": "低配 (10-20%)",
            "商品": "高配 (20-30%)",
            "现金": "标配 (10-20%)",
            "理由": "经济上行+通胀高企，商品受益，债券承压，股票需精选。",
        },
        "滞胀": {
            "股票": "低配 (20-30%)",
            "债券": "低配 (20-30%)",
            "商品": "标配 (20-30%)",
            "现金": "高配 (20-30%)",
            "理由": "经济下行+通胀高企，现金为王，防御为主。",
        },
        "衰退": {
            "股票": "低配 (20-30%)",
            "债券": "高配 (50-60%)",
            "商品": "低配 (0-5%)",
            "现金": "标配 (10-20%)",
            "理由": "经济下行+通胀低位，利率下行利好债券，股票等待底部信号。",
        },
    }
    return advice.get(cycle, advice["复苏"])


def plot_macro_trends(macro_data, output_dir):
    """
    绘制宏观经济趋势图
    """
    os.makedirs(output_dir, exist_ok=True)

    with plt.rc_context(rc=_RC_PARAMS):
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        plt.style.use("seaborn-v0_8-whitegrid")

        if "gdp" in macro_data and macro_data["gdp"]["trend"]:
            ax = axes[0, 0]
            values = macro_data["gdp"]["trend"][::-1]
            ax.plot(values, marker="o", color="steelblue")
            ax.set_title("GDP 同比增长 (%)")
            ax.axhline(y=5, color="red", linestyle="--", alpha=0.5, label="5%目标")
            ax.legend()

        if "cpi" in macro_data and macro_data["cpi"]["trend"]:
            ax = axes[0, 1]
            values = macro_data["cpi"]["trend"][::-1]
            ax.plot(values, marker="o", color="orange")
            ax.set_title("CPI 同比增长 (%)")
            ax.axhline(y=2, color="red", linestyle="--", alpha=0.5, label="2%温和通胀")
            ax.legend()

        if "pmi" in macro_data and macro_data["pmi"]["trend"]:
            ax = axes[1, 0]
            values = macro_data["pmi"]["trend"][::-1]
            ax.plot(values, marker="o", color="green")
            ax.set_title("制造业 PMI")
            ax.axhline(y=50, color="red", linestyle="--", alpha=0.5, label="荣枯线")
            ax.legend()

        if "lpr" in macro_data and macro_data["lpr"]["trend_1y"]:
            ax = axes[1, 1]
            values = macro_data["lpr"]["trend_1y"][::-1]
            ax.plot(values, marker="o", color="purple")
            ax.set_title("1年期 LPR (%)")

        fig.suptitle("宏观经济指标趋势", fontsize=16, fontweight="bold")
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        fig.savefig(os.path.join(output_dir, "macro_trends.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)


def analyze_fundamental(output_dir=""):
    """
    执行完整基本面分析
    返回 dict: 包含宏观、估值、周期判断、配置建议
    """
    macro = analyze_macro_economy()
    valuation = analyze_market_valuation()
    cycle = judge_economic_cycle(macro)
    allocation = allocation_advice_by_cycle(cycle)

    result = {
        "macro": macro,
        "valuation": valuation,
        "cycle": cycle,
        "allocation": allocation,
    }

    if output_dir:
        plot_macro_trends(macro, output_dir)

    return result
