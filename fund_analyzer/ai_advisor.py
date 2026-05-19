"""
AI 投资顾问模块 - 基于 Claude API 的智能对话建议
"""

import os
from typing import List, Dict, Optional


def get_api_key() -> Optional[str]:
    """获取 Anthropic API Key，优先级：环境变量 > Streamlit secrets"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    return key if key else None


def build_system_prompt(portfolio: List[dict], results: Optional[dict] = None,
                        sector_report: Optional[dict] = None) -> str:
    """根据当前持仓和分析结果构建系统提示。"""
    lines = [
        "你是一位专业的基金投资顾问，具备深厚的金融知识和市场分析能力。",
        "你的任务是基于用户提供的持仓信息和分析数据，给出专业、客观、谨慎的投资建议。",
        "请始终记住：你的建议仅供参考，不构成实际投资建议，投资有风险。",
        "",
        "=== 用户当前持仓 ===",
    ]
    total_value = 0.0
    for fund in portfolio:
        value = fund.get("shares", 0) * fund.get("cost", 0)
        total_value += value
        lines.append(f"- {fund.get('name', '未知')} ({fund.get('code', '')}): "
                     f"{fund.get('shares', 0)}份, 成本¥{fund.get('cost', 0):.3f}, "
                     f"总投入¥{value:,.0f}")
    lines.append(f"总投入金额：¥{total_value:,.0f}")
    lines.append("")

    if results:
        fundamental = results.get("fundamental_result", {})
        portfolio_advice = results.get("portfolio_advice", {})
        comparison = results.get("comparison_results", {})

        cycle = fundamental.get("cycle", "未知")
        pe = fundamental.get("valuation", {}).get("csi300_pe", {}).get("current", "-")
        pe_percentile = fundamental.get("valuation", {}).get("csi300_pe", {}).get("percentile", "-")
        allocation = fundamental.get("allocation", {})
        reason = allocation.get("理由", "")

        lines.append("=== 最新分析结果 ===")
        lines.append(f"经济周期判断：{cycle}")
        lines.append(f"沪深300市盈率：{pe}（历史分位：{pe_percentile}）")
        lines.append(f"配置理由：{reason}")
        lines.append("")

        dca = portfolio_advice.get("dca", {})
        suggested = dca.get("suggested_amount", 0)
        lines.append(f"定投建议：每月¥{suggested:,.0f}")
        lines.append("")

        lines.append("=== 持仓基金诊断 ===")
        for name, data in comparison.items():
            annual = data.get("returns", {}).get("年化收益率")
            max_dd = data.get("risk", {}).get("最大回撤")
            sharpe = data.get("risk", {}).get("夏普比率")
            mgr_score = data.get("manager", {}).get("score", "-")
            lines.append(
                f"- {name}: 年化收益={annual * 100:.2f}% 最大回撤={max_dd * 100:.2f}% "
                f"夏普={sharpe:.2f} 经理评分={mgr_score}"
            )
        lines.append("")

    if sector_report:
        lines.append("=== 今日市场资讯 ===")
        top_ind = sector_report.get("top_industry", [])
        top_con = sector_report.get("top_concept", [])
        if top_ind:
            lines.append("资金流入最多的行业（Top 5）：")
            for item in top_ind[:5]:
                lines.append(f"  - {item.get('行业', '')}: 净流入{item.get('净流入', 0):+.1f}亿, "
                             f"涨跌幅{item.get('涨跌幅', 0):+.2f}%")
        if top_con:
            lines.append("资金流入最多的概念（Top 5）：")
            for item in top_con[:5]:
                lines.append(f"  - {item.get('概念', '')}: 净流入{item.get('净流入', 0):+.1f}亿, "
                             f"涨跌幅{item.get('涨跌幅', 0):+.2f}%")
        lines.append("")

    lines.append(
        "请基于以上信息回答用户的投资相关问题。回答要求："
        "1. 专业但易懂，避免过度使用术语；"
        "2. 给出具体的数据支撑；"
        "3. 明确提示风险；"
        "4. 如果信息不足，请坦诚告知。"
    )
    return "\n".join(lines)


def chat_with_advisor(
    messages: List[Dict[str, str]],
    api_key: str,
    model: str = "claude-3-5-sonnet-20241022",
    max_tokens: int = 2048,
) -> str:
    """调用 Claude API 获取投资顾问回复。

    Args:
        messages: 对话历史，格式 [{"role": "user"/"assistant", "content": "..."}]
        api_key: Anthropic API Key
        model: 模型名称
        max_tokens: 最大生成token数

    Returns:
        AI 回复文本
    """
    try:
        import anthropic
    except ImportError as e:
        raise ImportError("未安装 anthropic SDK，请执行：pip install anthropic") from e

    client = anthropic.Anthropic(api_key=api_key)

    system = ""
    api_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            system = msg.get("content", "")
        else:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": api_messages,
    }
    if system:
        kwargs["system"] = system

    try:
        response = client.messages.create(**kwargs)
        return response.content[0].text
    except Exception as e:
        return f"调用 AI 服务失败：{e}"


def get_available_models() -> List[str]:
    """返回推荐的可用模型列表。"""
    return [
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
        "claude-3-5-haiku-20241022",
    ]
