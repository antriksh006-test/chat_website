from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import os 
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-hard-to-guess-string')
socketio = SocketIO(app, cors_allowed_origins="*")

active_rooms = set()

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
        # data now contains 'msg', 'user', and potentially 'type'
        emit('message', {
            'msg': data['msg'], 
            'user': data['username'], 
            'type': data.get('type', 'text') # Default to text
        }, to=room)

if __name__ == '__main__':
    # Use 0.0.0.0 so the server is accessible externally
    socketio.run(app, host='0.0.0.0', port=5000)