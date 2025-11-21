from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

# Get API keys from environment variables (secure!)
ALPHA_VANTAGE_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY', 'demo')
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')

@app.route('/')
def home():
    return jsonify({
        'status': 'Elite Trading API Active',
        'version': '2.0',
        'endpoints': ['/api/quote', '/api/analytics', '/api/config']
    })

@app.route('/api/config')
def get_config():
    """Return API configuration (without exposing keys)"""
    return jsonify({
        'perplexity_enabled': bool(PERPLEXITY_KEY),
        'alpha_vantage_enabled': bool(ALPHA_VANTAGE_KEY)
    })

@app.route('/api/perplexity', methods=['POST'])
def perplexity_proxy():
    """Secure proxy for Perplexity API calls"""
    if not PERPLEXITY_KEY:
        return jsonify({'error': 'Perplexity API key not configured'}), 400
    
    try:
        data = request.json
        
        # Call Perplexity API server-side (key never exposed to client)
        response = requests.post(
            'https://api.perplexity.ai/chat/completions',
            headers={
                'Authorization': f'Bearer {PERPLEXITY_KEY}',
                'Content-Type': 'application/json'
            },
            json=data,
            timeout=30
        )
        
        return jsonify(response.json())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/quote')
def get_quote():
    """Get stock quote from Alpha Vantage"""
    ticker = request.args.get('ticker', 'IBM')
    
    try:
        url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHA_VANTAGE_KEY}'
        response = requests.get(url, timeout=10)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics')
def get_analytics():
    """Get stock analytics"""
    ticker = request.args.get('ticker', 'IBM')
    
    # Your proprietary analytics logic here
    return jsonify({
        'ticker': ticker,
        'analytics': {
            'mean_reversion': -1.5,
            'inst_33': 45,
            'regime': 60.5
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
