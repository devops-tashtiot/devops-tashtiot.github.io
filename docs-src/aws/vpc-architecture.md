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
**CIDR:** `10.3.64.0/22` (1,024 IPs total)

Think of the VPC as your private data centre inside AWS. Everything inside it is
isolated from other AWS customers. The `/22` block is split across six subnets,
each with a specific role.

No default VPC is used — everything is purpose-built by CDK.

---

## Subnets

You have six subnets across three types. Each type exists in two Availability Zones
(`il-central-1a` and `il-central-1b`) for high availability — if one AZ fails,
traffic continues through the other.

### Spoke Subnets — where your workloads live

| Subnet | AZ | Size |
|---|---|---|
| `spokeSubnet1` | 1a | `/24` — 251 usable IPs |
| `spokeSubnet2` | 1b | `/24` — 251 usable IPs |

This is where you deploy everything: EC2 instances, Lambda functions, ECS tasks,
RDS databases, and so on. The `/24` size gives you 251 IPs per AZ — plenty of room
as your environment grows.

No resource here has a public IP. The only way out is through the firewall endpoint.

### Firewall Subnets — the inspection checkpoint

| Subnet | AZ | Size |
|---|---|---|
| `firewallSubnet1` | 1a | `/27` — 26 usable IPs |
| `firewallSubnet2` | 1b | `/27` — 26 usable IPs |

These subnets do not hold your workloads — they hold the **VPC endpoints** that
connect your VPC to the shared Network Firewall in the hub account.

When traffic leaves a spoke subnet, the route table sends it here first. The endpoint
forwards it to the hub's firewall for inspection. If the firewall approves it, the
traffic returns to the firewall subnet and continues to the NAT Gateway.

The `/27` is deliberately small — only the endpoint's network interface needs an IP here,
not real workloads.

### NAT Subnets — the exit door

| Subnet | AZ | Size |
|---|---|---|
| `natSubnet1` | 1a | `/27` — 26 usable IPs |
| `natSubnet2` | 1b | `/27` — 26 usable IPs |

After the firewall clears the traffic, it arrives here. The NAT Gateway translates
your private addresses to a public Elastic IP and sends the packet out through the
Internet Gateway.

Again `/27` — only the NAT Gateway's own network interface needs an IP in this subnet.

---

## Internet Gateway

**Name:** `gray-hippo-sandboxclouddevelopment-prd-001-egress-igw`

The Internet Gateway is attached to your VPC and is the **physical door to the
internet**. It does one thing: route packets between the VPC and the public internet.

On its own, an IGW doesn't allow anything through — routing and NAT still apply.
Resources in the NAT subnets route `0.0.0.0/0` to the IGW. Resources in other
subnets never reach the IGW directly.

---

## NAT Gateways

| Name | AZ | Elastic IP |
|---|---|---|
| `001-nat-1a` | 1a | `001-eip-1a` |
| `001-nat-1b` | 1b | `001-eip-1b` |

Two NAT Gateways — one per AZ — sit in the NAT subnets. Each has a permanently
allocated **Elastic IP** (a fixed public IP that doesn't change).

**What NAT does:** your workloads use private addresses that are not routable on
the public internet. The NAT Gateway swaps the private source address for its
Elastic IP before sending the packet out, and swaps it back when the reply comes in.
This lets private resources reach the internet without being directly reachable from it.

**Why two?** If AZ 1a fails, AZ 1b's NAT Gateway keeps working independently.
Cross-AZ traffic through a single NAT Gateway would also add latency and cost.

**Why Elastic IPs?** Fixed public IPs let you whitelist your outbound addresses at
external services (APIs, databases, third-party firewalls). The IPs never change
even if the NAT Gateway is recreated.

---

## VPC Endpoints (Gateway Load Balancer)

| Name | AZ | Type |
|---|---|---|
| `RootHub-inspection-firewall (il-central-1a)` | 1a | GatewayLoadBalancer |
| `RootHub-inspection-firewall (il-central-1b)` | 1b | GatewayLoadBalancer |

These two endpoints are **auto-managed by AWS Network Firewall** — you do not create
or configure them manually. AWS creates them when the hub account associates the
firewall with your VPC.

**What they are:** Gateway Load Balancer endpoints act as a transparent bump-in-the-wire.
Traffic enters the endpoint, gets forwarded to the Network Firewall in the hub account
for inspection, and returns through the same endpoint. From a routing perspective it
looks like any other hop.

**Why GatewayLoadBalancer type (not Interface)?** Network Firewall uses GWLB endpoints
specifically because they preserve the original packet headers end-to-end, which the
firewall needs in order to apply rules accurately.

**Cross-account:** The `Firewall` tag on each endpoint points to
`RootHub-inspection-firewall` in the hub account. Your account only owns the endpoints,
not the firewall itself — you cannot see or modify the inspection rules.

---

## Route Tables

Eight route tables control exactly where every packet goes. The routing is what
enforces the inspection pipeline — without the correct routes, packets could bypass
the firewall entirely.

### `igw-rt` — Internet Gateway route table

Associated with the **Internet Gateway itself** (not a subnet).

| Destination | Next hop |
|---|---|
| Spoke subnet 1a CIDR | Firewall endpoint 1a |
| Spoke subnet 1b CIDR | Firewall endpoint 1b |
| VPC local | local |

This handles **inbound** traffic from the internet. When a reply packet arrives at
the IGW destined for a spoke subnet, this table intercepts it and sends it through
the firewall endpoint first — ensuring inbound traffic is also inspected before
reaching your workloads.

### `spoke-rt-1b` — Spoke subnet route table

Associated with **both spoke subnets** (1a and 1b).

| Destination | Next hop |
|---|---|
| `0.0.0.0/0` | Firewall endpoint 1b |
| VPC local | local |

All outbound traffic from your workloads hits this table first and goes straight to
the firewall endpoint. There is no way to reach the internet without passing through it.

> **Note:** `spoke-rt-1a` exists in CloudFormation but is not associated with any subnet.
> Both spoke subnets currently use `spoke-rt-1b` and route through the 1b firewall endpoint.

### `firewall-rt-1b` — Firewall subnet route table

Associated with **both firewall subnets** (1a and 1b).

| Destination | Next hop |
|---|---|
| `0.0.0.0/0` | NAT Gateway 1b |
| VPC local | local |

After the hub firewall inspects and approves the traffic, it returns here. This
table then forwards it to the NAT Gateway to complete the egress journey.

> **Note:** `firewall-rt-1a` also exists but is unassociated — both firewall subnets
> use `firewall-rt-1b` and route to NAT GW 1b.

### `nat-rt-1a` and `nat-rt-1b` — NAT subnet route tables

Each associated with its respective NAT subnet.

| Destination | Next hop |
|---|---|
| `0.0.0.0/0` | Internet Gateway |
| VPC local | local |

The final hop — the NAT Gateway has already translated the address, and this table
sends the packet out through the IGW to the public internet.

### Route table anomaly — AZ 1a is partially bypassed

Both spoke subnets and both firewall subnets share the **1b** route tables, meaning
traffic always routes through the 1b firewall endpoint and 1b NAT Gateway regardless
of which AZ the source resource is in. AZ 1a's endpoint and NAT GW exist but receive
no traffic from the current routing.

This is likely a CDK deployment issue or intentional consolidation. It means:

- AZ 1a's NAT GW (`001-nat-1a`) and its Elastic IP are idle — you are paying for them
  but they handle no traffic
- If AZ 1b goes down, traffic does **not** automatically fail over to AZ 1a

---

## Network ACL

One default NACL is applied to all six subnets.

| Direction | Rule | Traffic | Action |
|---|---|---|---|
| Inbound | 100 | All | **Allow** |
| Inbound | 32767 | All | Deny |
| Outbound | 100 | All | **Allow** |
| Outbound | 32767 | All | Deny |

**Why fully open?** NACLs are stateless — they evaluate every packet independently,
including return traffic. Overly restrictive NACLs tend to break things in subtle ways
(e.g. blocking ephemeral port replies). In this architecture, the real access control
happens at two other layers:

1. **Hub Network Firewall** — enforces org-wide egress/ingress policy
2. **Security Groups** — enforce per-resource access rules

The NACL is intentionally left open to avoid double-maintenance.

---

## Security Groups

One security group exists — the default, automatically created with the VPC.

| Direction | Rule |
|---|---|
| Inbound | Allow from same security group only |
| Outbound | Allow all |

**No custom security groups exist yet** — because no workloads have been deployed
into the VPC. When you start deploying resources (EC2, Lambda in VPC, RDS, etc.),
you will create security groups tailored to each resource's needs.

The default security group's self-referencing inbound rule means resources assigned
to it can talk to each other freely, but nothing from outside can reach them
unless you explicitly allow it.

---

## What Is Not Present

| Resource | Present | Why |
|---|---|---|
| Transit Gateway | ❌ | Hub uses cross-account GWLB endpoints instead — no TGW needed |
| VPC Peering | ❌ | No peer VPCs in this account |
| Custom NACLs | ❌ | Default NACL kept open; firewall + SGs handle access control |
| Custom Security Groups | ❌ | No workloads deployed yet |
| VPN / Direct Connect | ❌ | No on-premises connectivity configured |
| Local Network Firewall | ❌ | Inspection is centralized in the hub account |

---

## Full Egress + Ingress Flow

```
EGRESS (outbound)
─────────────────
Workload (spoke subnet)
  ↓  route: 0.0.0.0/0 → firewall endpoint
GatewayLoadBalancer endpoint (firewall subnet)
  ↓  forwarded cross-account
RootHub-inspection-firewall (hub account)
  ↓  approved — packet returned
GatewayLoadBalancer endpoint (firewall subnet)
  ↓  route: 0.0.0.0/0 → NAT Gateway
NAT Gateway (NAT subnet)  ← swaps private IP for Elastic IP
  ↓  route: 0.0.0.0/0 → Internet Gateway
Internet Gateway → Internet


INGRESS (inbound reply)
───────────────────────
Internet → Internet Gateway
  ↓  IGW route table: destination subnet → firewall endpoint
GatewayLoadBalancer endpoint (firewall subnet)
  ↓  forwarded cross-account
RootHub-inspection-firewall (hub account)
  ↓  approved — packet returned
GatewayLoadBalancer endpoint (firewall subnet)
  ↓  delivered to workload
Workload (spoke subnet)
```

Both directions pass through the hub firewall — no packet bypasses inspection.
