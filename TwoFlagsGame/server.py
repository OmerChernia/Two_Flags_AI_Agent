import socket
import select
import time
import threading
import tkinter as tk
from gui import PawnChessGUI

# Global board setup and starting side. These can be updated by the GUI.
board_setup = "Setup Wa2 Wb2 Wc2 Wd2 We2 Wf2 Wg2 Wh2 Ba7 Bb7 Bc7 Bd7 Be7 Bf7 Bg7 Bh7"
starting_side = "White"  # Default starting side.

def update_setup(new_setup, new_starting_side):
    """
    Update the global board setup and starting side.
    Called from the GUI if a custom board setup is used.
    """
    global board_setup, starting_side
    board_setup = new_setup
    starting_side = new_starting_side
    print("Server board setup updated:")
    print("Board Setup:", board_setup)
    print("Starting Side:", starting_side)

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
    time_value = 30         # default time in minutes

    # Create game server socket and enable address reuse.
    game_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    game_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow address reuse.
    game_sock.bind((host, game_port))
    game_sock.listen(5)
    print(f"Game server listening on {host}:{game_port}")

    print("Waiting for game connection 1...")
    conn1, addr1 = game_sock.accept()
    print("Game connection 1 from", addr1)
    s_file1 = conn1.makefile("r")

    # Check if a custom board setup is being sent.
    first_msg = recv_msg(s_file1, stats)
    if first_msg.startswith("Setup "):  # Custom board message detected.
        update_setup(first_msg, "White")  # For simplicity, we use White as the starting side.
        send_msg(conn1, "SETUP-ACK", stats)
        print("Custom board setup received from connection 1.")
    else:
        send_msg(conn1, "OK", stats)

    # --- Accept second player connection ---
    print("Waiting for game connection 2...")
    conn2, addr2 = game_sock.accept()
    print("Game connection 2 from", addr2)
    s_file2 = conn2.makefile("r")

    # --- Common Handshake for Both Players ---
    # Step A: Announce connection.
    send_msg(conn1, "Connected to the server!", stats)
    send_msg(conn2, "Connected to the server!", stats)
    recv_msg(s_file1, stats)  # Expecting "OK" from conn1.
    recv_msg(s_file2, stats)  # Expecting "OK" from conn2.

    # Step B: Send board setup (using the (possibly updated) global board_setup).
    send_msg(conn1, board_setup, stats)
    send_msg(conn2, board_setup, stats)
    recv_msg(s_file1, stats)  # Expecting "OK" after board setup.
    recv_msg(s_file2, stats)

    # Step C: Send time message.
    send_msg(conn1, str(time_value), stats)
    send_msg(conn2, str(time_value), stats)
    recv_msg(s_file1, stats)  # Expecting "OK" after time message.
    recv_msg(s_file2, stats)

    # Step D: Send BEGIN and role assignments.
    send_msg(conn1, "BEGIN", stats)
    send_msg(conn2, "BEGIN", stats)
    if starting_side == "White":
        role1, role2 = "White", "Black"
    else:
        role1, role2 = "Black", "White"
    send_msg(conn1, f"Role {role1}", stats)
    send_msg(conn2, f"Role {role2}", stats)

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
                msg = recv_msg(s_file1, stats)
                print("Received from conn1:", msg)
                if msg.lower() == "exit" or msg.startswith("win:"):
                    send_msg(conn2, msg, stats)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
                        spectator_conn.close()
                    conn1.close()
                    conn2.close()
                    print("Game over.")
                    return
                else:
                    send_msg(conn2, msg, stats)
                    # Forward move to spectator, if connected.
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
            elif r == conn2:
                msg = recv_msg(s_file2, stats)
                print("Received from conn2:", msg)
                if msg.lower() == "exit" or msg.startswith("win:"):
                    send_msg(conn1, msg, stats)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
                        spectator_conn.close()
                    conn1.close()
                    conn2.close()
                    print("Game over.")
                    return
                else:
                    send_msg(conn1, msg, stats)
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