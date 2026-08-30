# Writing Style Router

An on-demand writing prompt plugin for MaiBot. It hooks into `maisaka.replyer.before_request` and appends style guidance only when the current request clearly asks for creative writing or text review.

## Features

- No writing prompt injection for normal chat, technical questions, or casual group replies.
- No additional model call and no copying of the full chat context.
- Composable routing for modern conversational prose, comedy web fiction, Japanese ACG light novels, anti-cliche editing, lifelike characterization, and text review.
- MaiBot-unknown macros, variables, and hidden chain-of-thought instructions have been removed.
- The default documentation is the Chinese [README.md](README.md).

## Automatic routing

Writing, continuation, rewriting, polishing, expansion, novel, style example, and similar requests enter writing mode.

Review, critique, “look at this passage”, style analysis, and similar requests enter review mode. Review mode uses an editor perspective and does not turn the response into roleplay.

Comedy web style is added only when the user explicitly requests comedy web fiction, meme-heavy language, internet style, or comic contrast. Japanese ACG style is added only for explicit requests such as light novel, Japanese style, ACG, anime, manga-like pacing, or waterfall formatting.

Casually mentioning a character, a meme, or modern language is not enough to trigger the plugin.

## Style policy

Writing requests default to modern conversational prose, anti-cliche editing, and lifelike characterization. Explicit style requests add the matching style rules. Review requests use review, anti-cliche, and lifelike-character rules.

The rules prioritize natural dialogue, concrete characterization, readable pacing, and evidence-based description. They discourage mechanical meme stacking, generic emotion labels, repetitive stock gestures, unnecessary professional jargon, and prompt leakage. ACG symbols, inner monologue, and waterfall formatting are opt-in.

## Configuration

See [config.toml](config.toml):

- `plugin.enabled`: global enable switch.
- `routing.max_prompt_characters`: maximum size of the injected prompt; default is `5200`.
- `styles.*`: enable or disable individual style groups.

The plugin preserves the existing `extra_prompt` and appends its route result, so it can work alongside character-memory and other prompt-injection plugins.

## Installation

Copy the complete `writing_style_router` directory into MaiBot's `plugins` directory, keep `plugin.enabled = true`, and restart MaiBot. No additional command is required after the plugin loads.

## License

MIT
