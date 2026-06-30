# devops-tashtiot

Infrastructure, automation, and platform tooling documentation.

## AWS

| Page | Description |
|---|---|
| [VPC Architecture](aws/vpc-architecture.md) | Hub-and-Spoke VPC design with distributed egress and centralized Network Firewall inspection |
| [Windows Server RDP](aws/windows-server-rdp.md) | Direct RDP access via natSubnet, SSM vs public access patterns, Elastic IP vs auto-assigned IP |
| [IRSA: Pod Identity Token Lifecycle](aws/irsa-pod-identity.md) | How EKS Pods automatically receive AWS credentials via JWT injection and STS — Zero-Code Identity pattern |
| [IAM Roles](aws/iam-roles.md) | All IAM roles in the workload account grouped by purpose: SSO, Control Tower, EKS, automation, and service-linked roles |
| [Control Tower](aws/control-tower.md) | How AWS Control Tower governs multi-account environments via SCPs, StackSets, and IAM role deployment |
