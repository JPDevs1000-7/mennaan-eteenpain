# Daily Together

A lightweight web app that gives couples one open-ended question a day to talk about. There are no accounts and no database: progress stays on the device and can be moved with a "Magic State Link".

- Live: https://jpdevs1000-7.github.io/mennaan-eteenpain/
- Product spec (source of truth): [`docs/product-spec.md`](docs/product-spec.md)
- Rules for anyone changing the code, human or AI: [`CLAUDE.md`](CLAUDE.md)

## Run it locally
```
python -m http.server 8080      # then open http://localhost:8080
```
No install or build step is needed.

## Check your changes
```
python tools/run_checks.py      # JS tests, Python tests, content validation, guardrails
```

## Add a week of prompts
```
python manage.py new-week --week 2026-W47 --theme "Kiitollisuus"   # theme and prompts in Finnish
python manage.py validate
```
Set `ANTHROPIC_API_KEY` to translate automatically; otherwise placeholders are written and validation fails until they are replaced.

## How changes reach production
`main` is protected: every change goes through a pull request, and the `test` check must pass before merging. Merging to `main` deploys to GitHub Pages automatically.
