# RGZ grammar — verified primary-source preparation

Date:2026-10-21JST. Owner/next owner:root coordinator. Source preparation only;
no actual RGZ member/record, CRC, decoded body, application or map PASS.
The full Modern/Renewal goal stays unchanged. This is independent of .006/.007.

An actual gpt-6-astra/high source advisory identifies a candidate grammar. Root
reads its full report, independently opens material primary pages and freshly
fetches five complete inert source texts at the pinned revisions. Every saved
byte count/SHA matches. Root personally reads the relevant reader/writer,
counted-string/u32 and explicit little-endian implementation passages, plus
gzip framing/trailer/compliance rules. No third-party parser/executable runs.

[GRFEditor e6508407](https://github.com/Tokeiburu/GRFEditor/blob/e6508407c1e193dac5252eef788dc0a0c1d9d07f/GRF/FileFormats/Rgz.cs)
and [RagLite d1ce2b1e](https://github.com/RagnarokResearchLab/RagLite/blob/d1ce2b1e2136c46b1409d5c6701f64d7c3cddaf9/Core/FileFormats/RagnarokRGZ.lua)
show directory/file/end opcodes, one-byte counted names and file length/content.
[ragassets0df6c374](https://github.com/adsonpleal/ragassets/blob/0df6c3744b895ed78acbbc68396878ab060d4980/extract-grf.mjs#L843)
explicitly reads unsigned little-endian32-bit file sizes. NUL/end validation and
codec behavior differ; these are implementation precedents, not an official
Taiwan publisher grammar. Root preserves raw name fields and treats exact end/
EOF as a proposed experiment policy, without extraction or path application.

[RFC1952](https://www.rfc-editor.org/rfc/rfc1952.txt) defines gzip member framing,
CRC32 and ISIZE modulo2^32. A valid prefix alone proves none of those checks.
The proposed first experiment is limited to one flags0member; concatenated
members are unsupported by that experiment, not inherently malformed gzip.
Explicit CRC/size checks and decoded-output limits are required. Shared zlib
inflation/checksum machinery is not an independent second codec implementation.

Fresh root five-source receipt1659bytes/SHA256
aeac25ae40d39c599f0c6abf93f7e7a8fa00818caa58c864dd25bebc20648632,
private `.tools/renewal/t07-007-rgz-root-source-verification-1`.
The full Astra report and12primary text selections remain separately preserved
under `.tools/renewal/t07-007-rgz-grammar-preparation-1`. Root reproduces only the
material five-source subset above; secondary implementation details remain
advisory until needed and separately checked.

Root also hand-checks an independently authored23-byte inner literal:
`640261006604615c6200030000004142436504656e6400`.
Directory starts0/next4; file starts4/size3at10/body14..17; end starts17/exact
EOF23. Full literal/expected offsets/body SHA are retained privately. This
checks synthetic field arithmetic only, not an inflater or any official file.

Next root qualifies a small separate streaming reference on synthetic
header/record/CRC/ISIZE/EOF/cap/short-read controls, then admits one exact
1467-byte RGZ(index9302) for a bounded read-only experiment. No archived path
may create/extract/overwrite/delete a file or directory; file content is hashed
and discarded. Only after qualified actual byte evidence can a new production
contract be frozen and compared through actual independent Claude/Grok work.
All29actual RGZ formats remain unresolved at this preparation checkpoint.

Astra provides concrete algorithm/I/O findings and primary grammar leads;
Opus5.5fallback remains available if later hard questions remain unresolved.
No new consultation is needed merely to repeat these resolved source findings.
No original app/save/SQL/network/preferences state changes or goal change.

## Synthetic streaming reference qualified

Root now fully reads the separate streaming reference and43-case qualifier,
and personally executes both original and corrected versions. Original27247B/
SHA256`324b913efb2f3154bd85719d00b155fa24403e4c5099f31498d06bbc28058fa8`
fails exactly three controls: requested read caps1/3 and a late successful EOF.
Its nonzero exit/failed guard remains recorded as a reproduced defect.

A separate27558-byte correction/SHA256
`1f6f3a1c4559c59d244ede4be3f6f65fa2482c2fedb8a85d11aa06ed41ef73a4`
passes the caller's read cap into header/trailer/trailing-prefix reads and
checks the deadline after final EOF. The unchanged43 test bodies and literal
goldens now all pass. Root verifies the two-line source-pin adaptation only;
qualifier14867bytes/SHA256
`fa43108906a8350f3339e4e6d52653b5820550fa74e4a2132ba413eeecfb36d2`.
Controls include framing/method/flags, truncation/extra member, CRC/ISIZE,
inner opcodes/end/EOF, bounded work/read/output, short writes and sink failures.
The corrected guard records0.296716seconds/26853376B sampled peak/exit0/no
action or signals/empty group. All44 metadata and protected source full hashes/
identities stay unchanged. Corrected root receipt49341bytes/SHA256
`237466bb1ac736fb85a85e0b9d51e9b49f5d414d1558bd530269e1736f7b785e`;
original49563bytes/SHA256
`06077f8d1ed84275a9454ffdd75909d63f2f82aea9043f2128c8e44f3220ec96`.

This qualifies the pure streaming/parser and explicit sink seams only. It
does not qualify the draft's physical `Publication` or main/fixed-run lifecycle;
root identifies an open/fstat failure-close concern there. Do not invoke that
route. Next use a separately reviewed root publication harness around only the
qualified pure parser for the exact1467-byte experiment. No actual RGZ opens/
decodes occur at this checkpoint; all29 remain unresolved. No production
contract, archive application, extraction or map/functionality PASS follows.

## Separate root publication harness qualified

Root fully reads and syntax-checks a separate15074-byte runner/SHA256
`715f06baa7b0dfa0d6478e0bce66bc06b1c3b513e694f4e76b7c5c48bd4e1dc7`
and9412-byte controls/SHA256
`f6464ca304923694b3bad9985400e139c83d5ee8dc7921202969855f9d4dbc2e`.
The runner compiles only the exact pinned parser prefix, explicitly excluding
unqualified Publication/Sink/fixed_run/main. The selected fixed body remains
unopened. It binds all six source pins, the29-entry minimum-size selection and
the selected ledger identity; only metadata/record raw-name hex/body hashes
can be written to two fixed private output names. No extracted paths are used.
Qualification requires the exact runner's captured zero exit plus full root
artifact/input audit; a report alone never proves final completion.

Root personally runs all12 authored wrapper control groups under its separate
outer guard. Positive three-byte short writes and complete output readback
pass. Zero-progress, physical two-byte fragment thenEIO, before-closeEIO,
real-close-thenEIO, wrong-hash constructor cleanup, same-content foreign inode,
directory replacement and four typed/hash ledger refusals pass. Fault activation,
immediate owned inode/EBADF close evidence and preserved foreign objects are
checked; no live owned FD or harness cleanup intervention remains. All56
protected metadata/source inputs retain their full hashes and identities.
Guard0.172801seconds/exit0/empty stderr/no action or signals/empty owned group.
Its1916928B sampled peak can miss the short process's real peak and is not a
hardware requirement or OS containment claim. No actual RGZ body is opened.

Next root may run only this separately qualified fixed wrapper on the admitted
1467-byte input, then independently audit all emitted records, gzip/inner axes,
CRC/ISIZE/end/EOF, source/input preservation, outputs and positive process exit.
All29 remain unresolved until that actual observation; no production tool,
installation, application, filename codec, renderer/game or goal change.

## Smallest actual RGZ fully audited

After committed harness checkpoint762264b, root personally invokes only the
exact fixed pure-prefix wrapper. Index9302/1467bytes retains its admitted full
SHA and ledger identity. It completes with four records: two directory entries,
one4687-byte file body and one strict end record. All names stay raw hex and
body bytes are hashed/discarded; no operation is applied or file extracted.
The gzip member inflates to4753bytes, CRC32=301909838/ISIZE=4753, exact DEFLATE/
compressed/inflated EOF and strict end pass. All57protected inputs remain
full-hash/identity equal; positive runner exit0, empty stderr, no guard action,
signals or owned process residue. Guard0.170394seconds; its short-run RSS sample
is not a hardware sizing result.

Root's separate scalar auditor imports neither parser nor runner. It bounds
inflation to64KiB for this fixed tiny input, independently walks all four full
typed record dictionaries and offsets/body hashes, and computes CRC32 with an
explicit bit loop. Zlib inflation remains shared codec machinery. Every gzip/
inner field, source/ledger/input/output binding, file size/hash/identity, final
62rereads and captured exact-runner zero exit agree. No second-codec claim.
Auditor7828bytes/SHA256
`7474b546e7b189f55da1944294f677ae7790db08cec6ae71738781dfa12f3f3d`;
root658-byte receipt/SHA256
`98bd9c50315aa3658b24a0b8337a3a6c0cec818e01f316a1ce2c802f1235e8e1`.
Private four-record output1997bytes/SHA256
`18ed981b35ab4b1c1a226817bdef23a035c55a69e899c07ac1280bfc87b9aa44`;
report4887bytes/SHA256
`c79e7e257b2a416487bb41fcfa4da8acbf1841f623dfa623e5f929bc6300efe3`.

One exact RGZ now has a qualified bounded grammar/integrity observation;
**28other RGZ remain unresolved**. The observed file is not a terrain/map
coverage result. Next root may freeze an explicit broader grammar experiment
with per-file unsupported/failure outcomes and independent checks before any
production pair. No universal RGZ support, publisher patch application, filename
codec/priority, installation, game content or full-goal completion follows.

For the next bounded experiment, root freshly rehashes the exact94572-byte
admission ledger and independently recomputes the remaining28metadata census:
100061839compressed bytes total, largest18003576bytes. All28saved four-byte
headers are1f8b0800(method8/flags0). No body opens occur in this census. Header
compatibility does not prove DEFLATE, CRC/ISIZE, inner grammar, EOF or content.
The broader serial wrapper and its explicit whole-run/output/final-rehash
headroom remain source preparation until root review and qualified controls.


## Remaining28 bounded wrapper qualified before actual observation

Root full-reads the original batch runner/qualifier and separate proposed-v2
changes. Internal source review finds two defects in the unexecuted draft:
root report publication still uses an expired scan budget despite reserved
finalization time; report-close failure can mask the original write failure.
Separate v2 switches root to the fixed final deadline in the real transition,
and independently retains document put/close errors. Originals stay preserved.
No extra close retry, deletion, extraction or source-policy expansion.

Reviewed runner22349B/SHA256
`db47925c5f47625a7b073e718e0d1a930f661427a35f506481bbc2a27a9033a5`;
qualifier14752B/SHA256
`9791fc1e9a6ad32c226f9bdbb0fdd7eb4840bf9b42b78adfe999e470193f290a`.
Root personally executes all10authored groups under the unchanged external
guard. Baseline two-file exact d/f/e/body hashes/full private output readback,
unsupported/unknown-inner/valid continuation, record cap/unattempted suffix,
real7-byte partial write then EIO, failures before and after real close, real
7-byte report-write failure plus secondary close error, preadmission drift,
unattempted suffix drift and expired-root-scan/live-final report publication
all satisfy their literal criteria. Exact fault activation and owned FD closure
before harness cleanup pass; zero cleanup interventions. All57protected
source/metadata receipts stay equal. Guard0.242491s/21184512B sampled peak,
process0/no action/signals/owned residue. No acquired RGZ body is opened here.

The fixed remaining28ledger entries total100061839compressed bytes; maximum
18003576. All28full inputs must admit before parsing; final and after-report
hashes include unattempted suffixes. Serial per-file180s/512MiBdecoded/500000
records/10million parser operations, scan1500s/final absolute1740s/outer1800s
and2GiB sampled RSS remain explicit. Record/report reservations248MiB/8MiB
cap physical runner output at256MiB, including failed prefixes. Parser is the
previously qualified pure prefix; original Publication/main are not called.

Next root executes exactly this frozen remaining28 observation in a fresh
private namespace, then independently audits every complete raw record/field,
input/output hash, private tree and terminal/process evidence. Unsupported or
incomplete profiles stay exact open outcomes; a complete observation is not
format success or patch applicability. No asset extraction/install/apply,
native/render/game or82world-gap closure follows. The separate actual
Astra/high Model repair can run concurrently without shared runtime writes.


## Remaining28 actual bounded observation completed; scalar audit pending

After the qualified-harness checkpoint b92db67, root personally runs the exact
fixed v2 wrapper on all28 remaining bodies. All28complete this strict gzip/inner
profile:271records,283166311decoded bytes,283156034inline-file body bytes hashed.
All28late full body checks and nine source checks pass after reports close.
All85independently protected source/metadata/body receipts remain equal.
Captured process0; guard1.349322s/28606464B sampled peak, no action/signals/owned
group residue. This is streamed hashing, with no extraction/apply.

Batch report100125B/SHA256
`6ac78beb09be926a7d565e48c172d316aeb8db2bae7940a1211bad1893865b2d`;
terminal receipt7168B/SHA256
`0057667a2b674a771e95829081f279c7c8972a3b7cc869dfefa55887f4924ab4`.
These are checked runner observations, not yet independently qualified full
raw-record artifacts. Root has read the separately authored streaming scalar
auditor, which remains disabled until authored controls qualify. Its raw
DEFLATE codec shares zlib; CRC32 and inner-field walk are separate. Full271
record/offset/name/body-hash/CRC/trailer/member/EOF comparisons and every output
file remain the next gate. No map resource reconciliation, patch installation,
new playable coverage or82functional-gap closure follows from this run.


Root full-reads the independent24031-byte scalar auditor/SHA256
`601c36bcae1c7f3cc0b5de57239c5d20f9503dcb96aab93860f563515f46da43`.
Its separate9174-byte authored-memory qualifier/SHA256
`d9d926bfff3da55beb883953843964e88c5dd77ad02b0f9c769efd5a6621e71b`
passes one full literal d/f/e/gzip positive and15targeted negatives. Literal
abc hash/offsets/all fields and three known CRC vectors qualify independent
bitwise versus table CRC32; baseline trailer is e08b66c315000000. Wrong record
hash/name/offset, truncations/opcode/end/trailing/member/CRC/ISIZE/header faults
raise their exact expected AuditFailure or ManualReview classes. No unexpected
exception credits, actual RGZ reads or FD/batch-artifact fault coverage.
Guard0.155810s/process0/no action/signals/owned residue; sampled peak3735552B
can miss the short process peak. All five protected source receipts stay equal.

Root now enables a separate exact copy solely by changing ROOT_ENABLED from
False to True; original disabled source is preserved. This permits the fixed
actual28scalar audit only. It adds no parser, codec, input/output path, policy
or acceptance override. Complete actual input/output/source comparisons and
observed file closes/process cleanup remain required before qualification.


## All remaining28 full scalar artifacts qualified

Root runs the separately enabled24030-byte auditor/SHA256
`813202964b50c0a3b2409983ab27c5ecdc736383003f937f2c70ef5350bf3e77`
after the authored qualification checkpoint. All271complete typed raw records
agree byte-for-byte: opcodes, offsets, counted raw names/NUL facts, size fields,
inline body spans/SHA256 and canonical JSONL bytes. Independent scalar grammar
and table CRC32 agree with every gzip trailer/ISIZE/member/strict inner end and
compressed/inflated EOF. Raw DEFLATE explicitly shares zlib; no independent
DEFLATE implementation or universal RGZ support is claimed.

Every ordered per-file state, original full ledger descriptor, plan, batch
report, terminal receipt and all59private output files match. Physical JSONL
171793B and reports213250B stay within the frozen reservations/caps. All97
input/source/output files receive final full hash/identity rereads and observed
reader closes. All148outer protected input/source/output receipts stay equal;
captured auditor process0, guard32.937869s/21561344B sampled peak/no action/
signals/owned residue. Root separately links the qualified actual observer exit
and authored controls; the auditor's pending-guard labels are not treated as
self-sufficient process proof. No injected file/FD-failure campaign is claimed
for this read-only auditor.

Together with separately qualified9302/four records, all29acquired RGZs now
have bounded reference grammar observations and full independent artifact
checks:275raw records total. This closes the reference-format uncertainty for
these exact inputs. A production facade, raw-name/resource reconciliation,
extraction/apply, installed coverage, render/game and82functional gaps remain
open. Existing source/GPF readiness and user scope do not change.

## Bounded resource finding and production-facade deferral

Root independently rechecks all29qualified canonical JSONL files/275full typed
records and their framing/name/span facts. The204file records classify by ASCII
suffix as121BMP,74LUB,7MP3,1DAT and1EXE; no counted RSW/GND/GAT suffix appears.
All121BMP raw names are ASCII. An explicit comparison maps backslash to slash
and applies URI segment escaping, with no prefix addition, trim, lookup case
folding or percent decoding. It finds zero exact matches against the current
178conditional model-texture paths. Five literal comparison controls pass.

This only compares qualified metadata. Existing independent raw-body/CRC
qualification supplies the record truth; no archive/body is reread here, no
client lookup is executed and no installed-resource or missing-content claim
follows. All33inner/35outer protected receipts and observed FD identities stay
equal. Guard0.177678s/process0/no action/signals/owned residue; two RSS samples
observe3751936B and can miss the short process peak.

Private finding31913B/SHA256
`df2d5e9ed2a53a95e19f128f5fdc2c6fcc6563cea2a65669cfde2f4f8216fd28`;
root receipt36589B/SHA256
`1a1829aec294eca3ca1a733d0867c7d27fd6441b12074d1b7da4197b4956ad53`
are retained in .tools/renewal/t07-007-rgz-resource-finding-preparation-1/.
Root reviewed the separately pinned11161B finding helper31369c77… and6470B
guard wrapper7c08ffa6… before that run.

Decision: defer a duplicate production RGZ facade; no public .010task/profile
is frozen or dispatched. Preserve its private unexecuted drafts and qualified
reference for later patch application/resource work. Prioritize the active .009
model-to-texture route and isolated ordinary save check. This is independently
verified preparation, not an actual provider implementation task or new game
PASS. Full patch reconciliation,82functional gaps and full-game intent stay open.
