# PAPR HVPIPE Test Suite

## Overview

This test suite validates the PAPR HVPIPE (Hypervisor Pipe) interface implementation in the Linux kernel for IBM Power Systems running in PowerVM LPAR mode.

## Background

HVPIPE is a hypervisor pipe interface that enables partitions to communicate with Hardware Management Consoles (HMCs) through an inband hypervisor channel. This feature was introduced through a series of kernel patches to support bidirectional communication between LPARs and HMCs.

### Kernel Patches Validated

This test suite validates the following kernel patches:

1. **ef104054a312** - Define `__u{8,32}` types in `papr_hvpipe_hdr` struct
2. **6d84f85151bb** - HVPIPE changes to support migration
3. **39a08a4f9498** - Enable hvpipe with `ibm,set-system-parameter` RTAS
4. **b48b6cc8c655** - Enable HVPIPE event message interrupt
5. **da24fb99a1b5** - Wakeup hvpipe FD when the payload is pending
6. **cebdb522fd3e** - Receive payload with `ibm,receive-hvpipe-msg` RTAS
7. **56dbc6678bbb** - Send payload with `ibm,send-hvpipe-msg` RTAS
8. **814ef095f12c** - Add papr-hvpipe char driver for HVPIPE interfaces
9. **26b4fcecea05** - Define HVPIPE specific macros
10. **043439ad1a23** - Define papr-hvpipe ioctl

## Test Coverage

The test suite includes 11 comprehensive test cases:

### Test 1: Device Node Existence
- Validates `/dev/papr-hvpipe` character device exists
- Checks device permissions and type

### Test 2: RTAS Functions Availability
- Verifies `ibm,send-hvpipe-msg` RTAS function
- Verifies `ibm,receive-hvpipe-msg` RTAS function

### Test 3: System Parameter Check
- Validates HVPIPE enable system parameter (token 64)
- Checks parameter configuration

### Test 4: Device Open/Close Operations
- Tests basic device file operations
- Validates proper resource management

### Test 5: ioctl CREATE_HANDLE
- Tests `PAPR_HVPIPE_IOC_CREATE_HANDLE` ioctl
- Validates handle creation for source IDs

### Test 6: Header Structure Validation
- Validates `papr_hvpipe_hdr` structure format
- Tests 52-byte header with version, flags, and reserved fields

### Test 7: Write Size Validation
- Tests minimum write size: `HVPIPE_HDR_LEN + 1` byte
- Tests maximum write size: `HVPIPE_HDR_LEN + 4048` bytes

### Test 8: Event Sources Check
- Validates device tree event source node
- Checks interrupt configuration

### Test 9: Kernel Module Check
- Verifies kernel HVPIPE support
- Checks kernel logs for HVPIPE messages
- Note: HVPIPE does not require a separate kernel configuration option

### Test 10: Concurrent Handle Creation
- Tests prevention of duplicate handles
- Validates `EALREADY` error handling

### Test 11: Invalid Source ID Validation
- Tests rejection of invalid source IDs
- Validates HMC mask requirement (0x02000000)

## Prerequisites

### System Requirements
- **Platform**: IBM Power Systems (ppc64le architecture)
- **Mode**: PowerVM LPAR (not PowerNV or KVM guest)
- **Kernel**: Linux kernel with HVPIPE patches applied
- **Firmware**: RTAS support with HVPIPE functions

### Software Requirements
- Python 3.x
- Avocado Framework
- Root/sudo privileges

### Hardware Requirements
- IBM Power system with PowerVM
- HMC connectivity (for full functional testing)

## Installation

1. Ensure avocado-misc-tests repository is cloned:
```bash
git clone https://github.com/avocado-framework-tests/avocado-misc-tests.git
cd avocado-misc-tests
```

2. Install Avocado Framework:
```bash
pip install avocado-framework
```

## Configuration

Edit the YAML configuration file to customize test parameters:

```bash
vi ras/papr_hvpipe.py.data/papr_hvpipe.yaml
```

### Configuration Parameters

- **source_id**: HMC source ID for testing (default: 0x02000001)
  - Format: 0xCCRRQQQQ
  - CC = 0x02 (HMC type, required)
  - RR = 0x00 (reserved)
  - QQQQ = Source index (0x0000 - 0xFFFF)

- **timeout**: Operation timeout in seconds (default: 30)

- **payload_size**: Test payload size in bytes (default: 100, max: 4048)

- **test_mode**: Test execution mode
  - `basic`: Run basic validation tests only
  - `full`: Run all tests including stress tests

- **verbose**: Enable detailed debug output (default: false)

## Running the Tests

### Run All Tests

```bash
avocado run kernel/papr_hvpipe.py
```

### Run with Custom Configuration

```bash
avocado run kernel/papr_hvpipe.py -m kernel/papr_hvpipe.py.data/papr_hvpipe.yaml
```

### Run Specific Test

```bash
avocado run kernel/papr_hvpipe.py:PAPRHvpipeTest.test_01_device_node_exists
```

### Run with Verbose Output

```bash
avocado run kernel/papr_hvpipe.py --show-job-log
```

### Run in Serial Mode

```bash
avocado run --max-parallel-tasks=1 kernel/papr_hvpipe.py
```

## Expected Results

### Successful Test Run

All tests should pass on a properly configured PowerVM LPAR with HVPIPE support:

```
JOB ID     : <job_id>
JOB LOG    : /root/avocado/job-results/job-<timestamp>/job.log
 (1/11) kernel/papr_hvpipe.py:PAPRHvpipeTest.test_01_device_node_exists: PASS
 (2/11) kernel/papr_hvpipe.py:PAPRHvpipeTest.test_02_rtas_functions_available: PASS
 (3/11) kernel/papr_hvpipe.py:PAPRHvpipeTest.test_03_system_parameter_check: PASS
 ...
 (11/11) kernel/papr_hvpipe.py:PAPRHvpipeTest.test_11_invalid_source_id_validation: PASS
RESULTS    : PASS 11 | ERROR 0 | FAIL 0 | SKIP 0 | WARN 0 | INTERRUPT 0
```

### Test Cancellation

Tests will be cancelled (SKIP) on unsupported platforms:
- Non-Power architecture systems
- PowerNV (bare metal) systems
- KVM guest systems
- Systems without HVPIPE firmware support

## Troubleshooting

### Device Not Found

If `/dev/papr-hvpipe` doesn't exist:
1. Check kernel version has HVPIPE patches
2. Verify RTAS functions are available
3. Check dmesg for HVPIPE initialization errors
4. Ensure running on PowerVM LPAR (not PowerNV or KVM)

### RTAS Functions Not Available

If RTAS functions are missing:
1. Update firmware to version supporting HVPIPE
2. Check `/proc/device-tree/rtas/` for available functions
3. Verify system is running in LPAR mode

### Permission Denied

If tests fail with permission errors:
1. Run tests with sudo/root privileges
2. Check device file permissions: `ls -l /dev/papr-hvpipe`

### ioctl Failures

If ioctl operations fail:
1. Verify source ID has correct HMC mask (0x02000000)
2. Check if HMC source is available and configured
3. Review kernel logs: `dmesg | grep hvpipe`

## Test Logs

Test logs are stored in the Avocado results directory:
```
~/avocado/job-results/job-<timestamp>/
├── job.log          # Main job log
├── test-results/    # Individual test results
└── html/            # HTML report
```

## Architecture Details

### HVPIPE Interface

```
User Space Application
        ↓
   /dev/papr-hvpipe (char device)
        ↓
   papr-hvpipe driver
        ↓
   RTAS Calls (ibm,send-hvpipe-msg / ibm,receive-hvpipe-msg)
        ↓
   Hypervisor (PowerVM)
        ↓
   HMC (Hardware Management Console)
```

### Data Flow

1. **Send Operation**:
   - User writes data with HVPIPE header
   - Driver validates size and format
   - Issues `ibm,send-hvpipe-msg` RTAS call
   - Returns success/error to user

2. **Receive Operation**:
   - Hypervisor sends event interrupt when data available
   - Event handler wakes up waiting file descriptors
   - User reads data with poll/read
   - Driver issues `ibm,receive-hvpipe-msg` RTAS call
   - Returns payload with header to user

3. **Migration**:
   - Suspend: Disable HVPIPE, set system parameter to 0
   - Resume: Enable HVPIPE, set system parameter to 1

## References

- Linux Kernel Source: `arch/powerpc/platforms/pseries/papr-hvpipe.c`
- UAPI Header: `arch/powerpc/include/uapi/asm/papr-hvpipe.h`
- PAPR Specification: Power Architecture Platform Reference
- Avocado Framework: https://avocado-framework.github.io/

## Contributing

To add new test cases:

1. Add test method following naming convention: `test_##_description`
2. Use appropriate skip decorators for platform requirements
3. Add comprehensive logging for debugging
4. Update this README with new test description

## Support

For issues or questions:
- Check kernel logs: `dmesg | grep hvpipe`
- Review test logs in Avocado results directory
- Verify system meets prerequisites
- Contact IBM Power Systems support for firmware issues

## License

This test suite is part of avocado-misc-tests and follows the same license terms.

## Author

- Sachin Sant <sachinp@linux.ibm.com>

## Version History

- **v1.0** (2026-02-10): Initial release
  - 12 comprehensive test cases
  - Full HVPIPE interface validation
  - Migration support testing
  - Error handling validation