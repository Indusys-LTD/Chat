import os
import requests
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
from PIL import Image, ImageTk, ImageDraw
import sys
from base64 import b64encode
from datetime import datetime
import io
import base64
from pygments import lex
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.token import Token
import re

class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Local LLM Chat")
        self.root.geometry("1000x700")  # Set default window size
        self.root.minsize(800, 600)     # Set minimum window size
        
        # Theme colors
        self.theme = {
            'bg_dark': "#1e1e1e",
            'bg_medium': "#252526",
            'bg_light': "#2d2d30",
            'accent_blue': "#007acc",
            'accent_hover': "#1c97ea",
            'user_color': "#4a9eff",
            'assistant_color': "#ff4a4a",
            'text_primary': "#ffffff",
            'text_secondary': "#cccccc",
            'border_color': "#404040",
            'scroll_trough': "#333333"  # Added new scrollbar color
        }
        
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')  # Added this line for better theme support
        
        style.configure(
            "Custom.TButton",
            padding=6,
            background=self.theme['bg_light'],
            foreground=self.theme['text_primary']
        )
        style.configure(
            "Custom.TEntry",
            padding=6,
            fieldbackground=self.theme['bg_dark'],
            foreground=self.theme['text_primary'],
            insertcolor=self.theme['text_primary']
        )
        style.configure(
            "Custom.Horizontal.TScrollbar",
            background=self.theme['bg_light'],
            troughcolor=self.theme['scroll_trough'],  # Changed from bg_dark
            bordercolor=self.theme['border_color']
        )
        
        style.configure(
            "Custom.TCombobox",
            fieldbackground=self.theme['bg_dark'],
            foreground=self.theme['text_primary'],
            background=self.theme['bg_dark'],
            selectbackground=self.theme['accent_blue'],
            selectforeground=self.theme['text_primary'],
            bordercolor=self.theme['border_color'],
            arrowcolor=self.theme['text_primary']
        )
        style.map('Custom.TCombobox',
            fieldbackground=[('readonly', self.theme['bg_dark'])],
            background=[('readonly', self.theme['bg_dark'])]
        )
        
        self.context = None
        self.available_models = []
        self.chat_history_data = []
        self.attachments = []
        self.current_attachments = []
        
        # Load and resize icons
        self.user_icon = self._load_resized_icon("user.png")
        self.bot_icon = self._load_resized_icon("bot.png")
        
        # Create Sidebar
        self.create_sidebar()

        # Create Main Chat Area
        self.create_main_area()

        # Create Footer
        self.create_footer()
        
        # Fetch models in background thread
        threading.Thread(target=self.fetch_available_models).start()
        
        # Configure fonts
        if sys.platform == "darwin":
            self.emoji_font = ("Apple Color Emoji", 12)
        elif sys.platform.startswith("linux"):
            self.emoji_font = ("Noto Color Emoji", 12) 
        else:
            self.emoji_font = ("Segoe UI Emoji", 12)
        
        self.configure_code_highlighting()
        
    def fetch_available_models(self):
        """Fetch list of available models from Ollama"""
        try:
            response = requests.get("http://localhost:11434/api/tags")
            response.raise_for_status()
            models_data = json.loads(response.text)
            self.available_models = [model['name'] for model in models_data.get('models', [])]
            
            # Update combobox on main thread
            self.root.after(0, lambda: self.model_selector.configure(
                values=self.available_models + ["custom"]
            ))
            if self.available_models:
                self.root.after(0, lambda: self.model_selector.set(self.available_models[0]))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showwarning(
                "Warning",
                f"Could not fetch models: {str(e)}\nYou can manually enter model names"
            ))
    
    def create_sidebar(self):
        sidebar = tk.Frame(self.root, bg=self.theme['bg_medium'], width=240)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Header
        header_frame = tk.Frame(sidebar, bg=self.theme['bg_medium'], height=60)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        tk.Label(
            header_frame, 
            text="Chat History", 
            font=("Segoe UI", 14, "bold"),
            bg=self.theme['bg_medium'],
            fg=self.theme['text_primary'],
            anchor="w"
        ).pack(side="left", padx=20, pady=15)

        # History list
        list_frame = tk.Frame(sidebar, bg=self.theme['bg_medium'])
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.history_listbox = tk.Listbox(
            list_frame,
            bg=self.theme['bg_dark'],
            fg=self.theme['text_primary'],
            selectbackground=self.theme['accent_blue'],
            selectforeground=self.theme['text_primary'],
            font=("Segoe UI", 10),
            bd=0,
            highlightthickness=0,
            activestyle="none"
        )
        self.history_listbox.pack(fill="both", expand=True)
        self.history_listbox.bind("<Double-1>", self.load_chat_from_history)

        # Load saved chats
        self.load_saved_chats()

    def create_main_area(self):
        # Header
        header = tk.Frame(self.root, bg=self.theme['bg_light'], height=60)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        
        header_label = tk.Label(
            header,
            text="Local LLM Chat",
            bg=self.theme['bg_light'],
            fg=self.theme['text_primary'],
            font=("Segoe UI", 16, "bold")
        )
        header_label.pack(side="left", padx=20, pady=10)

        # Model Selector
        model_frame = tk.Frame(header, bg=self.theme['bg_light'])
        model_frame.pack(side="right", padx=20, pady=10)
        model_label = tk.Label(
            model_frame,
            text="Model:",
            bg=self.theme['bg_light'],
            fg=self.theme['text_primary'],
            font=("Segoe UI", 10)
        )
        model_label.pack(side="left", padx=5)
        
        self.model_var = tk.StringVar()
        self.model_selector = ttk.Combobox(
            model_frame, 
            textvariable=self.model_var,
            state="readonly",
            values=self.available_models,
            width=20,
            style="Custom.TCombobox"
        )
        self.model_selector.pack(side="left")

        # Chat History
        history_frame = tk.Frame(self.root, bg=self.theme['bg_dark'])
        history_frame.pack(fill="both", expand=True, padx=20, pady=(10, 0))
        
        self.chat_history = scrolledtext.ScrolledText(
            history_frame,
            wrap=tk.WORD,
            state="disabled",
            font=("Segoe UI", 11),
            bg=self.theme['bg_dark'],
            fg=self.theme['text_primary'],
            bd=0,
            padx=10,
            pady=5,
            insertbackground=self.theme['text_primary'],
            selectbackground=self.theme['accent_blue'],
            selectforeground=self.theme['text_primary']
        )
        self.chat_history.pack(fill="both", expand=True)

        # Input Area
        input_frame = tk.Frame(self.root, bg=self.theme['bg_light'], height=100)
        input_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        
        # Attachment preview area
        self.attachment_frame = tk.Frame(input_frame, bg=self.theme['bg_light'])
        self.attachment_frame.pack(fill="x", pady=(0, 10))
        
        # Input and buttons
        input_controls = tk.Frame(input_frame, bg=self.theme['bg_light'])
        input_controls.pack(fill="x")
        
        self.input_entry = ttk.Entry(
            input_controls,
            font=("Segoe UI", 11),
            style="Custom.TEntry",
            width=50  # Added fixed width for better layout
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.input_entry.bind("<Return>", lambda event: self.send_message())

        button_frame = tk.Frame(input_controls, bg=self.theme['bg_light'])
        button_frame.pack(side="right")
        
        self.attach_btn = ttk.Button(
            button_frame,
            text="📎",
            command=self.attach_file,
            style="Custom.TButton",
            width=3
        )
        self.attach_btn.pack(side="left", padx=5)
        
        emoji_btn = ttk.Button(
            button_frame,
            text="😀",
            command=self.show_emoji_picker,
            style="Custom.TButton",
            width=3
        )
        emoji_btn.pack(side="left", padx=5)
        
        self.send_button = ttk.Button(
            button_frame,
            text="Send",
            command=self.send_message,
            style="Custom.TButton",
            width=8
        )
        self.send_button.pack(side="left", padx=5)

    def create_footer(self):
        footer = tk.Frame(self.root, bg=self.theme['bg_medium'], height=30)  # Changed from accent_blue
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        
        self.footer_label = tk.Label(
            footer,
            text="Status: Ready",
            bg=self.theme['bg_medium'],  # Changed from accent_blue
            fg=self.theme['text_primary'],
            font=("Segoe UI", 9),
            anchor="w"
        )
        self.footer_label.pack(side="left", padx=20, pady=5)

    def configure_code_highlighting(self):
        """Set up syntax highlighting colors and tags"""
        code_colors = {
            Token.Keyword: "#f92672",
            Token.Name.Builtin: "#66d9ef",
            Token.Literal.String: "#e6db74",
            Token.Comment.Single: "#75715e",
            Token.Text: "#f8f8f2",
        }
        
        for token_type, color in code_colors.items():
            self.chat_history.tag_config(str(token_type), foreground=color)
            
        self.chat_history.tag_config("codeblock", 
            background="#2a2a2a", 
            relief="ridge", 
            borderwidth=1,
            font=("Consolas", 10)
        )

    def update_chat_history(self, message_data):
        self.chat_history.configure(state="normal")
        
        # Add timestamp
        timestamp = datetime.fromisoformat(message_data.get("timestamp", datetime.now().isoformat()))
        time_str = timestamp.strftime("%I:%M %p")
        
        # Insert avatar and header
        sender = message_data["sender"]
        if sender == "You":
            # Add spacing for alignment
            self.chat_history.insert(tk.END, " " * 40)
            
            # Create message bubble canvas
            bubble_canvas = tk.Canvas(
                self.chat_history,
                bg=self.theme['bg_dark'],
                height=100,  # Initial height, will be adjusted
                width=400,
                highlightthickness=0
            )
            self.chat_history.window_create(tk.END, window=bubble_canvas)
            
            # Create bubble shape
            bubble_frame = tk.Frame(
                bubble_canvas,
                bg=self.theme['user_color'],
                padx=10,
                pady=5
            )
            
            # Add header with timestamp
            header = tk.Label(
                bubble_frame,
                text=f"You • {time_str}",
                font=("Segoe UI", 9, "bold"),
                fg=self.theme['text_primary'],
                bg=self.theme['user_color']
            )
            header.pack(anchor="e")
            
            # Add message content
            content = tk.Text(
                bubble_frame,
                wrap=tk.WORD,
                font=("Segoe UI", 11),
                bg=self.theme['user_color'],
                fg=self.theme['text_primary'],
                relief="flat",
                height=1,
                width=40,
                highlightthickness=0,
                borderwidth=0
            )
            content.pack(fill="both", expand=True)
            
            # Insert message text
            text = message_data.get("text", "")
            if text:
                content.insert("1.0", text)
            content.configure(state="disabled")
            
            # Create rounded rectangle for bubble
            bubble_window = bubble_canvas.create_window(10, 0, window=bubble_frame, anchor="nw")
            
            # Update canvas size based on content
            bubble_frame.update_idletasks()
            height = bubble_frame.winfo_height() + 20
            width = bubble_frame.winfo_width() + 20
            bubble_canvas.configure(height=height, width=width)
            
            # Draw rounded rectangle behind the frame
            bubble_canvas.create_polygon(
                width-10, 0,  # Top right
                10, 0,  # Top left
                10, height-10,  # Bottom left
                width-20, height-10,  # Bottom right before point
                width-10, height,  # Point
                width-10, height-10,  # Bottom right after point
                width-10, 0,  # Back to top right
                fill=self.theme['user_color'],
                outline=self.theme['user_color']
            )
            
            # Add user icon after bubble
            self.chat_history.insert(tk.END, "  ")
            self.chat_history.image_create(tk.END, image=self.user_icon)
        else:
            # Add assistant icon
            self.chat_history.image_create(tk.END, image=self.bot_icon)
            self.chat_history.insert(tk.END, "  ")
            
            # Create message bubble canvas
            bubble_canvas = tk.Canvas(
                self.chat_history,
                bg=self.theme['bg_dark'],
                height=100,  # Initial height, will be adjusted
                width=400,
                highlightthickness=0
            )
            self.chat_history.window_create(tk.END, window=bubble_canvas)
            
            # Create bubble shape
            bubble_frame = tk.Frame(
                bubble_canvas,
                bg=self.theme['assistant_color'],
                padx=10,
                pady=5
            )
            
            # Add header with timestamp
            header = tk.Label(
                bubble_frame,
                text=f"Assistant • {time_str}",
                font=("Segoe UI", 9, "bold"),
                fg=self.theme['text_primary'],
                bg=self.theme['assistant_color']
            )
            header.pack(anchor="w")
            
            # Add message content
            content = tk.Text(
                bubble_frame,
                wrap=tk.WORD,
                font=("Segoe UI", 11),
                bg=self.theme['assistant_color'],
                fg=self.theme['text_primary'],
                relief="flat",
                height=1,
                width=40,
                highlightthickness=0,
                borderwidth=0
            )
            content.pack(fill="both", expand=True)
            
            # Insert message text
            text = message_data.get("text", "")
            if text:
                parts = self.split_code_blocks(text)
                for part in parts:
                    if part['type'] == 'text':
                        content.insert(tk.END, part['content'])
                    elif part['type'] == 'code':
                        self.insert_code_block(content, part['content'], part.get('lang', ''))
            content.configure(state="disabled")
            
            # Create rounded rectangle for bubble
            bubble_window = bubble_canvas.create_window(10, 0, window=bubble_frame, anchor="nw")
            
            # Update canvas size based on content
            bubble_frame.update_idletasks()
            height = bubble_frame.winfo_height() + 20
            width = bubble_frame.winfo_width() + 20
            bubble_canvas.configure(height=height, width=width)
            
            # Draw rounded rectangle behind the frame
            bubble_canvas.create_polygon(
                10, 0,  # Top left
                width-10, 0,  # Top right
                width-10, height-10,  # Bottom right
                20, height-10,  # Bottom left before point
                10, height,  # Point
                20, height-10,  # Bottom left after point
                10, 0,  # Back to top left
                fill=self.theme['assistant_color'],
                outline=self.theme['assistant_color']
            )
        
        # Insert attachments
        for att in message_data.get("attachments", []):
            if att["type"] == "image":
                # Display embedded image
                img_data = att["data"]
                img = Image.open(io.BytesIO(base64.b64decode(img_data)))
                img.thumbnail((200, 200))
                photo = ImageTk.PhotoImage(img)
                self.chat_history.image_create(tk.END, image=photo)
                self.chat_history.image = photo
            else:
                # Show document icon and name
                self.chat_history.insert(tk.END, "    📄 " + att["name"])
            self.chat_history.insert(tk.END, "\n")
        
        self.chat_history.insert(tk.END, "\n\n")
        self.chat_history.configure(state="disabled")
        self.chat_history.see(tk.END)

    def split_code_blocks(self, text):
        """Split message text into regular text and code blocks"""
        parts = []
        current_pos = 0
        
        while True:
            start = text.find('```', current_pos)
            if start == -1:
                parts.append({'type': 'text', 'content': text[current_pos:]})
                break
                
            if start > current_pos:
                parts.append({'type': 'text', 'content': text[current_pos:start]})
                
            end = text.find('```', start + 3)
            if end == -1:
                code_content = text[start+3:]
                parts.append({'type': 'code', 'content': code_content, 'lang': ''})
                break
                
            lang_part = text[start+3:end].split('\n', 1)
            lang = lang_part[0].strip() if len(lang_part) > 1 else ''
            code_content = lang_part[-1].rsplit('```', 1)[0]
            
            parts.append({'type': 'code', 'content': code_content, 'lang': lang})
            current_pos = end + 3
            
        return parts

    def insert_code_block(self, parent_widget, code, lang):
        """Insert a syntax-highlighted code block into a text widget"""
        # Create code frame
        code_frame = tk.Frame(
            parent_widget,
            bg=self.theme['bg_dark'],
            padx=10,
            pady=5,
            relief="solid",
            borderwidth=1
        )
        parent_widget.window_create(tk.END, window=code_frame)
        
        # Add language label if provided
        if lang:
            lang_label = tk.Label(
                code_frame,
                text=lang,
                font=("Segoe UI", 9),
                fg=self.theme['text_secondary'],
                bg=self.theme['bg_dark']
            )
            lang_label.pack(anchor="w")
        
        # Create code text widget
        code_text = tk.Text(
            code_frame,
            wrap=tk.NONE,
            font=("Consolas", 10),
            bg=self.theme['bg_dark'],
            fg=self.theme['text_primary'],
            relief="flat",
            height=min(len(code.split('\n')), 20),
            width=60,
            highlightthickness=0,
            borderwidth=0
        )
        code_text.pack(fill="both", expand=True)
        
        # Add syntax highlighting
        self.highlight_code(code_text, code, lang)
        code_text.configure(state="disabled")

    def highlight_code(self, text_widget, code, lang):
        """Apply Pygments syntax highlighting"""
        try:
            lexer = get_lexer_by_name(lang, stripall=True)
        except:
            lexer = TextLexer()
            
        for token, content in lex(code, lexer):
            tag = str(token)
            if not text_widget.tag_cget(tag, "foreground"):
                continue  # Skip unconfigured tags
            text_widget.insert(tk.END, content, tag)

    def ollama_chat(self, prompt):
        model_name = self.model_var.get()
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "context": self.context
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            response_data = json.loads(response.text)
            
            self.context = response_data.get("context")
            return response_data.get("response", "")
        except Exception as e:
            return f"Error: {str(e)}"
        
    def send_message(self):
        user_input = self.input_entry.get().strip()
        if not user_input and not self.current_attachments:
            return
            
        # Create message object with attachments
        message_data = {
            "text": user_input,
            "attachments": [],
            "sender": "You",
            "timestamp": datetime.now().isoformat()
        }
        
        # Process attachments
        for file_path in self.current_attachments:
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                # Encode image as base64
                with open(file_path, "rb") as f:
                    encoded = b64encode(f.read()).decode('utf-8')
                message_data["attachments"].append({
                    "type": "image",
                    "data": encoded,
                    "name": os.path.basename(file_path)
                })
            else:
                # Store document path (or read content)
                message_data["attachments"].append({
                    "type": "document",
                    "path": file_path,
                    "name": os.path.basename(file_path)
                })
        
        self.chat_history_data.append(message_data)
        self.save_chat_to_file()
        
        # Clear attachments
        self.current_attachments = []
        for child in self.attachment_frame.winfo_children():
            child.destroy()
        
        self.input_entry.delete(0, tk.END)
        self.update_chat_history(message_data)
        
        # Disable UI during processing
        self.send_button.config(state="disabled")
        self.footer_label.config(text="Status: Assistant is typing...")
        
        # Use proper streaming endpoint
        threading.Thread(target=self.stream_llm_response, args=(user_input,)).start()

    def stream_llm_response(self, user_input):
        try:
            # Start typing animation
            self.root.after(0, self.start_typing_animation)
            
            url = "http://localhost:11434/api/chat"
            payload = {
                "model": self.model_var.get(),
                "messages": [{"role": "user", "content": user_input}],
                "stream": True,
                "context": self.context
            }

            raw_response = []
            with requests.post(url, json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if chunk.get("message"):
                            content = chunk["message"]["content"]
                            raw_response.append(content)

            # Stop typing animation and process response
            self.root.after(0, self.stop_typing_animation)
            
            full_content = "".join(raw_response)
            clean_content = full_content.replace("</think>", "").strip()
            clean_content = ' '.join(clean_content.split())
            
            self.root.after(0, self.finalize_response, clean_content)

        except Exception as e:
            self.root.after(0, self.stop_typing_animation)
            self.root.after(0, messagebox.showerror, "Error", str(e))
        finally:
            self.root.after(0, lambda: self.send_button.config(state="normal"))
            self.root.after(0, lambda: self.footer_label.config(text="Status: Ready"))

    def start_typing_animation(self):
        self.typing_active = True
        self.typing_steps = [".  ", ".. ", "..."]
        self.typing_step = 0
        self._animate_typing()

    def _animate_typing(self):
        if not self.typing_active:
            return
        
        self.chat_history.configure(state="normal")
        
        # Create or update typing indicator
        if hasattr(self, 'typing_indicator'):
            self.chat_history.delete(self.typing_indicator, "end")
        else:
            self.chat_history.image_create(tk.END, image=self.bot_icon, padx=5)
            self.typing_indicator = self.chat_history.index(tk.END)
        
        # Insert current animation step
        dots = self.typing_steps[self.typing_step]
        self.chat_history.insert(tk.END, "  " + dots, "typing")
        self.typing_step = (self.typing_step + 1) % len(self.typing_steps)
        
        self.chat_history.configure(state="disabled")
        self.chat_history.see(tk.END)
        
        # Schedule next animation frame
        self.root.after(500, self._animate_typing)

    def stop_typing_animation(self):
        self.typing_active = False
        if hasattr(self, 'typing_indicator'):
            self.chat_history.configure(state="normal")
            self.chat_history.delete(self.typing_indicator, "end")
            self.chat_history.configure(state="disabled")
            del self.typing_indicator

    def finalize_response(self, clean_content):
        self.stop_typing_animation()
        
        # Clean residual typing patterns
        clean_content = re.sub(r'(\.\s*){3,}', '', clean_content)
        clean_content = clean_content.strip()
        
        self.chat_history.configure(state="normal")
        self.chat_history.image_create(tk.END, image=self.bot_icon, padx=5)
        self.chat_history.insert(tk.END, "  " + clean_content + "\n\n", "assistant")
        self.chat_history.configure(state="disabled")
        
        # Save to history
        self.chat_history_data.append({"sender": "Assistant", "message": clean_content})
        self.save_chat_to_file()

    def save_chat_to_file(self):
        if not os.path.exists("history"):
            os.makedirs("history")
        file_name = "history/chat_history.json"
        with open(file_name, "w") as f:
            json.dump(self.chat_history_data, f, indent=4)

    def load_saved_chats(self):
        self.history_listbox.delete(0, tk.END)
        if os.path.exists("history/chat_history.json"):
            self.history_listbox.insert(tk.END, "chat_history.json")

    def load_chat_from_history(self, event):
        selection = self.history_listbox.get(self.history_listbox.curselection())
        file_path = f"history/{selection}"
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                self.chat_history_data = json.load(f)

            self.chat_history.configure(state="normal")
            self.chat_history.delete(1.0, tk.END)
            for entry in self.chat_history_data:
                self.update_chat_history(entry)
            self.chat_history.configure(state="disabled")

    def _load_resized_icon(self, filename):
        """Load and resize icon to 32x32 pixels"""
        try:
            img = Image.open(filename)
            img = img.resize((32, 32), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except FileNotFoundError:
            # Create default icons
            img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
            if filename == "user.png":
                # Create a simple user icon (circle with person silhouette)
                draw = ImageDraw.Draw(img)
                draw.ellipse([4, 4, 28, 28], fill="#4a9eff")
                draw.ellipse([12, 8, 20, 16], fill="white")  # head
                draw.ellipse([8, 16, 24, 28], fill="white")  # body
            elif filename == "bot.png":
                # Create a simple bot icon (square with antenna)
                draw = ImageDraw.Draw(img)
                draw.rectangle([6, 8, 26, 28], fill="#ff4a4a")
                draw.rectangle([14, 2, 18, 8], fill="#ff4a4a")  # antenna
                draw.ellipse([10, 12, 16, 18], fill="white")  # left eye
                draw.ellipse([16, 12, 22, 18], fill="white")  # right eye
            return ImageTk.PhotoImage(img)

    def show_emoji_picker(self):
        picker = tk.Toplevel(self.root)
        picker.title("Emoji Picker")
        picker.geometry("400x300")
        picker.configure(bg=self.theme['bg_light'])
        picker.transient(self.root)
        picker.grab_set()
        
        # Configure style
        style = ttk.Style()
        style.configure(
            "Custom.TNotebook",
            background=self.theme['bg_light'],
            foreground=self.theme['text_primary']
        )
        style.configure(
            "Custom.TNotebook.Tab",
            background=self.theme['bg_medium'],
            foreground=self.theme['text_primary'],
            padding=[10, 2],
            lightcolor=self.theme['bg_medium'],
            darkcolor=self.theme['bg_medium']
        )
        style.map(
            "Custom.TNotebook.Tab",
            background=[("selected", self.theme['bg_dark'])],
            foreground=[("selected", self.theme['text_primary'])],
            lightcolor=[("selected", self.theme['bg_dark'])],
            darkcolor=[("selected", self.theme['bg_dark'])]
        )
        
        # Add search entry
        search_frame = tk.Frame(picker, bg=self.theme['bg_light'])
        search_frame.pack(fill="x", padx=10, pady=10)
        
        search_entry = ttk.Entry(
            search_frame,
            font=("Segoe UI", 11),
            style="Custom.TEntry"
        )
        search_entry.pack(fill="x")
        
        # Emoji categories
        categories = {
            "Smileys": ["😀", "😃", "😄", "😁", "😅", "😂", "🤣", "😊", "😇", "🙂", "🙃", "😉", "😌", "😍", "🥰", "😘"],
            "Gestures": ["👋", "🤚", "✋", "🖐️", "👌", "🤌", "🤏", "✌️", "🤞", "🫰", "🤟", "🤘", "🤙", "👈", "👉", "👆"],
            "Animals": ["🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐸", "🐵", "🐔"],
            "Objects": ["💻", "📱", "⌚", "📷", "🎮", "🎧", "📚", "✏️", "📌", "💡", "🔑", "🎁", "🎈", "🎨", "🎭", "🎪"]
        }
        
        # Create notebook for categories
        notebook = ttk.Notebook(picker, style="Custom.TNotebook")
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        for category, emojis in categories.items():
            page = tk.Frame(
                notebook, 
                bg=self.theme['bg_dark'],  # Changed from bg_dark to match theme
                padx=5,
                pady=5
            )
            notebook.add(page, text=category)
            
            for i, emoji in enumerate(emojis):
                btn = tk.Label(
                    page,
                    text=emoji,
                    font=("Segoe UI Emoji", 20),
                    bg=self.theme['bg_dark'],
                    fg=self.theme['text_primary'],
                    padx=5,
                    pady=2
                )
                btn.bind("<Button-1>", lambda e, em=emoji: [self.insert_emoji(em), picker.destroy()])
                
                # Update hover effects to use theme colors
                btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=self.theme['accent_blue']))
                btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=self.theme['bg_dark']))

    def insert_emoji(self, emoji):
        self.input_entry.insert(tk.END, emoji)
        self.input_entry.focus()

    def attach_file(self):
        filetypes = [
            ("All files", "*.*"),
            ("Images", "*.jpg *.jpeg *.png *.gif"),
            ("Documents", "*.pdf *.doc *.docx *.txt")
        ]
        
        files = filedialog.askopenfilenames(
            title="Select files to attach",
            filetypes=filetypes
        )
        
        for file_path in files:
            self.current_attachments.append(file_path)
            self.show_attachment_preview(file_path)

    def show_attachment_preview(self, file_path):
        # Create preview item
        preview_frame = tk.Frame(
            self.attachment_frame,
            bg=self.theme['bg_dark'],
            padx=10,
            pady=5,
            relief="solid",
            borderwidth=1
        )
        preview_frame.pack(side="left", padx=5, pady=5)
        
        # Different handling for images
        if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            try:
                img = Image.open(file_path)
                img.thumbnail((100, 100))
                photo = ImageTk.PhotoImage(img)
                label = tk.Label(
                    preview_frame,
                    image=photo,
                    bg=self.theme['bg_dark']
                )
                label.image = photo  # Keep reference
                label.pack(side="left", padx=5)
            except Exception as e:
                messagebox.showerror("Error", f"Could not load image: {str(e)}")
        else:
            # Show document icon and filename
            doc_icon = tk.Label(
                preview_frame,
                text="📄",
                bg=self.theme['bg_dark'],
                fg=self.theme['text_primary'],
                font=("Segoe UI Emoji", 16)
            )
            doc_icon.pack(side="left", padx=5)
            
            filename = os.path.basename(file_path)
            name_label = tk.Label(
                preview_frame,
                text=filename,
                bg=self.theme['bg_dark'],
                fg=self.theme['text_primary'],
                font=("Segoe UI", 10),
                padx=5  # Add padding
            )
            name_label.pack(side="left", padx=5)
        
        # Add remove button
        remove_btn = tk.Button(
            preview_frame,
            text="×",
            font=("Segoe UI", 12, "bold"),
            fg=self.theme['text_primary'],
            bg=self.theme['bg_dark'],
            activebackground=self.theme['assistant_color'],
            activeforeground=self.theme['text_primary'],
            bd=0,
            padx=5,
            command=lambda f=file_path, p=preview_frame: self.remove_attachment(f, p)
        )
        remove_btn.pack(side="left", padx=5)
        
        # Add hover effect
        remove_btn.bind("<Enter>", lambda e: remove_btn.configure(bg=self.theme['assistant_color']))
        remove_btn.bind("<Leave>", lambda e: remove_btn.configure(bg=self.theme['bg_dark']))

    def remove_attachment(self, file_path, preview_frame):
        self.current_attachments.remove(file_path)
        preview_frame.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()
