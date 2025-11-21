from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# API Keys from environment variables
ALPHAVANTAGE_KEY = os.getenv('ALPHAVANTAGE_KEY', '')
FINNHUB_KEY = os.getenv('FINNHUB_KEY', '')
POLYGON_KEY = os.getenv('Massive', '')  # Your Massive/Polygon key
FRED_KEY = os.getenv('FRED', '')

@app.route('/')
def home():
    return jsonify({
        "status": "Elite Trading API",
        "version": "2.0",
        "endpoints": ["/quote", "/polygon", "/fred", "/health"],
        "data_sources": {
            "primary": "Polygon (Massive)",
            "backup": "Alpha Vantage",
            "macro": "FRED"
        }
    })

@app.route('/api')
def api_info():
    return jsonify({
        "available_endpoints": {
            "/api/quote?ticker=SYMBOL": "Get stock quote (Polygon primary, Alpha Vantage backup)",
            "/api/polygon?ticker=SYMBOL": "Get Polygon data directly",
            "/api/fred?series=SERIES_ID": "Get FRED economic data"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "Elite Trading API"})

# PRIMARY ENDPOINT - Uses Polygon (Massive)
@app.route('/api/quote')
def get_quote():
    ticker = request.args.get('ticker', '').upper()
    if not ticker:
        return jsonify({"error": "Ticker required"}), 400
    
    # Try Polygon first (better rate limits)
    if POLYGON_KEY:
        try:
            # Polygon Previous Close endpoint
            url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?adjusted=true&apiKey={POLYGON_KEY}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'OK' and data.get('results'):
                    result = data['results'][0]
                    
                    # Convert Polygon format to Global Quote format (for compatibility)
                    return jsonify({
                        "Global Quote": {
                            "01. symbol": ticker,
                            "02. open": str(result['o']),
                            "03. high": str(result['h']),
                            "04. low": str(result['l']),
                            "05. price": str(result['c']),
                            "06. volume": str(result['v']),
                            "07. latest trading day": "latest",
                            "08. previous close": str(result['c']),
                            "09. change": "0",
                            "10. change percent": "0%"
                        },
                        "source": "Polygon"
                    })
        except Exception as e:
            print(f"Polygon error for {ticker}: {e}")
    
    # Fallback to Alpha Vantage
    if ALPHAVANTAGE_KEY:
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={ALPHAVANTAGE_KEY}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'Global Quote' in data and data['Global Quote']:
                    data['source'] = 'Alpha Vantage'
                    return jsonify(data)
        except Exception as e:
            print(f"Alpha Vantage error for {ticker}: {e}")
    
    return jsonify({"error": "Unable to fetch data"}), 500

# Direct Polygon endpoint
@app.route('/api/polygon')
def get_polygon_data():
    ticker = request.args.get('ticker', '').upper()
    if not ticker or not POLYGON_KEY:
        return jsonify({"error": "Ticker required and Polygon key missing"}), 400
    
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev?adjusted=true&apiKey={POLYGON_KEY}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"Polygon API error: {response.status_code}"}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# FRED economic data endpoint
@app.route('/api/fred')
def get_fred_data():
    series = request.args.get('series', 'DFF')  # Default: Federal Funds Rate
    if not FRED_KEY:
        return jsonify({"error": "FRED key not configured"}), 400
    
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series}&api_key={FRED_KEY}&file_type=json&limit=10&sort_order=desc"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"FRED API error: {response.status_code}"}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)
