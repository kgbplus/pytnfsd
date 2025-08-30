# TNFS Daemon Test Suite

This directory contains comprehensive tests for the TNFS daemon Python implementation.

## Test Structure

- **`test_tnfsd.py`** - Main test suite covering core functionality
- **`test_protocol.py`** - Protocol constants and error handling tests
- **`test_windows_compatibility.py`** - Windows-specific compatibility tests
- **`conftest.py`** - Pytest configuration and common fixtures

## Running Tests

### Prerequisites

Install the required testing dependencies:

```bash
pip install -r requirements.txt
```

### Basic Test Execution

Run all tests:
```bash
python -m pytest tests/
```

Run with coverage:
```bash
python -m pytest --cov=tnfsd --cov-report=term-missing tests/
```

### Using the Test Runner Script

The `run_tests.py` script provides convenient options:

```bash
# Run all tests with coverage
python run_tests.py

# Run only unit tests
python run_tests.py --type unit

# Run only integration tests
python run_tests.py --type integration

# Run Windows-specific tests
python run_tests.py --type windows

# Run with verbose output
python run_tests.py --verbose

# Disable coverage reporting
python run_tests.py --no-coverage

# List all available tests
python run_tests.py --list

# Run specific test file
python run_tests.py --test-file test_tnfsd.py

# Run specific test function
python run_tests.py --test-file test_tnfsd.py --test-function TestTNFSHeader::test_header_creation
```

### Test Categories

Tests are organized into categories with markers:

- **`@pytest.mark.unit`** - Unit tests (default)
- **`@pytest.mark.integration`** - Integration tests
- **`@pytest.mark.slow`** - Slow-running tests
- **`@pytest.mark.windows`** - Windows-specific tests
- **`@pytest.mark.linux`** - Linux-specific tests

### Running Specific Test Categories

```bash
# Run only unit tests
python -m pytest -m unit tests/

# Run only integration tests
python -m pytest -m integration tests/

# Run Windows compatibility tests
python -m pytest -m windows tests/

# Run slow tests
python -m pytest -m slow tests/
```

## Test Coverage

The test suite covers:

### Core Components
- **TNFSHeader** - Header packing/unpacking, validation
- **Session** - Session management, file descriptor allocation
- **FileHandle** - File handle operations
- **DirectoryHandle** - Directory reading with . and .. entries
- **TNFSDaemon** - Main daemon functionality

### Protocol Handling
- All TNFS command types (MOUNT, OPENDIR, READDIR, etc.)
- Error handling and status codes
- Command classification and routing
- Protocol constants and compatibility

### Platform Compatibility
- Windows binary mode (O_BINARY flag)
- Cross-platform file operations
- Platform-specific test markers

### File Operations
- File opening with proper flags
- Binary mode reading (fixes the truncation issue)
- Directory listing with . and .. entries
- File statistics and metadata

## Test Fixtures

Common test fixtures are defined in `conftest.py`:

- **`temp_root_dir`** - Temporary root directory for testing
- **`temp_dir`** - Temporary directory for individual tests
- **`sample_files`** - Sample files and directories for testing
- **`mock_socket`** - Mock socket for network testing

## Writing New Tests

### Test Naming Convention
- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`

### Example Test Structure
```python
class TestNewFeature:
    """Test new feature functionality"""
    
    def test_feature_creation(self):
        """Test creating a new feature"""
        # Arrange
        # Act
        # Assert
        pass
    
    @pytest.mark.integration
    def test_feature_integration(self):
        """Test feature integration with other components"""
        pass
```

### Using Fixtures
```python
def test_with_fixture(temp_dir, sample_files):
    """Test using provided fixtures"""
    assert temp_dir.exists()
    assert 'test1.txt' in sample_files
```

### Mocking
```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Test using mocks"""
    mock_obj = Mock()
    mock_obj.method.return_value = "expected"
    
    result = mock_obj.method()
    assert result == "expected"
    mock_obj.method.assert_called_once()
```

## Continuous Integration

The test suite is designed to work with CI/CD systems:

- Tests run on both Windows and Linux
- Platform-specific tests are automatically marked
- Coverage reporting is integrated
- Exit codes properly indicate test success/failure

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're running from the project root directory
2. **Permission Errors**: Some tests create temporary files - ensure write permissions
3. **Platform Differences**: Windows and Linux tests may behave differently
4. **Socket Errors**: Network tests use mocks to avoid actual network operations

### Debug Mode

Run tests with verbose output to see detailed information:
```bash
python -m pytest -v tests/
```

### Running Individual Tests

To debug a specific test:
```bash
python -m pytest tests/test_tnfsd.py::TestTNFSHeader::test_header_creation -v -s
```

The `-s` flag allows print statements to be displayed during test execution.

## Contributing

When adding new tests:

1. Follow the existing naming conventions
2. Use appropriate test markers
3. Include docstrings explaining test purpose
4. Ensure tests are platform-independent when possible
5. Add platform-specific tests when needed
6. Update this README if adding new test categories
