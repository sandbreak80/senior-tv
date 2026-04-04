---
name: Bug Report
about: Something isn't working right
title: ''
labels: bug
assignees: ''
---

**What happened?**
A clear description of the bug.

**What did you expect?**
What should have happened instead.

**Steps to reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Environment**
- Hardware: [e.g., GMKtec NucBox K11]
- OS: [e.g., Ubuntu 24.04]
- Browser: [Chrome kiosk / remote admin on phone]

**Health check output**
```
curl -s http://localhost:5000/api/health | python3 -m json.tool
```

**Logs (if relevant)**
```
journalctl -u senior-tv --since "1 hour ago" --no-pager | tail -50
```
