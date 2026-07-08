# Configuring User Directories (LDAP/AD)

Jira, Confluence, and Bitbucket each authenticate against the same on-prem-style
Active Directory domain controller instead of maintaining their own local user
bases. Each app's embedded Crowd/user-directory screen is configured
independently (there's no shared config file), but they all point at the same
AD and hit the same gotchas.

---

## Connection Settings

| Field | Value | Why |
|---|---|---|
| Directory Type | Microsoft Active Directory | |
| Port | `389` | Plain LDAP, not LDAPS — the domain controller isn't configured for TLS on the LDAP port |
| Use SSL | **No** | matches the plain `ldap://` scheme above |
| Base DN | the AD organizational unit holding both the platform's users and its security group | |

> **Hostname:** connect by the domain controller's private IP, not a DNS name — there is no DNS zone for the AD domain configured anywhere in this platform (no CoreDNS stub domain, no `hostAliases`, no Route53 private hosted zone). This matters more than it looks like it should — see the Follow Referrals section below.

---

## Schema Mapping

These map Active Directory's actual attribute names onto Jira/Confluence/Bitbucket's generic directory-schema fields. They're standard AD attributes, not specific to this environment, but worth having in one place since the field names in Atlassian's UI don't always make the AD equivalent obvious.

**User schema:**

| Field | Value |
|---|---|
| User Object Class | `user` |
| User Object Filter | `(&(objectCategory=Person)(sAMAccountName=*))` |
| User Name Attribute | `sAMAccountName` |
| User Name RDN Attribute | `cn` |
| User First Name Attribute | `givenName` |
| User Last Name Attribute | `sn` |
| User Display Name Attribute | `displayName` |
| User Email Attribute | `mail` |
| User Unique ID Attribute | `objectGUID` |

**Group schema:**

| Field | Value |
|---|---|
| Group Object Class | `group` |
| Group Object Filter | `(objectCategory=Group)` |
| Group Name Attribute | `cn` |
| Group Description Attribute | `description` |

**Membership schema:**

| Field | Value |
|---|---|
| Group Members Attribute | `member` |
| Use the User Membership Attribute | **"When finding the members of a group"** |

The last one is a deliberate choice, not the Atlassian default: AD's group object carries a `member` attribute listing every member's DN directly, which is the more reliable direction to resolve membership from in a flat (non-nested) group structure. The platform's Keycloak/RHBK SSO integration resolves AD group membership the same way (via the group's `member` attribute, not a per-user back-link), so this keeps both integrations consistent with each other.

---

## Follow Referrals Must Be Disabled

This is the one setting most likely to trip you up, because everything else can be configured correctly and the directory will still fail — specifically on **"Test retrieve user."**

**Symptom:**

```
org.springframework.ldap.PartialResultException: nested exception is
javax.naming.PartialResultException [Root exception is
javax.naming.CommunicationException: <ad-domain>:389 [Root exception is
java.net.UnknownHostException: <ad-domain>]]
```

**Why it happens:** Active Directory frequently answers LDAP searches with a
*referral* — a response telling the client "continue this search at
`ldap://<ad-domain>/...`" — even when the client is already querying the
correct domain controller directly by IP. This is normal AD behavior around
naming-context boundaries and paged searches, not a sign anything is
misconfigured.

If "Follow Referrals" is enabled, Jira's (or Confluence's/Bitbucket's)
underlying LDAP client dutifully tries to open a *new* connection to that
referral target — which is the AD domain's DNS name, not the IP address you
configured. Since nothing in this platform resolves that domain name (see the
callout above), the hostname lookup fails outright.

**Fix:** uncheck **"Follow Referrals"** in the directory's Advanced Settings.
There is no other side effect to turning it off here — the platform's AD
structure is flat (no nested domains/partitions), so there's nothing a
referral would ever need to point the client at anyway.

> **Why RHBK/Keycloak's LDAP federation never hit this:** Keycloak's LDAP
> provider defaults to *ignoring* referrals rather than following them, so it
> never attempts the DNS lookup that trips up Jira/Confluence/Bitbucket's
> Spring-LDAP-based clients. If a future integration exposes a referral
> setting, ignoring/not-following is the option to match this platform's
> setup.
