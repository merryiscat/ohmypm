# Deployment / Operations Runbook

## 1. Service / Component
- owner:
- environment:
- dependencies:

## 2. Deployment Preconditions
- required checks
- migration readiness
- rollback readiness

## 3. Deploy
```bash
<deploy-command>
```

## 4. Post-Deploy Verification
- health
- metrics
- logs
- critical user flow

## 5. Configuration / Secrets
canonical location과 변경 절차를 명시한다.

## 6. Observability / SLO
| Signal | Target | Alert | Dashboard |
|---|---|---|---|

## 7. Rollback
```bash
<rollback-command>
```
- data migration rollback 가능 여부
- irreversible step

## 8. Common Incidents
### 증상: <...>
- 확인:
- 원인 후보:
- 안전한 완화:
- escalation:

## 9. Backup / Restore

## 10. Migration

## 11. Ownership / Escalation

## 12. Postmortem / Follow-up
Runbook에서 발견한 durable architecture/requirement 변경은 해당 canonical 문서로 반영한다.
