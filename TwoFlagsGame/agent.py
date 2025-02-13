import socket
import sys
import time
import random
import copy
import math

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
        execute_move(move, new_black, new_white)
    return new_white, new_black

# -----------------------------------------
# 1) GLOBAL WEIGHTS: Increase promotion etc.
# -----------------------------------------
weights = {
    "win_score": 10000,        # Winning the game
    "material": 20,            # Material is still important
    "promotion_bonus": 3500,   # Big bonus for near-promoting pawns (row=6 for Black, row=1 for White)
    "advancement": 250,         # Gains for pushing pawns forward
    "passed_pawn": 500,        # Large bonus for having a passed pawn
    "white_advancement": 30,   # Penalty for White advanced pawns (from Black's perspective)
    "white_passed_pawn": 150   # Large penalty for letting White have a passed pawn
}

# -----------------------------------------
# 2) HELPER: Check if Pawn is Passed
#    (No opposing pawns directly ahead)
# -----------------------------------------
def is_passed_pawn(own_bitmap, opp_bitmap, row, col, side):
    """
    Returns True if a pawn at (row, col) has no opposing pawns blocking
    or diagonally ahead on the relevant ranks.
    """
    if side == "Black":
        for r in range(row+1, 8):
            # Check same file, plus diagonals
            for cc in [col-1, col, col+1]:
                if 0 <= cc < 8 and opp_bitmap[r][cc]:
                    return False
        return True
    else:  # side == "White"
        for r in range(row-1, -1, -1):
            # Check same file, plus diagonals
            for cc in [col-1, col, col+1]:
                if 0 <= cc < 8 and opp_bitmap[r][cc]:
                    return False
        return True

# --- GLOBAL WEIGHTS ---
# These global weights are used by our evaluation function
weights = {
    "win_score": 10000,
    "material": 10,
    "promotion_bonus": 1000,
    "advancement": 30,
    "passed_pawn": 250,
    "white_advancement": 30,
    "white_passed_pawn": 150
}

def initialize_boards(setup_msg):
    """
    Parse the setup message (e.g.
    "Setup Wa2 Wb2 Wc2 Wd2 We2 Wf2 Wg2 Wh2 Ba7 Bb7 Bc7 Bd7 Be7 Bf7 Bg7 Bh7")
    and create bitmaps for white and black pawns.
    Each bitmap is an 8x8 matrix with boolean values: True indicates a pawn.
    """
    white_bitmap = [[False for _ in range(8)] for _ in range(8)]
    black_bitmap = [[False for _ in range(8)] for _ in range(8)]
    tokens = setup_msg.split()
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
                execute_move(move, new_white, new_black, simulate=True)
            else:
                execute_move(move, new_black, new_white, simulate=True)
            eval_val = minimax(new_white, new_black, depth - 1, True, role, start_time, time_limit, alpha, beta)
            min_eval = min(min_eval, eval_val)
            beta = min(beta, eval_val)
            if beta <= alpha:
                break  # Alpha cutoff.
        return min_eval

def display_board(bitmap, label):
    print(f"--- {label} Pawn Board ---")
    print("  a b c d e f g h")
    for i in range(8):
        row_str = ""
        for j in range(8):
            row_str += "1 " if bitmap[i][j] else ". "
        print(f"{8 - i} {row_str}")
    print("")

def display_boards(white_bitmap, black_bitmap):
    display_board(white_bitmap, "White")
    display_board(black_bitmap, "Black")

class AIAgent:
    def __init__(self, role, white_bitmap, black_bitmap):
        self.role = role  # "White" or "Black"
        self.white_bitmap = white_bitmap
        self.black_bitmap = black_bitmap
        self.transposition_table = {}
        self.time_limit = 10  # default; used for move search
        self.start_time = None
        self.learning_enabled = False
        self.learning_data = []
        # Attributes used for pondering.
        self.ponder_best_move = None
        self.ponder_best_score = None
        self.ponder_depth = 0

    def start_pondering(self):
        """Begins background pondering during the opponent's turn."""
        import threading
        self.ponder_stop = threading.Event()
        self.ponder_thread = threading.Thread(target=self.ponder_loop)
        self.ponder_thread.daemon = True  # Allows the thread to exit when main program exits.
        self.ponder_thread.start()

    def stop_pondering(self):
        """Stops the background pondering thread."""
        if hasattr(self, "ponder_stop"):
            self.ponder_stop.set()
            self.ponder_thread.join()

    def ponder_loop(self):
        """
        Continuously expands the search tree,
        using iterative deepening in the background.
        """
        current_depth = 1
        while not self.ponder_stop.is_set():
            try:
                candidate_move, candidate_score = self._iterative_search_ponder(current_depth)
                self.ponder_best_move = candidate_move
                self.ponder_best_score = candidate_score
                self.ponder_depth = current_depth
                # Optionally, log the pondered results:
                # log(f"[Ponder] Depth {current_depth}, Best move: {candidate_move}, Score: {candidate_score}")
            except Exception as e:
                # In case of interruption or error, break out.
                break
            current_depth += 1

    def _iterative_search_ponder(self, depth):
        """
        A variant of iterative search used during pondering.
        It does not enforce a strict time limit,
        but checks the `ponder_stop` flag to exit early.
        """
        moves = self._generate_legal_moves_for_role()
        if not moves:
            return "exit", self._evaluate_terminal()
        if self.role == "White":
            best_score = float('-inf')
        else:
            best_score = float('inf')
        best_move = None
        alpha = float('-inf')
        beta = float('inf')
        for move in moves:
            if self.ponder_stop.is_set():
                break
            # Work on a deep copy of the current board.
            w_copy = copy.deepcopy(self.white_bitmap)
            b_copy = copy.deepcopy(self.black_bitmap)
            if self.role == "White":
                execute_move(move, w_copy, b_copy, simulate=True)
                score = self._alpha_beta(w_copy, b_copy, depth - 1, alpha, beta, "Black")
                if score > best_score:
                    best_score = score
                    best_move = move
                alpha = max(alpha, best_score)
                if beta <= alpha:
                    break  # Beta cutoff.
            else:
                execute_move(move, b_copy, w_copy, simulate=True)
                score = self._alpha_beta(w_copy, b_copy, depth - 1, alpha, beta, "White")
                if score < best_score:
                    best_score = score
                    best_move = move
                beta = min(beta, best_score)
                if beta <= alpha:
                    break  # Alpha cutoff.
        return best_move, best_score

    def make_move(self, time_limit=10, move_count=0):
        """
        Produces a move within a given time limit, using alpha-beta search.
        The search depth is adjusted based on how many moves have already been played.
        """
        self.time_limit = time_limit
        self.start_time = time.time()

        # DYNAMIC DEPTH SCHEDULING:
        # For the first 10 moves of the entire game, search up to depth 4;
        if move_count < 10:
            max_depth = 5
        else:
            max_depth = 11

        moves = self._generate_legal_moves_for_role()
        if not moves:
            # Declare the other side as the winner if we can't move.
            opponent = "White" if self.role == "Black" else "Black"
            print(f"No legal moves for {self.role}. {opponent} wins!")
            return f"win: {opponent}"

        # If there's an immediate winning promotion, take it.
        winning_move = self._find_immediate_promotion(moves)
        if winning_move:
            if self.role == "White":
                execute_move(winning_move, self.white_bitmap, self.black_bitmap, simulate=False)
            else:
                execute_move(winning_move, self.black_bitmap, self.white_bitmap, simulate=False)
            
            self._print_turn_summary(
                depth_reached=0,
                move_chosen=winning_move,
                start_time=self.start_time,
                time_limit=self.time_limit
            )
            return winning_move

        best_move = moves[0]
        best_score = float('-inf') if self.role == "White" else float('inf')
        depth_reached = 1

        # Perform a simple iterative deepening from depth=1 up to max_depth
        for depth in range(1, max_depth + 1):
            candidate_move, candidate_score = self._iterative_search(depth)
            if candidate_move is not None:
                best_move, best_score = candidate_move, candidate_score
                depth_reached = depth
            # Check time limit after each iteration
            if time.time() - self.start_time > self.time_limit:
                break

        # Execute the best move found
        if best_move.lower() != "exit":
            if self.role == "White":
                execute_move(best_move, self.white_bitmap, self.black_bitmap, simulate=False)
            else:
                execute_move(best_move, self.black_bitmap, self.white_bitmap, simulate=False)

        # Print a final summary for this turn
        self._print_turn_summary(
            depth_reached=depth_reached,
            move_chosen=best_move,
            start_time=self.start_time,
            time_limit=self.time_limit
        )
        return best_move

    def _iterative_search(self, depth):
        moves = self._generate_legal_moves_for_role()
        if not moves:
            return "exit", self._evaluate_terminal()

        best_move = None
        best_score = float('-inf') if self.role == "White" else float('inf')
        alpha = float('-inf')
        beta = float('inf')

        for move in moves:
            if time.time() - self.start_time > self.time_limit:
                break

            w_copy = copy.deepcopy(self.white_bitmap)
            b_copy = copy.deepcopy(self.black_bitmap)

            if self.role == "White":
                execute_move(move, w_copy, b_copy, simulate=True)
                score = self._alpha_beta(w_copy, b_copy, depth - 1, alpha, beta, "Black")
                if score > best_score:
                    best_score = score
                    best_move = move
                alpha = max(alpha, best_score)
                if beta <= alpha:
                    break
            else:
                execute_move(move, b_copy, w_copy, simulate=True)
                score = self._alpha_beta(w_copy, b_copy, depth - 1, alpha, beta, "White")
                if score < best_score:
                    best_score = score
                    best_move = move
                beta = min(beta, best_score)
                if beta <= alpha:
                    break

        return best_move, best_score

    def _alpha_beta(self, white_bitmap, black_bitmap, depth, alpha, beta, role):
        if time.time() - self.start_time > self.time_limit:
            return self._evaluate_position(white_bitmap, black_bitmap)

        # Terminal check
        winner = check_win_conditions(white_bitmap, black_bitmap)
        if winner or depth == 0:
            return self._evaluate_position(white_bitmap, black_bitmap)

        # Transposition table usage
        state_key = self._hash_position(white_bitmap, black_bitmap, role)
        if state_key in self.transposition_table:
            stored_depth, stored_score, stored_move = self.transposition_table[state_key]
            if stored_depth >= depth:
                return stored_score

        moves = generate_all_legal_moves(role, white_bitmap, black_bitmap)
        if not moves:
            return -9999 if role == "White" else 9999

        if role == "White":
            best_score = float('-inf')
            for move in moves:
                if time.time() - self.start_time > self.time_limit:
                    break
                w_copy = copy.deepcopy(white_bitmap)
                b_copy = copy.deepcopy(black_bitmap)
                execute_move(move, w_copy, b_copy, simulate=True)
                score = self._alpha_beta(w_copy, b_copy, depth - 1, alpha, beta, "Black")
                best_score = max(best_score, score)
                alpha = max(alpha, best_score)
                if beta <= alpha:
                    break
        else:
            best_score = float('inf')
            for move in moves:
                if time.time() - self.start_time > self.time_limit:
                    break
                w_copy = copy.deepcopy(white_bitmap)
                b_copy = copy.deepcopy(black_bitmap)
                execute_move(move, b_copy, w_copy, simulate=True)
                score = self._alpha_beta(w_copy, b_copy, depth - 1, alpha, beta, "White")
                best_score = min(best_score, score)
                beta = min(beta, best_score)
                if beta <= alpha:
                    break

        self.transposition_table[state_key] = (depth, best_score, None)
        return best_score

    def _evaluate_position(self, white_bitmap, black_bitmap):
        """
        Basic evaluation: +10 for each White pawn, -10 for each Black pawn,
        plus a small row-based bonus to encourage forward movement.
        """
        white_score = 0
        black_score = 0
        for row in range(8):
            for col in range(8):
                if white_bitmap[row][col]:
                    white_score += 10 + (7 - row)  # small bonus for being further down
                if black_bitmap[row][col]:
                    black_score += 10 + row       # small bonus for being further up
        return white_score - black_score

    def _evaluate_terminal(self):
        if self.role == "White":
            return -9999
        else:
            return 9999

    def _generate_legal_moves_for_role(self):
        if self.role == "White":
            return generate_all_legal_moves("White", self.white_bitmap, self.black_bitmap)
        else:
            return generate_all_legal_moves("Black", self.black_bitmap, self.white_bitmap)

    def _find_immediate_promotion(self, moves):
        for move in moves:
            dst = move[2:]
            dst_row, _ = convert_coord(dst)
            if self.role == "White" and dst_row == 0:
                return move
            if self.role == "Black" and dst_row == 7:
                return move
        return None

    def _hash_position(self, white_bitmap, black_bitmap, role):
        bits = [role]
        for row in range(8):
            for col in range(8):
                w = '1' if white_bitmap[row][col] else '0'
                b = '1' if black_bitmap[row][col] else '0'
                bits.append(w + b)
        return ''.join(bits)

    # SINGLE SUMMARY PRINT
    def _print_turn_summary(self, depth_reached, move_chosen, start_time, time_limit):
        elapsed = time.time() - start_time
        time_left = time_limit - elapsed
        # Compute the board evaluation score using our dynamic evaluation function.
        score = evaluate_board_dynamic(self.white_bitmap, self.black_bitmap, self.role)
        print(
            f"[Agent {self.role}] "
            f"Depth reached: {depth_reached}, "
            f"Move chosen: {move_chosen}, "
            f"Score: {score}, "
            f"Time spent: {elapsed:.2f}s, "
            f"Time left: {max(time_left, 0):.2f}s"
        )

    def reset_game(self, setup_msg):
        self.white_bitmap, self.black_bitmap = initialize_boards(setup_msg)
        self.transposition_table.clear()

    # -----------------------------------
    # Learning or Optimization (Placeholder)
    # -----------------------------------
    def train(self, training_data):
        """
        Example stub for a learning routine. 
        Actual RL or supervised learning code would go here.
        This might store updates to self.learning_data or 
        adjust parameters for _evaluate_position.
        """
        if not self.learning_enabled:
            return

        # Pseudocode if we had a param-based evaluation:
        #   for board_state, outcome in training_data:
        #       # Adjust evaluation function parameters
        #       # e.g., using gradient descent or Q-learning
        #       pass

        print("Learning routine is not implemented yet.")

    def print_evaluation(self):
        """
        Prints the current evaluation value of the board.
        The evaluation is computed from the agent's perspective.
        """
        score = evaluate_board_dynamic(self.white_bitmap, self.black_bitmap, self.role)
        print(score)

def main():
    host = "127.0.0.1"
    port = 9999
    role = "White"
    custom_setup = None

    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            port = int(sys.argv[2])
        except ValueError:
            log("Invalid port; using default 9999.")
    if len(sys.argv) >= 4:
        role = sys.argv[3]
    if len(sys.argv) >= 5:
        # e.g., "Setup Wb8 Bd5 Be5"
        custom_setup = sys.argv[4]

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        log("Connected to server.")
    except Exception as e:
        log(f"Could not connect to {host}:{port}: {e}")
        return
    
    s_file = sock.makefile('r')
    
    # Handshake
    msg = s_file.readline().strip()  # e.g. "Connected to the server!"
    log(f"Server says: {msg}")

    if custom_setup and custom_setup.startswith("Setup "):
        send_message(sock, custom_setup)
        ack = s_file.readline().strip()  # Expecting "SETUP-ACK"
        log(f"Server setup acknowledgment: {ack}")
    else:
        send_message(sock, "OK")
    
    # Now receive the board setup.
    msg = s_file.readline().strip()  # Board setup message (e.g. "Setup Wa2 ...")
    log(f"Server says: {msg}")
    if msg.startswith("Setup"):
        white_bitmap, black_bitmap = initialize_boards(msg)
        log("Board setup received and parsed:")
        display_boards(white_bitmap, black_bitmap)
    else:
        log("Unexpected board setup message. Exiting.")
        return

    send_message(sock, "OK")

    # The server tries to provide a time setting here, e.g. "30"
    msg = s_file.readline().strip()
    log(f"Server says: {msg}")

    # BUT we override it with 600:
    GLOBAL_TIME = 600
    log("Overriding server time with 600 seconds for this entire game.")

    send_message(sock, "OK")

    # Next line: "BEGIN"
    msg = s_file.readline().strip()  # e.g., "BEGIN"
    log(f"Server says: {msg}")

    msg = s_file.readline().strip()  # e.g., "Role Black"
    if msg.startswith("Role"):
        assigned_role = msg.split()[1]
        log(f"Assigned role: {assigned_role}")
        role = assigned_role
    else:
        log("No explicit role assigned; using default role.")

    agent = AIAgent(role, white_bitmap, black_bitmap)

    # Print the current evaluation of the board:
    agent.print_evaluation()

    # Keep track of only the time the agent uses:
    agent_time_left = GLOBAL_TIME
    move_count = 0

    while True:
        # If it's our turn:
        is_my_turn = ((role == "White" and move_count % 2 == 0)
                      or (role == "Black" and move_count % 2 == 1))

        if is_my_turn:
            if agent_time_left <= 0:
                log("Agent is out of computed move time!")
                break

            start_move_time = time.time()
            chosen_move = agent.make_move(agent_time_left, move_count)
            end_move_time = time.time()

            move_elapsed = end_move_time - start_move_time
            agent_time_left -= move_elapsed

            log(f"[Agent {role}] used {move_elapsed:.2f}s, {agent_time_left:.2f}s left for the agent.")

            send_message(sock, chosen_move)
            if chosen_move.lower() == "exit":
                log("Exiting game.")
                break
            move_count += 1
        else:
            # Opponent's turn; read their move:
            agent.start_pondering()
            opp_move = s_file.readline().strip()
            agent.stop_pondering()

            if not opp_move or opp_move.lower() in ["exit", "gameover"]:
                log("Game over. Exiting.")
                break

            log(f"Opponent move: {opp_move}")
            if role == "White":
                # Opponent is Black
                execute_move(opp_move, black_bitmap, white_bitmap)
            else:
                # Opponent is White
                execute_move(opp_move, white_bitmap, black_bitmap)

            # Check for a winner
            winner = check_win_conditions(white_bitmap, black_bitmap)
            if winner:
                log(f"Game over: {winner}")
                send_message(sock, f"win: {winner}")
                break
            move_count += 1
    
    sock.close()

if __name__ == "__main__":
    main() 