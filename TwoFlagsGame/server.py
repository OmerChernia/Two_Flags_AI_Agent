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

    # --- Spectator Listener Setup (bind first so spectator can connect early) ---
    spec_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    spec_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    spec_sock.bind((host, spectator_port))
    spec_sock.listen(1)
    spec_sock.settimeout(0.1)
    spectator_conn = None
    spectator_file = None
    print(f"Spectator server listening on {host}:{spectator_port} (for GUI connection)")
    
    # Optionally wait a few seconds for a spectator to connect.
    start_wait = time.time()
    while time.time() - start_wait < 5:
        try:
            spectator_conn, sp_addr = spec_sock.accept()
            print("Spectator connected from", sp_addr)
            spectator_conn.sendall((board_setup + "\n").encode())
            # Wrap the spectator connection with a file-like object to read commands.
            spectator_file = spectator_conn.makefile("r")
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
    print("Game connection 1 from", addr1)
    s_file1 = conn1.makefile("r")
    
    # Check if a custom board setup is being sent from connection 1.
    import select
    ready, _, _ = select.select([conn1], [], [], 0.5)
    if ready:
        first_msg = recv_msg(s_file1, stats)
    else:
        first_msg = ""
    if first_msg.startswith("Setup "):
        update_setup(first_msg, "White")
        send_msg(conn1, "SETUP-ACK", stats)
        print("Custom board setup received from connection 1.")
    # If no custom setup is provided, do nothing.

    print("Waiting for game connection 2...")
    conn2, addr2 = game_sock.accept()
    print("Game connection 2 from", addr2)
    s_file2 = conn2.makefile("r")

    # --- Common Handshake for Both Players ---
    send_msg(conn1, "Connected to the server!", stats)
    send_msg(conn2, "Connected to the server!", stats)
    recv_msg(s_file1, stats)  # Expecting "OK" from conn1.
    recv_msg(s_file2, stats)  # Expecting "OK" from conn2.

    send_msg(conn1, board_setup, stats)
    send_msg(conn2, board_setup, stats)
    # (Spectator already received board_setup upon connection.)
    recv_msg(s_file1, stats)  # Expecting "OK" after board setup.
    recv_msg(s_file2, stats)

    send_msg(conn1, str(time_value), stats)
    send_msg(conn2, str(time_value), stats)
    recv_msg(s_file1, stats)  # Expecting "OK" after time message.
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

    # --- Game Loop: forward messages and wait for replay requests ---
    while True:
        # Also check if a new spectator connects.
        if spectator_conn is None:
            try:
                spectator_conn, sp_addr = spec_sock.accept()
                print("Spectator connected from", sp_addr)
                send_msg(spectator_conn, board_setup, stats)
                spectator_file = spectator_conn.makefile("r")
            except socket.timeout:
                pass

        # Include game connections and spectator_file in the select list.
        sources = [conn1, conn2]
        if spectator_file is not None:
            sources.append(spectator_file)
        ready, _, _ = select.select(sources, [], [], 0.1)
        game_over = False
        win_msg = ""
        for r in ready:
            if r == conn1:
                msg = recv_msg(s_file1, stats)
                print("Received from conn1:", msg)
                if msg.lower() == "exit":
                    send_msg(conn2, msg, stats)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
                    conn1.close()
                    conn2.close()
                    print("Game over due to exit.")
                    return
                if msg.startswith("win:"):
                    win_msg = msg
                    game_over = True
                    break
                else:
                    send_msg(conn2, msg, stats)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
            elif r == conn2:
                msg = recv_msg(s_file2, stats)
                print("Received from conn2:", msg)
                if msg.lower() == "exit":
                    send_msg(conn1, msg, stats)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
                    conn1.close()
                    conn2.close()
                    print("Game over due to exit.")
                    return
                if msg.startswith("win:"):
                    win_msg = msg
                    game_over = True
                    break
                else:
                    send_msg(conn1, msg, stats)
                    if spectator_conn:
                        send_msg(spectator_conn, msg, stats)
            elif r == spectator_file:
                # Read any commands from the spectator.
                spec_msg = recv_msg(spectator_file, stats)
                if spec_msg == "REPLAY":
                    print("Spectator requested replay.")
                    # If the game is not yet over, trigger game over.
                    if not game_over:
                        win_msg = "win: Replay requested"
                        game_over = True
                    break
        if game_over:
            # Broadcast the win/replay message to both game players.
            send_msg(conn1, win_msg, stats)
            send_msg(conn2, win_msg, stats)
            if spectator_conn:
                send_msg(spectator_conn, win_msg, stats)
            print("Game over:", win_msg)
            # Wait for a replay command (if not already received via the spectator file).
            if win_msg.startswith("win: Replay"):
                replay_received = True
            else:
                print("Waiting for replay request from spectator...")
                replay_received = False
                start_wait = time.time()
                while time.time() - start_wait < 30:
                    if spectator_file:
                        ready_spec, _, _ = select.select([spectator_file], [], [], 0.1)
                        if ready_spec:
                            replay_cmd = recv_msg(spectator_file, stats)
                            if replay_cmd == "REPLAY":
                                replay_received = True
                                break
                    time.sleep(0.1)
            if replay_received:
                print("Replay request received. Resetting game...")
                send_msg(conn1, board_setup, stats)
                send_msg(conn2, board_setup, stats)
                recv_msg(s_file1, stats)
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
                print("New game started.")
                continue
            else:
                if spectator_conn:
                    spectator_conn.close()
                conn1.close()
                conn2.close()
                print("No replay request received. Game session ended.")
                return

if __name__ == "__main__":
    # Start the server (game and spectator handling) in a separate daemon thread.
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Now start the GUI automatically. This GUI can be used as your spectator/human client.
    root = tk.Tk()
    gui = PawnChessGUI(root)
    root.mainloop() 