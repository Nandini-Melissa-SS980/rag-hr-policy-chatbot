# One tool, rewritten: docstring as prompt, error as a way out

`get_policy_version` on **my own server** (`mcp_servers/policy_server.py`).

Same failing call both times:
`get_policy_version(effective_date="2023-01-01")` - a date earlier than any edition in the index.

Question behind the call: *What notice period applied under the policy in force on 2023-01-01?*

> The transcripts come from a deterministic stand-in, not a live model: there are still no API credits. It recovers when the payload names a next step and cannot when it does not, so the comparison is about the payload - the thing being changed - and not about model luck. `--live` runs the same script against the real model.

---

### Before

**Tool description the model was given (this is the prompt):**

```
Gets policy version.
```

**Transcript**

```
-> tools/call get_policy_version {"effective_date": "2023-01-01"}
<- {"error": "Error 3"}

   model: The lookup failed with 'Error 3'. I cannot tell whether that version is missing or the server is down. The current notice period is 30 days.

```

- recovered: **False**
- quoted a figure it could not support: **True**

---

### After

**Tool description the model was given (this is the prompt):**

```
Find which edition of the handbook was in force on a given date.

Use this before quoting a figure for anything historical - an appraisal or a dispute about last year - so the answer quotes the edition that actually applied then.

Args:
    effective_date: The date the answer has to be correct for, as YYYY-MM-DD, for example "2024-06-01".
```

**Transcript**

```
-> tools/call get_policy_version {"effective_date": "2023-01-01"}
<- {"error": "no_version_effective", "message": "No policy version effective 2023-01-01: the earliest edition in the index is 2024-04-01. Nothing before that date has been digitised, so no figure can be quoted for it.", "earliest_effective_date": "2024-04-01", "recoverable": true, "retry_with": {"effective_date": "2024-04-01"}}

   model: That edition does not exist. The earliest is 2024-04-01 - re-asking for that date, and I will tell the user the figure cannot be quoted for 2023.

-> tools/call get_policy_version {"effective_date": "2024-04-01"}
<- {"version": "2024.1", "effective_date": "2024-04-01"}

   model: The edition in force was 2024.1.

```

- recovered: **True**
- quoted a figure it could not support: **False**

---

## What changed, and why it mattered

**The docstring.** `Gets policy version.` tells the model the tool exists and nothing about when to reach for it. The rewrite says what the tool is for, *when to use it* (before quoting anything historical), and what the argument looks like - with an example. That text is not a comment: it is shipped over `tools/list` as the tool's `description` and it is the only thing the model reads when deciding whether to call it. It is a prompt, so it is written like one.

**The error.** `Error 3` is indistinguishable from an outage, so the model cannot tell *this version does not exist* from *the server is down* - and, having no way to act, it answers anyway and quotes a current figure for a 2023 question. The rewrite names the cause, gives the earliest date that does exist, and marks itself recoverable with the argument to retry. The model re-asks, gets a real answer, and tells the user the 2023 figure cannot be quoted.

The difference is not politeness. A bare code produced a confident wrong answer; a described failure produced a correct refusal plus a successful second call.
