# VPC Architecture

Hub-and-Spoke network design with distributed egress and centralized inspection.  
Region: `il-central-1` (Israel) · Created by CDK via CloudFormation.

---

## The Big Picture

Your AWS account has **one VPC** that acts as a spoke in a hub-and-spoke architecture.
Every resource you deploy lives inside this VPC. Nothing has a public IP — all internet
traffic is forced through an inspection pipeline before it can leave or enter.

The pipeline has three layers, all within your VPC, but with inspection happening
cross-account in a shared hub:

```
[ Your workload ]
      ↓
[ Hub firewall ]   ← lives in a shared security account, not yours
      ↓
[ NAT Gateway ]    ← lives in your account
      ↓
[ Internet ]
```

---

## VPC

**Name:** `sandboxclouddevelopment-prd-001-spoke-vpc`  
**CIDR:** `10.3.64.0/22` (1,024 IPs total, range `10.3.64.0 – 10.3.67.255`)

The `/22` block is divided into six subnets. The split is designed so that workload
subnets are large and infrastructure subnets are small:

```
10.3.64.0/22
├── 10.3.64.0/27   → firewallSubnet1 (AZ 1a)
├── 10.3.64.32/27  → firewallSubnet2 (AZ 1b)
├── 10.3.65.0/24   → spokeSubnet1    (AZ 1a)
├── 10.3.66.0/24   → spokeSubnet2    (AZ 1b)
├── 10.3.67.0/27   → natSubnet1      (AZ 1a)
└── 10.3.67.32/27  → natSubnet2      (AZ 1b)
```

No default VPC is used — everything is purpose-built by CDK.

---

## Subnets

Six subnets across three types. Each type exists in two Availability Zones
(`il-central-1a` and `il-central-1b`) for high availability — if one AZ fails,
traffic continues through the other.

### Spoke Subnets — where your workloads live

| Subnet name | Subnet ID | CIDR | AZ | Usable IPs |
|---|---|---|---|---|
| `spokeSubnet1` | `subnet-01996bb83a6db398c` | `10.3.65.0/24` | 1a | 251 |
| `spokeSubnet2` | `subnet-0c8a2d1456074051e` | `10.3.66.0/24` | 1b | 251 |

This is where you deploy everything: EC2 instances, Lambda functions, ECS tasks,
RDS databases, and so on. The `/24` block gives 251 usable IPs per AZ.

No resource here has a public IP. The only way out is through the firewall endpoint.

### Firewall Subnets — the inspection checkpoint

| Subnet name | Subnet ID | CIDR | AZ | Usable IPs |
|---|---|---|---|---|
| `firewallSubnet1` | `subnet-065d2992d7a1b90a9` | `10.3.64.0/27` | 1a | 26 |
| `firewallSubnet2` | `subnet-084b04815d14b2834` | `10.3.64.32/27` | 1b | 26 |

These subnets hold the **Gateway Load Balancer endpoints** that connect to the hub
account's Network Firewall. No workloads go here.

Traffic arriving from a spoke subnet is forwarded cross-account to the hub firewall.
If approved, it returns here and continues to the NAT Gateway.

The `/27` is deliberately small — only the endpoint's network interface needs an IP.

### NAT Subnets — the exit door

| Subnet name | Subnet ID | CIDR | AZ | Usable IPs |
|---|---|---|---|---|
| `natSubnet1` | `subnet-04c18afcc7956af21` | `10.3.67.0/27` | 1a | 26 |
| `natSubnet2` | `subnet-00e82964cf19f5e31` | `10.3.67.32/27` | 1b | 26 |

After the firewall clears the traffic, the NAT Gateway here translates the private
source address to a fixed public Elastic IP and sends the packet to the Internet Gateway.

Again `/27` — only the NAT Gateway's own interface needs an IP in this subnet.

---

## Internet Gateway

**Name:** `gray-hippo-sandboxclouddevelopment-prd-001-egress-igw`  
**ID:** `igw-0d54a13bd04e6242e`

Attached to the VPC and is the **physical door to the internet**. On its own it does
nothing — routing and NAT still apply. Only the NAT subnets route `0.0.0.0/0` to the
IGW. No other subnet can reach it directly.

---

## NAT Gateways

| Name | ID | AZ | Subnet | Elastic IP name |
|---|---|---|---|---|
| `001-nat-1a` | `nat-03d2ad88c6d3bcda9` | 1a | `natSubnet1` | `001-eip-1a` |
| `001-nat-1b` | `nat-0fc371e4278247404` | 1b | `natSubnet2` | `001-eip-1b` |

**What NAT does:** workloads use private addresses not routable on the internet.
The NAT Gateway swaps the private source IP for its Elastic IP before sending the
packet out, and swaps it back on the reply. Private resources reach the internet
without being directly reachable from it.

**Why two?** If AZ 1a fails, AZ 1b's gateway keeps working. Cross-AZ NAT also adds
latency and cost.

**Why Elastic IPs?** Fixed public IPs that never change — you can whitelist them at
external APIs, third-party firewalls, or SaaS allow-lists.

> **⚠️ AZ 1a anomaly:** current route tables send all traffic — from both AZs —
> through `firewall-rt-1b` and then `001-nat-1b`. AZ 1a's NAT Gateway and Elastic IP
> receive zero traffic. You are paying for them but they are idle.
> See the [Route Tables](#route-tables) section for details.

---

## VPC Endpoints (Gateway Load Balancer)

| Name | ID | AZ | Subnet |
|---|---|---|---|
| `RootHub-inspection-firewall (il-central-1a)` | `vpce-065568da4cfe1d602` | 1a | `firewallSubnet1` |
| `RootHub-inspection-firewall (il-central-1b)` | `vpce-063335608106cb20a` | 1b | `firewallSubnet2` |

These are **auto-managed by AWS Network Firewall** — created automatically when the hub
account associates its firewall with your VPC. You do not create or configure them manually.

**Type — GatewayLoadBalancer (not Interface):** Network Firewall uses GWLB endpoints
because they preserve original packet headers end-to-end, which the firewall needs to
apply inspection rules correctly.

**Cross-account:** both endpoints point to `RootHub-inspection-firewall` in the hub
account. Your account owns the endpoints; the hub account owns the firewall and its rules.
You cannot see or modify the inspection policy from your account.

---

## Route Tables

Eight route tables control exactly where every packet goes. This routing is what
enforces the inspection pipeline — wrong routes would let traffic bypass the firewall.

### `igw-rt` — Internet Gateway route table

Associated with the **Internet Gateway itself** (not a subnet). Handles **inbound** replies.

| Destination | Next hop | Why |
|---|---|---|
| `10.3.65.0/24` (spoke 1a) | `vpce-065568da4cfe1d602` (fw endpoint 1a) | Inbound traffic to 1a must pass firewall |
| `10.3.66.0/24` (spoke 1b) | `vpce-063335608106cb20a` (fw endpoint 1b) | Inbound traffic to 1b must pass firewall |
| `10.3.64.0/22` | local | VPC-internal stays local |

### `spoke-rt-1b` — Spoke subnet route table

Associated with **both spoke subnets** (1a and 1b).

| Destination | Next hop |
|---|---|
| `0.0.0.0/0` | `vpce-063335608106cb20a` (firewall endpoint 1b) |
| `10.3.64.0/22` | local |

All outbound workload traffic goes to the firewall endpoint first. No bypass possible.

### `firewall-rt-1b` — Firewall subnet route table

Associated with **both firewall subnets** (1a and 1b).

| Destination | Next hop |
|---|---|
| `0.0.0.0/0` | `nat-0fc371e4278247404` (NAT Gateway 1b) |
| `10.3.64.0/22` | local |

Post-inspection traffic continues to the NAT Gateway.

### `nat-rt-1a` and `nat-rt-1b` — NAT subnet route tables

Each associated with its own NAT subnet.

| Destination | Next hop |
|---|---|
| `0.0.0.0/0` | `igw-0d54a13bd04e6242e` (Internet Gateway) |
| `10.3.64.0/22` | local |

The final hop before the public internet.

### Route table anomaly — AZ 1a is effectively bypassed

`spoke-rt-1a` and `firewall-rt-1a` both exist in CloudFormation but are **not
associated with any subnet**. Both spoke subnets and both firewall subnets use the
`1b` route tables, meaning:

- All traffic (regardless of source AZ) routes through firewall endpoint `1b` and NAT GW `1b`
- AZ 1a's firewall endpoint (`vpce-065568da4cfe1d602`) and NAT Gateway (`001-nat-1a`) receive no traffic
- You are paying for `001-nat-1a` and its Elastic IP (`001-eip-1a`) for zero benefit
- If AZ 1b goes down, there is **no automatic failover** to AZ 1a

This is likely a CDK deployment issue where the 1a route tables were created but the
subnet associations were not applied correctly.

---

## Network ACL

One default NACL — `acl-0833042dd260ca851` — is applied to all six subnets.

| Direction | Rule | Traffic | Action |
|---|---|---|---|
| Inbound | 100 | All protocols | **Allow** |
| Inbound | 32767 | All protocols | Deny (default) |
| Outbound | 100 | All protocols | **Allow** |
| Outbound | 32767 | All protocols | Deny (default) |

**Why fully open?** NACLs are stateless — they must explicitly allow return traffic too,
which makes fine-grained rules error-prone. In this architecture real access control
happens at two other layers:

1. **Hub Network Firewall** — org-wide egress/ingress policy
2. **Security Groups** — per-resource access rules (stateful)

The NACL is intentionally left open to avoid duplication and breakage.

---

## Security Groups

One security group exists — the default (`sg-0ad518583be2c8479`), auto-created with the VPC.

| Direction | Rule |
|---|---|
| Inbound | Allow from same security group only (self-reference) |
| Outbound | Allow all |

No custom security groups exist yet because **no workloads have been deployed**.
When you deploy resources (EC2, RDS, ECS, etc.), create dedicated security groups
per resource type with the minimum required ports.

---

## What Is Not Present

| Resource | Present | Why |
|---|---|---|
| Transit Gateway | ❌ | Hub uses cross-account GWLB endpoints — no TGW needed |
| VPC Peering | ❌ | No peer VPCs in this account |
| Custom NACLs | ❌ | Default kept open; firewall + SGs handle access control |
| Custom Security Groups | ❌ | No workloads deployed yet |
| VPN / Direct Connect | ❌ | No on-premises connectivity |
| Local Network Firewall | ❌ | Inspection is centralized in the hub account |

---

## Full Egress + Ingress Flow

```
EGRESS (outbound)
─────────────────────────────────────────────────────────
Workload  (spoke subnet — 10.3.65.0/24 or 10.3.66.0/24)
  ↓  route: 0.0.0.0/0 → vpce-063335608106cb20a
GWLB endpoint  (firewallSubnet — 10.3.64.0/27 or 10.3.64.32/27)
  ↓  forwarded cross-account
RootHub-inspection-firewall  (hub account)
  ↓  approved — packet returned to firewall subnet
GWLB endpoint  (firewall subnet)
  ↓  route: 0.0.0.0/0 → nat-0fc371e4278247404
NAT Gateway  (natSubnet — 10.3.67.0/27 or 10.3.67.32/27)
             swaps private IP → Elastic IP
  ↓  route: 0.0.0.0/0 → igw-0d54a13bd04e6242e
Internet Gateway → Internet


INGRESS (inbound reply)
─────────────────────────────────────────────────────────
Internet → Internet Gateway
  ↓  IGW route table: 10.3.65.0/24 → vpce-065568da4cfe1d602
                      10.3.66.0/24 → vpce-063335608106cb20a
GWLB endpoint  (firewall subnet)
  ↓  forwarded cross-account
RootHub-inspection-firewall  (hub account)
  ↓  approved — packet returned
GWLB endpoint  (firewall subnet)
  ↓  delivered to destination
Workload  (spoke subnet)
```

Both directions pass through the hub firewall — no packet bypasses inspection.

---

## What Is a Gateway Load Balancer Endpoint?

The GWLB endpoint is the most unusual component in this VPC — it looks like a route table entry but it is actually a **transparent network doorway into another AWS account**.

### The two players

```
Your account (spoke)               Hub account (security team)
────────────────────               ───────────────────────────
GWLB Endpoint                      Gateway Load Balancer (GWLB)
vpce-063335608106cb20a   ←──────→  + Firewall appliances (EC2s running inspection software)
  IP: 10.3.64.42
  Subnet: firewallSubnet2
```

Your account owns the **endpoint** — just a network interface sitting in `firewallSubnet2`. The hub security account owns the actual **load balancer and firewall VMs** that do the inspection. You cannot see or modify the firewall rules from your account.

### What happens inside when a packet hits the endpoint

```
1. Packet arrives at GWLB endpoint (10.3.64.42)

2. Endpoint wraps the packet in a GENEVE tunnel
   (GENEVE puts your original packet inside a new outer packet)

3. Wrapped packet is sent cross-account to the GWLB in the hub

4. GWLB picks a firewall appliance and delivers it

5. Firewall unwraps and inspects the original packet
   — checks rules: allowed destination? allowed protocol?
   — if approved → wraps it back and returns it through the tunnel

6. GWLB endpoint receives the packet back and forwards it to the next hop
```

The original packet is **completely unchanged** throughout — source IP, destination IP, port, protocol. The GENEVE tunnel is invisible to both the sender and the receiver. It is as if the packet passed through a transparent wall that happened to have a security guard examining it.

### Why GWLB instead of a simpler approach

The firewall needs to see the **real** source and destination IPs to apply meaningful rules. Older approaches (like routing through a proxy) rewrote the packet headers, which broke rule matching.

```
Old way (proxy):
  EC2 → Firewall proxy → Internet
  Firewall sees source = proxy IP   ← cannot write rules per workload

GWLB way:
  EC2 → GWLB endpoint → [GENEVE tunnel] → Firewall → Internet
  Firewall sees source = real EC2 IP ✅   destination = real destination ✅
```

GWLB preserves the original headers end-to-end, which is why AWS Network Firewall uses it for VPC traffic inspection.

### This endpoint in your VPC

| Property | Value |
|---|---|
| Endpoint ID | `vpce-063335608106cb20a` |
| Private IP | `10.3.64.42` |
| Subnet | `firewallSubnet2` (`subnet-084b04815d14b2834`) |
| Service | `com.amazonaws.vpce.il-central-1.vpce-svc-097b9b80cda8975a8` |
| Owner | Hub security account (not your account) |
| Type | `GatewayLoadBalancer` — packets pass *through* it, not *to* it |

You do not manage, configure, or pay for the firewall rules. The endpoint itself is auto-created by AWS when the hub account associates its Network Firewall with your VPC.
