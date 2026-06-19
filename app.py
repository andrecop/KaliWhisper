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

class ToolTip:
    def __init__(self, widget, text_dict):
        self.widget = widget
        self.text_dict = text_dict
        self.tip_window = None
        self.lang = "it"
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def set_language(self, lang):
        self.lang = lang

    def update_text(self, text_dict):
        self.text_dict = text_dict

    def show_tip(self, event=None):
        if self.tip_window or not self.text_dict:
            return
        
        content = self.text_dict.get(self.lang, self.text_dict.get("en", ""))
        if not content:
            return
            
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg="#18181b")
        
        # Border frame to match shadcn style
        border = tk.Frame(tw, bg="#27272a", bd=1)
        border.pack(fill=tk.BOTH, expand=True)
        
        container = tk.Frame(border, bg="#18181b", padx=10, pady=8)
        container.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        if isinstance(content, dict):
            title = content.get("title", "")
            desc = content.get("desc", "")
            
            title_lbl = tk.Label(
                container, text=title, justify=tk.LEFT,
                bg="#18181b", fg="#fafafa",
                font=("Segoe UI", 10, "bold")
            )
            title_lbl.pack(anchor="w")
            
            desc_lbl = tk.Label(
                container, text=desc, justify=tk.LEFT,
                bg="#18181b", fg="#a1a1aa",
                font=("Segoe UI", 9), wraplength=300
            )
            desc_lbl.pack(anchor="w", pady=(4, 0))
        else:
            label = tk.Label(
                container, text=content, justify=tk.LEFT,
                bg="#18181b", fg="#fafafa",
                font=("Segoe UI", 9, "bold")
            )
            label.pack()

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

class FlagDropdown(ctk.CTkToplevel):
    LANGUAGES = [
        {"name": "Spagnolo (Spanish)", "code": "es", "flag": "ES", "wer": "3.4%"},
        {"name": "Inglese (English)", "code": "en", "flag": "GB", "wer": "4.2%"},
        {"name": "Portoghese (Portuguese)", "code": "pt", "flag": "PT", "wer": "4.3%"},
        {"name": "Tedesco (German)", "code": "de", "flag": "DE", "wer": "4.4%"},
        {"name": "Italiano (Italian)", "code": "it", "flag": "IT", "wer": "4.7%"},
        {"name": "Francese (French)", "code": "fr", "flag": "FR", "wer": "4.8%"},
        {"name": "Russo (Russian)", "code": "ru", "flag": "RU", "wer": "5.0%"},
        {"name": "Giapponese (Japanese)", "code": "ja", "flag": "JP", "wer": "5.3%"},
        {"name": "Polacco (Polish)", "code": "pl", "flag": "PL", "wer": "5.4%"},
        {"name": "Catalano (Catalan)", "code": "ca", "flag": "CA", "wer": "5.4%"},
        {"name": "Cinese (Chinese)", "code": "zh", "flag": "CN", "wer": "5.5%"},
        {"name": "Olandese (Dutch)", "code": "nl", "flag": "NL", "wer": "5.9%"},
        {"name": "Svedese (Swedish)", "code": "sv", "flag": "SE", "wer": "6.1%"},
        {"name": "Turco (Turkish)", "code": "tr", "flag": "TR", "wer": "6.4%"},
        {"name": "Vietnamita (Vietnamese)", "code": "vi", "flag": "VN", "wer": "6.5%"},
        {"name": "Indonesiano (Indonesian)", "code": "id", "flag": "ID", "wer": "6.5%"},
        {"name": "Coreano (Korean)", "code": "ko", "flag": "KR", "wer": "7.2%"},
        {"name": "Ceco (Czech)", "code": "cs", "flag": "CZ", "wer": "7.2%"},
        {"name": "Malese (Malay)", "code": "ms", "flag": "MY", "wer": "7.5%"},
        {"name": "Finlandese (Finnish)", "code": "fi", "flag": "FI", "wer": "8.0%"},
        {"name": "Ucraino (Ukrainian)", "code": "uk", "flag": "UA", "wer": "8.5%"},
        {"name": "Greco (Greek)", "code": "el", "flag": "GR", "wer": "8.8%"},
        {"name": "Norvegese (Norwegian)", "code": "no", "flag": "NO", "wer": "~ 9%"},
        {"name": "Danese (Danish)", "code": "da", "flag": "DK", "wer": "~ 9%"},
        {"name": "Ungherese (Hungarian)", "code": "hu", "flag": "HU", "wer": "~ 9%"},
        {"name": "Rumeno (Romanian)", "code": "ro", "flag": "RO", "wer": "~ 10%"},
        {"name": "Arabo (Arabic)", "code": "ar", "flag": "SA", "wer": "~ 11%"},
        {"name": "Slovacco (Slovak)", "code": "sk", "flag": "SK", "wer": "~ 11%"},
        {"name": "Hindi (Hindi)", "code": "hi", "flag": "IN", "wer": "~ 11%"},
        {"name": "Croato (Croatian)", "code": "hr", "flag": "HR", "wer": "~ 12%"},
        {"name": "Bulgaro (Bulgarian)", "code": "bg", "flag": "BG", "wer": "~ 12%"},
        {"name": "Lituano (Lithuanian)", "code": "lt", "flag": "LT", "wer": "~ 13%"},
        {"name": "Serbo (Serbian)", "code": "sr", "flag": "RS", "wer": "~ 14%"},
        {"name": "Lettone (Latvian)", "code": "lv", "flag": "LV", "wer": "~ 14%"},
        {"name": "Ebraico (Hebrew)", "code": "he", "flag": "IL", "wer": "~ 15%"},
        {"name": "Sloveno (Slovenian)", "code": "sl", "flag": "SI", "wer": "~ 15%"},
        {"name": "Estone (Estonian)", "code": "et", "flag": "EE", "wer": "~ 16%"},
        {"name": "Tamil (Tamil)", "code": "ta", "flag": "IN", "wer": "~ 16%"},
        {"name": "Bengalese (Bengali)", "code": "bn", "flag": "BD", "wer": "~ 17%"},
        {"name": "Urdu (Urdu)", "code": "ur", "flag": "PK", "wer": "~ 17%"},
        {"name": "Tailandese (Thai)", "code": "th", "flag": "TH", "wer": "~ 18%"},
        {"name": "Galiziano (Galician)", "code": "gl", "flag": "ES", "wer": "~ 18%"},
        {"name": "Macedone (Macedonian)", "code": "mk", "flag": "MK", "wer": "~ 19%"},
        {"name": "Persiano (Persian)", "code": "fa", "flag": "IR", "wer": "~ 20%"},
        {"name": "Bosniaco (Bosnian)", "code": "bs", "flag": "BA", "wer": "~ 20%"},
        {"name": "Telugu (Telugu)", "code": "te", "flag": "IN", "wer": "~ 21%"},
        {"name": "Albanese (Albanian)", "code": "sq", "flag": "AL", "wer": "~ 22%"},
        {"name": "Marathi (Marathi)", "code": "mr", "flag": "IN", "wer": "~ 23%"},
        {"name": "Malese (Malayalam)", "code": "ml", "flag": "IN", "wer": "~ 24%"},
        {"name": "Islandese (Icelandic)", "code": "is", "flag": "IS", "wer": "~ 25%"},
        {"name": "Georgiano (Georgian)", "code": "ka", "flag": "GE", "wer": "~ 26%"},
        {"name": "Gallese (Welsh)", "code": "cy", "flag": "GB", "wer": "~ 27%"},
        {"name": "Kazako (Kazakh)", "code": "kk", "flag": "KZ", "wer": "~ 28%"},
        {"name": "Tagalog (Tagalog)", "code": "tl", "flag": "PH", "wer": "~ 29%"},
        {"name": "Punjabi (Punjabi)", "code": "pa", "flag": "PK", "wer": "~ 30%"},
        {"name": "Armeno (Armenian)", "code": "hy", "flag": "AM", "wer": "~ 31%"},
        {"name": "Nepalese (Nepali)", "code": "ne", "flag": "NP", "wer": "~ 32%"},
        {"name": "Gujarati (Gujarati)", "code": "gu", "flag": "IN", "wer": "~ 33%"},
        {"name": "Kannada (Kannada)", "code": "kn", "flag": "IN", "wer": "~ 34%"},
        {"name": "Basco (Basque)", "code": "eu", "flag": "ES", "wer": "~ 35%"},
        {"name": "Sundanese (Sundanese)", "code": "su", "flag": "ID", "wer": "~ 36%"},
        {"name": "Giavanese (Javanese)", "code": "jv", "flag": "ID", "wer": "~ 37%"},
        {"name": "Azero (Azerbaijani)", "code": "az", "flag": "AZ", "wer": "~ 38%"},
        {"name": "Swahili (Swahili)", "code": "sw", "flag": "TZ", "wer": "~ 39%"},
        {"name": "Sinhala (Sinhala)", "code": "si", "flag": "LK", "wer": "~ 40%"},
        {"name": "Mongolo (Mongolian)", "code": "mn", "flag": "MN", "wer": "~ 41%"},
        {"name": "Bielorusso (Belarusian)", "code": "be", "flag": "BY", "wer": "~ 42%"},
        {"name": "Khmer (Khmer)", "code": "km", "flag": "KH", "wer": "~ 43%"},
        {"name": "Uzbeco (Uzbek)", "code": "uz", "flag": "UZ", "wer": "~ 44%"},
        {"name": "Pashto (Pashto)", "code": "ps", "flag": "AF", "wer": "~ 45%"},
        {"name": "Lao (Lao)", "code": "lo", "flag": "LA", "wer": "~ 46%"},
        {"name": "Creolo Haitiano (Haitian Creole)", "code": "ht", "flag": "HT", "wer": "~ 47%"},
        {"name": "Somalo (Somali)", "code": "so", "flag": "SO", "wer": "~ 48%"},
        {"name": "Maori (Maori)", "code": "mi", "flag": "NZ", "wer": "~ 49%"},
        {"name": "Amarico (Amharic)", "code": "am", "flag": "ET", "wer": "> 50%"},
        {"name": "Sindhi (Sindhi)", "code": "sd", "flag": "PK", "wer": "> 50%"},
        {"name": "Bretone (Breton)", "code": "br", "flag": "FR", "wer": "> 50%"},
        {"name": "Hausa (Hausa)", "code": "ha", "flag": "NG", "wer": "> 50%"},
        {"name": "Shona (Shona)", "code": "sn", "flag": "ZW", "wer": "> 50%"},
        {"name": "Lingala (Lingala)", "code": "ln", "flag": "CD", "wer": "> 50%"},
        {"name": "Yoruba (Yoruba)", "code": "yo", "flag": "NG", "wer": "> 50%"},
        {"name": "Malgascio (Malagasy)", "code": "mg", "flag": "MG", "wer": "> 50%"},
        {"name": "Nynorsk (Norwegian Nynorsk)", "code": "nn", "flag": "NO", "wer": "> 50%"},
        {"name": "Lussemburghese (Luxembourgish)", "code": "lb", "flag": "LU", "wer": "> 50%"},
        {"name": "Maltese (Maltese)", "code": "mt", "flag": "MT", "wer": "> 50%"},
        {"name": "Yiddish (Yiddish)", "code": "yi", "flag": "IL", "wer": "> 50%"},
        {"name": "Occitano (Occitan)", "code": "oc", "flag": "FR", "wer": "> 60%"},
        {"name": "Hawaiano (Hawaiian)", "code": "haw", "flag": "US", "wer": "> 60%"},
        {"name": "Faroese (Faroese)", "code": "fo", "flag": "FO", "wer": "> 60%"},
        {"name": "Tataro (Tatar)", "code": "tt", "flag": "RU", "wer": "> 60%"},
        {"name": "Turkmeno (Turkmen)", "code": "tk", "flag": "TM", "wer": "> 60%"},
        {"name": "Tagico (Tajik)", "code": "tg", "flag": "TJ", "wer": "> 60%"},
        {"name": "Sanscrito (Sanskrit)", "code": "sa", "flag": "IN", "wer": "> 60%"},
        {"name": "Tibetano (Tibetan)", "code": "bo", "flag": "CN", "wer": "> 60%"},
        {"name": "Birmano (Burmese)", "code": "my", "flag": "MM", "wer": "> 60%"},
        {"name": "Assamese (Assamese)", "code": "as", "flag": "IN", "wer": "> 60%"},
        {"name": "Baschiro (Bashkir)", "code": "ba", "flag": "RU", "wer": "> 60%"},
        {"name": "Afrikaans (Afrikaans)", "code": "af", "flag": "ZA", "wer": "> 60%"}
    ]

    def __init__(self, master, get_flag_image_fn, on_select):
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        self.configure(fg_color="#09090b")
        self._get_flag_image = get_flag_image_fn
        self._on_select = on_select
        
        self.border_frame = ctk.CTkFrame(
            self, fg_color="#18181b", border_color="#27272a", border_width=1, corner_radius=8
        )
        self.border_frame.pack(fill=tk.BOTH, expand=True)
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._populate_list())
        
        self.search_entry = ctk.CTkEntry(
            self.border_frame, textvariable=self.search_var, placeholder_text="Cerca lingua...",
            fg_color="#09090b", border_color="#27272a", text_color="#fafafa",
            font=("Segoe UI", 11), height=28, corner_radius=6
        )
        self.search_entry.pack(fill=tk.X, padx=6, pady=(6, 2))
        
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.border_frame, fg_color="transparent", width=220, height=250
        )
        self.scroll_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 6))
        
        self.bind("<Button-1>", self._on_click_outside)
        self.bind("<Escape>", lambda e: self.close())
        
    def _populate_list(self):
        self.populate_seq = getattr(self, "populate_seq", 0) + 1
        current_seq = self.populate_seq
        
        for w in self.scroll_frame.winfo_children():
            w.destroy()
            
        query = self.search_var.get().lower().strip()
        filtered = []
        for lang in self.LANGUAGES:
            if not query or query in lang["name"].lower() or query in lang["code"].lower():
                filtered.append(lang)
                
        def load_batch(index, first_sync=False):
            if self.populate_seq != current_seq:
                return
            batch_size = 15 if first_sync else 6
            for i in range(index, min(index + batch_size, len(filtered))):
                lang = filtered[i]
                name = lang["name"]
                code = lang["code"]
                flag = lang["flag"]
                wer = lang["wer"]
                
                img = self._get_flag_image(flag)
                
                btn_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
                btn_frame.pack(fill=tk.X, pady=1)
                
                btn = ctk.CTkButton(
                    btn_frame, text=f" {name}", image=img, compound="left", anchor="w",
                    fg_color="transparent", text_color="#fafafa",
                    hover_color="#27272a", font=("Segoe UI", 11),
                    height=28, corner_radius=6,
                    command=lambda c=code: [self._on_select(c), self.close()]
                )
                btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
                
                wer_lbl = ctk.CTkLabel(
                    btn_frame, text=wer, font=("Segoe UI", 10, "bold"), text_color="#a1a1aa", width=45, anchor="e"
                )
                wer_lbl.pack(side=tk.RIGHT, padx=(5, 5))
                
            self.update_idletasks()
            if index + batch_size < len(filtered):
                self.after(5, lambda: load_batch(index + batch_size, False))
                
        load_batch(0, first_sync=True)
            
    def _on_click_outside(self, event):
        x, y = event.x_root, event.y_root
        win_x = self.winfo_rootx()
        win_y = self.winfo_rooty()
        win_w = self.winfo_width()
        win_h = self.winfo_height()
        if not (win_x <= x <= win_x + win_w and win_y <= y <= win_y + win_h):
            self.close()
            
    def open(self, x, y):
        self.search_var.set("")
        self.geometry(f"250x300+{int(x)}+{int(y)}")
        self.deiconify()
        self.update_idletasks()
        self._populate_list()
        self.lift()
        self.focus_force()
        self.search_entry.focus()
        self.grab_set()
        
    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.withdraw()

import customtkinter.windows.widgets.ctk_optionmenu as optmenu
optmenu.DropdownMenu = ShadcnDropdown

class ConfirmDialog(ctk.CTkToplevel):
    def __init__(self, master, title, message, on_confirm, on_cancel=None):
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
            command=lambda: [on_cancel() if on_cancel else None, self.destroy()]
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
        self.save_and_close_on_finish = False
        self.close_on_complete = False
        self.is_playing = False
        self.pa = pyaudio.PyAudio()
        self.stream = None
        self.rec = None
        
        self.dest_root = os.path.join(os.path.dirname(__file__), "recorded")
        self.dest_dir = self.dest_root
        self.custom_dest = False
        self.transcribe_lang = "it"
        self.target_lang = "it"
        self.ui_lang = "it"
        
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
        self.flag_images_cache = {}
        
        def get_flag_image_fn(flag_code):
            flag_code = flag_code.upper()
            if flag_code not in self.flag_images_cache:
                try:
                    svg_path = os.path.join(flags_dir, f"{flag_code}.svg")
                    if not os.path.exists(svg_path):
                        svg_path = os.path.join(flags_dir, "XX.svg")
                    self.flag_images_cache[flag_code] = ctk.CTkImage(
                        light_image=load_svg_as_image(svg_path, (24, 16)), size=(24, 16)
                    )
                except Exception:
                    try:
                        self.flag_images_cache[flag_code] = ctk.CTkImage(
                            light_image=load_svg_as_image(os.path.join(flags_dir, "XX.svg"), (24, 16)), size=(24, 16)
                        )
                    except Exception:
                        self.flag_images_cache[flag_code] = None
            return self.flag_images_cache[flag_code]
            
        self.get_flag_image = get_flag_image_fn
        self.img_it = self.get_flag_image("IT")
        self.img_en = self.get_flag_image("GB")
        
        # Pre-load all flags in a background thread to prevent dropdown loading lag and rendering bugs
        def pre_load_flags():
            for lang in FlagDropdown.LANGUAGES:
                if not getattr(self, "app_running", True):
                    break
                try:
                    self.get_flag_image(lang["flag"])
                except Exception:
                    pass
        threading.Thread(target=pre_load_flags, daemon=True).start()
        
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
        
        self.model_label = ctk.CTkLabel(self.model_frame, text="Motore di Trascrizione:", font=("Segoe UI", 11, "bold"), text_color="#fafafa", width=140, anchor="w")
        self.model_label.pack(side=tk.LEFT, padx=(0, 10))
        
        model_border = ctk.CTkFrame(self.model_frame, fg_color="#27272a", corner_radius=8, height=30)
        model_border.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
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
        self.dest_btn = ctk.CTkButton(self.model_frame, text="📂 Destinazione", command=self._choose_destination, font=("Segoe UI", 10, "bold"), width=148, height=30)
        self.dest_btn.pack(side=tk.RIGHT, padx=2)
        self._set_btn_state(self.dest_btn, "normal", "secondary")

        device_frame = ctk.CTkFrame(main_frame, fg_color="#09090b")
        device_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.device_label = ctk.CTkLabel(device_frame, text="Ingresso Audio:", font=("Segoe UI", 11, "bold"), text_color="#fafafa", width=140, anchor="w")
        self.device_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.target_lang_btn = ctk.CTkButton(
            device_frame, text=" ▾", image=self.img_it, compound="left",
            command=self._show_target_flag_dropdown, width=64, height=30,
            fg_color="#18181b", border_color="#27272a", border_width=1, hover_color="#27272a",
            text_color="#fafafa", font=("Segoe UI", 11, "bold"), corner_radius=8
        )
        self.target_lang_btn.pack(side=tk.RIGHT, padx=(2, 0))
        
        self.arrow_label = ctk.CTkLabel(device_frame, text="→", font=("Segoe UI", 12, "bold"), text_color="#a1a1aa")
        self.arrow_label.pack(side=tk.RIGHT, padx=4)
        
        self.lang_btn = ctk.CTkButton(
            device_frame, text=" ▾", image=self.img_it, compound="left",
            command=self._show_flag_dropdown, width=64, height=30,
            fg_color="#18181b", border_color="#27272a", border_width=1, hover_color="#27272a",
            text_color="#fafafa", font=("Segoe UI", 11, "bold"), corner_radius=8
        )
        self.lang_btn.pack(side=tk.RIGHT, padx=2)
        
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

        status_frame = ctk.CTkFrame(main_frame, fg_color="#09090b")
        status_frame.pack(fill=tk.X, pady=(0, 15))
        
        status_border = ctk.CTkFrame(status_frame, fg_color="#27272a", corner_radius=8, height=30)
        status_border.pack(fill=tk.X, expand=True)
        status_border.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            status_border, text="Inizializzazione...", font=("Segoe UI", 11, "bold"),
            text_color="#a1a1aa", fg_color="#18181b", corner_radius=7
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(1, 0), pady=1)

        status_divider = ctk.CTkFrame(status_border, fg_color="#27272a", width=1)
        status_divider.pack(side=tk.LEFT, fill=tk.Y, pady=4)

        self.wer_label = ctk.CTkLabel(
            status_border, text="WER 4.7%", font=("Segoe UI", 11, "bold"),
            text_color="#ef4444", fg_color="#18181b", corner_radius=7, width=80
        )
        self.wer_label.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(0, 1), pady=1)
        
        self.wer_tooltip = ToolTip(self.wer_label, {
            "it": {
                "title": "Affidabile (Reliable)",
                "desc": "La trascrizione è quasi perfetta. Le uniche correzioni necessarie riguardano tipicamente nomi propri, acronimi o punteggiatura complessa. Il testo è pronto all'uso con uno sforzo minimo."
            },
            "en": {
                "title": "Reliable",
                "desc": "The transcription is nearly perfect. Only minor corrections are needed for proper names, acronyms, or complex punctuation. Ready to use with minimal effort."
            }
        })
        self.wer_label.configure(text_color="#10B981")
        
        self.progress_frame = ctk.CTkFrame(main_frame, fg_color="#09090b")
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, progress_color="#ffffff", fg_color="#27272a")
        self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_bar.set(0.0)
        
        text_frame = ctk.CTkFrame(main_frame, fg_color="#18181b", border_color="#27272a", border_width=1)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        self.text_label = ctk.CTkLabel(text_frame, text="Trascrizione", font=("Segoe UI", 10, "bold"), text_color="#fafafa")
        self.text_label.pack(anchor=tk.W, padx=15, pady=(10, 4))
        
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
        
        self.reset_btn = ctk.CTkButton(button_frame, text="🗑 Reset", command=self._reset_transcription, font=("Segoe UI", 11, "bold"), height=38, fg_color="#ef4444", hover_color="#dc2626", text_color="#ffffff")
        self.reset_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.play_btn = ctk.CTkButton(button_frame, text="🔊 Ascolta Trascrizione", command=self._toggle_playback, font=("Segoe UI", 11, "bold"), height=38)
        self.play_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        self.start_btn = ctk.CTkButton(button_frame, text="▶ Avvia Trascrizione", command=self._toggle_recording, font=("Segoe UI", 11, "bold"), height=38)
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.bottom_btn_frame = ctk.CTkFrame(main_frame, fg_color="#09090b")
        self.bottom_btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.ui_lang_btn = ctk.CTkButton(
            self.bottom_btn_frame, text="UI ▾", image=self.img_it, compound="left",
            command=self._show_ui_flag_dropdown, height=38,
            fg_color="#18181b", border_color="#27272a", border_width=1, hover_color="#27272a",
            text_color="#fafafa", font=("Segoe UI", 11, "bold"), corner_radius=8
        )
        self.ui_lang_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self._set_btn_state(self.ui_lang_btn, "normal", "secondary")

        self.save_audio_btn = ctk.CTkButton(self.bottom_btn_frame, text="🎙️ Salva Audio", command=self._save_audio, font=("Segoe UI", 11, "bold"), height=38)
        self.save_audio_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        self.save_btn = ctk.CTkButton(self.bottom_btn_frame, text="💾 Salva Trascrizione", command=self._save_transcription, font=("Segoe UI", 11, "bold"), height=38)
        self.save_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        self.close_btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.close_btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.visualizer_container = ctk.CTkFrame(self.close_btn_frame, fg_color="#18181b", width=140, height=38, border_color="#27272a", border_width=1)
        self.visualizer_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.visualizer_container.pack_propagate(False)
        
        self.visualizer = tk.Canvas(self.visualizer_container, height=36, bg="#18181b", highlightthickness=0)
        self.visualizer.pack(fill=tk.BOTH, expand=True, padx=2, pady=1)

        self.save_and_close_btn = ctk.CTkButton(
            self.close_btn_frame, 
            text="💾 Salva tutto e Chiudi al termine", 
            command=self._save_all_and_close_on_finish, 
            font=("Segoe UI", 11, "bold"), 
            height=38, 
            fg_color="#18181b", 
            border_color="#27272a", 
            border_width=1, 
            text_color="#fafafa",
            hover_color="#27272a"
        )
        self.save_and_close_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        self._set_btn_state(self.start_btn, "disabled", "success")
        self._set_btn_state(self.save_btn, "disabled", "info")
        self._set_btn_state(self.play_btn, "disabled", "info")
        self._set_btn_state(self.save_audio_btn, "disabled", "info")
        self._set_btn_state(self.save_and_close_btn, "disabled", "secondary")

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
        is_transcribing = not self.transcription_queue.empty() or not self.audio_queue.empty()
        
        if not self.is_recording and not is_transcribing and text_content:
            self._set_btn_state(self.save_btn, "normal", "info")
        else:
            self._set_btn_state(self.save_btn, "disabled", "info")
            
        if not self.is_recording and not is_transcribing and getattr(self, "all_recorded_audio", None):
            self._set_btn_state(self.play_btn, "normal", "info")
            self._set_btn_state(self.save_audio_btn, "normal", "info")
        else:
            self._set_btn_state(self.play_btn, "disabled", "info")
            self._set_btn_state(self.save_audio_btn, "disabled", "info")
            
        if not self.is_recording and (text_content or getattr(self, "all_recorded_audio", None)):
            self._set_btn_state(self.save_and_close_btn, "normal", "secondary")
        else:
            self._set_btn_state(self.save_and_close_btn, "disabled", "secondary")
            
        if not self.is_recording and not is_transcribing:
            self.model_combo.configure(state="normal")
            self.device_combo.configure(state="normal")
            self._set_btn_state(self.lang_btn, "normal", "secondary")
            self._set_btn_state(self.target_lang_btn, "normal", "secondary")
            self._set_btn_state(self.ui_lang_btn, "normal", "secondary")
            self._set_btn_state(self.dest_btn, "normal", "secondary")
        else:
            self.model_combo.configure(state="disabled")
            self.device_combo.configure(state="disabled")
            self._set_btn_state(self.lang_btn, "disabled", "secondary")
            self._set_btn_state(self.target_lang_btn, "disabled", "secondary")
            self._set_btn_state(self.ui_lang_btn, "disabled", "secondary")
            self._set_btn_state(self.dest_btn, "disabled", "secondary")

    def _toggle_recording(self):
        if not self.is_recording:
            if self.model is None:
                messagebox.showwarning("Attenzione", "Il modello non è ancora pronto.")
                return
            self.is_recording = True
            if not getattr(self, "custom_dest", False):
                session_name = datetime.now().strftime("%Y-%m-%d %H.%M.%S")
                self.dest_dir = os.path.join(self.dest_root, session_name)
                os.makedirs(self.dest_dir, exist_ok=True)
            self.start_btn.configure(text="■ Ferma Trascrizione")
            self._set_btn_state(self.start_btn, "normal", "danger")
            self._set_btn_state(self.save_btn, "disabled", "info")
            self._set_btn_state(self.play_btn, "disabled", "info")
            self._set_btn_state(self.save_audio_btn, "disabled", "info")
            self.all_recorded_audio = []
            self.model_combo.configure(state="disabled")
            self.device_combo.configure(state="disabled")
            
            self.text_area.configure(state="normal")
            existing_text = self.text_area.get("1.0", "end").strip()
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            if self.ui_lang == "en":
                if existing_text:
                    self.text_area.insert("end", f"\n\n------- continued {now_str} -------\n\n")
                else:
                    self.text_area.insert("end", f"------- started {now_str} -------\n\n")
            else:
                if existing_text:
                    self.text_area.insert("end", f"\n\n------- continua {now_str} -------\n\n")
                else:
                    self.text_area.insert("end", f"------- inizio {now_str} -------\n\n")
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
            self._set_btn_state(self.start_btn, "normal", "success")
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
        try:
            canvas_width = max(38, self.visualizer.winfo_width())
            canvas_height = max(20, self.visualizer.winfo_height())
        except Exception:
            canvas_width = 140
            canvas_height = 36
            
        num_bars = max(1, (canvas_width - gap) // (bar_width + gap))
        start_x = (canvas_width - (num_bars * (bar_width + gap) - gap)) // 2
        for i in range(num_bars):
            factor = (0.5 + 0.5 * math.sin(i * 0.8)) if rms > 10 else 0.05
            h = int(3 + (canvas_height - 6) * normalized * factor)
            h = max(3, min(canvas_height - 6, h))
            y0 = (canvas_height - h) // 2
            y1 = y0 + h
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
            self.custom_dest = True
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
            if self.is_recording:
                self._toggle_recording()
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.task_done()
                except Exception:
                    pass
            while not self.transcription_queue.empty():
                try:
                    self.transcription_queue.get_nowait()
                    self.transcription_queue.task_done()
                except Exception:
                    pass
            for wav_path in list(self.temp_files):
                try:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
                except Exception:
                    pass
            self.temp_files.clear()
            self.text_area.configure(state="normal")
            self.text_area.delete("1.0", "end")
            self.text_area.configure(state="normal")
            self.all_recorded_audio = []
            self._update_save_button_state()
            self._set_status("Trascrizione e registrazione resettate.")
            
        ConfirmDialog(self.root, "Conferma Reset", "Sei sicuro di voler cancellare tutta la trascrizione e registrazione correnti?", do_reset)

    def _show_flag_dropdown(self):
        x = self.lang_btn.winfo_rootx()
        y = self.lang_btn.winfo_rooty() + self.lang_btn.winfo_height() + 2
        dropdown = FlagDropdown(self.root, self.get_flag_image, self._on_language_selected)
        dropdown.open(x, y)

    def _on_language_selected(self, selected_lang):
        self.transcribe_lang = selected_lang
        lang_item = next((l for l in FlagDropdown.LANGUAGES if l["code"] == selected_lang), None)
        flag_code = lang_item["flag"] if lang_item else selected_lang.upper()
        self.lang_btn.configure(image=self.get_flag_image(flag_code))
        
        # Display WER on status bar label
        wer = lang_item["wer"] if lang_item else "---%"
        self.wer_label.configure(text=f"WER {wer}")
        
        # Color-code and populate descriptive hover tooltip based on WER value
        wer_val = None
        try:
            val_str = wer.replace("%", "").replace(">", "").replace("~", "").strip()
            wer_val = float(val_str)
        except Exception:
            pass
            
        if wer_val is not None:
            if wer_val < 10.0:
                color = "#10B981" # Emerald
                title_it, title_en = "Affidabile", "Reliable"
                desc_it = "La trascrizione è quasi perfetta. Le uniche correzioni necessarie riguardano tipicamente nomi propri, acronimi o punteggiatura complessa. Il testo è pronto all'uso con uno sforzo minimo."
                desc_en = "The transcription is nearly perfect. Only minor corrections are needed for proper names, acronyms, or complex punctuation. Ready to use with minimal effort."
            elif 10.0 <= wer_val <= 20.0:
                color = "#F59E0B" # Amber
                title_it, title_en = "Accettabile", "Acceptable"
                desc_it = "Il testo è pienamente comprensibile, ma la revisione manuale diventa un requisito obbligatorio. Il modello confonde alcuni fonemi o sbaglia le concordanze."
                desc_en = "The text is fully understandable, but manual proofreading is mandatory. The model confuses some phonemes or makes alignment errors."
            elif 20.0 < wer_val <= 40.0:
                color = "#F97316" # Orange
                title_it, title_en = "Scarso", "Poor"
                desc_it = "La qualità degrada parecchio. La trascrizione letterale richiederà una riscrittura massiccia, ma è ancora sufficiente se lo scopo è estrarre il senso generale dell'audio o fare ricerca per parole chiave."
                desc_en = "Quality degrades significantly. Literal transcription requires heavy rewriting, but is still sufficient to grasp the general meaning or perform keyword search."
            else:
                color = "#EF4444" # Red
                title_it, title_en = "Sperimentale", "Experimental"
                desc_it = "In questa fascia il modello è inutilizzabile per compiti pratici. Tende ad 'allucinare' intere frasi, ripetere loop di parole o saltare completamente l'audio."
                desc_en = "The model is unusable for practical tasks in this range. It tends to hallucinate entire phrases, loop words, or completely skip parts of the audio."
        else:
            color = "#a1a1aa"
            title_it, title_en = "Sconosciuto", "Unknown"
            desc_it, desc_en = "Tasso di errore sulle parole non disponibile.", "Word Error Rate not available."
            
        self.wer_label.configure(text_color=color)
        self.wer_tooltip.update_text({
            "it": {"title": f"{title_it} ({title_en})", "desc": desc_it},
            "en": {"title": title_en, "desc": desc_en}
        })
        
        if selected_lang == "en":
            self._set_status("Lingua: Inglese")
        elif selected_lang == "it":
            self._set_status("Lingua: Italiano")
        else:
            name = lang_item["name"].split(" (")[0] if lang_item else selected_lang.upper()
            self._set_status(f"Lingua: {name}")
        
        self._load_model_async(self.model_combo.get(), self.transcribe_lang)

    def _show_target_flag_dropdown(self):
        x = self.target_lang_btn.winfo_rootx()
        y = self.target_lang_btn.winfo_rooty() + self.target_lang_btn.winfo_height() + 2
        dropdown = FlagDropdown(self.root, self.get_flag_image, self._on_target_language_selected)
        dropdown.open(x, y)

    def _on_target_language_selected(self, selected_lang):
        old_lang = self.target_lang
        self.target_lang = selected_lang
        lang_item = next((l for l in FlagDropdown.LANGUAGES if l["code"] == selected_lang), None)
        flag_code = lang_item["flag"] if lang_item else selected_lang.upper()
        self.target_lang_btn.configure(image=self.get_flag_image(flag_code))
        if selected_lang == "en":
            self._set_status("Traduzione in: Inglese")
        elif selected_lang == "it":
            self._set_status("Traduzione in: Italiano")
        else:
            name = lang_item["name"].split(" (")[0] if lang_item else selected_lang.upper()
            self._set_status(f"Traduzione in: {name}")
        self._translate_existing_text(old_lang, selected_lang)

    def _translate_existing_text(self, old_lang, new_lang):
        text_content = self.text_area.get("1.0", "end").strip()
        if not text_content or old_lang == new_lang:
            return
        def translate_task():
            self._set_status("Traduzione in corso...")
            try:
                from deep_translator import GoogleTranslator
                lines = text_content.split("\n")
                translated_lines = []
                for line in lines:
                    if line.strip():
                        if line.strip().startswith("-------"):
                            translated_lines.append(line)
                        else:
                            translated_lines.append(GoogleTranslator(source=old_lang, target=new_lang).translate(line))
                    else:
                        translated_lines.append("")
                new_text = "\n".join(translated_lines)
                def update_ui():
                    self.text_area.configure(state="normal")
                    self.text_area.delete("1.0", "end")
                    self.text_area.insert("1.0", new_text)
                    self.text_area.mark_set("active_start", "end-1c")
                    self.text_area.configure(state="normal" if not self.is_recording else "disabled")
                    self._set_status(f"Tradotto in {new_lang.upper()}")
                self.root.after(0, update_ui)
            except Exception as e:
                self.root.after(0, self._set_status, f"Errore traduzione: {e}")
        threading.Thread(target=translate_task, daemon=True).start()

    def _show_ui_flag_dropdown(self):
        x = self.ui_lang_btn.winfo_rootx()
        y = self.ui_lang_btn.winfo_rooty() + self.ui_lang_btn.winfo_height() + 2
        dropdown = FlagDropdown(self.root, self.get_flag_image, self._on_ui_language_selected)
        dropdown.open(x, y)

    def _on_ui_language_selected(self, selected_lang):
        self._update_ui_language(selected_lang)

    def _update_ui_language(self, lang_code):
        self.ui_lang = lang_code
        lang_item = next((l for l in FlagDropdown.LANGUAGES if l["code"] == lang_code), None)
        flag_code = lang_item["flag"] if lang_item else lang_code.upper()
        self.ui_lang_btn.configure(image=self.get_flag_image(flag_code))
        if hasattr(self, "wer_tooltip"):
            self.wer_tooltip.set_language(lang_code)
        if lang_code == "en":
            self.model_label.configure(text="Transcription Engine:")
            self.dest_btn.configure(text="📂 Destination")
            self.device_label.configure(text="Audio Input:")
            self.text_label.configure(text="Transcription")
            
            if self.is_recording:
                self.start_btn.configure(text="■ Stop Transcription")
            else:
                self.start_btn.configure(text="▶ Start Transcription")
                
            if getattr(self, "is_playing", False):
                self.play_btn.configure(text="■ Stop Listening")
            else:
                self.play_btn.configure(text="🔊 Listen to Transcription")
                
            self.save_btn.configure(text="💾 Save Transcription")
            self.save_audio_btn.configure(text="🎙️ Save Audio")
            self.save_and_close_btn.configure(text="💾 Save All & Close on Finish")
            
            self.text_area.configure(state="normal")
            content = self.text_area.get("1.0", "end")
            new_content = content.replace("------- continua ", "------- continued ").replace("------- inizio ", "------- started ")
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", new_content.strip())
            self.text_area.configure(state="normal" if not self.is_recording else "disabled")
            
            self._set_status("UI Language: English")
        else:
            self.ui_lang_btn.configure(image=self.img_it)
            self.model_label.configure(text="Motore di Trascrizione:")
            self.dest_btn.configure(text="📂 Destinazione")
            self.device_label.configure(text="Ingresso Audio:")
            self.text_label.configure(text="Trascrizione")
            
            if self.is_recording:
                self.start_btn.configure(text="■ Ferma Trascrizione")
            else:
                self.start_btn.configure(text="▶ Avvia Trascrizione")
                
            if getattr(self, "is_playing", False):
                self.play_btn.configure(text="■ Ferma Ascolto")
            else:
                self.play_btn.configure(text="🔊 Ascolta Trascrizione")
                
            self.save_btn.configure(text="💾 Salva Trascrizione")
            self.save_audio_btn.configure(text="🎙️ Salva Audio")
            self.save_and_close_btn.configure(text="💾 Salva tutto e Chiudi al termine")
            
            self.text_area.configure(state="normal")
            content = self.text_area.get("1.0", "end")
            new_content = content.replace("------- continued ", "------- continua ").replace("------- started ", "------- inizio ")
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", new_content.strip())
            self.text_area.configure(state="normal" if not self.is_recording else "disabled")
            
            self._set_status("Lingua UI: Italiano")

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
                if not self.is_recording and self.audio_queue.empty():
                    self.root.after(0, self._check_pending_actions)

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
                if not self.is_recording and self.transcription_queue.empty():
                    self.root.after(0, self._check_pending_actions)

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
            if self.target_lang != self.transcribe_lang:
                try:
                    from deep_translator import GoogleTranslator
                    translated = GoogleTranslator(source=self.transcribe_lang, target=self.target_lang).translate(formatted)
                    formatted = translated
                except Exception as e:
                    print(f"Translation error: {e}")
            self.text_area.insert("active_start", formatted + " ")
        self.text_area.see("end")
        if is_final:
            self.text_area.mark_set("active_start", "insert")
        if self.is_recording:
            self.text_area.configure(state="disabled")
        else:
            self.text_area.configure(state="normal")
        self._update_save_button_state()

    def _is_active_processing(self):
        if self.is_recording:
            return True
        if not self.transcription_queue.empty() or not self.audio_queue.empty():
            return True
        return False

    def _save_all_and_close_on_finish(self):
        if self.is_recording:
            self._toggle_recording()
        self.save_and_close_on_finish = True
        self._set_status("Salvataggio e chiusura al termine...")
        if not self._is_active_processing():
            self._execute_save_all_and_close()

    def _execute_save_all_and_close(self):
        text_content = self.text_area.get("1.0", "end").strip()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if text_content:
            filepath = os.path.join(self.dest_dir, f"trascrizione_{timestamp}.txt")
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(text_content)
            except Exception:
                pass
        if self.all_recorded_audio:
            filepath_audio = os.path.join(self.dest_dir, f"registrazione_{timestamp}.wav")
            try:
                raw_bytes = b"".join(self.all_recorded_audio)
                with wave.open(filepath_audio, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(self.pa.get_sample_size(pyaudio.paInt16))
                    wf.setframerate(16000)
                    wf.writeframes(raw_bytes)
            except Exception:
                pass
        self._on_closing_forced()

    def _check_pending_actions(self):
        self._update_save_button_state()
        if self._is_active_processing():
            return
        if getattr(self, "save_and_close_on_finish", False):
            self._execute_save_all_and_close()
        elif getattr(self, "close_on_complete", False):
            self._on_closing_forced()

    def _on_closing_forced(self):
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

    def _on_closing(self):
        if self._is_active_processing():
            def do_force_close():
                self._on_closing_forced()
            def do_wait_close():
                self.close_on_complete = True
                if self.is_recording:
                    self._toggle_recording()
                self._set_status("Chiusura pianificata al termine...")
            ConfirmDialog(
                self.root, 
                "Attività in corso", 
                "La trascrizione è in corso. Chiudere subito?", 
                do_force_close,
                on_cancel=do_wait_close
            )
        else:
            self._on_closing_forced()
    def _toggle_playback(self):
        if getattr(self, "is_playing", False):
            self.is_playing = False
        else:
            self._play_and_highlight()

    def _play_and_highlight(self):
        if not self.all_recorded_audio:
            return
        self.is_playing = True
        self.play_btn.configure(text="■ Ferma Ascolto", fg_color="#ef4444", hover_color="#dc2626")
        self.save_audio_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.save_and_close_btn.configure(state="disabled")
        def play_task():
            try:
                raw_audio = b"".join(self.all_recorded_audio)
                total_bytes = len(raw_audio)
                lines = self.text_area.get("1.0", "end-1c").split("\n")
                words_ranges = []
                current_char_offset = 0
                for line in lines:
                    if not line.strip().startswith("-------"):
                        import re
                        for m in re.finditer(r'\S+', line):
                            start = current_char_offset + m.start()
                            end = current_char_offset + m.end()
                            words_ranges.append((f"1.0 + {start}c", f"1.0 + {end}c"))
                    current_char_offset += len(line) + 1
                words_count = len(words_ranges)
                if words_count == 0:
                    return
                bytes_per_word = total_bytes // words_count
                p = pyaudio.PyAudio()
                out_stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, output=True)
                chunk_size = 1024
                for i, (start, end) in enumerate(words_ranges):
                    if not self.is_playing:
                        break
                    self.root.after(0, self._highlight_word, start, end)
                    word_audio = raw_audio[i * bytes_per_word : (i + 1) * bytes_per_word]
                    for offset in range(0, len(word_audio), chunk_size):
                        if not self.is_playing:
                            break
                        out_stream.write(word_audio[offset:offset+chunk_size])
                out_stream.stop_stream()
                out_stream.close()
                p.terminate()
            except Exception as e:
                print(f"TRACER: Playback error: {e}", flush=True)
            finally:
                self.is_playing = False
                self.root.after(0, self._on_playback_finished)
        threading.Thread(target=play_task, daemon=True).start()

    def _highlight_word(self, start, end):
        self.text_area.tag_remove("highlight", "1.0", "end")
        self.text_area.tag_add("highlight", start, end)
        self.text_area.tag_config("highlight", background="#2563eb", foreground="#ffffff")

    def _on_playback_finished(self):
        self.text_area.tag_remove("highlight", "1.0", "end")
        self.play_btn.configure(text="🔊 Ascolta Trascrizione", fg_color="#18181b", hover_color="#27272a")
        self._update_save_button_state()
        self.start_btn.configure(state="normal")

if __name__ == "__main__":
    root = ctk.CTk()
    app = WhisperApp(root)
    root.mainloop()
