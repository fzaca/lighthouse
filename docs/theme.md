# Documentation Theme (mkdocs-shadcn)

The Pharox docs use the
[`mkdocs-shadcn`](https://github.com/asiffer/mkdocs-shadcn) theme. It applies the
`shadcn/ui` design system on top of MkDocs so the site feels modern without
custom CSS.

## Quick Start

Install the theme alongside MkDocs:

```bash
pip install mkdocs mkdocs-shadcn
```

Then enable it in `mkdocs.yml`:

```yaml
theme:
  name: shadcn
```

## Supported Extensions

The theme works with the standard Markdown extensions plus several `pymdownx`
helpers. Pharox currently enables:

- `admonition`
- `tables`
- `toc`
- `codehilite`
- `pymdownx.details`
- `pymdownx.highlight`
- `pymdownx.inlinehilite`
- `pymdownx.superfences`
- `pymdownx.tabbed`

Syntax colors come from the theme’s bundled Pygments palette (`github-dark`),
configured through the `pygments_style` setting in `mkdocs.yml`.

Additional extensions you can enable:

- `pymdownx.blocks.details`
- `pymdownx.blocks.tab`
- `pymdownx.progressbar`
- `pymdownx.arithmatex`
- built-in `shadcn.echarts`, `shadcn.iconify`, `shadcn.codexec`

## Plugins

- built-in `excalidraw` – edit diagrams in dev mode and render SVG at build
  time.
- `mkdocstrings` – auto-generate API docs from docstrings (experimental in the
  shadcn theme).

These plugins are optional. Enable them in `mkdocs.yml` when you need the
functionality.

## Developing the Theme

The upstream project exposes its Tailwind CSS source for contributors. To work
on the theme itself, clone the repository and install both the Python and CSS
prerequisites:

```bash
git clone https://github.com/asiffer/mkdocs-shadcn
cd mkdocs-shadcn
uv sync --all-extras
bun install  # or npm/yarn/pnpm
```

Run the example docs in watch mode while hacking on the theme:

```bash
cd pages/
uv run mkdocs serve --watch-theme -w ..
```

In another terminal, keep the Tailwind watcher running from the project root:

```bash
bun dev
```

The Pharox repository does not need Tailwind or the dev tooling—only the
published `mkdocs-shadcn` package is required.
