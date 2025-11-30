import pygame
import socket, sys, json, random

HOST = '127.0.0.1'
PORT = 65432
BUFFER_SIZE = 4096
client_socket = None
local_client_id = None
remote_game_state = {} 
coin_state = {'x': 0, 'y': 0}
player_scores = {}

local_client_cache = {} 
LERP_FACTOR = 0.25 

PLAYER_SIZE = 30
MOVE_SPEED = 15
MAX_X = 800
MAX_Y = 400
COIN_SIZE = 15

local_player_state = {
    'id': None,
    'x': 0,
    'y': 0,
    'r': 0,
    'g': 0,
    'b': 0,
    'username': 'Guest' 
}

def get_random_color():
    return (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))

def init_network():
    global client_socket, local_client_id
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Attempting to connect to {HOST}:{PORT}...")
        client_socket.connect((HOST, PORT))
        client_socket.settimeout(0.01)
        print("Successfully connected to the server.")
        
        client_socket.settimeout(1.0)
        id_data = client_socket.recv(BUFFER_SIZE)
        client_socket.settimeout(0.01)
        
        if id_data:
            local_client_id = id_data.decode('utf-8').strip()
            
            local_player_state.update({
                'id': local_client_id,
                'x': random.randint(50, MAX_X - 50),
                'y': random.randint(50, MAX_Y - 50),
                'r': get_random_color()[0],
                'g': get_random_color()[1],
                'b': get_random_color()[2],
            })
            
            print(f"Received client ID: {local_client_id[:8]}")
            return True
        return False
            
    except socket.timeout:
        print("Error: Timed out waiting for client ID from server.")
    except ConnectionRefusedError:
        print(f"Error: Could not connect to the server at {HOST}:{PORT}. Ensure server.py is running.")
    except Exception as e:
        print(f"Network error during connection: {e}")
    return False

def send_state():
    if not client_socket or not local_client_id:
        return False
    
    try:
        client_socket.sendall(json.dumps(local_player_state).encode('utf-8'))
        return True
    except ConnectionResetError:
        print("Connection lost (Server reset).")
    except Exception as e:
        print(f"Error during sending: {e}")
    return False

def receive_state():
    global remote_game_state, coin_state, player_scores
    if not client_socket:
        return None
    try:
        data = client_socket.recv(BUFFER_SIZE)
        if data:
            full_state = json.loads(data.decode('utf-8'))
            
            remote_game_state = full_state.get('players', {})
            coin_state = full_state.get('coin', coin_state)
            player_scores = full_state.get('scores', player_scores)
            
            if local_client_id in remote_game_state:
                return local_client_id
            
            return None
        return "Server disconnected."
    except socket.timeout:
        return None
    except json.JSONDecodeError:
        return None
    except ConnectionResetError:
        print("Connection lost (Server reset).")
        return "Connection Lost."
    except Exception as e:
        print(f"Error during communication: {e}")
        return "Communication Error."

def update_local_position(command):
    x, y = local_player_state['x'], local_player_state['y']
    moved = False

    if command == 'w':
        y = max(y - MOVE_SPEED, 0)
        moved = True
    elif command == 's':
        y = min(y + MOVE_SPEED, MAX_Y - PLAYER_SIZE)
        moved = True
    elif command == 'a':
        x = max(x - MOVE_SPEED, 0)
        moved = True
    elif command == 'd':
        x = min(x + MOVE_SPEED, MAX_X - PLAYER_SIZE)
        moved = True

    if moved:
        local_player_state.update({'x': x, 'y': y})
        
    return moved

pygame.init()

SCREEN_WIDTH, SCREEN_HEIGHT = MAX_X, MAX_Y
total_screen_height = SCREEN_HEIGHT + 70
screen = pygame.display.set_mode((SCREEN_WIDTH, total_screen_height))

COLORS = {
    'WHITE': (255, 255, 255),
    'BLACK': (10, 10, 10),
    'YELLOW': (255, 200, 0),
    'GREEN': (40, 167, 69),
    'RED': (200, 50, 50),
    'BLUE': (50, 150, 255),
    'GAME_AREA': (30, 30, 30)
}

try:
    font = pygame.font.Font(None, 28)
    score_font = pygame.font.Font(None, 22)
except pygame.error:
    font = pygame.font.SysFont("monospace", 24)
    score_font = pygame.font.SysFont("monospace", 18)

def draw_text(surface, text, color, x, y, size='normal'):
    if size == 'normal':
        text_surface = font.render(text, True, color)
    else:
        text_surface = score_font.render(text, True, color)
    surface.blit(text_surface, (x, y))

def draw_coin(surface):
    if coin_state and 'x' in coin_state and 'y' in coin_state:
        coin_rect = pygame.Rect(coin_state['x'], coin_state['y'], COIN_SIZE, COIN_SIZE)
        pygame.draw.circle(surface, COLORS['YELLOW'], coin_rect.center, COIN_SIZE // 2)

def draw_players(surface):
    
    if local_client_id:
        local_client_cache[local_client_id] = local_player_state
    
    for player_id, data in local_client_cache.items():
        if 'x' in data and 'y' in data: 
            x, y = data.get('x', 0), data.get('y', 0)
            color = (data.get('r', 255), data.get('g', 255), data.get('b', 255))
            rect = pygame.Rect(x, y, PLAYER_SIZE, PLAYER_SIZE)
            
            pygame.draw.rect(surface, color, rect, 0, 8)
            
            username = data.get('username', player_id[:4])
            score = player_scores.get(player_id, 0)
            
            if player_id == local_client_id:
                pygame.draw.rect(surface, COLORS['WHITE'], rect, 3, 8)
            else:
                draw_text(surface, username, COLORS['WHITE'], x, y - 20)

def draw_ui(surface):
    status_color = COLORS['GREEN']
    players_count = len(local_client_cache)
    
    if not is_connected:
        status_text, status_color = "STATUS: DISCONNECTED", COLORS['RED']
    elif local_client_id is None:
        status_text, status_color = "STATUS: Connecting", COLORS['BLUE']
    else:
        status_text = f"STATUS: Connected | Players: {players_count} | ID: {local_client_id[:8]} | User: {local_player_state['username']}"
        
    
    score_list = sorted(player_scores.items(), key=lambda item: item[1], reverse=True)
    score_y = SCREEN_HEIGHT + 10
    score_x = SCREEN_WIDTH - 150
    
    draw_text(surface, "SCOREBOARD:", COLORS['WHITE'], score_x, score_y, size='small')
    
    for i, (p_id, score) in enumerate(score_list):
        username = remote_game_state.get(p_id, {}).get('username', p_id[:4])
        score_text = f"{i+1}. {username}: {score}"
        draw_text(surface, score_text, COLORS['WHITE'], score_x, score_y + 15 + (i * 15), size='small')


def get_user_input(surface):
    input_box = pygame.Rect(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2, 300, 40)
    user_text = ''
    done = False
    
    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if user_text:
                        done = True
                elif event.key == pygame.K_BACKSPACE:
                    user_text = user_text[:-1]
                else:
                    if len(user_text) < 12:
                        user_text += event.unicode
        
        surface.fill(COLORS['BLACK'])
        
        prompt_text = "Username"
        draw_text(surface, prompt_text, COLORS['WHITE'], SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 50)
        pygame.draw.rect(surface, COLORS['WHITE'], input_box, 2)
        draw_text(surface, user_text, COLORS['WHITE'], input_box.x + 5, input_box.y + 10)
        pygame.display.flip()
        pygame.time.Clock().tick(30)
        
    local_player_state['username'] = user_text
    print(f"Username set to: {user_text}")

def interpolate_state():
    for player_id, target_data in remote_game_state.items():
        if player_id == local_client_id:
            continue
            
        if player_id not in local_client_cache:
            local_client_cache[player_id] = target_data.copy()
            continue

        cached_data = local_client_cache[player_id]

        cached_data['x'] += (target_data['x'] - cached_data['x']) * LERP_FACTOR
        cached_data['y'] += (target_data['y'] - cached_data['y']) * LERP_FACTOR
        
        cached_data['r'] = target_data.get('r', cached_data['r'])
        cached_data['g'] = target_data.get('g', cached_data['g'])
        cached_data['b'] = target_data.get('b', cached_data['b'])
        cached_data['username'] = target_data.get('username', cached_data['username'])


def run_game_loop():
    global is_connected
    
    running = True
    is_connected = init_network()
    
    last_send_time = pygame.time.get_ticks()
    SEND_INTERVAL = 200 
    
    if is_connected:
        get_user_input(screen)
        send_state()
        
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
        movement_occurred = False
        if is_connected:
            keys = pygame.key.get_pressed()
            current_time = pygame.time.get_ticks()
            
            if keys[pygame.K_w] and update_local_position('w'): movement_occurred = True
            if keys[pygame.K_s] and update_local_position('s'): movement_occurred = True
            if keys[pygame.K_a] and update_local_position('a'): movement_occurred = True
            if keys[pygame.K_d] and update_local_position('d'): movement_occurred = True

            if movement_occurred and (current_time - last_send_time >= SEND_INTERVAL):
                if not send_state():
                    is_connected = False
                else:
                    last_send_time = current_time
                
        if is_connected:
            received_status = receive_state()
            
            if isinstance(received_status, str) and ("Connection" in received_status or "Error" in received_status):
                is_connected = False
                print(f"Received disconnection message: {received_status}")
        
        interpolate_state()
        
        screen.fill(COLORS['BLACK'])
        pygame.draw.rect(screen, COLORS['GAME_AREA'], pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        
        if is_connected and local_client_id:
            draw_coin(screen)
            draw_players(screen)
        elif not is_connected:
            draw_text(screen, "NOT CONNECTED. Check console for error.", COLORS['RED'], SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT//2)
        else:
            draw_text(screen, "Waiting for initial ID...", COLORS['WHITE'], SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT//2)
            
        draw_ui(screen)
        
        pygame.display.flip()

        pygame.time.Clock().tick(30) 

    if client_socket:
        client_socket.close()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    run_game_loop()