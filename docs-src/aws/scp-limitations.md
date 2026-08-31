# SCP Limitations

A running reference of Service Control Policy (SCP) restrictions discovered while working in
this account, so nobody re-attempts the same blocked approach without checking here first. SCPs
in this Control Tower-managed Landing Zone are pushed down from the management account — see
[Control Tower](control-tower.md) for how that governance model works. Member-account roles
(including full workload admins) cannot view or override an SCP; it just silently denies the
underlying API call, regardless of the caller's own IAM permissions.

Everything below the Identity Center entry was confirmed by direct probing of this account:
`ec2:*` calls with the `--dry-run` flag (which evaluates permissions/SCPs without ever executing
the action) wherever available; for non-dry-run-capable calls, relying on the fact that an
explicit deny stops the call before anything is created or read; and for the one test needing a
real resource (IAM role/policy attachment), creating a throwaway resource and deleting it
immediately after confirming the result. No resource was left behind, and no region setting was
permanently changed, to produce these findings. Riskier categories with no safe test method
(load-balancer creation with real cost, CloudTrail/Config/GuardDuty disable actions where a false
"allowed" would be a real security regression, KMS key creation where pending-deletion has a
mandatory 7+ day minimum) were deliberately left untested rather than risked.

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

### Region lock — restricted to `il-central-1` **and** `us-east-1`, not just one region

**Correction**: an earlier version of this entry said "almost everything is restricted to
`il-central-1`" — that was incomplete. `us-east-1` is a second fully-allowed region, confirmed by
re-testing the same read-only calls that were denied in `us-west-2`/`ap-southeast-2`/
`eu-central-1`/`ap-south-1` — all of them (`ec2:DescribeSubnets`, `rds:DescribeDBInstances`,
`s3:ListAllMyBuckets`, `lambda:ListFunctions`) succeed with real data when targeted at
`us-east-1` instead (an actual S3 bucket and an actual `aws-controltower-NotificationForwarder`
Lambda function both showed up there). This makes sense in hindsight — `us-east-1` is where a lot
of AWS's own control-plane/global-service machinery runs, including this account's own Control
Tower automation, so it's a common inclusion in any region-restriction SCP's allowlist. This is
also, not coincidentally, why `devtools-labs/terraform/modules/backup`'s cross-region DR copy
target is `us-east-1` and actually works — it's specifically an allowed region, not just one that
happened to pass an earlier read-only check.

| | |
|---|---|
| **Policy ID** | `p-cf140vwn` |
| **Allowed regions** | `il-central-1` (this account's home region) and `us-east-1` |
| **Denied actions** | Confirmed on `ec2:DescribeSubnets`, `rds:DescribeDBInstances`, `lambda:ListFunctions`, `s3:ListAllMyBuckets` — even plain reads — the moment the request targets any region **other than those two** (tested and denied: `us-west-2`, `ap-southeast-2`, `eu-central-1`, `ap-south-1`, `eu-west-1`, `ap-northeast-1`, `ca-central-1` — seven regions checked, all denied, confirming the allowlist is exactly `{il-central-1, us-east-1}` and not a longer list) |
| **Exempted (in addition to the two allowed regions)** | IAM (`iam:ListRoles` succeeded regardless of region) — consistent with IAM being a global control-plane service. STS/Organizations are very likely exempted the same way, though not directly tested. |
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
| `ec2:CreateRoute` (adding a route to an *existing* route table) | `p-wptrsvas` |
| `apigateway:POST` on `/restapis` (creating a REST API) | `p-wptrsvas` |

That last one is a genuine surprise — this same policy also blocks creating an API Gateway REST
API, not just EC2 networking primitives. Whatever this policy's actual scope is, it isn't limited
to "VPC-adjacent" resources the way its other members suggested. Confirmed it's not REST-API-
specific either: `apigatewayv2:CreateApi` (HTTP/WebSocket APIs) is denied by the same
`p-wptrsvas` — the block covers API Gateway as a whole. AppSync (GraphQL APIs) is a separate
service and is **not** covered by this or any other policy — tested by creating and immediately
deleting one.

**A related but distinct case — Global Accelerator**: `globalaccelerator:CreateAccelerator` is
also denied, but by `p-cf140vwn` (the region-lock policy), not this one. Global Accelerator's API
only exists in the `us-west-2` endpoint regardless of where you'd actually want the accelerator —
and `us-west-2` isn't in this account's two allowed regions (`il-central-1`, `us-east-1`), so this
is very likely collateral from the region lock rather than a deliberate "no Global Accelerator"
rule.

Same practical effect as the previous section, one level down, and the same two-way lock: even
carving up the *existing* VPC further, or adding new routing, is blocked — and so is deleting an
existing subnet.

### No new VPC peering or VPC endpoints — and no deleting the existing endpoint either

| Denied action | Policy ID |
|---|---|
| `ec2:CreateVpcPeeringConnection` | `p-uya91w09` |
| `ec2:CreateVpcEndpoint` / `ec2:DeleteVpcEndpoints` | `p-uya91w09` |

The existing shared VPC endpoint this whole platform's egress depends on can't be deleted either
— same two-way lock pattern as the VPC/subnet/NAT Gateway restrictions above.

### Public sharing of AMIs and snapshots is blocked

| Denied action | Policy ID |
|---|---|
| `ec2:ModifyImageAttribute` (adding launch permission for `Group=all`) | `p-iwp39iza` |
| `ec2:ModifySnapshotAttribute` (adding create-volume permission for `Group=all`) | `p-iwp39iza` |

Same policy blocks both — this is a general "no public AMIs or snapshots" rule, not narrowly
scoped to one resource type. Sharing with a specific other account ID (rather than the public
`all` group) wasn't tested for either.

### Route53 is entirely off-limits — not just hosted-zone creation

| | |
|---|---|
| **Policy ID** | `p-77bk5ceo` |
| **Denied actions** | `route53:CreateHostedZone` (confirmed by direct attempt, not dry-run — Route53 doesn't support `--dry-run`; the explicit deny stopped it before any zone was created), the purely read-only `route53:ListHostedZones`, and the same read-only denial extends to the **separate** `route53resolver:*` and `route53domains:*` API namespaces (`ListResolverEndpoints`, `ListDomains`) — all three fall under this one policy |
| **What it blocks** | Every Route53-family service is blocked wholesale in this account — core DNS, Resolver, and domain registration alike — not narrowly scoped to hosted-zone creation |
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
- `ec2:CreateKeyPair`, `ec2:CreateLaunchTemplate`, `ec2:CreateVolume` (unattached EBS),
  `ec2:ModifyInstanceMetadataOptions` (IMDSv2 enforcement) — no restrictions found on any of
  these.
- `ec2:CreateNetworkAcl`, `ec2:RequestSpotInstances`, `ec2:CreateSnapshot`,
  `ec2:TerminateInstances`, `ec2:StopInstances` (on an existing instance) — no restrictions found.
- `ec2:CopySnapshot` with a destination region of `us-east-1` — expected, given `us-east-1` is a
  fully allowed region (see the region-lock correction above), but confirms cross-region data
  replication into it specifically works, not just plain resource access.
- `ec2:ReleaseAddress` (releasing an *existing* Elastic IP) — asymmetric with
  `ec2:AllocateAddress` (a new one) being denied: this account can free up EIP usage but can't
  acquire more.
- `ssm:PutParameter` with `--tier Advanced` (the paid tier) — no cost-control guardrail found;
  tested by creating and immediately deleting one, no charge incurred.
- `sns:CreateTopic`, `sqs:CreateQueue`, `cloudwatch:PutMetricAlarm`,
  `secretsmanager:CreateSecret` — none of these non-EC2 services (which don't support
  `--dry-run`) are SCP-restricted either; each was created for real and deleted immediately after
  (Secrets Manager via `--force-delete-without-recovery`, bypassing its normal 7-30 day recovery
  window, so nothing lingered).
- `ce:GetCostAndUsage` (Cost Explorer, read-only) — not restricted.
- `dynamodb:CreateTable`, `wafv2:CreateWebACL`, `appsync:CreateGraphqlApi` — all created for
  real and deleted immediately after; not restricted.
- `rds:CreateDBSnapshot` — a real manual snapshot of the live `devtools-rds` instance, created
  and deleted immediately after (redundant with the existing AWS Backup daily plan); not
  restricted.
- `bedrock:ListFoundationModels`, `bedrock:GetModelInvocationLoggingConfiguration` (both
  read-only) — not restricted. Consistent with this account's existing
  `lz-integration-bedrock-cloudwatch-*` roles, which imply Bedrock is already in active use here.

### No standing IAM users (`iam:CreateUser`)

| | |
|---|---|
| **Denied action** | `iam:CreateUser` |
| **Policy ID** | `p-cf140vwn` (same policy as the region lock above — a combined policy with multiple deny statements, not two separate SCPs) |
| **What it blocks** | Creating any IAM user in this account at all |
| **Symptom** | `AccessDenied` with the same "explicit deny in a service control policy" marker |
| **Why** | Matches the SSO model described in [Control Tower](control-tower.md) — all human access is meant to flow through IAM Identity Center roles pushed from the management account, not standing per-account IAM users |
| **Workaround** | None — this is enforced by design. Use an Identity Center permission set instead. |

### IAM privilege escalation is NOT blocked by an SCP

Tested by creating a throwaway IAM role and attaching `AdministratorAccess` to it directly
(`iam:CreateRole`, `iam:AttachRolePolicy`) — both succeeded, confirmed attached, then cleaned up
immediately (`iam:DetachRolePolicy`, `iam:DeleteRole`). No SCP prevents a role created in this
account from being granted full admin permissions. This is a real, meaningful gap compared to the
"no standing IAM users" restriction above — the identity-creation door is closed, but nothing at
the SCP layer stops privilege escalation on identities (roles) this account is otherwise allowed
to create. Whatever prevents this in practice is a matter of IAM permission scoping/process
discipline, not an SCP guardrail.

### Governance model observations (read-only, no mutation attempted)

A few things about how this account's guardrails actually work, discovered by direct read-only
checks rather than testing an action:

| Check | Result |
|---|---|
| AWS Config recorder | **Active and recording** — `aws-controltower-BaselineConfigRecorder`, last successful run today |
| AWS Config Rules attached to this account | **Zero** (`describe-config-rules` returns an empty list) — the recorder captures resource history, but no local rule evaluation runs in this account; if Config-based guardrails exist for this org, they're evaluated centrally from the management/audit account, not visible here |
| GuardDuty detectors in this account | **Zero** (`list-detectors` returns an empty list) — no GuardDuty detector exists in this account context |
| CloudFormation StackSets | **None visible** — `list-stack-sets` returns empty, and a known Control Tower guardrail StackSet name (`AWSControlTowerBP-BASELINE-CONFIG`) returns `StackSetNotFoundException` from this account. Guardrail deployment machinery isn't visible from a member account, consistent with SCPs also being unreadable directly (see above) |

**Takeaway**: this account's actual preventive controls are entirely the SCPs on this page —
there's no locally-visible Config Rule or GuardDuty layer backing them up. Detective/compliance
monitoring for this account, if any, happens centrally and isn't observable from here.

---

## Related Topics

- [Control Tower](control-tower.md) — how SCPs fit into the broader multi-account governance model
- [IAM Roles](iam-roles.md) — the roles these restrictions apply to
