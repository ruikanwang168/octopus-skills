# Page Task Execution Template

> 用途：每次执行一个页面任务时使用。  
> 原则：本轮只生成一个页面或一个小模块。

---

## 1. Current Task

| Field | Content |
|---|---|
| Task ID |  |
| Function Module |  |
| Page Name |  |
| Page Type |  |
| Source Section |  |
| Source Type |  |
| Previous Page |  |
| Trigger Operation |  |
| Next Page |  |
| Core Components |  |
| Key Fields |  |
| Required Route | Yes / No |
| Suggested File Path |  |
| Status Before Execution |  |

---

## 2. Execution Requirements

1. Only generate this page or small module.
2. Do not generate other pages not assigned to this task.
3. Ensure navigation from the previous page if needed.
4. Ensure navigation to the next page if needed.
5. Add or update route if required.
6. Add or update mock data if required.
7. Use placeholder content only when information is missing, and record it.
8. After generation, update `prototype-index.md`.
9. After generation, update `prototype-generation-log.md`.

---

## 3. Generated Result

| Item | Content |
|---|---|
| Generated files |  |
| Updated files |  |
| Routes added / updated |  |
| Components added / updated |  |
| Mock data added / updated |  |
| Run / preview status |  |

---

## 4. Task Status Update

| Field | Content |
|---|---|
| New Status | Completed / Needs Fix / Needs Confirmation / Needs Input |
| Check Result |  |
| Notes |  |

---

## 5. Next Suggested Task

| Field | Content |
|---|---|
| Next Task ID |  |
| Next Page Name |  |
| Reason |  |
