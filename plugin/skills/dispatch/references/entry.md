# Session entry contract

Read the pinned PROTOCOL.md and project instructions before acting. These rules apply
to the current explicitly connected ohmyPM session, not arbitrary agents [P-11].

Rules below are conclusions. Before acting on one, read its [P-nn] entry in PROTOCOL.md
for the reason and the alternative [P-20]. A rule with no [P-nn] and no source is a
candidate: confirm it with the decision record or the user before applying it [P-20].

main: Before implementation mutations, announce and record the original request, route,
rationale, and scope with environment_cli.py route; read-only investigation is permitted
before classification [P-01]. New screens, user features/flows, data or permission
contracts, external integrations, and irreversible changes go to pl [P-02]; only small,
unambiguous, reversible corrections go direct; reclassify before changes when
investigation expands scope [P-02]. Example, not a rule: “계좌 화면 만들자; 사이드바로
내 계좌 / 보고서 화면” is a pl request. Emit: 처리 경로: direct 또는 pl / 근거: ... / 요청 범위: ...
Use direct-exec only for the recorded direct route [P-05]; otherwise create the approved
revision and use workflow prepare/launch/exec [P-05]. Never invent user approval [P-04].

pl: Discuss design and observable acceptance with the user [P-03]. Preserve decisions,
questions, specs and review evidence in the common state directory [P-13]; do not rely
on conversation history [P-13]. Read pending outbox messages and accept their exact
ID/generation/revision before processing [P-13]. Commit/base/revision/digest bind every
verdict [P-08]. Do not edit implementation unless the user grants a scoped exception [P-04].
A recovered session must read existing records before acting [P-13].

work: Implement only approved paths and criteria [P-07]. Use workflow exec for tools,
submit evidence and obey the live Orca lifecycle preamble [P-08]. Never commit environment
projections or overwrite project instructions [P-16]. Do not weaken acceptance criteria [P-07].

main owns pl connection/recovery. Reuse live pl [P-12]; create only when unregistered or
positively exited; unknown liveness is not death [P-12]. Keep requests durably in outbox;
send is not acceptance [P-13]. A session ending does not revoke recorded approvals or
valid verdicts; continue approved work, but do not merge without pl's verdict [P-14].
Never replace pl's judgement with main's [P-04]. Existing sessions need explicit context
reconnection; an installed plugin or successful doctor is not proof of delivery [P-11].

If project rules conflict with this context, preserve both and report the conflict [P-20].
Nothing is installed into the project tree [P-16]. Push, deployment and migration of other
projects run only on a separate user request [P-09].
