import os
import requests
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
from PIL import Image, ImageTk
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
        
        # Add to __init__ method
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
        sidebar = tk.Frame(self.root, bg="#252526", width=200)
        sidebar.pack(side="left", fill="y")

        tk.Label(
            sidebar, 
            text="History", 
            font=("Segoe UI Emoji", 12, "bold"),  # Update font
            bg="#252526", fg="white", anchor="w"
        ).pack(fill="x", padx=10, pady=5)

        self.history_listbox = tk.Listbox(sidebar, bg="#1e1e1e", fg="white", selectbackground="#565656", selectforeground="white")
        self.history_listbox.pack(fill="both", expand=True, padx=10, pady=5)
        self.history_listbox.bind("<Double-1>", self.load_chat_from_history)

        # Load saved chats
        self.load_saved_chats()

    def create_main_area(self):
        # Header
        header = tk.Frame(self.root, bg="#2d2d30", height=50)
        header.pack(side="top", fill="x")
        header_label = tk.Label(
            header, text="Local LLM Chat", bg="#2d2d30", fg="white",
            font=("Arial", 14, "bold")
        )
        header_label.pack(pady=10)

        # Model Selector
        model_frame = tk.Frame(header, bg="#2d2d30")
        model_frame.pack(side="right", padx=10)
        model_label = tk.Label(
            model_frame, text="Model:", bg="#2d2d30", fg="white",
            font=("Arial", 10)
        )
        model_label.pack(side="left", padx=5)
        self.model_var = tk.StringVar()
        self.model_selector = ttk.Combobox(
            model_frame, 
            textvariable=self.model_var, 
            state="readonly",
            values=self.available_models
        )
        self.model_selector.pack(side="left")

        # Chat History
        self.chat_history = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, state="disabled",
            font=("Segoe UI Emoji", 12),  # Use emoji-friendly font
            bg="#1e1e1e", fg="white", bd=0, padx=10, pady=5
        )
        self.chat_history.pack(pady=10, padx=10, fill="both", expand=True)

        # Input Area
        input_frame = tk.Frame(self.root, bg="#1e1e1e")
        input_frame.pack(pady=10, padx=10, fill="x")

        self.input_entry = ttk.Entry(
            input_frame,
            font=("Segoe UI Emoji", 12)  # Add emoji support to input
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.input_entry.bind("<Return>", lambda event: self.send_message())

        self.send_button = ttk.Button(input_frame, text="Send", command=self.send_message)
        self.send_button.pack(side="left", padx=5)

        # Add emoji button to input area
        emoji_btn = ttk.Button(
            input_frame, 
            text="😀", 
            command=self.show_emoji_picker
        )
        emoji_btn.pack(side="left", padx=5)

        # Add attachment button next to send button
        self.attach_btn = ttk.Button(
            input_frame,
            text="📎",
            command=self.attach_file
        )
        self.attach_btn.pack(side="left", padx=5)

        # Attachment preview area
        self.attachment_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.attachment_frame.pack(fill="x", padx=10, before=input_frame)

    def create_footer(self):
        footer = tk.Frame(self.root, bg="#252526", height=30)
        footer.pack(side="bottom", fill="x")
        self.footer_label = tk.Label(
            footer, text="Status: Ready", bg="#252526", fg="white",
            font=("Arial", 10), anchor="w"
        )
        self.footer_label.pack(side="left", padx=10)

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
        
        # Insert avatar
        sender = message_data["sender"]
        if sender == "You":
            self.chat_history.image_create(tk.END, image=self.user_icon, padx=5)
            tag = 'user'
        else:
            self.chat_history.image_create(tk.END, image=self.bot_icon, padx=5)
            tag = 'assistant'
        
        # Process message text with code blocks
        text = message_data.get("text", "")
        if text:
            parts = self.split_code_blocks(text)
            for part in parts:
                if part['type'] == 'text':
                    self.chat_history.insert(tk.END, "  " + part['content'], tag)
                elif part['type'] == 'code':
                    self.insert_code_block(part['content'], part.get('lang', ''), tag)
        
        # Insert attachments
        for att in message_data.get("attachments", []):
            if att["type"] == "image":
                # Display embedded image
                img_data = att["data"]
                img = Image.open(io.BytesIO(base64.b64decode(img_data)))
                img.thumbnail((200, 200))
                photo = ImageTk.PhotoImage(img)
                self.chat_history.image_create(tk.END, image=photo)
                self.chat_history.insert(tk.END, "\n")
                # Keep reference to image
                self.chat_history.image = photo
            else:
                # Show document icon
                self.chat_history.insert(tk.END, "  📄 " + att["name"] + "\n", tag)
        
        self.chat_history.insert(tk.END, "\n")
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

    def insert_code_block(self, code, lang, sender_tag):
        """Insert a syntax-highlighted code block"""
        self.chat_history.insert(tk.END, "\n", sender_tag)
        
        # Create code frame
        code_frame = tk.Frame(self.chat_history, bg="#2a2a2a")
        self.chat_history.window_create(tk.END, window=code_frame)
        
        # Create code text widget
        code_text = tk.Text(
            code_frame,
            wrap=tk.NONE,
            bg="#2a2a2a",
            fg="#f8f8f2",
            insertbackground="white",
            font=("Consolas", 10),
            padx=10,
            pady=5,
            borderwidth=0
        )
        code_text.pack(fill="both", expand=True)
        
        # Add syntax highlighting
        self.highlight_code(code_text, code, lang)
        code_text.configure(state="disabled")
        
        self.chat_history.insert(tk.END, "\n", sender_tag)

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
            print(f"Warning: Icon file {filename} not found")
            return ImageTk.PhotoImage(Image.new('RGBA', (32, 32), (0, 0, 0, 0)))

    def show_emoji_picker(self):
        # Simple emoji picker window
        picker = tk.Toplevel(self.root)
        picker.title("Select Emoji")
        picker.geometry("300x200")
        
        # Common emojis
        emojis = [
            "😀 😃 😄 😅",
            "🤣 😊 😇 🙂 🙃", 
            "😉 😌 😍 🥰 😘 😗",
            "😙 😚 😋 😛 😝 😜",
            "🤓 😎 🥸 🤩 🥳 😏"
        ]
        
        for row in emojis:
            frame = tk.Frame(picker)
            frame.pack(fill="x")
            for emoji in row.split():
                btn = tk.Button(
                    frame, 
                    text=emoji, 
                    font=("Segoe UI Emoji", 14),
                    command=lambda e=emoji: self.insert_emoji(e)
                )
                btn.pack(side="left")

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
        preview_frame = tk.Frame(self.attachment_frame, bg="#1e1e1e")
        preview_frame.pack(side="left", padx=5, pady=5)
        
        # Different handling for images
        if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            try:
                img = Image.open(file_path)
                img.thumbnail((100, 100))
                photo = ImageTk.PhotoImage(img)
                label = tk.Label(preview_frame, image=photo, bg="#1e1e1e")
                label.image = photo  # Keep reference
                label.pack()
            except Exception as e:
                messagebox.showerror("Error", f"Could not load image: {str(e)}")
        else:
            # Show document icon and filename
            doc_icon = tk.Label(preview_frame, text="📄", bg="#1e1e1e", fg="white")
            doc_icon.pack(side="left")
            filename = os.path.basename(file_path)
            tk.Label(
                preview_frame, 
                text=filename, 
                bg="#1e1e1e", 
                fg="white"
            ).pack(side="left", padx=5)
        
        # Add remove button
        remove_btn = tk.Button(
            preview_frame,
            text="×",
            fg="red",
            bg="#1e1e1e",
            command=lambda f=file_path, p=preview_frame: self.remove_attachment(f, p)
        )
        remove_btn.pack(side="left", padx=5)

    def remove_attachment(self, file_path, preview_frame):
        self.current_attachments.remove(file_path)
        preview_frame.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()
