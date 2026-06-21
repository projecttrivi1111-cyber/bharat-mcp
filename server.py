"""
Indian Stock Market MCP Server
Tools for NSE/BSE stock data, portfolio tracking, and market analysis.
Uses Yahoo Finance API (yfinance) - free, no API key needed.
"""

import json
import sys
from datetime import datetime, timedelta
from typing import Optional

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed. Run: pip install yfinance", file=sys.stderr)
    sys.exit(1)

# ─── Helper Functions ───────────────────────────────────────────────

def _resolve_symbol(symbol: str) -> str:
    """Ensure symbol has .NS (NSE) or .BSE (BSE) suffix."""
    symbol = symbol.strip().upper()
    if not symbol.endswith(".NS") and not symbol.endswith(".BSE"):
        symbol = symbol + ".NS"  # Default to NSE
    return symbol

def _safe_float(value) -> Optional[float]:
    """Safely convert to float, handling None/NaN."""
    if value is None:
        return None
    try:
        f = float(value)
        if f != f:  # NaN check
            return None
        return round(f, 2)
    except (TypeError, ValueError):
        return None

def _format_number(value: float) -> str:
    """Format large numbers in Indian style (Lakh/Crore)."""
    if value is None:
        return "N/A"
    if value >= 10000000:
        return f"₹{value/10000000:.2f} Cr"
    elif value >= 100000:
        return f"₹{value/100000:.2f} L"
    else:
        return f"₹{value:,.2f}"

# ─── Tool: get_price ────────────────────────────────────────────────

def get_price(symbol: str) -> dict:
    """Get live price for any NSE/BSE stock.
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE', 'TCS', 'INFY.NS')
    
    Returns:
        dict with price, change, change_percent, day_high, day_low, volume, company_name
    """
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
            "source": "Yahoo Finance"
        }
        
        # Calculate change
        if result["price"] and result["previous_close"]:
            change = result["price"] - result["previous_close"]
            result["change"] = round(change, 2)
            result["change_percent"] = round((change / result["previous_close"]) * 100, 2)
        
        return result
    except Exception as e:
        return {"error": f"Failed to fetch price for {symbol}: {str(e)}"}

# ─── Tool: get_history ──────────────────────────────────────────────

def get_history(symbol: str, period: str = "1mo") -> dict:
    """Get historical price data for a stock.
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE', 'TCS.NS')
        period: Time period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
    
    Returns:
        dict with historical OHLCV data
    """
    try:
        symbol = _resolve_symbol(symbol)
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        
        if hist.empty:
            return {"error": f"No data found for {symbol} with period {period}"}
        
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
        
        return {
            "symbol": symbol,
            "period": period,
            "data_points": len(data),
            "data": data[-30:]  # Last 30 data points max
        }
    except Exception as e:
        return {"error": f"Failed to fetch history for {symbol}: {str(e)}"}

# ─── Tool: get_company_info ─────────────────────────────────────────

def get_company_info(symbol: str) -> dict:
    """Get company information and fundamentals.
    
    Args:
        symbol: Stock symbol (e.g., 'RELIANCE', 'TCS.NS')
    
    Returns:
        dict with company details, sector, market cap, PE ratio, etc.
    """
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
            "currency": info.get("currency", "INR"),
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
            "description": info.get("longBusinessSummary", "N/A")[:500] if info.get("longBusinessSummary") else "N/A"
        }
    except Exception as e:
        return {"error": f"Failed to fetch company info for {symbol}: {str(e)}"}

# ─── Tool: get_top_gainers ──────────────────────────────────────────

def get_top_gainers(limit: int = 10) -> dict:
    """Get top gaining stocks on NSE for the day.
    
    Args:
        limit: Number of stocks to return (default 10)
    
    Returns:
        dict with list of top gainers
    """
    try:
        # NSE Nifty 50 symbols for scanning (excluding delisted TATAMOTORS)
        nifty50 = [
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
        
        gainers = []
        for sym in nifty50:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                price = _safe_float(getattr(info, 'last_price', None))
                prev_close = _safe_float(getattr(info, 'previous_close', None))
                
                if price and prev_close and prev_close > 0:
                    change_pct = ((price - prev_close) / prev_close) * 100
                    gainers.append({
                        "symbol": sym.replace(".NS", ""),
                        "company_name": ticker.info.get("shortName") or sym,
                        "price": price,
                        "change_percent": round(change_pct, 2),
                        "volume": int(getattr(info, 'last_volume', 0)) if getattr(info, 'last_volume', None) else 0
                    })
            except Exception:
                continue
        
        # Sort by change_percent descending
        gainers.sort(key=lambda x: x.get("change_percent", 0), reverse=True)
        
        return {
            "type": "top_gainers",
            "count": min(limit, len(gainers)),
            "data": gainers[:limit],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        }
    except Exception as e:
        return {"error": f"Failed to fetch top gainers: {str(e)}"}

# ─── Tool: get_top_losers ───────────────────────────────────────────

def get_top_losers(limit: int = 10) -> dict:
    """Get top losing stocks on NSE for the day.
    
    Args:
        limit: Number of stocks to return (default 10)
    
    Returns:
        dict with list of top losers
    """
    try:
        # NSE Nifty 50 symbols for scanning (excluding delisted TATAMOTORS)
        nifty50 = [
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
        
        losers = []
        for sym in nifty50:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.fast_info
                price = _safe_float(getattr(info, 'last_price', None))
                prev_close = _safe_float(getattr(info, 'previous_close', None))
                
                if price and prev_close and prev_close > 0:
                    change_pct = ((price - prev_close) / prev_close) * 100
                    losers.append({
                        "symbol": sym.replace(".NS", ""),
                        "company_name": ticker.info.get("shortName") or sym,
                        "price": price,
                        "change_percent": round(change_pct, 2),
                        "volume": int(getattr(info, 'last_volume', 0)) if getattr(info, 'last_volume', None) else 0
                    })
            except Exception:
                continue
        
        # Sort by change_percent ascending (most negative first)
        losers.sort(key=lambda x: x.get("change_percent", 0))
        
        return {
            "type": "top_losers",
            "count": min(limit, len(losers)),
            "data": losers[:limit],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        }
    except Exception as e:
        return {"error": f"Failed to fetch top losers: {str(e)}"}

# ─── Tool: get_portfolio ────────────────────────────────────────────

def get_portfolio(holdings: list) -> dict:
    """Calculate portfolio value and P&L.
    
    Args:
        holdings: List of dicts with 'symbol' and 'quantity' keys
                 Example: [{"symbol": "RELIANCE", "quantity": 10}, {"symbol": "TCS", "quantity": 5}]
    
    Returns:
        dict with portfolio summary and individual stock details
    """
    try:
        total_value = 0
        total_invested = 0
        stocks = []
        
        for holding in holdings:
            symbol = holding.get("symbol", "")
            quantity = holding.get("quantity", 0)
            avg_price = holding.get("avg_price", 0)
            
            if not symbol or quantity <= 0:
                continue
            
            price_data = get_price(symbol)
            if "error" in price_data:
                continue
            
            current_price = price_data.get("price", 0)
            current_value = current_price * quantity
            invested_value = avg_price * quantity if avg_price else 0
            pnl = current_value - invested_value
            pnl_pct = ((current_price - avg_price) / avg_price * 100) if avg_price and avg_price > 0 else 0
            
            total_value += current_value
            total_invested += invested_value
            
            stocks.append({
                "symbol": symbol,
                "company_name": price_data.get("company_name", symbol),
                "quantity": quantity,
                "avg_price": avg_price,
                "current_price": current_price,
                "current_value": round(current_value, 2),
                "invested_value": round(invested_value, 2),
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_pct, 2),
                "weight": 0  # Will be calculated after total
            })
        
        # Calculate weights
        for stock in stocks:
            if total_value > 0:
                stock["weight"] = round((stock["current_value"] / total_value) * 100, 2)
        
        total_pnl = total_value - total_invested
        total_pnl_pct = ((total_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
        
        return {
            "portfolio": {
                "total_value": round(total_value, 2),
                "total_invested": round(total_invested, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_percent": round(total_pnl_pct, 2),
                "num_stocks": len(stocks)
            },
            "holdings": stocks,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        }
    except Exception as e:
        return {"error": f"Failed to calculate portfolio: {str(e)}"}

# ─── Tool: screen_stocks ────────────────────────────────────────────

def screen_stocks(
    min_pe: Optional[float] = None,
    max_pe: Optional[float] = None,
    min_market_cap: Optional[float] = None,
    max_market_cap: Optional[float] = None,
    sector: Optional[str] = None,
    min_dividend_yield: Optional[float] = None,
    limit: int = 20
) -> dict:
    """Screen NSE stocks based on criteria.
    
    Args:
        min_pe: Minimum PE ratio
        max_pe: Maximum PE ratio
        min_market_cap: Minimum market cap (in Crores)
        max_market_cap: Maximum market cap (in Crores)
        sector: Sector name (e.g., 'Technology', 'Financial Services')
        min_dividend_yield: Minimum dividend yield percentage
        limit: Max results to return
    
    Returns:
        dict with screened stocks
    """
    try:
        nifty50 = [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
            "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS", "ITC.NS",
            "LT.NS", "AXISBANK.NS", "WIPRO.NS", "ASIANPAINT.NS", "MARUTI.NS",
            "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "POWERGRID.NS",
            "NTPC.NS", "TATAMOTORS.NS", "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS",
            "BAJFINANCE.NS", "HCLTECH.NS", "TECHM.NS", "DRREDDY.NS", "CIPLA.NS",
            "BRITANNIA.NS", "HEROMOTOCO.NS", "EICHERMOT.NS", "DIVISLAB.NS", "APOLLOHOSP.NS",
            "INDUSINDBK.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "GRASIM.NS",
            "ONGC.NS", "BPCL.NS", "IOC.NS", "TATACONSUM.NS", "SBILIFE.NS",
            "HDFCLIFE.NS", "BAJAJFINSV.NS", "M&M.NS", "PIDILITIND.NS"
        ]
        
        results = []
        for sym in nifty50:
            try:
                ticker = yf.Ticker(sym)
                info = ticker.info
                
                pe = _safe_float(info.get("trailingPE"))
                mcap = _safe_float(info.get("marketCap"))
                div_yield = _safe_float(info.get("dividendYield"))
                stock_sector = info.get("sector", "")
                
                # Convert market cap to Crores for comparison
                mcap_cr = mcap / 10000000 if mcap else None
                
                # Apply filters
                if min_pe is not None and (pe is None or pe < min_pe):
                    continue
                if max_pe is not None and (pe is None or pe > max_pe):
                    continue
                if min_market_cap is not None and (mcap_cr is None or mcap_cr < min_market_cap):
                    continue
                if max_market_cap is not None and (mcap_cr is None or mcap_cr > max_market_cap):
                    continue
                if sector is not None and sector.lower() not in stock_sector.lower():
                    continue
                if min_dividend_yield is not None and (div_yield is None or div_yield < min_dividend_yield):
                    continue
                
                results.append({
                    "symbol": sym.replace(".NS", ""),
                    "company_name": info.get("shortName") or sym,
                    "sector": stock_sector,
                    "pe_ratio": pe,
                    "market_cap_cr": round(mcap_cr, 2) if mcap_cr else None,
                    "dividend_yield": div_yield
                })
            except Exception:
                continue
        
        return {
            "screening_criteria": {
                "min_pe": min_pe,
                "max_pe": max_pe,
                "min_market_cap_cr": min_market_cap,
                "max_market_cap_cr": max_market_cap,
                "sector": sector,
                "min_dividend_yield": min_dividend_yield
            },
            "results_count": len(results),
            "data": results[:limit],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        }
    except Exception as e:
        return {"error": f"Failed to screen stocks: {str(e)}"}

# ─── Tool: get_crypto_price ─────────────────────────────────────────

def get_crypto_price(symbol: str = "bitcoin", inr: bool = True) -> dict:
    """Get cryptocurrency price in INR or USD.
    
    Args:
        symbol: Crypto symbol (e.g., 'bitcoin', 'ethereum', 'solana', 'cardano')
        inr: If True, return price in INR; if False, USD
    
    Returns:
        dict with crypto price data
    """
    try:
        # Yahoo Finance uses different format for crypto
        # Try multiple formats
        formats = [
            f"{symbol.upper()}-{'INR' if inr else 'USD'}",
            f"{symbol[:3].upper()}-{'INR' if inr else 'USD'}",
        ]
        
        for fmt in formats:
            try:
                ticker = yf.Ticker(fmt)
                info = ticker.fast_info
                price = _safe_float(getattr(info, 'last_price', None))
                if price:
                    return {
                        "crypto": symbol.upper(),
                        "currency": "INR" if inr else "USD",
                        "price": price,
                        "previous_close": _safe_float(getattr(info, 'previous_close', None)),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
                        "source": "Yahoo Finance"
                    }
            except Exception:
                continue
        
        return {"error": f"Could not fetch crypto price for {symbol}. Try: BTC-INR, ETH-INR, SOL-INR"}
    except Exception as e:
        return {"error": f"Failed to fetch crypto price for {symbol}: {str(e)}"}

# ─── CLI Interface ──────────────────────────────────────────────────

TOOLS = {
    "get_price": {
        "function": get_price,
        "description": "Get live price for any NSE/BSE stock",
        "args": {"symbol": "Stock symbol (e.g., RELIANCE, TCS, INFY.NS)"}
    },
    "get_history": {
        "function": get_history,
        "description": "Get historical price data",
        "args": {"symbol": "Stock symbol", "period": "Time period (1d/5d/1mo/3mo/6mo/1y/2y/5y/10y/ytd/max)"}
    },
    "get_company_info": {
        "function": get_company_info,
        "description": "Get company information and fundamentals",
        "args": {"symbol": "Stock symbol"}
    },
    "get_top_gainers": {
        "function": get_top_gainers,
        "description": "Get top gaining stocks on NSE",
        "args": {"limit": "Number of results (default 10)"}
    },
    "get_top_losers": {
        "function": get_top_losers,
        "description": "Get top losing stocks on NSE",
        "args": {"limit": "Number of results (default 10)"}
    },
    "get_portfolio": {
        "function": get_portfolio,
        "description": "Calculate portfolio value and P&L",
        "args": {"holdings": "List of {symbol, quantity, avg_price}"}
    },
    "screen_stocks": {
        "function": screen_stocks,
        "description": "Screen stocks by PE, market cap, sector, dividend yield",
        "args": {"min_pe": "Min PE", "max_pe": "Max PE", "sector": "Sector name", "limit": "Max results"}
    },
    "get_crypto_price": {
        "function": get_crypto_price,
        "description": "Get cryptocurrency price in INR",
        "args": {"symbol": "Crypto name (bitcoin, ethereum, etc.)", "inr": "True for INR, False for USD"}
    }
}

def run_cli():
    """Run as CLI tool for testing."""
    if len(sys.argv) < 2:
        print("Indian Stock Market MCP Server")
        print("=" * 40)
        print("\nAvailable tools:")
        for name, tool in TOOLS.items():
            print(f"  {name}: {tool['description']}")
        print("\nUsage: python server.py <tool_name> [args...]")
        print("\nExamples:")
        print('  python server.py get_price RELIANCE')
        print('  python server.py get_history TCS 1mo')
        print('  python server.py get_company_info INFY')
        print('  python server.py get_top_gainers')
        print('  python server.py get_top_losers')
        print('  python server.py get_crypto_price bitcoin')
        return
    
    tool_name = sys.argv[1]
    if tool_name not in TOOLS:
        print(f"ERROR: Unknown tool '{tool_name}'")
        print(f"Available: {', '.join(TOOLS.keys())}")
        return
    
    # Parse arguments
    args = sys.argv[2:]
    func = TOOLS[tool_name]["function"]
    
    try:
        if tool_name == "get_price":
            result = func(args[0] if args else "RELIANCE")
        elif tool_name == "get_history":
            result = func(args[0] if args else "RELIANCE", args[1] if len(args) > 1 else "1mo")
        elif tool_name == "get_company_info":
            result = func(args[0] if args else "RELIANCE")
        elif tool_name == "get_top_gainers":
            result = func(int(args[0]) if args else 10)
        elif tool_name == "get_top_losers":
            result = func(int(args[0]) if args else 10)
        elif tool_name == "get_portfolio":
            # Parse JSON holdings from file or stdin
            if args:
                holdings = json.loads(args[0])
            else:
                holdings = [{"symbol": "RELIANCE", "quantity": 10, "avg_price": 1200}]
            result = func(holdings)
        elif tool_name == "screen_stocks":
            kwargs = {}
            for arg in args:
                if "=" in arg:
                    k, v = arg.split("=", 1)
                    try:
                        kwargs[k] = float(v)
                    except ValueError:
                        kwargs[k] = v
            result = func(**kwargs)
        elif tool_name == "get_crypto_price":
            result = func(args[0] if args else "bitcoin", True)
        else:
            result = func()
        
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))

if __name__ == "__main__":
    run_cli()
