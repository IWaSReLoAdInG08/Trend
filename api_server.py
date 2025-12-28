
import os
import sys
import logging
from flask import Flask, jsonify, request

# Add project root to path
sys.path.append(os.getcwd())

# Import our decoupled tools
from fetch_news import fetch_data
from generate_report import generate_report
from trendradar.storage import get_storage_manager
from trendradar.core import load_config
from trendradar.core.categories import CATEGORIES

app = Flask(__name__)

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_sm():
    config = load_config()
    storage_config = config.get("STORAGE", {})
    local_config = storage_config.get("LOCAL", {})
    return get_storage_manager(
        backend_type="local", 
        data_dir=local_config.get("DATA_DIR", "output"),
        timezone=config.get("TIMEZONE", "Asia/Kolkata")
    )

@app.route('/fetch', methods=['GET'])
def api_fetch():
    """
    Endpoint to trigger news fetching.
    Returns: JSON with fetch statistics.
    """
    logger.info("Received request: /fetch")
    try:
        result = fetch_data()
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/report', methods=['GET'])
def api_report():
    """
    Endpoint to generate report.
    Query Params:
        date (optional): YYYY-MM-DD
    Returns: JSON with path to generated report.
    """
    date = request.args.get('date')
    logger.info(f"Received request: /report?date={date}")
    
    try:
        generate_report(target_date=date)
        return jsonify({
            "status": "success", 
            "message": "Report generation triggered.",
            "target_date": date or "today"
        }), 200
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/news', methods=['GET'])
def api_news():
    """
    Endpoint to get enriched news data with filtering.
    Query Params:
        date (optional): YYYY-MM-DD
        category (optional): e.g., 'AI & Technology'
        limit (optional): number of items per source
    """
    date = request.args.get('date')
    category = request.args.get('category')
    limit = request.args.get('limit', default=20, type=int)
    
    try:
        sm = get_sm()
        logger.info(f"Checking news for date: {date or 'today'}")
        data = sm.get_today_all_data(date)
        if not data:
            logger.warning(f"No data found for date: {date or 'today'}")
            return jsonify({"status": "error", "message": "No data found"}), 404
            
        results = []
        for source_id, items in data.items.items():
            for item in items:
                # Filter by category if provided
                if category and category not in item.categories:
                    continue
                
                # Convert news item to dict
                item_dict = item.to_dict()
                results.append(item_dict)
        
        # Sort and limit
        results.sort(key=lambda x: x['rank'])
        
        return jsonify({
            "status": "success",
            "date": data.date,
            "count": len(results[:limit]),
            "categories": list(CATEGORIES.keys()),
            "news": results[:limit]
        }), 200
    except Exception as e:
        logger.error(f"Failed to retrieve news: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/trending', methods=['GET'])
def api_trending():
    """
    Get latest hourly trending highlights.
    """
    try:
        sm = get_sm()
        summary = sm.get_latest_summary()
        if not summary:
            return jsonify({"status": "error", "message": "No trending summary available yet"}), 404
            
        return jsonify({
            "status": "success",
            "trending": summary
        }), 200
    except Exception as e:
        logger.error(f"Failed to retrieve trending: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/status', methods=['GET'])
def api_status():
    """Health check and system info."""
    return jsonify({
        "status": "online",
        "version": "1.1.0 (Simplified)",
        "features": ["auto-categorization", "hourly-summaries", "rss-fetching"]
    }), 200

@app.route('/stats', methods=['GET'])
def api_stats():
    """
    Get crawl statistics for the dashboard chart.
    """
    try:
        sm = get_sm()
        stats = sm.get_crawl_stats()
        return jsonify({
            "status": "success",
            "labels": stats.get("labels", []),
            "data": stats.get("data", [])
        }), 200
    except Exception as e:
        logger.error(f"Failed to retrieve stats: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    """Serve the Premium Dashboard."""
    try:
        if os.path.exists('dashboard.html'):
            with open('dashboard.html', 'r', encoding='utf-8') as f:
                return f.read(), 200, {'Content-Type': 'text/html'}
        return jsonify({
            "status": "online",
            "message": "Dashboard file not found. Use API endpoints.",
            "endpoints": ["/stats", "/news", "/trending", "/status"]
        })
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    print("Starting TrendRadar API Server...")
    print("Usage:")
    print("  Fetch News:    http://localhost:5000/fetch")
    print("  Gen Report:    http://localhost:5000/report?date=2024-12-21")
    app.run(host='0.0.0.0', port=5000, debug=True)
