# Autoscaler Not Scaling Down & Cost Impact

## Context

Autoscalers (e.g., Kubernetes HPA, cluster autoscaler) are designed to reduce resource consumption when demand drops. When scale-down does not trigger correctly, nodes and pods remain provisioned at peak capacity long after traffic returns to normal. This pattern causes sustained over-provisioning costs and is often mistaken for legitimate load growth.

## When to Use This

- Cluster or service cost jumps sharply during a traffic spike and does not decrease once traffic normalises.
- Pod or node count remains elevated for hours or days after load returns to baseline.
- Autoscaler event logs show frequent scale-up events but few or no scale-down events.
- Cost per request is increasing alongside rising resource allocation.

## Likely Causes

- **Scale-down thresholds too conservative** — utilisation must fall very low before a scale-down triggers.
- **Wrong scaling metric** — scaling on a metric that doesn't reflect actual load (e.g., CPU when the bottleneck is queue depth).
- **Minimum replica/node count set too high** — the floor prevents scale-down even when appropriate.
- **Cooldown or stabilisation window too long** — the autoscaler waits too long between scale-down decisions.
- Recent config change to autoscaler parameters that inadvertently broke scale-down behaviour.

## Quick Investigation Steps

1. **Plot traffic vs. pod/node count** over the relevant time window. Confirm that resource count did not follow traffic back down.
2. **Review autoscaler event logs** — check the ratio of scale-up to scale-down events and look for suppression or error messages.
3. **Inspect current autoscaler configuration** — note the scaling metric, thresholds, min/max values, and cooldown settings.
4. **Check for recent config changes** to the HPA, cluster autoscaler, or node pool settings around the time the issue started.

## Remediation

- Adjust scale-down threshold and stabilisation window to values appropriate for the service's traffic pattern.
- Review and correct the scaling metric if it does not accurately represent load.
- Lower the minimum replica/node count if it was set defensively high without justification.
- **Validate all changes in staging** before applying to production — confirm scale-down triggers under synthetic load reduction.

## Prevention / Best Practices

- Test autoscaling policies (both scale-up and scale-down) as part of staging performance testing.
- Alert when scale-down has not occurred for an extended period despite low utilisation.
- Set per-namespace or per-service cost budgets to catch over-provisioning quickly.
- Document intended min/max replica ranges and scaling metrics for each service; review quarterly.

## Related Docs

- Kubernetes HPA Configuration Reference
- Cluster Autoscaler Tuning Guide
- Cost Monitoring per Namespace Setup
- Staging Load Testing Runbook
