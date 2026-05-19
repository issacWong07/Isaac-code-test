# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 快速启动

```bash
cd fund_analyzer
source ../venv/bin/activate
streamlit run app.py
```

命令行入口：`python main.py`

> 项目无单元测试框架，验证方式以功能测试和 Streamlit 界面测试为主。

## 高层架构

**数据流**：`data_fetcher.py`（akshare API + JSON 缓存） → 各分析模块 → `report_generator.py` / `app.py`

| 模块 | 文件 | 职责 |
|------|------|------|
| 配置 | `config.py` | 用户持仓 `PORTFOLIO`、风险偏好、目标配置 `TARGET_ALLOCATION`、分析参数 |
| 数据获取 | `data_fetcher.py` | 所有 akshare 调用统一封装。JSON 缓存带版本号 `v1_`、3次重试+指数退避、0.3秒限速、`fcntl.flock` 文件锁+原子写入 |
| 技术分析 | `technical_analysis.py` | 单基金收益率（252交易日年化）、风险指标（夏普/索提诺/卡玛/VaR）、均线金叉死叉、绘图 |
| 基本面分析 | `fundamental_analysis.py` | 宏观经济（GDP/CPI/PMI/LPR）、市场估值（PE/ERP）、美林时钟周期判断 |
| 基金诊断 | `fund_comparison.py` | 基金评级、经理评估、费率分析、同类对比、雷达图归一化评分 |
| 资产配置 | `portfolio_advisor.py` | 组合分析（`how="inner"` 对齐日收益）、再平衡（按 `TARGET_ALLOCATION` 大类目标+同类型内等分）、定投策略（基于沪深300 PE 历史分位）、压力测试（按基金类型施加不同冲击系数） |
| 每日资讯 | `daily_market.py` | 行业/概念资金流向、板块异动、持仓赛道关联分析。行业名称使用 `INDUSTRY_NAME_MAP` 映射 + `difflib.get_close_matches` 模糊匹配 |
| 报告生成 | `report_generator.py` | HTML/Markdown 报告，图片以 base64 内嵌。提供 `generate_*_content()` 返回字符串（供 Streamlit 下载按钮使用） |
| Web 界面 | `app.py` | Streamlit 可视化入口，session_state 管理持仓列表。报告通过下载按钮获取，不自动写入磁盘 |

## 关键已知问题（不可修改）

1. **PE 数据排序**：`ak.stock_index_pe_lg()` 返回的数据是旧→新排列。`data_fetcher.py` 中已强制按日期降序排列。**不可移除该排序逻辑。**
2. **PE 列选择**：沪深300 PE 数据有多列（等权静态、静态、等权滚动、滚动）。分析时必须优先选择 `滚动市盈率`（TTM PE），排除 `等权` 和 `中位数` 列。相关逻辑分布在 `get_dca_strategy()` 和 `analyze_market_valuation()` 中。
3. **Streamlit 表单行为**：`st.form` 内部的交互不会触发重新渲染。条件输入控件（如 radio 切换）必须放在表单外部。参考 `app.py` 中成本录入方式的 radio 放在 `st.form` 外。

## 用户偏好

- 所有界面和输出用中文。
- 不中途询问确认，直接执行。
- 数据展示需带单位（%、亿、¥）。
- 报告不需要自动导出到磁盘，Streamlit 内通过下载按钮获取。

## 安全与代码规范

- **缓存**：JSON 格式（非 pickle），版本号 `CACHE_VERSION = "v1"`。缓存文件命名：`{CACHE_VERSION}_{name}.json`。`_save_cache()` 使用 `fcntl.flock` 文件锁 + `os.replace()` 原子替换临时文件。
- **HTML 输出**：所有 HTML 拼接使用 `html.escape()` 转义。`report_generator.py` 已提供 `_esc()` 辅助函数。`app.py` 中 `unsafe_allow_html=True` 的所有文本变量均经过转义。
- **图表**：使用 `plt.rc_context(rc=_RC_PARAMS)` 局部配置中文字体。**禁止**在模块顶层修改全局 `matplotlib.rcParams`。
- **年化计算**：使用 252 个交易日年化，非 365 天。总收益率年化公式：`(latest / first) ** (252 / n_days) - 1`。
- **组合收益对齐**：计算组合日收益率序列时，多只基金使用 `how="inner"` 合并日期，**禁止**使用 `ffill()` 填充缺失值。
- **sys.path**：模块入口使用绝对路径 + 存在性检查，避免重复插入：`if _src_dir not in sys.path: sys.path.insert(0, _src_dir)`。
