from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

# Load from environment
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')

@app.route('/api/config')
def get_config():
    """Check if AI is enabled"""
    return jsonify({
        'perplexity_enabled': bool(PERPLEXITY_KEY),
        'alpha_vantage_enabled': True
    })

@app.route('/api/perplexity', methods=['POST'])
def perplexity_proxy():
    """Secure AI proxy"""
    if not PERPLEXITY_KEY:
        return jsonify({'error': 'API key not configured'}), 400
    
    try:
        data = request.json
        
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
    """Get stock quote"""
    ticker = request.args.get('ticker', 'IBM')
    # Your existing quote logic
    return jsonify({'ticker': ticker})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
