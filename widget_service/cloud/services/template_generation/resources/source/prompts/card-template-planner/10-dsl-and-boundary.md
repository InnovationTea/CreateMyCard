---
promptGroup: card-template-planner
fragmentId: dsl-and-boundary
order: 10
promptVersion: card-plan-template-prompt/0.3
protocolVersion: card-plan-template/0.2
contractVersion: card-plan-template-context/0.2
---

<!-- prompt:start -->
Output schema:
{"themeId":"theme-profile","requestTemplate":["card@1","template-id@version"]}

Rules:
- Use strict JSON with double-quoted keys and strings. Do not append a semicolon.
- themeId must be one supplied Theme ID.
- requestTemplate must contain unique supplied Template IDs and must include card@1.
- Choose only Template capabilities relevant to the request and available data. Template sizes are descriptions for the second layer, not values selected here.
- When requiredSelection is present, copy its themeId and requestTemplate exactly.
- Do not emit Header, title, icon, Action, Button, Slot, Region, component trees, Template calls, parameters, capability IDs, event arguments, Data Paths, A2UI, Markdown, comments, code fences, explanations, or arbitrary calls.
<!-- prompt:end -->
