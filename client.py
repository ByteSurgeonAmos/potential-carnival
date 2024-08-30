"""
A robust client for testing a TCP server with optional SSL support.

This script connects to a server, sends a query, and reports the response and query time.
It includes comprehensive error handling and follows best practices for Python coding.
"""

import socket
import ssl
import time
import argparse
import sys
from typing import Union, Tuple


class CustomConnectionError(Exception):
    """Custom exception for connection-related errors."""


def create_ssl_socket(server_address: str, server_port: int) -> ssl.SSLSocket:
    """
    Create an SSL socket to connect to the server securely.

    Args:
        server_address (str): The server's address.
        server_port (int): The server's port number.

    Returns:
        ssl.SSLSocket: A connected SSL socket.

    Raises:
        CustomConnectionError: If unable to create or connect the SSL socket.
        ssl.SSLError: If an SSL-specific error occurs.
    """
    try:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.load_verify_locations('cert.pem')
        plain_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssl_socket = context.wrap_socket(
            plain_socket, server_hostname=server_address)
        ssl_socket.connect((server_address, server_port))
        return ssl_socket
    except ssl.SSLError as e:
        raise ssl.SSLError(f"SSL error occurred: {e}") from e
    except (socket.error, OSError) as e:
        raise CustomConnectionError(
            f"Failed to create or connect SSL socket: {e}") from e


def create_plain_socket(server_address: str, server_port: int) -> socket.socket:
    """
    Create a plain socket to connect to the server without SSL.

    Args:
        server_address (str): The server's address.
        server_port (int): The server's port number.

    Returns:
        socket.socket: A connected plain socket.

    Raises:
        CustomConnectionError: If unable to create or connect the socket.
    """
    try:
        plain_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        plain_socket.connect((server_address, server_port))
        return plain_socket
    except (socket.error, OSError) as e:
        raise CustomConnectionError(
            f"Failed to create or connect plain socket: {e}") from e


def connect_to_server(use_ssl: bool, server_address: str, server_port: int) -> Union[ssl.SSLSocket, socket.socket]:
    """
    Connect to the server using either an SSL or a plain socket.

    Args:
        use_ssl (bool): Whether to use SSL for the connection.
        server_address (str): The server's address.
        server_port (int): The server's port number.

    Returns:
        Union[ssl.SSLSocket, socket.socket]: A connected socket (SSL or plain).

    Raises:
        CustomConnectionError: If unable to connect to the server.
    """
    try:
        return create_ssl_socket(server_address, server_port) if use_ssl else create_plain_socket(server_address, server_port)
    except (CustomConnectionError, ssl.SSLError) as e:
        raise CustomConnectionError(f"Failed to connect to server: {e}") from e


def send_query(sock: Union[ssl.SSLSocket, socket.socket], query: str) -> str:
    """
    Send a query to the server and return the response.

    Args:
        sock (Union[ssl.SSLSocket, socket.socket]): The connected socket.
        query (str): The query string to send.

    Returns:
        str: The server's response.

    Raises:
        CustomConnectionError: If unable to send or receive data.
    """
    try:
        sock.sendall(query.encode('utf-8'))
        response = sock.recv(1024).decode('utf-8')
        if not response:
            raise CustomConnectionError("Server closed the connection")
        return response
    except (socket.error, OSError) as e:
        raise CustomConnectionError(
            f"Error during communication with server: {e}") from e


def execute_query(sock: Union[ssl.SSLSocket, socket.socket], query: str) -> Tuple[str, float]:
    """
    Execute a query and measure the time taken.

    Args:
        sock (Union[ssl.SSLSocket, socket.socket]): The connected socket.
        query (str): The query string to send.

    Returns:
        Tuple[str, float]: A tuple containing the response and the time taken.

    Raises:
        CustomConnectionError: If unable to send or receive data.
    """
    start_time = time.time()
    response = send_query(sock, query)
    end_time = time.time()
    return response, end_time - start_time


def main(server_address: str, server_port: int, use_ssl: bool, query: str) -> None:
    """
    Main function to run the client.

    Args:
        server_address (str): The server's address.
        server_port (int): The server's port number.
        use_ssl (bool): Whether to use SSL for the connection.
        query (str): The query string to send to the server.
    """
    sock = None
    try:
        print(f"[*] Connecting to server at {server_address}:{
              server_port} with SSL={'Yes' if use_ssl else 'No'}")
        sock = connect_to_server(use_ssl, server_address, server_port)

        print(f"[*] Sending query: {query}")
        response, duration = execute_query(sock, query)

        print(f"[*] Received response: {response.strip()}")
        print(f"[*] Query took {duration:.4f} seconds")

    except CustomConnectionError as e:
        print(f"Connection error: {e}", file=sys.stderr)
    except ssl.SSLError as e:
        print(f"SSL error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
    finally:
        if sock:
            try:
                sock.close()
            except (socket.error, OSError) as e:
                print(f"Error while closing socket: {e}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Client for testing the server")
    parser.add_argument("--server_address", type=str,
                        default="localhost", help="Server address to connect to")
    parser.add_argument("--server_port", type=int,
                        default=44445, help="Server port to connect to")
    parser.add_argument("--use_ssl", action="store_true",
                        help="Use SSL for the connection")
    parser.add_argument("--query", type=str, required=True,
                        help="The string to search for in the server's file")
    args = parser.parse_args()

    main(args.server_address, args.server_port, args.use_ssl, args.query)
