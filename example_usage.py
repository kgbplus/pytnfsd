#!/usr/bin/env python3
"""
Example usage of the Python TNFS daemon

This script demonstrates how to:
1. Start the TNFS daemon
2. Create a simple client to interact with it
3. Perform basic file system operations
"""

import os
import sys
import time
import threading
from pathlib import Path
from tnfsd import TNFSDaemon

def create_test_environment():
    """Create a test directory structure"""
    test_dir = Path("example_root")
    test_dir.mkdir(exist_ok=True)
    
    # Create some test files
    (test_dir / "readme.txt").write_text("This is a test TNFS server\nWelcome to the example!")
    (test_dir / "data.txt").write_text("Some sample data\nLine 2\nLine 3")
    
    # Create a subdirectory
    subdir = test_dir / "documents"
    subdir.mkdir(exist_ok=True)
    (subdir / "report.txt").write_text("This is a sample report\nWith multiple lines\nOf content")
    
    print(f"Created test environment in: {test_dir}")
    return test_dir

def run_daemon_example():
    """Run the TNFS daemon example"""
    print("=== TNFS Daemon Example ===\n")
    
    # Create test environment
    test_dir = create_test_environment()
    
    # Start daemon in a separate thread
    daemon = TNFSDaemon(str(test_dir), port=16385)  # Use different port for example
    
    def run_daemon():
        try:
            daemon.run()
        except KeyboardInterrupt:
            print("\nDaemon stopped by user")
    
    daemon_thread = threading.Thread(target=run_daemon, daemon=True)
    daemon_thread.start()
    
    # Give daemon time to start
    time.sleep(1)
    
    print("TNFS daemon started on port 16385")
    print(f"Serving directory: {test_dir}")
    print("\nYou can now connect to the daemon using a TNFS client")
    print("or run the test script: python3 test_tnfs.py")
    print("\nPress Ctrl+C to stop the daemon")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down daemon...")
        daemon.running = False

def show_client_example():
    """Show how to create a TNFS client"""
    print("\n=== TNFS Client Example ===\n")
    
    client_code = '''
import socket
import struct

class SimpleTNFSClient:
    def __init__(self, host='localhost', port=16385):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.host = host
        self.port = port
        self.sid = 0
        self.seqno = 0
    
    def mount(self):
        # TNFS_MOUNT command
        data = b'/\\x00test\\x00test\\x00'
        header = struct.pack('<HBB', self.sid, self.seqno, 0x00)
        packet = header + data
        self.sock.sendto(packet, (self.host, self.port))
        
        # Get response
        response, _ = self.sock.recvfrom(1024)
        self.sid = struct.unpack('<H', response[:2])[0]
        print(f"Mounted with session ID: {self.sid}")
    
    def list_directory(self):
        # Open directory
        data = b'\\x00'  # Root directory
        header = struct.pack('<HBB', self.sid, self.seqno, 0x10)  # OPENDIR
        packet = header + data
        self.sock.sendto(packet, (self.host, self.port))
        
        response, _ = self.sock.recvfrom(1024)
        handle = response[4]
        
        # Read directory entries
        while True:
            data = struct.pack('<B', handle)
            header = struct.pack('<HBB', self.sid, self.seqno, 0x11)  # READDIR
            packet = header + data
            self.sock.sendto(packet, (self.host, self.port))
            
            response, _ = self.sock.recvfrom(1024)
            if len(response) < 17:  # End of directory
                break
            
            # Parse entry
            flags, size, mtime, ctime = struct.unpack('<BIII', response[4:17])
            name = response[17:].split(b'\\x00')[0].decode('utf-8')
            print(f"  {name} ({size} bytes)")
        
        # Close directory
        data = struct.pack('<B', handle)
        header = struct.pack('<HBB', self.sid, self.seqno, 0x12)  # CLOSEDIR
        packet = header + data
        self.sock.sendto(packet, (self.host, self.port))
    
    def close(self):
        self.sock.close()

# Usage
client = SimpleTNFSClient()
client.mount()
client.list_directory()
client.close()
'''
    
    print("Here's an example of how to create a simple TNFS client:")
    print(client_code)

def main():
    """Main function"""
    if len(sys.argv) > 1:
        if sys.argv[1] == '--client-example':
            show_client_example()
        elif sys.argv[1] == '--help':
            print("TNFS Daemon Example Usage:")
            print("  python3 example_usage.py              # Run daemon example")
            print("  python3 example_usage.py --client-example  # Show client code")
            print("  python3 example_usage.py --help       # Show this help")
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for usage information")
    else:
        run_daemon_example()

if __name__ == '__main__':
    main() 