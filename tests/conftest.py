#!/usr/bin/env python3
"""
Pytest configuration and common fixtures for TNFS daemon tests
"""

import pytest
import tempfile
import shutil
import os
from pathlib import Path


@pytest.fixture(scope="session")
def test_root_dir():
    """Create a test root directory for the entire test session"""
    temp_dir = tempfile.mkdtemp(prefix="tnfs_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for individual tests"""
    temp_dir = tempfile.mkdtemp(prefix="tnfs_temp_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing"""
    # Create some test files
    test_file1 = Path(temp_dir) / "test1.txt"
    test_file1.write_text("This is test file 1\n" * 100)  # ~2000 bytes
    
    test_file2 = Path(temp_dir) / "test2.txt"
    test_file2.write_text("This is test file 2\n" * 50)   # ~1000 bytes
    
    # Create a subdirectory
    subdir = Path(temp_dir) / "subdir"
    subdir.mkdir()
    
    test_file3 = Path(temp_dir) / "subdir" / "test3.txt"
    test_file3.write_text("This is test file 3\n" * 25)   # ~500 bytes
    
    # Create a binary file for testing binary mode
    binary_file = Path(temp_dir) / "binary.dat"
    binary_file.write_bytes(b'\x00\x01\x02\x03' * 128)  # 512 bytes
    
    return {
        'test1.txt': test_file1,
        'test2.txt': test_file2,
        'subdir/test3.txt': test_file3,
        'binary.dat': binary_file,
        'subdir': subdir
    }


@pytest.fixture
def mock_socket():
    """Create a mock socket for testing"""
    from unittest.mock import Mock
    mock_sock = Mock()
    mock_sock.sendto = Mock()
    mock_sock.recvfrom = Mock()
    mock_sock.bind = Mock()
    mock_sock.close = Mock()
    return mock_sock


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "windows: mark test as Windows-specific"
    )
    config.addinivalue_line(
        "markers", "linux: mark test as Linux-specific"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on platform"""
    for item in items:
        # Add platform-specific markers
        if os.name == 'nt':
            item.add_marker(pytest.mark.windows)
        else:
            item.add_marker(pytest.mark.linux)
        
        # Add unit test marker by default if not specified
        if not any(marker.name in ['unit', 'integration'] for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
