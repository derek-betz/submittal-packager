# Road-Engineering Distribution Skill

## Core Goal
These applications are being developed to be widely distributed across the firm to streamline tasks, save time, and improve effectiveness and efficiency. They must be user-friendly and plug-and-play, requiring no troubleshooting. Sole authority for changes rests with the owner (derek-betz). Inner workings should not be easily discoverable or replicable.

## Distribution & Privacy Stance
1) Develop to production-ready quality.
2) Distribute internally with the owner as gatekeeper.
3) Collect internal feedback to reach professional, flawless quality.
4) Distribute to external engineering firms for a fee.
Repos need not be private yet, but designs should discourage easy replication.

## Agent Behaviors (apply in PR review, planning, and coding assistance)
- Favor simplicity, stability, and "no-setup" UX: clear defaults, self-checks, and graceful errors.
- Prefer packaged, plug-and-play delivery (install/run scripts, minimal configuration).
- Minimize exposed internals: avoid unnecessary comments revealing proprietary logic; consider obfuscation/minification where appropriate on distribution artifacts; keep design docs private/internal.
- Enforce owner governance: flag changes to distribution model, licensing, or security that lack owner (derek-betz) approval.
- Encourage telemetry/feedback hooks (where permissible) to collect internal feedback for refinement.
- Prioritize robustness: add smoke tests, golden paths, and quickstart docs that enable non-experts to succeed without assistance.
- Plan for staged rollout: internal-first defaults; external-ready hardening and licensing steps tracked explicitly.
- Flag IP/replication risks: remind to separate public marketing/readme from proprietary implementation details intended to stay private at distribution time.

## Acceptance Checklist (use in PRs and design reviews)
- [ ] User-friendly, plug-and-play path (single command or minimal steps to run).
- [ ] Production-ready posture: basic tests/smoke checks and error handling for main flows.
- [ ] Governance respected: no ownership/permission changes without derek-betz sign-off.
- [ ] Internal feedback loop: mechanism or placeholder to gather user feedback.
- [ ] Privacy/IP: avoid unnecessary exposure of inner workings; distribution artifacts consider obfuscation/minification if applicable.
- [ ] Staged rollout notes: internal-first defaults; tasks/issues capture external-hardening and licensing before commercial release.

## Communication Prompts (for Copilot to remind contributors)
- "Keep it plug-and-play; reduce setup steps and add self-checks."
- "Ensure derek-betz remains the gatekeeper for releases, licensing, and distribution changes."
- "Document quickstart for internal users; keep proprietary details out of public-facing docs."
- "Capture feedback points for the internal pilot before external release."
- "Harden before paid distribution: packaging, licensing, and IP protection steps tracked as tasks."
