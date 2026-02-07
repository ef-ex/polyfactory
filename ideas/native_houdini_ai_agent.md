# Native Houdini AI Agent - Architecture Design

**Date:** January 28, 2026  
**Status:** Concept / Future Implementation  
**Effort Estimate:** 2-3 months for production-ready version

## Concept Overview

A native Houdini Python panel that integrates LLM APIs directly, enabling AI-assisted procedural modeling with tight feedback loops and immediate geometry introspection - no WebSocket bridge overhead.

## Key Advantage Over WebSocket Bridge

Direct Python API access with <10ms operations instead of 200-500ms network roundtrips. Agent can introspect scene state, geometry data, and viewport instantly without serialization.

## Core Components

### 1. Houdini Python Panel (PySide6 UI)
- Chat interface for user requests
- Status display (current task, iteration count, geometry stats)
- Viewport reference widget (optional embedded viewer)
- Token/cost tracking display
- Iteration history with undo support

### 2. LLM Integration Layer
- API client (OpenAI/Anthropic) with request/response handling
- Streaming support for real-time feedback
- Token/cost tracking
- Context window management (compress old messages, prioritize recent)
- Rate limiting and error handling
- **No custom training required** - uses existing APIs via HTTP

### 3. Scene Context Extractor
- Current node selection
- Network hierarchy (parent context, siblings)
- Geometry statistics (point/prim counts, bounds, attributes)
- Parameter states
- Available node types in context
- Smart compression: only send relevant subgraph to LLM

### 4. Code Executor
- Safe `exec()` wrapper with error capture
- Stdout/stderr redirection
- Undo block management: `with hou.undos.group("AI Agent Iteration")`
- Execution history for debugging
- Timeout protection for infinite loops

### 5. Feedback Analyzer
- Geometry diff (before/after comparison)
- Error parser (extract meaningful info from hou exceptions)
- Success heuristics ("did we create expected geometry?")
- Viewport state capture (camera, display flags, selection)
- Semantic scene understanding: "4 tube primitives arranged radially, gaps at joints"

## Implementation Phases

### Phase 1: Basic Integration (1-2 weeks)
- Create Python panel with text input/output
- Implement LLM API client (start with OpenAI, it's simpler)
- Basic code generation: "user request → code → execute → show result"
- No iteration yet, just single-shot execution
- Basic error display

**Deliverable:** Chat panel that generates and executes Houdini Python code

### Phase 2: Scene Awareness (1 week)
- Extract current selection/context automatically
- Build scene state summary for LLM context
- Add geometry introspection (point counts, bounds, etc.)
- Template system: "Given context X, generate code for Y"
- Parameter inspection for selected nodes

**Deliverable:** Context-aware code generation based on current scene state

### Phase 3: Feedback Loop (2-3 weeks)
- Before/after geometry comparison
- Parse Houdini exceptions into LLM-friendly descriptions
- Retry logic: if error → send error + original request → new code → retry
- Iteration limit (max 5 attempts before asking user)
- Progress display during multi-step operations

**Deliverable:** Self-correcting agent that can recover from errors

### Phase 4: Visual Understanding (2-4 weeks, optional)
- Viewport capture via `hou.SceneViewer.flipbookToClipboard()` or render to texture
- Vision model integration (GPT-4V or Claude with vision)
- Semantic analysis: "Are points connected? Do beams align?"
- **Note:** May not add much value vs geometry queries, most complex phase

**Deliverable:** Agent can analyze viewport renders for visual validation

### Phase 5: Learning/Memory (1-2 weeks)
- Save successful code patterns to local database (JSON/SQLite)
- Pattern matching: "You've built chassis modules 5 times, here's the pattern..."
- User preference learning (naming conventions, node organization)
- Project-specific context (module specs, connection point rules)
- **Note:** This is application-level caching, NOT neural network training

**Deliverable:** Agent learns project-specific patterns and improves over time

## Key Technical Challenges

### 1. Context Window Management
**Problem:** Scene state can be huge (thousands of nodes)
- Need smart compression: only send relevant subgraph
- Balance: too little context = bad code, too much = token waste
- Typical scene: 500-1000 nodes, but only 10-20 relevant for current task

**Solution:** 
- Extract only selected node + siblings + parent context
- Summarize geometry stats instead of full attribute data
- Use conversation history compression after 5-10 iterations

### 2. Error Recovery
**Problem:** Houdini exceptions are verbose and technical
- Raw exception: "TypeError: 'NoneType' object is not callable at line 47..."
- Need to extract: "add node has no geometry because usept0 not set correctly"

**Solution:**
- Parse common error patterns
- Add geometry state snapshot at failure point
- Provide LLM with: error message + scene state + original intent
- Limit retries to avoid infinite loops

### 3. Undo/Redo Integration
**Problem:** Each iteration modifies scene, user may want to undo
- Agent makes 5 attempts, creates 20 nodes
- User wants "undo all AI changes" in one step

**Solution:**
```python
with hou.undos.group("AI Agent: Create Chassis"):
    for attempt in range(max_iterations):
        # ... agent code execution
        if success:
            break
# Single undo reverts all attempts
```

### 4. Cost Control
**Problem:** Each iteration = API call
- GPT-4: ~$0.01-0.10 per request (depending on context size)
- Complex task: 10-20 iterations = $0.10-2.00
- Monthly usage: $20-200 for active development

**Solution:**
- Display running cost in UI
- Budget limits (warn at $5, stop at $10)
- Use cheaper models for simple tasks (GPT-3.5 for parameter tweaks)
- Cache repeated queries

### 5. Latency
**Problem:** API calls are 1-3 seconds
- UI freeze is unacceptable
- Need progress feedback

**Solution:**
- Async execution with `QThread` or `asyncio`
- Progress display: "Analyzing geometry... Generating code... Executing..."
- Streaming API for real-time response (see partial code as it generates)
- Allow cancellation mid-operation

## Comparison: WebSocket Bridge vs Native Agent

| Aspect | WebSocket Bridge | Native Agent |
|--------|-----------------|--------------|
| **Latency** | 200-500ms per command | <10ms (no serialization) |
| **Geometry Access** | Text queries only | Direct `geo.points()` inspection |
| **Iteration Speed** | Slow (network + AI thinking) | Fast (AI thinking only) |
| **Context Awareness** | Agent must ask for context | Auto-extracted every iteration |
| **Visual Feedback** | Screenshots (manual) | Could capture programmatically |
| **Integration** | External tool | Native Houdini panel |
| **Setup Complexity** | Server + client | Single Python panel |
| **Error Handling** | Manual debugging | Automatic retry loops |

## Code Structure Example

```python
# polyfactory/python_panels/ai_agent.py

from PySide6 import QtWidgets, QtCore
import hou
import anthropic  # or openai

class HoudiniAIAgent(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.client = anthropic.Anthropic(api_key="...")
        self.conversation_history = []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Chat display
        self.chat_display = QtWidgets.QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)
        
        # Input
        self.input_field = QtWidgets.QLineEdit()
        self.input_field.returnPressed.connect(self.on_submit)
        layout.addWidget(self.input_field)
        
        # Status
        self.status_label = QtWidgets.QLabel("Ready")
        layout.addWidget(self.status_label)
    
    def get_scene_context(self):
        """Extract relevant scene state for LLM context"""
        selection = hou.selectedNodes()
        if not selection:
            return {"selection": None, "context": "/obj"}
        
        node = selection[0]
        context = {
            "path": node.path(),
            "type": node.type().name(),
            "parent": node.parent().path(),
            "siblings": [n.name() for n in node.parent().children()],
        }
        
        # Add geometry stats if SOP
        if node.type().category().name() == "Sop":
            try:
                geo = node.geometry()
                context["geometry"] = {
                    "points": len(geo.points()),
                    "prims": len(geo.prims()),
                    "bounds": geo.boundingBox().sizevec(),
                }
            except:
                context["geometry"] = "No geometry"
        
        return context
    
    def execute_with_feedback(self, user_request, max_iterations=5):
        """Execute request with automatic error recovery"""
        scene_context = self.get_scene_context()
        
        for iteration in range(max_iterations):
            self.status_label.setText(f"Iteration {iteration + 1}/{max_iterations}")
            
            # Build prompt with context
            prompt = self.build_prompt(user_request, scene_context, iteration)
            
            # Call LLM
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            
            code = self.extract_code(response.content[0].text)
            
            # Execute with error capture
            with hou.undos.group(f"AI Agent: {user_request[:50]}"):
                success, result = self.safe_execute(code)
            
            if success:
                self.chat_display.append(f"✓ Success: {result}")
                return True
            else:
                # Update context with error for next iteration
                scene_context["last_error"] = result
                self.chat_display.append(f"✗ Attempt {iteration + 1} failed: {result}")
        
        self.chat_display.append("⚠ Max iterations reached")
        return False
    
    def safe_execute(self, code):
        """Execute code with error capture"""
        try:
            exec_globals = {"hou": hou}
            exec(code, exec_globals)
            
            # Analyze result
            result = self.analyze_geometry_changes()
            return True, result
        except Exception as e:
            return False, str(e)
    
    def analyze_geometry_changes(self):
        """Check what changed in the scene"""
        selection = hou.selectedNodes()
        if selection:
            node = selection[0]
            geo = node.geometry()
            return f"Created {len(geo.points())} points, {len(geo.prims())} prims"
        return "Scene modified"
    
    def build_prompt(self, request, context, iteration):
        """Build LLM prompt with scene context"""
        prompt = f"""You are a Houdini Python expert. Generate code to: {request}

Current scene context:
{context}

Iteration: {iteration + 1}

Generate Python code using the `hou` module. Be precise and test edge cases.
"""
        if "last_error" in context:
            prompt += f"\n\nPrevious attempt failed with: {context['last_error']}\nFix the error and try again."
        
        return prompt

def createInterface():
    """Called by Houdini to create panel"""
    return HoudiniAIAgent()
```

## Pattern Learning Example

```python
# Application-level pattern storage (NOT neural network training)

patterns_db = {
    "create_tube": {
        "code": "tube = node.createNode('tube'); tube.parm('rad').set((r, r)); tube.parm('height').set(h)",
        "context": "Creating cylindrical geometry",
        "success_count": 15
    },
    "resample_curve": {
        "code": "resample = node.createNode('resample'); resample.parm('length').set(seg_length)",
        "context": "Resampling curves",
        "success_count": 8
    },
    # Saved to JSON/SQLite, used as examples in LLM prompts
}

# When user requests "create a tube", inject successful pattern into prompt:
prompt = f"""
Previous successful pattern for creating tubes:
{patterns_db["create_tube"]["code"]}

Now create a tube with radius {radius} and height {height}.
"""
```

## Realistic Effort Estimate

- **Minimum viable version**: 2-3 weeks (chat + LLM + basic execution)
- **Production-ready**: 2-3 months (feedback loops, error handling, polish)
- **Advanced (with vision)**: 4-6 months

## Cost Analysis

### Development Costs
- **Time:** 2-3 months full-time (or 6-12 months part-time)
- **API Keys:** Free tier for testing, $20-50/month during development
- **No GPU/infrastructure costs** - all hosted API calls

### Operational Costs
- **Light usage:** $5-20/month (occasional modeling tasks)
- **Active development:** $50-200/month (daily use, complex iterations)
- **Per task:** $0.01-2.00 depending on complexity and iterations

### Cost Optimization
- Use GPT-3.5 for simple tasks ($0.001/request vs $0.01)
- Cache repeated geometry queries
- Limit context window to relevant nodes only
- Implement token budgets per task

## Fundamental Limitation

Even with perfect implementation, **procedural modeling is hard to do blind**. The feedback loop helps, but complex geometry realistically needs 5-15 iterations:
- **Time per task:** 5-45 seconds (even with low latency)
- **API cost per task:** $0.05-1.50
- **Still requires user validation:** "Does it look right?"

## Best Use Cases

Where this agent would excel:
- **Parametric tasks:** "Add control points to this curve at X intervals"
- **Batch operations:** "Apply material to all tubes in scene"
- **Topology optimization:** "Reduce poly count by 50% preserving detail"
- **Attribute manipulation:** "Set color based on height, red at top, blue at bottom"
- **Repetitive workflows:** "Copy this setup, adjust parameters, merge results"

Where it would struggle:
- **Full blind modeling:** "Create entire spaceship chassis from scratch"
- **Aesthetic decisions:** "Make it look cooler"
- **Organic modeling:** Freeform surfaces without mathematical definition
- **One-shot perfection:** Complex geometry requiring immediate correctness

## Next Steps (When Ready to Implement)

1. **Proof of Concept** (1 week)
   - Basic Python panel with OpenAI API integration
   - Single-shot code execution (no iteration)
   - Validate API costs and latency

2. **Scene Context Extraction** (3-5 days)
   - Implement `get_scene_context()` with geometry introspection
   - Test context compression strategies
   - Measure token usage

3. **Feedback Loop MVP** (1-2 weeks)
   - Add error parsing and retry logic
   - Implement undo grouping
   - Test on simple tasks (create primitives, set parameters)

4. **Production Polish** (4-6 weeks)
   - UI improvements (progress, history, cost tracking)
   - Pattern learning database
   - Error recovery edge cases
   - Documentation and examples

5. **Advanced Features** (optional, 4-8 weeks)
   - Viewport capture and vision model integration
   - Multi-step planning (break complex tasks into subtasks)
   - Collaborative mode (agent suggests, user approves each step)

## Resources & References

### APIs
- **Anthropic Claude:** https://docs.anthropic.com/claude/reference/getting-started-with-the-api
- **OpenAI GPT-4:** https://platform.openai.com/docs/api-reference
- **Pricing:** Claude ~$0.003/1K tokens input, $0.015/1K output; GPT-4 ~$0.01/1K input, $0.03/1K output

### Houdini APIs
- **Python:** `$HFS/houdini/python3.11libs/hou.py` (full API documentation)
- **Scene Viewer:** `hou.SceneViewer` for viewport interaction
- **Geometry:** `hou.Geometry` for point/prim introspection
- **Undo:** `hou.undos.group()` for undo block management

### Similar Projects
- **GitHub Copilot in Houdini:** Similar concept, but for code completion not task execution
- **Houdini Script SOPs:** Node-level Python execution (agent could generate these)
- **PDG Task Graphs:** Could be used for complex multi-step agent workflows

## Conclusion

This is a **feasible but ambitious project** requiring 2-3 months of focused development. No ML/training expertise needed - pure software engineering using existing LLM APIs.

Key advantages over WebSocket bridge:
- 20-50x lower latency
- Direct geometry introspection
- Automatic context awareness
- Tighter iteration loops

However, even with perfect implementation, blind procedural modeling remains fundamentally challenging. Agent works best for parametric tasks, batch operations, and iterative refinement rather than full creative modeling from scratch.

**Recommendation:** Consider hybrid workflow where agent handles tedious/repetitive work while human guides creative decisions and validates results visually.
