# Skill: Implement New LLM Agent

Step-by-step guide for backend-engineer to add a new LLM agent to the system.

## Overview
Agents are LangGraph nodes that analyze code for specific issues. Security, Performance, Style, and Logic agents already exist. This skill covers how to add a custom agent (e.g., "ReactHooks" agent for React-specific issues).

## Step 1: Design the Agent

Before coding, decide:

1. **What does it analyze?**
   - Input: code (string), language (string), context (dict)
   - Example: "finds React hooks violations (eslint-plugin-react-hooks rules)"

2. **What does it find?**
   - Output: list of findings
   - Each finding: {type, line, severity, message, suggestion}
   - Example types: "hook_rules_violation", "dependency_array_missing"

3. **Which model to use?**
   - Simple (style-like): Claude Sonnet 4.6
   - Complex (logic-like): Claude Opus 4.6
   - Decision: Does it need deep reasoning?

4. **Success criteria:**
   - What makes a "good" agent output?
   - Examples: "catches 80%+ of real violations"

## Step 2: Create Agent File

Create `backend/agents/custom_agent.py`:

```python
"""Custom agent for analyzing [specific aspect]."""
import json
import logging
from typing import TypedDict

logger = logging.getLogger(__name__)

class CustomAgentState(TypedDict):
    """Agent state for custom analysis."""
    code: str
    language: str
    context: dict
    findings: list[dict]

async def custom_agent(state: CustomAgentState) -> dict:
    """Analyze code for [specific issues].
    
    Input:
        state: {code, language, context}
    
    Output:
        {findings: [{type, line, severity, message, suggestion}]}
    
    Example output:
        {
            "findings": [
                {
                    "type": "hook_rules_violation",
                    "line": 42,
                    "severity": "warning",
                    "message": "Missing dependency in useEffect hook",
                    "suggestion": "Add 'userId' to dependency array: useEffect(() => {...}, [userId])"
                }
            ]
        }
    """
    
    code = state["code"]
    language = state["language"]
    context = state.get("context", {})
    
    # Skip if not applicable to this language
    if language not in ["javascript", "typescript", "jsx", "tsx"]:
        return {"findings": []}
    
    # Build prompt
    prompt = f"""You are a code reviewer specializing in [SPECIALIZE_IN].

Analyze this {language} code for [ISSUES_TO_FIND]:

Code:
```{language}
{code}
```

Return ONLY valid JSON in this format:
{{
    "findings": [
        {{
            "type": "issue_type",
            "line": 42,
            "severity": "critical|warning|info",
            "message": "Human readable message",
            "suggestion": "How to fix it"
        }}
    ]
}}

Focus on:
- [Key concern 1]
- [Key concern 2]
- [Key concern 3]

Ignore:
- Style issues (use style_agent for those)
- Security issues (use security_agent for those)
"""
    
    # Select LLM (from DEVELOPMENT_PLAN context, user settings are available)
    from backend.agents.llm_router import llm_router
    from backend.config import settings
    
    # For this example, assume we're in agent execution with user context
    # In real code, this comes from orchestrator state
    llm = llm_router.get_default_llm()  # Or pass user_settings
    
    try:
        # Call LLM
        response = await llm.ainvoke(prompt)
        
        # Parse response
        try:
            data = json.loads(response)
            findings = data.get("findings", [])
        except json.JSONDecodeError:
            logger.error(f"Custom agent returned invalid JSON: {response}")
            findings = []
        
        # Validate findings
        validated = []
        for finding in findings:
            if all(key in finding for key in ["type", "line", "severity", "message"]):
                validated.append(finding)
        
        return {"findings": validated}
        
    except Exception as e:
        logger.error(f"Custom agent failed: {e}")
        return {"findings": []}
```

## Step 3: Register Agent in Orchestrator

Edit `backend/agents/orchestrator.py`:

```python
from backend.agents.custom_agent import custom_agent

# Add node to graph
graph.add_node("custom", custom_agent)

# Add edges (custom runs in parallel with other agents)
graph.add_edge("START", "custom")
graph.add_edge("custom", "aggregate")

# Update aggregator to handle custom findings
# (aggregator already handles any findings format)
```

## Step 4: Add to Serialization

Update `backend/models/schemas.py`:

```python
class FindingSchema(BaseModel):
    """Finding from any agent."""
    agent_name: str  # "security", "performance", "style", "logic", "custom"
    type: str
    severity: Literal["critical", "warning", "info"]
    file_path: str
    line_number: int
    message: str
    suggestion: Optional[str] = None

class ReviewResponse(BaseModel):
    """Review with all findings."""
    id: str
    status: str
    findings: list[FindingSchema]
    agents_used: list[str]  # Add custom here if selected
```

## Step 5: Make It User-Selectable

Update `backend/routers/reviews.py`:

```python
# Add custom to available agents list
AVAILABLE_AGENTS = ["security", "performance", "style", "logic", "custom"]

@router.post("/reviews")
async def create_review(
    request: CreateReviewRequest,  # Has selected_agents field
    ...
):
    """selected_agents can include 'custom'"""
    # Validation happens here
    if "custom" in request.selected_agents:
        # Allowed, continue
        pass
```

Update `backend/routers/settings.py`:

```python
@router.get("/settings")
async def get_settings(...):
    return {
        ...
        "available_agents": ["security", "performance", "style", "logic", "custom"],
        "selected_agents": user_settings.selected_agents
    }
```

## Step 6: Frontend Integration

Update `frontend/src/components/LLMSelector.tsx`:

```typescript
const AVAILABLE_AGENTS = [
  { id: "security", label: "Security Analysis", description: "Find vulnerabilities" },
  { id: "performance", label: "Performance", description: "Optimize speed" },
  { id: "style", label: "Code Style", description: "Follow conventions" },
  { id: "logic", label: "Logic Errors", description: "Fix bugs" },
  { id: "custom", label: "Custom Analysis", description: "Your specific checks" }
]

export function AgentSelector() {
  const { selectedAgents, updateSettings } = useSettingsStore()

  return (
    <div className="space-y-3">
      {AVAILABLE_AGENTS.map(agent => (
        <label key={agent.id} className="flex items-center">
          <input
            type="checkbox"
            checked={selectedAgents.includes(agent.id)}
            onChange={(e) => {
              const updated = e.target.checked
                ? [...selectedAgents, agent.id]
                : selectedAgents.filter(a => a !== agent.id)
              updateSettings({ selectedAgents: updated })
            }}
          />
          <span className="ml-3">
            <div className="font-medium">{agent.label}</div>
            <div className="text-sm text-gray-500">{agent.description}</div>
          </span>
        </label>
      ))}
    </div>
  )
}
```

## Step 7: Tests

Create `backend/tests/test_custom_agent.py`:

```python
import pytest
from backend.agents.custom_agent import custom_agent

@pytest.mark.asyncio
async def test_custom_agent_finds_issues():
    """Custom agent should detect [specific issues]."""
    code = """
    useEffect(() => {
        setData(fetchData(userId))
    })  // Missing dependency!
    """
    
    state = {
        "code": code,
        "language": "typescript",
        "context": {},
        "findings": []
    }
    
    result = await custom_agent(state)
    
    assert len(result["findings"]) > 0
    assert result["findings"][0]["type"] == "hook_rules_violation"
    assert "dependency" in result["findings"][0]["message"].lower()

@pytest.mark.asyncio
async def test_custom_agent_skips_non_relevant():
    """Should return empty findings for non-JavaScript code."""
    code = "function test() { return 42 }"
    
    state = {
        "code": code,
        "language": "python",
        "context": {},
        "findings": []
    }
    
    result = await custom_agent(state)
    assert result["findings"] == []
```

## Step 8: Integration Test

Create integration test in `backend/tests/integration/test_custom_agent_flow.py`:

```python
@pytest.mark.asyncio
async def test_custom_agent_in_workflow(async_client, test_repo):
    """End-to-end: create review with custom agent enabled."""
    
    # Create review with custom agent
    response = await async_client.post(
        "/api/reviews",
        json={
            "repo_id": test_repo.id,
            "github_pr_number": 42,
            "selected_agents": ["security", "custom"]  # Include custom
        }
    )
    assert response.status_code == 201
    review_id = response.json()["review_id"]
    
    # Analyze
    await async_client.post(f"/api/reviews/{review_id}/analyze")
    
    # Check results
    response = await async_client.get(f"/api/reviews/{review_id}")
    data = response.json()
    
    # Verify custom findings are included
    custom_findings = [f for f in data["findings"] if f["agent_name"] == "custom"]
    assert len(custom_findings) >= 0  # May or may not find issues
```

## Step 9: Documentation

Update `README.md` or `AGENTS.md`:

```markdown
## Custom Agent

Analyzes code for [specific aspect].

**What it finds:**
- Hook rules violations
- Missing dependencies
- Incorrect patterns

**Languages:** JavaScript, TypeScript, JSX, TSX

**Model:** Claude Sonnet 4.6

**Example findings:**
```
{
  "type": "hook_rules_violation",
  "message": "Missing dependency in useEffect hook",
  "suggestion": "Add 'userId' to dependency array"
}
```

**Enable in settings:** Check "Custom Analysis" checkbox
```

## Step 10: Deployment

1. Push code with new agent
2. Run migrations (none needed for this change)
3. Test in production: create review with custom agent selected
4. Monitor: check logs for custom agent errors

## Checklist

Before considering agent "done":

- [ ] Agent file created (backend/agents/custom_agent.py)
- [ ] Registered in orchestrator graph
- [ ] Available in API (ReviewRequest accepts "custom")
- [ ] Frontend selector shows it as option
- [ ] Unit tests pass (test_custom_agent.py)
- [ ] Integration tests pass
- [ ] Evaluation runs (measure accuracy)
- [ ] Documentation updated
- [ ] No errors in logs
- [ ] PR comment formatting includes custom findings

## Prompt Engineering Tips

**Good prompts:**
- Specific about what to find
- Examples of violations
- Clear output format (JSON)
- Language hints (comment before code)

**Bad prompts:**
- "Find issues" (too vague)
- No output format specified
- Too many concerns mixed

**Example good prompt for security:**
```
Analyze this Python code for SQL injection vulnerabilities.

Look for:
1. String interpolation in SQL: f"SELECT * WHERE id={id}"
2. Unescaped user input in queries
3. Missing parameterization

Return JSON: {"findings": [{"type": "sql_injection", "line": 42, ...}]}

Code:
...
```
