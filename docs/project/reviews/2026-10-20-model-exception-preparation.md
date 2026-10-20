# Known model exception: source and byte relationship preparation

Date:2026-10-20 JST. Root preparation at d2fdeaa; no model repair,
installed change or additional task qualification. The main work remains the
[.007 catalog comparison](2026-10-20-T06.003.003.007.md).

The qualified [.006 observation](2026-10-20-T06.003.003.006.md) retains one
GRSM1.4 constructor exception: model-004424,22471bytes/SHA
4b6aa735d909263f70ecd79d16014fa349bd239bf250b18fc948116d905afd92.
Root authorizes read-only preparation of this one retained body. An internal
aide prepares a byte-layout script and report; another aide independently
checks its source interpretation. Neither gets Claude/Grok task credit.
Root personally reads the complete script/report and the relevant pinned
Model/BinaryReader branches before executing the script, then performs an
independent direct-offset recount and provenance audit.

## Verified relationships

All five node layouts end exactly at22463; zero global position keys and zero
volume boxes end at22471, with no remaining bytes in this calculation. This
is byte-layout accounting, not a full format, float or face-index verdict.
Main selection chooses node0. Anonymous name equality is sufficient here:

| Node index | Name | Parent name | Caller guard allows children |
| --- | --- | --- | --- |
| 0 | A | empty | yes |
| 1 | A | A | no |
| 2 | A | A | no |
| 3 | B | A | yes |
| 4 | empty | A | yes |

The actual source condition at Model.js300–303 is
`nodes[i].parentname === this.name && this.name !== this.parentname`.
It induces edges0→1,0→2,0→3,0→4,4→0. Starting at0, source-order calls visit
0,1,2,3,4 and then revisit active node0: **0→4→0**. Root directly checks both
edge predicates from the pinned bytes, the complete contiguous span partition,
and the original catalog links: one target4434/catalog6700, two roots930/1084,
four declared placements. All seven full input/hash/identity postchecks pass.

This establishes a reachable loop under the pinned source's call rule. Matrix
and vertex work occurs before recursive calls; no new constructor execution or
stack trace was captured. The actual throw site and a semantics-preserving
repair remain unverified. Empty names must not simply be removed or aliased.

## Evidence and next action

Private evidence is below
`.tools/renewal/t06-map-dependency-preparation-1/root-model-exception-preparation-1`:

- Reviewed aide script11202bytes/SHA
  66a62910702d171c77ea1471188824479c9db56a19d43df745b3a1d43198abc8;
  root execution exit0, relationship report15384bytes/SHA
  0ab62bd41ff46290ed5f47517883fa2dd249ec8c54e09d5cf9004271a19fc3fe.
- Independent root script7410bytes/SHA
  837c873f923beac3c5888438523a313262d8fbf9b04ec23d3c1c12e5e5f7332c;
  corrected audit exit0, receipt2833bytes/SHA
  77462fd273af986f267040acd6dd99039ef30dd592d5c9511e9be65673e9f286.
- Earlier root audit/shape probes stopped on two nonexistent metadata keys;
  neither produced an audit result or changed inputs. Their failure record is
  retained privately; the successful recount uses the observed manifest shape.

Pinned source: Model30922bytes/SHA
d4643fc9a1a95747b41ee55537fe3159c2927e9840630291cce9d55bea20fe57;
BinaryReader8233bytes/SHA
bcf694b7034e36146eed1d5a2d7d5cf93d8a52aeafa74e62f0beed4c1ecc9215.
Manifest16968757bytes/SHA
cb7e49e0a0180636be580bf7f45e7e542bf886d6241ea26fd1bb11f18e5b5e94;
catalog32959912bytes/SHA
3c6b9707d2b9f8093d9e7ce21b7e320791d2b9d5ca4d3d6728e3f915356f64a3.

Next owner is root: retain this reproducer and freeze a later independent
Claude/Grok diagnosis/repair task with synthetic controls and actual constructor
evidence. Rendering/travel checks must follow a qualified repair. No exception,
map or placement is waived. The current .007 inputs and unknown exception
tables stay unchanged. No other asset body, client execution, native reader,
HTTP, game/save/settings or host-network action occurred. No critical issue
requiring a goal change is established. Rollback reverts this documentation
checkpoint; it does not restore runtime state.
