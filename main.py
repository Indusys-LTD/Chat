import requests
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading

class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ollama Chat")
        self.context = None
        self.available_models = []
        
        # Configure main window
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Create UI elements
        self.create_widgets()
        
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
            self.root.after(0, lambda: self.model_combobox.configure(
                values=self.available_models + ["custom"]
            ))
            if self.available_models:
                self.root.after(0, lambda: self.model_combobox.set(self.available_models[0]))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showwarning(
                "Warning",
                f"Could not fetch models: {str(e)}\nYou can manually enter model names"
            ))
        
    def create_widgets(self):
        # Model selection (updated combobox configuration)
        model_frame = ttk.Frame(self.root)
        model_frame.pack(pady=10, padx=10, fill="x")
        
        ttk.Label(model_frame, text="Model:").pack(side="left")
        self.model_var = tk.StringVar()
        self.model_combobox = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=["Loading models..."],  # Initial placeholder
            state="readonly"
        )
        self.model_combobox.pack(side="left", padx=5)
        
        # Chat history
        self.chat_history = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, state="disabled")
        self.chat_history.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Input area
        input_frame = ttk.Frame(self.root)
        input_frame.pack(pady=10, padx=10, fill="x")
        
        self.input_entry = ttk.Entry(input_frame)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.input_entry.bind("<Return>", lambda event: self.send_message())
        
        self.send_button = ttk.Button(input_frame, text="Send", command=self.send_message)
        self.send_button.pack(side="left")
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken")
        self.status_bar.pack(side="bottom", fill="x")
        
    def update_chat_history(self, sender, message):
        self.chat_history.configure(state="normal")
        self.chat_history.insert(tk.END, f"{sender}: {message}\n\n")
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
            
        self.input_entry.delete(0, tk.END)
        self.update_chat_history("You", user_input)
        self.send_button.config(state="disabled")
        self.status_var.set("Assistant is typing...")
        
        # Run API call in separate thread
        threading.Thread(target=self.process_response, args=(user_input,)).start()
        
    def process_response(self, user_input):
        try:
            response = self.ollama_chat(user_input)
            self.root.after(0, self.update_chat_history, "Assistant", response)
        except Exception as e:
            self.root.after(0, messagebox.showerror, "Error", str(e))
        finally:
            self.root.after(0, lambda: self.send_button.config(state="normal"))
            self.root.after(0, lambda: self.status_var.set("Ready"))

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()
