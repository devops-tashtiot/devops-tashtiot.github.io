# IAM Roles

This page covers only the IAM roles that are **built into this account by Control Tower and AWS
itself** — Control Tower's own execution roles, AWS's standard Identity Center permission sets,
and service-linked roles AWS auto-creates when a service is enabled. It deliberately excludes
custom roles created by staff members for specific applications/automation (Terraform, EKS
workloads, cost-automation Lambdas, etc.) — this page is about what the platform arrives with, not
what's been built on top of it.

---

## SSO / Human Access Roles (standard AWS-managed permission sets)

These roles are federated via **AWS IAM Identity Center (SSO)**. No long-lived IAM users exist —
humans assume these roles temporarily after authenticating through SSO. All four are AWS's own
predefined/managed permission sets, not custom ones defined for this account.

| Role | Access Level | When Used |
|---|---|---|
| `AWSAdministratorAccess` | Full admin — every AWS action | Break-glass emergencies or org-level admin tasks |
| `AWSPowerUserAccess` | Full except IAM user/group management | Developers needing broad but bounded access |
| `AWSReadOnlyAccess` | Read everything, change nothing | Auditors, monitoring dashboards, on-call review |
| `AWSOrganizationsFullAccess` | Manage OUs, accounts, and SCPs | Restructuring the org or moving accounts between OUs |

> **Why SSO roles instead of IAM users?** SSO-federated roles issue short-lived credentials (typically 1–8 hours). There are no permanent access keys to rotate, leak, or forget to revoke when someone leaves the team.

---

## Control Tower Roles

Control Tower deploys these roles into every member account so the management account can enforce baselines and guardrails without manual intervention per account. See the [Control Tower](control-tower.md) page for the full architecture.

| Role | Purpose |
|---|---|
| `AWSControlTowerExecution` | Assumed by the management account — gives CT full admin to enforce baselines in this account |
| `aws-controltower-AdministratorExecutionRole` | Used by CT to apply guardrails, run StackSets, and remediate drift |
| `aws-controltower-ConfigRecorderRole` | Allows AWS Config to record all resource changes for compliance tracking |
| `aws-controltower-ForwardSnsNotificationRole` | Forwards compliance alerts upstream to the central SNS topic in the management account |
| `aws-controltower-ReadOnlyExecutionRole` | CT reads this account's state to detect configuration drift |
| `AWSServiceRoleForAWSControlTower` | Service-linked role — CT's permanent presence in this account |

---

## AWS Service-Linked Roles

These are auto-created by AWS when you enable a service. They cannot be manually assumed — only the named AWS service can use them.

| Role | Service |
|---|---|
| `AWSServiceRoleForAutoScaling` | EC2 Auto Scaling groups |
| `AWSServiceRoleForCloudTrail` | CloudTrail audit logging |
| `AWSServiceRoleForConfig` | AWS Config compliance recording |
| `AWSServiceRoleForFMS` | Firewall Manager — centralized SG and WAF policies pushed from the management account |
| `AWSServiceRoleForIPAM` | IP Address Manager — centralized VPC CIDR planning |
| `AWSServiceRoleForNetworkFirewall` | Network Firewall — the hub inspection layer traffic routes through |
| `AWSServiceRoleForOrganizations` | AWS Organizations integration |
| `AWSServiceRoleForSSO` | IAM Identity Center — manages the `AWSReservedSSO_*` roles |
| `AWSServiceRoleForSupport` | AWS Support case management |
| `AWSServiceRoleForTrustedAdvisor` | Cost, performance, and security recommendations |
| `AWSServiceRoleForCloudFormationStackSetsOrgMember` | Receives StackSet deployments from the management account |
| `AWSServiceRoleForAmazonEKS` | EKS service-linked role — auto-created by AWS the first time EKS is used in this account |
| `AWSServiceRoleForAmazonEKSNodegroup` | EKS nodegroup service-linked role — manages node lifecycle |

---

## Related Topics

- [Control Tower](control-tower.md) — how the management account governs this account
- [IRSA: Pod Identity Token Lifecycle](irsa-pod-identity.md) — how EKS pods use IAM roles without credentials (a general AWS mechanism, not itself a Control-Tower-provided role)
