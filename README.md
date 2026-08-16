# bridge

A Claude Code marketplace hosting three independently installable plugins. Future skill series live here as additional plugins.

## Install

### Via Claude marketplace (GitHub URL)

```
/plugin install https://github.com/darkstar1227/bridge
```

### Manual

Add this repo as a marketplace in Claude Code settings, then install `bridge-dev`, `bridge-fin`, and/or `bridge-mind` independently — each is a separately installable plugin.

### Via `npx skills` (single skill, no plugin install)

Any skill in this repo can be pulled individually with [`skills`](https://github.com/vercel-labs/skills), without installing a plugin:

```
npx skills add ds-anxing/bridge --skill gstack-to-plan
npx skills add ds-anxing/bridge --all   # every skill across all three series
```

## Plugins

### [`bridge-dev`](plugins/bridge-dev/README.md) — 16 skills

Development-workflow skills, anchored by bridging [gstack](https://github.com/garrytan/gstack) reviewed plans into [Superpowers](https://github.com/obra/superpowers) `writing-plans` format, plus pipeline orchestration, autoresearch experiment loops, OpenCode model benchmarking, update-email digests, and pipeline log review.

**Requires:** [gstack](https://github.com/garrytan/gstack), [superpowers](https://github.com/obra/superpowers); [Resend](https://resend.com)/[`resend-mcp`](https://github.com/resend/resend-mcp), [`opencode`](https://opencode.ai) CLI, or [`relay`](https://github.com/darkstar1227/relay) CLI depending on which skill you use. Full list in the plugin README.

### [`bridge-fin`](plugins/bridge-fin/README.md) — 5 skills

Financial-workflow skills: configurable market/account data sources (MCP, direct HTTP, or local Python), portfolio/account reporting and DCF valuation bridged into [`anthropics/financial-services`](https://github.com/anthropics/financial-services), standalone strategy backtesting, and a shared Finnhub REST query skill.

**Requires:** at least one market/account data source (MCP connection, Finnhub API key, or `yfinance`), plus [`uv`](https://docs.astral.sh/uv/). `anthropics/financial-services` marketplace optional. Full list in the plugin README.

### [`bridge-mind`](plugins/bridge-mind/README.md) — 10 skills

Cognitive-support skills for an ESTP thinker with ADHD: decision-support skills tuned to the ESTP Se → Ti → Fe → Ni function stack (rapid prototyping, a risk/rollback checklist backed by a non-blocking hook and decision journal, a compound-learning plateau tracker, a system-design devil's-advocate pass, an outward-facing tone check), plus executive-function skills for ADHD (interrupted-work reconstruction, task activation, time-blindness guard, distraction capture, unfinished-work audit). Fully autonomous, bilingual (English/Traditional Chinese) triggering, no slash command needed.

**Requires:** nothing beyond Claude Code itself.

## License

MIT
