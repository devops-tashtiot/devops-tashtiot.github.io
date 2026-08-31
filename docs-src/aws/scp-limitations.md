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

### No new internet-facing network egress/ingress points

| Denied action | Policy ID |
|---|---|
| `ec2:CreateVpc` | `p-yb5x5s6s` |
| `ec2:CreateInternetGateway` | `p-yb5x5s6s` |
| `ec2:CreateNatGateway` | `p-yb5x5s6s` |
| `ec2:CreateTransitGateway` | `p-yb5x5s6s` |
| `ec2:CreateVpnGateway` | `p-yb5x5s6s` |
| `ec2:CreateEgressOnlyInternetGateway` | `p-yb5x5s6s` |
| `ec2:AllocateAddress` (new Elastic IP) | `p-yb5x5s6s` |

**What this means in practice**: this account can never create a new path in or out of the VPC to
the public internet, another VPC (via VPN), or acquire a new public IP. Every Terraform module
here must reuse whatever egress path and IP allocations already exist. This is the actual,
verified root cause behind `devtools-labs/terraform/modules/eks`'s design — reusing
`spokeSubnet1`/`spokeSubnet2`, an existing shared VPC endpoint for `0.0.0.0/0` egress, and (for
the NAT Gateway dry-run test used to confirm this) an already-allocated Elastic IP rather than a
fresh one — confirmed here as a hard SCP restriction, not just a cost-driven choice.

**Confirmed still allowed**, for contrast: `ec2:CreateCustomerGateway` (inert without a VPN
Gateway to pair it with, which is itself blocked), `ec2:CreateDhcpOptions`, and
`ec2:CreateFlowLogs` (security/observability tooling isn't restricted).

### No new subnets or route tables

| Denied action | Policy ID |
|---|---|
| `ec2:CreateSubnet` | `p-wptrsvas` |
| `ec2:CreateRouteTable` | `p-wptrsvas` |

Same practical effect as the previous section, one level down: even carving up the *existing* VPC
further, or adding new routing, is blocked — not just adding new top-level network objects.

### No new VPC peering or VPC endpoints

| Denied action | Policy ID |
|---|---|
| `ec2:CreateVpcPeeringConnection` | `p-uya91w09` |
| `ec2:CreateVpcEndpoint` | `p-uya91w09` |

### Confirmed NOT restricted (tested, allowed)

To keep this page honest about the actual boundary, not just what's denied — these were tested
and returned `DryRunOperation` (permitted):

- `ec2:RunInstances` — plain instance launch into an existing subnet, including large/GPU
  instance types (tested with `p4d.24xlarge`) — no instance-type-based SCP restriction found.
- `ec2:CreateSecurityGroup`
- `ec2:CreateCustomerGateway`, `ec2:CreateDhcpOptions`, `ec2:CreateFlowLogs`

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
