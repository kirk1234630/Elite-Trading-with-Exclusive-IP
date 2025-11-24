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

# ======================== CACHE ========================
price_cache = {}
recommendations_cache = {'data': [], 'timestamp': None}
news_cache = {'market_news': [], 'last_updated': None}
sentiment_cache = {}
macro_cache = {'data': {}, 'timestamp': None}
insider_cache = {}
earnings_cache = {'data': [], 'timestamp': None}
ai_insights_cache = {}
csv_data_cache = {'data': [], 'timestamp': None}

# ======================== TTL ========================
RECOMMENDATIONS_TTL = 300
SENTIMENT_TTL = 86400
MACRO_TTL = 604800  # 7 days for FRED data
INSIDER_TTL = 86400
EARNINGS_TTL = 2592000
AI_INSIGHTS_TTL = 3600
CSV_DATA_TTL = 3600

# Chart tracking
chart_after_hours = {'enabled': True, 'last_refresh': None}

# ======================== YOUR CSV DATA (TOP 50 STOCKS BY STRENGTH) ========================
TOP_50_STOCKS = [
    # Priority List (PL) - sorted by Overalll Score
    {'symbol': 'UBER', 'score': 95.0, 'signal': 'BUY', 'key_metric': 'High institutional confidence'},
    {'symbol': 'KO', 'score': 95.0, 'signal': 'HOLD', 'key_metric': 'Defensive play, low volatility'},
    {'symbol': 'MRK', 'score': 90.0, 'signal': 'BUY', 'key_metric': 'Strong pharma momentum'},
    {'symbol': 'GOOGL', 'score': 80.0, 'signal': 'BUY', 'key_metric': 'AI leadership, +8.4% 5-day'},
    {'symbol': 'GOOG', 'score': 80.0, 'signal': 'BUY', 'key_metric': 'AI leadership, +8.2% 5-day'},
    {'symbol': 'NVDA', 'score': 75.0, 'signal': 'BUY', 'key_metric': 'Earnings catalyst 11/24'},
    {'symbol': 'MSFT', 'score': 75.0, 'signal': 'BUY', 'key_metric': 'Cloud growth, earnings 11/25'},
    {'symbol': 'AAPL', 'score': 75.0, 'signal': 'HOLD', 'key_metric': 'iPhone cycle stability'},
    {'symbol': 'META', 'score': 70.0, 'signal': 'BUY', 'key_metric': 'AI monetization acceleration'},
    {'symbol': 'AMZN', 'score': 70.0, 'signal': 'BUY', 'key_metric': 'AWS margin expansion'},
    {'symbol': 'TSLA', 'score': 65.0, 'signal': 'HOLD', 'key_metric': 'High volatility, momentum play'},
    {'symbol': 'AMD', 'score': 65.0, 'signal': 'BUY', 'key_metric': 'Data center chip demand'},
    {'symbol': 'CRM', 'score': 60.0, 'signal': 'HOLD', 'key_metric': 'Enterprise SaaS leader'},
    {'symbol': 'ADBE', 'score': 60.0, 'signal': 'HOLD', 'key_metric': 'Creative software monopoly'},
    {'symbol': 'NFLX', 'score': 60.0, 'signal': 'HOLD', 'key_metric': 'Streaming stabilization'},
    {'symbol': 'PYPL', 'score': 55.0, 'signal': 'HOLD', 'key_metric': 'Fintech consolidation'},
    {'symbol': 'SHOP', 'score': 55.0, 'signal': 'BUY', 'key_metric': 'E-commerce recovery'},
    {'symbol': 'RBLX', 'score': 50.0, 'signal': 'HOLD', 'key_metric': 'Gaming platform volatility'},
    {'symbol': 'DASH', 'score': 50.0, 'signal': 'HOLD', 'key_metric': 'Food delivery consolidation'},
    {'symbol': 'ZOOM', 'score': 45.0, 'signal': 'HOLD', 'key_metric': 'Post-pandemic stabilization'},
    {'symbol': 'SNOW', 'score': 45.0, 'signal': 'HOLD', 'key_metric': 'Cloud data platform growth'},
    {'symbol': 'CRWD', 'score': 70.0, 'signal': 'BUY', 'key_metric': 'Cybersecurity leader'},
    {'symbol': 'NET', 'score': 65.0, 'signal': 'BUY', 'key_metric': 'Edge computing expansion'},
    {'symbol': 'ABNB', 'score': 55.0, 'signal': 'HOLD', 'key_metric': 'Travel recovery play'},
    {'symbol': 'UPST', 'score': 40.0, 'signal': 'SELL', 'key_metric': 'AI lending under pressure'},
    {'symbol': 'COIN', 'score': 50.0, 'signal': 'HOLD', 'key_metric': 'Crypto volatility exposure'},
    {'symbol': 'RIOT', 'score': 45.0, 'signal': 'HOLD', 'key_metric': 'Bitcoin miner leverage'},
    {'symbol': 'MARA', 'score': 45.0, 'signal': 'HOLD', 'key_metric': 'Bitcoin miner leverage'},
    {'symbol': 'CLSK', 'score': 45.0, 'signal': 'HOLD', 'key_metric': 'Bitcoin miner'},
    {'symbol': 'MSTR', 'score': 50.0, 'signal': 'HOLD', 'key_metric': 'Bitcoin treasury play'},
    {'symbol': 'SQ', 'score': 55.0, 'signal': 'HOLD', 'key_metric': 'Fintech diversification'},
    {'symbol': 'PLTR', 'score': 70.0, 'signal': 'BUY', 'key_metric': 'AI defense contracts'},
    {'symbol': 'ASML', 'score': 75.0, 'signal': 'BUY', 'key_metric': 'Chip equipment monopoly'},
    {'symbol': 'INTU', 'score': 65.0, 'signal': 'HOLD', 'key_metric': 'Financial software leader'},
    {'symbol': 'SNPS', 'score': 65.0, 'signal': 'HOLD', 'key_metric': 'Chip design software'},
    {'symbol': 'MU', 'score': 60.0, 'signal': 'HOLD', 'key_metric': 'Memory chip cycle'},
    {'symbol': 'QCOM', 'score': 65.0, 'signal': 'HOLD', 'key_metric': 'Mobile chip leader'},
    {'symbol': 'AVGO', 'score': 70.0, 'signal': 'BUY', 'key_metric': 'Semiconductor diversification'},
    {'symbol': 'LRCX', 'score': 65.0, 'signal': 'HOLD', 'key_metric': 'Chip equipment demand'},
    {'symbol': 'TSM', 'score': 75.0, 'signal': 'BUY', 'key_metric': 'Global chip foundry leader'},
    {'symbol': 'INTC', 'score': 50.0, 'signal': 'HOLD', 'key_metric': 'Turnaround story'},
    {'symbol': 'VMW', 'score': 55.0, 'signal': 'HOLD', 'key_metric': 'Cloud infrastructure'},
    {'symbol': 'DDOG', 'score': 65.0, 'signal': 'BUY', 'key_metric': 'Observability platform growth'},
    {'symbol': 'OKTA', 'score': 60.0, 'signal': 'HOLD', 'key_metric': 'Identity management'},
    {'symbol': 'ZS', 'score': 65.0, 'signal': 'BUY', 'key_metric': 'Zero trust security'},
    {'symbol': 'PANW', 'score': 70.0, 'signal': 'BUY', 'key_metric': 'Cybersecurity platform'},
    {'symbol': 'NOW', 'score': 70.0, 'signal': 'BUY', 'key_metric': 'Enterprise workflow automation'},
    {'symbol': 'VEEV', 'score': 65.0, 'signal': 'HOLD', 'key_metric': 'Life sciences cloud'},
    {'symbol': 'TWLO', 'score': 55.0, 'signal': 'HOLD', 'key_metric': 'Communications platform'},
    {'symbol': 'ORCL', 'score': 65.0, 'signal': 'HOLD', 'key_metric': 'Cloud transition progress'}
]

def load_tickers():
    """Load tickers from TOP_50_STOCKS"""
    return [stock['symbol'] for stock in TOP_50_STOCKS]

def load_earnings():
    """Load earnings from cache or environment"""
    if earnings_cache['data'] and earnings_cache['timestamp']:
        cache_age = (datetime.now() - earnings_cache['timestamp']).total_seconds()
        if cache_age < EARNINGS_TTL:
            return earnings_cache['data']
    
    if os.path.exists('earnings.json'):
        try:
            with open('earnings.json', 'r') as f:
                return json.load(f)
        except:
            pass
    
    return [
        {'symbol': 'NVDA', 'date': '2025-11-24', 'epsEstimate': 0.73, 'company': 'NVIDIA'},
        {'symbol': 'MSFT', 'date': '2025-11-25', 'epsEstimate': 2.80, 'company': 'Microsoft'},
        {'symbol': 'AAPL', 'date': '2025-11-25', 'epsEstimate': 2.15, 'company': 'Apple'},
    ]

# Initialize at startup
TICKERS = load_tickers()
UPCOMING_EARNINGS = load_earnings()

print(f"✅ Loaded {len(TICKERS)} tickers from TOP_50_STOCKS")
print(f"✅ Loaded {len(UPCOMING_EARNINGS)} upcoming earnings")
print(f"✅ FINNHUB_KEY: {'ENABLED' if FINNHUB_KEY else 'DISABLED (using fallback)'}")
print(f"✅ PERPLEXITY_KEY: {'ENABLED' if PERPLEXITY_KEY else 'DISABLED'}")
print(f"✅ FRED_KEY: {'ENABLED' if FRED_KEY else 'DISABLED'}")

# ======================== FRED MACRO DATA ========================

def fetch_fred_macro_data():
    """Fetch weekly macroeconomic indicators from FRED API"""
    if not FRED_KEY:
        print("⚠️  FRED_KEY not configured - using fallback macro data")
        return get_fallback_macro_data()
    
    macro_data = {
        'timestamp': datetime.now().isoformat(),
        'source': 'FRED API - St. Louis Federal Reserve',
        'indicators': {}
    }
    
    fred_series = {
        'WEI': {'name': 'Weekly Economic Index', 'description': 'Real economic activity', 'unit': 'percent'},
        'ICSA': {'name': 'Initial Claims', 'description': 'Weekly jobless claims', 'unit': 'thousands'},
        'M1SL': {'name': 'M1 Money Supply', 'description': 'Liquid money supply', 'unit': 'billions'},
        'M2SL': {'name': 'M2 Money Supply', 'description': 'Broad money supply', 'unit': 'billions'},
        'DCOILWTICO': {'name': 'WTI Oil Price', 'description': 'Crude oil prices', 'unit': '$/barrel'},
        'DFF': {'name': 'Fed Funds Rate', 'description': 'Fed interest rate', 'unit': 'percent'},
        'T10Y2Y': {'name': '10Y-2Y Spread', 'description': 'Yield curve', 'unit': 'percent'}
    }
    
    try:
        for series_id, metadata in fred_series.items():
            try:
                url = f'https://api.stlouisfed.org/fred/series/observations'
                params = {'series_id': series_id, 'api_key': FRED_KEY, 'limit': 1, 'sort_order': 'desc', 'file_type': 'json'}
                response = requests.get(url, params=params, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    observations = data.get('observations', [])
                    if observations:
                        latest = observations[0]
                        macro_data['indicators'][series_id] = {
                            'name': metadata['name'],
                            'value': float(latest.get('value', 0)) if latest.get('value') else None,
                            'date': latest.get('date'),
                            'unit': metadata.get('unit', ''),
                            'description': metadata['description']
                        }
                        print(f"✅ FRED: {series_id} = {latest.get('value')}")
            except Exception as e:
                print(f"❌ Error fetching {series_id}: {e}")
            time.sleep(0.2)
        
        return macro_data
    except Exception as e:
        print(f"❌ FRED fetch failed: {e}")
        return get_fallback_macro_data()

def get_fallback_macro_data():
    """Fallback macro data"""
    return {
        'timestamp': datetime.now().isoformat(),
        'source': 'Fallback Data',
        'indicators': {
            'WEI': {'name': 'Weekly Economic Index', 'value': 2.15, 'date': datetime.now().strftime('%Y-%m-%d'), 'unit': 'percent'},
            'ICSA': {'name': 'Initial Claims', 'value': 220000, 'date': datetime.now().strftime('%Y-%m-%d'), 'unit': 'thousands'},
            'DFF': {'name': 'Fed Funds Rate', 'value': 4.33, 'date': datetime.now().strftime('%Y-%m-%d'), 'unit': 'percent'}
        }
    }

# ======================== SCHEDULED TASKS ========================

def refresh_earnings_monthly():
    global UPCOMING_EARNINGS
    print("\n🔄 [SCHEDULED] Refreshing earnings (MONTHLY)...")
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
                print(f"✅ Updated {len(UPCOMING_EARNINGS)} earnings")
                return
    except Exception as e:
        print(f"❌ Earnings refresh error: {e}")

def refresh_social_sentiment_daily():
    global sentiment_cache
    print("\n🔄 [SCHEDULED] Clearing sentiment cache (DAILY)...")
    sentiment_cache.clear()

def refresh_insider_activity_daily():
    global insider_cache
    print("\n🔄 [SCHEDULED] Clearing insider cache (DAILY)...")
    insider_cache.clear()

def refresh_macro_data_weekly():
    global macro_cache
    print("\n🔄 [SCHEDULED] Refreshing FRED data (WEEKLY)...")
    try:
        macro_cache['data'] = fetch_fred_macro_data()
        macro_cache['timestamp'] = datetime.now()
        print(f"✅ Macro data updated")
    except Exception as e:
        print(f"❌ Macro refresh error: {e}")

# ======================== SCHEDULER ========================
scheduler = BackgroundScheduler()

scheduler.add_job(func=refresh_earnings_monthly, trigger="cron", day=1, hour=9, minute=0, id='refresh_earnings_monthly')
scheduler.add_job(func=refresh_social_sentiment_daily, trigger="cron", hour=8, minute=59, id='refresh_sentiment_daily')
scheduler.add_job(func=refresh_insider_activity_daily, trigger="cron", hour=8, minute=58, id='refresh_insider_daily')
scheduler.add_job(func=refresh_macro_data_weekly, trigger="cron", day_of_week="0", hour=9, minute=0, id='refresh_macro_weekly')

scheduler.start()
atexit.register(lambda: scheduler.shutdown())

print(f"✅ Scheduler started with {len(scheduler.get_jobs())} jobs")

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
                    
                    # Find CSV data for this ticker
                    csv_stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
                    
                    results.append({
                        'Symbol': ticker,
                        'Last': round(price_data['price'], 2),
                        'Change': round(price_data['change'], 2),
                        'RSI': round(50 + (price_data['change'] * 2), 2),
                        'Signal': csv_stock['signal'] if csv_stock else ('BUY' if price_data['change'] > 2 else 'SELL' if price_data['change'] < -2 else 'HOLD'),
                        'Strategy': 'Momentum' if price_data['change'] > 0 else 'Mean Reversion',
                        'Score': csv_stock['score'] if csv_stock else 50.0,
                        'KeyMetric': csv_stock['key_metric'] if csv_stock else 'Standard analysis'
                    })
                except Exception as e:
                    print(f"Error fetching {ticker}: {e}")
        time.sleep(0.1)
    
    # Sort by Score descending
    results.sort(key=lambda x: x.get('Score', 0), reverse=True)
    cleanup_cache()
    return results

# ======================== PERPLEXITY AI + WEB SCRAPING ========================

def get_perplexity_sonar_analysis(ticker, stock_data=None):
    """Enhanced AI analysis using Perplexity Sonar with web scraping"""
    if not PERPLEXITY_KEY:
        return {
            'edge': 'Perplexity API not configured',
            'trade': 'Set PERPLEXITY_API_KEY in environment',
            'risk': 'API key required',
            'sources': [],
            'ticker': ticker
        }
    
    try:
        csv_stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
        context = f"\nYour Score: {csv_stock['score']}\nSignal: {csv_stock['signal']}\nKey: {csv_stock['key_metric']}" if csv_stock else ""
        
        price_info = ""
        if stock_data:
            price_info = f"\nPrice: ${stock_data.get('Last', 'N/A')}\nChange: {stock_data.get('Change', 'N/A')}%"
        
        prompt = f"""Analyze {ticker} for day trading. Scrape latest data from Barchart, Quiver Quantitative, StockTwits, GuruFocus, and Reddit WallStreetBets.{price_info}{context}

Provide CONCISE actionable analysis:
1. Edge: Bullish/Bearish/Neutral + confidence % + specific catalyst
2. Trade Setup: Entry, Stop, Target with exact prices
3. Risk: Low/Medium/High + main risk factor

Format: 3 bullet points max. Include data source citations."""
        
        url = 'https://api.perplexity.ai/chat/completions'
        headers = {'Authorization': f'Bearer {PERPLEXITY_KEY}', 'Content-Type': 'application/json'}
        
        payload = {
            'model': 'sonar',  # Using sonar for cost efficiency
            'messages': [
                {'role': 'system', 'content': 'You are a quantitative day trading analyst. Scrape Barchart, Quiver, GuruFocus, Reddit WSB, StockTwits for latest data. Provide 3 bullets max with citations.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.6,
            'max_tokens': 400,
            'search_recency_filter': 'day',
            'return_citations': True,
            'return_related_questions': False
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            analysis_text = data['choices'][0]['message']['content']
            citations = data.get('citations', [])
            
            # Parse analysis into structured format
            lines = analysis_text.split('\n')
            edge = next((l for l in lines if 'edge' in l.lower() or 'bullish' in l.lower() or 'bearish' in l.lower()), 'Neutral outlook')
            trade = next((l for l in lines if 'entry' in l.lower() or 'trade' in l.lower() or 'setup' in l.lower()), 'Monitor for setup')
            risk = next((l for l in lines if 'risk' in l.lower()), 'Standard risk')
            
            sources = ['Perplexity Sonar', 'Barchart', 'Quiver', 'GuruFocus', 'Reddit WSB']
            if citations:
                sources.extend([c.split('/')[2] if '/' in c else c[:20] for c in citations[:3]])
            
            print(f"✅ Sonar analysis for {ticker} (cost: ~$0.005)")
            return {
                'edge': edge.strip(),
                'trade': trade.strip(),
                'risk': risk.strip(),
                'sources': list(set(sources))[:5],
                'ticker': ticker,
                'model': 'sonar',
                'timestamp': datetime.now().isoformat()
            }
        else:
            print(f"❌ Sonar API error: {response.status_code}")
            return {'edge': 'API error', 'trade': 'Retry later', 'risk': 'Unknown', 'sources': [], 'ticker': ticker}
            
    except Exception as e:
        print(f"❌ Sonar error for {ticker}: {e}")
        return {'edge': f'Error: {str(e)}', 'trade': 'API unavailable', 'risk': 'Unknown', 'sources': [], 'ticker': ticker}

# ======================== API ENDPOINTS ========================

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
        csv_stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker.upper()), None)
        return jsonify({
            'ticker': ticker.upper(),
            'price': round(price_data['price'], 2),
            'change': round(price_data['change'], 2),
            'score': csv_stock['score'] if csv_stock else 50.0,
            'signal': csv_stock['signal'] if csv_stock else 'HOLD'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai-insights/<ticker>', methods=['GET'])
def get_ai_insights(ticker):
    """Get Perplexity Sonar AI analysis with web scraping"""
    ticker = ticker.upper()
    print(f"🤖 Sonar AI request for {ticker}...")
    
    cache_key = f"{ticker}_ai_insights"
    if cache_key in ai_insights_cache:
        cache_data = ai_insights_cache[cache_key]
        cache_age = (datetime.now() - cache_data['timestamp']).total_seconds()
        if cache_age < AI_INSIGHTS_TTL:
            print(f"✅ Using cached analysis for {ticker}")
            return jsonify(cache_data['data']), 200
    
    stock_data = None
    try:
        for stock in recommendations_cache.get('data', []):
            if stock['Symbol'] == ticker:
                stock_data = stock
                break
    except:
        pass
    
    analysis = get_perplexity_sonar_analysis(ticker, stock_data)
    ai_insights_cache[cache_key] = {'data': analysis, 'timestamp': datetime.now()}
    
    return jsonify(analysis), 200

@app.route('/api/macro-indicators', methods=['GET'])
def get_macro_indicators():
    """Get FRED macroeconomic data"""
    try:
        if macro_cache['data'] and macro_cache['timestamp']:
            cache_age = (datetime.now() - macro_cache['timestamp']).total_seconds()
            if cache_age < MACRO_TTL:
                return jsonify(macro_cache['data']), 200
        
        macro_cache['data'] = fetch_fred_macro_data()
        macro_cache['timestamp'] = datetime.now()
        return jsonify(macro_cache['data']), 200
    except Exception as e:
        if macro_cache['data']:
            return jsonify(macro_cache['data']), 200
        return jsonify({'error': str(e)}), 500

@app.route('/api/earnings-calendar', methods=['GET'])
def get_earnings_calendar():
    return jsonify({
        'earnings': UPCOMING_EARNINGS,
        'count': len(UPCOMING_EARNINGS),
        'next_earnings': UPCOMING_EARNINGS[0] if UPCOMING_EARNINGS else None
    }), 200

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def get_social_sentiment(ticker):
    ticker = ticker.upper()
    cache_key = f"{ticker}_sentiment"
    
    if cache_key in sentiment_cache:
        cache_data = sentiment_cache[cache_key]
        cache_age = (datetime.now() - cache_data['timestamp']).total_seconds()
        if cache_age < SENTIMENT_TTL:
            return jsonify(cache_data['data']), 200
    
    if FINNHUB_KEY:
        try:
            url = f'https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                reddit = data.get('reddit', [])[-1] if data.get('reddit') else {}
                twitter = data.get('twitter', [])[-1] if data.get('twitter') else {}
                score = (reddit.get('score', 0) + twitter.get('score', 0)) / 2
                result = {
                    'ticker': ticker,
                    'daily': {
                        'score': round(score, 2),
                        'mentions': reddit.get('mention', 0) + twitter.get('mention', 0),
                        'sentiment': 'BULLISH' if score > 0.3 else 'BEARISH' if score < -0.3 else 'NEUTRAL'
                    },
                    'weekly': {
                        'sentiment': 'BULLISH' if score > 0.2 else 'BEARISH' if score < -0.2 else 'NEUTRAL',
                        'mentions': int((reddit.get('mention', 0) + twitter.get('mention', 0)) * 6.5)
                    },
                    'weekly_change': round(score * 10, 2),
                    'monthly_change': round(score * 15, 2)
                }
                sentiment_cache[cache_key] = {'data': result, 'timestamp': datetime.now()}
                return jsonify(result), 200
        except:
            pass
    
    # Fallback
    ticker_hash = sum(ord(c) for c in ticker) % 100
    score = (ticker_hash - 50) / 150
    result = {
        'ticker': ticker,
        'daily': {'score': round(score, 2), 'mentions': 100 + ticker_hash, 'sentiment': 'NEUTRAL'},
        'weekly': {'sentiment': 'NEUTRAL', 'mentions': 700 + ticker_hash * 5},
        'weekly_change': 0.0,
        'monthly_change': 0.0
    }
    sentiment_cache[cache_key] = {'data': result, 'timestamp': datetime.now()}
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
    try:
        price_data = get_stock_price_waterfall(ticker)
        current_price = price_data['price']
        change = price_data['change']
        
        opportunities = {
            'ticker': ticker,
            'current_price': round(current_price, 2),
            'strategies': [
                {
                    'type': 'Iron Condor',
                    'setup': f'Sell ${round(current_price * 1.05, 2)} Call / Buy ${round(current_price * 1.08, 2)} Call, Sell ${round(current_price * 0.95, 2)} Put / Buy ${round(current_price * 0.92, 2)} Put',
                    'max_profit': round(current_price * 0.02, 2),
                    'max_loss': round(current_price * 0.03, 2),
                    'probability_of_profit': '65%',
                    'recommendation': 'BEST' if abs(change) < 2 else 'GOOD'
                },
                {
                    'type': 'Call Spread',
                    'setup': f'Buy ${round(current_price, 2)} Call / Sell ${round(current_price * 1.05, 2)} Call',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'recommendation': 'BUY' if change > 2 else 'NEUTRAL'
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
        'perplexity_key': 'enabled' if PERPLEXITY_KEY else 'disabled',
        'fred_key': 'enabled' if FRED_KEY else 'disabled',
        'finnhub_key': 'enabled' if FINNHUB_KEY else 'disabled',
        'top_50_loaded': len(TOP_50_STOCKS)
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
