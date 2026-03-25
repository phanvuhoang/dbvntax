# BRIEF: Admin — Bulk Delete Documents UI

**Date:** 2026-03-26  
**Scope:** Frontend (AdminPage.tsx or HomePage.tsx) + Backend (main.py)  
**Priority:** MEDIUM  
**Access:** Admin only

---

## Feature: Select & Delete Documents/CongVan

Admin cần có thể tick chọn một hoặc nhiều văn bản/công văn và xóa chúng khỏi DB.

---

## Backend

### New endpoint: `DELETE /api/admin/documents`

```python
class BulkDeleteRequest(BaseModel):
    ids: List[int]
    source: str  # "documents" or "cong_van"

@app.delete("/api/admin/documents")
async def bulk_delete_docs(
    req: BulkDeleteRequest,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    if req.source not in ("documents", "cong_van"):
        raise HTTPException(400, "Invalid source")
    if not req.ids:
        raise HTTPException(400, "No ids provided")
    
    table = "documents" if req.source == "documents" else "cong_van"
    result = await db.execute(
        text(f"DELETE FROM {table} WHERE id = ANY(:ids) RETURNING id"),
        {"ids": req.ids}
    )
    deleted = [r[0] for r in result.fetchall()]
    await db.commit()
    return {"deleted": deleted, "count": len(deleted)}
```

---

## Frontend

### Option A: Add delete mode to existing DocList (recommended — no new page needed)

When user is admin, show a small "🗑 Xoá" toggle button in the DocList header. 
Clicking it activates "delete mode" — checkboxes appear next to each item.

#### Changes to `DocList.tsx` (or wherever the list renders):

```tsx
interface DocListProps {
  // ...existing...
  isAdmin?: boolean;
  onBulkDelete?: (ids: number[], source: 'documents' | 'cong_van') => void;
}
```

Add state:
```tsx
const [deleteMode, setDeleteMode] = useState(false);
const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
```

In the DocList header bar:
```tsx
{isAdmin && (
  <button
    onClick={() => { setDeleteMode(d => !d); setSelectedIds(new Set()); }}
    className={`text-xs px-2 py-1 rounded border transition ${
      deleteMode
        ? 'bg-red-50 border-red-300 text-red-600'
        : 'border-gray-200 text-gray-400 hover:border-red-300 hover:text-red-500'
    }`}
    title={deleteMode ? 'Hủy chọn' : 'Chọn để xóa'}
  >
    {deleteMode ? '✕ Hủy' : '🗑'}
  </button>
)}
```

In each list item, when `deleteMode=true`:
```tsx
{deleteMode && (
  <input
    type="checkbox"
    checked={selectedIds.has(item.id)}
    onChange={(e) => {
      setSelectedIds(prev => {
        const next = new Set(prev);
        e.target.checked ? next.add(item.id) : next.delete(item.id);
        return next;
      });
    }}
    onClick={(e) => e.stopPropagation()}  // don't select the item
    className="mr-2 accent-red-500 shrink-0"
  />
)}
```

When `deleteMode=true` and `selectedIds.size > 0`, show a floating confirm bar at bottom of DocList:
```tsx
{deleteMode && selectedIds.size > 0 && (
  <div className="sticky bottom-0 bg-red-50 border-t border-red-200 px-3 py-2 flex items-center justify-between">
    <span className="text-xs text-red-600 font-medium">
      Đã chọn {selectedIds.size} văn bản
    </span>
    <button
      onClick={handleDelete}
      className="px-3 py-1 bg-red-500 text-white text-xs font-medium rounded hover:bg-red-600 transition"
    >
      🗑 Xóa {selectedIds.size} mục
    </button>
  </div>
)}
```

Delete handler:
```tsx
const handleDelete = async () => {
  if (!window.confirm(`Xóa ${selectedIds.size} văn bản? Không thể hoàn tác!`)) return;
  try {
    const res = await fetch('/api/admin/documents', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ ids: Array.from(selectedIds), source: tab === 'vanban' ? 'documents' : 'cong_van' })
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Đã xóa ${data.count} văn bản`);
      setDeleteMode(false);
      setSelectedIds(new Set());
      onBulkDelete?.(Array.from(selectedIds), tab === 'vanban' ? 'documents' : 'cong_van');
      // Trigger refetch in parent
    }
  } catch (e) {
    alert('Lỗi khi xóa');
  }
};
```

### In `HomePage.tsx`:

Pass `isAdmin={auth.user?.role === 'admin'}` to DocList.

When `onBulkDelete` fires, call `setPage(1)` and clear `selectedItem` if it was deleted, then refetch.

---

## UX Notes

- Delete mode only visible to admin (check `auth.user?.role === 'admin'`)
- Works for both tab Văn bản (source=documents) and tab Công văn (source=cong_van)
- Confirmation dialog before delete — no undo
- After delete: list refreshes, delete mode exits automatically
- Select All: add a "☑ Tất cả" button in the confirm bar for convenience

---

## Do NOT change

- Search, filter, pagination logic
- Non-admin users see nothing different
- Any backend logic unrelated to delete

---

*Brief by Thanh AI — 2026-03-26*
