# TRIKAAL Market — Indian Stock Market MCP Server

**The most comprehensive Indian stock market MCP server for AI agents.**

31 tools. Zero setup. Free real-time data from Yahoo Finance.

## 🚀 Quick Start

```bash
cd mcp-indian-stock
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python mcp_server.py get_price symbol=RELIANCE
```

## 📊 31 Tools

### Price & History
- `get_price` — Live NSE/BSE stock prices
- `get_history` — Historical OHLCV data (1d to 10y)
- `get_company_info` — Fundamentals (PE, PB, MCap, EPS, dividend yield)
- `get_bulk_quotes` — Multiple stocks at once

### Market Overview
- `get_market_summary` — Nifty 50, Sensex, market breadth
- `get_top_gainers` — Top NSE gainers today
- `get_top_losers` — Top NSE losers today
- `get_sector_performance` — Sector-wise performance
- `get_heatmap_data` — Nifty 50 heatmap (change%, MCap, sector)

### Portfolio & Screening
- `get_portfolio` — Portfolio P&L calculator
- `screen_stocks` — Filter by PE, sector, dividend yield
- `ai_screener` — Natural language screener ("IT stocks under Rs 500 with PE < 20")
- `compare_stocks` — Side-by-side comparison
- `get_correlation` — "Which stocks move with RELIANCE?"

### Analysis
- `get_technical_snapshot` — MA20, MA50, volume ratio, signals
- `detect_candlestick_patterns` — Doji, hammer, engulfing, morning star
- `get_analyst_recommendations` — Buy/sell/hold ratings, price targets
- `get_news_sentiment` — Sentiment score (-100 to +100)
- `get_stock_chart` — Price charts with moving averages (base64 PNG)

### News & Data
- `get_stock_news` — Latest stock news from Yahoo Finance
- `get_fii_dii_data` — FII/DII daily flow from NSE
- `get_dividend_info` — Dividend yield, history, payout ratio
- `get_corporate_actions` — Bonuses, splits, dividends
- `get_earnings_calendar` — Upcoming earnings dates
- `get_insider_trading` — Company director buying/selling

### Indices & Funds
- `get_index_constituents` — Stocks in Nifty Bank, Nifty IT, etc.
- `get_ipo_calendar` — Upcoming IPOs
- `get_mutual_fund_nav` — Mutual fund NAV data
- `search_stock` — Find stocks by name or symbol

## 🔧 MCP Configuration

### Claude Desktop
```json
{
  "mcpServers": {
    "trikaal-market": {
      "command": "python",
      "args": ["/path/to/mcp_server.py", "--mcp"]
    }
  }
}
```

### Cursor
Add to `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "trikaal-market": {
      "command": "python",
      "args": ["/path/to/mcp_server.py", "--mcp"]
    }
  }
}
```

## 💰 Pricing

- **Free**: 100 requests/day (price + history + market status)
- **Pro ₹999/mo**: Everything + screener + portfolio + alerts
- **Enterprise ₹2499/mo**: API access + bulk + white-label

## 🏗️ Built by TRIKAAL

Trivi + KAITO-LAPTOP + KAITO-PHONE

Three pillars. One entity. Transforming Indian market data for AI agents.
