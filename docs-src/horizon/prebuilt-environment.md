# The Prebuilt Environment: What "Horizon" Provisions

This AWS account isn't a blank slate — it's a workload account inside a
**Horizon**-branded Landing Zone (a Control Tower-based multi-account setup;
see [Control Tower](../aws/control-tower.md) for how that governs this
account generally). This page covers what's specific to *this* account
that `devops-tashtiot`'s own repos didn't create, and the concrete limits
that come with it.

## The network is not yours to redesign

The account ships with exactly one VPC
(`sandboxclouddevelopment-prd-001-spoke-vpc`, `10.3.64.0/22`), a hub-and-spoke
design with centralized, cross-account firewall inspection and no per-workload
NAT Gateway to create — full breakdown in [VPC Architecture](../aws/vpc-architecture.md).
The practical consequence for anything built here: reuse `spokeSubnet1`/
`spokeSubnet2` and the existing egress path, don't provision your own VPC,
NAT Gateway, or Internet Gateway. `devtools-labs`' own EKS module does
exactly this — see its `terraform/modules/eks/main.tf` comments on reusing
the existing subnets and shared VPC endpoint instead of adding new network
resources.

## Governance is pushed from above

Service Control Policies and IAM Identity Center roles are defined in a
management account and pushed here — you can't view or override them, and
some AWS API calls fail outright with an SCP-level `AccessDenied` no matter
what IAM permissions your own role has. See
[Control Tower](../aws/control-tower.md) for the full mechanism and the
running list of SCP restrictions discovered so far (e.g.
`identitystore:ListUsers` is denied from this account).

Human access is entirely via IAM Identity Center SSO roles
(`AWSReservedSSO_Workload-Admin-PS` and similar) — no standing IAM users.

## A dormant OpenShift cluster already lives here

Four EC2 instances predate any `devops-tashtiot` work in this account,
tagged `AccountAlias: horizon`, `Project: openshift-upi`, `ManagedBy: terraform`,
and `kubernetes.io/cluster/horizon-79jz5: owned`:

| Instance | Type | Role |
|---|---|---|
| `horizon-horizon-bastion` | `t3.medium` | Bastion — also runs the cluster's internal CoreDNS (its ignition config points cluster nodes at it for DNS) |
| `horizon-horizon-master-0/1/2` | `m5.xlarge` ×3 | OpenShift control-plane nodes (UPI — User Provisioned Infrastructure, the manual/Terraform-driven install method, not the installer-managed one) |

All four are currently **stopped**. There's also a small, otherwise-unused
EFS filesystem (`horizon-horizon-efs`) that predates the devtools platform's
own EFS (`devtools-eks-shared-home`) and isn't related to it.

This cluster lives in the same VPC/subnets (`spokeSubnet1`) as the devtools
platform's own EKS nodes, but is otherwise fully independent — no shared
security groups, IAM roles, or Terraform state with anything in
`devops-tashtiot`. Its practical relevance here is just: don't assume an
account audit showing EC2/EFS resources means something in this platform
is running that isn't — check tags (`Project: openshift-upi` vs. this
platform's own tags) before investigating further.

## What this means in practice

- No NAT Gateway, Internet Gateway, or new VPC to provision — reuse what's here.
- Some read-only AWS API calls are SCP-blocked regardless of IAM permissions; check the Control Tower page's restriction table before assuming it's a permissions bug.
- EC2/EFS resources tagged `horizon`/`openshift-upi` are pre-existing and unrelated to `devops-tashtiot` — don't decommission or repurpose them without confirming first.
