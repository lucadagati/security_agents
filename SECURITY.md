# Security notes

- Never commit `.env`. It may contain Ollama URLs, Telegram bot tokens, and DB DSNs.
- If Telegram bot tokens or SSH passwords were shared in chat, **rotate them**:
  - Telegram: [@BotFather](https://t.me/BotFather) → revoke/regenerate token for `@L40unimebot`
  - SSH: change the `ml` account password on the L40 host
- Experiment outputs under `runs/` are gitignored (may contain model prompts / trajectories).
