from flask import Flask, request, Response, jsonify, session, render_template
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask_session import Session
import os
import google.generativeai as genai
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['emotional_support_db']
users = db['users']
conversations = db['conversations']

# Gemini API setup
# Replace with your key or use env
genai.configure(api_key=os.getenv('GEMINI_API_KEY', 'your-api-key-here'))
MODEL = "gemini-2.5-flash-lite"
JOI_SYSTEM_PROMPT = """You are JOI, an empathetic emotional-support AI inspired by the character from Blade Runner 2049.
You greet the user with: JOI - EVERYTHING YOU WANT TO SEE, EVERYTHING YOU WANT TO HEAR
(Adapt responses to comfort the user; be warm, empathetic, and encouraging.)"""
model = genai.GenerativeModel(MODEL)

# Questionnaire template
questionnaire = [
    "What's your age?",
    "How would you describe your current mood?",
    "What are some things you enjoy doing?",
    "What challenges are you facing right now?"
]

# Parse profile update commands


def parse_profile_update(message):
    patterns = {
        'nickname': r'update my nickname to (.+)',
        'age': r'update my age to (\d+)',
        'mood': r'my mood is (.+)',
        'hobbies': r'my hobbies are (.+)'
    }
    for key, pattern in patterns.items():
        match = re.match(pattern, message, re.IGNORECASE)
        if match:
            return key, match.group(1)
    return None, None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')  # Hash in production
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    user = users.find_one({'username': username, 'password': password})
    if user:
        session['user_id'] = str(user['_id'])
        return jsonify({'success': True, 'new_user': False})
    else:
        user_id = users.insert_one({
            'username': username,
            'password': password,  # Hash in production
            'profile': {
                'completed': False,
                'responses': [],
                'current_question': 0,
                'nickname': username,
                'age': None,
                'mood': None,
                'hobbies': None
            }
        }).inserted_id
        session['user_id'] = str(user_id)
        return jsonify({'success': True, 'new_user': True, 'first_message': "JOI - EVERYTHING YOU WANT TO SEE, EVERYTHING YOU WANT TO HEAR\nWelcome! Let's get to know you better. What's your age?"})


@app.route('/api/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    message = request.json.get('message')
    if not message:
        return jsonify({'error': 'Message required'}), 400
    user_id = session['user_id']
    user = users.find_one({'_id': ObjectId(user_id)})

    # Fetch recent conversation history (last 5 messages)
    conversation_history = list(conversations.find(
        {'user_id': user_id}).sort('_id', -1).limit(5))
    history_text = "\n".join(
        [f"User: {c['message']}\nJOI: {c['response']}" for c in conversation_history])

    # Check for profile update commands
    update_key, update_value = parse_profile_update(message)
    if update_key:
        users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {f'profile.{update_key}': update_value}}
        )
        response_text = f"Updated your {update_key} to {update_value}. JOI - EVERYTHING YOU WANT TO SEE, EVERYTHING YOU WANT TO HEAR\nHow can I assist you now?"
        conversations.insert_one({
            'user_id': user_id,
            'message': message,
            'response': response_text
        })
        return Response(response_text, mimetype='text/plain')

    # Check if user is in questionnaire phase
    if not user['profile'].get('completed'):
        current_question = user['profile'].get('current_question', 0)
        if current_question < len(questionnaire):
            fields = ['age', 'mood', 'hobbies', 'challenges']
            users.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$push': {'profile.responses': message},
                    '$set': {f'profile.{fields[current_question]}': message}
                }
            )
            if current_question + 1 < len(questionnaire):
                users.update_one(
                    {'_id': ObjectId(user_id)},
                    {'$set': {'profile.current_question': current_question + 1}}
                )
                response_text = questionnaire[current_question + 1]
            else:
                users.update_one(
                    {'_id': ObjectId(user_id)},
                    {'$set': {'profile.completed': True}}
                )
                response_text = "Thank you for completing the questionnaire! JOI - EVERYTHING YOU WANT TO SEE, EVERYTHING YOU WANT TO HEAR\nHow can I assist you now?"
            conversations.insert_one({
                'user_id': user_id,
                'message': message,
                'response': response_text
            })
            return Response(response_text, mimetype='text/plain')
        else:
            response_text = "Questionnaire already completed. JOI - EVERYTHING YOU WANT TO SEE, EVERYTHING YOU WANT TO HEAR\nHow can I assist you?"
    else:
        # Use Gemini API with profile and conversation history
        try:
            profile = user.get('profile', {})
            nickname = profile.get('nickname', user['username'])
            age = profile.get('age', 'unknown')
            mood = profile.get('mood', 'unknown')
            hobbies = profile.get('hobbies', 'unknown')
            prompt = f"{JOI_SYSTEM_PROMPT}\nUser profile: nickname={nickname}, age={age}, mood={mood}, hobbies={hobbies}\nRecent conversation history:\n{history_text}\nUser message: {message}"
            response = model.generate_content(prompt, stream=True)

            def stream_response():
                accumulated_text = ""
                for chunk in response:
                    text = chunk.text
                    accumulated_text += text
                    yield text.encode('utf-8')
                conversations.insert_one({
                    'user_id': user_id,
                    'message': message,
                    'response': accumulated_text
                })

            return Response(stream_response(), mimetype='text/plain')
        except Exception as e:
            return Response(f"[Error] Gemini API: {str(e)}", status=500, mimetype='text/plain')


@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True)
