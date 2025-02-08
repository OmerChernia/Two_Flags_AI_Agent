import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import time

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
        
        # For Spectator mode connection
        tk.Label(self.config_frame, text="Spectator Port:").grid(row=1, column=0, padx=5, pady=5)
        self.spec_port = tk.IntVar(value=10000)
        tk.Entry(self.config_frame, textvariable=self.spec_port).grid(row=1, column=1, padx=5, pady=5)
        
        # Mode selection: Spectator or Human
        tk.Label(self.config_frame, text="Mode:").grid(row=2, column=0, padx=5, pady=5)
        self.mode = tk.StringVar(value="Spectator")
        tk.Radiobutton(self.config_frame, text="Spectator", variable=self.mode, value="Spectator").grid(row=2, column=1, padx=5, pady=5, sticky="w")
        tk.Radiobutton(self.config_frame, text="Human", variable=self.mode, value="Human").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        
        # For Human mode connection (game port)
        tk.Label(self.config_frame, text="Game Port (if Human):").grid(row=3, column=0, padx=5, pady=5)
        self.game_port = tk.IntVar(value=9999)
        tk.Entry(self.config_frame, textvariable=self.game_port).grid(row=3, column=1, padx=5, pady=5)
        
        tk.Button(self.config_frame, text="Connect", command=self.connect).grid(row=4, column=0, columnspan=3, pady=10)
        self.config_frame.pack(pady=20)
        
        # --- Game Display Panel ---
        self.game_frame = tk.Frame(self.root)
        self.status_label = tk.Label(self.game_frame, text="Waiting for moves...", font=("Helvetica", 14))
        self.status_label.pack(pady=10)
        # Increase canvas size to allow for board plus coordinate labels
        self.canvas = tk.Canvas(self.game_frame, width=500, height=500)
        self.canvas.pack(pady=10)
        self.game_frame.pack_forget()
        
        # Initialize board state.
        self.default_setup = "Setup Wa2 Wb2 Wc2 Wd2 We2 Wf2 Wg2 Wh2 Ba7 Bb7 Bc7 Bd7 Be7 Bf7 Bg7 Bh7"
        self.white_bitmap, self.black_bitmap = initialize_boards(self.default_setup)
        self.draw_board()
        
        # Variables for human move input.
        self.selected_square = None   # Will store the first click (source square)
        self.human_mode = False       # True if player is human (not spectating)
        self.sock = None              # Network socket for human connection
        self.conn_file = None
        self.session_stats = {"bytes_read": 0, "bytes_written": 0}
        self.role = None              # Assigned role from the server

    def connect(self):
        mode = self.mode.get()
        host = self.host.get().strip()
        if mode == "Spectator":
            spec_port = self.spec_port.get()
            # Connect as spectator (existing behavior)
            try:
                self.spectator_client = SpectatorClient(host, spec_port, self.on_spectator_message)
                self.spectator_client.start()
                self.config_frame.pack_forget()
                self.game_frame.pack(fill="both", expand=True)
                self.status_label.config(text="Connected as spectator. Waiting for moves...")
            except Exception as e:
                messagebox.showerror("Connection Error", f"Could not connect as spectator: {e}")
        elif mode == "Human":
            game_port = self.game_port.get()
            self.connect_as_human(host, game_port)

    def connect_as_human(self, host, game_port):
        try:
            self.human_mode = True
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, game_port))
            self.conn_file = self.sock.makefile("r")
            # --- Handshake sequence (similar to client.py) ---
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
            # Switch to game view.
            self.config_frame.pack_forget()
            self.game_frame.pack(fill="both", expand=True)
            if self.role == "White":
                self.status_label.config(text="Connected as HUMAN (White). Your turn!")
            else:
                self.status_label.config(text="Connected as HUMAN (Black). Waiting for opponent's move...")
            # Bind the canvas for move input.
            self.canvas.bind("<Button-1>", self.on_canvas_click)
            # Start a background thread to listen for server messages.
            threading.Thread(target=self.human_listen_thread, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect as human: {e}")

    def human_listen_thread(self):
        # Continuously listen for messages from the server.
        while True:
            msg = recv_msg(self.conn_file, self.session_stats)
            if msg:
                print("Received from server:", msg)
                # Update the board in the main GUI thread.
                self.root.after(0, self.process_move, msg)
                # When it is our turn, update the status label.
                if ("BEGIN" in msg) or msg.startswith("Role"):
                    # ignore
                    pass
                elif msg.startswith("win:"):
                    self.root.after(0, self.status_label.config, {"text": msg})
                elif self.role == "Black":
                    # If Black, once a move arrives, it means it's now our turn.
                    self.root.after(0, self.status_label.config, {"text": "Your turn!"})
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
        # This method is used only in human mode.
        if not self.human_mode:
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
                self.status_label.config(text=f"Selected source: {clicked_square}. Now select destination.")
            else:
                move = self.selected_square + clicked_square
                if self.is_move_legal(move):
                    self.status_label.config(text=f"Sending move: {move}")
                    send_msg(self.sock, move, self.session_stats)
                    # Immediately update the board for visual feedback.
                    self.update_board_state(move)
                    self.draw_board()
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
            
    def update_board_state(self, move_str):
        """
        Update the board state based on a move string (e.g. "a2a4").
        It moves the pawn from the source to the destination square,
        and if there is an opponent piece on the destination, it is removed.
        """
        if len(move_str) < 4:
            return
        source = move_str[0:2]
        dest = move_str[2:4]
        s_row, s_col = convert_coord(source)
        d_row, d_col = convert_coord(dest)
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
        
    def on_spectator_message(self, msg):
        # For spectator mode, schedule the update in the main GUI thread.
        self.root.after(0, self.process_move, msg)

if __name__ == "__main__":
    root = tk.Tk()
    gui = PawnChessGUI(root)
    root.mainloop()