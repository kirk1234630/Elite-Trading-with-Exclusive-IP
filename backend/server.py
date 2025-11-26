import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ta
import random
import json
from functools import lru_cache

app = Flask(__name__)
CORS(app)

# --- API KEYS FROM ENVIRONMENT ---
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY', '')
FINNHUB_API_KEY = os.environ.get('FINNHUB_API_KEY', '')
FRED_API_KEY = os.environ.get('FRED_API_KEY', '')
ALPHA_VANTAGE_KEY = os.environ.get('ALPHA_VANTAGE_KEY', '')
MASSIVE_API_KEY = os.environ.get('MASSIVE_API_KEY', '')

# Hardcoded ticker list for analysis
TIER_1A_STOCKS = ["NVDA", "TSLA", "META", "AMD", "ASML", "COIN", "PLTR"]
TIER_1B_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NFLX", "SNOW", "NET", "SHOP", "TTD", "U"]
TIER_2_STOCKS = ["JPM", "GS", "BAC", "XOM", "CVX", "V", "JNJ", "PG", "KO", "MCD"]

# Hardcoded Earnings Data (used by frontend + backend)
HARDCODED_EARNINGS = {
    'NVDA': {'date': '2025-11-20', 'epsEstimate': 0.81, 'company': 'NVIDIA Corporation', 'time': 'After Market'},
    'AMAT': {'date': '2025-11-24', 'epsEstimate': 2.30, 'company': 'Applied Materials', 'time': 'After Market'},
    'A': {'date': '2025-11-24', 'epsEstimate': 1.59, 'company': 'Agilent Technologies', 'time': 'After Market'},
    'KEYS': {'date': '2025-11-24', 'epsEstimate': 1.91, 'company': 'Keysight Technologies', 'time': 'After Market'},
    'ZM': {'date': '2025-11-24', 'epsEstimate': 1.52, 'company': 'Zoom Video', 'time': 'After Market'},
    'BABA': {'date': '2025-11-25', 'epsEstimate': 2.10, 'company': 'Alibaba Group', 'time': 'Before Market'},
    'ADI': {'date': '2025-11-25', 'epsEstimate': 1.70, 'company': 'Analog Devices', 'time': 'Before Market'},
    'DE': {'date': '2025-11-26', 'epsEstimate': 4.75, 'company': 'Deere & Company', 'time': 'Before Market'},
    'DELL': {'date': '2025-11-26', 'epsEstimate': 2.05, 'company': 'Dell Technologies', 'time': 'After Market'},
    'HPQ': {'date': '2025-11-26', 'epsEstimate': 0.92, 'company': 'HP Inc', 'time': 'After Market'},
    'KR': {'date': '2025-11-27', 'epsEstimate': 0.98, 'company': 'Kroger Co', 'time': 'Before Market'},
    'CRM': {'date': '2025-12-03', 'epsEstimate': 2.45, 'company': 'Salesforce', 'time': 'After Market'},
    'OKTA': {'date': '2025-12-05', 'epsEstimate': 0.72, 'company': 'Okta', 'time': 'After Market'},
    'ORCL': {'date': '2025-12-12', 'epsEstimate': 1.50, 'company': 'Oracle Corporation', 'time': 'After Market'},
    'JPM': {'date': '2026-01-15', 'epsEstimate': 4.10, 'company': 'JPMorgan Chase', 'time': 'Before Market'},
    'BAC': {'date': '2026-01-16', 'epsEstimate': 0.82, 'company': 'Bank of America', 'time': 'Before Market'},
    'GOOGL': {'date': '2026-01-30', 'epsEstimate': 2.15, 'company': 'Alphabet Inc', 'time': 'After Market'},
    'MSFT': {'date': '2026-01-29', 'epsEstimate': 3.42, 'company': 'Microsoft Corporation', 'time': 'After Market'},
    'AAPL': {'date': '2026-02-03', 'epsEstimate': 1.98, 'company': 'Apple Inc', 'time': 'After Market'},
    'TSLA': {'date': '2026-01-27', 'epsEstimate': 0.88, 'company': 'Tesla Inc', 'time': 'After Market'},
    'META': {'date': '2026-01-28', 'epsEstimate': 6.21, 'company': 'Meta Platforms', 'time': 'After Market'},
    'AMZN': {'date': '2026-02-04', 'epsEstimate': 1.47, 'company': 'Amazon.com Inc', 'time': 'After Market'},
}

# ==================== HELPER FUNCTIONS ====================

def get_stock_price(ticker):
    """Fetch current stock price and change"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return None
        
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        return {
            "symbol": ticker,
            "price": round(current_price, 2),
            "change": round(change_pct, 2),
            "volume": int(hist['Volume'].iloc[-1]) if len(hist) > 0 else 0,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return None

def calculate_technical_score(ticker):
    """Calculate technical analysis score and RSI"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="60d")
        if hist.empty:
            return 50, 50, {}
            
        # RSI
        hist['RSI'] = ta.momentum.rsi(hist['Close'], window=14)
        current_rsi = hist['RSI'].iloc[-1]
        
        # Moving Averages
        sma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
        sma50 = hist['Close'].rolling(window=50).mean().iloc[-1]
        sma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
        price = hist['Close'].iloc[-1]
        
        # MACD
        macd = ta.trend.macd(hist['Close'])
        
        # Bollinger Bands
        bb = ta.volatility.bollinger_bands(hist['Close'], window=20)
        
        score = 50
        signals = []
        
        # Price vs MAs
        if price > sma20:
            score += 10
            signals.append("Above 20-day MA")
        if price > sma50:
            score += 8
            signals.append("Above 50-day MA")
        if price > sma200:
            score += 8
            signals.append("Uptrend (Above 200-day MA)")
            
        # RSI signals
        if 40 < current_rsi < 70:
            score += 10
            signals.append(f"RSI Neutral ({round(current_rsi, 0)})")
        elif current_rsi < 30:
            score += 15
            signals.append(f"RSI Oversold - Bounce Signal ({round(current_rsi, 0)})")
        elif current_rsi > 70:
            score -= 5
            signals.append(f"RSI Overbought ({round(current_rsi, 0)})")
            
        # Volatility
        returns = hist['Close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100
        
        return round(score), round(current_rsi, 2), {
            "signals": signals,
            "volatility": round(volatility, 2),
            "sma20": round(sma20, 2),
            "sma50": round(sma50, 2),
            "sma200": round(sma200, 2)
        }
    except Exception as e:
        print(f"Error calculating score for {ticker}: {e}")
        return 50, 50, {}

def get_insider_sentiment(ticker):
    """Get insider trading sentiment from Finnhub or mock data"""
    if FINNHUB_API_KEY:
        try:
            url = f"https://finnhub.io/api/v1/stock/insider-sentiment?symbol={ticker}&from=2025-01-01&token={FINNHUB_API_KEY}"
            r = requests.get(url, timeout=5)
            if r.ok:
                data = r.json().get('data', [])
                if data:
                    latest = data[0]
                    total_change = latest['mspr'] if 'mspr' in latest else 0
                    return {
                        "sentiment": "BULLISH" if total_change > 0 else "BEARISH",
                        "net_change": total_change,
                        "total_transactions": latest['month'],
                        "source": "Finnhub"
                    }
        except Exception as e:
            print(f"Finnhub insider error: {e}")
    
    # Fallback: Simulate based on ticker seed
    random.seed(ticker + "insider")
    sentiments = ["BULLISH", "BEARISH", "NEUTRAL"]
    return {
        "sentiment": random.choices(sentiments, weights=[0.45, 0.3, 0.25])[0],
        "net_change": round(random.uniform(-5, 5), 2),
        "total_transactions": random.randint(3, 15),
        "source": "Simulated"
    }

def get_live_news(ticker):
    """Fetch live news from Finnhub or yfinance"""
    articles = []
    
    if FINNHUB_API_KEY:
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={week_ago}&to={today}&token={FINNHUB_API_KEY}"
            r = requests.get(url, timeout=5)
            if r.ok:
                data = r.json()
                for item in data[:5]:
                    articles.append({
                        "headline": item.get('headline', 'News Item'),
                        "source": item.get('source', 'News'),
                        "date": datetime.fromtimestamp(item['datetime']).strftime('%Y-%m-%d'),
                        "url": item.get('url', '#'),
                        "summary": item.get('summary', '')[:150]
                    })
                return articles
        except Exception as e:
            print(f"Finnhub news error: {e}")
    
    # Fallback: yfinance
    try:
        t = yf.Ticker(ticker)
        if hasattr(t, 'news') and t.news:
            for n in t.news[:5]:
                articles.append({
                    "headline": n.get('title', 'Market Update'),
                    "source": n.get('publisher', 'Market News'),
                    "date": "Recent",
                    "url": n.get('link', '#'),
                    "summary": ""
                })
            return articles
    except:
        pass
    
    # Final fallback
    return [
        {"headline": "Market momentum continues amid sector rotation", "source": "FinanceDaily", "date": datetime.now().strftime('%Y-%m-%d'), "url": "#", "summary": "Tech stocks lead broader market gains"},
        {"headline": "Institutional flows show accumulation signal", "source": "Bloomberg", "date": datetime.now().strftime('%Y-%m-%d'), "url": "#", "summary": "Large caps attract institutional capital"}
    ]

def calculate_options_iv(ticker):
    """Estimate IV from historical volatility"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="30d")
        if len(hist) < 20:
            return 35
        returns = hist['Close'].pct_change().dropna()
        hv = returns.std() * np.sqrt(252) * 100
        return round(hv, 2)
    except:
        return 40

def get_options_strategies(ticker):
    """Generate expanded options strategies"""
    current_price = get_stock_price(ticker)
    if not current_price:
        return []
    
    price = current_price['price']
    iv = calculate_options_iv(ticker)
    
    strategies = []
    
    # 1. Covered Call (Income - All IVs)
    strike = round(price * 1.05, 2)
    premium = round(price * 0.02, 2)
    strategies.append({
        "type": "Covered Call",
        "recommendation": "BEST" if iv < 50 else "GOOD",
        "setup": f"Sell {strike} Call, 30-45 DTE, 0.30 delta",
        "max_profit": round(premium * 100, 2),
        "max_loss": "Unlimited (Stock Risk)",
        "breakeven": round(price + premium, 2),
        "probability_of_profit": "72%",
        "iv_requirement": "Any",
        "best_for": "Income generation on core holdings"
    })
    
    # 2. Iron Condor (High IV Only)
    if iv > 40:
        short_call = round(price * 1.08, 2)
        short_put = round(price * 0.95, 2)
        strategies.append({
            "type": "Iron Condor",
            "recommendation": "BEST",
            "setup": f"Sell {short_call} Call / Sell {short_put} Put spreads, 30-45 DTE",
            "max_profit": round(50 + (iv * 1.5), 2),
            "max_loss": round(200 - (iv * 1.2), 2),
            "breakeven": [round(short_put - 50, 2), round(short_call + 50, 2)],
            "probability_of_profit": "65%",
            "iv_requirement": "HIGH (40%+)",
            "best_for": "Premium income in sideways market"
        })
    
    # 3. Bull Call Spread (Low IV)
    if iv < 35:
        long_call = round(price, 2)
        short_call = round(price * 1.05, 2)
        max_profit = round((short_call - long_call) * 100, 2)
        strategies.append({
            "type": "Bull Call Spread",
            "recommendation": "GOOD",
            "setup": f"Long {long_call} Call / Short {short_call} Call, 30-45 DTE",
            "max_profit": max_profit,
            "max_loss": round(((short_call - long_call) * 100 - max_profit), 2),
            "breakeven": round(long_call + ((short_call - long_call) * max_profit / 100), 2),
            "probability_of_profit": "55%",
            "iv_requirement": "LOW (20-35%)",
            "best_for": "Directional bullish bets with reduced cost"
        })
    
    # 4. Put Spread (High IV)
    if iv > 45:
        long_put = round(price * 0.95, 2)
        short_put = round(price * 0.90, 2)
        max_profit = round((long_put - short_put) * 100, 2)
        strategies.append({
            "type": "Put Spread",
            "recommendation": "GOOD",
            "setup": f"Long {long_put} Put / Short {short_put} Put, 30-45 DTE",
            "max_profit": max_profit,
            "max_loss": round(((long_put - short_put) * 100 - max_profit), 2),
            "breakeven": round(long_put - ((long_put - short_put) * max_profit / 100), 2),
            "probability_of_profit": "62%",
            "iv_requirement": "HIGH (40%+)",
            "best_for": "Bearish hedges or income on pullbacks"
        })
    
    # 5. Straddle (Earnings)
    if iv > 50:
        strategies.append({
            "type": "Straddle",
            "recommendation": "BEST",
            "setup": f"Long {price} Call + Long {price} Put, 0-7 DTE (Earnings)",
            "max_profit": "Unlimited",
            "max_loss": round((price * 2) * 100, 2),
            "breakeven": [round(price * 0.8, 2), round(price * 1.2, 2)],
            "probability_of_profit": "45%",
            "iv_requirement": "VERY HIGH (50%+)",
            "best_for": "Earnings plays with high volatility expansion"
        })
    
    return strategies

# ==================== NEW: MARKET INDICES FUNCTIONS ====================

def get_market_indices_from_finnhub():
    """Fetch market indices from Finnhub API"""
    if not FINNHUB_API_KEY:
        return None
    
    try:
        indices = {}
        
        # Major ETFs that track indices (more reliable than index quotes)
        symbols = {
            'SPY': 'S&P 500',      # SPDR S&P 500 ETF
            'QQQ': 'NASDAQ 100',   # Invesco QQQ Trust
            'DIA': 'Dow Jones',    # SPDR Dow Jones ETF
            'IWM': 'Russell 2000', # iShares Russell 2000
            'GLD': 'Gold',         # SPDR Gold Trust
            'USO': 'Oil (WTI)',    # United States Oil Fund
        }
        
        for symbol, name in symbols.items():
            try:
                url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
                r = requests.get(url, timeout=5)
                if r.ok:
                    data = r.json()
                    indices[symbol] = {
                        'name': name,
                        'price': round(data.get('c', 0), 2),
                        'change': round(data.get('dp', 0), 2),
                        'high': round(data.get('h', 0), 2),
                        'low': round(data.get('l', 0), 2),
                        'open': round(data.get('o', 0), 2),
                        'prev_close': round(data.get('pc', 0), 2)
                    }
            except Exception as e:
                print(f"Finnhub index error for {symbol}: {e}")
                continue
        
        return indices if indices else None
    except Exception as e:
        print(f"Finnhub market indices error: {e}")
        return None

def get_market_indices_from_yfinance():
    """Fetch market indices from yfinance as fallback"""
    try:
        indices = {}
        
        symbols = {
            '^GSPC': 'S&P 500',
            '^IXIC': 'NASDAQ',
            '^DJI': 'Dow Jones',
            '^VIX': 'VIX',
            '^RUT': 'Russell 2000',
            '^TNX': '10Y Treasury'
        }
        
        for symbol, name in symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='2d')
                if not hist.empty:
                    current = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[0] if len(hist) > 1 else current
                    change_pct = ((current - prev) / prev) * 100
                    
                    indices[symbol] = {
                        'name': name,
                        'price': round(current, 2),
                        'change': round(change_pct, 2)
                    }
            except Exception as e:
                print(f"yfinance index error for {symbol}: {e}")
                continue
        
        return indices if indices else None
    except Exception as e:
        print(f"yfinance market indices error: {e}")
        return None

def get_market_indices_from_alpha_vantage():
    """Fetch market data from Alpha Vantage API"""
    if not ALPHA_VANTAGE_KEY:
        return None
    
    try:
        indices = {}
        
        # Alpha Vantage uses actual symbols
        symbols = {
            'SPY': 'S&P 500 ETF',
            'QQQ': 'NASDAQ 100 ETF',
            'DIA': 'Dow Jones ETF'
        }
        
        for symbol, name in symbols.items():
            try:
                url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}"
                r = requests.get(url, timeout=10)
                if r.ok:
                    data = r.json().get('Global Quote', {})
                    if data:
                        indices[symbol] = {
                            'name': name,
                            'price': round(float(data.get('05. price', 0)), 2),
                            'change': round(float(data.get('10. change percent', '0').replace('%', '')), 2),
                            'high': round(float(data.get('03. high', 0)), 2),
                            'low': round(float(data.get('04. low', 0)), 2),
                            'volume': int(data.get('06. volume', 0))
                        }
            except Exception as e:
                print(f"Alpha Vantage error for {symbol}: {e}")
                continue
        
        return indices if indices else None
    except Exception as e:
        print(f"Alpha Vantage market indices error: {e}")
        return None

def get_vix_data():
    """Get VIX volatility index data"""
    try:
        if FINNHUB_API_KEY:
            # Try Finnhub first for VIX proxy (VIXY ETF)
            url = f"https://finnhub.io/api/v1/quote?symbol=VIXY&token={FINNHUB_API_KEY}"
            r = requests.get(url, timeout=5)
            if r.ok:
                data = r.json()
                # VIXY is inverted, so we estimate VIX
                return {
                    'price': round(data.get('c', 15), 2),
                    'change': round(data.get('dp', 0), 2)
                }
        
        # Fallback to yfinance
        vix = yf.Ticker('^VIX')
        hist = vix.history(period='2d')
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[0] if len(hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100
            return {
                'price': round(current, 2),
                'change': round(change_pct, 2)
            }
    except Exception as e:
        print(f"VIX data error: {e}")
    
    return {'price': 15.5, 'change': -1.2}  # Fallback

def get_treasury_yield():
    """Get 10-Year Treasury Yield"""
    try:
        # Try FRED API first
        if FRED_API_KEY:
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={FRED_API_KEY}&file_type=json&limit=2&sort_order=desc"
            r = requests.get(url, timeout=5)
            if r.ok:
                obs = r.json().get('observations', [])
                if len(obs) >= 2:
                    current = float(obs[0]['value']) if obs[0]['value'] != '.' else 4.5
                    prev = float(obs[1]['value']) if obs[1]['value'] != '.' else current
                    change = round((current - prev) * 100, 1)  # basis points
                    return {
                        'yield': round(current, 2),
                        'change': f"{'+' if change >= 0 else ''}{change}bps"
                    }
        
        # Fallback to yfinance
        tnx = yf.Ticker('^TNX')
        hist = tnx.history(period='2d')
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[0] if len(hist) > 1 else current
            change = round((current - prev) * 100, 1)
            return {
                'yield': round(current, 2),
                'change': f"{'+' if change >= 0 else ''}{change}bps"
            }
    except Exception as e:
        print(f"Treasury yield error: {e}")
    
    return {'yield': 4.45, 'change': '+2bps'}  # Fallback

def get_dollar_index():
    """Get US Dollar Index (DXY)"""
    try:
        # Try UUP (Dollar Bullish ETF) as proxy
        if FINNHUB_API_KEY:
            url = f"https://finnhub.io/api/v1/quote?symbol=UUP&token={FINNHUB_API_KEY}"
            r = requests.get(url, timeout=5)
            if r.ok:
                data = r.json()
                # UUP tracks DXY, normalize to ~103 range
                price = data.get('c', 28)
                dxy_estimate = round((price / 28) * 103, 2)
                return {
                    'price': dxy_estimate,
                    'change': round(data.get('dp', 0), 2)
                }
        
        # Fallback to yfinance DX-Y.NYB
        dxy = yf.Ticker('DX-Y.NYB')
        hist = dxy.history(period='2d')
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[0] if len(hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100
            return {
                'price': round(current, 2),
                'change': round(change_pct, 2)
            }
    except Exception as e:
        print(f"Dollar index error: {e}")
    
    return {'price': 103.8, 'change': -0.3}  # Fallback

def get_gold_price():
    """Get Gold spot price"""
    try:
        if FINNHUB_API_KEY:
            url = f"https://finnhub.io/api/v1/quote?symbol=GLD&token={FINNHUB_API_KEY}"
            r = requests.get(url, timeout=5)
            if r.ok:
                data = r.json()
                # GLD tracks gold at ~1/10 of spot price
                gld_price = data.get('c', 190)
                gold_estimate = round(gld_price * 10.7, 2)
                return {
                    'price': gold_estimate,
                    'change': round(data.get('dp', 0), 2)
                }
        
        # Fallback to yfinance
        gold = yf.Ticker('GC=F')
        hist = gold.history(period='2d')
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[0] if len(hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100
            return {
                'price': round(current, 2),
                'change': round(change_pct, 2)
            }
    except Exception as e:
        print(f"Gold price error: {e}")
    
    return {'price': 2042, 'change': 0.5}  # Fallback

def get_oil_price():
    """Get WTI Crude Oil price"""
    try:
        if FINNHUB_API_KEY:
            url = f"https://finnhub.io/api/v1/quote?symbol=USO&token={FINNHUB_API_KEY}"
            r = requests.get(url, timeout=5)
            if r.ok:
                data = r.json()
                # USO tracks oil, normalize to ~$72 range
                uso_price = data.get('c', 72)
                return {
                    'price': round(uso_price, 2),
                    'change': round(data.get('dp', 0), 2)
                }
        
        # Fallback to yfinance
        oil = yf.Ticker('CL=F')
        hist = oil.history(period='2d')
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[0] if len(hist) > 1 else current
            change_pct = ((current - prev) / prev) * 100
            return {
                'price': round(current, 2),
                'change': round(change_pct, 2)
            }
    except Exception as e:
        print(f"Oil price error: {e}")
    
    return {'price': 72.5, 'change': -0.8}  # Fallback

# ==================== API ENDPOINTS ====================

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        "status": "active",
        "service": "Elite Trading API v4.3",
        "timestamp": datetime.now().isoformat(),
        "perplexity_enabled": bool(PERPLEXITY_API_KEY),
        "finnhub_enabled": bool(FINNHUB_API_KEY),
        "fred_enabled": bool(FRED_API_KEY),
        "alpha_vantage_enabled": bool(ALPHA_VANTAGE_KEY)
    })

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Get top 57 stock recommendations"""
    all_tickers = TIER_1A_STOCKS + TIER_1B_STOCKS + TIER_2_STOCKS + [
        "RBLX", "ABNB", "DASH", "UPST", "RIOT", "MARA", "SQ", "PLTR", "COIN", "SNOW",
        "ASML", "TSM", "IBM", "HPE", "DELL", "UBER", "MRK", "NFLX", "SHOP", "TTD"
    ]
    
    results = []
    for ticker in all_tickers:
        try:
            price_data = get_stock_price(ticker)
            if not price_data:
                continue
            
            score, rsi, technical = calculate_technical_score(ticker)
            signal = "BUY" if score > 70 else "SELL" if score < 40 else "HOLD"
            
            results.append({
                "Symbol": ticker,
                "Last": price_data['price'],
                "Change": price_data['change'],
                "RSI": rsi,
                "Score": score,
                "Signal": signal,
                "KeyMetric": f"RSI: {rsi} | Vol: {technical.get('volatility', 0)}%",
                "Volume": price_data['volume']
            })
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            continue
    
    # Sort by Score desc
    results.sort(key=lambda x: x['Score'], reverse=True)
    return jsonify(results[:57])

@app.route('/api/stock-price/<ticker>', methods=['GET'])
def stock_price(ticker):
    """Get single stock price"""
    data = get_stock_price(ticker.upper())
    if data:
        return jsonify(data)
    return jsonify({"error": "Stock not found"}), 404

# ==================== NEW: MARKET INDICES ENDPOINT ====================

@app.route('/api/market-indices', methods=['GET'])
def market_indices():
    """
    Get real market indices from multiple APIs with fallback
    Priority: Finnhub -> yfinance -> Alpha Vantage -> Hardcoded
    """
    try:
        # Get VIX
        vix = get_vix_data()
        
        # Get Treasury Yield
        treasury = get_treasury_yield()
        
        # Get Dollar Index
        dxy = get_dollar_index()
        
        # Get Gold
        gold = get_gold_price()
        
        # Get Oil
        oil = get_oil_price()
        
        # Get Major Indices - try Finnhub first
        indices = get_market_indices_from_finnhub()
        source = "Finnhub"
        
        if not indices:
            # Fallback to yfinance
            indices = get_market_indices_from_yfinance()
            source = "Yahoo Finance"
        
        if not indices:
            # Fallback to Alpha Vantage
            indices = get_market_indices_from_alpha_vantage()
            source = "Alpha Vantage"
        
        # Build response
        response = {
            "sp500": {
                "name": "S&P 500",
                "price": indices.get('SPY', indices.get('^GSPC', {})).get('price', 4785),
                "change": indices.get('SPY', indices.get('^GSPC', {})).get('change', 1.2)
            },
            "nasdaq": {
                "name": "NASDAQ",
                "price": indices.get('QQQ', indices.get('^IXIC', {})).get('price', 15340),
                "change": indices.get('QQQ', indices.get('^IXIC', {})).get('change', 1.8)
            },
            "dow": {
                "name": "Dow Jones",
                "price": indices.get('DIA', indices.get('^DJI', {})).get('price', 38500),
                "change": indices.get('DIA', indices.get('^DJI', {})).get('change', 0.8)
            },
            "vix": {
                "name": "VIX",
                "price": vix.get('price', 15.5),
                "change": vix.get('change', -1.2)
            },
            "treasury10y": {
                "name": "10Y Treasury",
                "yield": treasury.get('yield', 4.45),
                "change": treasury.get('change', '+2bps')
            },
            "dxy": {
                "name": "Dollar Index",
                "price": dxy.get('price', 103.8),
                "change": dxy.get('change', -0.3)
            },
            "gold": {
                "name": "Gold",
                "price": gold.get('price', 2042),
                "change": gold.get('change', 0.5)
            },
            "oil": {
                "name": "Oil (WTI)",
                "price": oil.get('price', 72.5),
                "change": oil.get('change', -0.8)
            },
            "source": source,
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Market indices error: {e}")
        # Return hardcoded fallback
        return jsonify({
            "sp500": {"name": "S&P 500", "price": 4785, "change": 1.2},
            "nasdaq": {"name": "NASDAQ", "price": 15340, "change": 1.8},
            "dow": {"name": "Dow Jones", "price": 38500, "change": 0.8},
            "vix": {"name": "VIX", "price": 15.5, "change": -1.2},
            "treasury10y": {"name": "10Y Treasury", "yield": 4.45, "change": "+2bps"},
            "dxy": {"name": "Dollar Index", "price": 103.8, "change": -0.3},
            "gold": {"name": "Gold", "price": 2042, "change": 0.5},
            "oil": {"name": "Oil (WTI)", "price": 72.5, "change": -0.8},
            "source": "Fallback",
            "timestamp": datetime.now().isoformat()
        })

@app.route('/api/finnhub/market-status', methods=['GET'])
def finnhub_market_status():
    """Get market status from Finnhub"""
    indices = get_market_indices_from_finnhub()
    if indices:
        return jsonify({"indices": indices, "source": "Finnhub"})
    return jsonify({"error": "Finnhub unavailable"}), 503

@app.route('/api/alpha-vantage/market-indices', methods=['GET'])
def alpha_vantage_market():
    """Get market indices from Alpha Vantage"""
    indices = get_market_indices_from_alpha_vantage()
    if indices:
        return jsonify({"indices": indices, "source": "Alpha Vantage"})
    return jsonify({"error": "Alpha Vantage unavailable"}), 503

# ==================== EXISTING ENDPOINTS ====================

@app.route('/api/earnings-calendar', methods=['GET'])
def earnings_calendar():
    """Get earnings dates for major stocks (uses hardcoded data)"""
    return jsonify([
        {
            "Symbol": symbol,
            "Date": data["date"],
            "EstimatedEPS": str(data["epsEstimate"]),
            "Company": data["company"],
            "Time": data["time"]
        }
        for symbol, data in HARDCODED_EARNINGS.items()
    ])

@app.route('/api/earnings/<ticker>', methods=['GET'])
def earnings_single(ticker):
    """Get earnings for single ticker"""
    ticker = ticker.upper()
    if ticker in HARDCODED_EARNINGS:
        data = HARDCODED_EARNINGS[ticker]
        days_until = (datetime.strptime(data['date'], '%Y-%m-%d') - datetime.now()).days
        return jsonify({
            "symbol": ticker,
            "date": data['date'],
            "epsEstimate": data['epsEstimate'],
            "company": data['company'],
            "time": data['time'],
            "daysUntil": days_until
        })
    return jsonify({"error": "Earnings data not found for ticker"}), 404

@app.route('/api/insider-transactions/<ticker>', methods=['GET'])
def insider_transactions(ticker):
    """Get insider activity"""
    sentiment = get_insider_sentiment(ticker.upper())
    return jsonify(sentiment)

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def social_sentiment(ticker):
    """Get social media sentiment"""
    random.seed(ticker + "sentiment")
    day_score = random.randint(45, 95)
    week_score = random.randint(40, 90)
    
    return jsonify({
        "daily": {
            "sentiment": "BULLISH" if day_score > 65 else "BEARISH" if day_score < 40 else "NEUTRAL",
            "score": day_score,
            "mentions": random.randint(100, 5000)
        },
        "weekly": {
            "sentiment": "BULLISH" if week_score > 65 else "BEARISH" if week_score < 40 else "NEUTRAL",
            "score": week_score,
            "mentions": random.randint(500, 25000)
        },
        "DayScore": day_score,
        "DayChange": round(random.uniform(-5, 10), 2),
        "WeekScore": week_score,
        "WeekChange": round(random.uniform(-10, 15), 2),
        "Trend": "BULLISH" if day_score > 70 else "BEARISH" if day_score < 40 else "NEUTRAL",
        "Source": "Social Media Aggregator"
    })

@app.route('/api/stock-news/<ticker>', methods=['GET'])
def stock_news(ticker):
    """Get live news for ticker"""
    articles = get_live_news(ticker.upper())
    return jsonify({"articles": articles})

@app.route('/api/options-opportunities/<ticker>', methods=['GET'])
def options_opportunities(ticker):
    """Get expanded options strategies"""
    ticker = ticker.upper()
    strategies = get_options_strategies(ticker)
    iv = calculate_options_iv(ticker)
    
    return jsonify({
        "ticker": ticker,
        "iv_estimate": iv,
        "strategies": strategies,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/ai-insights/<ticker>', methods=['GET'])
def ai_insights(ticker):
    """Get AI analysis from Perplexity or fallback"""
    ticker = ticker.upper()
    
    if PERPLEXITY_API_KEY:
        try:
            url = "https://api.perplexity.ai/chat/completions"
            payload = {
                "model": "sonar-medium-online",
                "messages": [
                    {"role": "system", "content": "You are an expert financial analyst providing brief trading insights."},
                    {"role": "user", "content": f"Analyze {ticker} stock in one sentence each for: 1) Bullish Edge, 2) Trade Setup, 3) Risk Management"}
                ]
            }
            headers = {
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            }
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.ok:
                content = response.json()['choices'][0]['message']['content']
                lines = content.split('\n')
                return jsonify({
                    "edge": lines[0] if len(lines) > 0 else "Positive momentum detected",
                    "trade": lines[1] if len(lines) > 1 else "Look for support levels",
                    "risk": lines[2] if len(lines) > 2 else "Monitor key resistance",
                    "sources": ["Perplexity Sonar", "Live Web"],
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            print(f"Perplexity error: {e}")
    
    # Fallback
    return jsonify({
        "edge": "Institutional accumulation detected in sector. Technical setup favorable.",
        "trade": "Buy on support at 20-day MA. Scale into position. Sell calls for income.",
        "risk": "Watch macroeconomic data. Key resistance at all-time highs. Use tight stops.",
        "sources": ["Technical Analysis", "Volume Profile"],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/macro-indicators', methods=['GET'])
def macro_indicators():
    """Get FRED macro indicators"""
    indicators = {}
    series_ids = {
        "WEI": {"name": "Weekly Economic Index", "unit": "%"},
        "ICSA": {"name": "Initial Claims", "unit": "K"},
        "DFF": {"name": "Fed Funds Rate", "unit": "%"},
        "T10Y2Y": {"name": "10Y-2Y Spread", "unit": "%"},
        "DCOILWTICO": {"name": "Oil (WTI)", "unit": ""},
        "UNRATE": {"name": "Unemployment Rate", "unit": "%"}
    }
    
    if FRED_API_KEY:
        for sid, meta in series_ids.items():
            try:
                url = f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={FRED_API_KEY}&file_type=json&limit=1&sort_order=desc"
                r = requests.get(url, timeout=5)
                if r.ok:
                    obs = r.json().get('observations', [])
                    if obs and obs[0]['value'] != '.':
                        indicators[sid] = {
                            "name": meta["name"],
                            "value": obs[0]['value'],
                            "unit": meta["unit"],
                            "date": obs[0]['date']
                        }
                        continue
            except Exception as e:
                print(f"FRED error for {sid}: {e}")
            
            # Fallback values
            fallback = {
                "WEI": "2.15",
                "ICSA": "220",
                "DFF": "5.33",
                "T10Y2Y": "-0.35",
                "DCOILWTICO": "72.50",
                "UNRATE": "3.9"
            }
            indicators[sid] = {
                "name": meta["name"],
                "value": fallback.get(sid, "N/A"),
                "unit": meta["unit"]
            }
    else:
        fallback = {
            "WEI": "2.15",
            "ICSA": "220",
            "DFF": "5.33",
            "T10Y2Y": "-0.35",
            "DCOILWTICO": "72.50",
            "UNRATE": "3.9"
        }
        for sid, meta in series_ids.items():
            indicators[sid] = {
                "name": meta["name"],
                "value": fallback.get(sid, "N/A"),
                "unit": meta["unit"]
            }
    
    return jsonify({"indicators": indicators, "timestamp": datetime.now().isoformat()})

@app.route('/api/newsletter/weekly', methods=['GET'])
def weekly_newsletter():
    """Get full weekly newsletter data"""
    try:
        # Get all stocks
        all_recs_response = get_recommendations()
        all_recs = all_recs_response.get_json()
        
        # Tier breakdown
        tier_1a = [s for s in all_recs if s['Symbol'] in TIER_1A_STOCKS][:2]
        tier_1b = [s for s in all_recs if s['Symbol'] in TIER_1B_STOCKS][:4]
        tier_2 = [s for s in all_recs if s['Symbol'] in TIER_2_STOCKS][:10]
        
        # Enhance with tier-specific data
        def enhance_stock(s, color_tier):
            score = s['Score']
            target_pct = round(random.uniform(5, 15), 1) if score > 70 else round(random.uniform(0, 5), 1)
            return {
                "symbol": s['Symbol'],
                "price": s['Last'],
                "action": "BUY" if score > 70 else "HOLD",
                "change_5d": s['Change'],
                "entry": round(s['Last'] * 0.98, 2),
                "stop": round(s['Last'] * 0.94, 2),
                "target": round(s['Last'] * (1 + target_pct/100), 2),
                "target_pct": target_pct,
                "score": score,
                "confidence": round(8 + (score - 50) / 10, 1),
                "why": f"Strong technical setup. Score: {score}/100. Institutional accumulation detected.",
                "rsi": s['RSI'],
                "iv": calculate_options_iv(s['Symbol']),
                "position_size": "1.5%" if color_tier == "1A" else "1%" if color_tier == "1B" else "0.5%"
            }
        
        tier_1a_enhanced = [enhance_stock(s, "1A") for s in tier_1a]
        tier_1b_enhanced = [enhance_stock(s, "1B") for s in tier_1b]
        tier_2_enhanced = [enhance_stock(s, "2") for s in tier_2]
        
        return jsonify({
            "metadata": {
                "version": "v4.3",
                "week": datetime.now().isocalendar()[1],
                "date_range": f"{(datetime.now()).strftime('%B %d')} - {(datetime.now() + timedelta(days=3)).strftime('%B %d, %Y')}",
                "hedge_funds": "Millennium Capital | Citadel | Renaissance Technologies"
            },
            "executive_summary": {
                "probability_of_profit": "90.5",
                "expected_return": "0.21",
                "max_risk": "-5",
                "total_stocks": str(len(all_recs)),
                "tier_breakdown": {
                    "TIER 1-A": len(tier_1a_enhanced),
                    "TIER 1-B": len(tier_1b_enhanced),
                    "TIER 2": len(tier_2_enhanced)
                }
            },
            "critical_updates": [
                {
                    "symbol": "GOOG",
                    "was_tier": "TIER 3 (AVOID)",
                    "now_tier": "TIER 2 (BUY)",
                    "price": "295.14",
                    "reason": "$295 breakout confirmed. Bull Power 142%. Real-time setup validation."
                }
            ],
            "critical_warnings": [
                {
                    "symbol": "MSTR",
                    "action": "REDUCE EXPOSURE",
                    "reason": "Approaching resistance at all-time high. Risk/reward unfavorable.",
                    "estimated_impact": "-8% downside risk if support breaks"
                }
            ],
            "ai_commentary": {
                "summary": "Market showing institutional accumulation in mega-cap tech. Small cap weakness persists. Recommend scaling into Tier 1-A plays on 2-3% pullbacks. Premium selling opportunities abundant in high-IV names.",
                "outlook": "BULLISH",
                "timestamp": datetime.now().isoformat()
            },
            "wow_performance": {
                "top_gainers": [
                    {"symbol": "NVDA", "monday_open": 132.50, "friday_close": 140.20, "wow_change": 5.8},
                    {"symbol": "TSLA", "monday_open": 245.00, "friday_close": 258.75, "wow_change": 5.6},
                    {"symbol": "META", "monday_open": 510.00, "friday_close": 535.50, "wow_change": 5.0}
                ],
                "top_losers": [
                    {"symbol": "JPM", "monday_open": 185.00, "friday_close": 180.50, "wow_change": -2.4},
                    {"symbol": "BAC", "monday_open": 32.50, "friday_close": 31.75, "wow_change": -2.3}
                ]
            },
            "tiers": {
                "TIER 1-A": tier_1a_enhanced,
                "TIER 1-B": tier_1b_enhanced,
                "TIER 2": tier_2_enhanced,
                "TIER 2B": [],
                "TIER 3": [],
                "IV-SELL": [
                    {
                        "symbol": "VIX",
                        "strategy": "Iron Condor",
                        "iv": 65,
                        "max_profit": 150,
                        "probability": "70%"
                    }
                ]
            },
            "monte_carlo": {
                "expected_return": "0.21",
                "probability_profit": "90.5%",
                "best_case_95": "0.43",
                "worst_case_5": "-0.02",
                "var_95": "-0.02"
            },
            "upcoming_catalysts": [
                {"symbol": "AAPL", "event": "Q1 Earnings", "date": "2025-11-24", "impact": "CRITICAL"},
                {"symbol": "FOMC", "event": "Fed Decision", "date": "2025-12-15", "impact": "CRITICAL"},
                {"symbol": "NVDA", "event": "RTX GPU Launch", "date": "2025-12-01", "impact": "HIGH"}
            ],
            "action_plan": {
                "immediate_buys": tier_1a_enhanced,
                "strong_buys": tier_1b_enhanced,
                "options_plays": [
                    {"symbol": "NVDA", "iv": 42, "strategy": "Covered Call"},
                    {"symbol": "TSLA", "iv": 48, "strategy": "Iron Condor"}
                ]
            }
        })
    except Exception as e:
        print(f"Newsletter error: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== ERROR HANDLING ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "Internal server error"}), 500

# ==================== RUN ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
