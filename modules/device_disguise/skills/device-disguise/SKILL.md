---
name: device-disguise
description: >-
  Guide for disguising Android device ODM properties (brand/manufacturer/model).
  Covers pre-flight checks, disguise execution, post-reboot verification, and
  troubleshooting. Use when the user asks to disguise a device, check disguise
  status, restore original values, or troubleshoot disguise failures.
category: device-operation
triggers:
  keywords: ["伪装", "disguise", "ODM", "build.prop", "device identity", "品牌修改"]
  patterns: ["(伪装|修改|还原).*(品牌|厂商|型号|ODM)"]
---

# Device Disguise Skill

## Overview

Modifies Android ODM (`ro.product.odm.*`) properties to change how the device
identifies itself to apps. The operation modifies `/odm/etc/build.prop` and
requires a reboot to take effect.

## Pre-flight Checks

1. **Verify device connection**: Call `device_status` to confirm the device is connected
   and retrieve current brand/manufacturer/model values.
2. **Confirm target values**: Ensure brand, manufacturer, and model are valid and match
   a known device profile. Check references/common_brands.md for valid combinations.
3. **Check disguise state**: If `is_disguised` is already true, warn that the device
   will be re-disguised (overwriting current ODM values).

## Execution Steps

### Step 1: Disguise

Call `device_disguise(serial=..., brand=..., manufacturer=..., model=...)`.

The function performs:
- ADB root → remount → setenforce 0
- Pull `/odm/etc/build.prop` → modify target properties → push back
- Reboot device → wait for boot complete → verify new values

**Evidence required**: After execution, the function returns a `DeviceState` with
verified ODM values. Confirm `current_brand`, `current_manufacturer`, `current_model`
match the requested target values.

### Step 2: Verify

Call `device_status(serial=...)` again to confirm the disguise persisted after reboot.

**Evidence required**: `is_disguised` should be `true` and current values should
match target values.

### Step 3: Register Profile (optional)

If the disguise combination is reusable, call `profile_add(brand=..., manufacturer=..., model=...)`
to save it for future use.

## Troubleshooting

### Disguise verification failed

If post-reboot values don't match targets:
1. Check ADB connection after reboot
2. Verify the device supports ODM property modification (some devices use vendor
   properties instead of ODM)
3. Check SELinux enforcement — should be permissive (`setenforce 0`)

### Device not rooted

The disguise operation requires root. If `device_status` shows root not available,
inform the user that root is required.

### Re-disguise after OTA update

OTA updates may restore original build.prop values. Check disguise status and
re-apply if needed.

## Conclusion Format

When reporting results:
- **Problem type**: disguise / restore / status-check / profile-management
- **Root cause** (if failure): root access denied / remount failed / verification mismatch
- **Result**: success (with current brand/mfr/model) or failure (with error details)
- **Confidence**: HIGH (verification values match), MEDIUM (partial match), LOW (post-reboot check failed)
- **Suggestion**: at least one actionable next step
