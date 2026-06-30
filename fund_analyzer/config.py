# 基金投资分析系统 - 用户配置
# 请在此文件配置你的持仓信息与分析参数

from datetime import datetime, timedelta

# ==================== 持仓配置 ====================
# 格式: {"基金代码": {"name": "基金简称", "shares": 持有份额, "cost": 成本单价（可选）}}
PORTFOLIO = {
    "010737": {"name": "易方达沪深300指数精选增强C", "shares": 2994.3, "cost": 1.2979},
    "012922": {"name": "易方达全球成长精选混合（QDII）C", "shares": 814.51, "cost": 3.1798},
    "019305": {"name": "摩根标普500指数（QDII）C", "shares": 1592.14, "cost": 1.6267},
    "020692": {"name": "博时中证全指通信设备指数C", "shares": 586.01, "cost": 3.8627},
    "025500": {"name": "东方阿尔法科技智选混合C", "shares": 915.65, "cost": 1.7894},
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
