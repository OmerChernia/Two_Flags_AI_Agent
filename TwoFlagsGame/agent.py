import socket
import sys
import time
import random
import copy
import math
from client import initialize_boards  # Import the board setup parser

def log(msg):
    print(msg)

def send_message(sock, msg):
    """Sends a message (appending a newline) over the socket."""
    full_msg = msg + "\n"
    try:
        sock.sendall(full_msg.encode())
    except BrokenPipeError:
        log("Warning: Broken pipe encountered when sending message. "
            "The server may have closed the connection. Consider reconnecting or cleaning up resources.")

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

# --- GLOBAL WEIGHTS & TD UPDATE ---
# These global weights are used by our evaluation function and can be updated via TD learning.
weights = {
    "win_score": 1000000,
    "material": 10,
    "promotion_bonus": 10000,
    "advancement": 30,
    "passed_pawn": 150,
    "white_advancement": 20,
    "white_passed_pawn": 100
}

def evaluate_board_dynamic(white_bitmap, black_bitmap, role):
    """
    Evaluate the board (using our two-bitmaps) with improved heuristics and dynamic weights.
    Evaluation is computed from Black's perspective.
    If role is White, the score is inverted.
    """
    global weights
    WIN_SCORE = weights["win_score"]
    winner = check_win_conditions(white_bitmap, black_bitmap)
    if winner == "Black wins":
        score = WIN_SCORE
    elif winner == "White wins":
        score = -WIN_SCORE
    else:
        # Material balance: count pawns (True values indicate a pawn)
        white_count = sum(cell for row in white_bitmap for cell in row)
        black_count = sum(cell for row in black_bitmap for cell in row)
        score = weights["material"] * (black_count - white_count)
        # Pawn advancement and promotion potential:
        for row in range(8):
            for col in range(8):
                if black_bitmap[row][col]:
                    # Add a huge bonus if the pawn is one move away from promotion (promotion row is 6 for Black).
                    if row == 6:
                        score += weights["promotion_bonus"]
                    advancement = row  # Higher row is closer to promotion (row 7)
                    score += weights["advancement"] * advancement
                    if is_passed_pawn(black_bitmap, white_bitmap, row, col, "Black"):
                        score += weights["passed_pawn"] + (weights["advancement"] * advancement)
                elif white_bitmap[row][col]:
                    advancement = 7 - row
                    score -= weights["white_advancement"] * advancement
                    if is_passed_pawn(white_bitmap, black_bitmap, row, col, "White"):
                        score -= weights["white_passed_pawn"] + (weights["white_advancement"] * advancement)
    return score if role == "Black" else -score

def td_update(state, next_state, reward, alpha=0.01, gamma=0.99):
    """
    A simple Temporal Difference (TD) update function.
    'state' and 'next_state' are tuples: (white_bitmap, black_bitmap, role)
    This updates the global 'weights' based on the TD error.
    (This is a very simplified example—more elaborate feature extraction and gradient computation can be used.)
    """
    global weights
    white, black, role = state
    # Example feature: material difference.
    white_count = sum(cell for row in white for cell in row)
    black_count = sum(cell for row in black for cell in row)
    material_diff = black_count - white_count

    # Example features for pawn advancement.
    black_advancement = sum(row for row in range(8) for col in range(8) if black[row][col])
    white_advancement = sum((7 - row) for row in range(8) for col in range(8) if white[row][col])
    
    # Construct a simple feature vector.
    f_state = {
        "material": material_diff,
        "advancement": black_advancement,
        "white_advancement": white_advancement,
    }
    
    V_state = evaluate_board_dynamic(white, black, role)
    new_white, new_black, role_next = next_state
    V_next = evaluate_board_dynamic(new_white, new_black, role_next)
    
    delta = reward + gamma * V_next - V_state
    # Update each weight proportionally to its feature value.
    for key in f_state:
        if key in weights:
            weights[key] += alpha * delta * f_state[key]

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

# --- MCTS IMPLEMENTATION ---

class MCTSNode:
    def __init__(self, white, black, move=None, parent=None, role=None):
        self.white = white
        self.black = black
        self.move = move         # The move that led to this state (from the parent)
        self.parent = parent
        self.children = []
        self.visits = 0
        self.total_reward = 0.0
        self.role = role         # Role perspective ("White" or "Black")

    def is_terminal(self):
        return check_win_conditions(self.white, self.black) is not None

    def expand(self):
        if self.children:
            return self.children
        if self.role == "White":
            moves = generate_all_legal_moves("White", self.white, self.black)
        else:
            moves = generate_all_legal_moves("Black", self.black, self.white)
        for move in moves:
            new_white, new_black = copy_boards(self.white, self.black)
            if self.role == "White":
                execute_move(move, new_white, new_black, simulate=True)
            else:
                execute_move(move, new_black, new_white, simulate=True)
            child = MCTSNode(new_white, new_black, move=move, parent=self, role=self.role)
            self.children.append(child)
        return self.children

def mcts_select(node):
    best_child = None
    best_value = -float('inf')
    for child in node.children:
        # Use UCB1 for balancing exploration and exploitation.
        exploitation = child.total_reward / (child.visits + 1e-5)
        exploration = 1.41 * math.sqrt(math.log(node.visits + 1) / (child.visits + 1e-5))
        ucb = exploitation + exploration
        if ucb > best_value:
            best_value = ucb
            best_child = child
    return best_child

def mcts_rollout(node, rollout_depth=10):
    current_white, current_black = copy_boards(node.white, node.black)
    current_role = node.role
    for _ in range(rollout_depth):
        winner = check_win_conditions(current_white, current_black)
        if winner:
            # Return reward +1 for win from node's perspective, -1 for loss.
            return 1 if winner == f"{node.role} wins" else -1
        # Generate a random move.
        if current_role == "White":
            moves = generate_all_legal_moves("White", current_white, current_black)
        else:
            moves = generate_all_legal_moves("Black", current_black, current_white)
        if not moves:
            break
        move = random.choice(moves)
        if current_role == "White":
            execute_move(move, current_white, current_black, simulate=True)
        else:
            execute_move(move, current_black, current_white, simulate=True)
        # Switch perspective for the next move.
        current_role = "Black" if current_role == "White" else "White"
    return 0  # If no terminal state was reached.

def mcts_backpropagate(node, reward):
    while node is not None:
        node.visits += 1
        node.total_reward += reward
        node = node.parent

def mcts_search(white, black, role, time_limit):
    """
    Run MCTS for a given time limit (in seconds) and return the best move.
    """
    start_time = time.time()
    root = MCTSNode(white, black, role=role)
    root.expand()
    iterations = 0
    while time.time() - start_time < time_limit:
        node = root
        # Selection: traverse the tree.
        while node.children:
            node = mcts_select(node)
        # Expansion.
        if not node.is_terminal():
            node.expand()
            if node.children:
                node = random.choice(node.children)
        # Simulation (rollout).
        reward = mcts_rollout(node)
        # Backpropagation.
        mcts_backpropagate(node, reward)
        iterations += 1
    # Select the move that has the highest visit count.
    best_child = max(root.children, key=lambda c: c.visits) if root.children else None
    return best_child.move if best_child else None

class AIAgent:
    def __init__(self, role, white_bitmap, black_bitmap):
        self.role = role  # "White" or "Black"
        self.white_bitmap = white_bitmap
        self.black_bitmap = black_bitmap
        # TD learning parameters: initial weights for features, learning rate, and discount factor.
        self.weights = {'material': 1.0, 'mobility': 0.5}
        self.alpha = 0.01  # learning rate
        self.gamma = 0.9   # discount factor

    def extract_features(self, white, black):
        """
        Extract features from the board state.
        For example, we define:
         - 'material': difference in piece counts (number of pawns for White minus Black)
         - 'mobility': number of legal moves available (as a dummy mobility measure)
        """
        # Count pawns: assuming each pawn is represented as True in the bitmap.
        white_count = sum(1 for row in white for cell in row if cell)
        black_count = sum(1 for row in black for cell in row if cell)
        # Dummy mobility: count legal moves for the current player.
        if self.role == "White":
            mobility = len(generate_all_legal_moves("White", white, black))
        else:
            mobility = len(generate_all_legal_moves("Black", black, white))
        return {'material': white_count - black_count, 'mobility': mobility}

    def evaluate_state(self, white, black):
        """
        Compute an evaluation value for the board as a weighted sum over features.
        """
        features = self.extract_features(white, black)
        value = sum(self.weights.get(feature, 0) * val for feature, val in features.items())
        return value

    def td_update(self, old_white, old_black, new_white, new_black, reward):
        """
        Update the evaluation weights using the TD learning rule.
        
        δ = r + γ * V(new_state) - V(old_state)
        For each feature f:
            w_f ← w_f + α * δ * f(old_state)
        """
        old_value = self.evaluate_state(old_white, old_black)
        new_value = self.evaluate_state(new_white, new_black)
        delta = reward + self.gamma * new_value - old_value
        features = self.extract_features(old_white, old_black)
        for feature, f_val in features.items():
            self.weights[feature] += self.alpha * delta * f_val
        print("TD update applied. New weights:", self.weights)

    def make_move(self, time_limit):
        """
        Uses iterative deepening and minimax search with dynamic search depth.
        Returns the best move found before time runs out.
        Incorporates a TD update after executing the move.
        """
        start_time = time.time()
        # Capture board state before making the move for TD update later.
        old_white, old_black = copy_boards(self.white_bitmap, self.black_bitmap)
        
        # Retrieve legal moves.
        if self.role == "White":
            legal_moves = generate_all_legal_moves("White", self.white_bitmap, self.black_bitmap)
        else:
            legal_moves = generate_all_legal_moves("Black", self.black_bitmap, self.white_bitmap)
        
        if not legal_moves:
            log("[Agent Turn] No legal moves available!")
            return "exit"

        best_move = None
        best_eval = -float('inf')
        depth = 1
        max_depth_allowed = 5  # Hard cap for iterative deepening
        
        while True:
            elapsed = time.time() - start_time
            remaining_time = time_limit - elapsed
            if remaining_time < 0.05 or depth > max_depth_allowed:
                log(f"[Agent Turn] Breaking out of iterative deepening: remaining time {remaining_time:.2f}s, depth {depth}")
                break

            log(f"[Agent Turn] Iterative deepening: starting search at depth {depth}, remaining time: {remaining_time:.2f}s")
            
            current_best = None
            current_best_eval = -float('inf')
            move_evals = []
            
            # Shuffle legal moves to add randomness.
            random.shuffle(legal_moves)
            
            for move in legal_moves:
                new_white_sim, new_black_sim = copy_boards(self.white_bitmap, self.black_bitmap)
                if self.role == "White":
                    execute_move(move, new_white_sim, new_black_sim, simulate=True)
                else:
                    execute_move(move, new_black_sim, new_white_sim, simulate=True)
                
                move_eval = minimax(new_white_sim, new_black_sim, depth - 1, False, self.role, start_time, time_limit)
                # Add small random noise for tie-breaking.
                move_eval += random.uniform(-0.01, 0.01)
                move_evals.append((move, move_eval))
                
                if move_eval > current_best_eval:
                    current_best_eval = move_eval
                    current_best = move

            # If multiple moves have almost identical evaluations, pick one at random.
            epsilon = 1e-5
            nearly_best = [m for m, ev in move_evals if abs(ev - current_best_eval) < epsilon]
            if nearly_best:
                current_best = random.choice(nearly_best)
            
            best_move = current_best
            best_eval = current_best_eval
            log(f"[Agent Turn] Depth {depth} search completed. Best eval: {best_eval}")
            depth += 1
        
        # Fallback: if no move is found, return 'exit'.
        if best_move is None:
            best_move = "exit"

        # If the chosen move is "exit", do not execute it.
        if best_move.lower() == "exit":
            log("[Agent Turn] No legal move available; returning 'exit' without executing move.")
            return best_move
        
        # Execute the chosen move on the actual board.
        if self.role == "White":
            execute_move(best_move, self.white_bitmap, self.black_bitmap, simulate=False)
        else:
            execute_move(best_move, self.black_bitmap, self.white_bitmap, simulate=False)
        log(f"[Agent Turn] Chosen move: {best_move} (eval: {best_eval}, depth reached: {depth-1})")
        
        # Capture post-move board state and perform a TD update with immediate reward = 0.
        new_white, new_black = copy_boards(self.white_bitmap, self.black_bitmap)
        self.td_update(old_white, old_black, new_white, new_black, reward=0)
        
        return best_move

    def make_move_mcts(self, time_limit):
        """
        Uses Monte Carlo Tree Search (MCTS) to select a move within the given time limit.
        """
        # In this simplified example, the current board state is used as the root.
        if self.role == "White":
            current_white = self.white_bitmap
            current_black = self.black_bitmap
        else:
            current_white = self.white_bitmap
            current_black = self.black_bitmap
        move = mcts_search(current_white, current_black, self.role, time_limit)
        if move is None:
            # Fallback to a random move if MCTS fails.
            if self.role == "White":
                legal_moves = generate_all_legal_moves("White", self.white_bitmap, self.black_bitmap)
            else:
                legal_moves = generate_all_legal_moves("Black", self.black_bitmap, self.white_bitmap)
            move = random.choice(legal_moves) if legal_moves else "exit"
        # Execute the chosen move on the actual (non-simulated) board.
        if self.role == "White":
            execute_move(move, self.white_bitmap, self.black_bitmap, simulate=False)
        else:
            execute_move(move, self.black_bitmap, self.white_bitmap, simulate=False)
        log(f"[Agent Turn] MCTS selected move: {move}")
        return move

    def reset_game(self, setup_msg):
        """
        Reset the agent's board state from a new setup message.
        """
        self.white_bitmap, self.black_bitmap = initialize_boards(setup_msg)
        log("Agent game state reset for a new game.")

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
            # Instead of breaking immediately, wait for a NEW GAME command.
            new_game_cmd = s_file.readline().strip()
            if new_game_cmd == "NEW GAME":
                setup_msg = s_file.readline().strip()  # New board setup
                
                # Reset the internal board state of the agent.
                agent.reset_game(setup_msg)
                # Update the local board variables in case they are used later.
                white_bitmap, black_bitmap = agent.white_bitmap, agent.black_bitmap
                # Optionally, reset move counter (or any other per-game state).
                move_count = 0
                log("New game started.")
                continue
            else:
                break
        
        move_count += 1
    
    elapsed = time.time() - session_start
    log(f"Session ended. Elapsed time: {int(elapsed)} secs")
    sock.close()

if __name__ == "__main__":
    main() 