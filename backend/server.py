from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# API Keys from environment variables
ALPHAVANTAGE_KEY = os.getenv('ALPHAVANTAGE_KEY', '5UKJXFOLH269EDBL')
FINNHUB_KEY = os.getenv('FINNHUB_KEY', 'd4fl7a9r01qsjdiqdks0d4fl7a9r01qsjdiqdksg')

@app.route('/api/quote', methods=['GET'])
def get_quote():
    ticker = request.args.get('ticker', 'CMCSA').upper()
    try:
        url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHAVANTAGE_KEY}'
        response = requests.get(url, timeout=5)
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    ticker = request.args.get('ticker', 'CMCSA').upper()
    try:
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&outputsize=full&apikey={ALPHAVANTAGE_KEY}'
        response = requests.get(url, timeout=5)
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/options', methods=['GET'])
def get_options():
    ticker = request.args.get('ticker', 'CMCSA').upper()
    try:
        url = f'https://finnhub.io/api/v1/stock/option-chain?symbol={ticker}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'OK', 'message': 'API running'})

@app.route('/', methods=['GET'])
def root():
    return jsonify({'app': 'Stock Newsletter Backend', 'version': '1.0.0'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
