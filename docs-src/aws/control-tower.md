# AWS Control Tower

Control Tower is AWS's service for setting up and governing a **multi-account AWS environment** (called a Landing Zone). It enforces security baselines, compliance guardrails, and account structure across every account in the organization — automatically, without per-account manual setup.

---

## The Problem It Solves

Without Control Tower, each AWS account is an island. Teams can disable CloudTrail, create permissive security groups, launch resources in unapproved regions, or ignore compliance requirements. As the number of accounts grows, enforcing consistent standards becomes impossible manually.

Control Tower solves this by making the **management account the single source of truth** for org-wide policy.

---

## Architecture

```
Management Account (Control Tower home)
│
│  Deploys via CloudFormation StackSets
├─────────────────────────────────────────────┐
│                                             │
▼                                             ▼
Log Archive Account             Audit Account
(centralized CloudTrail         (security read-only
 + Config logs)                  access to all accounts)
│
│  Governs all member accounts via SCPs + StackSets
▼
Member Accounts (e.g. this workload account)
├── AWSControlTowerExecution          ← management account assumes this
├── aws-controltower-AdministratorExecutionRole
├── aws-controltower-ConfigRecorderRole
├── aws-controltower-ForwardSnsNotificationRole
└── aws-controltower-ReadOnlyExecutionRole
```

---

## How Control Tower Manages This Account

Control Tower uses **four mechanisms** to govern member accounts:

### 1. SCPs (Service Control Policies)
Preventive guardrails applied at the OU level. Examples:
- Deny disabling CloudTrail
- Deny creating resources outside approved regions
- Deny deleting Config rules

SCPs live in the management account. Member accounts cannot read or override them — they silently block disallowed API calls.

### 2. CloudFormation StackSets
Control Tower pushes baseline configuration to every account via StackSets. In this account, that includes:
- Enabling AWS Config
- Enabling CloudTrail
- Deleting the default VPC (via `DeleteDefaultVPCStackSetRole`)
- Deploying the `aws-controltower-*` IAM roles

### 3. IAM Roles in Every Member Account
Control Tower pre-deploys roles it needs to operate:

| Role | What Control Tower uses it for |
|---|---|
| `AWSControlTowerExecution` | Assumed by the management account — full admin entry point into this account |
| `aws-controltower-AdministratorExecutionRole` | Applies guardrail remediations and StackSet updates |
| `aws-controltower-ConfigRecorderRole` | Records all resource changes to AWS Config |
| `aws-controltower-ForwardSnsNotificationRole` | Sends compliance breach notifications upstream to management account |
| `aws-controltower-ReadOnlyExecutionRole` | Scans for configuration drift without making changes |

### 4. AWS Config Rules
Detective guardrails — they detect non-compliant resources and alert (or auto-remediate). Examples:
- EC2 instances not tagged correctly
- S3 buckets with public access enabled
- Security groups open to `0.0.0.0/0`

---

## SSO Integration

All human access roles (`AWSReservedSSO_*`) are defined centrally in IAM Identity Center (the management account) and **pushed to every member account** by Control Tower. This means:

- Adding a new engineer → update IAM Identity Center once → they get access to all assigned accounts
- Removing an engineer → revoke in one place → access disappears everywhere
- No standing IAM users exist in member accounts

---

## What You Can and Cannot Do

| Action | Allowed? | Why |
|---|---|---|
| View SCPs | No | SCPs live in the management account |
| Delete `aws-controltower-*` roles | No (blocked by SCP) | CT needs them to function |
| Disable CloudTrail | No (blocked by SCP) | Org-wide compliance requirement |
| Create new IAM roles | Yes | Within the permissions of your SSO role |
| Provision resources in `il-central-1` | Yes | Approved region for this account |

---

## Related Topics

- [IAM Roles](iam-roles.md) — full list of roles deployed in this account and their purpose
- [VPC Architecture](vpc-architecture.md) — network guardrails enforced at the hub level