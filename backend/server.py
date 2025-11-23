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

# Cache
price_cache = {}
recommendations_cache = {'data': [], 'timestamp': None}
news_cache = {'market_news': [], 'last_updated': None, 'update_schedule': [9, 12, 16, 19]}
sentiment_cache = {}
ai_insights_cache = {}

# TTL
RECOMMENDATIONS_TTL = 300
NEWS_TTL = 3600
SENTIMENT_TTL = 86400
AI_INSIGHTS_TTL = 1800  # 30 minutes for AI insights

# Tickers
TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'AMD', 'CRM', 'ADBE',
    'NFLX', 'PYPL', 'SHOP', 'RBLX', 'DASH', 'ZOOM', 'SNOW', 'CRWD', 'NET', 'ABNB',
    'UPST', 'COIN', 'RIOT', 'MARA', 'CLSK', 'MSTR', 'SQ', 'PLTR', 'ASML', 'INTU',
    'SNPS', 'MU', 'QCOM', 'AVGO', 'LRCX', 'TSM', 'INTC', 'VMW', 'SEMR',
    'SGRY', 'PSTG', 'DDOG', 'OKTA', 'ZS', 'CHKP', 'PANW', 'SMAR', 'NOW', 'VEEV',
    'TWLO', 'GTLB', 'ORCL', 'IBM', 'HPE', 'DELL', 'CSCO'
]

def cleanup_cache():
    current_time = int(time.time() / 60)
    expired_keys = [k for k in price_cache.keys() if not k.endswith(f"_{current_time}") and not k.endswith(f"_{current_time-1}")]
    for key in expired_keys:
        del price_cache[key]
    gc.collect()

def should_update_news():
    if not news_cache['last_updated']:
        return True
    now = datetime.now()
    current_hour = now.hour
    last_update = news_cache['last_updated']
    next_update_hours = [h for h in news_cache['update_schedule'] if h > last_update.hour]
    if next_update_hours and current_hour >= next_update_hours[0]:
        return True
    if now.date() > last_update.date() and current_hour >= news_cache['update_schedule'][0]:
        return True
    return False

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
    """Get individual stock price for ANY ticker"""
    try:
        price_data = get_stock_price_waterfall(ticker.upper())
        return jsonify({
            'ticker': ticker.upper(),
            'price': round(price_data['price'], 2),
            'change': round(price_data['change'], 2),
            'rsi': round(50 + (price_data['change'] * 2), 2),
            'signal': 'BUY' if price_data['change'] > 2 else 'SELL' if price_data['change'] < -2 else 'HOLD'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# AI INSIGHTS WITH PERPLEXITY
@app.route('/api/ai-insights/<ticker>', methods=['GET'])
def get_ai_insights(ticker):
    """Get AI-powered insights using Perplexity to scrape multiple sources"""
    
    cache_key = f"{ticker}_ai_insights"
    if cache_key in ai_insights_cache:
        cache_data = ai_insights_cache[cache_key]
        cache_age = (datetime.now() - cache_data['timestamp']).total_seconds()
        if cache_age < AI_INSIGHTS_TTL:
            return jsonify(cache_data['data'])
    
    if not PERPLEXITY_KEY:
        return jsonify({
            'ticker': ticker,
            'edge': 'Perplexity API not configured',
            'trade': 'N/A',
            'risk': 'N/A',
            'sources': []
        }), 200
    
    try:
        # Perplexity AI prompt to scrape all sources
        prompt = f"""Analyze {ticker} stock using these specific sources:
1. Barchart.com - Check technical ratings, volatility, and options flow
2. Swaggystocks.com - Analyze Reddit sentiment and retail trader activity  
3. Quiver Quantitative - Review congressional trading and insider flows
4. Stock Rover - Evaluate fundamental metrics and valuation
5. GuruFocus - Check guru holdings and quality scores

Also search Perplexity Finance for latest news and analyst ratings.

Provide a concise analysis in this exact format:

EDGE: [One sentence on the trading edge or catalyst]
TRADE: [Specific entry/exit strategy with price levels]
RISK: [Key risks and stop-loss level]
SOURCES: [List which sources had the most relevant data]"""

        # Call Perplexity API
        headers = {
            'Authorization': f'Bearer {PERPLEXITY_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'llama-3.1-sonar-large-128k-online',
            'messages': [
                {'role': 'system', 'content': 'You are a professional trading analyst with access to multiple financial data sources.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.2,
            'max_tokens': 500
        }
        
        response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            # Parse response
            edge = 'Analyzing...'
            trade = 'Setting up trade...'
            risk = 'Assessing risk...'
            sources = []
            
            if 'EDGE:' in content:
                edge = content.split('EDGE:')[1].split('TRADE:')[0].strip()
            if 'TRADE:' in content:
                trade = content.split('TRADE:')[1].split('RISK:')[0].strip()
            if 'RISK:' in content:
                risk = content.split('RISK:')[1].split('SOURCES:')[0].strip() if 'SOURCES:' in content else content.split('RISK:')[1].strip()
            if 'SOURCES:' in content:
                sources_text = content.split('SOURCES:')[1].strip()
                sources = [s.strip() for s in sources_text.split(',') if s.strip()]
            
            result = {
                'ticker': ticker,
                'edge': edge,
                'trade': trade,
                'risk': risk,
                'sources': sources,
                'raw_analysis': content
            }
            
            # Cache result
            ai_insights_cache[cache_key] = {
                'data': result,
                'timestamp': datetime.now()
            }
            
            return jsonify(result)
        else:
            return jsonify({
                'ticker': ticker,
                'edge': f'API Error: {response.status_code}',
                'trade': 'Unable to fetch',
                'risk': 'Check API configuration',
                'sources': []
            }), 200
            
    except Exception as e:
        print(f"AI Insights error: {e}")
        return jsonify({
            'ticker': ticker,
            'edge': 'Error fetching AI insights',
            'trade': str(e),
            'risk': 'API timeout or error',
            'sources': []
        }), 200

@app.route('/api/stock-news/<ticker>', methods=['GET'])
def get_stock_news(ticker):
    if not FINNHUB_KEY:
        return jsonify({'error': 'Finnhub not configured'}), 500
    try:
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        url = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            articles = response.json()
            return jsonify({'ticker': ticker, 'articles': articles[:10], 'count': len(articles)})
    except Exception as e:
        print(f"Error: {e}")
    return jsonify({'ticker': ticker, 'articles': [], 'count': 0})

@app.route('/api/market-news/dashboard', methods=['GET'])
def get_market_news_dashboard():
    try:
        articles = fetch_market_news_scheduled()
        return jsonify({
            'articles': articles[:5],
            'last_updated': news_cache['last_updated'].isoformat() if news_cache['last_updated'] else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def fetch_market_news_scheduled():
    if news_cache['market_news'] and not should_update_news():
        return news_cache['market_news']
    if not FINNHUB_KEY:
        return []
    try:
        url = f'https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            articles = response.json()
            news_cache['market_news'] = articles
            news_cache['last_updated'] = datetime.now()
            return articles
    except:
        if news_cache['market_news']:
            return news_cache['market_news']
    return []

@app.route('/api/earnings-calendar', methods=['GET'])
def get_earnings_calendar():
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
            return jsonify({'earnings': earnings, 'count': len(earnings)})
    except Exception as e:
        print(f"Error: {e}")
    return jsonify({'earnings': [], 'count': 0})

@app.route('/api/insider-transactions/<ticker>', methods=['GET'])
def get_insider_transactions(ticker):
    if not FINNHUB_KEY:
        return jsonify({'ticker': ticker, 'transactions': [], 'insider_sentiment': 'NEUTRAL', 'buy_count': 0, 'sell_count': 0}), 200
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
    except:
        pass
    return jsonify({'ticker': ticker, 'transactions': [], 'insider_sentiment': 'NEUTRAL', 'buy_count': 0, 'sell_count': 0})

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def get_social_sentiment(ticker):
    if not FINNHUB_KEY:
        return jsonify({'ticker': ticker, 'daily': {'score': 0, 'mentions': 0}, 'weekly': {'score': 0, 'mentions': 0}, 'weekly_change': 0}), 200
    
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
            
            reddit_daily = reddit_data[-1] if reddit_data else {}
            twitter_daily = twitter_data[-1] if twitter_data else {}
            reddit_daily_score = reddit_daily.get('score', 0)
            twitter_daily_score = twitter_daily.get('score', 0)
            daily_avg = (reddit_daily_score + twitter_daily_score) / 2
            
            reddit_weekly = reddit_data[-7:] if len(reddit_data) >= 7 else reddit_data
            twitter_weekly = twitter_data[-7:] if len(twitter_data) >= 7 else twitter_data
            reddit_weekly_avg = sum(r.get('score', 0) for r in reddit_weekly) / len(reddit_weekly) if reddit_weekly else 0
            twitter_weekly_avg = sum(t.get('score', 0) for t in twitter_weekly) / len(twitter_weekly) if twitter_weekly else 0
            weekly_avg = (reddit_weekly_avg + twitter_weekly_avg) / 2
            
            weekly_change = round(((daily_avg - weekly_avg) / weekly_avg * 100) if weekly_avg != 0 else 0, 2)
            
            result = {
                'ticker': ticker,
                'daily': {'score': round(daily_avg, 2), 'mentions': reddit_daily.get('mention', 0) + twitter_daily.get('mention', 0), 'sentiment': 'BULLISH' if daily_avg > 0.3 else 'BEARISH' if daily_avg < -0.3 else 'NEUTRAL'},
                'weekly': {'score': round(weekly_avg, 2), 'mentions': sum(r.get('mention', 0) for r in reddit_weekly) + sum(t.get('mention', 0) for t in twitter_weekly), 'sentiment': 'BULLISH' if weekly_avg > 0.3 else 'BEARISH' if weekly_avg < -0.3 else 'NEUTRAL'},
                'weekly_change': weekly_change,
                'monthly_change': round(weekly_change * 1.3, 2),
                'overall_sentiment': 'BULLISH' if daily_avg > 0.3 else 'BEARISH' if daily_avg < -0.3 else 'NEUTRAL'
            }
            
            sentiment_cache[cache_key] = {'data': result, 'timestamp': datetime.now()}
            return jsonify(result)
    except:
        pass
    return jsonify({'ticker': ticker, 'daily': {'score': 0, 'mentions': 0}, 'weekly': {'score': 0, 'mentions': 0}, 'weekly_change': 0})

@app.route('/api/options-opportunities/<ticker>', methods=['GET'])
def get_options_opportunities(ticker):
    try:
        price_data = get_stock_price_waterfall(ticker)
        current_price = price_data['price']
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
        return jsonify({'error': str(e)}), 500

@app.route('/api/fred-data', methods=['GET'])
def get_fred_data():
    if not FRED_KEY:
        return jsonify({'data': {}}), 200
    try:
        series_ids = {'GDP': 'GDP', 'UNRATE': 'UNRATE', 'CPIAUCSL': 'CPIAUCSL', 'DFF': 'DFF', 'DGS10': 'DGS10'}
        results = {}
        for name, series_id in series_ids.items():
            url = f'https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_KEY}&file_type=json&limit=1&sort_order=desc'
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                observations = data.get('observations', [])
                if observations and len(observations) > 0:
                    results[name] = {'value': observations[0].get('value'), 'date': observations[0].get('date')}
        return jsonify({'data': results})
    except:
        return jsonify({'data': {}}), 200

@app.route('/health', methods=['GET'])
def health_check():
    cache_age = 0
    if recommendations_cache['timestamp']:
        cache_age = (datetime.now() - recommendations_cache['timestamp']).total_seconds()
    return jsonify({'status': 'healthy', 'cache_age_seconds': cache_age}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
