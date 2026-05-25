"""
AI 投资顾问模块 - 支持 Claude (Anthropic) 和 Kimi (Moonshot) 双后端
"""

import os
import json
import base64
from pathlib import Path
from typing import List, Dict, Optional

# 本地配置文件（base64 编码存储，不提交到 git）
_CONFIG_DIR = Path.home() / ".fund_analyzer"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _encode_key(key: str) -> str:
    return base64.b64encode(key.encode()).decode()


def _decode_key(encoded: str) -> str:
    return base64.b64decode(encoded.encode()).decode()


def load_saved_key(provider: str) -> Optional[str]:
    """从本地配置文件读取已保存的 API Key。"""
    if not _CONFIG_FILE.exists():
        return None
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        encoded = config.get(provider, "")
        return _decode_key(encoded) if encoded else None
    except Exception:
        return None


def save_key(provider: str, key: str) -> None:
    """保存 API Key 到本地配置文件。"""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {}
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass
    config[provider] = _encode_key(key)
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f)


def delete_saved_key(provider: str) -> None:
    """删除已保存的 API Key。"""
    if not _CONFIG_FILE.exists():
        return
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        config.pop(provider, None)
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f)
    except Exception:
        pass

# ==================== Provider 配置 ====================

PROVIDERS = {
    "claude": {
        "name": "Claude (Anthropic)",
        "env_key": "ANTHROPIC_API_KEY",
        "secret_key": "ANTHROPIC_API_KEY",
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-5-haiku-20241022",
        ],
    },
    "kimi": {
        "name": "Kimi (Moonshot)",
        "env_key": "KIMI_API_KEY",
        "secret_key": "KIMI_API_KEY",
        "models": [
            "kimi-k2-6",
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
        ],
    },
}


def get_api_key(provider: str = "claude") -> Optional[str]:
    """获取指定 Provider 的 API Key，优先级：环境变量 > Streamlit secrets > 本地文件。

    Args:
        provider: 提供商标识，"claude" 或 "kimi"

    Returns:
        API Key 字符串，或 None
    """
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return None

    # 1. 环境变量
    key = os.environ.get(cfg["env_key"], "")
    if key:
        return key

    # 2. Streamlit Secrets
    try:
        import streamlit as st
        key = st.secrets.get(cfg["secret_key"], "")
    except Exception:
        pass
    if key:
        return key

    # 3. 本地配置文件
    return load_saved_key(provider)


def get_available_providers() -> List[Dict[str, str]]:
    """返回所有支持的 Provider 列表。"""
    return [{"id": k, "name": v["name"]} for k, v in PROVIDERS.items()]


def get_available_models(provider: str = "claude") -> List[str]:
    """返回指定 Provider 的推荐模型列表。"""
    return PROVIDERS.get(provider, {}).get("models", [])


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


def _call_claude(messages: List[Dict[str, str]], api_key: str, model: str, max_tokens: int) -> str:
    """调用 Anthropic Claude API。"""
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

    response = client.messages.create(**kwargs)
    return response.content[0].text


def _call_kimi(messages: List[Dict[str, str]], api_key: str, model: str, max_tokens: int) -> str:
    """调用 Kimi (Moonshot) API（OpenAI 兼容格式）。"""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError("未安装 openai SDK，请执行：pip install openai") from e

    # 清理 Key 前后空格（常见导致 401 的原因）
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("API Key 为空")

    # 尝试中国大陆和国际两个端点
    base_urls = [
        "https://api.moonshot.cn/v1",
        "https://api.moonshot.ai/v1",
    ]
    last_error = None
    for base_url in base_urls:
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )

            api_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    api_messages.append({"role": "system", "content": msg["content"]})
                else:
                    api_messages.append({"role": msg["role"], "content": msg["content"]})

            response = client.chat.completions.create(
                model=model,
                messages=api_messages,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            # 如果是 401，继续尝试下一个端点
            error_str = str(e)
            if "401" in error_str or "Invalid Authentication" in error_str:
                continue
            # 其他错误直接抛出
            raise
    # 两个端点都失败
    if last_error:
        raise last_error
    raise RuntimeError("所有 Kimi API 端点均无法连接")


def chat_with_advisor(
    messages: List[Dict[str, str]],
    api_key: str,
    provider: str = "claude",
    model: str = "claude-3-5-sonnet-20241022",
    max_tokens: int = 2048,
) -> str:
    """调用指定 Provider 的 API 获取投资顾问回复。

    Args:
        messages: 对话历史，格式 [{"role": "user"/"assistant"/"system", "content": "..."}]
        api_key: API Key
        provider: 提供商，"claude" 或 "kimi"
        model: 模型名称
        max_tokens: 最大生成 token 数

    Returns:
        AI 回复文本
    """
    try:
        if provider == "kimi":
            return _call_kimi(messages, api_key, model, max_tokens)
        else:
            return _call_claude(messages, api_key, model, max_tokens)
    except Exception as e:
        return f"调用 AI 服务失败：{e}"
