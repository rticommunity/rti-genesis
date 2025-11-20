# Genesis DDS Configuration

## Overview

This document describes the DDS QoS configuration for the Genesis framework, specifically addressing macOS participant index exhaustion issues.

## Problem: macOS Participant Index Exhaustion

When running many DDS participants (e.g., 20+ services) on macOS, you may encounter:

```
ERROR: No index available for participant
Automatic participant index failed to initialize.
```

This occurs because:
1. macOS has stricter networking resource limits
2. Default DDS discovery uses multicast, which has limited port ranges
3. Participant indexes can be exhausted in the default configuration

## Solution: USER_QOS_PROFILES.xml

The `USER_QOS_PROFILES.xml` file in the repository root configures:

### 1. **UDP4 Discovery Stack**
```xml
<initial_peers>
    <element>builtin.udpv4://localhost</element>
    <element>builtin.udpv4://127.0.0.1</element>
    <element>builtin.udpv4://127.0.0.1:7400-7499</element>
</initial_peers>
```
- Uses explicit UDP4 peers instead of multicast
- Expands port range to 7400-7499 for more participants

### 2. **Auto-ID Configuration**
```xml
<rtps_auto_id_kind>LONG_GUID_AUTO_ID</rtps_auto_id_kind>
<participant_id>-1</participant_id>
```
- Lets DDS automatically assign unique participant IDs
- Reduces index conflicts

### 3. **Increased Resource Limits**
```xml
<local_writer_allocation>
    <max_count>256</max_count>
</local_writer_allocation>
```
- Supports up to 256 local participants
- Allocates sufficient resources for large topologies

## Usage

### Automatic Loading

RTI DDS automatically loads `USER_QOS_PROFILES.xml` from:
1. Current working directory
2. `$NDDSHOME/resource/xml/` directory
3. Paths specified by `NDDS_QOS_PROFILES` environment variable

### Manual Loading

```bash
# Option 1: Run from Genesis_LIB directory (automatic)
cd /path/to/Genesis_LIB
python test_functions/services/calculator_service.py

# Option 2: Set environment variable
export NDDS_QOS_PROFILES=/path/to/Genesis_LIB/USER_QOS_PROFILES.xml

# Option 3: Copy to NDDSHOME
cp USER_QOS_PROFILES.xml $NDDSHOME/resource/xml/
```

### Verification

To verify the configuration is loaded:

```bash
# Enable DDS logging
export NDDS_QOS_PROFILES=/path/to/Genesis_LIB/USER_QOS_PROFILES.xml
export NDDS_DISCOVERY_PEERS="builtin.udpv4://127.0.0.1"

# Run a test
python test_functions/services/calculator_service.py
```

You should see in the logs:
- No "No index available" errors
- Participants using UDP4 discovery
- Successful participant creation

## Testing Large Topologies

With this configuration, you can run:
- **20+ services** simultaneously
- **50+ total participants** (services + agents + interfaces)
- **Large-scale network tests** with `start_topology.sh`

Example:
```bash
cd /path/to/Genesis_LIB
./tests/stress/start_topology.sh \
  --agents 10 --services 20 --interfaces 1 -t 180 --force
```

## QoS Profiles

### GenesisDefaultProfile
- **Base profile** for all Genesis participants
- Reliable, UDP4-based discovery
- Optimized for local domain communication

### GenesisMonitoringProfile
- **High-throughput profile** for monitoring topics
- Increased resource limits (5000 samples)
- Suitable for graph topology and event streams

## Troubleshooting

### Still seeing "No index available"?

1. **Check current directory:**
   ```bash
   pwd
   ls -la USER_QOS_PROFILES.xml
   ```

2. **Explicitly set QoS path:**
   ```bash
   export NDDS_QOS_PROFILES="$(pwd)/USER_QOS_PROFILES.xml"
   ```

3. **Verify UDP4 discovery:**
   ```bash
   rtiddsspy -printSample
   # Should show participants using UDP4 transport
   ```

4. **Reduce participant count for testing:**
   ```bash
   # Test with fewer services first
   ./start_topology.sh --agents 5 --services 5 --interfaces 1
   ```

### Port conflicts?

If port 7400-7499 range conflicts with other services:

```xml
<!-- Edit USER_QOS_PROFILES.xml -->
<element>builtin.udpv4://127.0.0.1:8400-8499</element>
```

## Related Issues

- **Monitoring Consolidation:** This configuration is critical for testing the 5→2 monitoring topic consolidation
- **Graph Viewer:** Large topologies require proper DDS configuration to visualize all nodes
- **RC1 Release:** This configuration will be part of the first release

## References

- [RTI Connext DDS User's Manual: Discovery](https://community.rti.com/static/documentation/connext-dds/7.3.0/doc/manuals/connext_dds_professional/users_manual/users_manual/PartDiscovery.htm)
- [RTI Community: macOS Discovery Issues](https://community.rti.com/kb/osx1011)
- [DDS QoS Provider Reference](https://community.rti.com/static/documentation/connext-dds/7.3.0/doc/api/connext_dds/api_cpp2/classdds_1_1core_1_1QosProvider.html)


