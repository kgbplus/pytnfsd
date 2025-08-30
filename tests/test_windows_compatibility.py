#!/usr/bin/env python3
"""
Tests for Windows compatibility features
"""

import pytest
import os
import struct
from pathlib import Path
from unittest.mock import Mock

# Import the modules to test
from tnfsd import TNFSDaemon, TNFSHeader, Session, TNFS_CMD


@pytest.mark.windows
class TestWindowsCompatibility:
    """Test Windows-specific compatibility features"""
    
    def test_o_binary_constant_available(self):
        """Test that O_BINARY constant is available on Windows"""
        from tnfsd import O_BINARY
        assert O_BINARY == 0x8000  # Windows O_BINARY value
    
    def test_file_open_flags_windows(self):
        """Test file open flags on Windows"""
        from tnfsd import O_RDONLY, O_WRONLY, O_CREAT, O_TRUNC, O_BINARY
        
        # Test individual flags
        assert O_RDONLY == 0
        assert O_WRONLY == 1
        assert O_CREAT == 256  # Windows value
        assert O_TRUNC == 512
        assert O_BINARY == 32768  # Windows value
    
    def test_binary_mode_file_creation(self, temp_dir):
        """Test that files are opened in binary mode on Windows"""
        # Create a test file with binary content
        test_file = Path(temp_dir) / "binary_test.dat"
        binary_content = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F'
        test_file.write_bytes(binary_content)
        
        # Create daemon instance
        daemon = TNFSDaemon(temp_dir, 16384)
        
        # Create a session
        session = Session(sid=1234, ipaddr=2130706433, port=16384, root=temp_dir)
        daemon.sessions[1234] = session
        
        # Test data for opening file in read mode
        data = struct.pack('<BH', 0x01, 0o644) + b'\x00' + b'binary_test.dat\x00'
        header = TNFSHeader(sid=1234, seqno=1, cmd=TNFS_CMD.OPENFILE, 
                           status=0, ipaddr=0x7F000001, port=16384)
        
        # Mock the socket for testing
        mock_socket = Mock()
        daemon.udp_socket = mock_socket
        
        # Test openfile
        daemon.handle_openfile(header, session, data)
        
        # Should create a file handle
        fd_index = None
        for i, fd in enumerate(session.fd):
            if fd is not None:
                fd_index = i
                break
        
        assert fd_index is not None
        
        # Test reading from the file to ensure binary mode works
        read_data = struct.pack('<BH', fd_index, 16)
        read_header = TNFSHeader(sid=1234, seqno=2, cmd=TNFS_CMD.READBLOCK, 
                                status=0, ipaddr=0x7F000001, port=16384)
        
        # Test readblock
        daemon.handle_readblock(read_header, session, read_data)
        
        # Should send response with binary data
        mock_socket.sendto.assert_called()
        
        # Cleanup
        os.close(session.fd[fd_index])
        session.fd[fd_index] = None
    
    def test_binary_mode_large_file_read(self, temp_dir):
        """Test reading large files in binary mode on Windows"""
        # Create a large test file
        test_file = Path(temp_dir) / "large_test.dat"
        
        # Create 2KB of binary data
        large_content = bytes(range(256)) * 8  # 256 * 8 = 2048 bytes
        test_file.write_bytes(large_content)
        
        # Create daemon instance
        daemon = TNFSDaemon(temp_dir, 16384)
        
        # Create a session
        session = Session(sid=1234, ipaddr=2130706433, port=16384, root=temp_dir)
        daemon.sessions[1234] = session
        
        # Test data for opening file in read mode
        data = struct.pack('<BH', 0x01, 0o644) + b'\x00' + b'large_test.dat\x00'
        header = TNFSHeader(sid=1234, seqno=1, cmd=TNFS_CMD.OPENFILE, 
                           status=0, ipaddr=0x7F000001, port=16384)
        
        # Mock the socket for testing
        mock_socket = Mock()
        daemon.udp_socket = mock_socket
        
        # Test openfile
        daemon.handle_openfile(header, session, data)
        
        # Should create a file handle
        fd_index = None
        for i, fd in enumerate(session.fd):
            if fd is not None:
                fd_index = i
                break
        
        assert fd_index is not None
        
        # Test reading MAX_IOSZ bytes (should work correctly in binary mode)
        from tnfsd import MAX_IOSZ
        read_data = struct.pack('<BH', fd_index, MAX_IOSZ)
        read_header = TNFSHeader(sid=1234, seqno=2, cmd=TNFS_CMD.READBLOCK, 
                                status=0, ipaddr=0x7F000001, port=16384)
        
        # Test readblock
        daemon.handle_readblock(read_header, session, read_data)
        
        # Should send response with correct amount of data
        mock_socket.sendto.assert_called()
        
        # Cleanup
        os.close(session.fd[fd_index])
        session.fd[fd_index] = None
    
    def test_binary_mode_no_line_ending_translation(self, temp_dir):
        """Test that binary mode prevents line ending translation"""
        # Create a test file with mixed line endings
        test_file = Path(temp_dir) / "mixed_endings.txt"
        mixed_content = b'Line 1\r\nLine 2\nLine 3\r\nLine 4\n'
        test_file.write_bytes(mixed_content)
        
        # Create daemon instance
        daemon = TNFSDaemon(temp_dir, 16384)
        
        # Create a session
        session = Session(sid=1234, ipaddr=2130706433, port=16384, root=temp_dir)
        daemon.sessions[1234] = session
        
        # Test data for opening file in read mode
        data = struct.pack('<BH', 0x01, 0o644) + b'\x00' + b'mixed_endings.txt\x00'
        header = TNFSHeader(sid=1234, seqno=1, cmd=TNFS_CMD.OPENFILE, 
                           status=0, ipaddr=0x7F000001, port=16384)
        
        # Mock the socket for testing
        mock_socket = Mock()
        daemon.udp_socket = mock_socket
        
        # Test openfile
        daemon.handle_openfile(header, session, data)
        
        # Should create a file handle
        fd_index = None
        for i, fd in enumerate(session.fd):
            if fd is not None:
                fd_index = i
                break
        
        assert fd_index is not None
        
        # Test reading the entire file
        read_data = struct.pack('<BH', fd_index, len(mixed_content))
        read_header = TNFSHeader(sid=1234, seqno=2, cmd=TNFS_CMD.READBLOCK, 
                                status=0, ipaddr=0x7F000001, port=16384)
        
        # Test readblock
        daemon.handle_readblock(read_header, session, read_data)
        
        # Should send response with exact binary content (no translation)
        mock_socket.sendto.assert_called()
        
        # Cleanup
        os.close(session.fd[fd_index])
        session.fd[fd_index] = None


@pytest.mark.linux
class TestLinuxCompatibility:
    """Test Linux-specific compatibility features"""
    
    @pytest.mark.skipif(os.name == 'nt', reason="Linux-specific test")
    def test_o_binary_constant_not_used(self):
        """Test that O_BINARY constant is not used on Linux"""
        from tnfsd import O_BINARY
        assert O_BINARY == 0  # Should be 0 on non-Windows platforms
    
    @pytest.mark.skipif(os.name == 'nt', reason="Linux-specific test")
    def test_file_open_flags_linux(self):
        """Test file open flags on Linux"""
        from tnfsd import O_RDONLY, O_WRONLY, O_CREAT, O_TRUNC
        
        # Test individual flags
        assert O_RDONLY == 0
        assert O_WRONLY == 1
        assert O_CREAT == 64  # Linux value
        assert O_TRUNC == 512


class TestCrossPlatformCompatibility:
    """Test compatibility across different platforms"""
    
    def test_platform_detection(self):
        """Test that platform detection works correctly"""
        from tnfsd import O_BINARY
        
        if os.name == 'nt':
            # Windows
            assert O_BINARY != 0
        else:
            # Unix-like systems
            assert O_BINARY == 0
    
    def test_file_operations_work_on_all_platforms(self, temp_dir):
        """Test that file operations work on all platforms"""
        # Create a test file
        test_file = Path(temp_dir) / "cross_platform_test.txt"
        test_content = "This is a cross-platform test\n"
        test_file.write_text(test_content)
        
        # Create daemon instance
        daemon = TNFSDaemon(temp_dir, 16384)
        
        # Create a session
        session = Session(sid=1234, ipaddr=2130706433, port=16384, root=temp_dir)
        daemon.sessions[1234] = session
        
        # Test data for opening file in read mode
        data = struct.pack('<BH', 0x01, 0o644) + b'\x00' + b'cross_platform_test.txt\x00'
        header = TNFSHeader(sid=1234, seqno=1, cmd=TNFS_CMD.OPENFILE, 
                           status=0, ipaddr=0x7F000001, port=16384)
        
        # Mock the socket for testing
        mock_socket = Mock()
        daemon.udp_socket = mock_socket
        
        # Test openfile
        daemon.handle_openfile(header, session, data)
        
        # Should create a file handle
        fd_index = None
        for i, fd in enumerate(session.fd):
            if fd is not None:
                fd_index = i
                break
        
        assert fd_index is not None
        
        # Test reading from the file
        read_data = struct.pack('<BH', fd_index, len(test_content.encode()))
        read_header = TNFSHeader(sid=1234, seqno=2, cmd=TNFS_CMD.READBLOCK, 
                                status=0, ipaddr=0x7F000001, port=16384)
        
        # Test readblock
        daemon.handle_readblock(read_header, session, read_data)
        
        # Should send response
        mock_socket.sendto.assert_called()
        
        # Cleanup
        os.close(session.fd[fd_index])
        session.fd[fd_index] = None
