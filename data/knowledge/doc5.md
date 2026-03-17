# Investigating Cost Spikes Caused by Application Behaviour

## Context

Not all cost anomalies originate from infrastructure changes. Application-level behaviour — runaway retries, unbounded worker concurrency, inefficient background jobs, or excessive logging — can cause resource consumption to spike significantly. These cases are harder to diagnose because the infrastructure and autoscaler may be functioning exactly as designed; the problem is what the application is asking them to do.

## When to Use This

- Resource usage and cost spike for a specific service shortly after a deployment, with no corresponding infrastructure changes.
- No failed pipelines, no autoscaler misconfiguration, no new resources provisioned.
- The service is consuming significantly more CPU, memory, or I/O than historical baselines suggest it should.
- Logs show a high volume of errors, retries, or repeated identical operations.

## Likely Causes

- **Misconfigured retry/backoff logic** — a downstream failure triggers an unthrottled retry storm.
- **Unbounded worker or thread pool concurrency** — too many parallel workers processing a queue or running background jobs.
- **Logic bugs** — a code change causes a loop to run far more iterations than intended, or a job runs more frequently than expected.
- **Debug logging or verbose telemetry left enabled in production** — drives large volumes of log/metric ingest and storage cost.
- **Inefficient queries or API calls** — N+1 patterns or missing pagination causing large, repeated payloads.

## Quick Investigation Steps

1. Correlate the cost/resource spike with recent deployment timestamps to identify the likely change.
2. Compare key metrics before and after the deployment: CPU, memory, request rate, error rate, and relevant custom metrics.
3. Review application logs for the affected service — look for error floods, retry messages, or repeated identical operations.
4. Inspect application configuration values deployed in that release: worker counts, retry limits, logging levels, job schedules, and timeouts.

## Remediation

- Correct the relevant configuration value or fix the application logic.
- Redeploy (or roll back if a quick fix is not available).
- Confirm that resource utilisation returns to the expected baseline after redeployment.

## Prevention / Best Practices

- Include resource utilisation checks in pre-production testing, particularly for services with background processing or high-volume I/O.
- Add code review guidelines that flag changes to concurrency settings, retry logic, and logging levels.
- Define app-level SLOs that include efficiency metrics (e.g., cost per job, requests per CPU-second) alongside latency and error rate.
- Ensure debug logging and verbose telemetry are gated by environment config and cannot be accidentally promoted to production.

## Related Docs

- Service Deployment & Rollback Runbook
- Observability & Logging Standards
- Autoscaler Not Scaling Down & Cost Impact
- Cost Monitoring per Service Setup
