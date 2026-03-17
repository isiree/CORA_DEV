# Failed Terraform Destroy Jobs & Orphaned Resources

## Context

IaC destroy/cleanup jobs (Terraform or equivalent) can fail silently or mid-run, leaving test and POC environments running indefinitely. These orphaned resources continue to accrue cost without any active workload, often going unnoticed until a cost review. This is one of the most common sources of unexpected baseline cost increases in non-production environments.

## When to Use This

- Cost spikes during or after a test/experiment, then plateaus at a higher baseline instead of returning to normal.
- CI/CD pipeline shows failed or partially completed destroy/cleanup runs.
- Resources tagged `env=test`, `env=poc`, or `env=staging` are still running with no active owner.
- Spend on a non-production project is unexpectedly flat and sustained over days or weeks.

## Likely Causes

- **State lock not released** after a previous failed run, preventing subsequent destroy attempts.
- **State drift** — resources exist in the cloud that are no longer tracked in Terraform state, so `destroy` skips them.
- **Missing or insufficient permissions** — the pipeline service account cannot delete certain resource types.
- **Dependency ordering issues** — destroy fails because a dependent resource (e.g., a network interface) must be removed first.
- Pipeline fails early and subsequent teardown steps are skipped without alerting.

## Quick Investigation Steps

1. **Check the cost graph** for the affected project/subscription. Look for a step-change in spend on the day of the test that never reversed.
2. **Filter resources by tag** (`env=test`, `env=poc`, etc.) in the cloud console or asset inventory. Note creation dates and current running state.
3. **Open the destroy pipeline logs** for the relevant run. Search for `Error`, `lock`, `permission denied`, or `still exists` messages to identify the failure point.
4. **Check IaC state** — run `terraform state list` (or equivalent) against the workspace and compare to what is actually deployed. Flag any resources present in the cloud but absent from state.
5. **Verify IAM/RBAC permissions** for the pipeline service account against the resources that failed to delete.

## Remediation

- **State lock:** Force-unlock the state (`terraform force-unlock <lock-id>`) and re-run the destroy pipeline.
- **State drift:** Import the orphaned resource into state (`terraform import`) or manually add it, then re-run destroy.
- **Permission issues:** Grant the pipeline service account the required delete permissions, then re-run.
- **Dependency failures:** Identify the blocking dependency in the error logs, remove it manually or reorder destroy steps, then retry.
- **Last resort:** Manually delete resources via the cloud console or CLI. Document what was cleaned up and why automation failed.

## Prevention / Best Practices

- **TTL tags:** Require a `ttl` or `expires` tag on all test/POC resources. Run a scheduled job that flags or terminates resources past their TTL.
- **Destroy pipeline alerts:** Configure the CI/CD system to send a high-priority alert (Slack, PagerDuty, etc.) on any failed destroy run.
- **Cost alerts on non-prod projects:** Set a budget alert threshold on test/POC projects so any sustained spend triggers a notification.
- **Periodic resource audits:** Schedule a weekly report of resources older than N days in non-production environments.
- **State validation in pipelines:** Add a post-apply check that compares expected vs. actual resource count as a pipeline gate.

## Related Docs

- Non-Production Environment Lifecycle Policy
- IaC State Management & Locking Guide
- Pipeline Service Account Permission Matrix
- Cloud Budget Alerting Setup
