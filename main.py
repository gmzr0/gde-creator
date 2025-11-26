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



console = Console()

async def main():
    console.print(Panel.fit(
        "[bold cyan]Game Desktop Entry Creator [/bold cyan]\n"
        "[dim]Create desktop entry for game from steam database[/dim]",
        border_style="cyan"
    ))

    game_query = await questionary.text("Please input game name:").ask_async()
    if not game_query:
        console.print("[red]No game inputed.[/red]")
        return

    found_games = []

    with console.status(f"[bold green]Searching for game in steam database..[/bold green]"):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://store.steampowered.com/api/storesearch/",
                params={"term": game_query, "l": "english", "cc": "US"}
            )
            data = response.json()
            items = data.get("items", [])

            for item in items:
                found_games.append({
                    "name": item['name'],
                    "id": str(item["id"])
                })

    if not found_games:
        console.print("[yellow]Didn't found this game.[/yellow]")
        return

    choices = [
        questionary.Choice(
            title=f"{g["name"]} (ID: {g["id"]})",
            value=g
        ) for g in found_games
    ]

    selected_game = await questionary.select(
        "Please select game from list:",
        choices=choices
    ).ask_async()
    

    if not selected_game:
        console.print("[red]Didn't selected game[/red]")
        return

    icon_path = ""

    cookies = {
        "wants_mature_content": "1",
        "birthtime": "189302401",
        "lastagecheckage": "1-January-1980"
    }

    game_id = selected_game['id']


    try:
        async with httpx.AsyncClient(cookies=cookies) as client:
            with console.status("[dim]Checking...[/dim]"):

                resp = await client.get(f"https://steamcommunity.com/app/{game_id}")
                match = re.search(r'class="apphub_AppIcon".*?src="(.*?)"', resp.text, re.DOTALL)
            
            if match:
                with console.status("[dim]Downloading icon...[/dim]"):

                    url = match.group(1)
                    img_response = await client.get(url)
                    
                    create_dir = "~/.local/share/icons/gameicons" 
                    full_path = os.path.expanduser(create_dir)

                    os.makedirs(full_path, exist_ok=True)
                    icon_path = os.path.expanduser(f"~/.local/share/icons/gameicons/{game_id}.jpg")

                    with open(icon_path, "wb") as f:
                        f.write(img_response.content)

                console.print(f"[dim]Icon has been downloaded correctly.[/dim] \n {icon_path}")
                console.print()    
            else:
                console.print(f"[red]Couldn't find icon.[/red]")
                return
    except Exception as e:
        console.print(e)
        return
    
    default_exec = ""
    console.print(f"[yellow]Please provide path to .exe file or sh script. \nIn next input you will include runner commands.[/yellow]")
    exec_cmd = await questionary.text(
        "Please provide exec path:",
        default=default_exec,
        completer=PathCompleter(),
    ).ask_async()
    if not exec_cmd:
        console.print("[yellow]Provide exec path.")
        return
    
    runner_cmd = await questionary.text(
        "Please provide runner commands (blank if no runner or sh script provided before):",
        default=""
    ).ask_async()

    if runner_cmd:
        final_exec_cmd = f'{runner_cmd} "{exec_cmd}"'
    else:
        final_exec_cmd = f'bash "{exec_cmd}"'

    cmd_path = await questionary.text(
        "Please provide directory path where exec is:",
        default=os.path.dirname(exec_cmd),
        completer=PathCompleter(),
    ).ask_async()
    if not cmd_path:
        console.print("[red]Please provide directory path.[/red]")
        return

    table = Table(title="Summary of desktop entry:")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    table.add_row("Name", selected_game["name"])
    table.add_row("Exec path:", final_exec_cmd)
    table.add_row("Icon path:", icon_path)

    console.print(table)
    
    if await questionary.confirm("Do you want to create desktop entry?").ask_async():
        safe_name = "".join([c if c.isalnum() else "_" for c in selected_game['name']]).lower()
        desktop_path = os.path.expanduser(f"~/.local/share/applications/{safe_name}.desktop")
        content = f"""[Desktop Entry]
Type=Application
Name={selected_game['name']}
Exec={final_exec_cmd}
Path={cmd_path}
Icon={icon_path}
Terminal=false
Categories=Game;
"""
        with open(desktop_path, "w") as f:
            f.write(content)

        console.print()
        console.print(Panel(f"[bold green]Successfully created desktop entry.[/bold green]"))
    else:
        console.print("[red]Canceled.[/red]")


if __name__ == "__main__":
    asyncio.run(main())


