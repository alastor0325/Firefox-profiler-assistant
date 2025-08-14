---
id: gecko.media.MediaDecoderStateMachine
title: MediaDecoderStateMachine
kind: gecko-class
component: dom/media
aliases: [MDSM, StateMachine]
links:
  - type: source
    url: https://searchfox.org/mozilla-central/source/dom/media/MediaDecoderStateMachine.h
  - type: source
    url: https://searchfox.org/mozilla-central/source/dom/media/MediaDecoderStateMachineBase.cpp
  - type: source
    url: https://searchfox.org/mozilla-central/rev/ce0d41b6033e2a104904327a43edf730245f5241/dom/media/MediaDecoderStateMachine.h#40-111
---

## Summary
The **MediaDecoderStateMachine** (MDSM) coordinates playback: it requests decoded A/V from `MediaFormatReader`, buffers it (`MediaQueue<AudioData>`, `MediaQueue<VideoData>`), schedules state updates (ticks), drives A/V sync and frame dropping, and controls the `MediaSink`. It inherits common behavior from `MediaDecoderStateMachineBase`.

## Threads
- `MediaDecoderStateMachine` — the state‑machine task queue [1]. Runs core state logic and schedules ticks.
- `GeckoMain` — the main thread where `MediaDecoder`/DOM interactions occur (element control, notifications).

## Profiler Markers
### Normal
- `MDSM::StateChange`. A state transition has occurred; the marker payload contains the new state.
- `MDSM::PlayStateChanged`. The play state, controlled by `MediaDecoder`, has changed; the marker payload contains the new play state.
- `MDSM::VolumeChanged`. The volume has changed; the marker payload contains the new volume value.
- `MDSM::PushAudio`. A decoded audio frame has been pushed to the audio queue.
- `MDSM::PushVideo`. A decoded video frame has been pushed to the video queue.
- `MDSM::Shutdown`. The state machine is shutting down.
- `MDSM::BufferedRangeUpdated`. The buffered range has been updated.
- `MDSM::Seek`. A seek operation is in progress.
- `MDSM::DropVideoUpToSeekTarget`. During a seek, video frames are discarded until the target frame is reached (initial seek may land on a keyframe earlier than the target).
- `MDSM::LoopingChanged`. The looping state has changed. Since looping playback uses its own state to handle seamless playback, it’s useful to know whether looping is active during analysis.

### Troubleshooting
- `Video falling behind`. Video decoding is lagging (or the audio clock is advancing unusually fast).
- `MDSM::EnterVideoSuspend`. Video is suspended and decoding has paused, resulting in black video frames.
- `Skipping to next keyframe`. Non‑key frames are being skipped to decode the next available keyframe; can appear as a freeze when video decoding is too slow.
- `MDSM::StartBuffering`. Playback has started buffering; the marker payload contains the reason.

## Observability
### State transitions
This class is a finite state machine, with various states [2], implemented by corresponding state objects [3]. It’s crucial to know which state MDSM is in, as each state object has its own logic. For example, when a seek occurs, MDSM transitions to a seek state depending on the type of seek.

### Playback stalls
A stall typically means the state is either **dormant** (doing nothing, releasing resources) or **buffering** (waiting to accumulate more decoded data). Buffering can be caused by slow network throughput, insufficient MSE appends, or consumption outpacing decode.

### A/V desynchronization
First locate the log entry `StartMediaSink, mediaTime=XXX` to determine the start time. Then review logs and markers together across `AudioSink`, `AudioSinkWrapper`, `VideoSink`, and `DecodedStream` to pinpoint the issue. Also check whether any seeking or frame skipping occurred during the period.

## Related Components
- `MediaDecoder` — lifecycle owner; receives and forwards DOM‑facing control from `HTMLMediaElement`.
- `MediaFormatReader` — demuxing/decoding backend that feeds MDSM queues.
- `MediaSink` — A/V output and sync surface (e.g., `AudioSink`, `AudioSinkWrapper`, `VideoSink`, `DecodedStream`).

## References
[1] Thread name: https://searchfox.org/mozilla-central/rev/ce0d41b6033e2a104904327a43edf730245f5241/dom/media/VideoUtils.cpp#261-264
[2] States: https://searchfox.org/mozilla-central/rev/ce0d41b6033e2a104904327a43edf730245f5241/dom/media/MediaDecoderStateMachine.h#128-141
[3] State object: https://searchfox.org/mozilla-central/rev/ce0d41b6033e2a104904327a43edf730245f5241/dom/media/MediaDecoderStateMachine.h#418
