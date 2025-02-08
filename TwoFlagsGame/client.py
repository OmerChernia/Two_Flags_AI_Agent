import socket
import sys
import time

def send_msg(conn, msg, stats):
    data = msg.encode()
    conn.sendall(data)
    stats["bytes_written"] += len(data)

def recv_msg(conn, stats):
    data = conn.recv(1024)
    if not data:
        return ""
    stats["bytes_read"] += len(data)
    return data.decode().strip()

def convert_coord(coord):
    """
    Convert an algebraic coordinate (e.g. 'a2') to matrix indices.
    The board is stored as an 8x8 list of lists where row 0
    corresponds to the top of the board (rank 8) and row 7 to rank 1.
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
    A pawn is shown as a "P" while an empty square is a dot.
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
    Display both white and black bitmaps.
    """
    display_board(white_bitmap, "White")
    display_board(black_bitmap, "Black")

def execute_move(move, own_bitmap, opp_bitmap):
    """
    Update the appropriate bitmap given a move in the format "e2e4".
    - Removes the pawn from the source cell of the given board.
    - If the destination cell on the opponent's board is occupied, it removes that pawn (capture).
    - Places the pawn in the destination cell of the given board.
    """
    if len(move) != 4:
        print("Invalid move format! Move must be 4 characters (e.g., e2e4).")
        return
    from_coord = move[:2]
    to_coord = move[2:]
    r_from, c_from = convert_coord(from_coord)
    r_to, c_to = convert_coord(to_coord)
    
    if not own_bitmap[r_from][c_from]:
        print(f"Warning: No pawn found at {from_coord} on your board.")
    else:
        # Remove pawn from its current position.
        own_bitmap[r_from][c_from] = False
        # Check for capturing an opponent's pawn.
        if opp_bitmap[r_to][c_to]:
            print("Capture: Opponent's pawn removed!")
            opp_bitmap[r_to][c_to] = False
        # Place the pawn in the destination.
        own_bitmap[r_to][c_to] = True

def start_client():
    # Use command-line args for host and port if provided.
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
        print("Connected to the server!")

        # -- Handshake sequence --
        # Step 2: Receive "Connected to the server!" message.
        msg = recv_msg(s, session_stats)
        print(f"Server says: {msg}")
        # Step 3: Send "OK".
        send_msg(s, "OK", session_stats)

        # Step 4: Receive board setup message.
        msg = recv_msg(s, session_stats)
        print(f"Server says: {msg}")
        # Initialize board bitmaps from the setup message.
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
        msg = recv_msg(s, session_stats)
        print(f"Server says: {msg}")
        # Step 7: Send "OK".
        send_msg(s, "OK", session_stats)

        # Step 9: Receive "Begin" message.
        msg = recv_msg(s, session_stats)
        print(f"Server says: {msg}")

        # Receive role assignment (e.g. "Role White" or "Role Black").
        role_msg = recv_msg(s, session_stats)
        print(f"Server says: {role_msg}")
        role = ""
        if role_msg.startswith("Role"):
            role = role_msg.split()[1]
            print(f"Assigned role: {role}")
        else:
            print("Did not receive role assignment. Exiting.")
            return

        # Set up pointers for updating. If you're White then:
        #   - your own moves update the white bitmap;
        #   - opponent moves update the black bitmap.
        # And vice versa for Black.
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
                my_move = input("Enter your move (or 'exit' to quit): ").strip()
                send_msg(s, my_move, session_stats)
                if my_move.lower() == "exit":
                    break
                # Update your board for your move.
                execute_move(my_move, own_bitmap, opp_bitmap)
                print("Updated board after your move:")
                display_boards(white_bitmap, black_bitmap)

                # Wait for Black's move.
                opp_move = recv_msg(s, session_stats)
                if opp_move.lower() == "exit":
                    print("Server has quit the session.")
                    break
                print("Opponent move received:", opp_move)
                # Update the opponent's board for their move.
                execute_move(opp_move, opp_bitmap, own_bitmap)
                print("Updated board after opponent's move:")
                display_boards(white_bitmap, black_bitmap)
        elif role == "Black":
            print("You are Black. Waiting for White's move.")
            while True:
                # Wait for White's move first.
                opp_move = recv_msg(s, session_stats)
                if opp_move.lower() == "exit":
                    print("Server has quit the session.")
                    break
                print("Opponent move received:", opp_move)
                execute_move(opp_move, opp_bitmap, own_bitmap)
                print("Updated board after opponent's move:")
                display_boards(white_bitmap, black_bitmap)

                my_move = input("Enter your move (or 'exit' to quit): ").strip()
                send_msg(s, my_move, session_stats)
                if my_move.lower() == "exit":
                    break
                execute_move(my_move, own_bitmap, opp_bitmap)
                print("Updated board after your move:")
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
    start_client() 