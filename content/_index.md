---
title: IT SOP Wiki
toc: false
---

<div class="hx-mt-6 hx-mb-6">
{{< hextra/hero-headline >}}
  Agent-ready Standard&nbsp;<br class="sm:hx-block hx-hidden" />Operating Procedures
{{< /hextra/hero-headline >}}
</div>

<div class="hx-mb-12">
{{< hextra/hero-subtitle >}}
  A Git-based, machine-readable SOP knowledge base for IT operations.&nbsp;<br class="sm:hx-block hx-hidden" />Written for humans, structured for AIOps agents.
{{< /hextra/hero-subtitle >}}
</div>

<div class="hx-mb-6">
{{< hextra/hero-button text="Browse SOPs" link="docs" >}}
</div>

<div class="hx-mt-6"></div>

{{< hextra/feature-grid >}}
  {{< hextra/feature-card
    title="Structured for Agents"
    subtitle="Every SOP carries YAML frontmatter (symptoms, severity, verification metrics) so agents can match error logs and generate reports."
  >}}
  {{< hextra/feature-card
    title="Step-by-Step Runbooks"
    subtitle="Situation → Symptoms → Diagnosis → Action → Verification → Escalation. The action steps become the agent's response logic."
  >}}
  {{< hextra/feature-card
    title="Git-Versioned"
    subtitle="Every change is an auditable commit. Agents index the latest .md directly — no API, no scraping."
  >}}
  {{< hextra/feature-card
    title="Schema-Validated"
    subtitle="A JSON Schema enforces required fields in CI, so incomplete SOPs never reach the agent."
  >}}
  {{< hextra/feature-card
    title="Five-Line Reports"
    subtitle="Verification metrics drive automated incident summaries: what broke, root cause, action, verification, prevention."
  >}}
  {{< hextra/feature-card
    title="Escalation Paths"
    subtitle="Each SOP declares L1/L2 owners so unresolved incidents route to the right people automatically."
  >}}
{{< /hextra/feature-grid >}}
