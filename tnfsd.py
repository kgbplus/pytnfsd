#!/usr/bin/env python3
"""
TNFS (The Network File System) Daemon - Python Implementation

This is a Python rewrite of the original C TNFS daemon.
TNFS is a simple network file system protocol designed for 8-bit systems.

Copyright (c) 2010 Dylan Smith (original C implementation)
Python rewrite by AI Assistant

MIT License
"""

import argparse
import logging
from nt import O_EXCL
import os
import socket
import struct
import sys
import time
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import select
import fnmatch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration constants
TNFSD_PORT = 16384
MAXMSGSZ = 532
MAX_FD_PER_CONN = 16
MAX_DHND_PER_CONN = 8
MAX_CLIENTS = 4096
MAX_CLIENTS_PER_IP = 4096
MAX_TCP_CONN = 256
SESSION_TIMEOUT = 21600  # 6 hours
TNFS_HEADERSZ = 4
TNFS_MAX_PAYLOAD = MAXMSGSZ - TNFS_HEADERSZ - 1
MAX_TNFSPATH = 256
MAX_FILEPATH = 384
MAX_ROOT = 128
PROTOVERSION_LSB = 0x02
PROTOVERSION_MSB = 0x01
TIMEOUT_LSB = 0xE8
TIMEOUT_MSB = 0x03
MAX_FILENAME_LEN = 256
MAX_IOSZ = 512
TNFS_DIRSTATUS_EOF = 0x01

# File open flags (for Windows compatibility)
O_RDONLY = getattr(os, 'O_RDONLY', 0)
O_WRONLY = getattr(os, 'O_WRONLY', 1)
O_RDWR = getattr(os, 'O_RDWR', 2)
O_APPEND = getattr(os, 'O_APPEND', 8)
O_CREAT = getattr(os, 'O_CREAT', 64)
O_TRUNC = getattr(os, 'O_TRUNC', 512)
O_BINARY = getattr(os, 'O_BINARY', 0)  # Windows-specific, 0 on other platforms

# Command classes
class CLASS(IntEnum):
    SESSION = 0x00
    DIRECTORY = 0x10
    FILE = 0x20

# TNFS command IDs
class TNFS_CMD(IntEnum):
    # Session commands
    MOUNT = 0x00
    UMOUNT = 0x01
    
    # Directory commands
    OPENDIR = 0x10
    READDIR = 0x11
    CLOSEDIR = 0x12
    MKDIR = 0x13
    RMDIR = 0x14
    TELLDIR = 0x15
    SEEKDIR = 0x16
    OPENDIRX = 0x17
    READDIRX = 0x18
    
    # File commands
    OPENFILE_OLD = 0x20
    READBLOCK = 0x21
    WRITEBLOCK = 0x22
    CLOSEFILE = 0x23
    STATFILE = 0x24
    SEEKFILE = 0x25
    UNLINKFILE = 0x26
    CHMODFILE = 0x27
    RENAMEFILE = 0x28
    OPENFILE = 0x29

# Directory entry flags
class DIRENTRY_FLAGS(IntEnum):
    DIR = 0x01
    HIDDEN = 0x02
    SPECIAL = 0x04

# Error codes
class TNFS_ERROR(IntEnum):
    SUCCESS = 0x00
    EPERM = 0x01
    ENOENT = 0x02
    EIO = 0x03
    ENXIO = 0x04
    E2BIG = 0x05
    EBADF = 0x06
    EAGAIN = 0x07
    ENOMEM = 0x08
    EACCES = 0x09
    EBUSY = 0x0A
    EEXIST = 0x0B
    ENOTDIR = 0x0C
    EISDIR = 0x0D
    EINVAL = 0x0E
    ENFILE = 0x0F
    EMFILE = 0x10
    EFBIG = 0x11
    ENOSPC = 0x12
    ESPIPE = 0x13
    EROFS = 0x14
    ENAMETOOLONG = 0x15
    ENOSYS = 0x16
    ENOTEMPTY = 0x17
    ELOOP = 0x18
    ENODATA = 0x19
    ENOSTR = 0x1A
    EPROTO = 0x1B
    EBADFD = 0x1C
    EUSERS = 0x1D
    ENOBUFS = 0x1E
    EALREADY = 0x1F
    ESTALE = 0x20
    EOF = 0x21

@dataclass
class TNFSHeader:
    """TNFS packet header"""
    sid: int = 0          # Session ID
    seqno: int = 0        # Sequence number
    cmd: int = 0          # Command
    status: int = 0       # Status
    ipaddr: int = 0       # Client address
    port: int = 0         # Client port
    
    def pack(self) -> bytes:
        """Pack header into bytes"""
        return struct.pack('<HBBB', self.sid, self.seqno, self.cmd, self.status)
    
    @classmethod
    def unpack(cls, data: bytes) -> 'TNFSHeader':
        """Unpack bytes into header"""
        if len(data) < 3:
            raise ValueError("Header too short")
        sid, seqno, cmd = struct.unpack('<HBB', data[:4])
        return cls(sid=sid, seqno=seqno, cmd=cmd)

@dataclass
class DirectoryEntry:
    """Directory entry structure"""
    flags: int = 0
    size: int = 0
    mtime: int = 0
    ctime: int = 0
    entrypath: str = ""
    
    def pack(self) -> bytes:
        """Pack directory entry into bytes"""
        path_bytes = self.entrypath.encode('utf-8', errors='ignore')
        if len(path_bytes) > MAX_FILENAME_LEN - 1:
            path_bytes = path_bytes[:MAX_FILENAME_LEN - 1]
        path_bytes += b'\x00'
        
        return struct.pack('<BIII', self.flags, self.size, self.mtime, self.ctime) + path_bytes

class DirectoryHandle:
    """Directory handle for managing directory operations"""
    def __init__(self, path: str):
        self.path = path
        self.handle = None
        self.entry_count = 0
        self.entry_list = []
        self.current_entry = None
        self.entries = []
        self.current_index = 0
        
    def open(self):
        """Open directory handle"""
        try:
            self.entries = list(Path(self.path).iterdir())
            self.entry_count = len(self.entries)
            # Prepare to return '.' and '..' first, like POSIX readdir
            self.current_index = -2
            return True
        except Exception as e:
            logger.error(f"Failed to open directory {self.path}: {e}")
            return False
    
    def close(self):
        """Close directory handle"""
        self.entries = []
        self.current_index = 0
        self.entry_count = 0
    
    def read_entry(self) -> Optional[DirectoryEntry]:
        """Read next directory entry"""
        # Synthesize '.' and '..' first for compatibility with C version
        try:
            if self.current_index == -2:
                self.current_index += 1
                p = Path(self.path)
                st = p.stat()
                return DirectoryEntry(
                    flags=int(DIRENTRY_FLAGS.DIR),
                    size=0,
                    mtime=int(st.st_mtime),
                    ctime=int(st.st_ctime),
                    entrypath='.'
                )
            if self.current_index == -1:
                self.current_index += 1
                p = Path(self.path).parent
                # In case parent stats fail, fall back to zeros
                try:
                    st = p.stat()
                    mtime = int(st.st_mtime)
                    ctime = int(st.st_ctime)
                except Exception:
                    mtime = 0
                    ctime = 0
                return DirectoryEntry(
                    flags=int(DIRENTRY_FLAGS.DIR),
                    size=0,
                    mtime=mtime,
                    ctime=ctime,
                    entrypath='..'
                )

            if self.current_index >= len(self.entries):
                return None

            entry_path = self.entries[self.current_index]
            self.current_index += 1

            stat = entry_path.stat()
            flags = 0
            if entry_path.is_dir():
                flags |= int(DIRENTRY_FLAGS.DIR)
            if entry_path.name.startswith('.'):
                flags |= int(DIRENTRY_FLAGS.HIDDEN)

            return DirectoryEntry(
                flags=flags,
                size=stat.st_size if entry_path.is_file() else 0,
                mtime=int(stat.st_mtime),
                ctime=int(stat.st_ctime),
                entrypath=entry_path.name
            )
        except Exception as e:
            logger.error(f"Error reading directory entry: {e}")
            return None
    
    def seek(self, position: int):
        """Seek to position in directory"""
        if 0 <= position < len(self.entries):
            self.current_index = position
    
    def tell(self) -> int:
        """Get current position in directory"""
        return self.current_index

class Session:
    """TNFS session for managing client connections"""
    def __init__(self, sid: int, ipaddr: int, port: int, root: str):
        self.sid = sid
        self.ipaddr = ipaddr
        self.port = port
        self.root = root
        self.last_contact = time.time()
        self.seqno = 0
        self.fd = [None] * MAX_FD_PER_CONN  # File descriptors
        self.dhandles = [None] * MAX_DHND_PER_CONN  # Directory handles
        self.lastmsg = b''
        self.lastmsgsz = 0
        self.lastseqno = 0
        self.isTCP = False
        
    def get_free_fd(self) -> Optional[int]:
        """Get free file descriptor slot"""
        for i, fd in enumerate(self.fd):
            if fd is None:
                return i
        return None
    
    def get_free_dhandle(self) -> Optional[int]:
        """Get free directory handle slot"""
        for i, handle in enumerate(self.dhandles):
            if handle is None:
                return i
        return None
    
    def cleanup(self):
        """Clean up session resources"""
        # Close all open files
        for fd in self.fd:
            if fd is not None:
                try:
                    fd.close()
                except:
                    pass
        
        # Close all directory handles
        for handle in self.dhandles:
            if handle is not None:
                handle.close()

class TNFSDaemon:
    """Main TNFS daemon class"""
    def __init__(self, root_dir: str, port: int = TNFSD_PORT):
        self.root_dir = Path(root_dir).resolve()
        self.port = port
        self.sessions: Dict[int, Session] = {}
        self.sessions_by_ip: Dict[int, List[Session]] = {}
        self.next_sid = 1
        self.udp_socket = None
        self.tcp_socket = None
        self.running = False
        
        # Validate root directory
        if not self.root_dir.exists() or not self.root_dir.is_dir():
            raise ValueError(f"Invalid root directory: {root_dir}")
        
        logger.info(f"TNFS daemon initialized with root: {self.root_dir}")
    
    def get_new_sid(self) -> int:
        """Generate new session ID"""
        sid = self.next_sid
        self.next_sid = (self.next_sid + 1) % 65536
        return sid
    
    def create_session(self, ipaddr: int, port: int, root: str) -> Session:
        """Create new session"""
        sid = self.get_new_sid()
        session = Session(sid, ipaddr, port, root)
        self.sessions[sid] = session
        
        # Track by IP
        if ipaddr not in self.sessions_by_ip:
            self.sessions_by_ip[ipaddr] = []
        self.sessions_by_ip[ipaddr].append(session)
        
        logger.info(f"Created session {sid} for {ipaddr}:{port}")
        return session
    
    def find_session_by_sid(self, sid: int) -> Optional[Session]:
        """Find session by session ID"""
        return self.sessions.get(sid)
    
    def find_session_by_ip(self, ipaddr: int) -> Optional[Session]:
        """Find session by IP address"""
        sessions = self.sessions_by_ip.get(ipaddr, [])
        return sessions[0] if sessions else None
    
    def remove_session(self, session: Session):
        """Remove session"""
        if session.sid in self.sessions:
            del self.sessions[session.sid]
        
        if session.ipaddr in self.sessions_by_ip:
            self.sessions_by_ip[session.ipaddr] = [
                s for s in self.sessions_by_ip[session.ipaddr] 
                if s.sid != session.sid
            ]
            if not self.sessions_by_ip[session.ipaddr]:
                del self.sessions_by_ip[session.ipaddr]
        
        session.cleanup()
        logger.info(f"Removed session {session.sid}")
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = time.time()
        expired = []
        
        for session in self.sessions.values():
            if current_time - session.last_contact > SESSION_TIMEOUT:
                expired.append(session)
        
        for session in expired:
            self.remove_session(session)
    
    def setup_sockets(self):
        """Setup UDP and TCP sockets"""
        # UDP socket
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_socket.bind(('', self.port))
        
        # TCP socket
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(('', self.port))
        self.tcp_socket.listen(5)
        
        logger.info(f"TNFS daemon listening on port {self.port}")
    
    def send_response(self, session: Session, header: TNFSHeader, data: bytes = b''):
        """Send response to client"""
        response = header.pack() + data
        
        session.lastmsg = response
        session.lastmsgsz = len(response)
        session.lastseqno = header.seqno
        
        try:
            if session.isTCP:
                # TCP response
                pass  # TODO: Implement TCP response
            else:
                # UDP response
                client_addr = (socket.inet_ntoa(struct.pack('<I', session.ipaddr)), session.port)
                self.udp_socket.sendto(response, client_addr)
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    def send_error(self, session: Session, header: TNFSHeader, error: bytes):
        """Send error response"""
        error_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=error)
        self.send_response(session, error_header)
    
    def handle_mount(self, header: TNFSHeader, data: bytes, client_addr: Tuple[str, int]) -> Session:
        """Handle TNFS_MOUNT command"""
        try:
            # Parse mount data
            if not data.endswith(b'\x00'):
                logger.error("Unterminated mount data")
                return None

            # Extract mountpoint, username, password
            version_raw = struct.unpack_from('<H', data, 0)[0]
            version_major = version_raw >> 8
            version_minor = version_raw & 0xFF

            mount_point = data[2]

            offset = 3
            parts = data[offset:].rstrip(b'\x00').split(b'\x00', 2)
            if len(parts) == 2:
                username = parts[0].decode('utf-8', errors='ignore')
                password = parts[1].decode('utf-8', errors='ignore')
            
            # For now, ignore authentication
            ipaddr = struct.unpack('<I', socket.inet_aton(client_addr[0]))[0]
            
            # Check if session already exists for this IP
            existing_session = self.find_session_by_ip(ipaddr)
            if existing_session:
                self.remove_session(existing_session)
            
            # Create new session
            session = self.create_session(ipaddr, client_addr[1], mount_point)
            
            # Send mount response
            response_data = struct.pack('<BBBB', PROTOVERSION_LSB, PROTOVERSION_MSB, TIMEOUT_LSB, TIMEOUT_MSB)
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header, response_data)
            
            logger.info(f"Client {client_addr[0]}:{client_addr[1]} mounted {mount_point}")
            return session
            
        except Exception as e:
            logger.error(f"Mount failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EAGAIN)
            return None
    
    def handle_umount(self, header: TNFSHeader, session: Session):
        """Handle TNFS_UMOUNT command"""
        if session:
            self.remove_session(session)
        
        # Send success response
        response_header = TNFSHeader(sid=0, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
        self.send_response(session, response_header)
    
    def handle_opendir(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_OPENDIR command"""
        try:
            if not data.endswith(b'\x00'):
                logger.error("Unterminated path")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            path = data.rstrip(b'\x00').decode('utf-8', errors='ignore')
            full_path = self.root_dir / path.lstrip('/')
            
            if not full_path.exists() or not full_path.is_dir():
                logger.error("Directory does not exist")
                self.send_error(session, header, TNFS_ERROR.ENOENT)
                return None

            # Get free directory handle
            handle_index = session.get_free_dhandle()
            if handle_index is None:
                logger.error("No free directory handles")
                self.send_error(session, header, TNFS_ERROR.EMFILE)
                return None

            # Create directory handle
            dir_handle = DirectoryHandle(str(full_path))
            if not dir_handle.open():
                logger.error("Failed to open directory")
                self.send_error(session, header, TNFS_ERROR.ENOENT)
                return None

            session.dhandles[handle_index] = dir_handle
            
            # Send response with handle index
            response_data = struct.pack('<B', handle_index)
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header, response_data)
            
        except Exception as e:
            logger.error(f"Opendir failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EAGAIN)

    def handle_readdir(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_READDIR command"""
        try:
            if len(data) != 1:
                logger.error("No handle index")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            handle_index = data[0]
            if handle_index >= MAX_DHND_PER_CONN or session.dhandles[handle_index] is None:
                logger.error("Invalid directory handle")
                self.send_error(session, header, TNFS_ERROR.ENOENT)
                return None

            dir_handle = session.dhandles[handle_index]
            entry = dir_handle.read_entry()
 
            if entry is None:
                # End of directory
                self.send_error(session, header, TNFS_ERROR.EOF)
            else:
                # Send only the null-terminated entry name (legacy READDIR)
                name_bytes = entry.entrypath.encode('utf-8', errors='ignore') + b'\x00'
                response_data = name_bytes
                response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
                self.send_response(session, response_header, response_data)
 
        except Exception as e:
            logger.error(f"Readdir failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EBADF)
    
    def handle_closedir(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_CLOSEDIR command"""
        try:
            if len(data) < 1:
                logger.error("No handle index")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            handle_index = data[0]
            if handle_index >= MAX_DHND_PER_CONN or session.dhandles[handle_index] is None:
                logger.error("Invalid directory handle")
                self.send_error(session, header, TNFS_ERROR.ENOENT)
                return None

            # Close directory handle
            session.dhandles[handle_index].close()
            session.dhandles[handle_index] = None
            
            # Send success response
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header)
            
        except Exception as e:
            logger.error(f"Closedir failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EBADF)
    
    def handle_openfile(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_OPENFILE command"""
        try:
            if len(data) < 4:
                logger.error("Invalid open data")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            flags = struct.unpack('<H', data[0:2])[0]
            mode = struct.unpack('<H', data[2:4])[0]
            filename = data[4:].rstrip(b'\x00').decode('utf-8', errors='ignore')
            
            full_path = self.root_dir / filename.lstrip('/')
            
            # Get free file descriptor
            fd_index = session.get_free_fd()
            if fd_index is None:
                logger.error("No free file descriptors")
                self.send_error(session, header, TNFS_ERROR.EMFILE)
                return None

            # Open file
            file_flags = 0
            if (flags & 0x0003) == 0x0001:  # Read
                file_flags |= O_RDONLY
            if (flags & 0x0003) == 0x0002:  # Write
                file_flags |= O_WRONLY
            if (flags & 0x0003) == 0x0003:  # Read/Write
                file_flags |= O_RDWR

            if flags & 0x0008:  # Append
                file_flags |= O_APPEND
            if flags & 0x0100:  # Create
                file_flags |= O_CREAT
            if flags & 0x0200:  # Truncate
                file_flags |= O_TRUNC
            if flags & 0x0400:  # Exclusive
                file_flags |= O_EXCL
            
            # Add binary mode flag for Windows compatibility (like C code does)
            if os.name == 'nt':  # Windows
                file_flags |= O_BINARY
            
            fd = os.open(str(full_path), file_flags, mode)
            session.fd[fd_index] = fd
            
            # Send response with file descriptor index
            response_data = struct.pack('<B', fd_index)
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header, response_data)
            
        except Exception as e:
            logger.error(f"Openfile failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EACCES)
    
    def handle_readblock(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_READBLOCK command"""
        try:
            if len(data) < 3:
                logger.error("Invalid read data")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            fd_index = data[0]
            size = struct.unpack('<H', data[1:3])[0]
            
            if fd_index >= MAX_FD_PER_CONN or session.fd[fd_index] is None:
                logger.error("Invalid file descriptor")
                self.send_error(session, header, TNFS_ERROR.EBADF)
                return None

            # Read data
            data_read = os.read(session.fd[fd_index], min(size, MAX_IOSZ))
            
            # Send response with data
            response_data = struct.pack('<H', len(data_read)) + data_read
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header, response_data)
            
        except Exception as e:
            logger.error(f"Readblock failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EBADF)
    
    def handle_writeblock(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_WRITEBLOCK command"""
        try:
            if len(data) < 3:
                logger.error("Invalid write data")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            fd_index = data[0]
            size = struct.unpack('<H', data[1:3])[0]
            write_data = data[3:3+size]
            
            if fd_index >= MAX_FD_PER_CONN or session.fd[fd_index] is None:
                logger.error("Invalid file descriptor")
                self.send_error(session, header, TNFS_ERROR.EBADF)
                return None

            # Write data
            bytes_written = os.write(session.fd[fd_index], write_data)
            
            # Send response with bytes written
            response_data = struct.pack('<H', bytes_written)
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header, response_data)
            
        except Exception as e:
            logger.error(f"Writeblock failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EBADF)
    
    def handle_closefile(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_CLOSEFILE command"""
        try:
            if len(data) < 1:
                logger.error("No file descriptor index")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            fd_index = data[0]
            if fd_index >= MAX_FD_PER_CONN or session.fd[fd_index] is None:
                logger.error("Invalid file descriptor")
                self.send_error(session, header, TNFS_ERROR.EBADF)
                return None

            # Close file
            os.close(session.fd[fd_index])
            session.fd[fd_index] = None
            
            # Send success response
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header)
            
        except Exception as e:
            logger.error(f"Closefile failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EBADF)
 
    def handle_openfile_old(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_OPENFILE_OLD by translating to new OPENFILE format."""
        try:
            if len(data) < 3:
                logger.error("Invalid old open data")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            translated = bytearray(len(data) + 2)
            # Flags
            translated[0] = data[0]
            # Translate deprecated flags
            if data[1] & 0x01:
                translated[0] &= 0x08
            translated[1] = (data[1] >> 1) & 0xFF
            # Mode = 0644
            translated[2] = 0xA4
            translated[3] = 0x01
            # Filename moves from data[2:] to translated[4:]
            translated[4:] = data[2:]

            self.handle_openfile(header, session, bytes(translated))
        except Exception as e:
            logger.error(f"Openfile(old) failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EACCES)

    def handle_seekfile(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_SEEKFILE command"""
        try:
            if len(data) != 6:
                logger.error("Invalid seek data")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            fd_index = data[0]
            tnfs_whence = data[1]
            offset = struct.unpack('<I', data[2:6])[0]

            if fd_index >= MAX_FD_PER_CONN or session.fd[fd_index] is None:
                logger.error("Invalid file descriptor")
                self.send_error(session, header, TNFS_ERROR.EBADF)
                return None

            if tnfs_whence == 0x00:
                whence = os.SEEK_SET
            elif tnfs_whence == 0x01:
                whence = os.SEEK_CUR
            elif tnfs_whence == 0x02:
                whence = os.SEEK_END
            else:
                logger.error("Invalid whence")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            new_pos = os.lseek(session.fd[fd_index], int(offset), whence)
            response_data = struct.pack('<I', int(new_pos))
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header, response_data)

        except Exception as e:
            logger.error(f"Seekfile failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EBADF)

    def handle_unlinkfile(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_UNLINKFILE command"""
        try:
            if not data or not data.endswith(b'\x00'):
                logger.error("Invalid path")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None
            
            path = data.rstrip(b'\x00').decode('utf-8', errors='ignore')
            full_path = self.root_dir / path.lstrip('/')
            os.unlink(full_path)
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header)
        except FileNotFoundError:
            self.send_error(session, header, TNFS_ERROR.ENOENT)
        except PermissionError:
            self.send_error(session, header, TNFS_ERROR.EACCES)
        except Exception as e:
            logger.error(f"Unlink failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EINVAL)

    def handle_chmodfile(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_CHMODFILE command. Not supported in C implementation; return ENOTSUP."""
        self.send_error(session, header, TNFS_ERROR.ENOTSUP)

    def handle_renamefile(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_RENAMEFILE command"""
        try:
            if not data or data[-1] != 0:
                logger.error("Missing NULL terminator")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None
            
            zero_pos = data.find(b'\x00')
            if zero_pos == -1 or zero_pos >= len(data) - 1:
                logger.error("Invalid rename buffer")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None
            from_path = data[:zero_pos].decode('utf-8', errors='ignore')
            to_path = data[zero_pos + 1:-1].decode('utf-8', errors='ignore')

            full_from = self.root_dir / from_path.lstrip('/')
            full_to = self.root_dir / to_path.lstrip('/')

            os.rename(full_from, full_to)
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header)
        except FileNotFoundError:
            self.send_error(session, header, TNFS_ERROR.ENOENT)
        except PermissionError:
            self.send_error(session, header, TNFS_ERROR.EACCES)
        except Exception as e:
            logger.error(f"Rename failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EINVAL)

    def handle_statfile(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_STATFILE command"""
        try:
            if not data or not data.endswith(b'\x00'):
                logger.error("Invalid stat data")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None

            path = data.rstrip(b'\x00').decode('utf-8', errors='ignore')
            full_path = self.root_dir / path.lstrip('/')
 
            st = os.stat(full_path)
 
            # Pack as per C implementation (TNFS_STAT_SIZE = 0x16 bytes)
            # <H H H I I I I => mode, uid, gid, size, atime, mtime, ctime
            response_data = struct.pack(
                '<HHHIIII',
                int(st.st_mode) & 0xFFFF,
                int(getattr(st, 'st_uid', 0)) & 0xFFFF,
                int(getattr(st, 'st_gid', 0)) & 0xFFFF,
                int(st.st_size) & 0xFFFFFFFF,
                int(st.st_atime) & 0xFFFFFFFF,
                int(st.st_mtime) & 0xFFFFFFFF,
                int(st.st_ctime) & 0xFFFFFFFF,
            )
 
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header, response_data)
 
        except FileNotFoundError:
            self.send_error(session, header, TNFS_ERROR.ENOENT)
        except PermissionError:
            self.send_error(session, header, TNFS_ERROR.EACCES)
        except Exception as e:
            logger.error(f"Statfile failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EINVAL)

    def handle_mkdir(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_MKDIR command"""
        try:
            if not data or not data.endswith(b'\x00'):
                logger.error("Invalid dirname")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None
            
            path = data.rstrip(b'\x00').decode('utf-8', errors='ignore')
            full_path = self.root_dir / path.lstrip('/')
            os.mkdir(full_path, 0o755)
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header)
        except FileExistsError:
            self.send_error(session, header, TNFS_ERROR.EEXIST)
        except FileNotFoundError:
            self.send_error(session, header, TNFS_ERROR.ENOENT)
        except PermissionError:
            self.send_error(session, header, TNFS_ERROR.EACCES)
        except Exception as e:
            logger.error(f"Mkdir failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EINVAL)

    def handle_rmdir(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_RMDIR command"""
        try:
            if not data or not data.endswith(b'\x00'):
                logger.error("Invalid dirname")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None
            
            path = data.rstrip(b'\x00').decode('utf-8', errors='ignore')
            full_path = self.root_dir / path.lstrip('/')
            os.rmdir(full_path)
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header)
        except FileNotFoundError:
            self.send_error(session, header, TNFS_ERROR.ENOENT)
        except OSError as e:
            # ENOTEMPTY or others
            logger.error(f"Rmdir failed: {e}")
            self.send_error(session, header, TNFS_ERROR.ENOTEMPTY if getattr(e, 'errno', None) else TNFS_ERROR.EINVAL)

    def handle_seekdir(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_SEEKDIR command"""
        try:
            if len(data) != 5:
                logger.error("Invalid seekdir data")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None
            
            handle_index = data[0]
            pos = struct.unpack('<I', data[1:5])[0]
            if handle_index >= MAX_DHND_PER_CONN or session.dhandles[handle_index] is None:
                logger.error("Invalid directory handle")
                self.send_error(session, header, TNFS_ERROR.ENOENT)
                return None
            
            dir_handle = session.dhandles[handle_index]
            # Clamp position
            if pos > len(dir_handle.entries):
                pos = len(dir_handle.entries)
            dir_handle.current_index = int(pos)
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header)
        except Exception as e:
            logger.error(f"Seekdir failed: {e}")
            self.send_error(session, header, TNFS_ERROR.ENOENT)

    def handle_telldir(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_TELLDIR command"""
        try:
            if len(data) != 1:
                logger.error("Invalid telldir data")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None
            
            handle_index = data[0]
            if handle_index >= MAX_DHND_PER_CONN or session.dhandles[handle_index] is None:
                logger.error("Invalid directory handle")
                self.send_error(session, header, TNFS_ERROR.ENOENT)
                return None
            
            dir_handle = session.dhandles[handle_index]
            pos = dir_handle.current_index
            response_data = struct.pack('<I', int(pos))
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header, response_data)
        except Exception as e:
            logger.error(f"Telldir failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EBADF)

    def handle_opendirx(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_OPENDIRX command (simplified options)."""
        try:
            if len(data) < 7 or data[-1] != 0:
                logger.error("Invalid opendirx data")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None
            
            diropts = data[0]
            sortopts = data[1]
            maxresults = struct.unpack('<H', data[2:4])[0]
            # pattern and dirpath
            rest = data[4:-1]
            zero = rest.find(b'\x00')
            if zero == -1:
                pattern = None
                dirpath = rest.decode('utf-8', errors='ignore')
            else:
                pattern = rest[:zero].decode('utf-8', errors='ignore') or None
                dirpath = rest[zero + 1:].decode('utf-8', errors='ignore')

            full_path = self.root_dir / dirpath.lstrip('/')
            if not full_path.exists() or not full_path.is_dir():
                self.send_error(session, header, TNFS_ERROR.ENOENT)
                return None

            # Acquire entries
            all_entries = list(Path(full_path).iterdir())
            # Apply pattern (files only unless we choose otherwise) - simplified: apply to names
            if pattern:
                filtered = [p for p in all_entries if fnmatch.fnmatch(p.name, pattern)]
            else:
                filtered = all_entries

            # Sorting simplified: by name
            filtered.sort(key=lambda p: p.name.lower())

            # Apply maxresults as a cap on preloaded list length
            if maxresults:
                filtered = filtered[:maxresults]

            # Find free handle
            handle_index = session.get_free_dhandle()
            if handle_index is None:
                logger.error("No free directory handles")
                self.send_error(session, header, TNFS_ERROR.EMFILE)
                return None
            
            dir_handle = DirectoryHandle(str(full_path))
            dir_handle.entries = filtered
            dir_handle.entry_count = len(filtered)
            dir_handle.current_index = 0
            session.dhandles[handle_index] = dir_handle

            reply = struct.pack('<B', handle_index) + struct.pack('<H', dir_handle.entry_count)
            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header, reply)
        except FileNotFoundError:
            self.send_error(session, header, TNFS_ERROR.ENOENT)
        except Exception as e:
            logger.error(f"Opendirx failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EINVAL)

    def handle_readdirx(self, header: TNFSHeader, session: Session, data: bytes):
        """Handle TNFS_READDIRX command (simplified)."""
        try:
            if len(data) != 2:
                logger.error("Invalid readdirx data")
                self.send_error(session, header, TNFS_ERROR.EINVAL)
                return None
            
            handle_index = data[0]
            req_count = data[1]
            if handle_index >= MAX_DHND_PER_CONN or session.dhandles[handle_index] is None:
                logger.error("Invalid directory handle")
                self.send_error(session, header, TNFS_ERROR.ENOENT)
                return None

            dir_handle = session.dhandles[handle_index]
            start_pos = dir_handle.current_index

            # Prepare reply buffer
            reply = bytearray()
            reply.extend(b"\x00\x00")  # count, status
            reply.extend(struct.pack('<H', start_pos & 0xFFFF))  # dpos (2 bytes)

            count_sent = 0
            total_size = 4

            while dir_handle.current_index < len(dir_handle.entries):
                if req_count != 0 and count_sent >= req_count:
                    break
                entry_path = dir_handle.entries[dir_handle.current_index]
                # Compute entry fields
                try:
                    st = entry_path.stat()
                except Exception:
                    # Skip entries we cannot stat
                    dir_handle.current_index += 1
                    continue
                flags = 0
                if entry_path.is_dir():
                    flags |= DIRENTRY_FLAGS.DIR
                if entry_path.name.startswith('.'):
                    flags |= DIRENTRY_FLAGS.HIDDEN
                name_bytes = entry_path.name.encode('utf-8', errors='ignore') + b'\x00'
                entry_size = 1 + 4 + 4 + 4 + len(name_bytes)
                if total_size + entry_size > TNFS_MAX_PAYLOAD:
                    break
                # Append entry
                reply.append(flags & 0xFF)
                reply.extend(struct.pack('<I', int(st.st_size) if entry_path.is_file() else 0))
                reply.extend(struct.pack('<I', int(st.st_mtime)))
                reply.extend(struct.pack('<I', int(st.st_ctime)))
                reply.extend(name_bytes)
                count_sent += 1
                total_size += entry_size
                dir_handle.current_index += 1

            # EOF flag
            if dir_handle.current_index >= len(dir_handle.entries):
                reply[1] = reply[1] | TNFS_DIRSTATUS_EOF

            reply[0] = count_sent & 0xFF

            response_header = TNFSHeader(sid=session.sid, seqno=header.seqno, cmd=header.cmd, status=TNFS_ERROR.SUCCESS)
            self.send_response(session, response_header, bytes(reply))
        except Exception as e:
            logger.error(f"Readdirx failed: {e}")
            self.send_error(session, header, TNFS_ERROR.EBADF)

    def handle_packet(self, data: bytes, client_addr: Tuple[str, int]):
        """Handle incoming TNFS packet"""
        try:
            if len(data) < TNFS_HEADERSZ:
                logger.warning("Packet too short")
                return

            # Parse header
            header = TNFSHeader.unpack(data)
            header.ipaddr = struct.unpack('<I', socket.inet_aton(client_addr[0]))[0]
            header.port = client_addr[1]

            payload = data[TNFS_HEADERSZ:]

            # Find session
            session = None
            if header.sid != 0:
                session = self.find_session_by_sid(header.sid)
                if session:
                    session.last_contact = time.time()

            # Handle command
            cmd_class = header.cmd & 0xF0

            if cmd_class == CLASS.SESSION:
                if header.cmd == TNFS_CMD.MOUNT:
                    session = self.handle_mount(header, payload, client_addr)
                elif header.cmd == TNFS_CMD.UMOUNT:
                    self.handle_umount(header, session)
                else:
                    logger.warning(f"Unknown session command: {header.cmd}")
                    self.send_error(session, header, TNFS_ERROR.ENOSYS)

            elif cmd_class == CLASS.DIRECTORY:
                if not session:
                    logger.warning("No session for directory command")
                    return

                if header.cmd == TNFS_CMD.OPENDIR:
                    self.handle_opendir(header, session, payload)
                elif header.cmd == TNFS_CMD.READDIR:
                    self.handle_readdir(header, session, payload)
                elif header.cmd == TNFS_CMD.CLOSEDIR:
                    self.handle_closedir(header, session, payload)
                elif header.cmd == TNFS_CMD.MKDIR:
                    self.handle_mkdir(header, session, payload)
                elif header.cmd == TNFS_CMD.RMDIR:
                    self.handle_rmdir(header, session, payload)
                elif header.cmd == TNFS_CMD.TELLDIR:
                    self.handle_telldir(header, session, payload)
                elif header.cmd == TNFS_CMD.SEEKDIR:
                    self.handle_seekdir(header, session, payload)
                elif header.cmd == TNFS_CMD.OPENDIRX:
                    self.handle_opendirx(header, session, payload)
                elif header.cmd == TNFS_CMD.READDIRX:
                    self.handle_readdirx(header, session, payload)
                else:
                    logger.warning(f"Unsupported directory command: {header.cmd}")
                    self.send_error(session, header, TNFS_ERROR.ENOSYS)

            elif cmd_class == CLASS.FILE:
                if not session:
                    logger.warning("No session for file command")
                    return

                if header.cmd == TNFS_CMD.OPENFILE:
                    self.handle_openfile(header, session, payload)
                elif header.cmd == TNFS_CMD.READBLOCK:
                    self.handle_readblock(header, session, payload)
                elif header.cmd == TNFS_CMD.WRITEBLOCK:
                    self.handle_writeblock(header, session, payload)
                elif header.cmd == TNFS_CMD.CLOSEFILE:
                    self.handle_closefile(header, session, payload)
                elif header.cmd == TNFS_CMD.STATFILE:
                    self.handle_statfile(header, session, payload)
                elif header.cmd == TNFS_CMD.OPENFILE_OLD:
                    self.handle_openfile_old(header, session, payload)
                elif header.cmd == TNFS_CMD.SEEKFILE:
                    self.handle_seekfile(header, session, payload)
                elif header.cmd == TNFS_CMD.UNLINKFILE:
                    self.handle_unlinkfile(header, session, payload)
                elif header.cmd == TNFS_CMD.CHMODFILE:
                    self.handle_chmodfile(header, session, payload)
                elif header.cmd == TNFS_CMD.RENAMEFILE:
                    self.handle_renamefile(header, session, payload)
                else:
                    logger.warning(f"Unsupported file command: {header.cmd}")
                    self.send_error(session, header, TNFS_ERROR.ENOSYS)
            else:
                logger.warning(f"Unknown command class: {cmd_class}")
                self.send_error(session, header, TNFS_ERROR.ENOSYS)

        except Exception as e:
            logger.error(f"Error handling packet: {e}")
    
    def run(self):
        """Main daemon loop"""
        self.setup_sockets()
        self.running = True
        
        logger.info(f"TNFS daemon version 20.1115.2 starting on port {self.port}")
        logger.info(f"Root directory: {self.root_dir}")
        
        try:
            while self.running:
                # Cleanup expired sessions
                self.cleanup_expired_sessions()
                
                # Select on sockets
                readable, _, _ = select.select([self.udp_socket, self.tcp_socket], [], [], 1.0)
                
                for sock in readable:
                    if sock == self.udp_socket:
                        # Handle UDP packet
                        try:
                            data, client_addr = self.udp_socket.recvfrom(MAXMSGSZ)
                            self.handle_packet(data, client_addr)
                        except Exception as e:
                            logger.error(f"UDP receive error: {e}")
                    
                    elif sock == self.tcp_socket:
                        # Handle TCP connection
                        try:
                            client_sock, client_addr = self.tcp_socket.accept()
                            logger.info(f"TCP connection from {client_addr[0]}:{client_addr[1]}")
                            # TODO: Implement TCP handling
                        except Exception as e:
                            logger.error(f"TCP accept error: {e}")
                            
        except KeyboardInterrupt:
            logger.info("Shutting down TNFS daemon...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        self.running = False
        
        # Close all sessions
        for session in list(self.sessions.values()):
            self.remove_session(session)
        
        # Close sockets
        if self.udp_socket:
            self.udp_socket.close()
        if self.tcp_socket:
            self.tcp_socket.close()
        
        logger.info("TNFS daemon stopped")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='TNFS (The Network File System) Daemon')
    parser.add_argument('root_dir', help='Root directory to serve')
    parser.add_argument('-p', '--port', type=int, default=TNFSD_PORT, help=f'Port to listen on (default: {TNFSD_PORT})')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        daemon = TNFSDaemon(args.root_dir, args.port)
        daemon.run()
    except Exception as e:
        logger.error(f"Failed to start TNFS daemon: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 