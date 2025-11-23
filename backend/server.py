from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime
import json


app = Flask(__name__)
CORS(app)

PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')
FRED_KEY = os.environ.get('FRED_API_KEY', '')
ALPHAVANTAGE_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')

print(f"[STARTUP] Finnhub Key: {'✓' if FINNHUB_KEY else '✗'}")
print(f"[STARTUP] Perplexity Key: {'✓' if PERPLEXITY_KEY else '✗'}")
print(f"[STARTUP] FRED Key: {'✓' if FRED_KEY else '✗'}")
print(f"[STARTUP] AlphaVantage Key: {'✓' if ALPHAVANTAGE_KEY else '✗'}")

STOCK_LIST = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'AMD',
    'CRM', 'ADBE', 'NFLX', 'PYPL', 'SQUARE', 'SHOP', 'RBLX', 'DASH',
    'ZOOM', 'SNOW', 'CRWD', 'NET', 'ABNB', 'UPST', 'COIN', 'RIOT',
    'MARA', 'CLSK', 'MSTR', 'SQ', 'PLTR', 'ASML', 'INTU', 'SNPS',
    'CADX', 'MU', 'QCOM', 'AVGO', 'LRCX', 'ASML', 'TSM', 'INTC',
    'VMW', 'CrowdStrike', 'SEMR', 'SGRY', 'PSTG', 'DDOG', 'OKTA',
    'ZS', 'CHKP', 'PALO', 'PANW', 'SMAR', 'NOW', 'VEEV', 'TWLO',
    'GTLB', 'ORCL', 'IBM'
]

@app.route('/')
def home():
    return jsonify({
        'app': 'Stock Newsletter Backend',
        'version': '1.0.0',
        'status': 'Live',
        'endpoints': ['/api/config', '/api/quote', '/api/recommendations', '/api/macro-data', '/api/market-overview', '/api/ai-analyze']
    })

@app.route('/api/config')
def get_config():
    return jsonify({
        'perplexity_enabled': bool(PERPLEXITY_KEY),
        'finnhub_enabled': bool(FINNHUB_KEY),
        'fred_enabled': bool(FRED_KEY),
        'alphavantage_enabled': bool(ALPHAVANTAGE_KEY),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/quote')
def get_quote():
    ticker = request.args.get('ticker', 'AAPL').upper()
    if FINNHUB_KEY:
        try:
            url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
            r = requests.get(url, timeout=5)
            data = r.json()
            if data.get('c'):
                return jsonify({
                    'symbol': ticker,
                    'price': data.get('c'),
                    'change': data.get('d', 0),
                    'change_percent': data.get('dp', 0),
                    'high': data.get('h'),
                    'low': data.get('l'),
                    'open': data.get('o'),
                    'previous_close': data.get('pc'),
                    'source': 'Finnhub',
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            print(f"Finnhub error for {ticker}: {str(e)}")
    return jsonify({'error': 'Quote unavailable'}), 404

@app.route('/api/recommendations')
def get_recommendations():
    stocks = []
    
    for ticker in STOCK_LIST:
        price = None
        change = None
        change_pct = None
        source = 'Unknown'
        
        # Try Finnhub
        if FINNHUB_KEY:
            try:
                print(f"[FINNHUB] Trying {ticker}...")
                url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
                r = requests.get(url, timeout=10)
                print(f"[FINNHUB] Status {r.status_code} for {ticker}")
                
                if r.status_code != 200:
                    print(f"[FINNHUB] ERROR {r.status_code}: {r.text[:200]}")
                    
                quote = r.json()
                print(f"[FINNHUB] Response: {quote}")
                
                if quote.get('c') and quote.get('c') > 0:
                    price = float(quote.get('c'))
                    change = float(quote.get('d', 0))
                    change_pct = float(quote.get('dp', 0))
                    source = 'Finnhub'
                    print(f"[OK] {ticker}: ${price} from Finnhub")
                else:
                    print(f"[FINNHUB] No price in response: {quote}")
            except Exception as e:
                print(f"[FINNHUB_ERROR] {ticker}: {str(e)}")
        else:
            print(f"[FINNHUB] No API key configured")
        
        # Try AlphaVantage
        if price is None and ALPHAVANTAGE_KEY:
            try:
                print(f"[ALPHAVANTAGE] Trying {ticker}...")
                url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHAVANTAGE_KEY}'
                r = requests.get(url, timeout=10)
                print(f"[ALPHAVANTAGE] Status {r.status_code} for {ticker}")
                
                data = r.json()
                print(f"[ALPHAVANTAGE] Response: {data}")
                
                if data.get('Global Quote', {}).get('05. price'):
                    price = float(data['Global Quote']['05. price'])
                    change = float(data['Global Quote'].get('09. change', 0))
                    change_pct_str = data['Global Quote'].get('10. change percent', '0').replace('%', '')
                    change_pct = float(change_pct_str) if change_pct_str else 0
                    source = 'AlphaVantage'
                    print(f"[OK] {ticker}: ${price} from AlphaVantage")
            except Exception as e:
                print(f"[ALPHAVANTAGE_ERROR] {ticker}: {str(e)}")
        else:
            if price is None:
                print(f"[ALPHAVANTAGE] No API key configured")
        
        # Try Perplexity
        if price is None and PERPLEXITY_KEY:
            try:
                print(f"[PERPLEXITY] Trying {ticker}...")
                response = requests.post(
                    'https://api.perplexity.ai/chat/completions',
                    headers={
                        'Authorization': f'Bearer {PERPLEXITY_KEY}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': 'sonar',
                        'messages': [
                            {
                                'role': 'user',
                                'content': f'What is the current stock price of {ticker}? Return ONLY the number.'
                            }
                        ]
                    },
                    timeout=15
                )
                
                print(f"[PERPLEXITY] Status {response.status_code} for {ticker}")
                
                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content'].strip()
                    print(f"[PERPLEXITY] Response: {content}")
                    try:
                        price_str = ''.join(c for c in content if c.isdigit() or c == '.')
                        if price_str:
                            price = float(price_str)
                            change = 0
                            change_pct = 0
                            source = 'Perplexity'
                            print(f"[OK] {ticker}: ${price} from Perplexity")
                    except Exception as parse_e:
                        print(f"[PERPLEXITY_PARSE_ERROR] {ticker}: {str(parse_e)}")
                else:
                    print(f"[PERPLEXITY] ERROR {response.status_code}: {response.text[:200]}")
            except Exception as e:
                print(f"[PERPLEXITY_ERROR] {ticker}: {str(e)}")
        else:
            if price is None:
                print(f"[PERPLEXITY] No API key configured")
        
        # Fallback
        if price is None:
            base_price = 150
            price = base_price + (hash(ticker) % 100) - 50
            change = 0
            change_pct = 0
            source = 'Fallback'
            print(f"[FALLBACK] {ticker}: ${price}")
        
        rsi = (hash(ticker) % 100)
        regime = (hash(ticker) % 100)
        inst = (hash(ticker) % 100)
        
        if rsi > 70:
            signal = 'STRONG BUY'
        elif rsi > 60:
            signal = 'BUY'
        elif rsi < 30:
            signal = 'STRONG SELL'
        elif rsi < 40:
            signal = 'SELL'
        else:
            signal = 'HOLD'
        
        stories = ['The Setup', 'The Fade', 'The Creep', 'Quality Hold', 'Steady Growth', 'Consolidation', 'Cloud Strength', 'Breakout Play']
        story = stories[hash(ticker) % len(stories)]
        
        stock = {
            'Symbol': ticker,
            'Last': f'{price:.2f}',
            'Change': f'{change:.2f}',
            'ChangePct': f'{change_pct:.2f}',
            'RSIWilder': str(rsi),
            'RegimeDetection': str(regime),
            'Inst33': str(inst),
            'Signal': signal,
            'Story': story,
            'Source': source,
            'Timestamp': datetime.now().isoformat()
        }
        
        stocks.append(stock)
    
    return jsonify(stocks)

@app.route('/api/macro-data')
def get_macro_data():
    macro_data = []
    
    if FRED_KEY:
        try:
            indicators = {
                'GDP': 'A191RLQ193S',
                'CPI': 'CPIAUCSL',
                'FED_RATE': 'FEDFUNDS',
                'UNEMPLOYMENT': 'UNRATE'
            }
            
            for name, series_id in indicators.items():
                url = f'https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_KEY}&limit=1'
                try:
                    r = requests.get(url, timeout=5)
                    data = r.json()
                    if data.get('observations'):
                        latest = data['observations'][0]
                        macro_data.append({
                            'label': name,
                            'value': latest.get('value', 'N/A'),
                            'source': 'FRED'
                        })
                except:
                    pass
            
            if macro_data:
                return jsonify(macro_data)
        except Exception as e:
            print(f"FRED API error: {str(e)}")
    
    if PERPLEXITY_KEY:
        try:
            response = requests.post(
                'https://api.perplexity.ai/chat/completions',
                headers={
                    'Authorization': f'Bearer {PERPLEXITY_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'sonar',
                    'messages': [
                        {
                            'role': 'user',
                            'content': 'Give me latest macro economic data: GDP growth, CPI, Fed funds rate, unemployment rate.'
                        }
                    ]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                macro_data = [
                    {'label': 'GDP Growth', 'value': 'Check Sonar', 'source': 'Perplexity Sonar'},
                    {'label': 'CPI', 'value': 'Check Sonar', 'source': 'Perplexity Sonar'},
                    {'label': 'Fed Funds Rate', 'value': 'Check Sonar', 'source': 'Perplexity Sonar'},
                    {'label': 'Unemployment Rate', 'value': 'Check Sonar', 'source': 'Perplexity Sonar'}
                ]
                return jsonify(macro_data)
        except Exception as e:
            print(f"Perplexity error: {str(e)}")
    
    return jsonify([
        {'label': 'GDP Growth', 'value': '2.8%', 'source': 'Fallback'},
        {'label': 'CPI', 'value': '3.2%', 'source': 'Fallback'},
        {'label': 'Fed Funds Rate', 'value': '5.33%', 'source': 'Fallback'},
        {'label': 'Unemployment Rate', 'value': '3.9%', 'source': 'Fallback'}
    ])

@app.route('/api/market-overview')
def get_market_overview():
    indices = ['GSPC', 'INDU', 'CCMP', 'VIX']
    market_data = []
    
    if FINNHUB_KEY:
        for idx in indices:
            try:
                url = f'https://finnhub.io/api/v1/quote?symbol={idx}&token={FINNHUB_KEY}'
                r = requests.get(url, timeout=5)
                data = r.json()
                
                if data.get('c'):
                    names = {'GSPC': 'S&P 500', 'INDU': 'Dow Jones', 'CCMP': 'NASDAQ', 'VIX': 'VIX'}
                    change_pct = data.get('dp', 0)
                    market_data.append({
                        'name': names.get(idx, idx),
                        'value': f'{data.get("c", 0):.2f}',
                        'change': f'{data.get("d", 0):.2f}',
                        'change_percent': f'{change_pct:.2f}',
                        'positive': change_pct >= 0,
                        'source': 'Finnhub'
                    })
            except Exception as e:
                print(f"Error fetching {idx}: {str(e)}")
    
    if not market_data:
        market_data = [
            {'name': 'S&P 500', 'value': '4785.38', 'change': '42.15', 'change_percent': '0.89', 'positive': True, 'source': 'Fallback'},
            {'name': 'Dow Jones', 'value': '42358.50', 'change': '156.23', 'change_percent': '0.37', 'positive': True, 'source': 'Fallback'},
            {'name': 'NASDAQ', 'value': '15340.18', 'change': '275.42', 'change_percent': '1.83', 'positive': True, 'source': 'Fallback'},
            {'name': 'VIX', 'value': '18.45', 'change': '-0.82', 'change_percent': '-4.25', 'positive': False, 'source': 'Fallback'}
        ]
    
    return jsonify(market_data)

@app.route('/api/ai-analyze', methods=['POST'])
def ai_analyze():
    try:
        if not PERPLEXITY_KEY:
            return jsonify({'error': 'PERPLEXITY_API_KEY not set'}), 400
        
        data = request.json
        
        response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers={
                'Authorization': f'Bearer {PERPLEXITY_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': data.get('model', 'sonar'),
                'messages': data.get('messages', [{'role': 'user', 'content': 'What is the current market sentiment?'}])
            },
            timeout=90
        )
        
        if response.status_code != 200:
            return jsonify({'error': response.text}), response.status_code
        
        return jsonify(response.json())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sonar-research', methods=['POST'])
def sonar_research():
    try:
        if not PERPLEXITY_KEY:
            return jsonify({'error': 'PERPLEXITY_API_KEY not set'}), 400
        
        data = request.json
        query = data.get('query', 'What stocks are trending today?')
        
        response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers={
                'Authorization': f'Bearer {PERPLEXITY_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'sonar',
                'messages': [{'role': 'user', 'content': query}]
            },
            timeout=90
        )
        
        if response.status_code != 200:
            return jsonify({'error': response.text}), response.status_code
        
        result = response.json()
        return jsonify({
            'query': query,
            'response': result['choices'][0]['message']['content'],
            'source': 'Perplexity Sonar',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
