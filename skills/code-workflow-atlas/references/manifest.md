# Manifest version 1

Use UTF-8 JSON. The agent traces code and writes the semantic map; the builder captures evidence and renders it. It does not infer call graphs or call an LLM.

```json
{
  "version": 1,
  "title": "Request to output",
  "subtitle": "Select a stage to inspect it.",
  "baseline": "Inspected repository and revision",
  "phases": [
    {"id": "read", "label": "Read", "nodes": ["read"]},
    {"id": "work", "label": "Work", "nodes": ["reuse", "generate"]},
    {"id": "end", "label": "Return", "nodes": ["end"]}
  ],
  "nodes": [
    {"id": "read", "title": "Read input", "kind": "program", "summary": "Validate the request",
     "inputs": ["Request"], "steps": [{"title": "Validate", "detail": "Check required fields."}],
     "outputs": ["Valid request"], "sourceIds": ["entry"], "promptIds": []},
    {"id": "reuse", "title": "Reuse output", "sourceIds": ["entry"]},
    {"id": "generate", "title": "Generate output", "sourceIds": ["entry"]},
    {"id": "end", "title": "Return output", "sourceIds": ["entry"]}
  ],
  "edges": [
    {"from": "read", "to": "reuse", "label": "cache hit"},
    {"from": "read", "to": "generate", "label": "cache miss"},
    {"from": "reuse", "to": "end"}, {"from": "generate", "to": "end"}
  ],
  "sources": [
    {"id": "entry", "path": "src/pipeline.py", "start": 1, "end": 40, "ref": "HEAD",
     "annotations": [{"line": 12, "text": "A cache hit returns early."}]}
  ],
  "prompts": []
}
```

The example path/range above must be replaced with actual evidence. Paths use `/` and are repository-relative; absolute paths, traversal, and escaping symlinks are rejected.

## Sources

- `start` / `end`: inclusive one-based original file lines. Annotations use those numbers.
- `ref`: optional Git reference, preferably immutable commit. Omit it to read the working copy. Resolved revision, excerpt text, and SHA-256 are embedded in the result.
- `url`: optional verified HTTP(S) source link. Never guess an upstream URL or publish local machine paths.
- `title`: optional readable source label.
- Supplied text: use `text` instead of `path`, optionally `start`. It is labeled `provided-excerpt`, not verified Git source.
- A node without `sourceIds` needs `evidenceStatus: "inferred"` and an explanation of the uncertainty.

## Nodes and comparisons

`inputs`, `outputs`, `steps`, `sourceIds`, and `promptIds` are arrays. `kind` is a short role such as `program`, `model`, or `tts`.

For comparison, add top-level `comparison: {"title":"Reference", "baseline":"Pinned version"}` and a `compare` node-ID array to each corresponding phase. Declare those nodes and their edges too. Each node belongs to one phase/lane; a phase supports up to three nodes per lane. Add phases or another focused diagram instead of crowding the overview.

An optional node `comparison` object has strings `same`, `different`, `possibleImpact`, and `evidence`. Possible impact is visibly labeled as a hypothesis.

## Prompts

```json
{
  "id": "explain", "title": "Explain a page", "provenance": "repository-template",
  "sourceIds": ["system-template", "user-template"],
  "system": "Explain actual content. {{snippet:format}}",
  "user": "Title: {{title}}\nContent: {{content}}",
  "parameters": {"title":"Example", "content":"Provided example"},
  "assembly": {
    "syntax":"mustache-basic", "snippets":{"format":"Return a JSON array."},
    "systemAppend":"", "userAppend":"",
    "label":"Illustrative parameters; not a production request capture."
  },
  "outputExample": [{"type":"text", "content":"Illustrative response."}]
}
```

Without `assembly`, only raw templates, parameters, and examples are shown. `mustache-basic` expands snippets, handles non-nested `if` blocks, replaces variables, and appends rules. Missing values, unbalanced/nested conditionals, and unresolved placeholders fail the build. Use it only when it matches the source engine. A provided template without repository evidence uses `provided-template` or `illustrative` provenance.

Template source IDs must refer to the actual template excerpts. Explain additional runtime rules and response parsing in the node or annotations. Clearly label examples rather than presenting them as actual model returns.
