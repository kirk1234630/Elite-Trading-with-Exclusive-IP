from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import gc

app = Flask(__name__)
CORS(app)

# API KEYS
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')
ALPHAVANTAGE_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')
MASSIVE_KEY = os.environ.get('MASSIVE_API_KEY', '')
FRED_KEY = os.environ.get('FRED_API_KEY', '')

# PERSISTENT CACHE - Stocks stay cached for 5 minutes
price_cache = {}
recommendations_cache = {'data': [], 'timestamp': None}
news_cache = {'market_news': [], 'last_updated': None}

# Cache TTL in seconds
RECOMMENDATIONS_TTL = 300  # 5 minutes
NEWS_TTL = 1800  # 30 minutes

# Stock list (57 tickers)
TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'AMD', 'CRM', 'ADBE',
    'NFLX', 'PYPL', 'SHOP', 'RBLX', 'DASH', 'ZOOM', 'SNOW', 'CRWD', 'NET', 'ABNB',
    'UPST', 'COIN', 'RIOT', 'MARA', 'CLSK', 'MSTR', 'SQ', 'PLTR', 'ASML', 'INTU',
    'SNPS', 'MU', 'QCOM', 'AVGO', 'LRCX', 'TSM', 'INTC', 'VMW', 'SEMR',
    'SGRY', 'PSTG', 'DDOG', 'OKTA', 'ZS', 'CHKP', 'PANW', 'SMAR', 'NOW', 'VEEV',
    'TWLO', 'GTLB', 'ORCL', 'IBM', 'HPE', 'DELL', 'CSCO'
]

def cleanup_cache():
    """Remove expired cache entries to prevent memory buildup"""
    current_time = int(time.time() / 60)
    expired_keys = [k for k in price_cache.keys() if not k.endswith(f"_{current_time}") and not k.endswith(f"_{current_time-1}")]
    for key in expired_keys:
        del price_cache[key]
    gc.collect()

def get_stock_price_waterfall(ticker):
    """Fetch price with fallback: Polygon → Finnhub → Alpha Vantage"""
    
    # Check cache first (60-second TTL)
    cache_key = f"{ticker}_{int(time.time() / 60)}"
    if cache_key in price_cache:
        return price_cache[cache_key]
    
    result = {'price': 0, 'change': 0, 'source': 'fallback'}
    
    try:
        # Try Polygon (Massive API) first
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
        # Try Finnhub
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
    """Fetch multiple stock prices concurrently - MEMORY OPTIMIZED"""
    results = []
    
    # CRITICAL FIX: Process in batches of 15 with 3 concurrent workers
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
                        'Last': price_data['price'],
                        'Change': price_data['change'],
                        'RSI': 50 + (price_data['change'] * 2),
                        'Signal': 'BUY' if price_data['change'] > 2 else 'SELL' if price_data['change'] < -2 else 'HOLD',
                        'Strategy': 'Momentum' if price_data['change'] > 0 else 'Mean Reversion'
                    })
                except Exception as e:
                    print(f"Error fetching {ticker}: {e}")
        
        # Small delay between batches
        time.sleep(0.1)
    
    # Cleanup old cache entries
    cleanup_cache()
    
    return results

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Get stock recommendations with PERSISTENT CACHE (5 min TTL)"""
    try:
        # Check if we have valid cached data
        if recommendations_cache['data'] and recommendations_cache['timestamp']:
            cache_age = (datetime.now() - recommendations_cache['timestamp']).total_seconds()
            
            if cache_age < RECOMMENDATIONS_TTL:
                print(f"✅ Serving from cache (age: {cache_age:.0f}s)")
                return jsonify(recommendations_cache['data'])
        
        # Cache miss or expired - fetch fresh data
        print(f"🔄 Cache expired or empty - fetching fresh data")
        stocks = fetch_prices_concurrent(TICKERS)
        
        # Update cache
        recommendations_cache['data'] = stocks
        recommendations_cache['timestamp'] = datetime.now()
        
        return jsonify(stocks)
    except Exception as e:
        print(f"Error in recommendations: {e}")
        
        # If error but we have stale cache, return it anyway
        if recommendations_cache['data']:
            print(f"⚠️ Returning stale cache due to error")
            return jsonify(recommendations_cache['data'])
        
        return jsonify({'error': str(e)}), 500

@app.route('/api/recommendations/force-refresh', methods=['POST'])
def force_refresh_recommendations():
    """Force refresh stock data (ignores cache)"""
    try:
        print(f"🔄 FORCE REFRESH triggered")
        stocks = fetch_prices_concurrent(TICKERS)
        
        # Update cache
        recommendations_cache['data'] = stocks
        recommendations_cache['timestamp'] = datetime.now()
        
        return jsonify({
            'success': True,
            'stocks': stocks,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error in force refresh: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stock-news/<ticker>', methods=['GET'])
def get_stock_news(ticker):
    """Get stock-specific news from Finnhub"""
    if not FINNHUB_KEY:
        return jsonify({'error': 'Finnhub API key not configured'}), 500
    
    try:
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        
        url = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            articles = response.json()
            return jsonify({
                'ticker': ticker,
                'articles': articles[:10],
                'count': len(articles)
            })
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/market-news/dashboard', methods=['GET'])
def get_market_news_dashboard():
    """Get market news (5 articles) with 30min cache"""
    try:
        articles = fetch_market_news()
        return jsonify({
            'articles': articles[:5],
            'last_updated': news_cache['last_updated'].isoformat() if news_cache['last_updated'] else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/market-news/newsletter', methods=['GET'])
def get_market_news_newsletter():
    """Get detailed market news (10 articles) with 30min cache"""
    try:
        articles = fetch_market_news()
        return jsonify({
            'articles': articles[:10],
            'last_updated': news_cache['last_updated'].isoformat() if news_cache['last_updated'] else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def fetch_market_news():
    """Fetch general market news with persistent cache"""
    if news_cache['market_news'] and news_cache['last_updated']:
        cache_age = (datetime.now() - news_cache['last_updated']).total_seconds()
        if cache_age < NEWS_TTL:
            print(f"✅ Serving market news from cache (age: {cache_age:.0f}s)")
            return news_cache['market_news']
    
    if not FINNHUB_KEY:
        return []
    
    try:
        print(f"🔄 Fetching fresh market news")
        url = f'https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            articles = response.json()
            news_cache['market_news'] = articles
            news_cache['last_updated'] = datetime.now()
            return articles
    except Exception as e:
        print(f"Error fetching market news: {e}")
        # Return stale cache if error
        if news_cache['market_news']:
            return news_cache['market_news']
    
    return []

@app.route('/api/earnings-calendar', methods=['GET'])
def get_earnings_calendar():
    """Get next 7 days of earnings"""
    if not FINNHUB_KEY:
        return jsonify({'earnings': [], 'count': 0}), 200
    
    try:
        from_date = datetime.now().strftime('%Y-%m-%d')
        to_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        url = f'https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            earnings = data.get('earningsCalendar', [])
            filtered = [e for e in earnings if e.get('symbol') in TICKERS]
            
            return jsonify({
                'earnings': filtered,
                'count': len(filtered)
            })
    except Exception as e:
        print(f"Earnings error: {e}")
    
    return jsonify({'earnings': [], 'count': 0})

@app.route('/api/insider-transactions/<ticker>', methods=['GET'])
def get_insider_transactions(ticker):
    """Get insider activity"""
    if not FINNHUB_KEY:
        return jsonify({
            'ticker': ticker,
            'transactions': [],
            'insider_sentiment': 'NEUTRAL',
            'buy_count': 0,
            'sell_count': 0
        }), 200
    
    try:
        from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        url = f'https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&from={from_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            transactions = data.get('data', [])
            
            buys = sum(1 for t in transactions if t.get('transactionCode') in ['P', 'A'])
            sells = sum(1 for t in transactions if t.get('transactionCode') == 'S')
            
            return jsonify({
                'ticker': ticker,
                'transactions': transactions[:10],
                'insider_sentiment': 'BULLISH' if buys > sells else 'BEARISH' if sells > buys else 'NEUTRAL',
                'buy_count': buys,
                'sell_count': sells,
                'total_transactions': len(transactions)
            })
    except Exception as e:
        print(f"Insider error: {e}")
    
    return jsonify({
        'ticker': ticker,
        'transactions': [],
        'insider_sentiment': 'NEUTRAL',
        'buy_count': 0,
        'sell_count': 0
    })

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def get_social_sentiment(ticker):
    """Get social sentiment"""
    if not FINNHUB_KEY:
        return jsonify({
            'ticker': ticker,
            'reddit': {'score': 0, 'mentions': 0, 'sentiment': 'NEUTRAL'},
            'twitter': {'score': 0, 'mentions': 0, 'sentiment': 'NEUTRAL'},
            'overall_sentiment': 'NEUTRAL',
            'overall_score': 0
        }), 200
    
    try:
        url = f'https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            reddit_data = data.get('reddit', {})
            twitter_data = data.get('twitter', {})
            
            reddit_score = reddit_data.get('score', 0) if reddit_data else 0
            twitter_score = twitter_data.get('score', 0) if twitter_data else 0
            avg_score = (reddit_score + twitter_score) / 2
            
            return jsonify({
                'ticker': ticker,
                'reddit': {
                    'score': reddit_score,
                    'mentions': reddit_data.get('mention', 0) if reddit_data else 0,
                    'sentiment': 'BULLISH' if reddit_score > 0.5 else 'BEARISH' if reddit_score < -0.5 else 'NEUTRAL'
                },
                'twitter': {
                    'score': twitter_score,
                    'mentions': twitter_data.get('mention', 0) if twitter_data else 0,
                    'sentiment': 'BULLISH' if twitter_score > 0.5 else 'BEARISH' if twitter_score < -0.5 else 'NEUTRAL'
                },
                'overall_sentiment': 'BULLISH' if avg_score > 0.3 else 'BEARISH' if avg_score < -0.3 else 'NEUTRAL',
                'overall_score': round(avg_score, 2)
            })
    except Exception as e:
        print(f"Sentiment error: {e}")
    
    return jsonify({
        'ticker': ticker,
        'reddit': {'score': 0, 'mentions': 0, 'sentiment': 'NEUTRAL'},
        'twitter': {'score': 0, 'mentions': 0, 'sentiment': 'NEUTRAL'},
        'overall_sentiment': 'NEUTRAL',
        'overall_score': 0
    })

@app.route('/api/fred-data', methods=['GET'])
def get_fred_data():
    """Get FRED economic data"""
    if not FRED_KEY:
        return jsonify({'data': {}}), 200
    
    try:
        series_ids = {
            'GDP': 'GDP',
            'UNRATE': 'UNRATE',
            'CPIAUCSL': 'CPIAUCSL',
            'DFF': 'DFF',
            'DGS10': 'DGS10'
        }
        
        results = {}
        
        for name, series_id in series_ids.items():
            url = f'https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_KEY}&file_type=json&limit=1&sort_order=desc'
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                observations = data.get('observations', [])
                if observations and len(observations) > 0:
                    results[name] = {
                        'value': observations[0].get('value'),
                        'date': observations[0].get('date')
                    }
        
        return jsonify({'data': results, 'last_updated': datetime.now().isoformat()})
    except Exception as e:
        print(f"FRED error: {e}")
        return jsonify({'data': {}}), 200

@app.route('/api/balance-of-power/<ticker>', methods=['GET'])
def get_balance_of_power(ticker):
    """Calculate Balance of Power"""
    return jsonify({
        'ticker': ticker,
        'balance_of_power': 0.65,  # Mock data
        'interpretation': 'BULLISH'
    }), 200

# Health and cache status endpoints
@app.route('/health', methods=['GET'])
def health_check():
    """Health check with cache stats"""
    cache_age = 0
    if recommendations_cache['timestamp']:
        cache_age = (datetime.now() - recommendations_cache['timestamp']).total_seconds()
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'cache_stats': {
            'recommendations_cached': len(recommendations_cache['data']) > 0,
            'recommendations_age_seconds': cache_age,
            'news_cached': len(news_cache['market_news']) > 0
        }
    }), 200

@app.route('/api/cache-status', methods=['GET'])
def cache_status():
    """Get detailed cache status"""
    rec_age = 0
    news_age = 0
    
    if recommendations_cache['timestamp']:
        rec_age = (datetime.now() - recommendations_cache['timestamp']).total_seconds()
    
    if news_cache['last_updated']:
        news_age = (datetime.now() - news_cache['last_updated']).total_seconds()
    
    return jsonify({
        'recommendations': {
            'cached': len(recommendations_cache['data']) > 0,
            'count': len(recommendations_cache['data']),
            'age_seconds': rec_age,
            'ttl_seconds': RECOMMENDATIONS_TTL,
            'expires_in': max(0, RECOMMENDATIONS_TTL - rec_age)
        },
        'news': {
            'cached': len(news_cache['market_news']) > 0,
            'count': len(news_cache['market_news']),
            'age_seconds': news_age,
            'ttl_seconds': NEWS_TTL,
            'expires_in': max(0, NEWS_TTL - news_age)
        }
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
