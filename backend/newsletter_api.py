from flask import Flask, jsonify, send_file, request, Blueprint
from datetime import datetime
import os
import io

# Create blueprint for modular integration
newsletter_bp = Blueprint('newsletter', __name__)


@newsletter_bp.route('/api/newsletter/generate', methods=['POST'])
def generate_newsletter():
    """
    API endpoint to generate newsletter
    
    POST /api/newsletter/generate
    Body: {
        "format": "markdown" | "json",
        "include_charts": true/false
    }
    
    Returns: Newsletter content
    """
    try:
        data = request.get_json() or {}
        output_format = data.get('format', 'markdown')
        
        # Import here to avoid circular imports
        from newsletter_generator import NewsletterGenerator
        
        # Get API keys from environment
        api_keys = {
            'finnhub': os.getenv('FINNHUB_API_KEY', ''),
            'alpha_vantage': os.getenv('ALPHAVANTAGE_API_KEY', ''),
            'perplexity': os.getenv('PERPLEXITY_API_KEY', '')
        }
        
        # Generate newsletter
        generator = NewsletterGenerator(api_keys)
        newsletter_content = generator.generate_newsletter()
        
        if output_format == 'json':
            return jsonify({
                'success': True,
                'content': newsletter_content,
                'generated_at': datetime.now().isoformat(),
                'format': 'markdown'
            })
        else:
            # Return as downloadable file
            buffer = io.BytesIO()
            buffer.write(newsletter_content.encode('utf-8'))
            buffer.seek(0)
            
            filename = f"newsletter_{datetime.now().strftime('%Y-%m-%d')}.md"
            
            return send_file(
                buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='text/markdown'
            )
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@newsletter_bp.route('/api/newsletter/status', methods=['GET'])
def newsletter_status():
    """
    Check newsletter system status
    
    GET /api/newsletter/status
    
    Returns: System status and capabilities
    """
    try:
        # Check which APIs are available
        has_finnhub = bool(os.getenv('FINNHUB_API_KEY'))
        has_alpha_vantage = bool(os.getenv('ALPHAVANTAGE_API_KEY'))
        has_perplexity = bool(os.getenv('PERPLEXITY_API_KEY'))
        
        # Check if watchlist files exist
        watchlist_files = {
            'SS': os.path.exists('2025-11-24-watchlist-SS.csv'),
            'GN1': os.path.exists('2025-11-24-watchlist-GN1.csv'),
            'MM': os.path.exists('2025-11-23-watchlist-MM.csv'),
            'EMS': os.path.exists('2025-11-23-watchlist-EMS.csv'),
            'PL': os.path.exists('2025-11-23-watchlist-PL.csv')
        }
        
        return jsonify({
            'success': True,
            'status': 'operational',
            'api_availability': {
                'finnhub': has_finnhub,
                'alpha_vantage': has_alpha_vantage,
                'perplexity': has_perplexity,
                'yfinance': True  # Always available if installed
            },
            'watchlists': watchlist_files,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@newsletter_bp.route('/api/newsletter/schedule', methods=['POST'])
def schedule_newsletter():
    """
    Schedule automatic newsletter generation
    
    POST /api/newsletter/schedule
    Body: {
        "time": "08:45",  # 24-hour format
        "timezone": "America/Los_Angeles",
        "enabled": true
    }
    
    Returns: Schedule confirmation
    """
    try:
        data = request.get_json() or {}
        schedule_time = data.get('time', '08:45')
        timezone = data.get('timezone', 'America/Los_Angeles')
        enabled = data.get('enabled', True)
        
        # TODO: Implement scheduling logic (use APScheduler or similar)
        # For now, return configuration
        
        return jsonify({
            'success': True,
            'schedule': {
                'time': schedule_time,
                'timezone': timezone,
                'enabled': enabled,
                'next_run': 'Not implemented yet'
            },
            'message': 'Schedule configuration saved. Implementation pending.'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
