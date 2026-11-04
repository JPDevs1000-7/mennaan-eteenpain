# Product Spec v1.0 — Couples Daily Prompt App

Source of truth for the MVP. Merged from the v0.7 baseline and the v0.7 -> v1.0 changelog.
Items marked **[TBD]** or **[ASSUMED]** need an owner decision (see section 9).

## 1. Vision
A lightweight daily-prompt web app that helps couples talk and build a habit. One open-ended discussion prompt per day. The user marks it "Completed" after discussing it with their partner. No answers or notes are recorded.

- No registration and no end-user database.
- Progress lives in browser localStorage and moves between devices through a stateless **Magic State Link** (a GET URL).
- Content is published GitOps-style: a Super Admin uses local Python CLI tools and Git. A web CMS may come later.

## 2. User groups
| Group | Description | Interface |
|---|---|---|
| End-Users | Couples completing daily prompts and keeping streaks | Web SPA (desktop and mobile) |
| Super Admin | Creates weekly prompts, runs AI translation, publishes via Git | Terminal / Python CLI / Git |
| Regional Admins (future) | Manage country-specific overrides | Web CMS (future) |

## 3. Use cases

### End-user
**UC-1 First launch and onboarding**
1. Language is auto-detected from `navigator.language`; the user can change it (fi, en).
2. System sets `start_date` to the current local date, even late in the day (decision 9.2).
3. Day 1 prompt unlocks. UI unlock rhythm (daily vs weekly focus) is a setting, separate from content.
4. Older prompts in the global timeline are hidden and moved to a "Bonus/Practice" queue.

**UC-2 Complete a daily discussion and build streaks**
Business logic only (presentation is in section 7):
1. User marks the day's prompt "Completed".
2. System assigns a status from the timing delta between release day and completion time:
   Pending (0), Perfect (1), On Time (2), Rescued (3). Day boundaries use the device's local midnight; the On Time window ends at the end of the day after release (decisions 9.1 and 9.3).
3. Status is persisted to localStorage automatically.

**UC-3 Generate and use a State Link**
Two link types:
- **Self-Backup:** includes the optional email `e`. May be emailed or copied.
- **Partner Share:** strips `e`. Avoids third-party GDPR consent issues and makes clear it is not a database sync.

Flow:
1. User requests a link (Self-Backup optionally with an email).
2. System packs `v`, `start_date`, `lang`, optional `e`, and the history (2-bit packing) into Base64.
3. URL is `<window.location.origin>/?state=<Base64>` and always includes `v=1`.
4. Opening the link decodes the payload, restores localStorage, and resumes.

**UC-4 Domain migration (0-click)**
Old domain redirects immediately to the new domain and passes state parameters through unchanged. The app never hard-codes its origin (it uses `window.location.origin`).

**UC-5 Periodic backup nudge**
When active use passes a threshold (default 1 week) with no saved state, show a non-intrusive reminder to create a backup link.

### Admin
**UC-6 Author, translate and publish weekly content (GitOps)**
Focus is infrastructure, not authoring tools:
1. Admin runs `python manage.py new-week --week 2026-W34 --theme "Expressing Appreciation"`.
2. Admin enters 7 prompts in the primary language.
3. Script calls an AI API to translate into all supported languages.
4. Admin reviews and validates the generated JSON locally.
5. Optionally export prompts for external channels.
6. Admin commits and pushes (`git push`).
7. CI/CD triggers a build and serves the updated static JSON assets.

## 4. MVP scope
- Stateless end-user architecture (no user database).
- Open-ended prompts, no choices or correct answers.
- Git/CLI-driven publishing.
- Dynamic start date (feed is unique to the user's timeline).
- Three streak tiers (Perfect, On Time, Rescued) with neutral naming.
- State-link save and resume with schema versioning.
- Languages only (Finnish-first, plus English). No country variants.
- Static UI: same colours, fonts and logos in every language.
- One global question set, same weekly themes for everyone.

### Future (architected for, not built)
Country + language mapping (fr-CA vs fr-FR); localized UI branding; regional question sets (forking a week); delegated web CMS with RBAC.

## 5. Data model

### 5.1 Content (ISO-week based)
```json
{
  "week_id": "2026-W34",
  "theme": "Expressing Appreciation",
  "questions": [
    {
      "day_of_week": 1,
      "id": "q-2026-w34-1",
      "translations": {
        "fi": { "text": "Mikä on yksi pieni asia, jonka kumppanisi teki viime aikoina ja joka sai sinut tuntemaan itsesi todella arvostetuksi?" },
        "en": { "text": "What is one small thing your partner did recently that made you feel truly appreciated?" }
      }
    }
  ]
}
```

### 5.2 State and link format
State variables: `v` (schema version, currently 1), `e` (optional email, Self-Backup only), `startDate` (ISO, e.g. 2026-08-01), `lang` (fi, en), `history` (array of codes 0-3).

Packing:
- 4 statuses = 2 bits each, so 4 days per byte.
- Metadata plus packed history are concatenated and Base64-encoded.
- `v` makes later changes possible (for example 3-bit packing) without breaking old links. Decoders must reject or migrate unknown versions explicitly.
- **[TBD]** Whether the encoding is URL-safe Base64 (recommended) and the exact byte layout. To be pinned in the build step with test vectors.

## 6. Streak rules
| Status (FI / EN) | Code | Condition | Streak | Visual |
|---|---|---|---|---|
| Odottaa / Pending | 0 | Not yet completed | none | Grayed out / outline |
| Täydellinen / Perfect | 1 | Completed on release day | Perfect | Star icon / gold badge |
| Ajallaan / On Time | 2 | Completed within accepted window | Basic | Green check / solid line |
| Pelastettu / Rescued | 3 | Completed after accepted window | Rescued | Plus icon (+), meaning repair / first aid |

## 7. Accessibility (WCAG AAA, senior-friendly)
- Touch targets at least 48x48 px.
- Body text at least 18 px.
- High-contrast palette; low cognitive load.
- Full screen-reader support (ARIA).
- Status must never rely on colour alone (icon plus label).

## 8. Constraints and principles
- No backend and no stored end-user PII.
- Domain-agnostic: runtime origin detection only.
- Prompt content is the same for all users except translation.
- State link schema is always versioned.

## 9. Decisions
Resolved (owner-confirmed):
1. **On Time window:** release day = Perfect; the following day (until its local midnight) = On Time; later = Rescued.
2. **Late start (UC-1):** Day 1 is always the day the user first opens the app.
3. **Time zone:** day boundaries follow the user's device-local midnight.
4. **Email:** MVP is copy-to-clipboard only. The optional `e` field is carried in Self-Backup links but nothing is sent.
5. **Hosting:** repository lives on GitHub; CI is GitHub Actions. Build output must be plain static files with no host-specific features, so a move to Cloudflare Pages later is a config change only. Domain redirect (UC-4) is implemented in a host-neutral way (client-side redirect page) and may use Cloudflare redirect rules later.

6. **Stack:** vanilla HTML/CSS/JS, no build step, no npm dependencies. Can move to Vite + TypeScript later if needed.

Resolved by the builder (implemented and tested; owner may overrule):
7. **State payload:** URL-safe Base64 without padding; byte layout documented at the top of `js/codec.js` and pinned by test vectors in `tests/logic.test.js`. Link is `?v=1&state=...`.
8. **Streak tiers are nested:** Perfect streak = consecutive Perfect days; Basic streak = consecutive Perfect or On Time days; Rescued streak = consecutive completed days of any kind (a Rescued day keeps it alive). An unfinished today does not break a current streak.
9. **Question timeline:** all published weeks form one ordered sequence. A user's Day 1 is the first question of the ISO week containing their start date (keeps weekly themes intact); Day i is released on start date + i. Earlier questions form the Bonus queue. If a user catches up to the end of published content, they see a "coming soon" message.
10. **Links on project hosting:** links are built from `location.origin + location.pathname`, so they also work when the app lives under a sub-path such as GitHub Pages `/repo/`.
11. **Finnish text:** the sample Finnish prompts and UI strings were written by the AI builder and should be reviewed by a native speaker.

12. **Approver:** for now the project owner is the single human approver for every feature before it reaches production. The process must name the approver in one config place so it can change later.

Still open: none.

## 10. Changes made while merging
- Renumbered use cases to match the v1.0 changelog (domain migration = UC-4, backup nudge = UC-5, admin workflow = UC-6). The v0.7 body had the admin workflow as UC-4.
- Rescued symbol changed from "patch icon" to Plus (+).
- Section 9 decisions were not settled in either source; they were confirmed by the owner after the merge.
