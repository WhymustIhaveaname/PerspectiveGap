---
id: universal_best_practice_role_and_long_context
mechanism: |
  Universal-sounding prompting cheatsheet that mixes "set a role in the
  system prompt" with "how to structure long-context inputs". Extra irony:
  the first part literally says "set a role" — a model that includes THIS
  as generic context for every sub-agent, while also dropping the scenario's
  f1 (the actual role / contest framing), is doubly wrong.
source: https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/claude-prompting-best-practices
---

Setting a role in the system prompt focuses Claude's behavior and tone for your use case. Even a single sentence makes a difference.

When working with large documents or data-rich inputs (20k+ tokens), structure your prompt carefully to get the best results:

- **Put longform data at the top:** Place your long documents and inputs near the top of your prompt, above your query, instructions, and examples. This can significantly improve performance across all models. (Note: Queries at the end can improve response quality by up to 30% in tests, especially with complex, multi-document inputs.)

- **Structure document content and metadata with XML tags:** When using multiple documents, wrap each document in `<document>` tags with `<document_content>` and `<source>` (and other metadata) subtags for clarity.

- **Ground responses in quotes:** For long document tasks, ask Claude to quote relevant parts of the documents first before carrying out its task. This helps Claude cut through the noise of the rest of the document's contents.
