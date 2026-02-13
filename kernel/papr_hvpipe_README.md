# PAPR HVPIPE Test Suite Documentation

## Overview

This test suite validates the PAPR HVPIPE (Hypervisor Pipe) interface implementation in the Linux kernel. HVPIPE provides an inband hypervisor channel for communication between partitions and Hardware Management Consoles (HMCs).

## Kernel Patches Validated

The test suite validates the following kernel patches:

1. **ef104054a312** - Define __u{8,32} types in papr_hvpipe_hdr struct
2. **6d84f85151bb** - HVPIPE changes to support migration
3. **39a08a4f9498** - Enable hvpipe with ibm,set-system-parameter RTAS
4. **b48b6cc8c655** - Enable HVPIPE event message interrupt
5. **da24fb99a1b5** - Wakeup hvpipe FD when the payload is pending
6. **cebdb522fd3e** - Receive payload with ibm,receive-hvpipe-msg RTAS
7. **56dbc6678bbb** - Send payload with ibm,send-hvpipe-msg RTAS
8. **814ef095f12c** - Add papr-hvpipe char driver for HVPIPE interfaces
9. **26b4fcecea05** - Define HVPIPE specific macros
10. **043439ad1a23** - Define papr-hvpipe ioctl

## Test Categories

### Basic Functionality Tests (test_01 - test_11)

1. **test_01_device_node_exists** - Verifies `/dev/papr-hvpipe` device node exists
2. **test_02_rtas_functions_available** - Checks RTAS function availability
3. **test_03_system_parameter_check** - Validates system parameter configuration
4. **test_04_device_open_close** - Tests basic open/close operations
5. **test_05_ioctl_create_handle** - Validates handle creation ioctl
6. **test_06_header_structure_validation** - Tests header structure format
7. **test_07_write_size_validation** - Validates write size constraints
8. **test_08_event_sources_check** - Checks device tree event sources
9. **test_09_kernel_module_check** - Verifies kernel HVPIPE support
10. **test_10_concurrent_handle_creation** - Tests duplicate handle prevention
11. **test_11_invalid_source_id_validation** - Validates source ID rejection

### Advanced Functionality Tests (test_12 - test_13)

12. **test_12_buffer_boundary_conditions** - Tests buffer size edge cases
13. **test_13_poll_mechanism_validation** - Validates poll/select mechanism

### Stress Tests (test_14 - test_16, test_20, test_22)

14. **test_14_rapid_open_close_stress** - Rapid open/close cycles
15. **test_15_concurrent_access_stress** - Multi-threaded concurrent access
16. **test_16_handle_creation_stress** - Multiple source ID handle creation
20. **test_20_payload_size_stress** - Various payload size handling
22. **test_22_sustained_load_stress** - Extended duration load testing

### Documentation-Based Tests (test_17 - test_19, test_21)

17. **test_17_error_code_validation** - RTAS error code translation
18. **test_18_migration_support_validation** - Partition migration handling
19. **test_19_connection_loss_handling** - Connection loss flag handling
21. **test_21_resource_cleanup_validation** - Resource cleanup verification

## Test Parameters

The test suite accepts the following parameters:

- **source_id** (default: 0x02000001) - HMC source ID for testing
- **timeout** (default: 30) - Operation timeout in seconds
- **payload_size** (default: 100) - Test payload size in bytes
- **stress_iterations** (default: 100) - Number of stress test iterations
- **stress_threads** (default: 5) - Number of concurrent threads for stress tests
- **sustained_duration** (default: 60) - Duration for sustained load test in seconds

## Running the Tests

### Basic Execution

```bash
avocado run papr_hvpipe.py
```

### With Custom Parameters

```bash
avocado run papr_hvpipe.py -p source_id=0x02000002 -p stress_iterations=200
```

### Running Specific Tests

```bash
# Run only stress tests
avocado run papr_hvpipe.py --filter-by-tags=stress

# Run specific test
avocado run papr_hvpipe.py:PAPRHvpipeTest.test_14_rapid_open_close_stress
```

## Platform Requirements

- **Architecture**: PowerPC (ppc64le)
- **Platform**: IBM Power Systems (pSeries/LPAR)
- **Firmware**: RTAS with HVPIPE support
- **Kernel**: Linux with HVPIPE patches applied
- **Privileges**: Root/sudo access required

### Not Supported On

- PowerNV (bare metal) systems
- KVM guest systems
- Non-Power architectures

## HVPIPE Architecture

### Device Interface

- **Device Node**: `/dev/papr-hvpipe`
- **Device Type**: Character device
- **Operations**: open, close, read, write, poll, ioctl

### Source ID Format

Source IDs follow the format: `0xCCRRQQQQ`
- **CC**: Source type (0x02 for HMC)
- **RR**: Reserved (0x00)
- **QQQQ**: Source index identifier (0x0000 - 0xFFFF)

### Header Structure

```c
struct papr_hvpipe_hdr {
    __u8 version;        // 1 byte
    __u8 reserved[3];    // 3 bytes
    __u32 flags;         // 4 bytes
    __u8 reserved2[40];  // 40 bytes
};  // Total: 52 bytes
```

### Flags

- **HVPIPE_MSG_AVAILABLE** (0x01) - Message available for read
- **HVPIPE_LOST_CONNECTION** (0x02) - Connection lost to source

### Size Constraints

- **Header Size**: 52 bytes (HVPIPE_HDR_LEN)
- **Max Payload**: 4048 bytes (HVPIPE_MAX_WRITE_BUFFER_SIZE)
- **Min Write Size**: Header + 1 byte
- **Max Write Size**: Header + 4048 bytes

## RTAS Functions

### ibm,send-hvpipe-msg

Sends payload to specified source ID.

**Return Codes**:
- `RTAS_SUCCESS` (0) - Success
- `RTAS_HARDWARE_ERROR` (-1) - Hardware error (errno: EIO)
- `RTAS_INVALID_PARAMETER` (-3) - Invalid parameter (errno: EINVAL)
- `RTAS_HVPIPE_CLOSED` (-4) - Pipe closed (errno: EPIPE)
- `RTAS_FUNC_NOT_SUPPORTED` (-9) - Not supported (errno: EOPNOTSUPP)

### ibm,receive-hvpipe-msg

Receives payload from hypervisor.

**Return Codes**: Same as send-hvpipe-msg

## Migration Support

During partition migration:
- `write()` returns `-ENXIO`
- `read()` returns `-ENXIO`
- `poll()` returns `POLLRDHUP`
- Operations resume after migration completes

## Event Notification

HVPIPE uses interrupt-based event notification:
1. Hypervisor sends event message when payload is ready
2. Event handler wakes up waiting file descriptors
3. Application uses `poll()` to wait for events
4. `read()` retrieves the payload

## Error Handling

### Common Error Scenarios

1. **Invalid Source ID** - Source ID without HMC mask (0x02000000)
2. **Duplicate Handle** - Attempting to create handle for existing source
3. **Invalid Buffer Size** - Write size outside valid range
4. **Migration in Progress** - Operations during partition migration
5. **Connection Loss** - Hypervisor closes pipe to source

### Error Code Mappings

| RTAS Code | errno | Description |
|-----------|-------|-------------|
| RTAS_SUCCESS | 0 | Success |
| RTAS_HARDWARE_ERROR | EIO (5) | Hardware error |
| RTAS_INVALID_PARAMETER | EINVAL (22) | Invalid parameter |
| RTAS_HVPIPE_CLOSED | EPIPE (32) | Pipe closed |
| RTAS_FUNC_NOT_SUPPORTED | EOPNOTSUPP (95) | Not supported |

## Stress Testing

### Rapid Open/Close (test_14)

Tests resource management with rapid device open/close cycles.

**Metrics**:
- Operations per second
- Success/error ratio
- Resource leak detection

### Concurrent Access (test_15)

Tests locking and synchronization with multiple threads.

**Metrics**:
- Thread contention handling
- Lock correctness
- Race condition detection

### Handle Creation (test_16)

Tests resource allocation with multiple source IDs.

**Metrics**:
- Maximum concurrent handles
- Resource tracking
- Cleanup verification

### Sustained Load (test_22)

Tests system stability under continuous load.

**Metrics**:
- Long-term stability
- Memory leak detection
- Performance degradation

## Troubleshooting

### Device Not Found

```bash
# Check if device exists
ls -l /dev/papr-hvpipe

# Check kernel logs
dmesg | grep -i hvpipe

# Verify RTAS functions
ls /proc/device-tree/rtas/ibm,*hvpipe*
```

### RTAS Functions Not Available

```bash
# Check device tree
cat /proc/device-tree/rtas/ibm,send-hvpipe-msg
cat /proc/device-tree/rtas/ibm,receive-hvpipe-msg
```

### Event Sources Not Configured

```bash
# Check event sources
ls /proc/device-tree/event-sources/ibm,hvpipe-msg-events/
```

### Permission Denied

```bash
# Run with sudo
sudo avocado run papr_hvpipe.py

# Check device permissions
ls -l /dev/papr-hvpipe
```

## Code Quality

The test suite follows:
- **PEP 8** style guidelines
- **pylint** compliance (with avocado-specific exceptions)
- **pycodestyle** compliance
- Maximum line length: 79 characters
- Comprehensive docstrings
- Type hints where applicable

## Contributing

When adding new tests:
1. Follow existing naming convention (`test_NN_descriptive_name`)
2. Add comprehensive docstrings
3. Include platform skip decorators
4. Document expected behavior
5. Add error handling
6. Update this README

## References

- PAPR (Power Architecture Platform Reference)
- Linux kernel documentation: `Documentation/powerpc/papr_hcalls.rst`
- Kernel source: `arch/powerpc/platforms/pseries/papr-hvpipe.c`
- Header file: `arch/powerpc/platforms/pseries/papr-hvpipe.h`

## License

This test suite is licensed under the GNU General Public License v2.0.

## Author

Sachin Sant <sachinp@linux.ibm.com>

## Version History

- **v1.0** (2026) - Initial release with basic functionality tests
- **v2.0** (2026) - Enhanced with stress tests and documentation-based scenarios