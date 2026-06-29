# Windows Server EC2 — Direct RDP Access

A Windows Server 2022 EC2 instance deployed in `natSubnet1` for direct RDP access from the internet.

---

## Access Strategy: SSM vs Direct RDP

The right access method depends on which subnet your instance lives in.

### Best Practice: SSM Session Manager (spoke subnets)

For any instance running in a **spoke subnet**, the recommended approach is **AWS Systems Manager Session Manager** — no open inbound ports, no public IP required.

SSM works because the instance only needs outbound HTTPS (port 443) to reach AWS SSM endpoints. Traffic flows outbound through the GWLB → hub firewall → NAT → IGW path, which spoke subnets already have. There is no need to open any inbound port from the internet.

```bash
# Interactive shell
aws ssm start-session --target <instance-id> --region il-central-1

# RDP tunnel (then connect to localhost:13389)
aws ssm start-session --target <instance-id> \
  --document-name AWS-StartPortForwardingSession \
  --parameters portNumber=3389,localPortNumber=13389 \
  --region il-central-1
```

This is the pattern used for the EKS worker nodes and any future workloads in spoke subnets — no security group inbound rules needed at all.

### Alternative: Direct RDP (nat subnets only)

If you want a Windows machine accessible directly from the internet — without SSM, without a tunnel — you must place it in a **nat subnet**.

The nat subnets are the only subnets with a direct Internet Gateway route, making them the only subnets that can receive unsolicited inbound connections from the internet. Spoke and firewall subnets cannot — see the [VPC Architecture](vpc-architecture.md) page for why.

---

## Why natSubnet, Not spokeSubnet

| Subnet type | Outbound path | Inbound from internet? | Why |
|---|---|---|---|
| `spokeSubnet` | GWLB → hub firewall → NAT → IGW | ❌ No | GWLB endpoint is inspection-only — no inbound path |
| `firewallSubnet` | NAT → IGW | ❌ No | NAT is one-way — outbound only |
| `natSubnet` | IGW directly | ✅ Yes | IGW is a two-way door — handles both inbound and outbound |

> **Common misconception:** spoke subnet traffic does eventually reach the internet (via GWLB → hub firewall → NAT → IGW), so one might assume inbound works too. It does not — there is no mechanism to route an unsolicited inbound packet from the internet back through the GWLB endpoint into a spoke subnet.

---

## Public IP: Auto-Assigned vs Elastic IP

When you put an EC2 instance in a nat subnet, it needs a public IP for inbound connections. There are two ways to get one — they behave very differently.

### Auto-assigned public IP

Set `associate_public_ip_address = true` on the instance resource. AWS picks an IP from its pool and assigns it at launch.

| Property | Behavior |
|---|---|
| Assignment | Random — chosen by AWS at launch |
| Persistence | **Lost on stop** — released when the instance stops, new one assigned on next start |
| Cost | Free |

This means every time you stop and start the instance, the public IP changes. Anyone who saved the old IP (bookmark, RDP profile, firewall whitelist) needs to update it.

### Elastic IP

An Elastic IP is a public IP address you allocate to your account and explicitly attach to an instance.

| Property | Behavior |
|---|---|
| Assignment | You choose — allocated to your account, attached when you want |
| Persistence | **Survives stop/start** — stays attached until you explicitly detach it |
| Cost | Free while attached to a running instance. Charged if allocated but not attached |

```bash
# Attach an existing Elastic IP to an instance
aws ec2 associate-address \
  --instance-id <instance-id> \
  --allocation-id <eip-allocation-id> \
  --region il-central-1
```

**When to use which:**

- **Auto-assigned** — fine for short-lived dev instances where you connect immediately after launch and destroy soon after
- **Elastic IP** — use when the IP must be stable: saved in RDP profiles, whitelisted in external firewalls, or referenced in DNS

---

## Instance Details

| Setting | Value |
|---|---|
| AMI | Windows Server 2022 English Full Base (latest) |
| Instance type | `t3.micro` — free-tier eligible (750 hrs/month) |
| Subnet | `natSubnet1` (`subnet-04c18afcc7956af21`, AZ 1a) |
| Public IP | Auto-assigned at launch (`associate_public_ip_address = true`) |
| Root volume | 30 GB gp3, encrypted (required by org policy) |
| IMDSv2 | Enforced (`http_tokens = required`) |

> **Note:** `MapPublicIpOnLaunch` is `false` on all subnets in this VPC. The `associate_public_ip_address = true` flag on the instance is what gets the public IP assigned — without it, the instance launches with no public IP even in natSubnet.

---

## Security Group for Direct RDP

| Direction | Port | Source | Purpose |
|---|---|---|---|
| Inbound | 3389 (RDP) | Your IP `/32` or `0.0.0.0/0` | Remote desktop |
| Inbound | 5985 (WinRM HTTP) | VPC CIDR only | Internal management |
| Inbound | 5986 (WinRM HTTPS) | VPC CIDR only | Internal management |
| Outbound | All | `0.0.0.0/0` | Unrestricted egress |

Locking port 3389 to your IP `/32` is safer but breaks when your ISP changes your IP. Opening to `0.0.0.0/0` is convenient but exposes the port to automated scanners — use a strong password and consider a non-standard port (e.g. 33389) to reduce noise.

---

## Terraform Module

```
terraform/
├── modules/windows-server/
│   ├── main.tf       # EC2 instance resource
│   ├── data.tf       # AMI + VPC + subnet discovery
│   ├── security.tf   # Security group + rules
│   ├── iam.tf        # SSM instance profile
│   └── outputs.tf    # instance_id, public_ip, ssm commands
└── live/devtools/windows-server/
    └── terragrunt.hcl  # inputs: subnet filter, instance type, enabled flag
```

Key input variables:

| Variable | Purpose |
|---|---|
| `instance_enabled` | Set to `false` to destroy compute without touching the module |
| `private_subnet_tag_filter` | Tag name wildcard to select the subnet — use `natSubnet1` for direct internet access |
| `vpc_id` | Explicit VPC ID — leave empty to auto-discover |

```bash
cd terraform/live/devtools/windows-server
terragrunt apply
```

---

## How the IGW Delivers Inbound Packets — Behind the Scenes

When AWS assigns a public IP to an EC2 in a nat subnet, the Internet Gateway internally records a **1:1 mapping**:

```
Public IP  51.84.223.5  ←→  Private IP  10.3.67.28
```

This mapping lives inside the IGW itself — not in any route table you can see. AWS manages it automatically for the lifetime of the instance.

### Step by step — inbound RDP connection

```
1. Your machine sends a TCP packet:
   Source:      <your-ip>:54321
   Destination: 51.84.223.5:3389  (Windows Server public IP)

2. Packet travels the internet and arrives at the IGW

3. IGW checks its internal mapping table:
   "51.84.223.5 belongs to EC2 10.3.67.28"
   IGW rewrites the destination header:
   51.84.223.5:3389  →  10.3.67.28:3389

4. IGW checks the natSubnet route table:
   10.3.67.0/27 → local
   Packet delivered directly to the EC2 ✅

5. Windows RDP service receives the connection
```

### Step by step — reply going back out

```
6. EC2 sends the reply:
   Source:      10.3.67.28:3389   (private IP)
   Destination: <your-ip>:54321

7. natSubnet route table: 0.0.0.0/0 → IGW
   Packet goes to the IGW

8. IGW rewrites the source:
   10.3.67.28:3389  →  51.84.223.5:3389

9. Packet exits to the internet back to your machine ✅
```

### IGW vs NAT Gateway — the fundamental difference

```
IGW (1:1 NAT)
  51.84.223.5  ←→  10.3.67.28     two-way, permanent, one public IP per instance

NAT Gateway (many:1 NAT)
  10.3.65.5  ──┐
  10.3.65.6  ──┼──→  51.85.77.23  one-way, connection-tracked, many instances share one IP
  10.3.65.7  ──┘
```

The NAT Gateway only tracks connections **initiated from inside**. An unsolicited packet arriving from the internet has no entry in its connection table — it gets dropped. The IGW has no such restriction because it does a permanent 1:1 swap in both directions.

This is the entire reason why nat subnets support inbound connections and spoke subnets do not.
