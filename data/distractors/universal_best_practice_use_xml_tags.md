---
id: universal_best_practice_use_xml_tags
mechanism: |
  Universal-sounding prompt-engineering hygiene that looks like onboarding
  every agent should include. About using XML tags to structure prompts —
  high-level "good practice" with no bearing on any specific role's task.
source: https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/claude-prompting-best-practices
---

XML tags help Claude parse complex prompts unambiguously, especially when your prompt mixes instructions, context, examples, and variable inputs. Wrapping each type of content in its own tag (e.g. `<instructions>`, `<context>`, `<input>`) reduces misinterpretation.

Best practices:
- Use consistent, descriptive tag names across your prompts.
- Nest tags when content has a natural hierarchy (documents inside `<documents>`, each inside `<document index="n">`).
