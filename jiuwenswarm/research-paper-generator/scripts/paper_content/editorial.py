"""Model planning, critical review and revision with saved stage outputs."""
import json


def draft_and_review(model, messages, output, resume_from=None):
    if resume_from:
        previous = json.loads((resume_from / 'generation_request.json').read_text(encoding='utf-8'))
        if previous != messages:
            raise ValueError('Editorial resume requires identical manuscript instructions and evidence')
        report = resume_from / 'content_report.json'
        if report.is_file():
            prior = json.loads(report.read_text(encoding='utf-8'))
            model.calls.extend({**trace, 'reused_from_previous_run': True} for trace in prior.get('calls', []))
    def call(stage, prompt):
        cached = resume_from / (stage + '.json') if resume_from else None
        if cached and cached.is_file():
            value = json.loads(cached.read_text(encoding='utf-8'))
            (output / (stage + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print(f'Reusing saved stage: {stage}', flush=True)
            return value
        print(f'Writing stage: {stage}', flush=True)
        start = len(model.calls)
        original_request = dict(model.config['request'])
        # Long non-streaming thought budgets exceeded the gateway idle timeout in practice.
        # Preserve the flagship model, but bound short planning/review responses.
        model.config['request'].pop('thinking_budget', None)
        model.config['request'].pop('reasoning_effort', None)
        model.config['request']['enable_thinking'] = False
        model.config['request']['max_tokens'] = 6000 if stage in ('editorial_plan', 'editorial_review') else 16000
        try:
            value = model.complete(prompt)
        finally:
            model.config['request'] = original_request
            for trace in model.calls[start:]:
                trace['stage'] = stage
                trace['enable_thinking'] = False
            (output / 'editorial_calls.json').write_text(json.dumps(model.calls, indent=2) + '\n', encoding='utf-8')
        (output / (stage + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return value

    plan = call('editorial_plan', [
        {'role': 'system', 'content': 'Plan an evidence-grounded empirical research paper. Return JSON with thesis, contributions, section_plan, claim_limits and failure_modes. Do not invent experiments, sources, significance or novel algorithms. Focus on a sharp argument and concrete analysis.'},
        messages[1], {'role': 'user', 'content': 'Return only the editorial plan JSON, under 900 words, not the manuscript schema.'}])
    draft = call('editorial_draft', messages + [{'role': 'user', 'content': 'Follow this plan while obeying the exact manuscript JSON schema and metric tokens: ' + json.dumps(plan)}])
    critique = call('editorial_review', [
        {'role': 'system', 'content': 'Act as a skeptical academic reviewer and technical editor. Compare the draft with supplied evidence. Return JSON with major_issues (section, issue, required_revision), factual_checks, repetitive_passages, missing_analysis and ready_for_human_review. Check costs, overclaims, source support, baseline confounds and reproducibility. Do not assign a simulated acceptance score.'},
        messages[1], {'role': 'user', 'content': 'Review in under 1000 words. Recompute any cost ratios; do not trust approximate ratios from the plan. Draft: ' + json.dumps(draft)}])
    return call('editorial_revision', messages + [
        {'role': 'assistant', 'content': json.dumps(draft)},
        {'role': 'user', 'content': 'Revise the ENTIRE manuscript, preserving exact section/subsection schema. Address supported criticisms without inventing evidence. Use only known metric/citation tokens and no literal numbers. Keep 3000-3800 words. Critique: ' + json.dumps(critique)}])
