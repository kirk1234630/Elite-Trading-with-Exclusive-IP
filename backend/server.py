from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
import json
import threading
import time
from functools import lru_cache
import concurrent.futures

app = Flask(__name__)
CORS(app)

# API Keys
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')
FRED_KEY = os.environ.get('FRED_API_KEY', '')
ALPHAVANTAGE_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')
MASSIVE_KEY = os.environ.get('MASSIVE_API_KEY', '')

print(f"[STARTUP] Finnhub Key: {'✓' if FINNHUB_KEY else '✗'}")
print(f"[STARTUP] Perplexity Key: {'✓' if PERPLEXITY_KEY else '✗'}")
print(f"[STARTUP] FRED Key: {'✓' if FRED_KEY else '✗'}")
print(f"[STARTUP] AlphaVantage Key: {'✓' if ALPHAVANTAGE_KEY else '✗'}")
print(f"[STARTUP] Massive Key: {'✓' if MASSIVE_KEY else '✗'}")

# Cached data storage
news_cache = {
    'market_news': [],
    'last_updated': None,
    'timestamp': None
}

# Price cache to reduce API calls
price_cache = {}
PRICE_CACHE_TTL = 60  # 60 seconds

TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'AMD', 'CRM', 'ADBE',
    'NFLX', 'PYPL', 'SHOP', 'RBLX', 'DASH', 'ZOOM', 'SNOW', 'CRWD', 'NET', 'ABNB',
    'UPST', 'COIN', 'RIOT', 'MARA', 'CLSK', 'MSTR', 'SQ', 'PLTR', 'ASML', 'INTU',
    'SNPS', 'MU', 'QCOM', 'AVGO', 'LRCX', 'TSM', 'INTC', 'VMW', 'CRWD', 'SEMR',
    'SGRY', 'PSTG', 'DDOG', 'OKTA', 'ZS', 'CHKP', 'PANW', 'SMAR', 'NOW', 'VEEV',
    'TWLO', 'GTLB', 'ORCL', 'IBM', 'HPE', 'DELL', 'CSCO'
]

# ==================== CACHING & SCHEDULING ====================

def should_update_news():
    """Check if we should update news based on schedule"""
    now = datetime.now()
    
    # PST times for updates
    pre_market = 6.5  # 6:30 AM
    midday = 12.5     # 12:30 PM
    close = 16.0      # 4:00 PM
    evening = 19.0    # 7:00 PM
    
    current_hour = now.hour + (now.minute / 60)
    
    # Check if we're within 5 minutes of any scheduled time
    scheduled_times = [pre_market, midday, close, evening]
    
    for scheduled_time in scheduled_times:
        if abs(current_hour - scheduled_time) < (5/60):  # 5 minutes window
            if news_cache['last_updated'] is None or \
               (datetime.now() - news_cache['last_updated']).total_seconds() > 600:  # 10 min cooldown
                return True
    
    # Also update if cache is older than 1 hour
    if news_cache['last_updated'] is None:
        return True
    
    cache_age = (datetime.now() - news_cache['last_updated']).total_seconds()
    return cache_age > 3600  # 1 hour
    
def update_market_news_cache():
    """Fetch and cache market news"""
    if not FINNHUB_KEY:
        print("[CACHE] Skipping news update - no Finnhub key")
        return
    
    try:
        url = f'https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            raw_news = response.json()
            
            # Format with sentiment analysis
            formatted_articles = []
            for article in raw_news[:30]:
                sentiment = analyze_sentiment_from_headline(article.get('headline', ''))
                
                formatted_articles.append({
                    'headline': article.get('headline', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('source', ''),
                    'url': article.get('url', ''),
                    'datetime': article.get('datetime', 0),
                    'image': article.get('image', ''),
                    'sentiment': sentiment
                })
            
            news_cache['market_news'] = formatted_articles
            news_cache['last_updated'] = datetime.now()
            news_cache['timestamp'] = datetime.now().isoformat()
            
            print(f"[CACHE] Market news updated at {news_cache['timestamp']} - {len(formatted_articles)} articles")
            
    except Exception as e:
        print(f"[CACHE_ERROR] Failed to update news cache: {e}")

def analyze_sentiment_from_headline(headline):
    """Simple sentiment analysis from headline keywords"""
    headline_lower = headline.lower()
    
    positive_keywords = ['surge', 'jump', 'rally', 'beat', 'record', 'gain', 'soar', 'bull', 'profit', 'growth']
    negative_keywords = ['crash', 'plunge', 'drop', 'miss', 'loss', 'decline', 'bear', 'risk', 'warning', 'fell']
    
    positive_count = sum(1 for word in positive_keywords if word in headline_lower)
    negative_count = sum(1 for word in negative_keywords if word in headline_lower)
    
    if positive_count > negative_count:
        return 'bullish'
    elif negative_count > positive_count:
        return 'bearish'
    else:
        return 'neutral'

def summarize_news_ai(headline, summary, detail_level='concise'):
    """Use Perplexity to summarize news at different detail levels"""
    if not PERPLEXITY_KEY:
        return summary[:150] if detail_level == 'concise' else summary
    
    try:
        if detail_level == 'concise':
            prompt = f"Summarize this news in ONE sentence (max 50 chars): {headline}"
        else:  # detailed
            prompt = f"Provide a 2-3 sentence detailed analysis of this news for a trading newsletter:\n\nHeadline: {headline}\nSummary: {summary}"
        
        response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers={
                'Authorization': f'Bearer {PERPLEXITY_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'sonar',
                'messages': [{
                    'role': 'user',
                    'content': prompt
                }]
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"[AI_SUMMARY_ERROR] {e}")
    
    return summary

# ==================== STOCK PRICE FETCHING ====================

def get_cached_price(ticker):
    """Check if we have a recent cached price"""
    if ticker in price_cache:
        cached_data, cached_time = price_cache[ticker]
        if (time.time() - cached_time) < PRICE_CACHE_TTL:
            return cached_data
    return None

def cache_price(ticker, price_data):
    """Cache price data"""
    price_cache[ticker] = (price_data, time.time())

def get_stock_price_massive(ticker):
    """Try Massive.com API first"""
    if not MASSIVE_KEY:
        return None
    
    try:
        url = f'https://api.polygon.io/v2/last/trade/{ticker}?apiKey={MASSIVE_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'OK' and 'results' in data:
                result = data['results']
                return {
                    'price': result.get('p', 0),
                    'source': 'Polygon',
                    'change': 0
                }
    except Exception as e:
        print(f"[MASSIVE] {ticker}: {str(e)[:50]}")
    
    return None

def get_stock_price_finnhub(ticker):
    """Try Finnhub API"""
    if not FINNHUB_KEY:
        return None
    
    try:
        url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('c') and data.get('c') > 0:
                return {
                    'price': float(data.get('c')),
                    'source': 'Finnhub',
                    'change': float(data.get('dp', 0))
                }
    except Exception as e:
        print(f"[FINNHUB] {ticker}: {str(e)[:50]}")
    
    return None

def get_stock_price_alphavantage(ticker):
    """Try Alpha Vantage API"""
    if not ALPHAVANTAGE_KEY:
        return None
    
    try:
        url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHAVANTAGE_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if 'Global Quote' in data:
                quote = data['Global Quote']
                if quote.get('05. price'):
                    return {
                        'price': float(quote['05. price']),
                        'source': 'Alpha Vantage',
                        'change': float(quote.get('10. change percent', '0').replace('%', ''))
                    }
    except Exception as e:
        print(f"[ALPHAVANTAGE] {ticker}: {str(e)[:50]}")
    
    return None

def get_stock_price_waterfall(ticker):
    """Try APIs in priority order with caching"""
    # Check cache first
    cached = get_cached_price(ticker)
    if cached:
        return cached
    
    # Try APIs in order
    result = get_stock_price_massive(ticker)
    if result:
        cache_price(ticker, result)
        return result
    
    result = get_stock_price_finnhub(ticker)
    if result:
        cache_price(ticker, result)
        return result
    
    result = get_stock_price_alphavantage(ticker)
    if result:
        cache_price(ticker, result)
        return result
    
    # Fallback
    fallback = {
        'price': 0.0,
        'source': 'Unavailable',
        'change': 0
    }
    cache_price(ticker, fallback)
    return fallback

def fetch_prices_concurrent(tickers):
    """Fetch multiple stock prices concurrently"""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_ticker = {executor.submit(get_stock_price_waterfall, ticker): ticker for ticker in tickers}
        for future in concurrent.futures.as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                price_data = future.result(timeout=10)
                if price_data['price'] > 0:
                    results.append({
                        'Symbol': ticker,
                        'Last': round(price_data['price'], 2),
                        'Change': round(price_data['change'], 2),
                        'Source': price_data['source'],
                        'RSI': 50,
                        'Signal': 'HOLD',
                        'Strategy': 'Momentum'
                    })
            except Exception as e:
                print(f"[CONCURRENT] Error fetching {ticker}: {e}")
    
    return results

# ==================== API ENDPOINTS ====================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'online',
        'version': '2.1',
        'endpoints': [
            '/api/recommendations',
            '/api/stock-news/<ticker>',
            '/api/market-news',
            '/api/market-news/dashboard',
            '/api/market-news/newsletter',
            '/api/config'
        ]
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        'finnhub_enabled': bool(FINNHUB_KEY),
        'perplexity_enabled': bool(PERPLEXITY_KEY),
        'massive_enabled': bool(MASSIVE_KEY),
        'alphavantage_enabled': bool(ALPHAVANTAGE_KEY),
        'cache_status': {
            'last_updated': news_cache['last_updated'].isoformat() if news_cache['last_updated'] else None,
            'articles_cached': len(news_cache['market_news'])
        }
    })

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Get stock recommendations with REAL prices (no hardcoded!)"""
    try:
        recommendations = fetch_prices_concurrent(TICKERS[:20])
        return jsonify(recommendations)
    except Exception as e:
        print(f"[ERROR] /api/recommendations: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stock-news/<ticker>', methods=['GET'])
def get_stock_news(ticker):
    """Get latest news for a specific stock"""
    if not ticker or len(ticker) > 10:
        return jsonify({'error': 'Invalid ticker'}), 400
        
    if not FINNHUB_KEY:
        return jsonify({'error': 'Finnhub not configured'}), 500
    
    try:
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        
        url = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            news = response.json()
            
            formatted_news = []
            for article in news[:10]:
                sentiment = analyze_sentiment_from_headline(article.get('headline', ''))
                formatted_news.append({
                    'headline': article.get('headline', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('source', ''),
                    'url': article.get('url', ''),
                    'datetime': article.get('datetime', 0),
                    'sentiment': sentiment
                })
            
            return jsonify({
                'ticker': ticker,
                'news_count': len(formatted_news),
                'articles': formatted_news
            })
        else:
            return jsonify({'error': f'API returned status {response.status_code}'}), 500
            
    except Exception as e:
        print(f"[ERROR] /api/stock-news/{ticker}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/market-news', methods=['GET'])
def get_market_news():
    """Get cached market news (auto-refreshes)"""
    try:
        # Check if we should update cache
        if should_update_news():
            print("[AUTO-UPDATE] Triggering news cache update...")
            update_market_news_cache()
        
        return jsonify({
            'articles': news_cache['market_news'][:30],
            'news_count': len(news_cache['market_news']),
            'last_updated': news_cache['timestamp'],
            'cache_age_seconds': (datetime.now() - news_cache['last_updated']).total_seconds() if news_cache['last_updated'] else None
        })
    except Exception as e:
        print(f"[ERROR] /api/market-news: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/market-news/dashboard', methods=['GET'])
def get_market_news_dashboard():
    """Concise news for dashboard (5 articles max)"""
    try:
        if should_update_news():
            update_market_news_cache()
        
        concise_articles = []
        for article in news_cache['market_news'][:5]:
            concise_summary = article['summary'][:100] if article.get('summary') else article.get('headline', '')[:100]
            
            concise_articles.append({
                'headline': article['headline'],
                'summary': concise_summary,
                'sentiment': article.get('sentiment', 'neutral'),
                'source': article['source'],
                'url': article['url']
            })
        
        return jsonify({
            'articles': concise_articles,
            'news_count': len(concise_articles),
            'last_updated': news_cache['timestamp']
        })
    except Exception as e:
        print(f"[ERROR] /api/market-news/dashboard: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/market-news/newsletter', methods=['GET'])
def get_market_news_newsletter():
    """Detailed news for newsletter (10 articles)"""
    try:
        if should_update_news():
            update_market_news_cache()
        
        detailed_articles = []
        for article in news_cache['market_news'][:10]:
            detailed_articles.append({
                'headline': article['headline'],
                'summary': article['summary'],
                'sentiment': article.get('sentiment', 'neutral'),
                'source': article['source'],
                'url': article['url'],
                'datetime': article['datetime']
            })
        
        return jsonify({
            'articles': detailed_articles,
            'news_count': len(detailed_articles),
            'last_updated': news_cache['timestamp'],
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"[ERROR] /api/market-news/newsletter: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== STARTUP & THREADING ====================

def scheduled_news_updater():
    """Background thread that updates news on schedule"""
    while True:
        try:
            if should_update_news():
                print("[SCHEDULER] Updating news cache...")
                update_market_news_cache()
            
            # Check every 2 minutes
            time.sleep(120)
        except Exception as e:
            print(f"[SCHEDULER_ERROR] {e}")
            time.sleep(120)

# Initialize app data on startup (Flask 3.0 compatible)
def init_app_data():
    """Initialize cache and start scheduler"""
    print("[INIT] Fetching initial news cache...")
    update_market_news_cache()
    
    # Start background thread
    scheduler_thread = threading.Thread(target=scheduled_news_updater, daemon=True)
    scheduler_thread.start()
    print("[INIT] News scheduler started")

# Call initialization before first request using application context
with app.app_context():
    init_app_data()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(debug=False, host='0.0.0.0', port=port)

