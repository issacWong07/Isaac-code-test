# 基金投资分析系统 - 用户配置
# 请在此文件配置你的持仓信息与分析参数

from datetime import datetime, timedelta

# ==================== 持仓配置 ====================
# 格式: {"基金代码": {"name": "基金简称", "shares": 持有份额, "cost": 成本单价（可选）}}
PORTFOLIO = {
    "000001": {"name": "华夏成长混合", "shares": 10000, "cost": 1.2},
    "110022": {"name": "易方达消费行业", "shares": 5000, "cost": 3.5},
    "519732": {"name": "交银双息平衡", "shares": 8000, "cost": 1.8},
}

# ==================== 风险偏好 ====================
# 可选: "conservative"(保守), "moderate"(稳健), "aggressive"(积极)
RISK_PROFILE = "moderate"

# ==================== 目标配置比例 ====================
# 用于再平衡分析，总和应为100
TARGET_ALLOCATION = {
    "混合型": 40,
    "股票型": 30,
    "债券型": 20,
    "货币型": 10,
}

# ==================== 分析参数 ====================
# 回望周期（年）
LOOKBACK_YEARS = 10

# 基准指数（用于对比）
BENCHMARK = "sh000300"  # 沪深300

# 无风险利率（用于夏普比率计算，默认10年期国债收益率约2.5%）
RISK_FREE_RATE = 0.025

# 定投基准金额（用于定投策略建议）
MONTHLY_INVESTMENT_BASE = 3000

# ==================== 报告配置 ====================
# 输出目录
def get_output_dir():
    """获取输出目录（调用时动态计算日期）"""
    return "report_" + datetime.now().strftime("%Y%m%d")

# 图表风格
CHART_STYLE = "seaborn-v0_8-whitegrid"  # matplotlib样式

# 是否生成交互式图表（需要plotly）
ENABLE_INTERACTIVE_CHARTS = True

# ==================== 快捷函数 ====================
def get_start_date():
    """获取分析起始日期"""
    return (datetime.now() - timedelta(days=LOOKBACK_YEARS * 365)).strftime("%Y-%m-%d")


def get_end_date():
    """获取分析结束日期"""
    return datetime.now().strftime("%Y-%m-%d")
