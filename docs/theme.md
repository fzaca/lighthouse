# Documentation Theme (Material for MkDocs)

The Lighthouse docs now use
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) to deliver a
polished, accessible reading experience out of the box.

## Why Material?

- **Beautiful defaults:** Typography, spacing, and dark/light palettes ship with
the theme—no Tailwind or custom JavaScript required.
- **Productivity features:** Instant navigation, search highlighting, code copy
buttons, and tabs make it easier to explore the toolkit.
- **Extensible:** The theme exposes granular configuration and works well with
`pymdown-extensions` for rich content blocks.

## Quick Start

Install the theme alongside MkDocs:

```bash
pip install mkdocs mkdocs-material
```

Then enable it in `mkdocs.yml`:

```yaml
theme:
  name: material
```

## Lighthouse Customisation

- **Palette:** We set indigo + teal brand colours with automatic dark-mode
  support and a floating mode switch.
- **Typography:** The site uses Inter for UI text and Fira Code for code blocks.
- **Hero & feature blocks:** A small `extra.css` file adds the gradient hero and
  feature grid on the landing page.
- **Navigation:** Instant navigation, section expansion, and integrated tables
  of contents help readers jump to relevant sections quickly.

Material supports many more enhancements (search suggestions, version pickers,
icons, analytics). Extend the configuration as the documentation grows.
