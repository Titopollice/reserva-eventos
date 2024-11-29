import json
import os
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import threading
import time
from contextlib import contextmanager
from threading import Lock, Timer

app = Flask(__name__)
socketio = SocketIO(app)

# Caminho para o arquivo de dados JSON
EVENTS_FILE = 'events.json'

# Função para carregar eventos do arquivo JSON
def load_events():
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE, 'r') as file:
            return json.load(file)
    else:
        # Se o arquivo não existir, retorna uma lista padrão de eventos
        return [
            {"id": 1, "name": "Evento 1", "slots": 5},
            {"id": 2, "name": "Evento 2", "slots": 5},
            {"id": 3, "name": "Evento 3", "slots": 5},
            {"id": 4, "name": "Evento 4", "slots": 5},
            {"id": 5, "name": "Evento 5", "slots": 5},
        ]

# Função para salvar eventos no arquivo JSON
def save_events():
    with open(EVENTS_FILE, 'w') as file:
        json.dump(events, file, indent=4)

# Carrega os eventos ao iniciar o servidor
events = load_events()

# Queue and locks
queue = []
lock = threading.Lock()

# User ID counter
user_id_counter = 1

# Constants
RESERVATION_TIMEOUT = 120  # 2 minutes
QUEUE_TIMEOUT = 30  # 30 seconds

# No início do arquivo, adicione:
online_users = set()

@contextmanager
def timeout_lock(lock, timeout=5):
    result = lock.acquire(timeout=timeout)
    if not result:
        raise TimeoutError("Não foi possível adquirir o lock")
    try:
        yield
    finally:
        lock.release()

@app.route('/')
def index():
    return render_template('index.html', events=events)

@socketio.on('connect')
def handle_connect():
    global user_id_counter
    # Verifica se a conexão veio da página de admin
    if request.referrer and '/adm' in request.referrer:
        return  # Não adiciona admin na fila
        
    with lock:
        online_users.add(request.sid)
        user_id = f"User {user_id_counter}"
        user_id_counter += 1
        queue.append({"sid": request.sid, "user_id": user_id})
        
        # Emite o ID do usuário para ele mesmo
        emit('your_user_id', {'user_id': user_id})
        
        # Emite atualização da fila e usuários online para TODOS os clientes
        socketio.emit('update_queue', {'queue': [user['user_id'] for user in queue]})
        socketio.emit('update_online_users', {'count': len(online_users)})
        
        if queue:
            socketio.emit('current_state', {
                'current_user': queue[0]['user_id'],
                'time_left': QUEUE_TIMEOUT
            })

@socketio.on('reserve_slot')
def handle_reserve_slot(data):
    try:
        with timeout_lock(lock):
            if not queue or request.sid != queue[0]['sid']:
                emit('error', {'message': 'Fila Em Andamento'}, room=request.sid)
                return

            event_id = data['event_id']
            for event in events:
                if event['id'] == event_id and event['slots'] > 0:
                    event['slots'] -= 1
                    # Emitir para todos os clientes
                    socketio.emit('update_events', events)
                    save_events()  # Salva os eventos após a reserva
                    
                    threading.Thread(target=reservation_timer, args=(event_id,)).start()
                    
                    # Remove o usuário atual da fila
                    queue.pop(0)
                    
                    # Atualiza a fila e inicia o timer para o próximo
                    if queue:
                        socketio.emit('update_queue', {'queue': [user['user_id'] for user in queue]})
                        socketio.emit('current_state', {
                            'current_user': queue[0]['user_id'],
                            'time_left': QUEUE_TIMEOUT
                        })
                    else:
                        # Se não há mais ninguém na fila, emite uma fila vazia e limpa o estado atual
                        socketio.emit('update_queue', {'queue': []})
                        socketio.emit('current_state', {
                            'current_user': '-',
                            'time_left': QUEUE_TIMEOUT
                        })
                    return
            emit('error', {'message': 'Vagas Encerradas, escolha outro evento'}, room=request.sid)
    except TimeoutError:
        emit('error', {'message': 'Tente Novamente'}, room=request.sid)

@socketio.on('time_expired')
def handle_time_expired():
    with lock:
        if queue:
            # Move o primeiro usuário para o final da fila
            expired_user = queue.pop(0)
            queue.append(expired_user)
            
            # Emite atualização da fila para todos
            socketio.emit('update_queue', {'queue': [user['user_id'] for user in queue]})
            
            # Se ainda houver pessoas na fila, atualiza o estado
            if queue:
                socketio.emit('current_state', {
                    'current_user': queue[0]['user_id'],
                    'time_left': QUEUE_TIMEOUT
                })

def reservation_timer(event_id):
    time.sleep(RESERVATION_TIMEOUT)
    with lock:
        for event in events:
            if event['id'] == event_id:
                event['slots'] += 1
                # Emitir para todos os clientes
                socketio.emit('update_events', events)
                save_events()  # Salva os eventos após o timeout
                break

@socketio.on('disconnect')
def handle_disconnect():
    with lock:
        online_users.discard(request.sid)
        queue[:] = [user for user in queue if user['sid'] != request.sid]
        socketio.emit('update_queue', {'queue': [user['user_id'] for user in queue]})
        socketio.emit('update_online_users', {'count': len(online_users)})
        if queue:
            socketio.emit('current_state', {
                'current_user': queue[0]['user_id'],
                'time_left': QUEUE_TIMEOUT
            })

@socketio.on('request_state')
def handle_request_state():
    with lock:
        if queue:
            socketio.emit('current_state', {
                'current_user': queue[0]['user_id'],
                'time_left': QUEUE_TIMEOUT
            })

def update_queue():
    socketio.emit('update_queue', {'queue': [user['user_id'] for user in queue]})
    if queue:
        socketio.emit('current_state', {
            'current_user': queue[0]['user_id'],
            'time_left': QUEUE_TIMEOUT
        })
        threading.Thread(target=queue_timer, args=(queue[0]['sid'],)).start()

def queue_timer(sid):
    time.sleep(QUEUE_TIMEOUT)
    with lock:
        if queue and queue[0]['sid'] == sid:
            # Se o usuário ainda está na frente da fila após o timeout
            socketio.emit('time_expired')
            handle_time_expired()

@app.route('/adm')
def admin():
    return render_template('admin.html', events=events)

@socketio.on('update_event')
def handle_update_event(data):
    with lock:
        event_id = data['id']
        for event in events:
            if event['id'] == event_id:
                event['name'] = data['name']
                event['slots'] = data['slots']
                save_events()  # Salva os eventos após a atualização
                socketio.emit('update_events', events)
                break

@socketio.on('add_event')
def handle_add_event(data):
    with lock:
        new_id = max([event['id'] for event in events], default=0) + 1
        new_event = {
            'id': new_id,
            'name': data['name'],
            'slots': data['slots']
        }
        events.append(new_event)
        save_events()  # Salva os eventos após adicionar um novo
        socketio.emit('update_events', events)

@socketio.on('delete_event')
def handle_delete_event(data):
    with lock:
        events[:] = [event for event in events if event['id'] != data['id']]
        save_events()  # Salva os eventos após a exclusão
        socketio.emit('update_events', events)

if __name__ == '__main__':
    socketio.run(app, debug=True)
