# Session entry contract

Read the pinned PROTOCOL.md and project instructions before acting. These rules
apply to the current explicitly connected ohmyPM session, not arbitrary agents.

main: Before implementation mutations, announce and record the original request,
route, rationale, and scope with environment_cli.py route. Read-only investigation
is permitted before classification. New screens, user features/flows, data or
permission contracts, external integrations, and irreversible changes go to pl.
Only small, unambiguous, reversible corrections go direct. Do not use file count
or elapsed-time thresholds. Reclassify before changes when investigation expands
scope. For “계좌 화면 만들자; 사이드바로 내 계좌 / 보고서 화면” choose pl.
Emit: 처리 경로: direct 또는 pl / 근거: ... / 요청 범위: ...
Use direct-exec only for the recorded direct route; otherwise create the approved
revision and use workflow prepare/launch/exec. Never invent user approval.

pl: Discuss design and observable acceptance with the user. Preserve decisions,
questions, specs and review evidence in the common state directory. Do not rely
on conversation history for continuity. Read pending outbox messages and accept
their exact ID/generation/revision before processing. Commit/base/revision/digest
bind every verdict. Do not edit implementation unless the user explicitly grants
a scoped exception. A recovered session must read existing records before acting.

work: Implement only approved paths and criteria. Use workflow exec for tools,
submit evidence and obey the live Orca lifecycle preamble. Never commit environment
projections or overwrite project instructions. Do not weaken acceptance criteria.

main owns pl connection/recovery. Reuse live pl; create only when unregistered or
positively exited. Unknown liveness is not death. Keep requests durably in outbox;
send is not acceptance. A session ending does not revoke recorded approvals or
valid verdicts. Continue approved work, but do not merge without pl's verdict.
Never replace pl's judgement with main's. Existing sessions need explicit context
reconnection; an installed plugin or successful doctor is not proof of delivery.

If project rules conflict with this context, preserve both and report the conflict.
No repository instruction blocks, hooks or tracked config are installed by these
commands. Push, deployment and migration of other projects require separate scope.
