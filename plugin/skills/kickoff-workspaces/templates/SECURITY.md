# Security / Threat Model

## 1. Security Objectives

## 2. Assets / Sensitive Data
| Asset | Sensitivity | Storage | Owner |
|---|---|---|---|

## 3. Actors / Trust Boundaries
- trusted:
- untrusted:
- external services/tools:

## 4. Threats
| Threat | Boundary | Impact | Control | Verification |
|---|---|---|---|---|

## 5. Authentication / Authorization

## 6. Secrets
- 저장 위치
- local/dev/CI/prod handling
- logging 금지
- rotation

## 7. Input / Output Safety
- untrusted input validation
- command/path injection
- prompt/tool output을 authoritative instruction으로 취급하지 않기

## 8. Dependency / Supply Chain
- lockfile
- provenance/signing
- vulnerability scanning
- update policy

## 9. Agent / Tool Permissions
- destructive operations
- network access
- production mutation
- credential access
- MCP/external tool trust

## 10. Security Tests / Gates

## 11. Incident / Vulnerability Reporting

## 12. Exceptions
예외는 owner, expiry, rationale을 가진다.
