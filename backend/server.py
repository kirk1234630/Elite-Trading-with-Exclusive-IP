from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import gc
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

# ======================== CACHE ========================
price_cache = {}
recommendations_cache = {'data': [], 'timestamp': None}
news_cache = {'market_news': [], 'last_updated': None}
sentiment_cache = {}
macro_cache = {'data': {}, 'timestamp': None}
insider_cache = {}
earnings_cache = {'data': [], 'timestamp': None}
ai_insights_cache = {}

# ======================== TTL ========================
RECOMMENDATIONS_TTL = 300
SENTIMENT_TTL = 86400
MACRO_TTL = 604800
INSIDER_TTL = 86400
EARNINGS_TTL = 2592000
AI_INSIGHTS_TTL = 3600

chart_after_hours = {'enabled': True, 'last_refresh': None}

# ======================== TOP 50 STOCKS DATA ========================
TOP_50_STOCKS = [
    {'symbol': 'KO', 'inst33': 95, 'overall_score': 8, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 8, 'money_score': 4, 'alpha_score': 3, 'equity_score': 1.9, 'mean_reversion': 2.09, 'iv': 0.2, 'signal': 'STRONG_BUY', 'key_metric': 'Beverage leader - low IV, uptrend'},
    {'symbol': 'AZN', 'inst33': 95, 'overall_score': 8, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 7, 'money_score': 0, 'alpha_score': 3, 'equity_score': 1.7, 'mean_reversion': 1.57, 'iv': 0.26, 'signal': 'STRONG_BUY', 'key_metric': 'Biotech - highest institutional backing'},
    {'symbol': 'MRK', 'inst33': 90, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 5, 'money_score': 5, 'alpha_score': 3, 'equity_score': 2.0, 'mean_reversion': 1.87, 'iv': 0.33, 'signal': 'STRONG_BUY', 'key_metric': 'Pharma strong momentum'},
    # ... (rest of your 50 stocks) ...
]

def load_tickers():
    return [stock['symbol'] for stock in TOP_50_STOCKS]

def load_earnings():
    """Hardcoded earnings through March 31, 2026"""
    return [
        {'symbol': 'NVDA', 'date': '2025-11-20', 'epsEstimate': 0.81, 'company': 'NVIDIA Corporation'},
        {'symbol': 'BABA', 'date': '2025-11-25', 'epsEstimate': 2.10, 'company': 'Alibaba Group'},
        # ... (rest of your earnings) ...
    ]

TICKERS = load_tickers()
UPCOMING_EARNINGS = load_earnings()

# ... (all your existing functions and endpoints remain the same) ...

# ==================== NEWSLETTER FUNCTIONS (NEW) ====================

def calculate_newsletter_score(stock):
    """Simple 0-100 scoring based on existing data"""
    score = 0
    
    # Price momentum (40 points)
    change = stock.get('Change', 0)
    if change > 5:
        score += 40
    elif change > 2:
        score += 30
    elif change > 0:
        score += 20
    elif change > -2:
        score += 10
    
    # Institutional score (30 points)
    inst_score = stock.get('Score', 50)
    if inst_score >= 80:
        score += 30
    elif inst_score >= 60:
        score += 20
    elif inst_score >= 40:
        score += 10
    
    # Signal strength (20 points)
    signal = stock.get('Signal', 'HOLD')
    if signal == 'STRONG_BUY':
        score += 20
    elif signal == 'BUY':
        score += 15
    elif signal == 'HOLD':
        score += 10
    
    # Volume/RSI bonus (10 points)
    rsi = stock.get('RSI', 50)
    if 40 <= rsi <= 60:
        score += 10
    elif 30 <= rsi <= 70:
        score += 5
    
    return min(score, 100)

def classify_tier(score):
    """Classify stocks into tiers"""
    if score >= 85:
        return 'TIER 1-A', 'BUY NOW', '#10b981'
    elif score >= 70:
        return 'TIER 1-B', 'STRONG BUY', '#f59e0b'
    elif score >= 50:
        return 'TIER 2', 'HOLD/BUY', '#00d4ff'
    elif score >= 30:
        return 'TIER 2B', 'WATCH', '#9ca3af'
    else:
        return 'TIER 3', 'AVOID', '#ef4444'

@app.route('/api/newsletter/simple', methods=['GET'])
def get_simple_newsletter():
    """Generate newsletter with tiered stocks"""
    try:
        # Get all stocks
        if not recommendations_cache['data']:
            stocks = fetch_prices_concurrent(TICKERS)
        else:
            stocks = recommendations_cache['data']
        
        # Score and tier each stock
        newsletter_stocks = []
        for stock in stocks:
            score = calculate_newsletter_score(stock)
            tier, action, color = classify_tier(score)
            
            newsletter_stocks.append({
                'symbol': stock['Symbol'],
                'price': round(stock['Last'], 2),
                'change': round(stock['Change'], 2),
                'score': score,
                'tier': tier,
                'action': action,
                'color': color,
                'signal': stock.get('Signal', 'HOLD'),
                'key_metric': stock.get('KeyMetric', 'Standard analysis'),
                'entry': round(stock['Last'] * 0.98, 2),
                'stop': round(stock['Last'] * 0.95, 2),
                'target': round(stock['Last'] * 1.05, 2)
            })
        
        # Sort by score
        newsletter_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        # Group by tier
        tiers = {
            'TIER 1-A': [s for s in newsletter_stocks if s['tier'] == 'TIER 1-A'],
            'TIER 1-B': [s for s in newsletter_stocks if s['tier'] == 'TIER 1-B'],
            'TIER 2': [s for s in newsletter_stocks if s['tier'] == 'TIER 2'],
            'TIER 2B': [s for s in newsletter_stocks if s['tier'] == 'TIER 2B'],
            'TIER 3': [s for s in newsletter_stocks if s['tier'] == 'TIER 3']
        }
        
        # Summary
        total_stocks = len(newsletter_stocks)
        tier1a_count = len(tiers['TIER 1-A'])
        avg_score = sum(s['score'] for s in newsletter_stocks) / total_stocks if total_stocks > 0 else 0
        
        return jsonify({
            'date': datetime.now().strftime('%B %d, %Y'),
            'week': datetime.now().isocalendar()[1],
            'tiers': tiers,
            'summary': {
                'total_stocks': total_stocks,
                'tier_1a_count': tier1a_count,
                'tier_1b_count': len(tiers['TIER 1-B']),
                'avg_score': round(avg_score, 1),
                'top_pick': newsletter_stocks[0] if newsletter_stocks else None
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Newsletter error: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== END NEWSLETTER FUNCTIONS ====================
# ==================== NEWSLETTER FUNCTIONS (NEW) ====================

def calculate_newsletter_score(stock):
    """Simple 0-100 scoring based on existing data"""
    score = 0
    
    # Price momentum (40 points)
    change = stock.get('Change', 0)
    if change > 5:
        score += 40
    elif change > 2:
        score += 30
    elif change > 0:
        score += 20
    elif change > -2:
        score += 10
    
    # Institutional score (30 points)
    inst_score = stock.get('Score', 50)
    if inst_score >= 80:
        score += 30
    elif inst_score >= 60:
        score += 20
    elif inst_score >= 40:
        score += 10
    
    # Signal strength (20 points)
    signal = stock.get('Signal', 'HOLD')
    if signal == 'STRONG_BUY':
        score += 20
    elif signal == 'BUY':
        score += 15
    elif signal == 'HOLD':
        score += 10
    
    # Volume/RSI bonus (10 points)
    rsi = stock.get('RSI', 50)
    if 40 <= rsi <= 60:
        score += 10
    elif 30 <= rsi <= 70:
        score += 5
    
    return min(score, 100)

def classify_tier(score):
    """Classify stocks into tiers"""
    if score >= 85:
        return 'TIER 1-A', 'BUY NOW', '#10b981'
    elif score >= 70:
        return 'TIER 1-B', 'STRONG BUY', '#f59e0b'
    elif score >= 50:
        return 'TIER 2', 'HOLD/BUY', '#00d4ff'
    elif score >= 30:
        return 'TIER 2B', 'WATCH', '#9ca3af'
    else:
        return 'TIER 3', 'AVOID', '#ef4444'

@app.route('/api/newsletter/simple', methods=['GET'])
def get_simple_newsletter():
    """Generate newsletter with tiered stocks"""
    try:
        # Get all stocks
        if not recommendations_cache['data']:
            stocks = fetch_prices_concurrent(TICKERS)
        else:
            stocks = recommendations_cache['data']
        
        # Score and tier each stock
        newsletter_stocks = []
        for stock in stocks:
            score = calculate_newsletter_score(stock)
            tier, action, color = classify_tier(score)
            
            newsletter_stocks.append({
                'symbol': stock['Symbol'],
                'price': round(stock['Last'], 2),
                'change': round(stock['Change'], 2),
                'score': score,
                'tier': tier,
                'action': action,
                'color': color,
                'signal': stock.get('Signal', 'HOLD'),
                'key_metric': stock.get('KeyMetric', 'Standard analysis'),
                'entry': round(stock['Last'] * 0.98, 2),
                'stop': round(stock['Last'] * 0.95, 2),
                'target': round(stock['Last'] * 1.05, 2)
            })
        
        # Sort by score
        newsletter_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        # Group by tier
        tiers = {
            'TIER 1-A': [s for s in newsletter_stocks if s['tier'] == 'TIER 1-A'],
            'TIER 1-B': [s for s in newsletter_stocks if s['tier'] == 'TIER 1-B'],
            'TIER 2': [s for s in newsletter_stocks if s['tier'] == 'TIER 2'],
            'TIER 2B': [s for s in newsletter_stocks if s['tier'] == 'TIER 2B'],
            'TIER 3': [s for s in newsletter_stocks if s['tier'] == 'TIER 3']
        }
        
        # Summary
        total_stocks = len(newsletter_stocks)
        tier1a_count = len(tiers['TIER 1-A'])
        avg_score = sum(s['score'] for s in newsletter_stocks) / total_stocks if total_stocks > 0 else 0
        
        return jsonify({
            'date': datetime.now().strftime('%B %d, %Y'),
            'week': datetime.now().isocalendar()[1],
            'tiers': tiers,
            'summary': {
                'total_stocks': total_stocks,
                'tier_1a_count': tier1a_count,
                'tier_1b_count': len(tiers['TIER 1-B']),
                'avg_score': round(avg_score, 1),
                'top_pick': newsletter_stocks[0] if newsletter_stocks else None
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Newsletter error: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== END NEWSLETTER FUNCTIONS ====================

@app.route('/health', methods=['GET'])


def health_check():
    return jsonify({
        'status': 'healthy',
        'scheduler_running': scheduler.running,
        'endpoints': [
            '/api/recommendations',
            '/api/newsletter/simple',
            '/api/stock-price/<ticker>',
            '/api/social-sentiment/<ticker>'
        ]
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
