from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import traceback
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
CORS(app)

# ======================== API KEYS ========================
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')
FRED_KEY = os.environ.get('FRED_API_KEY', '')
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')

# ======================== ALL 50 STOCKS (FULL LIST) ========================
TOP_50_STOCKS = [
    {'symbol': 'KO', 'inst33': 95, 'signal': 'STRONG_BUY', 'key_metric': 'Beverage leader'},
    {'symbol': 'AZN', 'inst33': 95, 'signal': 'STRONG_BUY', 'key_metric': 'Biotech - inst backing'},
    {'symbol': 'MRK', 'inst33': 90, 'signal': 'STRONG_BUY', 'key_metric': 'Pharma momentum'},
    {'symbol': 'A', 'inst33': 80, 'signal': 'BUY', 'key_metric': 'Agilent emerging'},
    {'symbol': 'GOOGL', 'inst33': 80, 'signal': 'BUY', 'key_metric': 'Tech AI leader'},
    {'symbol': 'GOOG', 'inst33': 80, 'signal': 'BUY', 'key_metric': 'Tech uptrend'},
    {'symbol': 'JNJ', 'inst33': 75, 'signal': 'SELL_CALL', 'key_metric': 'Healthcare premium'},
    {'symbol': 'RY', 'inst33': 70, 'signal': 'SELL_CALL', 'key_metric': 'Financial low IV'},
    {'symbol': 'WMT', 'inst33': 70, 'signal': 'SELL_CALL', 'key_metric': 'Retail defensive'},
    {'symbol': 'LLY', 'inst33': 65, 'signal': 'HOLD', 'key_metric': 'Biotech GLP-1'},
    {'symbol': 'ASML', 'inst33': 65, 'signal': 'HOLD', 'key_metric': 'Chip equipment'},
    {'symbol': 'AAPL', 'inst33': 60, 'signal': 'HOLD', 'key_metric': 'Tech stable'},
    {'symbol': 'MSFT', 'inst33': 60, 'signal': 'BUY', 'key_metric': 'Cloud dominant'},
    {'symbol': 'NVDA', 'inst33': 45, 'signal': 'SELL', 'key_metric': 'Chip weakness'},
    {'symbol': 'AMZN', 'inst33': 45, 'signal': 'SELL', 'key_metric': 'E-commerce pull'},
    {'symbol': 'TSLA', 'inst33': 50, 'signal': 'HOLD', 'key_metric': 'EV volatility'},
    {'symbol': 'META', 'inst33': 55, 'signal': 'BUY', 'key_metric': 'AI upside'},
    {'symbol': 'NFLX', 'inst33': 58, 'signal': 'HOLD', 'key_metric': 'Streaming stable'},
    {'symbol': 'BABA', 'inst33': 48, 'signal': 'NEUTRAL', 'key_metric': 'China exposure'},
    {'symbol': 'JPM', 'inst33': 50, 'signal': 'HOLD', 'key_metric': 'Financial weak'},
    {'symbol': 'XOM', 'inst33': 50, 'signal': 'HOLD', 'key_metric': 'Energy dividend'},
    {'symbol': 'PG', 'inst33': 50, 'signal': 'SELL_CALL', 'key_metric': 'Staples'},
    {'symbol': 'V', 'inst33': 70, 'signal': 'BUY', 'key_metric': 'Payments strong'},
    {'symbol': 'MA', 'inst33': 70, 'signal': 'BUY', 'key_metric': 'Mastercard momentum'},
    {'symbol': 'CSCO', 'inst33': 55, 'signal': 'HOLD', 'key_metric': 'Networking dividend'},
    {'symbol': 'INTC', 'inst33': 52, 'signal': 'HOLD', 'key_metric': 'Chip turnaround'},
    {'symbol': 'AMD', 'inst33': 53, 'signal': 'SELL', 'key_metric': 'Chip competitor'},
    {'symbol': 'CRM', 'inst33': 58, 'signal': 'BUY', 'key_metric': 'Cloud CRM'},
    {'symbol': 'ADBE', 'inst33': 60, 'signal': 'HOLD', 'key_metric': 'Creative stable'},
    {'symbol': 'PYPL', 'inst33': 48, 'signal': 'NEUTRAL', 'key_metric': 'Fintech'},
    {'symbol': 'SQ', 'inst33': 52, 'signal': 'HOLD', 'key_metric': 'Square recovery'},
    {'symbol': 'DDOG', 'inst33': 62, 'signal': 'BUY', 'key_metric': 'Cloud monitor'},
    {'symbol': 'SNOW', 'inst33': 60, 'signal': 'BUY', 'key_metric': 'Data warehouse'},
    {'symbol': 'DBX', 'inst33': 54, 'signal': 'HOLD', 'key_metric': 'Cloud storage'},
    {'symbol': 'BOX', 'inst33': 48, 'signal': 'HOLD', 'key_metric': 'Content mgmt'},
    {'symbol': 'OKTA', 'inst33': 56, 'signal': 'HOLD', 'key_metric': 'Identity secure'},
    {'symbol': 'SPLK', 'inst33': 55, 'signal': 'HOLD', 'key_metric': 'Analytics platform'},
    {'symbol': 'COIN', 'inst33': 45, 'signal': 'SELL', 'key_metric': 'Crypto exposure'},
    {'symbol': 'MSTR', 'inst33': 58, 'signal': 'SELL', 'key_metric': 'Bitcoin proxy'},
    {'symbol': 'RIOT', 'inst33': 50, 'signal': 'SELL', 'key_metric': 'Mining weak'},
    {'symbol': 'HUT', 'inst33': 48, 'signal': 'SELL', 'key_metric': 'Miner volatile'},
    {'symbol': 'CLSK', 'inst33': 52, 'signal': 'HOLD', 'key_metric': 'Mining consolidate'},
    {'symbol': 'DELL', 'inst33': 48, 'signal': 'HOLD', 'key_metric': 'PC mature'},
    {'symbol': 'HPQ', 'inst33': 45, 'signal': 'HOLD', 'key_metric': 'Hardware'},
    {'symbol': 'IBM', 'inst33': 52, 'signal': 'HOLD', 'key_metric': 'IT services'},
    {'symbol': 'CISCO', 'inst33': 55, 'signal': 'HOLD', 'key_metric': 'Network leader'},
    {'symbol': 'NVDA', 'inst33': 45, 'signal': 'SELL', 'key_metric': 'GPU weakness'},
    {'symbol': 'TSM', 'inst33': 50, 'signal': 'HOLD', 'key_metric': 'Foundry Taiwan'},
    {'symbol': 'QCOM', 'inst33': 52, 'signal': 'HOLD', 'key_metric': 'Chip design'},
    {'symbol': 'AVGO', 'inst33': 53, 'signal': 'HOLD', 'key_metric': 'Broadcom'},
    {'symbol': 'MCHP', 'inst33': 48, 'signal': 'HOLD', 'key_metric': 'Micro-controller'},
]

TICKERS = [s['symbol'] for s in TOP_50_STOCKS]

# ======================== GLOBAL CACHES ========================
price_cache = {}
earnings_cache = {'data': [], 'timestamp': None}
sentiment_cache = {}
macro_cache = {'data': {}, 'timestamp': None}
ai_cache = {}

# ======================== 1. EARNINGS CALENDAR ========================
def fetch_earnings_live():
    """Fetch earnings from Yahoo + Finnhub"""
    earnings = []
    seen = set()
    
    for ticker in TICKERS[:25]:
        try:
            url = f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}'
            resp = requests.get(url, params={'modules': 'calendarEvents'}, timeout=5, 
                              headers={'User-Agent': 'Mozilla/5.0'})
            
            if resp.status_code == 200:
                data = resp.json().get('quoteSummary', {}).get('result', [])
                if data:
                    cal = data[0].get('calendarEvents', {})
                    ear_list = cal.get('earnings', {}).get('earningsDate', [])
                    if ear_list:
                        ts = ear_list[0].get('raw')
                        if ts:
                            date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                            earnings.append({
                                'symbol': ticker,
                                'date': date_str,
                                'source': 'Yahoo'
                            })
                            seen.add(ticker)
            time.sleep(0.15)
        except:
            pass
    
    if FINNHUB_KEY and len(earnings) < 40:
        try:
            from_date = datetime.now().strftime('%Y-%m-%d')
            to_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            url = f'https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={FINNHUB_KEY}'
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                for item in resp.json().get('earningsCalendar', []):
                    sym = item.get('symbol')
                    if sym in TICKERS and sym not in seen:
                        earnings.append({
                            'symbol': sym,
                            'date': item.get('date'),
                            'source': 'Finnhub'
                        })
                        seen.add(sym)
        except:
            pass
    
    earnings.sort(key=lambda x: x['date'])
    today = datetime.now().strftime('%Y-%m-%d')
    earnings = [e for e in earnings if e['date'] >= today]
    
    print(f"✅ Earnings: {len(earnings)} upcoming")
    return earnings[:50]

# ======================== 2. STOCK PRICES ========================
def get_price(ticker):
    """Get real-time price"""
    if ticker in price_cache:
        cached = price_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < 300:
            return cached['data']
    
    result = {'ticker': ticker, 'price': 150.00, 'change': 0}
    
    if FINNHUB_KEY:
        try:
            url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                price = data.get('c', 150)
                prev = data.get('pc', price)
                result = {
                    'ticker': ticker,
                    'price': round(price, 2),
                    'change': round(price - prev, 2),
                    'change_pct': round((price - prev) / prev * 100, 2) if prev else 0
                }
        except:
            pass
    
    price_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 3. SOCIAL SENTIMENT (FIXED) ========================
def get_sentiment(ticker):
    """Real sentiment with WoW/MoM"""
    if ticker in sentiment_cache:
        cached = sentiment_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < 43200:
            return cached['data']
    
    result = {
        'ticker': ticker,
        'daily': {'sentiment': 'NEUTRAL', 'mentions': 0, 'score': 0.00},
        'weekly': {'sentiment': 'NEUTRAL', 'mentions': 0, 'score': 0.00},
        'changes': {'wow_percent': 0.00, 'mom_percent': 0.00}
    }
    
    if not FINNHUB_KEY:
        return result
    
    try:
        url = f'https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&token={FINNHUB_KEY}'
        resp = requests.get(url, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            reddit = data.get('reddit', [])
            
            if reddit and len(reddit) > 0:
                daily = reddit[0]
                daily_score = daily.get('score', 0)
                daily_mentions = daily.get('mention', 0)
                daily_sentiment = 'BULLISH' if daily_score > 0.5 else ('BEARISH' if daily_score < -0.5 else 'NEUTRAL')
                
                weekly_data = reddit[:7]
                weekly_scores = [r.get('score', 0) for r in weekly_data]
                weekly_avg = sum(weekly_scores) / len(weekly_scores) if weekly_scores else 0
                weekly_mentions = sum(r.get('mention', 0) for r in weekly_data)
                weekly_sentiment = 'BULLISH' if weekly_avg > 0.5 else ('BEARISH' if weekly_avg < -0.5 else 'NEUTRAL')
                
                wow_change = 0.0
                mom_change = 0.0
                
                if len(reddit) >= 7 and reddit[6].get('score', 0) != 0:
                    prev_week = reddit[6].get('score', 0)
                    wow_change = ((daily_score - prev_week) / abs(prev_week)) * 100
                
                if len(reddit) >= 30 and reddit[29].get('score', 0) != 0:
                    prev_month = reddit[29].get('score', 0)
                    mom_change = ((daily_score - prev_month) / abs(prev_month)) * 100
                
                result = {
                    'ticker': ticker,
                    'daily': {'sentiment': daily_sentiment, 'mentions': daily_mentions, 'score': round(daily_score, 2)},
                    'weekly': {'sentiment': weekly_sentiment, 'mentions': weekly_mentions, 'score': round(weekly_avg, 2)},
                    'changes': {'wow_percent': round(wow_change, 2), 'mom_percent': round(mom_change, 2)}
                }
    except:
        pass
    
    sentiment_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 4. AI ANALYSIS (FIXED) ========================
def get_ai_analysis(ticker):
    """Perplexity Sonar analysis"""
    if ticker in ai_cache:
        cached = ai_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < 3600:
            return cached['data']
    
    result = {'ticker': ticker, 'edge': 'Unable to analyze', 'trade': 'N/A', 'risk': 'N/A'}
    
    if not PERPLEXITY_KEY:
        return result
    
    try:
        stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
        price = get_price(ticker)
        
        prompt = f"""Analyze {ticker} for day trading.
Price: ${price['price']}
Signal: {stock['signal'] if stock else 'NEUTRAL'}

Format EXACTLY as:
EDGE: [one line - bullish/bearish setup]
TRADE: [one line - entry/stop/target]
RISK: [one line - low/medium/high]"""
        
        url = 'https://api.perplexity.ai/chat/completions'
        headers = {'Authorization': f'Bearer {PERPLEXITY_KEY}', 'Content-Type': 'application/json'}
        payload = {
            'model': 'sonar',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.6,
            'max_tokens': 200
        }
        
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            try:
                content = resp.json()['choices'][0]['message']['content']
                lines = [l.strip() for l in content.split('\n') if l.strip() and ':' in l]
                
                result = {
                    'ticker': ticker,
                    'edge': lines[0][:100] if len(lines) > 0 else 'Neutral',
                    'trade': lines[1][:100] if len(lines) > 1 else 'Monitor',
                    'risk': lines[2][:100] if len(lines) > 2 else 'Standard'
                }
            except:
                result = {'ticker': ticker, 'edge': 'Parse error', 'trade': 'N/A', 'risk': 'N/A'}
    except Exception as e:
        print(f"AI error {ticker}: {e}")
    
    ai_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 5. OPTIONS ANALYSIS ========================
def get_options_analysis(ticker):
    """Options strategies with Greeks"""
    price = get_price(ticker)['price']
    
    return {
        'ticker': ticker,
        'strategies': [
            {
                'name': 'Iron Condor',
                'setup': f'Sell ${round(price*1.05, 2)} Call / Buy ${round(price*1.10, 2)} Call | Sell ${round(price*0.95, 2)} Put / Buy ${round(price*0.90, 2)} Put',
                'max_profit': round(price * 0.02, 2),
                'max_loss': round(price * 0.03, 2),
                'probability': '65%',
                'greeks': {'delta': '~0', 'gamma': 'Low', 'theta': '+High', 'vega': '-High', 'why': 'Collects premium, theta decay favors seller'}
            },
            {
                'name': 'Call Spread (Bullish)',
                'setup': f'Buy ${round(price, 2)} Call / Sell ${round(price*1.05, 2)} Call',
                'max_profit': round(price * 0.05, 2),
                'max_loss': round(price * 0.02, 2),
                'probability': '55%',
                'greeks': {'delta': '+0.60', 'gamma': 'Positive', 'theta': 'Neutral', 'vega': 'Low', 'why': 'Positive gamma = gains accelerate on rallies'}
            },
            {
                'name': 'Put Spread (Bearish)',
                'setup': f'Buy ${round(price, 2)} Put / Sell ${round(price*0.95, 2)} Put',
                'max_profit': round(price * 0.05, 2),
                'max_loss': round(price * 0.02, 2),
                'probability': '55%',
                'greeks': {'delta': '-0.60', 'gamma': 'Positive', 'theta': 'Neutral', 'vega': 'Low', 'why': 'Positive gamma = gains accelerate on drops'}
            },
            {
                'name': 'Call Spread (Bearish)',
                'setup': f'Sell ${round(price*1.02, 2)} Call / Buy ${round(price*1.08, 2)} Call',
                'max_profit': round(price * 0.015, 2),
                'max_loss': round(price * 0.035, 2),
                'probability': '60%',
                'greeks': {'delta': '-0.50', 'gamma': 'Negative', 'theta': '+High', 'vega': '-High', 'why': 'Credit spread, theta and vega crush collect premium'}
            },
            {
                'name': 'Put Spread (Bullish)',
                'setup': f'Sell ${round(price*0.98, 2)} Put / Buy ${round(price*0.92, 2)} Put',
                'max_profit': round(price * 0.015, 2),
                'max_loss': round(price * 0.035, 2),
                'probability': '60%',
                'greeks': {'delta': '+0.50', 'gamma': 'Negative', 'theta': '+High', 'vega': '-High', 'why': 'Credit spread, daily premium collection'}
            },
            {
                'name': 'Butterfly Spread',
                'setup': f'Buy ${round(price*0.98, 2)} Call / Sell 2x ${round(price, 2)} Call / Buy ${round(price*1.02, 2)} Call',
                'max_profit': round(price * 0.04, 2),
                'max_loss': round(price * 0.01, 2),
                'probability': '50%',
                'greeks': {'delta': '~0', 'gamma': 'Peaky', 'theta': '+Moderate', 'vega': 'Low', 'why': 'Mean reversion play, low cost entry'}
            }
        ]
    }

# ======================== 6. MACRO INDICATORS ========================
def get_macro():
    """FRED economic data"""
    if macro_cache['data'] and macro_cache['timestamp']:
        age = (datetime.now() - macro_cache['timestamp']).total_seconds()
        if age < 604800:
            return macro_cache['data']
    
    indicators = {}
    
    if FRED_KEY:
        series = {'UNRATE': 'Unemployment', 'CPIAUCSL': 'Inflation', 'DFF': 'Fed Rate', 'T10Y2Y': 'Yield Curve'}
        
        for sid, name in series.items():
            try:
                url = 'https://api.stlouisfed.org/fred/series/observations'
                resp = requests.get(url, params={'series_id': sid, 'api_key': FRED_KEY, 'file_type': 'json', 'limit': 1}, timeout=5)
                
                if resp.status_code == 200:
                    obs = resp.json().get('observations', [])
                    if obs and obs[0].get('value') != '.':
                        indicators[sid] = {'name': name, 'value': float(obs[0]['value'])}
            except:
                pass
    
    macro_cache['data'] = indicators
    macro_cache['timestamp'] = datetime.now()
    return indicators

# ======================== API ENDPOINTS ========================

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'OK', 'stocks': len(TICKERS)})

@app.route('/api/recommendations', methods=['GET'])
def recommendations():
    """Top 50 stocks"""
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(get_price, s['symbol']): s for s in TOP_50_STOCKS}
        for future in as_completed(futures):
            stock = futures[future]
            try:
                price = future.result()
                results.append({
                    'Symbol': stock['symbol'],
                    'Price': price['price'],
                    'Change': price.get('change_pct', 0),
                    'Signal': stock['signal'],
                    'Inst33': stock['inst33'],
                    'KeyMetric': stock['key_metric']
                })
            except:
                pass
    
    return jsonify(sorted(results, key=lambda x: x['Inst33'], reverse=True))

@app.route('/api/earnings-calendar', methods=['GET'])
def earnings():
    return jsonify(earnings_cache.get('data', UPCOMING_EARNINGS))

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def sentiment(ticker):
    return jsonify(get_sentiment(ticker.upper()))

@app.route('/api/ai-insights/<ticker>', methods=['GET'])
def ai_insights(ticker):
    return jsonify(get_ai_analysis(ticker.upper()))

@app.route('/api/options-opportunities/<ticker>', methods=['GET'])
def options_opportunities(ticker):
    return jsonify(get_options_analysis(ticker.upper()))

@app.route('/api/macro-indicators', methods=['GET'])
def macro_indicators():
    return jsonify(get_macro())

@app.route('/api/stock-detail/<ticker>', methods=['GET'])
def stock_detail(ticker):
    ticker = ticker.upper()
    return jsonify({
        'price': get_price(ticker),
        'sentiment': get_sentiment(ticker),
        'ai': get_ai_analysis(ticker),
        'options': get_options_analysis(ticker)
    })

# ======================== SCHEDULER ========================
def refresh_earnings():
    global UPCOMING_EARNINGS, earnings_cache
    UPCOMING_EARNINGS = fetch_earnings_live()
    earnings_cache['data'] = UPCOMING_EARNINGS
    earnings_cache['timestamp'] = datetime.now()

scheduler = BackgroundScheduler()
scheduler.add_job(func=refresh_earnings, trigger="cron", day=1, hour=9)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ======================== INITIALIZATION ========================
print(f"\n{'='*60}")
print(f"🚀 ELITE STOCK TRACKER - STARTUP")
print(f"{'='*60}")
print(f"✅ Stocks loaded: {len(TICKERS)}")
print(f"✅ Finnhub: {'YES' if FINNHUB_KEY else 'NO'}")
print(f"✅ FRED: {'YES' if FRED_KEY else 'NO'}")
print(f"✅ Perplexity: {'YES' if PERPLEXITY_KEY else 'NO'}")

UPCOMING_EARNINGS = fetch_earnings_live()
earnings_cache['data'] = UPCOMING_EARNINGS
earnings_cache['timestamp'] = datetime.now()

print(f"✅ Earnings: {len(UPCOMING_EARNINGS)} loaded")
print(f"{'='*60}\n")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
