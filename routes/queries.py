from flask import Blueprint, request, jsonify, make_response
from pymongo import MongoClient
from flask_jwt_extended import jwt_required, get_jwt_identity
from config import Config
from datetime import datetime
import logging

queries_bp = Blueprint('queries', __name__)
client = MongoClient(Config.MONGO_URI)
db = client['online_exam']
queries_collection = db['queries']

logger = logging.getLogger(__name__)

@queries_bp.route('/raise-query', methods=['POST', 'OPTIONS'])
@jwt_required()
def raise_query():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200
    current_user = get_jwt_identity()
    if current_user.get('role') != 'student':
        logger.warning(f"Unauthorized access to raise-query by {current_user.get('email')}")
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()
    if not data or 'exam_id' not in data or 'student_id' not in data or 'query_text' not in data or 'submitted_at' not in data:
        logger.error("Missing required fields in raise-query request")
        return jsonify({'message': 'Missing required fields'}), 400

    try:
        query = {
            'exam_id': data['exam_id'],
            'student_id': data['student_id'],
            'query_text': data['query_text'],
            'submitted_at': datetime.fromisoformat(data['submitted_at']),
            'status': 'pending'
        }
        queries_collection.insert_one(query)
        logger.info(f"Query raised by student {data['student_id']} for exam {data['exam_id']}")
        return jsonify({'message': 'Query submitted successfully'}), 200
    except Exception as e:
        logger.error(f"Failed to raise query: {str(e)}")
        return jsonify({'message': 'Failed to submit query'}), 500