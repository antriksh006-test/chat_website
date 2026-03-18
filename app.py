from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import os 
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-hard-to-guess-string')
socketio = SocketIO(app, cors_allowed_origins="*")

active_rooms = set()
room_history = {} # Stores latest 50 messages per room

# 1. Define the function FIRST
def update_room_list():
    emit('room_list', list(active_rooms), broadcast=True)

@app.route('/')
def index():
    return jsonify({"status": "Backend is running!"})

# 2. Add 'auth' as an argument to fix the TypeError
@socketio.on('connect')
def handle_connect(auth):
    print("Client connected")
    update_room_list() 

@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    active_rooms.add(room)
    update_room_list() # Now this will work because it's defined above!

    # Send past messages just to the user joining
    history = room_history.get(room, [])
    emit('chat_history', history)

    send(f"{username} has entered the room: {room}", to=room)

@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    send(f"{username} has left the room.", to=room)

@socketio.on('message')
def handle_message(data):
    room = data.get('room')
    if room:
        msg_obj = {
            'msg': data['msg'], 
            'user': data['username'], 
            'type': data.get('type', 'text')
        }

        # Save message to history (cap at 50 messages)
        if room not in room_history:
            room_history[room] = []
        room_history[room].append(msg_obj)
        if len(room_history[room]) > 50:
            room_history[room].pop(0)

        emit('message', msg_obj, to=room)

if __name__ == '__main__':
    # Use 0.0.0.0 so the server is accessible externally
    socketio.run(app, host='0.0.0.0', port=5000)