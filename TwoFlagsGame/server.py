import socket
import select
import time
import threading
import tkinter as tk
from gui import PawnChessGUI

# Global default board setup.
default_setup = "Setup Wa2 Wb2 Wc2 Wd2 We2 Wf2 Wg2 Wh2 Ba7 Bb7 Bc7 Bd7 Be7 Bf7 Bg7 Bh7"
board_setup = default_setup
starting_side = "White"  # Define a default starting side

def update_setup(new_setup, side):
    """
    Update the global board setup and starting side.
    Called from the GUI if a custom board setup is used.
    """
    global board_setup, starting_side  # Important for updating module-level variables
    board_setup = new_setup
    starting_side = side
    print("Board setup updated to:", board_setup)

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
    spectator_port = 10000 # spectator (GUI) connection portGui
    stats = {"bytes_read": 0, "bytes_written": 0}
    time_value = 30         # default time in minutes

    # --- Spectator Listener Setup (bind first so spectator can connect early) ---
    spec_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    spec_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    spec_sock.bind((host, spectator_port))
    spec_sock.listen(1)
    spec_sock.settimeout(0.1)
    spectator_conn = None
    print(f"Spectator server listening on {host}:{spectator_port} (for GUI connection)")
    
    # Optionally wait a few seconds for a spectator to connect.
    start_wait = time.time()
    while time.time() - start_wait < 5:
        try:
            spectator_conn, sp_addr = spec_sock.accept()
            print("Spectator connected from", sp_addr)
            # Immediately send the initial board setup to the spectator.
            send_msg(spectator_conn, board_setup, stats)
            break
        except socket.timeout:
            pass
    if spectator_conn is None:
        print("No spectator connected before game start.")

    # --- Game Server Setup ---
    game_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    game_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    game_sock.bind((host, game_port))
    game_sock.listen(5)
    print(f"Game server listening on {host}:{game_port}")

    print("Waiting for game connection 1...")
    conn1, addr1 = game_sock.accept()
    print(f"Connection 1 from {addr1}")
    s_file1 = conn1.makefile("r")
    
    # 1) Send the greeting
    send_msg(conn1, "Connected to the server!", stats)

    # 2) Now read the client's first message (which may be "Setup ..." or "OK")
    first_msg = recv_msg(s_file1, stats)
    if first_msg.startswith("Setup "):
        update_setup(first_msg, "White")
        send_msg(conn1, "SETUP-ACK", stats)
        print("Custom board setup received from connection 1.")
    elif first_msg == "OK":
        print("Connection 1 acknowledged handshake without a custom setup.")
    else:
        print("Unexpected handshake message from connection 1:", first_msg)

    print("Waiting for game connection 2...")
    conn2, addr2 = game_sock.accept()
    print("Game connection 2 from", addr2)
    s_file2 = conn2.makefile("r")

    send_msg(conn2, "Connected to the server!", stats)
    # For the second connection:
    handshake_msg = recv_msg(s_file2, stats)
    if handshake_msg.startswith("Setup "):
        update_setup(handshake_msg, "Black")  # or whichever side you intend
        send_msg(conn2, "SETUP-ACK", stats)
        print("Custom board setup received from connection 2.")
    elif handshake_msg == "OK":
        print("Connection 2 acknowledged handshake without a custom setup.")
    else:
        print("Unexpected handshake message from connection 2:", handshake_msg)

    # --- Common Handshake for Both Players ---
    # (Board setup has already been updated if a custom message was sent.)
    send_msg(conn1, board_setup, stats)
    send_msg(conn2, board_setup, stats)
    recv_msg(s_file1, stats)  # Expecting "OK" after receiving board setup.
    recv_msg(s_file2, stats)
    
    send_msg(conn1, str(time_value), stats)
    send_msg(conn2, str(time_value), stats)
    recv_msg(s_file1, stats)
    recv_msg(s_file2, stats)
    
    send_msg(conn1, "BEGIN", stats)
    send_msg(conn2, "BEGIN", stats)
    if starting_side == "White":
        role1, role2 = "White", "Black"
    else:
        role1, role2 = "Black", "White"
    send_msg(conn1, f"Role {role1}", stats)
    send_msg(conn2, f"Role {role2}", stats)

    print("Game started with roles assigned.")

    # --- Game Loop: forward moves between players and to spectator ---
    while True:
        # Also check (again) if a spectator connection comes in (if not already connected).
        if spectator_conn is None:
            try:
                sp_conn, sp_addr = spec_sock.accept()
                spectator_conn = sp_conn
                print("Spectator connected from", sp_addr)
                send_msg(spectator_conn, board_setup, stats)
            except socket.timeout:
                pass

        ready, _, _ = select.select([conn1, conn2], [], [], 0.1)
        for r in ready:
            if r == conn1:
                msg = recv_msg(s_file1, stats)
                print("Received from conn1:", msg)
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
                    send_msg(conn2, msg, stats)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
            elif r == conn2:
                msg = recv_msg(s_file2, stats)
                print("Received from conn2:", msg)
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
                    send_msg(conn1, msg, stats)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)

def handle_client(conn, addr):
    global board_setup, starting_side  # Ensure we refer to the global variables.
    stats = {"bytes_read": 0, "bytes_written": 0}
    conn_file = conn.makefile('r')
    print(f"Game connection from {addr}")
    
    # --- Initial Handshake ---
    # Send greeting message.
    send_msg(conn, "Connected to the server!", stats)
    
    # Read the first message from the client.
    handshake = recv_msg(conn_file, stats)
    if handshake.startswith("Setup "):
        print("Received custom board setup from client: " + handshake)
        # Use the update function so that the custom board is locked in.
        update_setup(handshake, starting_side)
        send_msg(conn, "SETUP-ACK", stats)
    else:
        send_msg(conn, "OK", stats)
    
    # Now send the (possibly updated) board setup to the client.
    print("Sending board setup: " + board_setup)
    send_msg(conn, board_setup, stats)
    
    # Continue with the remaining handshake (time control, BEGIN, role assignment, etc.)
    send_msg(conn, "30", stats)      # For example, time control in seconds.
    send_msg(conn, "BEGIN", stats)   
    # --- End handshake, now enter game loop, etc. ---
    try:
        while True:
            msg = recv_msg(conn_file, stats)
            if not msg:
                break
            if msg.startswith("Setup "):
                print("Ignoring board setup message during game: " + msg)
                continue
            print("Processing move: " + msg)
            send_msg(conn, "OK", stats)
    except Exception as e:
        print("Error in game loop: " + str(e))
    finally:
        conn.close()
        print("Connection closed.")

if __name__ == "__main__":
    # Start the server (game and spectator handling) in a separate daemon thread.
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Now start the GUI automatically. This GUI can be used as your spectator/human client.
    root = tk.Tk()
    gui = PawnChessGUI(root)
    root.mainloop() 