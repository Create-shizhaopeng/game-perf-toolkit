## ADDED Requirements

### Requirement: Trace metadata extraction

The system SHALL extract trace metadata as the first step of any analysis, including:
- Device model, manufacturer, SoC, Android version from `metadata` table
- Trace duration and timestamp range from `slice` table
- Total process count and thread count

#### Scenario: Extract device info from metadata

- **WHEN** LLM executes exploration queries on a new trace
- **THEN** `android_device_manufacturer`, `android_build_fingerprint`, `android_soc_model` are retrieved from the `metadata` table
- **AND** system machine info (`system_name`, `system_release`, `system_machine`) is retrieved

#### Scenario: Trace with incomplete metadata

- **WHEN** device metadata fields are NULL or missing
- **THEN** the exploration continues with available fields marked as "unknown"
- **AND** the header chapter renders "unknown" for missing fields without error

### Requirement: Target process identification

The system SHALL identify the primary application process by ranking processes by slice count and thread count, filtering out system processes.

System processes to exclude: `surfaceflinger`, `system_server`, `audioserver`, `servicemanager`, `hwcomposer`, `logd`, `statsd`, `netd`, `keystore`, processes under `/system/bin/`, `/vendor/bin/`, `/apex/`.

#### Scenario: Game trace with single dominant app

- **WHEN** a trace contains `com.tencent.tmgp.sgame` with 58 threads and 41K slices alongside system processes
- **THEN** `com.tencent.tmgp.sgame` is identified as the primary target
- **AND** `surfaceflinger` and `system_server` are excluded despite high slice counts

#### Scenario: Trace with no clear app process

- **WHEN** no non-system process has significant slice activity
- **THEN** system-level analysis mode is recommended (SF, binder, scheduler chapters)

### Requirement: Game engine and rendering pipeline detection

The system SHALL detect the game engine type by examining thread names in the target process.

Detection rules:
- Thread name matches `*Unity*` → Unity engine
- Thread name matches `*GameThread*` or `*RHIThread*` → Unreal engine
- Thread name matches `*cocos*` → Cocos engine
- Thread name matches `*Main::iteration*` or `*physics_process*` → Godot engine

The rendering pipeline SHALL be detected by examining slice names in rendering threads:
- `eglSwapBuffers` present → OpenGL ES
- `vkQueuePresentKHR` present → Vulkan
- `dequeueBuffer` on `SurfaceView` → SurfaceView rendering

#### Scenario: Unity game with SurfaceView + OpenGL ES

- **WHEN** target process has threads named `UnityMain` and `UnityGfxDeviceW`
- **AND** slices include `eglSwapBuffers` and `dequeueBuffer`
- **THEN** engine is detected as Unity, pipeline as SurfaceView + OpenGL ES
- **AND** the agent selects `game_fps_analysis` and `game_main_loop_jank` skills

#### Scenario: Unreal game with Vulkan

- **WHEN** target process has thread `GameThread` and slices match `vkQueuePresentKHR`
- **THEN** engine is detected as Unreal, pipeline as Vulkan
- **AND** the agent selects Vulkan-specific frame pacing analysis

### Requirement: FPS mode detection

The system SHALL detect the target FPS mode by analyzing frame interval distribution.

When FrameTimeline data is insufficient (games using SurfaceView/Vulkan), the system SHALL fall back to analyzing `eglSwapBuffers` or `vkQueuePresentKHR` intervals.

#### Scenario: 60fps game via swap intervals

- **WHEN** FrameTimeline `actual_frame_timeline_slice` returns only 154 frames (insufficient)
- **THEN** the agent falls back to analyzing `eglSwapBuffers` intervals from `UnityGfxDeviceW` thread
- **AND** 933 swap intervals are found with 69.8% in 14-17ms range → 60fps mode confirmed

### Requirement: Chapter selection from exploration results

The system SHALL select analysis chapters based on trace exploration results.

Selection rules:
- Game engine detected → fps, cpu, gpu, memory (mandatory)
- FrameTimeline data insufficient → fps chapter uses swap-based analysis
- `composer-service` slice count > 10K → sf_composition chapter
- Binder thread count > 3 → binder chapter
- Startup event detected → startup chapter
- Thermal/throttle counter present → thermal chapter

#### Scenario: Game trace chapter selection

- **WHEN** Unity engine detected, 933 eglSwapBuffers found, SurfaceView rendering confirmed
- **THEN** chapters selected: header, fps, cpu, gpu, memory, sf_composition, binder, root_causes
- **AND** fps chapter uses swap-based FPS analysis (not FrameTimeline-based)
