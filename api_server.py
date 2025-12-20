
import os
import sys
import logging
from flask import Flask, jsonify, request

# Add project root to path
sys.path.append(os.getcwd())

# Import our decoupled tools
from fetch_news import fetch_data
from generate_report import generate_report

app = Flask(__name__)

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        # Note: generate_report function prints to stdout/logging but doesn't return the path currently.
        # We might want to capture its output or modify it to return the path.
        # For now, we wrap it and assume success if no exception.
        
        # To get the accurate output path, we can predict it or modify the underlying function.
        # Since we are reusing code without modifying library code too much, let's just run it.
        
        generate_report(target_date=date)
        
        return jsonify({
            "status": "success", 
            "message": "Report generation triggered. Check server logs for details.",
            "target_date": date or "today"
        }), 200
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "online",
        "endpoints": [
            "GET /fetch",
            "GET /report?date=YYYY-MM-DD"
        ]
    })

if __name__ == '__main__':
    print("Starting TrendRadar API Server...")
    print("Usage:")
    print("  Fetch News:    http://localhost:5000/fetch")
    print("  Gen Report:    http://localhost:5000/report?date=2024-12-21")
    app.run(host='0.0.0.0', port=5000, debug=True)
