"""TCP Server with SSL support, binary search functionality, and robust error handling.

This module implements a TCP server that can use SSL for secure communication
and performs binary search on a sorted file to find queried strings. It includes
comprehensive error handling for improved reliability and debugging.
"""

import socket
import threading
import ssl
import configparser
import logging
from typing import Tuple, List, Optional
import sys
import time

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Custom exception for configuration-related errors."""


class FileError(Exception):
    """Custom exception for file-related errors."""


class ServerError(Exception):
    """Custom exception for server-related errors."""


class ServerConfig:
    """Handle server configuration settings."""

    def __init__(self, config_path: str):
        try:
            self.file_path, self.reread_on_query, self.use_ssl = self._read_config(
                config_path)
        except configparser.Error as e:
            raise ConfigError(f"Failed to read configuration: {e}") from e

    def _read_config(self, config_path: str) -> Tuple[str, bool, bool]:
        """Read configuration settings from the config file."""
        config = configparser.ConfigParser()
        config.read(config_path)
        try:
            return (
                config.get('DEFAULT', 'linuxpath'),
                config.getboolean('DEFAULT', 'REREAD_ON_QUERY'),
                config.getboolean('DEFAULT', 'use_ssl')
            )
        except configparser.NoSectionError as e:
            raise ConfigError(
                "Missing 'DEFAULT' section in config file") from e
        except configparser.NoOptionError as e:
            raise ConfigError(f"Missing option in config file: {e}") from e


class TCPServer:
    """Manage TCP server operations."""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.file_content: Optional[List[str]] = None
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.stop_event = threading.Event()  # Event to signal the server to stop
        self.client_threads = []  # List to keep track of client threads

    def shutdown(self) -> None:
        """Shutdown the server by closing the listening socket and terminating active connections."""
        self.running = False
        self.stop_event.set()
        if self.server_socket:
            self.server_socket.close()

        # Wait for all client threads to finish
        for thread in self.client_threads:
            thread.join()

        logger.info("Server shutdown successfully.")

    def start(self) -> None:
        """Start the TCP server to listen for incoming connections."""
        self.running = True
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                self.server_socket = server_socket  # Keep a reference for shutting down
                server_socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('0.0.0.0', 44445))
                server_socket.listen(5)
                logger.info("[*] Server listening on port 44445")

                while self.running:
                    try:
                        # Set a timeout for accept()
                        server_socket.settimeout(1.0)
                        try:
                            client_socket, addr = server_socket.accept()
                        except socket.timeout:
                            continue  # No connection received, check if we should keep running

                        logger.info("[*] Accepted connection from %s", addr)

                        if self.config.use_ssl:
                            try:
                                client_socket = self.wrap_socket_with_ssl(
                                    client_socket)
                            except ssl.SSLError as ssl_error:
                                logger.error("SSL error occurred: %s",
                                             ssl_error, exc_info=True)
                                client_socket.close()
                                continue

                        client_handler = threading.Thread(
                            target=self.handle_client,
                            args=(client_socket,)
                        )
                        self.client_threads.append(client_handler)
                        client_handler.start()
                    except socket.error as e:
                        if not self.running:
                            break  # Exit if server is shutting down
                        logger.error("Error accepting connection: %s",
                                     e, exc_info=True)
        except socket.error as e:
            raise ServerError("Failed to start server") from e

    def close(self) -> None:
        """Close the server and stop accepting new connections."""
        self.stop_event.set()
        if self.server_socket:
            self.server_socket.close()
            logger.info("[*] Server socket closed")

    def wrap_socket_with_ssl(self, client_socket: socket.socket) -> ssl.SSLSocket:
        """Wrap a socket with SSL for secure communication."""
        try:
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(certfile='cert.pem', keyfile='key.pem')
            return context.wrap_socket(client_socket, server_side=True)
        except (ssl.SSLError, FileNotFoundError) as e:
            raise ServerError("Failed to wrap socket with SSL") from e

    def handle_client(self, client_socket: socket.socket) -> None:
        """Handle each client connection, receiving data and sending responses."""
        client_address = client_socket.getpeername()
        try:
            while not self.stop_event.is_set():
                try:
                    client_socket.settimeout(1.0)  # Set a timeout for recv()
                    try:
                        data = client_socket.recv(1024).decode('utf-8').strip()
                    except socket.timeout:
                        continue  # No data received, check if we should keep running

                    if not data:
                        logger.info(
                            "[*] No data received from %s, closing connection", client_address)
                        break

                    logger.info("[*] Received query from %s: %s",
                                client_address, data)

                    try:
                        lines = (
                            self.read_file(self.config.file_path)
                            if self.config.reread_on_query
                            else self.get_cached_file_content()
                        )
                    except FileError as e:
                        logger.error("File error: %s", e, exc_info=True)
                        response = f"ERROR: {str(e)}\n"
                        client_socket.sendall(response.encode('utf-8'))
                        continue

                    response = (
                        "STRING EXISTS\n"
                        if self.binary_search(lines, data)
                        else "STRING NOT FOUND\n"
                    )

                    logger.info("[*] Sending response to %s: %s",
                                client_address, response.strip())
                    client_socket.sendall(response.encode('utf-8'))
                except (socket.error, UnicodeDecodeError) as e:
                    logger.error("Error communicating with client %s: %s",
                                 client_address, e, exc_info=True)
                    break
        except Exception as e:
            logger.error("Unexpected error handling client %s: %s",
                         client_address, e, exc_info=True)
        finally:
            client_socket.close()
            logger.info("[*] Closed connection from %s", client_address)

    def read_file(self, file_path: str) -> List[str]:
        """Read the contents of the file and return as a list of lines."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().splitlines()
        except FileNotFoundError as exc:
            raise FileError("File not found: %s" % file_path) from exc
        except IOError as e:
            raise FileError("Error reading file %s: %s" %
                            (file_path, e)) from e

    def get_cached_file_content(self) -> List[str]:
        """Get cached file content or read it if not already cached."""
        if self.file_content is None:
            try:
                self.file_content = sorted(
                    self.read_file(self.config.file_path))
            except FileError as e:
                logger.error("Error caching file content: %s",
                             e, exc_info=True)
                raise
        return self.file_content

    def binary_search(self, sorted_lines: List[str], query: str) -> bool:
        """Perform binary search to determine if the query string exists in the sorted list."""
        low, high = 0, len(sorted_lines) - 1
        while low <= high:
            mid = (low + high) // 2
            if sorted_lines[mid] == query:
                return True
            if sorted_lines[mid] < query:
                low = mid + 1
            else:
                high = mid - 1
        return False


def main():
    """Main function to set up and run the server."""
    try:
        config = ServerConfig('config.ini')
        server = TCPServer(config)
        server_thread = threading.Thread(target=server.start)
        server_thread.start()

        # Keep the main thread running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down the server...")
            server.shutdown()
            server_thread.join()
            print("Server shut down successfully.")
    except ConfigError as e:
        logger.critical("Configuration error: %s", e, exc_info=True)
        sys.exit(1)
    except ServerError as e:
        logger.critical("Server error: %s", e, exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.critical("Unexpected error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
