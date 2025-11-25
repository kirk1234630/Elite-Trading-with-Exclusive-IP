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
    {'symbol': 'A', 'inst33': 80, 'overall_score': 8, 'master_score': 4, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 7, 'money_score': 4, 'alpha_score': 3, 'equity_score': 2.7, 'mean_reversion': 2.19, 'iv': 0.4, 'signal': 'BUY', 'key_metric': 'Agilent - emerging strength'},
    {'symbol': 'GOOGL', 'inst33': 80, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 7, 'money_score': 4, 'alpha_score': 3, 'equity_score': 0.8, 'mean_reversion': 2.19, 'iv': 0.41, 'signal': 'BUY', 'key_metric': 'Tech - AI leadership'},
    {'symbol': 'GOOG', 'inst33': 80, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 6, 'money_score': 4, 'alpha_score': 3, 'equity_score': 0.8, 'mean_reversion': 2.16, 'iv': 0.41, 'signal': 'BUY', 'key_metric': 'Tech - strong uptrend'},
    {'symbol': 'JNJ', 'inst33': 75, 'overall_score': 8, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 8, 'money_score': 4, 'alpha_score': 2, 'equity_score': 1.83, 'mean_reversion': 1.83, 'iv': 0.22, 'signal': 'SELL_CALL', 'key_metric': 'Healthcare - premium seller'},
    {'symbol': 'RY', 'inst33': 70, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 8, 'money_score': 4, 'alpha_score': 3, 'equity_score': 1.9, 'mean_reversion': 2.1, 'iv': 0.21, 'signal': 'SELL_CALL', 'key_metric': 'Financial - low IV opportunity'},
    {'symbol': 'WMT', 'inst33': 70, 'overall_score': 0, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 6, 'money_score': 4, 'alpha_score': 3, 'equity_score': 1.75, 'mean_reversion': 1.75, 'iv': 0.27, 'signal': 'SELL_CALL', 'key_metric': 'Retail - defensive play'},
    {'symbol': 'LLY', 'inst33': 65, 'overall_score': 8, 'master_score': 4, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 7, 'money_score': 4, 'alpha_score': 3, 'equity_score': 2.7, 'mean_reversion': 1.34, 'iv': 0.38, 'signal': 'HOLD', 'key_metric': 'Biotech GLP-1 leader'},
    {'symbol': 'ASML', 'inst33': 65, 'overall_score': 0, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 6, 'money_score': 4, 'alpha_score': 2, 'equity_score': -2.34, 'mean_reversion': -2.34, 'iv': 0.47, 'signal': 'HOLD', 'key_metric': 'Chip equipment - pullback play'},
    {'symbol': 'DAL', 'inst33': 65, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': 0.41, 'iv': 0.59, 'signal': 'HOLD', 'key_metric': 'Airlines - recovery play'},
    {'symbol': 'BJ', 'inst33': 65, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': 0.05, 'iv': 0.35, 'signal': 'HOLD', 'key_metric': 'Retail club - neutral'},
    {'symbol': 'SNDK', 'inst33': 63, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -0.75, 'iv': 1.3, 'signal': 'HOLD', 'key_metric': 'Storage - high IV volatility'},
    {'symbol': 'OKLO', 'inst33': 63, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -1.49, 'iv': 1.21, 'signal': 'HOLD', 'key_metric': 'Nuclear energy - emerging'},
    {'symbol': 'ARM', 'inst33': 63, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -1.52, 'iv': 0.67, 'signal': 'SELL', 'key_metric': 'Chip design - bearish setup'},
    {'symbol': 'BE', 'inst33': 63, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -1.93, 'iv': 1.39, 'signal': 'SELL', 'key_metric': 'EV - downtrend high IV'},
    {'symbol': 'CRWD', 'inst33': 60, 'overall_score': 8, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 8, 'money_score': 4, 'alpha_score': 3, 'equity_score': 1.83, 'mean_reversion': 1.83, 'iv': 0.23, 'signal': 'SELL_CALL', 'key_metric': 'Cybersecurity - premium seller'},
    {'symbol': 'MCD', 'inst33': 60, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 5, 'money_score': 3, 'alpha_score': 3, 'equity_score': 1.48, 'mean_reversion': 1.48, 'iv': 0.2, 'signal': 'SELL_CALL', 'key_metric': 'QSR - best call seller'},
    {'symbol': 'AAPL', 'inst33': 60, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 6, 'money_score': 4, 'alpha_score': 3, 'equity_score': 0.65, 'mean_reversion': 0.65, 'iv': 0.29, 'signal': 'HOLD', 'key_metric': 'Tech giant - stable'},
    {'symbol': 'NUE', 'inst33': 60, 'overall_score': 6, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 7, 'money_score': 0, 'alpha_score': 3, 'equity_score': 1.7, 'mean_reversion': 1.55, 'iv': 0.4, 'signal': 'BUY_CALL', 'key_metric': 'Steel - uptrend reversion'},
    {'symbol': 'VCYT', 'inst33': 60, 'overall_score': 6, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 7, 'money_score': 0, 'alpha_score': 3, 'equity_score': 1.7, 'mean_reversion': 1.45, 'iv': 0.47, 'signal': 'HOLD', 'key_metric': 'Biotech - balanced setup'},
    {'symbol': 'ABT', 'inst33': 60, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 2, 'uva': 5, 'money_score': 3, 'alpha_score': 1, 'equity_score': 0.7, 'mean_reversion': 0.7, 'iv': 0.28, 'signal': 'HOLD', 'key_metric': 'Healthcare - stable dividend'},
    {'symbol': 'AVGO', 'inst33': 60, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 2, 'uva': 5, 'money_score': 3, 'alpha_score': 1, 'equity_score': -1.25, 'mean_reversion': -1.25, 'iv': 0.68, 'signal': 'HOLD', 'key_metric': 'Semiconductor - downtrend'},
    {'symbol': 'B', 'inst33': 60, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.1, 'mean_reversion': 0.9, 'iv': 0.5, 'signal': 'HOLD', 'key_metric': 'Industrial - mixed signals'},
    {'symbol': 'M', 'inst33': 60, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.1, 'mean_reversion': 0.5, 'iv': 0.7, 'signal': 'HOLD', 'key_metric': 'Retail - transformation play'},
    {'symbol': 'EA', 'inst33': 60, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -0.26, 'iv': 0.09, 'signal': 'HOLD', 'key_metric': 'Gaming - low IV play'},
    {'symbol': 'ORCL', 'inst33': 58, 'overall_score': 0, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 3, 'uva': 4, 'money_score': 3, 'alpha_score': 2, 'equity_score': -1.84, 'mean_reversion': -1.84, 'iv': 0.75, 'signal': 'SELL', 'key_metric': 'Database - bearish pullback'},
    {'symbol': 'BW', 'inst33': 58, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': 0.37, 'iv': 1.57, 'signal': 'HOLD', 'key_metric': 'Industrial - extreme IV play'},
    {'symbol': 'RIVN', 'inst33': 58, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': 0.03, 'iv': 0.84, 'signal': 'HOLD', 'key_metric': 'EV - nascent company'},
    {'symbol': 'MSTR', 'inst33': 58, 'overall_score': 0, 'master_score': 3, 'signal_strength': -1, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 9, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -1.77, 'iv': 1.11, 'signal': 'SELL', 'key_metric': 'Bitcoin proxy - volatile'},
    {'symbol': 'CSCO', 'inst33': 55, 'overall_score': 8, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 8, 'money_score': 4, 'alpha_score': 3, 'equity_score': 0.81, 'mean_reversion': 0.81, 'iv': 0.29, 'signal': 'HOLD', 'key_metric': 'Networking - stable dividend'},
    {'symbol': 'DG', 'inst33': 55, 'overall_score': 0, 'master_score': 2, 'signal_strength': 0, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.1, 'mean_reversion': 0.25, 'iv': 0.56, 'signal': 'HOLD', 'key_metric': 'Discount retail - neutral'},
    {'symbol': 'MDB', 'inst33': 55, 'overall_score': 0, 'master_score': 2, 'signal_strength': 0, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.1, 'mean_reversion': -2.03, 'iv': 0.83, 'signal': 'SELL', 'key_metric': 'Database NoSQL - downtrend'},
    {'symbol': 'MU', 'inst33': 53, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': -1.8, 'mean_reversion': -1.8, 'iv': 0.89, 'signal': 'SELL', 'key_metric': 'Memory chips - cycle downturn'},
    {'symbol': 'AMD', 'inst33': 53, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': -2.36, 'mean_reversion': -2.36, 'iv': 0.68, 'signal': 'SELL', 'key_metric': 'Chip maker - sharp pullback'},
    {'symbol': 'MLYS', 'inst33': 53, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': 0.05, 'mean_reversion': 0.05, 'iv': 0.83, 'signal': 'HOLD', 'key_metric': 'Medical devices - emerging'},
    {'symbol': 'HL', 'inst33': 53, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.18, 'mean_reversion': -0.18, 'iv': 0.92, 'signal': 'HOLD', 'key_metric': 'Precious metals - high vol'},
    {'symbol': 'CRWV', 'inst33': 53, 'overall_score': 0, 'master_score': 2, 'signal_strength': 0, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.1, 'mean_reversion': -1.23, 'iv': 1.09, 'signal': 'HOLD', 'key_metric': 'Specialty pharma - volatile'},
    {'symbol': 'DELL', 'inst33': 53, 'overall_score': 0, 'master_score': 2, 'signal_strength': 0, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.1, 'mean_reversion': -1.31, 'iv': 0.65, 'signal': 'HOLD', 'key_metric': 'PC/Server - mature market'},
    {'symbol': 'IREN', 'inst33': 53, 'overall_score': 0, 'master_score': 2, 'signal_strength': 0, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.1, 'mean_reversion': -1.61, 'iv': 1.46, 'signal': 'SELL', 'key_metric': 'Energy infrastructure - weak'},
    {'symbol': 'AU', 'inst33': 50, 'overall_score': 7, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 7, 'money_score': 0, 'alpha_score': 3, 'equity_score': 1.7, 'mean_reversion': 0.95, 'iv': 0.68, 'signal': 'HOLD', 'key_metric': 'Gold miner - balanced'},
    {'symbol': 'PG', 'inst33': 50, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': 1.54, 'mean_reversion': 1.54, 'iv': 0.24, 'signal': 'SELL_CALL', 'key_metric': 'Consumer staples - call seller'},
    {'symbol': 'XOM', 'inst33': 50, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': 0.25, 'mean_reversion': 0.25, 'iv': 0.27, 'signal': 'HOLD', 'key_metric': 'Energy dividend - stable'},
    {'symbol': 'PEP', 'inst33': 50, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': 0.21, 'mean_reversion': 0.21, 'iv': 0.26, 'signal': 'HOLD', 'key_metric': 'Beverage - steady dividend'},
    {'symbol': 'HD', 'inst33': 50, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': -1.41, 'mean_reversion': -1.41, 'iv': 0.29, 'signal': 'HOLD', 'key_metric': 'Home improvement - pullback'},
    {'symbol': 'JPM', 'inst33': 50, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': -1.59, 'mean_reversion': -1.59, 'iv': 0.3, 'signal': 'HOLD', 'key_metric': 'Financial system - weak'},
    {'symbol': 'TSM', 'inst33': 50, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': -1.69, 'mean_reversion': -1.69, 'iv': 0.49, 'signal': 'HOLD', 'key_metric': 'Chip foundry - downtrend'},
    {'symbol': 'MS', 'inst33': 50, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': -1.95, 'mean_reversion': -1.95, 'iv': 0.35, 'signal': 'HOLD', 'key_metric': 'Investment banking - weak'},
    {'symbol': 'MT', 'inst33': 50, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.1, 'mean_reversion': 0.7, 'iv': 0.39, 'signal': 'HOLD', 'key_metric': 'European steel - neutral'},
    {'symbol': 'GTLB', 'inst33': 48, 'overall_score': 0, 'master_score': 2, 'signal_strength': 0, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -0.1, 'mean_reversion': -1.85, 'iv': 0.83, 'signal': 'SELL', 'key_metric': 'API security - emerging'},
    {'symbol': 'NVDA', 'inst33': 45, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 2, 'money_score': 1, 'alpha_score': 1, 'equity_score': -1.69, 'mean_reversion': -1.69, 'iv': 0.59, 'signal': 'SELL', 'key_metric': 'Chip leader - weakness'},
    {'symbol': 'AMZN', 'inst33': 45, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 2, 'money_score': 1, 'alpha_score': 1, 'equity_score': -1.37, 'mean_reversion': -1.37, 'iv': 0.4, 'signal': 'SELL', 'key_metric': 'E-commerce leader - pullback'},
]

def load_tickers():
    return [stock['symbol'] for stock in TOP_50_STOCKS]

TICKERS = load_tickers()

print(f"✅ Loaded {len(TICKERS)} tickers")

# ======================== SCHEDULER ========================
scheduler = BackgroundScheduler()

def cleanup_cache():
    current_time = datetime.now()
    if recommendations_cache['timestamp']:
        age = (current_time - recommendations_cache['timestamp']).total_seconds()
        if age > RECOMMENDATIONS_TTL:
            recommendations_cache['data'] = []
            print(f"🧹 Cleared recommendations cache")

scheduler.add_job(cleanup_cache, 'interval', minutes=5)
scheduler.start()

def shutdown_scheduler():
    scheduler.shutdown()

atexit.register(shutdown_scheduler)

# ======================== UTILITY FUNCTIONS ========================

def get_stock_price_waterfall(ticker):
    cache_key = f"{ticker}_{int(time.time() / 60)}"
    if cache_key in price_cache:
        return price_cache[cache_key]
    
    result = {'price': 0, 'change': 0, 'source': 'fallback'}
    
    try:
        if FINNHUB_KEY:
            url = f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}'
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get('c', 0) > 0:
                    result['price'] = data['c']
                    result['change'] = data.get('dp', 0)
                    result['source'] = 'Finnhub'
                    price_cache[cache_key] = result
                    return result
    except:
        pass
    
    return result

def fetch_prices_concurrent(tickers):
    results = []
    batch_size = 15
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_ticker = {executor.submit(get_stock_price_waterfall, ticker): ticker for ticker in batch}
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    price_data = future.result(timeout=5)
                    csv_stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
                    
                    results.append({
                        'Symbol': ticker,
                        'Last': round(price_data['price'], 2),
                        'Change': round(price_data['change'], 2),
                        'RSI': round(50 + (price_data['change'] * 2), 2),
                        'Signal': csv_stock['signal'] if csv_stock else 'HOLD',
                        'Score': csv_stock['inst33'] if csv_stock else 50.0,
                        'KeyMetric': csv_stock['key_metric'] if csv_stock else ''
                    })
                except Exception as e:
                    print(f"Error fetching {ticker}: {e}")
        time.sleep(0.1)
    
    results.sort(key=lambda x: x.get('Score', 0), reverse=True)
    return results

# ==================== NEWSLETTER FUNCTIONS ====================

def calculate_newsletter_score(stock):
    """Calculate 0-100 score for newsletter"""
    score = 0
    
    try:
        # Price momentum (40 points)
        change = float(stock.get('Change', 0))
        if change > 5:
            score += 40
        elif change > 2:
            score += 30
        elif change > 0:
            score += 20
        elif change > -2:
            score += 10
        
        # Institutional score (30 points)
        inst_score = float(stock.get('Score', 50))
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
        rsi = float(stock.get('RSI', 50))
        if 40 <= rsi <= 60:
            score += 10
        elif 30 <= rsi <= 70:
            score += 5
        
        return min(score, 100)
    except Exception as e:
        print(f"Error calculating score: {e}")
        return 50

def classify_tier(score):
    """Classify tier from score"""
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
        print("📰 Newsletter request received...")
        
        # Get stocks from cache or fetch
        stocks = None
        if recommendations_cache.get('data'):
            stocks = recommendations_cache['data']
            print(f"✅ Using cached data: {len(stocks)} stocks")
        else:
            print("⚠️  Fetching fresh stock data...")
            stocks = fetch_prices_concurrent(TICKERS)
            recommendations_cache['data'] = stocks
            recommendations_cache['timestamp'] = datetime.now()
            print(f"✅ Fetched {len(stocks)} stocks")
        
        if not stocks or len(stocks) == 0:
            print("⚠️  No stocks available")
            return jsonify({
                'date': datetime.now().strftime('%B %d, %Y'),
                'week': datetime.now().isocalendar()[1],
                'tiers': {'TIER 1-A': [], 'TIER 1-B': [], 'TIER 2': [], 'TIER 2B': [], 'TIER 3': []},
                'summary': {'total_stocks': 0, 'tier_1a_count': 0, 'tier_1b_count': 0, 'avg_score': 0, 'top_pick': None}
            }), 200
        
        # Score and tier each stock
        newsletter_stocks = []
        for stock in stocks:
            try:
                score = calculate_newsletter_score(stock)
                tier, action, color = classify_tier(score)
                
                last_price = float(stock.get('Last', 0))
                
                newsletter_stocks.append({
                    'symbol': str(stock.get('Symbol', 'UNKNOWN')),
                    'price': round(last_price, 2),
                    'change': round(float(stock.get('Change', 0)), 2),
                    'score': score,
                    'tier': tier,
                    'action': action,
                    'color': color,
                    'signal': str(stock.get('Signal', 'HOLD')),
                    'key_metric': str(stock.get('KeyMetric', 'Standard analysis')),
                    'entry': round(last_price * 0.98, 2),
                    'stop': round(last_price * 0.95, 2),
                    'target': round(last_price * 1.05, 2)
                })
            except Exception as e:
                print(f"Error processing stock: {e}")
                continue
        
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
        
        # Summary stats
        total_stocks = len(newsletter_stocks)
        tier1a_count = len(tiers['TIER 1-A'])
        tier1b_count = len(tiers['TIER 1-B'])
        avg_score = sum(s['score'] for s in newsletter_stocks) / total_stocks if total_stocks > 0 else 0
        top_pick = newsletter_stocks[0] if newsletter_stocks else None
        
        print(f"✅ Newsletter: {tier1a_count} Tier 1-A, {tier1b_count} Tier 1-B, Avg Score: {avg_score:.1f}")
        
        return jsonify({
            'date': datetime.now().strftime('%B %d, %Y'),
            'week': datetime.now().isocalendar()[1],
            'tiers': tiers,
            'summary': {
                'total_stocks': total_stocks,
                'tier_1a_count': tier1a_count,
                'tier_1b_count': tier1b_count,
                'avg_score': round(avg_score, 1),
                'top_pick': top_pick
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Newsletter error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'tiers': {}, 'summary': {}}), 500

# ==================== END NEWSLETTER FUNCTIONS ====================

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    try:
        if recommendations_cache['data'] and recommendations_cache['timestamp']:
            cache_age = (datetime.now() - recommendations_cache['timestamp']).total_seconds()
            if cache_age < RECOMMENDATIONS_TTL:
                return jsonify(recommendations_cache['data'])
        
        stocks = fetch_prices_concurrent(TICKERS)
        recommendations_cache['data'] = stocks
        recommendations_cache['timestamp'] = datetime.now()
        return jsonify(stocks)
    except Exception as e:
        if recommendations_cache['data']:
            return jsonify(recommendations_cache['data'])
        return jsonify({'error': str(e)}), 500

@app.route('/api/stock-price/<ticker>', methods=['GET'])
def get_stock_price(ticker):
    try:
        price_data = get_stock_price_waterfall(ticker.upper())
        csv_stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker.upper()), None)
        return jsonify({
            'ticker': ticker.upper(),
            'price': round(price_data['price'], 2),
            'change': round(price_data['change'], 2),
            'score': csv_stock['inst33'] if csv_stock else 50.0,
            'signal': csv_stock['signal'] if csv_stock else 'HOLD'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'scheduler_running': scheduler.running,
        'cache_populated': len(recommendations_cache.get('data', [])) > 0,
        'stocks_loaded': len(TICKERS),
        'endpoints': [
            '/api/recommendations',
            '/api/newsletter/simple',
            '/api/stock-price/<ticker>'
        ]
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
