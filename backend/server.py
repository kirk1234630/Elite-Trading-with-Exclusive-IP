# FIRST: Update your server.py on Render - MAKE SURE PERPLEXITY KEY IS SET!

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import time

app = Flask(__name__)
CORS(app)

# API Keys from Render environment
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')
POLYGON_KEY = os.environ.get('POLYGON_API_KEY', '')
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')

print(f"[STARTUP] Perplexity Key Present: {bool(PERPLEXITY_KEY)}")
print(f"[STARTUP] Polygon Key Present: {bool(POLYGON_KEY)}")
print(f"[STARTUP] Finnhub Key Present: {bool(FINNHUB_KEY)}")

@app.route('/')
def home():
    return jsonify({'status': 'Elite Trading API Live'})

@app.route('/api/config')
def get_config():
    return jsonify({
        'perplexity_enabled': bool(PERPLEXITY_KEY),
        'polygon_enabled': bool(POLYGON_KEY),
        'finnhub_enabled': bool(FINNHUB_KEY)
    })

@app.route('/api/ai-analyze', methods=['POST'])
def ai_analyze():
    """AI endpoint - SIMPLIFIED"""
    try:
        data = request.json
        
        if not PERPLEXITY_KEY:
            return jsonify({'error': 'PERPLEXITY_API_KEY not configured in Render'}), 400
        
        print(f"[AI] Sending to Perplexity...")
        
        response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers={
                'Authorization': f'Bearer {PERPLEXITY_KEY}',
                'Content-Type': 'application/json'
            },
            json=data,
            timeout=90
        )
        
        print(f"[AI] Response: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[AI] Error: {response.text}")
            return jsonify({'error': f'Perplexity returned {response.status_code}: {response.text}'}), response.status_code
        
        return jsonify(response.json())
        
    except Exception as e:
        print(f"[AI] Exception: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/quote')
def get_quote():
    """Get live quote"""
    ticker = request.args.get('ticker', 'AAPL').upper()
    
    # Try Finnhub first
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
                    'source': 'Finnhub'
                })
        except:
            pass
    
    # Fallback to Alpha Vantage
    try:
        url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey=demo'
        r = requests.get(url, timeout=10)
        data = r.json()
        quote = data.get('Global Quote', {})
        if quote.get('05. price'):
            return jsonify({
                'symbol': ticker,
                'price': float(quote.get('05. price')),
                'change': float(quote.get('09. change', 0) or 0),
                'change_percent': float(quote.get('10. change percent', '0').replace('%', '') or 0),
                'source': 'Alpha Vantage'
            })
    except:
        pass
    
    return jsonify({'error': 'Quote not available'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
