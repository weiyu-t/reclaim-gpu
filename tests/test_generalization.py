"""Independent small datasets: no MIT IDs, expected totals, or detector outputs."""
import asyncio
import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import data_loader as loader
from reclaim.analysis import analysis
from reclaim.main import app
from reclaim.research import research
from reclaim import investigator as inv


def job(jid=1, uid=1, **values):
    row = dict(id_job=jid, id_user=uid, state_name='COMPLETED', is_success=True,
               gpu_hours=2., gpu_hours_alloc=2., gpu_count=1, walltime_sec=7200., attempts=1,
               sm_util_avg=90., sm_util_max=100., job_type='BATCH', time_submit=0.,
               time_start=1., time_end=7201., exit_code=0, id_array_job=0,
               is_array_task=False, hit_node_failure=False, nodefail_attempts=0, wait_sec=1., Node='node-clear')
    row.update(values)
    return row


def finding(node='node-amber', **metadata):
    return dict(id='finding-arbitrary', integrationId='test', enterpriseId='test',
                detectorId='rules::node-hardware-fault', shortDescription='Candidate only',
                longDescription='Candidate only', impactDescription='', resourceIds=[], rootCauses=[],
                status='OPEN', severity='HIGH', confidence='HIGH', category='AVAILABILITY',
                priority='HIGH', detectionTime='2030-01-01T00:00:00Z', isActive=True,
                metadata=dict(node=node, window_start='1970-01-01T00:00:00Z',
                              window_end='1970-01-15T00:00:00Z', exit_status=135, **metadata))


def write_dataset(root, rows, findings=None, **metadata):
    prep, syn = root/'prepped', root/'synthetic'
    prep.mkdir(parents=True, exist_ok=True); syn.mkdir(exist_ok=True)
    frame = pd.DataFrame(rows) if rows else pd.DataFrame([job()]).iloc[:0]
    frame.drop(columns=['Node']).to_parquet(prep/'jobs.parquet', index=False)
    cards = pd.DataFrame(dict(id_job=frame.id_job, Node=frame.Node, gpu_id=0, gpu_hours=frame.gpu_hours,
                              smutilization_pct_avg=frame.sm_util_avg, smutilization_pct_max=frame.sm_util_max,
                              mem_used_frac=.1, pcierxbandwidth_megabytes_avg=0., pcietxbandwidth_megabytes_avg=0.))
    cards.to_parquet(prep/'gpus.parquet', index=False)
    pd.DataFrame(columns=['id','type','name','resourceId']).to_parquet(syn/'resources.parquet', index=False)
    pd.DataFrame(columns=['sourceId','destinationId','relationshipType']).to_parquet(syn/'edges.parquet', index=False)
    (syn/'findings.json').write_text(json.dumps(findings or []))
    (root/'dataset.json').write_text(json.dumps(dict(name='Independent test cluster', epoch_offset=0, gpus_per_node=4, **metadata)))


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    monkeypatch.setenv('RECLAIM_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(loader, '_current', None)
    monkeypatch.setattr(inv, 'ROOT', tmp_path)
    monkeypatch.setattr(inv, 'settings', lambda: dict(key='', url='https://example.test', model='test'))
    token = loader.snapshot_context.set(None)
    yield tmp_path
    loader.snapshot_context.reset(token)


@pytest.mark.parametrize('rows,count,ids', [
    ([], 0, []),
    ([job()], 0, []),
    ([job(sm_util_avg=0., sm_util_max=0.)], 1, ['cpu-placement']),
    ([job(sm_util_avg=2., job_type='LLSUB:INTERACTIVE', walltime_sec=36000., gpu_hours=10., gpu_hours_alloc=10.)], 1, ['idle-sessions']),
    ([job(sm_util_avg=0., sm_util_max=0.), job(2, sm_util_avg=2., job_type='LLSUB:INTERACTIVE', walltime_sec=36000., gpu_hours=10., gpu_hours_alloc=10.)], 2, ['cpu-placement','idle-sessions']),
])
def test_recommendations_follow_new_records_and_empty_endpoints(dataset, rows, count, ids):
    write_dataset(dataset, rows)
    with TestClient(app) as c:
        o = c.get('/api/reclaim/overview').json()
        assert o['decision']['action_count'] == count
        assert {a['id'] for a in o['actions']} == set(ids)
        assert o['dataset']['name'] == 'Independent test cluster'
        assert o['sample']['jobs'] == len(rows)
        if not count:
            assert o['recovery']['point'] == 0
            assert 'No supported' in o['decision']['title']
        for endpoint in ['claims','node-audit','card-imbalance','scenario','drain-scenario','causal-case','trial-shortlist']:
            response = c.get('/api/reclaim/'+endpoint)
            assert response.status_code == 200, (endpoint, response.text)
        assert c.get('/api/reclaim/causal-case').json() is None
        assert c.get('/api/reclaim/node-audit').json()['cases'] == []
        assert c.get('/api/reclaim/card-imbalance').json()['examples'] == []
        if 'cpu-placement' not in ids:
            assert not c.post('/api/reclaim/trial-plan', json={}).json()['eligible']
            assert c.post('/api/reclaim/trial-brief', json={}).status_code == 422


def multi_machine_rows():
    rows = []
    for uid in range(1, 7):
        for n in range(10):
            rows.append(job(len(rows)+1, uid, Node='node-amber' if uid < 4 else 'node-violet',
                            state_name='FAILED', is_success=False, exit_code=135*256))
            rows.append(job(len(rows)+1, uid, Node='node-clear'))
    return rows


def test_raw_records_discover_multiple_hardware_candidates_without_findings(dataset):
    write_dataset(dataset, multi_machine_rows())
    with TestClient(app) as c:
        data = c.get('/api/reclaim/node-audit').json()
        assert {x['node'] for x in data['cases'] if x['cause'] == 'hardware'} == {'node-amber','node-violet'}
        assert all(x['hardware']['supported_users'] == 3 for x in data['cases'])
        assert data['baseline']['includes_hardware_node'] is False
        for e in data['episodes']:
            assert e['finding_id'] is None
            r = c.get('/api/reclaim/drain-scenario', params={'evidence_id':e['evidence_id'], 'nodes':1, 'duration':2}).json()
            assert r['available'] and r['node'] == e['node']
            assert r['unavailable_gpu_hours'] == 8  # metadata says four GPUs, not the MIT width
        assert c.get('/api/reclaim/drain-scenario?evidence_id=unknown').json()['available'] is False
        claims = c.get('/api/reclaim/claims').json()
        assert len(claims['node_triage']) == 2
    trace, obs = asyncio.run(inv.collect('node-audit', 2.5))
    assert [t['tool'] for t in trace] == ['decision_evidence','list_rules']
    assert obs['decision_evidence']['hardware']['supported']
    text = inv.final_brief(json.dumps(dict(recommendation='Inspect the machine.', downside='Capacity becomes unavailable.',
                           pilot='Run controlled checks.', finding_id=obs['decision_evidence']['evidence_id'])), obs)
    assert 'Evidence reference: `raw/' in text


def test_stale_hardware_finding_cannot_override_raw_records(dataset):
    rows = multi_machine_rows()
    for row in rows:
        row['exit_code'] = 0
    write_dataset(dataset, rows, [finding()])
    with TestClient(app) as c:
        audit = c.get('/api/reclaim/node-audit').json()
        assert audit['hardware'] is None
        assert audit['rejected_hardware_findings'] == ['finding-arbitrary']
        assert all(x['cause'] == 'cannot_determine' for x in audit['cases'])
        assert not c.get('/api/reclaim/drain-scenario').json()['available']
        assert c.get('/api/reclaim/claims').status_code == 200
    result = asyncio.run(inv.investigate('node-audit', 2.5))
    assert result['mode'] == 'evidence-only' and result['attempts'] == []
    assert 'No machine-specific episode' in result['text']


def test_unknown_node_and_malformed_episode_are_reported_without_crashing(dataset):
    missing = finding(node='node-not-in-telemetry')
    malformed = finding(); malformed['id'] = 'bad-date'; malformed['metadata']['window_start'] = 'bad-date'
    write_dataset(dataset, [job()], [missing, malformed])
    with TestClient(app) as c:
        audit = c.get('/api/reclaim/node-audit').json()
        assert set(audit['rejected_hardware_findings']) == {'finding-arbitrary','bad-date'}
        assert c.get('/api/reclaim/claims').status_code == 200


def test_array_discovery_does_not_require_precomputed_findings(dataset):
    rows = [job(n+1, 99, Node='west' if n % 2 else 'east', state_name='FAILED', is_success=False,
                exit_code=256, is_array_task=True, id_array_job=900) for n in range(12)]
    write_dataset(dataset, rows)
    with TestClient(app) as c:
        case = c.get('/api/reclaim/causal-case').json()
        assert (case['tasks'],case['nodes'],case['replicated']) == (12,2,True)
        assert case['finding_id'] is None and case['evidence_id'] == 'raw/array/99/900'
    result = asyncio.run(inv.investigate('causal-case',2.5))
    assert '12 failed tasks' in result['text']


def test_reload_is_atomic_changes_results_and_invalidates_mcp_cache(dataset):
    write_dataset(dataset, [job(sm_util_avg=0., sm_util_max=0.)])
    with TestClient(app) as c:
        before = c.get('/api/reclaim/overview').json()
        old_snapshot = loader.store()
        original_brief = asyncio.run(inv.investigate('cpu-placement',2.5))
        assert '1 jobs' in original_brief['text']
        write_dataset(dataset, [job()])
        # A snapshot stays stable until explicitly reloaded.
        assert c.get('/api/reclaim/overview').json()['dataset']['revision'] == before['dataset']['revision']
        assert c.post('/api/reclaim/dataset/reload').status_code == 200
        after = c.get('/api/reclaim/overview').json()
        assert after['decision']['action_count'] == 0
        assert after['dataset']['revision'] != before['dataset']['revision']
        new_brief = asyncio.run(inv.investigate('cpu-placement',2.5))
        assert not new_brief['cached'] and 'No eligible' in new_brief['text']
        # Existing requests can finish on their old, internally consistent snapshot.
        token = loader.snapshot_context.set(old_snapshot)
        try: assert analysis().overview()['decision']['action_count'] == 1
        finally: loader.snapshot_context.reset(token)
        pd.DataFrame({'wrong':[1]}).to_parquet(dataset/'prepped/jobs.parquet')
        failed = c.post('/api/reclaim/dataset/reload')
        assert failed.status_code == 422 and 'previous snapshot retained' in failed.text
        assert c.get('/api/reclaim/overview').json()['dataset']['revision'] == after['dataset']['revision']


def test_no_evidence_skips_model_even_when_key_is_configured(dataset, monkeypatch):
    write_dataset(dataset, [job()])
    monkeypatch.setattr(inv, 'settings', lambda: dict(key='test-only', url='https://example.test', model='test'))
    for action in ['cpu-placement','idle-sessions','node-audit','causal-case']:
        result = asyncio.run(inv.investigate(action,2.5))
        assert result['attempts'] == [] and result['mode'] == 'evidence-only'
        assert 'no model call' in result['note']


def test_selected_machine_mcp_context_and_cache_follow_evidence_id(dataset):
    write_dataset(dataset, multi_machine_rows())
    episodes = research().episodes
    results = []
    for episode in episodes:
        eid = episode['evidence_id']
        trace, obs = asyncio.run(inv.collect('node-audit', 2.5, eid))
        assert obs['decision_evidence']['hardware']['node'] == episode['node']
        assert obs['decision_evidence']['drain']['node'] == episode['node']
        assert trace[0]['arguments']['evidence_id'] == eid
        result = asyncio.run(inv.investigate('node-audit', 2.5, eid))
        assert not result['cached']
        results.append(result)
    assert len(results) == 2
    assert research().hardware['hours'] < 3  # last window stops at actual observations, not 14 days


def test_empty_api_summaries_and_missing_rule_coverage(dataset):
    write_dataset(dataset, [])
    with TestClient(app) as c:
        for path in ['efficiency/summary','waste/breakdown','queue/latency','scaling/efficiency']:
            response = c.get('/v1/'+path)
            assert response.status_code == 200, response.text
        rules = c.get('/api/reclaim/rules').json()['rules']
        assert rules and all(r['status'] == 'UNKNOWN' for r in rules)
        assert c.get('/v1/price-book').json()['epoch_offset'] == 0


def test_zero_allocated_time_is_not_divided_by_zero(dataset):
    write_dataset(dataset, [job(gpu_hours=0., gpu_hours_alloc=0.)])
    with TestClient(app) as c:
        for path in ['overview','claims','scenario','node-audit','card-imbalance']:
            response = c.get('/api/reclaim/'+path)
            assert response.status_code == 200, response.text
            assert 'NaN' not in response.text and 'Infinity' not in response.text
