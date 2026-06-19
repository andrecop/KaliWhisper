import os
import wave
import queue
import threading
import tempfile
import pyaudio
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from faster_whisper import WhisperModel

class WhisperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("KaliWhisper - Live Transcription")
        self.root.geometry("600x500")
        self.root.minsize(450, 400)
        
        self.model = None
        self.model_name = "base"
        self.is_recording = False
        self.temp_files = set()
        
        self.transcription_queue = queue.Queue()
        self.pa = pyaudio.PyAudio()
        self.stream = None
        
        self._setup_ui()
        self._initial_load()
        
        threading.Thread(target=self._transcription_worker, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        model_frame = ttk.Frame(main_frame)
        model_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(model_frame, text="Seleziona Modello Whisper:", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        self.model_combo = ttk.Combobox(model_frame, values=["tiny", "base", "small", "medium"], state="readonly")
        self.model_combo.set(self.model_name)
        self.model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_selected)
        
        status_frame = ttk.LabelFrame(main_frame, text="Stato", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Inizializzazione...", font=("Helvetica", 10))
        self.status_label.pack(anchor=tk.W)
        
        text_frame = ttk.LabelFrame(main_frame, text="Trascrizione", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.text_area = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, font=("Helvetica", 11))
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.start_btn = ttk.Button(button_frame, text="▶ Avvia Trascrizione", command=self._start_recording)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        self.stop_btn = ttk.Button(button_frame, text="■ Ferma e Salva", command=self._stop_recording, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

    def _set_status(self, text):
        self.status_label.config(text=text)

    def _initial_load(self):
        self.model_combo.config(state="disabled")
        self.start_btn.config(state="disabled")
        self._set_status(f"Caricamento modello {self.model_name}...")
        
        def load_task():
            try:
                self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
                self.root.after(0, self._on_model_loaded)
            except Exception as e:
                self.root.after(0, self._on_model_load_failed, e)
                
        threading.Thread(target=load_task, daemon=True).start()

    def _on_model_loaded(self):
        self.model_combo.config(state="readonly")
        self.start_btn.config(state="normal")
        self._set_status("In attesa...")

    def _on_model_load_failed(self, error):
        self.model_combo.config(state="readonly")
        self.start_btn.config(state="disabled")
        self._set_status(f"Errore caricamento modello: {error}")
        messagebox.showerror("Errore", f"Impossibile caricare il modello Whisper: {error}")

    def _on_model_selected(self, event):
        new_model = self.model_combo.get()
        if new_model != self.model_name:
            self._change_model(new_model)

    def _change_model(self, new_model):
        if self.is_recording:
            self._stop_recording_action()
            
        self.model_combo.config(state="disabled")
        self.start_btn.config(state="disabled")
        self._set_status(f"Caricamento modello {new_model}...")
        
        def load_task():
            try:
                if self.model is not None:
                    del self.model
                    import gc
                    gc.collect()
                    self.model = None
                self.model = WhisperModel(new_model, device="cpu", compute_type="int8")
                self.model_name = new_model
                self.root.after(0, self._on_model_loaded)
            except Exception as e:
                self.root.after(0, self._on_model_load_failed, e)
                
        threading.Thread(target=load_task, daemon=True).start()

    def _start_recording(self):
        if self.model is None:
            messagebox.showwarning("Attenzione", "Il modello non è ancora pronto.")
            return
            
        self.is_recording = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.model_combo.config(state="disabled")
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
