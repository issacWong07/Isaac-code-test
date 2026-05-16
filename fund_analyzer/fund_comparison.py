"""
基金诊断与比较模块 - 同类对比、基金经理评估、费率分析
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os


_RC_PARAMS = {
    'font.sans-serif': ['PingFang HK', 'Heiti TC', 'STHeiti', 'Arial Unicode MS'],
    'axes.unicode_minus': False,
}

from data_fetcher import (
    get_fund_rating, get_fund_manager, get_fund_rank,
    get_fund_nav, get_fund_info
)
from technical_analysis import calc_returns, calc_risk_metrics


def diagnose_fund(fund_code, fund_name=""):
    """
    对单只基金进行全面诊断
    返回 dict
    """
    result = {"code": fund_code, "name": fund_name}

    # 1. 基本信息
    info = get_fund_info(fund_code)
    result["info"] = info

    # 2. 评级
    rating_df = get_fund_rating(fund_code)
    if not rating_df.empty:
        r = rating_df.iloc[0]
        result["rating"] = {
            "morningstar": r.get("rating_morningstar", "N/A"),
            "shanghai": r.get("rating_sh", "N/A"),
            "zhaoshang": r.get("rating_zs", "N/A"),
            "jianan": r.get("rating_ja", "N/A"),
        }
    else:
        result["rating"] = {}

    # 3. 基金经理
    mgr_df = get_fund_manager(fund_code)
    if not mgr_df.empty:
        mgr = mgr_df.iloc[0]
        result["manager"] = {
            "name": mgr.get("name", "N/A"),
            "company": mgr.get("company", "N/A"),
            "tenure_days": mgr.get("tenure_days", 0),
            "tenure_years": round(mgr.get("tenure_days", 0) / 365, 1) if mgr.get("tenure_days") else 0,
            "total_assets": mgr.get("total_assets", "N/A"),
            "best_return": mgr.get("best_return", "N/A"),
        }
    else:
        result["manager"] = {}

    # 4. 净值与风险收益（需要传入nav_df）
    # 这部分在 analyze_funds_comparison 中统一计算

    return result


def compare_with_peers(fund_code, fund_nav_df, top_n=10):
    """
    与同类基金对比
    返回 dict
    """
    # 获取基金类型
    info = get_fund_info(fund_code)
    fund_type = ""
    if info:
        for k, v in info.items():
            if "类型" in k or "类别" in k:
                fund_type = v
                break

    if not fund_type:
        return {"error": "无法获取基金类型"}

    # 简化类型匹配
    category_map = {
        "混合型": "混合型",
        "股票型": "股票型",
        "债券型": "债券型",
        "指数型": "指数型",
        "QDII": "QDII",
        "货币型": "货币型",
    }
    match_category = "全部"
    for key, val in category_map.items():
        if key in fund_type:
            match_category = val
            break

    rank_df = get_fund_rank(category=match_category)
    if rank_df.empty:
        return {"error": "无法获取同类排名数据"}

    # 查找本基金在排名中的位置
    code_col = "代码" if "代码" in rank_df.columns else rank_df.columns[0]
    fund_row = rank_df[rank_df[code_col] == fund_code]
    if fund_row.empty:
        return {"error": "该基金暂无排名数据"}

    # 取前N名对比
    top_df = rank_df.head(top_n)

    return {
        "category": match_category,
        "fund_rank": fund_row.index[0] + 1 if len(fund_row) > 0 else "N/A",
        "top_peers": top_df.to_dict("records"),
    }


def analyze_fund_manager_quality(fund_code):
    """
    评估基金经理质量
    返回 dict
    """
    mgr_df = get_fund_manager(fund_code)
    if mgr_df.empty:
        return {"score": 0, "comment": "无基金经理数据"}

    mgr = mgr_df.iloc[0]
    tenure_years = mgr.get("tenure_days", 0) / 365 if mgr.get("tenure_days") else 0
    best_return = mgr.get("best_return", 0) or 0

    score = 0
    comments = []

    # 从业年限评分 (0-30)
    if tenure_years >= 10:
        score += 30
        comments.append("基金经理从业超过10年，经验丰富")
    elif tenure_years >= 5:
        score += 20
        comments.append("基金经理从业5-10年，经验较丰富")
    elif tenure_years >= 3:
        score += 10
        comments.append("基金经理从业3-5年，经验一般")
    else:
        score += 5
        comments.append("基金经理从业不足3年，经验较浅")

    # 历史最佳回报评分 (0-30)
    if best_return >= 100:
        score += 30
        comments.append(f"历史最佳回报{best_return:.1f}%，业绩突出")
    elif best_return >= 50:
        score += 20
        comments.append(f"历史最佳回报{best_return:.1f}%，业绩良好")
    elif best_return >= 20:
        score += 10
        comments.append(f"历史最佳回报{best_return:.1f}%，业绩一般")
    else:
        comments.append(f"历史最佳回报{best_return:.1f}%，业绩偏弱")

    # 管理规模评分 (0-20)
    assets = mgr.get("total_assets", 0)
    if assets:
        if assets >= 100:
            score += 20
            comments.append("管理规模较大，市场认可度高")
        elif assets >= 50:
            score += 15
            comments.append("管理规模中等")
        elif assets >= 10:
            score += 10
        else:
            score += 5
            comments.append("管理规模较小")

    # 稳定性评分 (0-20)
    if len(mgr_df) == 1:
        score += 20
        comments.append("基金经理稳定，未发生变更")
    else:
        score += 10
        comments.append(f"该基金历任{len(mgr_df)}位基金经理")

    return {
        "score": score,
        "max_score": 100,
        "comments": comments,
        "detail": {
            "tenure_years": round(tenure_years, 1),
            "best_return": best_return,
            "total_assets": assets,
            "manager_count": len(mgr_df),
        }
    }


def analyze_fee_structure(fund_code):
    """
    分析基金费率
    返回 dict
    """
    info = get_fund_info(fund_code)
    if not info:
        return {}

    fees = {}
    for k, v in info.items():
        if "管理费率" in k or "管理费" in k:
            fees["management"] = v
        elif "托管费率" in k or "托管费" in k:
            fees["custody"] = v
        elif "申购费率" in k or "申购费" in k:
            fees["purchase"] = v
        elif "赎回费率" in k or "赎回费" in k:
            fees["redemption"] = v
        elif "销售服务费率" in k:
            fees["service"] = v

    # 给出评价
    comments = []
    mgmt_str = fees.get("management", "")
    if mgmt_str:
        try:
            mgmt_val = float(str(mgmt_str).replace("%", "").replace("年", "").strip())
            if mgmt_val <= 0.5:
                comments.append("管理费率较低，成本控制优秀")
            elif mgmt_val <= 1.0:
                comments.append("管理费率适中")
            else:
                comments.append("管理费率偏高，需关注超额收益能否覆盖成本")
        except Exception:
            pass

    fees["comments"] = comments
    return fees


def plot_fund_diagnosis_summary(fund_results, output_path):
    """
    绘制基金诊断雷达图汇总
    fund_results: {基金名: diagnose_fund结果}
    """
    if not fund_results:
        return

    categories = ["收益率", "风控", "经理", "评级", "费率"]

    with plt.rc_context(rc=_RC_PARAMS):
        fig, ax = plt.subplots(figsize=(10, 7), subplot_kw=dict(polar=True))

        colors = plt.cm.tab10(np.linspace(0, 1, len(fund_results)))

        for idx, (name, result) in enumerate(fund_results.items()):
            values = []
            # 收益率评分 (0-100)
            ret = result.get("technical", {}).get("returns", {})
            annual = ret.get("年化收益率", 0) or 0
            annual_pct = annual * 100
            values.append(min(max((annual_pct + 20) * 2.5, 0), 100))

            # 风控评分 (0-100)
            risk = result.get("technical", {}).get("risk", {})
            sharpe = risk.get("夏普比率", 0) or 0
            values.append(min(max((sharpe + 1) * 50, 0), 100))

            # 经理评分 (0-100)
            mgr = result.get("manager_quality", {})
            values.append(min(max(mgr.get("score", 0), 0), 100))

            # 评级评分 (0-100)
            rating = result.get("rating", {})
            ms = rating.get("morningstar", 0)
            if isinstance(ms, (int, float)) and ms > 0:
                values.append(min(ms * 20, 100))
            else:
                values.append(50)

            # 费率评分 (0-100) - 默认给中等分
            values.append(60)

            values += values[:1]  # 闭合
            angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
            angles += angles[:1]

            ax.plot(angles, values, color=colors[idx], linewidth=1.5, label=name)
            ax.fill(angles, values, color=colors[idx], alpha=0.15)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_ylim(0, 100)
        ax.set_title("基金诊断雷达图", fontsize=14, fontweight="bold", pad=20)
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)


def analyze_funds_comparison(fund_codes, nav_data_dict):
    """
    对多只基金进行对比分析
    fund_codes: {code: name}
    nav_data_dict: {code: nav_df}
    返回 dict
    """
    results = {}
    for code, name in fund_codes.items():
        nav_df = nav_data_dict.get(code, pd.DataFrame())
        diag = diagnose_fund(code, name)

        # 技术指标
        from technical_analysis import analyze_fund_technical
        diag["technical"] = analyze_fund_technical(nav_df)

        # 同类对比
        diag["peer_comparison"] = compare_with_peers(code, nav_df)

        # 经理质量
        diag["manager_quality"] = analyze_fund_manager_quality(code)

        # 费率
        diag["fees"] = analyze_fee_structure(code)

        results[name] = diag

    return results
