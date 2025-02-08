import socket

HOST = '127.0.0.1'
PORT = 9999

def start_client():
    """
    Connect to the server at 127.0.0.1:9999.
    Once connected, you will see an initial handshake message,
    then you can send messages from the console.
    Later, replace console input with your game logic and protocol handling.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print("Connected to server!")

        # Wait for the handshake from the server (or any protocol-start message)
        handshake = s.recv(1024).decode()
        print(f"Server says: {handshake}")

        while True:
            msg = input("Enter message (or 'exit' to quit): ").strip()
            if msg.lower() == "exit":
                break

            try:
                s.sendall(msg.encode())
                data = s.recv(1024)
                if not data:
                    print("Server closed the connection.")
                    break
                print("Received:", data.decode())
            except Exception as e:
                print("Communication error:", e)
                break

if __name__ == "__main__":
    start_client() 