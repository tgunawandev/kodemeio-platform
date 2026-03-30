"""Scaffolding commands for generating code."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext

app = typer.Typer(help="Scaffold new apps, pages, hooks, and components.")


@app.command()
def page(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name (e.g. sfa, wms)")],
    name: Annotated[str, typer.Argument(help="Page name in PascalCase (e.g. CustomerDetail)")],
) -> None:
    """Scaffold a new page component.

    Creates: src/pages/{Name}.tsx with standard imports, i18n, and layout.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    if actx.is_nextjs(app_name):
        # Next.js App Router: app/{slug}/page.tsx
        slug = name.lower().replace(" ", "-")
        page_file = app_dir / "app" / slug / "page.tsx"
        if page_file.exists():
            out.error(f"Page already exists: {page_file}")
            raise typer.Exit(1)
        page_file.parent.mkdir(parents=True, exist_ok=True)

        content = f'''import type {{ Metadata }} from "next";

export const metadata: Metadata = {{
  title: "{name}",
}};

export default function {name}Page() {{
  return (
    <main className="p-4">
      <h1 className="text-lg font-semibold">{name}</h1>
    </main>
  );
}}
'''
        page_file.write_text(content)
        out.success(f"Created {page_file.relative_to(root)}")
        out.info(f"Add navigation link for /{slug} in your layout or nav component")
    else:
        # Vite React: src/pages/{Name}.tsx
        page_file = app_dir / "src" / "pages" / f"{name}.tsx"
        if page_file.exists():
            out.error(f"Page already exists: {page_file}")
            raise typer.Exit(1)
        page_file.parent.mkdir(parents=True, exist_ok=True)

        content = f'''import {{ useTranslation }} from "react-i18next";
import {{ usePageTitle }} from "@kodemeio/core/hooks";
import {{ MobileLayout }} from "@kodemeio/ui";

export function {name}() {{
  const {{ t }} = useTranslation();
  usePageTitle(t("{name.lower()}.title"));

  return (
    <MobileLayout title={{t("{name.lower()}.title")}}>
      <div className="p-4">
        <h1 className="text-lg font-semibold">{{t("{name.lower()}.title")}}</h1>
      </div>
    </MobileLayout>
  );
}}
'''
        page_file.write_text(content)
        out.success(f"Created {page_file.relative_to(root)}")
        out.info(f"Add route in {app_name}/src/App.tsx and i18n keys in en.json + id.json")


@app.command()
def hook(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    resource: Annotated[str, typer.Argument(help="Resource name (e.g. customers, orders)")],
) -> None:
    """Scaffold a TanStack Query API hook.

    Creates: src/hooks/use{Resource}.ts with list + detail queries and mutation.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    # Convert resource to hook name
    singular = resource[:-1] if resource.endswith("s") and not resource.endswith("ss") else resource
    pascal = singular.capitalize()
    plural = resource

    hook_file = app_dir / "src" / "hooks" / f"use{pascal}.ts"
    if hook_file.exists():
        out.error(f"Hook already exists: {hook_file}")
        raise typer.Exit(1)

    hook_file.parent.mkdir(parents=True, exist_ok=True)

    content = f'''import {{ useQuery, useMutation, useQueryClient }} from "@tanstack/react-query";
import {{ toast }} from "sonner";
import {{ useTranslation }} from "react-i18next";
import {{ client }} from "@/lib/client";
import {{ getErrorMessage }} from "@kodemeio/core/errors";
import type {{ {pascal}ListResponse, {pascal}DetailResponse, {pascal}CreateData }} from "@/types/api";

export function use{pascal}List(params?: {pascal}ListResponse["params"]) {{
  return useQuery({{
    queryKey: ["{plural}", params],
    queryFn: () => client.get<{pascal}ListResponse>("/{plural}/", {{ params }}),
  }});
}}

export function use{pascal}Detail(id: number | undefined) {{
  return useQuery({{
    queryKey: ["{plural}", id],
    queryFn: () => client.get<{pascal}DetailResponse>(`/{plural}/${{id}}/`),
    enabled: !!id,
  }});
}}

export function useCreate{pascal}() {{
  const queryClient = useQueryClient();
  const {{ t }} = useTranslation();

  return useMutation({{
    mutationFn: (data: {pascal}CreateData) => client.post<{pascal}DetailResponse>("/{plural}/", data),
    onSuccess: () => {{
      queryClient.invalidateQueries({{ queryKey: ["{plural}"] }});
      toast.success(t("{singular}.created"));
    }},
    onError: (err) => toast.error(getErrorMessage(err)),
  }});
}}
'''
    hook_file.write_text(content)
    out.success(f"Created {hook_file.relative_to(root)}")
    out.info("Import types from @/types/api and add i18n keys")


@app.command()
def form(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    name: Annotated[str, typer.Argument(help="Form component name in PascalCase (e.g. CustomerForm)")],
) -> None:
    """Scaffold a react-hook-form + zod form component.

    Creates: src/components/{Name}.tsx with useForm, zodResolver, and shadcn/ui inputs.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    form_file = app_dir / "src" / "components" / f"{name}.tsx"
    if form_file.exists():
        out.error(f"Form component already exists: {form_file}")
        raise typer.Exit(1)

    form_file.parent.mkdir(parents=True, exist_ok=True)

    content = f"""import {{ useForm }} from "react-hook-form";
import {{ zodResolver }} from "@hookform/resolvers/zod";
import {{ z }} from "zod";
import {{ Button }} from "@kodemeio/ui";
import {{ Input }} from "@kodemeio/ui";
import {{ Label }} from "@kodemeio/ui";

const schema = z.object({{
  name: z.string().min(1, "Name is required"),
}});

type FormValues = z.infer<typeof schema>;

interface {name}Props {{
  onSubmit: (data: FormValues) => void;
  defaultValues?: Partial<FormValues>;
}}

export function {name}({{ onSubmit, defaultValues }}: {name}Props) {{
  const {{
    register,
    handleSubmit,
    formState: {{ errors }},
  }} = useForm<FormValues>({{
    resolver: zodResolver(schema),
    defaultValues,
  }});

  return (
    <form onSubmit={{handleSubmit(onSubmit)}} className="space-y-4">
      <div className="space-y-1">
        <Label htmlFor="name">Name</Label>
        <Input id="name" {{...register("name")}} />
        {{errors.name && <p className="text-sm text-destructive">{{errors.name.message}}</p>}}
      </div>
      <Button type="submit">Submit</Button>
    </form>
  );
}}
"""
    form_file.write_text(content)
    out.success(f"Created {form_file.relative_to(root)}")
    out.info("Extend the zod schema with fields matching your API types from @/types/api")


@app.command()
def test(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    name: Annotated[str, typer.Argument(help="Component or page name in PascalCase (e.g. App, CustomerList)")],
) -> None:
    """Scaffold a vitest test file.

    Creates: src/pages/{Name}.test.tsx (or src/components/ based on where source exists).
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name
    src_dir = app_dir / "src"

    # Determine directory: follow the source file if it exists
    source_dirs = ["pages", "components", "hooks"]
    target_dir = src_dir / "pages"  # default
    for candidate in source_dirs:
        source_file = src_dir / candidate / f"{name}.tsx"
        if source_file.exists():
            target_dir = src_dir / candidate
            break

    test_file = target_dir / f"{name}.test.tsx"
    if test_file.exists():
        out.error(f"Test file already exists: {test_file}")
        raise typer.Exit(1)

    test_file.parent.mkdir(parents=True, exist_ok=True)

    content = f'''import {{ render, screen }} from "@testing-library/react";
import {{ describe, it, expect, vi }} from "vitest";
import {{ createWrapper }} from "@kodemeio/testing";
import {{ {name} }} from "@/{target_dir.relative_to(src_dir)}/{name}";

vi.mock("@/lib/client");
vi.mock("@kodemeio/offline");
vi.mock("sonner");

describe("{name}", () => {{
  it("renders without crashing", () => {{
    render(<{name} />, {{ wrapper: createWrapper() }});
    expect(screen.getByRole("main")).toBeDefined();
  }});

  it("matches snapshot", () => {{
    const {{ container }} = render(<{name} />, {{ wrapper: createWrapper() }});
    expect(container.firstChild).toMatchSnapshot();
  }});
}});
'''
    test_file.write_text(content)
    out.success(f"Created {test_file.relative_to(root)}")
    out.info("Update the import path and add specific assertions for your component")


@app.command()
def component(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    name: Annotated[str, typer.Argument(help="Component name in PascalCase")],
) -> None:
    """Scaffold a new component."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    # Next.js: components/ at root, Vite: src/components/
    comp_dir = app_dir / "components" if actx.is_nextjs(app_name) else app_dir / "src" / "components"
    comp_file = comp_dir / f"{name}.tsx"
    if comp_file.exists():
        out.error(f"Component already exists: {comp_file}")
        raise typer.Exit(1)

    comp_file.parent.mkdir(parents=True, exist_ok=True)

    content = f"""interface {name}Props {{
  // TODO: define props
}}

export function {name}({{ }}: {name}Props) {{
  return (
    <div>
      {name}
    </div>
  );
}}
"""
    comp_file.write_text(content)
    out.success(f"Created {comp_file.relative_to(root)}")
