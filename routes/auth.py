from flask import Blueprint, request, jsonify, make_response
from pymongo import MongoClient
from flask_jwt_extended import create_access_token
from flask_mail import Mail, Message
import bcrypt
import random
from config import Config
import logging

auth_bp = Blueprint('auth', __name__)
client = MongoClient(Config.MONGO_URI)
db = client['online_exam']
users_collection = db['users']
mail = Mail()

logger = logging.getLogger(__name__)

@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200
    data = request.get_json()
    if not data or 'password' not in data or 'email' not in data:
        logger.error("Missing required fields in registration request")
        return jsonify({'message': 'Missing required fields'}), 400
    password = data['password'].encode('utf-8')
    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
    user = {
        'name': data['name'],
        'email': data['email'],
        'password': hashed_password,
        'role': data['role'],
        'student_id': data['email'] if data['role'] == 'student' else None
    }
    if users_collection.find_one({'email': data['email']}):
        logger.warning(f"Email already exists: {data['email']}")
        return jsonify({'message': 'Email already exists'}), 400
    result = users_collection.insert_one(user)
    logger.info(f"User registered: {data['email']}")
    return jsonify({'message': 'User registered successfully'}), 201

@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        logger.error("Missing email or password in login request")
        return jsonify({'message': 'Missing email or password'}), 400
    user = users_collection.find_one({'email': data['email']})
    if user and bcrypt.checkpw(data['password'].encode('utf-8'), user['password']):
        token = create_access_token(identity={'email': user['email'], 'role': user['role'], 'student_id': user.get('student_id')})
        logger.info(f"User logged in: {user['email']}")
        return jsonify({
            'token': token,
            'user': {
                'email': user['email'],
                'role': user['role'],
                'name': user['name'],
                'student_id': user.get('student_id')
            }
        }), 200
    logger.warning(f"Invalid login attempt for email: {data['email']}")
    return jsonify({'message': 'Invalid credentials'}), 401

@auth_bp.route('/forgot-password', methods=['POST', 'OPTIONS'])
def forgot_password():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200
    data = request.get_json()
    if not data or 'email' not in data:
        logger.error("Missing email in forgot-password request")
        return jsonify({'message': 'Missing email'}), 400
    user = users_collection.find_one({'email': data['email']})
    if user:
        verification_code = str(random.randint(100000, 999999))
        users_collection.update_one({'email': data['email']}, {'$set': {'reset_code': verification_code}})
        msg = Message('Password Reset Verification Code', sender=Config.MAIL_USERNAME, recipients=[data['email']])
        msg.body = f'Your verification code is: {verification_code}\nThis code is valid for 10 minutes.'
        try:
            mail.send(msg)
            logger.info(f"Verification code sent to: {data['email']}")
            return jsonify({'message': 'Verification code sent to your email'}), 200
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return jsonify({'message': 'Failed to send verification email'}), 500
    logger.warning(f"User not found for forgot-password: {data['email']}")
    return jsonify({'message': 'User not found'}), 404

@auth_bp.route('/verify-code', methods=['POST', 'OPTIONS'])
def verify_code():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200
    data = request.get_json()
    if not data or 'email' not in data or 'code' not in data:
        logger.error("Missing email or code in verify-code request")
        return jsonify({'message': 'Missing email or code'}), 400
    user = users_collection.find_one({'email': data['email'], 'reset_code': data['code']})
    if user:
        logger.info(f"Verification code verified for: {data['email']}")
        return jsonify({'message': 'Code verified successfully'}), 200
    logger.warning(f"Invalid or expired code for: {data['email']}")
    return jsonify({'message': 'Invalid or expired code'}), 400

@auth_bp.route('/reset-password', methods=['POST', 'OPTIONS'])
def reset_password():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200
    data = request.get_json()
    if not data or 'email' not in data or 'code' not in data or 'newPassword' not in data:
        logger.error("Missing required fields in reset-password request")
        return jsonify({'message': 'Missing required fields'}), 400
    user = users_collection.find_one({'email': data['email'], 'reset_code': data['code']})
    if user:
        new_password = data['newPassword'].encode('utf-8')
        hashed_password = bcrypt.hashpw(new_password, bcrypt.gensalt())
        users_collection.update_one(
            {'email': data['email']},
            {'$set': {'password': hashed_password, 'reset_code': None}}
        )
        logger.info(f"Password reset successfully for: {data['email']}")
        return jsonify({'message': 'Password reset successfully'}), 200
    logger.warning(f"Invalid or expired code for reset-password: {data['email']}")
    return jsonify({'message': 'Invalid or expired code'}), 400