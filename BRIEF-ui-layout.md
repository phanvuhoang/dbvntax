# BRIEF: UI Layout — Sidebar Icons, Collapsible Panels, Mobile Maximize

**Date:** 2026-03-25  
**Scope:** Frontend only — Sidebar.tsx, ContentPanel.tsx, HomePage.tsx  
**Priority:** HIGH

---

## Fix 1: Sidebar Sắc thuế — Icons + Abbreviations + Collapsible

### 1a. Add icon abbreviations to each category

In `Sidebar.tsx`, update the category list rendering to show a colored pill/badge with short code on the left of each item.

Icon map (add as constant at top of `Sidebar.tsx`):
```ts
const CATEGORY_ICONS: Record<string, { abbr: string; color: string }> = {
  CIT:     { abbr: 'CIT',  color: 'bg-green-100 text-green-700' },
  VAT:     { abbr: 'VAT',  color: 'bg-teal-100 text-teal-700' },
  PIT:     { abbr: 'PIT',  color: 'bg-blue-100 text-blue-700' },
  SCT:     { abbr: 'SST',  color: 'bg-orange-100 text-orange-700' },
  QLT:     { abbr: 'ADM',  color: 'bg-gray-100 text-gray-600' },
  HDDT:    { abbr: 'INV',  color: 'bg-yellow-100 text-yellow-700' },
  FCT:     { abbr: 'FCT',  color: 'bg-purple-100 text-purple-700' },
  THUE_QT: { abbr: 'INT',  color: 'bg-indigo-100 text-indigo-700' },
  TP:      { abbr: 'TP',   color: 'bg-pink-100 text-pink-700' },
  HKD:     { abbr: 'BH',   color: 'bg-lime-100 text-lime-700' },
};
```

Update each category button to show:
```tsx
<button ...>
  {icon && (
    <span className={`text-[9px] font-bold px-1 py-0.5 rounded mr-1.5 shrink-0 ${icon.color}`}>
      {icon.abbr}
    </span>
  )}
  <span className="flex-1 text-left truncate">{cat.name}</span>
  {count badge}
</button>
```

Apply same icon rendering in BOTH flat mode (tab Văn bản) and accordion mode (tab Công văn).

---

### 1b. Collapsible sidebar with hamburger toggle + tooltips

**In `Sidebar.tsx`:**

Add `collapsed` prop (boolean) passed from parent.

When `collapsed=true`:
- Sidebar width shrinks to 40px (just icons)
- Show only the abbr pill vertically centered for each item, NO text
- Each item has a Tippy/title tooltip on hover showing full name
- Header "Sắc thuế" hidden
- Date filter section hidden
- Hamburger button at top of sidebar to toggle (rotates or animates)

When `collapsed=false`: normal display.

**Sidebar.tsx signature:**
```tsx
interface Props {
  // ...existing...
  collapsed: boolean;
  onToggleCollapse: () => void;
}
```

**Collapsed item render:**
```tsx
{collapsed ? (
  <button
    title={cat.name}  // native tooltip
    onClick={() => onSelect(cat.code)}
    className={`w-full flex justify-center items-center py-2 transition
      ${cat.code === selected ? 'bg-primary-light' : 'hover:bg-gray-50'}`}
  >
    <span className={`text-[9px] font-bold px-1.5 py-1 rounded ${icon?.color || 'bg-gray-100 text-gray-500'}`}>
      {icon?.abbr || cat.code.slice(0,3)}
    </span>
  </button>
) : (
  // normal expanded button
)}
```

**Toggle button at top of sidebar:**
```tsx
<div className="flex items-center justify-between px-2 pt-2 pb-1">
  {!collapsed && (
    <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">
      Sắc thuế
    </h3>
  )}
  <button
    onClick={onToggleCollapse}
    title={collapsed ? 'Mở rộng sidebar' : 'Thu gọn sidebar'}
    className="ml-auto p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition"
  >
    {/* Hamburger / Arrow icon */}
    {collapsed ? (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    ) : (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    )}
  </button>
</div>
```

**In `HomePage.tsx`:**
- Add `const [sidebarCollapsed, setSidebarCollapsed] = useState(false)`
- Pass `collapsed={sidebarCollapsed}` and `onToggleCollapse={() => setSidebarCollapsed(c => !c)}` to `<Sidebar>`
- When collapsed: `style={{ width: 40 }}` instead of `style={{ width: sidebarW }}`
- When collapsed on desktop: hide the resize `<Divider>` between sidebar and doclist (or set to non-resizable)

---

## Fix 2: DocList panel — Collapsible + Floating on mobile

### 2a. Desktop: collapsible DocList

In `HomePage.tsx`, add `const [listCollapsed, setListCollapsed] = useState(false)`.

Add a collapse toggle button on the right edge of the DocList panel:
```tsx
<div className="relative flex flex-col border-r border-gray-200 bg-gray-50 flex-shrink-0 overflow-hidden"
  style={{ width: listCollapsed ? 0 : listW, minWidth: listCollapsed ? 0 : 200 }}>
  
  {/* Collapse toggle button — always visible, attached to right edge */}
  <button
    onClick={() => setListCollapsed(c => !c)}
    title={listCollapsed ? 'Mở danh sách' : 'Thu gọn danh sách'}
    className="absolute right-0 top-1/2 -translate-y-1/2 z-10 bg-white border border-gray-200 rounded-l 
               shadow-sm px-0.5 py-3 hover:bg-gray-50 hover:text-primary transition text-gray-400"
    style={{ transform: 'translateY(-50%) translateX(100%)' }}
  >
    <svg className={`w-3 h-3 transition-transform ${listCollapsed ? 'rotate-180' : ''}`} 
         fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  </button>
  
  {!listCollapsed && <DocList ... />}
</div>
```

When `listCollapsed=true`: width=0, DocList hidden. The collapse button "floats" on the edge of ContentPanel.

### 2b. Mobile: DocList as floating bottom sheet

On mobile (screen width < 768px), DocList panel renders differently:
- Default: **hidden** (not taking space)
- A floating button "📋 Danh sách" appears at bottom-left of screen
- Tapping it slides up a bottom sheet (modal overlay) showing DocList
- Bottom sheet has a handle/close button at top
- Selecting an item closes the bottom sheet and shows content fullscreen

```tsx
// In HomePage.tsx — mobile DocList as bottom drawer
{isMobile && (
  <>
    {/* Floating trigger button */}
    {!mobileListOpen && (
      <button
        onClick={() => setMobileListOpen(true)}
        className="fixed bottom-4 left-4 z-50 bg-primary text-white rounded-full 
                   shadow-lg px-4 py-2 text-sm font-medium flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16" />
        </svg>
        {total > 0 ? `${total} văn bản` : 'Danh sách'}
      </button>
    )}
    
    {/* Bottom sheet */}
    {mobileListOpen && (
      <div className="fixed inset-0 z-50 flex flex-col justify-end">
        <div className="bg-black/40 absolute inset-0" onClick={() => setMobileListOpen(false)} />
        <div className="relative bg-white rounded-t-2xl shadow-2xl flex flex-col"
             style={{ height: '70vh' }}>
          {/* Handle */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-700">
              {tab === 'vanban' ? 'Văn bản' : 'Công văn'} ({total})
            </span>
            <button onClick={() => setMobileListOpen(false)} className="text-gray-400 hover:text-gray-600">✕</button>
          </div>
          <div className="flex-1 overflow-hidden">
            <DocList
              items={items} total={total} page={page} limit={LIMIT}
              selectedId={selectedItem?.id ?? null}
              tab={tab} isLoading={isLoading}
              onSelect={(item) => { setSelectedItem(item); setMobileListOpen(false); }}
              onPageChange={setPage}
            />
          </div>
        </div>
      </div>
    )}
  </>
)}
```

Use `const isMobile = typeof window !== 'undefined' && window.innerWidth < 768` or a `useWindowSize` hook.

---

## Fix 3: Move Tóm tắt + Hiệu lực chi tiết to Footer

In `ContentPanel.tsx`:

### Remove from top area:
Remove these two blocks from their current position (after header, before content):
```tsx
{/* Hiệu lực chi tiết — expandable, mặc định collapsed */}
{tab === 'vanban' && doc.hieu_luc_index && (
  <div className="px-4 mt-2 flex-shrink-0">
    <HieuLucDetail index={doc.hieu_luc_index} />
  </div>
)}

{/* Tóm tắt — expandable, mặc định collapsed */}
{(doc as Document).tom_tat && (
  <div className="px-4 flex-shrink-0">
    <TomTatBox text={(doc as Document).tom_tat!} />
  </div>
)}
```

### Add to Footer area (before or after the action buttons):
Move them into the footer section as collapsible accordions. The footer becomes:

```tsx
{/* Footer — collapsible summary + hieu_luc + action buttons */}
<div className="border-t border-gray-100 flex-shrink-0">
  
  {/* Tóm tắt accordion */}
  {(doc as Document).tom_tat && (
    <div className="border-b border-gray-100">
      <button
        onClick={() => setTomTatOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2 hover:bg-gray-50 transition text-left"
      >
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">📝 Tóm tắt</span>
        <span className="text-gray-400 text-xs">{tomTatOpen ? '▲' : '▼'}</span>
      </button>
      {tomTatOpen && (
        <div className="px-4 pb-3 text-sm text-gray-600 leading-relaxed max-h-40 overflow-y-auto">
          {(doc as Document).tom_tat}
        </div>
      )}
    </div>
  )}
  
  {/* Hiệu lực chi tiết accordion */}
  {tab === 'vanban' && doc.hieu_luc_index && (
    <div className="border-b border-gray-100">
      <button
        onClick={() => setHieuLucOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2 hover:bg-gray-50 transition text-left"
      >
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">⚡ Hiệu lực chi tiết</span>
        <span className="text-gray-400 text-xs">{hieuLucOpen ? '▲' : '▼'}</span>
      </button>
      {hieuLucOpen && (
        <div className="px-4 pb-3 max-h-48 overflow-y-auto">
          <HieuLucDetail index={doc.hieu_luc_index} />
        </div>
      )}
    </div>
  )}

  {/* Keywords */}
  {(doc.keywords ?? []).length > 0 && (
    <div className="px-4 py-2 flex flex-wrap gap-1">
      {(doc.keywords ?? []).map((k, i) => (
        <span key={i} className="bg-gray-100 text-gray-500 text-[11px] px-2 py-0.5 rounded">{k}</span>
      ))}
    </div>
  )}

  {/* Action buttons */}
  <div className="px-4 py-2 flex gap-2 flex-wrap">
    {/* ...existing buttons (AI, Xem gốc, TVPL, Mở tab mới)... */}
  </div>
</div>
```

Add state for these two accordions:
```tsx
const [tomTatOpen, setTomTatOpen] = useState(false);
const [hieuLucOpen, setHieuLucOpen] = useState(false);
```

Both default `false` (collapsed) — takes zero space until user opens them.

---

## Fix 4: Mobile — ContentPanel Maximized

On mobile, when an item is selected, ContentPanel should be truly fullscreen.

In `ContentPanel.tsx`, the content area should use `100vh` minus header height on mobile.

In `HomePage.tsx`:
- On mobile: when `selectedItem !== null`, the layout should be:
  - Header visible (for back navigation)
  - ContentPanel takes 100% remaining height
  - Both sidebars hidden/offscreen
  - DocList accessible via floating button (Fix 2b)

```tsx
// Mobile layout override in HomePage.tsx
const mobileContentFullscreen = isMobile && selectedItem !== null;

// In the main content flex container:
<div className="flex flex-1 overflow-hidden relative select-none">
  
  {/* Sidebar: hidden on mobile when content is open */}
  {(!mobileContentFullscreen) && (
    // ... sidebar div ...
  )}
  
  {/* DocList: hidden entirely on mobile (replaced by floating button) */}
  {!isMobile && (
    // ... doclist div ...
  )}
  
  {/* ContentPanel: always full width on mobile when item selected */}
  <div className={`flex flex-1 overflow-hidden ${mobileContentFullscreen ? 'w-full' : ''}`}>
    
    {/* Back button on mobile */}
    {mobileContentFullscreen && (
      <div className="absolute top-0 left-0 z-10 p-2">
        <button
          onClick={() => setSelectedItem(null)}
          className="bg-white shadow rounded-full p-2 text-primary hover:bg-primary-light"
        >
          ←
        </button>
      </div>
    )}
    
    <ContentPanel ... />
  </div>
</div>
```

Also: add a **"← Danh sách"** back button inside ContentPanel header on mobile:
- In `ContentPanel.tsx`, accept optional `onBack?: () => void` prop
- If `onBack` provided, show `← Danh sách` button in header next to title

---

## Summary of state variables to add in `HomePage.tsx`

```tsx
const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
const [listCollapsed, setListCollapsed] = useState(false);
const [mobileListOpen, setMobileListOpen] = useState(false);
const isMobile = useWindowSize() < 768;  // or use matchMedia hook
```

## Summary of state variables to add in `ContentPanel.tsx`

```tsx
const [tomTatOpen, setTomTatOpen] = useState(false);
const [hieuLucOpen, setHieuLucOpen] = useState(false);
```

---

## Do NOT change

- Search logic, API hooks, auth flow
- DocList rendering internals
- AI analysis panel
- Any backend code

---

*Brief by Thanh AI — 2026-03-25*
