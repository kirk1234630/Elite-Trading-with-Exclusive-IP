from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')

@app.route('/')
def home():
    return jsonify({'status': 'Elite Trading API Live'})

@app.route('/api/config')
def get_config():
    return jsonify({
        'perplexity_enabled': bool(PERPLEXITY_KEY),
        'finnhub_enabled': bool(FINNHUB_KEY)
    })

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
            json=data,
            timeout=90
        )
        
        if response.status_code != 200:
            return jsonify({'error': response.text}), response.status_code
        
        return jsonify(response.json())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
                    'source': 'Finnhub'
                })
        except:
            pass
    
    return jsonify({'error': 'Quote unavailable'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
