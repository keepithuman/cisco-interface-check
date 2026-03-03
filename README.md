# Cisco Interface Health Check — IAG Service

Connects to a Cisco device (IOS / IOS-XR / NX-OS) via Netmiko, runs `show interface` for each specified interface, and returns a JSON report with status, speed, MTU, and error counters.

## Setup

### 1. Create secrets

```bash
iagctl create secret cisco-device-username --prompt-value
iagctl create secret cisco-device-password --prompt-value
```

### 2. Update `services.yaml`

Set the repository URL to your Git repo (already set if you cloned this repo).

### 3. Import

```bash
iagctl db import services.yaml --validate
iagctl db import services.yaml
```

### 4. Verify

```bash
iagctl describe service cisco-interface-check
```

## Testing

### Check expected inputs

```bash
iagctl run service python-script cisco-interface-check --use
```

### Run against a device

```bash
iagctl run service python-script cisco-interface-check \
  --set device_ip=172.20.100.63 \
  --set device_type=cisco_xr \
  --set interfaces="GigabitEthernet0/0/0/0,GigabitEthernet0/0/0/1,GigabitEthernet0/0/0/2" \
  --raw
```

### Run with debug output

Includes raw `show interface` output in the report — useful for troubleshooting parsing issues:

```bash
iagctl run service python-script cisco-interface-check \
  --set device_ip=172.20.100.63 \
  --set device_type=cisco_xr \
  --set interfaces="GigabitEthernet0/0/0/0" \
  --set debug=true \
  --raw
```

### Inputs

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `device_ip` | yes | — | Target device IP |
| `device_type` | no | `cisco_ios` | Netmiko type: `cisco_ios`, `cisco_xr`, `cisco_nxos`, `cisco_xe` |
| `interfaces` | yes | — | Comma-separated interface names |
| `debug` | no | `false` | Set to `true` to include raw command output |

### Example output

```json
{
  "success": true,
  "device_ip": "172.20.100.63",
  "device_type": "cisco_xr",
  "interfaces": {
    "GigabitEthernet0/0/0/0": {
      "status": "admin-down",
      "line_protocol": "down",
      "speed": "1 Gbps",
      "mtu": 1514,
      "counters": {
        "input_packets": 0,
        "output_packets": 0,
        "input_errors": 0,
        "output_errors": 0,
        "crc_errors": 0
      },
      "has_errors": false
    }
  },
  "summary": {
    "total": 1,
    "up": 0,
    "down": 0,
    "admin_down": 1,
    "errors_detected": 0
  }
}
```

## Calling from an Itential Workflow

Use `GatewayManager.runService`:

```json
{
  "name": "runService",
  "app": "GatewayManager",
  "variables": {
    "incoming": {
      "serviceName": "cisco-interface-check",
      "clusterId": "YOUR_CLUSTER_ID",
      "params": {
        "device_ip": "172.20.100.63",
        "device_type": "cisco_xr",
        "interfaces": "GigabitEthernet0/0/0/0,GigabitEthernet0/0/0/1"
      },
      "inventory": ""
    },
    "outgoing": {
      "result": "$var.job.interfaceReport"
    }
  }
}
```

Extract the report from the JSON-RPC envelope with a `query` task on path `result.stdout`.
