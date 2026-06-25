"""
课件本地化工具链 - Nuitka 编译打包脚本
用法: python build_nuitka.py [--clean] （由 build.bat 调用）
  --clean    强制全量编译，忽略增量缓存
产物: build/ 目录下的独立 .exe 文件 + 资源文件
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
PROJECT = ROOT.parent
DEPS_FILE = ROOT / "deps.txt"

COMPILE_ENTRIES = [
    # (源文件, 类型: gui/cli/server)
    ("pipeline_gui.py",                "gui"),
    ("pipeline.py",                    "cli"),
    ("pre_process.py",                 "cli"),
    ("laya_asset.py",                  "cli"),
    ("laya_asset_sk.py",               "cli"),
    ("generated_finalConfig_xian.py",  "cli"),
    ("generated_homework_config.py",   "cli"),
    ("config_merger.py",               "cli"),
    ("merge_classname.py",             "cli"),
    ("res_extractor.py",               "cli"),
    ("extract_text.py",                "cli"),
    ("whisper_cli.py",                 "cli"),
    ("generated_finalConfig_translation.py", "cli"),
    ("extract_audio_mappings.py",      "cli"),
    ("process_translation.py",         "cli"),
    ("screenshot_tool.py",             "cli"),
    ("gen_scene_doc.py",               "cli"),
    ("post_process.py",                "cli"),
    ("audio_copy_tool.py",             "cli"),
    ("audio_copy_tool_gui.py",         "gui"),
    ("image_copy_tool.py",             "cli"),
    ("image_copy_tool_gui.py",         "gui"),
    ("video_copy_tool.py",             "cli"),
    ("video_copy_tool_gui.py",         "gui"),
    ("translate_images_gui.py",        "gui"),
    ("translate_content.py",           "gui"),
    ("server_web.py",                  "server"),
]

COPY_DIRS = [
    "models",
    "文档模版",
    "server/static",
]

COPY_FILES = [
    "requirements.txt",
    "requirements-gpu.txt",
]

# 编译时跳过增量检测，强制全量
FORCE_REBUILD = False


def banner(text):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def ensure_nuitka():
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True, text=True
        )
        print(f"  {result.stdout.splitlines()[0].strip()}")
    except Exception:
        print("  [ERROR] Nuitka 未安装，请先运行: pip install nuitka")
        sys.exit(1)


def get_all_project_py_files():
    """收集项目所有 .py 文件路径及最新 mtime"""
    py_files = []
    max_mtime = 0
    for p in PROJECT.rglob("*.py"):
        try:
            m = p.stat().st_mtime
            py_files.append(p)
            if m > max_mtime:
                max_mtime = m
        except OSError:
            pass
    return py_files, max_mtime


def get_deps_snapshot():
    """获取 pip freeze 快照"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True, text=True, timeout=30
        )
        return sorted(line.strip() for line in result.stdout.splitlines()
                      if line.strip() and not line.startswith("-e "))
    except Exception:
        return []


def check_deps_changed():
    """对比 deps.txt 与当前 pip freeze，返回是否有变化"""
    if not DEPS_FILE.exists():
        return True
    old = sorted(DEPS_FILE.read_text(encoding="utf-8").splitlines())
    new = get_deps_snapshot()
    return old != new


def save_deps_snapshot():
    deps = get_deps_snapshot()
    if deps:
        DEPS_FILE.write_text("\n".join(deps) + "\n", encoding="utf-8")


def sync_server_web():
    """将 server/server.py 同步到根目录 server_web.py"""
    src = PROJECT / "server" / "server.py"
    dst = PROJECT / "server_web.py"
    if not src.exists():
        return
    if dst.exists() and src.stat().st_mtime <= dst.stat().st_mtime:
        return
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"  同步: server/server.py -> server_web.py")


def should_skip(src: Path, out: Path) -> bool:
    """增量判断：exe 是否无需重新编译"""
    if FORCE_REBUILD:
        return False
    if not out.exists():
        return False
    # exe 的 mtime 必须 >= 入口源码的 mtime
    if src.stat().st_mtime > out.stat().st_mtime:
        return False
    # 项目中任意 .py 文件更新 → 全量重编
    _, max_py_mtime = get_all_project_py_files()
    if max_py_mtime > out.stat().st_mtime:
        return False
    # pip 依赖有变化 → 全量重编
    if check_deps_changed():
        return False
    return True


def clean_build_dir(full: bool = True):
    PROTECTED = {"build.py", "build_nuitka.py", "build.bat", "encrypt.bat", "deps.txt"}
    for item in list(ROOT.iterdir()):
        if item.name in PROTECTED:
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        elif item.is_file():
            item.unlink()
    if full:
        DEPS_FILE.unlink(missing_ok=True)


def compile_all():
    """增量编译（除非 FORCE_REBUILD）"""
    sync_server_web()
    _, max_py_mtime = get_all_project_py_files()
    deps_changed = check_deps_changed()

    if FORCE_REBUILD:
        print("  模式: 全量编译 (--clean)")
    elif deps_changed:
        print("  模式: 全量编译 (pip 依赖有变化)")
    elif max_py_mtime > 0:
        print(f"  模式: 增量编译 (仅编译有变化的文件)")

    total = len(COMPILE_ENTRIES)
    failed = []
    skipped = 0
    compiled = 0

    for i, (script, script_type) in enumerate(COMPILE_ENTRIES, 1):
        src = PROJECT / script
        if not src.exists():
            print(f"  [{i}/{total}] SKIP (not found): {script}")
            skipped += 1
            continue

        name = Path(script).stem
        # server_web.py 编译为 server.exe
        if script == "server_web.py":
            name = "server"
        out = ROOT / f"{name}.exe"

        if should_skip(src, out):
            print(f"  [{i}/{total}] SKIP (up-to-date): {script}")
            skipped += 1
            continue

        compiled += 1
        print(f"  [{i}/{total}] {script} -> {name}.exe", flush=True)

        cmd = [sys.executable, "-m", "nuitka"]
        cmd += ["--assume-yes-for-downloads"]
        cmd += ["--onefile"]
        cmd += ["--output-dir=" + str(ROOT)]
        cmd += ["--jobs=4"]

        # Windows GUI 不显示控制台
        if script_type == "gui":
            cmd += ["--windows-console-mode=disable"]
            cmd += ["--enable-plugin=tk-inter"]

        # 显式包含有原生 DLL 的包，防止 Nuitka 遗漏
        if script in ("whisper_cli.py", "extract_text.py"):
            cmd += [
                "--include-package=ctranslate2",
                "--include-package=onnxruntime",
                "--include-package=cv2",
            ]
        if script == "screenshot_tool.py":
            cmd += ["--include-package=playwright"]

        cmd += [str(src)]

        result = subprocess.run(
            cmd, cwd=str(PROJECT),
            capture_output=False,
        )
        if result.returncode != 0:
            print(f"  [FAIL] {script}")
            failed.append(script)
        elif script == "server_web.py" and not out.exists():
            # Nuitka 输出 server_web.exe，重命名为 server.exe
            web_out = ROOT / "server_web.exe"
            if web_out.exists():
                web_out.rename(out)
                print(f"  [OK] 重命名: server_web.exe -> server.exe")

    print(f"\n  统计: 编译 {compiled}, 跳过 {skipped}, 失败 {len(failed)}")
    return failed


def copy_resources():
    for dir_name in COPY_DIRS:
        src = PROJECT / dir_name
        dst = ROOT / Path(dir_name).name  # server/static -> static
        if not src.exists() or not src.is_dir():
            print(f"  [SKIP] {dir_name} 不存在")
            continue
        if dst.exists():
            shutil.rmtree(dst)
        file_count = sum(1 for _ in src.rglob('*'))
        print(f"  复制 {dir_name} -> {dst.name}/  ({file_count} 个文件)")
        shutil.copytree(src, dst)

    for name in COPY_FILES:
        src = PROJECT / name
        if src.exists():
            shutil.copy2(src, ROOT / name)
            print(f"  复制 {name}")


def create_launcher():
    lines = [
        "@echo off",
        'set "ROOT=%~dp0"',
        'set "HF_HOME=%ROOT%models\\huggingface"',
        'set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%models\\playwright"',
        'set "PYTHONUTF8=1"',
        'set "PYTHONIOENCODING=utf-8"',
        'set "PYTHONUNBUFFERED=1"',
        "",
        'if not exist "%ROOT%pipeline_gui.exe" (',
        "    echo [ERROR] pipeline_gui.exe not found, please re-run build.bat",
        "    pause",
        "    exit /b 1",
        ")",
        "",
        'start "Pipeline GUI" "" "%ROOT%pipeline_gui.exe"',
    ]
    with open(ROOT / "启动.bat", "w", encoding="utf-8", newline="\r\n") as f:
        f.write("chcp 65001 >nul\n")
        f.write("\n".join(lines))
    print("  创建 启动.bat")


def create_server_launcher():
    lines = [
        "@echo off",
        'set "ROOT=%~dp0"',
        'set "HF_HOME=%ROOT%models\\huggingface"',
        'set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%models\\playwright"',
        'set "PYTHONUTF8=1"',
        'set "PYTHONIOENCODING=utf-8"',
        'set "PYTHONUNBUFFERED=1"',
        "",
        'if not exist "%ROOT%server.exe" (',
        "    echo [ERROR] server.exe not found, please re-run build.bat",
        "    pause",
        "    exit /b 1",
        ")",
        "",
        'echo 服务启动: http://localhost:8765',
        'echo 浏览器打开上面的地址即可使用',
        'echo.',
        '"%ROOT%server.exe"',
    ]
    with open(ROOT / "启动服务.bat", "w", encoding="utf-8", newline="\r\n") as f:
        f.write("chcp 65001 >nul\n")
        f.write("\n".join(lines))
    print("  创建 启动服务.bat")


def main():
    global FORCE_REBUILD
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true",
                        help="强制全量编译，忽略增量缓存")
    args, _ = parser.parse_known_args()
    FORCE_REBUILD = args.clean

    banner("Nuitka 编译打包")
    print(f"  项目目录: {PROJECT}")
    print(f"  输出目录: {ROOT}")

    ensure_nuitka()

    print("\n[1/3] 清理旧产物...")
    clean_build_dir(full=FORCE_REBUILD)

    # 增量模式下，依赖有变化则提示
    if not FORCE_REBUILD and check_deps_changed():
        print("  检测到 pip 依赖有变化，将全量重编")

    print(f"\n[2/3] 编译 {len(COMPILE_ENTRIES)} 个文件（可能需要较长时间）...")
    failed = compile_all()

    # 编译完成后保存 deps 快照
    save_deps_snapshot()
    if FORCE_REBUILD:
        print("  已更新 deps.txt (pip 依赖快照)")

    if failed:
        print(f"\n  [WARN] {len(failed)} 个文件编译失败: {failed}")
        print("  继续执行后续步骤...")

    print("\n[3/3] 复制资源...")
    copy_resources()
    create_launcher()
    create_server_launcher()

    if failed:
        banner("打包完成（有失败项）")
        print(f"\n  失败: {failed}")
        sys.exit(1)
    else:
        banner("打包完成")
        print(f"\n  产物目录: {ROOT}")
        print(f"\n  分发方式:")
        print(f"    1. 把整个 build/ 文件夹拷贝到目标电脑")
        print(f"    2. 双击 build/启动.bat 运行 GUI")
        print(f"    3. 双击 build/启动服务.bat 运行 Web 服务")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[中断]")
        sys.exit(1)
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
