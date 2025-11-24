from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import traceback
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ======================== API KEYS ========================
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')
FRED_KEY = os.environ.get('FRED_API_KEY', '')
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')

print(f"\n✅ FINNHUB: {'READY' if FINNHUB_KEY else 'NOT SET'}")
print(f"✅ FRED: {'READY' if FRED_KEY else 'NOT SET'}")
print(f"✅ PERPLEXITY: {'READY' if PERPLEXITY_KEY else 'NOT SET'}\n")

# ======================== TOP 50 STOCKS (Elite Scoring) ========================
TOP_50_STOCKS = [
    {'symbol': 'KO', 'inst33': 95, 'overall_score': 8, 'signal': 'STRONG_BUY', 'key_metric': 'Beverage leader - institutional backing'},
    {'symbol': 'AZN', 'inst33': 95, 'overall_score': 8, 'signal': 'STRONG_BUY', 'key_metric': 'Biotech - highest inst backing'},
    {'symbol': 'MRK', 'inst33': 90, 'overall_score': 6, 'signal': 'STRONG_BUY', 'key_metric': 'Pharma strong momentum'},
    {'symbol': 'A', 'inst33': 80, 'overall_score': 8, 'signal': 'BUY', 'key_metric': 'Agilent - emerging strength'},
    {'symbol': 'GOOGL', 'inst33': 80, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Tech - AI leadership'},
    {'symbol': 'GOOG', 'inst33': 80, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Tech - strong uptrend'},
    {'symbol': 'JNJ', 'inst33': 75, 'overall_score': 8, 'signal': 'SELL_CALL', 'key_metric': 'Healthcare - premium seller'},
    {'symbol': 'RY', 'inst33': 70, 'overall_score': 6, 'signal': 'SELL_CALL', 'key_metric': 'Financial - low IV'},
    {'symbol': 'WMT', 'inst33': 70, 'overall_score': 0, 'signal': 'SELL_CALL', 'key_metric': 'Retail - defensive'},
    {'symbol': 'LLY', 'inst33': 65, 'overall_score': 8, 'signal': 'HOLD', 'key_metric': 'Biotech GLP-1 leader'},
    {'symbol': 'ASML', 'inst33': 65, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Chip equipment - pullback'},
    {'symbol': 'AAPL', 'inst33': 60, 'overall_score': 6, 'signal': 'HOLD', 'key_metric': 'Tech giant - stable'},
    {'symbol': 'MSFT', 'inst33': 60, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Cloud dominance'},
    {'symbol': 'NVDA', 'inst33': 45, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Chip leader - weakness'},
    {'symbol': 'AMZN', 'inst33': 45, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'E-commerce - pullback'},
    {'symbol': 'TSLA', 'inst33': 50, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'EV volatility high'},
    {'symbol': 'META', 'inst33': 55, 'overall_score': 4, 'signal': 'BUY', 'key_metric': 'AI upside'},
    {'symbol': 'NFLX', 'inst33': 58, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Streaming stable'},
    {'symbol': 'BABA', 'inst33': 48, 'overall_score': 3, 'signal': 'NEUTRAL', 'key_metric': 'China exposure'},
    {'symbol': 'JPM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Financial system weak'},
    {'symbol': 'XOM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Energy dividend'},
    {'symbol': 'PG', 'inst33': 50, 'overall_score': 0, 'signal': 'SELL_CALL', 'key_metric': 'Consumer staples'},
    {'symbol': 'JNJ', 'inst33': 75, 'overall_score': 8, 'signal': 'SELL_CALL', 'key_metric': 'Healthcare premium'},
    {'symbol': 'V', 'inst33': 70, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Payments strong'},
    {'symbol': 'MA', 'inst33': 70, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Mastercard momentum'},
    {'symbol': 'CSCO', 'inst33': 55, 'overall_score': 8, 'signal': 'HOLD', 'key_metric': 'Networking dividend'},
    {'symbol': 'INTC', 'inst33': 52, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Chip maker - turnaround'},
    {'symbol': 'AMD', 'inst33': 53, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Chip competitor weakness'},
    {'symbol': 'CRM', 'inst33': 58, 'overall_score': 5, 'signal': 'BUY', 'key_metric': 'Cloud CRM leader'},
    {'symbol': 'ADBE', 'inst33': 60, 'overall_score': 6, 'signal': 'HOLD', 'key_metric': 'Creative Cloud stable'},
    {'symbol': 'PYPL', 'inst33': 48, 'overall_score': 3, 'signal': 'NEUTRAL', 'key_metric': 'Fintech consolidation'},
    {'symbol': 'SQ', 'inst33': 52, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Square recovery'},
    {'symbol': 'DDOG', 'inst33': 62, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Cloud monitoring growth'},
    {'symbol': 'SNOW', 'inst33': 60, 'overall_score': 5, 'signal': 'BUY', 'key_metric': 'Data warehouse leader'},
    {'symbol': 'DBX', 'inst33': 54, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Cloud storage mature'},
    {'symbol': 'BOX', 'inst33': 48, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'Content management stable'},
    {'symbol': 'OKTA', 'inst33': 56, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Identity security growth'},
    {'symbol': 'SPLK', 'inst33': 55, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Data analytics platform'},
    {'symbol': 'COIN', 'inst33': 45, 'overall_score': 2, 'signal': 'SELL', 'key_metric': 'Crypto exposure'},
    {'symbol': 'MSTR', 'inst33': 58, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Bitcoin proxy volatile'},
    {'symbol': 'RIOT', 'inst33': 50, 'overall_score': 1, 'signal': 'SELL', 'key_metric': 'Bitcoin mining weak'},
    {'symbol': 'HUT', 'inst33': 48, 'overall_score': 1, 'signal': 'SELL', 'key_metric': 'Crypto miner volatile'},
    {'symbol': 'CLSK', 'inst33': 52, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'Mining consolidation'},
]

TICKERS = [s['symbol'] for s in TOP_50_STOCKS]

# ======================== GLOBAL CACHES ========================
price_cache = {}
earnings_cache = {'data': [], 'timestamp': None}
sentiment_cache = {}
macro_cache = {'data': {}, 'timestamp': None}
ai_cache = {}
options_cache = {}

PRICE_TTL = 300  # 5 min
EARNINGS_TTL = 86400  # 1 day
SENTIMENT_TTL = 43200  # 12 hours
MACRO_TTL = 604800  # 7 days
AI_TTL = 3600  # 1 hour

# ======================== 1. EARNINGS CALENDAR (LIVE) ========================
def fetch_earnings_live():
    """Fetch REAL earnings from Yahoo Finance & Finnhub - NO HARDCODING"""
    earnings = []
    seen = set()
    
    print("🔄 Fetching earnings from Yahoo Finance...")
    
    for ticker in TICKERS[:20]:
        try:
            url = f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}'
            params = {'modules': 'calendarEvents'}
            resp = requests.get(url, params=params, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
            
            if resp.status_code == 200:
                data = resp.json().get('quoteSummary', {}).get('result', [])
                if data:
                    cal = data[0].get('calendarEvents', {})
                    ear_list = cal.get('earnings', {}).get('earningsDate', [])
                    
                    if ear_list:
                        ts = ear_list[0].get('raw')
                        if ts:
                            date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                            eps = cal.get('earnings', {}).get('earningsAverage')
                            
                            earnings.append({
                                'symbol': ticker,
                                'date': date_str,
                                'eps': eps,
                                'source': 'Yahoo'
                            })
                            seen.add(ticker)
                            print(f"✅ {ticker}: {date_str}")
            time.sleep(0.2)
        except Exception as e:
            print(f"⚠️ {ticker} error: {e}")
    
    # Finnhub backup
    if FINNHUB_KEY and len(earnings) < 30:
        try:
            print("🔄 Fetching from Finnhub...")
            from_date = datetime.now().strftime('%Y-%m-%d')
            to_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            url = f'https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={FINNHUB_KEY}'
            resp = requests.get(url, timeout=10)
            
            if resp.status_code == 200:
                items = resp.json().get('earningsCalendar', [])
                for item in items:
                    sym = item.get('symbol')
                    if sym in TICKERS and sym not in seen:
                        earnings.append({
                            'symbol': sym,
                            'date': item.get('date'),
                            'eps': item.get('epsEstimate'),
                            'source': 'Finnhub'
                        })
                        seen.add(sym)
        except Exception as e:
            print(f"⚠️ Finnhub error: {e}")
    
    earnings.sort(key=lambda x: x['date'])
    today = datetime.now().strftime('%Y-%m-%d')
    earnings = [e for e in earnings if e['date'] >= today]
    
    print(f"✅ Loaded {len(earnings)} earnings\n")
    return earnings[:50]

# ======================== 2. SOCIAL SENTIMENT (REAL SCORES) ========================
def get_sentiment(ticker):
    """Real sentiment analysis with WoW & MoM changes"""
    
    # Check cache
    if ticker in sentiment_cache:
        cached = sentiment_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < SENTIMENT_TTL:
            return cached['data']
    
    # Default response
    result = {
        'ticker': ticker,
        'daily': {'sentiment': 'NEUTRAL', 'mentions': 0, 'score': 0.00},
        'weekly': {'sentiment': 'NEUTRAL', 'mentions': 0, 'score': 0.00},
        'changes': {'wow': 0.00, 'mom': 0.00},
        'source': 'Finnhub API'
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
                # Daily (most recent)
                daily = reddit[0]
                daily_score = daily.get('score', 0)
                daily_mentions = daily.get('mention', 0)
                
                daily_sentiment = 'BULLISH' if daily_score > 0.5 else ('BEARISH' if daily_score < -0.5 else 'NEUTRAL')
                
                # Weekly average (last 7 days)
                weekly_data = reddit[:7]
                weekly_scores = [r.get('score', 0) for r in weekly_data]
                weekly_avg = sum(weekly_scores) / len(weekly_scores) if weekly_scores else 0
                weekly_mentions = sum(r.get('mention', 0) for r in weekly_data)
                weekly_sentiment = 'BULLISH' if weekly_avg > 0.5 else ('BEARISH' if weekly_avg < -0.5 else 'NEUTRAL')
                
                # Calculate changes
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
                    'daily': {
                        'sentiment': daily_sentiment,
                        'mentions': daily_mentions,
                        'score': round(daily_score, 2)
                    },
                    'weekly': {
                        'sentiment': weekly_sentiment,
                        'mentions': weekly_mentions,
                        'score': round(weekly_avg, 2)
                    },
                    'changes': {
                        'wow_percent': round(wow_change, 2),
                        'mom_percent': round(mom_change, 2)
                    },
                    'source': 'Finnhub Social Sentiment',
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"✅ Sentiment {ticker}: {daily_sentiment} ({daily_score})")
    
    except Exception as e:
        print(f"❌ Sentiment error {ticker}: {e}")
    
    sentiment_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 3. STOCK PRICES ========================
def get_price(ticker):
    """Get real-time stock price from Finnhub"""
    
    if ticker in price_cache:
        cached = price_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < PRICE_TTL:
            return cached['data']
    
    # Mock data (replace with real API)
    result = {
        'ticker': ticker,
        'price': 150.00,
        'change': 1.50,
        'change_pct': 1.00,
        'source': 'Mock'
    }
    
    if FINNHUB_KEY:
        try:
            url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
            resp = requests.get(url, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                price = data.get('c', 150)
                prev = data.get('pc', price)
                change = price - prev
                change_pct = (change / prev * 100) if prev else 0
                
                result = {
                    'ticker': ticker,
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'change_pct': round(change_pct, 2),
                    'source': 'Finnhub',
                    'timestamp': datetime.now().isoformat()
                }
                print(f"✅ Price {ticker}: ${price}")
        except Exception as e:
            print(f"❌ Price error {ticker}: {e}")
    
    price_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 4. AI ANALYSIS (PERPLEXITY SONAR) ========================
def get_ai_analysis(ticker):
    """AI trading analysis with Edge/Trade/Risk breakdown"""
    
    if ticker in ai_cache:
        cached = ai_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < AI_TTL:
            return cached['data']
    
    result = {
        'ticker': ticker,
        'edge': 'Unable to analyze',
        'trade': 'N/A',
        'risk': 'N/A',
        'confidence': 0
    }
    
    if not PERPLEXITY_KEY:
        print(f"⚠️ Perplexity not configured")
        return result
    
    try:
        # Get stock context
        stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
        price = get_price(ticker)
        sentiment = get_sentiment(ticker)
        
        context = f"""
Ticker: {ticker}
Current Price: ${price['price']}
Change: {price['change_pct']}%
Signal: {stock['signal'] if stock else 'NEUTRAL'}
Sentiment: {sentiment['daily']['sentiment']}
Inst33: {stock['inst33'] if stock else 50}
"""
        
        prompt = f"""You are a professional day trader. Analyze {ticker} and provide EXACTLY this format:

{context}

Provide 3 sections separated by "###":

### EDGE (Bullish/Bearish setup with % objective, one line)
### TRADE (Entry price, stop loss, target price, one line)
### RISK (Low/Medium/High with reason, one line)

Be concise and actionable."""
        
        url = 'https://api.perplexity.ai/chat/completions'
        headers = {
            'Authorization': f'Bearer {PERPLEXITY_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'sonar',
            'messages': [
                {'role': 'system', 'content': 'Expert day trader providing concise analysis'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.6,
            'max_tokens': 300
        }
        
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            
            # Extract sections
            edge = next((l for l in lines if len(l) > 10 and any(x in l.lower() for x in ['bullish', 'bearish', '%'])), 'Neutral')
            trade = next((l for l in lines if len(l) > 10 and any(x in l.lower() for x in ['entry', 'stop', 'target', '$'])), 'Monitor')
            risk = next((l for l in lines if len(l) > 10 and 'risk' in l.lower()), 'Standard')
            
            result = {
                'ticker': ticker,
                'edge': edge[:120],
                'trade': trade[:120],
                'risk': risk[:120],
                'confidence': 85,
                'source': 'Perplexity Sonar',
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"✅ AI Analysis {ticker}")
        else:
            print(f"⚠️ Perplexity error: {resp.status_code}")
    
    except Exception as e:
        print(f"❌ AI error {ticker}: {e}")
        traceback.print_exc()
    
    ai_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== 5. OPTIONS ANALYSIS (WITH GREEKS EXPLANATION) ========================
def get_options_analysis(ticker):
    """Options strategies with Greeks explanation"""
    
    price = get_price(ticker)
    current = price['price']
    
    return {
        'ticker': ticker,
        'current_price': current,
        'strategies': [
            {
                'name': 'Iron Condor',
                'view': 'Neutral',
                'setup': f'Sell ${round(current*1.05, 2)} Call / Buy ${round(current*1.10, 2)} Call | Sell ${round(current*0.95, 2)} Put / Buy ${round(current*0.90, 2)} Put',
                'max_profit': round(current * 0.02, 2),
                'max_loss': round(current * 0.03, 2),
                'probability': '65%',
                'greeks_explanation': {
                    'delta': '~0 (no directional bias - Delta close to zero is attractive for neutral)',
                    'gamma': 'Low (stable premium collection - Gamma decay works for you)',
                    'theta': '+High (time decay helps seller - Theta is your friend)',
                    'vega': '-High (benefits from volatility drop - Short vega extracts premium)',
                    'why_attractive': 'Collects premium while protecting both sides. Works 65% of the time even if price doesn\'t move.'
                }
            },
            {
                'name': 'Call Spread (Bullish)',
                'view': 'Moderately Bullish',
                'setup': f'Buy ${round(current, 2)} Call / Sell ${round(current*1.05, 2)} Call',
                'max_profit': round(current * 0.05, 2),
                'max_loss': round(current * 0.02, 2),
                'probability': '55%',
                'greeks_explanation': {
                    'delta': '+0.50 to +0.70 (bullish exposure - positive delta = upside capture)',
                    'gamma': 'Positive & moderate (accelerates gains when stock rallies - Gamma is attractive)',
                    'theta': 'Slight decay but manageable (long premium offset by short premium)',
                    'vega': 'Near neutral (less affected by IV changes - Vega-neutral is good)',
                    'why_attractive': 'Limited risk + positive gamma = gains accelerate on rallies. Better than buying naked call.'
                }
            },
            {
                'name': 'Put Spread (Bearish)',
                'view': 'Moderately Bearish',
                'setup': f'Buy ${round(current, 2)} Put / Sell ${round(current*0.95, 2)} Put',
                'max_profit': round(current * 0.05, 2),
                'max_loss': round(current * 0.02, 2),
                'probability': '55%',
                'greeks_explanation': {
                    'delta': '-0.50 to -0.70 (bearish exposure - negative delta = downside capture)',
                    'gamma': 'Positive & moderate (accelerates gains when stock falls - Gamma is attractive)',
                    'theta': 'Slight decay but manageable (long premium offset by short premium)',
                    'vega': 'Near neutral (less affected by IV changes - Vega-neutral is good)',
                    'why_attractive': 'Limited risk + positive gamma = gains accelerate on drops. Better than buying naked put.'
                }
            },
            {
                'name': 'Call Spread (Bearish)',
                'view': 'Bearish / High IV Play',
                'setup': f'Sell ${round(current*1.02, 2)} Call / Buy ${round(current*1.08, 2)} Call',
                'max_profit': round(current * 0.015, 2),
                'max_loss': round(current * 0.035, 2),
                'probability': '60%',
                'greeks_explanation': {
                    'delta': '-0.40 to -0.60 (bearish tilt - short delta on upper strike)',
                    'gamma': 'Negative (decay works against you if stock rallies - but you collected premium)',
                    'theta': '+High (time decay helps - daily premium collection)',
                    'vega': '-High (benefits from IV crush - best when VIX is elevated)',
                    'why_attractive': 'Credit spread pays premium. Most profitable when IV drops or stock stays down. Theta decay = money in your pocket.'
                }
            },
            {
                'name': 'Put Spread (Bullish)',
                'view': 'Bullish / High IV Play',
                'setup': f'Sell ${round(current*0.98, 2)} Put / Buy ${round(current*0.92, 2)} Put',
                'max_profit': round(current * 0.015, 2),
                'max_loss': round(current * 0.035, 2),
                'probability': '60%',
                'greeks_explanation': {
                    'delta': '+0.40 to +0.60 (bullish tilt - short delta on lower strike)',
                    'gamma': 'Negative (decay works against you if stock drops - but you collected premium)',
                    'theta': '+High (time decay helps - daily premium collection)',
                    'vega': '-High (benefits from IV crush - best when VIX is elevated)',
                    'why_attractive': 'Credit spread pays premium. Most profitable when IV drops or stock stays up. Theta decay = daily profit.'
                }
            },
            {
                'name': 'Butterfly Spread',
                'view': 'Neutral / Mean Reversion',
                'setup': f'Buy ${round(current*0.98, 2)} Call / Sell 2x ${round(current, 2)} Call / Buy ${round(current*1.02, 2)} Call',
                'max_profit': round(current * 0.04, 2),
                'max_loss': round(current * 0.01, 2),
                'probability': '50%',
                'greeks_explanation': {
                    'delta': '~0 (delta-neutral peak at middle strike)',
                    'gamma': 'Mix of positive & negative (peaky - high profit near center)',
                    'theta': '+Moderate (time decay helps as stock stays pinned)',
                    'vega': 'Low impact (less affected by IV changes)',
                    'why_attractive': 'Cheap to enter, max risk is limited. Perfect when stock stays flat. Theta + gamma = small account friendly.'
                }
            }
        ],
        'timestamp': datetime.now().isoformat()
    }

# ======================== 6. MACRO INDICATORS (FRED) ========================
def get_macro():
    """Economic indicators from FRED"""
    
    if macro_cache['data'] and macro_cache['timestamp']:
        age = (datetime.now() - macro_cache['timestamp']).total_seconds()
        if age < MACRO_TTL:
            return macro_cache['data']
    
    indicators = {}
    
    if not FRED_KEY:
        return indicators
    
    series = {
        'UNRATE': 'Unemployment Rate',
        'CPIAUCSL': 'Inflation (CPI)',
        'DCOILWTICO': 'Oil Price',
        'DFF': 'Fed Funds Rate',
        'T10Y2Y': 'Yield Curve',
        'VIXCLS': 'VIX Index'
    }
    
    try:
        for sid, name in series.items():
            url = 'https://api.stlouisfed.org/fred/series/observations'
            params = {
                'series_id': sid,
                'api_key': FRED_KEY,
                'file_type': 'json',
                'sort_order': 'desc',
                'limit': 1
            }
            
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                obs = resp.json().get('observations', [])
                if obs:
                    val = obs[0].get('value')
                    indicators[sid] = {
                        'name': name,
                        'value': float(val) if val != '.' else None,
                        'date': obs[0].get('date')
                    }
                    print(f"✅ FRED: {sid} = {val}")
    except Exception as e:
        print(f"❌ FRED error: {e}")
    
    macro_cache['data'] = indicators
    macro_cache['timestamp'] = datetime.now()
    
    return indicators

# ======================== API ENDPOINTS ========================

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'OK', 'timestamp': datetime.now().isoformat()})

@app.route('/api/recommendations', methods=['GET'])
def recommendations():
    """Top 50 stocks with live pricing"""
    results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(get_price, s['symbol']): s for s in TOP_50_STOCKS}
        
        for future in as_completed(futures):
            stock = futures[future]
            try:
                price = future.result()
                results.append({
                    'Symbol': stock['symbol'],
                    'Price': price['price'],
                    'Change': price['change_pct'],
                    'Signal': stock['signal'],
                    'Inst33': stock['inst33'],
                    'KeyMetric': stock['key_metric']
                })
            except:
                pass
    
    return jsonify(sorted(results, key=lambda x: x['Inst33'], reverse=True))

@app.route('/api/earnings-calendar', methods=['GET'])
def earnings():
    """Earnings calendar from live APIs"""
    return jsonify(UPCOMING_EARNINGS)

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def sentiment(ticker):
    """Social sentiment with real scores"""
    return jsonify(get_sentiment(ticker.upper()))

@app.route('/api/macro-indicators', methods=['GET'])
def macro():
    """Economic indicators from FRED"""
    return jsonify(get_macro())

@app.route('/api/ai-analysis/<ticker>', methods=['GET'])
def ai_analysis(ticker):
    """AI trading analysis"""
    return jsonify(get_ai_analysis(ticker.upper()))

@app.route('/api/options-analysis/<ticker>', methods=['GET'])
def options_analysis(ticker):
    """Options strategies with Greeks"""
    return jsonify(get_options_analysis(ticker.upper()))

@app.route('/api/stock-detail/<ticker>', methods=['GET'])
def stock_detail(ticker):
    """Complete stock analysis"""
    ticker = ticker.upper()
    return jsonify({
        'price': get_price(ticker),
        'sentiment': get_sentiment(ticker),
        'ai_analysis': get_ai_analysis(ticker),
        'options': get_options_analysis(ticker)
    })

# ======================== SCHEDULER ========================
def refresh_earnings():
    """Monthly earnings refresh"""
    global UPCOMING_EARNINGS
    print("\n🔄 [SCHEDULED] Refreshing earnings...")
    try:
        UPCOMING_EARNINGS = fetch_earnings_live()
        earnings_cache['data'] = UPCOMING_EARNINGS
        earnings_cache['timestamp'] = datetime.now()
    except Exception as e:
        print(f"❌ Refresh error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=refresh_earnings, trigger="cron", day=1, hour=9)  # Daily 9am PST
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ======================== INITIALIZATION ========================
print("\n" + "="*60)
print("🚀 ELITE STOCK TRACKER - SERVER STARTUP")
print("="*60)

UPCOMING_EARNINGS = fetch_earnings_live()

print("\n✅ Server Ready!")
print(f"   - {len(TICKERS)} stocks loaded")
print(f"   - {len(UPCOMING_EARNINGS)} upcoming earnings")
print(f"   - APIs: FINNHUB, FRED, PERPLEXITY")
print("="*60 + "\n")

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
