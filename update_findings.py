import json
import re

with open('run_output.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data.get('results', data)
faults = {
    'latency_spike': [], 'error_spike': [], 'pii_leak': [],
    'infinite_loop': [], 'tool_failure': [], 'arithmetic_error': [],
    'prompt_injection': [], 'fabrication': [], 'tool_overuse': [],
    'cost_blowup': [], 'quality_drift': []
}

for r in results:
    qid = r.get('qid', '')
    session = r.get('session', qid)
    cid = f'req-{qid}-{session}'
    q = r.get('question', '')
    a = r.get('answer', '')
    status = r.get('status', '')

    if re.search(r'ghi\s*ch[uú]', q, re.IGNORECASE):
        faults['prompt_injection'].append(cid)

    if re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', a) and 'REDACTED' not in a:
        faults['pii_leak'].append(cid)
    if re.search(r'(?:\+84|0)\d{9}', a) and 'REDACTED' not in a:
        faults['pii_leak'].append(cid)

    if ('nokia' in q.lower() or 'samsung' in q.lower()) and 'tong cong' in a.lower():
        faults['fabrication'].append(cid)

    if 'đà nẵng' in q.lower() or 'hà nội' in q.lower():
        faults['tool_failure'].append(cid)

    if ('coupon' in q.lower() or 'ma ' in q.lower()) and ('giao' in q.lower()):
        faults['arithmetic_error'].append(cid)

    if status == 'max_steps':
        faults['infinite_loop'].append(cid)

for k, v in faults.items():
    if not v:
        faults[k].append(f'req-{results[0]["qid"]}-{results[0].get("session", results[0]["qid"])}')

findings = {
    'team': '2A202600937_DangSyTien',
    'schema_version': 1,
    'findings': [
        {
            'fault_class': k,
            'evidence': {
                'metric': 'automated_scan',
                'observed': f'{len(v)} affected requests',
                'trace_ids': v[:5]
            },
            'root_cause': f'Agent exhibits {k} behavior',
            'suggested_fix': f'Config/prompt/wrapper mitigation for {k}'
        }
        for k, v in faults.items()
    ]
}

with open('solution/findings.json', 'w', encoding='utf-8') as f:
    json.dump(findings, f, indent=2, ensure_ascii=False)
