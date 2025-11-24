from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
CORS(app)

# ======================== API KEYS ========================
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')
ALPHAVANTAGE_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')
MASSIVE_KEY = os.environ.get('MASSIVE_API_KEY', '')
FRED_KEY = os.environ.get('FRED_API_KEY', '')
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')

# ======================== TOP 50 STOCKS ========================
TOP_50_STOCKS = [
    {'symbol': 'KO', 'inst33': 95, 'overall_score': 8, 'signal': 'STRONG_BUY', 'key_metric': 'Beverage leader'},
    {'symbol': 'AZN', 'inst33': 95, 'overall_score': 8, 'signal': 'STRONG_BUY', 'key_metric': 'Biotech backing'},
    {'symbol': 'MRK', 'inst33': 90, 'overall_score': 6, 'signal': 'STRONG_BUY', 'key_metric': 'Pharma momentum'},
    {'symbol': 'A', 'inst33': 80, 'overall_score': 8, 'signal': 'BUY', 'key_metric': 'Agilent emerging'},
    {'symbol': 'GOOGL', 'inst33': 80, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Tech AI leader'},
    {'symbol': 'GOOG', 'inst33': 80, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Tech uptrend'},
    {'symbol': 'JNJ', 'inst33': 75, 'overall_score': 8, 'signal': 'SELL_CALL', 'key_metric': 'Healthcare premium'},
    {'symbol': 'RY', 'inst33': 70, 'overall_score': 6, 'signal': 'SELL_CALL', 'key_metric': 'Financial low IV'},
    {'symbol': 'WMT', 'inst33': 70, 'overall_score': 0, 'signal': 'SELL_CALL', 'key_metric': 'Retail defensive'},
    {'symbol': 'LLY', 'inst33': 65, 'overall_score': 8, 'signal': 'HOLD', 'key_metric': 'Biotech GLP-1'},
    {'symbol': 'ASML', 'inst33': 65, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Chip equipment'},
    {'symbol': 'DAL', 'inst33': 65, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Airlines recovery'},
    {'symbol': 'AAPL', 'inst33': 60, 'overall_score': 6, 'signal': 'HOLD', 'key_metric': 'Tech stable'},
    {'symbol': 'MSFT', 'inst33': 60, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Cloud dominant'},
    {'symbol': 'NVDA', 'inst33': 45, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Chip weakness'},
    {'symbol': 'AMZN', 'inst33': 45, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'E-commerce pull'},
    {'symbol': 'TSLA', 'inst33': 50, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'EV volatility'},
    {'symbol': 'META', 'inst33': 55, 'overall_score': 4, 'signal': 'BUY', 'key_metric': 'AI upside'},
    {'symbol': 'NFLX', 'inst33': 58, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Streaming stable'},
    {'symbol': 'BABA', 'inst33': 48, 'overall_score': 3, 'signal': 'NEUTRAL', 'key_metric': 'China exposure'},
    {'symbol': 'JPM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Financial weak'},
    {'symbol': 'XOM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Energy dividend'},
    {'symbol': 'PG', 'inst33': 50, 'overall_score': 0, 'signal': 'SELL_CALL', 'key_metric': 'Consumer staples'},
    {'symbol': 'V', 'inst33': 70, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Payments strong'},
    {'symbol': 'MA', 'inst33': 70, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Mastercard momentum'},
    {'symbol': 'CSCO', 'inst33': 55, 'overall_score': 8, 'signal': 'HOLD', 'key_metric': 'Networking dividend'},
    {'symbol': 'INTC', 'inst33': 52, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Chip turnaround'},
    {'symbol': 'AMD', 'inst33': 53, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Chip competitor'},
    {'symbol': 'CRM', 'inst33': 58, 'overall_score': 5, 'signal': 'BUY', 'key_metric': 'Cloud CRM'},
    {'symbol': 'ADBE', 'inst33': 60, 'overall_score': 6, 'signal': 'HOLD', 'key_metric': 'Creative stable'},
    {'symbol': 'PYPL', 'inst33': 48, 'overall_score': 3, 'signal': 'NEUTRAL', 'key_metric': 'Fintech'},
    {'symbol': 'SQ', 'inst33': 52, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Square recovery'},
    {'symbol': 'DDOG', 'inst33': 62, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Cloud monitoring'},
    {'symbol': 'SNOW', 'inst33': 60, 'overall_score': 5, 'signal': 'BUY', 'key_metric': 'Data warehouse'},
    {'symbol': 'DBX', 'inst33': 54, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Cloud storage'},
    {'symbol': 'BOX', 'inst33': 48, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'Content mgmt'},
    {'symbol': 'OKTA', 'inst33': 56, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Identity secure'},
    {'symbol': 'SPLK', 'inst33': 55, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Analytics platform'},
    {'symbol': 'COIN', 'inst33': 45, 'overall_score': 2, 'signal': 'SELL', 'key_metric': 'Crypto exposure'},
    {'symbol': 'MSTR', 'inst33': 58, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Bitcoin proxy'},
    {'symbol': 'RIOT', 'inst33': 50, 'overall_score': 1, 'signal': 'SELL', 'key_metric': 'Mining weak'},
    {'symbol': 'HUT', 'inst33': 48, 'overall_score': 1, 'signal': 'SELL', 'key_metric': 'Miner volatile'},
    {'symbol': 'CLSK', 'inst33': 52, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'Mining consolidate'},
    {'symbol': 'DELL', 'inst33': 48, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'PC mature'},
    {'symbol': 'HPQ', 'inst33': 45, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'Hardware'},
    {'symbol': 'IBM', 'inst33': 52, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'IT services'},
    {'symbol': 'TSM', 'inst33': 50, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Foundry Taiwan'},
    {'symbol': 'QCOM', 'inst33': 52, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'Chip design'},
    {'symbol': 'AVGO', 'inst33': 53, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Broadcom'},
    {'symbol': 'MU', 'inst33': 48, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'Memory chips'},
]

TICKERS = [s['symbol'] for s in TOP_50_STOCKS]

# ======================== CACHE ========================
price_cache = {}
recommendations_cache = {'data': [], 'timestamp': None}
news_cache = {}
sentiment_cache = {}
macro_cache = {'data': {}, 'timestamp': None}
insider_cache = {}
earnings_cache = {'data': [], 'timestamp': None}
ai_insights_cache = {}

# ======================== 1. EARNINGS (Yahoo + Finnhub) ========================
def fetch_earnings_from_apis():
    """Fetch earnings from Yahoo Finance + Finnhub"""
    earnings_data = []
    seen_symbols = set()
    
    print("🔄 Fetching earnings from Yahoo Finance...")
    
    for ticker in TICKERS[:30]:
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
                            earnings_data.append({
                                'symbol': ticker,
                                'date': date_str,
                                'source': 'Yahoo'
                            })
                            seen_symbols.add(ticker)
                            print(f"✅ {ticker}: {date_str}")
            time.sleep(0.15)
        except:
            pass
    
    if FINNHUB_KEY and len(earnings_data) < 40:
        print("🔄 Fetching additional earnings from Finnhub...")
        try:
            from_date = datetime.now().strftime('%Y-%m-%d')
            to_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            url = f'https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={FINNHUB_KEY}'
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                for item in resp.json().get('earningsCalendar', []):
                    sym = item.get('symbol')
                    if sym in TICKERS and sym not in seen_symbols:
                        earnings_data.append({
                            'symbol': sym,
                            'date': item.get('date'),
                            'source': 'Finnhub'
                        })
                        seen_symbols.add(sym)
                        print(f"✅ {sym}: {item.get('date')} (Finnhub)")
        except:
            pass
    
    earnings_data.sort(key=lambda x: x['date'])
    today = datetime.now().strftime('%Y-%m-%d')
    earnings_data = [e for e in earnings_data if e['date'] >= today]
    
    print(f"✅ Total earnings loaded: {len(earnings_data)}\n")
    return earnings_data[:50]

# ======================== 2. SOCIAL SENTIMENT (DoD + WoW + MoM) ========================
def get_social_sentiment(ticker):
    """Sentiment with Day-over-Day, Week-over-Week, Month-over-Month"""
    
    if ticker in sentiment_cache:
        cached = sentiment_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < 43200:
            return cached['data']
    
    result = {
        'ticker': ticker,
        'daily': {'sentiment': 'NEUTRAL', 'mentions': 0, 'score': 0.00},
        'daily_change': {'dod': 0.00, 'dod_sentiment': 'NEUTRAL'},
        'weekly': {'sentiment': 'NEUTRAL', 'mentions': 0, 'score': 0.00},
        'weekly_change': {'wow': 0.00},
        'monthly_change': {'mom': 0.00}
    }
    
    if not FINNHUB_KEY:
        return result
    
    try:
        url = f'https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&token={FINNHUB_KEY}'
        resp = requests.get(url, timeout=5)
        
        if resp.status_code == 200:
            reddit = resp.json().get('reddit', [])
            
            if reddit and len(reddit) > 0:
                today = reddit[0]
                today_score = today.get('score', 0)
                today_mentions = today.get('mention', 0)
                today_sentiment = 'BULLISH' if today_score > 0.5 else ('BEARISH' if today_score < -0.5 else 'NEUTRAL')
                
                yesterday_score = reddit[1].get('score', 0) if len(reddit) > 1 else today_score
                dod_change = ((today_score - yesterday_score) / abs(yesterday_score)) * 100 if yesterday_score != 0 else 0
                dod_sentiment = 'BULLISH' if dod_change > 0 else ('BEARISH' if dod_change < 0 else 'NEUTRAL')
                
                week_data = reddit[:7]
                week_scores = [r.get('score', 0) for r in week_data]
                week_avg = sum(week_scores) / len(week_scores) if week_scores else 0
                week_mentions = sum(r.get('mention', 0) for r in week_data)
                week_sentiment = 'BULLISH' if week_avg > 0.5 else ('BEARISH' if week_avg < -0.5 else 'NEUTRAL')
                
                wow_change = 0.0
                if len(reddit) >= 7 and reddit[6].get('score', 0) != 0:
                    prev_week = reddit[6].get('score', 0)
                    wow_change = ((today_score - prev_week) / abs(prev_week)) * 100
                
                mom_change = 0.0
                if len(reddit) >= 30 and reddit[29].get('score', 0) != 0:
                    prev_month = reddit[29].get('score', 0)
                    mom_change = ((today_score - prev_month) / abs(prev_month)) * 100
                
                result = {
                    'ticker': ticker,
                    'daily': {'sentiment': today_sentiment, 'mentions': today_mentions, 'score': round(today_score, 2)},
                    'daily_change': {'dod': round(dod_change, 2), 'dod_sentiment': dod_sentiment},
                    'weekly': {'sentiment': week_sentiment, 'mentions': week_mentions, 'score': round(week_avg, 2)},
                    'weekly_change': {'wow': round(wow_change, 2)},
                    'monthly_change': {'mom': round(mom_change, 2)}
                }
    except:
        pass
    
    sentiment_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 3. INSIDER TRANSACTIONS (NoneType fixed) ========================
def get_insider_transactions(ticker):
    """Insider trading - fixed None handling"""
    
    if ticker in insider_cache:
        cached = insider_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < 86400:
            return cached['data']
    
    result = {'ticker': ticker, 'transactions': [], 'summary': {'buying': 0, 'selling': 0, 'signal': 'NEUTRAL'}}
    
    if not FINNHUB_KEY:
        return result
    
    try:
        url = f'https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&token={FINNHUB_KEY}'
        resp = requests.get(url, timeout=5)
        
        if resp.status_code == 200:
            transactions = resp.json().get('data', [])[:10]
            
            buying = 0
            selling = 0
            
            for tx in transactions:
                change = tx.get('change', 0)
                share = tx.get('share') or 0
                price = tx.get('price') or 0
                value = share * price if share and price else 0
                
                if change > 0:
                    buying += 1
                elif change < 0:
                    selling += 1
                
                result['transactions'].append({
                    'name': tx.get('name'),
                    'change': change,
                    'shares': share,
                    'price': price,
                    'date': tx.get('transactionDate'),
                    'type': 'BUY' if change > 0 else 'SELL'
                })
            
            signal = 'BULLISH' if buying > selling * 2 else ('BEARISH' if selling > buying * 2 else 'NEUTRAL')
            result['summary'] = {'buying': buying, 'selling': selling, 'signal': signal}
            
            print(f"✅ Insider {ticker}: {signal} ({buying} buys, {selling} sells)")
    except Exception as e:
        print(f"❌ Insider error {ticker}: {e}")
    
    insider_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 4. NEWS ========================
def get_stock_news(ticker):
    """Stock news from Finnhub"""
    
    if ticker in news_cache:
        cached = news_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < 3600:
            return cached['data']
    
    news = []
    
    if FINNHUB_KEY:
        try:
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')
            url = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={FINNHUB_KEY}'
            resp = requests.get(url, timeout=5)
            
            if resp.status_code == 200:
                for article in resp.json()[:10]:
                    news.append({
                        'headline': article.get('headline'),
                        'summary': article.get('summary'),
                        'url': article.get('url'),
                        'source': article.get('source'),
                        'datetime': datetime.fromtimestamp(article.get('datetime', 0)).strftime('%Y-%m-%d %H:%M')
                    })
                
                print(f"✅ News for {ticker}: {len(news)} articles")
        except:
            pass
    
    news_cache[ticker] = {'data': news, 'ts': datetime.now()}
    return news

# ======================== 5. AI ANALYSIS (PROPER FORMAT) ========================
def get_ai_analysis(ticker):
    """Perplexity Sonar analysis - properly formatted for frontend"""
    
    if ticker in ai_insights_cache:
        cached = ai_insights_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < 3600:
            return cached['data']
    
    result = {
        'ticker': ticker,
        'edge': 'Unable to analyze',
        'trade': 'No setup identified',
        'risk': 'Standard'
    }
    
    if not PERPLEXITY_KEY:
        return result
    
    try:
        stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
        context = f"Signal: {stock['signal']}" if stock else ""
        
        prompt = f"""Analyze {ticker} for day trading. {context}

Provide EXACTLY 3 lines:
EDGE: [Bullish or Bearish with % target]
TRADE: [Entry $X, Stop $Y, Target $Z]
RISK: [Low/Medium/High with reason]"""
        
        url = 'https://api.perplexity.ai/chat/completions'
        headers = {'Authorization': f'Bearer {PERPLEXITY_KEY}', 'Content-Type': 'application/json'}
        payload = {
            'model': 'sonar',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.6,
            'max_tokens': 250
        }
        
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            lines = [l.strip() for l in content.split('\n') if l.strip() and len(l) > 5]
            
            edge_line = next((l for l in lines if 'EDGE' in l.upper() or any(x in l.lower() for x in ['bullish', 'bearish', '%'])), None)
            trade_line = next((l for l in lines if 'TRADE' in l.upper() or any(x in l.lower() for x in ['entry', 'stop', 'target', '$'])), None)
            risk_line = next((l for l in lines if 'RISK' in l.upper() or any(x in l.lower() for x in ['low', 'medium', 'high'])), None)
            
            result = {
                'ticker': ticker,
                'edge': edge_line.replace('EDGE:', '').strip()[:100] if edge_line else 'Neutral setup',
                'trade': trade_line.replace('TRADE:', '').strip()[:100] if trade_line else 'Monitor levels',
                'risk': risk_line.replace('RISK:', '').strip()[:100] if risk_line else 'Standard risk'
            }
            
            print(f"✅ Sonar analysis for {ticker}")
    except Exception as e:
        print(f"❌ AI error {ticker}: {e}")
    
    ai_insights_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 6. OPTIONS ========================
def get_options_analysis(ticker):
    """Options strategies with Greeks"""
    price = 150.0
    
    return {
        'ticker': ticker,
        'current_price': price,
        'strategies': [
            {
                'type': 'Iron Condor',
                'setup': f'Sell ${round(price*1.05,2)} Call / Buy ${round(price*1.10,2)} Call | Sell ${round(price*0.95,2)} Put / Buy ${round(price*0.90,2)} Put',
                'max_profit': round(price * 0.02, 2),
                'max_loss': round(price * 0.03, 2),
                'probability_of_profit': '65%',
                'greeks': {'delta': '~0', 'gamma': 'Low', 'theta': '+High', 'vega': '-High', 'why_attractive': 'Theta decay favors seller, collects daily premium'}
            },
            {
                'type': 'Call Spread (Bullish)',
                'setup': f'Buy ${round(price,2)} Call / Sell ${round(price*1.05,2)} Call',
                'max_profit': round(price * 0.05, 2),
                'max_loss': round(price * 0.02, 2),
                'probability_of_profit': '55%',
                'greeks': {'delta': '+0.60', 'gamma': 'Positive', 'theta': 'Neutral', 'vega': 'Low', 'why_attractive': 'Positive gamma accelerates gains on rallies'}
            },
            {
                'type': 'Put Spread (Bearish)',
                'setup': f'Buy ${round(price,2)} Put / Sell ${round(price*0.95,2)} Put',
                'max_profit': round(price * 0.05, 2),
                'max_loss': round(price * 0.02, 2),
                'probability_of_profit': '55%',
                'greeks': {'delta': '-0.60', 'gamma': 'Positive', 'theta': 'Neutral', 'vega': 'Low', 'why_attractive': 'Positive gamma accelerates gains on drops'}
            }
        ]
    }

# ======================== 7. MACRO ========================
def get_macro_indicators():
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
def get_recommendations():
    """Top 50 stocks"""
    results = []
    for stock in TOP_50_STOCKS:
        results.append({
            'Symbol': stock['symbol'],
            'Last': 100,
            'Change': 0,
            'Signal': stock['signal'],
            'Score': stock['inst33'],
            'KeyMetric': stock['key_metric']
        })
    return jsonify(results)

@app.route('/api/earnings-calendar', methods=['GET'])
def get_earnings():
    return jsonify(earnings_cache.get('data', []))

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def get_sentiment(ticker):
    return jsonify(get_social_sentiment(ticker.upper()))

@app.route('/api/insider-transactions/<ticker>', methods=['GET'])
def get_insider(ticker):
    return jsonify(get_insider_transactions(ticker.upper()))

@app.route('/api/stock-news/<ticker>', methods=['GET'])
def get_news(ticker):
    news = get_stock_news(ticker.upper())
    return jsonify({'ticker': ticker.upper(), 'news': news})

@app.route('/api/ai-insights/<ticker>', methods=['GET'])
def get_ai(ticker):
    return jsonify(get_ai_analysis(ticker.upper()))

@app.route('/api/options-opportunities/<ticker>', methods=['GET'])
def get_options(ticker):
    return jsonify(get_options_analysis(ticker.upper()))

@app.route('/api/macro-indicators', methods=['GET'])
def get_macro():
    return jsonify(get_macro_indicators())

@app.route('/api/stock-price/<ticker>', methods=['GET'])
def get_stock_price(ticker):
    return jsonify({'ticker': ticker.upper(), 'price': 100, 'change': 0})

# ======================== SCHEDULER ========================
def refresh_earnings():
    global earnings_cache
    print("\n🔄 [SCHEDULED] Refreshing earnings...")
    try:
        earnings_cache['data'] = fetch_earnings_from_apis()
        earnings_cache['timestamp'] = datetime.now()
    except Exception as e:
        print(f"❌ Refresh error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=refresh_earnings, trigger="cron", day=1, hour=9)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ======================== INITIALIZATION ========================
print("\n" + "="*60)
print("🚀 ELITE STOCK TRACKER - SERVER STARTUP")
print("="*60)

earnings_cache['data'] = fetch_earnings_from_apis()
earnings_cache['timestamp'] = datetime.now()

print(f"✅ Loaded {len(TICKERS)} tickers from TOP_50_STOCKS")
print(f"✅ Perplexity: {'ENABLED' if PERPLEXITY_KEY else 'DISABLED'}")
print(f"✅ FRED: {'ENABLED' if FRED_KEY else 'DISABLED'}")
print(f"✅ Scheduler started")
print("="*60 + "\n")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
