# tracker - AI-Native Issue Tracking

Welcome to tracker! This repository uses **tracker** for issue tracking - a modern, AI-native tool designed to live directly in your codebase alongside your code.

## What is tracker?

tracker is issue tracking that lives in your repo, making it perfect for AI coding agents and developers who want their issues close to their code. No web UI required - everything works through the CLI and integrates seamlessly with git.

**Learn more:** [github.com/steveyegge/tracker](https://github.com/steveyegge/tracker)

## Quick Start

### Essential Commands

```bash
# Create new issues
tracker-cli create "Add user authentication"

# View all issues
tracker-cli list

# View issue details
tracker-cli show <issue-id>

# Update issue status
tracker-cli update <issue-id> --claim
tracker-cli update <issue-id> --status done

# Sync with tracker remote
tracker-cli tracker push
```

### Working with Issues

Issues in tracker are:
- **Git-native**: Stored in tracker database with version control and branching
- **AI-friendly**: CLI-first design works perfectly with AI coding agents
- **Branch-aware**: Issues can follow your branch workflow
- **Sync-ready**: Uses tracker remotes for backup and team sharing

## Why tracker?

✨ **AI-Native Design**
- Built specifically for AI-assisted development workflows
- CLI-first interface works seamlessly with AI coding agents
- No context switching to web UIs

🚀 **Developer Focused**
- Issues live in your repo, right next to your code
- Works offline, syncs when you push
- Fast, lightweight, and stays out of your way

🔧 **Git Integration**
- tracker-native sync via tracker-cli tracker push / tracker-cli tracker pull
- Branch-aware issue tracking
- tracker-native three-way merge resolution

## Get Started with tracker

Try tracker in your own projects:

```bash
# Install tracker
curl -sSL https://raw.githubusercontent.com/steveyegge/tracker/main/scripts/install.sh | bash

# Initialize in your repo
tracker-cli init

# Create your first issue
tracker-cli create "Try out tracker"
```

## Learn More

- **Documentation**: [github.com/steveyegge/tracker/docs](https://github.com/steveyegge/tracker/tree/main/docs)
- **Quick Start Guide**: Run `tracker-cli quickstart`
- **Examples**: [github.com/steveyegge/tracker/examples](https://github.com/steveyegge/tracker/tree/main/examples)

---

*tracker: Issue tracking that moves at the speed of thought* ⚡
