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
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from faster_whisper import WhisperModel

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
        self.root.title("KaliWhisper - Live Transcription")
        self.root.geometry("650x550")
        self.root.minsize(500, 450)
        self.root.configure(bg="#09090b")
        
        self._init_styles()
        
        self.model = None
        self.model_name = "base"
        self.is_recording = False
        self.temp_files = set()
        
        self.transcription_queue = queue.Queue()
        self.pa = pyaudio.PyAudio()
        self.stream = None
        
        self.current_file_total = 0
        self.current_file_progress = 0
        
        self._setup_ui()
        self._update_action_buttons()
        
        if self._is_model_downloaded(self.model_name):
            self._load_model_async(self.model_name)
        else:
            self._set_status(f"Modello {self.model_name} non scaricato. Clicca su '⬇ Scarica'.")
            
        threading.Thread(target=self._transcription_worker, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _init_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("TFrame", background="#09090b")
        style.configure("Labelframe", background="#18181b", foreground="#fafafa", bordercolor="#27272a", borderwidth=1)
        style.configure("Labelframe.Label", background="#18181b", foreground="#fafafa", font=("Segoe UI", 10, "bold"))
        
        style.configure("TLabel", background="#09090b", foreground="#fafafa", font=("Segoe UI", 10))
        style.configure("Card.TLabel", background="#18181b", foreground="#fafafa", font=("Segoe UI", 10))
        
        style.configure("Primary.TButton", background="#ffffff", foreground="#09090b", font=("Segoe UI", 10, "bold"), borderwidth=0, padding=8)
        style.map("Primary.TButton",
                  background=[("active", "#e4e4e7"), ("disabled", "#27272a")],
                  foreground=[("disabled", "#a1a1aa")])
                  
        style.configure("Secondary.TButton", background="#27272a", foreground="#fafafa", font=("Segoe UI", 10), borderwidth=0, padding=8)
        style.map("Secondary.TButton",
                  background=[("active", "#3f3f46"), ("disabled", "#18181b")],
                  foreground=[("disabled", "#52525b")])
                  
        style.configure("Danger.TButton", background="#7f1d1d", foreground="#fca5a5", font=("Segoe UI", 10), borderwidth=0, padding=8)
        style.map("Danger.TButton",
                  background=[("active", "#991b1b"), ("disabled", "#18181b")],
                  foreground=[("disabled", "#52525b")])
                  
        style.configure("TCombobox", fieldbackground="#18181b", background="#27272a", foreground="#fafafa", bordercolor="#27272a", lightcolor="#27272a", darkcolor="#27272a")
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#18181b")],
                  background=[("readonly", "#27272a")],
                  foreground=[("readonly", "#fafafa")])
                  
        style.configure("Horizontal.TProgressbar", background="#ffffff", troughcolor="#27272a", bordercolor="#27272a", lightcolor="#ffffff", darkcolor="#ffffff")
        
        self.root.option_add("*TCombobox*Listbox.background", "#18181b")
        self.root.option_add("*TCombobox*Listbox.foreground", "#fafafa")
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#27272a")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        model_frame = ttk.Frame(main_frame)
        model_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(model_frame, text="Seleziona Modello Whisper:", font=("Segoe UI", 10, "bold"), foreground="#fafafa").pack(side=tk.LEFT, padx=(0, 10))
        self.model_combo = ttk.Combobox(model_frame, values=["tiny", "base", "small", "medium"], state="readonly", width=15)
        self.model_combo.set(self.model_name)
        self.model_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_selected)
        
        self.download_btn = ttk.Button(model_frame, text="⬇ Scarica", command=self._download_selected_model, style="Secondary.TButton")
        self.delete_btn = ttk.Button(model_frame, text="🗑 Elimina", command=self._delete_selected_model, style="Danger.TButton")
        self.update_btn = ttk.Button(model_frame, text="🔄 Aggiorna", command=self._update_selected_model, style="Secondary.TButton")
        
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100, style="Horizontal.TProgressbar")
        self.progress_bar.pack(fill=tk.X, expand=True)
        
        self.status_frame = ttk.LabelFrame(main_frame, text="Stato", padding="10")
        self.status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(self.status_frame, text="Inizializzazione...", style="Card.TLabel")
        self.status_label.pack(anchor=tk.W)
        
        text_frame = ttk.LabelFrame(main_frame, text="Trascrizione", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.text_area = scrolledtext.ScrolledText(
            text_frame, wrap=tk.WORD, font=("Segoe UI", 11),
            bg="#18181b", fg="#fafafa", insertbackground="#fafafa",
            selectbackground="#27272a", selectforeground="#ffffff",
            borderwidth=0, highlightthickness=1, highlightbackground="#27272a",
            highlightcolor="#ffffff", padx=10, pady=10
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.start_btn = ttk.Button(button_frame, text="▶ Avvia Trascrizione", command=self._start_recording, style="Primary.TButton")
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.stop_btn = ttk.Button(button_frame, text="■ Ferma e Salva", command=self._stop_recording, state="disabled", style="Secondary.TButton")
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))


    def _set_status(self, text):
        self.status_label.config(text=text)

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
            self.delete_btn.config(state="normal")
            if self.model is not None and self.model_name == model_name:
                self.start_btn.config(state="normal")
            else:
                self.start_btn.config(state="disabled")
            self._check_for_updates_async(model_name)
        else:
            self.delete_btn.pack_forget()
            self.download_btn.pack(side=tk.LEFT, padx=2)
            self.download_btn.config(state="normal")
            self.start_btn.config(state="disabled")

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
            self.update_btn.config(state="normal")


    def _on_model_selected(self, event):
        new_model = self.model_combo.get()
        self._update_action_buttons()
        
        if self._is_model_downloaded(new_model):
            if self.model_name != new_model or self.model is None:
                self._load_model_async(new_model)
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
            self.model_name = new_model
            self._set_status(f"Modello {new_model} non scaricato. Clicca su '⬇ Scarica'.")

    def _load_model_async(self, model_name):
        self.model_combo.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.delete_btn.config(state="disabled")
        self.update_btn.config(state="disabled")
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
        self.model_combo.config(state="readonly")
        self._update_action_buttons()
        self._set_status("In attesa...")

    def _on_model_load_failed(self, error):
        self.model_combo.config(state="readonly")
        self._update_action_buttons()
        self._set_status(f"Errore caricamento modello: {error}")
        messagebox.showerror("Errore", f"Impossibile caricare il modello Whisper: {error}")

    def _download_selected_model(self):
        model_name = self.model_combo.get()
        self.model_combo.config(state="disabled")
        self.download_btn.config(state="disabled")
        self._set_status(f"Avvio download modello {model_name}...")
        self._download_model_thread(model_name)

    def _download_model_thread(self, model_name):
        self.progress_frame.pack(fill=tk.X, pady=(0, 10), after=self.model_combo.master)
        
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
                self.root.after(0, lambda: self.progress_bar.config(maximum=self.current_file_total, mode="determinate"))
            else:
                self.root.after(0, lambda: self.progress_bar.config(mode="indeterminate"))
                self.root.after(0, self.progress_bar.start)
        elif action == "update":
            if self.current_file_total > 0:
                self.current_file_progress += value
                self.root.after(0, lambda: self.progress_var.set(self.current_file_progress))
        elif action == "close":
            self.root.after(0, self.progress_bar.stop)
            self.root.after(0, lambda: self.progress_var.set(0))

    def _on_download_success(self, model_name):
        self.model_combo.config(state="readonly")
        self._update_action_buttons()
        self._load_model_async(model_name)

    def _on_download_failed(self, model_name, error):
        self.model_combo.config(state="readonly")
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
            self.start_btn.config(state="disabled")
            
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
            
        self.model_combo.config(state="disabled")
        self.delete_btn.config(state="disabled")
        self.update_btn.config(state="disabled")
        self._set_status(f"Verifica aggiornamenti modello {model_name}...")
        self._download_model_thread(model_name)

    def _start_recording(self):
        if self.model is None:
            messagebox.showwarning("Attenzione", "Il modello non è ancora pronto.")
            return
            
        self.is_recording = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.model_combo.config(state="disabled")
        self.delete_btn.config(state="disabled")
        self.update_btn.config(state="disabled")
        self._set_status("Registrazione in corso...")
        
        threading.Thread(target=self._recording_worker, daemon=True).start()

    def _recording_worker(self):
        try:
            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )
        except Exception as e:
            self.root.after(0, self._set_status, f"Errore microfono: {e}")
            self.root.after(0, self._on_recording_failed)
            return

        frames = []
        chunk_length = 4.0
        samples_per_chunk = int(16000 * chunk_length)
        
        while self.is_recording:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                frames.append(data)
            except Exception:
                break
                
            current_samples = len(frames) * 1024
            if current_samples >= samples_per_chunk:
                self._save_chunk(frames)
                frames = []
                
        if frames:
            self._save_chunk(frames)
            
        try:
            self.stream.stop_stream()
            self.stream.close()
        except Exception:
            pass

    def _save_chunk(self, frames):
        try:
            if not os.path.exists("/tmp"):
                os.makedirs("/tmp")
        except Exception:
            pass
            
        try:
            fd, wav_path = tempfile.mkstemp(suffix=".wav", dir="/tmp")
            os.close(fd)
            self.temp_files.add(wav_path)
            
            wf = wave.open(wav_path, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(self.pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            self.transcription_queue.put(wav_path)
        except Exception as e:
            self.root.after(0, self._set_status, f"Errore scrittura audio: {e}")

    def _on_recording_failed(self):
        self.is_recording = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.model_combo.config(state="readonly")
        self._update_action_buttons()
        messagebox.showerror("Errore", "Impossibile avviare la registrazione audio. Verifica il microfono.")

    def _stop_recording(self):
        self._stop_recording_action()

    def _stop_recording_action(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self._set_status("Elaborazione degli ultimi frammenti...")
        
        def wait_and_save():
            self.transcription_queue.join()
            self.root.after(0, self._save_transcription)
            
        threading.Thread(target=wait_and_save, daemon=True).start()

    def _save_transcription(self):
        text_content = self.text_area.get("1.0", tk.END).strip()
        if not text_content:
            self._set_status("Salvataggio annullato (testo vuoto)")
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.model_combo.config(state="readonly")
            self._update_action_buttons()
            return
            
        filename = f"trascrizione_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        home_dir = os.path.expanduser("~")
        filepath = os.path.join(home_dir, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text_content)
            self._set_status(f"Salvataggio completato: {filename}")
            messagebox.showinfo("Salvataggio completato", f"La trascrizione è stata salvata in:\n{filepath}")
        except Exception as e:
            self._set_status(f"Errore di salvataggio: {e}")
            messagebox.showerror("Errore", f"Impossibile salvare il file: {e}")
            
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.model_combo.config(state="readonly")
        self._update_action_buttons()

    def _transcription_worker(self):
        while True:
            item = self.transcription_queue.get()
            if item is None:
                break
            wav_path = item
            try:
                if self.model is not None:
                    segments, info = self.model.transcribe(wav_path, beam_size=5)
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
        self.text_area.insert(tk.END, text + " ")
        self.text_area.see(tk.END)

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
    root = tk.Tk()
    app = WhisperApp(root)
    root.mainloop()
