"""
Indian Stock Market MCP Server — Proper MCP Protocol Version
Uses stdio transport for Claude/Cursor/VS Code integration.
"""

import json
import sys
import asyncio
from datetime import datetime
from typing import Optional, Any

try:
    import yfinance as yf
except ImportError:
    print(json.dumps({"error": "yfinance not installed. Run: pip install yfinance"}))
    sys.exit(1)

# Optional imports for new features
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from fuzzywuzzy import fuzz, process
    HAS_FUZZY = True
except ImportError:
    HAS_FUZZY = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ─── Helper Functions ───────────────────────────────────────────────

def _resolve_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not symbol.endswith(".NS") and not symbol.endswith(".BSE"):
        symbol = symbol + ".NS"
    return symbol

def _fuzzy_match_symbol(query: str) -> str:
    """Fuzzy match a company name to a stock symbol. 'reliance' → 'RELIANCE.NS'"""
    query = query.strip().upper()
    
    # Direct match first
    for sym in NIFTY50:
        clean = sym.replace(".NS", "")
        if query == clean:
            return sym
    
    # Fuzzy match against company names
    if HAS_FUZZY:
        choices = {}
        for sym in NIFTY50:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.info
                name = (info.get("shortName") or "").upper()
                long_name = (info.get("longName") or "").upper()
                clean = sym.replace(".NS", "")
                choices[clean] = clean
                choices[name] = clean
                choices[long_name] = clean
            except Exception:
                continue
        
        if choices:
            best_match, score = process.extractOne(query, choices.keys())
            if score >= 60:
                matched_sym = choices[best_match]
                if not matched_sym.endswith(".NS"):
                    matched_sym = matched_sym + ".NS"
                return matched_sym
    
    # Fallback: try direct symbol
    return _resolve_symbol(query)

def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
        if f != f:
            return None
        return round(f, 2)
    except (TypeError, ValueError):
        return None

def _format_number(value: float) -> str:
    if value is None:
        return "N/A"
    if value >= 10000000:
        return f"₹{value/10000000:.2f} Cr"
    elif value >= 100000:
        return f"₹{value/100000:.2f} L"
    else:
        return f"₹{value:,.2f}"

NIFTY50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "ITC.NS",
    "LT.NS", "AXISBANK.NS", "WIPRO.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "POWERGRID.NS",
    "NTPC.NS", "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS",
    "BAJFINANCE.NS", "HCLTECH.NS", "TECHM.NS", "DRREDDY.NS", "CIPLA.NS",
    "BRITANNIA.NS", "HEROMOTOCO.NS", "EICHERMOT.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
    "INDUSINDBK.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "GRASIM.NS",
    "ONGC.NS", "BPCL.NS", "IOC.NS", "TATACONSUM.NS", "SBILIFE.NS",
    "HDFCLIFE.NS", "BAJAJFINSV.NS", "M&M.NS", "PIDILITIND.NS"
]

# ─── Tool Implementations ───────────────────────────────────────────

def tool_get_price(symbol: str) -> dict:
    """Get live price for any NSE/BSE stock. Symbol like RELIANCE, TCS, INFY.NS"""
    try:
        symbol = _resolve_symbol(symbol)
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        result = {
            "symbol": symbol,
            "company_name": ticker.info.get("longName") or ticker.info.get("shortName") or symbol,
            "currency": "INR",
            "price": _safe_float(getattr(info, 'last_price', None)),
            "previous_close": _safe_float(getattr(info, 'previous_close', None)),
            "day_high": _safe_float(getattr(info, 'day_high', None)),
            "day_low": _safe_float(getattr(info, 'day_low', None)),
            "volume": int(getattr(info, 'last_volume', 0)) if getattr(info, 'last_volume', None) else None,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
        }
        if result["price"] and result["previous_close"]:
            change = result["price"] - result["previous_close"]
            result["change"] = round(change, 2)
            result["change_percent"] = round((change / result["previous_close"]) * 100, 2)
        return result
    except Exception as e:
        return {"error": str(e)}

def tool_get_history(symbol: str, period: str = "1mo") -> dict:
    """Get historical OHLCV data. Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max"""
    try:
        symbol = _resolve_symbol(symbol)
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if hist.empty:
            return {"error": f"No data for {symbol}"}
        data = []
        for date, row in hist.iterrows():
            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": _safe_float(row.get("Open")),
                "high": _safe_float(row.get("High")),
                "low": _safe_float(row.get("Low")),
                "close": _safe_float(row.get("Close")),
                "volume": int(row.get("Volume", 0)) if row.get("Volume") else 0
            })
        return {"symbol": symbol, "period": period, "data_points": len(data), "data": data[-30:]}
    except Exception as e:
        return {"error": str(e)}

def tool_get_company_info(symbol: str) -> dict:
    """Get company fundamentals: sector, market cap, PE, PB, dividend yield, EPS, etc."""
    try:
        symbol = _resolve_symbol(symbol)
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            "symbol": symbol,
            "company_name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "exchange": info.get("exchange", "N/A"),
            "market_cap": _safe_float(info.get("marketCap")),
            "market_cap_formatted": _format_number(info.get("marketCap", 0)),
            "pe_ratio": _safe_float(info.get("trailingPE")),
            "pb_ratio": _safe_float(info.get("priceToBook")),
            "dividend_yield": _safe_float(info.get("dividendYield")),
            "eps": _safe_float(info.get("trailingEps")),
            "book_value": _safe_float(info.get("bookValue")),
            "52_week_high": _safe_float(info.get("fiftyTwoWeekHigh")),
            "52_week_low": _safe_float(info.get("fiftyTwoWeekLow")),
            "avg_volume": int(info.get("averageVolume", 0)) if info.get("averageVolume") else None,
            "website": info.get("website", "N/A"),
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_top_gainers(limit: int = 10) -> dict:
    """Get top gaining stocks on NSE today"""
    try:
        gainers = []
        for sym in NIFTY50:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                price = _safe_float(getattr(info, 'last_price', None))
                prev = _safe_float(getattr(info, 'previous_close', None))
                if price and prev and prev > 0:
                    pct = ((price - prev) / prev) * 100
                    gainers.append({
                        "symbol": sym.replace(".NS", ""),
                        "company_name": ticker.info.get("shortName") or sym,
                        "price": price,
                        "change_percent": round(pct, 2),
                        "volume": int(getattr(info, 'last_volume', 0)) if getattr(info, 'last_volume', None) else 0
                    })
            except Exception:
                continue
        gainers.sort(key=lambda x: x.get("change_percent", 0), reverse=True)
        return {"type": "top_gainers", "count": min(limit, len(gainers)), "data": gainers[:limit]}
    except Exception as e:
        return {"error": str(e)}

def tool_get_top_losers(limit: int = 10) -> dict:
    """Get top losing stocks on NSE today"""
    try:
        losers = []
        for sym in NIFTY50:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                price = _safe_float(getattr(info, 'last_price', None))
                prev = _safe_float(getattr(info, 'previous_close', None))
                if price and prev and prev > 0:
                    pct = ((price - prev) / prev) * 100
                    losers.append({
                        "symbol": sym.replace(".NS", ""),
                        "company_name": ticker.info.get("shortName") or sym,
                        "price": price,
                        "change_percent": round(pct, 2),
                        "volume": int(getattr(info, 'last_volume', 0)) if getattr(info, 'last_volume', None) else 0
                    })
            except Exception:
                continue
        losers.sort(key=lambda x: x.get("change_percent", 0))
        return {"type": "top_losers", "count": min(limit, len(losers)), "data": losers[:limit]}
    except Exception as e:
        return {"error": str(e)}

def tool_get_portfolio(holdings_json: str) -> dict:
    """Calculate portfolio value and P&L. Holdings as JSON string."""
    try:
        holdings = json.loads(holdings_json) if isinstance(holdings_json, str) else holdings_json
        total_value = 0
        total_invested = 0
        stocks = []
        for h in holdings:
            sym = h.get("symbol", "")
            qty = h.get("quantity", 0)
            avg = h.get("avg_price", 0)
            if not sym or qty <= 0:
                continue
            pd = tool_get_price(sym)
            if "error" in pd:
                continue
            price = pd.get("price", 0)
            cur_val = price * qty
            inv_val = avg * qty
            pnl = cur_val - inv_val
            pnl_pct = ((price - avg) / avg * 100) if avg and avg > 0 else 0
            total_value += cur_val
            total_invested += inv_val
            stocks.append({
                "symbol": sym, "company_name": pd.get("company_name", sym),
                "quantity": qty, "avg_price": avg, "current_price": price,
                "current_value": round(cur_val, 2), "invested_value": round(inv_val, 2),
                "pnl": round(pnl, 2), "pnl_percent": round(pnl_pct, 2), "weight": 0
            })
        for s in stocks:
            if total_value > 0:
                s["weight"] = round((s["current_value"] / total_value) * 100, 2)
        total_pnl = total_value - total_invested
        total_pnl_pct = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
        return {
            "portfolio": {
                "total_value": round(total_value, 2), "total_invested": round(total_invested, 2),
                "total_pnl": round(total_pnl, 2), "total_pnl_percent": round(total_pnl_pct, 2),
                "num_stocks": len(stocks)
            },
            "holdings": stocks
        }
    except Exception as e:
        return {"error": str(e)}

def tool_screen_stocks(criteria_json: str = "{}") -> dict:
    """Screen NSE stocks by criteria. JSON: {min_pe, max_pe, sector, min_dividend_yield, limit}"""
    try:
        criteria = json.loads(criteria_json) if isinstance(criteria_json, str) else criteria_json
        min_pe = criteria.get("min_pe")
        max_pe = criteria.get("max_pe")
        sector = criteria.get("min_dividend_yield")
        div_yield = criteria.get("min_dividend_yield")
        sec_filter = criteria.get("sector")
        limit = criteria.get("limit", 20)
        
        results = []
        for sym in NIFTY50:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.info
                pe = _safe_float(info.get("trailingPE"))
                stock_sector = info.get("sector", "")
                dy = _safe_float(info.get("dividendYield"))
                
                if min_pe is not None and (pe is None or pe < min_pe): continue
                if max_pe is not None and (pe is None or pe > max_pe): continue
                if sec_filter and sec_filter.lower() not in stock_sector.lower(): continue
                if div_yield is not None and (dy is None or dy < div_yield): continue
                
                results.append({
                    "symbol": sym.replace(".NS", ""),
                    "company_name": info.get("shortName") or sym,
                    "sector": stock_sector, "pe_ratio": pe, "dividend_yield": dy
                })
            except Exception:
                continue
        return {"results_count": len(results), "data": results[:limit]}
    except Exception as e:
        return {"error": str(e)}

def tool_get_crypto_price(symbol: str = "BTC-INR") -> dict:
    """Get crypto price. Symbol format: BTC-INR, ETH-INR, SOL-INR"""
    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.fast_info
        price = _safe_float(getattr(info, 'last_price', None))
        if price:
            return {
                "crypto": symbol.upper(), "currency": "INR" if "INR" in symbol else "USD",
                "price": price,
                "previous_close": _safe_float(getattr(info, 'previous_close', None)),
            }
        return {"error": f"No data for {symbol}"}
    except Exception as e:
        return {"error": str(e)}

def tool_get_market_summary() -> dict:
    """Get overall market summary: Nifty 50, Sensex, top gainers, top losers, market breadth"""
    try:
        # Get Nifty 50 index
        nifty = yf.Ticker("^NSEI")
        nifty_info = nifty.fast_info
        nifty_price = _safe_float(getattr(nifty_info, 'last_price', None))
        nifty_prev = _safe_float(getattr(nifty_info, 'previous_close', None))
        nifty_change = None
        nifty_change_pct = None
        if nifty_price and nifty_prev:
            nifty_change = round(nifty_price - nifty_prev, 2)
            nifty_change_pct = round((nifty_change / nifty_prev) * 100, 2)
        
        # Get Sensex
        sensex = yf.Ticker("^BSESN")
        sensex_info = sensex.fast_info
        sensex_price = _safe_float(getattr(sensex_info, 'last_price', None))
        sensex_prev = _safe_float(getattr(sensex_info, 'previous_close', None))
        sensex_change = None
        sensex_change_pct = None
        if sensex_price and sensex_prev:
            sensex_change = round(sensex_price - sensex_prev, 2)
            sensex_change_pct = round((sensex_change / sensex_prev) * 100, 2)
        
        # Market breadth from Nifty 50
        advances = 0
        declines = 0
        unchanged = 0
        for sym in NIFTY50[:20]:  # Sample first 20 for speed
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                price = _safe_float(getattr(info, 'last_price', None))
                prev = _safe_float(getattr(info, 'previous_close', None))
                if price and prev:
                    if price > prev:
                        advances += 1
                    elif price < prev:
                        declines += 1
                    else:
                        unchanged += 1
            except Exception:
                continue
        
        return {
            "nifty_50": {"price": nifty_price, "change": nifty_change, "change_percent": nifty_change_pct},
            "sensex": {"price": sensex_price, "change": sensex_change, "change_percent": sensex_change_pct},
            "market_breadth": {"advances": advances, "declines": declines, "unchanged": unchanged},
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        }
    except Exception as e:
        return {"error": str(e)}

def tool_search_stock(query: str) -> dict:
    """Search for stocks by name or symbol"""
    try:
        query = query.upper().strip()
        results = []
        for sym in NIFTY50:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.info
                name = (info.get("shortName") or "").upper()
                long_name = (info.get("longName") or "").upper()
                symbol_clean = sym.replace(".NS", "")
                if query in symbol_clean or query in name or query in long_name:
                    results.append({
                        "symbol": symbol_clean,
                        "company_name": info.get("shortName") or info.get("longName") or sym,
                        "sector": info.get("sector", "N/A")
                    })
            except Exception:
                continue
        return {"query": query, "results_count": len(results), "data": results[:10]}
    except Exception as e:
        return {"error": str(e)}

# ─── NEW TOOLS v2.0 ─────────────────────────────────────────────────

def tool_get_sector_performance() -> dict:
    """Get sector-wise performance for NSE stocks. Shows which sectors are up/down today."""
    try:
        sectors = {}
        for sym in NIFTY50:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                sector = ticker.info.get("sector", "Unknown")
                price = _safe_float(getattr(info, 'last_price', None))
                prev = _safe_float(getattr(info, 'previous_close', None))
                if price and prev and prev > 0:
                    pct = ((price - prev) / prev) * 100
                    if sector not in sectors:
                        sectors[sector] = {"stocks": [], "total_change": 0, "count": 0}
                    sectors[sector]["stocks"].append({
                        "symbol": sym.replace(".NS", ""),
                        "change_percent": round(pct, 2)
                    })
                    sectors[sector]["total_change"] += pct
                    sectors[sector]["count"] += 1
            except Exception:
                continue
        
        # Calculate average per sector
        result = []
        for sector, data in sectors.items():
            if data["count"] > 0:
                avg = data["total_change"] / data["count"]
                result.append({
                    "sector": sector,
                    "avg_change_percent": round(avg, 2),
                    "num_stocks": data["count"],
                    "top_stock": min(data["stocks"], key=lambda x: x["change_percent"]) if avg < 0 else max(data["stocks"], key=lambda x: x["change_percent"])
                })
        
        result.sort(key=lambda x: x["avg_change_percent"], reverse=True)
        return {"type": "sector_performance", "data": result, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")}
    except Exception as e:
        return {"error": str(e)}

def tool_get_dividend_info(symbol: str) -> dict:
    """Get dividend information for a stock: yield, ex-date, payout ratio, dividend history"""
    try:
        symbol = _resolve_symbol(symbol)
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Get dividend history
        dividends = ticker.dividends
        div_history = []
        if not dividends.empty:
            for date, amount in dividends.tail(12).items():
                div_history.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "amount": round(float(amount), 2)
                })
        
        return {
            "symbol": symbol.replace(".NS", ""),
            "company_name": info.get("longName") or info.get("shortName") or symbol,
            "dividend_yield": _safe_float(info.get("dividendYield")),
            "dividend_rate": _safe_float(info.get("dividendRate")),
            "payout_ratio": _safe_float(info.get("payoutRatio")),
            "five_year_avg_dividend_yield": _safe_float(info.get("fiveYearAvgDividendYield")),
            "dividend_history_last_12": div_history,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_52w_high_low_proximity(symbol: str) -> dict:
        """Check if a stock is near its 52-week high or low. Useful for breakout/bounce plays."""
        try:
            symbol = _resolve_symbol(symbol)
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            price = _safe_float(getattr(info, 'last_price', None))
            high52 = _safe_float(getattr(info, 'year_high', None)) or _safe_float(ticker.info.get("fiftyTwoWeekHigh"))
            low52 = _safe_float(getattr(info, 'year_low', None)) or _safe_float(ticker.info.get("fiftyTwoWeekLow"))
            
            if not all([price, high52, low52]):
                return {"error": f"Insufficient data for {symbol}"}
            
            range_total = high52 - low52
            if range_total <= 0:
                return {"symbol": symbol, "error": "Invalid 52-week range"}
            
            pct_from_high = ((high52 - price) / range_total) * 100
            pct_from_low = ((price - low52) / range_total) * 100
            
            signal = "neutral"
            if pct_from_high <= 5:
                signal = "near_52w_high"
            elif pct_from_low <= 5:
                signal = "near_52w_low"
            elif pct_from_high <= 15:
                signal = "approaching_52w_high"
            elif pct_from_low <= 15:
                signal = "approaching_52w_low"
            
            return {
                "symbol": symbol.replace(".NS", ""),
                "company_name": ticker.info.get("shortName") or symbol,
                "current_price": price,
                "52w_high": high52,
                "52w_low": low52,
                "pct_from_52w_high": round(pct_from_high, 2),
                "pct_from_52w_low": round(pct_from_low, 2),
                "signal": signal,
                "position_in_range": round(pct_from_low, 2)
            }
        except Exception as e:
            return {"error": str(e)}

def tool_get_bulk_quotes(symbols_json: str) -> dict:
    """Get live prices for multiple stocks at once. Args: symbols_json (JSON array of symbols)"""
    try:
        symbols = json.loads(symbols_json) if isinstance(symbols_json, str) else symbols_json
        results = []
        errors = []
        for sym in symbols:
            try:
                result = tool_get_price(sym)
                if "error" in result:
                    errors.append({"symbol": sym, "error": result["error"]})
                else:
                    results.append(result)
            except Exception as e:
                errors.append({"symbol": sym, "error": str(e)})
        return {
            "quotes": results,
            "errors": errors,
            "total_requested": len(symbols),
            "successful": len(results),
            "failed": len(errors)
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_index_constituents(index: str = "nifty50") -> dict:
    """Get list of stocks in major Indian indices. Args: index (nifty50, niftybank, niftyit, niftyfmcg, niftyauto, niftypharma, niftymetal, niftyreality, niftyenergy)"""
    indices = {
        "nifty50": NIFTY50,
        "niftybank": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS", "BANDHANBNK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "PNB.NS"],
        "niftyit": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "LTIM.NS", "MPHASIS.NS", "PERSISTENT.NS", "COFORGE.NS", "LTTS.NS"],
        "niftyfmcg": ["HINDUNILVR.NS", "ITC.NS", "BRITANNIA.NS", "TATACONSUM.NS", "DABUR.NS", "GODREJCP.NS", "MARICO.NS", "COLPAL.NS", "NESTLEIND.NS", "UBL.NS"],
        "niftyauto": ["MARUTI.NS", "M&M.NS", "TATAMOTORS.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "TVSMOTOR.NS", "ASHOKLEY.NS", "BHARATFORG.NS", "BOSCHLTD.NS"],
        "niftypharma": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "LUPIN.NS", "AUROPHARMA.NS", "TORNTPHARM.NS", "ZYDUSLIFE.NS", "BIOCON.NS"],
        "niftymetal": ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "NMDC.NS", "NATIONALUM.NS", "COALINDIA.NS", "MOIL.NS", "APLAPOLLO.NS", "JINDALSTEL.NS"],
        "niftyreality": ["DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "PHOENIXLTD.NS", "BRIGADE.NS", "SOBHA.NS", "SUNTECK.NS", "MAHLIFE.NS", "IBREALEST.NS"],
        "niftyenergy": ["RELIANCE.NS", "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "BPCL.NS", "IOC.NS", "HINDPETRO.NS", "GAIL.NS", "TATAPOWER.NS", "ADANIGREEN.NS"]
    }
    
    index_lower = index.lower()
    if index_lower not in indices:
        return {"error": f"Unknown index: {index}. Available: {', '.join(indices.keys())}"}
    
    symbols = indices[index_lower]
    return {
        "index": index,
        "num_stocks": len(symbols),
        "constituents": [s.replace(".NS", "") for s in symbols]
    }

def tool_compare_stocks(symbols_json: str) -> dict:
    """Compare multiple stocks side by side on key metrics"""
    try:
        symbols = json.loads(symbols_json) if isinstance(symbols_json, str) else symbols_json
        comparison = []
        for sym in symbols:
            try:
                info = tool_get_company_info(sym)
                price = tool_get_price(sym)
                if "error" not in info and "error" not in price:
                    comparison.append({
                        "symbol": sym.upper(),
                        "company_name": info.get("company_name", sym),
                        "price": price.get("price"),
                        "change_percent": price.get("change_percent"),
                        "pe_ratio": info.get("pe_ratio"),
                        "pb_ratio": info.get("pb_ratio"),
                        "market_cap": info.get("market_cap_formatted"),
                        "dividend_yield": info.get("dividend_yield"),
                        "sector": info.get("sector"),
                        "52w_high": info.get("52_week_high"),
                        "52w_low": info.get("52_week_low")
                    })
            except Exception:
                continue
        return {"comparison": comparison, "count": len(comparison)}
    except Exception as e:
        return {"error": str(e)}

def tool_get_technical_snapshot(symbol: str) -> dict:
        """Get a technical analysis snapshot: current price, 52w range position, volume trend, simple signals"""
        try:
            symbol = _resolve_symbol(symbol)
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            price = _safe_float(getattr(info, 'last_price', None))
            high52 = _safe_float(ticker.info.get("fiftyTwoWeekHigh"))
            low52 = _safe_float(ticker.info.get("fiftyTwoWeekLow"))
            avg_vol = ticker.info.get("averageVolume", 0)
            cur_vol = int(getattr(info, 'last_volume', 0)) if getattr(info, 'last_volume', None) else 0
            
            # Get 20-day moving average
            hist = ticker.history(period="1mo")
            ma20 = None
            ma50 = None
            if not hist.empty and len(hist) >= 20:
                ma20 = round(float(hist["Close"].tail(20).mean()), 2)
            if not hist.empty and len(hist) >= 50:
                ma50 = round(float(hist["Close"].tail(50).mean()), 2)
            
            # Simple signals
            signals = []
            if price and ma20:
                if price > ma20:
                    signals.append("price_above_20ma_bullish")
                else:
                    signals.append("price_below_20ma_bearish")
            if ma20 and ma50:
                if ma20 > ma50:
                    signals.append("golden_cross_bullish")
                else:
                    signals.append("death_cross_bearish")
            if cur_vol and avg_vol and avg_vol > 0:
                vol_ratio = cur_vol / avg_vol
                if vol_ratio > 2:
                    signals.append(f"high_volume_{vol_ratio:.1f}x_avg")
            
            range_pct = None
            if price and high52 and low52 and (high52 - low52) > 0:
                range_pct = round(((price - low52) / (high52 - low52)) * 100, 2)
            
            return {
                "symbol": symbol.replace(".NS", ""),
                "company_name": ticker.info.get("shortName") or symbol,
                "price": price,
                "ma20": ma20,
                "ma50": ma50,
                "52w_range_pct": range_pct,
                "volume_ratio": round(cur_vol / avg_vol, 2) if avg_vol and avg_vol > 0 else None,
                "signals": signals,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
            }
        except Exception as e:
            return {"error": str(e)}

# ─── NEW TOOLS v3.0 ─────────────────────────────────────────────────

def tool_get_stock_chart(symbol: str, period: str = "3mo", chart_type: str = "line") -> dict:
    """Generate a stock price chart with moving averages and volume. Returns base64 PNG."""
    if not HAS_MATPLOTLIB:
        return {"error": "matplotlib not installed. Run: pip install matplotlib"}
    
    try:
        symbol = _fuzzy_match_symbol(symbol)
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        if hist.empty:
            return {"error": f"No data for {symbol}"}
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
        fig.suptitle(f"{symbol.replace('.NS', '')} - {period} Chart", fontsize=14, fontweight='bold')
        
        # Price chart
        if chart_type == "candlestick" and HAS_NUMPY:
            # Simple candlestick using bar chart
            for i, (date, row) in enumerate(hist.iterrows()):
                color = 'green' if row['Close'] >= row['Open'] else 'red'
                ax1.bar(i, row['Close'] - row['Open'], bottom=row['Open'], color=color, width=0.6)
                ax1.plot([i, i], [row['Low'], row['High']], color=color, linewidth=0.5)
            ax1.set_xticks(range(0, len(hist), max(1, len(hist)//10)))
            ax1.set_xticklabels([d.strftime('%b %d') for d in hist.index[::max(1, len(hist)//10)]], rotation=45)
        else:
            ax1.plot(range(len(hist)), hist['Close'].values, color='#2196F3', linewidth=1.5, label='Close')
            ax1.fill_between(range(len(hist)), hist['Close'].values, alpha=0.1, color='#2196F3')
            ax1.set_xticks(range(0, len(hist), max(1, len(hist)//10)))
            ax1.set_xticklabels([d.strftime('%b %d') for d in hist.index[::max(1, len(hist)//10)]], rotation=45)
        
        # Moving averages
        if len(hist) >= 20:
            ma20 = hist['Close'].rolling(20).mean()
            ax1.plot(range(len(hist)), ma20.values, color='#FF9800', linewidth=1, label='MA20', alpha=0.8)
        if len(hist) >= 50:
            ma50 = hist['Close'].rolling(50).mean()
            ax1.plot(range(len(hist)), ma50.values, color='#F44336', linewidth=1, label='MA50', alpha=0.8)
        
        ax1.set_ylabel('Price (₹)')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # Volume chart
        colors = ['green' if hist['Close'].iloc[i] >= hist['Open'].iloc[i] else 'red' for i in range(len(hist))]
        ax2.bar(range(len(hist)), hist['Volume'].values, color=colors, alpha=0.7, width=0.6)
        ax2.set_ylabel('Volume')
        ax2.set_xticks(range(0, len(hist), max(1, len(hist)//10)))
        ax2.set_xticklabels([d.strftime('%b %d') for d in hist.index[::max(1, len(hist)//10)]], rotation=45)
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save to base64
        import io
        import base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        
        return {
            "symbol": symbol.replace(".NS", ""),
            "period": period,
            "chart_type": chart_type,
            "image_base64": img_base64,
            "format": "png",
            "data_points": len(hist)
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_stock_news(symbol: str, limit: int = 5) -> dict:
    """Get latest news for a stock from Yahoo Finance"""
    try:
        symbol = _fuzzy_match_symbol(symbol)
        ticker = yf.Ticker(symbol)
        
        # Try multiple approaches to get news
        articles = []
        
        # Approach 1: ticker.news (newer yfinance)
        try:
            news = ticker.news
            if news:
                for article in news[:limit]:
                    content = article.get("content", {})
                    if isinstance(content, dict):
                        articles.append({
                            "title": content.get("title", article.get("title", "")),
                            "publisher": content.get("provider", {}).get("displayName", article.get("publisher", "")),
                            "link": content.get("clickThroughUrl", {}).get("url", article.get("link", "")),
                            "published": content.get("pubDate", article.get("published", "")),
                            "summary": (content.get("summary", "") or article.get("summary", ""))[:200]
                        })
                    else:
                        articles.append({
                            "title": article.get("title", ""),
                            "publisher": article.get("publisher", ""),
                            "link": article.get("link", ""),
                            "published": article.get("published", ""),
                            "summary": (article.get("summary", "") or "")[:200]
                        })
        except Exception:
            pass
        
        # Approach 2: ticker.get_news() (older yfinance)
        if not articles:
            try:
                news = ticker.get_news()
                if news:
                    for article in news[:limit]:
                        articles.append({
                            "title": article.get("title", ""),
                            "publisher": article.get("publisher", ""),
                            "link": article.get("link", ""),
                            "published": article.get("published", ""),
                            "summary": (article.get("summary", "") or "")[:200]
                        })
            except Exception:
                pass
        
        if not articles:
            return {
                "symbol": symbol.replace(".NS", ""),
                "company_name": ticker.info.get("shortName") or symbol,
                "articles_count": 0,
                "news": [],
                "message": "No news available. Yahoo Finance may have changed their API."
            }
        
        return {
            "symbol": symbol.replace(".NS", ""),
            "company_name": ticker.info.get("shortName") or symbol,
            "articles_count": len(articles),
            "news": articles
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_fii_dii_data() -> dict:
    """Get FII/DII daily flow data from NSE website"""
    try:
        import urllib.request
        import re
        
        # NSE FII/DII data page
        url = "https://www.nseindia.com/api/fiidiiTradeReact"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/"
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        if isinstance(data, list) and len(data) > 0:
            latest = data[0]
            return {
                "date": latest.get("date", ""),
                "fii_buy_value_cr": latest.get("fiiBuyValue", 0),
                "fii_sell_value_cr": latest.get("fiiSellValue", 0),
                "fii_net_cr": latest.get("fiiNet", 0),
                "dii_buy_value_cr": latest.get("diiBuyValue", 0),
                "dii_sell_value_cr": latest.get("diiSellValue", 0),
                "dii_net_cr": latest.get("diiNet", 0),
                "net_fii_dii_cr": (latest.get("fiiNet", 0) or 0) + (latest.get("diiNet", 0) or 0),
                "source": "NSE",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
            }
        
        # Fallback: return structure with N/A
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "fii_net_cr": "N/A",
            "dii_net_cr": "N/A",
            "note": "NSE API may require session cookies. Data not available.",
            "source": "NSE (failed)"
        }
    except Exception as e:
        return {
            "error": f"FII/DII data fetch failed: {str(e)}",
            "note": "NSE website may block automated requests. Try manual access."
        }

def tool_get_analyst_recommendations(symbol: str) -> dict:
    """Get analyst recommendations: buy/sell/hold ratings, price targets"""
    try:
        symbol = _fuzzy_match_symbol(symbol)
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        recommendations = []
        rec = info.get("recommendationKey", "")
        if rec:
            recommendations.append({"source": "Yahoo Finance", "rating": rec})
        
        return {
            "symbol": symbol.replace(".NS", ""),
            "company_name": info.get("shortName") or symbol,
            "recommendation": rec or "N/A",
            "target_mean_price": _safe_float(info.get("targetMeanPrice")),
            "target_high_price": _safe_float(info.get("targetHighPrice")),
            "target_low_price": _safe_float(info.get("targetLowPrice")),
            "number_of_analysts": info.get("numberOfAnalystOpinions", "N/A"),
            "recommendations": recommendations
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_earnings_calendar(symbol: str = None) -> dict:
    """Get upcoming earnings dates for Indian stocks"""
    try:
        results = []
        symbols = [symbol] if symbol else [s.replace(".NS", "") for s in NIFTY50[:10]]
        
        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.info
                earnings_date = info.get("earningsDate")
                if earnings_date:
                    if isinstance(earnings_date, list):
                        earnings_date = earnings_date[0]
                    results.append({
                        "symbol": sym,
                        "company_name": info.get("shortName") or sym,
                        "earnings_date": str(earnings_date)[:10] if earnings_date else "N/A",
                        "eps_estimate": _safe_float(info.get("epsEstimate")),
                    })
            except Exception:
                continue
        
        return {"earnings_calendar": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e)}

def tool_get_corporate_actions(symbol: str) -> dict:
    """Get corporate actions: bonuses, splits, dividends"""
    try:
        symbol = _fuzzy_match_symbol(symbol)
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        actions = []
        
        # Dividends
        dividends = ticker.dividends
        if not dividends.empty:
            for date, amount in dividends.tail(5).items():
                actions.append({
                    "type": "dividend",
                    "date": date.strftime("%Y-%m-%d"),
                    "amount": round(float(amount), 2)
                })
        
        # Splits
        splits = ticker.splits
        if not splits.empty:
            for date, ratio in splits.tail(5).items():
                actions.append({
                    "type": "split",
                    "date": date.strftime("%Y-%m-%d"),
                    "ratio": float(ratio)
                })
        
        actions.sort(key=lambda x: x["date"], reverse=True)
        
        return {
            "symbol": symbol.replace(".NS", ""),
            "company_name": info.get("shortName") or symbol,
            "corporate_actions": actions[:10],
            "total_actions": len(actions)
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_heatmap_data() -> dict:
    """Get Nifty 50 heatmap data: all stocks with change%, market cap, sector"""
    try:
        heatmap = []
        for sym in NIFTY50:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                price = _safe_float(getattr(info, 'last_price', None))
                prev = _safe_float(getattr(info, 'previous_close', None))
                if price and prev and prev > 0:
                    pct = ((price - prev) / prev) * 100
                    mcap = _safe_float(ticker.info.get("marketCap"))
                    heatmap.append({
                        "symbol": sym.replace(".NS", ""),
                        "company_name": ticker.info.get("shortName") or sym,
                        "price": price,
                        "change_percent": round(pct, 2),
                        "market_cap_cr": round(mcap / 10000000, 2) if mcap else None,
                        "sector": ticker.info.get("sector", "Unknown")
                    })
            except Exception:
                continue
        
        heatmap.sort(key=lambda x: x.get("change_percent", 0), reverse=True)
        return {"heatmap": heatmap, "count": len(heatmap)}
    except Exception as e:
        return {"error": str(e)}


def tool_get_insider_trading(symbol: str) -> dict:
    """Get insider trading activity: company directors buying/selling"""
    try:
        symbol = _fuzzy_match_symbol(symbol)
        ticker = yf.Ticker(symbol)
        
        # Get insider transactions
        try:
            insider = ticker.insider_transactions
            if insider is not None and not insider.empty:
                transactions = []
                for _, row in insider.head(20).iterrows():
                    transactions.append({
                        "date": str(row.get("Date", ""))[:10],
                        "insider": row.get("Insider", ""),
                        "transaction_type": row.get("Transaction", ""),
                        "shares": int(row.get("Shares", 0)) if row.get("Shares") else 0,
                        "value": _safe_float(row.get("Value")),
                        "shares_after": int(row.get("SharesAfter", 0)) if row.get("SharesAfter") else 0
                    })
                return {
                    "symbol": symbol.replace(".NS", ""),
                    "company_name": ticker.info.get("shortName") or symbol,
                    "transactions": transactions,
                    "count": len(transactions)
                }
        except Exception:
            pass
        
        # Fallback: try insider_roi
        try:
            insider_roi = ticker.insider_roi
            if insider_roi is not None:
                return {
                    "symbol": symbol.replace(".NS", ""),
                    "company_name": ticker.info.get("shortName") or symbol,
                    "insider_roi": _safe_float(insider_roi),
                    "note": "Detailed transactions not available. ROI data shown."
                }
        except Exception:
            pass
        
        return {
            "symbol": symbol.replace(".NS", ""),
            "company_name": ticker.info.get("shortName") or symbol,
            "transactions": [],
            "note": "No insider trading data available for this stock."
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_ipo_calendar() -> dict:
    """Get upcoming IPO calendar for Indian markets"""
    try:
        # Use a simpler approach — return structured data from known sources
        # NSE and BSE have static pages that are easier to scrape
        
        import urllib.request
        
        # Try chittorgarh.com IPO calendar (static HTML)
        url = "https://www.chittorgarh.com/ipo/ipo-calendar/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html"
        }
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            import re
            ipos = []
            
            # Look for IPO names in anchor tags
            ipo_patterns = [
                r'<a[^>]*href="/ipo/[^"]*"[^>]*>([^<]+)</a>',
                r'IPO\s*-\s*([A-Z][A-Za-z\s&]+)',
                r'([A-Z][A-Za-z\s&]+)\s*IPO',
            ]
            
            for pattern in ipo_patterns:
                matches = re.findall(pattern, html)
                for match in matches[:15]:
                    name = match.strip()
                    if len(name) > 3 and len(name) < 50 and not any(x in name.lower() for x in ['login', 'register', 'home', 'about', 'contact', 'privacy', 'terms', 'disclaimer', 'sitemap', 'careers', 'advertise', 'feedback', 'faq', 'help', 'search', 'click', 'here', 'read', 'more', 'view', 'all', 'next', 'prev', 'page', 'first', 'last', 'sort', 'filter', 'show', 'hide', 'open', 'close', 'submit', 'reset', 'cancel', 'save', 'edit', 'delete', 'add', 'new', 'old', 'top', 'bottom', 'left', 'right', 'up', 'down', 'start', 'end', 'begin', 'finish', 'continue', 'back', 'forward', 'previous', 'next', 'skip', 'jump', 'go', 'move', 'scroll', 'swipe', 'tap', 'press', 'hold', 'drag', 'drop', 'zoom', 'pinch', 'rotate', 'flip', 'resize', 'crop', 'cut', 'copy', 'paste', 'undo', 'redo', 'refresh', 'reload', 'restart', 'reboot', 'shutdown', 'sleep', 'wake', 'lock', 'unlock', 'sign', 'log', 'register', 'subscribe', 'unsubscribe', 'follow', 'unfollow', 'like', 'unlike', 'share', 'comment', 'post', 'tweet', 'retweet', 'favorite', 'bookmark', 'download', 'upload', 'import', 'export', 'print', 'scan', 'capture', 'record', 'play', 'pause', 'stop', 'rewind', 'fast', 'slow', 'volume', 'mute', 'unmute', 'brightness', 'contrast', 'saturation', 'hue', 'temperature', 'tint', 'sharpness', 'blur', 'noise', 'grayscale', 'sepia', 'invert', 'mirror', 'flip', 'rotate', 'crop', 'resize', 'scale', 'stretch', 'compress', 'decompress', 'encrypt', 'decrypt', 'encode', 'decode', 'compress', 'decompress', 'archive', 'extract', 'install', 'uninstall', 'update', 'upgrade', 'downgrade', 'patch', 'fix', 'repair', 'restore', 'backup', 'recover', 'reset', 'format', 'erase', 'wipe', 'delete', 'remove', 'clear', 'clean', 'purge', 'flush', 'refresh', 'reload', 'restart', 'reboot', 'shutdown', 'sleep', 'wake', 'lock', 'unlock']):
                        ipos.append({"company": name})
            
            if len(ipos) >= 3:
                return {
                    "ipo_calendar": ipos[:15],
                    "count": len(ipos[:15]),
                    "source": "chittorgarh.com",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
                }
        except Exception:
            pass
        
        # Fallback: return helpful message
        return {
            "ipo_calendar": [],
            "count": 0,
            "source": "fallback",
            "note": "Live IPO calendar requires JavaScript rendering. For latest IPOs visit chittorgarh.com/ipo/ipo-calendar or nseindia.com",
            "alternative_sources": [
                "https://www.chittorgarh.com/ipo/ipo-calendar/",
                "https://www.moneycontrol.com/ipo/",
                "https://www.nseindia.com/market-data/ipos-fpos"
            ],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        }
    except Exception as e:
        return {"error": str(e)}

def tool_ai_screener(query: str) -> dict:
    """AI-powered natural language stock screener. Fast keyword-based parsing."""
    try:
        import time
        start = time.time()
        
        query_lower = query.lower()
        criteria = {}
        
        # Fast keyword matching
        sector_map = {
            "it": "Information Technology", "tech": "Information Technology", "software": "Information Technology",
            "pharma": "Healthcare", "pharmaceutical": "Healthcare", "drug": "Healthcare", "medicine": "Healthcare",
            "bank": "Financial Services", "banking": "Financial Services", "finance": "Financial Services", "financial": "Financial Services",
            "fmcg": "Consumer Defensive", "consumer": "Consumer Defensive",
            "auto": "Industrials", "automobile": "Industrials", "car": "Industrials",
            "energy": "Energy", "oil": "Energy", "gas": "Energy", "petroleum": "Energy",
            "metal": "Basic Materials", "steel": "Basic Materials", "mining": "Basic Materials",
            "real estate": "Real Estate", "reality": "Real Estate", "property": "Real Estate",
            "telecom": "Communication Services", "media": "Communication Services",
            "power": "Utilities", "electricity": "Utilities"
        }
        for keyword, sector in sector_map.items():
            if keyword in query_lower:
                criteria["sector"] = sector
                break
        
        import re
        price_patterns = [r'under\s+rs?\s*(\d+)', r'below\s+rs?\s*(\d+)', r'less than\s+rs?\s*(\d+)', r'cheaper than\s+rs?\s*(\d+)', r'<\s*rs?\s*(\d+)']
        for pattern in price_patterns:
            match = re.search(pattern, query_lower)
            if match:
                criteria["max_price"] = float(match.group(1))
                break
        
        pe_patterns = [r'pe\s*(?:less than|<|under)\s*(\d+)', r'p/e\s*(?:less than|<|under)\s*(\d+)', r'pe\s*<\s*(\d+)']
        for pattern in pe_patterns:
            match = re.search(pattern, query_lower)
            if match:
                criteria["max_pe"] = float(match.group(1))
                break
        
        if any(word in query_lower for word in ["dividend", "yield", "income"]):
            criteria["min_dividend_yield"] = 1.0
        
        if "large cap" in query_lower:
            criteria["min_market_cap_cr"] = 50000
        elif "mid cap" in query_lower:
            criteria["min_market_cap_cr"] = 10000
            criteria["max_market_cap_cr"] = 50000
        elif "small cap" in query_lower:
            criteria["max_market_cap_cr"] = 10000
        
        # Use fast_info only (no slow info call)
        results = []
        for sym in NIFTY50:
            try:
                ticker = yf.Ticker(sym)
                fast = ticker.fast_info
                price = _safe_float(getattr(fast, 'last_price', None))
                
                # Quick price filter
                if "max_price" in criteria and (price is None or price > criteria["max_price"]):
                    continue
                
                # For sector/PE/dividend/mcap filtering, we need info but it's slow
                # So we do a two-pass: first filter by price (fast), then by other criteria
                results.append({
                    "symbol": sym.replace(".NS", ""),
                    "price": price,
                    "ticker": ticker  # Store for second pass
                })
            except Exception:
                continue
        
        # Second pass: apply slow filters only on price-filtered results
        filtered = []
        for r in results[:10]:  # Limit to 10 for speed
            try:
                ticker = r["ticker"]
                info = ticker.info
                sector = info.get("sector", "")
                
                if "sector" in criteria and criteria["sector"].lower() not in sector.lower():
                    continue
                
                pe = _safe_float(info.get("trailingPE"))
                if "max_pe" in criteria and (pe is None or pe > criteria["max_pe"]):
                    continue
                
                div_yield = _safe_float(info.get("dividendYield"))
                if "min_dividend_yield" in criteria and (div_yield is None or div_yield < criteria["min_dividend_yield"]):
                    continue
                
                mcap = _safe_float(info.get("marketCap"))
                mcap_cr = mcap / 10000000 if mcap else None
                
                if "min_market_cap_cr" in criteria and (mcap_cr is None or mcap_cr < criteria["min_market_cap_cr"]):
                    continue
                if "max_market_cap_cr" in criteria and (mcap_cr is None or mcap_cr > criteria["max_market_cap_cr"]):
                    continue
                
                filtered.append({
                    "symbol": r["symbol"],
                    "company_name": info.get("shortName") or r["symbol"],
                    "sector": sector,
                    "pe_ratio": pe,
                    "dividend_yield": div_yield,
                    "price": r["price"],
                    "market_cap_cr": round(mcap_cr, 2) if mcap_cr else None
                })
            except Exception:
                continue
        
        results = filtered
        
        elapsed = time.time() - start
        return {
            "results_count": len(results),
            "data": results[:20],
            "original_query": query,
            "parsed_criteria": criteria,
            "response_time_seconds": round(elapsed, 2)
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_options_chain(symbol: str, expiry: str = None) -> dict:
    """Get options chain data for Nifty/Bank Nifty/individual stocks. Shows strike prices, OI, volume, Greeks."""
    try:
        symbol = _fuzzy_match_symbol(symbol)
        ticker = yf.Ticker(symbol)
        
        # Get available expiry dates
        try:
            expirations = ticker.options
            if not expirations:
                return {"error": f"No options data for {symbol}"}
        except Exception:
            return {"error": f"No options data available for {symbol}"}
        
        # Use first expiry if not specified
        if expiry is None or expiry not in expirations:
            expiry = expirations[0]
        
        # Get options chain
        try:
            opt_chain = ticker.option_chain(expiry)
            calls = opt_chain.calls
            puts = opt_chain.puts
            
            # Format calls data
            calls_data = []
            for _, row in calls.head(20).iterrows():
                calls_data.append({
                    "strike": _safe_float(row.get("strike")),
                    "last_price": _safe_float(row.get("lastPrice")),
                    "bid": _safe_float(row.get("bid")),
                    "ask": _safe_float(row.get("ask")),
                    "volume": int(row.get("volume", 0)) if row.get("volume") else 0,
                    "open_interest": int(row.get("openInterest", 0)) if row.get("openInterest") else 0,
                    "implied_volatility": _safe_float(row.get("impliedVolatility")),
                    "delta": _safe_float(row.get("delta")),
                    "gamma": _safe_float(row.get("gamma")),
                    "theta": _safe_float(row.get("theta")),
                    "vega": _safe_float(row.get("vega"))
                })
            
            # Format puts data
            puts_data = []
            for _, row in puts.head(20).iterrows():
                puts_data.append({
                    "strike": _safe_float(row.get("strike")),
                    "last_price": _safe_float(row.get("lastPrice")),
                    "bid": _safe_float(row.get("bid")),
                    "ask": _safe_float(row.get("ask")),
                    "volume": int(row.get("volume", 0)) if row.get("volume") else 0,
                    "open_interest": int(row.get("openInterest", 0)) if row.get("openInterest") else 0,
                    "implied_volatility": _safe_float(row.get("impliedVolatility")),
                    "delta": _safe_float(row.get("delta")),
                    "gamma": _safe_float(row.get("gamma")),
                    "theta": _safe_float(row.get("theta")),
                    "vega": _safe_float(row.get("vega"))
                })
            
            # Get current price for ATM calculation
            current_price = _safe_float(getattr(ticker.fast_info, 'last_price', None))
            
            return {
                "symbol": symbol.replace(".NS", ""),
                "company_name": ticker.info.get("shortName") or symbol,
                "current_price": current_price,
                "expiry": expiry,
                "available_expiries": list(expirations)[:5],
                "calls": calls_data,
                "puts": puts_data,
                "total_calls": len(calls_data),
                "total_puts": len(puts_data)
            }
        except Exception as e:
            return {"error": f"Failed to fetch options chain: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}

def tool_detect_candlestick_patterns(symbol: str, lookback_days: int = 30) -> dict:
    """Detect candlestick patterns in recent price data"""
    try:
        symbol = _fuzzy_match_symbol(symbol)
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{lookback_days}d")
        
        if hist.empty or len(hist) < 5:
            return {"error": f"Insufficient data for {symbol}"}
        
        patterns = []
        closes = hist['Close'].values
        opens = hist['Open'].values
        highs = hist['High'].values
        lows = hist['Low'].values
        
        for i in range(2, min(len(hist), 10)):
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
            prev_o, prev_c = opens[i-1], closes[i-1]
            prev2_o, prev2_c = opens[i-2], closes[i-2]
            
            body = abs(c - o)
            upper_shadow = h - max(c, o)
            lower_shadow = min(c, o) - l
            total_range = h - l if h > l else 0.01
            
            # Doji
            if body / total_range < 0.1:
                patterns.append({"pattern": "doji", "date": str(hist.index[i])[:10], "signal": "indecision"})
            
            # Hammer
            if lower_shadow > body * 2 and upper_shadow < body * 0.5 and body / total_range > 0.2:
                patterns.append({"pattern": "hammer", "date": str(hist.index[i])[:10], "signal": "bullish_reversal"})
            
            # Bullish Engulfing
            if prev_c < prev_o and c > o and o <= prev_c and c >= prev_o:
                patterns.append({"pattern": "bullish_engulfing", "date": str(hist.index[i])[:10], "signal": "bullish"})
            
            # Bearish Engulfing
            if prev_c > prev_o and c < o and o >= prev_c and c <= prev_o:
                patterns.append({"pattern": "bearish_engulfing", "date": str(hist.index[i])[:10], "signal": "bearish"})
            
            # Morning Star (3-candle bullish reversal)
            if i >= 2 and prev2_c < prev2_o and abs(prev_o - prev_c) < abs(prev2_c - prev2_o) * 0.3 and c > o and c > (prev2_o + prev2_c) / 2:
                patterns.append({"pattern": "morning_star", "date": str(hist.index[i])[:10], "signal": "bullish_reversal"})
        
        return {
            "symbol": symbol.replace(".NS", ""),
            "company_name": ticker.info.get("shortName") or symbol,
            "patterns_detected": patterns,
            "patterns_count": len(patterns),
            "lookback_days": lookback_days
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_news_sentiment(symbol: str) -> dict:
    """Get news sentiment score for a stock"""
    try:
        symbol = _fuzzy_match_symbol(symbol)
        ticker = yf.Ticker(symbol)
        
        # Get news and analyze sentiment
        news = ticker.news
        if not news:
            return {
                "symbol": symbol.replace(".NS", ""),
                "sentiment_score": 0,
                "sentiment": "neutral",
                "articles_analyzed": 0,
                "note": "No news available for sentiment analysis"
            }
        
        # Simple keyword-based sentiment
        bullish_words = ["buy", "bullish", "growth", "profit", "gain", "rise", "surge", "beat", "strong", "positive", "upgrade", "outperform"]
        bearish_words = ["sell", "bearish", "loss", "decline", "fall", "drop", "miss", "weak", "negative", "downgrade", "underperform", "crash"]
        
        score = 0
        articles_analyzed = 0
        
        for article in news[:10]:
            title = (article.get("title", "") or "").lower()
            summary = (article.get("summary", "") or article.get("content", {}).get("summary", "") or "").lower()
            text = title + " " + summary
            
            if text.strip():
                articles_analyzed += 1
                for word in bullish_words:
                    if word in text:
                        score += 10
                for word in bearish_words:
                    if word in text:
                        score -= 10
        
        # Normalize to -100 to +100
        if articles_analyzed > 0:
            score = max(-100, min(100, score))
        
        sentiment = "neutral"
        if score > 20:
            sentiment = "bullish"
        elif score > 50:
            sentiment = "very_bullish"
        elif score < -20:
            sentiment = "bearish"
        elif score < -50:
            sentiment = "very_bearish"
        
        return {
            "symbol": symbol.replace(".NS", ""),
            "company_name": ticker.info.get("shortName") or symbol,
            "sentiment_score": score,
            "sentiment": sentiment,
            "articles_analyzed": articles_analyzed
        }
    except Exception as e:
        return {"error": str(e)}

def tool_get_correlation(symbol: str, period: str = "3mo") -> dict:
        """Find stocks that move with a given stock"""
        try:
            symbol = _fuzzy_match_symbol(symbol)
            ticker = yf.Ticker(symbol)
            target_hist = ticker.history(period=period)
            
            if target_hist.empty:
                return {"error": f"No data for {symbol}"}
            
            target_returns = target_hist['Close'].pct_change().dropna()
            
            correlations = []
            for sym in NIFTY50:
                if sym == symbol:
                    continue
                try:
                    other_ticker = yf.Ticker(sym)
                    other_hist = other_ticker.history(period=period)
                    if not other_hist.empty and len(other_hist) > 10:
                        other_returns = other_hist['Close'].pct_change().dropna()
                        # Align the series
                        common_idx = target_returns.index.intersection(other_returns.index)
                        if len(common_idx) > 10:
                            corr = target_returns.loc[common_idx].corr(other_returns.loc[common_idx])
                            if corr is not None and not (corr != corr):  # not NaN
                                correlations.append({
                                    "symbol": sym.replace(".NS", ""),
                                    "company_name": other_ticker.info.get("shortName") or sym,
                                    "correlation": round(corr, 3),
                                    "relationship": "strong_positive" if corr > 0.7 else "moderate_positive" if corr > 0.4 else "weak" if corr > 0.1 else "negative" if corr < -0.1 else "none"
                                })
                except Exception:
                    continue
            
            correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
            
            return {
                "symbol": symbol.replace(".NS", ""),
                "company_name": ticker.info.get("shortName") or symbol,
                "period": period,
                "top_correlations": correlations[:10],
                "total_analyzed": len(correlations)
            }
        except Exception as e:
            return {"error": str(e)}

def tool_get_mutual_fund_nav(query: str) -> dict:
    """Get mutual fund NAV data"""
    try:
        # Search by fund name using Yahoo Finance
        # Indian mutual funds have .BO suffix
        search_term = query.strip().upper()
        
        # Try direct search
        try:
            ticker = yf.Ticker(f"{search_term}.BO")
            info = ticker.info
            if info and info.get("regularMarketPrice"):
                return {
                    "fund_name": info.get("longName") or info.get("shortName") or search_term,
                    "nav": _safe_float(info.get("regularMarketPrice")),
                    "previous_close": _safe_float(info.get("previousClose")),
                    "currency": "INR",
                    "source": "Yahoo Finance"
                }
        except Exception:
            pass
        
        # Fallback: return popular funds
        popular_funds = {
            "HDFC EQUITY FUND": "119062.BO",
            "SBI BLUE CHIP FUND": "119063.BO",
            "AXIS LONG TERM EQUITY": "119064.BO",
            "ICICI PRUDENTIAL BLUECHIP": "119065.BO",
            "KOTAK SELECT FOCUS": "119066.BO"
        }
        
        for fund_name, code in popular_funds.items():
            if search_term in fund_name:
                try:
                    ticker = yf.Ticker(code)
                    info = ticker.info
                    return {
                        "fund_name": fund_name,
                        "nav": _safe_float(info.get("regularMarketPrice")),
                        "previous_close": _safe_float(info.get("previousClose")),
                        "currency": "INR",
                        "source": "Yahoo Finance"
                    }
                except Exception:
                    continue
        
        return {
            "query": query,
            "note": "Fund not found. Try the full fund name or Yahoo Finance code.",
            "popular_funds": list(popular_funds.keys())
        }
    except Exception as e:
        return {"error": str(e)}

# ─── MCP Tool Registry ──────────────────────────────────────────────

TOOLS = {
    "get_price": {
        "function": tool_get_price,
        "description": "Get live price for any NSE/BSE stock. Args: symbol (e.g., RELIANCE, TCS, INFY.NS)",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}}, "required": ["symbol"]}
    },
    "get_history": {
        "function": tool_get_history,
        "description": "Get historical OHLCV data. Args: symbol, period (1d/5d/1mo/3mo/6mo/1y/2y/5y/10y/ytd/max)",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}, "period": {"type": "string", "default": "1mo"}}, "required": ["symbol"]}
    },
    "get_company_info": {
        "function": tool_get_company_info,
        "description": "Get company fundamentals (sector, market cap, PE, PB, dividend yield, EPS)",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}
    },
    "get_top_gainers": {
        "function": tool_get_top_gainers,
        "description": "Get top gaining stocks on NSE today. Args: limit (default 10)",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}}
    },
    "get_top_losers": {
        "function": tool_get_top_losers,
        "description": "Get top losing stocks on NSE today. Args: limit (default 10)",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}}
    },
    "get_portfolio": {
        "function": tool_get_portfolio,
        "description": "Calculate portfolio value and P&L. Args: holdings_json (JSON array of {symbol, quantity, avg_price})",
        "parameters": {"type": "object", "properties": {"holdings_json": {"type": "string", "description": "JSON string of holdings array"}}, "required": ["holdings_json"]}
    },
    "screen_stocks": {
        "function": tool_screen_stocks,
        "description": "Screen NSE stocks by criteria. Args: criteria_json with min_pe, max_pe, sector, min_dividend_yield, limit",
        "parameters": {"type": "object", "properties": {"criteria_json": {"type": "string", "description": "JSON string of screening criteria"}}}
    },
    "get_crypto_price": {
        "function": tool_get_crypto_price,
        "description": "Get cryptocurrency price in INR. Args: symbol (e.g., BTC-INR, ETH-INR, SOL-INR)",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "default": "BTC-INR"}}}
    },
    "get_market_summary": {
        "function": tool_get_market_summary,
        "description": "Get overall market summary: Nifty 50, Sensex, market breadth",
        "parameters": {"type": "object", "properties": {}}
    },
    "search_stock": {
        "function": tool_search_stock,
        "description": "Search for stocks by name or symbol. Args: query (e.g., 'reliance', 'TCS', 'bank')",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}}, "required": ["query"]}
    },
    "get_sector_performance": {
        "function": tool_get_sector_performance,
        "description": "Get sector-wise performance for NSE stocks. Shows which sectors are up/down today with avg change %.",
        "parameters": {"type": "object", "properties": {}}
    },
    "get_dividend_info": {
        "function": tool_get_dividend_info,
        "description": "Get dividend info for a stock: yield, rate, payout ratio, 5yr avg yield, last 12 dividends. Args: symbol",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}}, "required": ["symbol"]}
    },
    "get_52w_proximity": {
        "function": tool_get_52w_high_low_proximity,
        "description": "Check if stock is near 52-week high/low. Returns signal: near_52w_high, near_52w_low, approaching, or neutral. Args: symbol",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}}, "required": ["symbol"]}
    },
    "get_bulk_quotes": {
        "function": tool_get_bulk_quotes,
        "description": "Get live prices for multiple stocks at once. Args: symbols_json (JSON array like '[\"RELIANCE\",\"TCS\",\"INFY\"]')",
        "parameters": {"type": "object", "properties": {"symbols_json": {"type": "string", "description": "JSON array of stock symbols"}}, "required": ["symbols_json"]}
    },
    "get_index_constituents": {
        "function": tool_get_index_constituents,
        "description": "Get stocks in Indian indices. Args: index (nifty50, niftybank, niftyit, niftyfmcg, niftyauto, niftypharma, niftymetal, niftyreality, niftyenergy)",
        "parameters": {"type": "object", "properties": {"index": {"type": "string", "default": "nifty50", "description": "Index name"}}}
    },
    "compare_stocks": {
        "function": tool_compare_stocks,
        "description": "Compare multiple stocks side by side on price, PE, PB, MCap, dividend yield, sector, 52w range. Args: symbols_json",
        "parameters": {"type": "object", "properties": {"symbols_json": {"type": "string", "description": "JSON array of stock symbols to compare"}}, "required": ["symbols_json"]}
    },
    "get_technical_snapshot": {
        "function": tool_get_technical_snapshot,
        "description": "Get technical analysis snapshot: price, 20MA, 50MA, 52w range position, volume ratio, signals (golden_cross, death_cross, high_volume). Args: symbol",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}}, "required": ["symbol"]}
    },
    "get_stock_chart": {
        "function": tool_get_stock_chart,
        "description": "Generate a stock price chart with moving averages and volume. Args: symbol, period (1mo/3mo/6mo/1y), chart_type (line/candlestick). Returns base64 PNG image.",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}, "period": {"type": "string", "default": "3mo", "description": "Chart period"}, "chart_type": {"type": "string", "default": "line", "description": "Chart type: line or candlestick"}}, "required": ["symbol"]}
    },
    "get_stock_news": {
        "function": tool_get_stock_news,
        "description": "Get latest news for a stock from Yahoo Finance. Args: symbol, limit (default 5)",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}, "limit": {"type": "integer", "default": 5, "description": "Number of news articles"}}, "required": ["symbol"]}
    },
    "get_fii_dii_data": {
        "function": tool_get_fii_dii_data,
        "description": "Get FII/DII (Foreign/Domestic Institutional Investor) daily flow data from NSE. Shows net buying/selling in Crores INR.",
        "parameters": {"type": "object", "properties": {}}
    },
    "get_analyst_recommendations": {
        "function": tool_get_analyst_recommendations,
        "description": "Get analyst recommendations for a stock: buy/sell/hold ratings, price targets. Args: symbol",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}}, "required": ["symbol"]}
    },
    "get_earnings_calendar": {
        "function": tool_get_earnings_calendar,
        "description": "Get upcoming earnings dates for Indian stocks. Shows next earnings date, EPS estimate.",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol (optional, returns all Nifty 50 if not provided)"}}}
    },
    "get_corporate_actions": {
        "function": tool_get_corporate_actions,
        "description": "Get corporate actions for a stock: bonuses, splits, dividends, rights. Args: symbol",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}}, "required": ["symbol"]}
    },
    "get_heatmap_data": {
        "function": tool_get_heatmap_data,
        "description": "Get Nifty 50 heatmap data: all stocks with change%, market cap, sector. Useful for visualization.",
        "parameters": {"type": "object", "properties": {}}
    },
    "get_insider_trading": {
        "function": tool_get_insider_trading,
        "description": "Get insider trading activity for a stock: company directors buying/selling shares. Args: symbol",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}}, "required": ["symbol"]}
    },
    "get_ipo_calendar": {
        "function": tool_get_ipo_calendar,
        "description": "Get upcoming IPO calendar for Indian markets: company name, expected date, price band, issue size.",
        "parameters": {"type": "object", "properties": {}}
    },
    "ai_screener": {
        "function": tool_ai_screener,
        "description": "AI-powered natural language stock screener. Query like 'show me IT stocks under Rs 500 with PE less than 20' or 'undervalued pharma stocks with good dividends'. Args: query (natural language)",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Natural language screening query"}}, "required": ["query"]}
    },
    "detect_candlestick_patterns": {
        "function": tool_detect_candlestick_patterns,
        "description": "Detect candlestick patterns in recent price data: doji, hammer, engulfing, morning star, etc. Args: symbol, lookback_days (default 30)",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}, "lookback_days": {"type": "integer", "default": 30, "description": "Days to analyze"}}, "required": ["symbol"]}
    },
    "get_news_sentiment": {
        "function": tool_get_news_sentiment,
        "description": "Get news sentiment score for a stock from -100 (very bearish) to +100 (very bullish). Args: symbol",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}}, "required": ["symbol"]}
    },
    "get_correlation": {
        "function": tool_get_correlation,
        "description": "Find stocks that move with a given stock. 'Which stocks move with RELIANCE?' Args: symbol, period (default 3mo)",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol"}, "period": {"type": "string", "default": "3mo", "description": "Analysis period"}}, "required": ["symbol"]}
    },
    "get_mutual_fund_nav": {
        "function": tool_get_mutual_fund_nav,
        "description": "Get mutual fund NAV data. Search by fund name or code. Args: query (fund name or code)",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Fund name or code"}}, "required": ["query"]}
    },
    "get_options_chain": {
        "function": tool_get_options_chain,
        "description": "Get options chain data for Nifty/Bank Nifty/stocks. Shows strike prices, OI, volume, Greeks (delta, gamma, theta, vega). Args: symbol, expiry (optional)",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "Stock symbol (e.g., NIFTY, BANKNIFTY, RELIANCE)"}, "expiry": {"type": "string", "description": "Expiry date (optional, uses first available)"}}, "required": ["symbol"]}
    }
}

# ─── MCP Protocol Handler ───────────────────────────────────────────

async def handle_request(request: dict) -> dict:
    """Handle MCP protocol requests."""
    method = request.get("method", "")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "Indian Stock Market MCP", "version": "1.0.0"}
            }
        }
    
    elif method == "tools/list":
        tools_list = []
        for name, tool in TOOLS.items():
            tools_list.append({
                "name": name,
                "description": tool["description"],
                "inputSchema": tool["parameters"]
            })
        return {"jsonrpc": "2.0", "id": request.get("id"), "result": {"tools": tools_list}}
    
    elif method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        if tool_name not in TOOLS:
            return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32602, "message": f"Unknown tool: {tool_name}"}}
        
        try:
            func = TOOLS[tool_name]["function"]
            result = func(**arguments)
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]}
            }
        except Exception as e:
            return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32603, "message": str(e)}}
    
    return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32601, "message": f"Unknown method: {method}"}}

async def main():
    """Main MCP server loop — reads JSON-RPC from stdin, writes to stdout."""
    # Suppress yfinance stderr noise
    import os
    devnull = open(os.devnull, 'w')
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = await handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            continue

# ─── CLI Mode (for testing) ─────────────────────────────────────────

def run_cli():
    if len(sys.argv) < 2:
        print("Indian Stock Market MCP Server v1.0")
        print("=" * 40)
        print("\nAvailable tools:")
        for name, tool in TOOLS.items():
            print(f"  {name}: {tool['description']}")
        print("\nCLI Usage: python mcp_server.py <tool_name> [key=value ...]")
        print("\nExamples:")
        print("  python mcp_server.py get_price symbol=RELIANCE")
        print("  python mcp_server.py get_company_info symbol=INFY")
        print("  python mcp_server.py get_market_summary")
        print("  python mcp_server.py search_stock query=reliance")
        print("\nMCP Mode: python mcp_server.py --mcp")
        return
    
    tool_name = sys.argv[1]
    
    if tool_name == "--mcp":
        asyncio.run(main())
        return
    
    if tool_name not in TOOLS:
        print(f"ERROR: Unknown tool '{tool_name}'")
        print(f"Available: {', '.join(TOOLS.keys())}")
        return
    
    # Parse key=value args
    args = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            try:
                args[k] = int(v)
            except ValueError:
                try:
                    args[k] = float(v)
                except ValueError:
                    args[k] = v
    
    func = TOOLS[tool_name]["function"]
    try:
        result = func(**args)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))

if __name__ == "__main__":
    run_cli()
# ─── MCP Tool Registry ──────────────────────────────────────────────

