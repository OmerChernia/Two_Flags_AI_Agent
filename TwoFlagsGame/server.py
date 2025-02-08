import socket
import select
import time
import threading
import tkinter as tk
from gui import PawnChessGUI

def send_msg(conn, msg, stats):
    full_msg = msg + "\n"
    data = full_msg.encode()
    try:
        conn.sendall(data)
        stats["bytes_written"] += len(data)
    except Exception as e:
        print("Send error:", e)

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

def start_server():
    host = '127.0.0.1'
    game_port = 9999       # game (player) connections port
    spectator_port = 10000 # spectator (GUI) connection port
    stats = {"bytes_read": 0, "bytes_written": 0}
    board_setup = "Setup Wa2 Wb2 Wc2 Wd2 We2 Wf2 Wg2 Wh2 Ba7 Bb7 Bc7 Bd7 Be7 Bf7 Bg7 Bh7"
    starting_side = "White"  # default (not used actively here)
    time_value = 30         # default time in minutes

    # --- Game Server: Accept two player connections ---
    game_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    game_sock.bind((host, game_port))
    game_sock.listen(5)
    print(f"Game server listening on {host}:{game_port}")
    
    print("Waiting for game connection 1...")
    conn1, addr1 = game_sock.accept()
    print("Game connection 1 from", addr1)
    
    print("Waiting for game connection 2...")
    while True:
        try:
            conn2, addr2 = game_sock.accept()
            print("Game connection 2 from", addr2)
            break
        except socket.timeout:
            print("Still waiting for game connection 2...")
    
    # Set up file wrappers and local stats for each player.
    s_file1 = conn1.makefile("r")
    s_file2 = conn2.makefile("r")
    stats1 = stats.copy()
    stats2 = stats.copy()
    
    # --- Perform handshake with game players ---
    send_msg(conn1, "Connected to the server!", stats1)
    send_msg(conn2, "Connected to the server!", stats2)
    recv_msg(s_file1, stats1)  # Expect an "OK"
    recv_msg(s_file2, stats2)
    
    # Send board setup.
    send_msg(conn1, board_setup, stats1)
    send_msg(conn2, board_setup, stats2)
    recv_msg(s_file1, stats1)
    recv_msg(s_file2, stats2)
    
    # Send time message.
    time_msg = f"Time {time_value}"
    send_msg(conn1, time_msg, stats1)
    send_msg(conn2, time_msg, stats2)
    recv_msg(s_file1, stats1)
    recv_msg(s_file2, stats2)
    
    # Send begin message (role assignments are not really used here)
    send_msg(conn1, "BEGIN", stats1)
    send_msg(conn2, "BEGIN", stats2)
    send_msg(conn1, "Role White", stats1)
    send_msg(conn2, "Role Black", stats2)
    print("Game started with roles assigned.")

    # --- Spectator Listener ---
    spec_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    spec_sock.bind((host, spectator_port))
    spec_sock.listen(1)
    spec_sock.settimeout(0.1)  # non-blocking accept
    spectator_conn = None
    print(f"Spectator server listening on {host}:{spectator_port} (for GUI connection)")

    # --- Game loop: forward moves from one player to the other and to spectator ---
    while True:
        # Check if a spectator is waiting and accept if needed.
        if spectator_conn is None:
            try:
                sp_conn, sp_addr = spec_sock.accept()
                spectator_conn = sp_conn
                print("Spectator connected from", sp_addr)
            except socket.timeout:
                pass
        
        # Wait for a move from either game connection.
        ready, _, _ = select.select([conn1, conn2], [], [], 0.1)
        for r in ready:
            if r == conn1:
                msg = recv_msg(s_file1, stats1)
                print("Received from conn1:", msg)
                if msg.lower() == "exit" or msg.startswith("win:"):
                    send_msg(conn2, msg, stats2)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
                        spectator_conn.close()
                    conn1.close()
                    conn2.close()
                    print("Game over.")
                    return
                else:
                    send_msg(conn2, msg, stats2)
                    # Forward move to spectator, if connected.
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
            elif r == conn2:
                msg = recv_msg(s_file2, stats2)
                print("Received from conn2:", msg)
                if msg.lower() == "exit" or msg.startswith("win:"):
                    send_msg(conn1, msg, stats1)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
                        spectator_conn.close()
                    conn1.close()
                    conn2.close()
                    print("Game over.")
                    return
                else:
                    send_msg(conn1, msg, stats1)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)

if __name__ == "__main__":
    # Start the server (game and spectator handling) in a separate daemon thread.
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Now start the GUI automatically. This GUI can be used as your spectator/human client.
    root = tk.Tk()
    gui = PawnChessGUI(root)
    root.mainloop() 