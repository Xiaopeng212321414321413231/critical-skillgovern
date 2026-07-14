# 🔍 Critical SkillGovern

> **A cross-platform skill quality governance framework** — battle-tested on **128 skills across 40 categories**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/Platform-Hermes%20%7C%20Claude%20Code%20%7C%20Codex-blue)]()

[中文版](README.zh-CN.md)

---

## The Problem

The more skills you have, the harder it is for an LLM agent to pick the right one. This isn't a model limitation — **it's a routing problem**. Skill descriptions lack the signal LLMs need for accurate selection.

| Skill Count | Routing Issues | Impact |
|-------------|----------------|--------|
| 1-10 | Nearly none | Easy to distinguish |
| 10-50 | Occasional misfires | Descriptions too vague |
| 50-100 | Frequent misfires | Need structured routing |
| 100+ | Unreliable system | Must govern |

**Critical SkillGovern** gives you a battle-tested workflow to keep your skill library accurate at any scale.

---

## Why You Should Care

The **third-party skill packs** you downloaded — Superpowers workflow pack, Baoyu creative pack, Matt Pocock TypeScript pack, design skill packs — likely have routing issues:

| Source | Routing Health | Typical Problem |
|--------|---------------|-----------------|
| Built-in (official) | 100% ✅ | — |
| Superpowers pack | Excellent ✅ | Best among community packs |
| Baoyu pack | ⚠️ ~60% | Weak negative samples, single-layer tags |
| Design pack (16 skills) | ⚠️ ~19% | 13/16 had weak negative samples |
| Matt Pocock pack | ⚠️ ~70% | Weak negative sample |

📖 Full case study → [examples/third-party-packs.md](examples/third-party-packs.md)

Before governance:

```yaml
【不适用场景】不需要生成创意内容/可视化时    ← Too vague, no alternative
```

After governance:

```yaml
【不适用场景】For simple charts/diagrams → use excalidraw;
For AI art rather than structured infographics → use image generation
            ← Points to specific alternatives
```

**The difference**: before, the model guesses wrong ~30% of the time. After, misfires drop to ~5%.

---

## Core Pipeline

```
Routing Diagnosis → Critical Questioning → User Approval → Execution → Verification → Final Report
```

| Phase | What It Does | Output |
|-------|-------------|--------|
| 1️⃣ **Routing Diagnosis** | Scan skill descriptions for template residuals, English-only triggers, weak negative samples | Issue list |
| 2️⃣ **Critical Questioning** | 5W1H questioning + reverse thinking + assumption mining | Deep analysis |
| 3️⃣ **User Approval** | Severity-based triage, user decides what to fix | Approved fix list |
| 4️⃣ **Execution** | Modify routing only (never touch functionality) | Patched files |
| 5️⃣ **Verification** | Re-run diagnosis to confirm fixes | Verification report |
| 6️⃣ **Final Report** | Document results | Complete audit report |

---

## Supported Platforms

| Platform | Skill Format | Adapter |
|----------|-------------|---------|
| 🏛️ **Hermes Agent** | SKILL.md (YAML frontmatter + Markdown) | [adapters/hermes.md](adapters/hermes.md) |
| 🌀 **Claude Code** | .claude/skills/*.md (Markdown) | [adapters/claude-code.md](adapters/claude-code.md) |
| 🤖 **Codex CLI** | Prompt templates / Shell wrappers | [adapters/codex.md](adapters/codex.md) |

---

## Quick Start

```bash
# 1. Review all your skills
python scripts/batch-review.py --path ~/.hermes/skills --format hermes

# 2. Review a specific category (e.g., third-party packs)
python scripts/batch-review.py --path ~/.hermes/skills/creative --format hermes

# 3. Export CSV report
python scripts/batch-review.py --path ~/.hermes/skills --format hermes --csv report.csv
```

### What to Fix (Priority Order)

| Severity | Issue | How to Fix |
|----------|-------|------------|
| 🔴 Critical | Template residuals (`.join`, `kw[:`) | Remove Python literals from descriptions |
| 🔴 Critical | English-only triggers | Translate to Chinese (or user's locale) |
| 🟡 Suggested | Weak negative samples | Point to specific alternative skills |
| 🟢 Optional | Single-layer tags | Add subcategory tags |
| 🟢 Optional | Missing related_skills | Link cross-category skills |

---

## Project Structure

```
critical-skillgovern/
├── README.md                         # English (this file)
├── README.zh-CN.md                   # 中文版
├── LICENSE                           # MIT
├── docs/
│   ├── methodology.md                # Core methodology (6-stage pipeline)
│   └── routing-optimization.md       # Routing optimization guide
├── adapters/
│   ├── hermes.md                     # Hermes Agent guide
│   ├── claude-code.md                # Claude Code guide
│   └── codex.md                      # Codex CLI guide
├── templates/
│   ├── diagnostic-card.md            # Diagnostic card template
│   └── skill-audit-report.md         # Audit report template
├── scripts/
│   ├── batch-review.py               # Batch review script
│   └── validate-routing.py           # Routing validation script
├── examples/
│   ├── before-after.md               # Before/after optimization examples
│   ├── full-audit-example.md         # Full 128-skill audit walkthrough
│   └── third-party-packs.md          # 🌟 Third-party pack case study
└── CONTRIBUTING.md                   # Contribution guide
```

---

## Real-World Impact

Tested on a **128-skill, 40-category** Hermes Agent library with Superpowers, Baoyu, and 16 design skill packs:

| Metric | Before | After |
|--------|--------|-------|
| Routing coverage | 23/128 (18%) | 128/128 (100%) |
| Template residuals | 14 skills | 0 |
| English-only triggers | 97 skills | 0 |
| Weak negative samples | 54 skills | All fixed |
| Third-party pack misfire rate | ~30% | ~5% |

---

## Why Critical SkillGovern?

| Feature | Critical SkillGovern | Traditional Approaches |
|---------|---------------------|----------------------|
| Cross-platform | Hermes / Claude Code / Codex | Single platform only |
| Critical thinking | Reverse thinking + assumption mining | Forward checks only |
| Third-party pack support | Dedicated case studies + batch scripts | No third-party coverage |
| Battle-tested | 128 real skills with real data | Theoretical design |
| User-controlled | Severity-based triage + selective fix | Fully automated, no oversight |
| Verification step | Full re-check after fixes | No verification |

---

## Contributing

PRs and issues welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — free to use, modify, and distribute.
