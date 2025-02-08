import socket
import sys
import time
import random
import copy
from client import initialize_boards  # Import the board setup parser

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

def execute_move(move, own_bitmap, opp_bitmap, simulate=False):
    """
    Updates the board state given a move in algebraic notation (e.g. "e2e4").
    - Removes the pawn from its source in own_bitmap.
    - Captures an opponent pawn in opp_bitmap (if present).
    - Places the pawn at the destination in own_bitmap.
    The optional 'simulate' flag (False by default) disables debug printing during simulations.
    """
    from_coord = move[:2]
    to_coord = move[2:]
    r_from, c_from = convert_coord(from_coord)
    r_to, c_to = convert_coord(to_coord)
    # Remove the pawn from its source.
    own_bitmap[r_from][c_from] = False
    # Capture opponent pawn if present.
    if opp_bitmap[r_to][c_to]:
        if not simulate:
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

def check_win_conditions(white_bitmap, black_bitmap):
    """
    Check if a winning condition has been reached.
    White wins if any pawn reaches row 0.
    Black wins if any pawn reaches row 7.
    Returns "White wins", "Black wins", or None.
    """
    for col in range(8):
        if white_bitmap[0][col]:
            return "White wins"
        if black_bitmap[7][col]:
            return "Black wins"
    return None

def simulate_move(move, white_bitmap, black_bitmap, role):
    """
    Simulate a move on a copy of the given board state.
    
    For a White move, update the white board (own_bitmap) and then the black board.
    For a Black move, note that in our board state the agent's own pieces are stored in black_bitmap
    (and the opponent's in white_bitmap). Therefore, we swap the boards when calling execute_move.
    """
    new_white, new_black = copy_boards(white_bitmap, black_bitmap)
    if role == "White":
        execute_move(move, new_white, new_black)
    else:
        # For Black, apply the move with boards swapped.
        execute_move(move, new_black, new_white)
    return new_white, new_black

# --- NEW HELPER: Passed Pawn Check ---
def is_passed_pawn(own_bitmap, opp_bitmap, row, col, side):
    """
    For a pawn at (row, col) of the given side, check if there is any opposing pawn
    in front (in adjacent files including the same file).
    For Black, 'in front' means in rows row+1 to 7.
    For White, it is rows 0 to row-1.
    """
    if side == "Black":
        for r in range(row+1, 8):
            for c in [col-1, col, col+1]:
                if 0 <= c < 8 and opp_bitmap[r][c]:
                    return False
        return True
    else:  # For White
        for r in range(0, row):
            for c in [col-1, col, col+1]:
                if 0 <= c < 8 and opp_bitmap[r][c]:
                    return False
        return True

# --- NEW EVALUATION FUNCTION ---
def evaluate_board_dynamic(white_bitmap, black_bitmap, role):
    """
    Evaluate the board (using our two-bitmaps) with improved heuristics.
    Evaluation is computed from Black's perspective.
    If role is White, the score is inverted.
    """
    WIN_SCORE = 1000000
    winner = check_win_conditions(white_bitmap, black_bitmap)
    if winner == "Black wins":
        score = WIN_SCORE
    elif winner == "White wins":
        score = -WIN_SCORE
    else:
        # Material balance: count pawns (True values indicate a pawn)
        white_count = sum(cell for row in white_bitmap for cell in row)
        black_count = sum(cell for row in black_bitmap for cell in row)
        score = 10 * (black_count - white_count)
        # Pawn advancement and promotion potential:
        for row in range(8):
            for col in range(8):
                if black_bitmap[row][col]:
                    # Add a huge bonus if the pawn is one move away from promotion (promotion row is 7 for Black).
                    if row == 6:
                        score += 10000
                    # The farther down (higher row index), the closer to promotion:
                    advancement = row  # (row 7 is best for Black)
                    score += 30 * advancement
                    if is_passed_pawn(black_bitmap, white_bitmap, row, col, "Black"):
                        score += 150 + (30 * advancement)
                elif white_bitmap[row][col]:
                    # For White, promotion row is 0.
                    advancement = 7 - row
                    score -= 20 * advancement
                    if is_passed_pawn(white_bitmap, black_bitmap, row, col, "White"):
                        score -= 100 + (20 * advancement)
    # Return score from the agent's perspective.
    return score if role == "Black" else -score

# --- MINIMAX WITH ITERATIVE DEEPENING SUPPORT ---
def minimax(white, black, depth, maximizing, role, start_time, time_limit, alpha=-float('inf'), beta=float('inf')):
    # Check for time-out.
    if time.time() - start_time > time_limit:
        raise TimeoutError("Time limit exceeded in minimax search.")
    winner = check_win_conditions(white, black)
    if depth == 0 or winner is not None:
        return evaluate_board_dynamic(white, black, role)
    
    if maximizing:
        max_eval = -float('inf')
        if role == "White":
            moves = generate_all_legal_moves("White", white, black)
        else:
            moves = generate_all_legal_moves("Black", black, white)
        for move in moves:
            new_white, new_black = copy_boards(white, black)
            if role == "White":
                execute_move(move, new_white, new_black, simulate=True)
            else:
                execute_move(move, new_black, new_white, simulate=True)
            eval_val = minimax(new_white, new_black, depth - 1, False, role, start_time, time_limit, alpha, beta)
            max_eval = max(max_eval, eval_val)
            alpha = max(alpha, eval_val)
            if beta <= alpha:
                break  # Beta cutoff.
        return max_eval
    else:
        min_eval = float('inf')
        if role == "White":
            moves = generate_all_legal_moves("Black", black, white)
        else:
            moves = generate_all_legal_moves("White", white, black)
        for move in moves:
            new_white, new_black = copy_boards(white, black)
            if role == "White":
                execute_move(move, new_black, new_white, simulate=True)
            else:
                execute_move(move, new_white, new_black, simulate=True)
            eval_val = minimax(new_white, new_black, depth - 1, True, role, start_time, time_limit, alpha, beta)
            min_eval = min(min_eval, eval_val)
            beta = min(beta, eval_val)
            if beta <= alpha:
                break  # Alpha cutoff.
        return min_eval

class AIAgent:
    def __init__(self, role, white_bitmap, black_bitmap):
        self.role = role  # "White" or "Black"
        self.white_bitmap = white_bitmap
        self.black_bitmap = black_bitmap

    def make_move(self, time_limit):
        """
        Uses iterative deepening and minimax search with dynamic search depth.
        Returns the best move found before time runs out.
        """
        import random  # ensure random is imported if not already
        start_time = time.time()
        
        # Retrieve legal moves.
        if self.role == "White":
            legal_moves = generate_all_legal_moves("White", self.white_bitmap, self.black_bitmap)
        else:
            legal_moves = generate_all_legal_moves("Black", self.black_bitmap, self.white_bitmap)
        
        if not legal_moves:
            print("[Agent Turn] No legal moves available!")
            return None

        best_move = None
        best_eval = -float('inf')
        depth = 1
        max_depth_allowed = 5  # Set a hard cap for iterative deepening

        while True:
            try:
                elapsed = time.time() - start_time
                remaining_time = time_limit - elapsed
                # Break if time is nearly up or maximum depth reached.
                if remaining_time < 0.05 or depth > max_depth_allowed:
                    print(f"[Agent Turn] Breaking out of iterative deepening: remaining time {remaining_time:.2f}s, depth {depth}")
                    break

                print(f"[Agent Turn] Iterative deepening: starting search at depth {depth}, remaining time: {remaining_time:.2f}s")
                
                current_best = None
                current_best_eval = -float('inf')
                
                # Evaluate each move at the current search depth.
                for move in legal_moves:
                    new_white, new_black = copy_boards(self.white_bitmap, self.black_bitmap)
                    if self.role == "White":
                        execute_move(move, new_white, new_black, simulate=True)
                    else:
                        execute_move(move, new_black, new_white, simulate=True)
                    
                    move_eval = minimax(new_white, new_black, depth - 1, False, self.role, start_time, time_limit)
                    if move_eval > current_best_eval:
                        current_best_eval = move_eval
                        current_best = move
                
                best_move = current_best
                best_eval = current_best_eval
                print(f"[Agent Turn] Depth {depth} search completed. Best eval: {best_eval}")
                depth += 1
            
            except TimeoutError:
                print("[Agent Turn] Search timed out during iterative deepening.")
                break

        # If no move was found (unlikely), select one at random.
        if best_move is None:
            best_move = random.choice(legal_moves)
        
        # For the actual move, use simulate=False so that logging (if any) occurs.
        if self.role == "White":
            execute_move(best_move, self.white_bitmap, self.black_bitmap, simulate=False)
        else:
            execute_move(best_move, self.black_bitmap, self.white_bitmap, simulate=False)

        print(f"[Agent Turn] Chosen move: {best_move} (eval: {best_eval}, depth reached: {depth-1})")
        return best_move

def main():
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
    # --- Updated Handshake Sequence ---
    msg = s_file.readline().strip()        # Expect greeting (e.g. "Connected to the server!")
    log(f"Server says: {msg}")
    send_message(sock, "OK")
    
    msg = s_file.readline().strip()        # Expect board setup message (starting with "Setup")
    log(f"Server says: {msg}")
    if msg.startswith("Setup"):
        white_bitmap, black_bitmap = initialize_boards(msg)
        log("Board setup received and parsed.")
    else:
        log("Unexpected board setup message. Exiting.")
        return
    
    send_message(sock, "OK")
    
    msg = s_file.readline().strip()        # Time message
    log(f"Server says: {msg}")
    send_message(sock, "OK")
    
    msg = s_file.readline().strip()        # BEGIN message
    log(f"Server says: {msg}")
    
    msg = s_file.readline().strip()        # Role assignment message
    if msg.startswith("Role"):
        assigned_role = msg.split()[1]
        log(f"Assigned role: {assigned_role}")
        role = assigned_role
    else:
        log("No role assignment from server; using default role.")
    
    agent = AIAgent(role, white_bitmap, black_bitmap)
    
    move_count = 0
    session_start = time.time()
    
    while True:
        if (role == "White" and move_count % 2 == 0) or (role == "Black" and move_count % 2 == 1):
            move = agent.make_move(600)
            log(f"Agent move: {move}")
            send_message(sock, move)
            if move.lower() == "exit":
                log("Exiting game.")
                break
        else:
            opp_move = s_file.readline().strip()
            if not opp_move or opp_move.lower() in ["exit", "gameover"]:
                log("Game over. Exiting.")
                break
            log(f"Opponent move: {opp_move}")
            if role == "White":
                execute_move(opp_move, black_bitmap, white_bitmap)
            else:
                execute_move(opp_move, white_bitmap, black_bitmap)
        
        # --- NEW WIN CHECK: After every move, check if a terminal win has been reached.
        winner = check_win_conditions(white_bitmap, black_bitmap)
        if winner:
            log(f"Game over: {winner}")
            send_message(sock, f"win: {winner}")
            break
        
        move_count += 1
    
    elapsed = time.time() - session_start
    log(f"Session ended. Elapsed time: {int(elapsed)} secs")
    sock.close()

if __name__ == "__main__":
    main() 