# Stepfork Product Roadmap

Strategic direction for transforming Stepfork from technical foundation to widely-adopted developer tool.

## Core Problem

**Current barrier to adoption**: Manual instrumentation (`@trace_tool`, `llm_request`) creates friction. Users must change existing code to try Stepfork.

**Current value gap**: Users see "trace recorder" rather than "regression test generator." The value proposition needs to be more immediate and obvious.

**Current credibility gap**: No public case studies, demos, or social proof. Repository needs distribution strategy.

---

## Priority 0: Remove Adoption Barriers

### 1. Auto-Instrumentation (HIGHEST IMPACT)

**Current state**: Users must manually decorate every tool and LLM call
```python
# Current: requires code changes
@trace_tool(name="search")
def search(query: str):
    ...
```

**Target state**: Zero-code instrumentation
```python
# Target: automatic
from stepfork import instrument

with instrument(app):  # or instrument.langraph(app)
    result = app.run()  # All tools, LLMs auto-captured
```

**Implementation priority:**
1. **LangGraph adapter** (FIRST) - Most common agent framework
   - Auto-record node inputs/outputs
   - Auto-record tool calls from `@tool` decorated functions
   - Auto-record model calls (LLM requests/responses)
   - Auto-record graph state transitions
   - Hook into LangGraph's execution callbacks

2. **OpenAI Agents SDK adapter** (SECOND)
   - Auto-record Assistant API calls
   - Auto-record function executions
   - Auto-record conversation turns

3. **Coverage reporting**
   ```bash
   stepfork inspect failure.sftrace --coverage
   # Instrumented: 15/18 tool calls (83%)
   # Warning: 3 external calls not captured
   # - requests.get() in line 45 of agent.py
   # - Database query in line 78 of db.py
   # - File write in line 92 of output.py
   ```

**Success metric**: Add Stepfork to a LangGraph agent in <5 lines of code

### 2. Realistic Case Study (HIGHEST CREDIBILITY)

Create `examples/realistic_failure/` with:

**Scenario**: Multi-step customer support agent
- **Agent task**: Process refund request (check policy, verify order, issue refund)
- **Failure**: Wrong refund decision due to incorrect policy interpretation
- **Recording**: Full trace captured automatically
- **Test generation**: pytest regression test exported
- **Fix verification**: Test fails on broken code, passes after fix

**Deliverables**:
- Complete working example
- README with before/after metrics
- 60-second demo GIF/video
- Blog post: "Real agent failure → regression test in 2 minutes"

**Metrics to include**:
- Steps: 12 events
- Trace size: 45KB
- Replay duration: 0.3s
- Test generation: 10 seconds
- Assertions: 5 (final output, tool sequence, state checks)

**Link prominently in main README**:
```markdown
## See It In Action

[**Watch the 2-minute demo**](examples/realistic_failure/demo.gif): 
Failing customer support agent → recorded trace → pytest regression test → verified fix

[Try it yourself →](examples/realistic_failure/README.md)
```

---

## Priority 1: Generate Value Automatically

### 3. Automatic Assertion Suggestions

**Current state**: User must manually write expected.json
```python
# User must figure out what to assert
expected = {"should_refund": True, "reason": "..."}
```

**Target state**: Auto-generated assertions
```bash
stepfork suggest failure.sftrace corrected.sftrace

# Suggested assertions:
# ✓ Final output: {"should_refund": True} 
# ✓ Tool sequence: check_policy → verify_order → issue_refund
# ✓ Tool NOT called: charge_customer
# ✓ State field "policy_version" = "2024-01"
# ✓ No repeated tool loops detected

Accept all? [Y/n/edit]
```

**Assertion types**:
- **Final response**: Exact match, contains, semantic similarity
- **Tool sequence**: Required tools called in order
- **Forbidden tools**: Specific tools NOT called
- **Side effects**: DB/API calls match expectations
- **State checks**: Required fields present and valid
- **Performance**: Token/cost/latency within threshold
- **Loop detection**: No repeated tool call patterns

**Implementation**:
```python
from stepfork.suggest import suggest_assertions

assertions = suggest_assertions(
    baseline="corrected.sftrace",
    reference="failure.sftrace",
    strictness="medium"  # loose, medium, strict
)

# Returns structured assertions ready for pytest export
```

### 4. Nondeterminism Normalization

**Current limitation**: User code must be deterministic or replay fails

**Auto-freeze common sources**:
- `datetime.now()` → Fixed timestamp
- `uuid.uuid4()` → Deterministic UUID sequence
- `random.random()` → Seeded RNG
- `os.getcwd()` → Normalized path
- Timestamps in API responses → `<TIMESTAMP>`
- Unordered dict/set iteration → Sorted

**Implementation**:
```python
# Auto-applied during replay
from stepfork.normalize import auto_normalize

with ReplaySession.from_trace("trace.sftrace", normalize=True):
    result = agent()  # UUIDs, timestamps auto-frozen

# Custom normalizers
@stepfork.normalizer("order_id")
def normalize_order_id(value):
    return "<ORDER_ID>"
```

**Replay report**:
```bash
stepfork replay trace.sftrace --report-nondeterminism

# Likely nondeterminism detected:
# - UUIDs differ in 3 locations (auto-normalized)
# - Timestamps differ in 2 locations (auto-normalized)
# - Unordered dict at step 5 (keys reordered)
# - Random value at step 8 (WARNING: not instrumented)
```

---

## Priority 1: Enable Team Workflows

### 5. CI Integration

**GitHub Actions workflow**:
```yaml
name: Agent Regression Tests
on: pull_request

jobs:
  replay:
    runs-on: ubuntu-latest
    steps:
      - uses: stepfork/replay-action@v1
        with:
          traces: tests/traces/
          mode: strict
          
      - name: Comment PR
        uses: stepfork/pr-comment@v1
        # Auto-comments diff summary
```

**CI mode**:
```bash
stepfork replay trace.sftrace --ci --baseline approved.sftrace

# CI mode:
# ✓ Tool sequence matches baseline
# ✗ Final output differs from baseline
# → Exit code 1 (CI failure)
```

**Approval workflow**:
```bash
# Developer makes intentional behavior change
stepfork replay new_behavior.sftrace --approve

# Creates approved baseline
# Team reviews in PR: "Approved behavior change"
```

**PR comment example**:
```markdown
## 🔍 Stepfork Regression Report

**Changed behaviors detected in 2 traces:**

### `refund_agent.sftrace`
- ✗ Final output changed: `{"approved": false}` → `{"approved": true}`
- ✓ Tool sequence unchanged
- ⚠️ New tool called: `verify_manager_approval`

### `search_agent.sftrace`  
- ✓ All behaviors match baseline
```

---

## Priority 2: Build Trust

### 6. Security & Trust Tools

**`stepfork doctor` command**:
```bash
stepfork doctor

# Checking project health...
# ✓ No unredacted secrets found
# ✓ Trace files under size limit (45MB / 100MB)
# ✗ Warning: 2 API keys detected in trace abc123
#   → line 45: "sk-proj-..."
#   → line 78: Bearer token
# ✓ All dependencies supported
# ✗ Warning: 15% of tool calls not instrumented
# → Suggestion: Add @trace_tool to utils.py:search()

# Overall health: 3 warnings, 0 errors
```

**Security features**:
- Auto-detect common secret patterns (API keys, tokens, credentials)
- Trace encryption at rest (optional)
- Audit log of what was redacted
- Clear privacy model documentation

**Trust documentation**:
- **What we record**: Tool calls, LLM requests, final outputs
- **What stays local**: Everything by default
- **What we freeze**: Instrumented boundaries only
- **What we can't guarantee**: Uninstrumented side effects
- **Telemetry**: Opt-in, clearly disclosed

### 7. Storage & Team Features

**Storage backends**:
```python
# Local (default)
stepfork configure --storage local --path ./traces

# S3
stepfork configure --storage s3 --bucket my-traces

# GCS
stepfork configure --storage gcs --bucket my-traces
```

**Team workflows**:
```bash
# Commit sanitized traces
stepfork export trace.sftrace --sanitized traces/baseline.sftrace

# Share approved baselines
git commit traces/approved/*.sftrace -m "Update baselines"

# Team member syncs
git pull
stepfork replay --baseline-dir traces/approved/
```

---

## Priority 3: Polish & Distribution

### 8. Workflow Improvements

**Simplified commands**:
```bash
# Initialize project
stepfork init

# Auto-record failed runs
stepfork watch "python agent.py"

# Record explicitly
stepfork record --run "python agent.py"

# Replay with ID
stepfork replay abc123

# Update after intentional change
stepfork replay abc123 --update-expected

# Clean up
stepfork prune --older-than 30d --larger-than 10MB

# Project config
cat stepfork.toml
```

**Config file** (`stepfork.toml`):
```toml
[stepfork]
storage = "local"
trace_dir = "./traces"
max_trace_size = "100MB"
auto_redact = true

[redaction]
patterns = ["sk-.*", "Bearer .*", "password.*"]
fields = ["api_key", "secret", "token"]

[instrumentation]
auto_instrument = ["langchain", "langgraph", "openai"]
warn_missing = true
```

### 9. Distribution Strategy

**Content**:
1. **Blog post**: "Why AI agents need regression tests, not just evals"
   - Evals test model quality
   - Regression tests verify behavior doesn't break
   - Stepfork bridges the gap

2. **Demo video**: 60-second screen recording
   - Agent fails
   - `stepfork record`
   - `stepfork export`
   - Fix agent
   - `pytest` passes
   - Done

3. **README improvements**:
   - Add badges (PyPI, tests, docs, Python versions)
   - Add "Who is this for?" section
   - Add comparison table (vs LangSmith, promptfoo, etc.)
   - Prominent demo link at top

4. **Community engagement**:
   - LangChain/LangGraph Discord
   - OpenAI developer forums
   - Reddit: r/LangChain, r/Python, r/MachineLearning
   - Hacker News: "Show HN: Stepfork - regression testing for AI agents"
   - Python Weekly newsletter
   - Agent engineering communities

**Social proof**:
- GitHub badges
- Star count
- PyPI download stats
- User testimonials (once available)
- Integration partner logos

---

## Prioritized Implementation Timeline

### Sprint 1: Remove Friction (2 weeks)

**Week 1: Auto-instrumentation**
- [ ] Build LangGraph adapter with auto-recording
- [ ] Add `instrument(app)` context manager
- [ ] Add coverage reporting to `inspect` command
- [ ] Test with real LangGraph examples
- [ ] Document migration: manual → auto

**Week 2: Credibility**
- [ ] Create realistic customer-support failure example
- [ ] Record demo GIF (60 seconds)
- [ ] Write case study README with metrics
- [ ] Blog post: "AI agent regression testing in 2 minutes"
- [ ] Update main README with prominent demo link

### Sprint 2: Generate Value (2 weeks)

**Week 3: Smart defaults**
- [ ] Implement `stepfork suggest` for basic assertions
- [ ] Add nondeterminism auto-normalization
- [ ] Add nondeterminism detection report
- [ ] Test with real-world traces
- [ ] Document assertion types

**Week 4: CI integration**
- [ ] Build `--ci` mode with strict baseline checking
- [ ] Create GitHub Actions workflow example
- [ ] Add approval flow (`--approve` flag)
- [ ] PR comment integration
- [ ] CI/CD documentation

### Sprint 3: Trust & Polish (1 week)

**Week 5: Security**
- [ ] Implement `stepfork doctor` health check
- [ ] Enhanced secret detection
- [ ] Trace encryption option
- [ ] Security documentation page
- [ ] Privacy model page

**Week 6: Distribution**
- [ ] Add all README improvements
- [ ] Create demo video
- [ ] Submit to communities (Discord, Reddit, HN)
- [ ] Python Weekly submission
- [ ] Track adoption metrics

---

## Success Metrics

### Adoption Metrics
- **Primary**: GitHub stars (target: 100 in 3 months)
- **Secondary**: PyPI downloads (target: 500/month)
- **Tertiary**: Time to first trace (target: <5 minutes)

### Engagement Metrics
- Issues opened (questions, bug reports, feature requests)
- PR contributions from external developers
- Example repositories using Stepfork
- Blog post views and shares

### Product Metrics
- % of traces recorded with auto-instrumentation vs manual
- % of users who export to pytest
- % of users who use suggestion feature
- Average trace size and replay time

---

## Quick Wins (Can Ship This Week)

### 1. README improvements (2 hours)
- Add badges
- Add "Who is this for?" section  
- Improve opening with clearer value prop
- Link to existing examples more prominently

### 2. Coverage hint (1 hour)
- Add warning when `@trace_tool` count is low
- Suggest specific functions to instrument
- Show instrumentation percentage

### 3. Workflow simplification (30 min)
- Add `stepfork init` to create stepfork.toml template
- Add `stepfork list` to show recorded traces
- Improve error messages with suggestions

### 4. Documentation polish (2 hours)
- Add "Quick Start" to docs/index.md
- Add "Migration Guide" for existing projects
- Add "Best Practices" guide
- Add "Limitations" page with workarounds

---

## Comparison: Stepfork vs Alternatives

| Feature | Stepfork | LangSmith | promptfoo | pytest |
|---------|----------|-----------|-----------|--------|
| **Trace recording** | ✅ Auto + manual | ✅ Auto | ❌ Manual | ❌ Manual |
| **Frozen replay** | ✅ Yes | ❌ No | ❌ No | ⚠️ Mocks |
| **pytest export** | ✅ Yes | ❌ No | ⚠️ Limited | N/A |
| **Local-first** | ✅ Yes | ❌ Cloud | ✅ Yes | ✅ Yes |
| **Auto assertions** | 🔜 v0.3 | ❌ No | ⚠️ Manual | ❌ Manual |
| **Minimization** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **CI integration** | 🔜 v0.3 | ✅ Yes | ✅ Yes | ✅ Yes |
| **Cost** | Free/OSS | Paid | Free/OSS | Free/OSS |

**Positioning**: 
- vs **LangSmith**: Local-first privacy, frozen replay, pytest export
- vs **promptfoo**: Automatic capture, frozen replay, regression (not just eval)
- vs **pytest**: Agent-aware, auto-assertions, deterministic replay

---

## Feedback Integration

This roadmap incorporates strategic feedback focusing on:
1. ✅ Effortless adoption (auto-instrumentation)
2. ✅ Real-world credibility (case study, demo)
3. ✅ Obvious value (auto-assertions, smart defaults)
4. ✅ Team workflows (CI, approvals)
5. ✅ Trust & security (doctor, redaction)
6. ✅ Distribution (content, community)

**Next Action**: Implement Sprint 1, Week 1 - LangGraph auto-instrumentation.
