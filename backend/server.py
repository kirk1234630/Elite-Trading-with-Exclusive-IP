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
from bs4 import BeautifulSoup

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
    {'symbol': 'MCD', 'inst33': 60, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 4, 'uva': 5, 'money_score': 3, 'alpha_score': 3, 'equity_score': 1.48, 'mean_reversion': 1.48, 'iv': 0.2, 'signal': 'SELL_CALL', 'key_metric': 'QSR - best call seller'},
    {'symbol': 'AAPL', 'inst33': 60, 'overall_score': 6, 'master_score': 3, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 6, 'money_score': 4, 'alpha_score': 3, 'equity_score': 0.65, 'mean_reversion': 0.65, 'iv': 0.29, 'signal': 'HOLD', 'key_metric': 'Tech giant - stable'},
    {'symbol': 'NUE', 'inst33': 60, 'overall_score': 6, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 7, 'money_score': 0, 'alpha_score': 3, 'equity_score': 1.7, 'mean_reversion': 1.55, 'iv': 0.4, 'signal': 'BUY_CALL', 'key_metric': 'Steel - uptrend reversion'},
    {'symbol': 'VCYT', 'inst33': 60, 'overall_score': 6, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 3, 'uva': 7, 'money_score': 0, 'alpha_score': 3, 'equity_score': 1.7, 'mean_reversion': 1.45, 'iv': 0.47, 'signal': 'HOLD', 'key_metric': 'Biotech - balanced setup'},
    {'symbol': 'ABT', 'inst33': 60, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 2, 'uva': 5, 'money_score': 3, 'alpha_score': 1, 'equity_score': 0.7, 'mean_reversion': 0.7, 'iv': 0.28, 'signal': 'HOLD', 'key_metric': 'Healthcare - stable dividend'},
    {'symbol': 'AVGO', 'inst33': 60, 'overall_score': 0, 'master_score': 2, 'signal_strength': 3, 'inst_stock_select': 2, 'composite_score': 2, 'uva': 5, 'money_score': 3, 'alpha_score': 1, 'equity_score': -1.25, 'mean_reversion': -1.25, 'iv': 0.68, 'signal': 'HOLD', 'key_metric': 'Semiconductor - downtrend'},
    {'symbol': 'B', 'inst33': 58, 'overall_score': 5, 'master_score': 2, 'signal_strength': 2, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 5, 'money_score': 2, 'alpha_score': 2, 'equity_score': 1.2, 'mean_reversion': 1.2, 'iv': 0.35, 'signal': 'HOLD', 'key_metric': 'Aerospace stable'},
    {'symbol': 'M', 'inst33': 45, 'overall_score': 2, 'master_score': 1, 'signal_strength': 0, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 3, 'money_score': 1, 'alpha_score': 0, 'equity_score': -1.5, 'mean_reversion': -1.5, 'iv': 0.42, 'signal': 'SELL', 'key_metric': 'Retail weakness'},
    {'symbol': 'EA', 'inst33': 52, 'overall_score': 4, 'master_score': 2, 'signal_strength': 1, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': 0.3, 'mean_reversion': 0.3, 'iv': 0.38, 'signal': 'HOLD', 'key_metric': 'Gaming stable'},
    {'symbol': 'ORCL', 'inst33': 58, 'overall_score': 5, 'master_score': 2, 'signal_strength': 2, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 5, 'money_score': 3, 'alpha_score': 1, 'equity_score': 0.8, 'mean_reversion': 0.8, 'iv': 0.26, 'signal': 'HOLD', 'key_metric': 'Cloud leader'},
    {'symbol': 'BW', 'inst33': 48, 'overall_score': 2, 'master_score': 1, 'signal_strength': -1, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -2.1, 'mean_reversion': -2.1, 'iv': 1.2, 'signal': 'SELL', 'key_metric': 'BW weakness'},
    {'symbol': 'RIVN', 'inst33': 42, 'overall_score': 1, 'master_score': 0, 'signal_strength': -2, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 1, 'money_score': 0, 'alpha_score': 0, 'equity_score': -3.0, 'mean_reversion': -3.0, 'iv': 1.5, 'signal': 'SELL', 'key_metric': 'EV trouble'},
    {'symbol': 'MSTR', 'inst33': 50, 'overall_score': 3, 'master_score': 1, 'signal_strength': 0, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 3, 'money_score': 1, 'alpha_score': 0, 'equity_score': 0.5, 'mean_reversion': 0.5, 'iv': 0.9, 'signal': 'HOLD', 'key_metric': 'Bitcoin proxy'},
    {'symbol': 'MDB', 'inst33': 56, 'overall_score': 4, 'master_score': 2, 'signal_strength': 2, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 5, 'money_score': 2, 'alpha_score': 2, 'equity_score': 1.5, 'mean_reversion': 1.5, 'iv': 0.44, 'signal': 'BUY', 'key_metric': 'Database growth'},
    {'symbol': 'DG', 'inst33': 55, 'overall_score': 4, 'master_score': 2, 'signal_strength': 2, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 5, 'money_score': 3, 'alpha_score': 1, 'equity_score': 1.2, 'mean_reversion': 1.2, 'iv': 0.32, 'signal': 'HOLD', 'key_metric': 'Discount retail'},
    {'symbol': 'CSCO', 'inst33': 55, 'overall_score': 4, 'master_score': 2, 'signal_strength': 2, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 5, 'money_score': 3, 'alpha_score': 1, 'equity_score': 0.9, 'mean_reversion': 0.9, 'iv': 0.24, 'signal': 'HOLD', 'key_metric': 'Networking dividend'},
    {'symbol': 'MU', 'inst33': 54, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 4, 'money_score': 1, 'alpha_score': 1, 'equity_score': -0.5, 'mean_reversion': -0.5, 'iv': 0.55, 'signal': 'HOLD', 'key_metric': 'Memory chips'},
    {'symbol': 'MLYS', 'inst33': 48, 'overall_score': 2, 'master_score': 1, 'signal_strength': 0, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -1.8, 'mean_reversion': -1.8, 'iv': 0.68, 'signal': 'SELL', 'key_metric': 'Mobility weak'},
    {'symbol': 'AMD', 'inst33': 53, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 4, 'money_score': 2, 'alpha_score': 0, 'equity_score': -0.8, 'mean_reversion': -0.8, 'iv': 0.62, 'signal': 'HOLD', 'key_metric': 'Chip competitor'},
    {'symbol': 'HL', 'inst33': 47, 'overall_score': 2, 'master_score': 0, 'signal_strength': -1, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -1.2, 'mean_reversion': -1.2, 'iv': 0.85, 'signal': 'SELL', 'key_metric': 'Silver mining'},
    {'symbol': 'DELL', 'inst33': 51, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 3, 'money_score': 1, 'alpha_score': 1, 'equity_score': -0.2, 'mean_reversion': -0.2, 'iv': 0.43, 'signal': 'HOLD', 'key_metric': 'PC mature'},
    {'symbol': 'AU', 'inst33': 49, 'overall_score': 2, 'master_score': 0, 'signal_strength': -1, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -1.1, 'mean_reversion': -1.1, 'iv': 0.58, 'signal': 'SELL', 'key_metric': 'Gold miner weak'},
    {'symbol': 'PG', 'inst33': 52, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 4, 'money_score': 2, 'alpha_score': 0, 'equity_score': 0.7, 'mean_reversion': 0.7, 'iv': 0.19, 'signal': 'HOLD', 'key_metric': 'Consumer staples'},
    {'symbol': 'XOM', 'inst33': 51, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 3, 'money_score': 1, 'alpha_score': 1, 'equity_score': 0.2, 'mean_reversion': 0.2, 'iv': 0.21, 'signal': 'HOLD', 'key_metric': 'Energy dividend'},
    {'symbol': 'PEP', 'inst33': 53, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 4, 'money_score': 2, 'alpha_score': 0, 'equity_score': 0.6, 'mean_reversion': 0.6, 'iv': 0.20, 'signal': 'HOLD', 'key_metric': 'Beverage stable'},
    {'symbol': 'HD', 'inst33': 54, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': 0.9, 'mean_reversion': 0.9, 'iv': 0.23, 'signal': 'HOLD', 'key_metric': 'Home depot stable'},
    {'symbol': 'TSM', 'inst33': 56, 'overall_score': 4, 'master_score': 2, 'signal_strength': 2, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 5, 'money_score': 2, 'alpha_score': 2, 'equity_score': 1.3, 'mean_reversion': 1.3, 'iv': 0.36, 'signal': 'BUY', 'key_metric': 'Foundry leader'},
    {'symbol': 'JPM', 'inst33': 52, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 3, 'money_score': 1, 'alpha_score': 1, 'equity_score': -0.1, 'mean_reversion': -0.1, 'iv': 0.28, 'signal': 'HOLD', 'key_metric': 'Bank giant'},
    {'symbol': 'MS', 'inst33': 51, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 3, 'money_score': 1, 'alpha_score': 0, 'equity_score': -0.3, 'mean_reversion': -0.3, 'iv': 0.29, 'signal': 'HOLD', 'key_metric': 'Morgan Stanley'},
    {'symbol': 'MT', 'inst33': 49, 'overall_score': 2, 'master_score': 0, 'signal_strength': 0, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -1.5, 'mean_reversion': -1.5, 'iv': 0.44, 'signal': 'SELL', 'key_metric': 'Steel producer'},
    {'symbol': 'GTLB', 'inst33': 50, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 3, 'money_score': 1, 'alpha_score': 1, 'equity_score': 0.4, 'mean_reversion': 0.4, 'iv': 0.37, 'signal': 'HOLD', 'key_metric': 'Gatilabs'},
    {'symbol': 'NVDA', 'inst33': 48, 'overall_score': 2, 'master_score': 0, 'signal_strength': -1, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -1.6, 'mean_reversion': -1.6, 'iv': 0.58, 'signal': 'SELL', 'key_metric': 'GPU weakness'},
    {'symbol': 'AMZN', 'inst33': 47, 'overall_score': 2, 'master_score': 0, 'signal_strength': -1, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 2, 'money_score': 0, 'alpha_score': 0, 'equity_score': -1.4, 'mean_reversion': -1.4, 'iv': 0.42, 'signal': 'SELL', 'key_metric': 'E-commerce pullback'},
    {'symbol': 'MSFT', 'inst33': 58, 'overall_score': 5, 'master_score': 2, 'signal_strength': 2, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 5, 'money_score': 3, 'alpha_score': 2, 'equity_score': 1.1, 'mean_reversion': 1.1, 'iv': 0.30, 'signal': 'BUY', 'key_metric': 'Cloud dominant'},
    {'symbol': 'TSLA', 'inst33': 45, 'overall_score': 1, 'master_score': 0, 'signal_strength': -1, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 1, 'money_score': 0, 'alpha_score': 0, 'equity_score': -2.2, 'mean_reversion': -2.2, 'iv': 0.75, 'signal': 'SELL', 'key_metric': 'EV volatility'},
    {'symbol': 'META', 'inst33': 54, 'overall_score': 3, 'master_score': 1, 'signal_strength': 1, 'inst_stock_select': 0, 'composite_score': 1, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': 0.5, 'mean_reversion': 0.5, 'iv': 0.45, 'signal': 'HOLD', 'key_metric': 'AI upside'},
    {'symbol': 'NFLX', 'inst33': 55, 'overall_score': 4, 'master_score': 2, 'signal_strength': 1, 'inst_stock_select': 1, 'composite_score': 2, 'uva': 4, 'money_score': 2, 'alpha_score': 1, 'equity_score': 0.6, 'mean_reversion': 0.6, 'iv': 0.34, 'signal': 'HOLD', 'key_metric': 'Streaming stable'},
    {'symbol': 'BABA', 'inst33': 45, 'overall_score': 1, 'master_score': 0, 'signal_strength': -1, 'inst_stock_select': 0, 'composite_score': 0, 'uva': 1, 'money_score': 0, 'alpha_score': 0, 'equity_score': -2.0, 'mean_reversion': -2.0, 'iv': 0.55, 'signal': 'SELL', 'key_metric': 'China exposure'},
]

TICKERS = [s['symbol'] for s in TOP_50_STOCKS]

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
SENTIMENT_TTL = 43200  # 12 hours
MACRO_TTL = 604800
INSIDER_TTL = 86400
EARNINGS_TTL = 86400  # Daily
AI_INSIGHTS_TTL = 3600

# ======================== 1. EARNINGS FROM EARNINGSHUB SCRAPING ========================
def fetch_earnings_from_earningshub():
    """Scrape earnings from earningshub.com"""
    earnings_data = []
    
    print("🔄 Fetching earnings from EarningsHub...")
    
    try:
        url = 'https://earningshub.com/earnings-calendar'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all rows in earnings table
            rows = soup.find_all('tr')
            
            for row in rows[:100]:  # Get first 100 earnings
                try:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        symbol = cells[0].text.strip()
                        date_text = cells[1].text.strip() if len(cells) > 1 else None
                        
                        if symbol in TICKERS and date_text:
                            earnings_data.append({
                                'symbol': symbol,
                                'date': date_text,
                                'source': 'EarningsHub'
                            })
                except:
                    continue
        
        print(f"✅ EarningsHub: {len(earnings_data)} earnings\n")
        return earnings_data[:50]
    
    except Exception as e:
        print(f"❌ EarningsHub error: {e}\n")
        return []

# ======================== 2. SOCIAL SENTIMENT (FIXED DoD + WoW + MoM) ========================
def get_social_sentiment(ticker):
    """Get sentiment with Day-over-Day, Week-over-Week, Month-over-Month"""
    
    if ticker in sentiment_cache:
        cached = sentiment_cache[ticker]
        if datetime.now() - cached['timestamp'] < timedelta(seconds=SENTIMENT_TTL):
            return cached['data']
    
    result = {
        'ticker': ticker,
        'daily': {'sentiment': 'NEUTRAL', 'mentions': 0, 'score': 0.00},
        'daily_change': {'dod': 0.00, 'dod_sentiment': 'NEUTRAL'},
        'weekly': {'sentiment': 'NEUTRAL', 'mentions': 0, 'score': 0.00},
        'weekly_change': {'wow': 0.00},
        'monthly_change': {'mom': 0.00},
        'source': 'Finnhub Social Sentiment API'
    }
    
    if not FINNHUB_KEY:
        return result
    
    try:
        url = f'https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            reddit = data.get('reddit', [])
            
            if reddit and len(reddit) > 0:
                # TODAY (index 0)
                today = reddit[0]
                today_score = today.get('score', 0)
                today_mentions = today.get('mention', 0)
                today_sentiment = 'BULLISH' if today_score > 0.5 else ('BEARISH' if today_score < -0.5 else 'NEUTRAL')
                
                # YESTERDAY (index 1) - for DoD
                yesterday_score = reddit[1].get('score', 0) if len(reddit) > 1 else today_score
                dod_change = ((today_score - yesterday_score) / abs(yesterday_score)) * 100 if yesterday_score != 0 else 0
                dod_sentiment = 'BULLISH' if dod_change > 0 else ('BEARISH' if dod_change < 0 else 'NEUTRAL')
                
                # WEEK (last 7 days average)
                week_data = reddit[:7]
                week_scores = [r.get('score', 0) for r in week_data]
                week_avg = sum(week_scores) / len(week_scores) if week_scores else 0
                week_mentions = sum(r.get('mention', 0) for r in week_data)
                week_sentiment = 'BULLISH' if week_avg > 0.5 else ('BEARISH' if week_avg < -0.5 else 'NEUTRAL')
                
                # WoW (week over week)
                wow_change = 0.0
                if len(reddit) >= 7 and reddit[6].get('score', 0) != 0:
                    prev_week = reddit[6].get('score', 0)
                    wow_change = ((today_score - prev_week) / abs(prev_week)) * 100
                
                # MoM (month over month)
                mom_change = 0.0
                if len(reddit) >= 30 and reddit[29].get('score', 0) != 0:
                    prev_month = reddit[29].get('score', 0)
                    mom_change = ((today_score - prev_month) / abs(prev_month)) * 100
                
                result = {
                    'ticker': ticker,
                    'daily': {
                        'sentiment': today_sentiment,
                        'mentions': today_mentions,
                        'score': round(today_score, 2)
                    },
                    'daily_change': {
                        'dod': round(dod_change, 2),
                        'dod_sentiment': dod_sentiment
                    },
                    'weekly': {
                        'sentiment': week_sentiment,
                        'mentions': week_mentions,
                        'score': round(week_avg, 2)
                    },
                    'weekly_change': {'wow': round(wow_change, 2)},
                    'monthly_change': {'mom': round(mom_change, 2)},
                    'source': 'Finnhub Social Sentiment API',
                    'timestamp': datetime.now().isoformat()
                }
                
                print(f"✅ Sentiment {ticker}: {today_sentiment} (Today: {today_score}, DoD: {dod_change:+.2f}%)")
    
    except Exception as e:
        print(f"❌ Sentiment error {ticker}: {e}")
    
    sentiment_cache[ticker] = {'data': result, 'timestamp': datetime.now()}
    return result

# ======================== 3. INSIDER TRANSACTIONS (FIXED NoneType) ========================
def get_insider_transactions(ticker):
    """Get insider trading activity - FIXED None values"""
    
    if ticker in insider_cache:
        cached = insider_cache[ticker]
        if datetime.now() - cached['timestamp'] < timedelta(seconds=INSIDER_TTL):
            return cached['data']
    
    result = {
        'ticker': ticker,
        'transactions': [],
        'summary': {'buying': 0, 'selling': 0, 'signal': 'NEUTRAL'},
        'source': 'Finnhub'
    }
    
    if not FINNHUB_KEY:
        return result
    
    try:
        url = f'https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            transactions = data.get('data', [])
            
            if transactions:
                recent_transactions = transactions[:10]
                
                buying_count = 0
                selling_count = 0
                total_value_buy = 0
                total_value_sell = 0
                
                for tx in recent_transactions:
                    change = tx.get('change', 0)
                    share = tx.get('share')
                    price = tx.get('price')
                    
                    # FIX: Handle None values
                    if share is None or price is None:
                        value = 0
                    else:
                        value = share * price
                    
                    if change > 0:
                        buying_count += 1
                        total_value_buy += value
                    elif change < 0:
                        selling_count += 1
                        total_value_sell += value
                    
                    result['transactions'].append({
                        'name': tx.get('name'),
                        'change': change,
                        'shares': share,
                        'price': price,
                        'date': tx.get('transactionDate'),
                        'type': 'BUY' if change > 0 else 'SELL'
                    })
                
                # Determine signal
                if buying_count > selling_count * 2:
                    signal = 'BULLISH'
                elif selling_count > buying_count * 2:
                    signal = 'BEARISH'
                else:
                    signal = 'NEUTRAL'
                
                result['summary'] = {
                    'buying': buying_count,
                    'selling': selling_count,
                    'signal': signal,
                    'buy_value': round(total_value_buy, 2),
                    'sell_value': round(total_value_sell, 2)
                }
                
                print(f"✅ Insider {ticker}: {signal} ({buying_count} buys, {selling_count} sells)")
    
    except Exception as e:
        print(f"❌ Insider error {ticker}: {e}")
    
    insider_cache[ticker] = {'data': result, 'timestamp': datetime.now()}
    return result

# ======================== 4. NEWS (RESTORED) ========================
def get_stock_news(ticker):
    """Get latest stock news from Finnhub"""
    
    if ticker in news_cache and news_cache['last_updated']:
        age = (datetime.now() - news_cache['last_updated']).seconds
        if age < 3600:  # 1 hour cache
            return [n for n in news_cache['market_news'] if n['symbol'] == ticker][:5]
    
    news = []
    
    if not FINNHUB_KEY:
        return news
    
    try:
        url = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from={datetime.now().date() - timedelta(days=7)}&to={datetime.now().date()}&token={FINNHUB_KEY}'
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            articles = response.json()
            
            for article in articles[:10]:
                news.append({
                    'symbol': ticker,
                    'headline': article.get('headline'),
                    'summary': article.get('summary'),
                    'url': article.get('url'),
                    'source': article.get('source'),
                    'datetime': datetime.fromtimestamp(article.get('datetime', 0)).strftime('%Y-%m-%d %H:%M:%S')
                })
            
            print(f"✅ News for {ticker}: {len(news)} articles")
    
    except Exception as e:
        print(f"⚠️ News error {ticker}: {e}")
    
    return news

# ======================== API ENDPOINTS ========================

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'OK', 'stocks': len(TICKERS), 'earnings': len(earnings_cache['data'])})

@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Top 50 stocks"""
    if recommendations_cache['data'] and recommendations_cache['timestamp']:
        age = (datetime.now() - recommendations_cache['timestamp']).seconds
        if age < RECOMMENDATIONS_TTL:
            return jsonify(recommendations_cache['data'])
    
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
    
    recommendations_cache['data'] = results
    recommendations_cache['timestamp'] = datetime.now()
    
    return jsonify(results)

@app.route('/api/earnings-calendar', methods=['GET'])
def get_earnings_calendar():
    """Earnings from EarningsHub"""
    return jsonify(earnings_cache.get('data', []))

@app.route('/api/social-sentiment/<ticker>', methods=['GET'])
def get_sentiment(ticker):
    """Sentiment with DoD + WoW + MoM"""
    return jsonify(get_social_sentiment(ticker.upper()))

@app.route('/api/insider-transactions/<ticker>', methods=['GET'])
def get_insider(ticker):
    """Insider transactions"""
    return jsonify(get_insider_transactions(ticker.upper()))

@app.route('/api/stock-news/<ticker>', methods=['GET'])
def get_news(ticker):
    """Stock news"""
    news = get_stock_news(ticker.upper())
    return jsonify({'ticker': ticker.upper(), 'news': news})

@app.route('/api/macro-indicators', methods=['GET'])
def get_macro_indicators():
    """FRED economic data"""
    
    if macro_cache['data'] and macro_cache['timestamp']:
        age = (datetime.now() - macro_cache['timestamp']).seconds
        if age < MACRO_TTL:
            return jsonify(macro_cache['data'])
    
    indicators = {}
    
    if FRED_KEY:
        fred_series = {
            'WEI': 'Weekly Economic Index',
            'ICSA': 'Initial Claims',
            'M1SL': 'M1 Money Supply',
            'M2SL': 'M2 Money Supply',
            'DCOILWTICO': 'WTI Crude Oil',
            'DFF': 'Federal Funds Rate',
            'T10Y2Y': 'Yield Curve'
        }
        
        for series_id, name in fred_series.items():
            try:
                url = f'https://api.stlouisfed.org/fred/series/observations'
                params = {
                    'series_id': series_id,
                    'api_key': FRED_KEY,
                    'file_type': 'json',
                    'sort_order': 'desc',
                    'limit': 1
                }
                response = requests.get(url, params=params, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    observations = data.get('observations', [])
                    if observations:
                        value = observations[0].get('value')
                        indicators[series_id] = {
                            'name': name,
                            'value': float(value) if value != '.' else None,
                            'date': observations[0].get('date')
                        }
            except:
                pass
    
    macro_cache['data'] = indicators
    macro_cache['timestamp'] = datetime.now()
    
    return jsonify(indicators)

@app.route('/api/options-opportunities/<ticker>', methods=['GET'])
def get_options_opportunities(ticker):
    """6 Options Strategies with Greeks"""
    try:
        current_price = 150.0
        
        opportunities = {
            'ticker': ticker,
            'current_price': current_price,
            'analysis_date': datetime.now().isoformat(),
            'strategies': [
                {
                    'type': 'Iron Condor',
                    'description': 'Sell OTM call/put spreads - best for range-bound',
                    'setup': f'Sell ${round(current_price * 1.05, 2)} Call / Buy ${round(current_price * 1.08, 2)} Call, Sell ${round(current_price * 0.95, 2)} Put / Buy ${round(current_price * 0.92, 2)} Put',
                    'max_profit': round(current_price * 0.02, 2),
                    'max_loss': round(current_price * 0.03, 2),
                    'probability_of_profit': '65%',
                    'days_to_expiration': 30,
                    'greeks': {
                        'delta': '~0',
                        'gamma': 'Low',
                        'theta': '+High',
                        'vega': '-High',
                        'why_attractive': 'Theta decay favors seller. Collects premium daily.'
                    }
                },
                {
                    'type': 'Call Spread (Bullish)',
                    'description': 'Buy lower call, sell higher call',
                    'setup': f'Buy ${round(current_price, 2)} Call / Sell ${round(current_price * 1.05, 2)} Call',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'greeks': {'delta': '+0.60', 'gamma': 'Positive', 'theta': 'Neutral', 'vega': 'Low'}
                },
                {
                    'type': 'Put Spread (Bearish)',
                    'description': 'Buy higher put, sell lower put',
                    'setup': f'Buy ${round(current_price, 2)} Put / Sell ${round(current_price * 0.95, 2)} Put',
                    'max_profit': round(current_price * 0.05, 2),
                    'max_loss': round(current_price * 0.02, 2),
                    'probability_of_profit': '55%',
                    'greeks': {'delta': '-0.60', 'gamma': 'Positive', 'theta': 'Neutral', 'vega': 'Low'}
                },
                {
                    'type': 'Call Spread (Bearish)',
                    'description': 'Sell lower call, buy higher call',
                    'setup': f'Sell ${round(current_price * 1.02, 2)} Call / Buy ${round(current_price * 1.07, 2)} Call',
                    'max_profit': round(current_price * 0.015, 2),
                    'max_loss': round(current_price * 0.035, 2),
                    'probability_of_profit': '60%',
                    'greeks': {'delta': '-0.50', 'gamma': 'Negative', 'theta': '+High', 'vega': '-High'}
                },
                {
                    'type': 'Put Spread (Bullish)',
                    'description': 'Sell higher put, buy lower put',
                    'setup': f'Sell ${round(current_price * 0.98, 2)} Put / Buy ${round(current_price * 0.93, 2)} Put',
                    'max_profit': round(current_price * 0.015, 2),
                    'max_loss': round(current_price * 0.035, 2),
                    'probability_of_profit': '60%',
                    'greeks': {'delta': '+0.50', 'gamma': 'Negative', 'theta': '+High', 'vega': '-High'}
                },
                {
                    'type': 'Butterfly Spread',
                    'description': 'Buy 1 call, sell 2 calls, buy 1 call',
                    'setup': f'Buy ${round(current_price * 0.98, 2)} Call / Sell 2x ${round(current_price, 2)} Call / Buy ${round(current_price * 1.02, 2)} Call',
                    'max_profit': round(current_price * 0.04, 2),
                    'max_loss': round(current_price * 0.01, 2),
                    'probability_of_profit': '50%',
                    'greeks': {'delta': '~0', 'gamma': 'Peaky', 'theta': '+Moderate', 'vega': 'Low'}
                }
            ]
        }
        return jsonify(opportunities)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai-insights/<ticker>', methods=['GET'])
def get_ai_insights(ticker):
    """Perplexity Sonar Analysis"""
    print(f"🤖 AI analysis for {ticker}")
    
    if ticker in ai_insights_cache:
        cached = ai_insights_cache[ticker]
        if datetime.now() - cached['timestamp'] < timedelta(seconds=AI_INSIGHTS_TTL):
            return jsonify(cached['data'])
    
    if not PERPLEXITY_KEY:
        return jsonify({
            'edge': 'API not configured',
            'trade': 'Set PERPLEXITY_API_KEY',
            'risk': 'N/A'
        })
    
    try:
        csv_stock = next((s for s in TOP_50_STOCKS if s['symbol'] == ticker), None)
        context = f"Signal: {csv_stock['signal']}" if csv_stock else "Signal: NEUTRAL"
        
        prompt = f"""Analyze {ticker} for day trading. {context}
Provide exactly 3 lines:
EDGE: [Bullish/Bearish] setup
TRADE: Entry, stop, target
RISK: Low/Medium/High"""
        
        url = 'https://api.perplexity.ai/chat/completions'
        headers = {'Authorization': f'Bearer {PERPLEXITY_KEY}', 'Content-Type': 'application/json'}
        payload = {
            'model': 'sonar',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.6,
            'max_tokens': 200
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            lines = content.split('\n')
            
            result = {
                'edge': lines[0][:100] if len(lines) > 0 else 'Neutral',
                'trade': lines[1][:100] if len(lines) > 1 else 'Monitor',
                'risk': lines[2][:100] if len(lines) > 2 else 'Standard'
            }
            
            print(f"✅ Sonar analysis for {ticker}")
            ai_insights_cache[ticker] = {'data': result, 'timestamp': datetime.now()}
            return jsonify(result)
    except Exception as e:
        print(f"❌ AI error: {e}")
    
    return jsonify({'edge': 'Error', 'trade': 'N/A', 'risk': 'N/A'})

@app.route('/api/stock-price/<ticker>', methods=['GET'])
def get_stock_price(ticker):
    """Stock price"""
    return jsonify({'ticker': ticker.upper(), 'price': 100, 'change': 0})

# ======================== SCHEDULER ========================
def refresh_earnings():
    global earnings_cache
    print("\n🔄 [SCHEDULED] Refreshing earnings...")
    try:
        earnings = fetch_earnings_from_earningshub()
        earnings_cache['data'] = earnings
        earnings_cache['timestamp'] = datetime.now()
    except Exception as e:
        print(f"❌ Refresh error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=refresh_earnings, trigger="cron", day=1, hour=9)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ======================== INITIALIZATION ========================
print("\n" + "="*60)
print("🚀 ELITE STOCK TRACKER - STARTUP")
print("="*60)

earnings_cache['data'] = fetch_earnings_from_earningshub()
earnings_cache['timestamp'] = datetime.now()

print(f"✅ Loaded {len(TICKERS)} tickers")
print(f"✅ Earnings: {len(earnings_cache['data'])} upcoming")
print(f"✅ Perplexity: {'ENABLED' if PERPLEXITY_KEY else 'DISABLED'}")
print("="*60 + "\n")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
