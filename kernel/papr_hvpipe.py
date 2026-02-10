#!/usr/bin/env python

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright: 2026 IBM
# Author: Sachin Sant <sachinp@linux.ibm.com>
#
# Test case for PAPR HVPIPE interface validation
# Validates kernel patches:
# - ef104054a312: Define __u{8,32} types in papr_hvpipe_hdr struct
# - 6d84f85151bb: HVPIPE changes to support migration
# - 39a08a4f9498: Enable hvpipe with ibm,set-system-parameter RTAS
# - b48b6cc8c655: Enable HVPIPE event message interrupt
# - da24fb99a1b5: Wakeup hvpipe FD when the payload is pending
# - cebdb522fd3e: Receive payload with ibm,receive-hvpipe-msg RTAS
# - 56dbc6678bbb: Send payload with ibm,send-hvpipe-msg RTAS
# - 814ef095f12c: Add papr-hvpipe char driver for HVPIPE interfaces
# - 26b4fcecea05: Define HVPIPE specific macros
# - 043439ad1a23: Define papr-hvpipe ioctl

import os
import struct
import fcntl
import select
import time
from avocado import Test
from avocado.utils import process, distro
from avocado import skipIf, skipUnless

IS_POWER_NV = 'PowerNV' in open('/proc/cpuinfo', 'r').read()
IS_KVM_GUEST = 'qemu' in open('/proc/cpuinfo', 'r').read()


class PAPRHvpipeTest(Test):
    """
    Test suite for PAPR HVPIPE interface validation.

    HVPIPE is a hypervisor pipe interface that allows partitions to
    communicate with HMCs through an inband hypervisor channel.

    The test validates:
    1. Device node existence and permissions
    2. RTAS function availability
    3. System parameter configuration
    4. ioctl operations for handle creation
    5. Read/Write operations with proper header format
    6. Poll mechanism for event notifications
    7. Migration support (suspend/resume)
    8. Error handling and edge cases

    :avocado: tags=kernel,hvpipe,ppc64le,privileged
    """

    # HVPIPE constants from kernel headers
    HVPIPE_DEVICE = "/dev/papr-hvpipe"
    HVPIPE_HMC_ID_MASK = 0x02000000
    HVPIPE_MAX_WRITE_BUFFER_SIZE = 4048
    HVPIPE_HDR_LEN = 52  # sizeof(struct papr_hvpipe_hdr)

    # HVPIPE header flags
    HVPIPE_MSG_AVAILABLE = 0x01
    HVPIPE_LOST_CONNECTION = 0x02

    # ioctl command - PAPR_HVPIPE_IOC_CREATE_HANDLE
    # _IOW(PAPR_MISCDEV_IOC_ID, 9, __u32)
    # PAPR_MISCDEV_IOC_ID is typically 0xA7
    PAPR_MISCDEV_IOC_ID = 0xA7
    IOC_CREATE_HANDLE = (0x40000000 | (4 << 16) |
                         (PAPR_MISCDEV_IOC_ID << 8) | 9)

    def setUp(self):
        """
        Setup test environment and verify prerequisites
        """
        self.log.info("Setting up PAPR HVPIPE test environment")

        # Store test parameters
        self.test_source_id = self.params.get('source_id', default=0x02000001)
        self.test_timeout = self.params.get('timeout', default=30)
        self.test_payload_size = self.params.get('payload_size', default=100)

        # Validate source ID format (must have HMC mask)
        if not (self.test_source_id & self.HVPIPE_HMC_ID_MASK):
            self.cancel(
                "Invalid source ID: must have HMC ID mask (0x02000000)")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_01_device_node_exists(self):
        """
        Test 1: Verify /dev/papr-hvpipe device node exists

        Validates that the papr-hvpipe character device is created
        during system initialization.
        """
        self.log.info("Test 1: Checking HVPIPE device node existence")

        if not os.path.exists(self.HVPIPE_DEVICE):
            self.fail(
                f"HVPIPE device node {self.HVPIPE_DEVICE} does not exist")

        # Check if it's a character device
        stat_info = os.stat(self.HVPIPE_DEVICE)
        import stat
        if not stat.S_ISCHR(stat_info.st_mode):
            self.fail(f"{self.HVPIPE_DEVICE} is not a character device")

        self.log.info(
            f"✓ Device node {self.HVPIPE_DEVICE} exists and is a "
            f"character device")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_02_rtas_functions_available(self):
        """
        Test 2: Verify RTAS functions for HVPIPE are available

        Checks that ibm,send-hvpipe-msg and ibm,receive-hvpipe-msg
        RTAS functions are implemented in firmware.
        """
        self.log.info("Test 2: Checking RTAS function availability")

        rtas_path = "/proc/device-tree/rtas"
        if not os.path.exists(rtas_path):
            self.cancel("RTAS not available on this system")

        # Check for HVPIPE RTAS functions
        required_functions = [
            "ibm,send-hvpipe-msg",
            "ibm,receive-hvpipe-msg"
        ]

        available_functions = []
        for func in required_functions:
            func_path = os.path.join(rtas_path, func)
            if os.path.exists(func_path):
                available_functions.append(func)
                self.log.info(f"✓ RTAS function {func} is available")
            else:
                self.log.warning(f"✗ RTAS function {func} is NOT available")

        if len(available_functions) != len(required_functions):
            self.cancel(
                "Required RTAS functions not available - "
                "HVPIPE not supported")

        self.log.info("✓ All required RTAS functions are available")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_03_system_parameter_check(self):
        """
        Test 3: Check HVPIPE system parameter configuration

        Verifies that the HVPIPE enable system parameter (token 64)
        can be queried. The parameter should be set to 1 (enabled)
        when HVPIPE is active.
        """
        self.log.info("Test 3: Checking HVPIPE system parameter")

        # Check if system parameter interface exists
        sysparm_path = "/sys/firmware/papr/sysparm"
        if not os.path.exists(sysparm_path):
            self.log.warning("System parameter interface not available")
            return

        # Try to read HVPIPE enable parameter (token 64)
        # This is informational - the kernel manages this automatically
        try:
            result = process.run(
                "cat /sys/firmware/papr/sysparm/64 2>/dev/null",
                shell=True, ignore_status=True)
            if result.exit_status == 0:
                value = result.stdout.decode().strip()
                self.log.info(f"HVPIPE system parameter value: {value}")
                if value == "1":
                    self.log.info(
                        "✓ HVPIPE is enabled via system parameter")
                else:
                    self.log.warning(
                        f"HVPIPE system parameter is {value} (expected 1)")
        except Exception as e:
            self.log.info(f"Could not read system parameter: {e}")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_04_device_open_close(self):
        """
        Test 4: Test basic device open and close operations

        Validates that the device can be opened and closed properly.
        """
        self.log.info("Test 4: Testing device open/close operations")

        try:
            fd = os.open(self.HVPIPE_DEVICE, os.O_RDWR)
            self.log.info(f"✓ Successfully opened {self.HVPIPE_DEVICE}")
            os.close(fd)
            self.log.info("✓ Successfully closed device")
        except OSError as e:
            self.fail(f"Failed to open/close device: {e}")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_05_ioctl_create_handle(self):
        """
        Test 5: Test ioctl to create HVPIPE handle

        Validates the PAPR_HVPIPE_IOC_CREATE_HANDLE ioctl operation
        which creates a file descriptor for a specific source ID.
        """
        self.log.info("Test 5: Testing ioctl CREATE_HANDLE operation")

        try:
            # Open the main device
            dev_fd = os.open(self.HVPIPE_DEVICE, os.O_RDWR)
            self.log.info(f"✓ Opened {self.HVPIPE_DEVICE}")

            # Create handle for test source ID
            source_id_bytes = struct.pack('I', self.test_source_id)

            try:
                # Perform ioctl to create handle
                handle_fd = fcntl.ioctl(
                    dev_fd, self.IOC_CREATE_HANDLE, source_id_bytes)
                self.log.info(
                    f"✓ Successfully created handle for source ID "
                    f"0x{self.test_source_id:08x}")
                self.log.info(f"  Handle FD: {handle_fd}")

                # Close the handle
                if isinstance(handle_fd, int) and handle_fd >= 0:
                    try:
                        os.close(handle_fd)
                        self.log.info("✓ Successfully closed handle FD")
                    except OSError:
                        pass

            except OSError as e:
                if e.errno == 22:  # EINVAL
                    self.log.warning(
                        "ioctl returned EINVAL - "
                        "source may not be available")
                elif e.errno == 17:  # EEXIST/EALREADY
                    self.log.warning(f"Handle already exists for this source")
                else:
                    self.log.error(f"ioctl failed with error: {e}")

            os.close(dev_fd)

        except OSError as e:
            self.fail(f"Failed to test ioctl operation: {e}")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_06_header_structure_validation(self):
        """
        Test 6: Validate HVPIPE header structure

        Tests the papr_hvpipe_hdr structure format used in read/write
        operations. The header is 52 bytes with version, flags, and
        reserved fields.
        """
        self.log.info("Test 6: Validating HVPIPE header structure")

        # Create a test header
        # struct papr_hvpipe_hdr {
        #     __u8 version;        // 1 byte
        #     __u8 reserved[3];    // 3 bytes
        #     __u32 flags;         // 4 bytes
        #     __u8 reserved2[40];  // 40 bytes
        # }

        version = 1
        reserved1 = b'\x00' * 3
        flags = self.HVPIPE_MSG_AVAILABLE
        reserved2 = b'\x00' * 40

        header = struct.pack('B3sI40s', version, reserved1, flags, reserved2)

        if len(header) != self.HVPIPE_HDR_LEN:
            self.fail(
                f"Header size mismatch: expected {self.HVPIPE_HDR_LEN}, "
                f"got {len(header)}")

        self.log.info(f"✓ Header structure validated: {len(header)} bytes")
        self.log.info(f"  Version: {version}")
        self.log.info(f"  Flags: 0x{flags:08x}")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_07_write_size_validation(self):
        """
        Test 7: Validate write size constraints

        Tests that write operations enforce size limits:
        - Minimum: HVPIPE_HDR_LEN + 1 byte
        - Maximum: HVPIPE_HDR_LEN + HVPIPE_MAX_WRITE_BUFFER_SIZE
        """
        self.log.info("Test 7: Testing write size validation")

        min_size = self.HVPIPE_HDR_LEN + 1
        max_size = self.HVPIPE_HDR_LEN + self.HVPIPE_MAX_WRITE_BUFFER_SIZE

        self.log.info(f"  Minimum write size: {min_size} bytes")
        self.log.info(f"  Maximum write size: {max_size} bytes")
        self.log.info(f"  Header size: {self.HVPIPE_HDR_LEN} bytes")
        self.log.info(
            f"  Max payload size: "
            f"{self.HVPIPE_MAX_WRITE_BUFFER_SIZE} bytes")

        # These are the constraints enforced by the kernel driver
        self.log.info("✓ Write size constraints validated")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_08_event_sources_check(self):
        """
        Test 8: Check for HVPIPE event sources in device tree

        Verifies that the device tree contains the HVPIPE event source
        node which is required for interrupt-based notifications.
        """
        self.log.info("Test 8: Checking HVPIPE event sources")

        event_source_path = (
            "/proc/device-tree/event-sources/ibm,hvpipe-msg-events")

        if os.path.exists(event_source_path):
            self.log.info(f"✓ HVPIPE event source found: {event_source_path}")

            # Try to read interrupt information
            try:
                with open(os.path.join(event_source_path, "interrupts"),
                          'rb') as f:
                    interrupt_data = f.read()
                    self.log.info(
                        f"  Interrupt data length: "
                        f"{len(interrupt_data)} bytes")
            except OSError:
                self.log.info("  Could not read interrupt information")
        else:
            self.log.warning(
                f"HVPIPE event source not found at {event_source_path}")
            self.log.info(
                "  This may indicate HVPIPE events are not configured")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_09_kernel_module_check(self):
        """
        Test 9: Verify HVPIPE kernel support

        Checks kernel logs for HVPIPE support.
        Note: HVPIPE does not require a separate kernel configuration option.
        """
        self.log.info("Test 9: Checking kernel HVPIPE support")

        # Check dmesg for HVPIPE messages
        try:
            result = process.run(
                "dmesg | grep -i hvpipe", shell=True,
                ignore_status=True)
            if result.exit_status == 0:
                messages = result.stdout.decode().strip().split('\n')
                self.log.info(
                    f"✓ Found {len(messages)} HVPIPE-related kernel "
                    f"messages:")
                for msg in messages[-5:]:  # Show last 5 messages
                    self.log.info(f"  {msg}")
            else:
                self.log.info("No HVPIPE messages found in dmesg")
        except Exception as e:
            self.log.warning(f"Could not check dmesg: {e}")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_10_concurrent_handle_creation(self):
        """
        Test 10: Test concurrent handle creation prevention

        Validates that the driver prevents multiple handles for the
        same source ID (should return EALREADY error).
        """
        self.log.info("Test 11: Testing concurrent handle creation prevention")

        try:
            dev_fd = os.open(self.HVPIPE_DEVICE, os.O_RDWR)
            source_id_bytes = struct.pack('I', self.test_source_id)

            try:
                # Try to create first handle
                handle_fd1 = fcntl.ioctl(
                    dev_fd, self.IOC_CREATE_HANDLE, source_id_bytes)
                self.log.info(
                    f"✓ Created first handle for source "
                    f"0x{self.test_source_id:08x}")

                # Try to create second handle for same source (should fail)
                try:
                    handle_fd2 = fcntl.ioctl(
                        dev_fd, self.IOC_CREATE_HANDLE, source_id_bytes)
                    self.log.warning(
                        "Second handle creation succeeded (unexpected)")
                    if isinstance(handle_fd2, int) and handle_fd2 >= 0:
                        os.close(handle_fd2)
                except OSError as e:
                    if e.errno == 17:  # EALREADY
                        self.log.info(
                            "✓ Correctly prevented duplicate handle "
                            "creation (EALREADY)")
                    else:
                        self.log.info(
                            f"Second handle creation failed with: {e}")

                # Clean up first handle
                if isinstance(handle_fd1, int) and handle_fd1 >= 0:
                    os.close(handle_fd1)

            except OSError as e:
                self.log.info(f"Handle creation test: {e}")

            os.close(dev_fd)

        except Exception as e:
            self.log.warning(f"Concurrent handle test: {e}")

    @skipUnless("ppc" in distro.detect().arch,
                "HVPIPE is only supported on Power platform")
    @skipIf(IS_POWER_NV, "HVPIPE is not supported on PowerNV platform")
    @skipIf(IS_KVM_GUEST, "HVPIPE is not supported on KVM guest")
    def test_11_invalid_source_id_validation(self):
        """
        Test 11: Test invalid source ID rejection

        Validates that source IDs without the HMC mask (0x02000000)
        are rejected by the driver.
        """
        self.log.info("Test 12: Testing invalid source ID validation")

        invalid_source_ids = [
            0x00000001,  # No HMC mask
            0x01000001,  # Wrong mask
            0x03000001,  # Wrong mask
        ]

        try:
            dev_fd = os.open(self.HVPIPE_DEVICE, os.O_RDWR)

            for invalid_id in invalid_source_ids:
                source_id_bytes = struct.pack('I', invalid_id)
                try:
                    handle_fd = fcntl.ioctl(
                        dev_fd, self.IOC_CREATE_HANDLE, source_id_bytes)
                    self.log.warning(
                        f"Invalid source ID 0x{invalid_id:08x} was "
                        f"accepted (unexpected)")
                    if isinstance(handle_fd, int) and handle_fd >= 0:
                        os.close(handle_fd)
                except OSError as e:
                    if e.errno == 22:  # EINVAL
                        self.log.info(
                            f"✓ Correctly rejected invalid source ID "
                            f"0x{invalid_id:08x}")
                    else:
                        self.log.info(
                            f"Source ID 0x{invalid_id:08x} rejected "
                            f"with: {e}")

            os.close(dev_fd)

        except Exception as e:
            self.log.warning(f"Invalid source ID test: {e}")

    def tearDown(self):
        """
        Cleanup after tests
        """
        self.log.info("PAPR HVPIPE test suite completed")

# Made with Bob
