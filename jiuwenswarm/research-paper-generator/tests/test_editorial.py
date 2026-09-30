import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from paper_content.editorial import draft_and_review

class FakeModel:
    def __init__(self): self.config={'request':{'enable_thinking': True}}; self.calls=[]; self.requests=0
    def complete(self, messages):
        self.requests += 1
        self.calls.append({'model':'test', 'usage':{'total_tokens':10}})
        return {'stage_response': self.requests}

class EditorialTests(unittest.TestCase):
    def test_resume_skips_completed_paid_stages(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); cached=root/'old'; output=root/'new'; cached.mkdir(); output.mkdir()
            messages=[{'role':'system','content':'JSON'}, {'role':'user','content':'same evidence'}]
            (cached/'generation_request.json').write_text(json.dumps(messages))
            for stage in ('editorial_plan','editorial_draft'):
                (cached/(stage+'.json')).write_text('{}')
            model=FakeModel()
            draft_and_review(model, messages, output, cached)
            self.assertEqual(model.requests,2)
            self.assertEqual([c['stage'] for c in model.calls],['editorial_review','editorial_revision'])
            self.assertTrue(model.config['request']['enable_thinking'])

    def test_changed_evidence_prevents_resume_before_call(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'generation_request.json').write_text('[]')
            model=FakeModel()
            with self.assertRaisesRegex(ValueError,'identical'):
                draft_and_review(model,[{'role':'user','content':'different'}],root,root)
            self.assertEqual(model.requests,0)

if __name__=='__main__': unittest.main()
