# IAM Roles

This page summarizes every IAM role in the AWS workload account, grouped by purpose. Understanding who (or what) uses each role helps with least-privilege audits, incident response, and onboarding.

---

## SSO / Human Access Roles

These roles are federated via **AWS IAM Identity Center (SSO)**. No long-lived IAM users exist — humans assume these roles temporarily after authenticating through SSO.

| Role | Access Level | When Used |
|---|---|---|
| `AWSAdministratorAccess` | Full admin — every AWS action | Break-glass emergencies or org-level admin tasks |
| `AWSPowerUserAccess` | Full except IAM user/group management | Developers needing broad but bounded access |
| `AWSReadOnlyAccess` | Read everything, change nothing | Auditors, monitoring dashboards, on-call review |
| `AWSOrganizationsFullAccess` | Manage OUs, accounts, and SCPs | Restructuring the org or moving accounts between OUs |
| `Workload-Admin-PS` | Full workload admin | Day-to-day infra work — Terraform, EKS, networking |
| `Workload-Security-Admin-PS` | Security admin + data perimeter reads | Managing firewall rules and perimeter exceptions between spoke OUs |
| `Workload-Security-Audit-PS` | Read-only resource configurations | Security audits, compliance reviews |
| `Workload-Security-Tagger-PS` | Tag resources only | Enforcing tagging standards without broader access |
| `Workload-Support-Admin-PS` | Support + perimeter exemptions | Escalating AWS Support cases, handling support-level perimeter access |

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

## EKS Roles

| Role | Purpose |
|---|---|
| `devtools-labs-cluster-*` | EKS control plane role — allows EKS to manage VPC ENIs, security groups, and load balancers |
| `default-eks-node-group-*` | Node IAM role — allows nodes to pull ECR images, join the cluster, and call EKS APIs |
| `devtools-labs-alb-controller` | IRSA role for the ALB Ingress Controller pod — grants it permission to manage ALBs and target groups |
| `AWSServiceRoleForAmazonEKS` | EKS service-linked role — auto-created by AWS when EKS is first used |
| `AWSServiceRoleForAmazonEKSNodegroup` | Nodegroup service-linked role — manages node lifecycle |

> The `devtools-labs-alb-controller` role uses **IRSA** (IAM Roles for Service Accounts) — see [IRSA: Pod Identity Token Lifecycle](irsa-pod-identity.md) for how the Pod receives credentials without any secrets in code.

---

## After-Hours Cost Automation

These roles power the automated shutdown of resources outside business hours to reduce costs.

| Role | Purpose |
|---|---|
| `after-hours-scheduler-role` | Allows EventBridge Scheduler to invoke the shutdown Lambda on a cron schedule |
| `after-hours-shutdown-role-*` / `afterhours-shut-down-role` | Lambda execution role — permission to stop EC2 instances |
| `EC2Stop-Role` | Scoped role with `ec2:StopInstances` permission |
| `Amazon_EventBridge_Scheduler_LAMBDA_*` | EventBridge Scheduler invocation role for Lambda targets |
| `lz-integration-Accounts-Shutdown-Role` | Org-wide shutdown role — assumes into member accounts to stop resources across the landing zone |

---

## Infrastructure / IaC Roles

| Role | Purpose |
|---|---|
| `horizon-terraform-role` | Assumed by Terraform (CI/CD or local) to provision all infrastructure in this account |
| `lz-integration-cdk-deploy-role` | CDK deployment role — used during `cdk deploy` to orchestrate the deployment |
| `lz-integration-cdk-cfn-exec-role` | CloudFormation execution role — the identity CloudFormation uses to actually create resources during a CDK deploy |
| `DeleteDefaultVPCStackSetRole` | Used by a StackSet that removes the AWS default VPC from newly vended accounts |
| `stacksets-exec-*` | CloudFormation StackSets execution role — receives StackSet operations from the management account |
| `FlowLogRole-*` | Allows VPC Flow Logs to write to CloudWatch Logs |

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

---

## Other Roles

| Role | Purpose |
|---|---|
| `xray-cron-lambda-role` | Lambda execution role for X-Ray tracing jobs |
| `xray-cron-scheduler-role` | EventBridge Scheduler role for X-Ray cron |
| `lz-integration-bedrock-cloudwatch-logging-role` | Allows Amazon Bedrock to write inference logs to CloudWatch |
| `lz-integration-bedrock-cloudwatch-read-role` | Read access to Bedrock CloudWatch logs |
| `BlastUnitCollectorRole` | Security posture / blast-radius scanning tool |
| `Costi` | Cost visibility and optimization tool |

---

## Related Topics

- [Control Tower](control-tower.md) — how the management account governs this account
- [IRSA: Pod Identity Token Lifecycle](irsa-pod-identity.md) — how EKS pods use IAM roles without credentials