import os
import logging
from flask import Flask, request, jsonify, session, render_template, send_from_directory
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Set up Groq API key
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.secret_key = os.urandom(24)  # Set a secret key for session management

# SQLAlchemy configuration
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance')
os.makedirs(db_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(db_path, "chats.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Set up rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)


class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    messages = db.relationship('Message', backref='chat', lazy=True)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    is_user = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    chat_id = db.Column(db.Integer, db.ForeignKey('chat.id'), nullable=False)


with app.app_context():
    db.create_all()


def get_ai_response(user_input, conversation_history):
    try:
        messages = [
            {
                "role": "system",
                "content": "You are a kawaii shy anime girl. Respond in a cute, shy manner, using anime-style expressions and mannerisms. Use emoticons and occasional Japanese words. Keep responses brief and sweet. Remember information from previous messages in the conversation."
            }
        ]

        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_input})

        completion = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=messages,
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=True,
            stop=None,
        )

        full_response = ""
        for chunk in completion:
            if chunk.choices[0].delta.content is not None:
                full_response += chunk.choices[0].delta.content

        return full_response.strip()
    except Exception as e:
        logger.error(f"Error creating completion: {e}")
        return "G-gomen nasai... I couldn't process that request. (⌒_⌒;)"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


@app.route('/api/chat', methods=['POST'])
@limiter.limit("10 per minute")
def chat():
    logger.info("Received request to /api/chat")
    logger.info(f"Request data: {request.json}")
    try:
        data = request.json
        user_message = data['message']
        chat_id = data.get('chat_id')

        if not user_message:
            return jsonify({'error': 'No message provided'}), 400

        if not chat_id:
            new_chat = Chat()
            db.session.add(new_chat)
            db.session.commit()
            chat_id = new_chat.id

        chat = Chat.query.get(chat_id)
        conversation_history = [{"role": "user" if msg.is_user else "assistant", "content": msg.content} for msg in
                                chat.messages]

        ai_response = get_ai_response(user_message, conversation_history)

        user_message_db = Message(content=user_message, is_user=True, chat_id=chat_id)
        ai_message_db = Message(content=ai_response, is_user=False, chat_id=chat_id)
        db.session.add(user_message_db)
        db.session.add(ai_message_db)
        db.session.commit()

        return jsonify({'response': ai_response, 'chat_id': chat_id})
    except KeyError as e:
        logger.error(f"Missing key in request data: {e}")
        return jsonify({'error': 'Invalid request data'}), 400
    except Exception as e:
        logger.error(f"Unexpected error in chat route: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


@app.route('/api/chat/<int:chat_id>')
def get_chat(chat_id):
    try:
        chat = Chat.query.get_or_404(chat_id)
        messages = [{"content": msg.content, "is_user": msg.is_user} for msg in chat.messages]
        return jsonify({"messages": messages})
    except Exception as e:
        logger.error(f"Error retrieving chat: {e}")
        return jsonify({'error': 'An error occurred while retrieving the chat'}), 500


@app.route('/api/chats')
def get_all_chats():
    try:
        chats = Chat.query.order_by(Chat.created_at.desc()).all()
        return jsonify({"chats": [{"id": chat.id, "created_at": chat.created_at.isoformat()} for chat in chats]})
    except Exception as e:
        logger.error(f"Error retrieving all chats: {e}")
        return jsonify({'error': 'An error occurred while retrieving chats'}), 500


@app.route('/health')
def health_check():
    return jsonify({'status': 'ok'}), 200


def cleanup_old_chats():
    try:
        one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        old_chats = Chat.query.filter(Chat.created_at < one_week_ago).all()
        for chat in old_chats:
            db.session.delete(chat)
        db.session.commit()
        logger.info(f"Cleaned up {len(old_chats)} old chats")
    except Exception as e:
        logger.error(f"Error cleaning up old chats: {e}")


if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=cleanup_old_chats, trigger="interval", hours=24)
    scheduler.start()

    with app.app_context():
        cleanup_old_chats()  # Clean up old chats on startup

    app.run(host='0.0.0.0', port=5000, debug=True)
