# Design System

## Identity

This project is an industrial product interface for equipment fault prediction and health evaluation. The visual language should feel like a serious factory reliability system: restrained, operational, traceable, and data-first. The interface may use atmospheric entry-page storytelling, but authenticated product screens must prioritize judgment speed, status clarity, and consistent controls.

## Visual Theme

The current frontend uses a dark industrial control-room theme with desaturated factory imagery, fine grid texture, muted panel surfaces, and a small high-visibility safety accent. It should not become a purple-blue AI dashboard, a game-like command center, or a marketing card wall.

Use the dark theme because the assumed scene is an operations engineer reviewing equipment health in a control room or laptop environment with dense telemetry and alert states. The dark surface reduces glare and lets risk state, online status, and system health indicators stand out.

## Color Palette

Current CSS tokens:

```css
--ink: #edf2e8;
--muted: rgba(237, 242, 232, 0.68);
--faint: rgba(237, 242, 232, 0.12);
--line: rgba(237, 242, 232, 0.18);
--amber: #d7ff62;
--rust: #c57044;
--steel: #9eb6b3;
--deep: #080b09;
--panel: rgba(17, 22, 19, 0.74);
```

Usage:

- `--deep` is the primary page background and product shell base.
- `--ink` is primary readable text.
- `--muted` is supporting text only; do not use it for important statuses or table values.
- `--amber` is reserved for primary actions, active navigation, live/online indicators, and critical visual anchors.
- `--rust` is a secondary industrial warning accent, suitable for rising risk or attention states.
- `--steel` supports neutral technical labels, diagrams, and low-priority metadata.
- `--line` and `--faint` define panel boundaries and structural separators.

Operational status colors should be semantic and text-labeled. Do not rely on color alone. Risk states should always include a readable label such as `正常`, `关注`, `高风险`, or `严重风险`.

## Typography

Primary font stack:

```css
"PingFang SC", "Microsoft YaHei", "Source Han Sans SC", "Noto Sans CJK SC", "Heiti SC", sans-serif
```

Rules:

- Chinese text must be set with practical CJK UI fonts; avoid decorative display fonts and avoid default-looking browser serif fallbacks.
- Product screens should use a compact fixed scale, not oversized fluid marketing headings.
- Landing-page hero headings may be large, but must stay readable and not wrap into cramped vertical blocks.
- Use `text-wrap: balance` for major headings and `text-wrap: pretty` for long explanatory copy.
- Body copy should stay within 65-75 characters per line where it is prose. Tables and telemetry panels may be denser.

## Layout Principles

- Entry page: cinematic but controlled, with clear sections for system purpose, runtime chain, backend capability map, and entry to the workbench.
- Product workbench: top-level shell with clear navigation, status summary, data tables, alert queues, and detail panels.
- One-screen loop is preferred: overview, device status, prediction result, warning state, and model/run status should cross-check each other.
- Use density only where it improves operational judgment. Avoid empty decorative cards.
- Use grid for true 2D information, flex for simple rows and control clusters.
- Do not nest cards inside cards. Use separators, rails, tables, split panels, or inline state rows instead.

## Components

Core component vocabulary:

- Fixed rounded top navigation for the landing page.
- Product shell navigation for the future workbench.
- Industrial panels with thin borders, dark surfaces, restrained shadows, and visible hierarchy.
- Status chips with both color and text labels.
- Dense tables for device ledger, predictions, warnings, model versions, and stream events.
- Pipeline diagrams for MQTT, Kafka, TSDB, Redis, feature windows, inference, and warning flow.
- Action buttons with clear verbs such as `启动接入`, `暂停接入`, `刷新状态`, `确认预警`, and `进入系统工作台`.

Every interactive control needs default, hover, focus, active, disabled, and loading states. Product flows should use skeletons or explicit empty states instead of fake data.

## Motion

Motion should communicate state or reveal structure. Entry-page motion may use GSAP for a controlled first impression, but product screens should stay fast and task-focused.

Rules:

- Prefer 150-250 ms transitions for product interactions.
- Use no bounce or elastic easing.
- Do not gate content visibility on animations.
- Respect `prefers-reduced-motion`.
- Use live indicators, loading transitions, row updates, and alert state changes as meaningful motion targets.

## Content Voice

The system speaks like an industrial reliability product, not a consumer AI app. Copy should name actual capabilities and boundaries:

- Good: `MQTT 到 Kafka 后台消费者`, `Raw 遥测清洗、校验与幂等`, `TSDB 点位写入与 Redis 快照`.
- Bad: `智能赋能未来工厂`, `AI 驱动全场景革新`, `展示接入`.

When a feature is simulated because no physical equipment is connected, label it as simulated source data running through the same backend chain. Do not present simulated data as real factory telemetry.

## Implementation Notes

Current frontend implementation:

- Framework: Vite + React + TypeScript.
- Entry HTML: `frontend/index.html`.
- Main app: `frontend/src/App.tsx`.
- Global styles and tokens: `frontend/src/styles.css`.
- Motion library: GSAP with ScrollTrigger.
- Icon system: Phosphor icons.

Future frontend restructuring should preserve the product strategy from `PRODUCT.md`: real data first, explain state before numbers, form a closed loop, keep useful density, and prefer stability over visual tricks.
