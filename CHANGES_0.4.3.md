# VCSE v0.4.3: Missing-action repair

A model reply with `action: null` or a missing action receives **one additional model request** with a correction prompt. This does not repair unknown or unsafe action names, selectors outside the observed DOM, external navigation, or unauthorized side effects.

Native Ollama requests now use an explicit JSON schema with the action enum, while retaining `think: false`, bounded output and local-only access.

Run `python -m unittest discover -s tests -v`, then `python -m vcse.phase4 --planner model --split development`. Model responses are not independently verified in this build environment.

If the model still responds with a null action, the report shows `proposal_keys` (field names only) to help diagnose format disagreement without leaking page contents.

**CPU note:** The correction requires a second model call, so it can take longer than a single response. No credentials or untrusted websites are involved in the fixtures.
