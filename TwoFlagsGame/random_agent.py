import socket
import sys
import time
import random

def send_msg(conn, msg, stats):
    # Append a newline so that the receiver can determine the end of the message.
    full_msg = msg + "\n"
    data = full_msg.encode()
    conn.sendall(data)
    stats["bytes_written"] += len(data)

def recv_msg(conn_file, stats):
    # Read a full line (i.e. one message ending with '\n')
    line = conn_file.readline()
    if not line:
        return ""
    stats["bytes_read"] += len(line)
    return line.strip()

def convert_coord(coord):
    """
    Convert an algebraic coordinate (e.g. 'a2') to matrix indices.
    The board is stored as an 8x8 list of lists where row 0 corresponds to the top (rank 8)
    and row 7 corresponds to rank 1.
    """
    col = ord(coord[0].lower()) - ord('a')
    row = 8 - int(coord[1])
    return row, col

def coord_to_algebraic(row, col):
    """
    Convert board indices (row, col) to algebraic coordinate (e.g. 'a2').
    Row 0 corresponds to rank 8, row 7 to rank 1.
    """
    letter = chr(ord('a') + col)
    number = str(8 - row)
    return letter + number

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
    # First token should be "Setup", then tokens like "Wa2" follow.
    for token in tokens[1:]:
        if len(token) < 3:
            continue  # skip ill-formed token
        color = token[0]
        pos = token[1:]
        row, col = convert_coord(pos)
        if color == 'W':
            white_bitmap[row][col] = True
        elif color == 'B':
            black_bitmap[row][col] = True
    return white_bitmap, black_bitmap

def display_board(bitmap, label):
    """
    Display a single bitmap with a header.
    Rows are labeled 8 (top) to 1 (bottom) and columns a to h.
    A pawn is shown as a "1" while an empty square is a dot.
    """
    print(f"--- {label} Pawn Board ---")
    print("  a b c d e f g h")
    for i in range(8):
        rank_label = 8 - i
        row_str = ""
        for j in range(8):
            row_str += "1 " if bitmap[i][j] else ". "
        print(f"{rank_label} {row_str}")
    print("")

def display_boards(white_bitmap, black_bitmap):
    """
    Display both the white and black pawn boards.
    """
    display_board(white_bitmap, "White")
    display_board(black_bitmap, "Black")

def execute_move(move, own_bitmap, opp_bitmap):
    """
    Update the appropriate bitmap given a move in the format "e2e4".
    - Removes the pawn from the source cell of own_bitmap.
    - If the destination cell on the opponent's board is occupied, it removes that pawn.
    - Places the pawn in the destination cell of own_bitmap.
    Assumes that the move has already been checked to be legal.
    """
    from_coord = move[:2]
    to_coord = move[2:]
    r_from, c_from = convert_coord(from_coord)
    r_to, c_to = convert_coord(to_coord)
    
    # Remove pawn from its current position.
    own_bitmap[r_from][c_from] = False
    # Capture opponent pawn if present.
    if opp_bitmap[r_to][c_to]:
        print("Capture: Opponent's pawn removed!")
        opp_bitmap[r_to][c_to] = False
    # Place pawn at destination.
    own_bitmap[r_to][c_to] = True

def is_move_legal(move, role, own_bitmap, opp_bitmap):
    """
    Returns True if the move is legal; otherwise prints an error and returns False.

    For White:
      - Move format (e.g. e2e3)
      - The source/destination must be on the board.
      - There must be a pawn at the source.
      - White pawns move upward (decreasing row number).
      - A straight move is only allowed if the destination is empty.
      - Two‑square moves are allowed only from row 6 (the initial position) and only if both squares are empty.
      - Diagonal moves are allowed only when capturing an opponent's pawn.
      
    For Black:
      - Similar rules, but black pawns move downward (increasing row number)
      - Two‑square moves are allowed only from row 1.
    """
    if len(move) != 4:
        print("Invalid move format. Use exactly 4 characters (e.g. e2e3).")
        return False
    try:
        fr, fc = convert_coord(move[0:2])
        tr, tc = convert_coord(move[2:4])
    except Exception as e:
        print("Error: Invalid coordinates.")
        return False

    row_diff = tr - fr
    col_diff = tc - fc

    # Check source cell has a pawn.
    if not own_bitmap[fr][fc]:
        print("Illegal move: no pawn at source location.")
        return False

    if role == "White":
        # For White, moving forward means decreasing row number.
        if row_diff >= 0:
            print("Illegal move: white pawns must move upward.")
            return False
        # Straight move
        if col_diff == 0:
            # One-square move.
            if row_diff == -1:
                if own_bitmap[tr][tc] or opp_bitmap[tr][tc]:
                    print("Illegal move: destination is occupied.")
                    return False
                return True
            # Two-square move from initial row (row 6).
            elif row_diff == -2:
                if fr != 6:
                    print("Illegal move: two-square move allowed only from initial row.")
                    return False
                if own_bitmap[fr - 1][fc] or opp_bitmap[fr - 1][fc]:
                    print("Illegal move: cannot jump over a pawn.")
                    return False
                if own_bitmap[tr][tc] or opp_bitmap[tr][tc]:
                    print("Illegal move: destination is occupied.")
                    return False
                return True
            else:
                print("Illegal move: can only move one square (or two from initial row).")
                return False
        # Diagonal move for capture.
        elif abs(col_diff) == 1 and row_diff == -1:
            if opp_bitmap[tr][tc]:
                return True
            else:
                print("Illegal move: diagonal move allowed only when capturing an opponent's pawn.")
                return False
        else:
            print("Illegal move: unsupported movement pattern for white pawn.")
            return False

    elif role == "Black":
        # For Black, moving forward means increasing row number.
        if row_diff <= 0:
            print("Illegal move: black pawns must move downward.")
            return False
        if col_diff == 0:
            # One-square move.
            if row_diff == 1:
                if own_bitmap[tr][tc] or opp_bitmap[tr][tc]:
                    print("Illegal move: destination is occupied.")
                    return False
                return True
            # Two-square move from initial row (row 1).
            elif row_diff == 2:
                if fr != 1:
                    print("Illegal move: two-square move allowed only from initial row.")
                    return False
                if own_bitmap[fr + 1][fc] or opp_bitmap[fr + 1][fc]:
                    print("Illegal move: cannot jump over a pawn.")
                    return False
                if own_bitmap[tr][tc] or opp_bitmap[tr][tc]:
                    print("Illegal move: destination is occupied.")
                    return False
                return True
            else:
                print("Illegal move: can only move one square (or two from initial row).")
                return False
        elif abs(col_diff) == 1 and row_diff == 1:
            if opp_bitmap[tr][tc]:
                return True
            else:
                print("Illegal move: diagonal move allowed only when capturing an opponent's pawn.")
                return False
        else:
            print("Illegal move: unsupported movement pattern for black pawn.")
            return False

    print("Illegal move: does not match any legal movement patterns.")
    return False

def generate_all_legal_moves(role, own_bitmap, opp_bitmap):
    """
    Scan the board for your pawns and generate all legal moves.
    Returns a list of move strings in the format "e2e3" that are deemed legal.
    """
    moves = []
    for r in range(8):
        for c in range(8):
            if own_bitmap[r][c]:
                src = coord_to_algebraic(r, c)
                if role == "White":
                    # one-square forward
                    nr = r - 1
                    if nr >= 0:
                        dest = coord_to_algebraic(nr, c)
                        cand = src + dest
                        if is_move_legal(cand, role, own_bitmap, opp_bitmap):
                            moves.append(cand)
                    # two-square forward (only from initial row 6)
                    if r == 6:
                        nr = r - 2
                        if nr >= 0:
                            dest = coord_to_algebraic(nr, c)
                            cand = src + dest
                            if is_move_legal(cand, role, own_bitmap, opp_bitmap):
                                moves.append(cand)
                    # diagonal capture left
                    if (c - 1) >= 0 and (r - 1) >= 0:
                        dest = coord_to_algebraic(r - 1, c - 1)
                        cand = src + dest
                        if is_move_legal(cand, role, own_bitmap, opp_bitmap):
                            moves.append(cand)
                    # diagonal capture right
                    if (c + 1) < 8 and (r - 1) >= 0:
                        dest = coord_to_algebraic(r - 1, c + 1)
                        cand = src + dest
                        if is_move_legal(cand, role, own_bitmap, opp_bitmap):
                            moves.append(cand)
                elif role == "Black":
                    # one-square forward
                    nr = r + 1
                    if nr < 8:
                        dest = coord_to_algebraic(nr, c)
                        cand = src + dest
                        if is_move_legal(cand, role, own_bitmap, opp_bitmap):
                            moves.append(cand)
                    # two-square forward (only from initial row 1)
                    if r == 1:
                        nr = r + 2
                        if nr < 8:
                            dest = coord_to_algebraic(nr, c)
                            cand = src + dest
                            if is_move_legal(cand, role, own_bitmap, opp_bitmap):
                                moves.append(cand)
                    # diagonal capture left
                    if (c - 1) >= 0 and (r + 1) < 8:
                        dest = coord_to_algebraic(r + 1, c - 1)
                        cand = src + dest
                        if is_move_legal(cand, role, own_bitmap, opp_bitmap):
                            moves.append(cand)
                    # diagonal capture right
                    if (c + 1) < 8 and (r + 1) < 8:
                        dest = coord_to_algebraic(r + 1, c + 1)
                        cand = src + dest
                        if is_move_legal(cand, role, own_bitmap, opp_bitmap):
                            moves.append(cand)
    return moves

def start_agent():
    # Use command-line arguments for host and port if provided.
    if len(sys.argv) >= 3:
        host = sys.argv[1]
        port = int(sys.argv[2])
    else:
        host = '127.0.0.1'
        port = 9999

    session_stats = {"bytes_read": 0, "bytes_written": 0}
    session_start = time.time()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        # Wrap the socket with a file-like object to enable readline().
        s_file = s.makefile('r')
        print("Connected to the server!")
        
        # -- Handshake sequence --
        # Step 2: Receive "Connected to the server!" message.
        msg = recv_msg(s_file, session_stats)
        print(f"Server says: {msg}")
        # Step 3: Send "OK".
        send_msg(s, "OK", session_stats)
        
        # Step 4: Receive board setup message.
        msg = recv_msg(s_file, session_stats)
        print(f"Server says: {msg}")
        if msg.startswith("Setup"):
            white_bitmap, black_bitmap = initialize_boards(msg)
            print("Initial board setup (parsed from server):")
            display_boards(white_bitmap, black_bitmap)
        else:
            print("Unexpected board setup message. Exiting.")
            return
        # Step 5: Send "OK".
        send_msg(s, "OK", session_stats)
        
        # Step 6: Receive time message.
        msg = recv_msg(s_file, session_stats)
        print(f"Server says: {msg}")
        # Step 7: Send "OK".
        send_msg(s, "OK", session_stats)
        
        # Step 9: Receive "Begin" message.
        msg = recv_msg(s_file, session_stats)
        print(f"Server says: {msg}")
        
        # Receive role assignment (e.g., "Role White" or "Role Black").
        role_msg = recv_msg(s_file, session_stats)
        print(f"Server says: {role_msg}")
        if role_msg.startswith("Role"):
            role = role_msg.split()[1]
            print(f"Assigned role: {role}")
        else:
            print("Did not receive role assignment. Exiting.")
            return

        # Set pointers for updating the board:
        # For White: own_bitmap = white_bitmap, opp_bitmap = black_bitmap.
        # For Black: own_bitmap = black_bitmap, opp_bitmap = white_bitmap.
        if role == "White":
            own_bitmap, opp_bitmap = white_bitmap, black_bitmap
        elif role == "Black":
            own_bitmap, opp_bitmap = black_bitmap, white_bitmap
        else:
            print("Unknown role. Exiting.")
            return

        # -- Game loop based on role --
        if role == "White":
            print("You are White. You make the first move.")
            while True:
                # Agent generates a random legal move.
                legal_moves = generate_all_legal_moves(role, own_bitmap, opp_bitmap)
                if not legal_moves:
                    print("No legal moves available. Exiting.")
                    send_msg(s, "exit", session_stats)
                    break
                my_move = random.choice(legal_moves)
                print(f"Agent move: {my_move}")
                send_msg(s, my_move, session_stats)
                execute_move(my_move, own_bitmap, opp_bitmap)
                print("Updated board after agent's move:")
                display_boards(white_bitmap, black_bitmap)
                
                # Wait for opponent's move.
                opp_move = recv_msg(s_file, session_stats)
                if opp_move.lower() == "exit":
                    print("Server has quit the session.")
                    break
                print("Opponent move received:", opp_move)
                execute_move(opp_move, opp_bitmap, own_bitmap)
                print("Updated board after opponent's move:")
                display_boards(white_bitmap, black_bitmap)
        elif role == "Black":
            print("You are Black. Waiting for White's move.")
            while True:
                # Wait for opponent's move.
                opp_move = recv_msg(s_file, session_stats)
                if opp_move.lower() == "exit":
                    print("Server has quit the session.")
                    break
                print("Opponent move received:", opp_move)
                execute_move(opp_move, opp_bitmap, own_bitmap)
                print("Updated board after opponent's move:")
                display_boards(white_bitmap, black_bitmap)
                
                # Agent generates a random legal move.
                legal_moves = generate_all_legal_moves(role, own_bitmap, opp_bitmap)
                if not legal_moves:
                    print("No legal moves available. Exiting.")
                    send_msg(s, "exit", session_stats)
                    break
                my_move = random.choice(legal_moves)
                print(f"Agent move: {my_move}")
                send_msg(s, my_move, session_stats)
                execute_move(my_move, own_bitmap, opp_bitmap)
                print("Updated board after agent's move:")
                display_boards(white_bitmap, black_bitmap)
        else:
            print("Unknown role. Exiting.")
            return

        elapsed = int(time.time() - session_start)
        print("********Session ********")
        print(f"Bytes written: {session_stats['bytes_written']} Bytes read: {session_stats['bytes_read']}")
        print(f"Elapsed time: {elapsed} secs")
        print("Connection closed")

if __name__ == "__main__":
    start_agent() 