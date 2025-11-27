import asyncio
import os
import re
import sys
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

console = Console()


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
            "[dim]Icon path: ~/.local/share/icons/gameicons/*[/dim]",
            border_style="cyan",
        )
    )

    found_games = await get_valid_games()

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
        console.print("[red]Didn't selected game[/red]")
        return

    game_id = selected_game["id"]

    icon_path = await get_game_assets(game_id)

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
    table.add_row("Icon path:", icon_path)

    console.print(table)

    if await questionary.confirm("Do you want to create desktop entry?").ask_async():
        os.makedirs(os.path.expanduser("~/.local/share/applications"), exist_ok=True)
        safe_name = "".join(
            [c if c.isalnum() else "_" for c in selected_game["name"]]
        ).lower()
        desktop_path = os.path.expanduser(
            f"~/.local/share/applications/{safe_name}.desktop"
        )
        content = f"""[Desktop Entry]
Type=Application
Name={selected_game["name"]}
Exec={final_exec_cmd}
Path={cmd_path}
Icon={icon_path}
Terminal=false
Categories=Game
    """
        with open(desktop_path, "w") as f:
            f.write(content)

        console.print()
        console.print(
            Panel("[bold green]Successfully created desktop entry.[/bold green]")
        )
        if await questionary.confirm(
            "Do you want to create symlink shortcut on desktop? If ~/Desktop doesn't exist, it will be created."
        ).ask_async():
            desktop_dir = get_desktop_path()
            if desktop_dir is not None:
                try:
                    link_name = f"{selected_game['name']}.desktop"
                    link_on_desktop = Path(desktop_dir) / link_name
                    console.print(f"[dim]Path: {link_on_desktop}")

                    os.symlink(desktop_path, link_on_desktop)
                    console.print(
                        "[green bold]Successfully created desktop symlink.[/green bold]"
                    )
                except FileExistsError:
                    console.print("[yellow]Symlink already exists.[/yellow]")
                except OSError:
                    console.print("[red]OS Error.[/red]")
                except Exception:
                    console.print("[red]Error when creating symlink.[/red]")
            else:
                console.print("[yellow]Cannot find desktop folder.[/yellow]")
    else:
        console.print("[red]Canceled.[/red]")


class NameValidator(Validator):
    def validate(self, query):
        if len(query.text) == 0:
            raise ValidationError(
                message="Please provide correct input",
                cursor_position=len(query.text),
            )


async def get_valid_games():
    while True:
        game_query = await questionary.text(
            "Please insert game name:", validate=NameValidator
        ).ask_async()

        if game_query is None:
            raise KeyboardInterrupt

        if not game_query:
            continue

        found_games = []
        try:
            with console.status(
                "[bold green]Searching for game in steam database..[/bold green]"
            ):
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        "https://store.steampowered.com/api/storesearch/",
                        params={"term": game_query, "l": "english", "cc": "US"},
                    )

                    data = response.json()
                    items = data.get("items", [])

                    if not items:
                        console.print(
                            f"[yellow]Cannot find game: {game_query}. Please try again.[/yellow]"
                        )
                        continue

                    for item in items:
                        found_games.append(
                            {"name": item["name"], "id": str(item["id"])}
                        )

                    return found_games
        except Exception:
            console.print("Error.")


async def get_game_assets(steam_id):
    icon_path = ""
    cookies = {
        "wants_mature_content": "1",
        "birthtime": "189302401",
        "lastagecheckage": "1-January-1980",
    }
    try:
        async with httpx.AsyncClient(cookies=cookies) as client:
            with console.status("[dim]Checking...[/dim]"):
                resp = await client.get(f"https://steamcommunity.com/app/{steam_id}")
                match = re.search(
                    r'class="apphub_AppIcon".*?src="(.*?)"', resp.text, re.DOTALL
                )

            if match:
                with console.status("[dim]Downloading icon...[/dim]"):
                    url = match.group(1)
                    img_response = await client.get(url)

                    create_dir = "~/.local/share/icons/gameicons"
                    full_path = os.path.expanduser(create_dir)

                    os.makedirs(full_path, exist_ok=True)
                    icon_path = os.path.expanduser(
                        f"~/.local/share/icons/gameicons/{steam_id}.jpg"
                    )

                    with open(icon_path, "wb") as f:
                        f.write(img_response.content)

                console.print(
                    f"[dim]Icon has been downloaded correctly.[/dim] \n {icon_path}"
                )
                console.print()
                return icon_path
            else:
                console.print("[red]Couldn't find icon.[/red]")
                return
    except Exception as e:
        console.print(e)
        return


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
    except Exception:
        console.print("[red]Program encountered error.[/red]")
        sys.exit(1)
