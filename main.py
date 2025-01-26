import os
import requests
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
from PIL import Image, ImageTk

class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Local LLM Chat")
        self.context = None
        self.available_models = []
        self.chat_history_data = []
        
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

        tk.Label(sidebar, text="History", bg="#252526", fg="white", font=("Arial", 12, "bold"), anchor="w").pack(fill="x", padx=10, pady=5)

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
            font=("Arial", 12), bg="#1e1e1e", fg="white", bd=0, padx=10, pady=5
        )
        self.chat_history.pack(pady=10, padx=10, fill="both", expand=True)

        # Input Area
        input_frame = tk.Frame(self.root, bg="#1e1e1e")
        input_frame.pack(pady=10, padx=10, fill="x")

        self.input_entry = ttk.Entry(input_frame)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.input_entry.bind("<Return>", lambda event: self.send_message())

        self.send_button = ttk.Button(input_frame, text="Send", command=self.send_message)
        self.send_button.pack(side="left", padx=5)

    def create_footer(self):
        footer = tk.Frame(self.root, bg="#252526", height=30)
        footer.pack(side="bottom", fill="x")
        self.footer_label = tk.Label(
            footer, text="Status: Ready", bg="#252526", fg="white",
            font=("Arial", 10), anchor="w"
        )
        self.footer_label.pack(side="left", padx=10)

    def update_chat_history(self, sender, message):
        self.chat_history.configure(state="normal")
        
        # Insert avatar
        if sender == "You":
            self.chat_history.image_create(tk.END, image=self.user_icon, padx=5)
            tag = 'user'
        else:
            self.chat_history.image_create(tk.END, image=self.bot_icon, padx=5)
            tag = 'assistant'
        
        # Insert message
        self.chat_history.insert(tk.END, "  " + message + "\n\n", tag)
        self.chat_history.configure(state="disabled")
        self.chat_history.see(tk.END)
        
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
        if not user_input:
            return
            
        # Save user message immediately
        self.chat_history_data.append({"sender": "You", "message": user_input})
        self.save_chat_to_file()
        
        self.input_entry.delete(0, tk.END)
        self.update_chat_history("You", user_input)
        
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
                self.update_chat_history(entry["sender"], entry["message"])
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

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()
