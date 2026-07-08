---
title: SOP Library
weight: 2
---

All Standard Operating Procedures, grouped by domain. Each SOP has a stable `sop_id` you can cite from an incident report.

{{< cards >}}
  {{< card link="db" title="Database (DB)" icon="database" subtitle="Connection pools, replication, slow queries, failover." >}}
  {{< card link="api" title="Application / API" icon="code" subtitle="Latency spikes, 5xx surges, rate limits, deploys." >}}
  {{< card link="infra" title="Infrastructure (INFRA)" icon="server" subtitle="Disk, memory, CPU, node/pod health." >}}
  {{< card link="network" title="Network" icon="globe-alt" subtitle="DNS, TLS, load balancers, connectivity." >}}
  {{< card link="security" title="Security" icon="shield-check" subtitle="Credential leaks, brute force, suspicious access." >}}
{{< /cards >}}
