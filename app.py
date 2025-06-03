from flask import Flask, make_response
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from routes.auth import auth_bp
from routes.exam import exam_bp
from routes.proctoring import proctoring_bp
from routes.queries import queries_bp
from config import Config
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure CORS
CORS(app)

# Load configuration
app.config.from_object(Config)
jwt = JWTManager(app)
mail = Mail(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(exam_bp, url_prefix='/api')
app.register_blueprint(proctoring_bp, url_prefix='/api')
app.register_blueprint(queries_bp, url_prefix='/api')

# Handle OPTIONS requests globally (optional, for redundancy)
@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    response = make_response()
    response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response, 200

logger.info("Flask application started")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)