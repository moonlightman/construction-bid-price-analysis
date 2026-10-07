"""只使用虚构记录和临时SQLite，绝不连接飞书。"""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from history_store import validate, put, current


def record():
    return dict(record_id='synthetic',kind='experience',name='synthetic feedback',status='pending',project_id='P',
        analysis_feedback=dict(finding_id='F',dimension='core_item',review_outcome='unreviewed',assessment_type='exploratory'))


class FeedbackTests(unittest.TestCase):
    def test_no_automatic_confirmation(self):
        r=record();r['status']='confirmed'
        with self.assertRaises(ValueError):validate(r)

    def test_feedback_not_price(self):
        r=record();r['kind']='price'
        with self.assertRaises(ValueError):validate(r)

    def test_no_validation_claim_without_evidence(self):
        r=record();r['analysis_feedback']['assessment_type']='validated'
        with self.assertRaises(ValueError):validate(r)

    def test_revision_and_readback(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/'synthetic.db'
            r=record();first=put(db,r)
            r['status']='confirmed';r['reason']='synthetic review'
            r['analysis_feedback'].update(review_outcome='cleared',review_source='synthetic',reviewed_at='2026-10-08')
            second=put(db,r,expected_revision=first['revision_id'])
            self.assertNotEqual(first['revision_id'],second['revision_id'])
            self.assertEqual(current(db)[0]['analysis_feedback']['review_outcome'],'cleared')
            self.assertEqual(put(db,r)['status'],'unchanged')


if __name__=='__main__':unittest.main()
