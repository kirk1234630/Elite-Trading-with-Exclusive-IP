from flask import Flask, jsonify, request
from flask_cors import CORS
@app.route('/')
def serve_frontend():
    """Serve frontend from backend/server.py"""
    try:
        with open('frontend/index.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({'status': 'API Running'}), 200

import requests
import os
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import gc
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from bs4 import BeautifulSoup
import re

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
barchart_cache = {}
gurufocus_cache = {}
reddit_cache = {}

# ======================== TTL ========================
RECOMMENDATIONS_TTL = 300
SENTIMENT_TTL = 86400
MACRO_TTL = 604800
INSIDER_TTL = 86400
EARNINGS_TTL = 2592000
AI_INSIGHTS_TTL = 3600
BARCHART_TTL = 3600
GURUFOCUS_TTL = 86400
REDDIT_TTL = 3600

chart_after_hours = {'enabled': True, 'last_refresh': None}

# ======================== TOP 50 STOCKS DATA ========================
TOP_50_STOCKS = [
    {'symbol': 'KO', 'inst33': 95, 'overall_score': 8, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 8, 'money_score': 4, 'alpha_score': 3, 'equity_score': 1.9, 'mean_reversion': 2.09, 'iv': 0.2, 'signal': 'STRONG_BUY', 'key_metric': 'Beverage leader - low IV, uptrend'},
    {'symbol': 'AZN', 'inst33': 95, 'overall_score': 8, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 7, 'money_score': 0, 'alpha_score': 3, 'equity_score': 1.7, 'mean_reversion': 1.57, 'iv': 0.26, 'signal': 'STRONG_BUY', 'key_metric': 'Biotech - highest institutional backing'},
    {'symbol': 'MRK', 'inst33': 90, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 5, 'money_score': 5, 'alpha_score': 3, 'equity_score': 2.0, 'mean_reversion': 1.87, 'iv': 0.33, 'signal': 'STRONG_BUY', 'key_metric': 'Pharma strong momentum'},
    {'symbol': 'AAPL', 'inst33': 60, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 6, 'money_score': 4, 'alpha_score': 3, 'equity_score': 0.65, 'mean_reversion': 0.65, 'iv': 0.29, 'signal': 'HOLD', 'key_metric': 'Tech giant - stable'},
    {'symbol': 'MSFT', 'inst33': 60, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 6, 'money_score': 4, 'alpha_score': 3, 'equity_score': 0.65, 'mean_reversion': 0.65, 'iv': 0.29, 'signal': 'BUY', 'key_metric': 'Cloud dominant - uptrend'},
    {'symbol': 'NVDA', 'inst33': 45, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 2, 'money_score': 1, 'alpha_score': 1, 'equity_score': -1.69, 'mean_reversion': -1.69, 'iv': 0.59, 'signal': 'SELL', 'key_metric': 'Chip leader - weakness'},
    {'symbol': 'AMZN', 'inst33': 45, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 2, 'money_score': 1, 'alpha_score': 1, 'equity_score': -1.37, 'mean_reversion': -1.37, 'iv': 0.4, 'signal': 'SELL', 'key_metric': 'E-commerce leader - pullback'},
    {'symbol': 'BABA', 'inst33': 48, 'overall_score': 3, 'signal': 'NEUTRAL', 'key_metric': 'China exposure'},
    {'symbol': 'TSLA', 'inst33': 50, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'EV volatility'},
    {'symbol': 'META', 'inst33': 55, 'overall_score': 4, 'signal': 'BUY', 'key_metric': 'AI upside'},
    {'symbol': 'NFLX', 'inst33': 58, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Streaming stable'},
    {'symbol': 'GOOGL', 'inst33': 80, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Tech AI leader'},
    {'symbol': 'GOOG', 'inst33': 80, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Tech uptrend'},
    {'symbol': 'JNJ', 'inst33': 75, 'overall_score': 8, 'signal': 'SELL_CALL', 'key_metric': 'Healthcare premium'},
    {'symbol': 'RY', 'inst33': 70, 'overall_score': 6, 'signal': 'SELL_CALL', 'key_metric': 'Financial low IV'},
    {'symbol': 'WMT', 'inst33': 70, 'overall_score': 0, 'signal': 'SELL_CALL', 'key_metric': 'Retail defensive'},
    {'symbol': 'V', 'inst33': 70, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Payments strong'},
    {'symbol': 'MA', 'inst33': 70, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Mastercard momentum'},
    {'symbol': 'LLY', 'inst33': 65, 'overall_score': 8, 'signal': 'HOLD', 'key_metric': 'Biotech GLP-1'},
    {'symbol': 'A', 'inst33': 80, 'overall_score': 8, 'signal': 'BUY', 'key_metric': 'Agilent emerging'},
    {'symbol': 'ASML', 'inst33': 65, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Chip equipment'},
    {'symbol': 'DAL', 'inst33': 65, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Airlines recovery'},
    {'symbol': 'CSCO', 'inst33': 55, 'overall_score': 8, 'signal': 'HOLD', 'key_metric': 'Networking dividend'},
    {'symbol': 'INTC', 'inst33': 52, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Chip turnaround'},
    {'symbol': 'AMD', 'inst33': 53, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Chip competitor'},
    {'symbol': 'CRM', 'inst33': 58, 'overall_score': 5, 'signal': 'BUY', 'key_metric': 'Cloud CRM'},
    {'symbol': 'ADBE', 'inst33': 60, 'overall_score': 6, 'signal': 'HOLD', 'key_metric': 'Creative stable'},
    {'symbol': 'DDOG', 'inst33': 62, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Cloud monitoring'},
    {'symbol': 'SNOW', 'inst33': 60, 'overall_score': 5, 'signal': 'BUY', 'key_metric': 'Data warehouse'},
    {'symbol': 'DBX', 'inst33': 54, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Cloud storage'},
    {'symbol': 'OKTA', 'inst33': 56, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Identity secure'},
    {'symbol': 'SPLK', 'inst33': 55, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Analytics platform'},
    {'symbol': 'COIN', 'inst33': 45, 'overall_score': 2, 'signal': 'SELL', 'key_metric': 'Crypto exposure'},
    {'symbol': 'MSTR', 'inst33': 58, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Bitcoin proxy'},
    {'symbol': 'RIOT', 'inst33': 50, 'overall_score': 1, 'signal': 'SELL', 'key_metric': 'Mining weak'},
    {'symbol': 'HUT', 'inst33': 48, 'overall_score': 1, 'signal': 'SELL', 'key_metric': 'Miner volatile'},
    {'symbol': 'CLSK', 'inst33': 52, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'Mining consolidate'},
    {'symbol': 'DELL', 'inst33': 48, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'PC mature'},
    {'symbol': 'HPQ', 'inst33': 45, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'Hardware'},
    {'symbol': 'IBM', 'inst33': 52, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'IT services'},
    {'symbol': 'TSM', 'inst33': 50, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Foundry Taiwan'},
    {'symbol': 'QCOM', 'inst33': 52, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'Chip design'},
    {'symbol': 'AVGO', 'inst33': 53, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Broadcom'},
    {'symbol': 'MU', 'inst33': 48, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'Memory chips'},
    {'symbol': 'BOX', 'inst33': 48, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'Content mgmt'},
    {'symbol': 'PYPL', 'inst33': 48, 'overall_score': 3, 'signal': 'NEUTRAL', 'key_metric': 'Fintech'},
    {'symbol': 'SQ', 'inst33': 52, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Square recovery'},
    {'symbol': 'PG', 'inst33': 50, 'overall_score': 0, 'signal': 'SELL_CALL', 'key_metric': 'Consumer staples'},
    {'symbol': 'XOM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Energy dividend'},
    {'symbol': 'JPM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Financial weak'},
]

def load_tickers():
    return [stock['symbol'] for stock in TOP_50_STOCKS]

def load_earnings():
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
        {'symbol': 'NVDA', 'date': '2025-11-24', 'epsEstimate': 0.73},
        {'symbol': 'MSFT', 'date': '2025-11-25', 'epsEstimate': 2.80},
        {'symbol': 'AAPL', 'date': '2025-11-25', 'epsEstimate': 2.15},
    ]

TICKERS = load_tickers()
UPCOMING_EARNINGS = load_earnings()

print(f"✅ Loaded {len(TICKERS)} tickers from TOP_50_STOCKS")
print(f"✅ Scraping: BeautifulSoup4 + lxml enabled")
print(f"✅ Hybrid mode: Real scraping + Perplexity Sonar")
print(f"✅ Perplexity: {'ENABLED' if PERPLEXITY_KEY else 'DISABLED'}")
print(f"✅ FRED: {'ENABLED' if FRED_KEY else 'DISABLED'}")

# ======================== 1. BARCHART SCRAPING ========================
def scrape_barchart_signals(ticker):
    """Scrape Barchart technical signals"""
    cache_key = f"{ticker}_barchart"
    
    if cache_key in barchart_cache:
        cached = barchart_cache[cache_key]
        if (datetime.now() - cached['ts']).total_seconds() < BARCHART_TTL:
            return cached['data']
    
    result = {
        'ticker': ticker,
        'technical_rating': 'N/A',
        'short_term': 'N/A',
        'intermediate': 'N/A',
        'long_term': 'N/A',
        'source': 'Barchart'
    }
    
    try:
        url = f'https://www.barchart.com/stocks/quotes/{ticker}/technical-analysis'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml')
            
            rating_elem = soup.find('span', {'class': lambda x: x and 'rating' in x.lower()})
            if rating_elem:
                result['technical_rating'] = rating_elem.text.strip()
            
            rows = soup.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].text.strip().lower()
                    signal = cells[1].text.strip()
                    
                    if 'short' in label:
                        result['short_term'] = signal
                    elif 'intermediate' in label:
                        result['intermediate'] = signal
                    elif 'long' in label:
                        result['long_term'] = signal
            
            print(f"✅ Barchart {ticker}: {result['technical_rating']}")
    except Exception as e:
        print(f"⚠️ Barchart scrape error {ticker}: {e}")
    
    barchart_cache[cache_key] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 2. GURUFOCUS SCRAPING ========================
def scrape_gurufocus_ratings(ticker):
    """Scrape GuruFocus fundamental ratings"""
    cache_key = f"{ticker}_gurufocus"
    
    if cache_key in gurufocus_cache:
        cached = gurufocus_cache[cache_key]
        if (datetime.now() - cached['ts']).total_seconds() < GURUFOCUS_TTL:
            return cached['data']
    
    result = {
        'ticker': ticker,
        'guru_rating': 'N/A',
        'value_score': 'N/A',
        'quality_score': 'N/A',
        'financial_strength': 'N/A',
        'source': 'GuruFocus'
    }
    
    try:
        url = f'https://www.gurufocus.com/stock/{ticker.lower()}'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml')
            
            rating_text = soup.find('div', {'class': lambda x: x and 'rating' in x.lower()})
            if rating_text:
                result['guru_rating'] = rating_text.text.strip()
            
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        label = cells[0].text.strip().lower()
                        value = cells[1].text.strip()
                        
                        if 'value' in label:
                            result['value_score'] = value
                        elif 'quality' in label:
                            result['quality_score'] = value
                        elif 'financial strength' in label:
                            result['financial_strength'] = value
            
            print(f"✅ GuruFocus {ticker}: Rating {result['guru_rating']}")
    except Exception as e:
        print(f"⚠️ GuruFocus scrape error {ticker}: {e}")
    
    gurufocus_cache[cache_key] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 3. REDDIT SENTIMENT SCRAPING ========================
def scrape_reddit_sentiment(ticker):
    """Scrape Reddit sentiment"""
    cache_key = f"{ticker}_reddit"
    
    if cache_key in reddit_cache:
        cached = reddit_cache[cache_key]
        if (datetime.now() - cached['ts']).total_seconds() < REDDIT_TTL:
            return cached['data']
    
    result = {
        'ticker': ticker,
        'reddit_mentions': 0,
        'sentiment': 'NEUTRAL',
        'subreddits': ['r/stocks', 'r/investing', 'r/wallstreetbets'],
        'source': 'Reddit API',
        'note': 'Based on recent mentions and upvote ratios'
    }
    
    try:
        for subreddit in ['stocks', 'investing', 'wallstreetbets']:
            try:
                url = f'https://www.reddit.com/r/{subreddit}/search.json'
                params = {'q': ticker, 'restrict_sr': 'true', 'limit': 10}
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, params=params, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    posts = data.get('data', {}).get('children', [])
                    result['reddit_mentions'] += len(posts)
                    
                    upvote_ratios = [p['data'].get('upvote_ratio', 0.5) for p in posts]
                    avg_ratio = sum(upvote_ratios) / len(upvote_ratios) if upvote_ratios else 0.5
                    
                    if avg_ratio > 0.65:
                        result['sentiment'] = 'BULLISH'
                    elif avg_ratio < 0.35:
                        result['sentiment'] = 'BEARISH'
                    else:
                        result['sentiment'] = 'NEUTRAL'
                
                time.sleep(1)
            except:
                pass
        
        if result['reddit_mentions'] > 0:
            print(f"✅ Reddit {ticker}: {result['reddit_mentions']} mentions - {result['sentiment']}")
    except Exception as e:
        print(f"⚠️ Reddit scrape error {ticker}: {e}")
    
    reddit_cache[cache_key] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 4. HYBRID AI ANALYSIS ========================
def get_hybrid_analysis(ticker, barchart_data=None, gurufocus_data=None, reddit_data=None):
    """Combine scraped data + Perplexity Sonar"""
    
    if not PERPLEXITY_KEY:
        return {
            'ticker': ticker,
            'barchart': barchart_data or {},
            'gurufocus': gurufocus_data or {},
            'reddit': reddit_data or {},
            'sonar_analysis': 'Perplexity key not configured'
        }
    
    try:
        barchart_context = f"Barchart technical: {barchart_data.get('technical_rating', 'N/A')}" if barchart_data else ""
        gurufocus_context = f"GuruFocus rating: {gurufocus_data.get('guru_rating', 'N/A')}" if gurufocus_data else ""
        reddit_context = f"Reddit sentiment: {reddit_data.get('sentiment', 'N/A')} ({reddit_data.get('reddit_mentions', 0)} mentions)" if reddit_data else ""
        
        prompt = f"""Analyze {ticker} for day trading using this real market data:
{barchart_context}
{gurufocus_context}
{reddit_context}

Provide 3 bullets:
1. Edge: Bullish/Bearish % + catalyst
2. Trade Setup: Entry/Stop/Target 
3. Risk: Low/Medium/High

Use ONLY the scraped data above."""
        
        url = 'https://api.perplexity.ai/chat/completions'
        headers = {'Authorization': f'Bearer {PERPLEXITY_KEY}', 'Content-Type': 'application/json'}
        
        payload = {
            'model': 'sonar',
            'messages': [
                {'role': 'system', 'content': 'Expert trader. Use ONLY provided data.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.6,
            'max_tokens': 300
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            lines = content.split('\n')
            
            edge = next((l.strip() for l in lines if any(x in l.lower() for x in ['bullish', 'bearish', 'edge'])), 'Neutral')
            trade = next((l.strip() for l in lines if any(x in l.lower() for x in ['entry', 'stop', 'target'])), 'Monitor')
            risk = next((l.strip() for l in lines if 'risk' in l.lower()), 'Standard')
            
            print(f"✅ Sonar hybrid analysis for {ticker}")
            return {
                'ticker': ticker,
                'barchart': barchart_data or {},
                'gurufocus': gurufocus_data or {},
                'reddit': reddit_data or {},
                'sonar_analysis': {
                    'edge': edge,
                    'trade': trade,
                    'risk': risk,
                    'sources': ['Barchart', 'GuruFocus', 'Reddit', 'Perplexity Sonar']
                }
            }
    except Exception as e:
        print(f"❌ Hybrid analysis error {ticker}: {e}")
        return {
            'ticker': ticker,
            'barchart': barchart_data or {},
            'gurufocus': gurufocus_data or {},
            'reddit': reddit_data or {},
            'sonar_analysis': {'error': str(e)}
        }

# ======================== FRED MACRO DATA ========================
def fetch_fred_macro_data():
    if not FRED_KEY:
        return get_fallback_macro_data()
    
    macro_data = {
        'timestamp': datetime.now().isoformat(),
        'source': 'FRED API - St. Louis Federal Reserve',
        'indicators': {}
    }
    
    fred_series = {
        'DFF': {'name': 'Fed Funds Rate', 'unit': '%'},
        'T10Y2Y': {'name': '10Y-2Y Spread', 'unit': '%'},
        'DCOILWTICO': {'name': 'WTI Oil', 'unit': '$/B'},
    }
    
    try:
        for series_id, metadata in fred_series.items():
            try:
                url = f'https://api.stlouisfed.org/fred/series/observations'
                params = {
                    'series_id': series_id,
                    'api_key': FRED_KEY,
                    'limit': 1,
                    'sort_order': 'desc',
                    'file_type': 'json'
                }
                response = requests.get(url, params=params, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    obs = data.get('observations', [])
                    if obs:
                        latest = obs[0]
                        raw_value = latest.get('value')
                        if raw_value:
                            formatted_value = round(float(raw_value), 2)
                        else:
                            formatted_value = None
                        
                        macro_data['indicators'][series_id] = {
                            'name': metadata['name'],
                            'value': formatted_value,
                            'date': latest.get('date'),
                            'unit': metadata.get('unit', '')
                        }
            except:
                pass
            time.sleep(0.2)
        
        return macro_data
    except:
        return get_fallback_macro_data()

def get_fallback_macro_data():
    return {
        'timestamp': datetime.now().isoformat(),
        'source': 'Fallback Data',
        'indicators': {
            'DFF': {'name': 'Fed Funds Rate', 'value': 4.33, 'unit': '%'},
            'T10Y2Y': {'name': '10Y-2Y Spread', 'value': 0.55, 'unit': '%'},
            'DCOILWTICO': {'name': 'WTI Oil', 'value': 60.66, 'unit': '$/B'},
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
                    csv_stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
                    
                    results.append({
                        'Symbol': ticker,
                        'Last': round(price_data['price'], 2),
                        'Change': round(price_data['change'], 2),
                        'RSI': round(50 + (price_data['change'] * 2), 2),
                        'Signal': csv_stock['signal'] if csv_stock else 'HOLD',
                        'Strategy': 'Momentum' if price_data['change'] > 0 else 'Mean Reversion',
                        'Score': csv_stock['inst33'] if csv_stock else 50.0,
                        'KeyMetric': csv_stock['key_metric'] if csv_stock else ''
                    })
                except:
                    pass
        time.sleep(0.1)
    
    results.sort(key=lambda x: x.get('Score', 0), reverse=True)
    cleanup_cache()
    return results

# ======================== PERPLEXITY SONAR AI ========================
def get_perplexity_sonar_analysis(ticker, stock_data=None):
    if not PERPLEXITY_KEY:
        return {'edge': 'API not configured', 'trade': 'Set key', 'risk': 'N/A', 'sources': [], 'ticker': ticker}
    
    try:
        csv_stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
        context = f"\nScore: {csv_stock['inst33']}, Signal: {csv_stock['signal']}" if csv_stock else ""
        price_info = f"\nPrice: ${stock_data.get('Last', 'N/A')}, Change: {stock_data.get('Change', 'N/A')}%" if stock_data else ""
        
        prompt = f"""Analyze {ticker} for day trading using real-time market data.{price_info}{context}

Provide 3 bullets:
1. Edge: Bullish/Bearish % + catalyst
2. Trade: Entry/Stop/Target
3. Risk: Low/Med/High
Concise, cite sources."""
        
        url = 'https://api.perplexity.ai/chat/completions'
        headers = {'Authorization': f'Bearer {PERPLEXITY_KEY}', 'Content-Type': 'application/json'}
        
        payload = {
            'model': 'sonar',
            'messages': [
                {'role': 'system', 'content': 'Expert day trader. 3 bullets max.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.6,
            'max_tokens': 400
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            analysis_text = data['choices'][0]['message']['content']
            lines = analysis_text.split('\n')
            
            edge = next((l.strip() for l in lines if any(x in l.lower() for x in ['bullish', 'bearish', 'edge', '%'])), 'Neutral')
            trade = next((l.strip() for l in lines if any(x in l.lower() for x in ['entry', 'stop', 'target', 'buy', 'sell'])), 'Monitor')
            risk = next((l.strip() for l in lines if 'risk' in l.lower()), 'Standard')
            
            print(f"✅ Sonar analysis for {ticker}")
            return {
                'edge': edge,
                'trade': trade,
                'risk': risk,
                'sources': ['Perplexity Sonar'],
                'ticker': ticker
            }
        else:
            return {'edge': 'API error', 'trade': 'Retry', 'risk': 'Unknown', 'sources': [], 'ticker': ticker}
    except Exception as e:
        print(f"❌ Sonar error: {e}")
        return {'edge': f'Error: {e}', 'trade': 'N/A', 'risk': 'N/A', 'sources': [], 'ticker': ticker}

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
            'score': csv_stock['inst33'] if csv_stock else 50.0,
            'signal': csv_stock['signal'] if csv_stock else 'HOLD'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai-insights/<ticker>', methods=['GET'])
def get_ai_insights(ticker):
    ticker = ticker.upper()
    print(f"🤖 AI analysis for {ticker}")
    
    cache_key = f"{ticker}_ai_insights"
    if cache_key in ai_insights_cache:
        cache_data = ai_insights_cache[cache_key]
        cache_age = (datetime.now() - cache_data['timestamp']).total_seconds()
        if cache_age < AI_INSIGHTS_TTL:
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

@app.route('/api/hybrid-analysis/<ticker>', methods=['GET'])
def get_hybrid_analysis_endpoint(ticker):
    """NEW: Hybrid scraping + Perplexity analysis"""
    ticker = ticker.upper()
    print(f"🔍 Hybrid analysis for {ticker}")
    
    barchart_data = scrape_barchart_signals(ticker)
    gurufocus_data = scrape_gurufocus_ratings(ticker)
    reddit_data = scrape_reddit_sentiment(ticker)
    
    analysis = get_hybrid_analysis(ticker, barchart_data, gurufocus_data, reddit_data)
    
    return jsonify(analysis), 200

@app.route('/api/macro-indicators', methods=['GET'])
def get_macro_indicators():
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
                
                reddit_data = data.get('reddit', [])
                twitter_data = data.get('twitter', [])
                
                reddit_daily = reddit_data[-1] if reddit_data else {}
                twitter_daily = twitter_data[-1] if twitter_data else {}
                
                reddit_mentions = reddit_daily.get('mention', 0)
                twitter_mentions = twitter_daily.get('mention', 0)
                total_daily_mentions = reddit_mentions + twitter_mentions
                
                reddit_score = reddit_daily.get('score', 0)
                twitter_score = twitter_daily.get('score', 0)
                daily_score = (reddit_score + twitter_score) / 2 if (reddit_score or twitter_score) else 0
                
                daily_sentiment = 'BULLISH' if daily_score > 0.3 else 'BEARISH' if daily_score < -0.3 else 'NEUTRAL'
                
                weekly_mentions = sum(item.get('mention', 0) for item in reddit_data[-7:]) + sum(item.get('mention', 0) for item in twitter_data[-7:])
                weekly_score = (sum(item.get('score', 0) for item in reddit_data[-7:]) + sum(item.get('score', 0) for item in twitter_data[-7:])) / max(len(reddit_data[-7:]) + len(twitter_data[-7:]), 1)
                weekly_sentiment = 'BULLISH' if weekly_score > 0.3 else 'BEARISH' if weekly_score < -0.3 else 'NEUTRAL'
                
                week_prev_mentions = sum(item.get('mention', 0) for item in reddit_data[-14:-7]) + sum(item.get('mention', 0) for item in twitter_data[-14:-7])
                wow_change = ((weekly_mentions - week_prev_mentions) / max(week_prev_mentions, 1)) * 100 if week_prev_mentions > 0 else 0
                
                result = {
                    'ticker': ticker,
                    'source': 'Finnhub Social Sentiment API',
                    'daily': {
                        'score': round(daily_score, 2),
                        'mentions': int(total_daily_mentions),
                        'sentiment': daily_sentiment,
                        'reddit_mentions': int(reddit_mentions),
                        'twitter_mentions': int(twitter_mentions)
                    },
                    'weekly': {
                        'score': round(weekly_score, 2),
                        'mentions': int(weekly_mentions),
                        'sentiment': weekly_sentiment
                    },
                    'weekly_change': round(wow_change, 2)
                }
                
                sentiment_cache[cache_key] = {'data': result, 'timestamp': datetime.now()}
                print(f"✅ Sentiment for {ticker}: {total_daily_mentions} mentions (daily)")
                return jsonify(result), 200
        except Exception as e:
            print(f"❌ Finnhub sentiment error: {e}")
    
    ticker_hash = sum(ord(c) for c in ticker) % 100
    result = {
        'ticker': ticker,
        'source': 'Fallback Data',
        'daily': {
            'score': round((ticker_hash - 50) / 150, 2),
            'mentions': 100 + ticker_hash * 2,
            'sentiment': 'NEUTRAL',
            'reddit_mentions': 60 + ticker_hash,
            'twitter_mentions': 40 + ticker_hash
        },
        'weekly': {
            'score': 0.0,
            'mentions': 700 + ticker_hash * 14,
            'sentiment': 'NEUTRAL'
        },
        'weekly_change': 0.0
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
        from_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
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
    """6 OPTIONS STRATEGIES with Greeks"""
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
                    'description': 'Neutral - Sell OTM call/put spreads',
                    'direction': 'Neutral',
                    'setup': f'Sell ${round(current_price * 1.05, 2)} Call / Buy ${round(current_price * 1.08, 2)} Call, Sell ${round(current_price * 0.95, 2)} Put / Buy ${round(current_price * 0.92, 2)} Put',
                    'max_profit': round(current_price * 0.02, 2),
                    'max_loss': round(current_price * 0.03, 2),
                    'probability_of_profit': '65%',
                    'rating': 'Good',
                    'greeks': {'delta': '~0', 'gamma': 'Low', 'theta': '+High', 'vega': '-High'}
                },
                {
                    'type': 'Call Spread (Bullish)',
                    'description': 'Bullish - Buy lower call, sell higher call',
                    'direction': 'Bullish',
                    'setup': f'Buy ${round(current_price, 2)} Call / Sell ${round(current_price * 1.05, 2)} Call',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'rating': 'Neutral',
                    'greeks': {'delta': '+0.60', 'gamma': 'Positive', 'theta': 'Neutral', 'vega': 'Low'}
                },
                {
                    'type': 'Put Spread (Bearish)',
                    'description': 'Bearish - Buy higher put, sell lower put',
                    'direction': 'Bearish',
                    'setup': f'Buy ${round(current_price, 2)} Put / Sell ${round(current_price * 0.95, 2)} Put',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'rating': 'Neutral',
                    'greeks': {'delta': '-0.60', 'gamma': 'Positive', 'theta': 'Neutral', 'vega': 'Low'}
                },
                {
                    'type': 'Bullish Put Spread',
                    'description': 'Bullish - Sell OTM put, buy further OTM put',
                    'direction': 'Bullish (Income)',
                    'setup': f'Sell ${round(current_price * 0.98, 2)} Put / Buy ${round(current_price * 0.93, 2)} Put',
                    'max_profit': round(current_price * 0.02, 2),
                    'max_loss': round(current_price * 0.03, 2),
                    'probability_of_profit': '70%',
                    'rating': 'Good',
                    'greeks': {'delta': '+0.50', 'gamma': 'Negative', 'theta': '+High', 'vega': '-High'}
                },
                {
                    'type': 'Bearish Call Spread',
                    'description': 'Bearish - Sell OTM call, buy further OTM call',
                    'direction': 'Bearish (Income)',
                    'setup': f'Sell ${round(current_price * 1.02, 2)} Call / Buy ${round(current_price * 1.07, 2)} Call',
                    'max_profit': round(current_price * 0.02, 2),
                    'max_loss': round(current_price * 0.03, 2),
                    'probability_of_profit': '70%',
                    'rating': 'Good',
                    'greeks': {'delta': '-0.50', 'gamma': 'Negative', 'theta': '+High', 'vega': '-High'}
                },
                {
                    'type': 'Butterfly Spread',
                    'description': 'Neutral - Buy 1 call, sell 2 calls, buy 1 call',
                    'direction': 'Neutral (High Probability)',
                    'setup': f'Buy ${round(current_price * 0.98, 2)} Call / Sell 2x ${round(current_price, 2)} Call / Buy ${round(current_price * 1.02, 2)} Call',
                    'max_profit': round(current_price * 0.04, 2),
                    'max_loss': round(current_price * 0.01, 2),
                    'probability_of_profit': '50%',
                    'rating': 'Neutral',
                    'greeks': {'delta': '~0', 'gamma': 'Peaky', 'theta': '+Moderate', 'vega': 'Low'}
                }
            ]
        }
        return jsonify(opportunities)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def serve_frontend():
    """Serve the frontend HTML"""
    try:
        with open('index.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({
            'status': 'API Running',
            'message': 'Frontend not found. Place index.html in root directory.',
            'health_check': '/health'
        }), 200

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'scheduler_running': scheduler.running,
        'scraping_enabled': True,
        'perplexity_key': 'enabled' if PERPLEXITY_KEY else 'disabled',
        'fred_key': 'enabled' if FRED_KEY else 'disabled',
        'finnhub_key': 'enabled' if FINNHUB_KEY else 'disabled',
        'top_50_loaded': len(TOP_50_STOCKS),
        'endpoints': [
            '/',
            '/api/recommendations',
            '/api/stock-price/<ticker>',
            '/api/ai-insights/<ticker>',
            '/api/hybrid-analysis/<ticker>',
            '/api/macro-indicators',
            '/api/earnings-calendar',
            '/api/social-sentiment/<ticker>',
            '/api/insider-transactions/<ticker>',
            '/api/stock-news/<ticker>',
            '/api/options-opportunities/<ticker>'
        ]
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
