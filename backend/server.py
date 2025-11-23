rom flask import Flask, jsonify, request
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

# PERSISTENT CACHE
price_cache = {}
recommendations_cache = {'data': [], 'timestamp': None}
news_cache = {
    'market_news': [],
    'last_updated': None,
    'update_schedule': [9, 12, 16, 19]  # Hours PST: 9am, 12pm, 4pm, 7pm
}
sentiment_cache = {}  # Cache daily/weekly sentiment per ticker

# Cache TTL
RECOMMENDATIONS_TTL = 300  # 5 minutes
NEWS_TTL = 3600  # 1 hour (but only updates 4x/day)
SENTIMENT_TTL = 86400  # 24 hours for sentiment

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
    """Remove expired cache entries"""
    current_time = int(time.time() / 60)
    expired_keys = [k for k in price_cache.keys() if not k.endswith(f"_{current_time}") and not k.endswith(f"_{current_time-1}")]
    for key in expired_keys:
        del price_cache[key]
    gc.collect()

def should_update_news():
    """Check if it's time for scheduled news update (4x/day)"""
    if not news_cache['last_updated']:
        return True
    
    now = datetime.now()
    current_hour = now.hour
    last_update = news_cache['last_updated']
    
    # Find next scheduled update hour
    next_update_hours = [h for h in news_cache['update_schedule'] if h > last_update.hour]
    
    # If we passed a scheduled hour since last update
    if next_update_hours and current_hour >= next_update_hours[0]:
        return True
    
    # Or if it's a new day and we haven't updated yet today
    if now.date() > last_update.date() and current_hour >= news_cache['update_schedule'][0]:
        return True
    
    return False

def get_stock_price_waterfall(ticker):
    """Fetch price with fallback"""
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
    """Fetch prices in batches - MEMORY OPTIMIZED"""
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
                        'Last': round(price_data['price'], 2),  # 2 decimal places
                        'Change': round(price_data['change'], 2),  # 2 decimal places
                        'RSI': round(50 + (price_data['change'] * 2), 2),
                        'Signal': 'BUY' if price_data['change'] > 2 else 'SELL' if price_data['change'] < -2 else 'HOLD',
                        'Strategy': 'Momentum' if price_data['change'] > 0 else 'Mean Reversion'
                    })
                except Exception as e:
                    print(f"Error fetching {ticker}: {e}")
        
        time.sleep(0.1)
    
    cleanup_cache()
    return results

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Get stock recommendations with PERSISTENT CACHE"""
    try:
        if recommendations_cache['data'] and recommendations_cache['timestamp']:
            cache_age = (datetime.now() - recommendations_cache['timestamp']).total_seconds()
            if cache_age < RECOMMENDATIONS_TTL:
                print(f"✅ Serving from cache (age: {cache_age:.0f}s)")
                return jsonify(recommendations_cache['data'])
        
        print(f"🔄 Fetching fresh data")
        stocks = fetch_prices_concurrent(TICKERS)
        recommendations_cache['data'] = stocks
        recommendations_cache['timestamp'] = datetime.now()
        
        return jsonify(stocks)
    except Exception as e:
        print(f"Error: {e}")
        if recommendations_cache['data']:
            return jsonify(recommendations_cache['data'])
        return jsonify({'error': str(e)}), 500

@app.route('/api/stock-news/<ticker>', methods=['GET'])
def get_stock_news(ticker):
    """Get stock-specific news - ALWAYS FRESH for non-CSV stocks"""
    if not FINNHUB_KEY:
        return jsonify({'error': 'Finnhub not configured'}), 500
    
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
        print(f"Error fetching news: {e}")
    
    return jsonify({'ticker': ticker, 'articles': [], 'count': 0})

@app.route('/api/market-news/dashboard', methods=['GET'])
def get_market_news_dashboard():
    """Get market news with 4x/day scheduled updates"""
    try:
        articles = fetch_market_news_scheduled()
        return jsonify({
            'articles': articles[:5],
            'last_updated': news_cache['last_updated'].isoformat() if news_cache['last_updated'] else None,
            'next_update': get_next_update_time()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/market-news/newsletter', methods=['GET'])
def get_market_news_newsletter():
    """Get detailed market news"""
    try:
        articles = fetch_market_news_scheduled()
        return jsonify({
            'articles': articles[:10],
            'last_updated': news_cache['last_updated'].isoformat() if news_cache['last_updated'] else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def fetch_market_news_scheduled():
    """Fetch market news on schedule (4x/day)"""
    # Check if we should update
    if news_cache['market_news'] and not should_update_news():
        cache_age = (datetime.now() - news_cache['last_updated']).total_seconds()
        print(f"✅ Serving market news from cache (age: {cache_age:.0f}s)")
        return news_cache['market_news']
    
    if not FINNHUB_KEY:
        return []
    
    try:
        print(f"🔄 Fetching fresh market news (scheduled update)")
        url = f'https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            articles = response.json()
            news_cache['market_news'] = articles
            news_cache['last_updated'] = datetime.now()
            return articles
    except Exception as e:
        print(f"Error: {e}")
        if news_cache['market_news']:
            return news_cache['market_news']
    
    return []

def get_next_update_time():
    """Get next scheduled news update time"""
    now = datetime.now()
    current_hour = now.hour
    
    for hour in news_cache['update_schedule']:
        if hour > current_hour:
            next_update = now.replace(hour=hour, minute=0, second=0)
            return next_update.isoformat()
    
    # Next update is tomorrow's first scheduled time
    tomorrow = now + timedelta(days=1)
    next_update = tomorrow.replace(hour=news_cache['update_schedule'][0], minute=0, second=0)
    return next_update.isoformat()

@app.route('/api/earnings-calendar', methods=['GET'])
def get_earnings_calendar():
    """Get earnings calendar"""
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
            
            return jsonify({'earnings': filtered, 'count': len(filtered)})
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
    """Get social sentiment with daily + weekly comparison"""
    if not FINNHUB_KEY:
        return jsonify({
            'ticker': ticker,
            'daily': {'score': 0, 'mentions': 0, 'sentiment': 'NEUTRAL'},
            'weekly': {'score': 0, 'mentions': 0, 'sentiment': 'NEUTRAL'},
            'weekly_change': 0,
            'monthly_change': 0,
            'overall_sentiment': 'NEUTRAL'
        }), 200
    
    # Check cache
    cache_key = f"{ticker}_sentiment"
    if cache_key in sentiment_cache:
        cache_data = sentiment_cache[cache_key]
        cache_age = (datetime.now() - cache_data['timestamp']).total_seconds()
        if cache_age < SENTIMENT_TTL:
            return jsonify(cache_data['data'])
    
    try:
        url = f'https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            reddit_data = data.get('reddit', [])
            twitter_data = data.get('twitter', [])
            
            # Calculate daily (last entry)
            reddit_daily = reddit_data[-1] if reddit_data else {}
            twitter_daily = twitter_data[-1] if twitter_data else {}
            
            reddit_daily_score = reddit_daily.get('score', 0)
            twitter_daily_score = twitter_daily.get('score', 0)
            daily_avg = (reddit_daily_score + twitter_daily_score) / 2
            
            # Calculate weekly average (last 7 entries)
            reddit_weekly = reddit_data[-7:] if len(reddit_data) >= 7 else reddit_data
            twitter_weekly = twitter_data[-7:] if len(twitter_data) >= 7 else twitter_data
            
            reddit_weekly_avg = sum(r.get('score', 0) for r in reddit_weekly) / len(reddit_weekly) if reddit_weekly else 0
            twitter_weekly_avg = sum(t.get('score', 0) for t in twitter_weekly) / len(twitter_weekly) if twitter_weekly else 0
            weekly_avg = (reddit_weekly_avg + twitter_weekly_avg) / 2
            
            # Calculate changes
            weekly_change = round(((daily_avg - weekly_avg) / weekly_avg * 100) if weekly_avg != 0 else 0, 2)
            
            result = {
                'ticker': ticker,
                'daily': {
                    'score': round(daily_avg, 2),
                    'mentions': reddit_daily.get('mention', 0) + twitter_daily.get('mention', 0),
                    'sentiment': 'BULLISH' if daily_avg > 0.3 else 'BEARISH' if daily_avg < -0.3 else 'NEUTRAL'
                },
                'weekly': {
                    'score': round(weekly_avg, 2),
                    'mentions': sum(r.get('mention', 0) for r in reddit_weekly) + sum(t.get('mention', 0) for t in twitter_weekly),
                    'sentiment': 'BULLISH' if weekly_avg > 0.3 else 'BEARISH' if weekly_avg < -0.3 else 'NEUTRAL'
                },
                'weekly_change': weekly_change,
                'monthly_change': round(weekly_change * 1.3, 2),  # Approximate monthly
                'overall_sentiment': 'BULLISH' if daily_avg > 0.3 else 'BEARISH' if daily_avg < -0.3 else 'NEUTRAL'
            }
            
            # Cache result
            sentiment_cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now()
            }
            
            return jsonify(result)
    except Exception as e:
        print(f"Sentiment error: {e}")
    
    return jsonify({
        'ticker': ticker,
        'daily': {'score': 0, 'mentions': 0, 'sentiment': 'NEUTRAL'},
        'weekly': {'score': 0, 'mentions': 0, 'sentiment': 'NEUTRAL'},
        'weekly_change': 0,
        'monthly_change': 0,
        'overall_sentiment': 'NEUTRAL'
    })

@app.route('/api/options-opportunities/<ticker>', methods=['GET'])
def get_options_opportunities(ticker):
    """Get options opportunities for spreads, iron condors, butterflies"""
    # This would integrate with options data APIs
    # For now, return mock data structure
    
    try:
        # Get current price
        price_data = get_stock_price_waterfall(ticker)
        current_price = price_data['price']
        
        # Mock opportunities
        opportunities = {
            'ticker': ticker,
            'current_price': round(current_price, 2),
            'strategies': [
                {
                    'type': 'Iron Condor',
                    'setup': f'Sell {round(current_price * 1.05, 2)} Call / Buy {round(current_price * 1.08, 2)} Call, Sell {round(current_price * 0.95, 2)} Put / Buy {round(current_price * 0.92, 2)} Put',
                    'max_profit': round(current_price * 0.02, 2),
                    'max_loss': round(current_price * 0.03, 2),
                    'probability_of_profit': '65%',
                    'days_to_expiration': 30,
                    'recommendation': 'GOOD' if abs(price_data['change']) < 2 else 'NEUTRAL'
                },
                {
                    'type': 'Call Spread',
                    'setup': f'Buy {round(current_price, 2)} Call / Sell {round(current_price * 1.05, 2)} Call',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'days_to_expiration': 30,
                    'recommendation': 'BUY' if price_data['change'] > 0 else 'NEUTRAL'
                },
                {
                    'type': 'Put Spread',
                    'setup': f'Buy {round(current_price, 2)} Put / Sell {round(current_price * 0.95, 2)} Put',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'days_to_expiration': 30,
                    'recommendation': 'BUY' if price_data['change'] < 0 else 'NEUTRAL'
                },
                {
                    'type': 'Butterfly',
                    'setup': f'Buy {round(current_price * 0.98, 2)} Call / Sell 2x {round(current_price, 2)} Call / Buy {round(current_price * 1.02, 2)} Call',
                    'max_profit': round(current_price * 0.04, 2),
                    'max_loss': round(current_price * 0.01, 2),
                    'probability_of_profit': '50%',
                    'days_to_expiration': 30,
                    'recommendation': 'GOOD' if abs(price_data['change']) < 1.5 else 'NEUTRAL'
                }
            ]
        }
        
        return jsonify(opportunities)
    except Exception as e:
        print(f"Options error: {e}")
        return jsonify({'error': str(e)}), 500

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
        
        return jsonify({'data': results})
    except Exception as e:
        print(f"FRED error: {e}")
        return jsonify({'data': {}}), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Health check"""
    cache_age = 0
    if recommendations_cache['timestamp']:
        cache_age = (datetime.now() - recommendations_cache['timestamp']).total_seconds()
    
    return jsonify({
        'status': 'healthy',
        'cache_age_seconds': cache_age,
        'next_news_update': get_next_update_time()
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
