from textual.app import App, ComposeResult
from textual.widgets import Input, Button, Label, DirectoryTree
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
import os


class FilePickerRunner(App):
    def __init__(self, start_path):
        super().__init__()
        self.start_path = start_path

    def on_mount(self):
        self.push_screen(FilePickerScreen(self.start_path), callback=self.exit)


class FilePickerScreen(Screen):
    CSS_PATH = "style.tcss"

    def __init__(self, start_path="./"):
        super().__init__()
        self.start_path = start_path if start_path else os.path.expanduser("~")

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            string = """
        File Picker - [yellow]Pick .exe or .sh file (or executable binary if game is linux native) [/yellow]\n
        [red bold]If you chose .exe, in next step you will have option to provide runner commands[/red bold]\n
        [dim]Use TAB to switch between panels[/dim]
            """
            yield Label(string)
            yield Input(value=self.start_path, id="path_input")
            yield DirectoryTree(self.start_path, id="tree")
            with Horizontal(id="buttons"):
                yield Button("Cancel", variant="error", id="cancel")
                yield Button("Confirm file", variant="success", id="select")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
        file_path = str(event.path)
        self.query_one("#path_input", Input).value = file_path

        self.validate_and_submit(file_path)

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ):
        dir_path = str(event.path)
        self.query_one("#path_input", Input).value = dir_path

    def on_input_submitted(self, event: Input.Submitted):
        self.validate_and_submit(event.value)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "select":
            current_value = self.query_one("#path_input", Input).value
            self.validate_and_submit(current_value)

    def validate_and_submit(self, path):
        if os.path.isfile(path):
            self.dismiss(path)
        elif os.path.isdir(path):
            try:
                tree = self.query_one("#tree", DirectoryTree)
                tree.path = path
                tree.focus()
            except Exception:
                self.app.notify("Error when changing directory", severity="error")
        else:
            self.app.notify("This is not a file.", severity="error")
