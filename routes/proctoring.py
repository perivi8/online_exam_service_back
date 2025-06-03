from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.ai_proctoring import start_proctoring, detect_malpractice
from services.drive_service import upload_video
from pymongo import MongoClient
from config import Config
from datetime import datetime
from flask_mail import Mail, Message
import logging

proctoring_bp = Blueprint('proctoring', __name__)
client = MongoClient(Config.MONGO_URI)
db = client['online_exam']
proctoring_logs = db['proctoring_logs']
submissions_collection = db['submissions']
users_collection = db['users']
mail = Mail()

logger = logging.getLogger(__name__)

@proctoring_bp.route('/start-proctoring', methods=['POST', 'OPTIONS'])
@jwt_required()
def start_proctoring_route():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200
    current_user = get_jwt_identity()
    if current_user.get('role') != 'proctor':
        logger.warning(f"Unauthorized access to start-proctoring by {current_user.get('email')}")
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()
    if not data or 'student_id' not in data or 'exam_id' not in data:
        logger.error("Missing required fields in start-proctoring request")
        return jsonify({'message': 'Missing required fields'}), 400

    student_id = data['student_id']
    exam_id = data['exam_id']
    submission = submissions_collection.find_one({'exam_id': exam_id, 'student_id': student_id})
    if not submission or submission['status'] != 'in_progress':
        logger.warning(f"No active exam session for student {student_id}, exam {exam_id}")
        return jsonify({'message': 'No active exam session found'}), 400

    file_path = start_proctoring(student_id, exam_id)
    if not file_path:
        logger.error(f"Failed to record proctoring session for student {student_id}, exam {exam_id}")
        return jsonify({'message': 'Failed to record proctoring session'}), 500

    try:
        file_id = upload_video(file_path, f'proctoring_{student_id}_{exam_id}.avi')
        malpractice_detected = detect_malpractice(file_path, student_id, exam_id)
        if malpractice_detected:
            proctor = users_collection.find_one({'role': 'proctor'})
            student = users_collection.find_one({'student_id': student_id})
            if proctor and student:
                msg = Message('Malpractice Alert', sender=Config.MAIL_USERNAME, recipients=[proctor['email'], student['email']])
                msg.body = f'Malpractice detected for student {student_id} in exam {exam_id}. Please review.'
                mail.send(msg)
                logger.info(f"Malpractice alert sent for student {student_id}")
        logger.info(f"Proctoring session recorded and uploaded for student {student_id}, exam {exam_id}")
        return jsonify({'message': 'Proctoring session recorded and uploaded', 'file_id': file_id}), 200
    except Exception as e:
        logger.error(f"Proctoring failed for student {student_id}, exam {exam_id}: {str(e)}")
        return jsonify({'message': 'Proctoring failed'}), 500

@proctoring_bp.route('/log-malpractice', methods=['POST', 'OPTIONS'])
@jwt_required()
def log_malpractice():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200
    current_user = get_jwt_identity()
    if current_user.get('role') != 'proctor':
        logger.warning(f"Unauthorized access to log-malpractice by {current_user.get('email')}")
        return jsonify({'message': 'Unauthorized'}), 403

    data = request.get_json()
    if not data or 'student_id' not in data or 'exam_id' not in data or 'event' not in data:
        logger.error("Missing required fields in log-malpractice request")
        return jsonify({'message': 'Missing required fields'}), 400

    log = {
        'student_id': data['student_id'],
        'exam_id': data['exam_id'],
        'event': data['event'],
        'timestamp': datetime.now()
    }
    try:
        proctoring_logs.insert_one(log)
        logger.info(f"Malpractice logged for student {data['student_id']}, exam {data['exam_id']}")
        return jsonify({'message': 'Malpractice logged'}), 200
    except Exception as e:
        logger.error(f"Failed to log malpractice: {str(e)}")
        return jsonify({'message': 'Failed to log malpractice'}), 500

@proctoring_bp.route('/stop-exam/<exam_id>/<student_id>', methods=['POST', 'OPTIONS'])
@jwt_required()
def stop_exam(exam_id, student_id):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200
    current_user = get_jwt_identity()
    if current_user.get('role') != 'proctor':
        logger.warning(f"Unauthorized access to stop-exam by {current_user.get('email')}")
        return jsonify({'message': 'Unauthorized'}), 403

    submission = submissions_collection.find_one({'exam_id': exam_id, 'student_id': student_id})
    if not submission or submission['status'] != 'in_progress':
        logger.warning(f"No active exam session for student {student_id}, exam {exam_id}")
        return jsonify({'message': 'No active exam session found'}), 400

    try:
        submissions_collection.update_one(
            {'exam_id': exam_id, 'student_id': student_id},
            {'$set': {'status': 'terminated', 'terminated_at': datetime.now()}}
        )
        student = users_collection.find_one({'student_id': student_id})
        if student:
            msg = Message('Exam Terminated', sender=Config.MAIL_USERNAME, recipients=[student['email']])
            msg.body = f'Your exam {exam_id} has been terminated due to malpractice.'
            mail.send(msg)
            logger.info(f"Termination email sent to student {student_id}")
        logger.info(f"Exam {exam_id} terminated for student {student_id}")
        return jsonify({'message': 'Exam terminated successfully'}), 200
    except Exception as e:
        logger.error(f"Failed to terminate exam: {str(e)}")
        return jsonify({'message': 'Failed to terminate exam'}), 500

@proctoring_bp.route('/proctoring-logs', methods=['GET', 'OPTIONS'])
@jwt_required()
def get_proctoring_logs():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200

    current_user = get_jwt_identity()
    if current_user.get('role') != 'proctor':
        logger.warning(f"Unauthorized access to proctoring-logs by {current_user.get('email')}")
        return jsonify({'message': 'Unauthorized'}), 403

    try:
        logs = proctoring_logs.find()
        result = [{
            'student_id': log['student_id'],
            'exam_id': log['exam_id'],
            'event': log['event'],
            'timestamp': log['timestamp'].isoformat()
        } for log in logs]
        logger.info(f"Retrieved proctoring logs for user {current_user['email']}")
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Failed to retrieve proctoring logs: {str(e)}")
        return jsonify({'message': 'Failed to retrieve proctoring logs'}), 500

@proctoring_bp.route('/download-report/<student_id>/<exam_id>', methods=['GET', 'OPTIONS'])
@jwt_required()
def download_report(student_id, exam_id):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://online-exam-system-nine.vercel.app')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response, 200

    current_user = get_jwt_identity()
    if current_user.get('role') != 'proctor':
        logger.warning(f"Unauthorized access to download-report by {current_user.get('email')}")
        return jsonify({'message': 'Unauthorized'}), 403

    try:
        import os
        from flask import send_from_directory
        filename = f"proctoring_report_{student_id}_{exam_id}.xml"
        folder_path = os.path.dirname(os.path.abspath(__file__))
        logger.info(f"Attempting to download report: {filename}")
        return send_from_directory(folder_path, filename, as_attachment=True)
    except FileNotFoundError:
        logger.error(f"Report not found: {filename}")
        return jsonify({'error': 'Report not found'}), 404
    except Exception as e:
        logger.error(f"Failed to download report: {str(e)}")
        return jsonify({'error': 'Failed to download report'}), 500