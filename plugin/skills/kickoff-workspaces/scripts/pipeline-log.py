#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""파이프라인 로그 — 자리끼리 주고받은 원문을 그대로 남기고 토큰·대기시간을 집계한다.

왜 보내는 통로를 감싸는가: 보내고 나서 따로 적게 하면 바쁠 때 빠진다.
`send`가 로그를 먼저 쓰고 그다음에 보내므로, 로그 없이 전달되는 경로가 없다.
덤으로 긴 지시를 argv에 싣지 않게 된다 — 2026-09-19에 큰따옴표가 인자를 쪼갠 실측(argv 함정 네 번째 변종).

저장처: <프로젝트>/logs/pipeline/T-NNN.jsonl (한 줄에 기록 하나).
그 폴더에 `*`만 담은 .gitignore를 같이 만들어 스스로를 무시한다 —
프로젝트 .gitignore를 건드리지 않고도 원문이 커밋되지 않는다(PC 고유 값 유출 항체).

`--model`은 그 자리가 **실제로 돌고 있는 모델**을 적는 칸이다 — roles.md에 적힌 이름도, 터미널 배너에
뜬 이름도 설정값이지 가용성이 아니다(2026-09-19 오독 실측). 소진으로 내려갔으면 내려간 모델을 적는다.

사용:
  pipeline-log.py send   --task T-005 --to pl --terminal <handle> --file docs/_ask/T-005.md [--stage 스펙v1지시] [--model gpt-6-astra]
  pipeline-log.py recv   --task T-005 --from pl --file docs/tasks/T-005-design-loop.md [--stage 스펙v1]
  pipeline-log.py usage  --task T-005 --role pl --raw "Token usage: total=76,449 input=70,580 (+ 367,872 cached) output=5,869"
  pipeline-log.py note   --task T-005 --text "사용자 게이트 승인" [--role user]
  pipeline-log.py report --task T-005
"""
import argparse, io, json, os, re, subprocess, sys, time

# 윈도우 콘솔은 기본이 cp949라 한글·줄표(—)에서 UnicodeEncodeError가 난다.
# 기록은 항상 UTF-8로 쓰므로, 출력 쪽만 맞춰 준다(2026-09-19 실측).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8')
    except Exception:
        pass


def root():
    r = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                       capture_output=True, text=True, encoding='utf-8')
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else os.getcwd()


def logdir():
    d = os.path.join(root(), 'logs', 'pipeline')
    if not os.path.isdir(d):
        os.makedirs(d)
    g = os.path.join(d, '.gitignore')
    if not os.path.exists(g):                      # 스스로를 무시하는 폴더
        io.open(g, 'w', encoding='utf-8', newline='\n').write('*\n')
    return d


def logpath(task):
    return os.path.join(logdir(), '%s.jsonl' % task)


def read(p):
    with io.open(p, encoding='utf-8-sig') as f:
        return f.read()


def est_tokens(s):
    """추정 토큰. tiktoken이 있으면 실제 토큰화, 없으면 글자 수 기반 근사.
    한글은 글자당 토큰이 영어보다 크다 — 한글 비율로 계수를 가른다."""
    try:
        import tiktoken
        return len(tiktoken.get_encoding('o200k_base').encode(s)), 'tiktoken'
    except Exception:
        han = sum(1 for c in s if '가' <= c <= '힣')
        ratio = han / max(len(s), 1)
        return int(len(s) / (1.1 if ratio > 0.3 else 3.5)), '근사'


def append(task, rec):
    rec['시각'] = time.strftime('%Y-%m-%d %H:%M:%S')
    p = logpath(task)
    prev = None
    if os.path.exists(p):
        lines = [l for l in read(p).splitlines() if l.strip()]
        if lines:
            try:
                prev = json.loads(lines[-1])
            except Exception:
                prev = None
    rec['왕복'] = (prev.get('왕복') or 0) + 1 if prev else 1
    if prev and prev.get('시각'):
        a = time.mktime(time.strptime(prev['시각'], '%Y-%m-%d %H:%M:%S'))
        b = time.mktime(time.strptime(rec['시각'], '%Y-%m-%d %H:%M:%S'))
        rec['직전_기록으로부터_초'] = int(b - a)
    with io.open(p, 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return rec


def body(path):
    """원문과 크기. 파일이 없으면 그 사실을 기록에 남긴다 — 조용히 넘어가지 않는다."""
    if not path or not os.path.exists(path):
        return None, {'원문': None, '글자': 0, '토큰_추정': 0, '주': '파일 없음: %s' % path}
    s = read(path)
    t, how = est_tokens(s)
    return s, {'경로': path.replace('\\', '/'), '원문': s, '글자': len(s),
               '토큰_추정': t, '추정_방법': how}


def cmd_send(a):
    _, meta = body(a.file)
    rec = {'방향': 'main->%s' % a.to, '단계': a.stage or '지시', '종류': '지시서',
           '모델': a.model or '미기록'}
    rec.update(meta)
    append(a.task, rec)
    text = '%s 파일을 읽고 거기 적힌 대로 수행하라.' % a.file.replace('\\', '/')
    if not a.terminal:
        print('기록만 함(터미널 없음): %s' % a.file)
        return 0
    r = subprocess.run(['orca', 'terminal', 'send', '--terminal', a.terminal,
                        '--enter', '--wait-submit', '10', '--json', '--text', text],
                       capture_output=True, text=True, encoding='utf-8')
    ok = '"accepted": true' in (r.stdout or '')
    print('보냄: %s -> %s (%s)' % (a.file, a.to, '수락' if ok else '실패'))
    if not ok:
        print((r.stdout or r.stderr or '')[:400], file=sys.stderr)
        return 1
    return 0


def cmd_recv(a):
    _, meta = body(a.file)
    rec = {'방향': '%s->main' % getattr(a, 'from'), '단계': a.stage or '산출물', '종류': '산출물',
           '모델': a.model or '미기록'}
    rec.update(meta)
    r = append(a.task, rec)
    print('받음: %s (%d자, 토큰 %s %d)' % (a.file, meta['글자'],
                                          meta.get('추정_방법', ''), meta.get('토큰_추정', 0)))
    if r.get('직전_기록으로부터_초') is not None:
        print('  직전 기록으로부터 %d초' % r['직전_기록으로부터_초'])
    return 0


USAGE_RE = re.compile(
    r'total=([\d,]+).*?input=([\d,]+)(?:\s*\(\+\s*([\d,]+)\s*cached\))?.*?output=([\d,]+)', re.S)


def cmd_usage(a):
    m = USAGE_RE.search(a.raw)
    n = lambda s: int(s.replace(',', '')) if s else 0
    rec = {'방향': '%s 결산' % a.role, '단계': '토큰 실측', '종류': '사용량', '원문': a.raw,
           '모델': a.model or '미기록'}
    if m:
        rec['토큰_실측'] = {'합계': n(m.group(1)), '입력': n(m.group(2)),
                            '캐시입력': n(m.group(3)), '출력': n(m.group(4))}
    else:
        rec['주'] = '형식을 못 읽었다 — 원문만 남긴다'
    append(a.task, rec)
    print('실측 기록:', rec.get('토큰_실측') or '파싱 실패(원문 보존)')
    return 0


def cmd_note(a):
    append(a.task, {'방향': a.role or 'main', '단계': '메모', '종류': '메모', '원문': a.text,
                    '모델': a.model or '미기록'})
    print('기록:', a.text[:60])
    return 0


def cmd_report(a):
    p = logpath(a.task)
    if not os.path.exists(p):
        print('기록 없음: %s' % p)
        return 1
    recs = [json.loads(l) for l in read(p).splitlines() if l.strip()]
    print('# %s 파이프라인 집계 (%d건)\n' % (a.task, len(recs)))
    print('| # | 시각 | 방향 | 모델 | 단계 | 글자 | 토큰(추정) | 토큰(실측) | 직전으로부터 |')
    print('|---|---|---|---|---|---|---|---|---|')
    tot_est = 0
    meas = {}
    longest = (0, None)
    for i, r in enumerate(recs, 1):
        est = r.get('토큰_추정') or 0
        tot_est += est
        if r.get('토큰_실측'):
            meas[r.get('방향', '')] = r['토큰_실측']
        gap = r.get('직전_기록으로부터_초')
        if gap and gap > longest[0]:
            longest = (gap, r.get('단계'))
        print('| %d | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            i, r.get('시각', ''), r.get('방향', ''), r.get('모델', '미기록'), r.get('단계', ''),
            r.get('글자', '') or '', est or '',
            (r.get('토큰_실측') or {}).get('합계', '') or '미측정',
            ('%d초' % gap) if gap is not None else ''))
    print('\n## 병목')
    print('- 오간 원문 합계(추정): %s 토큰' % format(tot_est, ','))
    for k, v in meas.items():
        cached = v.get('캐시입력') or 0
        ratio = cached / max(v.get('합계', 1), 1)
        print('- %s 실측: 합계 %s (입력 %s + 캐시 %s, 출력 %s) — 캐시 재전송이 합계의 %.1f배' % (
            k, format(v['합계'], ','), format(v['입력'], ','), format(cached, ','),
            format(v['출력'], ','), ratio))
    if longest[1]:
        print('- 가장 긴 공백: %d초 (%s) — 사람이 답을 쥐고 있던 시간이면 그게 병목이다' % longest)
    models = {}
    for r in recs:
        m = r.get('모델')
        if m and m != '미기록':
            models.setdefault(r.get('방향', ''), set()).add(m)
    if models:
        for k, v in models.items():
            print('- %s 가 실제로 돈 모델: %s' % (k, ', '.join(sorted(v))))
    if not models:
        print('- 모델이 한 건도 기록되지 않았다. roles.md는 설정이지 실물의 증거가 아니다'
              ' — send/recv/usage에 --model을 붙여라(protocol 10절)')
    # 자리별로 본다 — 한 자리라도 비면 그 자리의 모델은 모르는 것이다.
    # "한 건도 없을 때만" 경고하면 main 행 하나로 조용히 지나간다(pl2 지적, 2026-09-19).
    blank = {}
    for r in recs:
        if r.get('종류') in ('지시서', '산출물', '사용량') and r.get('모델', '미기록') == '미기록':
            blank[r.get('방향', '')] = blank.get(r.get('방향', ''), 0) + 1
    for k, v in sorted(blank.items()):
        print('- **%s: 모델 미기록 %d건** — 그 자리가 어느 모델로 돌았는지 이 바퀴에서는 알 수 없다' % (k, v))
    if not meas:
        print('- 실측 토큰이 한 건도 없다. 종량 자리는 실측이 필수다(protocol 7절)'
              ' — 태스크 끝에 /status를 걷어라')
    return 0


def main():
    ap = argparse.ArgumentParser(description='파이프라인 로그')
    sub = ap.add_subparsers(dest='cmd')
    s = sub.add_parser('send')
    s.add_argument('--task', required=True); s.add_argument('--to', required=True)
    s.add_argument('--file', required=True); s.add_argument('--terminal'); s.add_argument('--stage')
    s.add_argument('--model', help='이 자리가 실제로 돌고 있는 모델. 화면 배너가 아니라 응답한 모델을 적는다')
    r = sub.add_parser('recv')
    r.add_argument('--task', required=True); r.add_argument('--from', required=True)
    r.add_argument('--file', required=True); r.add_argument('--stage'); r.add_argument('--model')
    u = sub.add_parser('usage')
    u.add_argument('--task', required=True); u.add_argument('--role', required=True)
    u.add_argument('--raw', required=True); u.add_argument('--model')
    n = sub.add_parser('note')
    n.add_argument('--task', required=True); n.add_argument('--text', required=True)
    n.add_argument('--role'); n.add_argument('--model')
    p = sub.add_parser('report'); p.add_argument('--task', required=True)
    a = ap.parse_args()
    if not a.cmd:
        ap.print_help(); return 2
    return {'send': cmd_send, 'recv': cmd_recv, 'usage': cmd_usage,
            'note': cmd_note, 'report': cmd_report}[a.cmd](a)


if __name__ == '__main__':
    os.environ.setdefault('PYTHONUTF8', '1')
    sys.exit(main())
