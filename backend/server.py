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

# ======================== CACHE ========================
price_cache = {}
recommendations_cache = {'data': [], 'timestamp': None}
news_cache = {'market_news': [], 'last_updated': None}
sentiment_cache = {}
macro_cache = {'data': {}, 'timestamp': None}
insider_cache = {}
earnings_cache = {'data': [], 'timestamp': None}

# ======================== TTL ========================
RECOMMENDATIONS_TTL = 300
SENTIMENT_TTL = 86400
MACRO_TTL = 3600
INSIDER_TTL = 86400
EARNINGS_TTL = 2592000

# Chart tracking
chart_after_hours = {'enabled': True, 'last_refresh': None}

# ======================== DYNAMIC TICKER LOADING ========================
def load_tickers():
    """Load tickers from environment variable, config file, or default"""
    tickers_env = os.environ.get('STOCK_TICKERS', '')
    if tickers_env:
        try:
            return json.loads(tickers_env)
        except:
            return [t.strip().upper() for t in tickers_env.split(',') if t.strip()]
    
    if os.path.exists('tickers.json'):
        try:
            with open('tickers.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading tickers.json: {e}")
    
    return [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'AMD', 'CRM', 'ADBE',
        'NFLX', 'PYPL', 'SHOP', 'RBLX', 'DASH', 'ZOOM', 'SNOW', 'CRWD', 'NET', 'ABNB',
        'UPST', 'COIN', 'RIOT', 'MARA', 'CLSK', 'MSTR', 'SQ', 'PLTR', 'ASML', 'INTU',
        'SNPS', 'MU', 'QCOM', 'AVGO', 'LRCX', 'TSM', 'INTC', 'VMW', 'SEMR',
        'SGRY', 'PSTG', 'DDOG', 'OKTA', 'ZS', 'CHKP', 'PANW', 'SMAR', 'NOW', 'VEEV',
        'TWLO', 'GTLB', 'ORCL', 'IBM', 'HPE', 'DELL', 'CSCO'
    ]

def load_earnings():
    """Load earnings from cache or environment"""
    if earnings_cache['data'] and earnings_cache['timestamp']:
        cache_age = (datetime.now() - earnings_cache['timestamp']).total_seconds()
        if cache_age < EARNINGS_TTL:
            return earnings_cache['data']
    
    earnings_env = os.environ.get('UPCOMING_EARNINGS', '')
    if earnings_env:
        try:
            return json.loads(earnings_env)
        except:
            pass
    
    if os.path.exists('earnings.json'):
        try:
            with open('earnings.json', 'r') as f:
                return json.load(f)
        except:
            pass
    
    return [
        {'symbol': 'NVDA', 'report': '2025-11-24', 'epsEstimate': 0.73, 'company': 'NVIDIA'},
        {'symbol': 'MSFT', 'report': '2025-11-25', 'epsEstimate': 2.80, 'company': 'Microsoft'},
        {'symbol': 'AAPL', 'report': '2025-11-25', 'epsEstimate': 2.15, 'company': 'Apple'},
    ]

# Initialize at startup
TICKERS = load_tickers()
UPCOMING_EARNINGS = load_earnings()

print(f"✅ Loaded {len(TICKERS)} tickers")
print(f"✅ Loaded {len(UPCOMING_EARNINGS)} upcoming earnings")
print(f"✅ FINNHUB_KEY: {'ENABLED' if FINNHUB_KEY else 'DISABLED (using fallback)'}")

# ======================== SCHEDULED TASKS ========================

def refresh_earnings_monthly():
    """Refresh earnings data once per month"""
    global UPCOMING_EARNINGS
    print("\n🔄 [SCHEDULED] Refreshing earnings data (MONTHLY)...")
    
    try:
        if FINNHUB_KEY:
            from_date = datetime.now().strftime('%Y-%m-%d')
            to_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            url = f'https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                UPCOMING_EARNINGS = data.get('earningsCalendar', [])[:50]
                earnings_cache['data'] = UPCOMING_EARNINGS
                earnings_cache['timestamp'] = datetime.now()
                
                with open('earnings.json', 'w') as f:
                    json.dump(UPCOMING_EARNINGS, f)
                
                print(f"✅ Updated {len(UPCOMING_EARNINGS)} earnings records")
                return
    except Exception as e:
        print(f"❌ Earnings refresh error: {e}")
    
    print("⚠️  Earnings refresh failed - using cached data")

def refresh_social_sentiment_daily():
    """Refresh social sentiment daily"""
    global sentiment_cache
    print("\n🔄 [SCHEDULED] Clearing social sentiment cache (DAILY)...")
    sentiment_cache.clear()
    print(f"✅ Sentiment cache cleared")

def refresh_insider_activity_daily():
    """Refresh insider activity daily"""
    global insider_cache
    print("\n🔄 [SCHEDULED] Clearing insider activity cache (DAILY)...")
    insider_cache.clear()
    print(f"✅ Insider cache cleared")

def cleanup_price_chart_cache():
    """Keep only after-hours price data"""
    global chart_after_hours
    now = datetime.now()
    market_close_hour = 16
    
    if now.hour >= market_close_hour or now.weekday() >= 4:
        chart_after_hours['enabled'] = True
    else:
        chart_after_hours['enabled'] = False

# ======================== SCHEDULER ========================
scheduler = BackgroundScheduler()

scheduler.add_job(
    func=refresh_earnings_monthly,
    trigger="cron",
    day=1,
    hour=9,
    minute=0,
    id='refresh_earnings_monthly'
)

scheduler.add_job(
    func=refresh_social_sentiment_daily,
    trigger="cron",
    hour=8,
    minute=59,
    id='refresh_sentiment_daily'
)

scheduler.add_job(
    func=refresh_insider_activity_daily,
    trigger="cron",
    hour=8,
    minute=58,
    id='refresh_insider_daily'
)

scheduler.add_job(
    func=cleanup_price_chart_cache,
    trigger="cron",
    hour="*",
    minute=0,
    id='check_after_hours'
)

scheduler.start()
atexit.register(lambda: scheduler.shutdown())

print(f"✅ Scheduler started")

# ======================== UTILITY FUNCTIONS ========================
def cleanup_cache():
    current_time = int(time.time() / 60)
    expired_keys = [k for k in price_cache.keys() if not k.endswith(f"_{current_time}") and not k.endswith(f"_{current_time-1}")]
    for key in expired_keys:
        del price_cache[key]
    gc.collect()

def get_stock_price_waterfall(ticker):
    cache_key = f"{ticker}_{int(time.time() / 60)}"
    if cache_key in price_cache:
        return price_cache[cache_key]
    
    result = {'price': 0, 'change': 0, 'source': 'fallback'}
    
    try:
        if MASSIVE_KEY:
            url = f'https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?apiKey={MASSIVE_KEY}'
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    result['price'] = data['results'][0]['c']
                    result['change'] = ((data['results'][0]['c'] - data['results'][0]['o']) / data['results'][0]['o']) * 100
                    result['source'] = 'Polygon'
                    price_cache[cache_key] = result
                    return result
    except:
        pass
    
    try:
        if FINNHUB_KEY:
            url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('c', 0) > 0:
                    result['price'] = data['c']
                    result['change'] = data.get('dp', 0)
                    result['source'] = 'Finnhub'
                    price_cache[cache_key] = result
                    return result
    except:
        pass
    
    return result

def fetch_prices_concurrent(tickers):
    results = []
    batch_size = 15
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_ticker = {executor.submit(get_stock_price_waterfall, ticker): ticker for ticker in batch}
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    price_data = future.result(timeout=5)
                    results.append({
                        'Symbol': ticker,
                        'Last': round(price_data['price'], 2),
                        'Change': round(price_data['change'], 2),
                        'RSI': round(50 + (price_data['change'] * 2), 2),
                        'Signal': 'BUY' if price_data['change'] > 2 else 'SELL' if price_data['change'] < -2 else 'HOLD',
                        'Strategy': 'Momentum' if price_data['change'] > 0 else 'Mean Reversion'
                    })
                except Exception as e:
                    print(f"Error fetching {ticker}: {e}")
        time.sleep(0.1)
    
    cleanup_cache()
    return results

# ======================== API ENDPOINTS ========================

@app.route('/api/scheduler/status', methods=['GET'])
def get_scheduler_status():
    """Get scheduler status"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'name': job.name if hasattr(job, 'name') else job.id,
            'id': job.id,
            'next_run': job.next_run.isoformat() if job.next_run else None
        })
    
    return jsonify({
        'scheduler_running': scheduler.running,
        'jobs': jobs,
        'chart_after_hours_enabled': chart_after_hours['enabled']
    }), 200

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    try:
        if recommendations_cache['data'] and recommendations_cache['timestamp']:
            cache_age = (datetime.now() - recommendations_cache['timestamp']).total_seconds()
            if cache_age < RECOMMENDATIONS_TTL:
                return jsonify(recommendations_cache['data'])
        stocks = fetch_prices_concurrent(TICKERS)
        recommendations_cache['data'] = stocks
        recommendations_cache['timestamp'] = datetime.now()
        return jsonify(stocks)
    except Exception as e:
        if recommendations_cache['data']:
            return jsonify(recommendations_cache['data'])
        return jsonify({'error': str(e)}), 500

@app.route('/api/stock-price/<ticker>', methods=['GET'])
def get_stock_price_single(ticker):
    try:
        price_data = get_stock_price_waterfall(ticker.upper())
        return jsonify({
            'ticker': ticker.upper(),
            'price': round(price_data['price'], 2),
            'change': round(price_data['change'], 2),
            'after_hours_only': chart_after_hours['enabled']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings-calendar', methods=['GET'])
def get_earnings_calendar():
    return jsonify({
        'earnings': UPCOMING_EARNINGS,
        'count': len(UPCOMING_EARNINGS),
        'next_earnings': UPCOMING_EARNINGS[0] if UPCOMING_EARNINGS else None,
        'last_updated': earnings_cache['timestamp'].isoformat() if earnings_cache['timestamp'] else None
    }), 200

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def get_social_sentiment(ticker):
    ticker = ticker.upper()
    print(f"🔍 Fetching social sentiment for {ticker}...")
    
    cache_key = f"{ticker}_sentiment"
    
    # CHECK CACHE FIRST
    if cache_key in sentiment_cache:
        cache_data = sentiment_cache[cache_key]
        cache_age = (datetime.now() - cache_data['timestamp']).total_seconds()
        if cache_age < SENTIMENT_TTL:
            print(f"✅ Using cached sentiment for {ticker} (age: {int(cache_age)}s)")
            return jsonify(cache_data['data']), 200
    
    # PRIORITY 1: Try Finnhub API if key exists
    if FINNHUB_KEY:
        try:
            print(f"🌐 Calling Finnhub API for {ticker}...")
            url = f'https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                reddit_data = data.get('reddit', [])
                twitter_data = data.get('twitter', [])
                
                reddit_daily = reddit_data[-1] if reddit_data else {}
                twitter_daily = twitter_data[-1] if twitter_data else {}
                reddit_daily_score = reddit_daily.get('score', 0)
                twitter_daily_score = twitter_daily.get('score', 0)
                daily_avg = (reddit_daily_score + twitter_daily_score) / 2
                
                result = {
                    'ticker': ticker,
                    'source': 'Finnhub API',
                    'daily': {
                        'score': round(daily_avg, 2),
                        'mentions': max(int(reddit_daily.get('mention', 50) + twitter_daily.get('mention', 40)), 100),
                        'sentiment': 'BULLISH' if daily_avg > 0.3 else 'BEARISH' if daily_avg < -0.3 else 'NEUTRAL'
                    },
                    'overall_sentiment': 'BULLISH' if daily_avg > 0.3 else 'BEARISH' if daily_avg < -0.3 else 'NEUTRAL'
                }
                
                sentiment_cache[cache_key] = {'data': result, 'timestamp': datetime.now()}
                print(f"✅ Finnhub data cached for {ticker}")
                return jsonify(result), 200
            else:
                print(f"❌ Finnhub API error: {response.status_code} for {ticker}")
        except Exception as e:
            print(f"❌ Finnhub exception for {ticker}: {e}")
    else:
        print(f"⚠️  No FINNHUB_KEY set - using fallback for {ticker}")
    
    # PRIORITY 2: Fallback if no key or API fails
    print(f"📊 Using synthetic fallback for {ticker}")
    ticker_hash = sum(ord(c) for c in ticker) % 100
    daily_sentiment = ['BULLISH', 'NEUTRAL', 'BEARISH'][ticker_hash % 3]
    result = {
        'ticker': ticker,
        'source': 'Synthetic (Fallback)',
        'daily': {
            'score': round((ticker_hash - 50) / 150, 2),
            'mentions': max(150 + (ticker_hash * 7), 100),
            'sentiment': daily_sentiment
        },
        'overall_sentiment': daily_sentiment
    }
    
    sentiment_cache[cache_key] = {'data': result, 'timestamp': datetime.now()}
    print(f"✅ Fallback data cached for {ticker}")
    return jsonify(result), 200

@app.route('/api/insider-transactions/<ticker>', methods=['GET'])
def get_insider_transactions(ticker):
    ticker = ticker.upper()
    
    cache_key = f"{ticker}_insider"
    if cache_key in insider_cache:
        cache_data = insider_cache[cache_key]
        cache_age = (datetime.now() - cache_data['timestamp']).total_seconds()
        if cache_age < INSIDER_TTL:
            return jsonify(cache_data['data']), 200
    
    if FINNHUB_KEY:
        try:
            from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            url = f'https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&from={from_date}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                transactions = data.get('data', [])
                buys = sum(1 for t in transactions if t.get('transactionCode') in ['P', 'A'])
                sells = sum(1 for t in transactions if t.get('transactionCode') == 'S')
                
                result = {
                    'ticker': ticker,
                    'insider_sentiment': 'BULLISH' if buys > sells else 'BEARISH' if sells > buys else 'NEUTRAL',
                    'buy_count': buys,
                    'sell_count': sells,
                    'total_transactions': len(transactions)
                }
                
                insider_cache[cache_key] = {'data': result, 'timestamp': datetime.now()}
                return jsonify(result), 200
        except:
            pass
    
    ticker_hash = sum(ord(c) for c in ticker) % 100
    result = {
        'ticker': ticker,
        'insider_sentiment': 'BULLISH' if ticker_hash > 50 else 'BEARISH',
        'buy_count': (ticker_hash // 10) + 1,
        'sell_count': ((100 - ticker_hash) // 15) + 1
    }
    
    insider_cache[cache_key] = {'data': result, 'timestamp': datetime.now()}
    return jsonify(result), 200

@app.route('/api/stock-news/<ticker>', methods=['GET'])
def get_stock_news(ticker):
    if not FINNHUB_KEY:
        return jsonify({'ticker': ticker, 'articles': [], 'count': 0}), 200
    try:
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        url = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            articles = response.json()
            return jsonify({'ticker': ticker, 'articles': articles[:10], 'count': len(articles)})
    except:
        pass
    return jsonify({'ticker': ticker, 'articles': [], 'count': 0})

@app.route('/api/options-opportunities/<ticker>', methods=['GET'])
def get_options_opportunities(ticker):
    """Expanded options strategies"""
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
                    'setup': f'Sell ${round(current_price * 1.05, 2)} Call / Buy ${round(current_price * 1.08, 2)} Call, Sell ${round(current_price * 0.95, 2)} Put / Buy ${round(current_price * 0.92, 2)} Put',
                    'max_profit': round(current_price * 0.02, 2),
                    'max_loss': round(current_price * 0.03, 2),
                    'probability_of_profit': '65%',
                    'days_to_expiration': 30,
                    'recommendation': 'BEST' if abs(change) < 2 else 'GOOD'
                },
                {
                    'type': 'Call Spread (Bullish)',
                    'setup': f'Buy ${round(current_price, 2)} Call / Sell ${round(current_price * 1.05, 2)} Call',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'days_to_expiration': 30,
                    'recommendation': 'BUY' if change > 2 else 'NEUTRAL'
                },
                {
                    'type': 'Put Spread (Bearish)',
                    'setup': f'Buy ${round(current_price, 2)} Put / Sell ${round(current_price * 0.95, 2)} Put',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'days_to_expiration': 30,
                    'recommendation': 'BUY' if change < -2 else 'NEUTRAL'
                },
                {
                    'type': 'Butterfly (Range-bound)',
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

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'scheduler_running': scheduler.running,
        'after_hours_charts': chart_after_hours['enabled'],
        'finnhub_key': 'enabled' if FINNHUB_KEY else 'disabled'
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
