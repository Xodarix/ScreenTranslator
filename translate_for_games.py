from queue import Queue
import multiprocessing
import pystray
from PIL import Image, ImageFont, ImageDraw
import uuid 
import easyocr
import cv2
import numpy as np
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from tkinter import font as tkfont
import pyautogui
import pytesseract
from PIL import Image, ImageTk, ImageEnhance
import keyboard
import threading
import time
import requests
import json
import sys
import urllib.parse
import os
import pickle
from datetime import datetime
from pynput import mouse
from collections import deque

class SimpleTranslator:
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self.api_methods = {
            'deepl': self.translate_deepl,
            'microsoft': self.translate_microsoft, # <-- ДОДАНО
            'mymemory': self.translate_mymemory,
            'libre': self.translate_libre,
        }

    def translate(self, text, src='en', dest='uk'):
        selected_api = self.settings_manager.settings.get('translator_api', 'auto')

        if selected_api == 'auto':
            for api_name, api_method in self.api_methods.items():
                try:
                    if api_name == 'deepl' and not self.settings_manager.settings.get('deepl_api_key'):
                        continue
                    result = api_method(text, src, dest)
                    if result and not result.text.startswith("Помилка"):
                        return result
                except Exception as e:
                    print(f"API '{api_name}' failed: {e}")
                    continue
            return TranslationResult("Переклад недоступний")
        
        else:
            api_to_use = self.api_methods.get(selected_api)
            if not api_to_use:
                return TranslationResult(f"Помилка: Невідомий API '{selected_api}'")

            try:
                result = api_to_use(text, src, dest)
                if result and not result.text.startswith("Помилка"):
                    return result
                elif result:
                    return result
                else:
                    return TranslationResult(f"Помилка: API '{selected_api}' не повернув результат.")
            except requests.exceptions.RequestException as e:
                print(f"API '{selected_api}' connection failed: {e}")
                return TranslationResult(f"Помилка мережі при з'єднанні з '{selected_api}'.")
            except Exception as e:
                print(f"API '{selected_api}' failed: {e}")
                return TranslationResult(f"Невідома помилка з API '{selected_api}'.")

    def translate_deepl(self, text, src, dest):
        api_key = self.settings_manager.settings.get('deepl_api_key', '').strip()
        if not api_key:
            return TranslationResult("Помилка: API ключ DeepL не введено у налаштуваннях.")

        url = "https://api-free.deepl.com/v2/translate"
        headers = {
            'Authorization': f'DeepL-Auth-Key {api_key}',
            'Content-Type': 'application/json',
        }
        
        dest_lang = dest.upper()
        source_lang = src.upper()

        data = {
            'text': [text],
            'target_lang': dest_lang,
            'source_lang': source_lang
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=15)

            if response.status_code == 200:
                result = response.json()
                translated_text = result['translations'][0]['text']
                return TranslationResult(translated_text)
            elif response.status_code == 403:
                return TranslationResult("Помилка: Неправильний API ключ DeepL.")
            elif response.status_code == 456:
                return TranslationResult("Помилка: Вичерпано місячний ліміт DeepL.")
            else:
                return TranslationResult(f"Помилка DeepL: Код {response.status_code} {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"DeepL network error: {e}")
            return TranslationResult("Помилка мережі з DeepL.")
        except Exception as e:
            print(f"DeepL unknown error: {e}")
            return TranslationResult("Невідома помилка з DeepL.")
        
    def translate_microsoft(self, text, src, dest):
        api_key = self.settings_manager.settings.get('ms_translator_key', '').strip()
        region = self.settings_manager.settings.get('ms_translator_region', '').strip()

        if not api_key or not region:
            return TranslationResult("Помилка: Ключ або регіон Microsoft Translator не введено.")

        endpoint = "https://api.cognitive.microsofttranslator.com"
        path = '/translate'
        constructed_url = endpoint + path

        params = {
            'api-version': '3.0',
            'from': src,
            'to': dest
        }
        headers = {
            'Ocp-Apim-Subscription-Key': api_key,
            'Ocp-Apim-Subscription-Region': region,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
        body = [{'text': text}]

        try:
            response = requests.post(constructed_url, params=params, headers=headers, json=body, timeout=15)
            response.raise_for_status()  # Перевірка на HTTP помилки (4xx or 5xx)
            
            result = response.json()
            translated_text = result[0]['translations'][0]['text']
            return TranslationResult(translated_text)
            
        except requests.exceptions.HTTPError as e:
            error_data = e.response.json()
            error_message = error_data.get('error', {}).get('message', str(e))
            return TranslationResult(f"Помилка Microsoft Translator: {error_message}")
        except requests.exceptions.RequestException as e:
            print(f"Microsoft Translator network error: {e}")
            return TranslationResult("Помилка мережі з Microsoft Translator.")
        except Exception as e:
            print(f"Microsoft Translator unknown error: {e}")
            return TranslationResult("Невідома помилка з Microsoft Translator.")

    def translate_mymemory(self, text, src, dest):
        url = "https://api.mymemory.translated.net/get"
        params = {'q': text[:500], 'langpair': f'{src}|{dest}'}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'responseData' in data and 'translatedText' in data['responseData']:
                return TranslationResult(data['responseData']['translatedText'])
        return None

    def translate_libre(self, text, src, dest):
        try:
            url = "https://translate.argosopentech.com/translate"
            data = {'q': text, 'source': src, 'target': dest}
            response = requests.post(url, json=data, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                if 'translatedText' in result:
                    return TranslationResult(result['translatedText'])
                elif 'error' in result:
                    return TranslationResult(f"Помилка ArgosTranslate: {result['error']}")
            else:
                return TranslationResult(f"Помилка ArgosTranslate: Код {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"ArgosTranslate network error: {e}")
            return TranslationResult("Помилка мережі з ArgosTranslate")
        except Exception as e:
            print(f"ArgosTranslate unknown error: {e}")
        return None

class TranslationResult:
    def __init__(self, text):
        self.text = text

class SettingsManager:
    def __init__(self):
        self.settings_file = "translator_settings.json"
        self.presets_file = "translator_presets.json"
        self.default_settings = {
            "monitor_interval": 3, "result_alpha": 0.9,
            "result_font_size": 11, "result_theme": "blue",
            "auto_close_time": 10, "display_mode": "popup",
            "fixed_window_pos": [50, 50], "fixed_window_size": [400, 200],
            "fixed_window_pinned": True, "app_font": "Arial",
            "translator_api": "auto",
            "deepl_api_key": "",
            "ms_translator_key": "",    # <-- ДОДАНО
            "ms_translator_region": "", # <-- ДОДАНО
            "subtitle_mode": False,  # <-- ДОДАНО
            "hotkeys": {
                "select_area": "ctrl+shift+s",
                "start_monitoring": "ctrl+shift+a",
                "stop_monitoring": "ctrl+shift+x",
                "pause_monitoring": "ctrl+shift+z",  # <-- ДОДАНО
                "show_settings": "ctrl+shift+c",
                "toggle_mode": "ctrl+shift+d",
                "show_presets": "ctrl+shift+p"
            }
        }
        self.saved_presets = {}
        self.load_settings()
        self.load_presets()
    
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
                for key, value in self.default_settings.items():
                    if key not in self.settings: self.settings[key] = value
                if 'hotkeys' not in self.settings:
                    self.settings['hotkeys'] = self.default_settings['hotkeys']
                else:
                    for key, value in self.default_settings['hotkeys'].items():
                        if key not in self.settings['hotkeys']:
                            self.settings['hotkeys'][key] = value
            else: self.settings = self.default_settings.copy()
        except: self.settings = self.default_settings.copy()
    
    def save_preset(self, name, region, interval=3, description="", hotkey=None):
        self.saved_presets[name] = {
            'region': region,
            'interval': interval,
            'description': description,
            'hotkey': hotkey,
            'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'used_count': 0
        }
        self.save_presets()

    def get_preset(self, name):
        if name in self.saved_presets:
            self.saved_presets[name]['used_count'] += 1
            self.save_presets()
            return self.saved_presets[name]
        return None

    def delete_preset(self, name):
        if name in self.saved_presets:
            del self.saved_presets[name]
            self.save_presets()
    
    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e: print(f"Помилка збереження налаштувань: {e}")
    
    def load_presets(self):
        try:
            if os.path.exists(self.presets_file):
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    self.saved_presets = json.load(f)
        except: self.saved_presets = {}
    
    def save_presets(self):
        try:
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_presets, f, indent=2, ensure_ascii=False)
        except Exception as e: print(f"Помилка збереження пресетів: {e}")
    
    def get_theme_colors(self, theme):
        themes = {
            'blue': { 'bg': '#e3f2fd', 'text': '#1976d2', 'border': '#2196f3', 'error_bg': '#ffebee', 'error_text': '#d32f2f', 'error_border': '#f44336', 'accent': '#64b5f6', 'hover': '#1565c0' },
            'green': { 'bg': '#e8f5e8', 'text': '#2E7D32', 'border': '#4CAF50', 'error_bg': '#ffebee', 'error_text': '#d32f2f', 'error_border': '#f44336', 'accent': '#81c784', 'hover': '#2e7d32' },
            'dark': { 'bg': '#2e2e2e', 'text': '#ffffff', 'border': '#555555', 'error_bg': '#4a2828', 'error_text': '#ff6b6b', 'error_border': '#ff4444', 'accent': '#777777', 'hover': '#666666' }
        }
        return themes.get(theme, themes['blue'])

class ResizableFrame(tk.Frame):
    def __init__(self, parent, callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.callback = callback
        self.resizing = False
        self.resize_start_x = 0; self.resize_start_y = 0
        self.resize_start_width = 0; self.resize_start_height = 0
        self.create_resize_handles()
    
    def create_resize_handles(self):
        try: self.se_handle = tk.Frame(self, bg='#888888', cursor='bottom_right_corner')
        except tk.TclError: self.se_handle = tk.Frame(self, bg='#888888', cursor='sizing')
        self.se_handle.place(relx=1.0, rely=1.0, width=15, height=15, anchor='se')
        try: self.s_handle = tk.Frame(self, bg='#888888', cursor='bottom_side')
        except tk.TclError: self.s_handle = tk.Frame(self, bg='#888888', cursor='sb_v_double_arrow')
        self.s_handle.place(relx=0.5, rely=1.0, width=50, height=5, anchor='s')
        try: self.e_handle = tk.Frame(self, bg='#888888', cursor='right_side')
        except tk.TclError: self.e_handle = tk.Frame(self, bg='#888888', cursor='sb_h_double_arrow')
        self.e_handle.place(relx=1.0, rely=0.5, width=5, height=50, anchor='e')
        self.bind_resize_events(self.se_handle, 'se'); self.bind_resize_events(self.s_handle, 's'); self.bind_resize_events(self.e_handle, 'e')
    
    def bind_resize_events(self, handle, direction):
        handle.bind('<Button-1>', lambda e: self.start_resize(e, direction))
        handle.bind('<B1-Motion>', lambda e: self.do_resize(e, direction))
        handle.bind('<ButtonRelease-1>', self.end_resize)
    
    def start_resize(self, event, direction):
        self.resizing = True
        self.resize_direction = direction
        self.resize_start_x = event.x_root; self.resize_start_y = event.y_root
        parent_window = self.winfo_toplevel()
        self.resize_start_width = parent_window.winfo_width(); self.resize_start_height = parent_window.winfo_height()
    
    def do_resize(self, event, direction):
        if not self.resizing: return
        dx = event.x_root - self.resize_start_x; dy = event.y_root - self.resize_start_y
        parent_window = self.winfo_toplevel()
        new_width = self.resize_start_width; new_height = self.resize_start_height
        if 'e' in direction: new_width = max(200, self.resize_start_width + dx)
        if 's' in direction: new_height = max(100, self.resize_start_height + dy)
        parent_window.geometry(f"{new_width}x{new_height}")
        if self.callback: self.callback(new_width, new_height)
    
    def end_resize(self, event):
        self.resizing = False

class FixedTranslationWindow:
    def __init__(self, parent, settings_manager):
        self.parent = parent; self.settings_manager = settings_manager
        self.window = None; self.text_widget = None
        self.is_pinned = True; self.dragging = False
        self.drag_start_x = 0; self.drag_start_y = 0
        self.current_text = ""; self.resizable_frame = None
        self.app_font = self.settings_manager.settings.get('app_font', 'Arial')
        # Додайте цей рядок
        self.subtitle_mode = self.settings_manager.settings.get('subtitle_mode', False)
        
    def copy_text(self):
        if self.current_text:
            self.parent.copy_to_clipboard(self.current_text)

    def create_custom_header(self, colors, parent):
        header_frame = tk.Frame(parent, bg=colors['border'], height=28)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)
        title_label = tk.Label(header_frame, text=f"🔤", font=(self.app_font, 8, 'bold'), fg='white', bg=colors['border'])
        title_label.pack(side='left', padx=8, pady=3)
        
        # --- ПОЧАТОК ЗМІН ---
        # Додаємо віджет для індикатора статусу
        self.status_indicator_label = tk.Label(header_frame, text="🔴 ВИМКНЕНО", font=(self.app_font, 8, 'bold'), fg='white', bg=colors['border'])
        self.status_indicator_label.pack(side='left', padx=10)
        # --- КІНЕЦЬ ЗМІН ---

        btn_frame = tk.Frame(header_frame, bg=colors['border'])
        btn_frame.pack(side='right', padx=3)
        
        copy_btn = tk.Button(btn_frame, text="📋", command=self.copy_text, bg=colors['border'], activebackground=colors['hover'], fg='white', font=(self.app_font, 8), relief='flat', bd=0)
        copy_btn.pack(side='right', padx=1)
        
        # <-- ПОЧАТОК ЗМІН -->
        subtitle_icon = "📜" if self.subtitle_mode else "📝"
        self.subtitle_btn = tk.Button(btn_frame, text=subtitle_icon, command=self.toggle_subtitle_mode, bg=colors['border'], activebackground=colors['hover'], fg='white', font=(self.app_font, 10), relief='flat', bd=0)
        self.subtitle_btn.pack(side='right', padx=1)
        # <-- КІНЕЦЬ ЗМІН -->

        self.pin_btn = tk.Button(btn_frame, text="📌" if self.is_pinned else "📍", command=self.toggle_pin, bg=colors['border'], activebackground=colors['hover'], fg='white', font=(self.app_font, 8), relief='flat', bd=0)
        self.pin_btn.pack(side='right', padx=1)
        
        settings_btn = tk.Button(btn_frame, text="⚙️", command=self.show_window_settings, bg=colors['border'], activebackground=colors['hover'], fg='white', font=(self.app_font, 8), relief='flat', bd=0)
        settings_btn.pack(side='right', padx=1)
        
        close_btn = tk.Button(btn_frame, text="✕", command=self.close_window, bg='#f44336', activebackground='#d32f2f', fg='white', font=(self.app_font, 8, 'bold'), relief='flat', bd=0)
        close_btn.pack(side='right', padx=1)
        
        self.header_frame = header_frame
        title_label.bind('<Button-1>', self.start_drag); title_label.bind('<B1-Motion>', self.on_drag); title_label.bind('<ButtonRelease-1>', self.end_drag)
        header_frame.bind('<Button-1>', self.start_drag); header_frame.bind('<B1-Motion>', self.on_drag); header_frame.bind('<ButtonRelease-1>', self.end_drag)
        
    def keep_on_top(self):
        if self.window and self.window.winfo_exists():
            try:
                self.window.lift(); self.window.attributes('-topmost', True)
                self.window.after(2000, self.keep_on_top)
            except: pass
        
    def create_text_area(self, colors, parent):
        text_frame = tk.Frame(parent, bg=colors['bg'])
        text_frame.pack(fill='both', expand=True, padx=3, pady=(0, 3))
        font_size = self.settings_manager.settings['result_font_size']
        self.text_widget = tk.Text(text_frame, font=(self.app_font, font_size), bg=colors['bg'], fg=colors['text'], wrap='word', relief='flat', bd=0, highlightthickness=0, padx=10, pady=10)
        scrollbar = tk.Scrollbar(text_frame, orient='vertical', command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)
        self.text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        self.text_widget.bind("<MouseWheel>", lambda e: self.text_widget.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        
    def setup_dragging(self):
        def on_window_configure(event):
            if event.widget == self.window:
                x, y = self.window.winfo_x(), self.window.winfo_y()
                self.settings_manager.settings['fixed_window_pos'] = [x, y]
                self.settings_manager.save_settings()
        self.window.bind('<Configure>', on_window_configure)
        
    def start_drag(self, event):
        if not self.is_pinned: return
        self.dragging = True
        self.drag_start_x = event.x_root; self.drag_start_y = event.y_root
        
    def on_drag(self, event):
        if not self.dragging or not self.is_pinned: return
        dx = event.x_root - self.drag_start_x; dy = event.y_root - self.drag_start_y
        x = self.window.winfo_x() + dx; y = self.window.winfo_y() + dy
        self.window.geometry(f"+{x}+{y}")
        self.drag_start_x = event.x_root; self.drag_start_y = event.y_root
        
    def end_drag(self, event):
        self.dragging = False
        
    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self.settings_manager.settings['fixed_window_pinned'] = self.is_pinned
        self.settings_manager.save_settings()
        self.pin_btn.config(text="📌" if self.is_pinned else "📍")
        self.window.attributes('-topmost', self.is_pinned)
        self.parent.update_status("📌 Фіксоване вікно закріплено" if self.is_pinned else "📍 Фіксоване вікно відкріплено")
            
    def toggle_subtitle_mode(self):
        self.subtitle_mode = not self.subtitle_mode
        self.settings_manager.settings['subtitle_mode'] = self.subtitle_mode
        self.settings_manager.save_settings()

        self.subtitle_btn.config(text="📜" if self.subtitle_mode else "📝")
        
        # Очищуємо вікно і виводимо повідомлення про зміну режиму
        self.text_widget.config(state='normal')
        self.text_widget.delete('1.0', 'end')
        
        if self.subtitle_mode:
            status_message = "💬 Режим субтитрів УВІМКНЕНО"
            self.text_widget.insert('1.0', "[Історія діалогу буде з'являтися тут]")
        else:
            status_message = "📝 Режим субтитрів ВИМКНЕНО"
            self.text_widget.insert('1.0', "[Вікно буде очищуватись]")
        
        self.text_widget.config(state='disabled')
        self.parent.update_status(status_message)        
            
    def show_window_settings(self):
        settings_dialog = tk.Toplevel()
        settings_dialog.title("Налаштування фіксованого вікна")
        settings_dialog.geometry("480x350+300+300")
        settings_dialog.attributes('-topmost', True); settings_dialog.configure(bg='#f0f0f0')
        header = tk.Frame(settings_dialog, bg='#2196f3', height=40); header.pack(fill='x'); header.pack_propagate(False)
        tk.Label(header, text="⚙️ Налаштування вікна", font=(self.app_font, 12, 'bold'), fg='white', bg='#2196f3').pack(pady=8)
        content = tk.Frame(settings_dialog, bg='#f0f0f0'); content.pack(fill='both', expand=True, padx=15, pady=15)
        transparency_frame = tk.LabelFrame(content, text="👁️ Прозорість", font=(self.app_font, 10, 'bold'), bg='#f0f0f0')
        transparency_frame.pack(fill='x', pady=(0, 10))
        alpha_var = tk.DoubleVar(value=self.settings_manager.settings['result_alpha'])
        alpha_scale = tk.Scale(transparency_frame, from_=0.3, to=1.0, resolution=0.1, orient='horizontal', variable=alpha_var, length=280, bg='#f0f0f0')
        alpha_scale.pack(pady=8, padx=10)
        font_frame = tk.LabelFrame(content, text="🔤 Розмір шрифту", font=(self.app_font, 10, 'bold'), bg='#f0f0f0')
        font_frame.pack(fill='x', pady=(0, 10))
        font_var = tk.IntVar(value=self.settings_manager.settings['result_font_size'])
        font_scale = tk.Scale(font_frame, from_=8, to=20, orient='horizontal', variable=font_var, length=280, bg='#f0f0f0')
        font_scale.pack(pady=8, padx=10)
        btn_frame = tk.Frame(content, bg='#f0f0f0'); btn_frame.pack(pady=20)
        def apply_settings():
            self.settings_manager.settings['result_alpha'] = alpha_var.get()
            self.settings_manager.settings['result_font_size'] = font_var.get()
            self.settings_manager.save_settings()
            self.window.attributes('-alpha', alpha_var.get())
            self.text_widget.config(font=(self.app_font, font_var.get()))
            settings_dialog.destroy()
        apply_btn = tk.Button(btn_frame, text="✅ Застосувати", command=apply_settings, bg='#4CAF50', fg='white', font=(self.app_font, 10, 'bold'), padx=20, pady=8, relief='flat')
        apply_btn.pack(side='left', padx=5)
        cancel_btn = tk.Button(btn_frame, text="❌ Скасувати", command=settings_dialog.destroy, bg='#f44336', fg='white', font=(self.app_font, 10, 'bold'), padx=20, pady=8, relief='flat')
        cancel_btn.pack(side='left', padx=5)
        
    def update_text(self, text):
        if not self.text_widget: return
        
        self.text_widget.config(state='normal')
        
        if self.subtitle_mode:
            # Режим субтитрів: додаємо текст
            current_content = self.text_widget.get("1.0", "end-1c").strip()
            if current_content:
                self.text_widget.insert('end', f"\n\n{text}")
            else:
                self.text_widget.insert('end', text)
            self.text_widget.see('end') # Автоматична прокрутка донизу
        else:
            # Стандартний режим: замінюємо текст
            self.text_widget.delete('1.0', 'end')
            self.text_widget.insert('1.0', text)
        
        self.current_text = self.text_widget.get("1.0", "end-1c")
        self.text_widget.config(state='disabled')
        
    def update_monitoring_status(self, is_monitoring, is_paused):
        if not self.window or not self.window.winfo_exists():
            return

        status_config = {
            'active': {'text': "🟢 АКТИВНИЙ", 'color': '#4CAF50'},
            'paused': {'text': "⏸️ ПАУЗА", 'color': '#ff9800'},
            'off':    {'text': "🔴 ВИМКНЕНО", 'color': '#6c757d'} # Нейтральний сірий
        }

        if is_monitoring and not is_paused:
            current_status = 'active'
        elif is_monitoring and is_paused:
            current_status = 'paused'
        else:
            current_status = 'off'

        config = status_config[current_status]
        color = config['color']

        # Оновлюємо колір рамки та всіх елементів у заголовку
        self.window.config(bg=color)
        self.header_frame.config(bg=color)
        for widget in self.header_frame.winfo_children():
            widget.config(bg=color)
            if isinstance(widget, tk.Frame): # Для рамки з кнопками
                 for btn in widget.winfo_children():
                    btn.config(bg=color)

        # Оновлюємо текст індикатора
        self.status_indicator_label.config(text=config['text'])
        
    def close_window(self):
        if self.window:
            self.settings_manager.settings['display_mode'] = 'popup'
            self.settings_manager.save_settings()
            self.window.destroy()
            self.window = None
            self.parent.fixed_window = None
            self.parent.update_status("📱 Режим відображення: спливаюче вікно")
            
    def is_visible(self):
        return self.window is not None and self.window.winfo_exists()
    
    def on_window_resize(self, width, height):
        self.settings_manager.settings['fixed_window_size'] = [width, height]
        self.settings_manager.save_settings()

    def create_window(self, is_monitoring_initial=False, is_paused_initial=False):
        if self.window: self.window.destroy()
        self.window = tk.Toplevel()
        self.window.wm_overrideredirect(True)
        pos_x, pos_y = self.settings_manager.settings['fixed_window_pos']
        width, height = self.settings_manager.settings['fixed_window_size']
        self.window.geometry(f"{width}x{height}+{pos_x}+{pos_y}")
        self.window.attributes('-topmost', True); self.window.lift(); self.window.focus_force()
        
        alpha = self.settings_manager.settings['result_alpha']
        self.window.attributes('-alpha', alpha)
        
        colors = self.settings_manager.get_theme_colors(self.settings_manager.settings['result_theme'])
        self.window.configure(bg=colors['border'])
        
        main_frame = tk.Frame(self.window, bg=colors['bg'])
        main_frame.pack(fill='both', expand=True, padx=2, pady=2)

        self.resizable_frame = ResizableFrame(main_frame, callback=self.on_window_resize, bg=colors['bg'])
        self.resizable_frame.pack(fill='both', expand=True)
        content_parent = self.resizable_frame

        self.create_custom_header(colors, content_parent)
        self.create_text_area(colors, content_parent)
        self.setup_dragging()
        self.update_text("Фіксоване вікно готове!")
        self.keep_on_top()
        
        # Встановлюємо початковий статус, переданий при створенні
        self.update_monitoring_status(is_monitoring_initial, is_paused_initial)

class ScreenTranslator:
    def __init__(self, root):
        self.root = root
        self.status_queue = Queue()
        self.ocr_reader = None

        # --- Створюємо тимчасовий інтерфейс завантаження ---
        self.root.overrideredirect(True)
        width, height = 450, 200
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        splash_frame = tk.Frame(self.root, bg='#2196f3', relief='solid', bd=1)
        splash_frame.pack(fill='both', expand=True)
        
        tk.Label(splash_frame, text="Screen Translator", font=("Arial", 24, "bold"), fg="white", bg='#2196f3').pack(pady=(30, 10))
        self.splash_status_label = tk.Label(splash_frame, text="Ініціалізація...", font=("Arial", 11), fg="white", bg='#2196f3')
        self.splash_status_label.pack(pady=5)
        
        progress = ttk.Progressbar(splash_frame, orient='horizontal', length=300, mode='indeterminate')
        progress.pack(pady=(10, 30))
        progress.start(10)
        # ---------------------------------------------------

        # Ініціалізуємо інші змінні, як і раніше
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.1
        self.settings_manager = SettingsManager()
        self.translator = SimpleTranslator(self.settings_manager)
        self.app_font = self.settings_manager.settings.get('app_font', 'Arial')
        
        self.status_window = self.root # Тепер status_window - це наше головне вікно
        self.tray_icon = None
        # ... та інші змінні ...
        self.canvas = None; self.start_x = None; self.start_y = None; self.rect = None; self.selecting = False; self.selection_window = None; self.result_window = None; self.status_label = None; self.monitor_label = None; self.settings_window = None; self.fixed_window = None; self.mouse_listener = None; self.monitoring = False; self.monitor_region = None; self.monitoring_paused = False; self.monitor_thread = None; self.last_translated_text = ""; self.translation_history = deque(maxlen=20); self.hotkey_entries = {}
        
    def initialize_ocr(self):
        try:
            self.status_queue.put("Завантаження моделі EasyOCR...")
            self.ocr_reader = easyocr.Reader(['en']) 
            self.status_queue.put("Модель EasyOCR успішно завантажено.")
        except Exception as e:
            messagebox.showerror("Помилка EasyOCR", f"Не вдалося ініціалізувати EasyOCR: {e}\nПеревірте інтернет-з'єднання для першого завантаження моделей.")
            # Повідомляємо головний потік про помилку
            self.status_queue.put("error")

    def copy_to_clipboard(self, text):
        try:
            self.status_window.clipboard_clear()
            self.status_window.clipboard_append(text)
            self.update_status("✅ Текст скопійовано в буфер обміну!")
        except tk.TclError:
            self.update_status("❌ Помилка: не вдалося отримати доступ до буфера обміну.")

    def create_status_window(self):
        self.status_window.title("Screen Translator v0.1 by Xodarix&AI")
        self.status_window.minsize(640, 400)
        self.status_window.resizable(True, True)
        self.status_window.attributes('-topmost', True)
        self.status_window.configure(bg='#f8f9fa')
        
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=[25, 8], font=(self.app_font, 10))

        notebook = ttk.Notebook(self.status_window, style='TNotebook')
        notebook.pack(pady=10, padx=10, fill="both", expand=True)

        control_tab = tk.Frame(notebook, bg='#f8f9fa')
        history_tab = tk.Frame(notebook, bg='#f8f9fa')
        notebook.add(control_tab, text='⚙️ Керування')
        notebook.add(history_tab, text='📖 Історія')

        header_frame = tk.Frame(control_tab, bg='#2196f3', height=45)
        header_frame.pack(fill='x', expand=False)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="🎮 Screen Translator v0.1 by Xodarix&AI", font=(self.app_font, 12, 'bold'), fg='white', bg='#2196f3')
        title_label.pack(pady=8)
        
        content_frame = tk.Frame(control_tab, bg='#f8f9fa')
        content_frame.pack(fill='both', expand=True, padx=15, pady=10)
        
        status_frame = tk.LabelFrame(content_frame, text="📊 Статус", font=(self.app_font, 9, 'bold'), bg='#f8f9fa')
        status_frame.pack(fill='x', pady=(0, 8))
        
        self.status_label = tk.Label(status_frame, text="✅ Готовий до роботи!", font=(self.app_font, 12), justify='left', bg='#f8f9fa', fg='#2e7d32')
        self.status_label.pack(pady=8, padx=10, fill='x', expand=True)
        
        indicators_frame = tk.Frame(content_frame, bg='#f8f9fa')
        indicators_frame.pack(fill='x', pady=(0, 8))
        
        monitor_frame = tk.Frame(indicators_frame, bg='#fff', relief='solid', bd=1)
        monitor_frame.pack(side='left', fill='x', expand=True, padx=(0, 5))
        
        self.monitor_label = tk.Label(monitor_frame, text="🔴 Моніторинг: ВИМКНЕНО", font=(self.app_font, 9, 'bold'), fg='#d32f2f', bg='#fff')
        self.monitor_label.pack(pady=5)
        
        display_frame = tk.Frame(indicators_frame, bg='#fff', relief='solid', bd=1)
        display_frame.pack(side='right', fill='x', expand=True, padx=(5, 0))
        
        display_mode = self.settings_manager.settings['display_mode']
        mode_text = "🖥️ Фіксоване вікно" if display_mode == 'fixed' else "📱 Спливаюче вікно"
        self.display_mode_label = tk.Label(display_frame, text=f"Режим: {mode_text}", font=(self.app_font, 9, 'bold'), fg='#1976d2', bg='#fff')
        self.display_mode_label.pack(pady=5)
        
        actions_frame = tk.LabelFrame(content_frame, text="⚡ Швидкі дії", font=(self.app_font, 9, 'bold'), bg='#f8f9fa')
        actions_frame.pack(fill='x')
        
        btn_frame = tk.Frame(actions_frame, bg='#f8f9fa')
        btn_frame.pack(pady=8, fill='x')
        
        btn_frame.columnconfigure(0, weight=1); btn_frame.columnconfigure(1, weight=1);
        btn_frame.columnconfigure(2, weight=1); btn_frame.columnconfigure(3, weight=1)

        self.create_action_button(btn_frame, "⚙️", "Налаштування", self.show_settings, column=0)
        self.create_action_button(btn_frame, "🔄", "Режим", self.toggle_display_mode, column=1)
        self.create_action_button(btn_frame, "📋", "Пресети", self.show_presets_manager, column=2)
        self.create_action_button(btn_frame, "❌", "Вихід", self.quit_application, column=3)
        
        history_main_frame = tk.Frame(history_tab, bg='#f8f9fa')
        history_main_frame.pack(fill='both', expand=True, padx=15, pady=15)
        
        tree_frame = tk.Frame(history_main_frame)
        tree_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('original', 'translated')
        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
        self.history_tree.heading('original', text='Оригінал')
        self.history_tree.heading('translated', text='Переклад')
        self.history_tree.column('original', width=250)
        self.history_tree.column('translated', width=250)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        
        self.history_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.history_tree.bind("<Double-1>", self.copy_from_history)
        self.history_context_menu = tk.Menu(self.status_window, tearoff=0)
        self.history_context_menu.add_command(label="Копіювати оригінал", command=lambda: self.copy_from_history(event=None, part='original'))
        self.history_context_menu.add_command(label="Копіювати переклад", command=lambda: self.copy_from_history(event=None, part='translated'))
        self.history_tree.bind("<Button-3>", self.show_history_context_menu)

        clear_btn = tk.Button(history_main_frame, text="Очистити історію", command=self.clear_history, bg='#f44336', fg='white', relief='flat', font=(self.app_font, 10, 'bold'), padx=10, pady=5)
        clear_btn.pack()

    def copy_from_history(self, event, part='translated'):
        selected_item = self.history_tree.focus()
        if not selected_item: return
        
        item_values = self.history_tree.item(selected_item, 'values')
        if part == 'original' and len(item_values) > 0:
            self.copy_to_clipboard(item_values[0])
        elif part == 'translated' and len(item_values) > 1:
            self.copy_to_clipboard(item_values[1])

    def show_history_context_menu(self, event):
        selected_item = self.history_tree.identify_row(event.y)
        if selected_item:
            self.history_tree.focus(selected_item)
            self.history_context_menu.post(event.x_root, event.y_root)

    def update_history_tab(self):
        if not hasattr(self, 'history_tree'): return
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        for original, translated in reversed(self.translation_history):
            self.history_tree.insert('', 'end', values=(original, translated))

    def clear_history(self):
        if messagebox.askyesno("Підтвердження", "Очистити всю історію перекладів?"):
            self.translation_history.clear()
            self.update_history_tab()
            self.update_status("🧹 Історію очищено.")

    def add_to_history(self, original, translated):
        self.translation_history.append((original.strip(), translated.strip()))
        self.update_history_tab()

    def create_action_button(self, parent, icon, text, command, column):
        color_map = { 'Налаштування': '#2196F3', 'Режим': '#9C27B0', 'Пресети': '#4CAF50', 'Вихід': '#f44336' }
        color = color_map.get(text, '#555555')
        btn = tk.Button(parent, text=f"{icon}\n{text}", command=command, bg=color, fg='white', font=(self.app_font, 8, 'bold'), height=2, relief='flat', bd=0, padx=10, pady=5)
        btn.grid(row=0, column=column, padx=5, sticky="ew")
        
    def update_status(self, message):
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.config(text=message)
        print(f"Status: {message}")

    def start_region_monitoring(self):
        self._force_fixed_window_mode()
        self.monitoring = True
        self.monitoring_paused = False
        
        # --- ВИПРАВЛЕННЯ ТУТ ---
        # Визначаємо змінну 'interval', щоб вона була доступна для внутрішніх функцій
        interval = self.settings_manager.settings.get('monitor_interval', 3)

        self.update_status(f"🔍 Моніторинг активний (інтервал: {interval}с)")
        
        def monitor_loop():
            last_text = ""
            while self.monitoring and self.monitor_region:
                if self.monitoring_paused:
                    time.sleep(1) # Зменшуємо навантаження на ЦП під час паузи
                    continue
                try:
                    screenshot = pyautogui.screenshot(region=self.monitor_region)
                    # ... (тут ваш код розпізнавання, він без змін)
                    processed_image = self.enhance_image(screenshot)
                    screenshot_np = np.array(screenshot)
                    results = self.ocr_reader.readtext(screenshot_np)
                    text = ' '.join([res[1] for res in results])

                    if text and text != last_text:
                        last_text = text
                        translated = self.translator.translate(text, src='en', dest='uk').text
                        if not translated.startswith("Помилка"):
                            self.add_to_history(text, translated)
                        self.show_result_with_settings(translated, is_monitoring=True)
                    
                    time.sleep(interval) # Тепер ця змінна доступна
                except Exception as e:
                    print(f"Помилка моніторингу: {e}")
                    time.sleep(interval) # І тут також
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        self.monitoring = False
        self.monitoring_paused = False  # <-- ДОДАНО
        self.monitor_region = None
        self.update_status("⏹️ Моніторинг зупинено")
        self.status_window.after(0, self.close_result_window)

    def toggle_pause_monitoring(self):
        if not self.monitoring:
            self.update_status("⚠️ Моніторинг не активний, нічого призупиняти.")
            return

        self.monitoring_paused = not self.monitoring_paused

        if self.monitoring_paused:
            self.update_status("⏸️ Моніторинг призупинено.")
        else:
            self.update_status("▶️ Моніторинг відновлено.")
        # --- КІНЕЦЬ БЛОКУ ---

    def process_selection(self, x1, y1, x2, y2):
        try:
            self.update_status("📷 Захоплення скріншоту...")
            time.sleep(0.5)
            
            try:
                screenshot = pyautogui.screenshot(region=(x1, y1, x2-x1, y2-y1))
            except Exception:
                full_screenshot = pyautogui.screenshot()
                screenshot = full_screenshot.crop((x1, y1, x2, y2))
            
            screenshot = self.enhance_image(screenshot)
            self.update_status("🔍 Розпізнавання тексту...")
            
            # Конвертуємо зображення Pillow у формат, зрозумілий для OpenCV/EasyOCR
            screenshot_np = np.array(screenshot)
            # EasyOCR повертає список результатів, де кожен елемент — це [координати, текст, впевненість]
            results = self.ocr_reader.readtext(screenshot_np)
            # Об'єднуємо всі знайдені текстові фрагменти в один рядок
            text = ' '.join([res[1] for res in results])
            
            if not text or len(text.strip()) < 2:
                self.show_result_with_settings("Текст не знайдено або він нечіткий.")
                return
                
            self.update_status("🔄 Переклад тексту...")
            
            translated = self.translator.translate(text, src='en', dest='uk')
            translated_text = translated.text
            
            if not translated_text.startswith("Помилка"):
                self.add_to_history(text, translated_text)

            self.show_result_with_settings(translated_text)
            
        except Exception as e:
            error_message = f"Сталася помилка: {str(e)}"
            self.show_result_with_settings(error_message)
            print(error_message)

    def show_result_with_settings(self, translated_text, is_monitoring=False, is_test=False):
        display_mode = self.settings_manager.settings['display_mode']
        
        if display_mode == 'fixed' and not is_test:
            if not self.fixed_window or not self.fixed_window.is_visible():
                if not self.fixed_window:
                    self.fixed_window = FixedTranslationWindow(self, self.settings_manager)
                self.fixed_window.create_window()
            self.fixed_window.update_text(translated_text)
            return
        
        try:
            self.close_result_window() 
                
            self.result_window = tk.Toplevel()
            self.result_window.wm_overrideredirect(True)
            self.result_window.attributes('-topmost', True)
            
            alpha = self.settings_manager.settings['result_alpha']
            self.result_window.attributes('-alpha', alpha)
            
            theme = self.settings_manager.settings['result_theme']
            colors = self.settings_manager.get_theme_colors(theme)
            
            is_error = "Помилка" in translated_text or "не знайдено" in translated_text
            
            bg_color = colors['error_bg'] if is_error else colors['bg']
            text_color = colors['error_text'] if is_error else colors['text']
            border_color = colors['error_border'] if is_error else colors['border']
            
            main_frame = tk.Frame(self.result_window, bg=border_color, padx=3, pady=3)
            main_frame.pack()
            
            inner_frame = tk.Frame(main_frame, bg=bg_color)
            inner_frame.pack()
            
            text_frame = tk.Frame(inner_frame, bg=bg_color, padx=15, pady=10)
            text_frame.pack()
            
            copy_btn = tk.Button(inner_frame, text="📋", command=lambda: self.copy_to_clipboard(translated_text), 
                                 bg=bg_color, fg=text_color, relief='flat', bd=0, font=(self.app_font, 8))
            copy_btn.place(relx=1.0, rely=0, anchor='ne', x=-5, y=5)
            
            font_size = self.settings_manager.settings['result_font_size']
            current_font = self.settings_manager.settings.get('app_font', 'Arial')
            
            text_widget = tk.Label(
                text_frame,
                text=translated_text,
                font=(current_font, font_size, 'bold'),
                bg=bg_color,
                fg=text_color,
                justify='left',
                wraplength=400
            )
            text_widget.pack()
            
            self.result_window.update_idletasks()
            mouse_x, mouse_y = pyautogui.position()
            w, h = self.result_window.winfo_reqwidth(), self.result_window.winfo_reqheight()
            sw, sh = self.result_window.winfo_screenwidth(), self.result_window.winfo_screenheight()
            x = mouse_x + 20 if mouse_x + w + 20 < sw else mouse_x - w - 20
            y = mouse_y + 20 if mouse_y + h + 20 < sh else mouse_y - h - 20
            self.result_window.geometry(f"+{max(0, x)}+{max(0, y)}")
            
            if not is_monitoring:
                self.start_mouse_listener_for_popup()
                auto_close_time = self.settings_manager.settings.get('auto_close_time', 10) * 1000
                self.result_window.after(auto_close_time, self.close_result_window)
            
        except Exception as e:
            print(f"Помилка відображення результату: {e}")
            self.update_status(f"❌ Помилка відображення: {e}")

    def close_result_window(self):
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        if self.result_window:
            try:
                self.result_window.destroy()
                self.result_window = None
            except: pass

    def setup_hotkeys(self):
        try:
            keyboard._hooks.clear()
            time.sleep(0.1)
            
            main_hotkeys = self.settings_manager.settings.get('hotkeys', {})
            callbacks = {
                "select_area": self.start_selection,
                "start_monitoring": self.start_auto_monitoring,
                "stop_monitoring": self.stop_monitoring,
                "pause_monitoring": self.toggle_pause_monitoring, # <-- ДОДАНО
                "show_settings": self.show_settings,
                "toggle_mode": self.toggle_display_mode,
                "show_presets": self.show_presets_manager,
            }
            for action, callback in callbacks.items():
                hotkey_str = main_hotkeys.get(action)
                if hotkey_str:
                    keyboard.add_hotkey(hotkey_str, callback, suppress=False)

            for name, data in self.settings_manager.saved_presets.items():
                hotkey = data.get('hotkey')
                if hotkey:
                    keyboard.add_hotkey(hotkey, lambda n=name: self.use_preset_by_name(n), suppress=False)

            print("Гарячі клавіші успішно оновлено.")
            
        except Exception as e:
            self.update_status(f"⚠️ Помилка оновлення гарячих клавіш: {e}")
            print(f"⚠️ Помилка оновлення гарячих клавіш: {e}")

    def use_preset_by_name(self, name):
        self._force_fixed_window_mode()
        
        preset_data = self.settings_manager.get_preset(name)
        if preset_data:
            self.monitor_region = preset_data['region']
            self.settings_manager.settings['monitor_interval'] = preset_data.get('interval', 3)
            self.settings_manager.save_settings()
            
            self.start_region_monitoring()
            self.update_status(f"⚡ Запущено пресет '{name}'")
        else:
            self.update_status(f"❌ Не вдалося знайти пресет '{name}'")

    def quit_application(self):
        if messagebox.askyesno("Підтвердження", "Закрити Screen Translator?"):
            self.monitoring = False
            
            if self.tray_icon:
                self.tray_icon.stop()

            if self.fixed_window: self.fixed_window.close_window()
            if self.mouse_listener: self.mouse_listener.stop()
            self.status_window.quit()
            self.status_window.destroy()

    def _build_main_ui(self):
        # Очищуємо вікно від елементів завантаження
        for widget in self.root.winfo_children():
            widget.destroy()

        # Повертаємо вікну нормальний вигляд
        self.root.overrideredirect(False)
        
        # Запускаємо всі ті функції, що були раніше в __init__
        self.create_status_window() # Цей метод створює основний інтерфейс
        self.setup_hotkeys()
        self.status_window.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self._ui_update_loop()
        threading.Thread(target=self.setup_tray_icon, daemon=True).start()
        self.update_status("✅ Програма готова до роботи!")
    
    def _ui_update_loop(self):
        # Ця функція буде постійно перевіряти стан і оновлювати UI
        
        # Оновлення індикатора в головному вікні
        if self.monitor_label:
            if self.monitoring and not self.monitoring_paused:
                self.monitor_label.config(text="🟢 Моніторинг: АКТИВНИЙ", fg='#4CAF50')
            elif self.monitoring and self.monitoring_paused:
                self.monitor_label.config(text="⏸️ Моніторинг: ПАУЗА", fg='#ff9800')
            else:
                self.monitor_label.config(text="🔴 Моніторинг: ВИМКНЕНО", fg='#d32f2f')

        # Оновлення індикатора у фіксованому вікні
        if self.fixed_window and self.fixed_window.is_visible():
            self.fixed_window.update_monitoring_status(self.monitoring, self.monitoring_paused)
            
        # Запланувати наступний виклик цієї ж функції
        self.status_window.after(250, self._ui_update_loop) # Оновлюється 4 рази на секунду
    
    # --- НОВІ МЕТОДИ ДЛЯ РОБОТИ З СИСТЕМНИМ ТРЕЄМ ---
    def create_tray_image(self):
        # Створюємо просте зображення для іконки програмно
        width = 64
        height = 64
        color1 = (0, 0, 0, 0) # Прозорий фон
        color2 = (255, 255, 255, 255) # Білий текст
        image = Image.new('RGBA', (width, height), color1)

        try:
            # Спробуємо використати стандартний шрифт
            font = ImageFont.truetype("arial.ttf", 32)
        except IOError:
            # Якщо не знайдено, використовуємо шрифт за замовчуванням
            font = ImageFont.load_default()

        draw = ImageDraw.Draw(image)
        # Малюємо фон та текст 'ST'
        draw.rectangle([8, 8, width-8, height-8], fill=(50, 150, 255, 180))
        draw.text((16, 14), "ST", fill=color2, font=font)
        return image

    def setup_tray_icon(self):
        image = self.create_tray_image()
        
        # Функції для динамічного стану меню
        def is_monitoring_running(item):
            return self.monitoring
        
        def is_monitoring_off(item):
            return not self.monitoring

        # Створюємо більш функціональне меню
        menu = pystray.Menu(
            pystray.MenuItem('Показати', self.show_from_tray, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Виділити область (разово)', self.start_selection),
            pystray.MenuItem('Почати моніторинг', self.start_auto_monitoring, enabled=is_monitoring_off),
            pystray.MenuItem('Пауза / Відновити', self.toggle_pause_monitoring, enabled=is_monitoring_running),
            pystray.MenuItem('Зупинити моніторинг', self.stop_monitoring, enabled=is_monitoring_running),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Вихід', self.quit_application_from_tray)
        )

        self.tray_icon = pystray.Icon("ScreenTranslator", image, "Screen Translator", menu)
        self.tray_icon.run()

    def hide_to_tray(self):
        self.status_window.withdraw()
        self.update_status("Програма згорнута в системний трей.")

    def show_from_tray(self):
        self.status_window.deiconify()
        self.status_window.lift()

    def quit_application_from_tray(self):
        self.monitoring = False
        if self.tray_icon:
            self.tray_icon.stop()
        if self.fixed_window: self.fixed_window.close_window()
        self.status_window.quit()
        self.status_window.destroy()

    def darken_color(self, color):
        color_map = {'#2196F3': '#1565c0', '#9C27B0': '#7b1fa2', '#4CAF50': '#388e3c', '#f44336': '#d32f2f'}
        return color_map.get(color, color)

    def start_selection(self):
        if self.selecting:
            return
        self.selecting = True
        self.create_selection_window()

    def create_selection_window(self):
        self.selection_window = tk.Toplevel()
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-topmost', True)
        self.selection_window.attributes('-alpha', 0.3)
        self.selection_window.configure(bg='black')
        
        try:
            self.selection_window.wm_attributes("-disabled", 0)
            self.selection_window.wm_attributes("-toolwindow", 1)
        except: pass
        
        self.selection_window.focus_force(); self.selection_window.grab_set()
        
        self.canvas = tk.Canvas(self.selection_window, highlightthickness=0, bg='black', cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.selection_window.bind('<Escape>', self.cancel_selection)
        
        screen_width = self.selection_window.winfo_screenwidth()
        
        if hasattr(self, '_selecting_for_preset') and self._selecting_for_preset:
            instruction_text = "🎯 ВИБІР ОБЛАСТІ ДЛЯ ПРЕСЕТУ: Виділіть область | ESC - скасувати"
            color = 'orange'
        else:
            instruction_text = "Натисніть і перетягніть для виділення області | ESC - скасувати"
            color = 'white'
        
        self.canvas.create_text(
            screen_width // 2, 50,
            text=instruction_text,
            fill=color,
            font=(self.app_font, 16, 'bold')
        )
    
    def on_click(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = None
        
    def on_drag(self, event):
        if self.rect:
            self.canvas.delete(self.rect)
            
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline='#ff0066', width=3
        )
        
        width = abs(event.x - self.start_x)
        height = abs(event.y - self.start_y)
        size_text = f"{width}x{height}"
        
        if hasattr(self, 'size_text_id'):
            self.canvas.delete(self.size_text_id)
            
        self.size_text_id = self.canvas.create_text(
            event.x + 10, event.y - 10,
            text=size_text,
            fill='yellow',
            font=(self.app_font, 12),
            anchor='w'
        )

    def on_release(self, event):
        if self.start_x is None or self.start_y is None:
            return
            
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        
        if (x2 - x1) < 10 or (y2 - y1) < 10:
            self.update_status("Область занадто мала, спробуйте ще раз")
            self.close_selection_window()
            return
        
        self.close_selection_window()
        
        if hasattr(self, '_selecting_for_preset') and self._selecting_for_preset:
            self.selected_region_for_preset = (x1, y1, x2-x1, y2-y1)
            self.region_display.config(text=f"({x1},{y1},{x2-x1},{y2-y1})")
            self._selecting_for_preset = False
            self.update_status("✅ Область для пресету вибрано")
            return
        
        if hasattr(self, '_auto_monitoring_requested') and self._auto_monitoring_requested:
            self.monitor_region = (x1, y1, x2-x1, y2-y1)
            self.start_region_monitoring()
            self._auto_monitoring_requested = False
        else:
            threading.Thread(target=self.process_selection, 
                            args=(x1, y1, x2, y2), daemon=True).start()

    def close_selection_window(self):
        if self.selection_window:
            self.selection_window.destroy(); self.selection_window = None
        self.selecting = False; self.start_x = None; self.start_y = None

    def cancel_selection(self, event=None):
        if self.selecting:
            self.close_selection_window()
            self.update_status("Виділення скасовано")
    
    def enhance_image(self, image):
        try:
            # Конвертуємо зображення з Pillow у формат OpenCV
            open_cv_image = np.array(image.convert('RGB'))
            open_cv_image = open_cv_image[:, :, ::-1].copy()

            height, width, _ = open_cv_image.shape
            
            # Якщо зображення занадто мале, трохи збільшимо його
            if height < 100:
                scale_factor = 2
                new_size = (width * scale_factor, height * scale_factor)
                resized = cv2.resize(open_cv_image, new_size, interpolation=cv2.INTER_LANCZOS4)
                return resized
            
            return open_cv_image # Повертаємо кольорове зображення
            
        except Exception as e:
            print(f"Помилка покращення зображення: {e}")
            return image
            
    def start_mouse_listener_for_popup(self):
        def on_click(x, y, button, pressed):
            if not pressed: return
            try:
                if self.result_window and self.result_window.winfo_exists():
                    win_x, win_y = self.result_window.winfo_x(), self.result_window.winfo_y()
                    win_w, win_h = self.result_window.winfo_width(), self.result_window.winfo_height()
                    if not (win_x <= x < win_x + win_w and win_y <= y < win_y + win_h):
                        self.close_result_window()
            except: self.close_result_window()
        if self.mouse_listener: self.mouse_listener.stop()
        self.mouse_listener = mouse.Listener(on_click=on_click)
        self.mouse_listener.start()
    
    def toggle_display_mode(self):
        current_mode = self.settings_manager.settings.get('display_mode', 'popup')
        
        if current_mode == 'popup':
            self.settings_manager.settings['display_mode'] = 'fixed'
            self.settings_manager.save_settings()
            
            if not self.fixed_window:
                self.fixed_window = FixedTranslationWindow(self, self.settings_manager)
            if not self.fixed_window.is_visible():
                # Створюємо вікно, одразу передаючи йому статус "АКТИВНИЙ"
                self.fixed_window.create_window(is_monitoring_initial=True, is_paused_initial=False)
            
            self.update_status("🖥️ Режим відображення: фіксоване вікно")
            if hasattr(self, 'display_mode_label'):
                self.display_mode_label.config(text="Режим: 🖥️ Фіксоване вікно")
        else:
            self.settings_manager.settings['display_mode'] = 'popup'
            self.settings_manager.save_settings()
            
            if self.fixed_window and self.fixed_window.is_visible():
                self.fixed_window.close_window()
            
            self.update_status("📱 Режим відображення: спливаюче вікно")
            if hasattr(self, 'display_mode_label'):
                self.display_mode_label.config(text="Режим: 📱 Спливаюче вікно")
            
    def show_presets_manager(self):
        if hasattr(self, 'presets_window') and self.presets_window and self.presets_window.winfo_exists():
            self.presets_window.lift()
            return
            
        self.presets_window = tk.Toplevel()
        self.presets_window.title("Менеджер пресетів")
        self.presets_window.geometry("1156x728+200+100")
        self.presets_window.attributes('-topmost', True)
        self.presets_window.configure(bg='#f8f9fa')
        self.presets_window.protocol("WM_DELETE_WINDOW", lambda: self.presets_window.destroy())
        
        header = tk.Frame(self.presets_window, bg='#4CAF50', height=50)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        tk.Label(header, text="📋 Менеджер пресетів автоматичного моніторингу", 
                font=(self.app_font, 14, 'bold'), fg='white', bg='#4CAF50').pack(pady=12)
        
        main_frame = tk.Frame(self.presets_window, bg='#f8f9fa')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        list_frame = tk.LabelFrame(main_frame, text="💾 Збережені пресети", 
                                 font=(self.app_font, 11, 'bold'), bg='#f8f9fa')
        list_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        columns = ('name', 'region', 'interval', 'hotkey', 'created', 'used')
        self.presets_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        
        self.presets_tree.heading('name', text='Назва пресету')
        self.presets_tree.heading('region', text='Область (x,y,w,h)')
        self.presets_tree.heading('interval', text='Інтервал')
        self.presets_tree.heading('hotkey', text='Гаряча клавіша')
        self.presets_tree.heading('created', text='Створено')
        self.presets_tree.heading('used', text='Використано')
        
        self.presets_tree.column('name', width=150); self.presets_tree.column('region', width=180)
        self.presets_tree.column('interval', width=80); self.presets_tree.column('hotkey', width=120)
        self.presets_tree.column('created', width=140); self.presets_tree.column('used', width=80)
        
        scrollbar_presets = ttk.Scrollbar(list_frame, orient='vertical', command=self.presets_tree.yview)
        self.presets_tree.configure(yscrollcommand=scrollbar_presets.set)
        
        self.presets_tree.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar_presets.pack(side='right', fill='y', padx=(0, 10), pady=10)
        
        form_frame = tk.LabelFrame(main_frame, text="➕ Створити новий пресет", 
                                 font=(self.app_font, 11, 'bold'), bg='#f8f9fa')
        form_frame.pack(fill='x')
        
        form_content = tk.Frame(form_frame, bg='#f8f9fa')
        form_content.pack(fill='x', padx=15, pady=15)

        row1 = tk.Frame(form_content, bg='#f8f9fa')
        row1.pack(fill='x', pady=(0, 10))
        tk.Label(row1, text="📝 Назва:", font=(self.app_font, 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=5)
        self.preset_name_var = tk.StringVar()
        tk.Entry(row1, textvariable=self.preset_name_var, font=(self.app_font, 10), width=20).pack(side='left', padx=5)
        
        tk.Label(row1, text="📄 Опис:", font=(self.app_font, 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=5)
        self.preset_desc_var = tk.StringVar()
        tk.Entry(row1, textvariable=self.preset_desc_var, font=(self.app_font, 10), width=30).pack(side='left', padx=5)
        
        row2 = tk.Frame(form_content, bg='#f8f9fa')
        row2.pack(fill='x', pady=(0, 10))
        tk.Label(row2, text="📍 Область:", font=(self.app_font, 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=5)
        self.region_display = tk.Label(row2, text="Не вибрано", bg='#fff', relief='sunken', width=20)
        self.region_display.pack(side='left', padx=5)
        tk.Button(row2, text="🎯 Вибрати", command=self.select_region_for_preset, bg='#2196F3', fg='white', font=(self.app_font, 9, 'bold')).pack(side='left', padx=5)
        
        tk.Label(row2, text="⏱️ Інтервал:", font=(self.app_font, 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=5)
        self.preset_interval_var = tk.DoubleVar(value=self.settings_manager.settings.get('monitor_interval', 3.0))
        tk.Spinbox(row2, from_=0.2, to=10.0, increment=0.1, textvariable=self.preset_interval_var, width=5, font=(self.app_font, 10), format="%.1f").pack(side='left', padx=5)
        
        tk.Label(row2, text="⌨️ Клавіша:", font=(self.app_font, 10, 'bold'), bg='#f8f9fa').pack(side='left', padx=5)
        self.preset_hotkey_var = tk.StringVar()
        hotkey_options = ["Не призначено"] + [f"ctrl+{i}" for i in range(1, 10)]
        hotkey_combo = ttk.Combobox(row2, textvariable=self.preset_hotkey_var, values=hotkey_options, state='readonly', width=15)
        hotkey_combo.pack(side='left', padx=5)
        hotkey_combo.set("Не призначено")

        actions_row = tk.Frame(form_content, bg='#f8f9fa')
        actions_row.pack(fill='x', pady=(10, 0), anchor='center')
        tk.Button(actions_row, text="💾 Зберегти пресет", command=self.save_new_preset, bg='#4CAF50', fg='white', font=(self.app_font, 10, 'bold'), padx=20).pack(side='left', padx=10)
        tk.Button(actions_row, text="▶️ Використати", command=self.use_selected_preset, bg='#ff9800', fg='white', font=(self.app_font, 10, 'bold'), padx=20).pack(side='left', padx=10)
        tk.Button(actions_row, text="🗑️ Видалити", command=self.delete_selected_preset, bg='#f44336', fg='white', font=(self.app_font, 10, 'bold'), padx=20).pack(side='left', padx=10)
        
        self.selected_region_for_preset = None
        self.refresh_presets_list()

    def refresh_presets_list(self):
        for item in self.presets_tree.get_children():
            self.presets_tree.delete(item)
        for name, data in self.settings_manager.saved_presets.items():
            region = data.get('region', [0,0,0,0])
            region_str = f"({region[0]},{region[1]},{region[2]},{region[3]})"
            hotkey = data.get('hotkey') or "Немає"
            self.presets_tree.insert('', 'end', values=(name, region_str, data.get('interval', 3), hotkey, data.get('created', ''), data.get('used_count', 0)))

    def select_region_for_preset(self):
        self.update_status("🎯 Виділіть область для нового пресету...")
        self._selecting_for_preset = True
        self.start_selection()

    def save_new_preset(self):
        name = self.preset_name_var.get().strip()
        if not name:
            messagebox.showwarning("Попередження", "Введіть назву пресету", parent=self.presets_window)
            return
        if not self.selected_region_for_preset:
            messagebox.showwarning("Попередження", "Виберіть область для пресету", parent=self.presets_window)
            return
        if name in self.settings_manager.saved_presets and not messagebox.askyesno("Підтвердження", f"Пресет '{name}' вже існує. Перезаписати?", parent=self.presets_window):
            return
            
        hotkey = self.preset_hotkey_var.get()
        if hotkey == "Не призначено":
            hotkey = None
            
        self.settings_manager.save_preset(name, self.selected_region_for_preset, self.preset_interval_var.get(), self.preset_desc_var.get(), hotkey)
        
        self.preset_name_var.set(""); self.preset_desc_var.set(""); self.preset_interval_var.set(3); self.preset_hotkey_var.set("Не призначено")
        self.selected_region_for_preset = None; self.region_display.config(text="Не вибрано")
        self.refresh_presets_list()
        self.setup_hotkeys()
        self.update_status(f"💾 Пресет '{name}' збережено!")

    def use_selected_preset(self):
        selection = self.presets_tree.selection()
        if not selection: return
        item = self.presets_tree.item(selection[0])
        preset_data = self.settings_manager.get_preset(item['values'][0])
        if preset_data:
            self.settings_manager.settings['monitor_interval'] = preset_data['interval']
            self.settings_manager.save_settings()
            self.monitor_region = preset_data['region']
            self.start_region_monitoring()
            self.refresh_presets_list()
        else: messagebox.showerror("Помилка", "Пресет не знайдено")

    def delete_selected_preset(self):
        selection = self.presets_tree.selection()
        if not selection: return
        item = self.presets_tree.item(selection[0])
        preset_name = item['values'][0]
        if messagebox.askyesno("Підтвердження", f"Видалити пресет '{preset_name}'?", parent=self.presets_window):
            self.settings_manager.delete_preset(preset_name)
            self.refresh_presets_list()
            self.setup_hotkeys()
            self.update_status(f"🗑️ Пресет '{preset_name}' видалено")

    def show_settings(self):
        if hasattr(self, 'settings_window') and self.settings_window and self.settings_window.winfo_exists():
            try:
                self.settings_window.lift()
                return
            except tk.TclError:
                pass

        self.settings_window = tk.Toplevel()
        self.settings_window.title("Налаштування Screen Translator")
        self.settings_window.attributes('-topmost', True)
        self.settings_window.configure(bg='#f8f9fa')
        
        win_width = 1179
        win_height = 1029
        
        screen_width = self.settings_window.winfo_screenwidth()
        screen_height = self.settings_window.winfo_screenheight()
        
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        
        self.settings_window.geometry(f'{win_width}x{win_height}+{x}+{y}')
        
        header = tk.Frame(self.settings_window, bg='#2196f3', height=60)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        header_content = tk.Frame(header, bg='#2196f3')
        header_content.pack(expand=True, fill='both')
        
        tk.Label(header_content, text="⚙️ Налаштування Screen Translator", 
                font=(self.app_font, 16, 'bold'), fg='white', bg='#2196f3').pack(pady=5)
        
        style = ttk.Style()
        style.configure('Custom.TNotebook.Tab', padding=[20, 10], font=(self.app_font, 10))
        style.configure('Custom.TNotebook', tabmargins=[2, 5, 2, 0])

        notebook = ttk.Notebook(self.settings_window, style='Custom.TNotebook')
        notebook.pack(fill='both', expand=True, padx=20, pady=20)
        
        self.create_enhanced_basic_settings_tab(notebook)
        self.create_enhanced_display_settings_tab(notebook)
        self.create_enhanced_info_tab(notebook)
        self.create_hotkeys_tab(notebook)

        def update_tab_margins(event=None):
            try:
                font = tkfont.Font(font=style.lookup('Custom.TNotebook.Tab', 'font'))
                total_tabs_width = 0
                for tab_id in notebook.tabs():
                    text = notebook.tab(tab_id, "text")
                    total_tabs_width += font.measure(text) + 25 + (style.lookup('Custom.TNotebook.Tab', 'padding')[0] * 2)
                notebook_width = notebook.winfo_width()
                empty_space = notebook_width - total_tabs_width
                left_margin = max(2, empty_space // 2)
                style.configure('Custom.TNotebook', tabmargins=[left_margin, 5, 2, 0])
            except (tk.TclError, NameError): pass
        
        notebook.bind("<Configure>", update_tab_margins)
        notebook.after(100, update_tab_margins)

    def create_enhanced_basic_settings_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="🔧 Основні налаштування")
        
        canvas = tk.Canvas(tab, bg='#f8f8f8', highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f8f9fa')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        scrollable_window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_canvas_configure(event):
            canvas.itemconfig(scrollable_window_id, width=event.width)

        canvas.bind("<Configure>", on_canvas_configure)
        
        interval_frame = tk.LabelFrame(scrollable_frame, text="⏱️ Інтервал моніторингу", font=(self.app_font, 12, 'bold'), bg='#f8f9fa', fg='#1976d2')
        interval_frame.pack(fill='x', padx=20, pady=(20, 15))
        
        interval_content = tk.Frame(interval_frame, bg='#f8f9fa')
        interval_content.pack(fill='x', padx=15, pady=15)
        tk.Label(interval_content, text="Час між автоматичними перекладами:", font=(self.app_font, 10), bg='#f8f9fa').pack()
        
        self.interval_var = tk.DoubleVar(value=self.settings_manager.settings.get('monitor_interval', 3.0))
        
        self.interval_display_var = tk.StringVar()
        def update_interval_label(*args):
            self.interval_display_var.set(f"{self.interval_var.get():.1f}")
        self.interval_var.trace_add('write', update_interval_label)
        
        interval_control = tk.Frame(interval_content, bg='#f8f9fa')
        interval_control.pack(pady=10)
        
        interval_scale = tk.Scale(interval_control, from_=0.2, to=10.0, resolution=0.1, orient='horizontal', variable=self.interval_var, length=400, bg='#f8f9fa', font=(self.app_font, 10), troughcolor='#e0e0e0', activebackground='#2196f3')
        interval_scale.pack(side='left')
        
        self.interval_value_label = tk.Label(interval_control, textvariable=self.interval_display_var, font=(self.app_font, 12, 'bold'), fg='#2196f3', bg='#f8f9fa')
        self.interval_value_label.pack(side='left', padx=(20, 0))
        
        update_interval_label()
        
        tk.Label(interval_control, text="секунд", font=(self.app_font, 10), bg='#f8f9fa').pack(side='left', padx=(5, 0))
        
        translator_frame = tk.LabelFrame(scrollable_frame, text="🌐 Вибір перекладача", font=(self.app_font, 12, 'bold'), bg='#f8f9fa', fg='#1976d2')
        translator_frame.pack(fill='x', padx=20, pady=(0, 15))
        
        translator_content = tk.Frame(translator_frame, bg='#f8f9fa')
        translator_content.pack(fill='x', padx=15, pady=15)
        
        self.translator_api_var = tk.StringVar(value=self.settings_manager.settings.get('translator_api', 'auto'))
        
        api_options = [
            ("DeepL (Найвища якість)", "deepl", "Потребує API ключ. Ліміт ~500 тис. символів/міс."),
            ("Microsoft (Висока якість)", "microsoft", "Потребує ключ Azure. Ліміт ~2 млн. символів/міс."), # <-- ДОДАНО
            ("Авто (рекомендовано)", "auto", "Резервний переклад при відмові основного."),
            # ...
        ]
        
        for text, value, desc in api_options:
            option_frame = tk.Frame(translator_content, bg='#f8f9fa')
            option_frame.pack(fill='x', pady=2)
            radio = tk.Radiobutton(option_frame, text=text, variable=self.translator_api_var, value=value, font=(self.app_font, 10, 'bold'), bg='#f8f9fa', activebackground='#f8f9fa')
            radio.pack(side='left')
            tk.Label(option_frame, text=f"- {desc}", font=(self.app_font, 9), bg='#f8f9fa', fg='#555').pack(side='left', padx=10)
            
        deepl_key_frame = tk.LabelFrame(scrollable_frame, text="🔑 Ключ DeepL API", font=(self.app_font, 12, 'bold'), bg='#f8f9fa', fg='#1976d2')
        deepl_key_frame.pack(fill='x', padx=20, pady=(0, 15))
        
        # --- Блок для Microsoft Translator ---
        ms_key_frame = tk.LabelFrame(scrollable_frame, text="🔑 Ключ та регіон Microsoft Translator", font=(self.app_font, 12, 'bold'), bg='#f8f9fa', fg='#1976d2')
        ms_key_frame.pack(fill='x', padx=20, pady=(0, 15))
        
        ms_content = tk.Frame(ms_key_frame, bg='#f8f9fa')
        ms_content.pack(fill='x', padx=15, pady=15)

        # Поле для ключа
        tk.Label(ms_content, text="Вставте сюди ваш ключ Microsoft Translator API (Key 1):", font=(self.app_font, 10), bg='#f8f9fa').pack(anchor='w')
        self.ms_translator_key_var = tk.StringVar(value=self.settings_manager.settings.get('ms_translator_key', ''))
        tk.Entry(ms_content, textvariable=self.ms_translator_key_var, font=(self.app_font, 10), width=50, show="*").pack(fill='x', pady=(2, 8))

        # Поле для регіону
        tk.Label(ms_content, text="Введіть ваш регіон (напр., westeurope):", font=(self.app_font, 10), bg='#f8f9fa').pack(anchor='w')
        self.ms_translator_region_var = tk.StringVar(value=self.settings_manager.settings.get('ms_translator_region', ''))
        tk.Entry(ms_content, textvariable=self.ms_translator_region_var, font=(self.app_font, 10), width=50).pack(fill='x', pady=2)
        
        deepl_content = tk.Frame(deepl_key_frame, bg='#f8f9fa')
        deepl_content.pack(fill='x', padx=15, pady=15)
        
        tk.Label(deepl_content, text="Вставте сюди ваш безкоштовний ключ DeepL API:", font=(self.app_font, 10), bg='#f8f9fa').pack(anchor='w')
        
        key_entry_frame = tk.Frame(deepl_content, bg='#f8f9fa')
        key_entry_frame.pack(fill='x', pady=5)
        
        self.deepl_api_key_var = tk.StringVar(value=self.settings_manager.settings.get('deepl_api_key', ''))
        key_entry = tk.Entry(key_entry_frame, textvariable=self.deepl_api_key_var, font=(self.app_font, 10), width=50, show="*")
        key_entry.pack(side='left', expand=True, fill='x')
        
        def toggle_key_visibility():
            if key_entry.cget('show') == '*':
                key_entry.config(show='')
                show_btn.config(text='👁️')
            else:
                key_entry.config(show='*')
                show_btn.config(text='🙈')

        show_btn = tk.Button(key_entry_frame, text='🙈', command=toggle_key_visibility, font=(self.app_font, 10))
        show_btn.pack(side='left', padx=5)
        
        theme_frame = tk.LabelFrame(scrollable_frame, text="🎨 Оформлення та вигляд", font=(self.app_font, 12, 'bold'), bg='#f8f9fa', fg='#1976d2')
        theme_frame.pack(fill='x', padx=20, pady=(0, 15))
        
        theme_content = tk.Frame(theme_frame, bg='#f8f9fa')
        theme_content.pack(fill='x', padx=15, pady=15)
        
        def update_font_preview(*args):
            font_family = self.font_family_var.get()
            font_size = self.font_var.get()
            try:
                self.font_preview.config(font=(font_family, font_size))
            except tk.TclError:
                self.font_preview.config(font=("Arial", font_size))

        font_family_section = tk.Frame(theme_content, bg='#f8f9fa')
        font_family_section.pack(fill='x', pady=(10, 0))
        tk.Label(font_family_section, text="Основний шрифт програми:", font=(self.app_font, 11, 'bold'), bg='#f8f9fa').pack()
        
        self.font_family_var = tk.StringVar(value=self.settings_manager.settings.get('app_font', 'Arial'))
        
        try:
            font_list = sorted([f for f in tkfont.families() if not f.startswith('@')])
        except:
            font_list = ['Arial', 'Verdana', 'Tahoma', 'Times New Roman', 'Courier New']
        
        font_combobox = ttk.Combobox(font_family_section, textvariable=self.font_family_var, values=font_list, state='readonly', width=30)
        font_combobox.pack(pady=5)
        font_combobox.bind("<<ComboboxSelected>>", update_font_preview)

        font_size_section = tk.Frame(theme_content, bg='#f8f9fa')
        font_size_section.pack(fill='x', pady=(10, 0))
        tk.Label(font_size_section, text="Розмір шрифту:", font=(self.app_font, 11, 'bold'), bg='#f8f9fa').pack()
        self.font_var = tk.IntVar(value=self.settings_manager.settings.get('result_font_size', 11))
        
        font_control = tk.Frame(font_size_section, bg='#f8f9fa')
        font_control.pack(pady=10)
        
        font_scale = tk.Scale(font_control, from_=8, to=18, orient='horizontal', variable=self.font_var, length=350, bg='#f8f9fa', font=(self.app_font, 10), troughcolor='#e0e0e0', activebackground='#ff9800')
        font_scale.pack(side='left')
        
        self.font_preview = tk.Label(font_control, text="Зразок тексту", bg='#fff', relief='sunken', padx=10, pady=5)
        self.font_preview.pack(side='left', padx=(20, 0))
        
        self.font_var.trace('w', update_font_preview)
        update_font_preview()

        tk.Label(theme_content, text="Кольорова тема:", font=(self.app_font, 11, 'bold'), bg='#f8f9fa').pack(pady=(20,0))
        self.theme_var = tk.StringVar(value=self.settings_manager.settings.get('result_theme', 'blue'))
        themes_frame = tk.Frame(theme_content, bg='#f8f9fa')
        themes_frame.pack(pady=10)
        themes = [('blue', 'Синя', '#2196f3'), ('green', 'Зелена', '#4CAF50'), ('dark', 'Темна', '#555555')]
        for theme_id, theme_name, color in themes:
            theme_btn_frame = tk.Frame(themes_frame, bg=color, relief='solid', bd=2)
            theme_btn_frame.pack(side='left', padx=10)
            radio = tk.Radiobutton(theme_btn_frame, text=theme_name, variable=self.theme_var, value=theme_id, bg=color, fg='white', font=(self.app_font, 10, 'bold'), selectcolor=color, relief='flat')
            radio.pack(padx=15, pady=8)
        
        transparency_section = tk.Frame(theme_content, bg='#f8f9fa')
        transparency_section.pack(fill='x', pady=(20, 0))
        tk.Label(transparency_section, text="Прозорість вікон:", font=(self.app_font, 11, 'bold'), bg='#f8f9fa').pack()
        self.alpha_var = tk.DoubleVar(value=self.settings_manager.settings.get('result_alpha', 0.9))
        alpha_control = tk.Frame(transparency_section, bg='#f8f9fa')
        alpha_control.pack(pady=10)
        alpha_scale = tk.Scale(alpha_control, from_=0.5, to=1.0, resolution=0.1, orient='horizontal', variable=self.alpha_var, length=350, bg='#f8f9fa', font=(self.app_font, 10), troughcolor='#e0e0e0', activebackground='#4CAF50')
        alpha_scale.pack(side='left')
        alpha_preview = tk.Frame(alpha_control, bg='#2196f3', width=50, height=30)
        alpha_preview.pack(side='left', padx=(20, 0))
        def update_alpha_preview(*args):
            alpha_val = self.alpha_var.get()
            gray_val = int(255 * (1 - alpha_val * 0.5))
            color = f"#{gray_val:02x}{gray_val:02x}{gray_val:02x}"
            alpha_preview.configure(bg=color)
        self.alpha_var.trace('w', update_alpha_preview)
        update_alpha_preview()
        
        buttons_frame = tk.Frame(scrollable_frame, bg='#f8f9fa')
        buttons_frame.pack(fill='x', padx=20, pady=20)
        buttons_subframe = tk.Frame(buttons_frame, bg='#f8f9fa')
        buttons_subframe.pack()
        save_btn = tk.Button(buttons_subframe, text="💾 Зберегти налаштування", command=self.save_enhanced_settings, bg='#4CAF50', fg='white', font=(self.app_font, 11, 'bold'), padx=25, pady=10, relief='flat', bd=0)
        save_btn.pack(side='left', padx=(0, 15))
        test_btn = tk.Button(buttons_subframe, text="🧪 Тестувати", command=self.test_enhanced_settings, bg='#2196F3', fg='white', font=(self.app_font, 11, 'bold'), padx=25, pady=10, relief='flat', bd=0)
        test_btn.pack(side='left', padx=(0, 15))
        reset_btn = tk.Button(buttons_subframe, text="🔄 Скинути", command=self.reset_enhanced_settings, bg='#ff9800', fg='white', font=(self.app_font, 11, 'bold'), padx=25, pady=10, relief='flat', bd=0)
        reset_btn.pack(side='left')
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_enhanced_display_settings_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="🖥️ Режими відображення")
        
        center_frame = tk.Frame(tab, bg='#f8f9fa')
        center_frame.pack(expand=True)

        mode_frame = tk.LabelFrame(center_frame, text="📱 Вибір режиму відображення", 
                                 font=(self.app_font, 12, 'bold'), bg='#f8f9fa', fg='#1976d2', padx=10, pady=10)
        mode_frame.pack(pady=(20, 20))
        
        mode_content = tk.Frame(mode_frame, bg='#f8f9fa')
        mode_content.pack(padx=15, pady=15)
        
        self.display_mode_var = tk.StringVar(value=self.settings_manager.settings['display_mode'])
        
        popup_card = tk.Frame(mode_content, bg='#e3f2fd', relief='solid', bd=2)
        popup_card.pack(side='left', padx=(0, 10))
        
        popup_radio = tk.Radiobutton(popup_card, text="📱 Спливаючі вікна", 
                                   variable=self.display_mode_var, value='popup',
                                   font=(self.app_font, 12, 'bold'), bg='#e3f2fd',
                                   command=self.on_display_mode_change)
        popup_radio.pack(pady=10)
        
        tk.Label(popup_card, text="• З'являються біля курсора\n• Автоматично закриваються\n• Підходять для швидких перекладів", 
                justify='left', font=(self.app_font, 9), bg='#f8f9fa').pack(padx=10, pady=(0, 10))
        
        fixed_card = tk.Frame(mode_content, bg='#e8f5e8', relief='solid', bd=2)
        fixed_card.pack(side='left', padx=(10, 0))
        
        fixed_radio = tk.Radiobutton(fixed_card, text="🖥️ Фіксоване вікно", 
                                   variable=self.display_mode_var, value='fixed',
                                   font=(self.app_font, 12, 'bold'), bg='#e8f5e8',
                                   command=self.on_display_mode_change)
        fixed_radio.pack(pady=10)
        
        tk.Label(fixed_card, text="• Постійне вікно в обраному місці\n• Можна перетягувати та змінювати розмір\n• Ідеально для ігор", 
                justify='left', font=(self.app_font, 9), bg='#e8f5e8').pack(padx=10, pady=(0, 10))
        
        fixed_settings_frame = tk.LabelFrame(center_frame, text="🖥️ Налаштування фіксованого вікна", 
                                           font=(self.app_font, 12, 'bold'), bg='#f8f9fa', fg='#1976d2', padx=10, pady=10)
        fixed_settings_frame.pack(pady=(0, 20))
        
        fixed_content = tk.Frame(fixed_settings_frame, bg='#f8f9fa')
        fixed_content.pack(padx=15, pady=15)
        
        options_frame = tk.Frame(fixed_content, bg='#f8f9fa')
        options_frame.pack()
        
        self.topmost_var = tk.BooleanVar(value=self.settings_manager.settings.get('fixed_window_pinned', True))
        topmost_check = tk.Checkbutton(options_frame, text="📌 Завжди поверх інших вікон", 
                                     variable=self.topmost_var, font=(self.app_font, 10), bg='#f8f9fa')
        topmost_check.pack(anchor='w', pady=5)
        
        control_frame = tk.Frame(fixed_content, bg='#f8f9fa')
        control_frame.pack(pady=(15, 0))
        
        create_btn = tk.Button(control_frame, text="🖥️ Створити вікно", 
                             command=self.create_fixed_window_from_settings,
                             bg='#4CAF50', fg='white', font=(self.app_font, 10, 'bold'),
                             padx=20, pady=8)
        create_btn.pack(side='left', padx=(0, 10))
        
        toggle_btn = tk.Button(control_frame, text="🔄 Змінити режим", 
                             command=self.toggle_display_mode,
                             bg='#9C27B0', fg='white', font=(self.app_font, 10, 'bold'),
                             padx=20, pady=8)
        toggle_btn.pack(side='left')
        save_btn_frame = tk.Frame(center_frame, bg='#f8f9fa')
        save_btn_frame.pack(pady=(10, 20))
        save_btn = tk.Button(save_btn_frame, text="💾 Зберегти налаштування", command=self.save_enhanced_settings, bg='#4CAF50', fg='white', font=(self.app_font, 11, 'bold'), padx=25, pady=10, relief='flat', bd=0)
        save_btn.pack()
    
        

    def create_enhanced_info_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="ℹ️ Про програму")
        
        canvas = tk.Canvas(tab, bg='#f8f9fa', highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f8f9fa')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        scrollable_window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def on_canvas_configure(event):
            canvas.itemconfig(scrollable_window_id, width=event.width)

        canvas.bind("<Configure>", on_canvas_configure)
        
        header_frame = tk.Frame(scrollable_frame, bg='#2196f3')
        header_frame.pack(fill='x', padx=20, pady=20)
        
        tk.Label(header_frame, text="🎮 Screen Translator v0.1 by Xodarix&AI", 
                font=(self.app_font, 20, 'bold'), fg='white', bg='#2196f3').pack(pady=15)
        
        info_sections = [
            ("✨ Основні функції", [
                "🔍 Розпізнавання тексту з екрану (OCR)",
                "🌐 Автоматичний переклад на українську мову", 
                "📱 Два режими відображення: спливаючі та фіксоване вікно",
                "🔄 Авто-моніторинг діалогів з налаштуваннями",
            ]),
            ("🎮 Особливості для ігор", [
                "🖥️ Фіксоване вікно без заважаючих рамок Windows",
                "📌 Гарантоване відображення поверх ігор",
                "🎯 Автоматичне збереження областей діалогів",
                "⏱️ Налаштуваний інтервал від 1 до 10 секунд",
            ]),
        ]
        
        for section_title, items in info_sections:
            section_frame = tk.LabelFrame(scrollable_frame, text=section_title, 
                                        font=(self.app_font, 12, 'bold'), bg='#f8f9fa', fg='#1976d2')
            section_frame.pack(fill='x', padx=20, pady=(0, 15))
            
            for item in items:
                tk.Label(section_frame, text=item, font=(self.app_font, 10), 
                        bg='#f8f9fa').pack(padx=15, pady=2)
        
        hotkeys_frame = tk.LabelFrame(scrollable_frame, text="⌨️ Гарячі клавіші", 
                                    font=(self.app_font, 12, 'bold'), bg='#f8f9fa', fg='#1976d2')
        hotkeys_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        hotkeys_data = [
            ("Ctrl+Shift+S", "Разовий переклад виділеної області"),
            ("Ctrl+Shift+A", "Запуск авто-моніторингу діалогів"),
            ("Ctrl+Shift+X", "Зупинити моніторинг"),
            ("Ctrl+Shift+Z", "Пауза / Відновлення моніторингу"), # <-- ДОДАНО
            ("Ctrl+Shift+D", "Перемикання режиму відображення"),
            ("Ctrl+Shift+C", "Відкрити меню налаштувань"),
        ]
        
        hotkeys_center_frame = tk.Frame(hotkeys_frame, bg='#f8f9fa')
        hotkeys_center_frame.pack(pady=5)

        for i, (key, description) in enumerate(hotkeys_data):
            row_frame = tk.Frame(hotkeys_center_frame, bg='#fff' if i % 2 == 0 else '#f0f0f0')
            row_frame.pack(fill='x')
            
            tk.Label(row_frame, text=key, font=('Courier New', 10, 'bold'), 
                    bg=row_frame['bg'], fg='#1976d2', width=20, anchor='e').pack(side='left', padx=10, pady=3)
            tk.Label(row_frame, text=description, font=(self.app_font, 10), 
                    bg=row_frame['bg'], justify='left').pack(side='left', padx=10, pady=3)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_hotkeys_tab(self, notebook):
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="⌨️ Гарячі клавіші")

        main_frame = tk.LabelFrame(tab,
                                   text="⌨️ Налаштування гарячих клавіш",
                                   font=(self.app_font, 12, 'bold'),
                                   bg='#f8f9fa',
                                   fg='#1976d2')
        main_frame.pack(padx=20, pady=20, fill='both', expand=True)

        grid_container = tk.Frame(main_frame, bg='#f8f9fa')
        grid_container.pack(padx=10, pady=10, fill='x')

        grid_container.columnconfigure(0, weight=1)
        grid_container.columnconfigure(1, weight=0)
        grid_container.columnconfigure(2, weight=0)
        grid_container.columnconfigure(3, weight=0)

        header_font = (self.app_font, 10, 'bold')
        tk.Label(grid_container, text="Дія", font=header_font, bg='#f8f9fa').grid(row=0, column=0, sticky='w', pady=(0, 5))
        tk.Label(grid_container, text="Клавіша", font=header_font, bg='#f8f9fa').grid(row=0, column=1, sticky='w', pady=(0, 5), padx=5)

        separator = ttk.Separator(grid_container, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=4, sticky='ew', pady=(0, 10))

        hotkey_actions = {
            "select_area": "Разовий переклад",
            "start_monitoring": "Почати моніторинг",
            "stop_monitoring": "Зупинити моніторинг",
            "pause_monitoring": "Пауза / Відновлення", # <-- ДОДАНО
            "toggle_mode": "Змінити режим",
            "show_settings": "Відкрити налаштування",
            "show_presets": "Відкрити пресети"
        }
        
        self.hotkey_entries = {}
        
        for i, (action_key, description) in enumerate(hotkey_actions.items()):
            current_row = i + 2
            
            tk.Label(grid_container, text=f"{description}:", font=(self.app_font, 10), bg='#f8f9fa').grid(row=current_row, column=0, sticky='w', pady=4)
            
            entry_var = tk.StringVar(value=self.settings_manager.settings['hotkeys'].get(action_key, ''))
            entry = tk.Entry(grid_container, textvariable=entry_var, font=(self.app_font, 10), width=25, relief='solid', bd=1, state='readonly')
            entry.grid(row=current_row, column=1, padx=5, pady=4)
            self.hotkey_entries[action_key] = entry_var

            change_btn = tk.Button(grid_container, text="Змінити", command=lambda k=action_key, v=entry_var: self.listen_for_hotkey(k, v), font=(self.app_font, 9))
            change_btn.grid(row=current_row, column=2, padx=(5, 2), pady=4)

            reset_btn = tk.Button(grid_container, text="Скинути", command=lambda k=action_key, v=entry_var: self.reset_hotkey(k, v), font=(self.app_font, 9))
            reset_btn.grid(row=current_row, column=3, padx=(2, 5), pady=4)

        presets_info_frame = tk.Frame(main_frame, bg='#f8f9fa')
        presets_info_frame.pack(padx=10, pady=(20, 10), fill='x')
        save_btn_frame = tk.Frame(main_frame, bg='#f8f9fa')
        save_btn_frame.pack(pady=(10, 0))
        save_btn = tk.Button(save_btn_frame, text="💾 Зберегти налаштування", command=self.save_enhanced_settings, bg='#4CAF50', fg='white', font=(self.app_font, 11, 'bold'), padx=25, pady=10, relief='flat', bd=0)
        save_btn.pack()
        
    def listen_for_hotkey(self, action_key, entry_var):
        original_text = entry_var.get()
        entry_var.set("Натисніть комбінацію...")
        self.settings_window.update_idletasks()

        def wait_for_hotkey():
            try:
                hotkey = keyboard.read_hotkey(suppress=False)
                if hotkey in ('ctrl', 'shift', 'alt'):
                    entry_var.set(original_text)
                    return

                entry_var.set(hotkey)
            except Exception as e:
                print(f"Помилка зчитування клавіші: {e}")
                entry_var.set(original_text)
            finally:
                if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
                    self.settings_window.focus_force()
                    self.settings_window.lift()

        threading.Thread(target=wait_for_hotkey, daemon=True).start()
    
    def reset_hotkey(self, action_key, entry_var):
        default_hotkey = self.settings_manager.default_settings['hotkeys'].get(action_key)
        if default_hotkey:
            entry_var.set(default_hotkey)
            self.settings_manager.settings['hotkeys'][action_key] = default_hotkey
            self.settings_manager.save_settings()
            self.setup_hotkeys()
            self.update_status(f"✅ Клавішу для '{action_key}' скинуто до '{default_hotkey}'")
        
    def save_enhanced_settings(self):
        self.settings_manager.settings.update({
            'monitor_interval': self.interval_var.get(),
            'result_alpha': self.alpha_var.get(),
            'result_font_size': self.font_var.get(),
            'result_theme': self.theme_var.get(),
            'display_mode': self.display_mode_var.get(),
            'fixed_window_pinned': self.topmost_var.get(),
            'app_font': self.font_family_var.get(),
            'translator_api': self.translator_api_var.get(),
            'deepl_api_key': self.deepl_api_key_var.get().strip(),
            'ms_translator_key': self.ms_translator_key_var.get().strip(),      # <-- ДОДАНО
            'ms_translator_region': self.ms_translator_region_var.get().strip() # <-- ДОДАНО
            
        })

        for action_key, entry_var in self.hotkey_entries.items():
            self.settings_manager.settings['hotkeys'][action_key] = entry_var.get()
            
        self.settings_manager.save_settings()
        self.setup_hotkeys() 
        
        if self.fixed_window and self.fixed_window.is_visible():
            new_font = (self.font_family_var.get(), self.font_var.get())
            self.fixed_window.window.attributes('-alpha', self.alpha_var.get())
            if self.fixed_window.text_widget:
                self.fixed_window.text_widget.config(font=new_font)
        
        self.update_status("💾 Всі налаштування збережено успішно!")
        messagebox.showinfo("Успіх", "Налаштування збережено!", parent=self.settings_window)

    def test_enhanced_settings(self):
        font_name = self.font_family_var.get()
        font_size = self.font_var.get()
        translator_name = self.translator_api_var.get()
        
        test_text = f"""🧪 ТЕСТОВЕ ПОВІДОМЛЕННЯ

Це тестування налаштувань Screen Translator:

📊 Поточні налаштування:
• Перекладач: {translator_name.title()}
• Шрифт: {font_name}
• Тема: {self.theme_var.get().title()}
• Прозорість: {self.alpha_var.get():.1f}
• Розмір шрифту: {font_size}px
• Інтервал моніторингу: {self.interval_var.get()}с
• Режим відображення: {'Фіксоване вікно' if self.display_mode_var.get() == 'fixed' else 'Спливаюче вікно'}

✨ Якщо ви бачите це повідомлення, налаштування працюють правильно!"""
        
        current_mode = self.display_mode_var.get()
        if current_mode == 'fixed':
            if not self.fixed_window or not self.fixed_window.is_visible():
                self.create_fixed_window_from_settings()
            self.fixed_window.update_text(test_text)
        else:
            old_settings = {}
            for key in ['result_alpha', 'result_font_size', 'result_theme', 'app_font']:
                old_settings[key] = self.settings_manager.settings[key]
                
            self.settings_manager.settings.update({
                'result_alpha': self.alpha_var.get(),
                'result_font_size': self.font_var.get(),
                'result_theme': self.theme_var.get(),
                'app_font': self.font_family_var.get()
            })
            
            self.show_result_with_settings(test_text, is_test=True)
            self.settings_manager.settings.update(old_settings)

    def reset_enhanced_settings(self):
        if messagebox.askyesno("Підтвердження", 
                              "Скинути всі налаштування до значень за замовчуванням?\n\nЦя дія незворотна."):
            defaults = self.settings_manager.default_settings.copy()
            self.settings_manager.settings = defaults.copy()
            self.settings_manager.save_settings()
            
            if hasattr(self, 'interval_var'):
                self.interval_var.set(defaults['monitor_interval'])
                self.alpha_var.set(defaults['result_alpha'])
                self.font_var.set(defaults['result_font_size'])
                self.theme_var.set(defaults['result_theme'])
                self.display_mode_var.set(defaults['display_mode'])
                if hasattr(self, 'topmost_var'):
                    self.topmost_var.set(defaults['fixed_window_pinned'])
                if hasattr(self, 'font_family_var'):
                    self.font_family_var.set(defaults['app_font'])
                if hasattr(self, 'translator_api_var'):
                    self.translator_api_var.set(defaults['translator_api'])
                if hasattr(self, 'deepl_api_key_var'):
                    self.deepl_api_key_var.set(defaults['deepl_api_key'])

            self.update_status("🔄 Налаштування скинуто до значень за замовчуванням")
            messagebox.showinfo("Готово", "Всі налаштування скинуто до значень за замовчуванням.")

    def on_display_mode_change(self):
        new_mode = self.display_mode_var.get()
        self.settings_manager.settings['display_mode'] = new_mode
        self.settings_manager.save_settings()
        
        if new_mode == 'fixed':
            self.create_fixed_window_from_settings()
        else:
            if self.fixed_window and self.fixed_window.is_visible():
                self.fixed_window.close_window()

    def create_fixed_window_from_settings(self):
        self.settings_manager.settings['display_mode'] = 'fixed'
        self.settings_manager.save_settings()
        
        if not self.fixed_window:
            self.fixed_window = FixedTranslationWindow(self, self.settings_manager)
        
        if not self.fixed_window.is_visible():
            self.fixed_window.create_window()
        
        self.update_status("🖥️ Фіксоване вікно створено")

    def start_auto_monitoring(self):
        self._force_fixed_window_mode()
        
        if self.monitoring:
            self.update_status("Моніторинг вже активний! Ctrl+Shift+X для зупинки")
            return
        self.update_status("🎯 Виділіть область для постійного моніторингу діалогів")
        self._auto_monitoring_requested = True
        self.start_selection()

    def _force_fixed_window_mode(self):
        if self.settings_manager.settings['display_mode'] != 'fixed':
            self.settings_manager.settings['display_mode'] = 'fixed'
            self.settings_manager.save_settings()
            
            if hasattr(self, 'display_mode_label'):
                self.display_mode_label.config(text="Режим: 🖥️ Фіксоване вікно")
            self.update_status("🖥️ Режим автоматично змінено на фіксоване вікно.")
    

if __name__ == "__main__":
    multiprocessing.freeze_support()

    root = tk.Tk()
    app = ScreenTranslator(root)

    def loader_thread():
        # Запускаємо повільну ініціалізацію OCR
        app.initialize_ocr()
        # Повідомляємо, що все готово
        app.status_queue.put("done")

    def check_queue():
        try:
            message = app.status_queue.get(block=False)
            if message == "done":
                # Якщо все завантажено, будуємо основний інтерфейс
                app._build_main_ui()
                return
            elif message == "error":
                root.destroy()
                return
            else:
                # Оновлюємо текст на вікні завантаження
                app.splash_status_label.config(text=message)
        except:
            pass
        
        root.after(100, check_queue)

    threading.Thread(target=loader_thread, daemon=True).start()
    check_queue()
    
    root.mainloop()