from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
import json

app = Flask(__name__)
CORS(app)

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

# Stock tickers list
TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'AMD', 'CRM', 'ADBE',
    'NFLX', 'PYPL', 'SHOP', 'RBLX', 'DASH', 'ZOOM', 'SNOW', 'CRWD', 'NET', 'ABNB',
    'UPST', 'COIN', 'RIOT', 'MARA', 'CLSK', 'MSTR', 'SQ', 'PLTR', 'ASML', 'INTU',
    'SNPS', 'MU', 'QCOM', 'AVGO', 'LRCX', 'TSM', 'INTC', 'VMW', 'CRWD', 'SEMR',
    'SGRY', 'PSTG', 'DDOG', 'OKTA', 'ZS', 'CHKP', 'PANW', 'SMAR', 'NOW', 'VEEV',
    'TWLO', 'GTLB', 'ORCL', 'IBM', 'HPE', 'DELL', 'CSCO'
]

def get_stock_price_massive(ticker):
    """Try Massive.com API first (100 calls/day free tier)"""
    if not MASSIVE_KEY:
        return None
    
    try:
        url = f'https://api.polygon.io/v2/last/trade/{ticker}?apiKey={MASSIVE_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'results' in data:
                return {
                    'price': data['results']['p'],
                    'source': 'Massive (Real-time)',
                    'timestamp': data['results']['t']
                }
    except Exception as e:
        print(f"[MASSIVE] Error for {ticker}: {e}")
    
    return None

def get_stock_price_finnhub(ticker):
    """Try Finnhub API (60 calls/min free tier)"""
    if not FINNHUB_KEY:
        return None
    
    try:
        url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'c' in data and data['c'] > 0:
                return {
                    'price': data['c'],
                    'source': 'Finnhub (Real-time)',
                    'change': data.get('dp', 0)
                }
    except Exception as e:
        print(f"[FINNHUB] Error for {ticker}: {e}")
    
    return None

def get_stock_price_alphavantage(ticker):
    """Try Alpha Vantage API (25 calls/day free tier)"""
    if not ALPHAVANTAGE_KEY:
        return None
    
    try:
        url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHAVANTAGE_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'Global Quote' in data:
                quote = data['Global Quote']
                if '05. price' in quote:
                    return {
                        'price': float(quote['05. price']),
                        'source': 'Alpha Vantage',
                        'change': float(quote.get('10. change percent', '0%').replace('%', ''))
                    }
    except Exception as e:
        print(f"[ALPHAVANTAGE] Error for {ticker}: {e}")
    
    return None

def get_stock_price_perplexity(ticker):
    """Fallback to Perplexity (slow but unlimited)"""
    if not PERPLEXITY_KEY:
        return None
    
    try:
        url = 'https://api.perplexity.ai/chat/completions'
        headers = {
            'Authorization': f'Bearer {PERPLEXITY_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': 'sonar',
            'messages': [{
                'role': 'user',
                'content': f'What is the current stock price of {ticker}? Reply with just the number.'
            }]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            price_text = data['choices'][0]['message']['content']
            # Extract number from response
            import re
            price_match = re.search(r'\d+\.?\d*', price_text)
            if price_match:
                return {
                    'price': float(price_match.group()),
                    'source': 'Perplexity (AI-parsed)',
                    'change': 0
                }
    except Exception as e:
        print(f"[PERPLEXITY] Error for {ticker}: {e}")
    
    return None

def get_stock_price_waterfall(ticker):
    """Try APIs in priority order: Massive → Finnhub → AlphaVantage → Perplexity"""
    
    # Priority 1: Massive (best data, 100/day limit)
    result = get_stock_price_massive(ticker)
    if result:
        return result
    
    # Priority 2: Finnhub (good data, 60/min unlimited daily)
    result = get_stock_price_finnhub(ticker)
    if result:
        return result
    
    # Priority 3: Alpha Vantage (backup, 25/day limit)
    result = get_stock_price_alphavantage(ticker)
    if result:
        return result
    
    # Priority 4: Perplexity (last resort, slow)
    result = get_stock_price_perplexity(ticker)
    if result:
        return result
    
    # Complete fallback
    return {
        'price': 100.0,
        'source': 'Fallback (No API available)',
        'change': 0
    }

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Get stock recommendations with real-time prices"""
    recommendations = []
    
    for ticker in TICKERS:
        price_data = get_stock_price_waterfall(ticker)
        
        recommendations.append({
            'Symbol': ticker,
            'Last': price_data['price'],
            'Change': price_data.get('change', 0),
            'Source': price_data['source'],
            'RSI': 50,  # Placeholder - integrate your ThinkScript logic
            'Signal': 'HOLD',  # Placeholder
            'Strategy': 'Momentum'  # Placeholder
        })
    
    return jsonify(recommendations)

@app.route('/api/stock-news/<ticker>', methods=['GET'])
def get_stock_news(ticker):
    """Get latest news for a specific stock using Finnhub"""
    if not FINNHUB_KEY:
        return jsonify({'error': 'Finnhub not configured'}), 500
    
    try:
        # Get last 7 days of news
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        
        url = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            news = response.json()
            
            # Format news articles
            formatted_news = []
            for article in news[:10]:  # Top 10 most recent
                formatted_news.append({
                    'headline': article.get('headline', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('source', ''),
                    'url': article.get('url', ''),
                    'datetime': article.get('datetime', 0),
                    'image': article.get('image', '')
                })
            
            return jsonify({
                'ticker': ticker,
                'news_count': len(formatted_news),
                'articles': formatted_news
            })
        else:
            return jsonify({'error': f'Finnhub returned {response.status_code}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/market-news', methods=['GET'])
def get_market_news():
    """Get general market news using Finnhub"""
    if not FINNHUB_KEY:
        return jsonify({'error': 'Finnhub not configured'}), 500
    
    try:
        url = f'https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            news = response.json()
            
            formatted_news = []
            for article in news[:20]:  # Top 20
                formatted_news.append({
                    'headline': article.get('headline', ''),
                    'summary': article.get('summary', ''),
                    'source': article.get('source', ''),
                    'url': article.get('url', ''),
                    'datetime': article.get('datetime', 0),
                    'image': article.get('image', '')
                })
            
            return jsonify({
                'news_count': len(formatted_news),
                'articles': formatted_news
            })
        else:
            return jsonify({'error': f'Finnhub returned {response.status_code}'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['GET'])
def get_config():
    """Check which APIs are configured"""
    return jsonify({
        'finnhub_enabled': bool(FINNHUB_KEY),
        'perplexity_enabled': bool(PERPLEXITY_KEY),
        'fred_enabled': bool(FRED_KEY),
        'alphavantage_enabled': bool(ALPHAVANTAGE_KEY),
        'massive_enabled': bool(MASSIVE_KEY),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'online',
        'endpoints': [
            '/api/recommendations',
            '/api/stock-news/<ticker>',
            '/api/market-news',
            '/api/config'
        ]
    })

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
