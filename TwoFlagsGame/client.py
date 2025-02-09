import socket
import sys
import time

def send_msg(conn, msg, stats):
    # Append newline for message termination.
    full_msg = msg + "\n"
    data = full_msg.encode()
    try:
        conn.sendall(data)
        stats["bytes_written"] += len(data)
    except BrokenPipeError:
        print("Send error: Broken pipe.")

def recv_msg(conn_file, stats):
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

def display_board(bitmap, label):
    """
    Display a single bitmap with a header.
    Rows are labeled 8 (top) to 1 (bottom) and columns a to h.
    A pawn is shown as a "1" while an empty square is a dot.
    """
    print(f"--- {label} Pawn Board ---")
    print("  a b c d e f g h")
    for i in range(8):
        row_str = ""
        for j in range(8):
            row_str += "1 " if bitmap[i][j] else ". "
        print(f"{8 - i} {row_str}")
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

def is_move_legal(move, role, own_bitmap, opp_bitmap, debug=True):
    """
    Returns True if the move is legal; otherwise prints an error and returns False.

    Legal move constraints checked:
      1. Format: exactly 4 characters.
      2. Source/destination coordinates must be on board.
      3. A pawn must be at the source position.
      4. Pawns must move in the forward direction (White upward, Black downward).
      5. A straight move must target an empty square.
      6. Two‑square forward moves are allowed only from the initial row
         (row 6 for White, row 1 for Black) and only if the path is clear.
      7. Diagonal moves are allowed only for capturing an opponent pawn.
      8. Any other displacement is illegal.
    """
    if len(move) != 4:
        if debug:
            print("Invalid move format. Use exactly 4 characters (e.g. e2e3).")
        return False
    try:
        fr, fc = convert_coord(move[0:2])
        tr, tc = convert_coord(move[2:4])
    except Exception as e:
        if debug:
            print("Error: Invalid coordinates.")
        return False

    row_diff = tr - fr
    col_diff = tc - fc

    if not own_bitmap[fr][fc]:
        if debug:
            print("Illegal move: no pawn at the source position.")
        return False

    if role == "White":
        if row_diff >= 0:
            if debug:
                print("Illegal move: white pawns must move upward.")
            return False
        if col_diff == 0:
            if row_diff == -1:
                if own_bitmap[tr][tc] or opp_bitmap[tr][tc]:
                    if debug:
                        print("Illegal move: destination is occupied.")
                    return False
                return True
            elif row_diff == -2:
                if fr != 6:
                    if debug:
                        print("Illegal move: two-square move allowed only from initial row.")
                    return False
                if own_bitmap[fr - 1][fc] or opp_bitmap[fr - 1][fc]:
                    if debug:
                        print("Illegal move: cannot jump over a pawn.")
                    return False
                if own_bitmap[tr][tc] or opp_bitmap[tr][tc]:
                    if debug:
                        print("Illegal move: destination is occupied.")
                    return False
                return True
            else:
                if debug:
                    print("Illegal move: can only move one square (or two from initial row).")
                return False
        elif abs(col_diff) == 1 and row_diff == -1:
            if opp_bitmap[tr][tc]:
                return True
            else:
                if debug:
                    print("Illegal move: diagonal move allowed only when capturing an opponent's pawn.")
                return False
        else:
            if debug:
                print("Illegal move: unsupported movement pattern for white pawn.")
            return False
    elif role == "Black":
        if row_diff <= 0:
            if debug:
                print("Illegal move: black pawns must move downward.")
            return False
        if col_diff == 0:
            if row_diff == 1:
                if own_bitmap[tr][tc] or opp_bitmap[tr][tc]:
                    if debug:
                        print("Illegal move: destination is occupied.")
                    return False
                return True
            elif row_diff == 2:
                if fr != 1:
                    if debug:
                        print("Illegal move: two-square move allowed only from initial row.")
                    return False
                if own_bitmap[fr + 1][fc] or opp_bitmap[fr + 1][fc]:
                    if debug:
                        print("Illegal move: cannot jump over a pawn.")
                    return False
                if own_bitmap[tr][tc] or opp_bitmap[tr][tc]:
                    if debug:
                        print("Illegal move: destination is occupied.")
                    return False
                return True
            else:
                if debug:
                    print("Illegal move: can only move one square (or two from initial row).")
                return False
        elif abs(col_diff) == 1 and row_diff == 1:
            if opp_bitmap[tr][tc]:
                return True
            else:
                if debug:
                    print("Illegal move: diagonal move allowed only when capturing an opponent's pawn.")
                return False
        else:
            if debug:
                print("Illegal move: unsupported movement pattern for black pawn.")
            return False
    if debug:
        print("Illegal move: does not match any legal movement patterns.")
    return False

def coord_to_algebraic(row, col):
    """
    Convert board indices to algebraic coordinate (e.g. 'a2').
    Row 0 corresponds to rank 8; row 7 corresponds to rank 1.
    """
    letter = chr(ord('a') + col)
    number = str(8 - row)
    return letter + number

def generate_all_legal_moves(role, own_bitmap, opp_bitmap):
    """
    Scan the board for all pawns of the given role and generate candidate moves.
    Only moves that pass is_move_legal() are included.
    """
    moves = []
    for r in range(8):
        for c in range(8):
            if not own_bitmap[r][c]:
                continue
            src = coord_to_algebraic(r, c)
            if role == "White":
                # One-square forward.
                nr = r - 1
                if nr >= 0:
                    dest = coord_to_algebraic(nr, c)
                    candidate = src + dest
                    if is_move_legal(candidate, role, own_bitmap, opp_bitmap, debug=False):
                        moves.append(candidate)
                # Two-square move (only from initial row 6).
                if r == 6:
                    nr = r - 2
                    if nr >= 0:
                        dest = coord_to_algebraic(nr, c)
                        candidate = src + dest
                        if is_move_legal(candidate, role, own_bitmap, opp_bitmap, debug=False):
                            moves.append(candidate)
                # Diagonal captures.
                nr = r - 1
                for dc in [-1, 1]:
                    nc = c + dc
                    if 0 <= nc < 8 and nr >= 0:
                        dest = coord_to_algebraic(nr, nc)
                        candidate = src + dest
                        if is_move_legal(candidate, role, own_bitmap, opp_bitmap, debug=False):
                            moves.append(candidate)
            elif role == "Black":
                # One-square forward.
                nr = r + 1
                if nr < 8:
                    dest = coord_to_algebraic(nr, c)
                    candidate = src + dest
                    if is_move_legal(candidate, role, own_bitmap, opp_bitmap, debug=False):
                        moves.append(candidate)
                # Two-square move (only from initial row 1).
                if r == 1:
                    nr = r + 2
                    if nr < 8:
                        dest = coord_to_algebraic(nr, c)
                        candidate = src + dest
                        if is_move_legal(candidate, role, own_bitmap, opp_bitmap, debug=False):
                            moves.append(candidate)
                # Diagonal captures.
                nr = r + 1
                for dc in [-1, 1]:
                    nc = c + dc
                    if 0 <= nc < 8 and nr < 8:
                        dest = coord_to_algebraic(nr, nc)
                        candidate = src + dest
                        if is_move_legal(candidate, role, own_bitmap, opp_bitmap, debug=False):
                            moves.append(candidate)
    return moves

def check_win_conditions(white_bitmap, black_bitmap):
    """
    Examine the two board bitmaps and determine if a win condition has been met.
    Returns a win message string (e.g. "White wins") or None otherwise.
    
    Conditions:
      1. A pawn has reached the opponent's first row.
         - White wins if any white pawn is on row 0.
         - Black wins if any black pawn is on row 7.
      2. One player has no pawns left.
      3. One player cannot make any legal move.
    """
    # Condition 1.
    for c in range(8):
        if white_bitmap[0][c]:
            return "White wins"
    for c in range(8):
        if black_bitmap[7][c]:
            return "Black wins"
    # Condition 2.
    white_count = sum(cell for row in white_bitmap for cell in row)
    black_count = sum(cell for row in black_bitmap for cell in row)
    if black_count == 0:
        return "White wins"
    if white_count == 0:
        return "Black wins"
    # Condition 3.
    if not generate_all_legal_moves("White", white_bitmap, black_bitmap):
        return "Black wins"
    if not generate_all_legal_moves("Black", black_bitmap, white_bitmap):
        return "White wins"
    return None

def start_client():
    if len(sys.argv) >= 3:
        host = sys.argv[1]
        port = int(sys.argv[2])
    else:
        host = '127.0.0.1'
        port = 9999
    custom_setup = None
    if len(sys.argv) >= 4:
        custom_setup = sys.argv[3]
    
    session_stats = {"bytes_read": 0, "bytes_written": 0}
    session_start = time.time()
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s_file = s.makefile('r')
        print("Connected to the server!")
        
        # --- Handshake Sequence ---
        msg = recv_msg(s_file, session_stats)
        print(f"Server says: {msg}")
        if custom_setup and custom_setup.startswith("Setup "):
            send_msg(s, custom_setup, session_stats)
            ack = recv_msg(s_file, session_stats)
            print("Server setup acknowledgment:", ack)
        else:
            send_msg(s, "OK", session_stats)
        
        msg = recv_msg(s_file, session_stats)
        print(f"Server says: {msg}")
        if msg.startswith("Setup"):
            white_bitmap, black_bitmap = initialize_boards(msg)
            print("Initial board setup (parsed from server):")
            display_boards(white_bitmap, black_bitmap)
        else:
            print("Unexpected board setup message. Exiting.")
            return
        
        # Continue handshake (time, BEGIN, role assignment, etc.)
        send_msg(s, "OK", session_stats)
        msg = recv_msg(s_file, session_stats)
        print(f"Server says: {msg}")
        send_msg(s, "OK", session_stats)
        msg = recv_msg(s_file, session_stats)
        print(f"Server says: {msg}")
        role_msg = recv_msg(s_file, session_stats)
        print(f"Server says: {role_msg}")
        if role_msg.startswith("Role"):
            role = role_msg.split()[1]
            print(f"Assigned role: {role}")
        else:
            print("Did not receive role assignment. Exiting.")
            return
        
        # Set pointers for updating:
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
                all_moves = generate_all_legal_moves(role, own_bitmap, opp_bitmap)
                if not all_moves:
                    # No legal moves => opponent wins.
                    opponent = "White" if role == "Black" else "Black"
                    print(f"No moves left for {role}. {opponent} wins!")
                    win_msg = f"win: {opponent}"
                    send_msg(s, win_msg, session_stats)
                    break

                my_move = input("Enter your move (or 'exit' to quit): ").strip()
                if my_move.lower() == "exit":
                    break
                if is_move_legal(my_move, role, own_bitmap, opp_bitmap, debug=False):
                    break
                else:
                    print("Illegal move. Please try again.")
                if my_move.lower() == "exit":
                    send_msg(s, my_move, session_stats)
                    break

                send_msg(s, my_move, session_stats)
                execute_move(my_move, own_bitmap, opp_bitmap)
                print("Updated board after your move:")
                display_boards(white_bitmap, black_bitmap)

                # Check win condition.
                winner = check_win_conditions(white_bitmap, black_bitmap)
                if winner:
                    win_msg = f"win: {winner}"
                    send_msg(s, win_msg, session_stats)
                    print(win_msg)
                    # (Game over reached; see below for replay handling.)
                # Wait for opponent's move.
                opp_move = recv_msg(s_file, session_stats)
                if opp_move.lower() == "exit":
                    print("Server has quit the session.")
                    break
                print("Opponent move received:", opp_move)
                execute_move(opp_move, opp_bitmap, own_bitmap)
                print("Updated board after opponent's move:")
                display_boards(white_bitmap, black_bitmap)

                winner = check_win_conditions(white_bitmap, black_bitmap)
                if winner:
                    win_msg = f"win: {winner}"
                    send_msg(s, win_msg, session_stats)
                    print(win_msg)
                    # (Do not break—wait for a possible replay command instead.)
        elif role == "Black":
            print("You are Black. Waiting for White's move.")
            while True:
                opp_move = recv_msg(s_file, session_stats)
                if opp_move.lower() == "exit":
                    print("Server has quit the session.")
                    break
                print("Opponent move received:", opp_move)
                execute_move(opp_move, opp_bitmap, own_bitmap)
                print("Updated board after opponent's move:")
                display_boards(white_bitmap, black_bitmap)

                # Get your move.
                while True:
                    all_moves = generate_all_legal_moves(role, own_bitmap, opp_bitmap)
                    if not all_moves:
                        # No legal moves => opponent wins.
                        opponent = "White" if role == "Black" else "Black"
                        print(f"No moves left for {role}. {opponent} wins!")
                        win_msg = f"win: {opponent}"
                        send_msg(s, win_msg, session_stats)
                        break

                    my_move = input("Enter your move (or 'exit' to quit): ").strip()
                    if my_move.lower() == "exit":
                        break
                    if is_move_legal(my_move, role, own_bitmap, opp_bitmap, debug=False):
                        break
                    else:
                        print("Illegal move. Please try again.")
                if my_move.lower() == "exit":
                    send_msg(s, my_move, session_stats)
                    break

                send_msg(s, my_move, session_stats)
                execute_move(my_move, own_bitmap, opp_bitmap)
                print("Updated board after your move:")
                display_boards(white_bitmap, black_bitmap)

                win_message = check_win_conditions(white_bitmap, black_bitmap)
                if win_message:
                    print(win_message)
                    send_msg(s, win_message, session_stats)
                    # (Continue looping so that replay commands can be handled.)
        else:
            print("Unknown role. Exiting.")
            return

        elapsed = int(time.time() - session_start)
        print("********Session ********")
        print(f"Bytes written: {session_stats['bytes_written']} Bytes read: {session_stats['bytes_read']}")
        print(f"Elapsed time: {elapsed} secs")
        print("Connection closed")

if __name__ == "__main__":
    start_client() 