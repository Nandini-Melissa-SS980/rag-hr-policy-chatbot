# Tools discovered, before and after

Both counts come from `tools/list` at run time - the client asks each server what it has and counts the replies. Nothing here is read from a list in the code.

**2 before -> 4 after.**

| Stage | Servers | Tools | Names |
| --- | --- | --- | --- |
| Before | policy | 2 | `policy__search_handbook`, `policy__get_policy_version` |
| After | hris, policy | 4 | `policy__search_handbook`, `policy__get_policy_version`, `hris__get_leave_balance`, `hris__get_grade_band` |

Grouped by the server each came from:

```json
{
  "policy": [
    "search_handbook",
    "get_policy_version"
  ],
  "hris": [
    "get_leave_balance",
    "get_grade_band"
  ]
}
```

The two new tools arrived from the HRIS server after an eight-line addition to `mcp_servers.json`. No Python was edited - see `agent_diff.txt`.

## One query that provably calls the new server

> How many days of annual leave does employee HR-1002 have left, and what does the policy say the full-time entitlement is?

```
[ 1] think        lap 1: asking the model what to do next
[ 2] tool_call    hris__get_leave_balance({"employee_id": "HR-1002"})
[ 3] observation  {"employee_id": "HR-1002", "accrued_leave_days": 7.0, "leave_year_ends": "2026-12-31"}
[ 4] think        lap 2: asking the model what to do next
[ 5] tool_call    policy__search_handbook({"query": "annual leave entitlement full-time employees"})
[ 6] observation  {"query": "annual leave entitlement full-time employees", "passages": [{"policy_id": "HR-202", "section": "2.1", "score": 0.8699, "text": "2.1 Entitlement\nFull-time employees receive twenty-five days
[ 7] think        lap 3: asking the model what to do next
[ 8] answer       model returned a final answer
```

Tools invoked: `hris__get_leave_balance`, `policy__search_handbook`

From the new server: `hris__get_leave_balance`

Answer: HR-1002 has 7.0 days of accrued leave remaining. The handbook grants full-time employees twenty-five days per leave year.

> The model here is a scripted stand-in (no API credits). It proves the plumbing - a tool discovered from the HRIS server is selected by name and invoked through the unchanged agent loop - not that a real model would choose well. `--live` runs the same path against the real model.
