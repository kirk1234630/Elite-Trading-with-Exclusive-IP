from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

app = Flask(__name__)
CORS(app)

# API KEYS
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')
ALPHAVANTAGE_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')
MASSIVE_KEY = os.environ.get('MASSIVE_API_KEY', '')
FRED_KEY = os.environ.get('FRED_API_KEY', '')

# Price cache
price_cache = {}
news_cache = {'market_news': [], 'last_updated': None}

# Stock list (57 tickers)
TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'AMD', 'CRM', 'ADBE',
    'NFLX', 'PYPL', 'SHOP', 'RBLX', 'DASH', 'ZOOM', 'SNOW', 'CRWD', 'NET', 'ABNB',
    'UPST', 'COIN', 'RIOT', 'MARA', 'CLSK', 'MSTR', 'SQ', 'PLTR', 'ASML', 'INTU',
    'SNPS', 'MU', 'QCOM', 'AVGO', 'LRCX', 'TSM', 'INTC', 'VMW', 'SEMR',
    'SGRY', 'PSTG', 'DDOG', 'OKTA', 'ZS', 'CHKP', 'PANW', 'SMAR', 'NOW', 'VEEV',
    'TWLO', 'GTLB', 'ORCL', 'IBM', 'HPE', 'DELL', 'CSCO'
]

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
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    result['price'] = data['results']['c']
                    result['change'] = ((data['results']['c'] - data['results']['o']) / data['results']['o']) * 100
                    result['source'] = 'Polygon'
                    price_cache[cache_key] = result
                    return result
    except:
        pass
    
    try:
        # Try Finnhub
        if FINNHUB_KEY:
            url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=5)
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
    
    try:
        # Try Alpha Vantage
        if ALPHAVANTAGE_KEY:
            url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHAVANTAGE_KEY}'
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                quote = data.get('Global Quote', {})
                if quote:
                    result['price'] = float(quote.get('05. price', 0))
                    result['change'] = float(quote.get('10. change percent', '0').replace('%', ''))
                    result['source'] = 'AlphaVantage'
                    price_cache[cache_key] = result
                    return result
    except:
        pass
    
    return result

def fetch_prices_concurrent(tickers):
    """Fetch multiple stock prices concurrently"""
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ticker = {executor.submit(get_stock_price_waterfall, ticker): ticker for ticker in tickers}
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                price_data = future.result()
                results.append({
                    'Symbol': ticker,
                    'Last': price_data['price'],
                    'Change': price_data['change'],
                    'RSI': 50 + (price_data['change'] * 2),  # Mock RSI
                    'Signal': 'BUY' if price_data['change'] > 2 else 'SELL' if price_data['change'] < -2 else 'HOLD',
                    'Strategy': 'Momentum' if price_data['change'] > 0 else 'Mean Reversion'
                })
            except Exception as e:
                print(f"Error fetching {ticker}: {e}")
    return results

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Get stock recommendations with real prices"""
    try:
        stocks = fetch_prices_concurrent(TICKERS)
        return jsonify(stocks)
    except Exception as e:
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
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            articles = response.json()
            return jsonify({
                'ticker': ticker,
                'articles': articles[:10],  # Return top 10
                'count': len(articles)
            })
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/market-news/dashboard', methods=['GET'])
def get_market_news_dashboard():
    """Get market news (5 articles for dashboard)"""
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
    """Get detailed market news (10 articles for newsletter)"""
    try:
        articles = fetch_market_news()
        return jsonify({
            'articles': articles[:10],
            'last_updated': news_cache['last_updated'].isoformat() if news_cache['last_updated'] else None
        })
    except Exception as e):
        return jsonify({'error': str(e)}), 500

def fetch_market_news():
    """Fetch general market news"""
    if news_cache['market_news'] and news_cache['last_updated']:
        cache_age = (datetime.now() - news_cache['last_updated']).total_seconds()
        if cache_age < 1800:  # 30 minutes
            return news_cache['market_news']
    
    if not FINNHUB_KEY:
        return []
    
    try:
        url = f'https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            articles = response.json()
            news_cache['market_news'] = articles
            news_cache['last_updated'] = datetime.now()
            return articles
    except:
        pass
    
    return []

# ======== PHASE 1 ADDITIONS ========

@app.route('/api/earnings-calendar', methods=['GET'])
def get_earnings_calendar():
    """Get next 7 days of earnings (Finnhub)"""
    if not FINNHUB_KEY:
        return jsonify({'error': 'Finnhub not configured'}), 500
    
    try:
        from_date = datetime.now().strftime('%Y-%m-%d')
        to_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        url = f'https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            earnings = data.get('earningsCalendar', [])
            
            # Filter to our tickers only
            filtered = [e for e in earnings if e.get('symbol') in TICKERS]
            
            return jsonify({
                'earnings': filtered,
                'count': len(filtered),
                'from_date': from_date,
                'to_date': to_date
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/insider-transactions/<ticker>', methods=['GET'])
def get_insider_transactions(ticker):
    """Get last 30 days of insider activity (Finnhub)"""
    if not FINNHUB_KEY:
        return jsonify({'error': 'Finnhub not configured'}), 500
    
    try:
        from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        
        url = f'https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&from={from_date}&to={to_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            transactions = data.get('data', [])
            
            # Calculate insider sentiment
            buys = sum(1 for t in transactions if t.get('transactionCode') in ['P', 'A'])
            sells = sum(1 for t in transactions if t.get('transactionCode') == 'S')
            
            sentiment = 'BULLISH' if buys > sells else 'BEARISH' if sells > buys else 'NEUTRAL'
            
            return jsonify({
                'ticker': ticker,
                'transactions': transactions[:10],  # Last 10
                'insider_sentiment': sentiment,
                'buy_count': buys,
                'sell_count': sells,
                'total_transactions': len(transactions)
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def get_social_sentiment(ticker):
    """Get Reddit/Twitter sentiment (Finnhub)"""
    if not FINNHUB_KEY:
        return jsonify({'error': 'Finnhub not configured'}), 500
    
    try:
        url = f'https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            reddit_data = data.get('reddit', {})
            twitter_data = data.get('twitter', {})
            
            reddit_score = reddit_data.get('score', 0) if reddit_data else 0
            twitter_score = twitter_data.get('score', 0) if twitter_data else 0
            
            avg_score = (reddit_score + twitter_score) / 2 if (reddit_score or twitter_score) else 0
            
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/fred-data', methods=['GET'])
def get_fred_data():
    """Get macro economic data from FRED API"""
    if not FRED_KEY:
        return jsonify({'error': 'FRED API key not configured'}), 500
    
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
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                observations = data.get('observations', [])
                if observations:
                    results[name] = {
                        'value': observations.get('value'),
                        'date': observations.get('date')
                    }
        
        return jsonify({
            'data': results,
            'last_updated': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/balance-of-power/<ticker>', methods=['GET'])
def get_balance_of_power(ticker):
    """Calculate Balance of Power indicator"""
    try:
        # Fetch OHLC data from Alpha Vantage
        if not ALPHAVANTAGE_KEY:
            return jsonify({'error': 'Alpha Vantage not configured'}), 500
        
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={ALPHAVANTAGE_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            time_series = data.get('Time Series (Daily)', {})
            
            if not time_series:
                return jsonify({'error': 'No data available'}), 404
            
            # Get last day's data
            latest_date = list(time_series.keys())
            latest = time_series[latest_date]
            
            open_price = float(latest['1. open'])
            high_price = float(latest['2. high'])
            low_price = float(latest['3. low'])
            close_price = float(latest['4. close'])
            
            # Balance of Power = (Close - Open) / (High - Low)
            if high_price != low_price:
                bop = (close_price - open_price) / (high_price - low_price)
            else:
                bop = 0
            
            return jsonify({
                'ticker': ticker,
                'balance_of_power': round(bop, 4),
                'interpretation': 'BULLISH' if bop > 0.5 else 'BEARISH' if bop < -0.5 else 'NEUTRAL',
                'date': latest_date
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
# Add these endpoints to your server.py

@app.route('/api/earnings-calendar', methods=['GET'])
def get_earnings_calendar():
    """Get next 7 days of earnings"""
    if not FINNHUB_KEY:
        return jsonify({'error': 'Finnhub not configured', 'earnings': [], 'count': 0}), 200
    
    try:
        from_date = datetime.now().strftime('%Y-%m-%d')
        to_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        url = f'https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'earnings': data.get('earningsCalendar', []),
                'count': len(data.get('earningsCalendar', []))
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
            'sell_count': 0,
            'total_transactions': 0
        }), 200
    
    try:
        from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        url = f'https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&from={from_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
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
        'sell_count': 0,
        'total_transactions': 0
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
        response = requests.get(url, timeout=10)
        
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
