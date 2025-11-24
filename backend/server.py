from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import json
from datetime import datetime
import math

app = Flask(__name__)
CORS(app)

# ======================== API KEYS ========================
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')
ALPHAVANTAGE_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')

# ======================== DYNAMIC TICKER LOADING ========================
def load_tickers():
    """Load tickers dynamically"""
    tickers_env = os.environ.get('STOCK_TICKERS', '')
    if tickers_env:
        try:
            return json.loads(tickers_env)
        except:
            return [t.strip().upper() for t in tickers_env.split(',') if t.strip()]
    
    if os.path.exists('tickers.json'):
        try:
            with open('tickers.json', 'r') as f:
                return json.load(f)
        except:
            pass
    
    if os.path.exists('tickers.csv'):
        try:
            tickers = []
            with open('tickers.csv', 'r') as f:
                for line in f:
                    ticker = line.strip().upper()
                    if ticker and not ticker.startswith('#'):
                        tickers.append(ticker)
            if tickers:
                return tickers
        except:
            pass
    
    # DEFAULT: Your original 57 stocks (kept as fallback)
    return ['NVDA', 'TSLA', 'META', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'AMD', 'NFLX', 'PYPL',
            'SHOP', 'RBLX', 'DASH', 'ZOOM', 'SNOW', 'CRWD', 'NET', 'ABNB', 'UPST', 'COIN',
            'RIOT', 'MARA', 'CLSK', 'MSTR', 'SQ', 'PLTR', 'ASML', 'INTU', 'SNPS', 'MU',
            'QCOM', 'AVGO', 'LRCX', 'TSM', 'INTC', 'VMW', 'SEMR', 'SGRY', 'PSTG', 'DDOG',
            'OKTA', 'ZS', 'CHKP', 'PANW', 'SMAR', 'NOW', 'VEEV', 'TWLO', 'GTLB', 'ORCL',
            'IBM', 'HPE', 'DELL', 'CSCO', 'ADBE', 'CRM']

TICKERS = load_tickers()

# ======================== DATA GENERATION ========================
def generate_stock_data(ticker, seed=None):
    """Generate realistic stock data based on ticker hash"""
    if seed is None:
        seed = sum(ord(c) for c in ticker) % 100
    
    # Generate consistent data for each ticker
    base_price = 50 + seed * 5
    change = (seed % 10) - 5
    rsi = 30 + (seed % 40)
    regime = 50 + (seed % 40)
    inst_flow = 60 + (seed % 30)
    
    stories = ['The Setup', 'The Fade', 'The Creep', 'Breakout Play', 'Quality Hold', 'Consolidation', 'Mean Reversion', 'The Pump']
    story = stories[seed % len(stories)]
    
    # Determine signal
    if change < -3 and rsi < 35:
        signal = 'STRONG BUY'
    elif change > 5 and rsi > 65:
        signal = 'STRONG BUY'
    elif change > 2:
        signal = 'BUY'
    elif change < -2:
        signal = 'SELL'
    else:
        signal = 'HOLD'
    
    return {
        'Symbol': ticker,
        'Last': round(base_price, 2),
        'Change': round(change, 2),
        'RSIWilder': int(rsi),
        'RegimeDetection': int(regime),
        'Inst33': int(inst_flow),
        'Signal': signal,
        'Story': story
    }

# ======================== API ENDPOINTS ========================

@app.route('/api/stocks', methods=['GET'])
def get_all_stocks():
    """Return all stocks data for landing page"""
    stocks = []
    for ticker in TICKERS[:57]:  # Match original 57 stocks
        stocks.append(generate_stock_data(ticker))
    
    return jsonify(stocks), 200

@app.route('/api/stock/<ticker>/data', methods=['GET'])
def get_stock_data(ticker):
    """Return single stock data"""
    ticker = ticker.upper()
    stock = generate_stock_data(ticker)
    return jsonify(stock), 200

@app.route('/api/stock/<ticker>/greeks', methods=['GET'])
def get_greeks(ticker):
    """Return ATM Greeks"""
    ticker = ticker.upper()
    stock = generate_stock_data(ticker)
    
    # Consistent Greeks based on ticker
    seed = sum(ord(c) for c in ticker) % 100
    
    call_delta = round(0.3 + (seed % 50) / 100, 4)
    call_gamma = round(0.001 + (seed % 50) / 10000, 4)
    call_theta = round(0.2 + (seed % 30) / 100, 4)
    call_vega = round(0.02 + (seed % 30) / 1000, 4)
    
    return jsonify({
        'ticker': ticker,
        'call': {
            'delta': call_delta,
            'gamma': call_gamma,
            'theta': call_theta,
            'vega': call_vega
        },
        'put': {
            'delta': round(call_delta - 1, 4),
            'gamma': call_gamma,
            'theta': call_theta,
            'vega': call_vega
        }
    }), 200

@app.route('/api/stock/<ticker>/projection', methods=['GET'])
def get_projection(ticker):
    """Return 30-day price projection"""
    ticker = ticker.upper()
    stock = generate_stock_data(ticker)
    current = stock['Last']
    
    seed = sum(ord(c) for c in ticker) % 100
    volatility = 0.15 + (seed % 30) / 100
    
    # 1-sigma projections (68% probability)
    sigma_low = round(current * (1 - volatility), 2)
    sigma_high = round(current * (1 + volatility), 2)
    
    # 2-sigma projections (95% probability)
    two_sigma_low = round(current * (1 - volatility * 2), 2)
    two_sigma_high = round(current * (1 + volatility * 2), 2)
    
    return jsonify({
        'ticker': ticker,
        'current_price': current,
        'proj_1_low': sigma_low,
        'proj_1_high': sigma_high,
        'proj_2_low': two_sigma_low,
        'proj_2_high': two_sigma_high
    }), 200

@app.route('/api/newsletter', methods=['GET'])
def get_newsletter():
    """Return newsletter data with all sections"""
    
    stocks = [generate_stock_data(t) for t in TICKERS[:57]]
    
    # Value stocks (oversold, low RSI)
    value_stocks = [s for s in stocks if s['Change'] < -2]
    
    # Momentum stocks (strong change, high RSI)
    momentum_stocks = [s for s in stocks if s['Change'] > 2]
    
    # Top 3 picks
    top_3 = sorted(stocks, key=lambda x: (x['RSIWilder'] + x['RegimeDetection'] + x['Inst33']), reverse=True)[:3]
    
    # Market data
    today = datetime.now().strftime('%A, %B %d, %Y')
    
    return jsonify({
        'date': today,
        'value_stocks': value_stocks[:15],
        'momentum_stocks': momentum_stocks[:15],
        'top_3': top_3,
        'market_stats': {
            'sp500': 4785,
            'nasdaq': 15340,
            'vix': 15.2,
            'treasury_10y': 4.45
        },
        'macro': {
            'gdp_growth': '2.8%',
            'unemployment': '3.9%',
            'inflation': '3.2%',
            'fed_rate': '5.25-5.50%'
        }
    }), 200

@app.route('/api/ai-chat', methods=['POST'])
def ai_chat():
    """AI Chat endpoint matching original responses"""
    data = request.json
    message = data.get('message', '').lower()
    
    # Original AI responses mapped to keywords
    responses = {
        'nvda': 'NVDA at $178.88. RSI 70 = overbought short-term. Support at $175. Sell calls for premium.',
        'tsla': 'TSLA at $342.80. Mean reversion play. Support $325. Resistance $360. Scale 25%.',
        'meta': 'META at $512.15. Breakout play. RSI 66. Sell calls at $550. Target $580.',
        'buy': 'Top buys: AMD (+4.2%), META (+2.1%), AMZN (+1.2%). All showing institutional inflows.',
        'sell': 'Overbought: NVDA (RSI 70), AMD (RSI 68). Take profits. Consider puts.',
        'options': 'NVDA: Sell $180 calls for $2.50 premium. TSLA: Cash-secured $340 puts. Theta decay your friend.',
        'risk': 'Use 2% position sizing. Set stops 5-7% below entry. Take profits at T1. Never go all-in.',
        'portfolio': 'Current portfolio: 60% tech, 20% financials, 20% cash. Position sizing: 2% per trade. Max drawdown: 15%.',
        'greeks': 'Call Delta 0.53 = 53% probability in-the-money. Gamma peaks at-the-money. Theta accelerates near expiration.',
        'iv': 'IV Rank 57 = moderate volatility. IV Crush post-earnings. Calendar spreads profitable. Watch VIX 15.2.',
        'earnings': 'NVDA earnings Tue after close. Expect IV crush 20-30%. Iron Condors ideal setup.',
        'strategy': 'Long 1 share + Sell 1 call = Covered call income. Buy 1 put + Sell 1 put = Defined risk.',
        'economic': 'Fed Minutes Tue. Jobless Claims Thu. PCE Inflation Fri. Watch for rate cut signals.',
        'sector': 'Tech strong +2.1%. Financials neutral +0.3%. Energy weak -1.2%. Rotate to strength.',
        'vix': 'VIX 15.2 = low fear. Consider calendar spreads. Watch 20 for hedging needs. Spike 25 = crisis.',
        'default': 'Analyzing market setup... NVDA breakout candidate, AMD momentum building, TSLA mean reversion. Watch institutional flows.'
    }
    
    # Find matching response
    reply = responses['default']
    for key, response in responses.items():
        if key != 'default' and key in message:
            reply = response
            break
    
    return jsonify({
        'user': data.get('message'),
        'ai': reply,
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'tickers_loaded': len(TICKERS),
        'api_configured': {
            'finnhub': bool(FINNHUB_KEY),
            'alphavantage': bool(ALPHAVANTAGE_KEY)
        }
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
