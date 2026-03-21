"""DeviceState 模型测试 — is_disguised 逻辑覆盖"""

from toolkit.sdk.models import DeviceState


class TestDeviceState:
    def test_not_connected_is_not_disguised(self) -> None:
        state = DeviceState(is_connected=False, current_brand="A", original_brand="B")
        assert not state.is_disguised

    def test_same_props_not_disguised(self) -> None:
        state = DeviceState(
            is_connected=True,
            current_brand="Samsung",
            current_manufacturer="Samsung",
            current_model="SM-G991B",
            original_brand="Samsung",
            original_manufacturer="Samsung",
            original_model="SM-G991B",
        )
        assert not state.is_disguised

    def test_different_brand_is_disguised(self) -> None:
        state = DeviceState(
            is_connected=True,
            current_brand="Apple",
            current_manufacturer="Samsung",
            current_model="SM-G991B",
            original_brand="Samsung",
            original_manufacturer="Samsung",
            original_model="SM-G991B",
        )
        assert state.is_disguised

    def test_different_manufacturer_is_disguised(self) -> None:
        state = DeviceState(
            is_connected=True,
            current_brand="Samsung",
            current_manufacturer="Foxconn",
            current_model="SM-G991B",
            original_brand="Samsung",
            original_manufacturer="Samsung",
            original_model="SM-G991B",
        )
        assert state.is_disguised

    def test_different_model_is_disguised(self) -> None:
        state = DeviceState(
            is_connected=True,
            current_brand="Samsung",
            current_manufacturer="Samsung",
            current_model="Pixel-7",
            original_brand="Samsung",
            original_manufacturer="Samsung",
            original_model="SM-G991B",
        )
        assert state.is_disguised

    def test_all_different_is_disguised(self) -> None:
        state = DeviceState(
            is_connected=True,
            current_brand="Apple",
            current_manufacturer="Apple",
            current_model="iPhone15",
            original_brand="Samsung",
            original_manufacturer="Samsung",
            original_model="SM-G991B",
        )
        assert state.is_disguised

    def test_default_empty_not_disguised(self) -> None:
        state = DeviceState()
        assert not state.is_disguised

    def test_connected_empty_strings_not_disguised(self) -> None:
        state = DeviceState(is_connected=True)
        assert not state.is_disguised
