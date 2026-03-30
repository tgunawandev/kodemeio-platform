# Slash Commands Implementation Prompt

Copy ONE of the prompts below into a new Claude Code session in the target project repo.
Claude will read the project's CLAUDE.md and codebase, then create the right slash commands.

---

## kodemeio-react

```
Create Claude Code slash commands for this project. Read CLAUDE.md and explore the codebase first.

Place all commands in .claude/commands/ as markdown files. Each file becomes a /command.

Create these commands:

1. test.md — /test [app] — Run vitest for a specific app or all apps
   Should support: /test wms, /test sfa, /test (all), /test --coverage

2. dev.md — /dev [app] — Start dev server
   Should support: /dev wms, /dev (all apps)

3. lint.md — /lint — Run eslint + type-check + prettier

4. codegen.md — /codegen [app] — Fetch OpenAPI schema and regenerate types
   Must run: fetch-schema.sh then openapi-ts for the target app
   Should support: /codegen wms, /codegen sfa, /codegen (all)

5. new-page.md — /new-page <app> <name> — Scaffold a new page component
   Must follow the project's exact patterns: lazy loading, MobileLayout, useTranslation,
   TanStack Query hook. Read an existing page from apps/wms/src/pages/ as reference.
   Create: pages/<Name>Page.tsx, add route to App.tsx, add i18n keys to en.json + id.json

6. new-hook.md — /new-hook <app> <name> — Scaffold a TanStack Query API hook
   Must follow: apps/wms/src/api/ pattern with useQuery/useMutation, import from @/types/api,
   queryKey convention, invalidation patterns. Read existing hooks as reference.

7. new-app.md — /new-app <name> <port> — Scaffold a new app in apps/
   Must follow: createViteConfig factory, openapi-ts.config.ts, standard provider stack in main.tsx,
   package.json with workspace deps. Use apps/wms/ as template.

8. deploy.md — /deploy <app> — Show deploy commands for a specific app

9. build.md — /build [app] — Build for production

Each command should:
- Read the project's actual files to understand current patterns (don't guess)
- Include clear instructions for Claude on what to do
- Reference specific files as examples
- Handle both "do it for me" and "show me how" modes
```

---

## kodemeio-odoo-18

```
Create Claude Code slash commands for this project. Read CLAUDE.md and explore the codebase first.

Place all commands in .claude/commands/ as markdown files. Each file becomes a /command.

Create these commands:

1. test.md — /test [module] — Run Odoo tests for a specific module
   Should generate the right docker exec / ./run test command with proper tags

2. dev.md — /dev — Start development environment
   Should use the ./run command or docker compose

3. lint.md — /lint [module] — Run ruff check + mypy on a module in src/private/

4. new-module.md — /new-module <name> — Scaffold a new Odoo module in src/private/
   Must follow project conventions: __manifest__.py, __init__.py, models/, views/, security/,
   tests/, CLAUDE.md, ir.model.access.csv. Read an existing simple module as template.

5. new-model.md — /new-model <module> <name> — Add a new model to an existing module
   Must follow: _name convention, field patterns, _sql_constraints, mail.thread inheritance,
   OU isolation, security CSV entry. Read existing models as reference.

6. new-router.md — /new-router <module> <name> — Add a new FastAPI router to a module
   Must follow: base_management patterns, router file in services/, schemas in schemas/,
   response envelope convention, dependency injection, error handling, registration in
   fastapi_endpoint model. Read sfa_management/services/ as reference.

7. new-schema.md — /new-schema <module> <name> — Add Pydantic schemas for a router
   Must follow: response envelope (success, data, total, message), from_record() pattern,
   nested models, validators. Read existing schemas as reference.

8. new-test.md — /new-test <module> <name> — Add a test file for a model or router
   Must follow: FastAPITransactionCase for API tests, tagged decorators, setUpClass pattern,
   mock dependencies. Read existing tests as reference.

9. install.md — /install <bundle> — Install module bundles
   Should reference install/*.yaml bundle files and generate the right command

10. shell.md — /shell — Open Odoo shell for debugging

11. deploy.md — /deploy — Show production deployment commands

Each command should:
- Read the project's actual files to understand current patterns (don't guess)
- Follow the conventions in CLAUDE.md strictly (field namespaces, hook signatures, etc.)
- Reference specific files as examples
```

---

## kodemeio-next

```
Create Claude Code slash commands for this project. Read CLAUDE.md and explore the codebase first.

Place all commands in .claude/commands/ as markdown files. Each file becomes a /command.

Create these commands:

1. test.md — /test [app] — Run vitest for a specific app or all
   Should support: /test portfolio, /test (all)

2. dev.md — /dev [app] — Start dev server
   Should support: /dev portfolio, /dev corporate, /dev consulting

3. lint.md — /lint — Run eslint + type-check + prettier

4. new-page.md — /new-page <app> <path> — Scaffold a new page in App Router
   Must follow: the app's exact patterns (Server Components, metadata export, layout nesting).
   For portfolio: include i18n with next-intl, [locale] segment.
   For consulting: include custom dictionary i18n.
   For corporate: no i18n needed.
   Read existing pages as reference.

5. new-component.md — /new-component <name> [--app APP] — Scaffold a component
   If --app: create in apps/<app>/components/
   If no --app: create in packages/ui/src/components/ (shared)
   Must follow: shadcn/ui patterns, Tailwind v4 (no config file), cn() utility

6. new-data.md — /new-data <app> <name> — Add a new TypeScript data file
   Must follow the data file pattern in apps/<app>/data/ (typed arrays, no CMS)

7. new-app.md — /new-app <name> — Scaffold a new Next.js app in apps/
   Must follow: App Router, standalone output, shared packages, Tailwind v4, Sentry

8. build.md — /build [app] — Build for production

9. deploy.md — /deploy <app> — Deploy with Docker + Dokploy

Each command should:
- Read the project's actual files to understand current patterns (don't guess)
- Handle the differences between portfolio (i18n), corporate (no i18n), consulting (custom dict)
```

---

## kodemeio-hono

```
Create Claude Code slash commands for this project. Read CLAUDE.md and explore the codebase first.

Place all commands in .claude/commands/ as markdown files. Each file becomes a /command.

Create these commands:

1. test.md — /test [service] — Run vitest for a specific service or all
   Should support: /test svc1, /test (all)

2. dev.md — /dev [service|--all] — Start dev server(s)
   Should use the scripts/dev wrapper

3. lint.md — /lint — Run eslint + type-check

4. new-route.md — /new-route <service> <name> — Add a new route module
   Must follow: export const xRoutes = new Hono(), requireAuth() middleware,
   zValidator for input, error format { error: "message" }.
   Read apps/svc1/src/routes/ as reference.

5. new-worker.md — /new-worker <service> <name> — Add a BullMQ worker
   Must follow: @kodemeio/queue patterns, concurrency settings, retry config.
   Read apps/svc1/src/workers/ as reference.

6. new-integration.md — /new-integration <name> — Add a new integration client
   Must follow: packages/integrations/src/ pattern.
   Read existing integrations (mattermost.ts, s3.ts) as reference.

7. new-app.md — /new-app <name> [--type api|cli|mcp] [--port PORT] — Scaffold new service
   Should use scripts/new-app if it exists, or follow the svc2 template pattern.

8. db.md — /db <action> — Database operations (migrate, generate, push, studio)
   Should use scripts/db wrapper

9. deploy.md — /deploy <service> — Deploy with Docker

Each command should:
- Read the project's actual files to understand current patterns (don't guess)
- Follow CLAUDE.md conventions (soft delete, rate limit tiers, Redis DB isolation, etc.)
```

---

## kodemeio-fastapi

```
Create Claude Code slash commands for this project. Read CLAUDE.md and explore the codebase first.

Place all commands in .claude/commands/ as markdown files. Each file becomes a /command.

Create these commands:

1. test.md — /test [app] [--cov] — Run pytest for a specific app or all
   Should use scripts/test wrapper

2. dev.md — /dev [--all|--odoo-mm|--plane-mm|--webhooks] — Start dev server(s)
   Should use scripts/dev wrapper

3. lint.md — /lint — Run ruff check + mypy strict
   Should use scripts/lint wrapper

4. fmt.md — /fmt — Run ruff format + auto-fix

5. new-endpoint.md — /new-endpoint <app> <name> — Add a new API endpoint
   Must follow: Annotated dependency injection (DB, CurrentUser, AdminUser),
   soft delete filtering, pagination utility, response format { error: "message" },
   Pydantic response models. Read apps/api-main/src/kodemeio_api_main/routes/ as reference.

6. new-model.md — /new-model <name> — Add a new SQLAlchemy model
   Must follow: UUIDMixin + TimestampMixin + SoftDeleteMixin, lazy="raise" on relationships,
   Alembic migration generation. Read packages/core/src/kodemeio_core/models/ as reference.

7. new-app.md — /new-app <name> --type <webhook|events|integration|agent|etl|scheduler|stream>
   Should use scripts/new-app wrapper or follow the template pattern.

8. new-webhook.md — /new-webhook <name> — Add a webhook receiver app
   Must follow: packages/webhook framework, HMAC verification, event forwarding to Redis Streams.

9. db.md — /db <action> [message] — Database operations
   Should support: /db migrate, /db generate "add users table", /db push

10. deploy.md — /deploy <app> — Deploy with Docker

Each command should:
- Read the project's actual files to understand current patterns (don't guess)
- Follow CLAUDE.md conventions (soft delete, dependency injection, structured logging, etc.)
- Use uv for Python commands, not pip
```

---

## Cross-Project Platform Skill (optional, install globally)

```
Create a Claude Code skill at ~/.claude/skills/kodemeio-platform/SKILL.md that documents
how the 5 kodemeio projects connect to each other.

Read the CLAUDE.md of each project:
- /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-react/CLAUDE.md
- /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-odoo-18/CLAUDE.md
- /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-next/CLAUDE.md
- /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-hono/CLAUDE.md
- /home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-fastapi/CLAUDE.md

The skill should document:
1. Architecture overview: how the 5 repos relate
   - React PWA apps → call Odoo FastAPI backends
   - Next.js websites → call Hono API (svc1)
   - Hono services → integrate with Odoo, Mattermost, Plane, etc.
   - FastAPI services → webhooks, background jobs, AI agents
   - All auth via Authentik (auth.kodeme.io)

2. Data flow: React app → OpenAPI → Odoo FastAPI addon → Odoo ORM → PostgreSQL

3. How to add a new feature end-to-end:
   - Add Odoo model + FastAPI router + Pydantic schema (kodemeio-odoo-18)
   - Regenerate OpenAPI types (kodemeio-react: /codegen)
   - Add React page + API hook (kodemeio-react: /new-page, /new-hook)

4. Shared infrastructure:
   - PostgreSQL (kodemeio-postgres-16 at 10.0.0.3)
   - Authentik SSO (auth.kodeme.io, managed by kctl-ak)
   - Mailcow (mail.kodeme.io)
   - Dokploy + Traefik (deployment)
   - Hetzner Cloud (hosting)

5. Which project to work in for each task type:
   - "Add mobile app feature" → kodemeio-odoo-18 (backend) + kodemeio-react (frontend)
   - "Add website page" → kodemeio-next
   - "Add integration/webhook" → kodemeio-hono or kodemeio-fastapi
   - "Manage users/SSO" → kctl-ak CLI
```
