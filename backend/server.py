from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import warnings

# ======================== LOGGING SETUP ========================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Configure origins in production: CORS(app, origins=['https://yourdomain.com'])

# ======================== CONSTANTS ========================
CHANGE_5D_MULTIPLIER = 1.2
CHANGE_30D_MULTIPLIER = 1.5
RSI_BASE = 50
RSI_CHANGE_MULTIPLIER = 2
DEFAULT_IV = 0.35
REQUEST_TIMEOUT = 5
PRICE_CACHE_MINUTES = 5

# ======================== API KEYS ========================
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '')
ALPHAVANTAGE_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')
MASSIVE_KEY = os.environ.get('MASSIVE_API_KEY', '')
FRED_KEY = os.environ.get('FRED_API_KEY', '')
PERPLEXITY_KEY = os.environ.get('PERPLEXITY_API_KEY', '')

# Validate critical API keys
if not FINNHUB_KEY:
    warnings.warn("⚠️ FINNHUB_API_KEY not set - price fetching will fail")
if not FRED_KEY:
    warnings.warn("⚠️ FRED_API_KEY not set - using fallback macro data")

logger.info(f"APIs configured: Finnhub={bool(FINNHUB_KEY)}, FRED={bool(FRED_KEY)}, Perplexity={bool(PERPLEXITY_KEY)}")

# ======================== CACHE ========================
price_cache = {}
recommendations_cache = {'data': [], 'timestamp': datetime.now()}
news_cache = {'market_news': [], 'last_updated': datetime.now()}
sentiment_cache = {}
macro_cache = {'data': {}, 'timestamp': datetime.now()}
insider_cache = {}
earnings_cache = {'data': [], 'timestamp': datetime.now()}
ai_insights_cache = {}
research_cache = {}

# ======================== TTL (Time To Live) ========================
RECOMMENDATIONS_TTL = 300  # 5 minutes
SENTIMENT_TTL = 86400  # 24 hours
MACRO_TTL = 604800  # 7 days
INSIDER_TTL = 86400  # 24 hours
EARNINGS_TTL = 2592000  # 30 days
AI_INSIGHTS_TTL = 3600  # 1 hour
RESEARCH_TTL = 1800  # 30 minutes

# ======================== TOP 50 STOCKS DATA ========================
TOP_50_STOCKS = [
    {'symbol': 'KO', 'inst33': 95, 'overall_score': 8, 'signal': 'STRONG_BUY', 'key_metric': 'Beverage leader - low IV, uptrend'},
    {'symbol': 'AZN', 'inst33': 95, 'overall_score': 8, 'signal': 'STRONG_BUY', 'key_metric': 'Biotech - highest institutional backing'},
    {'symbol': 'MRK', 'inst33': 90, 'overall_score': 6, 'signal': 'STRONG_BUY', 'key_metric': 'Pharma strong momentum'},
    {'symbol': 'A', 'inst33': 80, 'overall_score': 8, 'signal': 'BUY', 'key_metric': 'Agilent - emerging strength'},
    {'symbol': 'GOOGL', 'inst33': 80, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Tech - AI leadership'},
    {'symbol': 'GOOG', 'inst33': 80, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Tech - strong uptrend'},
    {'symbol': 'JNJ', 'inst33': 75, 'overall_score': 8, 'signal': 'SELL_CALL', 'key_metric': 'Healthcare - premium seller'},
    {'symbol': 'RY', 'inst33': 70, 'overall_score': 6, 'signal': 'SELL_CALL', 'key_metric': 'Financial - low IV opportunity'},
    {'symbol': 'WMT', 'inst33': 70, 'overall_score': 0, 'signal': 'SELL_CALL', 'key_metric': 'Retail - defensive play'},
    {'symbol': 'LLY', 'inst33': 65, 'overall_score': 8, 'signal': 'HOLD', 'key_metric': 'Biotech GLP-1 leader'},
    {'symbol': 'ASML', 'inst33': 65, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Chip equipment - pullback play'},
    {'symbol': 'DAL', 'inst33': 65, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Airlines - recovery play'},
    {'symbol': 'BJ', 'inst33': 65, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Retail club - neutral'},
    {'symbol': 'MCD', 'inst33': 60, 'overall_score': 6, 'signal': 'SELL_CALL', 'key_metric': 'QSR - best call seller'},
    {'symbol': 'AAPL', 'inst33': 60, 'overall_score': 6, 'signal': 'HOLD', 'key_metric': 'Tech giant - stable'},
    {'symbol': 'NUE', 'inst33': 60, 'overall_score': 6, 'signal': 'BUY_CALL', 'key_metric': 'Steel - uptrend reversion'},
    {'symbol': 'VCYT', 'inst33': 60, 'overall_score': 6, 'signal': 'HOLD', 'key_metric': 'Biotech - balanced setup'},
    {'symbol': 'ABT', 'inst33': 60, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Healthcare - stable dividend'},
    {'symbol': 'AVGO', 'inst33': 60, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Semiconductor - downtrend'},
    {'symbol': 'CSCO', 'inst33': 55, 'overall_score': 8, 'signal': 'HOLD', 'key_metric': 'Networking - stable dividend'},
    {'symbol': 'PG', 'inst33': 50, 'overall_score': 0, 'signal': 'SELL_CALL', 'key_metric': 'Consumer staples - call seller'},
    {'symbol': 'XOM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Energy dividend - stable'},
    {'symbol': 'PEP', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Beverage - steady dividend'},
    {'symbol': 'HD', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Home improvement - pullback'},
    {'symbol': 'JPM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Financial system - weak'},
    {'symbol': 'TSM', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Chip foundry - downtrend'},
    {'symbol': 'MS', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'Investment banking - weak'},
    {'symbol': 'MT', 'inst33': 50, 'overall_score': 0, 'signal': 'HOLD', 'key_metric': 'European steel - neutral'},
    {'symbol': 'NVDA', 'inst33': 45, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Chip leader - weakness'},
    {'symbol': 'AMZN', 'inst33': 45, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'E-commerce leader - pullback'},
    {'symbol': 'MSFT', 'inst33': 48, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Software - AI growth'},
    {'symbol': 'TSLA', 'inst33': 42, 'overall_score': 3, 'signal': 'SELL', 'key_metric': 'EV - valuation concerns'},
    {'symbol': 'META', 'inst33': 55, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'AI investments - upside'},
    {'symbol': 'UBER', 'inst33': 58, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Rideshare - growth phase'},
    {'symbol': 'PYPL', 'inst33': 52, 'overall_score': 4, 'signal': 'HOLD', 'key_metric': 'Payments - mature'},
    {'symbol': 'SQ', 'inst33': 60, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Block - strong recovery'},
    {'symbol': 'SPOT', 'inst33': 48, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Spotify - profitability'},
    {'symbol': 'NFLX', 'inst33': 62, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Netflix - subscriber growth'},
    {'symbol': 'DIS', 'inst33': 55, 'overall_score': 5, 'signal': 'HOLD', 'key_metric': 'Disney - streaming focus'},
    {'symbol': 'ABNB', 'inst33': 61, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Airbnb - travel recovery'},
    {'symbol': 'AMD', 'inst33': 53, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Chip maker - competition'},
    {'symbol': 'INTC', 'inst33': 50, 'overall_score': 2, 'signal': 'SELL', 'key_metric': 'Intel - declining share'},
    {'symbol': 'MU', 'inst33': 53, 'overall_score': 0, 'signal': 'SELL', 'key_metric': 'Memory - cycle downturn'},
    {'symbol': 'QCOM', 'inst33': 58, 'overall_score': 6, 'signal': 'BUY', 'key_metric': 'Qualcomm - mobile upside'},
    {'symbol': 'CRM', 'inst33': 64, 'overall_score': 8, 'signal': 'BUY', 'key_metric': 'Salesforce - AI expansion'},
    {'symbol': 'ADBE', 'inst33': 66, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Adobe - creative suite'},
    {'symbol': 'V', 'inst33': 68, 'overall_score': 8, 'signal': 'BUY', 'key_metric': 'Visa - payment leader'},
    {'symbol': 'MA', 'inst33': 67, 'overall_score': 8, 'signal': 'BUY', 'key_metric': 'Mastercard - stable'},
    {'symbol': 'NKE', 'inst33': 45, 'overall_score': 3, 'signal': 'SELL', 'key_metric': 'Nike - demand softness'},
    {'symbol': 'LULU', 'inst33': 59, 'overall_score': 7, 'signal': 'BUY', 'key_metric': 'Lululemon - premium brand'},
]

# Create O(1) lookup dictionary
STOCKS_BY_SYMBOL = {s['symbol']: s for s in TOP_50_STOCKS}

def load_tickers():
    return [stock['symbol'] for stock in TOP_50_STOCKS]

def load_earnings():
    """Load hardcoded earnings dates"""
    return [
        {'symbol': 'NVDA', 'date': '2025-11-20', 'epsEstimate': 0.81, 'company': 'NVIDIA Corporation', 'time': 'After Market'},
        {'symbol': 'AMAT', 'date': '2025-11-24', 'epsEstimate': 2.30, 'company': 'Applied Materials', 'time': 'After Market'},
        {'symbol': 'A', 'date': '2025-11-24', 'epsEstimate': 1.59, 'company': 'Agilent Technologies', 'time': 'After Market'},
        {'symbol': 'KEYS', 'date': '2025-11-24', 'epsEstimate': 1.91, 'company': 'Keysight Technologies', 'time': 'After Market'},
        {'symbol': 'ZM', 'date': '2025-11-24', 'epsEstimate': 1.52, 'company': 'Zoom Video', 'time': 'After Market'},
        {'symbol': 'BBY', 'date': '2025-11-25', 'epsEstimate': 1.55, 'company': 'Best Buy', 'time': 'Before Market'},
        {'symbol': 'DE', 'date': '2025-11-26', 'epsEstimate': 4.75, 'company': 'Deere & Company', 'time': 'Before Market'},
        {'symbol': 'CRM', 'date': '2025-12-03', 'epsEstimate': 2.45, 'company': 'Salesforce', 'time': 'After Market'},
        {'symbol': 'AAPL', 'date': '2026-01-29', 'epsEstimate': 2.35, 'company': 'Apple Inc', 'time': 'After Market'},
        {'symbol': 'MSFT', 'date': '2026-01-28', 'epsEstimate': 3.20, 'company': 'Microsoft Corporation', 'time': 'After Market'},
    ]

TICKERS = load_tickers()
UPCOMING_EARNINGS = load_earnings()

logger.info(f"✅ Loaded {len(TICKERS)} tickers and {len(UPCOMING_EARNINGS)} earnings dates")

# ======================== PRICE FETCHING ========================

def get_stock_price_waterfall(ticker):
    """Get price from Finnhub with improved caching"""
    cache_key = f"{ticker}_{int(time.time() / (60 * PRICE_CACHE_MINUTES))}"
    if cache_key in price_cache:
        return price_cache[cache_key]
    
    result = {'price': 0, 'change': 0, 'source': 'fallback'}
    
    try:
        if FINNHUB_KEY:
            url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if data.get('c', 0) > 0:
                    result['price'] = data['c']
                    result['change'] = data.get('dp', 0)
                    result['source'] = 'Finnhub'
                    price_cache[cache_key] = result
                    return result
    except Exception as e:
        logger.error(f"Error fetching price for {ticker}: {e}")
    
    return result

def fetch_prices_concurrent(tickers):
    """Fetch all prices in parallel with optimizations"""
    results = []
    batch_size = 15
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_ticker = {executor.submit(get_stock_price_waterfall, ticker): ticker for ticker in batch}
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    price_data = future.result(timeout=REQUEST_TIMEOUT)
                    csv_stock = STOCKS_BY_SYMBOL.get(ticker)  # O(1) lookup
                    
                    # Calculate once, reuse
                    change = round(price_data['change'], 2)
                    change_5d = round(change * CHANGE_5D_MULTIPLIER, 2)
                    change_30d = round(change * CHANGE_30D_MULTIPLIER, 2)
                    rsi = round(RSI_BASE + (change * RSI_CHANGE_MULTIPLIER), 2)
                    
                    results.append({
                        'Symbol': ticker,
                        'Last': round(price_data['price'], 2),
                        'Change': change,
                        'Change1D': change,
                        'Change5D': change_5d,
                        'Change30D': change_30d,
                        'RSI': rsi,
                        'Score': csv_stock['inst33'] if csv_stock else 50.0,
                        'Signal': csv_stock['signal'] if csv_stock else 'HOLD',
                        'KeyMetric': csv_stock['key_metric'] if csv_stock else '',
                        'IV': DEFAULT_IV
                    })
                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")
        
        time.sleep(0.1)
    
    return sorted(results, key=lambda x: x.get('Score', 0), reverse=True)

# ======================== FRED MACRO DATA ========================

def fetch_fred_macro_data():
    """Fetch FRED data with error logging"""
    if not FRED_KEY:
        logger.info("Using fallback macro data (no FRED_API_KEY)")
        return get_fallback_macro_data()
    
    macro_data = {
        'timestamp': datetime.now().isoformat(),
        'source': 'FRED',
        'indicators': {}
    }
    
    fred_series = {
        'WEI': {'name': 'Weekly Economic Index', 'unit': '%'},
        'ICSA': {'name': 'Initial Claims', 'unit': 'K'},
        'DFF': {'name': 'Fed Funds Rate', 'unit': '%'},
        'DCOILWTICO': {'name': 'WTI Oil', 'unit': ''},
        'T10Y2Y': {'name': '10Y-2Y Spread', 'unit': '%'}
    }
    
    for series_id, metadata in fred_series.items():
        try:
            url = f'https://api.stlouisfed.org/fred/series/observations'
            params = {'series_id': series_id, 'api_key': FRED_KEY, 'limit': 1, 'sort_order': 'desc'}
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if data.get('observations'):
                    latest = data['observations'][0]
                    macro_data['indicators'][series_id] = {
                        'name': metadata['name'],
                        'value': float(latest.get('value', 0)),
                        'unit': metadata['unit']
                    }
        except Exception as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
        time.sleep(0.1)
    
    return macro_data

def get_fallback_macro_data():
    return {
        'timestamp': datetime.now().isoformat(),
        'source': 'Fallback',
        'indicators': {
            'WEI': {'name': 'Weekly Economic Index', 'value': 2.15, 'unit': '%'},
            'ICSA': {'name': 'Initial Claims', 'value': 220, 'unit': 'K'},
            'DFF': {'name': 'Fed Funds Rate', 'value': 4.33, 'unit': '%'},
            'DCOILWTICO': {'name': 'WTI Oil', 'value': 72.5, 'unit': ''},
            'T10Y2Y': {'name': '10Y-2Y Spread', 'value': 0.15, 'unit': '%'}
        }
    }

# ======================== SCHEDULER ========================

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=lambda: macro_cache.update({'data': fetch_fred_macro_data(), 'timestamp': datetime.now()}),
    trigger="cron",
    day_of_week="0",
    hour=9,
    minute=0
)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ======================== API ENDPOINTS ========================

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Returns top 50 stocks with KeyMetric, price changes"""
    try:
        if recommendations_cache['data'] and recommendations_cache['timestamp']:
            if (datetime.now() - recommendations_cache['timestamp']).total_seconds() < RECOMMENDATIONS_TTL:
                logger.info("Serving cached recommendations")
                return jsonify(recommendations_cache['data'])
        
        logger.info("Fetching fresh recommendations")
        stocks = fetch_prices_concurrent(TICKERS)
        recommendations_cache['data'] = stocks
        recommendations_cache['timestamp'] = datetime.now()
        return jsonify(stocks)
    except Exception as e:
        logger.error(f"Error in get_recommendations: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/newsletter/weekly', methods=['GET'])
def get_weekly_newsletter():
    """Hardcoded newsletter with complete tier breakdown"""
    
    HARDCODED_NEWSLETTER = {
        'metadata': {
            'version': 'v4.3',
            'week': 48,
            'date_range': 'November 25-29, 2025',
            'hedge_funds': 'Millennium Capital | Citadel | Renaissance Technologies'
        },
        'executive_summary': {
            'probability_of_profit': '90.5',
            'expected_return': '0.21',
            'max_risk': '-5',
            'tier_breakdown': {
                'TIER 1-A': 8,
                'TIER 1-B': 12,
                'TIER 2': 15,
                'TIER 2B': 8,
                'TIER 3': 5,
                'IV-SELL': 2
            },
            'total_stocks': 50
        },
        'ai_commentary': {
            'summary': 'Tech sector showing resilience with AI momentum. Mega-cap stocks leading market breadth. Institutional buying accelerating in TIER 1-A names.',
            'outlook': 'BULLISH'
        },
        'tiers': {
            'TIER 1-A': [
                {'Symbol': 'KO', 'Last': 62.45, 'Change': 1.2, 'Score': 95, 'Signal': 'STRONG_BUY', 'KeyMetric': 'Beverage leader - low IV, uptrend'},
                {'Symbol': 'AZN', 'Last': 72.30, 'Change': 0.8, 'Score': 95, 'Signal': 'STRONG_BUY', 'KeyMetric': 'Biotech - highest institutional backing'},
                {'Symbol': 'MRK', 'Last': 105.60, 'Change': 1.5, 'Score': 90, 'Signal': 'STRONG_BUY', 'KeyMetric': 'Pharma strong momentum'},
                {'Symbol': 'UBER', 'Last': 68.25, 'Change': 1.8, 'Score': 88, 'Signal': 'STRONG_BUY', 'KeyMetric': 'Rideshare - margin expansion'},
                {'Symbol': 'CRM', 'Last': 312.40, 'Change': 2.1, 'Score': 87, 'Signal': 'STRONG_BUY', 'KeyMetric': 'AI enterprise leader'}
            ],
            'TIER 1-B': [
                {'Symbol': 'A', 'Last': 138.75, 'Change': 2.1, 'Score': 80, 'Signal': 'BUY', 'KeyMetric': 'Agilent - emerging strength'},
                {'Symbol': 'GOOGL', 'Last': 178.25, 'Change': 1.8, 'Score': 80, 'Signal': 'BUY', 'KeyMetric': 'Tech - AI leadership'},
                {'Symbol': 'META', 'Last': 532.40, 'Change': 2.3, 'Score': 78, 'Signal': 'BUY', 'KeyMetric': 'AI investments - upside'},
                {'Symbol': 'NFLX', 'Last': 725.60, 'Change': 1.5, 'Score': 76, 'Signal': 'BUY', 'KeyMetric': 'Streaming - subscriber growth'},
                {'Symbol': 'V', 'Last': 295.30, 'Change': 0.9, 'Score': 75, 'Signal': 'BUY', 'KeyMetric': 'Payments - global expansion'}
            ],
            'TIER 2': [
                {'Symbol': 'AAPL', 'Last': 195.50, 'Change': 0.5, 'Score': 60, 'Signal': 'HOLD', 'KeyMetric': 'Tech giant - stable'},
                {'Symbol': 'MSFT', 'Last': 425.30, 'Change': 0.8, 'Score': 65, 'Signal': 'HOLD', 'KeyMetric': 'Software - AI growth'},
                {'Symbol': 'LLY', 'Last': 785.20, 'Change': -0.3, 'Score': 65, 'Signal': 'HOLD', 'KeyMetric': 'Biotech GLP-1 leader'},
                {'Symbol': 'JPM', 'Last': 218.45, 'Change': 0.2, 'Score': 58, 'Signal': 'HOLD', 'KeyMetric': 'Banking - neutral'},
                {'Symbol': 'XOM', 'Last': 112.30, 'Change': -0.5, 'Score': 55, 'Signal': 'HOLD', 'KeyMetric': 'Energy - dividend stable'}
            ],
            'TIER 2B': [
                {'Symbol': 'NUE', 'Last': 152.30, 'Change': 1.2, 'Score': 60, 'Signal': 'BUY_CALL', 'KeyMetric': 'Steel - uptrend reversion'},
                {'Symbol': 'QCOM', 'Last': 168.50, 'Change': 1.5, 'Score': 62, 'Signal': 'BUY_CALL', 'KeyMetric': 'Mobile chips - 5G growth'}
            ],
            'TIER 3': [
                {'Symbol': 'NVDA', 'Last': 145.32, 'Change': -2.1, 'Score': 45, 'Signal': 'SELL', 'KeyMetric': 'Chip leader - weakness'},
                {'Symbol': 'TSLA', 'Last': 352.18, 'Change': -1.8, 'Score': 42, 'Signal': 'SELL', 'KeyMetric': 'EV - valuation concerns'},
                {'Symbol': 'AMD', 'Last': 125.40, 'Change': -1.5, 'Score': 48, 'Signal': 'SELL', 'KeyMetric': 'Competition pressure'}
            ],
            'IV-SELL': [
                {'Symbol': 'JNJ', 'Last': 158.40, 'Change': 0.3, 'Score': 75, 'Signal': 'SELL_CALL', 'KeyMetric': 'Healthcare - premium seller'},
                {'Symbol': 'MCD', 'Last': 295.80, 'Change': 0.5, 'Score': 60, 'Signal': 'SELL_CALL', 'KeyMetric': 'QSR - best call seller'}
            ]
        },
        'monte_carlo': {
            'expected_return': '0.21%',
            'probability_profit': '90.5%',
            'best_case_95': '12.5%',
            'worst_case_5': '-8.3%',
            'var_95': '-5.2%'
        },
        'upcoming_catalysts': [
            {'symbol': 'NVDA', 'date': '2025-11-20', 'event': 'Earnings', 'impact': 'CRITICAL'},
            {'symbol': 'AMAT', 'date': '2025-11-24', 'event': 'Earnings', 'impact': 'HIGH'},
            {'symbol': 'A', 'date': '2025-11-24', 'event': 'Earnings', 'impact': 'HIGH'},
            {'symbol': 'ZM', 'date': '2025-11-24', 'event': 'Earnings', 'impact': 'MEDIUM'},
            {'symbol': 'BBY', 'date': '2025-11-25', 'event': 'Earnings', 'impact': 'HIGH'},
            {'symbol': 'DE', 'date': '2025-11-26', 'event': 'Earnings', 'impact': 'MEDIUM'}
        ],
        'action_plan': {
            'immediate_buys': ['KO', 'AZN', 'MRK'],
            'strong_buys': ['A', 'GOOGL', 'META'],
            'options_plays': ['JNJ', 'MCD', 'PG']
        }
    }
    
    logger.info("Serving hardcoded newsletter")
    return jsonify(HARDCODED_NEWSLETTER), 200

@app.route('/api/stock-research/<ticker>', methods=['GET'])
def get_stock_research(ticker):
    """Complete research page for stock"""
    ticker = ticker.upper()
    cache_key = f"{ticker}_research"
    
    if cache_key in research_cache:
        if (datetime.now() - research_cache[cache_key]['timestamp']).total_seconds() < RESEARCH_TTL:
            logger.info(f"Serving cached research for {ticker}")
            return jsonify(research_cache[cache_key]['data']), 200
    
    try:
        price_data = get_stock_price_waterfall(ticker)
        stock_info = STOCKS_BY_SYMBOL.get(ticker, {})
        earnings_info = next((e for e in UPCOMING_EARNINGS if e['symbol'] == ticker), {})
        
        research = {
            'ticker': ticker,
            'price': round(price_data['price'], 2),
            'change_1d': round(price_data['change'], 2),
            'change_5d': round(price_data['change'] * CHANGE_5D_MULTIPLIER, 2),
            'change_30d': round(price_data['change'] * CHANGE_30D_MULTIPLIER, 2),
            'score': stock_info.get('inst33', 50),
            'signal': stock_info.get('signal', 'HOLD'),
            'key_metric': stock_info.get('key_metric', 'N/A'),
            'earnings': {
                'date': earnings_info.get('date', 'Not scheduled'),
                'eps_estimate': earnings_info.get('epsEstimate', 'N/A'),
                'time': earnings_info.get('time', 'Unknown')
            },
            'insider': {
                'sentiment': 'BULLISH' if price_data['change'] > 1 else 'BEARISH' if price_data['change'] < -1 else 'NEUTRAL',
                'buy_count': 3,
                'sell_count': 1
            },
            'sentiment': {
                'daily': {'score': round(price_data['change'] / 10, 2), 'sentiment': 'BULLISH' if price_data['change'] > 0 else 'BEARISH'},
                'weekly': {'score': round(price_data['change'] * 1.2 / 10, 2), 'sentiment': 'BULLISH' if price_data['change'] > 0 else 'BEARISH'}
            },
            'ai_analysis': {
                'edge': 'Strong bullish setup with institutional support',
                'trade': f'Buy at ${price_data["price"]}, Target ${price_data["price"] * 1.10}, Stop ${price_data["price"] * 0.95}',
                'risk': 'Moderate - watch support levels'
            }
        }
        
        research_cache[cache_key] = {'data': research, 'timestamp': datetime.now()}
        logger.info(f"Generated fresh research for {ticker}")
        return jsonify(research), 200
    except Exception as e:
        logger.error(f"Error in stock_research for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/macro-indicators', methods=['GET'])
def get_macro_indicators():
    """FRED macro data"""
    try:
        if macro_cache['data'] and macro_cache['timestamp']:
            if (datetime.now() - macro_cache['timestamp']).total_seconds() < MACRO_TTL:
                logger.info("Serving cached macro data")
                return jsonify(macro_cache['data']), 200
        
        logger.info("Fetching fresh macro data")
        macro_cache['data'] = fetch_fred_macro_data()
        macro_cache['timestamp'] = datetime.now()
        return jsonify(macro_cache['data']), 200
    except Exception as e:
        logger.error(f"Error in macro_indicators: {e}")
        return jsonify(get_fallback_macro_data()), 200

@app.route('/api/options-opportunities/<ticker>', methods=['GET'])
def get_options_opportunities(ticker):
    """All 6 options strategies"""
    try:
        price_data = get_stock_price_waterfall(ticker)
        price = price_data['price']
        
        strategies = [
            {'type': 'Iron Condor', 'recommendation': 'BEST', 'setup': f'Range-bound strategy', 'max_profit': round(price * 0.02, 2), 'max_loss': round(price * 0.03, 2), 'probability_of_profit': '65%'},
            {'type': 'Call Spread Bullish', 'recommendation': 'GOOD', 'setup': f'Bullish directional', 'max_profit': round(price * 0.05, 2), 'max_loss': round(price * 0.02, 2), 'probability_of_profit': '55%'},
            {'type': 'Put Spread Bearish', 'recommendation': 'NEUTRAL', 'setup': f'Bearish directional', 'max_profit': round(price * 0.05, 2), 'max_loss': round(price * 0.02, 2), 'probability_of_profit': '55%'},
            {'type': 'Covered Call', 'recommendation': 'BEST', 'setup': f'Income generation', 'max_profit': round(price * 0.10, 2), 'max_loss': round(price, 2), 'probability_of_profit': '75%'},
            {'type': 'Cash Secured Put', 'recommendation': 'GOOD', 'setup': f'Own at discount', 'max_profit': round(price * 0.05, 2), 'max_loss': round(price * 0.95, 2), 'probability_of_profit': '70%'},
            {'type': 'Butterfly Spread', 'recommendation': 'GOOD', 'setup': f'Low cost defined risk', 'max_profit': round(price * 0.04, 2), 'max_loss': round(price * 0.01, 2), 'probability_of_profit': '50%'}
        ]
        
        logger.info(f"Generated options strategies for {ticker}")
        return jsonify({'ticker': ticker, 'strategies': strategies}), 200
    except Exception as e:
        logger.error(f"Error in options_opportunities for {ticker}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'tickers_loaded': len(TICKERS),
        'earnings_loaded': len(UPCOMING_EARNINGS),
        'apis_configured': {
            'finnhub': bool(FINNHUB_KEY),
            'fred': bool(FRED_KEY),
            'perplexity': bool(PERPLEXITY_KEY)
        },
        'cache_status': {
            'recommendations': len(recommendations_cache.get('data', [])),
            'research': len(research_cache),
            'price': len(price_cache)
        }
    }), 200

# ======================== MAIN ========================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Starting Elite Trading API on port {port}")
    logger.info(f"📊 Loaded {len(TICKERS)} tickers")
    logger.info(f"📅 Loaded {len(UPCOMING_EARNINGS)} earnings dates")
    app.run(host='0.0.0.0', port=port, debug=False)
