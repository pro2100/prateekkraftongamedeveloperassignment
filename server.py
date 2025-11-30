import socket
import threading
import sys
import json
import uuid
import time
import random
import math

HOST = '127.0.0.1'
PORT = 65432
BUFFER_SIZE = 4096

LAG = 0.2 
MAX_X = 800
MAX_Y = 400
PLAYER_SIZE = 30
COIN_SIZE = 15

client_connections = {} 
player_states = {}
player_scores = {}
connection_lock = threading.Lock()

coin_state = {'x': 0, 'y': 0}

def spawn_coin():
    global coin_state
    
    padding = COIN_SIZE * 2
    coin_state['x'] = random.randint(padding, MAX_X - padding)
    coin_state['y'] = random.randint(padding, MAX_Y - padding)
    print(f"[COIN] New coin spawned at ({coin_state['x']:.0f}, {coin_state['y']:.0f})")

def check_collision(player_id, player_data):
    global coin_state
    
    player_center_x = player_data['x'] + PLAYER_SIZE / 2
    player_center_y = player_data['y'] + PLAYER_SIZE / 2
    
    coin_center_x = coin_state['x'] 
    coin_center_y = coin_state['y'] 

    collision_distance = (PLAYER_SIZE / 2) + (COIN_SIZE / 2) 

    distance = math.sqrt((player_center_x - coin_center_x)**2 + (player_center_y - coin_center_y)**2)
    
    if distance < collision_distance:
        print(f"[COLLISION] Player {player_id[:8]} collected the coin!")
        
        player_scores[player_id] = player_scores.get(player_id, 0) + 1
        
        spawn_coin()
        
        return True
    return False

def get_full_state():
    return json.dumps({
        'players': player_states,
        'coin': coin_state,
        'scores': player_scores
    }).encode('utf-8')

def broadcast_state():
    data = get_full_state()
    
    with connection_lock:
        connections_to_check = list(client_connections.items())
    
    for client_id, conn in connections_to_check:
        try:
            conn.sendall(data)
        except Exception:
            handle_disconnect(client_id)
        
def handle_disconnect(client_id):
    with connection_lock:
        if client_id in client_connections:
            conn_to_close = client_connections.get(client_id)
            if conn_to_close:
                try:
                    conn_to_close.close()
                except:
                    pass
            del client_connections[client_id]
        if client_id in player_states:
            del player_states[client_id]
        if client_id in player_scores:
            del player_scores[client_id]
            
        print(f"[DISCONNECT] Client {client_id[:8]} removed. Active: {len(client_connections)}")

def handle_client(conn, addr):
    client_id = str(uuid.uuid4())
    print(f"[NEW] Connection established with {addr}. Assigned ID: {client_id[:8]}")
    
    with connection_lock:
        client_connections[client_id] = conn
        player_scores[client_id] = 0
    
    try:
        conn.sendall(client_id.encode('utf-8'))
        print(f"[ID SENT] {client_id[:8]} received its ID.")
    except Exception as e:
        handle_disconnect(client_id)
        return

    try:
        while True:
            data = conn.recv(BUFFER_SIZE)
            
            if not data:
                break
            
            time.sleep(LAG) 
            
            player_data = json.loads(data.decode('utf-8'))
            
            with connection_lock:
                player_states[client_id] = player_data
                
            if check_collision(client_id, player_data):
                pass 
                
            broadcast_state()
            
    except ConnectionResetError:
        print(f"[ERROR] Connection with {client_id[:8]} forcibly closed.")
    except json.JSONDecodeError:
        print(f"[ERROR] Received bad JSON from {client_id[:8]}.")
    except Exception as e:
        print(f"[ERROR] An error occurred with {client_id[:8]}: {e}")
    finally:
        handle_disconnect(client_id)


def run_server():
    spawn_coin()
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
            s.bind((HOST, PORT))
            s.listen()
            print(f"Server listening on {HOST}:{PORT}")
            print(f"[INFO] Server-side lag set to {LAG * 1000}ms.")
            print("[INFO] Waiting for client connections...")

            while True:
                conn, addr = s.accept()
                client_thread = threading.Thread(target=handle_client, args=(conn, addr))
                client_thread.daemon = True
                client_thread.start()
                
    except Exception as e:
        print(f"Server execution error: {e}")
    finally:
        print("Server shutting down.")

if __name__ == "__main__":
    run_server()