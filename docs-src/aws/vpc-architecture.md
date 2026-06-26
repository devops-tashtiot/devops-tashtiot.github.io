# VPC Architecture

Hub-and-Spoke network design with distributed egress and centralized inspection.

## Overview

Each workload account runs a **spoke VPC** in `il-central-1` (Israel).
All outbound internet traffic is inspected by a **centralized Network Firewall** that lives in a shared hub account — without any Transit Gateway.
After inspection, traffic exits through the spoke's own NAT Gateway and Internet Gateway.

This is the **distributed egress** model: shared inspection, local exit.

---

## Traffic Flow — Egress

```
Your app  (spoke subnet)
    ↓  0.0.0.0/0 → firewall VPC endpoint
Hub firewall  (centralized Network Firewall — hub account)
    ↓  approved — traffic returns to firewall subnet
NAT Gateway  (NAT subnet — per AZ, in your account)
    ↓  0.0.0.0/0 → Internet Gateway
Internet
```

---

## Subnet Layout

| Subnet | CIDR | AZs | Purpose | Deploy workloads? |
|---|---|---|---|---|
| **Spoke** | `/24` — 251 IPs | 1a, 1b | All app resources — EC2, Lambda, RDS, ECS | ✅ Yes |
| **Firewall** | `/27` — 26 IPs | 1a, 1b | VPC endpoints connecting to the hub's Network Firewall | ❌ No |
| **NAT** | `/27` — 26 IPs | 1a, 1b | NAT Gateways — actual door to the internet after inspection | ❌ No |

---

## Who Owns What

| Component | Lives in | Shared across accounts? |
|---|---|---|
| Network Firewall (inspection rules) | Hub account | ✅ Yes — all spokes share it |
| Firewall VPC endpoints | Spoke account (firewall subnets) | ❌ No — one per spoke VPC |
| NAT Gateway | Spoke account (NAT subnets) | ❌ No — one per AZ per spoke |
| Internet Gateway | Spoke account | ❌ No — one per spoke VPC |

---

## Design Principles

### Centralized inspection
All egress traffic passes through a single shared firewall. Security rules are managed once, enforced everywhere — across all spoke accounts.

### Distributed egress
Each spoke has its own NAT GW and IGW. No Transit Gateway needed — internet exit is local, only inspection is centralized in the hub.

### High availability
Every subnet type is deployed in two AZs (`il-central-1a` and `il-central-1b`). Each AZ has its own firewall endpoint, NAT Gateway, and spoke subnet.

### No direct internet access
No resource has a public IP. All subnets are isolated — nothing reaches the internet without passing the hub firewall first.

---

## How Traffic Is Routed (Route Tables)

| Route table | Associated to | Default route (`0.0.0.0/0`) |
|---|---|---|
| `spoke-rt-1a/1b` | Spoke subnets | → Firewall VPC endpoint |
| `firewall-rt-1a/1b` | Firewall subnets | → NAT Gateway |
| `nat-rt-1a/1b` | NAT subnets | → Internet Gateway |
| `igw-rt` | Internet Gateway | → Firewall VPC endpoint (return path for inbound) |

The IGW route table routes **inbound** traffic back through the firewall endpoint before it reaches the spoke subnets — ensuring all traffic (in and out) is inspected.
