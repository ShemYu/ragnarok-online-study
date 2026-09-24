# Character Lab milestones

**Public checkout:** source and notes are available here; artwork, visual evidence and full archives remain local. Asset/archive links below refer to the local study pack. See [repository scope and setup](../PUBLIC_REPOSITORY.md).

## v0.1.0 — native actions with replacement artwork

Saved on 2026-09-24. This milestone records the successful Wayfarer costume/head substitution on one original RO attack and facing. It preserves the earlier experiments so the change in approach remains reviewable.

- [Findings and review](native-art-poc-v0.1.0.md): what worked, what failed, exact scope and evidence.
- [Reusable workflow](WORKFLOW.md): existing stages and commands, module contracts, proposed extraction into a generic recipe.
- [Snapshot inventory](releases/native-art-poc-v0.1.0/manifest.json), [restorable archive](releases/native-art-poc-v0.1.0/source.zip), and [verification](releases/native-art-poc-v0.1.0/verification.json).
- [Live comparison](http://127.0.0.1:8767/native.html).

The version is a local artifact checkpoint, not a Git tag or published release. The archive freezes code, images, original source records, generated boards, prompts and prior experiments. Each archived file has a SHA-256 record. Live files may continue to change; the frozen archive stays unchanged.

The evidence separates technical verification from visual acceptance. The native clothing result received positive user feedback. The head is a candidate preserved for review. Neither is a claim of a complete original job or gameplay integration.

To create another checkpoint, copy the packaging recipe to a new version, change its `version` and `releaseDirectory`, update the review/evidence and run `pipeline.py snapshot --recipe <new recipe path>`. The tool refuses to replace an existing release. See [pipeline commands](../../tools/character-lab/pipeline/README.md).
