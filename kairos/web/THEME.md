# KAIROS Design System

Version 1.0 · 2026-04-28

---

## Overview

KAIROS uses a custom dark-first CSS design system inspired by Linear.app, Vercel Dashboard, Raycast, and Resend. The design communicates depth, clarity, and professional trust — a serious intelligence tool for professional coaches.

**No external UI libraries.** Pure CSS with minimal vanilla JS where needed.

---

## File Structure

```
kairos/web/static/css/
├── theme.css       # CSS variables, reset, base styles, typography
├── components.css  # All reusable component classes
└── layout.css      # App shell, sidebar, topbar, grid, responsive
```

Templates are Jinja2 files in `kairos/web/templates/` extending `base.html`.

---

## Color System

All colors are defined as CSS custom properties in `:root`:

| Variable | Value | Usage |
|----------|-------|-------|
| `--bg-primary` | `#0a0a0f` | Page background |
| `--bg-secondary` | `#111118` | Cards, sidebar, topbar |
| `--bg-tertiary` | `#1a1a24` | Inputs, hover states, code blocks |
| `--border-subtle` | `#1e1e2e` | Dividers, subtle separators |
| `--border-default` | `#2a2a3a` | Card borders, input borders |
| `--border-strong` | `#3a3a4a` | Active/focus borders |
| `--accent-teal` | `#2dd4bf` | Primary actions, active states, scores > 0.7 |
| `--accent-teal-hover` | `#14b8a6` | Hover variant |
| `--accent-teal-muted` | `rgba(45,212,191,0.12)` | Badge backgrounds, sidebar active |
| `--accent-indigo` | `#818cf8` | Secondary accent, tags, N2 memory |
| `--accent-indigo-muted` | `rgba(129,140,248,0.12)` | Indigo badge backgrounds |
| `--text-primary` | `#f1f5f9` | Headings, primary text |
| `--text-secondary` | `#94a3b8` | Body text |
| `--text-muted` | `#475569` | Captions, placeholders |
| `--text-disabled` | `#2d3748` | Disabled text |
| `--success` | `#34d399` | Healthy states, success badges |
| `--warning` | `#fbbf24` | Mid-range scores, warnings |
| `--danger` | `#f87171` | Errors, low scores, urgent alerts |
| `--info` | `#38bdf8` | Info alerts |

---

## Typography

**Font stack**: Inter (sans-serif) + JetBrains Mono (monospace), loaded from Google Fonts.

```css
--font-sans: 'Inter', system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;
```

**Scale**:

| Class | Size | Weight | Color | Use |
|-------|------|--------|-------|-----|
| `h1` / `.h1` | 28px | 600 | `--text-primary` | Page titles, tracking -0.02em |
| `h2` / `.h2` | 20px | 600 | `--text-primary` | Section headings, tracking -0.01em |
| `h3` / `.h3` | 16px | 500 | `--text-primary` | Card titles |
| `.body` | 14px | 400 | `--text-secondary` | Paragraphs, line-height 1.6 |
| `.text-sm` | 12px | 400 | `--text-muted` | Captions, timestamps |
| `.text-mono` | 13px | 400 | `--text-secondary` | Code, scores, metrics |

---

## Component Reference

### Cards
```html
<div class="card">Default panel</div>
<div class="card-ghost">No bg, subtle border</div>
<div class="card-active">Active with teal border + glow</div>
```

### Buttons
```html
<button class="btn btn-primary">Primary (teal bg)</button>
<button class="btn btn-secondary">Secondary (bordered)</button>
<button class="btn btn-ghost">Ghost (no border)</button>
<button class="btn btn-danger">Danger (red border)</button>
```
Sizes: `btn-sm` (28px), default (36px), `btn-lg` (44px)

### Badges
```html
<span class="badge badge-teal">Active</span>
<span class="badge badge-indigo">Pattern</span>
<span class="badge badge-success">Healthy</span>
<span class="badge badge-warning">Warning</span>
<span class="badge badge-danger">Urgent</span>
<span class="badge badge-info">Info</span>
<span class="badge badge-neutral">Default</span>
```

### Score Display
```html
<div class="score-bar">
    <div class="score-bar-fill" style="width: 75%"></div>
</div>
<span class="score-value score-high">0.85</span>
<span class="score-value score-mid">0.55</span>
<span class="score-value score-low">0.25</span>
```

### Progress Bars
```html
<div class="progress-mini">
    <div class="progress-mini-fill high" style="width: 80%"></div>
</div>
<!-- Classes: high (teal), mid (warning), low (danger) -->
```

### Inputs
```html
<input type="text" class="input" placeholder="Placeholder">
<textarea class="input" rows="3"></textarea>
<select class="input">...</select>
```

### Alerts
```html
<div class="alert alert-success">Success message</div>
<div class="alert alert-info">Info message</div>
<div class="alert alert-warning">Warning message</div>
<div class="alert alert-danger">Error message</div>
```

### Chat Bubbles
```html
<div class="chat-bubble chat-bubble-coach">
    Message text
    <div class="chat-bubble-time">12:34</div>
</div>
<div class="chat-bubble chat-bubble-client">
    Response
    <div class="chat-bubble-time">12:35</div>
</div>
```

### Typing Indicator
```html
<div class="typing">
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
</div>
```

### Avatar
```html
<div class="avatar avatar-md">AB</div>
<div class="avatar avatar-md avatar-ring">CD</div>
```
Sizes: `avatar-sm` (24px), `avatar-md` (32px), `avatar-lg` (40px)

### Modal
```html
<div class="modal-overlay">
    <div class="modal">
        <div class="modal-header">
            <h2>Title</h2>
            <button class="modal-close">&times;</button>
        </div>
        <!-- content -->
        <div class="modal-footer">
            <button class="btn btn-primary">Confirm</button>
            <button class="btn btn-secondary">Cancel</button>
        </div>
    </div>
</div>
```

### Loading States
```html
<!-- Skeleton placeholder -->
<div class="skeleton skeleton-text"></div>
<div class="skeleton skeleton-card"></div>

<!-- Spinner -->
<div class="spinner"></div>

<!-- Pulse dot (live indicator) -->
<span class="pulse-dot"></span>
<span class="pulse-dot warning"></span>
<span class="pulse-dot danger"></span>
<span class="pulse-dot success"></span>
```

### Memory Level Indicators
```html
<span class="memory-badge memory-n1">N1 Raw · 42</span>
<span class="memory-badge memory-n2">N2 Cases · 18</span>
<span class="memory-badge memory-n3">N3 Patterns · 7</span>
<span class="memory-badge memory-n4">N4 Exec · 33</span>
```

### Stat Cards
```html
<div class="stat-card">
    <div class="stat-value">42</div>
    <div class="stat-label">Total clients</div>
</div>
```

### Data Table
```html
<table class="table">
    <thead><tr><th>Column</th></tr></thead>
    <tbody><tr><td>Data</td></tr></tbody>
</table>
```

### Tabs
```html
<div class="tabs">
    <button class="tab active">Overview</button>
    <button class="tab">Sessions</button>
    <button class="tab">Patterns</button>
</div>
```

### Timeline
```html
<div class="timeline">
    <div class="timeline-item">Event content</div>
    <div class="timeline-item">Event content</div>
</div>
```

### Upload Drop Area
```html
<div class="drop-area">Drop files here or click to select</div>
<!-- Add .dragover class on drag over -->
```

---

## Layout System

### App Shell
```
┌─────────────────────────────────────────────┐
│  TOPBAR (52px) — Logo · Nav · User          │
├──────────┬──────────────────────────────────┤
│ SIDEBAR  │  MAIN CONTENT                    │
│ (240px)  │  (fluid, max 1200px centered)    │
└──────────┴──────────────────────────────────┘
```

### Grid
```html
<div class="grid grid-2">  <!-- 2 columns -->
<div class="grid grid-3">  <!-- 3 columns -->
<div class="grid grid-4">  <!-- 4 columns -->
<div class="grid grid-12"><div class="col-span-8">...</div></div>
```
Gap: 24px (`var(--space-6)`). Responsive: collapses to fewer columns on smaller screens.

### Flex Utilities
```html
<div class="flex items-center justify-between gap-4">
```

### Spacing
```html
<!-- Margin -->
<div class="mt-4 mb-6 ml-auto">

<!-- Padding -->
<div class="p-4 py-2 px-3">
```

### Responsive Visibility
- `.lg-only` — visible on large screens (≥1025px)
- `.lg-hidden` — hidden on large screens
- `.md-only` — visible on medium+ screens
- `.sm-only` — visible on small screens

### Chat Layout (split view)
```html
<div class="chat-layout">
    <div class="chat-main">...</div>
    <div class="chat-sidebar">...</div>
</div>
```

### Split Layout (client detail)
```html
<div class="split-layout">
    <div>Left column (1/3)</div>
    <div>Right column (2/3)</div>
</div>
```

---

## Design Principles

1. **Dark-first only** — No light mode. The entire app is designed for dark backgrounds.
2. **No gradients except score bars** — Flat, clean, professional.
3. **No shadows except modals and tooltips** — Depth communicated through borders and layering.
4. **Data is the design** — No decorative elements. Every pixel serves function.
5. **Visible focus states** — All interactive elements use teal outline on `:focus-visible`.
6. **Use only defined CSS variables** — Never hardcode colors.

---

## Adding a New Page

1. Create `<name>.html` extending `base.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="page-header">
    <div class="page-header-left"><h1>Title</h1></div>
    <div class="page-header-right"><!-- actions --></div>
</div>
<!-- content -->
{% endblock %}
```

2. Use only the CSS classes from this design system. No inline `style=` unless absolutely necessary for dynamic values (e.g., progress bar widths).
3. For dynamic color values, use the semantic classes (`.score-high`, `.score-mid`, `.score-low`, etc.).

---

## Browser Support

- Chrome 90+
- Firefox 90+
- Safari 15+
- Edge 90+

CSS features used: custom properties, grid, flexbox, `backdrop-filter`, `@keyframes`.
