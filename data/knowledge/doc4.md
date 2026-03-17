# Avoiding Idle Cost from Forgotten Test/POC Environments

## Context

Test, POC, and experimental environments are frequently spun up to validate ideas or support short-term projects. Without a defined lifecycle, these environments are rarely decommissioned. Even at low utilisation, they accumulate a steady and hard-to-justify cost over weeks or months. This is primarily a governance and ownership problem.

## When to Use This

- A long-running cost plateau is linked to resources tagged `env=test`, `env=poc`, or similar.
- Resources show near-zero CPU/memory utilisation but consistent, stable spend.
- No active team member can confirm whether an environment is still needed.
- A cost review surfaces non-production spend with no associated active project or ticket.

## Likely Causes

- No TTL or expiry policy was defined at environment creation time.
- No automated destroy pipeline exists; teardown was left as a manual step that never happened.
- Team ownership is unclear — the original creator has moved on or the project was abandoned.
- Environment was created outside the standard provisioning process and never registered.

## Quick Investigation Steps

1. Filter resources by `env=test`, `env=poc`, or equivalent tags. Note creation dates.
2. Check utilisation metrics (CPU, memory, network) over the past 7–30 days. Near-zero activity is a strong signal the environment is idle.
3. Identify the owning team from tags or resource group naming and confirm whether the environment is still needed.
4. Check whether a destroy or cleanup pipeline was ever created for this environment.

## Remediation

- If confirmed idle: decommission following the standard environment teardown process.
- If ownership is unclear: escalate to the platform or FinOps lead to make a decommission decision within a defined SLA.
- Document the cleanup action in the relevant ticket or cost review record.

## Prevention / Best Practices

- **Require TTL tags** (`ttl`, `expires-on`) at environment creation. Enforce via policy or a CI gate.
- **Auto-cleanup jobs:** Run a scheduled job that warns when a TTL is approaching and terminates environments past their TTL if no renewal is submitted.
- **Clear ownership:** Require `team` and `owner` tags at creation; link environments to an active project or ticket.
- **Regular non-prod spend reviews:** Include non-production cost as a standing item in FinOps or platform team reviews.
- **Lifecycle process:** Maintain a simple, documented process for requesting, extending, and decommissioning test environments.

## Related Docs

- Non-Production Environment Request & Lifecycle Policy
- TTL Tag Auto-Cleanup Job Documentation
- Failed Terraform Destroy Jobs & Orphaned Resources
- Cloud Tagging Standards
