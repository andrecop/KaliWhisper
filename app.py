import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import logging
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
import warnings
warnings.filterwarnings("ignore")
import wave
import queue
import threading
import tempfile
import shutil
import pyaudio
import tqdm
import tqdm.auto
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from faster_whisper import WhisperModel
class ShadcnDropdown(ctk.CTkToplevel):
    def __init__(self, master, values, command, fg_color=None, hover_color=None, text_color=None, font=None, **kwargs):
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        
        self._values = values
        self._command = command
        self._fg_color = fg_color or "#18181b"
        self._hover_color = hover_color or "#27272a"
        self._text_color = text_color or "#fafafa"
        self._font = font or ("Segoe UI", 11)
        
        self.border_frame = ctk.CTkFrame(
            self, fg_color=self._fg_color, border_color="#27272a", border_width=1, corner_radius=8
        )
        self.border_frame.pack(fill=tk.BOTH, expand=True)
        
        self._rebuild_items()
        
        self.bind("<Button-1>", self._on_click_outside)
        self.bind("<Escape>", lambda e: self.close())
        
    def _rebuild_items(self):
        for widget in self.border_frame.winfo_children():
            widget.destroy()
            
        for val in self._values:
            btn = ctk.CTkButton(
                self.border_frame, text=val, anchor="w",
                fg_color="transparent", text_color=self._text_color,
                hover_color=self._hover_color, font=self._font,
                height=28, corner_radius=6,
                command=lambda v=val: self._on_select(v)
            )
            btn.pack(fill=tk.X, padx=4, pady=2)
            
    def _on_select(self, value):
        self._command(value)
        self.close()
        
    def _on_click_outside(self, event):
        x, y = event.x_root, event.y_root
        win_x = self.winfo_rootx()
        win_y = self.winfo_rooty()
        win_w = self.winfo_width()
        win_h = self.winfo_height()
        if not (win_x <= x <= win_x + win_w and win_y <= y <= win_y + win_h):
            self.close()
            
    def open(self, x, y):
        parent_width = self.master.winfo_width()
        import tkinter.font as tkfont
        if isinstance(self._font, tuple) and len(self._font) >= 2:
            font_obj = tkfont.Font(family=self._font[0], size=self._font[1])
        elif hasattr(self._font, "cget"):
            try:
                font_obj = tkfont.Font(family=self._font.cget("family"), size=self._font.cget("size"))
            except Exception:
                font_obj = tkfont.nametofont("TkDefaultFont")
        else:
            font_obj = tkfont.nametofont("TkDefaultFont")
            
        max_text_width = max([font_obj.measure(val) + 40 for val in self._values] + [parent_width])
        height = len(self._values) * 32 + 8
        self.geometry(f"{max_text_width}x{height}+{int(x)}+{int(y)}")
        self.deiconify()
        self.lift()
        self.focus_force()
        self.grab_set()
        
    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.withdraw()
        
    def configure(self, **kwargs):
        rebuild = False
        if "values" in kwargs:
            self._values = kwargs.pop("values")
            rebuild = True
        if "fg_color" in kwargs:
            self._fg_color = kwargs.pop("fg_color")
            self.border_frame.configure(fg_color=self._fg_color)
            rebuild = True
        if "hover_color" in kwargs:
            self._hover_color = kwargs.pop("hover_color")
            rebuild = True
        if "text_color" in kwargs:
            self._text_color = kwargs.pop("text_color")
            rebuild = True
        if "font" in kwargs:
            self._font = kwargs.pop("font")
            rebuild = True
            
        if rebuild:
            self._rebuild_items()
            
    def cget(self, attribute_name):
        if attribute_name == "values":
            return self._values
        elif attribute_name == "fg_color":
            return self._fg_color
        elif attribute_name == "hover_color":
            return self._hover_color
        elif attribute_name == "text_color":
            return self._text_color
        elif attribute_name == "font":
            return self._font
        return None

import customtkinter.windows.widgets.ctk_optionmenu as optmenu
optmenu.DropdownMenu = ShadcnDropdown

import customtkinter.windows.widgets.ctk_combobox as combobox
combobox.DropdownMenu = ShadcnDropdown

ctk.set_appearance_mode("dark")

def _clean_string(s):
    try:
        return s.encode("latin1").decode("utf-8")
    except Exception:
        return s

class TkinterTqdm(tqdm.tqdm):
    callback = None
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if TkinterTqdm.callback:
            desc = kwargs.get("desc", "Download")
            TkinterTqdm.callback("init", self.total, desc)
            
    def update(self, n=1):
        res = super().update(n)
        if TkinterTqdm.callback:
            TkinterTqdm.callback("update", n, None)
        return res
        
    def close(self):
        super().close()
        if TkinterTqdm.callback:
            TkinterTqdm.callback("close", None, None)

class WhisperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KaliWhisper")
        self.root.geometry("650x600")
        self.root.minsize(550, 480)
        self.root.configure(fg_color="#09090b")
        
        self.model = None
        self.model_name = "base"
        self.is_recording = False
        self.temp_files = set()
        
        self.transcription_queue = queue.Queue()
        self.pa = pyaudio.PyAudio()
        self.stream = None
        
        self.current_file_total = 0
        self.current_file_progress = 0
        self.dest_dir = os.path.expanduser("~")
        self.transcribe_lang = "it"
        
        self._setup_ui()
        self._update_action_buttons()
        
        if self._is_model_downloaded(self.model_name):
            self._load_model_async(self.model_name)
        else:
            self._set_status(f"Modello {self.model_name} non scaricato. Clicca su '⬇ Scarica'.")
            
        threading.Thread(target=self._transcription_worker, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _set_btn_state(self, btn, state, btn_type="secondary"):
        if state == "normal":
            btn.configure(state="normal")
            if btn_type == "primary":
                btn.configure(fg_color="#ffffff", text_color="#09090b", hover_color="#e4e4e7")
            elif btn_type == "danger":
                btn.configure(fg_color="#ef4444", text_color="#ffffff", hover_color="#f87171")
            elif btn_type == "success":
                btn.configure(fg_color="#22c55e", text_color="#ffffff", hover_color="#4ade80")
            elif btn_type == "info":
                btn.configure(fg_color="#3b82f6", text_color="#ffffff", hover_color="#60a5fa")
            else:
                btn.configure(fg_color="#27272a", text_color="#fafafa", hover_color="#3f3f46")
        else:
            btn.configure(state="disabled")
            if btn_type == "primary":
                btn.configure(fg_color="#27272a", text_color="#71717a")
            elif btn_type == "danger":
                btn.configure(fg_color="#7f1d1d", text_color="#991b1b")
            elif btn_type == "success":
                btn.configure(fg_color="#14532d", text_color="#166534")
            elif btn_type == "info":
                btn.configure(fg_color="#1e3a8a", text_color="#1e40af")
            else:
                btn.configure(fg_color="#18181b", text_color="#52525b")

    def _setup_ui(self):
        main_frame = ctk.CTkFrame(self.root, fg_color="#09090b")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.model_frame = ctk.CTkFrame(main_frame, fg_color="#09090b")
        self.model_frame.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkLabel(self.model_frame, text="Seleziona Modello Whisper:", font=("Segoe UI", 11, "bold"), text_color="#fafafa").pack(side=tk.LEFT, padx=(0, 10))
        
        model_border = ctk.CTkFrame(self.model_frame, fg_color="#27272a", corner_radius=8, height=30, width=130)
        model_border.pack(side=tk.LEFT, padx=(0, 8))
        model_border.pack_propagate(False)
        
        self.model_combo = ctk.CTkOptionMenu(
            model_border, values=["tiny", "base", "small", "medium"],
            command=self._on_model_selected,
            fg_color="#18181b", button_color="#18181b", button_hover_color="#27272a",
            text_color="#fafafa", font=("Segoe UI", 11),
            dropdown_fg_color="#18181b", dropdown_text_color="#fafafa",
            dropdown_hover_color="#27272a", dropdown_font=("Segoe UI", 11),
            corner_radius=7
        )
        self.model_combo.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.model_combo.set(self.model_name)
        
        self.download_btn = ctk.CTkButton(self.model_frame, text="⬇ Scarica", command=self._download_selected_model, font=("Segoe UI", 10, "bold"), width=90)
        self.delete_btn = ctk.CTkButton(self.model_frame, text="🗑 Elimina", command=self._delete_selected_model, font=("Segoe UI", 10, "bold"), width=90)
        self.update_btn = ctk.CTkButton(self.model_frame, text="🔄 Aggiorna", command=self._update_selected_model, font=("Segoe UI", 10, "bold"), width=90)
        
        self.lang_btn = ctk.CTkButton(self.model_frame, text="🇮🇹", command=self._toggle_language, font=("Segoe UI", 12), width=40)
        self.lang_btn.pack(side=tk.RIGHT, padx=2)
        self._set_btn_state(self.lang_btn, "normal", "secondary")

        self.dest_btn = ctk.CTkButton(self.model_frame, text="📂 Destinazione", command=self._choose_destination, font=("Segoe UI", 10, "bold"), width=100)
        self.dest_btn.pack(side=tk.RIGHT, padx=2)
        self._set_btn_state(self.dest_btn, "normal", "secondary")
        
        device_frame = ctk.CTkFrame(main_frame, fg_color="#09090b")
        device_frame.pack(fill=tk.X, pady=(0, 15))
        
        ctk.CTkLabel(device_frame, text="Ingresso Audio:", font=("Segoe UI", 11, "bold"), text_color="#fafafa").pack(side=tk.LEFT, padx=(0, 8))
        
        device_border = ctk.CTkFrame(device_frame, fg_color="#27272a", corner_radius=8, height=30)
        device_border.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        device_border.pack_propagate(False)
        self.devices = []
        device_names = []
        default_device_name = None
        try:
            default_info = self.pa.get_default_input_device_info()
            default_device_name = _clean_string(default_info.get('name', ''))
        except Exception:
            pass

        try:
            all_devices_info = []
            for h in range(self.pa.get_host_api_count()):
                try:
                    info = self.pa.get_host_api_info_by_index(h)
                    numdevices = info.get('deviceCount', 0)
                    for i in range(0, numdevices):
                        device_info = self.pa.get_device_info_by_host_api_device_index(h, i)
                        if device_info.get('maxInputChannels', 0) > 0:
                            dev_info_copy = dict(device_info)
                            dev_info_copy['name'] = _clean_string(device_info.get('name', ''))
                            all_devices_info.append(dev_info_copy)
                except Exception:
                    pass

            mme_info = self.pa.get_host_api_info_by_index(0)
            mme_devices_count = mme_info.get('deviceCount', 0)
            for i in range(0, mme_devices_count):
                device_info = self.pa.get_device_info_by_host_api_device_index(0, i)
                if device_info.get('maxInputChannels', 0) > 0:
                    name = _clean_string(device_info.get('name', ''))
                    if name in ["Microsoft Sound Mapper - Input", "Driver primario di acquisizione suoni"]:
                        continue
                    
                    full_name = name
                    best_global_idx = device_info.get('index')
                    
                    for other_info in all_devices_info:
                        other_name = other_info.get('name')
                        if other_name.startswith(name) and len(other_name) > len(full_name):
                            full_name = other_name
                            best_global_idx = other_info.get('index')
                            
                    if full_name not in device_names:
                        self.devices.append((best_global_idx, full_name))
                        device_names.append(full_name)
        except Exception:
            pass
        if not device_names:
            device_names = ["Predefinito"]
            self.devices = [(-1, "Predefinito")]
            
        self.device_combo = ctk.CTkOptionMenu(
            device_border, values=device_names,
            fg_color="#18181b", button_color="#18181b", button_hover_color="#27272a",
            text_color="#fafafa", font=("Segoe UI", 11),
            dropdown_fg_color="#18181b", dropdown_text_color="#fafafa",
            dropdown_hover_color="#27272a", dropdown_font=("Segoe UI", 11),
            corner_radius=7
        )
        self.device_combo.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        selected_device = device_names[0]
        if default_device_name:
            for name in device_names:
                if name == default_device_name or name.startswith(default_device_name) or default_device_name.startswith(name):
                    selected_device = name
                    break
        self.device_combo.set(selected_device)

        status_border = ctk.CTkFrame(device_frame, fg_color="#27272a", corner_radius=8, height=30, width=150)
        status_border.pack(side=tk.RIGHT, padx=(10, 0))
        status_border.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            status_border, text="Inizializzazione...", font=("Segoe UI", 11, "bold"),
            text_color="#a1a1aa", fg_color="#18181b", corner_radius=7
        )
        self.status_label.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        self.progress_frame = ctk.CTkFrame(main_frame, fg_color="#09090b")
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, progress_color="#ffffff", fg_color="#27272a")
        self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_bar.set(0.0)
        
        text_frame = ctk.CTkFrame(main_frame, fg_color="#18181b", border_color="#27272a", border_width=1)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        ctk.CTkLabel(text_frame, text="Trascrizione", font=("Segoe UI", 10, "bold"), text_color="#fafafa").pack(anchor=tk.W, padx=15, pady=(10, 4))
        
        self.text_area = ctk.CTkTextbox(
            text_frame, font=("Segoe UI", 12),
            fg_color="#18181b", text_color="#fafafa",
            border_color="#27272a", border_width=0,
            activate_scrollbars=True
        )
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 10))
        self.text_area.bind("<KeyRelease>", lambda e: self._update_save_button_state())
        
        button_frame = ctk.CTkFrame(main_frame, fg_color="#09090b")
        button_frame.pack(fill=tk.X)
        
        self.start_btn = ctk.CTkButton(button_frame, text="▶ Avvia Trascrizione", command=self._toggle_recording, font=("Segoe UI", 11, "bold"), height=38)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.save_btn = ctk.CTkButton(button_frame, text="💾 Salva Trascrizione", command=self._save_transcription, font=("Segoe UI", 11, "bold"), height=38)
        self.save_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        self._set_btn_state(self.start_btn, "disabled", "success")
        self._set_btn_state(self.save_btn, "disabled", "info")

    def _set_status(self, text):
        self.status_label.configure(text=text)

    def _is_model_downloaded(self, model_name):
        model_dir = os.path.join(os.path.dirname(__file__), "models")
        repo_id = f"Systran/faster-whisper-{model_name}"
        folder_name = f"models--{repo_id.replace('/', '--')}"
        path = os.path.join(model_dir, folder_name, "snapshots")
        if os.path.exists(path):
            try:
                for sub in os.listdir(path):
                    sub_path = os.path.join(path, sub)
                    if os.path.isdir(sub_path):
                        if os.path.isfile(os.path.join(sub_path, "model.bin")):
                            return True
            except Exception:
                pass
        return False

    def _update_action_buttons(self):
        model_name = self.model_combo.get()
        downloaded = self._is_model_downloaded(model_name)
        
        self.update_btn.pack_forget()
        
        if downloaded:
            self.download_btn.pack_forget()
            self.delete_btn.pack(side=tk.LEFT, padx=2)
            self._set_btn_state(self.delete_btn, "normal", "danger")
            if self.model is not None and self.model_name == model_name:
                self._set_btn_state(self.start_btn, "normal", "success")
            else:
                self._set_btn_state(self.start_btn, "disabled", "success")
            self._check_for_updates_async(model_name)
        else:
            self.delete_btn.pack_forget()
            self.download_btn.pack(side=tk.LEFT, padx=2)
            self._set_btn_state(self.download_btn, "normal", "secondary")
            self._set_btn_state(self.start_btn, "disabled", "success")

    def _check_for_updates_async(self, model_name):
        def check_task():
            model_dir = os.path.join(os.path.dirname(__file__), "models")
            repo_id = f"Systran/faster-whisper-{model_name}"
            folder_name = f"models--{repo_id.replace('/', '--')}"
            snapshots_path = os.path.join(model_dir, folder_name, "snapshots")
            if not os.path.exists(snapshots_path):
                return
            try:
                from huggingface_hub import model_info
                info = model_info(repo_id, timeout=3)
                latest_sha = info.sha
                if latest_sha:
                    local_sha_path = os.path.join(snapshots_path, latest_sha)
                    if not os.path.exists(local_sha_path):
                        self.root.after(0, lambda: self._show_update_button_if_selected(model_name))
            except Exception:
                pass
        threading.Thread(target=check_task, daemon=True).start()

    def _show_update_button_if_selected(self, checked_model):
        if self.model_combo.get() == checked_model:
            self.update_btn.pack(side=tk.LEFT, padx=2)
            self._set_btn_state(self.update_btn, "normal", "secondary")

    def _on_model_selected(self, selected_value):
        self._update_action_buttons()
        
        if self._is_model_downloaded(selected_value):
            if self.model_name != selected_value or self.model is None:
                self._load_model_async(selected_value)
            else:
                self._set_status("Modello pronto ed in memoria.")
        else:
            if self.is_recording:
                self._stop_recording_action()
            if self.model is not None:
                del self.model
                import gc
                gc.collect()
                self.model = None
            self.model_name = selected_value
            self._set_status(f"Modello {selected_value} non scaricato. Clicca su '⬇ Scarica'.")

    def _load_model_async(self, model_name):
        self.model_combo.configure(state="disabled")
        self.device_combo.configure(state="disabled")
        self._set_btn_state(self.start_btn, "disabled", "success")
        self._set_btn_state(self.delete_btn, "disabled", "danger")
        self._set_btn_state(self.update_btn, "disabled", "secondary")
        self._set_status(f"Caricamento modello {model_name}...")
        
        def load_task():
            try:
                if self.model is not None:
                    del self.model
                    import gc
                    gc.collect()
                    self.model = None
                
                model_dir = os.path.join(os.path.dirname(__file__), "models")
                self.model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=model_dir)
                self.model_name = model_name
                self.root.after(0, self._on_model_loaded)
            except Exception as e:
                self.root.after(0, self._on_model_load_failed, e)
                
        threading.Thread(target=load_task, daemon=True).start()

    def _on_model_loaded(self):
        self.model_combo.configure(state="normal")
        self.device_combo.configure(state="normal")
        self._set_btn_state(self.start_btn, "normal", "success")
        self._update_action_buttons()
        self._update_save_button_state()
        self._set_status("In attesa...")

    def _on_model_load_failed(self, error):
        self.model_combo.configure(state="normal")
        self.device_combo.configure(state="normal")
        self._set_btn_state(self.start_btn, "disabled", "success")
        self._update_action_buttons()
        self._update_save_button_state()
        self._set_status(f"Errore caricamento modello: {error}")
        messagebox.showerror("Errore", f"Impossibile caricare il modello Whisper: {error}")

    def _download_selected_model(self):
        model_name = self.model_combo.get()
        self.model_combo.configure(state="disabled")
        self.device_combo.configure(state="disabled")
        self._set_btn_state(self.download_btn, "disabled", "secondary")
        self._set_status(f"Avvio download modello {model_name}...")
        self._download_model_thread(model_name)

    def _download_model_thread(self, model_name):
        self.progress_frame.pack(fill=tk.X, pady=(0, 15), after=self.model_frame)
        
        def download_task():
            model_dir = os.path.join(os.path.dirname(__file__), "models")
            original_tqdm = tqdm.tqdm
            original_auto_tqdm = tqdm.auto.tqdm
            tqdm.tqdm = TkinterTqdm
            tqdm.auto.tqdm = TkinterTqdm
            TkinterTqdm.callback = self._tqdm_callback
            try:
                from faster_whisper.utils import download_model
                download_model(model_name, cache_dir=model_dir)
                self.root.after(0, self._on_download_success, model_name)
            except Exception as e:
                self.root.after(0, self._on_download_failed, model_name, e)
            finally:
                tqdm.tqdm = original_tqdm
                tqdm.auto.tqdm = original_auto_tqdm
                TkinterTqdm.callback = None
                self.root.after(0, self.progress_frame.pack_forget)
                
        threading.Thread(target=download_task, daemon=True).start()

    def _tqdm_callback(self, action, value, desc):
        if action == "init":
            self.current_file_total = value or 0
            self.current_file_progress = 0
            if desc:
                self.root.after(0, self._set_status, f"Download: {desc}")
            if self.current_file_total > 0:
                self.root.after(0, lambda: self.progress_bar.configure(mode="determinate"))
                self.root.after(0, lambda: self.progress_bar.set(0.0))
            else:
                self.root.after(0, lambda: self.progress_bar.configure(mode="indeterminate"))
                self.root.after(0, self.progress_bar.start)
        elif action == "update":
            if self.current_file_total > 0:
                self.current_file_progress += value
                fraction = min(1.0, float(self.current_file_progress) / self.current_file_total)
                self.root.after(0, lambda: self.progress_bar.set(fraction))
        elif action == "close":
            self.root.after(0, self.progress_bar.stop)
            self.root.after(0, lambda: self.progress_bar.set(0.0))

    def _on_download_success(self, model_name):
        self.model_combo.configure(state="normal")
        self.device_combo.configure(state="normal")
        self._update_action_buttons()
        self._load_model_async(model_name)

    def _on_download_failed(self, model_name, error):
        self.model_combo.configure(state="normal")
        self.device_combo.configure(state="normal")
        self._update_action_buttons()
        self._set_status(f"Download fallito: {error}")
        messagebox.showerror("Errore", f"Impossibile scaricare il modello: {error}")

    def _delete_selected_model(self):
        model_name = self.model_combo.get()
        if not messagebox.askyesno("Conferma", f"Sei sicuro di voler eliminare il modello {model_name} dal disco?"):
            return
            
        if self.is_recording:
            self._stop_recording_action()
            
        if self.model_name == model_name and self.model is not None:
            del self.model
            import gc
            gc.collect()
            self.model = None
            self._set_btn_state(self.start_btn, "disabled", "success")
            
        model_dir = os.path.join(os.path.dirname(__file__), "models")
        repo_id = f"Systran/faster-whisper-{model_name}"
        folder_name = f"models--{repo_id.replace('/', '--')}"
        path = os.path.join(model_dir, folder_name)
        
        try:
            if os.path.exists(path):
                shutil.rmtree(path)
            self._set_status(f"Modello {model_name} eliminato.")
            self._update_action_buttons()
        except PermissionError:
            self._set_status(f"Modello {model_name} bloccato in memoria.")
            messagebox.showwarning(
                "Eliminazione Parziale",
                "Il modello è attualmente caricato e bloccato in memoria dal processo.\n"
                "Per eliminarlo completamente, riavvia l'applicazione e clicca su Elimina senza caricarlo."
            )
            self._update_action_buttons()
        except Exception as e:
            self._set_status(f"Errore eliminazione: {e}")
            messagebox.showerror("Errore", f"Impossibile eliminare il modello: {e}")

    def _update_selected_model(self):
        model_name = self.model_combo.get()
        if self.is_recording:
            self._stop_recording_action()
            
        self.model_combo.configure(state="disabled")
        self.device_combo.configure(state="disabled")
        self._set_btn_state(self.delete_btn, "disabled", "danger")
        self._set_btn_state(self.update_btn, "disabled", "secondary")
        self._set_status(f"Verifica aggiornamenti modello {model_name}...")
        self._download_model_thread(model_name)

    def _update_save_button_state(self):
        text_content = self.text_area.get("1.0", "end").strip()
        if not self.is_recording and text_content:
            self._set_btn_state(self.save_btn, "normal", "info")
        else:
            self._set_btn_state(self.save_btn, "disabled", "info")

    def _toggle_recording(self):
        if not self.is_recording:
            if self.model is None:
                messagebox.showwarning("Attenzione", "Il modello non è ancora pronto.")
                return
                
            self.is_recording = True
            self.start_btn.configure(text="■ Ferma Trascrizione")
            self._set_btn_state(self.start_btn, "normal", "danger")
            self._set_btn_state(self.save_btn, "disabled", "info")
            self.model_combo.configure(state="disabled")
            self.device_combo.configure(state="disabled")
            self._set_btn_state(self.delete_btn, "disabled", "danger")
            self._set_btn_state(self.update_btn, "disabled", "secondary")
            self.text_area.configure(state="disabled")
            self._set_status("Registrazione in corso...")
            
            threading.Thread(target=self._recording_worker, daemon=True).start()
        else:
            self.start_btn.configure(text="▶ Avvia Trascrizione")
            self._set_btn_state(self.start_btn, "disabled", "success")
            self._stop_recording_action()

    def _on_recording_failed(self):
        self.is_recording = False
        self.start_btn.configure(text="▶ Avvia Trascrizione")
        self._set_btn_state(self.start_btn, "normal", "success")
        self.model_combo.configure(state="normal")
        self.device_combo.configure(state="normal")
        self.text_area.configure(state="normal")
        self._update_action_buttons()
        self._update_save_button_state()
        messagebox.showerror("Errore", "Impossibile avviare la registrazione audio. Verifica il microfono.")

    def _stop_recording_action(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self._set_status("Elaborazione degli ultimi frammenti...")
        
        def wait_and_save():
            self.transcription_queue.join()
            self.root.after(0, self._on_transcription_finished)
            
        threading.Thread(target=wait_and_save, daemon=True).start()

    def _on_transcription_finished(self):
        self._set_btn_state(self.start_btn, "normal", "success")
        self.model_combo.configure(state="normal")
        self.device_combo.configure(state="normal")
        self.text_area.configure(state="normal")
        self._update_action_buttons()
        self._update_save_button_state()
        self._set_status("In attesa...")

    def _choose_destination(self):
        from tkinter import filedialog
        selected_dir = filedialog.askdirectory(initialdir=self.dest_dir, title="Seleziona cartella di destinazione")
        if selected_dir:
            self.dest_dir = selected_dir
            self._set_status(f"Destinazione salvataggio impostata su: {self.dest_dir}")

    def _save_transcription(self):
        text_content = self.text_area.get("1.0", "end").strip()
        if not text_content:
            return
            
        filename = f"trascrizione_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(self.dest_dir, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text_content)
            self._set_status(f"Salvataggio completato: {filename}")
            messagebox.showinfo("Salvataggio completato", f"La trascrizione è stata salvata in:\n{filepath}")
        except Exception as e:
            self._set_status(f"Errore di salvataggio: {e}")
            messagebox.showerror("Errore", f"Impossibile salvare il file: {e}")
            
        self._update_save_button_state()

    def _toggle_language(self):
        if self.transcribe_lang == "it":
            self.transcribe_lang = "en"
            self.lang_btn.configure(text="🇬🇧")
            self._set_status("Lingua: Inglese")
        else:
            self.transcribe_lang = "it"
            self.lang_btn.configure(text="🇮🇹")
            self._set_status("Lingua: Italiano")

    def _transcription_worker(self):
        while True:
            item = self.transcription_queue.get()
            if item is None:
                break
            wav_path = item
            try:
                if self.model is not None:
                    segments, info = self.model.transcribe(wav_path, beam_size=5, language=self.transcribe_lang)
                    text = "".join([segment.text for segment in segments])
                    if text.strip():
                        self.root.after(0, self._append_text, text)
            except Exception as e:
                self.root.after(0, self._set_status, f"Errore trascrizione: {e}")
            finally:
                try:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
                        self.temp_files.discard(wav_path)
                except Exception:
                    pass
                self.transcription_queue.task_done()

    def _append_text(self, text):
        self.text_area.configure(state="normal")
        self.text_area.insert("end", text + " ")
        self.text_area.see("end")
        self.text_area.configure(state="disabled")
        self._update_save_button_state()

    def _on_closing(self):
        self.is_recording = False
        self.transcription_queue.put(None)
        try:
            if hasattr(self, 'stream') and self.stream.is_active():
                self.stream.stop_stream()
                self.stream.close()
        except Exception:
            pass
        self.pa.terminate()
        
        for wav_path in list(self.temp_files):
            try:
                if os.path.exists(wav_path):
                    os.remove(wav_path)
            except Exception:
                pass
                
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = WhisperApp(root)
    root.mainloop()
