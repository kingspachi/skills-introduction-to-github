# CLAUDE.md — Introduction to GitHub Skills Course

## Repository Purpose

This is a **GitHub Skills template repository** for the "Introduction to GitHub" course. It teaches learners the core GitHub workflow — branching, committing, pull requests, and merging — through a hands-on, step-by-step exercise driven entirely by GitHub Actions.

When a learner creates their own repository from this template, the course walks them through four steps automatically tracked by GitHub Actions workflows.

---

## Repository Structure

```
.
├── README.md                        # Learner-facing course content (auto-updated per step)
├── LICENSE                          # MIT license
├── .gitignore                       # Standard ignores (binaries, archives, OS files, logs)
├── images/                          # Screenshots referenced in course instructions
│   ├── code-tab.png
│   ├── main-branch-dropdown.png
│   ├── create-branch-button.png
│   ├── create-new-file.png
│   ├── my-profile-file.png
│   ├── commit-full-screen.png
│   ├── compare-and-pull-request.png
│   ├── pull-request-branches.png
│   ├── Pull-request-description.png
│   ├── Actions-to-step-4.png
│   ├── Green-merge-pull-request.png
│   ├── delete-branch.png
│   └── profile-readme-example.png
├── .github/
│   ├── dependabot.yml               # Monthly GitHub Actions dependency updates
│   ├── steps/                       # Step content fragments injected into README.md
│   │   ├── -step.txt                # Current step tracker (contains a single integer: 0–4 or "X")
│   │   ├── 0-welcome.md
│   │   ├── 1-create-a-branch.md
│   │   ├── 2-commit-a-file.md
│   │   ├── 3-open-a-pull-request.md
│   │   ├── 4-merge-your-pull-request.md
│   │   └── X-finish.md
│   └── workflows/
│       ├── 0-welcome.yml            # Triggers on push to main; initialises step 1
│       ├── 1-create-a-branch.yml    # Triggers on branch creation; advances to step 2
│       ├── 2-commit-a-file.yml      # Triggers on push to my-first-branch; advances to step 3
│       ├── 3-open-a-pull-request.yml# Triggers on PR open/reopen; advances to step 4
│       └── 4-merge-your-pull-request.yml # Triggers on push to main; advances to step X (finish)
```

---

## Course Flow

The course progresses through numbered steps. The current step is stored in `.github/steps/-step.txt`.

| Step | File | Trigger | Action |
|------|------|---------|--------|
| 0 | `0-welcome.yml` | Push to `main` | Initialises README to show Step 1 |
| 1 | `1-create-a-branch.yml` | Branch named `my-first-branch` created | Advances README to Step 2 |
| 2 | `2-commit-a-file.yml` | Push to `my-first-branch` | Advances README to Step 3 |
| 3 | `3-open-a-pull-request.yml` | PR opened/reopened from `my-first-branch` | Advances README to Step 4 |
| 4 | `4-merge-your-pull-request.yml` | Push to `main` (after merge) | Advances README to Step X (finish) |

### Branch naming is enforced
- The learner **must** name their branch exactly `my-first-branch`. Workflows check `github.ref_name == 'my-first-branch'` before running.
- The learner **must** commit a file named `PROFILE.md` to that branch.
- The PR **must** target `main` and come from `my-first-branch`.

---

## Step Advancement Mechanism

All step transitions use the `skills/action-update-step@v2` GitHub Action, which:
1. Reads `.github/steps/-step.txt` to confirm the current step.
2. Replaces the step content block in `README.md` with the next step's content from `.github/steps/`.
3. Writes the new step number to `.github/steps/-step.txt`.
4. Commits and pushes those changes.

Every workflow has a `get_current_step` job that gates the main job — it only runs when the step in `-step.txt` matches the expected value. This prevents workflows from firing out of order.

---

## GitHub Actions Conventions

- All workflows use `runs-on: ubuntu-latest`.
- All workflows require `contents: write` permission (to update README and step file).
- Workflows are triggered by both `workflow_dispatch` (manual) and their specific event.
- Checkout steps use `fetch-depth: 0` to get full branch history.
- The template repository itself is excluded from triggering course logic via `!github.event.repository.is_template`.

---

## Key Files to Know

| File | Role |
|------|------|
| `README.md` | The live learner-facing instructions. **Do not edit manually** in normal course operation — content is managed by `skills/action-update-step@v2`. |
| `.github/steps/-step.txt` | Single integer (or `X`) tracking which step the learner is on. Editing this directly will cause the next workflow to skip or misfire. |
| `.github/steps/*.md` | Source content for each course step. Safe to edit to update course copy. |
| `images/` | Static screenshots. File names are referenced directly in step `.md` files. Renaming an image requires updating all references. |

---

## Development Workflow

The active development branch is `claude/add-claude-documentation-cEFfz`. All changes should be developed there and pushed with:

```bash
git push -u origin claude/add-claude-documentation-cEFfz
```

The `main` branch is the production branch that learners fork from. **Do not push directly to `main`** unless intentionally publishing a new course version.

### Editing course content

To update step instructions:
1. Edit the relevant file in `.github/steps/` (e.g., `2-commit-a-file.md`).
2. `README.md` will reflect the new content the next time `action-update-step` runs for that step, or manually update the matching section in `README.md` for consistency.

To add or replace images:
1. Place the new image in `images/`.
2. Update the `![]()` reference in the relevant `.github/steps/*.md` file.

### Dependabot

`dependabot.yml` runs monthly to keep GitHub Actions pinned versions current (`actions/checkout`, `skills/action-update-step`, etc.).

---

## No Build System

This repository has no build system, package manager, test suite, or linter. There is no `package.json`, `Makefile`, or CI test job. The only automation is the GitHub Actions course-progression workflows described above.
