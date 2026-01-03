# SPDX-License-Identifier: GPL-2.0-or-later
"""
Client ID Protocol Wrapper

Provides multi-client isolation for keyboard protocol commands. Each client
gets a unique ID from the keyboard, allowing multiple applications to
communicate simultaneously without interference.

Usage:
    wrapper = ClientWrapper(dev, hid_send)

    # For Viable commands
    response = wrapper.send_viable(command_bytes)

    # For VIA commands
    response = wrapper.send_via(command_bytes)
"""

import os
import struct
import time
import logging

from protocol.constants import VIABLE_PREFIX

# Protocol constants
WRAPPER_PREFIX = 0xDD
CLIENT_ID_BOOTSTRAP = 0x00000000
CLIENT_ID_ERROR = 0xFFFFFFFF

# Error codes
CLIENT_ERR_INVALID_ID = 0x01
CLIENT_ERR_NO_IDS = 0x02
CLIENT_ERR_UNKNOWN_PROTO = 0x03

# Bootstrap nonce size
NONCE_SIZE = 20


class ClientWrapperError(Exception):
    """Exception raised for client wrapper protocol errors."""
    pass


class ClientWrapper:
    """
    Manages client ID lifecycle and wraps Viable protocol commands.

    The wrapper protocol allows multiple applications to communicate with
    the same keyboard simultaneously. Each application gets a unique client ID,
    and the keyboard includes this ID in responses so apps can identify
    which responses are theirs.
    """

    def __init__(self, dev, hid_send_fn, msg_len=32):
        """
        Initialize the client wrapper.

        Args:
            dev: HID device handle
            hid_send_fn: Function to send/receive HID messages (dev, msg, retries) -> response
            msg_len: HID message length (default 32)
        """
        self.dev = dev
        self.hid_send = hid_send_fn
        self.msg_len = msg_len
        self.client_id = None
        self.ttl_seconds = 120
        self.last_bootstrap = 0
        self._renewal_threshold = 0.70  # Renew at 70% of TTL

    def reset(self):
        """Reset client state (call on device disconnect/reconnect)."""
        self.client_id = None
        self.last_bootstrap = 0

    def _needs_renewal(self):
        """Check if client ID needs renewal."""
        if self.client_id is None:
            return True
        age = time.time() - self.last_bootstrap
        return age >= (self.ttl_seconds * self._renewal_threshold)

    def bootstrap(self, retries=5):
        """
        Bootstrap to get a new client ID from the keyboard.

        The bootstrap request includes a random nonce that the keyboard
        echoes back, allowing us to verify the response is for our request.

        Args:
            retries: Number of retry attempts

        Returns:
            True on success

        Raises:
            ClientWrapperError: On bootstrap failure
        """
        nonce = os.urandom(NONCE_SIZE)

        # Bootstrap request: [0xDD] [0x00000000] [nonce:20]
        msg = struct.pack("<BI", WRAPPER_PREFIX, CLIENT_ID_BOOTSTRAP) + nonce
        msg = msg + b"\x00" * (self.msg_len - len(msg))

        for attempt in range(retries):
            try:
                # Use low-level write/read for bootstrap
                written = self.dev.write(b"\x00" + msg)
                if written != self.msg_len + 1:
                    logging.debug("bootstrap: write returned %d, expected %d", written, self.msg_len + 1)
                    time.sleep(0.1)
                    continue

                response = bytes(self.dev.read(self.msg_len, timeout_ms=500))
                if not response:
                    logging.debug("bootstrap: no response")
                    time.sleep(0.1)
                    continue

                # Verify response format: [0xDD] [0x00000000] [nonce:20] [client_id:4] [ttl:2]
                if response[0] != WRAPPER_PREFIX:
                    logging.debug("bootstrap: unexpected prefix 0x%02X", response[0])
                    continue

                resp_id = struct.unpack("<I", response[1:5])[0]
                if resp_id != CLIENT_ID_BOOTSTRAP:
                    # Not our response - might be another client's response
                    logging.debug("bootstrap: response for different client 0x%08X", resp_id)
                    continue

                # Verify nonce echo
                resp_nonce = response[5:5 + NONCE_SIZE]
                if resp_nonce != nonce:
                    logging.debug("bootstrap: nonce mismatch")
                    continue

                # Extract client ID
                new_id = struct.unpack("<I", response[25:29])[0]
                if new_id == CLIENT_ID_ERROR:
                    error_code = response[29]
                    raise ClientWrapperError(f"Bootstrap failed with error code {error_code}")

                # Extract TTL
                ttl = struct.unpack("<H", response[29:31])[0]

                self.client_id = new_id
                self.ttl_seconds = ttl
                self.last_bootstrap = time.time()
                logging.debug("bootstrap: got client ID 0x%08X, TTL %d seconds", new_id, ttl)
                return True

            except OSError as e:
                logging.debug("bootstrap attempt %d failed: %s", attempt + 1, e)
                time.sleep(0.1)

        raise ClientWrapperError("Bootstrap failed after all retries")

    def _ensure_client_id(self):
        """Ensure we have a valid client ID, bootstrapping if needed."""
        if self._needs_renewal():
            self.bootstrap()

    def send_viable(self, command, retries=20, read_timeout_ms=500):
        """
        Send a Viable protocol command wrapped with client ID.

        The wrapper adds 6 bytes of overhead:
        - 1 byte: wrapper prefix (0xDD)
        - 4 bytes: client ID
        - 1 byte: protocol (0xDF for Viable)

        This leaves 26 bytes for the inner command (from 32 byte packet).

        Args:
            command: Raw Viable command bytes (WITHOUT 0xDF prefix)
            retries: Number of send retry attempts (for write failures)
            read_timeout_ms: Timeout for each read attempt

        Returns:
            Response bytes (inner payload, without wrapper header)

        Raises:
            ClientWrapperError: On protocol errors
        """
        self._ensure_client_id()

        # Wrapped request: [0xDD] [client_id:4] [0xDF] [command...]
        msg = struct.pack("<BI", WRAPPER_PREFIX, self.client_id) + bytes([VIABLE_PREFIX]) + command
        msg = msg + b"\x00" * (self.msg_len - len(msg))

        if len(msg) > self.msg_len:
            raise ClientWrapperError(f"Command too long: {len(msg)} > {self.msg_len}")

        for attempt in range(retries):
            try:
                # Send the request ONCE
                written = self.dev.write(b"\x00" + msg)
                if written != self.msg_len + 1:
                    logging.debug("send_viable: write failed, attempt %d", attempt + 1)
                    time.sleep(0.1)
                    continue

                # Read responses until we get ours (discard other clients' responses)
                for _ in range(50):  # Max reads before giving up
                    response = bytes(self.dev.read(self.msg_len, timeout_ms=read_timeout_ms))
                    if not response:
                        break  # Timeout - retry send

                    # Verify wrapper header
                    if response[0] != WRAPPER_PREFIX:
                        logging.debug("send_viable: unexpected response prefix 0x%02X", response[0])
                        continue  # Read again

                    resp_id = struct.unpack("<I", response[1:5])[0]

                    # Check if it's our response
                    if resp_id != self.client_id:
                        # Not our response - discard and read again
                        logging.debug("send_viable: discarding response for client 0x%08X (we are 0x%08X)",
                                      resp_id, self.client_id)
                        continue

                    # Check for error response
                    if response[5] == 0xFF:  # Error protocol
                        error_code = response[6]
                        if error_code == CLIENT_ERR_INVALID_ID:
                            # Our ID expired - re-bootstrap and retry send
                            logging.debug("send_viable: client ID expired, re-bootstrapping")
                            self.bootstrap()
                            msg = struct.pack("<BI", WRAPPER_PREFIX, self.client_id) + bytes([VIABLE_PREFIX]) + command
                            msg = msg + b"\x00" * (self.msg_len - len(msg))
                            break  # Retry send with new ID
                        elif error_code == CLIENT_ERR_UNKNOWN_PROTO:
                            raise ClientWrapperError("Unknown protocol - wrapped VIA not supported")
                        else:
                            raise ClientWrapperError(f"Protocol error code {error_code}")

                    # Verify protocol byte
                    if response[5] != VIABLE_PREFIX:
                        logging.debug("send_viable: unexpected protocol 0x%02X", response[5])
                        continue  # Read again

                    # Return inner response (skip 5-byte wrapper header, keep protocol byte)
                    return response[5:]

            except OSError as e:
                logging.debug("send_viable attempt %d failed: %s", attempt + 1, e)
                time.sleep(0.1)

        raise ClientWrapperError("Failed to communicate after all retries")

    def send_via(self, command, retries=20, read_timeout_ms=500):
        """
        Send a VIA protocol command wrapped with client ID.

        The wrapper adds 6 bytes of overhead:
        - 1 byte: wrapper prefix (0xDD)
        - 4 bytes: client ID
        - 1 byte: protocol (0xFE for VIA)

        This leaves 26 bytes for the inner command (from 32 byte packet).

        Args:
            command: Raw VIA command bytes
            retries: Number of send retry attempts (for write failures)
            read_timeout_ms: Timeout for each read attempt

        Returns:
            Response bytes (VIA response, matching unwrapped format)

        Raises:
            ClientWrapperError: On protocol errors
        """
        VIA_PROTOCOL = 0xFE

        self._ensure_client_id()

        # Wrapped request: [0xDD] [client_id:4] [0xFE] [command...]
        msg = struct.pack("<BIB", WRAPPER_PREFIX, self.client_id, VIA_PROTOCOL) + command
        msg = msg + b"\x00" * (self.msg_len - len(msg))

        if len(msg) > self.msg_len:
            raise ClientWrapperError(f"Command too long: {len(msg)} > {self.msg_len}")

        for attempt in range(retries):
            try:
                # Send the request ONCE
                written = self.dev.write(b"\x00" + msg)
                if written != self.msg_len + 1:
                    logging.debug("send_via: write failed, attempt %d", attempt + 1)
                    time.sleep(0.1)
                    continue

                # Read responses until we get ours (discard other clients' responses)
                for _ in range(50):  # Max reads before giving up
                    response = bytes(self.dev.read(self.msg_len, timeout_ms=read_timeout_ms))
                    if not response:
                        break  # Timeout - retry send

                    # Verify wrapper header
                    if response[0] != WRAPPER_PREFIX:
                        logging.debug("send_via: unexpected response prefix 0x%02X", response[0])
                        continue  # Read again

                    resp_id = struct.unpack("<I", response[1:5])[0]

                    # Check if it's our response
                    if resp_id != self.client_id:
                        # Not our response - discard and read again
                        logging.debug("send_via: discarding response for client 0x%08X (we are 0x%08X)",
                                      resp_id, self.client_id)
                        continue

                    # Check for error response
                    if response[5] == 0xFF:  # Error protocol
                        error_code = response[6]
                        if error_code == CLIENT_ERR_INVALID_ID:
                            # Our ID expired - re-bootstrap and retry send
                            logging.debug("send_via: client ID expired, re-bootstrapping")
                            self.bootstrap()
                            msg = struct.pack("<BIB", WRAPPER_PREFIX, self.client_id, VIA_PROTOCOL) + command
                            msg = msg + b"\x00" * (self.msg_len - len(msg))
                            break  # Retry send with new ID
                        else:
                            raise ClientWrapperError(f"Protocol error code {error_code}")

                    # Verify protocol byte
                    if response[5] != VIA_PROTOCOL:
                        logging.debug("send_via: unexpected protocol 0x%02X", response[5])
                        continue  # Read again

                    # Return inner response (skip 6-byte wrapper header)
                    return response[6:]

            except OSError as e:
                logging.debug("send_via attempt %d failed: %s", attempt + 1, e)
                time.sleep(0.1)

        raise ClientWrapperError("Failed to communicate after all retries")
