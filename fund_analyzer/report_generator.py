"""
报告生成模块 - 生成HTML/Markdown分析报告
"""

import os
import base64
import html
from datetime import datetime

from config import get_output_dir


def img_to_base64(path):
    """将图片转为base64嵌入HTML"""
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        data = f.read()
    ext = os.path.splitext(path)[1].replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{base64.b64encode(data).decode()}"


def format_pct(val):
    """格式化百分比"""
    if val is None:
        return "N/A"
    return f"{val * 100:.2f}%"


def format_num(val, decimals=2):
    """格式化数字"""
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"


def _esc(val):
    """HTML转义，None返回空字符串"""
    if val is None:
        return ""
    return html.escape(str(val))


def _build_html_content(tech_results, fundamental_result, comparison_results,
                        portfolio_advice, chart_dir):
    """构建HTML报告内容，返回字符串"""
    html_parts = []
    html_parts.append("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>基金投资分析报告</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 0; padding: 0; background: #f5f6fa; color: #333; }
        .container { max-width: 960px; margin: 0 auto; padding: 20px; }
        h1 { text-align: center; color: #2c3e50; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #7f8c8d; margin-bottom: 30px; }
        .section { background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
        h2 { color: #2980b9; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; margin-top: 0; }
        h3 { color: #34495e; margin-top: 20px; }
        table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 14px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background: #f8f9fa; font-weight: 600; }
        .highlight { background: #e8f4fd; padding: 12px; border-radius: 6px; margin: 10px 0; }
        .warning { background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 10px 0; }
        .danger { background: #f8d7da; border-left: 4px solid #dc3545; padding: 12px; margin: 10px 0; }
        .success { background: #d4edda; border-left: 4px solid #28a745; padding: 12px; margin: 10px 0; }
        .chart { text-align: center; margin: 16px 0; }
        .chart img { max-width: 100%; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .metric { text-align: center; padding: 16px; background: #f8f9fa; border-radius: 6px; }
        .metric-value { font-size: 24px; font-weight: bold; color: #2980b9; }
        .metric-label { font-size: 12px; color: #7f8c8d; margin-top: 4px; }
        ul { line-height: 1.8; }
        footer { text-align: center; color: #95a5a6; font-size: 12px; margin-top: 40px; padding-bottom: 20px; }
    </style>
</head>
<body>
<div class="container">
""")

    # 标题
    now = datetime.now().strftime("%Y年%m月%d日")
    html_parts.append(f"<h1>基金投资分析报告</h1>")
    html_parts.append(f"<p class='subtitle'>生成日期：{now} | 数据周期：近10年回望</p>")

    # ==================== 执行摘要 ====================
    html_parts.append("<div class='section'>")
    html_parts.append("<h2>一、执行摘要</h2>")

    cycle = fundamental_result.get("cycle", "未知")
    cycle_color = {"复苏": "success", "过热": "warning", "滞胀": "danger", "衰退": "danger"}.get(cycle, "highlight")
    html_parts.append(f"""
    <div class="{cycle_color}">
        <strong>当前经济周期判断：{_esc(cycle)}</strong><br>
        {_esc(fundamental_result.get("allocation", {}).get("理由", ""))}
    </div>
    """)

    # 组合概况
    portfolio = portfolio_advice.get("portfolio", {})
    if "total_value" in portfolio:
        html_parts.append(f"""
        <div class="grid-2" style="margin-top:16px;">
            <div class="metric">
                <div class="metric-value">¥{format_num(portfolio.get('total_value', 0), 0)}</div>
                <div class="metric-label">组合总市值</div>
            </div>
            <div class="metric">
                <div class="metric-value">{portfolio.get('portfolio_return', 'N/A')}%</div>
                <div class="metric-label">组合累计收益</div>
            </div>
        </div>
        """)

    # 核心建议
    dca = portfolio_advice.get("dca", {})
    if "suggested_amount" in dca:
        html_parts.append(f"""
        <div class="highlight" style="margin-top:16px;">
            <strong>定投建议：</strong>基于沪深300当前PE {dca.get('current_pe', 'N/A')}（历史分位 {dca.get('pe_percentile', 'N/A')}%），
            建议每月定投 <strong>¥{dca.get('suggested_amount', 'N/A')}</strong>（基准¥{dca.get('base_amount', 'N/A')} × {dca.get('multiplier', 'N/A')}倍）。<br>
            {dca.get('comment', '')}
        </div>
        """)

    html_parts.append("</div>")

    # ==================== 市场概览 ====================
    html_parts.append("<div class='section'>")
    html_parts.append("<h2>二、市场概览</h2>")

    macro = fundamental_result.get("macro", {})
    html_parts.append("<h3>2.1 宏观经济指标</h3>")
    html_parts.append("<table>")
    html_parts.append("<tr><th>指标</th><th>最新值</th><th>时间</th></tr>")
    if "gdp" in macro:
        gdp = macro["gdp"]
        html_parts.append(f"<tr><td>GDP同比增长</td><td>{_esc(gdp.get('gdp_yoy', 'N/A'))}%</td><td>{_esc(gdp.get('latest_quarter', 'N/A'))}</td></tr>")
    if "cpi" in macro:
        cpi = macro["cpi"]
        html_parts.append(f"<tr><td>CPI同比增长</td><td>{_esc(cpi.get('cpi_yoy', 'N/A'))}%</td><td>{_esc(cpi.get('latest_month', 'N/A'))}</td></tr>")
    if "pmi" in macro:
        pmi = macro["pmi"]
        html_parts.append(f"<tr><td>制造业PMI</td><td>{_esc(pmi.get('pmi', 'N/A'))}</td><td>{_esc(pmi.get('latest_month', 'N/A'))}</td></tr>")
    if "lpr" in macro:
        lpr = macro["lpr"]
        html_parts.append(f"<tr><td>1年期LPR</td><td>{_esc(lpr.get('lpr_1y', 'N/A'))}%</td><td>{_esc(lpr.get('latest_date', 'N/A'))}</td></tr>")
        html_parts.append(f"<tr><td>5年期以上LPR</td><td>{_esc(lpr.get('lpr_5y', 'N/A'))}%</td><td>{_esc(lpr.get('latest_date', 'N/A'))}</td></tr>")
    html_parts.append("</table>")

    # 宏观趋势图
    macro_chart = os.path.join(chart_dir, "macro_trends.png")
    if os.path.exists(macro_chart):
        html_parts.append(f"<div class='chart'><img src='{img_to_base64(macro_chart)}' alt='宏观趋势'></div>")

    # 估值
    valuation = fundamental_result.get("valuation", {})
    html_parts.append("<h3>2.2 市场估值</h3>")
    if "csi300_pe" in valuation:
        pe = valuation["csi300_pe"]
        html_parts.append(f"""
        <div class="highlight">
            <strong>沪深300 PE-TTM：</strong>{pe.get('current', 'N/A')} |
            历史分位：<strong>{pe.get('percentile', 'N/A')}%</strong> |
            历史均值：{pe.get('history_mean', 'N/A')} |
            历史中位数：{pe.get('history_median', 'N/A')}
        </div>
        """)
    if "erp" in valuation:
        erp = valuation["erp"]
        html_parts.append(f"""
        <div class="highlight">
            <strong>股债性价比 (ERP)：</strong>{erp.get('value', 'N/A')}% |
            盈利收益率：{erp.get('earnings_yield', 'N/A')}% |
            债券收益率：{erp.get('bond_yield', 'N/A')}%
        </div>
        """)

    html_parts.append("</div>")

    # ==================== 持仓基金诊断 ====================
    html_parts.append("<div class='section'>")
    html_parts.append("<h2>三、持仓基金逐一诊断</h2>")

    for name, comp in comparison_results.items():
        html_parts.append(f"<h3>3.{list(comparison_results.keys()).index(name)+1} {_esc(name)} ({_esc(comp.get('code', ''))})</h3>")

        # 技术指标
        tech = comp.get("technical", {})
        returns = tech.get("returns", {})
        risk = tech.get("risk", {})

        html_parts.append("<table>")
        html_parts.append("<tr><th>指标</th><th>数值</th><th>指标</th><th>数值</th></tr>")
        html_parts.append(f"""
        <tr>
            <td>近1月收益</td><td>{format_pct(returns.get('1月'))}</td>
            <td>年化波动率</td><td>{format_pct(risk.get('年化波动率'))}</td>
        </tr>
        <tr>
            <td>近1年收益</td><td>{format_pct(returns.get('1年'))}</td>
            <td>最大回撤</td><td>{format_pct(risk.get('最大回撤'))}</td>
        </tr>
        <tr>
            <td>年化收益率</td><td>{format_pct(returns.get('年化收益率'))}</td>
            <td>夏普比率</td><td>{format_num(risk.get('夏普比率'))}</td>
        </tr>
        <tr>
            <td>总收益率</td><td>{format_pct(returns.get('总收益率'))}</td>
            <td>卡玛比率</td><td>{format_num(risk.get('卡玛比率'))}</td>
        </tr>
        """)
        html_parts.append("</table>")

        # 评级
        rating = comp.get("rating", {})
        if rating:
            html_parts.append("<p><strong>基金评级：</strong>")
            parts = []
            if rating.get("morningstar") and rating["morningstar"] != "N/A":
                parts.append(f"晨星 {rating['morningstar']}星")
            if rating.get("shanghai") and rating["shanghai"] != "N/A":
                parts.append(f"上海证券 {rating['shanghai']}星")
            html_parts.append(" | ".join(parts) + "</p>")

        # 基金经理
        mgr = comp.get("manager_quality", {})
        if mgr:
            html_parts.append(f"<p><strong>基金经理评分：</strong>{mgr.get('score', 'N/A')}/100</p>")
            if mgr.get("comments"):
                html_parts.append("<ul>")
                for c in mgr["comments"][:3]:
                    html_parts.append(f"<li>{_esc(c)}</li>")
                html_parts.append("</ul>")

        # 图表
        safe_name = name.replace(" ", "_").replace("/", "_")
        trend_chart = os.path.join(chart_dir, f"{safe_name}_trend.png")
        dd_chart = os.path.join(chart_dir, f"{safe_name}_drawdown.png")
        if os.path.exists(trend_chart):
            html_parts.append(f"<div class='chart'><img src='{img_to_base64(trend_chart)}' alt='净值走势'></div>")
        if os.path.exists(dd_chart):
            html_parts.append(f"<div class='chart'><img src='{img_to_base64(dd_chart)}' alt='回撤图'></div>")

    html_parts.append("</div>")

    # ==================== 组合整体分析 ====================
    html_parts.append("<div class='section'>")
    html_parts.append("<h2>四、组合整体分析</h2>")

    if "total_value" in portfolio:
        html_parts.append("<h3>4.1 持仓结构</h3>")
        html_parts.append("<table>")
        html_parts.append("<tr><th>基金</th><th>份额</th><th>最新净值</th><th>市值</th><th>占比</th><th>成本收益率</th></tr>")
        for code, h in portfolio.get("holdings", {}).items():
            html_parts.append(f"""
            <tr>
                <td>{_esc(h.get('name', code))}</td>
                <td>{h.get('shares', 0)}</td>
                <td>{format_num(h.get('nav'))}</td>
                <td>¥{format_num(h.get('market_value'))}</td>
                <td>{format_pct(h.get('weight'))}</td>
                <td>{format_pct(h.get('return_pct'))}</td>
            </tr>
            """)
        html_parts.append("</table>")

        # 组合风险指标
        risk = portfolio.get("risk", {})
        html_parts.append("<h3>4.2 组合风险指标</h3>")
        html_parts.append("<div class='grid-2'>")
        html_parts.append(f"""
            <div class="metric"><div class="metric-value">{format_pct(risk.get('年化波动率'))}</div><div class="metric-label">年化波动率</div></div>
            <div class="metric"><div class="metric-value">{format_pct(risk.get('最大回撤'))}</div><div class="metric-label">最大回撤</div></div>
            <div class="metric"><div class="metric-value">{format_num(risk.get('夏普比率'))}</div><div class="metric-label">夏普比率</div></div>
            <div class="metric"><div class="metric-value">{format_num(risk.get('卡玛比率'))}</div><div class="metric-label">卡玛比率</div></div>
        """)
        html_parts.append("</div>")

        # 组合图表
        alloc_chart = os.path.join(chart_dir, "portfolio_allocation.png")
        comp_chart = os.path.join(chart_dir, "portfolio_comparison.png")
        if os.path.exists(alloc_chart):
            html_parts.append(f"<div class='chart'><img src='{img_to_base64(alloc_chart)}' alt='持仓占比'></div>")
        if os.path.exists(comp_chart):
            html_parts.append(f"<div class='chart'><img src='{img_to_base64(comp_chart)}' alt='组合对比'></div>")

    html_parts.append("</div>")

    # ==================== 调仓与配置建议 ====================
    html_parts.append("<div class='section'>")
    html_parts.append("<h2>五、调仓与配置建议</h2>")

    # 再平衡
    rebalance = portfolio_advice.get("rebalance", [])
    if rebalance:
        html_parts.append("<h3>5.1 再平衡建议</h3>")
        html_parts.append("<table>")
        html_parts.append("<tr><th>基金</th><th>当前占比</th><th>目标占比</th><th>操作建议</th><th>金额</th><th>理由</th></tr>")
        for r in rebalance:
            html_parts.append(f"""
            <tr>
                <td>{_esc(r.get('name', ''))}</td>
                <td>{r.get('current_weight', '')}%</td>
                <td>{r.get('target_weight', '')}%</td>
                <td><strong>{_esc(r.get('action', ''))}</strong></td>
                <td>¥{format_num(r.get('amount'))}</td>
                <td>{_esc(r.get('reason', ''))}</td>
            </tr>
            """)
        html_parts.append("</table>")
    else:
        html_parts.append("<div class='success'>当前持仓比例较为均衡，暂无再平衡需求。</div>")

    # 大类资产配置
    cycle_advice = portfolio_advice.get("cycle_advice", {})
    if cycle_advice:
        html_parts.append("<h3>5.2 大类资产配置方向（基于经济周期）</h3>")
        html_parts.append("<table>")
        html_parts.append("<tr><th>资产类别</th><th>建议配置</th></tr>")
        for asset, advice in cycle_advice.items():
            if asset != "理由":
                html_parts.append(f"<tr><td>{_esc(asset)}</td><td>{_esc(advice)}</td></tr>")
        html_parts.append("</table>")
        html_parts.append(f"<p><strong>逻辑：</strong>{_esc(cycle_advice.get('理由', ''))}</p>")

    # 压力测试
    stress = portfolio_advice.get("stress_test", [])
    if stress:
        html_parts.append("<h3>5.3 压力测试</h3>")
        html_parts.append("<table>")
        html_parts.append("<tr><th>压力情景</th><th>当前市值</th><th>预估亏损</th><th>剩余市值</th></tr>")
        for s in stress:
            html_parts.append(f"""
            <tr>
                <td>{_esc(s.get('scenario', ''))}</td>
                <td>¥{format_num(s.get('current_value'))}</td>
                <td style="color:#c0392b">¥{format_num(s.get('estimated_loss'))}</td>
                <td>¥{format_num(s.get('remaining_value'))}</td>
            </tr>
            """)
        html_parts.append("</table>")

    html_parts.append("</div>")

    # ==================== 风险提示 ====================
    html_parts.append("<div class='section'>")
    html_parts.append("<h2>六、风险提示</h2>")
    html_parts.append("""
    <ul>
        <li><strong>市场风险：</strong>基金投资受股市、债市波动影响，过往业绩不代表未来表现。</li>
        <li><strong>模型风险：</strong>本报告基于历史数据和简化模型生成，不构成投资建议。</li>
        <li><strong>数据延迟：</strong>部分数据可能存在T+1或更长的延迟，请以官方披露为准。</li>
        <li><strong>个性化差异：</strong>本报告未考虑您的个人税收、流动性需求、投资期限等具体因素。</li>
        <li><strong>集中度风险：</strong>如组合中单一基金或行业占比过高，需警惕尾部风险。</li>
    </ul>
    """)
    html_parts.append("</div>")

    html_parts.append(f"<footer>本报告由基金投资分析系统自动生成 | {now}</footer>")
    html_parts.append("</div></body></html>")

    return "\n".join(html_parts)


def generate_html_report(tech_results, fundamental_result, comparison_results,
                         portfolio_advice, chart_dir, output_path):
    """生成HTML报告并写入文件"""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    content = _build_html_content(tech_results, fundamental_result, comparison_results,
                                  portfolio_advice, chart_dir)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] HTML报告已生成: {output_path}")


def generate_html_report_content(tech_results, fundamental_result, comparison_results,
                                 portfolio_advice, chart_dir):
    """生成HTML报告内容并返回字符串（不写入文件）"""
    return _build_html_content(tech_results, fundamental_result, comparison_results,
                               portfolio_advice, chart_dir)


def _build_markdown_content(tech_results, fundamental_result, comparison_results,
                            portfolio_advice):
    """构建Markdown摘要内容，返回字符串"""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d")
    lines.append(f"# 基金投资分析摘要 ({now})")
    lines.append("")

    cycle = fundamental_result.get("cycle", "未知")
    lines.append(f"## 市场判断：{cycle}")
    lines.append(f"{fundamental_result.get('allocation', {}).get('理由', '')}")
    lines.append("")

    portfolio = portfolio_advice.get("portfolio", {})
    if "total_value" in portfolio:
        lines.append("## 组合概况")
        lines.append(f"- 总市值：¥{format_num(portfolio.get('total_value', 0), 0)}")
        lines.append(f"- 累计收益：{portfolio.get('portfolio_return', 'N/A')}%")
        lines.append(f"- 夏普比率：{format_num(portfolio.get('risk', {}).get('夏普比率'))}")
        lines.append("")

    lines.append("## 持仓基金")
    lines.append("| 基金 | 年化收益 | 最大回撤 | 夏普比率 | 经理评分 |")
    lines.append("|------|----------|----------|----------|----------|")
    for name, comp in comparison_results.items():
        tech = comp.get("technical", {})
        ret = format_pct(tech.get("returns", {}).get("年化收益率"))
        dd = format_pct(tech.get("risk", {}).get("最大回撤"))
        sharpe = format_num(tech.get("risk", {}).get("夏普比率"))
        mgr = comp.get("manager_quality", {}).get("score", "N/A")
        lines.append(f"| {name} | {ret} | {dd} | {sharpe} | {mgr} |")
    lines.append("")

    lines.append("## 核心建议")
    dca = portfolio_advice.get("dca", {})
    if "suggested_amount" in dca:
        lines.append(f"- **定投**：每月建议投入 ¥{dca.get('suggested_amount')}（{dca.get('comment')}）")
    rebalance = portfolio_advice.get("rebalance", [])
    if rebalance:
        lines.append("- **再平衡**：")
        for r in rebalance:
            lines.append(f"  - {r['name']}：{r['action']} ¥{format_num(r['amount'])}")
    else:
        lines.append("- **再平衡**：当前持仓均衡，无需调整")
    lines.append("")

    lines.append("---")
    lines.append("*本报告由基金投资分析系统自动生成，仅供参考，不构成投资建议。*")

    return "\n".join(lines)


def generate_markdown_summary(tech_results, fundamental_result, comparison_results,
                              portfolio_advice, output_path):
    """生成Markdown摘要并写入文件"""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    content = _build_markdown_content(tech_results, fundamental_result, comparison_results,
                                      portfolio_advice)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Markdown摘要已生成: {output_path}")


def generate_markdown_summary_content(tech_results, fundamental_result, comparison_results,
                                      portfolio_advice):
    """生成Markdown摘要内容并返回字符串（不写入文件）"""
    return _build_markdown_content(tech_results, fundamental_result, comparison_results,
                                   portfolio_advice)
