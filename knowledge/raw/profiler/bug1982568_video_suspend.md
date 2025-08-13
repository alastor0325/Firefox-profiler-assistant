---
id: fxpa-bug1982568-video-suspend
title: Video Suspended Due to Invisible Media Element
source: bugzilla
bugzilla_id: 1982568
bugzilla_link: https://bugzilla.mozilla.org/show_bug.cgi?id=1982568
profile_link: https://share.firefox.dev/4oyDtd7
product_area: "Firefox Profiler"
tags: ["profiler", "media", "video", "suspend", "visibility"]
updated_at: 2025-08-12
---

# Summary
Video playback produced only audio while the video track was suspended. Profiling shows that suspension was triggered because the media element was considered **invisible**, and it never resumed.

## Signals & Evidence
- **MediaDecoderStateMachine** thread at `~11.450s`: [`MDSM::EnterVideoSuspend`](https://share.firefox.dev/3UqFcU4).
- **MediaSupervisor** threads filtered with [`Update(Video)`](https://share.firefox.dev/46UxSaO): decoder in use was `blank media data decoder` (from `desc:` log message).
- **MediaDecoderStateMachine** markers filtered with `MediaDecoder,MDSM` to find [all related markers](https://share.firefox.dev/3UqVzzV): suspension marker immediately follows `MDSM::StateChange` at `11.450s`.
- Likely suspension trigger in code: [MediaDecoderStateMachine.cpp#3052-3059](https://searchfox.org/mozilla-central/rev/430cfd128fd71d4970c8475f2cf289ab0a8253a7/dom/media/MediaDecoderStateMachine.cpp#3052-3059).
- **GeckoMain** (tab) [markers filtered with `MediaDecoder`](https://share.firefox.dev/4oznGe5) : log `"set Suspend because of invisible element."` at `11.279s` — [reason for suspension](https://searchfox.org/mozilla-central/rev/430cfd128fd71d4970c8475f2cf289ab0a8253a7/dom/media/MediaDecoder.cpp#1227-1229).
- No `UpdateVideoDecodeMode(), set Normal ...` logs → video remained suspended.
- `MediaDecoder::mIsOwnerInvisible` modified [here](https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/MediaDecoder.cpp#1141) with `aIsOwnerInvisible = true`.
- `MediaDecoder::NotifyOwnerActivityChanged()` can only be called [here](https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/mediaelement/HTMLMediaElement.cpp#7778-7780), meaning [`HTMLMediaElement::IsActuallyInvisible()` returns true](https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/mediaelement/HTMLMediaElement.cpp#6459-6480).
- **GeckoMain** markers filtered with `HTMLMediaElement`: [all HTMLMediaElement markers](https://share.firefox.dev/45x7aT0) show no `OnVisibilityChange` logs. Closest related log: `SuspendOrResumeElement(suspend=0) docHidden=0` — [owner doc not hidden](https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/mediaelement/HTMLMediaElement.cpp#6718-6719).

## Analysis & Reasoning
The `"invisible element"` log confirms that suspension was triggered by the visibility logic.
`mIsOwnerInvisible` being set to `true` indicates `HTMLMediaElement::IsActuallyInvisible()` evaluated to true.
That can happen if:
- The element is **not connected** ([HTMLMediaElement.cpp#6460-6471](https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/mediaelement/HTMLMediaElement.cpp#6460-6471)), or
- The element is **outside the viewport** ([HTMLMediaElement.cpp#6466-6471](https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/mediaelement/HTMLMediaElement.cpp#6466-6471)).

The absence of `OnVisibilityChange` markers suggests that the status change was inferred from element connection or layout state rather than an explicit visibility event.
No resume markers (`UpdateVideoDecodeMode()`) were seen, meaning the decoder stayed suspended for the entire session.

## Conclusion
Suspension was triggered by visibility logic marking the `<video>` element invisible, either due to DOM detachment or being outside the viewport. Playback remained audio-only because normal decoding was never resumed.

## References
- Bugzilla: https://bugzilla.mozilla.org/show_bug.cgi?id=1982568
- Profile: https://share.firefox.dev/4oyDtd7
- Key code references:
  - `MediaDecoderStateMachine.cpp#3052-3059` — https://searchfox.org/mozilla-central/rev/430cfd128fd71d4970c8475f2cf289ab0a8253a7/dom/media/MediaDecoderStateMachine.cpp#3052-3059
  - `MediaDecoder.cpp#1227-1229` — https://searchfox.org/mozilla-central/rev/430cfd128fd71d4970c8475f2cf289ab0a8253a7/dom/media/MediaDecoder.cpp#1227-1229
  - `MediaDecoder.cpp#1141` — https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/MediaDecoder.cpp#1141
  - `HTMLMediaElement.cpp#6459-6480` — https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/mediaelement/HTMLMediaElement.cpp#6459-6480
  - `HTMLMediaElement.cpp#6460-6471` — https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/mediaelement/HTMLMediaElement.cpp#6460-6471
  - `HTMLMediaElement.cpp#6466-6471` — https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/mediaelement/HTMLMediaElement.cpp#6466-6471
  - `HTMLMediaElement.cpp#6718-6719` — https://searchfox.org/mozilla-central/rev/c85c168374483a3c37aab49d7f587ea74a516492/dom/media/mediaelement/HTMLMediaElement.cpp#6718-6719
