# Critical SkillGovern — Methodology

> **Core insight**: The more skills you add, the harder routing becomes. The system isn't weak — skill descriptions simply lack the signal LLMs need to make good decisions.
>
> Battle-tested on **120+ skills across 40 categories**.

## The 7-Stage Pipeline

```
Stage 1: Routing Diagnosis          — Find problems
Stage 2: Classification & Tagging   — Build the skill tree
         ↓ User verifies classification ←--- KEY STEP
Stage 3: Critical Questioning       — Deep analysis
Stage 4: User Approval              — Decision & triage
Stage 5: Execution & Fix            — Precise treatment
Stage 6: Verification               — Quality check
Stage 7: Final Report               — Deliver results
```

---

## Stage 1: Routing Diagnosis

### Health Checklist

Check each skill against **6 routing health items**:

| # | Check | Symptoms | Severity |
|---|-------|----------|----------|
| 1 | Template Residuals | Python literals like .join, kw[: in descriptions | Critical |
| 2 | Wrong Locale | Triggers in English (for non-English users) | Critical |
| 3 | Redundant Description | Trigger scenario and output are nearly identical | Suggested |
| 4 | Weak Negative Samples | "When not needed" — no alternative pointed to | Suggested |
| 5 | Single-layer Tags | Tags have only one level (e.g., ["media"]) | Optional |
| 6 | Missing Links | related_skills is empty or no cross-category links | Optional |

### Universal Routing Structure

```
[Trigger Scenario] When to use — "When the user needs to..."
[Input Signals] Keywords/intent in user input
[Output Goal] What it produces — clear deliverable
[Exclusion Rules] When NOT to use — points to alternative skills
```

---

## Stage 2: Classification and Tagging (⚠️ Previously Missing)

Before deep analysis, **classify each skill into the right category**.

### What We Do

```
Each skill gets:
  1. tags (dual-layer: category + subcategory) e.g. [media, bilibili]
  2. Directory placement (which category it belongs to)
  3. related_skills (upstream/downstream links)
```

### Skill Tree

```
Development
├── planning       — brainstorming, writing-plans
├── implementation — tdd, subagent-driven, spike
├── debugging      — systematic-debugging
├── code-review    — requesting, receiving
└── completion     — verification, branch-finishing

Collaboration
├── coordination   — parallel-agents, git-worktrees, kanban

GitHub
├── devops         — auth, issues, pr-workflow
├── management     — repo-management, cleanup, polish
└── codebase       — inspection, code-review

Creative
├── design         — architecture-diagram, excalidraw, p5js
├── visual         — ascii-art, sketch, touchdesigner
├── writing        — humanizer, songwriting
└── prototype      — claude-design, pretext

Media
├── video          — bilibili, youtube, songsee
├── audio          — transcription, music
└── image          — gif-search, vision-tagging

MLOps — models, inference, evaluation
Productivity — pdf, notion, airtable, workspace
Note-taking — obsidian, pipeline
Research — arxiv, blogwatcher, llm-wiki
Hermes Config — profile, plugin, gateway
```

### ➡️ User Verifies Classification (Key Step)

```
Classifications assembled → You review → 
✅ Confirm → Move to Stage 3
🔄 Adjust → You tell me what to change → Re-confirm
```

This prevents "the categories I chose aren't the ones you wanted" — avoids wasted effort downstream.

---

## Stage 3: Critical Questioning

Now that classifications are confirmed, challenge them.

### 5W1H Framework

```
What: What does this skill do? What if it didn't? Better category?
Why: Why is it here? Why not another category? Does user need it?
Who: Who uses it? Who would misfire it?
When: When does it trigger correctly? When would it false trigger?
Where: Is the placement right? Better position?
How: How does it execute? How to verify?
```

### Reverse Thinking

```
Normal to Edge
- Normal trigger to Edge case (empty, max length, special chars)
- Normal flow to Error flow (interrupt, timeout, failure)
- Normal environment to Abnormal (no network, no permissions)

Certain to Hypothetical
- User expresses clearly to User expresses vaguely
- Keywords match to Keywords don't match
- Skill executes correctly to Skill executes incorrectly
```

### "So What?" Probe

```
Issue found to So what?
- Affects one skill to So what? What else?
- Affects one category to So what? Who else?
- Affects whole system to So what? How big?
- Affects user to So what? How many users?
```

---

## Stage 4: User Approval

Package findings into a decision list:

```
Critical (always fix — these are bugs):
  [ ] Template residual → Fix
  [ ] English trigger → Localize

Suggested (user decides):
  [ ] Weak negative → Point to alternative
  [ ] Category move → From media to note-taking

Optional (nice to have):
  [ ] Missing related_skills → Add links
```

---

## Stage 5: Execution and Fix

### Core Principle: Route Only, Don't Touch

| OK to Modify | NOT OK to Modify |
|-------------|-----------------|
| Description, trigger conditions | Functional code, commands |
| Tags, categories | API parameters, script commands |
| related_skills | Config templates |
| Negative samples | File structure |

---

## Stage 6: Verification

Re-run Stage 1 checklist:

```
- [ ] Template residuals cleared?
- [ ] Triggers localized?
- [ ] Input signals cover natural language variants?
- [ ] Negative samples point to alternatives?
- [ ] Tags dual-layer?
- [ ] related_skills have cross-category links?
- [ ] YAML frontmatter syntax valid?
```

---

## Stage 7: Final Report

```
=== Skill Audit Report ===
Skills: 128
Initial coverage: 23/128 (18%)
Final coverage: 128/128 (100%)

Fixes applied:
- Template residuals: 14
- English triggers: 97
- Weak negatives: 54

Skipped (user choice):
- Tags optimization: Not processed
- related_skills: Not processed

Third-party pack misfire rate: ~30% to ~5%

Status: Healthy
```

---

## Difference from the Old 6-Stage Flow

| Old (6-stage) | New (7-stage) | Why |
|---------------|---------------|-----|
| Diagnosis to Critical Questioning | Diagnosis to **Classification to User Verification to** Critical Questioning | Classification must come before critique, and you need to confirm it |
| One approval step | **Classification verification + Fix approval** — two decisions | One decision was too much; splitting is clearer |
| Critique came first | Classification verified before critique | Avoids wasting effort on a classification you don't agree with |

---

## When to Run

1. After installing new skills: Run stages 1-2, wait for your confirmation
2. After batch import: Full pipeline
3. After misfire incidents: Start from stage 3 (classification is already set)
4. Periodic maintenance: Stages 3-7 (classification stays, only routing quality)
