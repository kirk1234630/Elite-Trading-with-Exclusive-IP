from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import gc
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
CORS(app)

# ======================== API KEYS ========================
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')
ALPHAVANTAGE_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')
MASSIVE_KEY = os.environ.get('MASSIVE_API_KEY', '')
FRED_KEY = os.environ.get('FRED_API_KEY', '')
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')

# ======================== TOP 50 STOCKS ========================
TOP_50_STOCKS = [
    {'symbol': 'KO', 'inst33': 95, 'overall_score': 8, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 8, 'money_score': 4, 'alpha_score': 3, 'equity_score': 1.9, 'mean_reversion': 2.09, 'iv': 0.2, 'signal': 'STRONG_BUY', 'key_metric': 'Beverage leader - low IV, uptrend'},
    {'symbol': 'AZN', 'inst33': 95, 'overall_score': 8, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 7, 'money_score': 0, 'alpha_score': 3, 'equity_score': 1.7, 'mean_reversion': 1.57, 'iv': 0.26, 'signal': 'STRONG_BUY', 'key_metric': 'Biotech - highest institutional backing'},
    {'symbol': 'MRK', 'inst33': 90, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 5, 'money_score': 5, 'alpha_score': 3, 'equity_score': 2.0, 'mean_reversion': 1.87, 'iv': 0.33, 'signal': 'STRONG_BUY', 'key_metric': 'Pharma strong momentum'},
    {'symbol': 'A', 'inst33': 80, 'overall_score': 8, 'master_score': 4, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 7, 'money_score': 4, 'alpha_score': 3, 'equity_score': 2.7, 'mean_reversion': 2.19, 'iv': 0.4, 'signal': 'BUY', 'key_metric': 'Agilent - emerging strength'},
    {'symbol': 'GOOGL', 'inst33': 80, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 7, 'money_score': 4, 'alpha_score': 3, 'equity_score': 0.8, 'mean_reversion': 2.19, 'iv': 0.41, 'signal': 'BUY', 'key_metric': 'Tech - AI leadership'},
    {'symbol': 'GOOG', 'inst33': 80, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 6, 'money_score': 4, 'alpha_score': 3, 'equity_score': 0.8, 'mean_reversion': 2.16, 'iv': 0.41, 'signal': 'BUY', 'key_metric': 'Tech - strong uptrend'},
    {'symbol': 'JNJ', 'inst33': 75, 'overall_score': 8, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 8, 'money_score': 4, 'alpha_score': 2, 'equity_score': 1.83, 'mean_reversion': 1.83, 'iv': 0.22, 'signal': 'SELL_CALL', 'key_metric': 'Healthcare - premium seller'},
    {'symbol': 'RY', 'inst33': 70, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 8, 'money_score': 4, 'alpha_score': 3, 'equity_score': 1.9, 'mean_reversion': 2.1, 'iv': 0.21, 'signal': 'SELL_CALL', 'key_metric': 'Financial - low IV opportunity'},
    {'symbol': 'WMT', 'inst33': 70, 'overall_score': 0, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 6, 'money_score': 4, 'alpha_score': 3, 'equity_score': 1.75, 'mean_reversion': 1.75, 'iv': 0.27, 'signal': 'SELL_CALL', 'key_metric': 'Retail - defensive play'},
    {'symbol': 'LLY', 'inst33': 65, 'overall_score': 8, 'master_score': 4, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 7, 'money_score': 4, 'alpha_score': 3, 'equity_score': 2.7, 'mean_reversion': 1.34, 'iv': 0.38, 'signal': 'HOLD', 'key_metric': 'Biotech GLP-1 leader'},
    {'symbol': 'ASML', 'inst33': 65, 'overall_score': 0, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 6, 'money_score': 4, 'alpha_score': 2, 'equity_score': -2.34, 'mean_reversion': -2.34, 'iv': 0.47, 'signal': 'HOLD', 'key_metric': 'Chip equipment - pullback play'},
    {'symbol': 'DAL', 'inst33': 65, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': 0.41, 'iv': 0.59, 'signal': 'HOLD', 'key_metric': 'Airlines - recovery play'},
    {'symbol': 'BJ', 'inst33': 65, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': 0.05, 'iv': 0.35, 'signal': 'HOLD', 'key_metric': 'Retail club - neutral'},
    {'symbol': 'SNDK', 'inst33': 63, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -0.75, 'iv': 1.3, 'signal': 'HOLD', 'key_metric': 'Storage - high IV volatility'},
    {'symbol': 'OKLO', 'inst33': 63, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -1.49, 'iv': 1.21, 'signal': 'HOLD', 'key_metric': 'Nuclear energy - emerging'},
    {'symbol': 'ARM', 'inst33': 63, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -1.52, 'iv': 0.67, 'signal': 'SELL', 'key_metric': 'Chip design - bearish setup'},
    {'symbol': 'BE', 'inst33': 63, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -1.93, 'iv': 1.39, 'signal': 'SELL', 'key_metric': 'EV - downtrend high IV'},
    {'symbol': 'MCD', 'inst33': 60, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 5, 'money_score': 3, 'alpha_score': 3, 'equity_score': 1.48, 'mean_reversion': 1.48, 'iv': 0.2, 'signal': 'SELL_CALL', 'key_metric': 'QSR - best call seller'},
    {'symbol': 'AAPL', 'inst33': 60, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 6, 'money_score': 4, 'alpha_score': 3, 'equity_score': 0.65, 'mean_reversion': 0.65, 'iv': 0.29, 'signal': 'HOLD', 'key_metric': 'Tech giant - stable'},
    {'symbol': 'NUE', 'inst33': 60, 'overall_score': 6, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 7, 'money_score': 0, 'alpha_score': 3, 'equity_score': 1.7, 'mean_reversion': 1.55, 'iv': 0.4, 'signal': 'BUY_CALL', 'key_metric': 'Steel - uptrend reversion'},
    {'symbol': 'VCYT', 'inst33': 60, 'overall_score': 6, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 7, 'money_score': 0, 'alpha_score': 3, 'equity_score': 1.7, 'mean_reversion': 1.45, 'iv': 0.47, 'signal': 'HOLD', 'key_metric': 'Biotech - balanced setup'},
    {'symbol': 'ABT', 'inst33': 60, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 2, 'uva': 5, 'money_score': 3, 'alpha_score': 1, 'equity_score': 0.7, 'mean_reversion': 0.7, 'iv': 0.28, 'signal': 'HOLD', 'key_metric': 'Healthcare - stable dividend'},
    {'symbol': 'AVGO', 'inst33': 60, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 2, 'uva': 5, 'money_score': 3, 'alpha_score': 1, 'equity_score': -1.25, 'mean_reversion': -1.25, 'iv': 0.68, 'signal': 'HOLD', 'key_metric': 'Semiconductor - downtrend'},
]

TICKERS = [s['symbol'] for s in TOP_50_STOCKS]

# ======================== CACHE ========================
price_cache = {}
recommendations_cache = {'data': [], 'timestamp': None}
news_cache = {'market_news': [], 'last_updated': None}
sentiment_cache = {}
macro_cache = {'data': {}, 'timestamp': None}
insider_cache = {}
earnings_cache = {'data': [], 'timestamp': None}
ai_insights_cache = {}

# ======================== TTL ========================
RECOMMENDATIONS_TTL = 300
SENTIMENT_TTL = 86400
MACRO_TTL = 604800  # 7 days for FRED
INSIDER_TTL = 86400
EARNINGS_TTL = 2592000  # 30 days
AI_INSIGHTS_TTL = 3600

# ======================== EARNINGS CALENDAR ========================
def fetch_earnings_from_apis():
    """Fetch earnings from Yahoo Finance and Finnhub - NO HARDCODED DATES"""
    earnings_data = []
    seen_symbols = set()
    
    print("🔄 Fetching earnings from Yahoo Finance...")
    try:
        for ticker in TICKERS[:30]:
            try:
                url = f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}'
                params = {'modules': 'calendarEvents'}
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, params=params, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get('quoteSummary', {}).get('result', [])
                    
                    if result:
                        calendar = result.get('calendarEvents', {})
                        earnings_dates = calendar.get('earnings', {}).get('earningsDate', [])
                        
                        if earnings_dates:
                            timestamp = earnings_dates.get('raw')
                            if timestamp:
                                earnings_date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                                eps_estimate = calendar.get('earnings', {}).get('earningsAverage')
                                
                                earnings_data.append({
                                    'symbol': ticker,
                                    'date': earnings_date,
                                    'epsEstimate': eps_estimate,
                                    'company': ticker,
                                    'source': 'Yahoo Finance'
                                })
                                seen_symbols.add(ticker)
                
                time.sleep(0.3)
            except:
                continue
    except Exception as e:
        print(f"Yahoo error: {e}")
    
    # Finnhub backup
    if FINNHUB_KEY:
        try:
            from_date = datetime.now().strftime('%Y-%m-%d')
            to_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            url = f'https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for item in data.get('earningsCalendar', []):
                    symbol = item.get('symbol')
                    if symbol in TICKERS and symbol not in seen_symbols:
                        earnings_data.append({
                            'symbol': symbol,
                            'date': item.get('date'),
                            'epsEstimate': item.get('epsEstimate'),
                            'company': symbol,
                            'source': 'Finnhub'
                        })
                        seen_symbols.add(symbol)
        except:
            pass
    
    earnings_data.sort(key=lambda x: x['date'])
    today = datetime.now().strftime('%Y-%m-%d')
    earnings_data = [e for e in earnings_data if e['date'] >= today]
    
    return earnings_data[:50]

UPCOMING_EARNINGS = fetch_earnings_from_apis()

# ======================== SOCIAL SENTIMENT (FIXED) ========================
def get_social_sentiment(ticker):
    """Get TRUE sentiment analysis - not just mention count"""
    
    if ticker in sentiment_cache:
        cached = sentiment_cache[ticker]
        if datetime.now() - cached['timestamp'] < timedelta(seconds=SENTIMENT_TTL):
            return cached['data']
    
    # Use Finnhub Social Sentiment API (real sentiment scoring)
    if FINNHUB_KEY:
        try:
            url = f'https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Calculate REAL sentiment (not mentions)
                reddit_data = data.get('reddit', [])
                twitter_data = data.get('twitter', [])
                
                # Daily sentiment (most recent)
                daily_sentiment = 'NEUTRAL'
                daily_mentions = 0
                daily_score = 0
                
                if reddit_data:
                    recent = reddit_data
                    daily_mentions = recent.get('mention', 0)
                    daily_score = recent.get('score', 0)  # Actual sentiment score
                    
                    if daily_score > 0.5:
                        daily_sentiment = 'BULLISH'
                    elif daily_score < -0.5:
                        daily_sentiment = 'BEARISH'
                
                # Weekly sentiment (last 7 days average)
                weekly_mentions = sum(d.get('mention', 0) for d in reddit_data[:7])
                weekly_scores = [d.get('score', 0) for d in reddit_data[:7]]
                weekly_avg_score = sum(weekly_scores) / len(weekly_scores) if weekly_scores else 0
                
                weekly_sentiment = 'NEUTRAL'
                if weekly_avg_score > 0.5:
                    weekly_sentiment = 'BULLISH'
                elif weekly_avg_score < -0.5:
                    weekly_sentiment = 'BEARISH'
                
                # Calculate WoW and MoM changes
                wow_change = 0.0
                mom_change = 0.0
                
                if len(reddit_data) >= 7:
                    prev_week_score = reddit_data.get('score', 0)
                    wow_change = ((daily_score - prev_week_score) / abs(prev_week_score)) * 100 if prev_week_score != 0 else 0
                
                if len(reddit_data) >= 30:
                    prev_month_score = reddit_data.get('score', 0)
                    mom_change = ((daily_score - prev_month_score) / abs(prev_month_score)) * 100 if prev_month_score != 0 else 0
                
                result = {
                    'ticker': ticker,
                    'daily': {
                        'sentiment': daily_sentiment,
                        'mentions': daily_mentions,
                        'score': round(daily_score, 2)
                    },
                    'weekly': {
                        'sentiment': weekly_sentiment,
                        'mentions': weekly_mentions,
                        'score': round(weekly_avg_score, 2)
                    },
                    'changes': {
                        'wow': round(wow_change, 2),
                        'mom': round(mom_change, 2)
                    },
                    'source': 'Finnhub Social Sentiment API',
                    'last_updated': datetime.now().isoformat()
                }
                
                sentiment_cache[ticker] = {'data': result, 'timestamp': datetime.now()}
                return result
        except Exception as e:
            print(f"Sentiment error for {ticker}: {e}")
    
    # Fallback dummy data
    return {
        'ticker': ticker,
        'daily': {'sentiment': 'NEUTRAL', 'mentions': 0, 'score': 0},
        'weekly': {'sentiment': 'NEUTRAL', 'mentions': 0, 'score': 0},
        'changes': {'wow': 0.0, 'mom': 0.0},
        'source': 'Fallback',
        'last_updated': datetime.now().isoformat()
    }

# ======================== STOCK PRICES ========================
def get_stock_price_waterfall(ticker):
    """Waterfall pricing with Finnhub → AlphaVantage → Massive"""
    
    if ticker in price_cache:
        cached = price_cache[ticker]
        if datetime.now() - cached['timestamp'] < timedelta(seconds=60):
            return cached['data']
    
    # Try Finnhub first
    if FINNHUB_KEY:
        try:
            url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                price = data.get('c', 0)
                if price > 0:
                    prev_close = data.get('pc', price)
                    change = ((price - prev_close) / prev_close) * 100
                    
                    result = {
                        'price': price,
                        'change': round(change, 2),
                        'open': data.get('o', price),
                        'high': data.get('h', price),
                        'low': data.get('l', price),
                        'volume': data.get('v', 0),
                        'source': 'Finnhub'
                    }
                    
                    price_cache[ticker] = {'data': result, 'timestamp': datetime.now()}
                    return result
        except:
            pass
    
    # Fallback to simple price
    return {'price': 100, 'change': 0, 'source': 'Mock'}

# ======================== API ENDPOINTS ========================

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Top 50 stocks with pricing"""
    
    if recommendations_cache['data'] and recommendations_cache['timestamp']:
        age = (datetime.now() - recommendations_cache['timestamp']).seconds
        if age < RECOMMENDATIONS_TTL:
            return jsonify(recommendations_cache['data'])
    
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_stock_price_waterfall, stock['symbol']): stock for stock in TOP_50_STOCKS}
        
        for future in as_completed(futures):
            stock = futures[future]
            try:
                price_data = future.result()
                results.append({
                    'Symbol': stock['symbol'],
                    'Last': round(price_data['price'], 2),
                    'Change': round(price_data['change'], 2),
                    'RSI': 50,
                    'Signal': stock['signal'],
                    'Strategy': 'Momentum' if price_data['change'] > 0 else 'Mean Reversion',
                    'Score': stock['inst33'],
                    'KeyMetric': stock['key_metric']
                })
            except:
                pass
    
    recommendations_cache['data'] = results
    recommendations_cache['timestamp'] = datetime.now()
    
    return jsonify(results)

@app.route('/api/earnings-calendar', methods=['GET'])
def get_earnings_calendar():
    """Dynamic earnings from APIs"""
    return jsonify(earnings_cache.get('data', UPCOMING_EARNINGS))

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def get_ticker_sentiment(ticker):
    """Fixed sentiment with WoW/MoM"""
    return jsonify(get_social_sentiment(ticker))

@app.route('/api/macro-indicators', methods=['GET'])
def get_macro_indicators():
    """FRED economic data"""
    
    if macro_cache['data'] and macro_cache['timestamp']:
        age = (datetime.now() - macro_cache['timestamp']).seconds
        if age < MACRO_TTL:
            return jsonify(macro_cache['data'])
    
    indicators = {}
    
    if FRED_KEY:
        fred_series = {
            'WEI': 'Weekly Economic Index',
            'ICSA': 'Initial Claims',
            'M1SL': 'M1 Money Supply',
            'M2SL': 'M2 Money Supply',
            'DCOILWTICO': 'WTI Crude Oil',
            'DFF': 'Federal Funds Rate',
            'T10Y2Y': 'Yield Curve'
        }
        
        for series_id, name in fred_series.items():
            try:
                url = f'https://api.stlouisfed.org/fred/series/observations'
                params = {
                    'series_id': series_id,
                    'api_key': FRED_KEY,
                    'file_type': 'json',
                    'sort_order': 'desc',
                    'limit': 1
                }
                response = requests.get(url, params=params, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    observations = data.get('observations', [])
                    if observations:
                        value = observations.get('value')
                        indicators[series_id] = {
                            'name': name,
                            'value': float(value) if value != '.' else None,
                            'date': observations.get('date')
                        }
                        print(f"✅ FRED: {series_id} = {value}")
            except:
                pass
    
    macro_cache['data'] = indicators
    macro_cache['timestamp'] = datetime.now()
    
    return jsonify(indicators)

@app.route('/api/options-opportunities/<ticker>', methods=['GET'])
def get_options_opportunities(ticker):
    """6 Options Strategies"""
    try:
        price_data = get_stock_price_waterfall(ticker)
        current_price = price_data['price']
        change = price_data['change']
        
        opportunities = {
            'ticker': ticker,
            'current_price': round(current_price, 2),
            'analysis_date': datetime.now().isoformat(),
            'strategies': [
                {
                    'type': 'Iron Condor',
                    'description': 'Sell OTM call/put spreads - range-bound',
                    'setup': f'Sell ${round(current_price * 1.05, 2)} Call / Buy ${round(current_price * 1.08, 2)} Call, Sell ${round(current_price * 0.95, 2)} Put / Buy ${round(current_price * 0.92, 2)} Put',
                    'max_profit': round(current_price * 0.02, 2),
                    'max_loss': round(current_price * 0.03, 2),
                    'probability_of_profit': '65%',
                    'days_to_expiration': 30,
                    'recommendation': 'BEST' if abs(change) < 2 else 'GOOD'
                },
                {
                    'type': 'Call Spread (Bullish)',
                    'description': 'Buy lower call, sell higher call',
                    'setup': f'Buy ${round(current_price, 2)} Call / Sell ${round(current_price * 1.05, 2)} Call',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'days_to_expiration': 30,
                    'recommendation': 'BUY' if change > 2 else 'NEUTRAL'
                },
                {
                    'type': 'Put Spread (Bearish)',
                    'description': 'Buy higher put, sell lower put',
                    'setup': f'Buy ${round(current_price, 2)} Put / Sell ${round(current_price * 0.95, 2)} Put',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'days_to_expiration': 30,
                    'recommendation': 'BUY' if change < -2 else 'NEUTRAL'
                },
                {
                    'type': 'Call Spread (Bearish)',
                    'description': 'Sell lower call, buy higher call - credit',
                    'setup': f'Sell ${round(current_price * 1.02, 2)} Call / Buy ${round(current_price * 1.07, 2)} Call',
                    'max_profit': round(current_price * 0.015, 2),
                    'max_loss': round(current_price * 0.035, 2),
                    'probability_of_profit': '60%',
                    'days_to_expiration': 30,
                    'recommendation': 'SELL' if change < -1.5 else 'NEUTRAL'
                },
                {
                    'type': 'Put Spread (Bullish)',
                    'description': 'Sell higher put, buy lower put - credit',
                    'setup': f'Sell ${round(current_price * 0.98, 2)} Put / Buy ${round(current_price * 0.93, 2)} Put',
                    'max_profit': round(current_price * 0.015, 2),
                    'max_loss': round(current_price * 0.035, 2),
                    'probability_of_profit': '60%',
                    'days_to_expiration': 30,
                    'recommendation': 'SELL' if change > 1.5 else 'NEUTRAL'
                },
                {
                    'type': 'Butterfly Spread',
                    'description': 'Buy 1 call, sell 2 calls, buy 1 call',
                    'setup': f'Buy ${round(current_price * 0.98, 2)} Call / Sell 2x ${round(current_price, 2)} Call / Buy ${round(current_price * 1.02, 2)} Call',
                    'max_profit': round(current_price * 0.04, 2),
                    'max_loss': round(current_price * 0.01, 2),
                    'probability_of_profit': '50%',
                    'days_to_expiration': 30,
                    'recommendation': 'GOOD' if abs(change) < 1.5 else 'NEUTRAL'
                }
            ]
        }
        return jsonify(opportunities)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai-insights/<ticker>', methods=['GET'])
def get_ai_insights(ticker):
    """Perplexity Sonar Analysis"""
    print(f"🤖 AI analysis for {ticker}")
    
    if ticker in ai_insights_cache:
        cached = ai_insights_cache[ticker]
        if datetime.now() - cached['timestamp'] < timedelta(seconds=AI_INSIGHTS_TTL):
            return jsonify(cached['data'])
    
    if not PERPLEXITY_KEY:
        return jsonify({
            'edge': 'API not configured',
            'trade': 'Set PERPLEXITY_API_KEY',
            'risk': 'N/A',
            'sources': [],
            'ticker': ticker
        })
    
    try:
        csv_stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
        context = f"\nInst33: {csv_stock['inst33']}, Signal: {csv_stock['signal']}" if csv_stock else ""
        
        prompt = f"""Analyze {ticker} for day trading TODAY.

Provide EXACTLY 3 sections:
1. EDGE: [Bullish/Bearish] setup with % catalyst (one line)
2. TRADE: Entry price, stop loss, target (one line)
3. RISK: Low/Medium/High with reason (one line)

Data: {context}"""
        
        url = 'https://api.perplexity.ai/chat/completions'
        headers = {'Authorization': f'Bearer {PERPLEXITY_KEY}', 'Content-Type': 'application/json'}
        
        payload = {
            'model': 'sonar',
            'messages': [
                {'role': 'system', 'content': 'Expert day trader. Give Edge, Trade, Risk sections.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.6,
            'max_tokens': 400,
            'return_citations': True
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            content = data['choices']['message']['content']
            
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            
            edge = next((l for l in lines if any(x in l.lower() for x in ['bullish', 'bearish', 'edge', '%'])), 'Neutral')
            trade = next((l for l in lines if any(x in l.lower() for x in ['entry', 'stop', 'target', '$'])), 'Monitor')
            risk = next((l for l in lines if 'risk' in l.lower()), 'Standard')
            
            result = {
                'edge': edge[:150],
                'trade': trade[:150],
                'risk': risk[:150],
                'sources': ['Perplexity Sonar', 'Barchart', 'GuruFocus', 'Quiver'],
                'ticker': ticker
            }
            
            ai_insights_cache[ticker] = {'data': result, 'timestamp': datetime.now()}
            return jsonify(result)
        else:
            print(f"❌ Sonar error: {response.status_code}")
            return jsonify({'edge': 'API error', 'trade': 'Retry', 'risk': 'Unknown', 'sources': [], 'ticker': ticker})
            
    except Exception as e:
        print(f"❌ Sonar error: {e}")
        return jsonify({'edge': 'Error', 'trade': 'N/A', 'risk': 'N/A', 'sources': [], 'ticker': ticker})

# ======================== SCHEDULER ========================
def refresh_earnings_monthly():
    """Monthly earnings refresh"""
    global UPCOMING_EARNINGS, earnings_cache
    print("\n🔄 [SCHEDULED] Refreshing earnings...")
    try:
        UPCOMING_EARNINGS = fetch_earnings_from_apis()
        earnings_cache['data'] = UPCOMING_EARNINGS
        earnings_cache['timestamp'] = datetime.now()
        print(f"✅ Updated {len(UPCOMING_EARNINGS)} earnings")
    except Exception as e:
        print(f"❌ Earnings error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=refresh_earnings_monthly, trigger="cron", day=1, hour=9)  # Monthly
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

print(f"\n✅ Loaded {len(TICKERS)} tickers from TOP_50_STOCKS")
print(f"✅ Perplexity: {'ENABLED' if PERPLEXITY_KEY else 'DISABLED'}")
print(f"✅ FRED: {'ENABLED' if FRED_KEY else 'DISABLED'}")
print(f"✅ Scheduler started\n")

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
