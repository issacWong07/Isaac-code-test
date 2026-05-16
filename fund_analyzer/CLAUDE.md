# 基金投资分析系统 - Claude 协作备忘

## 项目结构

```
fund_analyzer/
├── app.py                  # Streamlit 可视化界面（主入口）
├── main.py                 # 命令行入口
├── config.py               # 用户持仓配置
├── data_fetcher.py         # 数据获取（akshare + 缓存）
├── technical_analysis.py   # 技术分析
├── fundamental_analysis.py # 基本面分析
├── fund_comparison.py      # 基金诊断比较
├── portfolio_advisor.py    # 资产配置建议
├── daily_market.py         # 每日赛道资讯
├── report_generator.py     # 报告生成
└── charts/                 # 运行时生成的图表目录
```

## 快速启动

```bash
cd fund_analyzer
source ../venv/bin/activate
streamlit run app.py
```

或双击桌面图标：`基金分析系统.app`

## 关键已知问题

1. **PE 数据排序**：akshare `stock_index_pe_lg` 返回的数据是旧→新排列，`data_fetcher.py` 中已强制按日期降序排列。不可移除该排序逻辑。
2. **PE 列选择**：沪深300 PE 数据有多个列（等权静态、静态、等权滚动、滚动），分析时必须优先选择 `滚动市盈率`（TTM PE），排除 `等权` 和 `中位数` 列。
3. **Streamlit 表单行为**：`st.form` 内部的交互不会触发重新渲染，条件输入控件（如 radio 切换）必须放在表单外部。

## 用户偏好

- 所有界面和输出用中文
- 不中途询问确认，直接执行
- 数据展示需带单位（%、亿、¥）
- 报告不需要自动导出到磁盘，Streamlit 内通过下载按钮获取
