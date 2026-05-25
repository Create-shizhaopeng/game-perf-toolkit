## ADDED Requirements

### Requirement: Game FPS analysis supports non-FrameTimeline frame detection

The `game_fps_analysis.skill.yaml` SHALL document that games using SurfaceView + OpenGL ES or Vulkan bypass Android FrameTimeline, and SHALL guide the Agent to fall back to `eglSwapBuffers` or `vkQueuePresentKHR` interval analysis.

The skill SHALL include documentation describing:
- When FrameTimeline data is insufficient (< 20% of expected frames)
- How to identify the rendering thread (`UnityGfxDeviceW`, `GameThread`, etc.)
- How to analyze frame intervals from swap buffer slices

#### Scenario: Agent detects insufficient FrameTimeline data

- **WHEN** `actual_frame_timeline_slice` returns significantly fewer frames than expected (e.g., 154 vs ~900 based on swap count)
- **THEN** the Agent reads the skill's alternative detection documentation
- **AND** switches to swap-based frame interval analysis using `eglSwapBuffers` slices from the rendering thread

#### Scenario: Game with Vulkan rendering

- **WHEN** target process contains `vkQueuePresentKHR` slices instead of `eglSwapBuffers`
- **THEN** the Agent uses `vkQueuePresentKHR` intervals for FPS and jank analysis
- **AND** the analysis follows the same interval-based methodology

### Requirement: Game main loop jank covers rendering pipeline slices

The `game_main_loop_jank.skill.yaml` SHALL cover key rendering pipeline slices beyond engine-specific loops, including:

- `dequeueBuffer` — buffer acquisition wait time
- `eglSwapBuffers` — swap/present operation
- `queueBuffer` — buffer submission to SurfaceFlinger
- `GPU completion` + `waitForever` — GPU fence wait time
- `waitForever` on rendering threads — GPU sync point blocking

These slices SHALL be matched by slice name patterns in the SQL `WHERE` clause, not by thread name alone.

#### Scenario: dequeueBuffer becomes the jank root cause

- **WHEN** the game has 934 dequeueBuffer calls on UnityGfxDeviceW with individual durations up to 31.6ms
- **THEN** `game_main_loop_jank` captures these as `engine_work` phase slices
- **AND** the `slow_engine_slices` step lists the longest dequeueBuffer calls with their timestamps and durations

#### Scenario: GPU completion waitForever indicates fence blocking

- **WHEN** the `GPU completion` thread has 932 `waitForever` calls averaging 2.2ms with max 46.2ms
- **THEN** the skill captures `waitForever` slices in the slow slices list
- **AND** the phase is classified as `present_wait` (waiting for GPU to complete rendering)
