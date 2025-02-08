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
        # Step 5: Send "OK".
        send_msg(s, "OK", session_stats)

        # Step 6: Receive time message.
        msg = recv_msg(s, session_stats)
        print(f"Server says: {msg}")
        # Step 7: Send "OK".
        send_msg(s, "OK", session_stats)

        # Step 9: Receive "Begin".
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

        # -- Game loop based on role --
        if role == "White":
            print("You are White. You make the first move.")
            while True:
                my_move = input("Enter your move (or 'exit' to quit): ").strip()
                send_msg(s, my_move, session_stats)
                if my_move.lower() == "exit":
                    break
                # After playing, wait for Black's move.
                opp_move = recv_msg(s, session_stats)
                if opp_move.lower() == "exit":
                    print("Server has quit the session.")
                    break
                print("Opponent move:", opp_move)
        elif role == "Black":
            print("You are Black. Waiting for White's move.")
            while True:
                # Wait for White's move first.
                opp_move = recv_msg(s, session_stats)
                if opp_move.lower() == "exit":
                    print("Server has quit the session.")
                    break
                print("Opponent move:", opp_move)
                my_move = input("Enter your move (or 'exit' to quit): ").strip()
                send_msg(s, my_move, session_stats)
                if my_move.lower() == "exit":
                    break
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