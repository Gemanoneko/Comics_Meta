# Comics Meta Organizer — Backlog

Items Sergei has approved for a future version. Not started unless marked.

## Next version

### False "GPU release could not be confirmed" when Ollama is off (Sergei, 2026-10-24)
- **Seen in:** v0.3.0, while paused. The banner reads "Workers paused, but Gemma GPU release could not be confirmed. Retrying." It never clears.
- **Cause (Jane's read, not yet confirmed by Ender):** `pause_control.unload_model()` asks Ollama to unload Gemma. With Ollama not running, the request fails, and `checkpoint()` turns any exception into this error ([pause_control.py:184-188](../pause_control.py)). It retries about every 10 s, and every retry fails the same way.
- **Wanted (Sergei):** if Ollama isn't running, count that as "GPU released". No false alarm.
- **Also check (Sergei's question):** what the app does when it is resumed with Ollama off. Sergei resumed on 2026-10-24 and couldn't tell what the app was doing. The app never starts Ollama itself. `local_model.available()` returns False, and credits reading returns None when the model call fails. Find out whether Gemma-dependent comics get skipped, retried later or marked as failed, and whether the dashboard should say "Ollama not running".
- **Owner:** Ender (fix). Judy reviews any new dashboard wording. Futaba verifies.

### App starts and stops Ollama itself (Sergei, 2026-10-24)
- **Wanted (Sergei):** the app starts Ollama when it needs Gemma and stops it again. Sergei shouldn't have to start Ollama by hand.
- **Stop timing (Sergei):** stop Ollama when the app quits. Pausing doesn't stop Ollama; it only unloads Gemma, as today.
- **Stops it even if Sergei started it (Sergei):** on quit, the app stops Ollama even if Sergei started Ollama himself.
- **Owner:** Ender. Judy reviews any status wording. Futaba verifies. Our tooling never steals focus (ProcessRules § Desktop App / GUI Rules), so Ollama has to start hidden.
