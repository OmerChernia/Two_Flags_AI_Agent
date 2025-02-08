import socket
import threading

HOST = '127.0.0.1'
PORT = 9999

def handle_client(conn, addr, client_id, other_client_conn):
    """
    Handle communication with an individual client.
    
    For now, this function simply prints incoming data and echoes it back.
    Later, you'll integrate your defined protocol for the Two Flags game.
    """
    print(f"Client {client_id} connected from {addr}")
    try:
        # This is a placeholder loop for receiving and echoing messages.
        while True:
            data = conn.recv(1024)
            if not data:
                break

            message = data.decode().strip()
            print(f"Received from Client {client_id}: {message}")
            
            # Example: relay the message to the other client.
            # (In your game protocol, you'll likely have more structured messaging.)
            if other_client_conn:
                try:
                    other_client_conn.sendall(data)
                except Exception as e:
                    print(f"Failed to send data to the other client: {e}")
            else:
                # Otherwise, echo back to the same client
                conn.sendall(data)
    except Exception as e:
        print(f"Error with Client {client_id}: {e}")
    finally:
        conn.close()
        print(f"Client {client_id} disconnected.")

def start_server():
    """
    Start the server to listen for two client connections.
    Once two clients have connected, initiate threads to handle
    client communication according to your protocol.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")
        
        clients = []
        # Accept exactly two connections:
        while len(clients) < 2:
            conn, addr = s.accept()
            clients.append((conn, addr))
            print(f"Accepted connection {len(clients)} from {addr}")
        
        # Extract connections for clarity
        conn1, addr1 = clients[0]
        conn2, addr2 = clients[1]

        # Optionally, send an initial handshake message to both clients (for your protocol)
        handshake_message = "HANDSHAKE_READY".encode()
        conn1.sendall(handshake_message)
        conn2.sendall(handshake_message)

        # Create threads for each client; pass the "other client" connection for relaying messages.
        t1 = threading.Thread(target=handle_client, args=(conn1, addr1, 1, conn2))
        t2 = threading.Thread(target=handle_client, args=(conn2, addr2, 2, conn1))
        
        t1.start()
        t2.start()
        
        # Optionally, join the threads if you want the server to wait until both disconnect.
        t1.join()
        t2.join()

if __name__ == "__main__":
    start_server() 