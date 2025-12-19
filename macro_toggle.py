from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pynput import keyboard, mouse
from pynput.keyboard import Key, KeyCode, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController

CONFIG_PATH = Path(__file__).with_name("macros.json")

# --- pydirectinput（Windowsゲーム向け） ---
try:
    import pydirectinput as PDI  # type: ignore
except Exception:
    PDI = None

USE_PDI = sys.platform.startswith("win") and (PDI is not None)

K = KeyboardController()     # fallback
M = MouseController()        # fallback

KeyLike = Union[Key, KeyCode]


def load_config() -> Dict[str, Any]:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not data.get("trigger_hotkey") and not data.get("trigger_key"):
        raise ValueError('macros.json に "trigger_hotkey" か "trigger_key" が必要です。')
    if "macro" not in data:
        raise ValueError('macros.json に "macro" が必要です。')
    return data


def parse_key_pynput(s: str) -> KeyLike:
    s = s.strip()
    if s.startswith("Key."):
        name = s.split(".", 1)[1]
        try:
            return getattr(Key, name)
        except AttributeError as e:
            raise ValueError(f"不明なキー名: {s}") from e
    if len(s) == 1:
        return KeyCode.from_char(s)
    raise ValueError(f"キー指定は 'Key.xxx' か 1文字のみ対応です: {s}")


def key_matches(event_key: KeyLike, target: KeyLike) -> bool:
    if isinstance(event_key, Key) and isinstance(target, Key):
        return event_key == target
    if isinstance(event_key, KeyCode) and isinstance(target, KeyCode):
        return event_key == target
    return False


# ---- pydirectinput 用キー名変換 ----
PDI_KEY_MAP: Dict[str, str] = {
    "Key.enter": "enter",
    "Key.esc": "esc",
    "Key.tab": "tab",
    "Key.space": "space",
    "Key.backspace": "backspace",
    "Key.delete": "delete",
    "Key.home": "home",
    "Key.end": "end",
    "Key.page_up": "pageup",
    "Key.page_down": "pagedown",
    "Key.up": "up",
    "Key.down": "down",
    "Key.left": "left",
    "Key.right": "right",
    "Key.shift": "shift",
    "Key.shift_l": "shift",
    "Key.shift_r": "shift",
    "Key.ctrl": "ctrl",
    "Key.ctrl_l": "ctrl",
    "Key.ctrl_r": "ctrl",
    "Key.alt": "alt",
    "Key.alt_l": "alt",
    "Key.alt_r": "alt",
}
for i in range(1, 25):
    PDI_KEY_MAP[f"Key.f{i}"] = f"f{i}"


def to_pdi_key(raw: str) -> str:
    raw = raw.strip()
    if len(raw) == 1:
        return raw
    return PDI_KEY_MAP.get(raw, raw.replace("Key.", ""))


def to_pdi_button(btn: str) -> str:
    b = btn.strip().lower()
    if b in ("left", "right", "middle"):
        return b
    raise ValueError('button は "left"/"right"/"middle" のみ対応です')


class HoldState:
    """
    停止時に「押しっぱなし」を必ず解放するための状態。
    token 例:
      - "key:a"
      - "key:Key.ctrl_l"
      - "mouse:left"
    """
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._held: set[str] = set()

    def mark_down(self, token: str) -> None:
        with self._lock:
            self._held.add(token)

    def mark_up(self, token: str) -> None:
        with self._lock:
            self._held.discard(token)

    def release_all(self) -> None:
        with self._lock:
            tokens = list(self._held)
            self._held.clear()

        for t in tokens:
            try:
                kind, val = t.split(":", 1)
                if kind == "key":
                    if USE_PDI:
                        PDI.keyUp(to_pdi_key(val))  # type: ignore
                    else:
                        K.release(parse_key_pynput(val))
                elif kind == "mouse":
                    if USE_PDI:
                        PDI.mouseUp(button=to_pdi_button(val))  # type: ignore
                    else:
                        btn = Button.left if val == "left" else (Button.right if val == "right" else Button.middle)
                        M.release(btn)
            except Exception:
                pass


def do_step(step: Dict[str, Any], stop_event: threading.Event, hold: HoldState) -> None:
    t = step.get("type")

    if t == "wait":
        stop_event.wait(timeout=float(step.get("seconds", 0)))
        return

    if stop_event.is_set():
        return

    if t == "text":
        text = str(step.get("text", ""))
        if USE_PDI:
            PDI.write(text, interval=0)  # type: ignore
        else:
            K.type(text)
        return

    if t == "key":
        raw = str(step["key"])
        action = str(step.get("action", "tap"))

        if USE_PDI:
            k = to_pdi_key(raw)
            token = f"key:{raw}"
            if action == "tap":
                PDI.press(k)  # type: ignore
                return
            if action == "press":
                PDI.keyDown(k)  # type: ignore
                hold.mark_down(token)
                return
            if action == "release":
                PDI.keyUp(k)  # type: ignore
                hold.mark_up(token)
                return
            raise ValueError('key.action は "tap"/"press"/"release" のみ')

        # fallback: pynput
        key = parse_key_pynput(raw)
        token = f"key:{raw}"
        if action == "tap":
            K.press(key); K.release(key)
            return
        if action == "press":
            K.press(key); hold.mark_down(token)
            return
        if action == "release":
            K.release(key); hold.mark_up(token)
            return
        raise ValueError('key.action は "tap"/"press"/"release" のみ')

    if t == "combo":
        raw_keys = [str(k) for k in step.get("keys", [])]
        if not raw_keys:
            return

        if USE_PDI:
            for rk in raw_keys:
                PDI.keyDown(to_pdi_key(rk))  # type: ignore
            for rk in reversed(raw_keys):
                PDI.keyUp(to_pdi_key(rk))  # type: ignore
            return

        keys = [parse_key_pynput(rk) for rk in raw_keys]
        for k in keys:
            K.press(k)
        for k in reversed(keys):
            K.release(k)
        return

    if t == "mouse_click":
        button = str(step.get("button", "left"))
        count = int(step.get("count", 1))
        if USE_PDI:
            PDI.click(button=to_pdi_button(button), clicks=max(1, count), interval=0)  # type: ignore
            return
        btn = Button.left if button == "left" else (Button.right if button == "right" else Button.middle)
        for _ in range(max(1, count)):
            M.click(btn)
        return

    # ★追加：マウス押しっぱなし
    if t == "mouse_button":
        button = str(step.get("button", "left"))
        action = str(step.get("action", "tap"))
        token = f"mouse:{button}"

        if USE_PDI:
            b = to_pdi_button(button)
            if action == "tap":
                PDI.click(button=b, clicks=1, interval=0)  # type: ignore
                return
            if action == "press":
                PDI.mouseDown(button=b)  # type: ignore
                hold.mark_down(token)
                return
            if action == "release":
                PDI.mouseUp(button=b)  # type: ignore
                hold.mark_up(token)
                return
            raise ValueError('mouse_button.action は "tap"/"press"/"release" のみ')

        # fallback
        btn = Button.left if button == "left" else (Button.right if button == "right" else Button.middle)
        if action == "tap":
            M.click(btn); return
        if action == "press":
            M.press(btn); hold.mark_down(token); return
        if action == "release":
            M.release(btn); hold.mark_up(token); return
        raise ValueError('mouse_button.action は "tap"/"press"/"release" のみ')

    if t == "mouse_move":
        mode = str(step.get("mode", "relative"))
        x = int(step.get("x", 0))
        y = int(step.get("y", 0))
        if USE_PDI:
            if mode == "relative":
                PDI.moveRel(x, y)  # type: ignore
                return
            if mode == "absolute":
                PDI.moveTo(x, y)  # type: ignore
                return
            raise ValueError('mouse_move.mode は "relative"/"absolute" のみ')
        if mode == "relative":
            M.move(x, y); return
        if mode == "absolute":
            M.position = (x, y); return
        raise ValueError('mouse_move.mode は "relative"/"absolute" のみ')

    if t == "mouse_scroll":
        dx = int(step.get("dx", 0))
        dy = int(step.get("dy", 0))
        if USE_PDI:
            # pydirectinput は縦スクロール中心
            if dy != 0:
                PDI.scroll(dy)  # type: ignore
            return
        M.scroll(dx, dy)
        return

    raise ValueError(f"不明な step.type: {t}")


class MacroTool:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.trigger_hotkey: Optional[str] = (
            str(config.get("trigger_hotkey")).strip() if config.get("trigger_hotkey") else None
        )
        self.quit_hotkey: Optional[str] = (
            str(config.get("quit_hotkey")).strip() if config.get("quit_hotkey") else None
        )

        self.trigger_key: Optional[KeyLike] = (
            parse_key_pynput(str(config["trigger_key"])) if config.get("trigger_key") else None
        )
        self.quit_key: Optional[KeyLike] = (
            parse_key_pynput(str(config["quit_key"])) if config.get("quit_key") else None
        )

        self.loop: bool = bool(config.get("loop", False))
        self.macro: List[Dict[str, Any]] = list(config.get("macro", []))

        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        self._down: set[str] = set()
        self._hotkeys: Optional[keyboard.GlobalHotKeys] = None

        self._hold = HoldState()

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self) -> None:
        with self.lock:
            if self.is_running():
                return
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            print(f"[macro] started (USE_PDI={USE_PDI})")

    def stop(self) -> None:
        self.stop_event.set()
        # 停止した瞬間に押しっぱなしを必ず解放
        self._hold.release_all()

        with self.lock:
            if self.is_running():
                print("[macro] stopping...")

    def toggle(self) -> None:
        if self.is_running():
            self.stop()
        else:
            self.start()

    def request_quit(self) -> None:
        print("[macro] quitting...")
        self.stop()
        if self._hotkeys is not None:
            self._hotkeys.stop()

    def _run(self) -> None:
        try:
            if self.loop:
                while not self.stop_event.is_set():
                    for step in self.macro:
                        if self.stop_event.is_set():
                            break
                        do_step(step, self.stop_event, self._hold)
            else:
                for step in self.macro:
                    if self.stop_event.is_set():
                        break
                    do_step(step, self.stop_event, self._hold)
        finally:
            self._hold.release_all()
            print("[macro] stopped")

    # --- 単キー監視（必要な人向け） ---
    def _key_id(self, k: KeyLike) -> str:
        if isinstance(k, Key):
            return f"Key.{k.name}"
        if isinstance(k, KeyCode):
            return f"Char.{k.char}"
        return str(k)

    def _on_press_single(self, k: KeyLike) -> Optional[bool]:
        kid = self._key_id(k)
        if kid in self._down:
            return None
        self._down.add(kid)

        if self.trigger_key is not None and key_matches(k, self.trigger_key):
            self.toggle()
            return None

        if self.quit_key is not None and key_matches(k, self.quit_key):
            self.request_quit()
            return False

        return None

    def _on_release_single(self, k: KeyLike) -> None:
        self._down.discard(self._key_id(k))

    def run_forever(self) -> None:
        if self.trigger_hotkey:
            mapping = {self.trigger_hotkey: self.toggle}
            if self.quit_hotkey:
                mapping[self.quit_hotkey] = self.request_quit

            print(f"[macro] trigger_hotkey={self.trigger_hotkey} / quit_hotkey={self.quit_hotkey}")
            print(f"[macro] listening (GlobalHotKeys) / USE_PDI={USE_PDI}")

            with keyboard.GlobalHotKeys(mapping) as h:
                self._hotkeys = h
                h.join()
            return

        if self.trigger_key is None:
            raise ValueError("trigger_hotkey も trigger_key も設定されていません。")

        print(f"[macro] trigger_key={self.trigger_key} / quit_key={self.quit_key}")
        print(f"[macro] listening (single key) / USE_PDI={USE_PDI}")

        with keyboard.Listener(on_press=self._on_press_single, on_release=self._on_release_single) as l:
            l.join()


def main() -> None:
    config = load_config()
    MacroTool(config).run_forever()


if __name__ == "__main__":
    main()
