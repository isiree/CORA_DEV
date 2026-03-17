# Cost Attribution Issues Due to Missing or Incorrect Tags

## Context

Cloud cost allocation relies on consistent resource tagging — typically `team`, `cost_center`, `env`, and similar keys. When tags are missing, wrong, or inconsistently named, costs land in an unallocated bucket or are attributed to the wrong team. This makes it impossible to hold teams accountable for their spend and masks real cost growth at the subscription level.

## When to Use This

- Total subscription/account spend is growing faster than any individual team's reported cost.
- A large "unallocated" or "unknown" cost segment appears in the cost dashboard.
- A team's dashboard shows flat spend while the overall bill increases.
- Recent infrastructure changes were made outside the standard IaC pipeline (e.g., manual console deployments).

## Likely Causes

- New resources deployed without the required tags (manual creation, rushed deployments).
- **Incorrect team values** — e.g., `team=legacy` used instead of `team=payments` after a team rename or reorganisation.
- **Inconsistent tag keys** — `Team`, `team`, `TEAM`, or `squad` used interchangeably across resources or regions.
- Tags applied at the resource level but not inherited by child resources (e.g., disks, snapshots, network interfaces).
- IaC modules updated without propagating new tagging requirements to all resource blocks.

## Quick Investigation Steps

1. **Compare subscription-level vs. team-level cost totals.** The gap between them is the unattributed spend — note its size and trend.
2. **Inspect the "unallocated" or "other" cost bucket** in your cost management tool. List the top resource types and groups by unattributed spend.
3. **Cross-reference resource names and groups** with known team ownership (service catalogue, CMDB, or Slack channels) to identify likely owning teams.
4. **Check recent IaC changes and pipeline runs** that deployed or modified resources around the time the unallocated cost appeared.
5. **Audit tag keys and values** on the flagged resources — look for typos, casing differences, and missing mandatory keys.

## Remediation

- **Fix tags on existing resources** using bulk tag update tooling (cloud CLI, tagging API, or IaC import + re-apply).
- **Update IaC modules and pipelines** to use the correct tag values going forward. Raise a PR for review.
- **Notify owning teams** of the misattributed cost so they can reconcile their dashboards.
- Where resources cannot be retagged immediately, document the exception and track manually until resolved.

## Prevention / Best Practices

- **Tagging standards document:** Maintain a single source of truth listing mandatory tag keys, allowed values, and naming conventions.
- **Tag validation in CI:** Add a linting step to IaC pipelines that fails the build if mandatory tags are missing or use invalid values.
- **Policy / guardrails enforcement:** Use cloud policy tools to deny or flag resource creation that omits required tags.
- **Regular tagging compliance reports:** Schedule a weekly report showing the percentage of fully tagged resources, with a trend line.
- **Tag changes in change management:** Treat `team`/`cost_center` tag updates as a change request to avoid silent misattribution.

## Related Docs

- Mandatory Tagging Standard & Allowed Values
- IaC Tagging Module Reference
- Cost Allocation Dashboard Guide
- Cloud Policy & Guardrails Overview
