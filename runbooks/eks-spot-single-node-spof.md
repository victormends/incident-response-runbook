# Runbook: EKS Spot Interruption Single-Node SPOF Outage

> [!IMPORTANT]
> **Severity: P1/P2.** Partial or total service outage occurs when all replicas of a workload land on a single Spot node and that node is terminated or consolidated.
> **Target recovery time: 5 to 15 minutes.**
> **Prerequisites:** `kubectl` access to the affected cluster and namespace, ArgoCD/GitOps access for durable manifest changes.

Stateless deployments scaled to multiple replicas (`replicas >= 2`) still suffer complete downtime if Kubernetes schedules every pod onto the same worker node and Karpenter or EC2 reclaims that Spot instance. Restarting pods without fixing placement rules merely packs them onto another single node.

---

## Pre-Triage Checklist

- [ ] Identify affected namespace, deployment name, and exact UTC start of health-check failures.
- [ ] Check whether pods are concentrated on one node or stuck in `Pending` / `Terminating`.
- [ ] Confirm whether a Spot interruption notice or node consolidation event just fired.

**Inspect pod placement, node status, and recent scheduling events:**

```bash
kubectl get pods -n <namespace> -l app=<service> -o wide
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | tail -n 30
kubectl get nodes -L capacity-type,topology.kubernetes.io/zone,node.kubernetes.io/instance-type
```

**Inspect unscheduled pods or drained nodes:**

```bash
kubectl describe pod -n <namespace> <pending-pod-name>
kubectl describe node <draining-node-name>
```

---

## Common Root Causes

- **Missing `topologySpreadConstraints`:** Scheduler bin-packs multiple replicas onto whichever recently provisioned node has free CPU/memory, turning a multi-replica Deployment into a single-node SPOF.
- **`ScheduleAnyway` instead of `DoNotSchedule`:** Soft spread constraints allow co-location during bursts when other zones or nodes have slightly higher utilization.
- **No `PodDisruptionBudget` (PDB) or Spot-only placement on critical APIs:** Concurrent voluntary evictions or multi-AZ Spot capacity reclaims drop all pods simultaneously.

---

## Step 1 — Immediate Mitigation (Restore Availability)

1. **If pods are stuck `Pending` after Spot reclamation:**
   - Read `Events` in `kubectl describe pod` for node affinity mismatch, missing AZ volume affinity, or Karpenter provisioning quota limits.
   - Check NodePool / Provisioner events if no replacement node launches within 2 minutes:
   ```bash
   kubectl get nodeclaims
   kubectl logs -n kube-system -l app.kubernetes.io/name=karpenter --tail=100
   ```
2. **If a deployment recovered onto a single node again and remains fragile:**
   - Cordon no existing active node prematurely without spare capacity; first confirm cluster can schedule across multiple nodes or temporarily scale out replicas if `WhenUnsatisfiable` is not yet enforced.
3. **If a terminated pod is stuck in `Terminating` holding a service endpoint:**
   ```bash
   # Verify node is actually NotReady/Gone before force-deleting pod state
   kubectl get node <old-node>
   ```
   Only force-delete after confirming the underlying EC2 node is terminated so split-brain writers cannot remain running.

---

## Step 2 — Durable GitOps Fix (Eliminate Single-Node SPOF)

Update the service Deployment (or Helm values) in GitOps so Kubernetes refuses to pack critical replicas onto one host:

```yaml
spec:
  replicas: 2
  template:
    spec:
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: DoNotSchedule
          labelSelector:
            matchLabels:
              app: <service>
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app: <service>
```

Add a matching `PodDisruptionBudget` for voluntary disruptions (upgrades, node consolidations):

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: <service>-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: <service>
```

For Tier-0 gateways or stateful workers that cannot tolerate Spot preemption windows, keep at least one baseline replica pinned to an On-Demand node pool while bursting additional replicas on Spot.

---

## Verification

- [ ] Roll out GitOps sync (`ArgoCD` synced and healthy).
- [ ] Confirm every replica runs on a distinct `NODE` and ideally distinct zones:
  `kubectl get pods -n <namespace> -l app=<service> -o wide`
- [ ] Confirm `PodDisruptionBudget` status shows `ALLOWED DISRUPTIONS >= 1` during normal steady state.
