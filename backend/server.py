from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import logging

app = Flask(__name__)
CORS(app)

# API Keys - Set these in your Render environment variables
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', 'ctbu1gpr01qn3qtjcv3gctbu1gpr01qn3qtjcv40')
ALPHAVANTAGE_API_KEY = os.getenv('ALPHAVANTAGE_API_KEY', 'your_alpha_vantage_key')
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY', 'your_perplexity_key')

# Simple in-memory cache (use Redis in production)
news_cache = {}
CACHE_DURATION = 300  # 5 minutes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== NEWS ENDPOINT ====================
@app.route('/api/stock-news/<ticker>', methods=['GET'])
def get_stock_news(ticker):
    """
    Aggregates news from multiple sources:
    1. Finnhub API (if available)
    2. AlphaVantage API (if available)
    3. Web scraping Yahoo Finance with BeautifulSoup
    """
    ticker = ticker.upper()
    
    # Check cache
    cache_key = f"news_{ticker}"
    if cache_key in news_cache:
        cached_data, cached_time = news_cache[cache_key]
        if (datetime.now() - cached_time).seconds < CACHE_DURATION:
            logger.info(f"Returning cached news for {ticker}")
            return jsonify(cached_data)
    
    all_news = []
    
    # 1. Try Finnhub first
    try:
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        finnhub_url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from_date}&to={to_date}&token={FINNHUB_API_KEY}"
        response = requests.get(finnhub_url, timeout=5)
        
        if response.status_code == 200:
            finnhub_news = response.json()
            for article in finnhub_news[:10]:
                all_news.append({
                    'source': article.get('source', 'Finnhub'),
                    'headline': article.get('headline', ''),
                    'url': article.get('url', ''),
                    'datetime': article.get('datetime', 0),
                    'summary': article.get('summary', ''),
                    'provider': 'finnhub'
                })
            logger.info(f"Finnhub returned {len(finnhub_news)} articles for {ticker}")
    except Exception as e:
        logger.error(f"Finnhub API error for {ticker}: {str(e)}")
    
    # 2. Try AlphaVantage
    try:
        alpha_url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&apikey={ALPHAVANTAGE_API_KEY}"
        response = requests.get(alpha_url, timeout=5)
        
        if response.status_code == 200:
            alpha_data = response.json()
            if 'feed' in alpha_data:
                for article in alpha_data['feed'][:10]:
                    all_news.append({
                        'source': article.get('source', 'AlphaVantage'),
                        'headline': article.get('title', ''),
                        'url': article.get('url', ''),
                        'datetime': int(datetime.strptime(article.get('time_published', '20250101T000000'), '%Y%m%dT%H%M%S').timestamp()),
                        'summary': article.get('summary', ''),
                        'provider': 'alphavantage'
                    })
                logger.info(f"AlphaVantage returned {len(alpha_data['feed'])} articles for {ticker}")
    except Exception as e:
        logger.error(f"AlphaVantage API error for {ticker}: {str(e)}")
    
    # 3. Scrape Yahoo Finance as fallback
    if len(all_news) < 5:
        try:
            yahoo_news = scrape_yahoo_finance_news(ticker)
            all_news.extend(yahoo_news)
            logger.info(f"Yahoo scraping returned {len(yahoo_news)} articles for {ticker}")
        except Exception as e:
            logger.error(f"Yahoo scraping error for {ticker}: {str(e)}")
    
    # Sort by datetime (newest first) and remove duplicates
    all_news = sorted(all_news, key=lambda x: x['datetime'], reverse=True)
    
    # Remove duplicate headlines
    seen_headlines = set()
    unique_news = []
    for article in all_news:
        if article['headline'] not in seen_headlines:
            seen_headlines.add(article['headline'])
            unique_news.append(article)
    
    result = {
        'ticker': ticker,
        'news': unique_news[:15],  # Return top 15
        'sources': list(set([n['provider'] for n in unique_news])),
        'count': len(unique_news)
    }
    
    # Cache result
    news_cache[cache_key] = (result, datetime.now())
    
    return jsonify(result)


def scrape_yahoo_finance_news(ticker):
    """
    Scrapes Yahoo Finance news using BeautifulSoup
    """
    news = []
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/news"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return news
        
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Find news articles (Yahoo's structure may change)
        articles = soup.find_all('li', class_='js-stream-content')
        
        for article in articles[:10]:
            try:
                headline_tag = article.find('h3') or article.find('a')
                link_tag = article.find('a', href=True)
                
                if headline_tag and link_tag:
                    headline = headline_tag.get_text(strip=True)
                    link = link_tag['href']
                    
                    # Fix relative URLs
                    if not link.startswith('http'):
                        link = f"https://finance.yahoo.com{link}"
                    
                    news.append({
                        'source': 'Yahoo Finance',
                        'headline': headline,
                        'url': link,
                        'datetime': int(datetime.now().timestamp()),
                        'summary': '',
                        'provider': 'yahoo_scrape'
                    })
            except Exception as e:
                logger.error(f"Error parsing Yahoo article: {str(e)}")
                continue
        
    except Exception as e:
        logger.error(f"Yahoo scraping failed for {ticker}: {str(e)}")
    
    return news


# ==================== EXISTING ENDPOINTS ====================
# Your existing endpoints remain unchanged:
# - /api/recommendations
# - /api/stock-research/<ticker>
# - /api/options-opportunities/<ticker>
# - /api/newsletter/weekly
# etc.


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
