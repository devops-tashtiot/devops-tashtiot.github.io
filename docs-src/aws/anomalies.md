# Governance Anomalies

Things found while probing this account's [SCP Limitations](scp-limitations.md) that stood out as
**surprising** — actions a security-conscious control-plane owner would typically expect to be
locked down in a Control Tower-managed Landing Zone, but that this account's actual guardrails
don't restrict. Every entry here was verified the same way as the SCP Limitations page (`--dry-run`
where available, or a real create-and-immediately-clean-up test where it wasn't) — nothing here is
speculative.

This page isn't a criticism of a specific decision — some of these may be entirely intentional
tradeoffs. It exists so nobody assumes a protection exists here that was never actually verified.

---

## `ec2:DeleteInternetGateway` is allowed, despite `ec2:CreateInternetGateway` being denied

The clearest anomaly found. This account's network-topology lockdown (see the "No new
internet-facing network egress/ingress points" entry on [SCP Limitations](scp-limitations.md))
blocks creating a *new* Internet Gateway, and — consistently — blocks *deleting* the existing VPC,
subnets, NAT Gateway, and VPC endpoint. But `ec2:DetachInternetGateway` and
`ec2:DeleteInternetGateway` on the account's one existing IGW both returned `DryRunOperation`
(permitted), confirmed via `--dry-run` against the real, in-use IGW
(`igw-0d54a13bd04e6242e`) — not a hypothetical one.

**Why this is dangerous**: the IGW is the single resource this account's entire public internet
reachability depends on. Every other network-topology guardrail on this page protects its
resource from deletion symmetrically with its creation restriction — the IGW is the one exception.
Anyone with this account's admin role could detach and delete it right now, severing all public
connectivity for every resource in the VPC, and no SCP would stop them.

**Expected**: given every sibling resource (VPC, subnet, NAT Gateway, VPC endpoint) is protected
from deletion by the same policy family, the IGW would reasonably be expected to be covered too.

## IAM privilege escalation via `AttachRolePolicy` is not blocked

Confirmed by creating a throwaway role and attaching `AdministratorAccess` to it directly —
succeeded, then cleaned up immediately. The "no standing IAM users" restriction
([SCP Limitations](scp-limitations.md)) closes the *identity-creation* door, but nothing stops a
role this account is otherwise allowed to create from being granted full administrator access.
Whatever prevents this in practice is IAM permission scoping/process discipline on who can call
`iam:CreateRole`/`iam:AttachRolePolicy`, not an SCP guardrail.

## No detective controls back up the preventive SCPs

Three separate checks, all read-only, all confirmed:

- AWS Config's baseline recorder is actively recording — but **zero Config Rules** are attached to
  this account (`describe-config-rules` returns an empty list).
- **Zero GuardDuty detectors** exist in this account (`list-detectors` returns an empty list).
- **No CloudFormation StackSets** are visible from this account, including a known Control Tower
  guardrail StackSet name that returned `StackSetNotFoundException`.

**Why this is notable**: the SCPs on [SCP Limitations](scp-limitations.md) are this account's
*entire* verified preventive layer — there's no local compliance-monitoring layer to catch a
misconfiguration that falls outside what an SCP happens to cover (like the IGW deletion gap
above). If detective monitoring exists for this org, it isn't visible or running from this
account.

## An idle NAT Gateway has been running unused for at least 7 days, and this account can't delete it

This VPC has two NAT Gateways, one per AZ (`natSubnet1`/`natSubnet2` — part of the shared spoke
network, not something `devtools-labs` created):

| NAT Gateway | Subnet | Route table associations | Traffic (last 7 days) |
|---|---|---|---|
| `nat-0fc371e4278247404` | `natSubnet1` (`il-central-1a`) | 2 subnets | 16MB–599MB/day — actively used |
| `nat-03d2ad88c6d3bcda9` | `natSubnet2` (`il-central-1b`) | **0 subnets** | **0 bytes every single day** |

The second one's own route table (`rtb-0f4a9c7ec7f42af28`) has no subnet associated with it at
all — nothing can route through it even if it wanted to — and CloudWatch confirms zero
`BytesOutToDestination` for all 7 days checked. It's just running, billing per-hour (NAT Gateways
bill hourly regardless of traffic), for nothing.

**Why this is worse than ordinary waste**: per [SCP Limitations](scp-limitations.md),
`ec2:DeleteNatGateway` is explicitly denied by policy `p-yb5x5s6s` — the same policy that blocks
*creating* a new one. This workload account is structurally unable to clean this up itself, even
though it's clearly and verifiably serving no purpose. Removing it requires the same
management-account-level access that created it in the first place.

---

## Related Topics

- [SCP Limitations](scp-limitations.md) — the full reference this page's findings were sourced
  from, including everything confirmed *restricted*
- [Control Tower](control-tower.md) — the governance model these SCPs are pushed down from
