from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from bs4 import BeautifulSoup
import time

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
    {'symbol': 'AAPL', 'inst33': 60, 'overall_score': 6, 'signal': 'HOLD', 'key_metric': 'Tech stable'},
    {'symbol': 'MSFT', 'inst33': 60, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Cloud dominant'},
    {'symbol': 'NVDA', 'inst33': 45, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Chip weakness'},
    {'symbol': 'AMZN', 'inst33': 45, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'E-commerce pull'},
    {'symbol': 'BABA', 'inst33': 48, 'overall_score': 3, 'signal': 'NEUTRAL', 'key_metric': 'China exposure'},
    {'symbol': 'TSLA', 'inst33': 50, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'EV volatility'},
    {'symbol': 'META', 'inst33': 55, 'overall_score': 4, 'signal': 'BUY', 'key_metric': 'AI upside'},
    {'symbol': 'NFLX', 'inst33': 58, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Streaming stable'},
    {'symbol': 'GOOGL', 'inst33': 80, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Tech AI leader'},
    {'symbol': 'GOOG', 'inst33': 80, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Tech uptrend'},
    {'symbol': 'JNJ', 'inst33': 75, 'overall_score': 8, 'signal': 'SELL_CALL', 'key_metric': 'Healthcare premium'},
    {'symbol': 'RY', 'inst33': 70, 'overall_score': 6, 'signal': 'SELL_CALL', 'key_metric': 'Financial low IV'},
    {'symbol': 'WMT', 'inst33': 70, 'overall_score': 0, 'signal': 'SELL_CALL', 'key_metric': 'Retail defensive'},
    {'symbol': 'V', 'inst33': 70, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Payments strong'},
    {'symbol': 'MA', 'inst33': 70, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Mastercard momentum'},
    {'symbol': 'LLY', 'inst33': 65, 'overall_score': 8, 'signal': 'HOLD', 'key_metric': 'Biotech GLP-1'},
    {'symbol': 'A', 'inst33': 80, 'overall_score': 8, 'signal': 'BUY', 'key_metric': 'Agilent emerging'},
    {'symbol': 'ASML', 'inst33': 65, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Chip equipment'},
    {'symbol': 'JPM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Financial weak'},
    {'symbol': 'XOM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Energy dividend'},
    {'symbol': 'PG', 'inst33': 50, 'overall_score': 0, 'signal': 'SELL_CALL', 'key_metric': 'Consumer staples'},
    {'symbol': 'CSCO', 'inst33': 55, 'overall_score': 8, 'signal': 'HOLD', 'key_metric': 'Networking dividend'},
    {'symbol': 'INTC', 'inst33': 52, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Chip turnaround'},
    {'symbol': 'AMD', 'inst33': 53, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Chip competitor'},
    {'symbol': 'CRM', 'inst33': 58, 'overall_score': 5, 'signal': 'BUY', 'key_metric': 'Cloud CRM'},
    {'symbol': 'ADBE', 'inst33': 60, 'overall_score': 6, 'signal': 'HOLD', 'key_metric': 'Creative stable'},
    {'symbol': 'DDOG', 'inst33': 62, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Cloud monitoring'},
    {'symbol': 'SNOW', 'inst33': 60, 'overall_score': 5, 'signal': 'BUY', 'key_metric': 'Data warehouse'},
    {'symbol': 'DBX', 'inst33': 54, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Cloud storage'},
    {'symbol': 'OKTA', 'inst33': 56, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Identity secure'},
    {'symbol': 'SPLK', 'inst33': 55, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Analytics platform'},
    {'symbol': 'COIN', 'inst33': 45, 'overall_score': 2, 'signal': 'SELL', 'key_metric': 'Crypto exposure'},
    {'symbol': 'MSTR', 'inst33': 58, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Bitcoin proxy'},
    {'symbol': 'RIOT', 'inst33': 50, 'overall_score': 1, 'signal': 'SELL', 'key_metric': 'Mining weak'},
    {'symbol': 'HUT', 'inst33': 48, 'overall_score': 1, 'signal': 'SELL', 'key_metric': 'Miner volatile'},
    {'symbol': 'CLSK', 'inst33': 52, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'Mining consolidate'},
    {'symbol': 'DELL', 'inst33': 48, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'PC mature'},
    {'symbol': 'IBM', 'inst33': 52, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'IT services'},
    {'symbol': 'TSM', 'inst33': 50, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Foundry Taiwan'},
    {'symbol': 'QCOM', 'inst33': 52, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'Chip design'},
    {'symbol': 'AVGO', 'inst33': 53, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Broadcom'},
    {'symbol': 'MU', 'inst33': 48, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'Memory chips'},
    {'symbol': 'BOX', 'inst33': 48, 'overall_score': 3, 'signal': 'HOLD', 'key_metric': 'Content mgmt'},
    {'symbol': 'PYPL', 'inst33': 48, 'overall_score': 3, 'signal': 'NEUTRAL', 'key_metric': 'Fintech'},
    {'symbol': 'SQ', 'inst33': 52, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Square recovery'},
    {'symbol': 'DAL', 'inst33': 65, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Airlines recovery'},
    {'symbol': 'HPQ', 'inst33': 45, 'overall_score': 2, 'signal': 'HOLD', 'key_metric': 'Hardware'},
]

TICKERS = [s['symbol'] for s in TOP_50_STOCKS]

# ======================== CACHE ========================
recommendations_cache = {'data': [], 'timestamp': None}
news_cache = {}
sentiment_cache = {}
macro_cache = {'data': {}, 'timestamp': None}
insider_cache = {}
earnings_cache = {'data': [], 'timestamp': None}
ai_insights_cache = {}
options_cache = {}

# ======================== EARNINGS EVALUATION ========================
def fetch_earnings_multi_source():
    """Evaluate: Yahoo + Finnhub + Perplexity + AlphaVantage + Massive + EarningsHub"""
    earnings_data = []
    sources_tried = []
    
    print("\n" + "="*70)
    print("🔄 EARNINGS EVALUATION - Testing all APIs")
    print("="*70)
    
    # 1. YAHOO FINANCE
    print("\n1️⃣ YAHOO FINANCE")
    try:
        for ticker in TICKERS[:5]:
            url = f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}'
            resp = requests.get(url, params={'modules': 'calendarEvents'}, timeout=5,
                              headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                data = resp.json().get('quoteSummary', {}).get('result', [])
                if data:
                    cal = data[0].get('calendarEvents', {})
                    ear = cal.get('earnings', {}).get('earningsDate', [])
                    if ear:
                        ts = ear[0].get('raw')
                        if ts:
                            date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                            earnings_data.append({'symbol': ticker, 'date': date_str, 'source': 'Yahoo'})
                            print(f"  ✅ {ticker}: {date_str}")
            time.sleep(0.2)
        sources_tried.append(f"Yahoo ({len([e for e in earnings_data if e['source']=='Yahoo'])} results)")
    except Exception as e:
        print(f"  ❌ Yahoo error: {e}")
        sources_tried.append("Yahoo (failed)")
    
    # 2. FINNHUB
    print("\n2️⃣ FINNHUB")
    try:
        if FINNHUB_KEY:
            from_date = datetime.now().strftime('%Y-%m-%d')
            to_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
            url = f'https://finnhub.io/api/v1/calendar/earnings?from={from_date}&to={to_date}&token={FINNHUB_KEY}'
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                cal_data = resp.json().get('earningsCalendar', [])
                fh_count = 0
                for item in cal_data[:10]:
                    sym = item.get('symbol')
                    if sym in TICKERS:
                        earnings_data.append({'symbol': sym, 'date': item.get('date'), 'source': 'Finnhub'})
                        fh_count += 1
                print(f"  ✅ Finnhub: {fh_count} results")
                sources_tried.append(f"Finnhub ({fh_count} results)")
            else:
                print(f"  ❌ Finnhub HTTP {resp.status_code}")
                sources_tried.append("Finnhub (API error)")
        else:
            print("  ⚠️ Finnhub key not configured")
            sources_tried.append("Finnhub (no key)")
    except Exception as e:
        print(f"  ❌ Finnhub error: {e}")
        sources_tried.append("Finnhub (failed)")
    
    # 3. PERPLEXITY SONAR
    print("\n3️⃣ PERPLEXITY SONAR")
    try:
        if PERPLEXITY_KEY:
            prompt = f"List upcoming earnings dates for: {','.join(TICKERS[:5])} in format SYMBOL:DATE"
            url = 'https://api.perplexity.ai/chat/completions'
            headers = {'Authorization': f'Bearer {PERPLEXITY_KEY}', 'Content-Type': 'application/json'}
            payload = {
                'model': 'sonar',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 500
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                # Parse earnings from Sonar response
                lines = content.split('\n')
                sonar_count = 0
                for line in lines:
                    if ':' in line and any(t in line for t in TICKERS[:5]):
                        parts = line.split(':')
                        if len(parts) >= 2:
                            sonar_count += 1
                print(f"  ✅ Perplexity Sonar: Parsed {sonar_count} potential earnings")
                sources_tried.append(f"Perplexity Sonar ({sonar_count} potential)")
            else:
                print(f"  ❌ Sonar HTTP {resp.status_code}")
                sources_tried.append("Sonar (API error)")
        else:
            print("  ⚠️ Perplexity key not configured")
            sources_tried.append("Sonar (no key)")
    except Exception as e:
        print(f"  ❌ Sonar error: {e}")
        sources_tried.append("Sonar (failed)")
    
    # 4. ALPHAVANTAGE
    print("\n4️⃣ ALPHAVANTAGE")
    try:
        if ALPHAVANTAGE_KEY:
            av_count = 0
            for ticker in TICKERS[:2]:
                url = f'https://www.alphavantage.co/query'
                params = {
                    'function': 'EARNINGS_CALENDAR',
                    'symbol': ticker,
                    'apikey': ALPHAVANTAGE_KEY
                }
                resp = requests.get(url, params=params, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if 'data' in data and data['data']:
                        av_count += len(data['data'])
                        print(f"  ✅ {ticker}: {len(data['data'])} earnings")
                time.sleep(0.5)
            sources_tried.append(f"AlphaVantage ({av_count} total)")
        else:
            print("  ⚠️ AlphaVantage key not configured")
            sources_tried.append("AlphaVantage (no key)")
    except Exception as e:
        print(f"  ❌ AlphaVantage error: {e}")
        sources_tried.append("AlphaVantage (failed)")
    
    # 5. MASSIVE (ALTERNATIVE)
    print("\n5️⃣ MASSIVE API")
    try:
        if MASSIVE_KEY:
            print("  ⚠️ MASSIVE - No public earnings endpoint identified")
            sources_tried.append("Massive (no earnings endpoint)")
        else:
            print("  ⚠️ Massive key not configured")
            sources_tried.append("Massive (no key)")
    except Exception as e:
        print(f"  ❌ Massive error: {e}")
        sources_tried.append("Massive (failed)")
    
    # 6. EARNINGSHUB SCRAPING
    print("\n6️⃣ EARNINGSHUB SCRAPING")
    try:
        print("  🔍 Evaluating EarningsHub page structure...")
        url = 'https://www.earningshub.com/earnings-calendar'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Try multiple selectors
            tables = soup.find_all('table')
            rows = soup.find_all('tr')
            divs = soup.find_all('div', class_=lambda x: x and 'earning' in x.lower())
            
            print(f"    - Tables found: {len(tables)}")
            print(f"    - TR elements: {len(rows)}")
            print(f"    - Earnings divs: {len(divs)}")
            
            if rows and len(rows) > 0:
                print(f"    ✅ EarningsHub: Scrapeable structure detected")
                print(f"    ✅ Sample row structure: {rows[0].text[:100]}")
                sources_tried.append("EarningsHub (scrapeable)")
            else:
                print(f"    ⚠️ EarningsHub: Structure changed (js-rendered)")
                sources_tried.append("EarningsHub (js-rendered)")
        else:
            print(f"  ❌ EarningsHub HTTP {resp.status_code}")
            sources_tried.append("EarningsHub (blocked)")
    except Exception as e:
        print(f"  ❌ EarningsHub error: {e}")
        sources_tried.append("EarningsHub (failed)")
    
    # Remove duplicates and limit
    seen = set()
    unique_earnings = []
    for e in earnings_data:
        key = (e['symbol'], e['date'])
        if key not in seen:
            seen.add(key)
            unique_earnings.append(e)
    
    unique_earnings.sort(key=lambda x: x['date'])
    today = datetime.now().strftime('%Y-%m-%d')
    final_earnings = [e for e in unique_earnings if e['date'] >= today][:50]
    
    print("\n" + "="*70)
    print(f"✅ EARNINGS SUMMARY:")
    print(f"   Total unique: {len(final_earnings)}")
    print(f"   Sources evaluated: {', '.join(sources_tried)}")
    print("="*70 + "\n")
    
    return final_earnings

# ======================== SOCIAL SENTIMENT ========================
def get_social_sentiment(ticker):
    """Sentiment with DoD + WoW + MoM"""
    
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

# ======================== INSIDER TRANSACTIONS ========================
def get_insider_transactions(ticker):
    """Insider trading activity"""
    
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
    except Exception as e:
        print(f"❌ Insider error {ticker}: {e}")
    
    insider_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== NEWS (LAST 24 HOURS ONLY) ========================
def get_stock_news(ticker):
    """Stock news from Finnhub - LAST 24 HOURS ONLY"""
    
    if ticker in news_cache:
        cached = news_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < 3600:
            return cached['data']
    
    news = []
    
    if FINNHUB_KEY:
        try:
            # LAST 24 HOURS ONLY
            from_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')
            
            url = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={FINNHUB_KEY}'
            resp = requests.get(url, timeout=5)
            
            if resp.status_code == 200:
                articles = resp.json()
                if isinstance(articles, list):
                    for article in articles[:10]:
                        pub_time = article.get('datetime', 0)
                        article_time = datetime.fromtimestamp(pub_time)
                        now = datetime.now()
                        age_hours = (now - article_time).total_seconds() / 3600
                        
                        if age_hours <= 24:  # Only last 24 hours
                            news.append({
                                'headline': article.get('headline'),
                                'summary': article.get('summary'),
                                'url': article.get('url'),
                                'source': article.get('source'),
                                'datetime': article_time.strftime('%Y-%m-%d %H:%M'),
                                'hours_ago': round(age_hours, 1)
                            })
                
                print(f"✅ News for {ticker}: {len(news)} recent (last 24h)")
        except Exception as e:
            print(f"⚠️ News error {ticker}: {e}")
    
    news_cache[ticker] = {'data': news, 'ts': datetime.now()}
    return news

# ======================== OPTIONS STRATEGIES ========================
def get_options_analysis(ticker):
    """6 Options strategies with Greeks and Greeks explanation"""
    
    if ticker in options_cache:
        cached = options_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < 86400:
            return cached['data']
    
    price = 150.0
    
    strategies = [
        {
            'type': 'Iron Condor',
            'description': 'Sell OTM call + put spreads for neutral markets',
            'setup': f'Sell ${round(price*1.05,2)} Call / Buy ${round(price*1.10,2)} Call | Sell ${round(price*0.95,2)} Put / Buy ${round(price*0.90,2)} Put',
            'max_profit': round(price * 0.02, 2),
            'max_loss': round(price * 0.03, 2),
            'probability_of_profit': '65%',
            'greeks': {'delta': '~0', 'gamma': 'Low', 'theta': '+High', 'vega': '-High'},
            'greek_explain': 'Theta decay favors seller (earn daily premium), vega short benefits from IV crush'
        },
        {
            'type': 'Call Spread (Bullish)',
            'description': 'Limited upside capture with reduced cost',
            'setup': f'Buy ${round(price,2)} Call / Sell ${round(price*1.05,2)} Call',
            'max_profit': round(price * 0.05, 2),
            'max_loss': round(price * 0.02, 2),
            'probability_of_profit': '55%',
            'greeks': {'delta': '+0.60', 'gamma': 'Positive', 'theta': 'Neutral', 'vega': 'Low'},
            'greek_explain': 'Positive delta and gamma = profits accelerate on rallies'
        },
        {
            'type': 'Put Spread (Bearish)',
            'description': 'Limited downside capture with reduced risk',
            'setup': f'Buy ${round(price,2)} Put / Sell ${round(price*0.95,2)} Put',
            'max_profit': round(price * 0.05, 2),
            'max_loss': round(price * 0.02, 2),
            'probability_of_profit': '55%',
            'greeks': {'delta': '-0.60', 'gamma': 'Positive', 'theta': 'Neutral', 'vega': 'Low'},
            'greek_explain': 'Negative delta, positive gamma = accelerates profits on sharp drops'
        },
        {
            'type': 'Call Spread (Bearish)',
            'description': 'Profit from stagnation or decline',
            'setup': f'Sell ${round(price*1.02,2)} Call / Buy ${round(price*1.07,2)} Call',
            'max_profit': round(price * 0.015, 2),
            'max_loss': round(price * 0.035, 2),
            'probability_of_profit': '60%',
            'greeks': {'delta': '-0.50', 'gamma': 'Negative', 'theta': '+High', 'vega': '-High'},
            'greek_explain': 'Negative delta (profits on drops), theta works for seller'
        },
        {
            'type': 'Put Spread (Bullish)',
            'description': 'Neutral to bullish income strategy',
            'setup': f'Sell ${round(price*0.98,2)} Put / Buy ${round(price*0.93,2)} Put',
            'max_profit': round(price * 0.015, 2),
            'max_loss': round(price * 0.035, 2),
            'probability_of_profit': '60%',
            'greeks': {'delta': '+0.50', 'gamma': 'Negative', 'theta': '+High', 'vega': '-High'},
            'greek_explain': 'Positive delta (profits on rallies), theta collected daily'
        },
        {
            'type': 'Butterfly Spread',
            'description': 'High probability, low profit defined risk',
            'setup': f'Buy ${round(price*0.98,2)} / Sell 2x ${round(price,2)} / Buy ${round(price*1.02,2)} Call',
            'max_profit': round(price * 0.04, 2),
            'max_loss': round(price * 0.01, 2),
            'probability_of_profit': '70%',
            'greeks': {'delta': '~0', 'gamma': 'Peaky', 'theta': '+Moderate', 'vega': 'Low'},
            'greek_explain': 'Gamma spike at center strike = high prob breakeven'
        }
    ]
    
    result = {
        'ticker': ticker,
        'current_price': price,
        'strategies': strategies,
        'updated': datetime.now().isoformat()
    }
    
    options_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== AI INSIGHTS ========================
def get_ai_analysis(ticker):
    """Perplexity Sonar - FIXED parsing"""
    
    if ticker in ai_insights_cache:
        cached = ai_insights_cache[ticker]
        if (datetime.now() - cached['ts']).total_seconds() < 3600:
            return cached['data']
    
    result = {'ticker': ticker, 'edge': 'Unable to analyze', 'trade': 'Monitor', 'risk': 'Standard'}
    
    if not PERPLEXITY_KEY:
        return result
    
    try:
        stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
        context = f"Your signal: {stock['signal']}" if stock else "No CSV signal"
        
        prompt = f"""Analyze {ticker} for day trading. {context}

Provide 3 SHORT lines:
EDGE: Bullish/Bearish with target
TRADE: Entry/Stop/Target prices
RISK: Low/Medium/High assessment"""
        
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
            content = resp.json()['choices'][0]['message']['content']
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            
            result = {
                'ticker': ticker,
                'edge': lines[0][:100] if len(lines) > 0 else 'Neutral',
                'trade': lines[1][:100] if len(lines) > 1 else 'Monitor',
                'risk': lines[2][:100] if len(lines) > 2 else 'Standard'
            }
            
            print(f"✅ Sonar analysis for {ticker}")
    except Exception as e:
        print(f"❌ AI error {ticker}: {e}")
    
    ai_insights_cache[ticker] = {'data': result, 'ts': datetime.now()}
    return result

# ======================== MACRO ========================
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
    results = [{'Symbol': s['symbol'], 'Signal': s['signal'], 'Score': s['inst33'], 'KeyMetric': s['key_metric']} for s in TOP_50_STOCKS]
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
    return jsonify({'ticker': ticker.upper(), 'news': news, 'count': len(news)})

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
        earnings_cache['data'] = fetch_earnings_multi_source()
        earnings_cache['timestamp'] = datetime.now()
    except Exception as e:
        print(f"❌ Refresh error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=refresh_earnings, trigger="cron", hour=9, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ======================== INITIALIZATION ========================
print("\n" + "="*70)
print("🚀 ELITE STOCK TRACKER - STARTUP")
print("="*70)

earnings_cache['data'] = fetch_earnings_multi_source()
earnings_cache['timestamp'] = datetime.now()

print(f"\n✅ Loaded {len(TICKERS)} tickers")
print(f"✅ News filter: Last 24 hours ONLY")
print(f"✅ All options restored (6 strategies)")
print(f"✅ APIs: Finnhub, Perplexity, FRED, AlphaVantage, Massive")
print("="*70 + "\n")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
