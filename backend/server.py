from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

# Load API keys from environment
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '')
ALPHA_VANTAGE_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY', 'demo')

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'Elite Trading API Active',
        'version': '2.0',
        'ai_provider': 'Perplexity' if PERPLEXITY_KEY else 'Gemini' if GEMINI_KEY else 'None',
        'endpoints': ['/api/config', '/api/ai-analyze', '/api/quote']
    })

@app.route('/api/config')
def get_config():
    """Check API configuration"""
    return jsonify({
        'perplexity_enabled': bool(PERPLEXITY_KEY),
        'gemini_enabled': bool(GEMINI_KEY),
        'ai_provider': 'Perplexity' if PERPLEXITY_KEY else 'Gemini' if GEMINI_KEY else 'None',
        'alpha_vantage_enabled': bool(ALPHA_VANTAGE_KEY)
    })

@app.route('/api/ai-analyze', methods=['POST'])
def ai_analyze():
    """
    Universal AI endpoint
    Tries Perplexity first (paid), falls back to FREE Gemini
    """
    try:
        data = request.json
        
        # Try Perplexity first
        if PERPLEXITY_KEY:
            try:
                response = requests.post(
                    'https://api.perplexity.ai/chat/completions',
                    headers={
                        'Authorization': f'Bearer {PERPLEXITY_KEY}',
                        'Content-Type': 'application/json'
                    },
                    json=data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return jsonify(response.json())
            except Exception as e:
                print(f"Perplexity error: {str(e)}")
                # Fall through to Gemini
        
        # Fall back to FREE Gemini
        if GEMINI_KEY:
            try:
                # Extract user message
                user_msg = data['messages'][-1]['content'] if data.get('messages') else 'Hello'
                
                # Call Gemini API
                response = requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}',
                    headers={'Content-Type': 'application/json'},
                    json={
                        'contents': [{
                            'parts': [{'text': user_msg}]
                        }],
                        'generationConfig': {
                            'temperature': 0.3,
                            'maxOutputTokens': 1000
                        }
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['candidates'][0]['content']['parts'][0]['text']
                    
                    # Convert to OpenAI format for compatibility
                    return jsonify({
                        'choices': [{
                            'message': {
                                'content': content
                            },
                            'finish_reason': 'stop'
                        }],
                        'model': 'gemini-pro',
                        'provider': 'Gemini (Free)'
                    })
                else:
                    return jsonify({'error': f'Gemini error: {response.status_code}'}), response.status_code
            except Exception as e:
                return jsonify({'error': f'Gemini error: {str(e)}'}), 500
        
        return jsonify({'error': 'No AI provider configured. Add GEMINI_API_KEY or PERPLEXITY_API_KEY to environment'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/perplexity', methods=['POST'])
def perplexity_proxy():
    """Legacy endpoint - redirects to universal AI endpoint"""
    return ai_analyze()

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
    
    return jsonify({
        'ticker': ticker,
        'analytics': {
            'mean_reversion': -1.5,
            'inst_33': 45,
            'regime': 60.5,
            'volatility': 55.0
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
