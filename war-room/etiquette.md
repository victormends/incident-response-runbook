# War Room Etiquette

A war room that runs well resolves incidents faster. A war room that runs poorly adds political overhead to a technical problem. The difference is not the seniority of the people in the room — it is whether the room has a structure and everyone in it knows it.

These rules apply to any multi-person incident call, whether it's two engineers on a Slack huddle or five people on a phone bridge.

---

## Roles

Every effective war room has exactly three role types. In a small team, one person may hold two of them, but they cannot be absent.

**Incident Commander (IC)**

Owns the call. Makes the decisions. Controls who speaks and when. Does not need to be the most senior person — needs to be the calmest and most organized person available. The IC's job is to manage the incident, not to fix it. If the IC is also the best diagnostic engineer in the room, consider swapping roles.

Responsibilities:
- Opens the call with a 60-second state-of-the-world summary
- Calls on specialists by name — does not wait for volunteers
- Forces decisions every 15 minutes (see time-boxing below)
- Controls client communication — only the IC or their designated spokesperson updates the client
- Calls the post-war-room capture session when the incident resolves

**Scribe**

Types the incident timeline in real time. Pastes query outputs into the shared channel as they appear. Owns the post-mortem document from the first moment of the call. If you don't have a scribe, the IC takes notes — but this degrades their ability to manage the call.

Responsibilities:
- Records every decision with a timestamp: "14:52 — IC decided to drop slot after team lead confirmed it was orphaned"
- Records every query output verbatim — no summarizing
- Tracks hypotheses: "Hypothesis: slot is orphaned. Status: confirmed at 14:51."
- Does not contribute to the technical discussion unless directly asked

**Technical Specialists**

Everyone else. Speak when asked. Run queries when assigned. Report results factually. Do not volunteer hypotheses in the main call — that goes in the side channel.

---

## The Three Rules

**Rule 1: One voice at a time.** The IC holds the floor. When a specialist is speaking, everyone else is quiet. This is not about authority — it is about signal quality. Multiple people talking simultaneously means critical information gets missed. The IC enforces this by naming who speaks next.

**Rule 2: Observations only in the main call.** No "I think this is because..." in the main call. Factual observations only: "pg_stat_replication shows no active connections." "WAL directory is 47 GB." "Slot `backup_legacy_subscriber` has `active = false`." Hypotheses go in the side channel or in a designated "hypotheses" thread. This prevents the main call from becoming a debate about causes before the diagnosis is complete.

**Rule 3: Hypotheses in a side channel.** Create a separate thread or channel the moment the war room opens. Label it clearly. All speculation, theories, and "what if we try..." goes there. The side channel is not reviewed in the main call unless the IC pulls something from it. This keeps the main call focused on confirmed observations and next actions.

---

## Time-Boxing Decisions

The most common war room failure is spending too long on a single hypothesis without a decision gate. The pattern: the team pursues hypothesis A for 30 minutes, it doesn't pan out, now 30 minutes are gone and a new hypothesis has to start from scratch.

The IC must force a decision every **15 minutes** during a P1:

> "We've been working hypothesis A — the connection pool — for 15 minutes. pg_stat_activity shows no pool exhaustion. Are we moving on or do we have one more thing to check?"

This is not micromanagement. It is the IC's primary technical function. The answer might be "one more thing" — that's fine. The point is that the question gets asked explicitly, and the team makes a conscious choice, rather than drifting.

At the 15-minute gate, the IC has three options:
1. **Continue** — one specific additional check is defined and time-boxed to 5 minutes
2. **Switch** — name the next hypothesis explicitly. The scribe records it.
3. **Escalate** — if no hypothesis is gaining ground and 20 minutes have elapsed, invoke [`escalation/protocol.md`](../escalation/protocol.md)

---

## Client Update Structure

Every client update from the war room follows this format exactly. No improvising.

```
Current confirmed state: [what is factually true right now]
What is being done: [one sentence — what the team is working on at this moment]
Next update: [specific time — not "soon"]
```

**Example:**
> "The database is still unavailable. We have identified the cause as a disk capacity issue and freed sufficient space to restart the service. We are currently confirming the database has started successfully. I'll call you with a confirmed status by 10:15."

Never speculate in a client update. If the cause is not confirmed, say "still investigating." "Still investigating" is more credible than a wrong guess. The client's confidence in you is not built by the speed of your answers — it is built by the accuracy of them.

---

## Post-War-Room Capture (Do Not Skip This)

When the incident is resolved, the war room does not immediately dissolve. The IC runs a 10-minute capture session before anyone disconnects.

The capture session:

1. **Scribe confirms timeline completeness** — every major decision and observation should be recorded. Fill any gaps now while everyone's memory is fresh.
2. **Each specialist confirms their action log** — "I ran query X, result was Y, that ruled out hypothesis Z." If it's not in the scribe's notes, add it now.
3. **Post-mortem is opened and assigned** — the IC creates the post-mortem document, names the owner (usually the primary responder), and sets a due date. The post-mortem is not assigned days later when details are lost.
4. **Client communication is closed** — confirm that the client has been notified of resolution, not just that the technical fix is complete.

The most common post-mortem failure is that it gets assigned a week later, by which time the timeline details are gone and the lessons learned section becomes generic. The capture session prevents this.

---

## Cross-Reference

- Escalation procedures during a war room: [`escalation/protocol.md`](../escalation/protocol.md)
- Communication framework used in client updates: [`communication/nvc-incident-communication.md`](../communication/nvc-incident-communication.md)
- Post-mortem template to open during capture session: [`post-mortem/template.md`](../post-mortem/template.md)
- Severity classification to confirm before closing: [`severity-classification/matrix.md`](../severity-classification/matrix.md)
