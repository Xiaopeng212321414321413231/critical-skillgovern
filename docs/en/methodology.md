# Critical SkillGovern — Methodology

> **Core insight**: The more skills you add, the harder routing becomes. The system isn't weak — skill descriptions simply lack the signal LLMs need to make good decisions.
>
> This methodology has been battle-tested on **128 skills across 40 categories**, covering Hermes Agent, Claude Code, and Codex ecosystems.

## The 6-Stage Review Pipeline

```
Stage 1: Routing Diagnosis — Find problems
Stage 2: Critical Questioning — Deep analysis
Stage 3: User Approval — Decision and triage
Stage 4: Execution and Fix — Precise treatment
Stage 5: Verification — Quality check
Stage 6: Final Report — Deliver results
```

## Stage 1: Routing Diagnosis

### Health Checklist

Check each skill against 6 routing health items:

| # | Check | Symptoms | Severity |
|---|-------|----------|----------|
| 1 | Template Residuals | Python literals like .join, kw[: in descriptions | Critical |
| 2 | Wrong Locale | Triggers in English (for non-English users) | Critical |
| 3 | Redundant Description | Trigger scenario and output are nearly identical | Suggested |
| 4 | Weak Negative Samples | "When not needed" — too vague, no alternative | Suggested |
| 5 | Single-layer Tags | Tags have only one level (e.g., ["media"]) | Optional |
| 6 | Missing Links | related_skills is empty or no cross-category links | Optional |

### Universal Routing Structure

Every skill should have 4 layers of routing information:

```
[Trigger Scenario] When to use — "When the user needs to..."
[Input Signals] Keywords/intent in user input
[Output Goal] What it produces — clear deliverable
[Exclusion Rules] When NOT to use — points to alternatives
```

## Stage 2: Critical Questioning

### 5W1H Framework

- **What**: What does this skill do? What if it didn't? Is there a better category?
- **Why**: Why is it in this category? Why not another? Does the user need it?
- **Who**: Who will use this skill? Who benefits? Who would misfire it?
- **When**: When does it trigger correctly? When would it false trigger?
- **Where**: Is the category placement right? Is there a better position?
- **How**: How does it execute? How do you verify it worked?

### Reverse Thinking

```
Normal to Edge
- Normal trigger to Edge case (empty input, max length, special chars)
- Normal flow to Error flow (interrupt, timeout, failure)
- Normal environment to Abnormal (no network, no permissions)

Certain to Hypothetical
- User expresses clearly to User expresses vaguely
- Keywords match to Keywords don't match
- Skill executes correctly to Skill executes incorrectly
```

### Assumption Mining

| Assumption Type | Common Assumption | Counter-Example |
|----------------|-------------------|-----------------|
| User behavior | User describes as expected | Vague, incomplete input |
| Environment | Environment works | Network errors, service down |
| Dependencies | All skills exist | Missing or mismatched skills |
| Sequencing | Skills fire in order | Out-of-order, concurrent triggers |

### "So What?" Probe

```
Found issue to So what?
- Affects one skill to So what? What else?
- Affects one category to So what? Who else?
- Affects entire system to So what? How big?
- Affects user to So what? How many users?
```

## Stage 3: User Approval

Package findings into a decision list:

```
Critical (always fix):
  [ ] Template residual: + ,.join(kw[:5]) + to Fix
  [ ] English trigger: When user needs... to Localize

Suggested (user decides):
  [ ] Weak negative: "When not needed" to Point to alternative

Optional (nice to have):
  [ ] Missing related_skills to Add cross-links
```

## Stage 4: Execution and Fix

### Core Principle: Route Only, Don't Touch

| OK to Modify | NOT OK to Modify |
|-------------|-----------------|
| Description, trigger conditions | Functional code, commands |
| Keywords, tags | Script commands, API params |
| related_skills links | Config templates, examples |
| Negative samples | File structure, layouts |

### Batch Fix Mode

1. Category mapping: Auto-generate triggers from directory names
2. Format unification: Template the 4-layer description
3. Link completion: Auto-recommend related_skills

## Stage 5: Verification

After fixes, re-run Stage 1 checks:

- [ ] Template residuals cleared?
- [ ] Triggers localized?
- [ ] Input signals cover natural language variants?
- [ ] Negative samples point to alternatives?
- [ ] Tags optimized (dual-layer)?
- [ ] related_skills have cross-category links?
- [ ] YAML frontmatter syntax valid?

## Stage 6: Final Report

```
=== Skill Audit Report ===
Skill: example-skill
Category: media/bilibili
Result: 5/6 passed

Critical Template residual to Fixed
Critical English trigger to Fixed
Suggested Weak negative to Fixed
Suggested Redundant desc to User declined
Optional Single-layer tag to Fixed
Optional Missing links to Fixed
Verification passed
```

## When to Apply This

1. After installing new skills: Auto-review
2. When writing new skills: Apply routing standards at creation
3. After batch import: Batch review + routing optimization
4. Before system upgrade: Full skill audit
5. After misfire incidents: Targeted fix + improve negative samples

## Advantages

- Cross-platform: Hermes, Claude Code, Codex
- Battle-tested: 128 skills in production
- Quantifiable: Each check can be automated
- Progressive: Single skill to batch optimization
- Non-invasive: Only routing descriptions, never functionality
