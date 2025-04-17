import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import subprocess
import tempfile
import re
import platform
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageTk
from tkinter import ttk
import pathlib


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
        elif platform.system() == "Darwin":
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            return "dark" if "Dark" in result.stdout else "light"
    except Exception as e:
        print("System theme detection failed:", e)
    return "dark"


class VamCodeo:
    def __init__(self, root):
        self.root = root
        self.root.title("VamCodeo")
        self.root.minsize(600, 400)
        self._base_title = "VamCodeo"

        # Icon
        img_size = 1024
        img = Image.new('RGB', (img_size, img_size), color='red')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 700)
        except IOError:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), "</>", font=font)
        x = (img_size - (bbox[2] - bbox[0])) // 2 - bbox[0]
        y = (img_size - (bbox[3] - bbox[1])) // 2 - bbox[1]
        draw.text((x, y), "</>", fill='white', font=font)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        icon_img = ImageTk.PhotoImage(Image.open(buffer))
        self.root.iconphoto(True, icon_img)
        self.icon_img_ref = icon_img

        # Theme
        self.theme = "dark"

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

        self.tabs = {}
        self.sidebar_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.sidebar_pane.pack(fill=tk.BOTH, expand=True)

# File tree panel
        self.file_tree_frame = tk.Frame(self.sidebar_pane, width=200)
        self.file_tree = ttk.Treeview(self.file_tree_frame)
        self.file_tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.file_tree_scroll = tk.Scrollbar(self.file_tree_frame, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=self.file_tree_scroll.set)
        self.file_tree_scroll.pack(fill=tk.Y, side=tk.RIGHT)
        self.sidebar_pane.add(self.file_tree_frame)

# Tab area
        self.tab_control = ttk.Notebook(self.sidebar_pane)
        self.sidebar_pane.add(self.tab_control)

        self.tab_control.bind("<<NotebookTabChanged>>", self._on_tab_switched)
        self.tab_control.bind("<Button-1>", self._on_tab_click)
        self._create_new_tab()

        self.output_area = tk.Text(self.root, height=10, state=tk.DISABLED)
        self.output_area.pack(fill=tk.BOTH)

        self.menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        run_menu = tk.Menu(self.menu_bar, tearoff=0)
        debug_menu = tk.Menu(self.menu_bar, tearoff=0)
        edit_menu = tk.Menu(self.menu_bar, tearoff=0)

        file_menu.add_command(label="New Tab", command=self._create_new_tab)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_command(label="Save As...", command=self.save_as_file)
        file_menu.add_separator()
        file_menu.add_command(label="Toggle Theme", command=self.toggle_theme)
        file_menu.add_command(label="Exit", command=self._safe_close)

        run_menu.add_command(label="Run", command=self._run_code)
        debug_menu.add_command(label="Run with Print Debugging", command=self._debug_with_print)

        edit_menu.add_command(label="Find and Replace", command=self.show_find_replace)

        self.menu_bar.add_cascade(label="File", menu=file_menu)
        self.menu_bar.add_cascade(label="Run", menu=run_menu)
        self.menu_bar.add_cascade(label="Debug", menu=debug_menu)
        self.menu_bar.add_cascade(label="Edit", menu=edit_menu)

        self.root.config(menu=self.menu_bar)

        self.root.bind("<Control-n>", lambda e: self._create_new_tab())
        self.root.bind("<Control-o>", self.open_file)
        self.root.bind("<Control-s>", self.save_file)
        self.root.bind("<Control-S>", self.save_as_file)
        self.root.bind("<Control-f>", lambda e: self.show_find_replace())
        self.root.bind("<F5>", self._run_code)
        self.root.protocol("WM_DELETE_WINDOW", self._safe_close)
         
        self._populate_file_tree(pathlib.Path.cwd())
        self.file_tree.bind("<Double-1>", self._on_file_tree_open)


    def _create_new_tab(self, content="", title="Untitled", file_path=None):
        tab = tk.Frame(self.tab_control)
        display_title = f"{title}  [x]"
        self.tab_control.add(tab, text=display_title)
        self.tab_control.select(tab)

        editor_frame = tk.Frame(tab)
        editor_frame.pack(fill=tk.BOTH, expand=True)

        # Line numbers
        line_numbers = tk.Text(editor_frame, width=4, padx=4, state=tk.DISABLED)
        line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        # Main text editor
        text_area = tk.Text(editor_frame, undo=True, wrap=tk.NONE)
        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scroll sync
        def sync_scroll(*args):
                text_area.yview(*args)
                line_numbers.yview(*args)

        scrollbar = tk.Scrollbar(editor_frame, command=sync_scroll)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_area.config(yscrollcommand=scrollbar.set)
        line_numbers.config(yscrollcommand=scrollbar.set)

        # Update line numbers
        def update_lines(event=None):
                lines = text_area.get("1.0", tk.END).split("\n")
                nums = "\n".join(str(i + 1) for i in range(len(lines)))
                line_numbers.config(state=tk.NORMAL)
                line_numbers.delete("1.0", tk.END)
                line_numbers.insert("1.0", nums)
                line_numbers.config(state=tk.DISABLED)

        text_area.bind("<KeyRelease>", lambda e: (self._highlight_syntax(), update_lines(), self._show_autocomplete(e)))
        text_area.bind("<<Modified>>", lambda e: update_lines())
        text_area.bind("<Return>", self._auto_indent)

        # Autocomplete popup (init but not shown yet)
        self.autocomplete_listbox = None

        text_area.insert("1.0", content)
        update_lines()

        self.tabs[tab] = {
                "text_widget": text_area,
                "file_path": file_path,
                "line_numbers": line_numbers
        }

        text_area.edit_modified(False)
        self._update_title()
        self._highlight_syntax()

    def _get_current_tab_info(self):
        tab = self.tab_control.select()
        return self.tabs.get(self.root.nametowidget(tab))

    def _get_current_text_widget(self):
        info = self._get_current_tab_info()
        return info["text_widget"] if info else None

    def _get_current_file_path(self):
        info = self._get_current_tab_info()
        return info["file_path"] if info else None

    def _set_current_file_path(self, path):
        info = self._get_current_tab_info()
        if info:
            info["file_path"] = path

    def _on_tab_switched(self, event=None):
        self._update_title()
        self._highlight_syntax()

    def _update_title(self):
        text_widget = self._get_current_text_widget()
        file_path = self._get_current_file_path()
        title = self._base_title
        if file_path:
            title += f" - {os.path.basename(file_path)}"
        else:
            title += " - Untitled"
        if text_widget and text_widget.edit_modified():
            title += " *"
        self.root.title(title)

    def _on_text_modified(self, event=None):
        self._update_title()
        self._highlight_syntax()

    def _ask_save_if_dirty(self):
        text_widget = self._get_current_text_widget()
        if not text_widget or not text_widget.edit_modified():
            return True
        response = messagebox.askyesnocancel("Save Changes?", "Save changes before proceeding?")
        if response is True:
            return self.save_file()
        return response is not None

    def _safe_close(self):
        if self._ask_save_if_dirty():
            self.root.destroy()

    def open_file(self, event=None):
        if not self._ask_save_if_dirty():
            return
        file_path = filedialog.askopenfilename(filetypes=[("Python Files", "*.py"), ("All Files", "*.*"), ("Text Files", "*.txt")])
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._create_new_tab(content, os.path.basename(file_path), file_path)

    def save_file(self, event=None):
        path = self._get_current_file_path()
        if path:
            try:
                text = self._get_current_text_widget().get("1.0", tk.END)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self._get_current_text_widget().edit_modified(False)
                self._update_title()
                return True
            except Exception as e:
                messagebox.showerror("Save Error", str(e))
        else:
            return self.save_as_file()
        return False

    def save_as_file(self, event=None):
        file_path = filedialog.asksaveasfilename(defaultextension=".py")
        if file_path:
            self._set_current_file_path(file_path)
            return self.save_file()
        return False

    def _run_code(self, event=None):
        text = self._get_current_text_widget()
        if text:
            code = text.get("1.0", tk.END)
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

    def _display_output(self, output, error=""):
        self.output_area.config(state=tk.NORMAL)
        self.output_area.delete("1.0", tk.END)
        self.output_area.insert(tk.END, "--- Output ---\n" + output)
        if error:
            self.output_area.insert(tk.END, "\n--- Errors ---\n" + error)
        self.output_area.config(state=tk.DISABLED)
        self.output_area.see(tk.END)

    def _debug_with_print(self):
        text = self._get_current_text_widget()
        if text:
            code = text.get("1.0", tk.END)
            debugged = []
            lines = code.splitlines()
            for i, line in enumerate(lines):
                debugged.append(line)
                if any(line.strip().startswith(x) for x in ("def ", "for ", "if ", "while ", "elif ", "else:")):
                    indent = len(line) - len(line.lstrip())
                    debugged.append(" " * (indent + 4) + f'print("Debug: Line {i + 1}")')
            self._run_code_from_string("\n".join(debugged))

    def _run_code_from_string(self, code):
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
        text = self._get_current_text_widget()
        if not text:
            return
        for tag in ["keyword", "comment", "string", "number", "operator", "builtin"]:
            text.tag_remove(tag, "1.0", tk.END)

        code = text.get("1.0", tk.END)
        lines = code.splitlines()
        for i, line in enumerate(lines):
            line_num = i + 1
            for kw in self.keywords:
                for match in re.finditer(rf'\b{re.escape(kw)}\b', line):
                    text.tag_add("keyword", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
            if (m := re.search(r'#.*', line)):
                text.tag_add("comment", f"{line_num}.{m.start()}", f"{line_num}.{m.end()}")
            for match in re.finditer(r'(".*?"|\'.*?\')', line):
                text.tag_add("string", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
            for match in re.finditer(r'\b\d+(\.\d+)?\b', line):
                text.tag_add("number", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
            for match in re.finditer(r'[+\-*/%=<>!&|^]', line):
                text.tag_add("operator", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")
            for b in self.builtins:
                for match in re.finditer(rf'\b{re.escape(b)}\b', line):
                    text.tag_add("builtin", f"{line_num}.{match.start()}", f"{line_num}.{match.end()}")

    def _auto_indent(self, event):
        text = self._get_current_text_widget()
        if not text:
            return
        cursor = text.index("insert")
        line = cursor.split(".")[0]
        line_text = text.get(f"{line}.0", f"{line}.end")
        indent = re.match(r"^(\s+)", line_text)
        spaces = indent.group(1) if indent else ""
        if line_text.rstrip().endswith(":"):
            spaces += "    "
        text.insert(cursor, f"\n{spaces}")
        return "break"

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()

    def apply_theme(self):
        # Force dark theme if not explicitly set
        if self.theme not in self.themes:
                self.theme = "dark"

        t = self.themes[self.theme]

        # Root and output
        self.root.config(bg=t["bg"])
        self.output_area.config(bg=t["output_bg"], fg=t["output_fg"])

        # Tab editor widgets
        for tab_info in self.tabs.values():
                w = tab_info["text_widget"]
                w.config(bg=t["bg"], fg=t["fg"], insertbackground=t["insert"])
                w.tag_configure("keyword", foreground=t["keyword"])
                w.tag_configure("comment", foreground=t["comment"])
                w.tag_configure("string", foreground=t["string"])
                w.tag_configure("number", foreground=t["number"])
                w.tag_configure("operator", foreground=t["operator"])
                w.tag_configure("builtin", foreground=t["builtin"])

                # Line numbers
                if "line_numbers" in tab_info:
                        tab_info["line_numbers"].config(bg=t["line_bg"], fg=t["fg"])

        # File tree styling
        self.file_tree_frame.config(bg=t["bg"])
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=t["bg"],
                        foreground=t["fg"],
                        fieldbackground=t["bg"],
                        font=("Consolas", 10))
        style.map("Treeview",
                  background=[('selected', "#444444" if self.theme == "dark" else "#cccccc")],
                  foreground=[('selected', t["fg"])])

        self.file_tree.configure(style="Treeview")

        # Reapply highlighting to ensure new colors take effect
        self._highlight_syntax()



    def show_find_replace(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Find and Replace")
        dialog.geometry("300x140")
        dialog.transient(self.root)
        dialog.resizable(False, False)

        tk.Label(dialog, text="Find:").pack(pady=(10, 0))
        find_entry = tk.Entry(dialog, width=30)
        find_entry.pack()
        tk.Label(dialog, text="Replace:").pack(pady=(5, 0))
        replace_entry = tk.Entry(dialog, width=30)
        replace_entry.pack()

        def do_find():
            text = self._get_current_text_widget()
            if text:
                text.tag_remove("search", "1.0", tk.END)
                word = find_entry.get()
                if word:
                    idx = "1.0"
                    while True:
                        idx = text.search(word, idx, nocase=1, stopindex=tk.END)
                        if not idx:
                            break
                        end_idx = f"{idx}+{len(word)}c"
                        text.tag_add("search", idx, end_idx)
                        idx = end_idx
                    text.tag_config("search", background="orange", foreground="black")

        def do_replace():
            text = self._get_current_text_widget()
            if text:
                word = find_entry.get()
                replacement = replace_entry.get()
                idx = text.search(word, "1.0", nocase=1, stopindex=tk.END)
                if idx:
                    end_idx = f"{idx}+{len(word)}c"
                    text.delete(idx, end_idx)
                    text.insert(idx, replacement)

        def do_replace_all():
            text = self._get_current_text_widget()
            if text:
                content = text.get("1.0", tk.END)
                new_content = content.replace(find_entry.get(), replace_entry.get())
                text.delete("1.0", tk.END)
                text.insert("1.0", new_content)

        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Find", command=do_find).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Replace", command=do_replace).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Replace All", command=do_replace_all).pack(side=tk.LEFT, padx=5)
     
        def _populate_file_tree(self, path, parent=""):
          for p in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            node_id = self.file_tree.insert(parent, "end", text=p.name, open=False)
            if p.is_dir():
                self._populate_file_tree(p, node_id)
            else:
                self.file_tree.item(node_id, values=[str(p)])

    def _on_file_tree_open(self, event):
      selected = self.file_tree.focus()
      path_parts = []
      while selected:
        node = self.file_tree.item(selected)
        path_parts.insert(0, node["text"])
        selected = self.file_tree.parent(selected)
        full_path = os.path.join(*path_parts)
        if os.path.isfile(full_path) and full_path.endswith   (".py"):
            with open(full_path, "r", encoding="utf-8") as f:
              content = f.read()
            self._create_new_tab(content, os.path.basename(full_path), full_path)

    def _populate_file_tree(self, path, parent=""):
      try:
          for p in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
              node_id = self.file_tree.insert(parent, "end", text=p.name, open=False)
              if p.is_dir():
                  self._populate_file_tree(p, node_id)
              else:
                  self.file_tree.item(node_id, values=[str(p)])
      except PermissionError:
          pass  # Skip folders we can't access

    def _on_tab_click(self, event):
        x, y = event.x, event.y
        tab_index = self.tab_control.index(f"@{x},{y}")
        tab_id = self.tab_control.tabs()[tab_index]
        tab_text = self.tab_control.tab(tab_id, "text")

        if tab_text.endswith("✕"):
                # Get width of text before '✕' to estimate click range
                text_area = self.tabs[self.root.nametowidget(tab_id)]["text_widget"]
                bbox = self.tab_control.bbox(tab_index)
                if bbox:
                        bx, by, bw, bh = bbox
                        close_btn_width = 20  # Estimate width of ✕ area
                        if x >= bx + bw - close_btn_width:
                                self._close_tab(tab_id)


    def _close_tab(self, tab_id):
        widget = self.root.nametowidget(tab_id)
        info = self.tabs.get(widget)
        text_widget = info["text_widget"]

        if text_widget.edit_modified():
                confirm = messagebox.askyesnocancel("Unsaved Changes", "Save changes before closing?")
                if confirm is None:
                        return
                elif confirm:
                        self.tab_control.select(widget)
                        if not self.save_file():
                                return

        self.tab_control.forget(widget)
        del self.tabs[widget]
        self._update_title()

    def _show_autocomplete(self, event):
        widget = self._get_current_text_widget()
        if not widget:
                return

        cursor = widget.index(tk.INSERT)
        line = widget.get(f"{cursor} linestart", cursor)
        match = re.findall(r"[a-zA-Z_]\w*$", line)
        if not match:
                if self.autocomplete_listbox:
                        self.autocomplete_listbox.destroy()
                        self.autocomplete_listbox = None
                return

        prefix = match[-1]
        suggestions = [w for w in self.keywords + self.builtins if w.startswith(prefix)]

        if not suggestions:
                if self.autocomplete_listbox:
                        self.autocomplete_listbox.destroy()
                        self.autocomplete_listbox = None
                return

        if self.autocomplete_listbox:
                self.autocomplete_listbox.destroy()

        self.autocomplete_listbox = tk.Listbox(widget, height=min(6, len(suggestions)), bg="black", fg="white")
        for word in suggestions:
                self.autocomplete_listbox.insert(tk.END, word)

        # Position below cursor
        bbox = widget.bbox(tk.INSERT)
        if bbox:
                x, y, _, h = bbox
                self.autocomplete_listbox.place(x=x, y=y + h)
                self.autocomplete_listbox.lift()
                self.autocomplete_listbox.bind("<Double-Button-1>", lambda e: self._insert_autocomplete(widget, prefix))
                self.autocomplete_listbox.bind("<Return>", lambda e: self._insert_autocomplete(widget, prefix))
  
    def _insert_autocomplete(self, widget, prefix):
        if not self.autocomplete_listbox:
                return
        selection = self.autocomplete_listbox.get(tk.ACTIVE)
        cursor = widget.index(tk.INSERT)
        widget.delete(f"{cursor} - {len(prefix)}c", cursor)
        widget.insert(cursor, selection)
        self.autocomplete_listbox.destroy()
        self.autocomplete_listbox = None


if __name__ == "__main__":
    root = tk.Tk()
    app = VamCodeo(root)
    root.mainloop()

