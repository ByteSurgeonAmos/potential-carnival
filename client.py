import socket
import ssl
import time
import argparse

def create_ssl_socket(server_address: str, server_port: int) -> ssl.SSLSocket:
    """
    Create an SSL socket to connect to the server securely.
    """
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.load_verify_locations('cert.pem')  # Ensure to load the correct server certificate
    plain_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ssl_socket = context.wrap_socket(plain_socket, server_hostname=server_address)
    ssl_socket.connect((server_address, server_port))
    return ssl_socket

def create_plain_socket(server_address: str, server_port: int) -> socket.socket:
    """
    Create a plain socket to connect to the server without SSL.
    """
    plain_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    plain_socket.connect((server_address, server_port))
    return plain_socket

def connect_to_server(use_ssl: bool, server_address: str, server_port: int) -> socket.socket:
    """
    Connect to the server using either an SSL or a plain socket.
    """
    if use_ssl:
        return create_ssl_socket(server_address, server_port)
    else:
        return create_plain_socket(server_address, server_port)

def send_query(socket: socket.socket, query: str) -> str:
    """
    Send a query to the server and return the response.
    """
    socket.sendall(query.encode('utf-8'))  # Send the query to the server
    response = socket.recv(1024).decode('utf-8')  # Receive the server's response
    return response

def main(server_address: str, server_port: int, use_ssl: bool, query: str):
    """
    Main function to run the client.
    """
    try:
        print(f"[*] Connecting to server at {server_address}:{server_port} with SSL={'Yes' if use_ssl else 'No'}")
        client_socket = connect_to_server(use_ssl, server_address, server_port)  # Connect to the server

        print(f"[*] Sending query: {query}")
        start_time = time.time()  # Start timing the query
        response = send_query(client_socket, query)  # Send the query and get the response
        end_time = time.time()  # End timing the query

        print(f"[*] Received response: {response.strip()}")
        print(f"[*] Query took {end_time - start_time:.4f} seconds")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client_socket.close()  # Close the client socket

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client for testing the server")
    parser.add_argument("--server_address", type=str, default="localhost", help="Server address to connect to")
    parser.add_argument("--server_port", type=int, default=44445, help="Server port to connect to")
    parser.add_argument("--use_ssl", action="store_true", help="Use SSL for the connection")
    parser.add_argument("--query", type=str, required=True, help="The string to search for in the server's file")
    args = parser.parse_args()

    main(args.server_address, args.server_port, args.use_ssl, args.query)
