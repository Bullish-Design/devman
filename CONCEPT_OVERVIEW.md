# Devman Development Manager

## Overview

Devman is a system daemon for reactive template-based development, providing automatic template instantiation through filesystem monitoring.

**Foundation Stack:**
- Copier (template engine)
- Watchdog (filesystem monitoring)
- Jujutsu (version control)

## Core Concept

Devman enables a three-tier repository architecture where templates, instances, and projects each maintain full independence while staying connected through symlinks.

### Three-Layer Repository Model

1. **Base Templates**: Master template repos (jj/git) with workspace capability
2. **Instance Store**: Each instantiation creates an independent jj repo
3. **Project Repos**: Main development with symlinks to instance outputs

### System Components

- **Devman Process**: System daemon for commands & orchestration
- **Watchdog**: Filesystem monitoring via glob pattern configuration
- **Instance Lifecycle**: Template → copier generate → new jj repo → symlink replacement

## Workflow

1. Developer creates file/folder matching glob pattern
2. Watchdog triggers Devman
3. Copier instantiates from base template into store location
4. New jj repo initialized for instance
5. Original file/folder replaced with symlink to instance output
6. Instance evolves independently with full jj capabilities

## Architecture Diagram
```
┌──────────────────────────────────────────────────────────────────┐
│           DEVMAN THREE-TIER REPOSITORY ARCHITECTURE              │
└──────────────────────────────────────────────────────────────────┘

TIER 1: BASE TEMPLATE REPOS
════════════════════════════
    ~/devman/templates/python-module/     (jj/git repo)
    ├── copier.yml
    ├── template/
    └── .jj/workspaces/
        └── experimental/    ◄── template evolution workspaces

    ~/devman/templates/service-layer/     (jj/git repo)
    ├── copier.yml
    └── ...

TIER 2: INSTANCE STORE (each = independent jj repo)
════════════════════════════════════════════════════
    ~/devman/instances/
    ├── my-app-auth-module/              (jj repo)
    │   ├── .devman/
    │   │   ├── automations/
    │   │   └── workflows/
    │   ├── output/          ◄── symlink target
    │   └── .jj/workspaces/
    │       └── refactor/    ◄── instance-specific workspaces
    │
    ├── my-app-user-module/              (jj repo)
    │   ├── .devman/
    │   ├── output/
    │   └── .jj/workspaces/
    │
    └── other-app-payments/              (jj repo)
        └── ...

TIER 3: PROJECT REPOS (main development)
═════════════════════════════════════════
    ~/projects/my-app/                   (jj repo)
    ├── src/
    │   └── modules/
    │       ├── auth/ ────────┐ symlink
    │       └── user/ ────────┤ symlink
    ├── tests/               │
    └── pyproject.toml       │
                             │
                ┌────────────┴──────────────┐
                ▼                           ▼
    ~/devman/instances/         ~/devman/instances/
        my-app-auth-module/         my-app-user-module/
            output/                     output/
```

## Event Flow
```
devman.yml (glob config):
  - pattern: "src/modules/*/"
    template: "python-module"

Event Flow:
═══════════
1. Developer: mkdir src/modules/auth
   
2. Watchdog: Match detected!
   
3. Devman:
   ├─ Copier: ~/devman/templates/python-module 
   │          → ~/devman/instances/my-app-auth-module/
   ├─ Init jj repo in instance
   └─ Replace src/modules/auth/ with symlink

4. Result: Independent evolution at all tiers
   ├─ Template can evolve (Tier 1)
   ├─ Instance has own jj repo + workspaces (Tier 2)
   └─ Project continues normally (Tier 3)
```

## Parallel Evolution Model
```
Template Tier: jj repo + workspaces
     ↓ copier instantiate
Instance Tier: jj repo + workspaces  ◄── Full autonomy!
     ↓ symlink
Project Tier: jj repo + workspaces
```

Each tier:
- Independently version-controlled
- Can spawn jj workspaces for parallel work
- Instances are NOT workspaces of template - they are full repos

## Key Benefits

- **Zero Manual Setup**: Automatic template instantiation on file creation
- **Full Instance Autonomy**: Each instance = independent jj repo (not just workspace)
- **Clean Project Repos**: Infrastructure lives elsewhere via symlinks
- **Parallel Evolution**: Templates, instances, and projects evolve independently
- **Background Infrastructure**: Automations/data accessible but not tracked in projects
- **Flexible Iteration**: Update templates without disrupting existing instances

## Configuration Example
```yaml
# devman.yml
watch_patterns:
  - pattern: "src/modules/*/"
    template: "python-module"
  
  - pattern: "*.service.py"
    template: "service-layer"
  
  - pattern: "src/components/*/"
    template: "react-component"

template_store: "~/devman/templates"
instance_store: "~/devman/instances"

