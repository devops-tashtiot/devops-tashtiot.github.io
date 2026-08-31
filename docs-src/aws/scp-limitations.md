# SCP Limitations

A running reference of Service Control Policy (SCP) restrictions discovered while working in
this account, so nobody re-attempts the same blocked approach without checking here first. SCPs
in this Control Tower-managed Landing Zone are pushed down from the management account — see
[Control Tower](control-tower.md) for how that governance model works. Member-account roles
(including full workload admins) cannot view or override an SCP; it just silently denies the
underlying API call, regardless of the caller's own IAM permissions.

---

## Known Restrictions

### Identity Center directory/user listing (`identitystore:ListUsers`)

| | |
|---|---|
| **Denied actions** | `identitystore:ListUsers`, `sso-directory:ListUsers`, `sso-directory:SearchUsers` |
| **What it blocks** | Inspecting IAM Identity Center's provisioned users, or checking Identity Center's sync status with its external identity source (directory/SCIM), from a workload-account role |
| **Symptom** | `AccessDenied` — the error message includes "explicit deny in a service control policy," distinguishing it from a plain IAM permission gap |
| **Workaround** | None via CLI/API. Check in the Identity Center console instead (**Settings → Identity source → Provisioning**), which runs in the management-account context, not this workload account |

---

## Related Topics

- [Control Tower](control-tower.md) — how SCPs fit into the broader multi-account governance model
- [IAM Roles](iam-roles.md) — the roles these restrictions apply to
