## Evaluation Criteria Mapping

The system logs lightweight metrics aligned with the AIA-PAL evaluation criteria:

- Accuracy: last_score for the cycle.
- Adaptability: decision action taken.
- Response Time: timing per decision/crew/monitor step.
- Workflow Coordination: validation status.
- Tracking Agents: presence of learning history updates.
- Errors and Inconsistencies: validation failures or missing outputs.
- Expert Review: mapped to validation status.
- Scaffolding Strategies: actions that increase or reduce support.

Outputs:
- `logs/evaluation.log`
- `logs/evaluation.jsonl`
