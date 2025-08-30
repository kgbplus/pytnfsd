
# TNFS Daemon - Python Implementation

This is a Python 3 implementation of the TNFS (The Network File System) daemon, compatible with the original C protocol and suitable for 8-bit and retro systems. It is designed for clarity, maintainability, and protocol compatibility.

## Features

- **Session Management**: Unique session IDs, session timeout, and per-session resource tracking
- **Directory Operations**: Open, read, close, seek, and tell directory position; supports both legacy and extended (OPENDIRX/READDIRX) directory commands
- **File Operations**: Open, read, write, seek, stat, close, unlink, chmod (not supported), and rename files
- **UDP Transport**: Fully functional; TCP connection handling is stubbed for future support
- **Error Handling**: Full TNFS error code mapping, protocol-aligned with C version
- **Resource Cleanup**: Automatic cleanup of expired sessions and open resources
- **Cross-Platform**: Works on Linux, Windows, and macOS (with some platform-specific flags)
- **Docker Support**: Official Dockerfile for containerized deployment

## Requirements

- Python 3.7 or higher (tested with 3.11)
- No external dependencies required for core functionality
- Optional: `requirements.txt` for future or extended features

## Installation

1. Clone or download the repository
2. Ensure Python 3.7+ is installed
3. (Optional) Install dependencies: `pip install -r requirements.txt`

## Usage

### Basic Usage

```bash
python3 tnfsd.py /path/to/root/directory
```

### Command Line Options

```bash
python3 tnfsd.py [OPTIONS] ROOT_DIR

Options:
  ROOT_DIR              Root directory to serve
  -p, --port PORT       Port to listen on (default: 16384)
  -v, --verbose         Enable verbose logging
  -h, --help            Show help message
```

### Docker Usage

Build and run the daemon in a container, serving `/data`:

```bash
docker build -t tnfsd .
docker run -it -p 16384:16384 -v /host/path:/data tnfsd
```

## Supported TNFS Commands

### Session
- MOUNT, UMOUNT

### Directory
- OPENDIR, READDIR, CLOSEDIR, MKDIR, RMDIR, TELLDIR, SEEKDIR, OPENDIRX, READDIRX

### File
- OPENFILE, OPENFILE_OLD, READBLOCK, WRITEBLOCK, CLOSEFILE, STATFILE, SEEKFILE, UNLINKFILE, CHMODFILE (returns ENOTSUP), RENAMEFILE

## Architecture

- **TNFSDaemon**: Main event loop, socket handling, and command dispatch
- **Session**: Per-client session state, file and directory handles
- **DirectoryHandle**: Directory enumeration and state
- **TNFSHeader**: Protocol header packing/unpacking
- **DirectoryEntry**: Directory entry serialization

## Configuration

All protocol constants (ports, limits, timeouts) match the C implementation for compatibility. See `tnfsd.py` for details.

## Security Considerations

- No authentication (matches original C)
- Path validation prevents directory traversal
- File access is restricted to the root directory
- Sessions are isolated per client

## Limitations

- TCP transport is not yet implemented (UDP only)
- No authentication or encryption
- Performance is lower than C version
- No support for extended file attributes

## Comparison with C Implementation

**Advantages:**
- Easier to read, modify, and debug
- Improved error handling and logging
- Cross-platform and no compilation required

**Disadvantages:**
- Slower and higher memory usage than C
- Not suitable for high-load production

## Development & Extending

To add a new TNFS command:
1. Add the command to `TNFS_CMD` in `tnfsd.py`
2. Implement a handler method in `TNFSDaemon`
3. Register the handler in `handle_packet`

## Testing

Test with any TNFS client, or use the included `test_tnfs.py` for basic protocol checks. Manual packet crafting is also possible for advanced testing.

## License

MIT License (same as original C implementation)

## Credits

Original C TNFS daemon by Dylan Smith. Python port and enhancements by the open-source community.