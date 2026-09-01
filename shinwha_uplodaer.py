import json
import platform
import queue
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_resource_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", get_app_dir())).resolve()


def resolve_resource_dir(name: str) -> Path:
    external_path = get_app_dir() / name
    if external_path.exists():
        return external_path
    return get_resource_dir() / name


BASE_DIR = get_app_dir()
FIRMWARE_DIR = resolve_resource_dir("firmware")
SETTINGS_PATH = BASE_DIR / "shinwhatech_uploader_settings.json"
LEGACY_SETTINGS_PATH = BASE_DIR / "shinwha_uplodaer_settings.json"
BOARDS_PATH = BASE_DIR / "boards.txt"
COMMANDS_PATH = BASE_DIR / "commands.txt"
GITHUB_REPO_OWNER = "ttnada132-gif"
GITHUB_REPO_NAME = "shinwhatech"
GITHUB_REPO_URL = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}.git"
GITHUB_API_REPO_URL = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
GIT_DOWNLOAD_DIR = BASE_DIR / "git_download"
GIT_VERSION_PATH = GIT_DOWNLOAD_DIR / ".shinwhatech_git_version.json"
DEFAULT_BAUDS = ["115200", "230400", "460800", "921600"]
DEFAULT_SERIAL_BAUDS = ["9600", "115200", "230400", "460800", "921600"]
WINDOWS_PORT_KEYWORDS = ("ch340", "usb-serial", "usb serial", "cp210", "silicon labs")
LINUX_PORT_PREFIXES = ("/dev/ttyusb", "/dev/ttyacm", "/dev/serial/by-id/")
LINUX_PORT_KEYWORDS = ("ch340", "usb", "uart", "cp210", "serial")
DEFAULT_COMMAND_SETS: dict[str, list[dict[str, str]]] = {
    "c71_": [
        {"label": "RTC 보기", "command": "GETRTC"},
        {"label": "배터리 보기", "command": "GETBATT"},
        {"label": "배터리 보정", "command": "bat=12.30"},
        {"label": "배터리 보정(batcal)", "command": "batcal=12.30"},
        {"label": "배터리 계수 직접", "command": "bat_cal=1.104"},
        {"label": "RTC 설정", "command": "rtc=2026-08-13 12:34:56"},
        {"label": "RTC 설정(SETRTC)", "command": "SETRTC 2026-08-13 12:34:56"},
    ],
    "c72": [
        {"label": "설정 보기", "command": "show"},
        {"label": "내부 오디오", "command": "source=1"},
        {"label": "외부 오디오", "command": "source=2"},
        {"label": "배터리 보정", "command": "bat=12.30"},
        {"label": "트랙 재생", "command": "play=1"},
    ],
    "c72_with_streaming": [
        {"label": "스트림 재생", "command": "play"},
        {"label": "스트림 중지", "command": "stop"},
        {"label": "스트림 URL", "command": "url http://server-ip:5000/stream.mp3"},
    ],
    "shinwhatech_gas_detect_modem": [
        {"label": "설정 보기", "command": "show"},
        {"label": "서버 host", "command": "host=iotgw.raycom.co.kr"},
        {"label": "서버 port", "command": "port=8089"},
        {"label": "서버 path", "command": "path=/libra/iot/gw/v1.0/node"},
        {"label": "게이트웨이 AID", "command": "aid=SH_GW_0001"},
        {"label": "노드 NID", "command": "nid=SH_GAS_9000"},
        {"label": "HTTP token", "command": "token=0017B2FFFE0D252E"},
        {"label": "CO2 임계값", "command": "send_co2=3000"},
        {"label": "CH4 임계값", "command": "send_ch4=0.2"},
        {"label": "O2 하한", "command": "send_o2_low=20.0"},
        {"label": "O2 상한", "command": "send_o2_high=23.0"},
        {"label": "CO 임계값", "command": "send_co=6"},
        {"label": "H2S 임계값", "command": "send_h2s=2"},
        {"label": "온도 상한", "command": "send_temp_high=99"},
        {"label": "온도 하한", "command": "send_temp_low=-10"},
        {"label": "가스 보정", "command": "cal"},
    ],
    "shinwhatech_gas_detect_modem_v2": [
        {"label": "도움말", "command": "help"},
        {"label": "설정 보기", "command": "show"},
        {"label": "서버 host", "command": "host=iotgw.raycom.co.kr"},
        {"label": "서버 port", "command": "port=8089"},
        {"label": "서버 path", "command": "path=/libra/iot/gw/v1.0/node"},
        {"label": "게이트웨이 AID", "command": "aid=SH_GW_0001"},
        {"label": "노드 NID", "command": "nid=SH_GAS_9000"},
        {"label": "HTTP token", "command": "token=0017B2FFFE0D252E"},
        {"label": "배터리 보정", "command": "bat=12.30"},
        {"label": "네트워크 전체", "command": "net=111"},
        {"label": "Ethernet 전용", "command": "net=100"},
        {"label": "BG95 전용", "command": "net=010"},
        {"label": "Wi-Fi 전용", "command": "net=001"},
        {"label": "오프라인", "command": "net=000"},
        {"label": "CO2 임계값", "command": "send_co2=3000"},
        {"label": "CH4 임계값", "command": "send_ch4=0.2"},
        {"label": "O2 하한", "command": "send_o2_low=20.0"},
        {"label": "O2 상한", "command": "send_o2_high=23.0"},
        {"label": "CO 임계값", "command": "send_co=6"},
        {"label": "H2S 임계값", "command": "send_h2s=2"},
        {"label": "온도 상한", "command": "send_temp_high=99"},
        {"label": "온도 하한", "command": "send_temp_low=-10"},
        {"label": "가스 전체 보정", "command": "cal"},
        {"label": "O2 공기 보정", "command": "cal_o2_air"},
    ],
    "shinwhatech_sos": [
        {"label": "배터리 보정", "command": "bat=12.30"},
        {"label": "배터리 보정(battery)", "command": "battery=12.30"},
        {"label": "배터리 보정(battery_voltage)", "command": "battery_voltage=12.30"},
    ],
    "shinwha_gaegubu": [
        {"label": "도움말", "command": "help"},
        {"label": "설정 보기", "command": "show"},
        {"label": "기본값 초기화", "command": "reset"},
        {"label": "기본값 저장", "command": "set=default"},
        {"label": "서버 host", "command": "host=iotgw.raycom.co.kr"},
        {"label": "서버 port", "command": "port=8089"},
        {"label": "서버 path", "command": "path=/libra/iot/gw/v1.0/node"},
        {"label": "게이트웨이 AID", "command": "aid=SH_GW_0001"},
        {"label": "노드 NID", "command": "nid=SH_MOVE_0001"},
        {"label": "노드 번호", "command": "node_no=1"},
        {"label": "HTTP token", "command": "token=0017B2FFFE0D252E"},
        {"label": "Wi-Fi SSID", "command": "wifi_ssid=shth_"},
        {"label": "Wi-Fi PASS", "command": "wifi_pass=15553365"},
        {"label": "배터리 보정", "command": "bat=12.30"},
        {"label": "배터리 계수 직접", "command": "bat_cal=1.104"},
    ],
    "shinwha_movement": [
        {"label": "도움말", "command": "help"},
        {"label": "설정 보기", "command": "show"},
        {"label": "기본값 초기화", "command": "reset"},
        {"label": "서버 host", "command": "host=iotgw.raycom.co.kr"},
        {"label": "서버 port", "command": "port=8089"},
        {"label": "서버 path", "command": "path=/libra/iot/gw/v1.0/node"},
        {"label": "게이트웨이 AID", "command": "aid=SH_GW_0001"},
        {"label": "노드 NID", "command": "nid=SH_MOVE_0001"},
        {"label": "HTTP token", "command": "token=0017B2FFFE0D252E"},
    ],
    "shinwha_movement_offline": [
        {"label": "도움말", "command": "help"},
        {"label": "설정 보기", "command": "show"},
        {"label": "기본값 초기화", "command": "reset"},
        {"label": "서버 host", "command": "host=iotgw.raycom.co.kr"},
        {"label": "서버 port", "command": "port=8089"},
        {"label": "서버 path", "command": "path=/libra/iot/gw/v1.0/node"},
        {"label": "게이트웨이 AID", "command": "aid=SH_GW_0001"},
        {"label": "노드 NID", "command": "nid=SH_MOVE_0001"},
        {"label": "HTTP token", "command": "token=0017B2FFFE0D252E"},
    ],
    "shinwha_movement_v2": [
        {"label": "도움말", "command": "help"},
        {"label": "설정 보기", "command": "show"},
        {"label": "기본값 초기화", "command": "reset"},
        {"label": "오디오 중지", "command": "stopaudio"},
        {"label": "서버 host", "command": "host=iotgw.raycom.co.kr"},
        {"label": "서버 port", "command": "port=8089"},
        {"label": "서버 path", "command": "path=/libra/iot/gw/v1.0/node"},
        {"label": "게이트웨이 AID", "command": "aid=SH_GW_0001"},
        {"label": "노드 NID", "command": "nid=SH_MOVE_0001"},
        {"label": "노드 번호", "command": "node_no=1"},
        {"label": "HTTP token", "command": "token=0017B2FFFE0D252E"},
        {"label": "배터리 보정", "command": "bat=12.30"},
        {"label": "배터리 계수 직접", "command": "bat_cal=1.104"},
        {"label": "Angle", "command": "angle=2.5"},
        {"label": "Alarm Angle", "command": "alarm_angle=2.5"},
        {"label": "트랙 재생", "command": "play=1"},
        {"label": "볼륨 설정", "command": "vol=15"},
        {"label": "앰프 mute", "command": "mute=1"},
        {"label": "앰프 unmute", "command": "mute=0"},
    ],
    "shinwha_movement_v2_offline": [
        {"label": "도움말", "command": "help"},
        {"label": "설정 보기", "command": "show"},
        {"label": "기본값 초기화", "command": "reset"},
        {"label": "오디오 중지", "command": "stopaudio"},
        {"label": "서버 host", "command": "host=iotgw.raycom.co.kr"},
        {"label": "서버 port", "command": "port=8089"},
        {"label": "서버 path", "command": "path=/libra/iot/gw/v1.0/node"},
        {"label": "게이트웨이 AID", "command": "aid=SH_GW_0001"},
        {"label": "노드 NID", "command": "nid=SH_MOVE_0001"},
        {"label": "HTTP token", "command": "token=0017B2FFFE0D252E"},
        {"label": "배터리 보정", "command": "bat=12.30"},
        {"label": "배터리 계수 직접", "command": "bat_cal=1.104"},
        {"label": "Angle", "command": "angle=2.5"},
        {"label": "Alarm Angle", "command": "alarm_angle=2.5"},
        {"label": "트랙 재생", "command": "play=1"},
        {"label": "볼륨 설정", "command": "vol=15"},
        {"label": "앰프 mute", "command": "mute=1"},
        {"label": "앰프 unmute", "command": "mute=0"},
    ],
    "shinwha_movement_v2_wifi": [
        {"label": "도움말", "command": "help"},
        {"label": "설정 보기", "command": "show"},
        {"label": "기본값 초기화", "command": "reset"},
        {"label": "오디오 중지", "command": "stopaudio"},
        {"label": "서버 host", "command": "host=iotgw.raycom.co.kr"},
        {"label": "서버 port", "command": "port=8089"},
        {"label": "서버 path", "command": "path=/libra/iot/gw/v1.0/node"},
        {"label": "게이트웨이 AID", "command": "aid=SH_GW_0001"},
        {"label": "노드 NID", "command": "nid=SH_MOVE_0001"},
        {"label": "노드 번호", "command": "node_no=1"},
        {"label": "HTTP token", "command": "token=0017B2FFFE0D252E"},
        {"label": "Wi-Fi SSID", "command": "wifi_ssid=shth_"},
        {"label": "Wi-Fi PASS", "command": "wifi_pass=15553365"},
        {"label": "배터리 보정", "command": "bat=12.30"},
        {"label": "배터리 계수 직접", "command": "bat_cal=1.104"},
        {"label": "Angle", "command": "angle=2.5"},
        {"label": "Alarm Angle", "command": "alarm_angle=2.5"},
        {"label": "트랙 재생", "command": "play=1"},
        {"label": "볼륨 설정", "command": "vol=15"},
        {"label": "앰프 mute", "command": "mute=1"},
        {"label": "앰프 unmute", "command": "mute=0"},
    ],
}
DEFAULT_FLASH_FILES = [
    {"name": "bootloader", "address": "0x1000", "path": FIRMWARE_DIR / "bootloader.bin"},
    {"name": "partitions", "address": "0x8000", "path": FIRMWARE_DIR / "partitions.bin"},
    {"name": "firmware", "address": "0x10000", "path": FIRMWARE_DIR / "firmware.bin"},
    {"name": "littlefs", "address": "0x250000", "path": FIRMWARE_DIR / "littlefs.bin"},
]
FLASH_FILE_ALIASES = {
    "bootloader": ("bootloader", "bootloadaer"),
    "partitions": ("partitions", "partition"),
    "firmware": ("firmware",),
    "littlefs": ("littlefs", "spiffs"),
}
ADDRESS_PATTERN = re.compile(r"^0x[0-9a-fA-F]+$")


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_raspberry_pi() -> bool:
    if not is_linux():
        return False
    model_path = Path("/proc/device-tree/model")
    try:
        return "raspberry pi" in model_path.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return "raspberry" in platform.uname().node.lower()


def get_platform_label() -> str:
    if is_windows():
        return "Windows"
    if is_raspberry_pi():
        return "Raspberry Pi"
    if is_linux():
        return "Linux"
    return platform.system() or sys.platform


def get_port_hint() -> str:
    if is_windows():
        return "COM26"
    if is_linux():
        return "/dev/ttyUSB0 또는 /dev/ttyACM0"
    return "시리얼 포트"


def is_preferred_serial_port(port_info: object) -> bool:
    device = str(getattr(port_info, "device", "") or "")
    haystack = " ".join(
        str(value or "")
        for value in (
            getattr(port_info, "device", ""),
            getattr(port_info, "description", ""),
            getattr(port_info, "manufacturer", ""),
            getattr(port_info, "hwid", ""),
        )
    ).lower()
    device_lower = device.lower()

    if is_windows():
        return any(keyword in haystack for keyword in WINDOWS_PORT_KEYWORDS)
    if is_linux():
        return (
            any(device_lower.startswith(prefix) for prefix in LINUX_PORT_PREFIXES)
            or any(keyword in haystack for keyword in LINUX_PORT_KEYWORDS)
        )
    return True


def add_linux_uart_fallback_ports(ports: list[str]) -> None:
    if not is_linux():
        return
    for candidate in ("/dev/serial0", "/dev/serial1", "/dev/ttyS0"):
        path = Path(candidate)
        if path.exists() and candidate not in ports:
            ports.append(candidate)


def get_existing_settings_path() -> Path:
    if SETTINGS_PATH.exists():
        return SETTINGS_PATH
    if LEGACY_SETTINGS_PATH.exists():
        return LEGACY_SETTINGS_PATH
    return SETTINGS_PATH


def bool_from_setting(value: object, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", ""}
    if value is None:
        return default
    return bool(value)


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(BASE_DIR.resolve()))
    except ValueError:
        return str(path)


def path_from_setting(value: str, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    if path.is_absolute():
        return path
    external_path = BASE_DIR / path
    if external_path.exists():
        return external_path
    bundled_path = get_resource_dir() / path
    if bundled_path.exists():
        return bundled_path
    return external_path


def read_text_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        return [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    except Exception:
        return []


def load_boards() -> list[str]:
    boards = []
    seen = set()
    for board in DEFAULT_COMMAND_SETS:
        boards.append(board)
        seen.add(board)
    for line in read_text_lines(BOARDS_PATH):
        board = line.split(",", 1)[0].strip()
        if board and board not in seen:
            boards.append(board)
            seen.add(board)
    return boards


def split_command_items(text: str) -> list[str]:
    items = []
    current = []
    for part in text.split(","):
        if ":" in part and current:
            items.append(",".join(current).strip())
            current = [part]
        else:
            current.append(part)
    if current:
        items.append(",".join(current).strip())
    return [item for item in items if item]


def load_commands() -> dict[str, list[dict[str, str]]]:
    commands_by_board: dict[str, list[dict[str, str]]] = {
        board: [dict(command) for command in commands]
        for board, commands in DEFAULT_COMMAND_SETS.items()
    }
    for line in read_text_lines(COMMANDS_PATH):
        if "," not in line:
            continue
        board, command_text = line.split(",", 1)
        board = board.strip()
        if not board:
            continue

        for item in split_command_items(command_text):
            if ":" not in item:
                continue
            label, command = item.split(":", 1)
            label = label.strip()
            command = command.strip()
            if label and command:
                board_commands = commands_by_board.setdefault(board, [])
                if not any(
                    existing["label"] == label and existing["command"] == command
                    for existing in board_commands
                ):
                    board_commands.append({"label": label, "command": command})
    return commands_by_board


def list_firmware_folders() -> list[str]:
    folders: list[str] = []
    seen = set()

    def add_folder(path: Path) -> None:
        if not path.exists() or not path.is_dir():
            return
        label = display_path(path)
        if label not in seen:
            folders.append(label)
            seen.add(label)

    add_folder(FIRMWARE_DIR)
    for base in (FIRMWARE_DIR, BASE_DIR / "latest_board", GIT_DOWNLOAD_DIR, GIT_DOWNLOAD_DIR / "1latest_board"):
        if not base.exists() or not base.is_dir():
            continue
        try:
            children = sorted(
                (path for path in base.iterdir() if path.is_dir()),
                key=lambda path: path.name.lower(),
            )
        except OSError:
            continue
        for child in children:
            add_folder(child)

    return folders


def find_flash_files_in_folder(folder: Path) -> dict[str, Path]:
    if not folder.exists() or not folder.is_dir():
        return {}

    bin_files = sorted(folder.glob("*.bin"), key=lambda path: path.name.lower())
    if not bin_files:
        bin_files = sorted(folder.rglob("*.bin"), key=lambda path: len(path.parts))

    found: dict[str, Path] = {}
    for name, aliases in FLASH_FILE_ALIASES.items():
        for path in bin_files:
            stem = path.stem.lower()
            if any(stem == alias for alias in aliases):
                found[name] = path
                break
        if name in found:
            continue
        for path in bin_files:
            stem = path.stem.lower()
            if any(alias in stem for alias in aliases):
                found[name] = path
                break
    return found


def git_download_is_empty() -> bool:
    if not GIT_DOWNLOAD_DIR.exists():
        return True
    try:
        return not any(path.name != GIT_VERSION_PATH.name for path in GIT_DOWNLOAD_DIR.iterdir())
    except OSError:
        return True


def run_process_capture(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return completed.returncode, completed.stdout.strip()
    except Exception as exc:
        return 1, str(exc)


def read_json_url(url: str, timeout: int = 15) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "shinwhatech-uploader",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_remote_git_info() -> dict[str, str]:
    repo = read_json_url(GITHUB_API_REPO_URL)
    branch = str(repo.get("default_branch") or "main")
    commit = read_json_url(f"{GITHUB_API_REPO_URL}/commits/{branch}")
    sha = str(commit.get("sha") or "").strip()
    if not sha:
        raise RuntimeError("GitHub latest commit SHA not found")
    return {"branch": branch, "sha": sha}


def get_local_git_sha() -> str:
    if (GIT_DOWNLOAD_DIR / ".git").exists():
        rc, output = run_process_capture(["git", "-C", str(GIT_DOWNLOAD_DIR), "rev-parse", "HEAD"], timeout=20)
        if rc == 0 and output:
            return output.splitlines()[-1].strip()

    if GIT_VERSION_PATH.exists():
        try:
            data = json.loads(GIT_VERSION_PATH.read_text(encoding="utf-8"))
            return str(data.get("sha") or "").strip()
        except Exception:
            return ""

    return ""


def remote_has_newer_commit(local_sha: str, remote_sha: str) -> bool:
    if not local_sha:
        return True
    if local_sha == remote_sha:
        return False

    try:
        compare = read_json_url(f"{GITHUB_API_REPO_URL}/compare/{local_sha}...{remote_sha}")
        return str(compare.get("status") or "").lower() in {"behind", "diverged"}
    except Exception:
        return True


def save_local_git_version(remote_info: dict[str, str]) -> None:
    GIT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    GIT_VERSION_PATH.write_text(
        json.dumps(
            {
                "repo": GITHUB_REPO_URL,
                "branch": remote_info["branch"],
                "sha": remote_info["sha"],
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def clear_directory_contents(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    base = path.resolve()
    for child in path.iterdir():
        resolved = child.resolve()
        if base not in resolved.parents and resolved != base:
            raise RuntimeError(f"Unexpected path outside git_download: {resolved}")
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def download_repo_zip(remote_info: dict[str, str]) -> None:
    zip_url = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/archive/{remote_info['sha']}.zip"
    with tempfile.TemporaryDirectory(prefix="shinwhatech_repo_") as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / "repo.zip"
        urllib.request.urlretrieve(zip_url, zip_path)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(temp_path)
        extracted_roots = [
            path for path in temp_path.iterdir()
            if path.is_dir() and path.name.startswith(f"{GITHUB_REPO_NAME}-")
        ]
        if not extracted_roots:
            raise RuntimeError("Downloaded GitHub zip did not contain repository files")

        clear_directory_contents(GIT_DOWNLOAD_DIR)
        for child in extracted_roots[0].iterdir():
            shutil.move(str(child), str(GIT_DOWNLOAD_DIR / child.name))

    save_local_git_version(remote_info)


def update_git_download(remote_info: dict[str, str]) -> None:
    git_exe = shutil.which("git")
    if git_exe and git_download_is_empty():
        GIT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        rc, output = run_process_capture(
            [git_exe, "clone", "--branch", remote_info["branch"], GITHUB_REPO_URL, str(GIT_DOWNLOAD_DIR)],
            cwd=BASE_DIR,
            timeout=300,
        )
        if rc == 0:
            save_local_git_version(remote_info)
            return

    if git_exe and (GIT_DOWNLOAD_DIR / ".git").exists():
        rc, output = run_process_capture([git_exe, "-C", str(GIT_DOWNLOAD_DIR), "fetch", "origin"], timeout=180)
        if rc != 0:
            raise RuntimeError(output or "git fetch failed")
        rc, output = run_process_capture(
            [git_exe, "-C", str(GIT_DOWNLOAD_DIR), "reset", "--hard", f"origin/{remote_info['branch']}"],
            timeout=120,
        )
        if rc != 0:
            raise RuntimeError(output or "git reset failed")
        save_local_git_version(remote_info)
        return

    download_repo_zip(remote_info)


def load_settings() -> dict:
    defaults = {
        "port": "",
        "upload_baud": "921600",
        "serial_baud": "115200",
        "firmware_folder": display_path(FIRMWARE_DIR),
        "selected_board": "",
        "selected_command": "",
        "files": [
            {
                "name": item["name"],
                "enabled": True,
                "address": item["address"],
                "path": display_path(item["path"]),
            }
            for item in DEFAULT_FLASH_FILES
        ],
    }
    settings_path = get_existing_settings_path()
    if not settings_path.exists():
        return defaults

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return defaults

    files_by_name = {
        str(item.get("name", "")): item
        for item in data.get("files", [])
        if isinstance(item, dict)
    }
    files = []
    for default in DEFAULT_FLASH_FILES:
        saved = files_by_name.get(default["name"], {})
        saved_path = path_from_setting(str(saved.get("path", "")), default["path"])
        files.append(
            {
                "name": default["name"],
                "enabled": bool_from_setting(saved.get("enabled", True)),
                "address": str(saved.get("address", default["address"])).strip() or default["address"],
                "path": display_path(saved_path),
            }
        )

    return {
        "port": str(data.get("port", defaults["port"])),
        "upload_baud": str(data.get("upload_baud", defaults["upload_baud"])),
        "serial_baud": str(data.get("serial_baud", defaults["serial_baud"])),
        "firmware_folder": str(data.get("firmware_folder", defaults["firmware_folder"])),
        "selected_board": str(data.get("selected_board", defaults["selected_board"])),
        "selected_command": str(data.get("selected_command", defaults["selected_command"])),
        "files": files,
    }


class BrightmonUploaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.update_worker: threading.Thread | None = None
        self.save_after_id: str | None = None
        self.serial_conn = None
        self.serial_lock = threading.Lock()
        self.serial_reader: threading.Thread | None = None
        self.serial_stop = threading.Event()
        self.remote_git_info: dict[str, str] | None = None
        self.update_blink_after_id: str | None = None
        self.update_blink_on = False

        settings = load_settings()
        self.port_var = tk.StringVar(value=settings["port"])
        self.upload_baud_var = tk.StringVar(value=settings["upload_baud"])
        self.serial_baud_var = tk.StringVar(value=settings["serial_baud"])
        self.firmware_folder_var = tk.StringVar(value=settings["firmware_folder"])
        self.board_var = tk.StringVar(value=settings["selected_board"])
        self.command_name_var = tk.StringVar(value=settings["selected_command"])
        self.command_text_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="대기 중")
        self.file_vars: list[dict[str, tk.Variable]] = []
        self.firmware_folders = list_firmware_folders()
        self.boards = load_boards()
        self.commands_by_board = load_commands()
        self.current_commands: list[dict[str, str]] = []
        self.log_lines: list[str] = []
        self.serial_log_lines: list[str] = []

        for file_setting in settings["files"]:
            self.file_vars.append(
                {
                    "name": tk.StringVar(value=file_setting["name"]),
                    "enabled": tk.BooleanVar(value=file_setting["enabled"]),
                    "address": tk.StringVar(value=file_setting["address"]),
                    "path": tk.StringVar(value=file_setting["path"]),
                }
            )

        self.root.title(f"Shinwha Firmware Uploader - {get_platform_label()}")
        self.root.geometry("840x650")
        self.root.minsize(760, 580)

        self._build_ui()
        self._bind_auto_save()
        self.refresh_ports()
        self.root.bind_all("<space>", self.on_space_upload)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self._poll_events)
        self.root.after(500, self.start_update_check)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Upload.TButton", font=("맑은 고딕", 15, "bold"), padding=(22, 12))
        style.configure("Update.TButton", font=("맑은 고딕", 10, "bold"), padding=(10, 8))
        style.configure("UpdateBlink.TButton", font=("맑은 고딕", 10, "bold"), padding=(10, 8), foreground="red")

        parent = ttk.Frame(self.root, padding=12)
        parent.grid(row=0, column=0, sticky="nsew")
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(5, weight=1)

        port_box = ttk.LabelFrame(parent, text="업로드 설정", padding=10)
        port_box.grid(row=0, column=0, sticky="ew")
        port_box.columnconfigure(1, weight=1)

        ttk.Label(port_box, text="포트").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.port_combo = ttk.Combobox(port_box, textvariable=self.port_var)
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=(10, 8), pady=(0, 8))
        ttk.Button(port_box, text="새로고침", command=self.refresh_ports).grid(
            row=0, column=2, sticky="ew", pady=(0, 8)
        )

        ttk.Label(port_box, text="업로드 보레이트").grid(row=1, column=0, sticky="w")
        self.upload_baud_combo = ttk.Combobox(
            port_box,
            textvariable=self.upload_baud_var,
            values=DEFAULT_BAUDS,
        )
        self.upload_baud_combo.grid(row=1, column=1, sticky="ew", padx=(10, 8))

        file_box = ttk.LabelFrame(parent, text="플래시 파일", padding=10)
        file_box.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        file_box.columnconfigure(3, weight=1)

        ttk.Label(file_box, text="펌웨어 폴더").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.firmware_folder_combo = ttk.Combobox(
            file_box,
            textvariable=self.firmware_folder_var,
            values=self.firmware_folders,
        )
        self.firmware_folder_combo.grid(row=0, column=2, columnspan=2, sticky="ew", padx=(10, 0), pady=(0, 8))
        ttk.Button(file_box, text="폴더 찾기", command=self.browse_firmware_folder).grid(
            row=0, column=4, sticky="ew", padx=(10, 0), pady=(0, 8)
        )
        ttk.Button(file_box, text="자동 채우기", command=self.apply_firmware_folder).grid(
            row=0, column=5, sticky="ew", padx=(8, 0), pady=(0, 8)
        )

        ttk.Label(file_box, text="업로드").grid(row=1, column=0, sticky="w", pady=(0, 6))
        ttk.Label(file_box, text="구분").grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(0, 6))
        ttk.Label(file_box, text="주소").grid(row=1, column=2, sticky="w", padx=(10, 0), pady=(0, 6))
        ttk.Label(file_box, text="파일 경로").grid(row=1, column=3, sticky="w", padx=(10, 0), pady=(0, 6))
        ttk.Label(file_box, text="상태").grid(row=1, column=4, sticky="w", padx=(10, 0), pady=(0, 6))

        self.status_labels: list[ttk.Label] = []
        for index, file_var in enumerate(self.file_vars):
            row = index + 2
            name = file_var["name"].get()
            ttk.Checkbutton(file_box, variable=file_var["enabled"]).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Label(file_box, text=name).grid(row=row, column=1, sticky="w", padx=(10, 0), pady=4)
            ttk.Entry(file_box, textvariable=file_var["address"], width=12).grid(
                row=row, column=2, sticky="ew", padx=(10, 0), pady=4
            )
            ttk.Entry(file_box, textvariable=file_var["path"]).grid(
                row=row, column=3, sticky="ew", padx=(10, 0), pady=4
            )
            status_label = ttk.Label(file_box, width=8)
            status_label.grid(row=row, column=4, sticky="w", padx=(10, 0), pady=4)
            self.status_labels.append(status_label)
            ttk.Button(
                file_box,
                text="찾기",
                command=lambda index=index: self.browse_file(index),
            ).grid(row=row, column=5, sticky="ew", padx=(8, 0), pady=4)

        command_box = ttk.LabelFrame(parent, text="시리얼 명령어 전송", padding=10)
        command_box.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        command_box.columnconfigure(1, weight=1)
        command_box.columnconfigure(3, weight=1)

        ttk.Label(command_box, text="보드 선택").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.board_combo = ttk.Combobox(command_box, textvariable=self.board_var, values=self.boards)
        self.board_combo.grid(row=0, column=1, sticky="ew", padx=(10, 8), pady=(0, 8))
        ttk.Button(command_box, text="목록 새로고침", command=self.reload_command_files).grid(
            row=0, column=2, sticky="ew", padx=(0, 8), pady=(0, 8)
        )
        ttk.Label(command_box, text="명령 보레이트").grid(row=0, column=3, sticky="e", pady=(0, 8))
        self.serial_baud_combo = ttk.Combobox(
            command_box,
            textvariable=self.serial_baud_var,
            values=DEFAULT_SERIAL_BAUDS,
            width=10,
        )
        self.serial_baud_combo.grid(row=0, column=4, sticky="ew", padx=(10, 0), pady=(0, 8))

        ttk.Label(command_box, text="명령어 선택").grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.command_combo = ttk.Combobox(command_box, textvariable=self.command_name_var)
        self.command_combo.grid(row=1, column=1, columnspan=4, sticky="ew", padx=(10, 0), pady=(0, 8))

        ttk.Label(command_box, text="실제 문자열").grid(row=2, column=0, sticky="w")
        ttk.Entry(command_box, textvariable=self.command_text_var).grid(
            row=2, column=1, columnspan=3, sticky="ew", padx=(10, 8)
        )
        self.command_send_button = ttk.Button(
            command_box,
            text="전송",
            command=self.start_send_command,
        )
        self.command_send_button.grid(row=2, column=4, sticky="ew")
        ttk.Button(
            command_box,
            text="현재시간 입력",
            command=self.fill_current_rtc_command,
        ).grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.serial_connect_button = ttk.Button(
            command_box,
            text="시리얼 연결",
            command=self.connect_serial,
        )
        self.serial_connect_button.grid(row=3, column=1, sticky="ew", padx=(10, 8), pady=(8, 0))
        self.serial_disconnect_button = ttk.Button(
            command_box,
            text="시리얼 연결 해제",
            command=self.disconnect_serial,
        )
        self.serial_disconnect_button.grid(row=3, column=2, sticky="ew", pady=(8, 0))

        actions = ttk.Frame(parent)
        actions.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        actions.columnconfigure(3, weight=1)

        self.upload_button = ttk.Button(
            actions,
            text="업로드",
            width=18,
            style="Upload.TButton",
            command=self.start_upload,
        )
        self.upload_button.grid(row=0, column=0, sticky="ew")
        self.erase_flash_button = ttk.Button(
            actions,
            text="Erase Flash",
            width=14,
            command=self.start_erase_flash,
        )
        self.erase_flash_button.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.update_button = ttk.Button(
            actions,
            text="업데이트 확인중",
            width=16,
            style="Update.TButton",
            command=self.confirm_update_download,
            state="disabled",
        )
        self.update_button.grid(row=0, column=2, sticky="ew", padx=(8, 0))
        ttk.Label(actions, textvariable=self.status_var).grid(row=0, column=3, sticky="e", padx=(12, 0))

        log_header = ttk.Frame(parent)
        log_header.grid(row=4, column=0, sticky="ew", pady=(12, 4))
        log_header.columnconfigure(0, weight=1)
        ttk.Label(log_header, text="로그").grid(row=0, column=0, sticky="w")
        ttk.Button(log_header, text="로그 복사", command=self.copy_log_to_clipboard).grid(
            row=0, column=1, sticky="e", padx=(6, 0)
        )
        ttk.Button(log_header, text="시리얼 로그 저장", command=self.save_serial_log_as_txt).grid(
            row=0, column=2, sticky="e", padx=(6, 0)
        )
        ttk.Button(log_header, text="전체 로그 저장", command=self.save_all_log_as_txt).grid(
            row=0, column=3, sticky="e", padx=(6, 0)
        )
        ttk.Button(log_header, text="로그 지우기", command=self.clear_log).grid(
            row=0, column=4, sticky="e", padx=(6, 0)
        )
        self.log_text = tk.Text(parent, height=16, wrap="word", state="disabled", font=("Consolas", 10))
        self.log_text.grid(row=5, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(parent, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=5, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.bind("<Control-c>", self.copy_selected_log_to_clipboard)
        self.log_text.bind("<Control-C>", self.copy_selected_log_to_clipboard)
        self.log_text.bind("<Button-3>", self.copy_log_to_clipboard)

        self.update_file_statuses()
        self.refresh_command_choices()
        self.update_serial_buttons()

    def _bind_auto_save(self) -> None:
        self.port_var.trace_add("write", self.schedule_save_settings)
        self.upload_baud_var.trace_add("write", self.schedule_save_settings)
        self.serial_baud_var.trace_add("write", self.schedule_save_settings)
        self.firmware_folder_var.trace_add("write", self.on_firmware_folder_changed)
        self.board_var.trace_add("write", self.on_board_changed)
        self.command_name_var.trace_add("write", self.on_command_changed)
        for file_var in self.file_vars:
            file_var["enabled"].trace_add("write", self.on_file_setting_changed)
            file_var["address"].trace_add("write", self.schedule_save_settings)
            file_var["path"].trace_add("write", self.on_file_setting_changed)

    def on_file_setting_changed(self, *_args: object) -> None:
        self.update_file_statuses()
        self.schedule_save_settings()

    def on_firmware_folder_changed(self, *_args: object) -> None:
        self.apply_firmware_folder(show_message=False)
        self.schedule_save_settings()

    def schedule_save_settings(self, *_args: object) -> None:
        if self.save_after_id is not None:
            self.root.after_cancel(self.save_after_id)
        self.save_after_id = self.root.after(300, self.save_settings)

    def save_settings(self) -> None:
        self.save_after_id = None
        data = {
            "port": self.port_var.get().strip(),
            "upload_baud": self.upload_baud_var.get().strip(),
            "serial_baud": self.serial_baud_var.get().strip(),
            "firmware_folder": self.firmware_folder_var.get().strip(),
            "selected_board": self.board_var.get().strip(),
            "selected_command": self.command_name_var.get().strip(),
            "files": [
                {
                    "name": file_var["name"].get(),
                    "enabled": bool(file_var["enabled"].get()),
                    "address": file_var["address"].get().strip(),
                    "path": file_var["path"].get().strip(),
                }
                for file_var in self.file_vars
            ],
        }

        try:
            SETTINGS_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            self.status_var.set("설정 저장 실패")
            self.append_log(f"설정 저장 실패: {exc}")

    def start_update_check(self) -> None:
        if self.update_worker and self.update_worker.is_alive():
            return
        self.update_button.configure(text="업데이트 확인중", state="disabled", style="Update.TButton")
        self.update_worker = threading.Thread(target=self._update_check_worker, daemon=True)
        self.update_worker.start()

    def _update_check_worker(self) -> None:
        try:
            remote_info = get_remote_git_info()
            local_sha = get_local_git_sha()
            is_empty = git_download_is_empty()
            if is_empty or remote_has_newer_commit(local_sha, remote_info["sha"]):
                self.events.put(("update_available", json.dumps(remote_info)))
                if is_empty:
                    self.events.put(("log", "git_download 폴더가 비어 있어 GitHub 다운로드가 필요합니다."))
                elif local_sha:
                    self.events.put(("log", f"새 GitHub 버전 발견: {local_sha[:8]} -> {remote_info['sha'][:8]}"))
                else:
                    self.events.put(("log", "git_download 폴더의 버전을 확인할 수 없어 GitHub 다운로드가 필요합니다."))
            else:
                self.events.put(("update_not_available", remote_info["sha"]))
        except Exception as exc:
            self.events.put(("update_error", str(exc)))

    def _start_update_blink(self) -> None:
        self._stop_update_blink()
        self.update_blink_on = False
        self._blink_update_button()

    def _blink_update_button(self) -> None:
        self.update_blink_on = not self.update_blink_on
        text = "새 버전 있음" if self.update_blink_on else "업데이트 받기"
        style = "UpdateBlink.TButton" if self.update_blink_on else "Update.TButton"
        self.update_button.configure(text=text, style=style, state="normal")
        self.update_blink_after_id = self.root.after(500, self._blink_update_button)

    def _stop_update_blink(self) -> None:
        if self.update_blink_after_id is not None:
            self.root.after_cancel(self.update_blink_after_id)
            self.update_blink_after_id = None
        self.update_blink_on = False

    def confirm_update_download(self) -> None:
        if self.update_worker and self.update_worker.is_alive():
            return
        if self.remote_git_info is None:
            self.start_update_check()
            return
        if not messagebox.askyesno(
            "새 버전 다운로드",
            "GitHub에 새 버전이 있습니다.\n새로 받으시겠습니까?",
        ):
            return

        self._stop_update_blink()
        self.update_button.configure(text="다운로드 중", state="disabled", style="Update.TButton")
        self.status_var.set("GitHub 다운로드 중")
        self.update_worker = threading.Thread(target=self._update_download_worker, daemon=True)
        self.update_worker.start()

    def _update_download_worker(self) -> None:
        try:
            remote_info = self.remote_git_info or get_remote_git_info()
            update_git_download(remote_info)
            self.events.put(("update_download_done", json.dumps(remote_info)))
        except Exception as exc:
            self.events.put(("update_download_error", str(exc)))

    def on_close(self) -> None:
        self.disconnect_serial(show_log=False)
        if self.save_after_id is not None:
            self.root.after_cancel(self.save_after_id)
            self.save_settings()
        if self.update_blink_after_id is not None:
            self.root.after_cancel(self.update_blink_after_id)
            self.update_blink_after_id = None
        self.root.destroy()

    def browse_firmware_folder(self) -> None:
        current_path = path_from_setting(self.firmware_folder_var.get().strip(), FIRMWARE_DIR)
        initial_dir = current_path if current_path.exists() else BASE_DIR
        selected = filedialog.askdirectory(
            title="펌웨어 폴더 선택",
            initialdir=str(initial_dir),
        )
        if selected:
            selected_path = Path(selected)
            selected_label = display_path(selected_path)
            if selected_label not in self.firmware_folders:
                self.firmware_folders.append(selected_label)
                self.firmware_folder_combo["values"] = self.firmware_folders
            self.firmware_folder_var.set(selected_label)

    def apply_firmware_folder(self, show_message: bool = True) -> None:
        folder_text = self.firmware_folder_var.get().strip()
        if not folder_text:
            return

        folder = path_from_setting(folder_text, FIRMWARE_DIR)
        found_files = find_flash_files_in_folder(folder)
        for file_var in self.file_vars:
            name = file_var["name"].get()
            found_path = found_files.get(name)
            if found_path is not None:
                file_var["path"].set(display_path(found_path))

        self.update_file_statuses()
        if show_message:
            found_names = ", ".join(found_files.keys()) if found_files else "없음"
            self.append_log(f"펌웨어 폴더 적용: {display_path(folder)} / 찾은 파일: {found_names}")
        self.schedule_save_settings()

    def reload_command_files(self) -> None:
        self.boards = load_boards()
        self.commands_by_board = load_commands()
        self.board_combo["values"] = self.boards
        self.refresh_command_choices()
        self.append_log("boards.txt / commands.txt 다시 불러옴")

    def on_board_changed(self, *_args: object) -> None:
        self.refresh_command_choices()
        self.schedule_save_settings()

    def on_command_changed(self, *_args: object) -> None:
        selected = self.command_name_var.get().strip()
        for command in self.current_commands:
            if command["label"] == selected:
                if self.command_text_var.get() != command["command"]:
                    self.command_text_var.set(command["command"])
                break
        self.schedule_save_settings()

    def fill_current_rtc_command(self) -> None:
        command = f"SETRTC {datetime.now():%Y-%m-%d %H:%M:%S}"
        self.command_text_var.set(command)
        self.command_name_var.set("RTC 현재시간")
        self.append_log(f"RTC 현재시간 명령 입력: {command}")
        self.schedule_save_settings()

    def refresh_command_choices(self) -> None:
        if not self.boards:
            self.board_combo["values"] = []
            self.command_combo["values"] = []
            self.current_commands = []
            return

        if not self.board_var.get().strip() or self.board_var.get().strip() not in self.boards:
            self.board_var.set(self.boards[0])
            return

        board = self.board_var.get().strip()
        self.current_commands = self.commands_by_board.get(board, [])
        command_names = [command["label"] for command in self.current_commands]
        self.command_combo["values"] = command_names

        if command_names and self.command_name_var.get().strip() not in command_names:
            self.command_name_var.set(command_names[0])
            return
        if not command_names:
            self.command_name_var.set("")
            self.command_text_var.set("")
            return

        self.on_command_changed()

    def browse_file(self, index: int) -> None:
        current_path = path_from_setting(self.file_vars[index]["path"].get().strip(), Path())
        initial_dir = current_path.parent if current_path.parent.exists() else FIRMWARE_DIR
        selected = filedialog.askopenfilename(
            title=f"{self.file_vars[index]['name'].get()} 파일 선택",
            initialdir=str(initial_dir),
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")],
        )
        if selected:
            self.file_vars[index]["path"].set(display_path(Path(selected)))

    def update_file_statuses(self) -> None:
        for file_var, label in zip(self.file_vars, self.status_labels):
            if not bool(file_var["enabled"].get()):
                label.configure(text="SKIP")
                continue
            path = path_from_setting(file_var["path"].get().strip(), Path())
            label.configure(text="OK" if path.exists() else "없음")

    def on_space_upload(self, _event: tk.Event) -> str:
        if self.worker and self.worker.is_alive():
            return "break"
        self.start_upload()
        return "break"

    def refresh_ports(self) -> None:
        if list_ports is None:
            self.port_combo["values"] = []
            self.status_var.set(f"pyserial 없음: 포트를 직접 입력하세요. 예: {get_port_hint()}")
            return

        preferred_ports = []
        all_ports = []
        for port in list_ports.comports():
            device = str(port.device or "")
            if not device:
                continue
            all_ports.append(device)
            if is_preferred_serial_port(port):
                preferred_ports.append(device)

        ports = preferred_ports or all_ports
        add_linux_uart_fallback_ports(ports)
        self.port_combo["values"] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])
        elif not ports and not self.port_var.get().strip():
            self.status_var.set(f"{get_platform_label()} 시리얼 포트 없음: 직접 입력하세요. 예: {get_port_hint()}")

    def get_serial_baud(self) -> int | None:
        baud_text = self.serial_baud_var.get().strip()
        try:
            return int(baud_text)
        except ValueError:
            messagebox.showerror("보레이트 오류", "명령 보레이트는 숫자로 입력하세요.")
            return None

    def update_serial_buttons(self) -> None:
        connected = self.serial_conn is not None and getattr(self.serial_conn, "is_open", False)
        if hasattr(self, "serial_connect_button"):
            self.serial_connect_button.configure(state="disabled" if connected else "normal")
        if hasattr(self, "serial_disconnect_button"):
            self.serial_disconnect_button.configure(state="normal" if connected else "disabled")

    def connect_serial(self, show_log: bool = True) -> bool:
        if serial is None:
            messagebox.showerror(
                "pyserial 없음",
                "시리얼 연결에는 pyserial이 필요합니다.\npython -m pip install pyserial",
            )
            return False

        if self.serial_conn is not None and getattr(self.serial_conn, "is_open", False):
            return True

        port = self.port_var.get().strip()
        baud = self.get_serial_baud()
        if not port:
            messagebox.showerror("포트 오류", "시리얼 연결할 포트를 선택하세요.")
            return False
        if baud is None:
            return False

        try:
            self.serial_stop.clear()
            self.serial_conn = serial.Serial(port=port, baudrate=baud, timeout=0.2, write_timeout=2)
            self.serial_reader = threading.Thread(target=self._serial_read_worker, daemon=True)
            self.serial_reader.start()
            self._status("시리얼 연결됨")
            if show_log:
                self.append_log(f"시리얼 연결됨: port={port}, baud={baud}")
            self.update_serial_buttons()
            return True
        except Exception as exc:
            self.serial_conn = None
            self.update_serial_buttons()
            messagebox.showerror("시리얼 연결 실패", str(exc))
            return False

    def disconnect_serial(self, show_log: bool = True) -> None:
        self.serial_stop.set()
        with self.serial_lock:
            conn = self.serial_conn
            self.serial_conn = None
            if conn is not None:
                try:
                    if getattr(conn, "is_open", False):
                        conn.close()
                except Exception:
                    pass
        if show_log:
            self.append_log("시리얼 연결 해제")
            self.status_var.set("시리얼 연결 해제")
        self.update_serial_buttons()

    def _serial_read_worker(self) -> None:
        while not self.serial_stop.is_set():
            conn = self.serial_conn
            if conn is None:
                break
            try:
                data = conn.readline()
            except Exception as exc:
                if not self.serial_stop.is_set():
                    self.events.put(("log", f"시리얼 읽기 오류: {exc}"))
                    self.events.put(("status", "시리얼 연결 끊김"))
                    self.events.put(("serial_closed", ""))
                break
            if not data:
                continue
            line = data.decode("utf-8", errors="replace").rstrip()
            if line:
                self.events.put(("log", f"[SERIAL] {line}"))

    def read_flash_files(self) -> list[tuple[str, Path]] | None:
        flash_files = []
        errors = []
        for file_var in self.file_vars:
            if not bool(file_var["enabled"].get()):
                continue

            name = file_var["name"].get()
            address = file_var["address"].get().strip()
            path = path_from_setting(file_var["path"].get().strip(), Path())

            if not ADDRESS_PATTERN.fullmatch(address):
                errors.append(f"{name}: 주소 형식 오류 ({address})")
            if not path.exists():
                errors.append(f"{name}: 파일 없음 ({path})")
            else:
                flash_files.append((address, path))

        if not flash_files:
            messagebox.showerror("플래시 파일 설정 오류", "업로드할 bin 파일을 하나 이상 체크하세요.")
            return None

        if errors:
            messagebox.showerror("펌웨어 설정 오류", "\n".join(errors))
            return None
        return flash_files

    def start_upload(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        port = self.port_var.get().strip()
        upload_baud_text = self.upload_baud_var.get().strip()
        if not port:
            messagebox.showerror("포트 오류", "업로드할 포트를 선택하세요.")
            return

        try:
            upload_baud = int(upload_baud_text)
        except ValueError:
            messagebox.showerror("보레이트 오류", "업로드 보레이트는 숫자로 입력하세요.")
            return

        flash_files = self.read_flash_files()
        if flash_files is None:
            return

        self.disconnect_serial(show_log=False)
        self.save_settings()
        self.upload_button.configure(state="disabled")
        self.erase_flash_button.configure(state="disabled")
        self.command_send_button.configure(state="disabled")
        self.serial_connect_button.configure(state="disabled")
        self.serial_disconnect_button.configure(state="disabled")
        self.status_var.set("업로드 중")
        self.clear_log()
        self.worker = threading.Thread(
            target=self._upload_worker,
            args=(port, upload_baud, flash_files),
            daemon=True,
        )
        self.worker.start()

    def start_erase_flash(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        port = self.port_var.get().strip()
        upload_baud_text = self.upload_baud_var.get().strip()
        if not port:
            messagebox.showerror("Port error", "Select a port before erasing flash.")
            return

        try:
            upload_baud = int(upload_baud_text)
        except ValueError:
            messagebox.showerror("Baud error", "Upload baud must be a number.")
            return

        if not messagebox.askyesno(
            "Erase Flash",
            f"This will erase the entire ESP32 flash on {port}.\nContinue?",
        ):
            return

        self.disconnect_serial(show_log=False)
        self.save_settings()
        self.upload_button.configure(state="disabled")
        self.erase_flash_button.configure(state="disabled")
        self.command_send_button.configure(state="disabled")
        self.serial_connect_button.configure(state="disabled")
        self.serial_disconnect_button.configure(state="disabled")
        self.status_var.set("Erasing flash...")
        self.clear_log()
        self.worker = threading.Thread(
            target=self._erase_flash_worker,
            args=(port, upload_baud),
            daemon=True,
        )
        self.worker.start()

    def start_send_command(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        if serial is None:
            messagebox.showerror(
                "pyserial 없음",
                "시리얼 명령어 전송에는 pyserial이 필요합니다.\npython -m pip install pyserial",
            )
            return

        port = self.port_var.get().strip()
        command = self.command_text_var.get().strip()
        if not port:
            messagebox.showerror("포트 오류", "명령어를 보낼 포트를 선택하세요.")
            return
        if not command:
            messagebox.showerror("명령어 오류", "전송할 명령어를 선택하거나 입력하세요.")
            return

        baud = self.get_serial_baud()
        if baud is None:
            return

        self.save_settings()
        self.upload_button.configure(state="disabled")
        self.erase_flash_button.configure(state="disabled")
        self.command_send_button.configure(state="disabled")
        self.serial_connect_button.configure(state="disabled")
        self.serial_disconnect_button.configure(state="disabled")
        self.status_var.set("명령어 전송 중")
        self.worker = threading.Thread(
            target=self._send_command_worker,
            args=(port, baud, command),
            daemon=True,
        )
        self.worker.start()

    def _send_command_worker(self, port: str, baud: int, command: str) -> None:
        try:
            self._log(f"시리얼 전송: port={port}, baud={baud}, command={command}")
            with self.serial_lock:
                conn = self.serial_conn
                if conn is not None and getattr(conn, "is_open", False):
                    conn.write((command + "\n").encode("utf-8"))
                    conn.flush()
                else:
                    with serial.Serial(port=port, baudrate=baud, timeout=1, write_timeout=2) as ser:
                        ser.write((command + "\n").encode("utf-8"))
                        ser.flush()
            self._status("명령어 전송 완료")
            self._log("명령어 전송 완료")
        except Exception as exc:
            self._status("명령어 전송 실패")
            self._log(f"명령어 전송 오류: {exc}")
        finally:
            self.events.put(("done", ""))

    def _erase_flash_worker(self, port: str, upload_baud: int) -> None:
        try:
            self._log("esptool erase-flash start")
            self._run_erase_flash(port, upload_baud)
            self._status("Erase flash success")
            self._log("Erase flash success")
        except Exception as exc:
            self._status("Erase flash failed")
            self._log(f"Erase flash error: {exc}")
        finally:
            self.events.put(("done", ""))

    def _upload_worker(self, port: str, upload_baud: int, flash_files: list[tuple[str, Path]]) -> None:
        try:
            self._log("esptool 업로드 시작")
            self._run_esptool(port, upload_baud, flash_files)
            self._status("업로드 성공")
            self._log("업로드 성공")
            self.events.put(("connect_serial_after_upload", ""))
        except Exception as exc:
            self._status("실패")
            self._log(f"오류: {exc}")
        finally:
            self.events.put(("done", ""))

    def _run_esptool(self, port: str, baud: int, flash_files: list[tuple[str, Path]]) -> None:
        esptool_args = [
            "--chip",
            "esp32",
            "--port",
            port,
            "--baud",
            str(baud),
            "--before",
            "default-reset",
            "--after",
            "hard-reset",
            "write-flash",
        ]
        for address, path in flash_files:
            esptool_args.extend([address, str(path)])

        commands = self._build_esptool_commands(esptool_args)
        last_output = ""
        for index, cmd in enumerate(commands, start=1):
            self._log("실행: " + " ".join(cmd))
            rc, output = self._run_command(cmd)
            last_output = output
            if rc == 0 and "No module named esptool" not in output:
                return
            if index < len(commands):
                self._log("esptool 실행 실패, 다른 실행 경로로 재시도합니다.")

        if "No module named esptool" in last_output:
            raise RuntimeError("esptool 모듈이 없습니다. 실행 중인 Python에 esptool을 설치하세요: python -m pip install esptool")
        raise RuntimeError("esptool 업로드 실패. esptool 설치 여부와 포트 상태를 확인하세요.")

    def _run_erase_flash(self, port: str, baud: int) -> None:
        self._force_download_mode(port)
        esptool_args = [
            "--chip",
            "esp32",
            "--port",
            port,
            "--baud",
            str(baud),
            "--before",
            "no-reset",
            "--after",
            "hard-reset",
            "erase-flash",
        ]

        commands = self._build_esptool_commands(esptool_args)
        last_output = ""
        for index, cmd in enumerate(commands, start=1):
            self._log("Run: " + " ".join(cmd))
            rc, output = self._run_command(cmd)
            last_output = output
            if rc == 0 and "No module named esptool" not in output:
                return
            if index < len(commands):
                self._log("esptool failed, retrying with another executable path.")

        if "No module named esptool" in last_output:
            raise RuntimeError("esptool module is missing. Install it with: python -m pip install esptool")
        raise RuntimeError("esptool erase-flash failed. Check port, boot mode, and USB connection.")

    def _force_download_mode(self, port: str) -> None:
        if serial is None:
            self._log("pyserial is missing, skipping DTR/RTS boot sequence.")
            return

        def open_port() -> serial.Serial:
            return serial.Serial(port=port, baudrate=115200, timeout=0.1, write_timeout=0.1)

        self._log(f"Forcing ESP32 download mode with repeated DTR/RTS cycles on {get_platform_label()}...")
        sequences = [
            ("classic DTR=BOOT RTS=EN", "dtr_boot"),
            ("hold BOOT before reset", "dtr_boot_prehold"),
            ("swapped RTS=BOOT DTR=EN", "rts_boot"),
            ("both asserted open/close pulse", "both_asserted"),
        ]

        for cycle in range(1, 4):
            for label, mode in sequences:
                try:
                    self._log(f"Boot cycle {cycle}: {label}")
                    with open_port() as ser:
                        ser.dtr = False
                        ser.rts = False
                        time.sleep(0.12)

                        if mode == "dtr_boot":
                            ser.rts = True
                            time.sleep(0.25)
                            ser.dtr = True
                            time.sleep(0.12)
                            ser.rts = False
                            time.sleep(0.9)
                            ser.dtr = False
                        elif mode == "dtr_boot_prehold":
                            ser.dtr = True
                            time.sleep(0.12)
                            ser.rts = True
                            time.sleep(0.25)
                            ser.rts = False
                            time.sleep(0.9)
                            ser.dtr = False
                        elif mode == "rts_boot":
                            ser.dtr = True
                            time.sleep(0.25)
                            ser.rts = True
                            time.sleep(0.12)
                            ser.dtr = False
                            time.sleep(0.9)
                            ser.rts = False
                        elif mode == "both_asserted":
                            ser.dtr = True
                            ser.rts = True
                            time.sleep(0.35)
                            ser.rts = False
                            time.sleep(0.35)
                            ser.dtr = False

                        time.sleep(0.12)
                    time.sleep(0.2)
                except Exception as exc:
                    self._log(f"Boot cycle failed ({label}): {exc}")

        self._log("DTR/RTS boot cycles done. Running erase without extra reset.")

    def _build_esptool_commands(self, esptool_args: list[str]) -> list[list[str]]:
        commands: list[list[str]] = []
        if getattr(sys, "frozen", False):
            commands.append([sys.executable, "--esptool-subprocess", *esptool_args])
        else:
            commands.append([sys.executable, "-m", "esptool", *esptool_args])

        esptool_exe = shutil.which("esptool")
        if esptool_exe:
            commands.append([esptool_exe, *esptool_args])

        python_exe = shutil.which("python")
        if python_exe and Path(python_exe).resolve() != Path(sys.executable).resolve():
            commands.append([python_exe, "-m", "esptool", *esptool_args])

        python3_exe = shutil.which("python3")
        if python3_exe and Path(python3_exe).resolve() != Path(sys.executable).resolve():
            commands.append([python3_exe, "-m", "esptool", *esptool_args])

        unique_commands = []
        seen = set()
        for cmd in commands:
            key = tuple(cmd)
            if key not in seen:
                unique_commands.append(cmd)
                seen.add(key)
        return unique_commands

    def _run_command(self, cmd: list[str]) -> tuple[int, str]:
        process = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        lines = []
        for line in process.stdout:
            line = line.rstrip()
            lines.append(line)
            self._log(line)

        rc = process.wait()
        return rc, "\n".join(lines)

    def _poll_events(self) -> None:
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self.append_log(value)
            elif kind == "status":
                self.status_var.set(value)
            elif kind == "done":
                self.upload_button.configure(state="normal")
                self.erase_flash_button.configure(state="normal")
                self.command_send_button.configure(state="normal")
                self.update_serial_buttons()
            elif kind == "update_available":
                try:
                    self.remote_git_info = json.loads(value)
                except Exception:
                    self.remote_git_info = None
                self.status_var.set("GitHub 새 버전 있음")
                self._start_update_blink()
            elif kind == "update_not_available":
                self.remote_git_info = None
                self._stop_update_blink()
                self.update_button.configure(text="최신 버전", state="disabled", style="Update.TButton")
            elif kind == "update_error":
                self.remote_git_info = None
                self._stop_update_blink()
                self.update_button.configure(text="업데이트 재확인", state="normal", style="Update.TButton")
                self.append_log(f"업데이트 확인 실패: {value}")
            elif kind == "update_download_done":
                try:
                    self.remote_git_info = json.loads(value)
                except Exception:
                    self.remote_git_info = None
                self._stop_update_blink()
                self.update_button.configure(text="다운로드 완료", state="disabled", style="Update.TButton")
                self.status_var.set("GitHub 다운로드 완료")
                self.append_log("git_download 폴더를 최신 GitHub 버전으로 갱신했습니다.")
                self.firmware_folders = list_firmware_folders()
                self.firmware_folder_combo["values"] = self.firmware_folders
            elif kind == "update_download_error":
                self._stop_update_blink()
                self.update_button.configure(text="다운로드 재시도", state="normal", style="Update.TButton")
                self.status_var.set("GitHub 다운로드 실패")
                self.append_log(f"GitHub 다운로드 실패: {value}")
                messagebox.showerror("GitHub 다운로드 실패", value)
            elif kind == "serial_closed":
                self.disconnect_serial(show_log=False)
            elif kind == "connect_serial_after_upload":
                self.root.after(1000, lambda: self.connect_serial(show_log=True))

        self.root.after(100, self._poll_events)

    def _log(self, message: str) -> None:
        self.events.put(("log", message))

    def _status(self, message: str) -> None:
        self.events.put(("status", message))

    def append_log(self, message: str) -> None:
        self.log_lines.append(message)
        if message.startswith("[SERIAL]"):
            self.serial_log_lines.append(message)
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def get_log_text(self, serial_only: bool = False) -> str:
        lines = self.serial_log_lines if serial_only else self.log_lines
        return "\n".join(lines).rstrip() + ("\n" if lines else "")

    def copy_log_to_clipboard(self, _event: tk.Event | None = None) -> str:
        text = self.get_log_text(serial_only=False)
        if not text:
            self.status_var.set("복사할 로그가 없습니다")
            return "break"

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("로그를 클립보드에 복사했습니다")
        return "break"

    def copy_selected_log_to_clipboard(self, _event: tk.Event | None = None) -> str:
        try:
            text = self.log_text.get("sel.first", "sel.last")
        except tk.TclError:
            return self.copy_log_to_clipboard()

        if not text:
            return self.copy_log_to_clipboard()

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("선택한 로그를 클립보드에 복사했습니다")
        return "break"

    def save_log_as_txt(self, serial_only: bool) -> None:
        text = self.get_log_text(serial_only=serial_only)
        if not text:
            messagebox.showinfo("로그 저장", "저장할 로그가 없습니다.")
            return

        suffix = "serial" if serial_only else "all"
        default_name = f"shinwhatech_uploader_{suffix}_log_{datetime.now():%Y%m%d_%H%M%S}.txt"
        selected = filedialog.asksaveasfilename(
            title="로그 TXT 저장",
            initialdir=str(BASE_DIR),
            initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not selected:
            return

        try:
            Path(selected).write_text(text, encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("로그 저장 실패", str(exc))
            return

        self.status_var.set(f"로그 저장 완료: {display_path(Path(selected))}")
        self.append_log(f"로그 저장 완료: {display_path(Path(selected))}")

    def save_serial_log_as_txt(self) -> None:
        self.save_log_as_txt(serial_only=True)

    def save_all_log_as_txt(self) -> None:
        self.save_log_as_txt(serial_only=False)

    def clear_log(self) -> None:
        self.log_lines.clear()
        self.serial_log_lines.clear()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    BrightmonUploaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--esptool-subprocess":
        sys.argv = ["esptool", *sys.argv[2:]]
        runpy.run_module("esptool", run_name="__main__", alter_sys=True)
    else:
        main()
