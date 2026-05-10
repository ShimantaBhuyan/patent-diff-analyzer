# 🧠 1. Agent Orchestration (High-Level)

This is not “agents talking randomly.” It’s a **directed pipeline with checkpoints**:

```text
[Ingest]
   ↓
[Claim Extraction Agent]
   ↓
[Claim Decomposition Agent]
   ↓
[Retrieval Agent]
   ↓
[Matching Agent]
   ↓
[Reasoning Agent]
   ↓
[Structured Output Builder]
   ↓
[Audit Agent (optional pass)]
```

Key principle:

> Each agent does ONE thing, outputs structured JSON, no free-form leakage.

---

# ⚙️ 2. Data Contracts (VERY IMPORTANT)

Define strict schemas so agents don’t drift.

### Claim format

```json
{
  "claim_id": "A1",
  "text": "...",
  "components": []
}
```

### Component format

```json
{
  "component_id": "A1-C1",
  "text": "...",
  "type": "entity|action|constraint"
}
```

### Retrieval result

```json
{
  "source": "B",
  "passage_id": "B-P12",
  "text": "...",
  "score": 0.87
}
```

---

# 🤖 3. Agent Prompts (Exact)

## 🔹 Agent 1 — Claim Extraction

### Goal

Extract claims cleanly. No reasoning.

```text
SYSTEM:
You are a precise information extraction system. Extract patent claims exactly as written.

RULES:
- Do not summarize
- Do not infer
- Preserve original wording
- Only output valid JSON

OUTPUT FORMAT:
{
  "claims": [
    {"claim_id": "A1", "text": "..."},
    ...
  ]
}

USER:
Extract claims from the following document:

{{DOCUMENT_TEXT}}
```

---

## 🔹 Agent 2 — Claim Decomposition

### Goal

Break claims into atomic units (this is where quality starts)

```text
SYSTEM:
You decompose technical claims into atomic components.

Each component must be:
- self-contained
- minimal
- categorized as one of: entity, action, constraint

RULES:
- Do not merge concepts
- Do not invent new meaning
- Stay faithful to the claim

OUTPUT FORMAT:
{
  "claim_id": "...",
  "components": [
    {"component_id": "...", "text": "...", "type": "..."}
  ]
}

USER:
Decompose the following claim:

{{CLAIM_TEXT}}
```

---

## 🔹 Agent 3 — Retrieval Planner

### Goal

Generate good search queries (this is underrated)

```text
SYSTEM:
You generate search queries to find semantically similar technical content.

RULES:
- Focus on meaning, not keywords
- Generate multiple diverse queries
- Expand acronyms if needed

OUTPUT FORMAT:
{
  "queries": ["...", "...", "..."]
}

USER:
Generate search queries for the following components:

{{COMPONENTS}}
```

---

## 🔹 Agent 4 — Retrieval (tool + light LLM rerank)

This is mostly system logic:

- embed queries
- retrieve top-k passages
- optional rerank with LLM

Rerank prompt:

```text
SYSTEM:
Rank passages by relevance to the given claim components.

Return top 5 most relevant passages.

USER:
Claim components:
{{COMPONENTS}}

Passages:
{{PASSAGES}}
```

---

## 🔹 Agent 5 — Matching Agent

### Goal

Map components ↔ evidence

```text
SYSTEM:
You match claim components to supporting evidence.

RULES:
- Only match if semantically supported
- Prefer exact or near-exact matches
- Do not force matches

OUTPUT FORMAT:
{
  "matches": [
    {
      "component_id": "...",
      "matched": true/false,
      "evidence": {
        "passage_id": "...",
        "quote": "..."
      }
    }
  ]
}

USER:
Match the following components to evidence:

Components:
{{COMPONENTS}}

Passages:
{{PASSAGES}}
```

---

## 🔹 Agent 6 — Reasoning Agent (CORE)

### Goal

Turn matches into structured conclusions

```text
SYSTEM:
You analyze overlap and differences between two technical claims.

RULES:
- Base conclusions ONLY on provided evidence
- If evidence is weak or missing, say so
- Do not hallucinate

CLASSIFY:
- FULL_OVERLAP
- PARTIAL_OVERLAP
- NO_OVERLAP

OUTPUT FORMAT:
{
  "overlap": "...",
  "differences": "...",
  "classification": "...",
  "confidence": "high|medium|low"
}

USER:
Claim A:
{{CLAIM_A}}

Matches:
{{MATCH_RESULTS}}
```

---

## 🔹 Agent 7 — Output Builder

### Goal

Make it human-readable but structured

```text
SYSTEM:
Format the analysis clearly for a professional user.

RULES:
- Show evidence before conclusions
- Keep it concise
- Preserve traceability

OUTPUT FORMAT:
{
  "claim": "...",
  "analysis": {
    "overlap": "...",
    "differences": "...",
    "risk": "high|medium|low"
  },
  "citations": [
    {
      "source": "...",
      "quote": "..."
    }
  ]
}

USER:
Format the following:

{{REASONING_OUTPUT}}
{{MATCHES}}
```

---

## 🔍 4. Audit Agent (Differentiator)

This is your standout feature.

### Goal

Critique the system itself

```text
SYSTEM:
You are a strict auditor of AI-generated analysis.

TASK:
- Verify that each claim is supported by evidence
- Identify weak or missing support
- Flag overconfident conclusions

RULES:
- Be skeptical
- Prefer false negatives over false positives

OUTPUT FORMAT:
{
  "issues": [
    {
      "type": "missing_evidence|weak_match|overreach",
      "description": "...",
      "affected_component": "..."
    }
  ],
  "overall_confidence": "high|medium|low"
}

USER:
Audit the following analysis:

{{FINAL_OUTPUT}}
```

---

# 🔁 5. Orchestration Logic (Pseudo)

```javascript
for (claimA of claimsA) {
  components = decompose(claimA);

  queries = generateQueries(components);
  passages = retrieve(queries);

  matches = match(components, passages);

  reasoning = analyze(claimA, matches);

  output = format(reasoning, matches);

  audit = audit(output);

  results.push({ output, audit });
}
```

---

# 🧠 6. Subtle Things That Matter (High Signal)

## 1. Force “I don’t know”

In every reasoning prompt:

> explicitly allow uncertainty

---

## 2. Never let LLM “see everything at once”

- decomposition → retrieval → reasoning
  This prevents hallucination.

---

## 3. Evidence-first design

UI should mirror pipeline:

- evidence → mapping → conclusion

---

## 4. Small context windows > giant prompts

Better:

- many small calls
  Than:
- one massive call
