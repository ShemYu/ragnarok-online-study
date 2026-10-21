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
