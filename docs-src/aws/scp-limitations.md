# SCP Limitations

A running reference of Service Control Policy (SCP) restrictions discovered while working in
this account, so nobody re-attempts the same blocked approach without checking here first. SCPs
in this Control Tower-managed Landing Zone are pushed down from the management account — see
[Control Tower](control-tower.md) for how that governance model works. Member-account roles
(including full workload admins) cannot view or override an SCP; it just silently denies the
underlying API call, regardless of the caller's own IAM permissions.

Everything below the Identity Center entry was confirmed by direct, safe probing of this
account — `ec2:*` calls with the `--dry-run` flag (which evaluates permissions/SCPs without ever
executing the action), and for non-dry-run-capable calls, relying on the fact that an explicit
deny stops the call before anything is created or read. No real resource was created and no
region setting was permanently changed to produce these findings.

---

## Known Restrictions

### Identity Center directory/user listing (`identitystore:ListUsers`)

| | |
|---|---|
| **Denied actions** | `identitystore:ListUsers`, `sso-directory:ListUsers`, `sso-directory:SearchUsers` |
| **What it blocks** | Inspecting IAM Identity Center's provisioned users, or checking Identity Center's sync status with its external identity source (directory/SCIM), from a workload-account role |
| **Symptom** | `AccessDenied` — the error message includes "explicit deny in a service control policy," distinguishing it from a plain IAM permission gap |
| **Workaround** | None via CLI/API. Check in the Identity Center console instead (**Settings → Identity source → Provisioning**), which runs in the management-account context, not this workload account |

### Organizations policy visibility

| | |
|---|---|
| **Denied actions** | `organizations:DescribeOrganization`, `organizations:ListPoliciesForTarget` |
| **What it blocks** | Reading the account's own SCPs directly — you can't list which policies are attached or fetch their JSON from inside the workload account |
| **Symptom** | `AccessDeniedException: You don't have permissions to access this resource` |
| **Workaround** | None from this account. This is exactly why the restrictions on this page were found by empirically probing individual actions with `--dry-run` rather than reading the policy documents themselves — nobody in a workload account can do the latter. |

### Region lock — almost everything is restricted to `il-central-1`

| | |
|---|---|
| **Policy ID** | `p-cf140vwn` |
| **Denied actions** | Confirmed on `ec2:DescribeSubnets`, `rds:DescribeDBInstances`, `lambda:ListFunctions`, `s3:ListAllMyBuckets` — even plain reads — the moment the request targets any region other than `il-central-1` |
| **Exempted** | IAM (`iam:ListRoles` succeeded regardless of region) — consistent with IAM being a global control-plane service. STS/Organizations are very likely exempted the same way, though not directly tested. |
| **Symptom** | `UnauthorizedOperation`/`AccessDenied` with "explicit deny in a service control policy," even for read-only calls |
| **Workaround** | None. Stay in `il-central-1` for anything regional. This is also why this account's [enabled-regions list](https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-regions.html) being long (18 regions) doesn't mean those regions are actually usable from this workload account — enabled and permitted are different things. |

### No new internet-facing network egress/ingress points — and no deleting the existing ones either

| Denied action | Policy ID |
|---|---|
| `ec2:CreateVpc` / `ec2:DeleteVpc` | `p-yb5x5s6s` |
| `ec2:CreateNatGateway` / `ec2:DeleteNatGateway` | `p-yb5x5s6s` |
| `ec2:CreateTransitGateway` | `p-yb5x5s6s` |
| `ec2:CreateVpnGateway` | `p-yb5x5s6s` |
| `ec2:CreateEgressOnlyInternetGateway` | `p-yb5x5s6s` |
| `ec2:AllocateAddress` (new Elastic IP) | `p-yb5x5s6s` |

**What this means in practice**: this account can never create a new path in or out of the VPC to
the public internet, another VPC (via VPN), or acquire a new public IP — and, notably, this cuts
both ways for VPCs and NAT Gateways specifically: deleting the *existing* one is blocked by the
same policy as creating a new one, not just a one-way "no more of these" rule. Every Terraform
module here must reuse whatever egress path and IP allocations already exist. This is the actual,
verified root cause behind `devtools-labs/terraform/modules/eks`'s design — reusing
`spokeSubnet1`/`spokeSubnet2`, an existing shared VPC endpoint for `0.0.0.0/0` egress, and (for
the NAT Gateway dry-run test used to confirm this) an already-allocated Elastic IP rather than a
fresh one — confirmed here as a hard SCP restriction, not just a cost-driven choice.

**Not symmetric across every resource type, though** — `ec2:CreateInternetGateway` is denied, but
both `ec2:DetachInternetGateway` and `ec2:DeleteInternetGateway` on the *existing* one returned
`DryRunOperation` (permitted). Don't assume "creation blocked" implies "deletion blocked" for
every resource type here; each was verified independently.

**Confirmed still allowed**, for contrast: `ec2:CreateCustomerGateway` (inert without a VPN
Gateway to pair it with, which is itself blocked), `ec2:CreateDhcpOptions`, `ec2:CreateFlowLogs`
(security/observability tooling isn't restricted), and disabling EBS-default-encryption
(`ec2:DisableEbsEncryptionByDefault`) — no guardrail against that specific action was found.

### No new subnets or route tables — and no deleting the existing ones either

| Denied action | Policy ID |
|---|---|
| `ec2:CreateSubnet` / `ec2:DeleteSubnet` | `p-wptrsvas` |
| `ec2:CreateRouteTable` | `p-wptrsvas` |

Same practical effect as the previous section, one level down, and the same two-way lock: even
carving up the *existing* VPC further, or adding new routing, is blocked — and so is deleting an
existing subnet.

### No new VPC peering or VPC endpoints

| Denied action | Policy ID |
|---|---|
| `ec2:CreateVpcPeeringConnection` | `p-uya91w09` |
| `ec2:CreateVpcEndpoint` | `p-uya91w09` |

### AMI public sharing is blocked

| | |
|---|---|
| **Denied action** | `ec2:ModifyImageAttribute` (adding launch permission for `Group=all`) |
| **Policy ID** | `p-iwp39iza` |
| **What it blocks** | Making any AMI in this account publicly shared |
| **Confirmed still allowed** | Sharing an AMI with a specific other account ID wasn't tested — only the `all` (public) group was |

### Route53 is entirely off-limits — not just hosted-zone creation

| | |
|---|---|
| **Policy ID** | `p-77bk5ceo` |
| **Denied actions** | `route53:CreateHostedZone` (confirmed by direct attempt, not dry-run — Route53 doesn't support `--dry-run`; the explicit deny stopped it before any zone was created), plus even the purely read-only `route53:ListHostedZones` |
| **What it blocks** | Route53 appears to be blocked wholesale in this account, reads included, not narrowly scoped to zone creation |
| **Why this matters** | This is why `devtools-labs/terraform/modules/domain-controller` doesn't use a private Route53 hosted zone for a stable LDAP endpoint (tried first, per that module's own comments) — it publishes the domain controller's current private IP to an SSM parameter (`/devops/terraform-created/domain-controller/ldap-connection-url`) instead, refreshed on every apply, since RHBK needs a stable address to read but Route53 was never an option here |
| **Workaround** | None from this account for DNS. Use SSM (or another mechanism outside Route53) for any "stable name for a thing whose IP can change" need |

### Confirmed NOT restricted (tested, allowed)

To keep this page honest about the actual boundary, not just what's denied — these were tested
and returned `DryRunOperation` (permitted):

- `ec2:RunInstances` — plain instance launch into an existing subnet, including large/GPU
  instance types (tested with `p4d.24xlarge`) — no instance-type-based SCP restriction found.
- `ec2:CreateSecurityGroup`, and authorizing a wide-open ingress rule
  (`0.0.0.0/0` on port 22) on an existing security group — no SCP guardrail against permissive
  security group rules was found (a Config rule may still flag this detectively, but nothing
  preventively blocks it at the SCP layer).
- `ec2:CreateCustomerGateway`, `ec2:CreateDhcpOptions`, `ec2:CreateFlowLogs`
- `ec2:DisableEbsEncryptionByDefault`
- `ec2:DetachInternetGateway`, `ec2:DeleteInternetGateway` (on the existing IGW) — see the
  asymmetry noted above.

### No standing IAM users (`iam:CreateUser`)

| | |
|---|---|
| **Denied action** | `iam:CreateUser` |
| **Policy ID** | `p-cf140vwn` (same policy as the region lock above — a combined policy with multiple deny statements, not two separate SCPs) |
| **What it blocks** | Creating any IAM user in this account at all |
| **Symptom** | `AccessDenied` with the same "explicit deny in a service control policy" marker |
| **Why** | Matches the SSO model described in [Control Tower](control-tower.md) — all human access is meant to flow through IAM Identity Center roles pushed from the management account, not standing per-account IAM users |
| **Workaround** | None — this is enforced by design. Use an Identity Center permission set instead. |

---

## Related Topics

- [Control Tower](control-tower.md) — how SCPs fit into the broader multi-account governance model
- [IAM Roles](iam-roles.md) — the roles these restrictions apply to
