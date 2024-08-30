"""
Unit tests for the TCP server.

This module contains unit tests for the TCP server implemented in the `server` module.
Tests include:
- Verification of server configuration reading.
- File content reading and caching.
- Binary search functionality.
- SSL socket wrapping.
- Server startup and connection acceptance.

These tests use pytest fixtures to initialize the server configuration and TCP server.
"""

import threading
import time
import socket
import ssl
import pytest
from server import ServerConfig, TCPServer, ServerError


@pytest.fixture
def server_config_fixture() -> ServerConfig:
    """
    Fixture for server configuration.

    Returns:
        ServerConfig: Configured server configuration object.
    """
    config_path = 'config.ini'
    # Create a mock or a temporary configuration file if needed
    return ServerConfig(config_path)


@pytest.fixture
def tcp_server_fixture(server_config_fixture: ServerConfig) -> TCPServer:
    """
    Fixture for initializing the TCP server.

    Args:
        server_config_fixture (ServerConfig): The server configuration object.

    Returns:
        TCPServer: Initialized TCP server object.
    """
    return TCPServer(server_config_fixture)


def test_read_config(server_config_fixture: ServerConfig) -> None:
    """
    Test that the server configuration is read correctly.

    Args:
        server_config_fixture (ServerConfig): The server configuration object.
    """
    assert server_config_fixture.file_path == './200k.txt'
    assert server_config_fixture.reread_on_query is False
    assert server_config_fixture.use_ssl is True


def test_read_file(tcp_server_fixture: TCPServer) -> None:
    """
    Test reading file content.

    Args:
        tcp_server_fixture (TCPServer): The initialized TCP server object.
    """
    tcp_server_fixture.file_content = None  # Reset cache
    # Ensure 'file_path' points to a valid temporary or mock file
    content = tcp_server_fixture.read_file(tcp_server_fixture.config.file_path)
    assert isinstance(content, list)
    assert len(content) > 0  # Assuming the file is not empty


def test_cached_file_content(tcp_server_fixture: TCPServer) -> None:
    """
    Test that file content is cached correctly.

    Args:
        tcp_server_fixture (TCPServer): The initialized TCP server object.
    """
    tcp_server_fixture.file_content = None  # Reset cache
    # Ensure 'file_path' points to a valid temporary or mock file
    tcp_server_fixture.read_file(tcp_server_fixture.config.file_path)
    cached_content = tcp_server_fixture.get_cached_file_content()
    assert tcp_server_fixture.file_content is not None
    assert cached_content == tcp_server_fixture.file_content


def test_binary_search(tcp_server_fixture: TCPServer) -> None:
    """
    Test the binary search functionality.

    Args:
        tcp_server_fixture (TCPServer): The initialized TCP server object.
    """
    sorted_lines = ['alpha', 'beta', 'delta', 'epsilon', 'gamma']
    assert tcp_server_fixture.binary_search(sorted_lines, 'delta') is True
    assert tcp_server_fixture.binary_search(sorted_lines, 'zeta') is False


def test_ssl_wrap_socket(tcp_server_fixture: TCPServer) -> None:
    """
    Test SSL wrapping of sockets.

    Args:
        tcp_server_fixture (TCPServer): The initialized TCP server object.
    """
    tcp_server_fixture.config.use_ssl = True  # Enable SSL for the test
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        try:
            wrapped_socket = tcp_server_fixture.wrap_socket_with_ssl(
                client_socket)
            assert isinstance(wrapped_socket, ssl.SSLSocket)
        except ServerError as e:
            pytest.fail(f"SSL wrapping failed: {e}")


def test_server_start_and_accept(tcp_server_fixture: TCPServer) -> None:
    """
    Test starting the server, accepting connections, and graceful shutdown.

    Args:
        tcp_server_fixture (TCPServer): The initialized TCP server object.
    """
    tcp_server_fixture.config.use_ssl = False  # Disable SSL for simplicity in this test

    def run_server():
        tcp_server_fixture.start()

    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True  # Set as daemon thread for automatic termination
    server_thread.start()

    def connect_with_retry(host, port, retries=5, delay=1):
        """
        Attempt to connect to the server with a retry mechanism.

        Args:
            host (str): The server hostname.
            port (int): The server port number.
            retries (int): Number of retries.
            delay (int): Delay between retries in seconds.

        Returns:
            socket: A connected socket object.

        Raises:
            pytest.fail: If connection fails after all retries.
        """
        last_exception = None
        for _ in range(retries):
            try:
                sock = socket.create_connection((host, port), timeout=5)
                return sock
            except socket.error as e:
                last_exception = e
                time.sleep(delay)  # Wait before retrying
        pytest.fail(f"Unable to connect to the server after {
                    retries} attempts: {last_exception}")

    try:
        # Try to connect with retry logic
        client_socket = connect_with_retry('localhost', 44445)

        # Test multiple queries
        for _ in range(3):
            client_socket.sendall(b"test_query\n")
            response = client_socket.recv(1024)
            assert response in (b"STRING EXISTS\n", b"STRING NOT FOUND\n")

        # Close the client socket
        client_socket.close()
    except socket.error as e:
        pytest.fail(f"Socket error occurred: {e}")
    finally:
        # Signal the server to shut down
        tcp_server_fixture.shutdown()

        # Wait for the server thread to finish
        server_thread.join(timeout=5)
        if server_thread.is_alive():
            pytest.fail("Server did not shut down properly")
