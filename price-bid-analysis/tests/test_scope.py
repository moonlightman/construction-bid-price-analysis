import copy
import unittest
from test_analysis import sample
from compare_scope import DIMENSIONS, review_scope
from analyze_bids import analyze
from analyze_structure import run

def fixture():
    data = sample()
    data['project']['scope_review_required'] = True
    for bid in data['items'][0]['bids']:
        text = 'DN80 含主材供应与安装 含运输 不另收费'
        bid['construction_content'] = text
        bid['scope_review'] = dict(review_status='confirmed', coverage_confirmed=True,
            reference=dict(kind='tender', text=text, source=dict(file='招标.xlsx', sheet='清单', cell='C2')),
            quoted=dict(text=text, source=bid['source']),
            dimensions=[dict(dimension=k, status='same', reference_evidence=text,
                             quoted_evidence=text, reason='测试两侧对应原文一致') for k in DIMENSIONS])
    return data

class ScopeTests(unittest.TestCase):
    def test_complete_identical_admitted(self):
        r=analyze(fixture()); self.assertTrue(all(x['ranking_eligible'] for x in r['bidder_summary']))
    def test_missing_required_review_rejects(self):
        d=sample();d['project']['scope_review_required']=True
        self.assertFalse(analyze(d)['item_analysis'][0]['eligible_for_comparison'])
    def test_legacy_not_run(self):
        self.assertEqual(analyze(sample())['scope_comparison'][0]['status'],'not_run')
    def test_supply_change_overrides_comparable_and_total_flags(self):
        d=fixture();b=d['items'][0]['bids'][0];s=b['scope_review']
        b['construction_content']=s['quoted']['text']='DN80 主材甲供 仅安装 含运输 不另收费'
        for dim in s['dimensions']:
            dim.update(status='unknown',reason='仍需核对')
        s['dimensions'][1].update(status='different',reference_evidence='含主材供应与安装',quoted_evidence='主材甲供',reason='供材责任变更')
        r=analyze(d)
        self.assertFalse(r['item_analysis'][0]['eligible_for_comparison'])
        self.assertFalse(r['bidder_summary'][0]['ranking_eligible'])
        self.assertEqual(r['bidder_summary'][0]['reconciliation_status'],'一致')
        self.assertEqual(run(d)['item_statistics'][0]['included_bidder_ids'],['B'])
    def test_unknown_blocks(self):
        d=fixture();d['items'][0]['bids'][0]['scope_review']['dimensions'][0]['status']='unknown'
        self.assertFalse(analyze(d)['bidder_summary'][0]['ranking_eligible'])
    def test_missing_dimension_blocks(self):
        d=fixture();d['items'][0]['bids'][0]['scope_review']['dimensions'].pop()
        self.assertFalse(analyze(d)['item_analysis'][0]['eligible_for_comparison'])
    def test_false_evidence_blocks(self):
        d=fixture();d['items'][0]['bids'][0]['scope_review']['dimensions'][0]['quoted_evidence']='伪造原文'
        self.assertFalse(analyze(d)['item_analysis'][0]['eligible_for_comparison'])
    def test_registered_raw_text_mismatch_blocks(self):
        d=fixture();d['items'][0]['bids'][0]['construction_content']='不含安装'
        self.assertFalse(analyze(d)['item_analysis'][0]['eligible_for_comparison'])
    def test_no_locator_blocks(self):
        d=fixture();d['items'][0]['bids'][0]['scope_review']['reference']['source']={}
        self.assertFalse(analyze(d)['item_analysis'][0]['eligible_for_comparison'])
    def test_all_na_blocks(self):
        d=fixture()
        for x in d['items'][0]['bids'][0]['scope_review']['dimensions']:x['status']='not_applicable'
        self.assertFalse(analyze(d)['item_analysis'][0]['eligible_for_comparison'])
    def test_equivalent_wording_requires_evidence_and_reason(self):
        d=fixture();b=d['items'][0]['bids'][0];b['construction_content']='DN80 含运输及供材安装 无另计费用'
        b['scope_review']['quoted']['text']=b['construction_content']
        for x in b['scope_review']['dimensions']:
            x.update(status='equivalent', quoted_evidence=b['construction_content'], reason='仅为合成测试中的经核查等效措辞')
        self.assertTrue(analyze(d)['item_analysis'][0]['eligible_for_comparison'])
    def test_peer_reference_labeled(self):
        d=fixture();d['items'][0]['bids'][0]['scope_review']['reference']['kind']='peer'
        self.assertEqual(analyze(d)['scope_comparison'][0]['reference_kind'],'peer')
    def test_inputs_not_mutated(self):
        d=fixture();old=copy.deepcopy(d);analyze(d);self.assertEqual(d,old)
