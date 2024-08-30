"""TCP Server with SSL support, binary search functionality, and robust error handling.

This module implements a TCP server that can use SSL for secure communication
and performs binary search on a sorted file to find queried strings. It includes
comprehensive error handling for improved reliability and debugging.
"""
import threading
import time
import socket
from unittest.mock import patch, MagicMock
import pytest
from server import ServerConfig, TCPServer, ConfigError, FileError


@pytest.fixture
def server_config_fixture(tmp_path) -> ServerConfig:
    """
    Fixture for server configuration.

    Returns:
        ServerConfig: Configured server configuration object.
    """
    config_content = """
    [DEFAULT]
    linuxpath = ./200k.txt
    REREAD_ON_QUERY = false
    use_ssl = true
    """
    config_file = "config.ini"
    # config_file.write_text(config_content)
    return ServerConfig(config_file)


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


@pytest.fixture
def sample_data_file(tmp_path):
    """
    Fixture to create a sample data file for testing.
    """
    data = ["apple", "banana", "cherry", "date", "elderberry"]
    file_path = tmp_path / "./200k.txt"
    file_path.write_text("\n".join(data))
    return str(file_path)


def test_read_config(server_config_fixture: ServerConfig) -> None:
    """
    Test that the server configuration is read correctly.

    Args:
        server_config_fixture (ServerConfig): The server configuration object.
    """
    assert server_config_fixture.file_path == './200k.txt'
    assert server_config_fixture.reread_on_query is False
    assert server_config_fixture.use_ssl is True


def test_read_file(tcp_server_fixture: TCPServer, sample_data_file) -> None:
    """
    Test reading file content.

    Args:
        tcp_server_fixture (TCPServer): The initialized TCP server object.
        sample_data_file (str): Path to the sample data file.
    """
    tcp_server_fixture.config.file_path = sample_data_file
    content = tcp_server_fixture.read_file(tcp_server_fixture.config.file_path)
    assert isinstance(content, list)
    assert len(content) == 5
    assert content == ["apple", "banana", "cherry", "date", "elderberry"]


def test_cached_file_content(tcp_server_fixture: TCPServer, sample_data_file) -> None:
    """
    Test that file content is cached correctly.

    Args:
        tcp_server_fixture (TCPServer): The initialized TCP server object.
        sample_data_file (str): Path to the sample data file.
    """
    tcp_server_fixture.config.file_path = sample_data_file
    tcp_server_fixture.file_content = None  # Reset cache
    cached_content = tcp_server_fixture.get_cached_file_content()
    assert tcp_server_fixture.file_content is not None
    assert cached_content == [
        "apple", "banana", "cherry", "date", "elderberry"]


def test_binary_search(tcp_server_fixture: TCPServer) -> None:
    """
    Test the binary search functionality.

    Args:
        tcp_server_fixture (TCPServer): The initialized TCP server object.
    """
    sorted_lines = ['alpha', 'beta', 'delta', 'epsilon', 'gamma']
    assert tcp_server_fixture.binary_search(sorted_lines, 'delta') is True
    assert tcp_server_fixture.binary_search(sorted_lines, 'zeta') is False
    assert tcp_server_fixture.binary_search(sorted_lines, 'alpha') is True
    assert tcp_server_fixture.binary_search(sorted_lines, 'gamma') is True
    assert tcp_server_fixture.binary_search(sorted_lines, 'omega') is False


@patch('ssl.create_default_context')
def test_ssl_wrap_socket(mock_create_context, tcp_server_fixture: TCPServer) -> None:
    """
    Test SSL wrapping of sockets.

    Args:
        mock_create_context: Mocked SSL context creation.
        tcp_server_fixture (TCPServer): The initialized TCP server object.
    """
    mock_context = MagicMock()
    mock_create_context.return_value = mock_context
    mock_wrapped_socket = MagicMock()
    mock_context.wrap_socket.return_value = mock_wrapped_socket

    tcp_server_fixture.config.use_ssl = True  # Enable SSL for the test
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        wrapped_socket = tcp_server_fixture.wrap_socket_with_ssl(client_socket)
        assert wrapped_socket == mock_wrapped_socket
        mock_context.load_cert_chain.assert_called_once_with(
            certfile='cert.pem', keyfile='key.pem')


def test_config_error_handling():
    """Test handling of configuration errors."""
    with pytest.raises(ConfigError):
        ServerConfig("non_existent_config.ini")


def test_file_error_handling(tcp_server_fixture: TCPServer):
    """Test handling of file-related errors."""
    tcp_server_fixture.config.file_path = "non_existent_file.txt"
    with pytest.raises(FileError):
        tcp_server_fixture.read_file(tcp_server_fixture.config.file_path)


def test_server_shutdown(tcp_server_fixture: TCPServer):
    """Test server shutdown process."""
    def run_server():
        tcp_server_fixture.start()

    server_thread = threading.Thread(target=run_server)
    server_thread.start()

    time.sleep(1)  # Give the server time to start

    tcp_server_fixture.shutdown()
    server_thread.join(timeout=5)
    assert not server_thread.is_alive(), "Server thread should not be alive after shutdown"


def test_handle_client_with_invalid_data(tcp_server_fixture: TCPServer, sample_data_file):
    """Test handling of invalid data from client."""
    tcp_server_fixture.config.file_path = sample_data_file
    mock_socket = MagicMock()
    # Send invalid data, then simulate connection close
    mock_socket.recv.side_effect = [b'invalid\n', b'']

    tcp_server_fixture.handle_client(mock_socket)

    mock_socket.sendall.assert_called_once_with(b'STRING NOT FOUND\n')
    mock_socket.close.assert_called_once()
