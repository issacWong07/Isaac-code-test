"""
基金投资分析系统 - Streamlit 可视化界面
双击桌面图标即可运行，无需命令行操作
"""

import os
import sys
import base64
import html
import time

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import streamlit as st
import pandas as pd

from config import (
    PORTFOLIO, RISK_PROFILE, TARGET_ALLOCATION, LOOKBACK_YEARS, BENCHMARK,
    RISK_FREE_RATE, MONTHLY_INVESTMENT_BASE, get_start_date, get_end_date
)
from data_fetcher import get_fund_nav, get_fund_info
from technical_analysis import analyze_fund_technical, compare_funds_risk_return
from fundamental_analysis import analyze_fundamental
from fund_comparison import analyze_funds_comparison
from portfolio_advisor import generate_portfolio_advice
from report_generator import generate_html_report_content, generate_markdown_summary_content
from daily_market import build_daily_sector_report
from ai_advisor import get_api_key, build_system_prompt, chat_with_advisor, get_available_models


def format_sector_df(df, table_type):
    """为赛道数据表格添加单位，返回格式化后的DataFrame副本"""
    if df.empty:
        return df
    df = df.copy()
    if table_type == "industry" or table_type == "concept":
        if "涨跌幅" in df.columns:
            df["涨跌幅"] = df["涨跌幅"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "-")
        if "净流入" in df.columns:
            df["净流入"] = df["净流入"].apply(lambda x: f"{x:+.1f}亿" if pd.notna(x) else "-")
        if "领涨股涨幅" in df.columns:
            df["领涨股涨幅"] = df["领涨股涨幅"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "-")
        if "行业指数" in df.columns:
            df["行业指数"] = df["行业指数"].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "-")
        if "概念指数" in df.columns:
            df["概念指数"] = df["概念指数"].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "-")
        if "当前价" in df.columns:
            df["当前价"] = df["当前价"].apply(lambda x: f"¥{x:,.2f}" if pd.notna(x) else "-")
    elif table_type == "board_change":
        if "涨跌幅" in df.columns:
            df["涨跌幅"] = df["涨跌幅"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "-")
        if "主力净流入" in df.columns:
            df["主力净流入"] = df["主力净流入"].apply(lambda x: f"{x:+.1f}万" if pd.notna(x) else "-")
    elif table_type == "hot_stocks":
        if "最新价" in df.columns:
            df["最新价"] = df["最新价"].apply(lambda x: f"¥{x:,.2f}" if pd.notna(x) else "-")
        if "涨跌额" in df.columns:
            df["涨跌额"] = df["涨跌额"].apply(lambda x: f"{x:+.2f}" if pd.notna(x) else "-")
        if "涨跌幅" in df.columns:
            df["涨跌幅"] = df["涨跌幅"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "-")
    return df


st.set_page_config(
    page_title="基金投资分析系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================== 全局样式 ====================
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .stButton>button {
        background-color: #1f77b4;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
    }
    .stButton>button:hover {
        background-color: #145a8c;
    }
    .sector-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .sector-card-outflow {
        border-left: 4px solid #d62728;
    }
    .sector-card-neutral {
        border-left: 4px solid #ff7f0e;
    }
</style>
""", unsafe_allow_html=True)

# ==================== 初始化状态 ====================
def init_state():
    # 从 config.py 读取默认持仓
    default_portfolio = [
        {"code": code, "name": cfg["name"], "shares": cfg["shares"], "cost": cfg["cost"]}
        for code, cfg in PORTFOLIO.items()
    ]
    defaults = {
        "portfolio": default_portfolio,
        "risk_profile": "moderate",
        "lookback_years": 10,
        "monthly_base": 3000,
        "results": None,
        "analyzing": False,
        "sector_report": None,
        "loading_sectors": False,
        "chat_history": [],
        "chat_model": "claude-3-5-sonnet-20241022",
        "chat_api_key": "",
        "chat_initialized": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ==================== 侧边栏 ====================
st.sidebar.markdown("## ⚙️ 持仓配置")
st.sidebar.markdown("---")

# 当前持仓列表
st.sidebar.markdown("### 📋 我的基金")
for i, fund in enumerate(st.session_state.portfolio):
    cols = st.sidebar.columns([3, 1])
    total_cost = fund["shares"] * fund["cost"]
    cols[0].markdown(
        f"**{fund['name']}**<br>"
        f"`{fund['code']}` | {fund['shares']}份 | 成本¥{fund['cost']:.3f} | 总投入¥{total_cost:,.0f}"
    )
    if cols[1].button("🗑️ 删除", key=f"del_{i}"):
        st.session_state.portfolio.pop(i)
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### ➕ 添加基金")
input_mode = st.sidebar.radio(
    "成本录入方式",
    options=["直接输入成本单价", "输入总投入金额自动计算"],
    index=0,
    key="cost_input_mode",
)

with st.sidebar.form("add_fund_form", clear_on_submit=True):
    new_code = st.text_input("基金代码", placeholder="例如：000001")
    new_name = st.text_input("基金名称", placeholder="例如：华夏成长混合")
    new_shares = st.number_input("持有份额", min_value=0, value=10000, step=100)

    if input_mode == "直接输入成本单价":
        new_cost = st.number_input("成本单价（元）", min_value=0.0, value=1.0, step=0.001, format="%.3f")
    else:
        new_total = st.number_input("总投入金额（元）", min_value=0.0, value=10000.0, step=100.0, format="%.2f")

    submitted = st.form_submit_button("添加基金")
    if submitted and new_code and new_name:
        if input_mode == "输入总投入金额自动计算":
            new_cost = round(new_total / new_shares, 4) if new_shares > 0 else 0.0
        st.session_state.portfolio.append({
            "code": new_code.strip(),
            "name": new_name.strip(),
            "shares": int(new_shares),
            "cost": float(new_cost),
        })
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔧 分析参数")
st.session_state.risk_profile = st.sidebar.selectbox(
    "风险偏好",
    options=["conservative", "moderate", "aggressive"],
    format_func=lambda x: {"conservative": "保守型", "moderate": "稳健型", "aggressive": "积极型"}[x],
    index=["conservative", "moderate", "aggressive"].index(st.session_state.risk_profile),
)
st.session_state.lookback_years = st.sidebar.slider("历史回望周期（年）", 1, 15, st.session_state.lookback_years)
st.session_state.monthly_base = st.sidebar.number_input(
    "每月定投基准金额（元）", min_value=0, value=st.session_state.monthly_base, step=500
)

st.sidebar.markdown("---")
st.sidebar.info("💡 提示：配置完成后，点击主界面「开始分析」按钮。")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🧭 页面导航")
page = st.sidebar.radio(
    "选择页面",
    options=["📊 分析面板", "🤖 AI投资顾问"],
    index=0,
    label_visibility="collapsed",
)

# ==================== 主界面头部 ====================
st.markdown('<div class="main-header">📈 基金投资分析系统</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">基于过去十年金融知识，为您的基金投资提供全方位分析与建议</div>', unsafe_allow_html=True)

# 当前持仓概览
if st.session_state.portfolio:
    df_display = pd.DataFrame(st.session_state.portfolio)
    df_display["总投入"] = df_display["shares"] * df_display["cost"]
    st.markdown("#### 📋 当前持仓概览")
    st.dataframe(df_display, width='stretch', hide_index=True)
else:
    st.warning("⚠️ 请在左侧添加至少一只基金后再开始分析。")

st.markdown("---")

# ==================== 每日赛道资讯（独立刷新）====================
sector_expander = st.expander("📰 每日赛道资讯与热点（点击展开，可独立刷新）", expanded=False)
with sector_expander:
    refresh_col1, refresh_col2 = st.columns([1, 4])
    with refresh_col1:
        if st.button("🔄 刷新赛道数据", key="refresh_sectors"):
            st.session_state.loading_sectors = True
            st.session_state.sector_report = None
            st.rerun()

    if st.session_state.loading_sectors:
        with st.spinner("正在获取最新赛道数据..."):
            try:
                portfolio_dict = {f["code"]: f for f in st.session_state.portfolio}
                st.session_state.sector_report = build_daily_sector_report(portfolio_dict)
                st.session_state.loading_sectors = False
                st.rerun()
            except Exception as e:
                st.error(f"获取赛道数据失败：{e}")
                st.session_state.loading_sectors = False

    if st.session_state.sector_report:
        rep = st.session_state.sector_report
        tabs = st.tabs(["🔥 热门行业", "🚀 热门概念", "📊 板块异动", "🔝 人气个股"])

        with tabs[0]:
            if rep["top_industry"]:
                df = format_sector_df(pd.DataFrame(rep["top_industry"]), "industry")
                st.dataframe(df, width='stretch', hide_index=True)
            else:
                st.info("暂无行业数据")

        with tabs[1]:
            if rep["top_concept"]:
                df = format_sector_df(pd.DataFrame(rep["top_concept"]), "concept")
                st.dataframe(df, width='stretch', hide_index=True)
            else:
                st.info("暂无概念数据")

        with tabs[2]:
            if rep["board_changes"]:
                df = format_sector_df(pd.DataFrame(rep["board_changes"]), "board_change")
                st.dataframe(df, width='stretch', hide_index=True)
            else:
                st.info("暂无板块异动数据")

        with tabs[3]:
            if rep["hot_stocks"]:
                df = format_sector_df(pd.DataFrame(rep["hot_stocks"]), "hot_stocks")
                st.dataframe(df, width='stretch', hide_index=True)
            else:
                st.info("暂无人气个股数据")
    else:
        st.info("点击上方「刷新赛道数据」按钮获取最新市场资讯。")

st.markdown("---")

# ==================== AI 投资顾问 ====================
ai_expander = st.expander("🤖 AI投资顾问（看完资讯后，点击此处与我对话）", expanded=False)
with ai_expander:
    # API Key 检测与配置
    env_key = get_api_key()
    if env_key:
        st.success("✅ 已检测到 API Key（来自环境变量或 Secrets）")
        api_key = env_key
    else:
        st.warning("⚠️ 未检测到 Anthropic API Key")
        api_key = st.text_input(
            "请输入你的 Anthropic API Key（仅当前会话使用，不会保存）：",
            type="password",
            value=st.session_state.chat_api_key,
            key="ai_api_key_input",
        )
        st.session_state.chat_api_key = api_key
        if not api_key:
            st.info("💡 获取方式：访问 https://console.anthropic.com/settings/keys 创建 API Key")
            st.stop()

    # 模型选择
    model_cols = st.columns([3, 1])
    with model_cols[0]:
        available_models = get_available_models()
        selected_model = st.selectbox(
            "选择模型",
            options=available_models,
            index=available_models.index(st.session_state.chat_model)
            if st.session_state.chat_model in available_models else 0,
            key="ai_model_select",
        )
        st.session_state.chat_model = selected_model
    with model_cols[1]:
        if st.button("🗑️ 清空对话", key="clear_chat"):
            st.session_state.chat_history = []
            st.session_state.chat_initialized = False
            st.rerun()

    # 初始化系统提示（首次进入或有新分析结果时）
    portfolio_dict_list = st.session_state.portfolio
    results = st.session_state.results
    sector_rep = st.session_state.sector_report

    if not st.session_state.chat_initialized and portfolio_dict_list:
        system_prompt = build_system_prompt(portfolio_dict_list, results, sector_rep)
        st.session_state.chat_history = [{"role": "system", "content": system_prompt}]
        st.session_state.chat_initialized = True

    # 显示对话历史
    for msg in st.session_state.chat_history:
        if msg.get("role") == "system":
            continue
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 用户输入
    user_input = st.chat_input("请输入你的投资问题...", key="chat_input")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                reply = chat_with_advisor(
                    st.session_state.chat_history,
                    api_key=api_key,
                    model=st.session_state.chat_model,
                )
            st.markdown(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.rerun()

st.markdown("---")

# ==================== 开始分析按钮 ====================
can_analyze = len(st.session_state.portfolio) > 0
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    start_btn = st.button(
        "🚀 开始全面分析",
        width='stretch',
        disabled=not can_analyze or st.session_state.analyzing
    )

# ==================== 分析执行 ====================
if start_btn and can_analyze and not st.session_state.analyzing:
    st.session_state.analyzing = True
    st.session_state.results = None
    st.rerun()

if st.session_state.analyzing:
    progress_bar = st.progress(0, text="准备开始分析...")
    log_container = st.container()

    def log(msg):
        with log_container:
            st.info(msg)

    try:
        from datetime import datetime, timedelta
        portfolio_dict = {}
        for f in st.session_state.portfolio:
            portfolio_dict[f["code"]] = {
                "name": f["name"],
                "shares": f["shares"],
                "cost": f["cost"],
            }

        start_date = (datetime.now() - timedelta(days=st.session_state.lookback_years * 365)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        chart_dir = "charts"
        os.makedirs(chart_dir, exist_ok=True)

        # 1. 数据获取
        progress_bar.progress(5, text="[1/7] 正在获取基金净值数据...")
        nav_data = {}
        fund_codes = {}
        for code, cfg in portfolio_dict.items():
            name = cfg.get("name", code)
            fund_codes[code] = name
            nav_df = get_fund_nav(code, start_date, end_date)
            if nav_df.empty:
                log(f"⚠️ {code}（{name}）数据获取失败，将跳过")
            else:
                log(f"✅ {code}（{name}）：{len(nav_df)} 条记录")
                nav_data[code] = nav_df
            time.sleep(0.2)

        if not nav_data:
            st.error("❌ 未获取到任何基金数据，请检查基金代码或网络连接")
            st.session_state.analyzing = False
            st.stop()

        # 2. 技术分析
        progress_bar.progress(20, text="[2/7] 正在进行技术分析...")
        tech_results = {}
        for code, name in fund_codes.items():
            if code not in nav_data:
                continue
            tech_results[name] = analyze_fund_technical(nav_data[code], name, chart_dir)
            time.sleep(0.1)
        nav_dict_for_plot = {name: nav_data[code] for code, name in fund_codes.items() if code in nav_data}
        compare_funds_risk_return(nav_dict_for_plot, os.path.join(chart_dir, "risk_return_scatter.png"))
        log("✅ 技术分析完成")

        # 3. 基本面分析
        progress_bar.progress(35, text="[3/7] 正在进行基本面分析...")
        fundamental_result = analyze_fundamental(chart_dir)
        log(f"✅ 经济周期判断：{fundamental_result.get('cycle', '未知')}")

        # 4. 基金诊断比较
        progress_bar.progress(50, text="[4/7] 正在进行基金诊断与比较...")
        comparison_results = analyze_funds_comparison(fund_codes, nav_data)
        log(f"✅ 基金诊断完成：{', '.join(comparison_results.keys())}")

        # 5. 资产配置建议
        progress_bar.progress(65, text="[5/7] 正在生成资产配置建议...")
        portfolio_advice = generate_portfolio_advice(nav_data, portfolio_dict, fundamental_result, chart_dir)
        total_value = portfolio_advice.get('portfolio', {}).get('total_value', 0)
        dca = portfolio_advice.get("dca", {})
        log(f"✅ 组合总市值：¥{total_value:,.2f}")
        if "suggested_amount" in dca:
            log(f"✅ 定投建议：每月 ¥{dca['suggested_amount']}")

        # 6. 每日赛道关联分析
        progress_bar.progress(80, text="[6/7] 正在获取持仓赛道关联资讯...")
        try:
            sector_report = build_daily_sector_report(portfolio_dict)
            st.session_state.sector_report = sector_report
            log(f"✅ 赛道关联分析完成，涉及 {len(sector_report.get('all_matched_sectors', []))} 个相关赛道")
        except Exception as e:
            log(f"⚠️ 赛道关联分析失败：{e}")
            sector_report = None

        # 7. 生成报告（内存中生成，不写入磁盘）
        progress_bar.progress(92, text="[7/7] 正在生成报告...")
        html_content = generate_html_report_content(tech_results, fundamental_result, comparison_results, portfolio_advice, chart_dir)
        md_content = generate_markdown_summary_content(tech_results, fundamental_result, comparison_results, portfolio_advice)

        st.session_state.results = {
            "tech_results": tech_results,
            "fundamental_result": fundamental_result,
            "comparison_results": comparison_results,
            "portfolio_advice": portfolio_advice,
            "sector_report": sector_report,
            "html_content": html_content,
            "md_content": md_content,
            "chart_dir": chart_dir,
        }

        progress_bar.progress(100, text="分析完成！")
        st.success("🎉 分析完成！请向下滚动查看完整结果。")
        st.session_state.analyzing = False
        time.sleep(1)
        st.rerun()

    except Exception as e:
        st.error(f"❌ 分析过程中出现错误：{e}")
        import traceback
        st.code(traceback.format_exc())
        st.session_state.analyzing = False

# ==================== 结果展示 ====================
if st.session_state.results and not st.session_state.analyzing:
    results = st.session_state.results
    fundamental = results["fundamental_result"]
    portfolio = results["portfolio_advice"]
    comparison = results["comparison_results"]
    tech = results["tech_results"]
    sector_report = results.get("sector_report")

    st.markdown("---")
    st.markdown("## 📊 分析结果")

    # 执行摘要
    st.markdown("### 📝 执行摘要")
    cycle = fundamental.get("cycle", "未知")
    allocation = fundamental.get("allocation", {})

    cols = st.columns(4)
    with cols[0]:
        st.metric("经济周期判断", cycle)
    with cols[1]:
        st.metric("组合总市值", f"¥{portfolio.get('portfolio', {}).get('total_value', 0):,.0f}")
    with cols[2]:
        dca = portfolio.get("dca", {})
        st.metric("建议定投金额", f"¥{dca.get('suggested_amount', 0):,.0f}/月")
    with cols[3]:
        pe = fundamental.get("valuation", {}).get("csi300_pe", {}).get("current", "-")
        st.metric("沪深300市盈率", pe)

    st.markdown(f"**配置理由**：{allocation.get('理由', '')}")

    st.markdown("#### 大类资产配置建议")
    alloc_df = pd.DataFrame([
        {"资产类别": k, "建议配置比例": v}
        for k, v in allocation.items() if k != "理由"
    ])
    st.dataframe(alloc_df, width='stretch', hide_index=True)

    # 持仓基金诊断
    st.markdown("### 🔍 持仓基金诊断")
    diag_data = []
    for name, data in comparison.items():
        diag_data.append({
            "基金名称": name,
            "年化收益率": f"{data.get('returns', {}).get('年化收益率', 0) * 100:.2f}%" if data.get('returns', {}).get('年化收益率') else "-",
            "最大回撤": f"{data.get('risk', {}).get('最大回撤', 0) * 100:.2f}%" if data.get('risk', {}).get('最大回撤') else "-",
            "夏普比率": f"{data.get('risk', {}).get('夏普比率', 0):.2f}" if data.get('risk', {}).get('夏普比率') else "-",
            "基金经理评分": data.get("manager", {}).get("score", "-"),
        })
    if diag_data:
        st.dataframe(pd.DataFrame(diag_data), width='stretch', hide_index=True)

    # 持仓赛道关联分析（新增核心功能）
    if sector_report and sector_report.get("fund_sector_advice"):
        st.markdown("---")
        st.markdown("### 🏎️ 持仓赛道关联分析与今日建议")
        st.caption("以下分析结合您持仓基金的行业配置与今日市场资金流向、板块异动数据生成")

        for fund_name, sector_data in sector_report["fund_sector_advice"].items():
            with st.expander(f"📌 {fund_name}", expanded=True):
                if sector_data["sectors"]:
                    st.markdown(f"**基金涉及行业**：{', '.join(sector_data['sectors'])}")
                else:
                    st.markdown("**基金涉及行业**：未能获取行业配置数据")

                if sector_data["matched"]:
                    st.markdown("**今日市场表现**：")
                    for item in sector_data["matched"]:
                        name = item.get("行业", item.get("概念", "未知"))
                        change = item.get("涨跌幅", 0) or 0
                        net = item.get("净流入", 0) or 0
                        leader = item.get("领涨股", item.get("领涨股名称", "-"))
                        leader_change = item.get("领涨股涨幅", 0) or 0

                        if net > 20:
                            card_class = "sector-card"
                        elif net < -20:
                            card_class = "sector-card sector-card-outflow"
                        else:
                            card_class = "sector-card sector-card-neutral"

                        st.markdown(
                            f'<div class="{card_class}">'
                            f"<strong>{html.escape(str(name))}</strong>（{html.escape(str(item.get('来源', '')))}）｜ "
                            f"涨跌幅：{change:+.2f}% ｜ "
                            f"净流入：{net:+.1f}亿 ｜ "
                            f"领涨股：{html.escape(str(leader))}（{leader_change:+.2f}%）"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                else:
                    st.info("该基金涉及的行业/概念暂无今日市场数据匹配。")

                st.markdown(f"**💡 建议**：{sector_data['advice']}")

        # 全市场热门赛道速览
        st.markdown("---")
        st.markdown("#### 🔥 全市场热门赛道速览")
        sec_cols = st.columns(2)
        with sec_cols[0]:
            st.markdown("**资金流入最多的行业（Top 5）**")
            if sector_report.get("top_industry"):
                for item in sector_report["top_industry"][:5]:
                    st.markdown(
                        f"• {item['行业']}：净流入 {item['净流入']:+.1f}亿，涨跌幅 {item['涨跌幅']:+.2f}%"
                    )
        with sec_cols[1]:
            st.markdown("**资金流入最多的概念（Top 5）**")
            if sector_report.get("top_concept"):
                for item in sector_report["top_concept"][:5]:
                    st.markdown(
                        f"• {item['概念']}：净流入 {item['净流入']:+.1f}亿，涨跌幅 {item['涨跌幅']:+.2f}%"
                    )

    # 再平衡建议
    st.markdown("---")
    st.markdown("### ⚖️ 再平衡建议")
    rebalance = portfolio.get("rebalance", [])
    if rebalance:
        rb_df = pd.DataFrame(rebalance)
        st.dataframe(rb_df, width='stretch', hide_index=True)
    else:
        st.info("当前持仓较为均衡，暂无再平衡建议。")

    # 压力测试
    st.markdown("### 🧪 压力测试")
    stress = portfolio.get("stress_test", [])
    if stress:
        stress_df = pd.DataFrame(stress)
        st.dataframe(stress_df, width='stretch', hide_index=True)

    # 关键图表
    st.markdown("---")
    st.markdown("### 📈 关键图表")
    chart_dir = results["chart_dir"]
    chart_files = [
        ("组合持仓市值占比", "portfolio_allocation.png"),
        ("组合与各基金累计收益对比", "portfolio_comparison.png"),
        ("基金风险收益分布散点图", "risk_return_scatter.png"),
        ("宏观经济指标趋势", "macro_trends.png"),
    ]

    for title, filename in chart_files:
        path = os.path.join(chart_dir, filename)
        if os.path.exists(path):
            st.markdown(f"#### {title}")
            st.image(path, width='stretch')

    # 单基金图表
    st.markdown("#### 各基金净值与回撤走势")
    for name in tech.keys():
        safe_name = name.replace(" ", "_").replace("/", "_")
        trend_path = os.path.join(chart_dir, safe_name + "_trend.png")
        dd_path = os.path.join(chart_dir, safe_name + "_drawdown.png")
        if os.path.exists(trend_path):
            st.image(trend_path, caption=f"{name} 净值走势与均线", width='stretch')
        if os.path.exists(dd_path):
            st.image(dd_path, caption=f"{name} 历史回撤", width='stretch')

    # 报告下载
    st.markdown("---")
    st.markdown("### 📥 报告下载")
    dl_cols = st.columns(2)
    with dl_cols[0]:
        html_content = results.get("html_content", "")
        if html_content:
            st.download_button(
                label="📄 下载完整 HTML 报告",
                data=html_content.encode("utf-8"),
                file_name="fund_report.html",
                mime="text/html",
                width='stretch',
            )
    with dl_cols[1]:
        md_content = results.get("md_content", "")
        if md_content:
            st.download_button(
                label="📝 下载 Markdown 摘要",
                data=md_content.encode("utf-8"),
                file_name="summary.md",
                mime="text/markdown",
                width='stretch',
            )

    st.markdown("---")
    st.caption("*本报告由基金投资分析系统自动生成，仅供参考，不构成投资建议。*")
