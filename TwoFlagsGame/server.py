import socket
import select
import time

HOST = '127.0.0.1'
PORT = 9999

def send_msg(conn, msg, stats):
    full_msg = msg + "\n"
    data = full_msg.encode()
    conn.sendall(data)
    stats["bytes_written"] += len(data)

def recv_msg(conn, stats):
    data = conn.recv(1024)
    if not data:
        return ""
    stats["bytes_read"] += len(data)
    return data.decode().strip()

def perform_handshake(conn, role, stats):
    # Step 2: Send "Connected to the server!" and wait for "OK".
    send_msg(conn, "Connected to the server!", stats)
    print("Awaiting client response for initial handshake...")
    resp = recv_msg(conn, stats)
    print("Client response:", resp)
    if resp != "OK":
        print("Handshake failed at initial handshake.")
        return False

    # Step 4: Send board setup message.
    board_setup = "Setup Wa2 Wb2 Wc2 Wd2 We2 Wf2 Wg2 Wh2 Ba7 Bb7 Bc7 Bd7 Be7 Bf7 Bg7 Bh7"
    send_msg(conn, board_setup, stats)
    print("Awaiting client response for board setup...")
    resp = recv_msg(conn, stats)
    print("Client response:", resp)
    if resp != "OK":
        print("Handshake failed at board setup.")
        return False

    # Step 6: Send time message.
    time_msg = "Time 30"  # example: 30 minutes for the match.
    send_msg(conn, time_msg, stats)
    print("Awaiting client response for time message...")
    resp = recv_msg(conn, stats)
    print("Client response:", resp)
    if resp != "OK":
        print("Handshake failed at time message.")
        return False

    # Step 9: Send 'Begin' message.
    send_msg(conn, "Begin", stats)
    # Additionally, send role assignment
    send_msg(conn, f"Role {role}", stats)
    return True

def game_loop(conn_white, conn_black, stats, session_start):
    sockets = [conn_white, conn_black]
    while True:
        readable, _, _ = select.select(sockets, [], [])
        for s in readable:
            msg = recv_msg(s, stats)
            if msg == "":
                print("A client disconnected unexpectedly.")
                send_msg(conn_white, "exit", stats)
                send_msg(conn_black, "exit", stats)
                return
            sender_role = "White" if s == conn_white else "Black"
            if msg.lower() == "exit":
                print(f"{sender_role} client requested exit.")
                send_msg(conn_white, "exit", stats)
                send_msg(conn_black, "exit", stats)
                elapsed = int(time.time() - session_start)
                print("********Session ********")
                print(f"Bytes written: {stats['bytes_written']} Bytes read: {stats['bytes_read']}")
                print(f"Elapsed time: {elapsed} secs")
                print("Connection closed")
                return
            else:
                print(f"{sender_role} move: {msg}")
                # Relay the move to the opposing client.
                if s == conn_white:
                    send_msg(conn_black, msg, stats)
                else:
                    send_msg(conn_white, msg, stats)

def start_server():
    session_stats = {"bytes_read": 0, "bytes_written": 0}
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Enable reuse of the address to avoid the "Address already in use" error.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(2)
        print(f"Server listening on {HOST}:{PORT}")
        print("Waiting for two clients to connect...")

        # Accept two connections.
        conn1, addr1 = s.accept()
        print(f"Accepted connection 1 from {addr1}")
        conn2, addr2 = s.accept()
        print(f"Accepted connection 2 from {addr2}")

        session_start = time.time()

        # Perform handshake with client 1 (assign as White).
        if not perform_handshake(conn1, "White", session_stats):
            conn1.close()
            conn2.close()
            return
        # Perform handshake with client 2 (assign as Black).
        if not perform_handshake(conn2, "Black", session_stats):
            conn1.close()
            conn2.close()
            return

        print("Both clients have completed handshake. Starting game loop.")
        # Enter game loop.
        game_loop(conn1, conn2, session_stats, session_start)
        conn1.close()
        conn2.close()

if __name__ == "__main__":
    start_server() 