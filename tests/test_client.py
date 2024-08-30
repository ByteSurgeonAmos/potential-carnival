"""
Unit tests for the client module.

This module contains a series of unit tests for testing the functionality of 
the `client.py` script, which is a robust TCP client with optional SSL support.
The tests cover the following functionalities:

1. **SSL and Plain Socket Creation**:
   - `test_create_ssl_socket` verifies SSL socket creation and secure connection 
     to the server using a mock SSL context.
   - `test_create_plain_socket` checks the creation of a plain socket and 
     connection to the server without SSL.

2. **Server Connection**:
   - `test_connect_to_server` tests the connection logic to ensure it correctly 
     uses SSL or plain sockets based on the user's choice.

3. **Query Handling**:
   - `test_send_query` confirms that queries are sent correctly and responses 
     are received from the server.
   - `test_execute_query` measures the time taken to execute a query and receive 
     a response from the server.

4. **Error Handling**:
   - `test_custom_connection_error` checks that custom connection errors are 
     raised and handled properly.
   - `test_create_ssl_socket_error` and `test_create_plain_socket_error` ensure 
     the module raises appropriate exceptions when socket creation fails.
   - `test_send_query_error` validates the error handling when sending a query 
     fails.

This test suite uses `pytest` for testing and mocking, providing a robust 
framework for ensuring the reliability and correctness of the client module's 
functions.
"""

from unittest.mock import patch, MagicMock
import socket
import ssl
import pytest
from client import (
    create_ssl_socket,
    create_plain_socket,
    connect_to_server,
    send_query,
    execute_query,
    CustomConnectionError,
)


@pytest.fixture
def mock_socket():
    """Fixture to create a mock socket."""
    return MagicMock(spec=socket.socket)


@pytest.fixture
def mock_ssl_context():
    """Fixture to create a mock SSL context."""
    context = MagicMock()
    context.wrap_socket.return_value = MagicMock(spec=ssl.SSLSocket)
    return context


def test_create_ssl_socket(mock_socket, mock_ssl_context):
    """Test SSL socket creation and connection."""
    with patch('socket.socket', return_value=mock_socket), \
            patch('ssl.create_default_context', return_value=mock_ssl_context):
        result = create_ssl_socket('example.com', 443)

    assert result == mock_ssl_context.wrap_socket.return_value
    mock_ssl_context.load_verify_locations.assert_called_once_with('cert.pem')
    mock_ssl_context.wrap_socket.assert_called_once()
    result.connect.assert_called_once_with(('example.com', 443))


def test_create_plain_socket(mock_socket):
    """Test plain socket creation and connection."""
    with patch('socket.socket', return_value=mock_socket):
        result = create_plain_socket('example.com', 80)

    assert result == mock_socket
    mock_socket.connect.assert_called_once_with(('example.com', 80))


@pytest.mark.parametrize("use_ssl,expected_function", [
    (True, 'client.create_ssl_socket'),
    (False, 'client.create_plain_socket')
])
def test_connect_to_server(use_ssl, expected_function):
    """Test connecting to server with SSL and without SSL."""
    with patch(expected_function, return_value=MagicMock()) as mock_func:
        result = connect_to_server(use_ssl, 'example.com', 443)

    assert result == mock_func.return_value
    mock_func.assert_called_once_with('example.com', 443)


def test_send_query(mock_socket):
    """Test sending a query to the server and receiving a response."""
    mock_socket.recv.return_value = b'Server response'

    result = send_query(mock_socket, 'Test query')

    assert result == 'Server response'
    mock_socket.sendall.assert_called_once_with(b'Test query')
    mock_socket.recv.assert_called_once_with(1024)


def test_execute_query(mock_socket):
    """Test executing a query and measuring the time taken."""
    mock_socket.recv.return_value = b'Server response'

    with patch('time.time', side_effect=[0, 1]):  # Simulate 1 second elapsed
        response, duration = execute_query(mock_socket, 'Test query')

    assert response == 'Server response'
    assert duration == 1.0
    mock_socket.sendall.assert_called_once_with(b'Test query')
    mock_socket.recv.assert_called_once_with(1024)


def test_custom_connection_error():
    """Test custom connection error handling."""
    with pytest.raises(CustomConnectionError, match="Test error"):
        raise CustomConnectionError("Test error")


def test_create_ssl_socket_error():
    """Test error handling when SSL socket creation fails."""
    with patch('socket.socket', side_effect=socket.error("Test error")):
        with pytest.raises(CustomConnectionError, match="Failed to create or connect SSL socket"):
            create_ssl_socket('example.com', 443)


def test_create_plain_socket_error():
    """Test error handling when plain socket creation fails."""
    with patch('socket.socket', side_effect=OSError("Test error")):
        with pytest.raises(CustomConnectionError, match="Failed to create or connect plain socket"):
            create_plain_socket('example.com', 80)


def test_send_query_error(mock_socket):
    """Test error handling when sending a query fails."""
    mock_socket.sendall.side_effect = socket.error("Test error")

    with pytest.raises(CustomConnectionError, match="Error during communication with server"):
        send_query(mock_socket, 'Test query')
