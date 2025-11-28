import asyncio
import os
import re
import sys
from typing import Dict, List, Optional
import httpx
import questionary
from questionary import Validator, ValidationError
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from prompt_toolkit.completion import PathCompleter
import filepicker
from pathlib import Path
import subprocess
from PIL import Image
import io
import time

console = Console()

HOME_DIR = Path.home()
ICONS_DIR = HOME_DIR / ".local/share/icons/hicolor/32x32/apps"
APPLICATIONS_DIR = HOME_DIR / ".local/share/applications"

STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
STEAM_COMMUNITY_URL = "https://steamcommunity.com/app/"

COOKIES = {
    "wants_mature_content": "1",
    "birthtime": "189302401",
    "lastagecheckage": "1-January-1980",
}


async def main():
    console.print(
        Panel.fit(
            "[bold cyan]Game Desktop Entry Creator [/bold cyan]\n"
            "[dim]Create desktop entry for game from steam database[/dim]",
            border_style="cyan",
        )
    )
    console.print(
        Panel.fit(
            "[bold magenta]Defaults:[/bold magenta]\n"
            "[dim]Icon path: ~/.local/share/icons/hicolor/32x32/apps[/dim]",
            border_style="cyan",
        )
    )
    while True:
        game_query = await questionary.text(
            "Please insert game name:", validate=NameValidator
        ).ask_async()
        if game_query is None:
            raise KeyboardInterrupt
        if not game_query.strip():
            continue

        with console.status("[green]Searching for game in steam database...[/green]"):
            found_games = await get_valid_games(game_query)
            if not found_games:
                console.print(
                    f"[yellow]No games found for query: {game_query}. Try again[/yellow]"
                )
                continue

        choices = [
            questionary.Choice(
                title=[
                    ("class:text", g["name"]),
                    ("class:text", " "),
                    ("fg:yellow", f"(ID: {g['id']})"),
                ],
                value=g,
            )
            for g in found_games
        ]

        selected_game = await questionary.select(
            "Please select game from list:", choices=choices
        ).ask_async()

        if not selected_game:
            console.print("[red]No game selected.[/red]")
            return

        game_id = selected_game["id"]

        with console.status("[green]Downloading icon from steam database...[/green]"):
            icon_filename = await get_game_assets(game_id)
            if not icon_filename:
                console.print("[yellow]Couldn't fetch icon from steam.[/yellow]")
                raise KeyboardInterrupt
            console.print("[bold green]Successfully downloaded game icon.[/bold green]")
        time.sleep(0.5)

        with console.status("[bold green]Picking file...[/bold green]"):
            picker = filepicker.FilePickerRunner(start_path=os.path.expanduser("~"))
            exec_cmd = await picker.run_async()
            if exec_cmd is None:
                raise KeyboardInterrupt

        console.print("[bold green]File provided.[/bold green]")
        runner_cmd = await questionary.text(
            "Please provide runner commands (blank if no runner or sh script provided before):",
            default="",
        ).ask_async()

        cmd_path = await questionary.text(
            "Please provide directory path where exec is:",
            default=os.path.dirname(exec_cmd),
            completer=PathCompleter(),
            validate=NameValidator,
        ).ask_async()
        if cmd_path is None:
            raise KeyboardInterrupt
        if not cmd_path.strip():
            continue

        ## either run.sh provided or runner
        if runner_cmd:
            final_exec_cmd = f'{runner_cmd} "{exec_cmd}"'
        else:
            final_exec_cmd = f'bash "{exec_cmd}"'

        table = Table(title="Summary of desktop entry:")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Value", style="magenta")

        table.add_row("Name", selected_game["name"])
        table.add_row("Exec path:", final_exec_cmd)
        table.add_row("Directory path:", cmd_path)
        table.add_row("Icon path:", icon_filename)

        console.print(table)

        if await questionary.confirm(
            "Do you want to create desktop entry?"
        ).ask_async():
            try:
                with console.status(
                    "[bold green]Creating .desktop entry...[/bold green]"
                ):
                    desktop_entry = await create_desktop_entry(
                        selected_game["name"], final_exec_cmd, cmd_path, icon_filename
                    )
                    if desktop_entry is None:
                        console.print("[red]Cannot create desktop entry.[/red]")
                        return
                    console.print("[bold green]Successfully created .desktop entry.")
            except Exception:
                console.print("[red]Error occured when creating desktop entry.[/red]")
                return

            if await questionary.confirm(
                "Do you want to create symlink shortcut on desktop? If ~/Desktop doesn't exist, it will be created."
            ).ask_async():
                with console.status(
                    "[bold green]Creating ~/Desktop symlink...[/bold green]"
                ):
                    desktop_symlink = await create_desktop_symlink(
                        selected_game["name"], desktop_entry
                    )
                    console.print(
                        "[bold green]Successfully created ~/Desktop symlink.[/bold green]"
                    )
                    return
            else:
                console.print("[yellow]Skipped creating ~/Desktop symlink.[/yellow]")
                return

        else:
            console.print("[yellow]Desktop entry creation canceled.[/yellow]")
            return


class NameValidator(Validator):
    def validate(self, document):
        if len(document.text) == 0:
            raise ValidationError(
                message="Please provide correct input",
                cursor_position=len(document.text),
            )


async def create_desktop_entry(
    selected_game: str, final_exec_cmd: str, cmd_path: str, icon_filename: str
) -> Optional[str]:
    try:
        safe_name = "".join([c if c.isalnum() else "_" for c in selected_game]).lower()
        entry_path = APPLICATIONS_DIR / f"{safe_name}.desktop"
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"""[Desktop Entry]
    Type=Application
    Name={selected_game}
    Exec={final_exec_cmd}
    Path={cmd_path}
    Icon={icon_filename}
    Terminal=false
    Categories=Game
    """
        with open(entry_path, "w") as f:
            f.write(content)

        return str(entry_path)

    except Exception as e:
        console.print(f"{e}")


async def create_desktop_symlink(selected_game: str, entry_path: str) -> Optional[str]:
    desktop_dir = get_desktop_path()
    if desktop_dir is not None:
        try:
            link_name = f"{selected_game}.desktop"
            link_on_desktop = Path(desktop_dir) / link_name
            console.print(f"[dim]Path: {link_on_desktop}")

            link_on_desktop.unlink(missing_ok=True)

            link_on_desktop.symlink_to(entry_path)
            return str(link_on_desktop)
        except FileExistsError:
            console.print("[yellow]Symlink already exists.[/yellow]")
            return None
        except OSError:
            console.print("[red]OS Error.[/red]")
            return None
        except Exception:
            return None
    else:
        return None


async def get_valid_games(game_name: str) -> List[Dict[str, str]]:
    found_games = []
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                STEAM_SEARCH_URL,
                params={"term": game_name, "l": "english", "cc": "US"},
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])

            for item in items:
                found_games.append({"name": item["name"], "id": str(item["id"])})

    except httpx.HTTPStatusError:
        console.print("[red]HTTPStatusError, cannot access API.[/red]")
    except Exception:
        console.print("Error.")

    return found_games


async def get_game_assets(steam_id: int) -> Optional[str]:
    try:
        async with httpx.AsyncClient(cookies=COOKIES) as client:
            resp = await client.get(f"{STEAM_COMMUNITY_URL}{steam_id}")
            match = re.search(
                r'class="apphub_AppIcon".*?src="(.*?)"', resp.text, re.DOTALL
            )

            if match:
                icon_filename_path = f"game_icon_{steam_id}.png"
                icon_filename = f"game_icon_{steam_id}"

                url = match.group(1)
                img_response = await client.get(url)
                img_response.raise_for_status()

                image_content = img_response.content
                with Image.open(io.BytesIO(image_content)) as img:
                    ICONS_DIR.mkdir(parents=True, exist_ok=True)

                    full_icon_path = ICONS_DIR / icon_filename_path

                    img.save(full_icon_path, "png")

                    return icon_filename
    except Exception:
        console.print("[red]Error when downloading icon.[/red]")


def get_desktop_path():
    try:
        path = (
            subprocess.check_output(["xdg-user-dir", "DESKTOP"]).decode("utf-8").strip()
        )
        os.makedirs(path, exist_ok=True)
        return path
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print()
        sys.exit(0)
    except Exception as e:
        console.print(e)
        console.print("[red]Program encountered error.[/red]")
        sys.exit(1)
