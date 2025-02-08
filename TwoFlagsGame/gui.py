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

# ----------------------
# Spectator Client Thread
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
        self.root.title("Pawn Chess GUI (Spectator)")
        self.root.geometry("600x700")
        
        # --- Configuration Panel for the Spectator ---
        self.config_frame = tk.Frame(self.root)
        tk.Label(self.config_frame, text="Server Host:").grid(row=0, column=0, padx=5, pady=5)
        self.host = tk.StringVar(value="127.0.0.1")
        tk.Entry(self.config_frame, textvariable=self.host).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(self.config_frame, text="Spectator Port:").grid(row=1, column=0, padx=5, pady=5)
        self.spec_port = tk.IntVar(value=10000)
        tk.Entry(self.config_frame, textvariable=self.spec_port).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(self.config_frame, text="Connect", command=self.connect_as_spectator).grid(row=2, column=0, columnspan=2, pady=10)
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
        # The default starting setup string includes white and black tokens.
        self.default_setup = "Setup Wa2 Wb2 Wc2 Wd2 We2 Wf2 Wg2 Wh2 Ba7 Bb7 Bc7 Bd7 Be7 Bf7 Bg7 Bh7"
        self.white_bitmap, self.black_bitmap = initialize_boards(self.default_setup)
        
        self.draw_board()
        
        self.spectator_client = None
        self.current_turn = "White"  # initial turn

    def draw_board(self):
        self.canvas.delete("all")
        square_size = 50
        margin_left = 30
        margin_top = 30
        board_size = 8 * square_size
        colors = ["#f0d9b5", "#b58863"]
        # Draw board squares and pieces
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
            # Remove captured pawn if present.
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
        # Update the board state based on the received move.
        self.update_board_state(msg)
        self.status_label.config(text=f"Move received: {msg}")
        self.draw_board()
        
    def on_spectator_message(self, msg):
        # Schedule the update in the main GUI thread.
        self.root.after(0, self.process_move, msg)
    
    def connect_as_spectator(self):
        host = self.host.get().strip()
        port = self.spec_port.get()
        try:
            self.spectator_client = SpectatorClient(host, port, self.on_spectator_message)
            self.spectator_client.start()
            self.config_frame.pack_forget()
            self.game_frame.pack(fill="both", expand=True)
            self.status_label.config(text="Connected as spectator. Waiting for moves...")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect as spectator: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    gui = PawnChessGUI(root)
    root.mainloop()