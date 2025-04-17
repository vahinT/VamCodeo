import tkinter as tk
from tkinter import filedialog, messagebox
import os
import subprocess
import tempfile
import re
import platform
import sys
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageTk


# --- System Theme Detection ---


def detect_system_theme():
    try:
        if platform.system() == "Windows":
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if value == 1 else "dark"

        elif platform.system() == "Darwin":  # macOS
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            return "dark" if "Dark" in result.stdout else "light"

    except Exception as e:
        print("System theme detection failed:", e)

    return "dark"  # Fallback default


class VamCodeo:
    def __init__(self, root):
        self.root = root
        self.root.title("VamCodeo")
        self.root.minsize(600, 400)

        self._base_title = "VamCodeo"
        self.current_file = None
       # Create a red 256x256 image
        img = Image.new('RGB', (256, 256),color='red')
        draw = ImageDraw.Draw(img)

# Load font
        # Create red 256x256 icon image
        img_size = 1024
        img = Image.new('RGB', (img_size, img_size), color='red')
        draw = ImageDraw.Draw(img)

        # Try to use a large, nice-looking font
        try:
            font = ImageFont.truetype("arial.ttf", 700)
        except IOError:
            font = ImageFont.load_default()

        text = "</>"

        # Get bounding box to center the text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (img_size - text_width) // 2 - bbox[0]
        y = (img_size - text_height) // 2 - bbox[1]

        # Draw white centered text
        draw.text((x, y), text, fill='white', font=font)

        # Convert to Tkinter-compatible image
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        icon_img = ImageTk.PhotoImage(Image.open(buffer))

        # Set app icon
        self.root.iconphoto(True, icon_img)
        self.icon_img_ref = icon_img  # Prevent garbage collection


        # Theme setup
        self.theme = detect_system_theme()
        self.themes = {
            "dark": {
                "bg": "black", "fg": "white", "insert": "white",
                "line_bg": "grey25", "output_bg": "grey15", "output_fg": "lightgrey",
                "keyword": "#FF7F50", "comment": "grey", "string": "#98FB98",
                "number": "#F0E68C", "operator": "#DCDCAA", "builtin": "#6495ED"
            },
            "light": {
                "bg": "white", "fg": "black", "insert": "black",
                "line_bg": "lightgrey", "output_bg": "#f0f0f0", "output_fg": "black",
                "keyword": "blue", "comment": "green", "string": "brown",
                "number": "purple", "operator": "darkorange", "builtin": "navy"
            }
        }

        self.keywords = [
            "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "False", "finally", "for", "from", "global", "if", "import",
            "in", "is", "lambda", "None", "nonlocal", "not", "or", "pass", "raise", "return",
            "True", "try", "while", "with", "yield"
        ]
        self.builtins = [
            "print", "len", "str", "int", "float", "bool", "list", "tuple", "dict", "set",
            "range", "open", "input", "exit"
        ]

        # --- Layout ---
        self.main_paned_window = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL)
        self.main_paned_window.pack(fill=tk.BOTH, expand=True)

        self.editor_frame = tk.Frame(self.main_paned_window)
        self.main_paned_window.add(self.editor_frame)

        self.line_number_bar = tk.Text(self.editor_frame, width=4, padx=3, pady=3,
                                       state=tk.DISABLED)
        self.line_number_bar.pack(side=tk.LEFT, fill=tk.Y)

        self.text_area = tk.Text(self.editor_frame, undo=True, wrap=tk.WORD,
                                 yscrollcommand=self._sync_scrollbar)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.output_area = tk.Text(self.root, height=10, state=tk.DISABLED)
        self.output_area.pack(fill=tk.BOTH)

        self.text_area.bind("<<Modified>>", self._on_text_modified)
        self.text_area.bind("<KeyRelease>", self._highlight_syntax)

        # Apply initial theme
        self.apply_theme()

        # --- Menus ---
        self.menu_bar = tk.Menu(self.root)
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.run_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.debug_menu = tk.Menu(self.menu_bar, tearoff=0)

        self.file_menu.add_command(label="New", command=self.new_file)
        self.file_menu.add_command(label="Open", command=self.open_file)
        self.file_menu.add_command(label="Save", command=self.save_file)
        self.file_menu.add_command(
            label="Save As...", command=self.save_as_file)
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label="Toggle Theme", command=self.toggle_theme)
        self.file_menu.add_command(label="Exit", command=self._safe_close)

        self.run_menu.add_command(label="Run", command=self._run_code)
        self.debug_menu.add_command(
            label="Run with Print Debugging", command=self._debug_with_print)

        self.menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.menu_bar.add_cascade(label="Run", menu=self.run_menu)
        self.menu_bar.add_cascade(label="Debug", menu=self.debug_menu)

        self.root.config(menu=self.menu_bar)

        # Shortcuts
        self.root.bind("<Control-n>", self.new_file)
        self.root.bind("<Control-o>", self.open_file)
        self.root.bind("<Control-s>", self.save_file)
        self.root.bind("<Control-S>", self.save_as_file)
        self.root.bind("<F5>", self._run_code)
        self.root.protocol("WM_DELETE_WINDOW", self._safe_close)

        # Final setup
        self.text_area.edit_modified(False)
        self._update_title()
        self._update_line_numbers()

    # --- THEME ---
    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()

    def apply_theme(self):
        t = self.themes[self.theme]
        self.root.config(bg=t["bg"])
        self.editor_frame.config(bg=t["bg"])
        self.text_area.config(bg=t["bg"], fg=t["fg"],
                              insertbackground=t["insert"])
        self.line_number_bar.config(bg=t["line_bg"], fg=t["fg"])
        self.output_area.config(bg=t["output_bg"], fg=t["output_fg"])

        self.text_area.tag_configure("keyword", foreground=t["keyword"])
        self.text_area.tag_configure("comment", foreground=t["comment"])
        self.text_area.tag_configure("string", foreground=t["string"])
        self.text_area.tag_configure("number", foreground=t["number"])
        self.text_area.tag_configure("operator", foreground=t["operator"])
        self.text_area.tag_configure("builtin", foreground=t["builtin"])
        self._highlight_syntax()

    # --- CORE LOGIC ---
    def _update_title(self):
        title = self._base_title
        if self.current_file:
            title += f" - {os.path.basename(self.current_file)}"
        else:
            title += " - Untitled"
        if self.text_area.edit_modified():
            title += " *"
        self.root.title(title)

    def _on_text_modified(self, event=None):
        self._update_title()
        self._update_line_numbers()

    def _ask_save_if_dirty(self):
        if not self.text_area.edit_modified():
            return True
        response = messagebox.askyesnocancel(
            "Save Changes?", "Save changes before proceeding?")
        if response is True:
            return self.save_file()
        return response is not None

    def _safe_close(self):
        if self._ask_save_if_dirty():
            self.root.destroy()

    def _display_output(self, output, error=""):
        self.output_area.config(state=tk.NORMAL)
        self.output_area.delete("1.0", tk.END)
        self.output_area.insert(tk.END, "--- Output ---\n" + output)
        if error:
            self.output_area.insert(tk.END, "\n--- Errors ---\n" + error)
        self.output_area.config(state=tk.DISABLED)
        self.output_area.see(tk.END)

    def _execute_code(self, code):
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
                tmp.write(code)
                path = tmp.name
            process = subprocess.Popen(["python", path],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       text=True)
            output, error = process.communicate(timeout=10)
            self._display_output(output, error)
        except Exception as e:
            self._display_output("", str(e))
        finally:
            if os.path.exists(path):
                os.remove(path)

    def _highlight_syntax(self, event=None):
        self.text_area.tag_remove("keyword", "1.0", tk.END)
        self.text_area.tag_remove("comment", "1.0", tk.END)
        self.text_area.tag_remove("string", "1.0", tk.END)
        self.text_area.tag_remove("number", "1.0", tk.END)
        self.text_area.tag_remove("operator", "1.0", tk.END)
        self.text_area.tag_remove("builtin", "1.0", tk.END)

        code = self.text_area.get("1.0", tk.END)
        lines = code.splitlines()

        for i, line in enumerate(lines):
            line_num = i + 1

            # Keywords
            for keyword in self.keywords:
                for match in re.finditer(rf'\b{re.escape(keyword)}\b', line):
                    self.text_area.tag_add("keyword",
                                           f"{line_num}.{match.start()}",
                                           f"{line_num}.{match.end()}")

            # Comments
            match = re.search(r'#.*', line)
            if match:
                self.text_area.tag_add("comment",
                                       f"{line_num}.{match.start()}",
                                       f"{line_num}.{match.end()}")

            # Strings
            for match in re.finditer(r'(".*?"|\'.*?\')', line):
                self.text_area.tag_add("string",
                                       f"{line_num}.{match.start()}",
                                       f"{line_num}.{match.end()}")

            # Numbers
            for match in re.finditer(r'\b\d+(\.\d+)?\b', line):
                self.text_area.tag_add("number",
                                       f"{line_num}.{match.start()}",
                                       f"{line_num}.{match.end()}")

            # Operators
            for match in re.finditer(r'[+\-*/%=<>!&|^]', line):
                self.text_area.tag_add("operator",
                                       f"{line_num}.{match.start()}",
                                       f"{line_num}.{match.end()}")

            # Built-ins
            for builtin in self.builtins:
                for match in re.finditer(rf'\b{re.escape(builtin)}\b', line):
                    self.text_area.tag_add("builtin",
                                           f"{line_num}.{match.start()}",
                                           f"{line_num}.{match.end()}")

    def _update_line_numbers(self, event=None):
        line_count = int(self.text_area.index('end-1c').split('.')[0])
        numbers = "\n".join(str(i + 1) for i in range(line_count))
        self.line_number_bar.config(state=tk.NORMAL)
        self.line_number_bar.delete("1.0", tk.END)
        self.line_number_bar.insert("1.0", numbers)
        self.line_number_bar.config(state=tk.DISABLED)

    def _sync_scrollbar(self, *args):
        self.text_area.yview_moveto(args[0])
        self.line_number_bar.yview_moveto(args[0])

    def new_file(self, event=None):
        if not self._ask_save_if_dirty():
            return
        self.text_area.delete("1.0", tk.END)
        self.current_file = None
        self._update_title()
        self.text_area.edit_modified(False)

    def open_file(self, event=None):
        if not self._ask_save_if_dirty():
            return
        file_path = filedialog.askopenfilename(filetypes=[(
            "Python Files", "*.py"), ("Text Files", "*.txt"), ("All Files", "*.*")])
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert("1.0", content)
            self.current_file = file_path
            self._update_title()
            self.text_area.edit_modified(False)

    def save_file(self, event=None):
        if self.current_file:
            try:
                with open(self.current_file, "w", encoding="utf-8") as f:
                    f.write(self.text_area.get("1.0", tk.END))
                self.text_area.edit_modified(False)
                self._update_title()
                return True
            except Exception as e:
                messagebox.showerror("Save Error", str(e))
        else:
            return self.save_as_file()
        return False

    def save_as_file(self, event=None):
        file_path = filedialog.asksaveasfilename(defaultextension=".py", filetypes=[
                                                 ("Python Files", "*.py"), ("All Files", "*.*")])
        if file_path:
            self.current_file = file_path
            return self.save_file()
        return False

    def _run_code(self, event=None):
        code = self.text_area.get("1.0", tk.END)
        self._execute_code(code)

    def _debug_with_print(self):
        code = self.text_area.get("1.0", tk.END)
        # Basic debug insert logic: adds print after each line with a def or for/if
        debugged = []
        lines = code.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            debugged.append(line)
            if any(stripped.startswith(x) for x in ("def ", "for ", "if ", "while ", "elif ", "else:")):
                indent = len(line) - len(stripped)
                debugged.append(" " * (indent + 4) +
                                f'print("Debug: Line {i + 1}")')
        self._execute_code("\n".join(debugged))
      
       # Create a red 256x256 image
        img = Image.new('RGB', (256, 256),color='red')
        draw = ImageDraw.Draw(img)

# Load font
        try:
            font = ImageFont.truetype("arial.ttf", 48)
        except IOError:
            font = ImageFont.load_default()

# Draw centered white text
        text = "Vam</>"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (256 - text_width) // 2
        y = (256 - text_height) // 2
        draw.text((x, y), text, fill='white', font=font)

# Convert to base64 PNG
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)  # Important!
        icon_img = ImageTk.PhotoImage(Image.open(buffer))

# Set icon
        self.root.iconphoto(False, icon_img)
        self.icon_img_ref = icon_img  # prevent garbage collection



# --- Run the Application ---
if __name__ == "__main__":
    root = tk.Tk()
    app = VamCodeo(root)
    root.mainloop()

