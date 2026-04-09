# ★ NVC in Incident Communication

The most expensive minutes in a P1 are not the minutes spent diagnosing. They are the minutes spent arguing about who is responsible, reassuring a panicking client with information you haven't confirmed yet, or rerunning a fix that already failed because someone in the meeting demanded immediate action.

A database goes down at 14:30. The client calls at 14:32. The support engineer hasn't run a single diagnostic query. The client says "your system destroyed our operations." The engineer, feeling defensive and pressured, says "we're looking into it, it was probably a configuration issue." The guess is wrong. The client calls back at 14:45 angry that the "configuration issue" hasn't been fixed. Thirty minutes are gone. The real diagnosis hasn't started.

This is not a knowledge failure. The engineer knows how to diagnose PostgreSQL. It is a communication failure, and communication failures have structured solutions.

---

## NVC Foundations

Nonviolent Communication was developed by Marshall Rosenberg and published in *Nonviolent Communication: A Language of Life* (1999). Its four-step structure — Observation, Feeling, Need, Request — was designed for interpersonal conflict. Its value in incident response comes from a structural parallel: both contexts involve high-stakes communication between people with conflicting information and competing urgency. In conflict resolution, you are trying to resolve a disagreement. In incident response, you are trying to solve a technical problem while a disagreement is happening around you. The framework applies to both.

---

## The Four Steps Applied to Incident Response

### Step 1 — Observation (without evaluation)

NVC distinguishes between observations and evaluations. An observation is a factual statement that a third party could verify by checking the same data you checked. An evaluation blends fact with interpretation, attribution, or judgment.

In incident response, this distinction is diagnostic, not philosophical. An evaluation masquerading as an observation forecloses investigation. "The system is broken" leads nowhere. "The database has been unreachable for 12 minutes since the 14:30 deployment" opens three immediate hypotheses.

**Before/after examples:**

| Evaluation (avoid) | Observation (use instead) |
|---|---|
| "The system is broken again." | "The database has been unreachable since 14:32. That's 18 minutes." |
| "The deployment team broke the database." | "The database became unreachable at 14:32, approximately 2 minutes after the 14:30 deployment." |
| "This query is garbage." | "This query is scanning 70 million rows sequentially. Execution time is 4.2 minutes." |
| "The client is always causing their own problems." | "The client created 47 concurrent connections in the last 10 minutes. The max_connections limit is 50." |
| "We have no visibility into what's happening." | "We have not yet received the pg_stat_activity output. We have the last 50 lines of the PostgreSQL log." |
| "The replication is completely broken." | "Replication lag is currently 8.3 GB on the primary slot `backup_legacy_subscriber`, which has been inactive for 6 days." |

**The pattern:** `[Observable system state] [at/since specific time] [quantified impact if known].`

No adjectives. No attribution. No emotion. If a third party checked the same metric, they would see the same value.

**Why it matters in incidents:** Evaluations generate disagreements. Observations generate hypotheses. During a P1, you cannot afford a disagreement about what is happening — that debate consumes the time you need to fix it.

---

### Step 2 — Feeling (naming the emotional state)

This is the most counterintuitive step for engineers. The instinct in a technical crisis is to treat emotion as irrelevant — "focus on the problem." NVC doesn't ask you to process your emotions in the middle of an incident. It asks you to name them, briefly, because unnamed emotions drive behavior invisibly.

An engineer who doesn't recognize that they're feeling pressured will make decisions that look like data-driven analysis but are actually driven by the need to give the client something — anything — to make the pressure stop. That is how wrong guesses get delivered as confident diagnoses.

**Internal recognition (what you say to yourself or your team lead):**

- "I notice I'm feeling pressure to provide an answer before I have enough information to do it accurately." — Recognition of this feeling prevents premature diagnosis.
- "I'm feeling defensive because the client implied this was our fault." — Recognition prevents a defensive response that escalates the situation.
- "I feel uncertain about this path and I've been on it for 15 minutes." — Recognition triggers the escalation question: should I continue or ask for help?

**External recognition (reading the client's state accurately):**

- "The client is expressing urgency. Their fiscal transmission window closes in 2 hours."
- "The client sounds frustrated. They've been waiting 45 minutes with no confirmed diagnosis."
- "The client's tone has shifted from frustrated to threatening. They mentioned cancellation."

**The pattern:** Name the feeling once. To yourself, or to your team lead. Then make the next decision based on data, not the feeling. You are not suppressing the emotion — you are preventing it from making decisions without your knowledge.

---

### Step 3 — Need (what is driving the feeling)

Every emotional state in a P1 is driven by an unmet need. The client is not angry at you. They are expressing an unmet need for reliability and operational continuity. The developer on the incident call is not defensive about the deployment. They are expressing an unmet need to not be publicly blamed for a mistake before the investigation is complete. The team lead is not demanding premature answers. They are expressing an unmet need to show their own manager that the situation is under control.

Understanding the need allows you to address it directly — without overpromising, without lying, and without conceding things that aren't true.

**Matching emotional states to needs:**

| Who | What they express | What they actually need |
|---|---|---|
| Client | Anger, urgency, cancellation threats | Operational continuity. Accurate information. Predictability about when it will be resolved. |
| Client's manager | Escalation, demands for ETA | A narrative they can share upward that shows the team is in control. |
| Developer | Defensiveness about the recent change | To understand what happened before being asked to explain it to management. |
| Team lead | Pressure for quick answers | Progress they can report. Confidence that the incident is being worked systematically. |
| Support engineer | Self-imposed pressure | Enough time to diagnose correctly. Permission to not have an answer yet. |

**The pattern:** Before your next client or team communication, ask yourself: "What would make this person feel okay right now?" Address that need directly in what you say next. You don't have to solve the underlying problem — you have to show that you understand it.

---

### Step 4 — Request (concrete, actionable, genuinely optional)

An NVC request has three properties: it is specific, it is actionable right now, and it is genuinely optional — the other person can decline, and you have a plan if they do. This is what distinguishes a request from a demand.

Demands from clients during incidents ("fix this in the next 10 minutes or we're cancelling") generate panic, which generates bad decisions. Responding with a genuine request de-escalates without conceding a timeline you cannot meet.

**To the client — communication timing:**

| Non-request (avoid) | Request (use instead) |
|---|---|
| "We're working on it. I'll update you when we know more." | "I'd like to give you an accurate diagnosis rather than a guess. Can I call you back in 15 minutes with confirmed findings? If anything changes before then, I'll contact you immediately." |
| "It should be fixed soon." | "Our current hypothesis is X. I'll have a confirmed answer or a workaround by 15:30. Does that work for you?" |
| "I need you to calm down." | "I understand this is stopping your operations. Can I have 10 minutes to run the diagnostics, and then give you a complete picture rather than a partial one?" |

**To the team — information gathering:**

| Non-request (avoid) | Request (use instead) |
|---|---|
| "Someone pull the logs." | "Marcus, I need the last 50 lines of the PostgreSQL log from the primary. Can you paste them in the channel in the next 2 minutes?" |
| "Can someone check the database?" | "Ana, can you run `SELECT count(*) FROM pg_stat_activity` on the production primary and share the output here? I need it before 14:52." |

**To management — escalation:**

| Non-request (avoid) | Request (use instead) |
|---|---|
| "I need help, this is out of control." | "I'm escalating this to P1. I have the PostgreSQL logs and pg_stat_activity output. I need a second set of eyes on the WAL directory size. Can [Name] join the call in the next 5 minutes?" |

**The pattern:** `[What you need] + [from whom] + [by when] + [what you'll do if they can't].`

---

## The De-escalation Script

Use this verbatim for the first 90 seconds of a P1 client call. Do not improvise until the client is calm.

```
"[Client name], I have your incident open. I can confirm the database has been
unreachable since [time] — that's [X] minutes. I don't have a diagnosis yet,
and I'm not going to guess. I'm running the initial checks right now. I'll call
you back in 15 minutes with confirmed findings and a timeline. If anything
changes before that, I'll contact you immediately."
```

**Why this works, line by line:**

- *"I can confirm the database has been unreachable since [time]"* — Observation. You are acknowledging the factual state, not defending against it. This signals that you have checked, you are informed, and you are not going to gaslight them about what is happening.
- *"I don't have a diagnosis yet, and I'm not going to guess"* — Addresses the client's implicit need: accurate information. It signals that when you do give them a diagnosis, it will be reliable.
- *"I'll call you back in 15 minutes"* — A specific, actionable request. 15 minutes is the P1 communication cadence. It gives them something to hold onto instead of an open-ended void.
- *"If anything changes before that, I'll contact you immediately"* — Removes the fear that they'll be left in silence if the situation worsens.

---

## Business Impact

Organizations that apply structured communication frameworks during incidents report consistent outcomes: faster resolution (less time spent on interpersonal escalation, more on technical diagnosis), lower escalation rates to supervisors, and higher client retention after incidents compared to incidents where the communication was reactive and unstructured.

The mechanism is simple. Unstructured communication during a P1 typically follows this pattern: client escalates → engineer panics → engineer guesses → guess is wrong → client is angrier → more time is lost. Structured communication breaks the loop at the second step. The engineer who names their own pressure and responds with a genuine request instead of a defensive guess takes control of the call dynamic without requiring authority or seniority to do so.

The framework is also teachable. A communication approach that lives in one engineer's personality cannot scale. One that is documented, practiced, and reviewed in post-mortems can.

---

## Anti-Patterns

Recognizing what not to do is as important as knowing the framework.

| Anti-pattern | Why it fails | NVC alternative |
|---|---|---|
| Premature reassurance ("don't worry, we'll have this fixed shortly") | Builds false confidence. Damages credibility when the timeline proves wrong. | Honest uncertainty + specific next update time. |
| Blame language in the war room ("whoever pushed this broke it") | Activates defensiveness. Derails the technical investigation into a political one. | Pure observation language. "This changed at 14:30. We don't know why yet." |
| "Working as designed" | Dismisses the client's valid operational problem. Even if true, it is not useful. | Acknowledge the operational impact first. Explain the technical behavior separately and later. |
| Silence during long diagnosis | The client escalates to management, introducing new pressure into the call. | Scheduled updates even when status is "still investigating." Silence reads as abandonment. |
| Over-technical updates to non-technical stakeholders | Increases anxiety rather than reducing it. "We're checking pg_replication_slots" means nothing to a business owner. | Translate to operational impact language. "We've identified the cause. We're running the fix now. Your operations should resume within 20 minutes." |
| Matching the client's emotional register | If the client is panicking and you match their urgency, you amplify rather than contain. | Calm, precise, practiced. The tone you project is the tone the call will eventually settle into. |

---

## Cross-Reference

- War room communication protocols: [`war-room/etiquette.md`](../war-room/etiquette.md)
- Post-mortem communication review section: [`post-mortem/template.md`](../post-mortem/template.md)
- Escalation language: [`escalation/protocol.md`](../escalation/protocol.md)
- The WAL runbook this framework accompanies: [`runbooks/pg-wal-zero-bytes-free.md`](../runbooks/pg-wal-zero-bytes-free.md)
