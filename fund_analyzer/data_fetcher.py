"""
数据获取层 - 封装akshare接口，支持数据缓存
"""

import os
import json
import fcntl
import time
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_VERSION = "v1"

# 请求限速
_last_request_time = 0
_REQUEST_INTERVAL = 0.3  # 秒


def _cache_path(name):
    """生成缓存文件路径"""
    return os.path.join(CACHE_DIR, f"{CACHE_VERSION}_{name}.json")


def _serialize_cache(data):
    """将Python对象序列化为JSON安全结构"""
    if isinstance(data, pd.DataFrame):
        return {"__type__": "DataFrame", "data": data.to_dict(orient="list")}
    elif isinstance(data, dict):
        return {k: _serialize_cache(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [_serialize_cache(item) for item in data]
    elif isinstance(data, (pd.Timestamp, datetime)):
        return data.isoformat()
    elif isinstance(data, (np.integer,)):
        return int(data)
    elif isinstance(data, (np.floating,)):
        return float(data)
    elif isinstance(data, np.ndarray):
        return data.tolist()
    return data


def _deserialize_cache(data):
    """将JSON反序列化后的结构还原为原始Python对象"""
    if isinstance(data, dict):
        if data.get("__type__") == "DataFrame":
            return pd.DataFrame(data["data"])
        return {k: _deserialize_cache(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_deserialize_cache(item) for item in data]
    return data


def _load_cache(name, max_age_hours=24):
    """加载缓存数据"""
    path = _cache_path(name)
    if not os.path.exists(path):
        return None
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    if datetime.now() - mtime > timedelta(hours=max_age_hours):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return _deserialize_cache(raw)
    except Exception:
        return None


def _save_cache(name, data):
    """保存缓存数据（带文件锁）"""
    path = _cache_path(name)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(_serialize_cache(data), f, ensure_ascii=False)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"[WARN] 缓存写入失败: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _rate_limit():
    """确保API请求间隔不低于_REQUEST_INTERVAL秒"""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _REQUEST_INTERVAL:
        time.sleep(_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _with_retry(func, max_retries=3, base_delay=1.0):
    """带指数退避的重试包装器"""
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"[RETRY] {func.__name__ if hasattr(func, '__name__') else 'API'} 第{attempt+1}次失败，{delay:.1f}秒后重试: {e}")
                time.sleep(delay)
    raise last_error


def get_fund_nav(fund_code, start_date=None, end_date=None):
    """
    获取基金历史净值走势
    返回 DataFrame: [净值日期, 单位净值, 日增长率]
    """
    cache_key = f"fund_nav_{fund_code}_{start_date}_{end_date}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached

    try:
        _rate_limit()
        df = _with_retry(lambda: ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势"))
        df.columns = ["date", "nav", "daily_return"]
        df["date"] = pd.to_datetime(df["date"])
        df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
        df["daily_return"] = pd.to_numeric(df["daily_return"], errors="coerce")

        if start_date:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["date"] <= pd.to_datetime(end_date)]

        df = df.sort_values("date").reset_index(drop=True)
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取基金 {fund_code} 净值失败: {e}")
        return pd.DataFrame()


def get_fund_info(fund_code):
    """
    获取基金基本信息
    返回 dict
    """
    cache_key = f"fund_info_{fund_code}"
    cached = _load_cache(cache_key, max_age_hours=168)
    if cached is not None:
        return cached

    try:
        _rate_limit()
        df = _with_retry(lambda: ak.fund_open_fund_info_em(symbol=fund_code, indicator="基金概况"))
        if df.empty:
            return {}
        info = dict(zip(df.iloc[:, 0], df.iloc[:, 1]))
        _save_cache(cache_key, info)
        return info
    except Exception as e:
        print(f"[ERROR] 获取基金 {fund_code} 信息失败: {e}")
        return {}


def get_fund_rating(fund_code=None):
    """
    获取基金评级数据
    如果指定fund_code，返回该基金评级；否则返回全部评级
    返回 DataFrame
    """
    cache_key = "fund_rating_all"
    df = _load_cache(cache_key, max_age_hours=168)
    if df is None:
        try:
            _rate_limit()
            df = _with_retry(lambda: ak.fund_rating_all())
            df.columns = ["code", "name", "manager", "company", "star_count",
                          "rating_sh", "rating_zs", "rating_ja", "rating_morningstar",
                          "fee", "type"]
            _save_cache(cache_key, df)
        except Exception as e:
            print(f"[ERROR] 获取基金评级失败: {e}")
            return pd.DataFrame()

    if fund_code:
        df = df[df["code"] == fund_code]
    return df


def get_fund_manager(fund_code=None):
    """
    获取基金经理信息
    如果指定fund_code，返回该基金历任经理；否则返回全部经理数据
    返回 DataFrame
    """
    cache_key = "fund_manager_all"
    df = _load_cache(cache_key, max_age_hours=168)
    if df is None:
        try:
            _rate_limit()
            df = _with_retry(lambda: ak.fund_manager_em())
            df.columns = ["seq", "name", "company", "fund_code", "fund_name",
                          "tenure_days", "total_assets", "best_return"]
            df["tenure_days"] = pd.to_numeric(df["tenure_days"], errors="coerce")
            df["best_return"] = pd.to_numeric(df["best_return"], errors="coerce")
            _save_cache(cache_key, df)
        except Exception as e:
            print(f"[ERROR] 获取基金经理数据失败: {e}")
            return pd.DataFrame()

    if fund_code:
        df = df[df["fund_code"] == fund_code]
    return df


def get_fund_asset_allocation(fund_code):
    """
    获取基金资产配置（股票/债券/现金比例）
    返回 DataFrame
    """
    cache_key = f"fund_allocation_{fund_code}"
    cached = _load_cache(cache_key, max_age_hours=168)
    if cached is not None:
        return cached

    try:
        _rate_limit()
        df = _with_retry(lambda: ak.fund_portfolio_hold_em(symbol=fund_code, date=""))
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取基金 {fund_code} 资产配置失败: {e}")
        return pd.DataFrame()


def get_fund_industry_allocation(fund_code):
    """
    获取基金行业配置
    返回 DataFrame
    """
    cache_key = f"fund_industry_{fund_code}"
    cached = _load_cache(cache_key, max_age_hours=168)
    if cached is not None:
        return cached

    try:
        _rate_limit()
        df = _with_retry(lambda: ak.fund_portfolio_industry_allocation_em(symbol=fund_code))
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取基金 {fund_code} 行业配置失败: {e}")
        return pd.DataFrame()


def get_macro_gdp():
    """获取中国GDP数据"""
    cache_key = "macro_gdp"
    cached = _load_cache(cache_key, max_age_hours=720)
    if cached is not None:
        return cached

    try:
        _rate_limit()
        df = _with_retry(lambda: ak.macro_china_gdp())
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取GDP数据失败: {e}")
        return pd.DataFrame()


def get_macro_cpi():
    """获取中国CPI数据"""
    cache_key = "macro_cpi"
    cached = _load_cache(cache_key, max_age_hours=720)
    if cached is not None:
        return cached

    try:
        _rate_limit()
        df = _with_retry(lambda: ak.macro_china_cpi())
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取CPI数据失败: {e}")
        return pd.DataFrame()


def get_macro_pmi():
    """获取中国PMI数据"""
    cache_key = "macro_pmi"
    cached = _load_cache(cache_key, max_age_hours=720)
    if cached is not None:
        return cached

    try:
        _rate_limit()
        df = _with_retry(lambda: ak.macro_china_pmi())
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取PMI数据失败: {e}")
        return pd.DataFrame()


def get_macro_lpr():
    """获取贷款市场报价利率(LPR)"""
    cache_key = "macro_lpr"
    cached = _load_cache(cache_key, max_age_hours=720)
    if cached is not None:
        return cached

    try:
        _rate_limit()
        df = _with_retry(lambda: ak.macro_china_lpr())
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取LPR数据失败: {e}")
        return pd.DataFrame()


def get_market_index(index_code="sh000300", start_date=None, end_date=None):
    """
    获取宽基指数历史行情
    index_code: sh000300=沪深300, sh000016=上证50, sh000905=中证500, sz399006=创业板指
    返回 DataFrame: [date, open, close, high, low, volume]
    """
    cache_key = f"index_{index_code}_{start_date}_{end_date}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached

    try:
        _start = start_date.replace("-", "") if start_date else "20000101"
        _end = end_date.replace("-", "") if end_date else datetime.now().strftime("%Y%m%d")
        _rate_limit()
        df = _with_retry(lambda: ak.index_zh_a_hist(
            symbol=index_code, period="daily",
            start_date=_start, end_date=_end
        ))
        if df is not None and not df.empty:
            df.columns = ["date", "open", "close", "high", "low", "volume", "amount",
                          "amplitude", "pct_change", "change_amount", "turnover"]
            df["date"] = pd.to_datetime(df["date"])
            _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取指数 {index_code} 失败: {e}")
        return pd.DataFrame()


def get_index_pe(index_code="sh000300"):
    """
    获取指数估值(PE/PB)
    返回 DataFrame: [日期, 指数, 等权静态市盈率, 静态市盈率, 静态市盈率中位数, 等权滚动市盈率, 滚动市盈率, 滚动市盈率中位数]
    """
    cache_key = f"index_pe_{index_code}"
    cached = _load_cache(cache_key, max_age_hours=24)
    if cached is not None:
        if not cached.empty and "日期" in cached.columns:
            cached = cached.sort_values("日期", ascending=False).reset_index(drop=True)
        return cached

    try:
        name_map = {
            "sh000300": "沪深300",
            "sh000016": "上证50",
            "sh000905": "中证500",
            "sz399006": "创业板指",
        }
        name = name_map.get(index_code, index_code)
        _rate_limit()
        df = _with_retry(lambda: ak.stock_index_pe_lg(symbol=name))
        if not df.empty and "日期" in df.columns:
            df = df.sort_values("日期", ascending=False).reset_index(drop=True)
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取指数估值失败: {e}")
        return pd.DataFrame()


def get_fund_list():
    """获取全部开放式基金列表"""
    cache_key = "fund_list"
    cached = _load_cache(cache_key, max_age_hours=168)
    if cached is not None:
        return cached

    try:
        _rate_limit()
        df = _with_retry(lambda: ak.fund_name_em())
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取基金列表失败: {e}")
        return pd.DataFrame()


def get_fund_rank(category="全部"):
    """
    获取基金收益排名
    category: 全部/股票型/混合型/债券型/指数型/QDII/LOF/FOF
    """
    cache_key = f"fund_rank_{category}"
    cached = _load_cache(cache_key, max_age_hours=24)
    if cached is not None:
        return cached

    try:
        _rate_limit()
        df = _with_retry(lambda: ak.fund_open_fund_rank_em(symbol=category))
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取基金排名失败: {e}")
        return pd.DataFrame()


def get_industry_fund_flow():
    """获取行业板块资金流向（实时）"""
    cache_key = "industry_fund_flow"
    cached = _load_cache(cache_key, max_age_hours=2)
    if cached is not None:
        return cached
    try:
        _rate_limit()
        df = _with_retry(lambda: ak.stock_fund_flow_industry())
        df.columns = ["序号", "行业", "行业指数", "涨跌幅", "流入资金", "流出资金", "净流入", "公司家数", "领涨股", "领涨股涨幅", "当前价"]
        df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
        df["净流入"] = pd.to_numeric(df["净流入"], errors="coerce")
        df["领涨股涨幅"] = pd.to_numeric(df["领涨股涨幅"], errors="coerce")
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取行业资金流向失败: {e}")
        return pd.DataFrame()


def get_concept_fund_flow():
    """获取概念板块资金流向（实时）"""
    cache_key = "concept_fund_flow"
    cached = _load_cache(cache_key, max_age_hours=2)
    if cached is not None:
        return cached
    try:
        _rate_limit()
        df = _with_retry(lambda: ak.stock_fund_flow_concept())
        df.columns = ["序号", "概念", "概念指数", "涨跌幅", "流入资金", "流出资金", "净流入", "公司家数", "领涨股", "领涨股涨幅", "当前价"]
        df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
        df["净流入"] = pd.to_numeric(df["净流入"], errors="coerce")
        df["领涨股涨幅"] = pd.to_numeric(df["领涨股涨幅"], errors="coerce")
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取概念资金流向失败: {e}")
        return pd.DataFrame()


def get_hot_stocks():
    """获取热门股票排名"""
    cache_key = "hot_stocks"
    cached = _load_cache(cache_key, max_age_hours=2)
    if cached is not None:
        return cached
    try:
        _rate_limit()
        df = _with_retry(lambda: ak.stock_hot_rank_em())
        df.columns = ["当前排名", "代码", "股票名称", "最新价", "涨跌额", "涨跌幅"]
        df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取热门股票失败: {e}")
        return pd.DataFrame()


def get_board_change():
    """获取板块异动数据"""
    cache_key = "board_change"
    cached = _load_cache(cache_key, max_age_hours=2)
    if cached is not None:
        return cached
    try:
        _rate_limit()
        df = _with_retry(lambda: ak.stock_board_change_em())
        df.columns = ["板块名称", "涨跌幅", "主力净流入", "异动总次数", "领涨股代码", "领涨股名称", "买卖方向", "异动类型列表"]
        df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
        df["主力净流入"] = pd.to_numeric(df["主力净流入"], errors="coerce")
        _save_cache(cache_key, df)
        return df
    except Exception as e:
        print(f"[ERROR] 获取板块异动失败: {e}")
        return pd.DataFrame()
