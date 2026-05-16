"""
基金投资分析系统 - 入口脚本
"""

import os
import sys

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from config import PORTFOLIO, get_start_date, get_end_date, get_output_dir
from data_fetcher import get_fund_nav, get_fund_info
from technical_analysis import analyze_fund_technical, compare_funds_risk_return
from fundamental_analysis import analyze_fundamental
from fund_comparison import analyze_funds_comparison
from portfolio_advisor import generate_portfolio_advice
from report_generator import generate_html_report, generate_markdown_summary


def main():
    print("=" * 60)
    print("基金投资分析系统启动")
    print("=" * 60)

    start_date = get_start_date()
    end_date = get_end_date()
    print(f"分析周期: {start_date} 至 {end_date}")
    print(f"持仓基金: {list(PORTFOLIO.keys())}")
    print()

    # 创建输出目录
    output_dir = get_output_dir()
    chart_dir = os.path.join(output_dir, "charts")
    os.makedirs(chart_dir, exist_ok=True)

    # ==================== 1. 数据获取 ====================
    print("[1/6] 正在获取基金净值数据...")
    nav_data = {}
    fund_codes = {}
    for code, cfg in PORTFOLIO.items():
        name = cfg.get("name", code)
        fund_codes[code] = name
        nav_df = get_fund_nav(code, start_date, end_date)
        if nav_df.empty:
            print(f"  [WARN] {code} ({name}) 数据获取失败，将跳过")
        else:
            print(f"  [OK] {code} ({name}): {len(nav_df)} 条记录")
            nav_data[code] = nav_df

    if not nav_data:
        print("[ERROR] 未获取到任何基金数据，请检查基金代码或网络连接")
        return

    # ==================== 2. 技术分析 ====================
    print("\n[2/6] 正在进行技术分析...")
    tech_results = {}
    for code, name in fund_codes.items():
        if code not in nav_data:
            continue
        print(f"  分析 {name}...")
        tech_results[name] = analyze_fund_technical(nav_data[code], name, chart_dir)

    # 风险收益对比图
    nav_dict_for_plot = {name: nav_data[code] for code, name in fund_codes.items() if code in nav_data}
    compare_funds_risk_return(nav_dict_for_plot, os.path.join(chart_dir, "risk_return_scatter.png"))

    # ==================== 3. 基本面分析 ====================
    print("\n[3/6] 正在进行基本面分析...")
    fundamental_result = analyze_fundamental(chart_dir)
    print(f"  经济周期判断: {fundamental_result.get('cycle', '未知')}")

    # ==================== 4. 基金诊断比较 ====================
    print("\n[4/6] 正在进行基金诊断与比较...")
    comparison_results = analyze_funds_comparison(fund_codes, nav_data)
    for name in comparison_results:
        print(f"  [OK] {name} 诊断完成")

    # ==================== 5. 资产配置建议 ====================
    print("\n[5/6] 正在生成资产配置建议...")
    portfolio_advice = generate_portfolio_advice(nav_data, PORTFOLIO, fundamental_result, chart_dir)
    print(f"  组合总市值: ¥{portfolio_advice.get('portfolio', {}).get('total_value', 0):,.2f}")
    dca = portfolio_advice.get("dca", {})
    if "suggested_amount" in dca:
        print(f"  定投建议: 每月 ¥{dca['suggested_amount']}")

    # ==================== 6. 生成报告 ====================
    print("\n[6/6] 正在生成报告...")
    html_path = os.path.join(output_dir, "report.html")
    md_path = os.path.join(output_dir, "summary.md")

    generate_html_report(
        tech_results, fundamental_result, comparison_results,
        portfolio_advice, chart_dir, html_path
    )
    generate_markdown_summary(
        tech_results, fundamental_result, comparison_results,
        portfolio_advice, md_path
    )

    print("\n" + "=" * 60)
    print("分析完成！")
    print(f"报告目录: {os.path.abspath(output_dir)}")
    print(f"  - HTML报告: {html_path}")
    print(f"  - Markdown摘要: {md_path}")
    print(f"  - 图表目录: {chart_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
