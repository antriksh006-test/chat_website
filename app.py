from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import os 
from datetime import datetime
import re

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-hard-to-guess-string')
socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=10485760) # 10MB max

room_info = {} # Maps room_name -> {'is_private': bool, 'password': str, 'limit': int, 'users': {username: color}}
room_history = {} # Stores latest 50 messages per room
session_users = {} # Maps connections: {'sid': {'username': 'u', 'room': 'r', 'color': 'color'}}

def filter_profanity(text):
    bad_words = ['fuck', 'shit', 'bitch', 'asshole', 'crap']
    for word in bad_words:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        text = pattern.sub('*'*len(word), text)
    return text

def broadcast_room_users(room):
    if room in room_info:
        users_list = [{'name': u, 'color': room_info[room]['users'][u]} for u in room_info[room]['users']]
        socketio.emit('room_users', users_list, to=room)

# 1. Define the function FIRST
def update_room_list():
    rooms_data = [{'name': r, 'private': room_info[r].get('is_private', False)} for r in room_info.keys()]
    emit('room_list', rooms_data, broadcast=True)

@app.route('/')
def index():
    return jsonify({"status": "Backend is running!"})

# 2. Add 'auth' as an argument to fix the TypeError
@socketio.on('connect')
def handle_connect(auth):
    print("Client connected")
    update_room_list() 

@socketio.on('disconnect')
def handle_disconnect():
    user = session_users.get(request.sid)
    if user:
        username = user['username']
        room = user['room']
        if room in room_info and username in room_info[room]['users']:
            del room_info[room]['users'][username]
            broadcast_room_users(room)
            if len(room_info[room]['users']) == 0:
                del room_info[room]
                if room in room_history:
                    del room_history[room]
                update_room_list()
        del session_users[request.sid]
        send(f"{username} has disconnected.", to=room)

@socketio.on('create_room')
def on_create_room(data):
    room = data['room'].strip()
    if not room:
        emit('create_error', {'error': 'Room name cannot be empty!'})
        return
        
    if room in room_info:
        emit('create_error', {'error': 'Room already exists! Join it instead.'})
        return

    room_info[room] = {
        'is_private': data.get('is_private', False),
        'password': data.get('password', ''),
        'limit': int(data.get('limit', 10)),
        'users': {}
    }
    
    emit('create_success', {'room': room})
    update_room_list()

@socketio.on('join')
def on_join(data):
    username = data['username'].strip()
    room = data['room'].strip()
    password = data.get('password', '')
    color = data.get('color', '#000000')
    
    if not username or not room:
        emit('join_error', {'error': 'Username and room cannot be empty!'})
        return
        
    if room not in room_info:
        emit('join_error', {'error': f"Room '{room}' doesn't exist! Create it first."})
        return
        
    info = room_info[room]
    
    if info['is_private'] and info['password'] != password:
        emit('join_error', {'error': 'Incorrect room password!'})
        return
        
    if len(info['users']) >= info['limit']:
        emit('join_error', {'error': f"Room '{room}' is full! (Limit: {info['limit']})"})
        return
        
    if username in info['users']:
        emit('join_error', {'error': f"Username '{username}' is already taken in this room!"})
        return
        
    join_room(room)
    info['users'][username] = color
    session_users[request.sid] = {'username': username, 'room': room, 'color': color}
    
    update_room_list()
    broadcast_room_users(room)

    history = room_history.get(room, [])
    emit('chat_history', history)

    send(f"{username} has entered the room: {room} ({len(info['users'])}/{info['limit']})", to=room)

@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    
    if room in room_info and username in room_info[room]['users']:
        del room_info[room]['users'][username]
        broadcast_room_users(room)
        if len(room_info[room]['users']) == 0:
            del room_info[room]
            if room in room_history:
                del room_history[room]
            update_room_list()
            
    if request.sid in session_users:
        del session_users[request.sid]
        
    send(f"{username} has left the room.", to=room)

@socketio.on('typing')
def handle_typing(data):
    user_info = session_users.get(request.sid)
    if user_info:
        emit('typing', {'user': user_info['username'], 'is_typing': data.get('is_typing', True)}, to=user_info['room'], include_self=False)

@socketio.on('message')
def handle_message(data):
    user_info = session_users.get(request.sid)
    if not user_info:
        return
        
    room = user_info['room']
    
    raw_msg = data['msg']
    if data.get('type', 'text') == 'text':
        raw_msg = filter_profanity(raw_msg)
        
    msg_obj = {
        'msg': raw_msg, 
        'user': user_info['username'], 
        'color': user_info.get('color', '#000000'),
        'type': data.get('type', 'text'),
        'timestamp': datetime.now().strftime("%I:%M %p")
    }

    if room not in room_history:
        room_history[room] = []
    room_history[room].append(msg_obj)
    if len(room_history[room]) > 50:
        room_history[room].pop(0)

    emit('message', msg_obj, to=room)

if __name__ == '__main__':
    # Use 0.0.0.0 so the server is accessible externally
    socketio.run(app, host='0.0.0.0', port=5000)