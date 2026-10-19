# Actual macOS Chinese IME: preparation and capability gate

Date2026-10-19JST. Parent T05 remains in_progress. This is root source/tool
preparation for planned T05.013; no Claude/Grok plan comparison, native IME
trial or input-method repair is claimed. Earlier Unicode entry is separate.

Root reads the actual client ChatBox.js912–1140, ChatBox.html, complete
KeyEventHandler.js, GUIComponent.js486–524 and MapEngine.js969–1030. Root
also reads the corresponding current Quest-ON bundle ChatBox223144–223280
and extension composition/input-state boundaries332319–332339 and
332674–332690. Whole bundle13174160/SHA9c148d9e… remains the installed
qualified stage; no code is executed or changed by these source reads.

The message draft is .message.input-chatbox[contenteditable=true]. The
adjacent .username INPUT is the whisper-recipient field. ChatBox's Enter
branch calls submit when the message field has focus and stated guards
permit it; no explicit isComposing/key229 guard appears in that handler.
GUIComponent passes the event through and prevents default only on false.
Up/Down can replace the draft with history, and Escape blurs it. MapEngine's
talk callback can send public/party/guild/whisper packets. The extension's
compositionstart/end listeners restrict extension movement; they do not
add a ChatBox-submit guard. Actual IME key codes/order are untested, so
these facts identify test constraints rather than a reproduced product bug.

Root's narrow read-only HIToolbox inspection confirms current/selected ABC
and enabled Traditional Chinese Zhuyin; Japanese input is also enabled.
These identifiers are preferences, not proof of the input source at a
focused native field. No source, ordering, hotkey or OS setting is changed.
Browser CUA can control the game tab, but this checkpoint's native Chrome
app bind fails with cgWindowNotFound. That is a native-control observation,
not a diagnosis of missing permissions, OS configuration or the game.
Do not repeat blind app binding or substitute paste/locator fill/synthetic
composition events for real phonetic input and candidate selection.

Future root/paired read-only procedure must establish native-key routing
and candidate/preedit visibility in an inert scratch field first. Only then
test an unsent game draft: composition, pointer candidate selection/commit,
separate cancellation, draft-only cleanup and restoration of the original
input source. Avoid Enter/Up/Down until their actual composition behavior
is established. No chat send, slash command, whisper, quest or reward input;
preserve other work, Chrome audio/mute and OS/IME/window preferences. If the
native capability gate remains unavailable, keep it explicitly unverified
while independent source/content work proceeds. No goal reduction or
critical goal-changing product issue is established.

Private .tools/renewal/t05-ime-preparation-1 retains selective identifiers/
native-access proof SHA7cb08d74f27d0c4bfd1425d6ac738eddd15225de47134ed584dca5bcda7bbec1
and complete source pins/read-boundary receipt SHA
eb303513979d022383450f18f2554a5bc3744a0b202ad1e3817c2ebd65b36733.
ChatBox.js50594/SHA3542ccea…60c5a; HTML1711/SHA44808bc5…6f9ef;
GUIComponent42213/SHA44b8767b…2a57; KeyEventHandler3858/SHAa6da3ef6…e69;
MapEngine38006/SHAf3ead6ab…85cc. No full preference/environment dump or
private credentials are recorded. Next owner root: resolve the native test
surface and freeze same-input Claude/Grok verification plans; neither
internal preparation aid earns provider credit or a passed IME gate.
