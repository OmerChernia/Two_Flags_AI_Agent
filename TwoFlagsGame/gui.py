import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import time
from client import generate_all_legal_moves

# ----------------------
# Helper Functions
# ----------------------
def recv_msg(conn_file, stats):
    try:
        line = conn_file.readline()
        if not line:
            return ""
        stats["bytes_read"] += len(line)
        return line.strip()
    except Exception as e:
        print("Receive error:", e)
        return ""

def coord_to_algebraic(row, col):
    return chr(ord('a') + col) + str(8 - row)

def convert_coord(coord):
    """
    Convert an algebraic coordinate (e.g. 'a2') to board indices.
    Row 0 corresponds to rank 8.
    """
    col = ord(coord[0].lower()) - ord('a')
    row = 8 - int(coord[1])
    return row, col

def initialize_boards(setup_msg):
    # Create bitmaps from the "Setup ..." string.
    white_bitmap = [[False]*8 for _ in range(8)]
    black_bitmap = [[False]*8 for _ in range(8)]
    tokens = setup_msg.split()
    for token in tokens[1:]:
        if len(token) < 3:
            continue
        color = token[0]
        pos = token[1:]
        col = ord(pos[0].lower()) - ord('a')
        row = 8 - int(pos[1])
        if color.upper() == 'W':
            white_bitmap[row][col] = True
        elif color.upper() == 'B':
            black_bitmap[row][col] = True
    return white_bitmap, black_bitmap

def send_msg(conn, msg, stats):
    full_msg = msg + "\n"
    data = full_msg.encode()
    conn.sendall(data)
    stats["bytes_written"] += len(data)

# ----------------------
# Spectator / Human Client Thread (for spectator mode we already used SpectatorClient)
# ----------------------
class SpectatorClient(threading.Thread):
    def __init__(self, host, port, on_message):
        threading.Thread.__init__(self)
        self.host = host
        self.port = port
        self.on_message = on_message
        self.running = True

    def run(self):
        stats = {"bytes_read": 0, "bytes_written": 0}
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.conn_file = self.sock.makefile("r")
            while self.running:
                msg = recv_msg(self.conn_file, stats)
                if msg:
                    self.on_message(msg)
                else:
                    time.sleep(0.1)
        except Exception as e:
            print("Spectator connection error:", e)
        finally:
            try:
                self.sock.close()
            except:
                pass

    def send_message(self, msg):
        try:
            full_msg = msg + "\n"
            self.sock.sendall(full_msg.encode())
        except Exception as e:
            print("Spectator send error:", e)

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except:
            pass

# ----------------------
# Main GUI Class
# ----------------------
class PawnChessGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Pawn Chess GUI (Spectator/Human)")
        self.root.geometry("600x700")
        
        # --- Configuration Panel ---
        self.config_frame = tk.Frame(self.root)
        tk.Label(self.config_frame, text="Server Host:").grid(row=0, column=0, padx=5, pady=5)
        self.host = tk.StringVar(value="127.0.0.1")
        tk.Entry(self.config_frame, textvariable=self.host).grid(row=0, column=1, padx=5, pady=5)
        
        # Spectator mode connection.
        tk.Label(self.config_frame, text="Spectator Port:").grid(row=1, column=0, padx=5, pady=5)
        self.spec_port = tk.IntVar(value=10000)
        tk.Entry(self.config_frame, textvariable=self.spec_port).grid(row=1, column=1, padx=5, pady=5)
        
        # Mode selection: Spectator or Human.
        tk.Label(self.config_frame, text="Mode:").grid(row=2, column=0, padx=5, pady=5)
        self.mode = tk.StringVar(value="Spectator")
        tk.Radiobutton(self.config_frame, text="Spectator", variable=self.mode, value="Spectator").grid(row=2, column=1, padx=5, pady=5, sticky="w")
        tk.Radiobutton(self.config_frame, text="Human", variable=self.mode, value="Human").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        
        # For Human mode connection (game port).
        tk.Label(self.config_frame, text="Game Port (if Human):").grid(row=3, column=0, padx=5, pady=5)
        self.game_port = tk.IntVar(value=9999)
        tk.Entry(self.config_frame, textvariable=self.game_port).grid(row=3, column=1, padx=5, pady=5)
        
        # Connect button.
        tk.Button(self.config_frame, text="Connect", command=self.connect).grid(row=4, column=0, columnspan=3, pady=10)
        
        # --- Custom Board Setup Panel ---
        # Button to start board editing.
        tk.Button(self.config_frame, text="Custom Board Setup", command=self.edit_board_setup)\
            .grid(row=5, column=0, columnspan=3, pady=10)
        # Button to load the custom board (i.e. mark it for upload).
        tk.Button(self.config_frame, text="Load Custom Board", command=self.load_custom_board)\
            .grid(row=7, column=0, columnspan=3, pady=10)
        tk.Label(self.config_frame, text="Starting Side:").grid(row=6, column=0, padx=5, pady=5)
        self.starting_side = tk.StringVar(value="White")
        tk.Radiobutton(self.config_frame, text="White", variable=self.starting_side, value="White")\
            .grid(row=6, column=1, padx=5, pady=5)
        tk.Radiobutton(self.config_frame, text="Black", variable=self.starting_side, value="Black")\
            .grid(row=6, column=2, padx=5, pady=5)
        
        self.config_frame.pack(pady=20)
        
        # --- Game Display Panel ---
        self.game_frame = tk.Frame(self.root)
        self.status_label = tk.Label(self.game_frame, text="Waiting for moves...", font=("Helvetica", 14))
        self.status_label.pack(pady=10)
        self.canvas = tk.Canvas(self.game_frame, width=500, height=500)
        self.canvas.pack(pady=10)
        # Add Replay Button for spectator mode.
        self.replay_button = tk.Button(self.game_frame, text="Replay", command=self.request_replay)
        self.replay_button.pack(pady=5)
        self.game_frame.pack_forget()
        
        # Flag to indicate whether a custom board has been loaded.
        self.use_custom_board = False
        
        # Initialize board state with default setup.
        self.default_setup = "Setup Wa2 Wb2 Wc2 Wd2 We2 Wf2 Wg2 Wh2 Ba7 Bb7 Bc7 Bd7 Be7 Bf7 Bg7 Bh7"
        self.white_bitmap, self.black_bitmap = initialize_boards(self.default_setup)
        self.draw_board()
        
        # Variables for human move input.
        self.selected_square = None   # Used for move selection.
        self.human_mode = False       # True for human play.
        self.sock = None              # Network socket for human connection.
        self.conn_file = None
        self.session_stats = {"bytes_read": 0, "bytes_written": 0}
        self.role = None              # Assigned role from the server.
        # Flag to track if it is the human player's turn.
        self.my_turn = False

    def connect(self):
        mode = self.mode.get()
        host = self.host.get().strip()
        if mode == "Spectator":
            spec_port = self.spec_port.get()
            try:
                self.spectator_client = SpectatorClient(host, spec_port, self.on_spectator_message)
                self.spectator_client.start()
                self.config_frame.pack_forget()
                self.game_frame.pack(fill="both", expand=True)
                self.status_label.config(text="Connected as spectator. Waiting for moves...")
            except Exception as e:
                messagebox.showerror("Connection Error", f"Could not connect as spectator: {e}")
        elif mode == "Human":
            try:
                game_port = int(self.game_port.get())
            except ValueError:
                messagebox.showerror("Invalid Port", "Game port must be an integer.")
                return
            self.connect_as_human(host, game_port)

    def connect_as_human(self, host, game_port):
        try:
            self.human_mode = True
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, game_port))
            self.conn_file = self.sock.makefile("r")
            
            # --- Custom setup sequence (if any) ---
            if self.use_custom_board:
                send_msg(self.sock, self.custom_setup_string, self.session_stats)
                ack = recv_msg(self.conn_file, self.session_stats)
                if ack != "SETUP-ACK":
                    print("Custom setup acknowledgment not received, got:", ack)
                else:
                    print("Custom board setup sent and acknowledged by server.")

            # --- Handshake Sequence ---
            welcome = recv_msg(self.conn_file, self.session_stats)
            print("Server says:", welcome)
            send_msg(self.sock, "OK", self.session_stats)
            
            setup_msg = recv_msg(self.conn_file, self.session_stats)
            print("Server says:", setup_msg)
            self.white_bitmap, self.black_bitmap = initialize_boards(setup_msg)
            self.draw_board()
            send_msg(self.sock, "OK", self.session_stats)
            
            time_msg = recv_msg(self.conn_file, self.session_stats)
            print("Server says:", time_msg)
            send_msg(self.sock, "OK", self.session_stats)
            
            begin_msg = recv_msg(self.conn_file, self.session_stats)
            print("Server says:", begin_msg)
            
            role_msg = recv_msg(self.conn_file, self.session_stats)
            print("Server says:", role_msg)
            if role_msg.startswith("Role"):
                self.role = role_msg.split()[1]
                print("Assigned role:", self.role)
            else:
                messagebox.showerror("Error", "Role not assigned. Exiting.")
                return

            # Switch the display to game mode.
            self.config_frame.pack_forget()
            self.game_frame.pack(fill="both", expand=True)

            # If white, it's your turn right away. Otherwise, wait.
            if self.role == "White":
                self.my_turn = True
                self.status_label.config(text="Connected as HUMAN (White). Your turn!")
            else:
                self.my_turn = False
                self.status_label.config(text="Connected as HUMAN (Black). Waiting for opponent's move...")

            self.canvas.bind("<Button-1>", self.on_canvas_click)
            threading.Thread(target=self.human_listen_thread, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect as human: {e}")

    def human_listen_thread(self):
        # Continuously listen for messages from the server.
        while True:
            msg = recv_msg(self.conn_file, self.session_stats)
            if msg:
                print("Received from server:", msg)
                self.root.after(0, self.process_move, msg)
                # Do not change turn on handshake messages.
                if msg.startswith("BEGIN") or msg.startswith("Role"):
                    pass
                # When a win message is received, just display it.
                elif msg.startswith("win:"):
                    self.root.after(0, self.status_label.config, {"text": msg})
                else:
                    # For any opponent move, it is now your turn.
                    self.root.after(0, self.set_my_turn, True)
            else:
                time.sleep(0.1)

    def is_move_legal(self, move, debug=False):
        """
        Check if the proposed move is legal for the current role.
        Assumes move is a 4-character string (e.g. "a2a4").
        For White, pawns move upward (decreasing row index);
        for Black, downward.
        """
        if len(move) != 4:
            if debug:
                print("Invalid move format (should be 4 characters).")
            return False
        try:
            s_row, s_col = convert_coord(move[:2])
            d_row, d_col = convert_coord(move[2:])
        except Exception as e:
            if debug:
                print("Invalid coordinates:", e)
            return False

        if self.role == "White":
            # Ensure a white pawn is at the source.
            if not self.white_bitmap[s_row][s_col]:
                if debug:
                    print("No white pawn at source.")
                return False
            row_diff = d_row - s_row
            col_diff = d_col - s_col
            # One-step forward move: must be an empty destination.
            if row_diff == -1 and col_diff == 0:
                if self.white_bitmap[d_row][d_col] or self.black_bitmap[d_row][d_col]:
                    if debug:
                        print("Destination occupied.")
                    return False
                return True
            # Two-step forward move from initial row (row 6 for white).
            elif row_diff == -2 and col_diff == 0 and s_row == 6:
                # Check intermediate square (row 5) and destination (row 4) are empty.
                if (self.white_bitmap[s_row-1][s_col] or self.black_bitmap[s_row-1][s_col] or
                    self.white_bitmap[d_row][d_col] or self.black_bitmap[d_row][d_col]):
                    if debug:
                        print("Path obstructed for two-step move.")
                    return False
                return True
            # Diagonal capture.
            elif row_diff == -1 and abs(col_diff) == 1:
                if self.black_bitmap[d_row][d_col]:
                    return True
                else:
                    if debug:
                        print("No black pawn to capture diagonally.")
                    return False
            else:
                if debug:
                    print("Invalid move direction/step for white pawn.")
                return False

        elif self.role == "Black":
            # Ensure a black pawn is at the source.
            if not self.black_bitmap[s_row][s_col]:
                if debug:
                    print("No black pawn at source.")
                return False
            row_diff = d_row - s_row
            col_diff = d_col - s_col
            # One-step forward move.
            if row_diff == 1 and col_diff == 0:
                if self.white_bitmap[d_row][d_col] or self.black_bitmap[d_row][d_col]:
                    if debug:
                        print("Destination occupied.")
                    return False
                return True
            # Two-step forward move from initial row (row 1 for black).
            elif row_diff == 2 and col_diff == 0 and s_row == 1:
                if (self.white_bitmap[s_row+1][s_col] or self.black_bitmap[s_row+1][s_col] or
                    self.white_bitmap[d_row][d_col] or self.black_bitmap[d_row][d_col]):
                    if debug:
                        print("Path obstructed for two-step move.")
                    return False
                return True
            # Diagonal capture.
            elif row_diff == 1 and abs(col_diff) == 1:
                if self.white_bitmap[d_row][d_col]:
                    return True
                else:
                    if debug:
                        print("No white pawn to capture diagonally.")
                    return False
            else:
                if debug:
                    print("Invalid move direction/step for black pawn.")
                return False
        else:
            if debug:
                print("Unknown role:", self.role)
            return False

    def on_canvas_click(self, event):
        """
        Handles the canvas click in human mode.
        Checks that it is your turn before accepting a move.
        """
        # Only process if in human mode and it is currently your turn.
        if not self.human_mode or not self.my_turn:
            self.status_label.config(text="Not your turn! Please wait.")
            return

        square_size = 50
        margin_left = 30
        margin_top = 30
        col = (event.x - margin_left) // square_size
        row = (event.y - margin_top) // square_size

        if 0 <= row < 8 and 0 <= col < 8:
            clicked_square = coord_to_algebraic(row, col)
            if not self.selected_square:
                self.selected_square = clicked_square
                self.status_label.config(
                    text=f"Selected source: {clicked_square}. Now select destination."
                )
            else:
                move = self.selected_square + clicked_square
                if self.is_move_legal(move):
                    self.status_label.config(text=f"Sending move: {move}")
                    send_msg(self.sock, move, self.session_stats)
                    self.update_board_state(move)
                    self.draw_board()
                    # Disable your turn immediately after sending your move.
                    self.my_turn = False
                    self.status_label.config(text="Waiting for opponent's move...")
                else:
                    self.status_label.config(text=f"Illegal move: {move}")
                self.selected_square = None

    def draw_board(self):
        self.canvas.delete("all")
        square_size = 50
        margin_left = 30
        margin_top = 30
        board_size = 8 * square_size
        colors = ["#f0d9b5", "#b58863"]
        # Draw board squares and pieces.
        for row in range(8):
            for col in range(8):
                x0 = margin_left + col * square_size
                y0 = margin_top + row * square_size
                x1 = x0 + square_size
                y1 = y0 + square_size
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=colors[(row+col)%2], outline="black")
                # Draw white pawn with an outline for contrast.
                if self.white_bitmap[row][col]:
                    self.canvas.create_text(x0 + square_size/2 + 1, y0 + square_size/2 + 1, 
                                              text="♙", font=("Helvetica", 24), fill="black")
                    self.canvas.create_text(x0 + square_size/2, y0 + square_size/2, 
                                              text="♙", font=("Helvetica", 24), fill="white")
                # Draw black pawn with an outline.
                if self.black_bitmap[row][col]:
                    self.canvas.create_text(x0 + square_size/2 + 1, y0 + square_size/2 + 1, 
                                              text="♟", font=("Helvetica", 24), fill="white")
                    self.canvas.create_text(x0 + square_size/2, y0 + square_size/2, 
                                              text="♟", font=("Helvetica", 24), fill="black")
        # Draw column labels (a-h) below the board.
        for col in range(8):
            label = chr(ord('a') + col)
            x = margin_left + col * square_size + square_size/2
            y = margin_top + board_size + 15  # offset below the board
            self.canvas.create_text(x, y, text=label, font=("Helvetica", 12))
        # Draw row labels (8 through 1) along the left side.
        for row in range(8):
            label = str(8 - row)
            x = margin_left - 15  # offset to the left of the board
            y = margin_top + row * square_size + square_size/2
            self.canvas.create_text(x, y, text=label, font=("Helvetica", 12))
            
    def update_board_state(self, msg):
        # Only process msg if it is a valid move (length 4 with proper coordinate formatting).
        if not (len(msg) == 4 and msg[0].isalpha() and msg[1].isdigit() 
                and msg[2].isalpha() and msg[3].isdigit()):
            print("Ignoring non-move message:", msg)
            return

        source = msg[:2]
        dest = msg[2:4]
        s_row, s_col = convert_coord(source)
        d_row, d_col = convert_coord(dest)
        # Proceed to update the internal board state with the computed indices.
        # Determine which side's pawn is being moved.
        if self.white_bitmap[s_row][s_col]:
            self.white_bitmap[s_row][s_col] = False
            if self.black_bitmap[d_row][d_col]:
                self.black_bitmap[d_row][d_col] = False
            self.white_bitmap[d_row][d_col] = True
        elif self.black_bitmap[s_row][s_col]:
            self.black_bitmap[s_row][s_col] = False
            if self.white_bitmap[d_row][d_col]:
                self.white_bitmap[d_row][d_col] = False
            self.black_bitmap[d_row][d_col] = True

    def process_move(self, msg):
        print("Processing move:", msg)
        self.update_board_state(msg)
        self.status_label.config(text=f"Move received: {msg}")
        self.draw_board()
    
        # Check for win conditions after updating the board.
        winner = self.check_win_conditions()
        if winner:
            self.status_label.config(text=f"Game Over: {winner}")
            # Disable further moves.
            self.my_turn = False
            
    def check_win_conditions(self):
        """
        Check if a winning condition has been reached.
        White wins if a white pawn reaches row 0.
        Black wins if a black pawn reaches row 7.
        Also checks if one side has no pawns left or no legal moves.
        """
        # Check promotion.
        for col in range(8):
            if self.white_bitmap[0][col]:
                return "White wins"
            if self.black_bitmap[7][col]:
                return "Black wins"
        
        # Check piece counts.
        white_count = sum(1 for row in self.white_bitmap for cell in row if cell)
        black_count = sum(1 for row in self.black_bitmap for cell in row if cell)
        if black_count == 0:
            return "White wins"
        if white_count == 0:
            return "Black wins"
        
        # Check if either side has no legal moves.
        white_moves = generate_all_legal_moves("White", self.white_bitmap, self.black_bitmap)
        black_moves = generate_all_legal_moves("Black", self.black_bitmap, self.white_bitmap)
        if not white_moves:
            return "Black wins"
        if not black_moves:
            return "White wins"
        
        return None
        
    def on_spectator_message(self, msg):
        # For spectator mode, schedule the update in the main GUI thread.
        self.root.after(0, self.process_move, msg)

    # --- New Methods for Board Setup Mode ---
    def set_setup_color(self, color):
        """Set the pawn color to be used in board setup."""
        self.setup_color = color
        if hasattr(self, 'status_label'):
            self.status_label.config(text=f"Selected Pawn Color for Setup: {color}")

    def edit_board_setup(self):
        """Enter board setup mode to define a custom board configuration."""
        # Hide configuration and game view panels.
        self.config_frame.pack_forget()
        self.game_frame.pack_forget()
        # Create a new frame for board setup.
        self.setup_frame = tk.Frame(self.root)
        tk.Label(self.setup_frame, text="Board Setup Mode", font=("Helvetica", 16)).pack(pady=10)
        # Buttons to select pawn color.
        color_frame = tk.Frame(self.setup_frame)
        tk.Button(color_frame, text="White Pawn", command=lambda: self.set_setup_color("White"))\
            .pack(side="left", padx=5)
        tk.Button(color_frame, text="Black Pawn", command=lambda: self.set_setup_color("Black"))\
            .pack(side="left", padx=5)
        tk.Button(color_frame, text="Clear Board", command=self.clear_board_setup)\
            .pack(side="left", padx=5)
        color_frame.pack()
        # Create a new canvas for board setup (do not reuse the game canvas).
        self.setup_canvas = tk.Canvas(self.setup_frame, width=500, height=500)
        self.setup_canvas.pack(pady=10)
        tk.Button(self.setup_frame, text="Finish Setup", command=self.finish_board_setup)\
            .pack(pady=10)
        self.setup_frame.pack(pady=20)
        # Clear board state for custom setup.
        self.white_bitmap = [[False]*8 for _ in range(8)]
        self.black_bitmap = [[False]*8 for _ in range(8)]
        self.draw_setup_board()
        self.setup_color = "White"
        # Bind canvas clicks to the board setup handler.
        self.setup_canvas.bind("<Button-1>", self.on_setup_canvas_click_setup)

    def draw_setup_board(self):
        """Draw the board on the setup canvas."""
        self.setup_canvas.delete("all")
        square_size = 50
        margin_left = 30
        margin_top = 30
        colors = ["#f0d9b5", "#b58863"]
        for row in range(8):
            for col in range(8):
                x0 = margin_left + col * square_size
                y0 = margin_top + row * square_size
                x1 = x0 + square_size
                y1 = y0 + square_size
                self.setup_canvas.create_rectangle(x0, y0, x1, y1,
                                                   fill=colors[(row + col) % 2],
                                                   outline="black")
                # Draw white pawn with an outline.
                if self.white_bitmap[row][col]:
                    self.setup_canvas.create_text(x0 + square_size/2 + 1,
                                                  y0 + square_size/2 + 1,
                                                  text="♙", font=("Helvetica", 24),
                                                  fill="black")
                    self.setup_canvas.create_text(x0 + square_size/2,
                                                  y0 + square_size/2,
                                                  text="♙", font=("Helvetica", 24),
                                                  fill="white")
                # Draw black pawn with an outline.
                if self.black_bitmap[row][col]:
                    self.setup_canvas.create_text(x0 + square_size/2 + 1,
                                                  y0 + square_size/2 + 1,
                                                  text="♟", font=("Helvetica", 24),
                                                  fill="white")
                    self.setup_canvas.create_text(x0 + square_size/2,
                                                  y0 + square_size/2,
                                                  text="♟", font=("Helvetica", 24),
                                                  fill="black")
        # (Optional) You can also add coordinate labels if desired.

    def on_setup_canvas_click_setup(self, event):
        """Place a pawn on the board during setup according to the selected color."""
        square_size = 50
        margin_left = 30
        margin_top = 30
        col = (event.x - margin_left) // square_size
        row = (event.y - margin_top) // square_size
        if 0 <= row < 8 and 0 <= col < 8:
            if self.setup_color == "White":
                self.white_bitmap[row][col] = True
                self.black_bitmap[row][col] = False
            elif self.setup_color == "Black":
                self.black_bitmap[row][col] = True
                self.white_bitmap[row][col] = False
            self.draw_setup_board()

    def clear_board_setup(self):
        """Clear the board in board setup mode."""
        self.white_bitmap = [[False]*8 for _ in range(8)]
        self.black_bitmap = [[False]*8 for _ in range(8)]
        # If the setup canvas exists, redraw the board.
        if hasattr(self, "setup_canvas"):
            self.draw_setup_board()

    def finish_board_setup(self):
        """Generate the Setup string from the board state and return to the configuration panel."""
        tokens = []
        for row in range(8):
            for col in range(8):
                pos = coord_to_algebraic(row, col)
                if self.white_bitmap[row][col]:
                    tokens.append("W" + pos)
                elif self.black_bitmap[row][col]:
                    tokens.append("B" + pos)
        self.custom_setup_string = "Setup " + " ".join(tokens)
        self.status_label.config(text=f"Custom Setup: {self.custom_setup_string}")
        # Destroy the setup frame (and its canvas) then show the config panel.
        self.setup_frame.destroy()
        self.config_frame.pack(pady=20)

    def load_custom_board(self):
        """
        Called when the user clicks the "Load Custom Board" button.
        It verifies that a custom setup was configured and sets a flag,
        so that later when connecting the custom board is sent to the server.
        """
        if self.custom_setup_string:
            self.use_custom_board = True
            messagebox.showinfo("Custom Setup Loaded",
                                f"Custom board loaded:\n{self.custom_setup_string}")
            print("Custom board loaded and will be sent during connection.")
        else:
            messagebox.showerror("Error",
                                 "No custom board setup defined. Please edit the board setup first.")

    def set_my_turn(self, flag):
        self.my_turn = flag
        if flag:
            self.status_label.config(text="Your turn!")

    def request_replay(self):
        """
        Called when the Replay button is clicked.
        Sends a replay command to the server via the spectator connection.
        """
        if hasattr(self, 'spectator_client') and self.spectator_client is not None:
            self.spectator_client.send_message("REPLAY")
            self.status_label.config(text="Replay requested. Waiting for new game setup...")
        else:
            print("No spectator connection available.")

if __name__ == "__main__":
    root = tk.Tk()
    gui = PawnChessGUI(root)
    root.mainloop()