"""
每日赛道资讯与持仓关联分析模块
"""

import os
import sys
import difflib

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import pandas as pd
from data_fetcher import (
    get_industry_fund_flow, get_concept_fund_flow,
    get_hot_stocks, get_board_change, get_fund_industry_allocation
)

INDUSTRY_NAME_MAP = {
    "制造业": "专用设备",
    "金融业": "银行",
    "信息传输、软件和信息技术服务业": "软件开发",
    "房地产业": "房地产开发",
    "批发和零售业": "商业百货",
    "交通运输、仓储和邮政业": "物流行业",
    "建筑业": "工程建设",
    "采矿业": "贵金属",
    "农、林、牧、渔业": "农牧饲渔",
    "电力、热力、燃气及水生产和供应业": "电力行业",
    "文化、体育和娱乐业": "文化传媒",
    "卫生和社会工作": "医疗服务",
    "住宿和餐饮业": "旅游酒店",
    "科学研究和技术服务业": "专业服务",
    "教育": "教育",
    "综合": "综合行业",
}


def fetch_daily_sector_data():
    """获取每日赛道数据，返回 dict"""
    industry = get_industry_fund_flow()
    concept = get_concept_fund_flow()
    hot = get_hot_stocks()
    change = get_board_change()
    return {
        "industry": industry,
        "concept": concept,
        "hot": hot,
        "change": change,
    }


def analyze_fund_sectors(fund_code, fund_name):
    """获取单只基金的行业配置"""
    df = get_fund_industry_allocation(fund_code)
    if df.empty:
        return []
    sectors = []
    for col in df.columns:
        if any(k in str(col) for k in ["行业", "板块", "名称"]):
            for _, row in df.iterrows():
                val = row.get(col, "")
                if val and str(val) != "nan":
                    sectors.append(str(val))
            break
    return list(dict.fromkeys(sectors))


def _match_name(series, target, cutoff=0.6):
    """在Series中匹配名称，优先精确匹配，其次模糊匹配"""
    exact = series[series == target]
    if not exact.empty:
        return exact.index[0]
    matches = difflib.get_close_matches(target, series.tolist(), n=1, cutoff=cutoff)
    if matches:
        idx = series[series == matches[0]].index
        if not idx.empty:
            return idx[0]
    return None


def match_sectors_to_market(fund_sectors, industry_df, concept_df):
    """
    将基金持仓行业与当日市场数据进行匹配
    返回匹配到的市场数据子集
    """
    matched = []
    for sector in fund_sectors:
        mapped = INDUSTRY_NAME_MAP.get(sector, sector)

        if not industry_df.empty and "行业" in industry_df.columns:
            idx = _match_name(industry_df["行业"], mapped)
            if idx is not None:
                matched.append({"来源": "行业", **industry_df.loc[idx].to_dict()})
                continue
            idx = _match_name(industry_df["行业"], sector)
            if idx is not None:
                matched.append({"来源": "行业", **industry_df.loc[idx].to_dict()})
                continue

        if not concept_df.empty and "概念" in concept_df.columns:
            idx = _match_name(concept_df["概念"], mapped)
            if idx is not None:
                matched.append({"来源": "概念", **concept_df.loc[idx].to_dict()})
                continue

    return matched


def generate_sector_advice(matched_sectors):
    """根据匹配到的赛道数据生成建议"""
    if not matched_sectors:
        return "暂无对应赛道数据。"

    advices = []
    net_in_total = 0
    for item in matched_sectors:
        net = item.get("净流入", 0) or 0
        change_pct = item.get("涨跌幅", 0) or 0
        name = item.get("行业", item.get("概念", "未知"))
        net_in_total += net
        direction = "流入" if net > 0 else "流出"
        trend = "上涨" if change_pct > 0 else "下跌"
        if net > 20:
            advices.append(f"「{name}」资金大幅{direction}({net:.1f}亿)，板块{trend}{change_pct:.2f}%，短期热度高，可持有观望。")
        elif net > 5:
            advices.append(f"「{name}」资金温和{direction}({net:.1f}亿)，板块{trend}{change_pct:.2f}%，趋势平稳。")
        elif net < -20:
            advices.append(f"「{name}」资金大幅{direction}({abs(net):.1f}亿)，板块{trend}{abs(change_pct):.2f}%，短期承压，注意风险。")
        elif net < -5:
            advices.append(f"「{name}」资金温和{direction}({abs(net):.1f}亿)，板块{trend}{abs(change_pct):.2f}%，谨慎观察。")
        else:
            advices.append(f"「{name}」资金流动平缓({net:.1f}亿)，板块{trend}{change_pct:.2f}%，中性。")

    if net_in_total > 30:
        summary = "整体看，持仓涉及赛道今日资金大幅净流入，市场情绪积极。"
    elif net_in_total > 10:
        summary = "整体看，持仓涉及赛道今日资金温和净流入，情绪偏乐观。"
    elif net_in_total < -30:
        summary = "整体看，持仓涉及赛道今日资金大幅净流出，需警惕回调风险。"
    elif net_in_total < -10:
        summary = "整体看，持仓涉及赛道今日资金温和净流出，建议谨慎。"
    else:
        summary = "整体看，持仓涉及赛道今日资金流动平稳，市场分歧不大。"

    return "\n".join(advices) + "\n\n**总结**：" + summary


def build_daily_sector_report(portfolio_dict):
    """
    为持仓组合构建完整的每日赛道报告
    portfolio_dict: {code: {"name": ..., ...}}
    返回 dict
    """
    sector_data = fetch_daily_sector_data()
    industry_df = sector_data["industry"]
    concept_df = sector_data["concept"]
    hot_df = sector_data["hot"]
    change_df = sector_data["change"]

    fund_sector_advice = {}
    all_matched_sectors = []

    for code, cfg in portfolio_dict.items():
        name = cfg.get("name", code)
        sectors = analyze_fund_sectors(code, name)
        matched = match_sectors_to_market(sectors, industry_df, concept_df)
        all_matched_sectors.extend(matched)
        advice = generate_sector_advice(matched)
        fund_sector_advice[name] = {
            "sectors": sectors,
            "matched": matched,
            "advice": advice,
        }

    seen = set()
    unique_matched = []
    for m in all_matched_sectors:
        key = m.get("行业", m.get("概念", ""))
        if key and key not in seen:
            seen.add(key)
            unique_matched.append(m)

    top_industry = []
    if not industry_df.empty:
        top_industry = industry_df.nlargest(10, "净流入")[["行业", "涨跌幅", "净流入", "领涨股", "领涨股涨幅"]].to_dict("records")

    top_concept = []
    if not concept_df.empty:
        top_concept = concept_df.nlargest(10, "净流入")[["概念", "涨跌幅", "净流入", "领涨股", "领涨股涨幅"]].to_dict("records")

    hot_stocks = []
    if not hot_df.empty:
        hot_stocks = hot_df.head(15).to_dict("records")

    board_changes = []
    if not change_df.empty:
        board_changes = change_df.nlargest(10, "涨跌幅")[["板块名称", "涨跌幅", "主力净流入", "领涨股名称"]].to_dict("records")

    return {
        "fund_sector_advice": fund_sector_advice,
        "all_matched_sectors": unique_matched,
        "top_industry": top_industry,
        "top_concept": top_concept,
        "hot_stocks": hot_stocks,
        "board_changes": board_changes,
    }
