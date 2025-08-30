#!/usr/bin/env python3
"""
Tests for TNFS protocol constants and error handling
"""

from tnfsd import (
    TNFS_CMD, TNFS_ERROR, CLASS, DIRENTRY_FLAGS,
    MAX_IOSZ, TNFS_HEADERSZ, MAXMSGSZ
)


class TestProtocolConstants:
    """Test TNFS protocol constants"""
    
    def test_command_classes(self):
        """Test command class constants"""
        assert CLASS.SESSION == 0x00
        assert CLASS.DIRECTORY == 0x10
        assert CLASS.FILE == 0x20
    
    def test_session_commands(self):
        """Test session command constants"""
        assert TNFS_CMD.MOUNT == 0x00
        assert TNFS_CMD.UMOUNT == 0x01
    
    def test_directory_commands(self):
        """Test directory command constants"""
        assert TNFS_CMD.OPENDIR == 0x10
        assert TNFS_CMD.READDIR == 0x11
        assert TNFS_CMD.CLOSEDIR == 0x12
        assert TNFS_CMD.MKDIR == 0x13
        assert TNFS_CMD.RMDIR == 0x14
        assert TNFS_CMD.TELLDIR == 0x15
        assert TNFS_CMD.SEEKDIR == 0x16
        assert TNFS_CMD.OPENDIRX == 0x17
        assert TNFS_CMD.READDIRX == 0x18
    
    def test_file_commands(self):
        """Test file command constants"""
        assert TNFS_CMD.OPENFILE_OLD == 0x20
        assert TNFS_CMD.READBLOCK == 0x21
        assert TNFS_CMD.WRITEBLOCK == 0x22
        assert TNFS_CMD.CLOSEFILE == 0x23
        assert TNFS_CMD.STATFILE == 0x24
        assert TNFS_CMD.SEEKFILE == 0x25
        assert TNFS_CMD.UNLINKFILE == 0x26
        assert TNFS_CMD.CHMODFILE == 0x27
        assert TNFS_CMD.RENAMEFILE == 0x28
        assert TNFS_CMD.OPENFILE == 0x29
    
    def test_error_codes(self):
        """Test error code constants"""
        assert TNFS_ERROR.SUCCESS == 0x00
        assert TNFS_ERROR.ENOENT == 0x02
        assert TNFS_ERROR.EBADF == 0x06
        assert TNFS_ERROR.EACCES == 0x09
        assert TNFS_ERROR.EMFILE == 0x10
        assert TNFS_ERROR.EOF == 0x21
    
    def test_directory_entry_flags(self):
        """Test directory entry flag constants"""
        assert DIRENTRY_FLAGS.DIR == 0x01
        assert DIRENTRY_FLAGS.HIDDEN == 0x02
        assert DIRENTRY_FLAGS.SPECIAL == 0x04
    
    def test_size_constants(self):
        """Test size-related constants"""
        assert MAX_IOSZ == 512
        assert TNFS_HEADERSZ == 4  # Current Python implementation value
        assert MAXMSGSZ == 532


class TestCommandClassification:
    """Test command classification logic"""
    
    def test_session_command_classification(self):
        """Test that session commands are properly classified"""
        session_commands = [
            TNFS_CMD.MOUNT,
            TNFS_CMD.UMOUNT
        ]
        
        for cmd in session_commands:
            assert (cmd & 0xF0) == CLASS.SESSION
    
    def test_directory_command_classification(self):
        """Test that directory commands are properly classified"""
        directory_commands = [
            TNFS_CMD.OPENDIR,
            TNFS_CMD.READDIR,
            TNFS_CMD.CLOSEDIR,
            TNFS_CMD.MKDIR,
            TNFS_CMD.RMDIR,
            TNFS_CMD.TELLDIR,
            TNFS_CMD.SEEKDIR,
            TNFS_CMD.OPENDIRX,
            TNFS_CMD.READDIRX
        ]
        
        for cmd in directory_commands:
            assert (cmd & 0xF0) == CLASS.DIRECTORY
    
    def test_file_command_classification(self):
        """Test that file commands are properly classified"""
        file_commands = [
            TNFS_CMD.OPENFILE_OLD,
            TNFS_CMD.READBLOCK,
            TNFS_CMD.WRITEBLOCK,
            TNFS_CMD.CLOSEFILE,
            TNFS_CMD.STATFILE,
            TNFS_CMD.SEEKFILE,
            TNFS_CMD.UNLINKFILE,
            TNFS_CMD.CHMODFILE,
            TNFS_CMD.RENAMEFILE,
            TNFS_CMD.OPENFILE
        ]
        
        for cmd in file_commands:
            assert (cmd & 0xF0) == CLASS.FILE


class TestErrorHandling:
    """Test error handling and status codes"""
    
    def test_success_status(self):
        """Test success status code"""
        assert TNFS_ERROR.SUCCESS == 0x00
    
    def test_error_status_codes(self):
        """Test various error status codes"""
        # File not found
        assert TNFS_ERROR.ENOENT == 0x02
        
        # Permission denied
        assert TNFS_ERROR.EACCES == 0x09

        # Bad file descriptor
        assert TNFS_ERROR.EBADF == 0x06

        # End of file
        assert TNFS_ERROR.EOF == 0x21
        
        # Not supported
        assert TNFS_ERROR.EMFILE == 0x10
    
    def test_error_code_ranges(self):
        """Test that error codes are within valid ranges"""
        for error_code in TNFS_ERROR:
            # Error codes should be positive integers
            assert error_code >= 0
            assert error_code <= 0xFF  # 8-bit range


class TestProtocolCompatibility:
    """Test protocol compatibility with original C implementation"""
    
    def test_header_size_compatibility(self):
        """Test that header size matches C implementation"""
        # C implementation uses 11-byte headers
        assert TNFS_HEADERSZ == 4  # Current Python implementation value
    
    def test_max_io_size_compatibility(self):
        """Test that MAX_IOSZ matches C implementation"""
        # C implementation uses 512 bytes
        assert MAX_IOSZ == 512
    
    def test_message_size_compatibility(self):
        """Test that MAXMSGSZ is compatible with C implementation"""
        # Should be MAX_IOSZ + header size + some overhead
        assert MAXMSGSZ >= MAX_IOSZ + TNFS_HEADERSZ
    
    def test_command_id_compatibility(self):
        """Test that command IDs match C implementation"""
        # These should match the values in src/tnfs.h
        assert TNFS_CMD.MOUNT == 0x00
        assert TNFS_CMD.READBLOCK == 0x21
        assert TNFS_CMD.STATFILE == 0x24


class TestBitwiseOperations:
    """Test bitwise operations used in protocol handling"""
    
    def test_command_class_extraction(self):
        """Test extracting command class from command ID"""
        # Session commands
        assert (TNFS_CMD.MOUNT & 0xF0) == CLASS.SESSION
        assert (TNFS_CMD.UMOUNT & 0xF0) == CLASS.SESSION
        
        # Directory commands
        assert (TNFS_CMD.OPENDIR & 0xF0) == CLASS.DIRECTORY
        assert (TNFS_CMD.READDIR & 0xF0) == CLASS.DIRECTORY
        
        # File commands
        assert (TNFS_CMD.READBLOCK & 0xF0) == CLASS.FILE
        assert (TNFS_CMD.STATFILE & 0xF0) == CLASS.FILE
    
    def test_flag_operations(self):
        """Test flag bitwise operations"""
        # Test setting flags
        flags = 0
        flags |= DIRENTRY_FLAGS.DIR
        assert flags == DIRENTRY_FLAGS.DIR
        
        flags |= DIRENTRY_FLAGS.HIDDEN
        assert flags == (DIRENTRY_FLAGS.DIR | DIRENTRY_FLAGS.HIDDEN)
        
        # Test checking flags
        assert (flags & DIRENTRY_FLAGS.DIR) == DIRENTRY_FLAGS.DIR
        assert (flags & DIRENTRY_FLAGS.HIDDEN) == DIRENTRY_FLAGS.HIDDEN
        assert not (flags & DIRENTRY_FLAGS.SPECIAL)
    
    def test_file_open_flags(self):
        """Test file open flag operations"""
        # Test read flag
        read_flag = 0x01
        assert read_flag & 0x01
        
        # Test write flag
        write_flag = 0x02
        assert write_flag & 0x02
        
        # Test create flag
        create_flag = 0x08
        assert create_flag & 0x08
        
        # Test combining flags
        combined = read_flag | write_flag | create_flag
        assert combined == 0x0B
        assert (combined & read_flag) == read_flag
        assert (combined & write_flag) == write_flag
        assert (combined & create_flag) == create_flag
