import socket
import sys
import time
import random
import copy

def log(msg):
    print(msg)

def send_message(sock, msg):
    """Sends a message (appending a newline) over the socket."""
    full_msg = msg + "\n"
    sock.sendall(full_msg.encode())

def receive_message(file_obj):
    """Reads one line (i.e. one message) from the file-like socket object."""
    return file_obj.readline().strip()

def convert_coord(coord):
    """
    Converts an algebraic coordinate (e.g. 'a2') to board indices.
    Row 0 corresponds to rank 8; row 7 to rank 1.
    """
    col = ord(coord[0].lower()) - ord('a')
    row = 8 - int(coord[1])
    return row, col

def coord_to_algebraic(row, col):
    """Converts board indices to algebraic coordinate (e.g. 'a2')."""
    return chr(ord('a') + col) + str(8 - row)

def initialize_boards(setup_msg):
    """
    Parse the setup message (e.g. "Setup Wa2 Wb2 Wc2 ...")
    and create the 8x8 boolean bitmaps for white and black pawns.
    """
    white_bitmap = [[False for _ in range(8)] for _ in range(8)]
    black_bitmap = [[False for _ in range(8)] for _ in range(8)]
    tokens = setup_msg.split()
    # tokens[0] should be "Setup"
    for token in tokens[1:]:
        if len(token) < 3:
            continue
        color = token[0].upper()
        pos = token[1:]
        row, col = convert_coord(pos)
        if color == 'W':
            white_bitmap[row][col] = True
        elif color == 'B':
            black_bitmap[row][col] = True
    return white_bitmap, black_bitmap

def copy_boards(white, black):
    """
    Returns deep copies of the white and black bitmaps.
    (Used to simulate a move without altering the current board.)
    """
    new_white = [row[:] for row in white]
    new_black = [row[:] for row in black]
    return new_white, new_black

def execute_move(move, own_bitmap, opp_bitmap):
    """
    Updates the board state given a move in algebraic notation (e.g. "e2e4").
    - Removes the pawn from the source of own_bitmap.
    - If a pawn exists at the destination in opp_bitmap, it is "captured."
    - Places the pawn at the destination in own_bitmap.
    """
    from_coord = move[:2]
    to_coord = move[2:]
    r_from, c_from = convert_coord(from_coord)
    r_to, c_to = convert_coord(to_coord)
    # Remove the pawn from its source.
    own_bitmap[r_from][c_from] = False
    # Capture opponent pawn if present.
    if opp_bitmap[r_to][c_to]:
        log("Capture: Opponent's pawn removed!")
        opp_bitmap[r_to][c_to] = False
    # Place the pawn in the destination.
    own_bitmap[r_to][c_to] = True

def generate_all_legal_moves(role, own_bitmap, opp_bitmap):
    """
    Returns a list of moves as strings (e.g. "e2e4") for all pawns in own_bitmap.
    For White pawns, moves are upward (decreasing row index);
    for Black pawns, moves are downward (increasing row index).
    Also considers the two-square move (from the initial row) and diagonal captures.
    """
    moves = []
    for r in range(8):
        for c in range(8):
            if own_bitmap[r][c]:
                src = coord_to_algebraic(r, c)
                if role == "White":
                    # One-square forward.
                    tr = r - 1
                    if tr >= 0 and not (own_bitmap[tr][c] or opp_bitmap[tr][c]):
                        moves.append(src + coord_to_algebraic(tr, c))
                    # Two-square move from initial row (row 6 for White).
                    if r == 6:
                        tr = r - 2
                        if tr >= 0 and not (own_bitmap[r-1][c] or opp_bitmap[r-1][c]) and not (own_bitmap[tr][c] or opp_bitmap[tr][c]):
                            moves.append(src + coord_to_algebraic(tr, c))
                    # Diagonal captures.
                    for dc in [-1, 1]:
                        tc = c + dc
                        tr = r - 1
                        if tr >= 0 and 0 <= tc < 8 and opp_bitmap[tr][tc]:
                            moves.append(src + coord_to_algebraic(tr, tc))
                elif role == "Black":
                    # One-square forward.
                    tr = r + 1
                    if tr < 8 and not (own_bitmap[tr][c] or opp_bitmap[tr][c]):
                        moves.append(src + coord_to_algebraic(tr, c))
                    # Two-square move from initial row (row 1 for Black).
                    if r == 1:
                        tr = r + 2
                        if tr < 8 and not (own_bitmap[r+1][c] or opp_bitmap[r+1][c]) and not (own_bitmap[tr][c] or opp_bitmap[tr][c]):
                            moves.append(src + coord_to_algebraic(tr, c))
                    # Diagonal captures.
                    for dc in [-1, 1]:
                        tc = c + dc
                        tr = r + 1
                        if tr < 8 and 0 <= tc < 8 and opp_bitmap[tr][tc]:
                            moves.append(src + coord_to_algebraic(tr, tc))
    return moves

def evaluate_board(white_bitmap, black_bitmap, role):
    """
    Computes a simple evaluation score from the perspective of the given role.
    Counts the difference in pawn counts and gives a slight bonus based on pawn advancement.
    (For White, pawns advanced toward row 0 are "better"; for Black, those advanced toward row 7.)
    """
    white_count = sum(cell for row in white_bitmap for cell in row)
    black_count = sum(cell for row in black_bitmap for cell in row)
    
    white_adv = 0
    for r in range(8):
        for c in range(8):
            if white_bitmap[r][c]:
                white_adv += (7 - r)
    black_adv = 0
    for r in range(8):
        for c in range(8):
            if black_bitmap[r][c]:
                black_adv += r
                
    if role == "White":
        return (white_count - black_count) + (white_adv * 0.1)
    else:
        return (black_count - white_count) + (black_adv * 0.1)

class AIAgent:
    def __init__(self, role, white_bitmap, black_bitmap):
        self.role = role  # "White" or "Black"
        # The agent keeps its own internal board state.
        self.white_bitmap = white_bitmap
        self.black_bitmap = black_bitmap

    def make_move(self, time_left):
        """
        Chooses a move by first "thinking" (simulated with a sleep)
        then evaluating all legal moves with a one-ply lookahead.
        Returns the move in algebraic notation (e.g. "e2e4"). If no legal moves exist, returns "exit".
        Prints for each turn the search depth (always 1 here), the thinking time, and evaluation values.
        """
        # Record start time for thinking.
        start_time = time.time()
        # Simulate thinking.
        think_sleep = random.uniform(1.0, 3.0)
        time.sleep(think_sleep)
        thinking_duration = time.time() - start_time

        # For one-ply search.
        search_depth = 1
        print(f"[Agent Turn] Search Depth: {search_depth}")

        # Get all legal moves.
        if self.role == "White":
            legal_moves = generate_all_legal_moves("White", self.white_bitmap, self.black_bitmap)
        else:
            legal_moves = generate_all_legal_moves("Black", self.black_bitmap, self.white_bitmap)

        if not legal_moves:
            print("[Agent Turn] No legal moves available. Exiting.")
            return "exit"

        best_move = None
        best_value = -float('inf')

        # Evaluate each move with one-ply lookahead.
        for move in legal_moves:
            new_white, new_black = copy_boards(self.white_bitmap, self.black_bitmap)
            if self.role == "White":
                execute_move(move, new_white, new_black)
            else:
                execute_move(move, new_black, new_white)
            value = evaluate_board(new_white, new_black, self.role)
            print(f"[Agent Turn] Move: {move}  |  Eval: {value}")
            if value > best_value:
                best_value = value
                best_move = move

        if best_move is None:
            best_move = random.choice(legal_moves)

        # Update internal board state with the chosen move.
        if self.role == "White":
            execute_move(best_move, self.white_bitmap, self.black_bitmap)
        else:
            execute_move(best_move, self.black_bitmap, self.white_bitmap)

        print(f"[Agent Turn] Chosen move: {best_move} with Eval: {best_value} after thinking for {thinking_duration:.3f} seconds")
        return best_move

def main():
    # Default connection parameters.
    host = "127.0.0.1"
    port = 9999
    role = "White"
    
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            port = int(sys.argv[2])
        except ValueError:
            log("Invalid port; using default 9999.")
    if len(sys.argv) >= 4:
        role = sys.argv[3]
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        log("Connected to server.")
    except Exception as e:
        log(f"Could not connect to {host}:{port}: {e}")
        return
    
    s_file = sock.makefile('r')
    # --- Handshake Sequence ---
    # Step 1: Receive initial message.
    msg = s_file.readline().strip()
    log(f"Server says: {msg}")
    send_message(sock, "OK")
    
    # Step 2: Receive board setup message.
    msg = s_file.readline().strip()
    log(f"Server says: {msg}")
    if not msg.startswith("Setup"):
        log("Unexpected board setup message. Exiting.")
        sock.close()
        return
    white_bitmap, black_bitmap = initialize_boards(msg)
    log("Initial board setup received.")
    send_message(sock, "OK")
    
    # Step 3: Receive time message.
    msg = s_file.readline().strip()
    log(f"Server says: {msg}")
    send_message(sock, "OK")
    
    # Step 4: Receive Begin message.
    msg = s_file.readline().strip()
    log(f"Server says: {msg}")
    
    # Step 5: Receive role assignment.
    msg = s_file.readline().strip()
    if msg.startswith("Role"):
        assigned_role = msg.split()[1]
        log(f"Assigned role: {assigned_role}")
        role = assigned_role
    else:
        log("No role assignment from server; using default role.")
    
    # Initialize the AI agent.
    agent = AIAgent(role, white_bitmap, black_bitmap)
    
    # Main game loop.
    # For White, the agent moves when move_count is even; for Black, when odd.
    move_count = 0
    session_start = time.time()
    
    while True:
        if (role == "White" and move_count % 2 == 0) or (role == "Black" and move_count % 2 == 1):
            # It's the agent's turn.
            move = agent.make_move(600)  # Passing an arbitrary time leftover.
            log(f"Agent move: {move}")
            send_message(sock, move)
            if move.lower() == "exit":
                log("Exiting game.")
                break
        else:
            # Wait for the opponent's move.
            opp_move = s_file.readline().strip()
            if not opp_move or opp_move.lower() in ["exit", "gameover"]:
                log("Game over. Exiting.")
                break
            log(f"Opponent move: {opp_move}")
            # Update the internal board state with the opponent's move.
            if role == "White":
                execute_move(opp_move, black_bitmap, white_bitmap)
            else:
                execute_move(opp_move, white_bitmap, black_bitmap)
        move_count += 1
    
    elapsed = time.time() - session_start
    log(f"Session ended. Elapsed time: {int(elapsed)} secs")
    sock.close()

if __name__ == "__main__":
    main() 