# BRIEF: Enable Text Selection & Copy in ContentPanel

**Date:** 2026-03-26  
**Scope:** Frontend only — ContentPanel.tsx, index.css  
**Priority:** HIGH

---

## Problem

Currently the document/cong van content area has CSS that prevents text selection, making it impossible to highlight or copy text. Users need to be able to select and copy text from documents.

---

## Fix

### 1. `frontend/src/pages/HomePage.tsx`

The main layout wrapper has `select-none` class which disables all text selection across the entire app:

```tsx
{/* Main Content — 3-panel resizable layout */}
<div className="flex flex-1 overflow-hidden relative select-none">
```

Change `select-none` to `select-auto` — but this will make the divider drag handles awkward to use. Better approach: keep `select-none` on the layout but explicitly re-enable selection inside the content area only.

### 2. `frontend/src/components/ContentPanel.tsx`

In the scrollable content div, add `select-text` class to explicitly re-enable text selection:

```tsx
{/* Scrollable content area */}
<div
  ref={scrollRef}
  className="flex-1 overflow-y-auto px-4 py-3 select-text"   {/* ← add select-text */}
>
```

Also add `select-text` to:
- The `prose` div containing `dangerouslySetInnerHTML`
- The `tom_tat` text div at end of document
- The `ket_luan` section for cong van

```tsx
<div
  className="prose max-w-none text-gray-700 leading-relaxed select-text
             [&_table]:border-collapse ..."
  style={{ fontSize: `${fontSize}px` }}
  dangerouslySetInnerHTML={{ __html: content ?? '' }}
/>
```

### 3. `frontend/src/index.css`

Ensure the content area CSS does not have `user-select: none`. Add a utility override:

```css
/* Allow text selection inside document content */
.select-text,
.select-text * {
  user-select: text !important;
  -webkit-user-select: text !important;
}
```

### 4. Also add `select-text` to:
- `DocList` item text (so users can copy document titles from the list)
- `ContentPanel` header title and metadata (so users can copy the so_hieu, date etc.)

In ContentPanel header:
```tsx
<h2 className="font-semibold text-gray-800 text-sm leading-snug flex-1 min-w-0 select-text">
  {doc.ten || cv.ten}
</h2>
<div className="flex gap-2 mt-1 text-xs text-gray-500 items-center flex-wrap select-text">
  {/* metadata */}
</div>
```

---

## Do NOT change

- The `select-none` on the outer layout div (needed for drag dividers)
- Any backend code
- Sidebar or search logic

---

*Brief by Thanh AI — 2026-03-26*
