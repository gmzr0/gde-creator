# 🎮 Game Desktop Entry Creator

> **Create beautiful desktop entries for games outside Steam.**

GDE-Creator is a modern CLI tool that automatically search steam database, fetch name and icons and generate compliant `.desktop` file in your Linux system.

![Demo](https://github.com/user-attachments/assets/a10b0617-5248-421f-afc6-bcb48835eb01)

## ✨ Features

* 🔍 **Quick search:** fast querying of the Steam Store API.
* 🖼️ **Auto-Icons:** automatically fetches proper icons from Steam.
* 🚀 **No more problems:** Create desktop entry fast. No more manual creating `.desktop` and editing them.
* ⚡ **Fast game startup via launcher:** Launch your games blazingly fast via your favourite launcher.

## 📦 Installation
### Option 1: Download binary
1. Download latest binary release from GitHub
2. Extract and run:
```console
tar -xvf gde-creator-linux-x64.tar.gz
./gde-creator
```

### Option 2: Arch Linux (AUR)
Coming soon

## 💻 Usage
```console
gde-creator
```
1. Search your game.
2. Select correct game from the list.
3. Provide launch command or execute file. (`/path/to/run.sh`, `/path/to/run.exe`)
4. If `.exe` provided then select your runner. (e.g. `umu-run`, `wine`, `gamescope [options] -- umu-run`)
5. Path to exe/sh directory.
6. Done!

## 🛠️ Built with
1. [Rich](https://github.com/Textualize/rich) - beautiful terminal UI.
2. [Questionary](https://github.com/tmbo/questionary) - for interactive menus.
3. [Httpx](https://www.python-httpx.org/) - for async API requests.
4. [PyInstaller](https://pyinstaller.org/) - building the standalone binary.
