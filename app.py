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
from vosk import Model, KaldiRecognizer
import json
import numpy as np
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

class ConfirmDialog(ctk.CTkToplevel):
    def __init__(self, master, title, message, on_confirm):
        super().__init__(master)
        self.title(title)
        self.geometry("320x160")
        self.resizable(False, False)
        self.configure(fg_color="#09090b")
        
        # Center the window relative to parent
        self.update_idletasks()
        parent_x = master.winfo_rootx()
        parent_y = master.winfo_rooty()
        parent_w = master.winfo_width()
        parent_h = master.winfo_height()
        x = parent_x + (parent_w - 320) // 2
        y = parent_y + (parent_h - 160) // 2
        self.geometry(f"320x160+{x}+{y}")
        
        self.overrideredirect(True)
        self.border_frame = ctk.CTkFrame(
            self, fg_color="#09090b", border_color="#27272a", border_width=1, corner_radius=8
        )
        self.border_frame.pack(fill=tk.BOTH, expand=True)
        
        self.label = ctk.CTkLabel(self.border_frame, text=message, font=("Segoe UI", 12), text_color="#fafafa", wraplength=280)
        self.label.pack(expand=True, fill=tk.BOTH, padx=20, pady=(25, 10))
        
        btn_frame = ctk.CTkFrame(self.border_frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=(0, 20), padx=20)
        
        self.yes_btn = ctk.CTkButton(
            btn_frame, text="Sì", width=120, height=32,
            fg_color="#ef4444", hover_color="#dc2626", text_color="#ffffff",
            font=("Segoe UI", 11, "bold"), corner_radius=6,
            command=lambda: [on_confirm(), self.destroy()]
        )
        self.yes_btn.pack(side=tk.LEFT, expand=True, padx=5)
        
        self.no_btn = ctk.CTkButton(
            btn_frame, text="No", width=120, height=32,
            fg_color="#27272a", hover_color="#3f3f46", text_color="#fafafa",
            font=("Segoe UI", 11), corner_radius=6,
            command=self.destroy
        )
        self.no_btn.pack(side=tk.RIGHT, expand=True, padx=5)
        
        self.transient(master)
        self.grab_set()
        self.focus_force()

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
        self.models_cache = {}
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.transcription_queue = queue.Queue()
        self.temp_files = set()
        self.all_recorded_audio = []
        self.active_audio_frames = []
        self.frames_since_last_transcribe = 0
        self.speech_detected = False
        self.window_id = 0
        self.transcribe_seq = 0
        self.latest_seq_processed = 0
        self.pa = pyaudio.PyAudio()
        self.stream = None
        self.rec = None
        
        self.dest_dir = os.path.expanduser("~")
        self.transcribe_lang = "it"
        
        from PIL import Image
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        import io

        def load_svg_as_image(svg_path, size):
            drawing = svg2rlg(svg_path)
            factor_x = size[0] / drawing.width
            factor_y = size[1] / drawing.height
            drawing.scale(factor_x, factor_y)
            drawing.width, drawing.height = size[0], size[1]
            
            png_data = io.BytesIO()
            renderPM.drawToFile(drawing, png_data, fmt="PNG")
            png_data.seek(0)
            return Image.open(png_data)

        flags_dir = os.path.join(os.path.dirname(__file__), "assets", "flags")
        self.img_it = ctk.CTkImage(light_image=load_svg_as_image(os.path.join(flags_dir, "IT.svg"), (24, 16)), size=(24, 16))
        self.img_en = ctk.CTkImage(light_image=load_svg_as_image(os.path.join(flags_dir, "GB.svg"), (24, 16)), size=(24, 16))
        
        self._setup_ui()
        self._load_model_async("Vosk Live", self.transcribe_lang)
            
        self.app_running = True
        self.noise_floor = 300.0
        threading.Thread(target=self._audio_monitor_worker, daemon=True).start()
        threading.Thread(target=self._transcription_worker, daemon=True).start()
        threading.Thread(target=self._whisper_transcription_worker, daemon=True).start()
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
        
        ctk.CTkLabel(self.model_frame, text="Motore di Trascrizione:", font=("Segoe UI", 11, "bold"), text_color="#fafafa").pack(side=tk.LEFT, padx=(0, 10))
        
        model_border = ctk.CTkFrame(self.model_frame, fg_color="#27272a", corner_radius=8, height=30, width=130)
        model_border.pack(side=tk.LEFT, padx=(0, 8))
        model_border.pack_propagate(False)
        
        self.model_combo = ctk.CTkOptionMenu(
            model_border, values=["Vosk Live", "Whisper tiny", "Whisper base", "Whisper small", "Whisper medium"],
            command=self._on_model_selected,
            fg_color="#18181b", button_color="#18181b", button_hover_color="#27272a",
            text_color="#fafafa", font=("Segoe UI", 11),
            dropdown_fg_color="#18181b", dropdown_text_color="#fafafa",
            dropdown_hover_color="#27272a", dropdown_font=("Segoe UI", 11),
            corner_radius=7
        )
        self.model_combo.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.model_combo.set("Vosk Live")
        
        self.download_btn = ctk.CTkButton(self.model_frame, text="⬇ Scarica", command=None, font=("Segoe UI", 10, "bold"), width=90)
        self.delete_btn = ctk.CTkButton(self.model_frame, text="🗑 Elimina", command=None, font=("Segoe UI", 10, "bold"), width=90)
        self.update_btn = ctk.CTkButton(self.model_frame, text="🔄 Aggiorna", command=None, font=("Segoe UI", 10, "bold"), width=90)
        
        self.lang_btn = ctk.CTkButton(self.model_frame, text="", image=self.img_it, command=self._toggle_language, width=46)
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
            for i in range(self.pa.get_device_count()):
                try:
                    device_info = self.pa.get_device_info_by_index(i)
                    if device_info.get('maxInputChannels', 0) > 0:
                        name = _clean_string(device_info.get('name', ''))
                        if name not in device_names:
                            try:
                                test_stream = self.pa.open(
                                    format=pyaudio.paInt16,
                                    channels=int(device_info.get('maxInputChannels', 1)),
                                    rate=int(device_info.get('defaultSampleRate', 16000)),
                                    input=True,
                                    input_device_index=i,
                                    frames_per_buffer=256
                                )
                                test_stream.close()
                            except Exception:
                                continue
                            self.devices.append((i, name))
                            device_names.append(name)
                except Exception:
                    pass
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
        
        self.visualizer = tk.Canvas(button_frame, width=38, height=38, bg="#09090b", highlightthickness=0)
        self.visualizer.pack(side=tk.LEFT, padx=(0, 5))
        
        self.start_btn = ctk.CTkButton(button_frame, text="▶ Avvia Trascrizione", command=self._toggle_recording, font=("Segoe UI", 11, "bold"), height=38)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        save_container = ctk.CTkFrame(button_frame, fg_color="transparent")
        save_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        save_container.columnconfigure(0, weight=2)
        save_container.columnconfigure(1, weight=1)
        
        self.save_btn = ctk.CTkButton(save_container, text="💾 Salva Trascrizione", command=self._save_transcription, font=("Segoe UI", 11, "bold"), height=38)
        self.save_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        
        self.save_audio_btn = ctk.CTkButton(save_container, text="🎙️ Salva Audio", command=self._save_audio, font=("Segoe UI", 11, "bold"), height=38)
        self.save_audio_btn.grid(row=0, column=1, sticky="ew", padx=(2, 0))
        
        self.reset_btn = ctk.CTkButton(button_frame, text="🗑", command=self._reset_transcription, font=("Segoe UI", 13), width=38, height=38, fg_color="#ef4444", hover_color="#dc2626", text_color="#ffffff")
        self.reset_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        self._set_btn_state(self.start_btn, "disabled", "success")
        self._set_btn_state(self.save_btn, "disabled", "info")
        self._set_btn_state(self.save_audio_btn, "disabled", "info")

    def _set_status(self, text):
        self.status_scroll_id = getattr(self, "status_scroll_id", 0) + 1
        scroll_id = self.status_scroll_id
        max_len = 18
        if len(text) <= max_len:
            self.status_label.configure(text=text)
            return

        def animate(start_idx, direction, pause_ticks):
            if getattr(self, "status_scroll_id", 0) != scroll_id:
                return
            self.status_label.configure(text=text[start_idx:start_idx+max_len])
            if start_idx == 0 and direction < 0:
                if pause_ticks < 15:
                    self.root.after(100, lambda: animate(0, -1, pause_ticks + 1))
                else:
                    self.root.after(250, lambda: animate(1, 1, 0))
                return
            max_start = len(text) - max_len
            if start_idx == max_start and direction > 0:
                if pause_ticks < 15:
                    self.root.after(100, lambda: animate(max_start, 1, pause_ticks + 1))
                else:
                    self.root.after(250, lambda: animate(max_start, -1, 0))
                return
            if direction > 0:
                self.root.after(250, lambda: animate(start_idx + 1, 1, 0))
            else:
                self.root.after(250, lambda: animate(0, -1, 0))
        animate(0, -1, 0)

    def _update_action_buttons(self):
        pass

    def _check_for_updates_async(self, model_name):
        pass

    def _show_update_button_if_selected(self, checked_model):
        pass

    def _on_model_selected(self, selected_value):
        self._load_model_async(selected_value, self.transcribe_lang)

    def _load_model_async(self, engine_name, lang):
        self.model_combo.configure(state="disabled")
        self.device_combo.configure(state="disabled")
        self._set_btn_state(self.start_btn, "disabled", "success")
        self._set_status(f"Caricamento {engine_name} ({lang})...")
        
        def load_task():
            try:
                cache_key = f"{engine_name}_{lang}"
                if cache_key not in self.models_cache:
                    if engine_name.startswith("Whisper "):
                        model_size = engine_name.split(" ", 1)[1]
                        from faster_whisper import WhisperModel
                        model_dir = os.path.join(os.path.dirname(__file__), "models")
                        self.models_cache[cache_key] = WhisperModel(model_size, device="cpu", compute_type="int8", download_root=model_dir)
                    else:
                        self.models_cache[cache_key] = Model(lang="en-us" if lang == "en" else "it")
                self.model = self.models_cache[cache_key]
                self.root.after(0, self._on_model_loaded)
            except Exception as e:
                self.root.after(0, self._on_model_load_failed, e)
                
        threading.Thread(target=load_task, daemon=True).start()

    def _on_model_loaded(self):
        self.model_combo.configure(state="normal")
        self.device_combo.configure(state="normal")
        self._set_btn_state(self.start_btn, "normal", "success")
        self._update_save_button_state()
        self._set_status("In attesa...")

    def _on_model_load_failed(self, error):
        self.model_combo.configure(state="normal")
        self.device_combo.configure(state="normal")
        self._set_btn_state(self.start_btn, "disabled", "success")
        self._update_save_button_state()
        self._set_status(f"Errore caricamento: {error}")
        messagebox.showerror("Errore", f"Impossibile caricare il modello: {error}")

    def _update_save_button_state(self):
        text_content = self.text_area.get("1.0", "end").strip()
        if not self.is_recording and text_content:
            self._set_btn_state(self.save_btn, "normal", "info")
        else:
            self._set_btn_state(self.save_btn, "disabled", "info")
        if not self.is_recording and getattr(self, "all_recorded_audio", None):
            self._set_btn_state(self.save_audio_btn, "normal", "info")
        else:
            self._set_btn_state(self.save_audio_btn, "disabled", "info")

    def _toggle_recording(self):
        if not self.is_recording:
            if self.model is None:
                messagebox.showwarning("Attenzione", "Il modello non è ancora pronto.")
                return
            self.is_recording = True
            self.start_btn.configure(text="■ Ferma Trascrizione")
            self._set_btn_state(self.start_btn, "normal", "danger")
            self._set_btn_state(self.save_btn, "disabled", "info")
            self._set_btn_state(self.save_audio_btn, "disabled", "info")
            self.all_recorded_audio = []
            self.model_combo.configure(state="disabled")
            self.device_combo.configure(state="disabled")
            
            self.text_area.configure(state="normal")
            existing_text = self.text_area.get("1.0", "end").strip()
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            if existing_text:
                self.text_area.insert("end", f"\n\n------- continua {now_str} -------\n\n")
            else:
                self.text_area.insert("end", f"------- {now_str} -------\n\n")
            self.text_area.see("end")
            
            self.text_area.mark_set("active_start", "insert")
            self.text_area.mark_gravity("active_start", "left")
            self.text_area.configure(state="disabled")
            
            self._set_status("Registrazione in corso...")
            if self.model_combo.get().startswith("Whisper "):
                self.active_audio_frames = []
                self.frames_since_last_transcribe = 0
                self.speech_detected = False
                self.window_id = 0
                self.transcribe_seq = 0
                self.latest_seq_processed = 0
                while not self.transcription_queue.empty():
                    try:
                        self.transcription_queue.get_nowait()
                        self.transcription_queue.task_done()
                    except Exception:
                        break
            else:
                self.rec = KaldiRecognizer(self.model, 16000)
                while not self.audio_queue.empty():
                    try:
                        self.audio_queue.get_nowait()
                        self.audio_queue.task_done()
                    except Exception:
                        break
        else:
            self.start_btn.configure(text="▶ Avvia Trascrizione")
            self._set_btn_state(self.start_btn, "disabled", "success")
            self._stop_recording_action()

    def _audio_monitor_worker(self):
        current_device = None
        stream = None
        native_channels = 1
        native_rate = 16000
        format_type = pyaudio.paInt16
        
        while getattr(self, "app_running", True):
            selected = self.device_combo.get()
            device_idx = -1
            for idx, name in self.devices:
                if name == selected:
                    device_idx = idx
                    break
            if device_idx != current_device:
                if stream is not None:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass
                    stream = None
                try:
                    try:
                        device_info = self.pa.get_device_info_by_index(device_idx) if device_idx >= 0 else self.pa.get_default_input_device_info()
                    except Exception:
                        device_info = self.pa.get_default_input_device_info()
                    native_channels = int(device_info.get('maxInputChannels', 1))
                    native_rate = int(device_info.get('defaultSampleRate', 16000))
                    chunk_size = int(native_rate * 0.1)
                    
                    stream = self.pa.open(
                        format=format_type,
                        channels=native_channels,
                        rate=native_rate,
                        input=True,
                        input_device_index=device_idx if device_idx >= 0 else None,
                        frames_per_buffer=chunk_size
                    )
                    current_device = device_idx
                    print(f"TRACER: Opened device {device_idx} ({device_info.get('name')}) | channels: {native_channels} | rate: {native_rate} | chunk_size: {chunk_size}", flush=True)
                except Exception as e:
                    print(f"TRACER: Monitor failed to open stream: {e}", flush=True)
                    import time
                    time.sleep(1.0)
                    continue
            if stream is None:
                import time
                time.sleep(0.1)
                continue
            try:
                data = stream.read(chunk_size, exception_on_overflow=False)
                import numpy as np
                audio_data = np.frombuffer(data, dtype=np.int16)
                if native_channels > 1:
                    audio_data = audio_data.reshape(-1, native_channels)
                    mono_data = audio_data[:, 0].astype(np.float64)
                else:
                    mono_data = audio_data.astype(np.float64)
                mono_data -= np.mean(mono_data)
                mono_data = np.clip(mono_data * 3.0, -32768, 32767).astype(np.int16)
                
                if native_rate != 16000:
                    num_samples = int(len(mono_data) * 16000 / native_rate)
                    resampled_data = np.interp(
                        np.linspace(0, len(mono_data), num_samples, endpoint=False),
                        np.arange(len(mono_data)),
                        mono_data
                    ).astype(np.int16)
                else:
                    resampled_data = mono_data
                
                audio_signals = resampled_data.astype(np.float32)
                rms = np.sqrt(np.mean(audio_signals ** 2))
                
                threshold = 0.0
                
                self.root.after(0, self._update_visualizer, rms, threshold)
                
                if self.is_recording:
                    self.all_recorded_audio.append(resampled_data.tobytes())
                    if self.model_combo.get().startswith("Whisper "):
                        self.active_audio_frames.append(resampled_data.tobytes())
                        self.frames_since_last_transcribe += 1
                        if rms > 250.0:
                            self.speech_detected = True
                        if self.frames_since_last_transcribe >= 10:
                            self.frames_since_last_transcribe = 0
                            if self.speech_detected:
                                self._trigger_transcribe(is_final=False)
                                self.speech_detected = False
                        if len(self.active_audio_frames) >= 150:
                            self._trigger_transcribe(is_final=True)
                            self.active_audio_frames = self.active_audio_frames[-30:]
                            self.window_id += 1
                    else:
                        self.audio_queue.put((resampled_data.tobytes(), rms))
            except Exception as e:
                print(f"TRACER: Monitor read error: {e}", flush=True)
                import time
                time.sleep(0.1)
                
        if stream is not None:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass

    def _update_visualizer(self, rms, threshold):
        self.visualizer.delete("all")
        import math
        normalized = min(1.0, rms / 3000.0)
        bar_width = 4
        gap = 3
        start_x = 7
        for i in range(4):
            factor = (0.5 + 0.5 * math.sin(i * 1.5)) if rms > 10 else 0.05
            h = int(3 + 30 * normalized * factor)
            h = max(3, min(30, h))
            y0 = 34 - h
            y1 = 34
            x0 = start_x + i * (bar_width + gap)
            x1 = x0 + bar_width
            color = "#ef4444" if rms < threshold else "#22c55e"
            self.visualizer.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

    def _stop_recording_action(self):
        if not self.is_recording:
            return
        self.is_recording = False
        if self.model_combo.get().startswith("Whisper "):
            if self.active_audio_frames:
                self._trigger_transcribe(is_final=True)
                self.active_audio_frames = []
        else:
            self.audio_queue.put(None)
        self._on_transcription_finished()

    def _on_transcription_finished(self):
        self._set_btn_state(self.start_btn, "normal", "success")
        self.model_combo.configure(state="normal")
        self.device_combo.configure(state="normal")
        self.text_area.configure(state="normal")
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

    def _save_audio(self):
        if not self.all_recorded_audio:
            return
        filename = f"registrazione_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        filepath = os.path.join(self.dest_dir, filename)
        try:
            raw_bytes = b"".join(self.all_recorded_audio)
            with wave.open(filepath, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(self.pa.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(raw_bytes)
            self._set_status(f"Registrazione audio salvata: {filename}")
            messagebox.showinfo("Salvataggio completato", f"La registrazione audio è stata salvata in:\n{filepath}")
        except Exception as e:
            self._set_status(f"Errore di salvataggio: {e}")
            messagebox.showerror("Errore", f"Impossibile salvare il file audio: {e}")
        self._update_save_button_state()

    def _reset_transcription(self):
        def do_reset():
            self.text_area.configure(state="normal")
            self.text_area.delete("1.0", "end")
            self.text_area.configure(state="normal" if not self.is_recording else "disabled")
            self.all_recorded_audio = []
            self._update_save_button_state()
            self._set_status("Trascrizione e registrazione resettate.")
            
        ConfirmDialog(self.root, "Conferma Reset", "Sei sicuro di voler cancellare tutta la trascrizione e registrazione correnti?", do_reset)

    def _toggle_language(self):
        if self.transcribe_lang == "it":
            self.transcribe_lang = "en"
            self.lang_btn.configure(text="", image=self.img_en)
            self._set_status("Lingua: Inglese")
        else:
            self.transcribe_lang = "it"
            self.lang_btn.configure(text="", image=self.img_it)
            self._set_status("Lingua: Italiano")
        
        self._load_model_async(self.model_combo.get(), self.transcribe_lang)

    def _transcription_worker(self):
        while True:
            item = self.audio_queue.get()
            if item is None:
                print("TRACER: Worker got None sentinel", flush=True)
                if not self.app_running:
                    break
                try:
                    if self.rec:
                        res = json.loads(self.rec.Result())
                        text = res.get("text", "")
                        print(f"TRACER: Final stop text: '{text}'", flush=True)
                        if text.strip():
                            self.root.after(0, self._update_transcription_text, text, True)
                except Exception as e:
                    print(f"TRACER: final result error: {e}", flush=True)
                self.audio_queue.task_done()
                continue
            
            data, rms = item
            print(f"TRACER: Worker got chunk. Len: {len(data)}, RMS: {rms:.2f}", flush=True)
            
            try:
                if self.rec:
                    if self.rec.AcceptWaveform(data):
                        res = json.loads(self.rec.Result())
                        text = res.get("text", "")
                        print(f"TRACER: Final AcceptWaveform text: '{text}'", flush=True)
                        if text.strip():
                            self.root.after(0, self._update_transcription_text, text, True)
                    else:
                        res = json.loads(self.rec.PartialResult())
                        text = res.get("partial", "")
                        if text.strip():
                            print(f"TRACER: Partial text: '{text}'", flush=True)
                        self.root.after(0, self._update_transcription_text, text, False)
                else:
                    print("TRACER: self.rec is None!", flush=True)
            except Exception as e:
                print(f"TRACER: AcceptWaveform error: {e}", flush=True)
            finally:
                self.audio_queue.task_done()

    def _trigger_transcribe(self, is_final=False):
        if not self.active_audio_frames:
            return
        try:
            frames_copy = list(self.active_audio_frames)
            raw_bytes = b"".join(frames_copy)
            local_temp_dir = os.path.join(os.path.dirname(__file__), "temp_chunks")
            os.makedirs(local_temp_dir, exist_ok=True)
            import uuid
            filename = f"chunk_{self.transcribe_seq + 1}_{uuid.uuid4().hex[:8]}.wav"
            path = os.path.join(local_temp_dir, filename)
            self.temp_files.add(path)
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(self.pa.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(raw_bytes)
            self.transcribe_seq += 1
            self.transcription_queue.put((path, is_final, self.window_id, self.transcribe_seq))
        except Exception as e:
            print(f"TRACER: _trigger_transcribe failed: {e}", flush=True)

    def _whisper_transcription_worker(self):
        while True:
            item = self.transcription_queue.get()
            if item is None:
                break
            wav_path, is_final, win_id, seq = item
            
            if seq < self.latest_seq_processed and not is_final:
                try:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
                        self.temp_files.discard(wav_path)
                except Exception:
                    pass
                self.transcription_queue.task_done()
                continue
                
            self.latest_seq_processed = max(self.latest_seq_processed, seq)
            print(f"TRACER: Worker transcribing chunk {wav_path} (win: {win_id}, seq: {seq}, final: {is_final})", flush=True)
            
            try:
                if self.model is not None:
                    segments, info = self.model.transcribe(
                        wav_path,
                        beam_size=5,
                        language=self.transcribe_lang,
                        vad_filter=True,
                        vad_parameters=dict(min_speech_duration_ms=300),
                        condition_on_previous_text=False
                    )
                    text = "".join([segment.text for segment in segments])
                    text = self._clean_hallucinations(text)
                    print(f"TRACER: Transcribed: '{text}'", flush=True)
                    self.root.after(0, self._update_transcription_text, text, is_final)
                else:
                    print("TRACER: self.model is None!", flush=True)
            except Exception as e:
                print(f"TRACER: Transcribe exception: {e}", flush=True)
                self.root.after(0, self._set_status, f"Errore trascrizione: {e}")
            finally:
                try:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
                        self.temp_files.discard(wav_path)
                except Exception as e:
                    print(f"TRACER: Temp file cleanup exception: {e}", flush=True)
                self.transcription_queue.task_done()

    def _clean_hallucinations(self, text):
        text_lower = text.lower()
        blacklist = ["amara.org", "qtss", "sottotitoli", "subtitles", "thank you for watching", "grazie per averci seguito", "iscriviti", "comunità amara"]
        for word in blacklist:
            if word in text_lower:
                return ""
        return text

    def _format_text(self, text, is_final):
        if not text:
            return ""
        if not self.model_combo.get().startswith("Whisper "):
            text = " ".join(text.split())
            words = text.split()
            if words:
                words[0] = words[0].capitalize()
                text = " ".join(words)
        if is_final:
            if text[-1] in {"?", "!"}:
                return text
            clean_text = text[:-1].strip() if text[-1] == "." else text
            question_indicators = {
                "chi", "che", "cosa", "come", "dove", "quando", "perché", "perche", "quale", "quanto", "quanti", "quante", 
                "puoi", "riesci", "vuoi", "sai", "hai", "è", "sono", "potresti", "sapresti", "dovresti",
                "per caso", "percaso", "vero", "giusto", "capisci", "senti", "who", "what", "where", "when", "why", "how",
                "is", "are", "do", "does", "did", "can", "could", "would", "should"
            }
            is_question = False
            text_lower = clean_text.lower()
            for indicator in question_indicators:
                if f" {indicator} " in f" {text_lower} " or text_lower.startswith(indicator) or text_lower.endswith(indicator):
                    is_question = True
                    break
            if is_question:
                text = clean_text + "?"
            elif text[-1] not in {".", "?", "!"}:
                text = text + "."
        return text

    def _update_transcription_text(self, text, is_final):
        self.text_area.configure(state="normal")
        self.text_area.delete("active_start", "end-1c")
        if text.strip():
            formatted = self._format_text(text.strip(), is_final)
            self.text_area.insert("active_start", formatted + " ")
        self.text_area.see("end")
        if is_final:
            self.text_area.mark_set("active_start", "insert")
        if self.is_recording:
            self.text_area.configure(state="disabled")
        else:
            self.text_area.configure(state="normal")
        self._update_save_button_state()

    def _on_closing(self):
        self.is_recording = False
        self.app_running = False
        self.audio_queue.put(None)
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
        local_temp_dir = os.path.join(os.path.dirname(__file__), "temp_chunks")
        if os.path.exists(local_temp_dir):
            try:
                shutil.rmtree(local_temp_dir)
            except Exception:
                pass
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = WhisperApp(root)
    root.mainloop()
