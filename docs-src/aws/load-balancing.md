# Load Balancing — NLB, EC2 & EKS

How to expose services to traffic in this VPC — and what you need to add first.

---

## Why This VPC Has No Public Subnets

All six subnets in the spoke VPC are **isolated** — none have a direct Internet Gateway
route for incoming connections. The architecture was built for egress-only workloads:
resources call the internet, but nothing from the internet initiates a connection into
the VPC directly.

This means you **cannot place an internet-facing load balancer today** without adding
dedicated public subnets first.

There are two different scenarios:

| Goal | Requires public subnets? | Complexity |
|---|---|---|
| Internal NLB (VPC or org-internal traffic only) | ❌ No | Low — works today |
| Internet-facing NLB (expose to public internet) | ✅ Yes | Medium — add subnets first |

---

## How NLB Works Generally

An NLB (Network Load Balancer) operates at Layer 4 (TCP/UDP). It:

- Accepts connections on a **listener** (port + protocol)
- Forwards packets to a **target group** (a set of EC2 instances, IPs, or Lambda functions)
- Does **not** terminate TLS by default (passes raw TCP through) — though TLS termination is supported
- Preserves the client's source IP (unlike ALB which rewrites it)
- Has **no security groups itself** — access control lives on the targets

In this VPC, the NLB sits in subnets and the targets live in the spoke subnets.

---

## Option 1 — Internal NLB (no internet, works today)

Use this when the service only needs to be reachable **within the VPC** or from other
accounts in the same org (via Transit Gateway or VPC peering, when those exist).

### How it fits the architecture

```
VPC-internal client  (or future TGW/peering)
      ↓
Internal NLB  ←— place in spoke subnets (10.3.65.0/24 or 10.3.66.0/24)
      ↓
EC2 / EKS pod  ←— target group, also in spoke subnets
```

The NLB gets a private IP in the spoke subnet. No internet involved.

### Steps for EC2

1. **Create a target group** — type `instance`, protocol `TCP`, port of your app
2. **Register EC2 instances** in spoke subnets as targets
3. **Create NLB** — scheme `internal`, place in spoke subnets (`subnet-01996bb83a6db398c`, `subnet-0c8a2d1456074051e`)
4. **Add a listener** — TCP on port 80 (or 443) → forward to target group
5. **Security group on EC2** — allow TCP on app port from the spoke subnet CIDRs (`10.3.65.0/24`, `10.3.66.0/24`)

### Steps for EKS (Kubernetes Service)

Tag the spoke subnets so the AWS Load Balancer Controller knows where to place internal LBs:

```bash
# Subnet tags required on spoke subnets
kubernetes.io/cluster/<cluster-name>: shared
kubernetes.io/role/internal-elb: 1
```

Create a Service with these annotations:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "external"
    service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: "ip"
    service.beta.kubernetes.io/aws-load-balancer-scheme: "internal"
spec:
  type: LoadBalancer
  selector:
    app: my-app
  ports:
    - port: 80
      targetPort: 8080
      protocol: TCP
```

The AWS Load Balancer Controller creates an internal NLB in the spoke subnets, targeting pod IPs directly (`nlb-target-type: ip`).

---

## Option 2 — Internet-facing NLB (requires new public subnets)

### The problem

An internet-facing NLB needs to sit in a subnet that:
- Has a route `0.0.0.0/0 → Internet Gateway`
- Has `MapPublicIpOnLaunch: true` (or uses Elastic IPs on the NLB)

No current subnet satisfies both conditions. The NAT subnets have an IGW route but are
too small (`/27`, 26 IPs) and are reserved for NAT Gateways.

### The solution — add two public subnets

The VPC CIDR `10.3.64.0/22` has free space in `10.3.64.64–10.3.64.255`.
Add one `/27` public subnet per AZ:

| Proposed name | CIDR | AZ | Purpose |
|---|---|---|---|
| `publicSubnet1` | `10.3.64.64/27` | 1a | Internet-facing NLB node |
| `publicSubnet2` | `10.3.64.96/27` | 1b | Internet-facing NLB node |

Each subnet needs:
- Route table: `0.0.0.0/0 → igw-0d54a13bd04e6242e`
- `MapPublicIpOnLaunch: false` — the NLB will use Elastic IPs (fixed IPs, not ephemeral)

> **Why not use the existing NAT subnets?** They have IGW routes, but they're occupied
> by NAT Gateways and mixing NLBs there would complicate routing and is not supported
> by AWS Load Balancer Controller subnet discovery.

### Traffic flow with internet-facing NLB

```
Internet
  ↓
Internet Gateway (igw-0d54a13bd04e6242e)
  ↓  (direct — no hub firewall on inbound to public subnets)
NLB  (public subnet — 10.3.64.64/27 or 10.3.64.96/27)
  ↓  forwards to target group
EC2 / EKS pod  (spoke subnet — 10.3.65.0/24 or 10.3.66.0/24)
```

> **Security note:** inbound traffic from the internet to the public subnets does
> **not** pass through the hub firewall — the IGW route table only routes traffic
> destined for spoke subnet CIDRs through the firewall endpoints. Traffic to the
> NLB's public subnet goes directly. The NLB's listener rules and the target's
> security group are your access control here.
>
> If your org requires hub firewall inspection of inbound internet traffic, this
> design needs to be reviewed with the network/security team before deploying.

### Steps to add the public subnets (CDK)

In your CDK stack (the `SPOKE-Networking` stack), add:

```typescript
const publicSubnet1 = new ec2.Subnet(this, 'publicSubnet1', {
  vpcId: vpc.vpcId,
  cidrBlock: '10.3.64.64/27',
  availabilityZone: 'il-central-1a',
  mapPublicIpOnLaunch: false,
});

const publicSubnet2 = new ec2.Subnet(this, 'publicSubnet2', {
  vpcId: vpc.vpcId,
  cidrBlock: '10.3.64.96/27',
  availabilityZone: 'il-central-1b',
  mapPublicIpOnLaunch: false,
});

// Route both public subnets to the existing IGW
new ec2.CfnRoute(this, 'publicSubnet1DefaultRoute', {
  routeTableId: publicSubnet1.routeTable.routeTableId,
  destinationCidrBlock: '0.0.0.0/0',
  gatewayId: igw.ref,
});

new ec2.CfnRoute(this, 'publicSubnet2DefaultRoute', {
  routeTableId: publicSubnet2.routeTable.routeTableId,
  destinationCidrBlock: '0.0.0.0/0',
  gatewayId: igw.ref,
});
```

### Steps for EC2 after adding public subnets

1. **Create a target group** — type `instance`, TCP, your app port
2. **Register EC2 instances** (in spoke subnets) as targets
3. **Create NLB** — scheme `internet-facing`, place in **public subnets** (`publicSubnet1`, `publicSubnet2`)
4. **Assign Elastic IPs** to the NLB nodes (optional but recommended for fixed public IPs)
5. **Listener** — TCP 443 → target group
6. **Security group on EC2** — allow TCP on app port from public subnet CIDRs (`10.3.64.64/27`, `10.3.64.96/27`)

> NLBs do not have security groups themselves — you must allow traffic on the **EC2 security group**
> from the NLB subnet CIDRs, not from the NLB itself.

### Steps for EKS after adding public subnets

Tag the subnets so the AWS Load Balancer Controller can discover them:

```bash
# On PUBLIC subnets — for internet-facing LBs
kubernetes.io/cluster/<cluster-name>: shared
kubernetes.io/role/elb: 1

# On SPOKE subnets — for internal LBs and pod targets
kubernetes.io/cluster/<cluster-name>: shared
kubernetes.io/role/internal-elb: 1
```

Create a Service:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-public-service
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "external"
    service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: "ip"
    service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
spec:
  type: LoadBalancer
  selector:
    app: my-app
  ports:
    - port: 443
      targetPort: 8443
      protocol: TCP
```

The controller creates an internet-facing NLB in the public subnets, with pod IPs in
the spoke subnets as targets.

---

## ALB vs NLB — Which to Use

| | NLB | ALB |
|---|---|---|
| Layer | 4 (TCP/UDP) | 7 (HTTP/HTTPS) |
| TLS termination | Supported (pass-through or terminate) | Supported |
| Source IP preserved | ✅ Yes | ❌ No (uses X-Forwarded-For) |
| Security groups | ❌ Not on NLB itself | ✅ Yes, on ALB |
| Path/host routing | ❌ No | ✅ Yes |
| WebSockets | ✅ Yes | ✅ Yes |
| Static IP / Elastic IP | ✅ Yes | ❌ No (use Global Accelerator) |
| In EKS | `Service type: LoadBalancer` | `Ingress` (needs ALB Ingress Controller) |

**Use NLB** when you need fixed IPs, low latency, raw TCP, or source IP preservation.  
**Use ALB** when you need path/host routing, WAF integration, or HTTP-level health checks.

Both use the same public subnet requirement for internet-facing deployment.

---

## AWS Load Balancer Controller (EKS prerequisite)

The AWS Load Balancer Controller is a Kubernetes controller that manages NLBs and ALBs
for EKS. Without it, EKS uses the legacy in-tree cloud controller which creates Classic
Load Balancers (CLBs) — avoid those.

**Install via Helm:**

```bash
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=<cluster-name> \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
```

**Required IAM policy:** the controller's service account needs an IAM role with the
`AWSLoadBalancerControllerIAMPolicy`. Create using IRSA (IAM Roles for Service Accounts).

---

## Summary — What to Do First

```
Want internal NLB only?
  → Deploy today. Place NLB in spoke subnets.
  → Tag spoke subnets with kubernetes.io/role/internal-elb: 1 for EKS.

Want internet-facing NLB?
  → Step 1: Add publicSubnet1 (10.3.64.64/27, AZ 1a) and
             publicSubnet2 (10.3.64.96/27, AZ 1b) in CDK.
  → Step 2: Route both to the existing Internet Gateway.
  → Step 3: Tag with kubernetes.io/role/elb: 1 for EKS.
  → Step 4: Deploy NLB/ALB in public subnets, targets in spoke subnets.
  → Step 5: Allow traffic on EC2/pod security groups from public subnet CIDRs.
```
