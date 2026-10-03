"""回归测试：金额完整性、比较资格、复核覆盖及输入边界。"""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_bids import analyze
from reconcile_sources import compare


def sample():
    return {'project': {}, 'bidders': [
        {'bidder_id': x, 'stated_total': 1200, 'source': {'file': x+'.xlsx','sheet':'汇总','cell':'B2'},
         'stated_total_review_status':'confirmed','coverage_confirmed':True,'total_comparable':True}
        for x in ['A','B']], 'items': [
        {'item_key':'管道-DN80-m','name':'合金钢管','tender_quantity':10,'mapping_confirmed':True,
         'bids':[{'bidder_id':x,'quoted_quantity':10,'unit_price':120,'line_total':1200,
                  'price_basis':'comprehensive','review_status':'confirmed','comparable':True,
                  'source':{'file':x+'.xlsx','sheet':'清单','row':2}} for x in ['A','B']]}]}


def paired():
    side={'source':{'file':'报价.pdf','page':1},'review_status':'confirmed','values':{'total':1200}}
    return {'coverage_confirmed':True,'pairs':[{'pair_id':'A-总价','same_version_confirmed':True,
             'fields':['total'],'excel':copy.deepcopy(side),'pdf':copy.deepcopy(side)}]}


class AnalysisTests(unittest.TestCase):
    def test_valid_totals_and_tied_ranks(self):
        result=analyze(sample())
        self.assertEqual([s['reconciliation_status'] for s in result['bidder_summary']],['一致','一致'])
        self.assertEqual([s['provisional_rank'] for s in result['bidder_summary']],[1,1])

    def test_split_material_installation_and_alloy_name(self):
        data=sample(); row=data['items'][0]['bids'][0]
        row.update(unit_price=None,line_total=None,price_basis='split_additive',additivity_confirmed=True,
                   material_unit_price=100,material_line_total=1000,
                   installation_unit_price=20,installation_line_total=200)
        result=analyze(data)
        self.assertEqual(result['bidder_summary'][0]['extracted_sum'],1200)
        self.assertEqual(result['item_analysis'][0]['unit_price'],120)
        self.assertEqual(len(result['item_analysis']),2)
        self.assertEqual(row['line_total'],None)

    def test_unconfirmed_additivity_excluded(self):
        data=sample(); data['items'][0]['bids'][0]['price_basis']='split_additive'
        self.assertFalse(analyze(data)['item_analysis'][0]['eligible_for_comparison'])

    def test_mismatch_excluded_from_peer(self):
        data=sample(); data['items'][0]['bids'][0]['line_total']=1250
        result=analyze(data)
        self.assertIsNone(result['item_analysis'][1]['peer_median'])
        self.assertNotIn('provisional_rank',result['bidder_summary'][1])

    def test_unconfirmed_mapping_excluded(self):
        data=sample(); data['items'][0]['mapping_confirmed']=False
        self.assertFalse(any(r['eligible_for_comparison'] for r in analyze(data)['item_analysis']))

    def test_duplicate_bid_rejected(self):
        data=sample(); data['items'][0]['bids'].append(copy.deepcopy(data['items'][0]['bids'][0]))
        with self.assertRaises(ValueError): analyze(data)

    def test_duplicate_item_rejected(self):
        data=sample(); data['items'].append(copy.deepcopy(data['items'][0]))
        with self.assertRaises(ValueError): analyze(data)

    def test_missing_amount_not_backfilled(self):
        data=sample(); data['items'][0]['bids'][0]['line_total']=None
        result=analyze(data)
        self.assertIsNone(result['item_analysis'][0]['line_total'])
        self.assertEqual(result['bidder_summary'][0]['reconciliation_status'],'无法完整核对')

    def test_quantity_difference_blocks_ranking(self):
        data=sample(); data['items'][0]['bids'][0].update(quoted_quantity=11,line_total=1320)
        self.assertFalse(analyze(data)['bidder_summary'][0]['ranking_eligible'])

    def test_unknown_coverage_not_passed(self):
        data=sample(); data['bidders'][0]['coverage_confirmed']=False
        self.assertEqual(analyze(data)['bidder_summary'][0]['reconciliation_status'],'无法完整核对')

    def test_pending_ocr_excluded(self):
        data=sample(); data['items'][0]['bids'][0]['review_status']='pending'
        self.assertFalse(analyze(data)['item_analysis'][0]['eligible_for_comparison'])

    def test_zero_not_missing(self):
        data=sample(); data['items'][0]['bids'][0].update(unit_price=0,line_total=0)
        result=analyze(data)
        self.assertEqual(result['item_analysis'][0]['unit_price'],0)
        self.assertTrue(any('零单价' in f['issue'] for f in result['review_signals']))

    def test_single_bidder_has_no_rank(self):
        data=sample(); data['bidders']=data['bidders'][:1]; data['items'][0]['bids']=data['items'][0]['bids'][:1]
        result=analyze(data)
        self.assertNotIn('provisional_rank',result['bidder_summary'][0])
        self.assertIsNone(result['item_analysis'][0]['peer_median'])

    def test_adjustment_not_omitted(self):
        data=sample(); data['bidders'][0].update(stated_total=1100,total_adjustments=[
            {'amount':-100,'source':{'file':'A.xlsx','sheet':'汇总','cell':'B3'},'review_status':'confirmed'}])
        self.assertEqual(analyze(data)['bidder_summary'][0]['reconciliation_status'],'一致')

    def test_nonfinite_and_bad_threshold_rejected(self):
        for bad in [float('nan'),float('inf'),True,'1,200']:
            data=sample(); data['items'][0]['bids'][0]['unit_price']=bad
            with self.assertRaises(ValueError): analyze(data)
        data=sample(); data['project']['thresholds']={'arithmetic_tolerance_pct':-1}
        with self.assertRaises(ValueError): analyze(data)


class SourceTests(unittest.TestCase):
    def test_equal_fields_full_coverage(self):
        self.assertTrue(compare(paired())['full_reconciliation_passed'])

    def test_difference_keeps_both_values(self):
        data=paired(); data['pairs'][0]['pdf']['values']['total']=1201
        result=compare(data)
        self.assertFalse(result['full_reconciliation_passed'])
        self.assertEqual(result['pairs'][0]['differences'][0]['pdf_value'],1201)

    def test_partial_not_full(self):
        data=paired(); data['unmatched']=[{'scope':'第二页'}]
        self.assertTrue(compare(data)['all_compared_fields_equal'])
        self.assertFalse(compare(data)['full_reconciliation_passed'])

    def test_version_unknown_not_passed(self):
        data=paired(); data['pairs'][0]['same_version_confirmed']=False
        self.assertFalse(compare(data)['full_reconciliation_passed'])

    def test_missing_not_equal(self):
        data=paired(); data['pairs'][0]['pdf']['values']['total']=None
        self.assertFalse(compare(data)['all_compared_fields_equal'])

    def test_pending_recognition_not_passed(self):
        data=paired(); data['pairs'][0]['pdf']['review_status']='pending'
        self.assertFalse(compare(data)['full_reconciliation_passed'])

    def test_empty_comparison_not_passed(self):
        self.assertFalse(compare({'coverage_confirmed':True,'pairs':[]})['full_reconciliation_passed'])

    def test_tolerance_requires_reason(self):
        data=paired(); data['numeric_tolerance']=1
        with self.assertRaises(ValueError): compare(data)


if __name__=='__main__':
    unittest.main()
