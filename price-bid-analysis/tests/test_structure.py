"""虚构数据仅用于开发回归；不作为业务样例或历史价格。"""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_structure import run
from structure_algorithms import run as algorithms
from calibrate_threshold import run as calibrate


def bids():
    source = dict(file='synthetic.xlsx',sheet='test',cell='A1')
    data = dict(project=dict(project_id='SYNTHETIC'), bidders=[],items=[])
    prices = [[100,200],[80,400],[101,190]]
    for index, values in enumerate(prices):
        data['bidders'].append(dict(bidder_id=str(index), stated_total=values[0]*1000+values[1]*100,
            source=source,stated_total_review_status='confirmed',coverage_confirmed=True,total_comparable=True))
    for j, q in enumerate((1000,100)):
        data['items'].append(dict(item_key=str(j),tender_quantity=q,mapping_confirmed=True,
            bids=[dict(bidder_id=str(i),quoted_quantity=q,unit_price=values[j],line_total=q*values[j],
                       price_basis='comprehensive',review_status='confirmed',comparable=True,source=source)
                  for i,values in enumerate(prices)]))
    return data


def features():
    return dict(sample_unit='bidder_project',cohort_basis='synthetic same scope',cohort_confirmed=True,
        feature_basis_confirmed=True,feature_names=['x','y'],feature_definitions={'x':'synthetic index','y':'synthetic share'},
        samples=[dict(sample_id=str(i),entity_key=str(i),project_id='synthetic',review_status='confirmed',
                      comparable=True,source_refs=['synthetic fixture'],values=[i*.01,i*.015]) for i in range(11)]
                +[dict(sample_id='11',entity_key='11',project_id='synthetic',review_status='confirmed',
                      comparable=True,source_refs=['synthetic fixture'],values=[8,9])])


def calibration():
    return dict(score_definition='synthetic frozen score',score_direction='higher_more_unusual',
        scores_oof_confirmed=True,validation_source='synthetic fixture',holdout_project_ids=['P4','P5'],
        baseline_threshold=1.5,loss_weights=dict(false_negative=5,false_positive=1,review=.1),
        samples=[dict(sample_id=f'{i}-{label}',project_id=f'P{i}',score=score,
                      label=label,label_status='confirmed',label_source='synthetic fixture',
                      model_training_project_ids=['TRAIN'],training_cutoff='2024-01-01',scored_at='2025-01-01')
                 for i in range(6) for label,score in [(0,.1+i*.01),(1,1+i*.01)]])


class StructureTests(unittest.TestCase):
    def test_same_total_different_structure_and_scenario(self):
        d=bids();before=copy.deepcopy(d)
        d['structural_analysis']=dict(scenarios=[dict(scenario_id='S',item_key='1',delta_quantity=50,
            basis_confirmed=True,source=dict(file='synthetic.xlsx',sheet='test',cell='B1'))])
        r=run(d)
        p=r['bidder_profiles'][1]
        self.assertEqual(p['positive_impact'],20000)
        self.assertEqual(p['negative_impact'],-20000)
        self.assertEqual(p['net_impact'],0)
        self.assertEqual(p['gross_absolute_impact'],40000)
        self.assertEqual(r['scenarios'][1]['incremental_reference_gap'],10000)
        self.assertEqual(d['items'],before['items'])

    def test_pending_and_arithmetic_not_in_baseline(self):
        d=bids();d['items'][0]['bids'][1]['line_total']+=500
        r=run(d)
        self.assertEqual(r['item_statistics'][0]['included_bidder_ids'],['0','2'])
        self.assertIsNone(r['item_structure'][1]['relative_index'])
        self.assertEqual(r['bidder_profiles'][0]['common_item_keys'],['1'])

    def test_single_bidder_no_statistics(self):
        d=bids();d['bidders']=d['bidders'][:1]
        for item in d['items']:item['bids']=item['bids'][:1]
        r=run(d)
        self.assertIsNone(r['total_statistics']['median'])
        self.assertIsNone(r['item_structure'][0]['relative_index'])

    def test_zero_preserved_no_positive_index(self):
        d=bids();d['items'][0]['bids'][1].update(unit_price=0,line_total=0)
        r=run(d)
        self.assertEqual(r['item_structure'][1]['unit_price'],0)
        self.assertIsNone(r['item_structure'][0]['relative_index'])

    def test_unknown_quantity_no_impact(self):
        d=bids();d['items'][0]['tender_quantity']=None
        r=run(d)
        self.assertIsNone(r['item_structure'][0]['impact_amount'])

    def test_relationship_requires_evidence(self):
        d=bids();d['structural_analysis']=dict(relationships=[dict(relationship_id='R',numerator_item='0',
            denominator_item='1',reason='synthetic',confirmed=True)])
        self.assertEqual(run(d)['relationships'][0]['status'],'not_evaluable')

    def test_negative_final_quantity_rejected(self):
        d=bids();d['structural_analysis']=dict(scenarios=[dict(scenario_id='S',item_key='1',delta_quantity=-101)])
        with self.assertRaises(ValueError):run(d)


class AlgorithmTests(unittest.TestCase):
    def test_anomalous_object_and_traceability(self):
        r=algorithms(features())
        self.assertEqual(r['status'],'exploratory')
        self.assertEqual(r['independent_project_count'],1)
        scores=r['diagnostics']['lof']['runs'][0]['scores']
        self.assertEqual(scores.index(max(scores)),11)
        self.assertLess(r['diagnostics']['kde']['features'][0]['variants'][1]['leave_one_out_log_density'][11],
                        r['diagnostics']['kde']['features'][0]['variants'][1]['leave_one_out_log_density'][5])
        self.assertEqual(len(r['source_refs']),12)

    def test_missing_not_imputed(self):
        d=features();d['samples'][0]['values'][0]=None
        r=algorithms(d)
        self.assertEqual(r['excluded_samples'][0]['sample_id'],'0')
        self.assertEqual(r['sample_count'],11)

    def test_small_sample_does_not_fit(self):
        d=features();d['samples']=d['samples'][:3]
        self.assertEqual(algorithms(d)['status'],'not_evaluable')

    def test_duplicate_identity_rejected(self):
        d=features();d['samples'][1]['entity_key']='0'
        with self.assertRaises(ValueError):algorithms(d)

    def test_constant_features_not_forced_cluster(self):
        d=features()
        for row in d['samples']:row['values']=[1,1]
        self.assertEqual(algorithms(d)['status'],'not_evaluable')

    def test_deterministic_outputs(self):
        self.assertEqual(algorithms(features()),algorithms(features()))


class CalibrationTests(unittest.TestCase):
    def test_threshold_candidate_and_holdout(self):
        r=calibrate(calibration())
        self.assertEqual(r['status'],'candidate_only')
        self.assertEqual(r['holdout_baseline']['recall'],0)
        self.assertEqual(r['holdout_candidate']['recall'],1)
        self.assertEqual(len(r['trials']),24)
        self.assertEqual(set(r['calibration_projects']) & set(r['holdout_projects']),set())

    def test_training_leakage_rejected(self):
        d=calibration();d['samples'][0]['model_training_project_ids'].append('P4')
        with self.assertRaises(ValueError):calibrate(d)

    def test_pending_label_rejected(self):
        d=calibration();d['samples'][0]['label_status']='pending'
        with self.assertRaises(ValueError):calibrate(d)

    def test_future_training_rejected(self):
        d=calibration();d['samples'][0]['training_cutoff']='2026-01-01'
        with self.assertRaises(ValueError):calibrate(d)


if __name__=='__main__':unittest.main()
