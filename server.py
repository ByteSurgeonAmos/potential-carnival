import socket  # Import socket module for network communication
import threading  # Import threading module to handle concurrent connections
import ssl  # Import ssl module for secure socket layer (SSL) communication
import configparser  # Import configparser to read configuration files
from typing import Tuple, List, Optional  # Import Tuple, List, Optional for type hinting

class ServerConfig:
    """
    Class to handle server configuration settings.
    """

    def __init__(self, config_path: str):
        self.file_path, self.reread_on_query, self.use_ssl = self.read_config(config_path)

    def read_config(self, config_path: str) -> Tuple[str, bool, bool]:
        """
        Read configuration settings from the config file.
        """
        config = configparser.ConfigParser()  # Create a ConfigParser object to handle the config file
        config.read(config_path)  # Read the configuration file at the given path
        linuxpath = config.get('DEFAULT', 'linuxpath')  # Get the file path for the text file to search in
        reread_on_query = config.getboolean('DEFAULT', 'REREAD_ON_QUERY')  # Get the boolean for whether to reread the file on each query
        use_ssl = config.getboolean('DEFAULT', 'use_ssl')  # Get the boolean for whether to use SSL for secure connections
        return linuxpath, reread_on_query, use_ssl  # Return the configuration values as a tuple

class TCPServer:
    """
    Class to manage the TCP server operations.
    """

    def __init__(self, config: ServerConfig):
        self.config = config  # Store server configuration
        self.file_content: Optional[List[str]] = None  # Initialize file content cache as None

    def start(self) -> None:
        """
        Start the TCP server to listen for incoming connections.
        """
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create a TCP/IP socket
        server_socket.bind(('0.0.0.0', 44445))  # Bind the socket to all network interfaces on port 44445
        server_socket.listen(5)  # Listen for incoming connections, with a backlog of 5 connections

        print("[*] Server listening on port 44445")  # Print a message indicating that the server is listening

        while True:  # Infinite loop to continuously accept client connections
            client_socket, addr = server_socket.accept()  # Accept a new client connection
            print(f"[*] Accepted connection from {addr}")  # Print the address of the connected client

            if self.config.use_ssl:  # Check if SSL is configured to be used
                client_socket = self._wrap_socket_with_ssl(client_socket)  # Wrap the client socket with SSL

            client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))  # Create a new thread to handle the client connection
            client_handler.start()  # Start the thread to handle client requests

    def _wrap_socket_with_ssl(self, client_socket: socket.socket) -> ssl.SSLSocket:
        """
        Wrap a socket with SSL for secure communication.
        """
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)  # Create a default SSL context for server-side SSL
        context.load_cert_chain(certfile='cert.pem', keyfile='key.pem')  # Load server certificate and private key for SSL
        return context.wrap_socket(client_socket, server_side=True)  # Wrap the socket with SSL and return it

    def handle_client(self, client_socket: socket.socket) -> None:
        """
        Handle each client connection, receiving data and sending responses.
        """
        try:
            while True:
                data = client_socket.recv(1024).decode('utf-8').strip()
                if not data:
                    break

                print(f"[*] Received query: {data}")

                try:
                    lines = self._read_file(self.config.file_path) if self.config.reread_on_query else self._get_cached_file_content()
                except FileNotFoundError:
                    print(f"[*] Error: File not found at {self.config.file_path}")
                    response = "ERROR: File not found\n"
                    client_socket.sendall(response.encode('utf-8'))
                    continue

                if self.binary_search(lines, data):  # Use binary search to find the data
                    response = "STRING EXISTS\n"
                else:
                    response = "STRING NOT FOUND\n"

                print(f"[*] Sending response: {response.strip()}")
                client_socket.sendall(response.encode('utf-8'))
        except ssl.SSLError as ssl_error:
            print(f"[*] SSL error occurred: {ssl_error}")
        except Exception as e:
            print(f"An error occurred while handling client: {e}")
        finally:
            client_socket.close()

    def _read_file(self, file_path: str) -> List[str]:
        """
        Read the contents of the file and return as a list of lines.
        """
        with open(file_path, 'r') as file:  # Open the file in read mode
            return file.read().splitlines()  # Read the file and split it into lines

    def _get_cached_file_content(self) -> List[str]:
        """
        Get cached file content or read it if not already cached.
        """
        if self.file_content is None:  # If file content is not cached
            self.file_content = sorted(self._read_file(self.config.file_path))  # Cache and sort the file content
        return self.file_content  # Return the cached and sorted file content

    def binary_search(self, sorted_lines: List[str], query: str) -> bool:
        """
        Perform binary search to determine if the query string exists in the sorted list.
        """
        low, high = 0, len(sorted_lines) - 1
        while low <= high:
            mid = (low + high) // 2
            if sorted_lines[mid] == query:
                return True
            elif sorted_lines[mid] < query:
                low = mid + 1
            else:
                high = mid - 1
        return False

if __name__ == "__main__":  # If this script is being run directly (not imported as a module)
    config = ServerConfig('config.ini')  # Create a ServerConfig object with the configuration file
    server = TCPServer(config)  # Create a TCPServer object with the configuration
    server.start()  # Start the server
