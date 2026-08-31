# SCP Limitations

A running reference of Service Control Policy (SCP) restrictions discovered while working in
this account, so nobody re-attempts the same blocked approach without checking here first. SCPs
in this Control Tower-managed Landing Zone are pushed down from the management account — see
[Control Tower](control-tower.md) for how that governance model works. Member-account roles
(including full workload admins) cannot view or override an SCP; it just silently denies the
underlying API call, regardless of the caller's own IAM permissions.

Everything below the Identity Center entry was confirmed by direct, safe probing of this
account — `ec2:*` calls with the `--dry-run` flag (which evaluates permissions/SCPs without ever
executing the action), and for the one non-dry-run-capable case (`iam:CreateUser`) relying on the
fact that an explicit deny stops the call before anything is created. No real resource was
created to produce these findings.

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

### Network topology is fully locked — no new VPC, subnet, gateway, peering, or endpoint

Every action that would change this account's network topology is explicitly denied, across at
least three distinct SCP policy IDs:

| Denied action | Policy ID |
|---|---|
| `ec2:CreateVpc` | `p-yb5x5s6s` |
| `ec2:CreateInternetGateway` | `p-yb5x5s6s` |
| `ec2:CreateNatGateway` | `p-yb5x5s6s` |
| `ec2:CreateTransitGateway` | `p-yb5x5s6s` |
| `ec2:CreateSubnet` | `p-wptrsvas` |
| `ec2:CreateVpcPeeringConnection` | `p-uya91w09` |
| `ec2:CreateVpcEndpoint` | `p-uya91w09` |

**What this means in practice**: any Terraform module in this account must reuse the existing
VPC, subnets, and egress path — it can never provision its own. This is the actual, verified root
cause behind `devtools-labs/terraform/modules/eks`'s design (reusing `spokeSubnet1`/
`spokeSubnet2` and an existing shared VPC endpoint for `0.0.0.0/0` egress instead of creating a
NAT Gateway or a new VPC) — confirmed here as a hard SCP restriction, not just a cost-driven
choice.

**Confirmed still allowed**, for contrast: `ec2:RunInstances` (plain instance launch into an
existing subnet) and `ec2:CreateSecurityGroup` both returned `DryRunOperation` (i.e. permitted) —
the lockdown is specifically on topology-defining resources, not on using the network that
already exists.

### No standing IAM users (`iam:CreateUser`)

| | |
|---|---|
| **Denied action** | `iam:CreateUser` |
| **Policy ID** | `p-cf140vwn` |
| **What it blocks** | Creating any IAM user in this account at all |
| **Symptom** | `AccessDenied` with the same "explicit deny in a service control policy" marker |
| **Why** | Matches the SSO model described in [Control Tower](control-tower.md) — all human access is meant to flow through IAM Identity Center roles pushed from the management account, not standing per-account IAM users |
| **Workaround** | None — this is enforced by design. Use an Identity Center permission set instead. |

---

## Related Topics

- [Control Tower](control-tower.md) — how SCPs fit into the broader multi-account governance model
- [IAM Roles](iam-roles.md) — the roles these restrictions apply to
