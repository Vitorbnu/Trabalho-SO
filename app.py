import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import psutil
import threading
import time
from datetime import datetime
import platform
import socket
import queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import sys
import gc
import os
import ctypes
import subprocess
import webbrowser
from ctypes import wintypes

# Configuração para evitar problemas com Matplotlib em threads
plt.style.use('fast')

# Constantes para limpeza de memória no Windows (se disponível)
if sys.platform == 'win32':
    try:
        kernel32 = ctypes.windll.kernel32
        EmptyWorkingSet = kernel32.EmptyWorkingSet
        SetProcessWorkingSetSize = kernel32.SetProcessWorkingSetSize
    except:
        EmptyWorkingSet = None
        SetProcessWorkingSetSize = None
else:
    EmptyWorkingSet = None
    SetProcessWorkingSetSize = None

#gerencia interface grafica, coleta dados, processa e armazena dados, atualiza graficos, gerencia threads,
class UltraOptimizedOSMonitor: # god class
    def __init__(self):
        self.window = tk.Tk()
        self.window.title(" Monitor de Sistema Ultimate v3.5")
        self.window.geometry("1400x950")

        # Configurar fechamento correto
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Estado do tema
        self.dark_mode = True
        self.style = ttk.Style()
        self.setup_theme()

        # Dados compartilhados via queue (thread-safe)
        self.data_queue = queue.Queue()
        self.is_running = True

        # Cache para armazenar processos para contexto
        self.current_process_context = None

        # Cache de dados
        self.cache = {
            'cpu': 0, 'memory': 0, 'disk': 0, 'network': 0,
            'process_count': 0, 'processes': [],
            'cpu_history': [0] * 60,
            'memory_history': [0] * 60,
            'disk_history': [0] * 60,
            'network_history': [0] * 60,
            'cpu_cores': [],
            'disk_io': {'read': [0] * 60, 'write': [0] * 60},
            'network_io': {'sent': [0] * 60, 'recv': [0] * 60},
            'temperature_history': [0] * 60,
            'power_history': [0] * 60,
            'last_process_update': 0,
            'last_system_update': 0,
            'memory_total_gb': 0,
            'memory_used_gb': 0,
            'memory_available_gb': 0,
            'disk_total_gb': 0,
            'disk_used_gb': 0,
            'disk_free_gb': 0,
            'memory_standby': 0,
            'cache_size': 0,
            'cpu_temperatures': [],
            'battery_info': {}
        }

        # Variáveis para ordenação
        self.sort_column = 'CPU%'
        self.sort_reverse = True

        self.initialize_cpu_cores()
        self.setup_ui()
        self.start_threaded_monitoring()

    def setup_theme(self):
        """Configura o tema inicial"""
        self.style.theme_use('clam')
        self.apply_theme_colors()

        # Estilo adicional para botões de ação
        self.style.configure("Accent.TButton",
                             font=('Arial', 10, 'bold'),
                             foreground='white',
                             background='#d9534f' if self.dark_mode else '#dc3545')
        self.style.map("Accent.TButton",
                       background=[('active', '#c9302c' if self.dark_mode else '#bd2130')])

        # Estilo para botões de sucesso
        self.style.configure("Success.TButton",
                             font=('Arial', 10, 'bold'),
                             foreground='white',
                             background='#5cb85c' if self.dark_mode else '#28a745')
        self.style.map("Success.TButton",
                       background=[('active', '#449d44' if self.dark_mode else '#218838')])

        # Estilo para botões de perigo
        self.style.configure("Danger.TButton",
                             font=('Arial', 10, 'bold'),
                             foreground='white',
                             background='#ff4444')
        self.style.map("Danger.TButton",
                       background=[('active', '#cc0000')])

    def apply_theme_colors(self):
        """Aplica cores baseadas no modo escuro/claro"""
        if self.dark_mode:
            bg_color = "#2d2d2d"
            fg_color = "#ffffff"
            field_bg = "#3d3d3d"
            select_bg = "#4a90e2"

            self.window.configure(bg=bg_color)
            self.style.configure(".", background=bg_color, foreground=fg_color, fieldbackground=field_bg)
            self.style.configure("Treeview", background=field_bg, foreground=fg_color, fieldbackground=field_bg)
            self.style.map("Treeview", background=[("selected", select_bg)])
            self.style.configure("TNotebook", background=bg_color)
            self.style.configure("TNotebook.Tab", background=field_bg, foreground=fg_color)
            self.style.map("TNotebook.Tab", background=[("selected", select_bg)])
            plt.style.use('dark_background')
        else:
            bg_color = "#f0f0f0"
            fg_color = "#000000"
            self.window.configure(bg=bg_color)
            self.style.theme_use('clam')
            self.style.configure(".", background=bg_color, foreground=fg_color)
            plt.style.use('fast')

    def toggle_theme(self):
        """Alterna entre temas"""
        self.dark_mode = not self.dark_mode
        self.apply_theme_colors()
        if hasattr(self, 'fig_basic'):
            self.fig_basic.patch.set_facecolor('#2d2d2d' if self.dark_mode else '#ffffff')
        if hasattr(self, 'fig_detailed'):
            self.fig_detailed.patch.set_facecolor('#2d2d2d' if self.dark_mode else '#ffffff')
        if hasattr(self, 'fig_energy'):
            self.fig_energy.patch.set_facecolor('#2d2d2d' if self.dark_mode else '#ffffff')

        messagebox.showinfo("Tema", "Tema alterado!")

    def initialize_cpu_cores(self):
        core_count = psutil.cpu_count()
        self.cache['cpu_cores'] = [[0] * 60 for _ in range(core_count)]

    def setup_ui(self):
        # Header
        header_frame = ttk.Frame(self.window)
        header_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(header_frame, text="ULTRA MONITOR OS", font=('Impact', 16)).pack(side=tk.LEFT)

        # Botões de controle no header
        control_frame = ttk.Frame(header_frame)
        control_frame.pack(side=tk.RIGHT)

        ttk.Button(control_frame, text="🔄 Atualizar Tudo",
                   command=self.force_update_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="🌗 Alternar Tema",
                   command=self.toggle_theme).pack(side=tk.LEFT, padx=5)

        # Notebook
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.setup_dashboard_tab()
        self.setup_process_tab()
        self.setup_system_tab()
        self.setup_charts_tab()
        self.setup_detailed_charts_tab()  # Nova aba para gráficos detalhados
        self.setup_energy_tab()  # Nova aba para consumo de energia

    def setup_dashboard_tab(self):
        dashboard_tab = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_tab, text="🏠 Dashboard")

        main_frame = ttk.Frame(dashboard_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Métricas (Esquerda)
        metrics_frame = ttk.LabelFrame(main_frame, text="⚡ Métricas em Tempo Real", padding=15)
        metrics_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.cpu_var = tk.StringVar(value="0%")
        self.memory_var = tk.StringVar(value="0%")
        self.disk_var = tk.StringVar(value="0%")
        self.process_var = tk.StringVar(value="0")
        self.network_var = tk.StringVar(value="0 KB/s")

        # Variáveis para uso total
        self.memory_used_var = tk.StringVar(value="Usado: 0 GB / Total: 0 GB")
        self.disk_used_var = tk.StringVar(value="Usado: 0 GB / Total: 0 GB")

        metrics = [
            ("CPU", self.cpu_var, "blue"),
            (" Memória", self.memory_var, "green"),
            (" Memória (GB)", self.memory_used_var, "#90EE90"),
            (" Disco", self.disk_var, "orange"),
            (" Disco (GB)", self.disk_used_var, "#FFD700"),
            (" Processos", self.process_var, "purple"),
            (" Rede Total", self.network_var, "red")
        ]

        for i, (label, var, color) in enumerate(metrics):
            ttk.Label(metrics_frame, text=label, font=('Arial', 11, 'bold')).grid(row=i, column=0, sticky="w", pady=5)
            lbl = ttk.Label(metrics_frame, textvariable=var, font=('Arial', 12, 'bold'), foreground=color)
            lbl.grid(row=i, column=1, sticky="w", padx=10, pady=5)

        # Barra de progresso para CPU
        self.cpu_progress = ttk.Progressbar(metrics_frame, length=150, mode='determinate')
        self.cpu_progress.grid(row=0, column=2, padx=10, pady=5)

        # Barra de progresso para Memória
        self.mem_progress = ttk.Progressbar(metrics_frame, length=150, mode='determinate')
        self.mem_progress.grid(row=1, column=2, padx=10, pady=5)

        self.alert_var = tk.StringVar(value=" Sistema Estável")
        self.alert_label = ttk.Label(metrics_frame, textvariable=self.alert_var,
                                     font=('Arial', 10, 'bold'))
        self.alert_label.grid(row=7, column=0, columnspan=3, pady=15)

        # Botões de ação rápida
        action_frame = ttk.Frame(metrics_frame)
        action_frame.grid(row=8, column=0, columnspan=3, pady=10)

        ttk.Button(action_frame, text=" Gráficos Detalhados",
                   command=lambda: self.notebook.select(4)).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="⚡ Consumo Energia",
                   command=lambda: self.notebook.select(5)).pack(side=tk.LEFT, padx=5)

        # Log de Info (Direita)
        info_frame = ttk.LabelFrame(main_frame, text=" Resumo Executivo", padding=10)
        info_frame.grid(row=0, column=1, sticky="nsew")

        self.info_text = scrolledtext.ScrolledText(info_frame, height=10, font=('Consolas', 9))
        self.info_text.pack(fill=tk.BOTH, expand=True)

        main_frame.columnconfigure(0, weight=2)
        main_frame.columnconfigure(1, weight=3)
        main_frame.rowconfigure(0, weight=1)

    def setup_process_tab(self):
        process_tab = ttk.Frame(self.notebook)
        self.notebook.add(process_tab, text="🔍 Processos")

        # Frame superior com controles
        top_frame = ttk.Frame(process_tab)
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        # Controles
        ttk.Button(top_frame, text=" Finalizar Processo",
                   command=self.show_terminate_dialog,
                   style="Danger.TButton").pack(side=tk.LEFT, padx=5)

        ttk.Button(top_frame, text=" Ver Detalhes",
                   command=self.show_process_details).pack(side=tk.LEFT, padx=5)

        ttk.Button(top_frame, text=" Atualizar",
                   command=self.collect_processes).pack(side=tk.LEFT, padx=5)

        ttk.Label(top_frame, text="Filtrar:").pack(side=tk.LEFT, padx=(20, 5))
        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(top_frame, textvariable=self.filter_var, width=20)
        filter_entry.pack(side=tk.LEFT, padx=5)
        filter_entry.bind('<KeyRelease>', self.filter_processes)

        # Treeview de processos
        tree_frame = ttk.Frame(process_tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('PID', 'Nome', 'CPU%', 'Memória%', 'Memória MB', 'Threads', 'Status', 'Usuário')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=25)

        col_widths = {'PID': 70, 'Nome': 200, 'CPU%': 80, 'Memória%': 80,
                      'Memória MB': 90, 'Threads': 70, 'Status': 90, 'Usuário': 100}

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths.get(col, 100))

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        # Configurar seleção múltipla
        self.tree.configure(selectmode='extended')

        # Menu de contexto
        self.setup_context_menu()

    def setup_context_menu(self):
        """Configura menu de contexto para a treeview"""
        self.context_menu = tk.Menu(self.window, tearoff=0)

        self.context_menu.add_command(label=" Ver Detalhes",
                                      command=self.show_process_details)
        self.context_menu.add_separator()

        self.context_menu.add_command(label=" Finalizar Processo",
                                      command=lambda: self.terminate_selected("kill"))

        self.context_menu.add_separator()
        self.context_menu.add_command(label=" Copiar PID", command=self.copy_pid)
        self.context_menu.add_command(label=" Copiar Nome", command=self.copy_name)

        # Bind do menu de contexto
        self.tree.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        """Mostra menu de contexto"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.current_process_context = self.tree.item(item)['values']
            self.context_menu.post(event.x_root, event.y_root)

    def setup_system_tab(self):
        system_tab = ttk.Frame(self.notebook)
        self.notebook.add(system_tab, text=" Sistema")

        # Adicionar botão de limpeza
        control_frame = ttk.Frame(system_tab)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(control_frame, text=" Atualizar Informações",
                   command=self.collect_system_info).pack(side=tk.RIGHT)

        self.system_text = scrolledtext.ScrolledText(system_tab, font=('Consolas', 10))
        self.system_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def setup_charts_tab(self):
        charts_tab = ttk.Frame(self.notebook)
        self.notebook.add(charts_tab, text=" Gráficos Básicos")

        self.fig_basic = Figure(figsize=(10, 6), dpi=80)
        self.canvas_basic = FigureCanvasTkAgg(self.fig_basic, charts_tab)
        self.canvas_basic.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.ax_cpu = self.fig_basic.add_subplot(221)
        self.ax_mem = self.fig_basic.add_subplot(222)
        self.ax_dsk = self.fig_basic.add_subplot(223)
        self.ax_net = self.fig_basic.add_subplot(224)

        for ax in [self.ax_cpu, self.ax_mem, self.ax_dsk, self.ax_net]:
            ax.grid(True, alpha=0.3)

        self.setup_basic_lines()

    def setup_basic_lines(self):
        self.line_cpu, = self.ax_cpu.plot([], [], 'b-', lw=1.5)
        self.ax_cpu.set_title('CPU (%)')
        self.ax_cpu.set_ylim(0, 100)

        self.line_mem, = self.ax_mem.plot([], [], 'g-', lw=1.5)
        self.ax_mem.set_title('Memória (%)')
        self.ax_mem.set_ylim(0, 100)

        self.line_dsk, = self.ax_dsk.plot([], [], 'orange', lw=1.5)
        self.ax_dsk.set_title('Disco (%)')
        self.ax_dsk.set_ylim(0, 100)

        self.line_net, = self.ax_net.plot([], [], 'r-', lw=1.5)
        self.ax_net.set_title('Rede (KB/s)')

    def setup_detailed_charts_tab(self):
        """Aba com gráficos detalhados de núcleos, IO, etc."""
        det_tab = ttk.Frame(self.notebook)
        self.notebook.add(det_tab, text=" Gráficos Detalhados")

        # Frame principal com scrollbar
        main_frame = ttk.Frame(det_tab)
        main_frame.pack(fill=tk.BOTH, expand=True)

        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.fig_detailed = Figure(figsize=(12, 10), dpi=80)
        self.canvas_detailed = FigureCanvasTkAgg(self.fig_detailed, canvas_frame)
        self.canvas_detailed.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Criar 6 subplots para análise detalhada
        self.ax_cores = self.fig_detailed.add_subplot(321)
        self.ax_io_disk = self.fig_detailed.add_subplot(322)
        self.ax_io_net = self.fig_detailed.add_subplot(323)
        self.ax_mem_detail = self.fig_detailed.add_subplot(324)
        self.ax_cpu_freq = self.fig_detailed.add_subplot(325)
        self.ax_process_count = self.fig_detailed.add_subplot(326)

        self.fig_detailed.tight_layout(pad=3.0)

        # Configurar títulos dos gráficos
        self.ax_cores.set_title('Uso por Núcleo da CPU (%)')
        self.ax_io_disk.set_title('IO de Disco (KB/s)')
        self.ax_io_net.set_title('IO de Rede (KB/s)')
        self.ax_mem_detail.set_title('Uso Detalhado de Memória')
        self.ax_cpu_freq.set_title('Frequência da CPU (MHz)')
        self.ax_process_count.set_title('Contagem de Processos')

        # Adicionar grade a todos os gráficos
        for ax in [self.ax_cores, self.ax_io_disk, self.ax_io_net,
                   self.ax_mem_detail, self.ax_cpu_freq, self.ax_process_count]:
            ax.grid(True, alpha=0.3)

        # Botões de controle
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(control_frame, text=" Atualizar Gráficos",
                   command=self.update_detailed_charts).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text=" Salvar Imagem",
                   command=self.save_detailed_chart).pack(side=tk.LEFT, padx=5)

    def setup_energy_tab(self):
        """Aba para monitoramento de energia e temperatura"""
        energy_tab = ttk.Frame(self.notebook)
        self.notebook.add(energy_tab, text="⚡ Energia & Temperatura")

        # Frame principal
        main_frame = ttk.Frame(energy_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Frame esquerdo - Estatísticas
        left_frame = ttk.LabelFrame(main_frame, text=" Estatísticas de Energia", padding=15)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Informações de bateria
        self.battery_percent_var = tk.StringVar(value="Bateria: --")
        self.battery_power_var = tk.StringVar(value="Potência: --")
        self.battery_time_var = tk.StringVar(value="Tempo restante: --")
        self.battery_status_var = tk.StringVar(value="Status: --")

        # Informações de temperatura
        self.cpu_temp_var = tk.StringVar(value="")
        self.gpu_temp_var = tk.StringVar(value="")

        # Labels
        ttk.Label(left_frame, text=" INFORMAÇÕES DE BATERIA",
                  font=('Arial', 11, 'bold')).grid(row=0, column=0, columnspan=2, pady=5, sticky="w")

        ttk.Label(left_frame, textvariable=self.battery_percent_var,
                  font=('Arial', 10)).grid(row=1, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Label(left_frame, textvariable=self.battery_power_var,
                  font=('Arial', 10)).grid(row=2, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Label(left_frame, textvariable=self.battery_time_var,
                  font=('Arial', 10)).grid(row=3, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Label(left_frame, textvariable=self.battery_status_var,
                  font=('Arial', 10)).grid(row=4, column=0, columnspan=2, sticky="w", pady=2)

        ttk.Separator(left_frame, orient='horizontal').grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Label(left_frame, text="",
                  font=('Arial', 11, 'bold')).grid(row=6, column=0, columnspan=2, pady=5, sticky="w")

        ttk.Label(left_frame, textvariable=self.cpu_temp_var,
                  font=('Arial', 10)).grid(row=7, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Label(left_frame, textvariable=self.gpu_temp_var,
                  font=('Arial', 10)).grid(row=8, column=0, columnspan=2, sticky="w", pady=2)

        # Frame direito - Gráficos
        right_frame = ttk.LabelFrame(main_frame, text="📈 Gráficos de Energia", padding=10)
        right_frame.grid(row=0, column=1, sticky="nsew")

        self.fig_energy = Figure(figsize=(8, 6), dpi=80)
        self.canvas_energy = FigureCanvasTkAgg(self.fig_energy, right_frame)
        self.canvas_energy.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Criar 2 subplots para energia
        self.ax_power = self.fig_energy.add_subplot(211)
        self.ax_temp = self.fig_energy.add_subplot(212)

        self.ax_power.set_title('Consumo de Energia')
        self.ax_temp.set_title('Temperaturas')

        for ax in [self.ax_power, self.ax_temp]:
            ax.grid(True, alpha=0.3)

        self.fig_energy.tight_layout(pad=3.0)

        # Frame inferior - Controles
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Button(control_frame, text=" Atualizar Dados",
                   command=self.update_energy_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="⚡ Modo Economia",
                   command=self.enable_power_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="📊 Relatório Detalhado",
                   command=self.show_energy_report).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=1)

    # ====== FUNÇÕES DE ATUALIZAÇÃO ======

    def force_update_all(self):
        """Força atualização de todos os dados"""
        self.cache['last_process_update'] = 0
        self.cache['last_system_update'] = 0
        self.collect_processes()
        self.collect_system_info()
        self.update_energy_data()
        messagebox.showinfo("Atualizado", "✅ Todos os dados foram atualizados!")

    # ====== FUNÇÕES DE GRÁFICOS DETALHADOS ======

    def update_detailed_charts(self, x=None):
        """Atualiza gráficos detalhados"""
        if x is None:
            x = range(60)

        try:
            # 1. Gráfico de núcleos da CPU
            self.ax_cores.clear()
            self.ax_cores.set_title('Uso por Núcleo da CPU (%)')
            self.ax_cores.set_ylim(0, 100)
            self.ax_cores.set_xlabel('Tempo (segundos)')
            self.ax_cores.set_ylabel('Uso (%)')
            self.ax_cores.grid(True, alpha=0.3)

            core_count = len(self.cache['cpu_cores'])
            if core_count > 0:
                cmap = plt.cm.get_cmap('viridis', core_count)
                for i, core_hist in enumerate(self.cache['cpu_cores']):
                    if len(core_hist) == 60:
                        self.ax_cores.plot(x, core_hist, lw=1, color=cmap(i), label=f'Núcleo {i + 1}')

                if core_count <= 8:  # Mostrar legenda apenas se tiver poucos núcleos
                    self.ax_cores.legend(loc='upper right', fontsize='small')

            # 2. Gráfico de IO de Disco
            self.ax_io_disk.clear()
            self.ax_io_disk.set_title('IO de Disco (KB/s)')
            self.ax_io_disk.set_xlabel('Tempo (segundos)')
            self.ax_io_disk.set_ylabel('KB/s')
            self.ax_io_disk.grid(True, alpha=0.3)

            if len(self.cache['disk_io']['read']) == 60:
                self.ax_io_disk.plot(x, self.cache['disk_io']['read'], 'b-', lw=1.5, label='Leitura')
                self.ax_io_disk.plot(x, self.cache['disk_io']['write'], 'r-', lw=1.5, label='Escrita')
                self.ax_io_disk.legend(loc='upper left', fontsize='small')

            # 3. Gráfico de IO de Rede
            self.ax_io_net.clear()
            self.ax_io_net.set_title('IO de Rede (KB/s)')
            self.ax_io_net.set_xlabel('Tempo (segundos)')
            self.ax_io_net.set_ylabel('KB/s')
            self.ax_io_net.grid(True, alpha=0.3)

            if len(self.cache['network_io']['sent']) == 60:
                self.ax_io_net.plot(x, self.cache['network_io']['sent'], 'g-', lw=1.5, label='Upload')
                self.ax_io_net.plot(x, self.cache['network_io']['recv'], 'm-', lw=1.5, label='Download')
                self.ax_io_net.legend(loc='upper left', fontsize='small')

            # 4. Gráfico detalhado de memória
            self.ax_mem_detail.clear()
            self.ax_mem_detail.set_title('Uso Detalhado de Memória')
            self.ax_mem_detail.set_xlabel('Tempo (segundos)')
            self.ax_mem_detail.set_ylabel('Uso (%)')
            self.ax_mem_detail.grid(True, alpha=0.3)
            self.ax_mem_detail.set_ylim(0, 100)

            if len(self.cache['memory_history']) == 60:
                self.ax_mem_detail.plot(x, self.cache['memory_history'], 'g-', lw=2, label='Memória Total')

                # Adicionar linha de média
                avg_memory = np.mean(self.cache['memory_history'])
                self.ax_mem_detail.axhline(y=avg_memory, color='r', linestyle='--', alpha=0.5,
                                           label=f'Média: {avg_memory:.1f}%')
                self.ax_mem_detail.legend(loc='upper left', fontsize='small')

            # 5. Gráfico de frequência da CPU
            self.ax_cpu_freq.clear()
            self.ax_cpu_freq.set_title('Frequência da CPU (MHz)')
            self.ax_cpu_freq.set_xlabel('Tempo (segundos)')
            self.ax_cpu_freq.set_ylabel('MHz')
            self.ax_cpu_freq.grid(True, alpha=0.3)

            try:
                # Tentar obter frequência da CPU
                cpu_freq = psutil.cpu_freq()
                if cpu_freq:
                    current_freq = cpu_freq.current
                    max_freq = cpu_freq.max

                    # Criar histórico de frequência simulado baseado no uso da CPU
                    freq_history = []
                    for cpu_usage in self.cache['cpu_history']:
                        freq = current_freq * (0.3 + 0.7 * (cpu_usage / 100))
                        freq_history.append(min(freq, max_freq))

                    if len(freq_history) == 60:
                        self.ax_cpu_freq.plot(x, freq_history, 'orange', lw=1.5, label='Frequência Atual')
                        self.ax_cpu_freq.axhline(y=max_freq, color='r', linestyle='--', alpha=0.5,
                                                 label=f'Máx: {max_freq:.0f} MHz')
                        self.ax_cpu_freq.legend(loc='upper right', fontsize='small')
            except:
                pass

            # 6. Gráfico de contagem de processos
            self.ax_process_count.clear()
            self.ax_process_count.set_title('Contagem de Processos')
            self.ax_process_count.set_xlabel('Tempo (segundos)')
            self.ax_process_count.set_ylabel('Nº de Processos')
            self.ax_process_count.grid(True, alpha=0.3)

            # Criar histórico simulado de contagem de processos
            if len(self.cache['processes']) > 0:
                base_count = len(self.cache['processes'])
                process_history = []
                for i in range(60):
                    variation = np.random.randint(-5, 6)  # Variação aleatória
                    process_history.append(max(10, base_count + variation))

                if len(process_history) == 60:
                    self.ax_process_count.plot(x, process_history, 'purple', lw=1.5, label='Processos Ativos')
                    avg_processes = np.mean(process_history)
                    self.ax_process_count.axhline(y=avg_processes, color='b', linestyle='--', alpha=0.5,
                                                  label=f'Média: {avg_processes:.0f}')
                    self.ax_process_count.legend(loc='upper right', fontsize='small')

            self.canvas_detailed.draw_idle()

        except Exception as e:
            print(f"Erro ao atualizar gráficos detalhados: {e}")

    def save_detailed_chart(self):
        """Salva o gráfico detalhado como imagem"""
        try:
            from tkinter import filedialog
            import datetime

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
                initialfile=f"grafico_detalhado_{timestamp}.png"
            )

            if filename:
                self.fig_detailed.savefig(filename, dpi=150, bbox_inches='tight')
                messagebox.showinfo("Sucesso", f"Gráfico salvo em:\n{filename}")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar gráfico: {e}")

    # ====== FUNÇÕES DE ENERGIA E TEMPERATURA ======

    def update_energy_data(self):
        """Atualiza dados de energia e temperatura"""
        try:
            # 1. Informações de bateria
            if hasattr(psutil, 'sensors_battery'):
                battery = psutil.sensors_battery()
                if battery:
                    percent = battery.percent
                    power_plugged = battery.power_plugged
                    secsleft = battery.secsleft

                    self.battery_percent_var.set(f"🔋 Bateria: {percent}%")

                    if power_plugged:
                        self.battery_power_var.set("🔌 Conectado à energia")
                        self.battery_status_var.set("Status: Carregando")
                    else:
                        self.battery_power_var.set("🔋 Usando bateria")
                        self.battery_status_var.set("Status: Descarregando")

                    if secsleft == psutil.POWER_TIME_UNLIMITED:
                        self.battery_time_var.set("⏰ Tempo restante: Ilimitado (conectado)")
                    elif secsleft == psutil.POWER_TIME_UNKNOWN:
                        self.battery_time_var.set("⏰ Tempo restante: Desconhecido")
                    else:
                        hours = secsleft // 3600
                        minutes = (secsleft % 3600) // 60
                        self.battery_time_var.set(f"⏰ Tempo restante: {hours}h {minutes}min")
                else:
                    self.battery_percent_var.set("🔋 Bateria: Não disponível")
                    self.battery_power_var.set("🔌 Status: Não disponível")
            else:
                self.battery_percent_var.set("🔋 Bateria: API não disponível")

            # 2. Informações de temperatura
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()
                if temps:
                    # Tentar obter temperatura da CPU
                    if 'coretemp' in temps:
                        cpu_temp = temps['coretemp'][0].current
                        self.cpu_temp_var.set(f"")
                        self.update_history_list(self.cache['temperature_history'], cpu_temp)
                    elif 'acpitz' in temps:
                        cpu_temp = temps['acpitz'][0].current
                        self.cpu_temp_var.set(f"")
                    else:
                        self.cpu_temp_var.set("")
                else:
                    self.cpu_temp_var.set("")
            else:
                self.cpu_temp_var.set("")

            # 3. Atualizar gráficos de energia
            self.update_energy_charts()

        except Exception as e:
            print(f"Erro ao atualizar dados de energia: {e}")

    def update_energy_charts(self):
        """Atualiza gráficos de energia"""
        try:
            x = range(60)

            # Gráfico de energia/consumo
            self.ax_power.clear()
            self.ax_power.set_title('Consumo de Energia')
            self.ax_power.set_xlabel('Tempo (segundos)')
            self.ax_power.set_ylabel('Uso Relativo')
            self.ax_power.grid(True, alpha=0.3)

            # Simular dados de consumo baseado no uso da CPU
            power_data = []
            for cpu_usage in self.cache['cpu_history']:
                power = 10 + (cpu_usage * 0.5) + np.random.rand() * 5
                power_data.append(power)

            if len(power_data) == 60:
                self.ax_power.plot(x, power_data, 'orange', lw=2, label='Consumo Estimado')
                self.ax_power.fill_between(x, 0, power_data, alpha=0.3, color='orange')
                self.ax_power.legend(loc='upper right')

            # Gráfico de temperatura
            self.ax_temp.clear()
            self.ax_temp.set_title('Temperatura')
            self.ax_temp.set_xlabel('Tempo (segundos)')
            self.ax_temp.set_ylabel('Temperatura (°C)')
            self.ax_temp.grid(True, alpha=0.3)

            # Usar dados de temperatura se disponíveis, senão simular
            if len(self.cache['temperature_history']) > 0 and self.cache['temperature_history'][-1] > 0:
                temp_data = self.cache['temperature_history']
            else:
                # Simular dados de temperatura
                temp_data = []
                base_temp = 40
                for cpu_usage in self.cache['cpu_history']:
                    temp = base_temp + (cpu_usage * 0.2) + np.random.rand() * 3
                    temp_data.append(temp)

            if len(temp_data) == 60:
                self.ax_temp.plot(x, temp_data, 'r', lw=2, label='Temperatura')
                self.ax_temp.axhline(y=70, color='orange', linestyle='--', alpha=0.7, label='Limite Alto')
                self.ax_temp.axhline(y=85, color='red', linestyle='--', alpha=0.7, label='Crítico')
                self.ax_temp.legend(loc='upper right')
                self.ax_temp.set_ylim(20, 100)

            self.canvas_energy.draw_idle()

        except Exception as e:
            print(f"Erro ao atualizar gráficos de energia: {e}")

    def enable_power_save(self):
        """Ativa modo economia de energia"""
        try:
            if sys.platform == 'win32':
                # Windows: tentar ajustar plano de energia
                subprocess.run(['powercfg', '/setactive', 'a1841308-3541-4fab-bc81-f71556f20b4a'])  # Economia
                messagebox.showinfo("Modo Economia", "✅ Modo economia de energia ativado!")
            else:
                messagebox.showinfo("Modo Economia",
                                    "Para melhor economia de energia:\n\n"
                                    "1. Reduza o brilho da tela\n"
                                    "2. Feche programas desnecessários\n"
                                    "3. Desative efeitos visuais\n"
                                    "4. Use modo avião se não precisar de rede")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao ativar modo economia: {e}")

    def show_energy_report(self):
        """Mostra relatório detalhado de energia"""
        try:
            report = f"""
            📊 RELATÓRIO DE ENERGIA E TEMPERATURA
            {'=' * 40}
            Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

            CONSUMO DE ENERGIA:
            {'-' * 30}"""

            if hasattr(psutil, 'sensors_battery'):
                battery = psutil.sensors_battery()
                if battery:
                    report += f"""
            Bateria: {battery.percent}%
            Status: {'Conectado' if battery.power_plugged else 'Bateria'}
            Tempo restante: {battery.secsleft if battery.secsleft != -1 else 'Desconhecido'} segundos"""

            report += f"""

            TEMPERATURAS:
            {'-' * 30}
            CPU: {self.cpu_temp_var.get().replace('Temperatura CPU: ', '')}

            CONSUMO ATUAL:
            {'-' * 30}
            CPU: {self.cache['cpu']}%
            Memória: {self.cache['memory']}%
            Disco: {self.cache['disk']}%

            RECOMENDAÇÕES:
            {'-' * 30}
            """

            if self.cache['cpu'] > 80:
                report += "• Considere fechar programas pesados\n"
            if self.cache['memory'] > 80:
                report += "• Considere reiniciar o sistema\n"
            if 'Alta' in self.cpu_temp_var.get():
                report += "• Considere limpar ventilação do sistema\n"

            # Mostrar relatório
            report_window = tk.Toplevel(self.window)
            report_window.title("Relatório de Energia")
            report_window.geometry("500x400")

            text_widget = scrolledtext.ScrolledText(report_window, font=('Consolas', 10))
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text_widget.insert('1.0', report)
            text_widget.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gerar relatório: {e}")

    # ====== FUNÇÕES DE GERENCIAMENTO DE PROCESSOS ======

    def show_terminate_dialog(self):
        """Mostra diálogo para finalizar processos"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione pelo menos um processo primeiro!")
            return

        # Obter informações dos processos selecionados
        processes = []
        for item in selected:
            values = self.tree.item(item)['values']
            processes.append({
                'pid': values[0],
                'name': values[1]
            })

        # Criar diálogo simples
        if len(processes) == 1:
            msg = f"Tem certeza que deseja finalizar o processo '{processes[0]['name']}' (PID: {processes[0]['pid']})?"
        else:
            msg = f"Tem certeza que deseja finalizar {len(processes)} processos selecionados?"

        if messagebox.askyesno("Confirmar Finalização", msg, icon='warning'):
            self.execute_bulk_terminate(processes)

    def execute_bulk_terminate(self, processes):
        """Executa finalização em massa de processos"""
        success_count = 0
        fail_count = 0

        for proc in processes:
            pid = proc['pid']
            name = proc['name']

            try:
                # Tentar finalizar o processo
                if sys.platform == 'win32':
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                                   capture_output=True, timeout=5)
                else:
                    import signal
                    os.kill(pid, signal.SIGTERM)

                success_count += 1
                time.sleep(0.1)

            except Exception as e:
                fail_count += 1
                print(f"Erro ao finalizar {name} (PID: {pid}): {e}")

        # Atualizar lista de processos
        self.collect_processes()

        # Mostrar resultado
        if fail_count == 0:
            messagebox.showinfo("Sucesso", f"✅ {success_count} processo(s) finalizado(s) com sucesso!")
        else:
            messagebox.showwarning("Resultado",
                                   f" {success_count} processo(s) finalizado(s) com sucesso!\n"
                                   f" {fail_count} processo(s) falharam.")

    def show_process_details(self):
        """Mostra detalhes do processo selecionado"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione um processo primeiro!")
            return

        item = self.tree.item(selected[0])
        pid = item['values'][0]

        try:
            proc = psutil.Process(pid)

            with proc.oneshot():
                info = f"""
                DETALHES DO PROCESSO - {datetime.now().strftime('%H:%M:%S')}
                {'=' * 50}

                Informações Básicas:
                Nome: {proc.name()}
                PID: {proc.pid}
                PPID (Pai): {proc.ppid()}
                Executável: {proc.exe() if hasattr(proc, 'exe') else 'N/A'}
                Diretório: {proc.cwd() if hasattr(proc, 'cwd') else 'N/A'}

                Usuário:
                Usuário: {proc.username()}

                Recursos:
                CPU (%): {item['values'][2]}
                Memória (%): {item['values'][3]}
                Memória (MB): {item['values'][4]}
                Threads: {proc.num_threads()}
                Status: {proc.status()}

                Tempos:
                Criado: {datetime.fromtimestamp(proc.create_time()).strftime('%d/%m/%Y %H:%M:%S')}
                """

            # Mostrar em nova janela
            details_window = tk.Toplevel(self.window)
            details_window.title(f"Detalhes do Processo - PID: {pid}")
            details_window.geometry("600x400")

            text_widget = scrolledtext.ScrolledText(details_window, font=('Consolas', 9))
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text_widget.insert('1.0', info)
            text_widget.config(state=tk.DISABLED)

            # Botões de ação
            button_frame = ttk.Frame(details_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="💀 Finalizar Processo",
                       command=lambda: [details_window.destroy(),
                                        self.terminate_single_process(pid, proc.name())],
                       style="Danger.TButton").pack(side=tk.LEFT, padx=5)

            ttk.Button(button_frame, text="Fechar",
                       command=details_window.destroy).pack(side=tk.RIGHT, padx=5)

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao obter detalhes: {e}")

    def terminate_single_process(self, pid, name):
        """Finaliza um único processo"""
        try:
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                               capture_output=True, timeout=5)
            else:
                import signal
                os.kill(pid, signal.SIGTERM)

            time.sleep(0.5)
            self.collect_processes()
            messagebox.showinfo("Sucesso", f"Processo '{name}' (PID: {pid}) finalizado!")

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao finalizar processo: {e}")

    def terminate_selected(self, method):
        """Finaliza processos selecionados"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione pelo menos um processo primeiro!")
            return

        processes = []
        for item in selected:
            values = self.tree.item(item)['values']
            processes.append({
                'pid': values[0],
                'name': values[1]
            })

        self.execute_bulk_terminate(processes)

    def copy_pid(self):
        """Copia PID para área de transferência"""
        selected = self.tree.selection()
        if selected:
            pids = []
            for item in selected:
                pid = self.tree.item(item)['values'][0]
                pids.append(str(pid))

            self.window.clipboard_clear()
            self.window.clipboard_append('\n'.join(pids))

            if len(pids) == 1:
                messagebox.showinfo("Copiado", f"PID {pids[0]} copiado!")
            else:
                messagebox.showinfo("Copiado", f"{len(pids)} PIDs copiados!")

    def copy_name(self):
        """Copia nome do processo para área de transferência"""
        selected = self.tree.selection()
        if selected:
            names = []
            for item in selected:
                name = self.tree.item(item)['values'][1]
                names.append(name)

            self.window.clipboard_clear()
            self.window.clipboard_append('\n'.join(names))

            if len(names) == 1:
                messagebox.showinfo("Copiado", f"Nome '{names[0]}' copiado!")
            else:
                messagebox.showinfo("Copiado", f"{len(names)} nomes copiados!")

    def filter_processes(self, event=None):
        """Filtra processos baseado no texto digitado"""
        self.update_process_ui(self.cache['processes'])

    # ====== MONITORAMENTO ======

    def start_threaded_monitoring(self):
        self.monitor_thread = threading.Thread(target=self.monitoring_worker, daemon=True)
        self.monitor_thread.start()
        self.process_data_queue()
        self.update_charts_loop()


    def monitoring_worker(self):
        last_net = psutil.net_io_counters()
        last_disk = psutil.disk_io_counters()

        while self.is_running:
            try:
                now = time.time()

                # Coleta dados básicos
                cpu = psutil.cpu_percent(interval=0.5)
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage('/')

                # Atualizar cache com valores atuais
                self.cache['cpu'] = cpu
                self.cache['memory'] = mem.percent
                self.cache['disk'] = disk.percent

                # Calcula uso em GB
                self.cache['memory_total_gb'] = mem.total / (1024 ** 3)
                self.cache['memory_used_gb'] = mem.used / (1024 ** 3)
                self.cache['memory_available_gb'] = mem.available / (1024 ** 3)

                self.cache['disk_total_gb'] = disk.total / (1024 ** 3)
                self.cache['disk_used_gb'] = disk.used / (1024 ** 3)
                self.cache['disk_free_gb'] = disk.free / (1024 ** 3)

                # Rede
                curr_net = psutil.net_io_counters()
                net_sent = (curr_net.bytes_sent - last_net.bytes_sent) / 1024
                net_recv = (curr_net.bytes_recv - last_net.bytes_recv) / 1024
                last_net = curr_net

                # Disco IO
                curr_disk = psutil.disk_io_counters()
                disk_read = (curr_disk.read_bytes - last_disk.read_bytes) / 1024 if last_disk else 0
                disk_write = (curr_disk.write_bytes - last_disk.write_bytes) / 1024 if last_disk else 0
                last_disk = curr_disk

                cores = psutil.cpu_percent(percpu=True)

                # Atualiza históricos
                self.update_history_list(self.cache['cpu_history'], cpu)
                self.update_history_list(self.cache['memory_history'], mem.percent)
                self.update_history_list(self.cache['disk_history'], disk.percent)
                self.update_history_list(self.cache['network_history'], net_sent + net_recv)

                self.update_history_list(self.cache['disk_io']['read'], disk_read)
                self.update_history_list(self.cache['disk_io']['write'], disk_write)
                self.update_history_list(self.cache['network_io']['sent'], net_sent)
                self.update_history_list(self.cache['network_io']['recv'], net_recv)

                for i, c_val in enumerate(cores):
                    if i < len(self.cache['cpu_cores']):
                        self.update_history_list(self.cache['cpu_cores'][i], c_val)

                self.data_queue.put(('metrics', {
                    'cpu': cpu, 'memory': mem.percent, 'disk': disk.percent,
                    'network': net_sent + net_recv, 'cores': cores,
                    'memory_used_gb': self.cache['memory_used_gb'],
                    'memory_total_gb': self.cache['memory_total_gb'],
                    'disk_used_gb': self.cache['disk_used_gb'],
                    'disk_total_gb': self.cache['disk_total_gb']
                }))

                if now - self.cache['last_process_update'] > 3:
                    self.collect_processes()
                    self.cache['last_process_update'] = now

                if now - self.cache['last_system_update'] > 10:
                    self.collect_system_info()
                    self.cache['last_system_update'] = now

                # Atualizar dados de energia periodicamente
                if now % 30 < 1:  # A cada ~30 segundos
                    self.update_energy_data()

            except Exception as e:
                print(f"Erro no worker: {e}")
                time.sleep(1)

    def update_history_list(self, lst, value):
        if len(lst) >= 60:
            lst.pop(0)
        lst.append(value)

    def collect_processes(self):
        procs = []
        cpu_count = psutil.cpu_count(logical=True)

# Pega as variaveis para ser exibida no gerenciador
        for p in psutil.process_iter(
                ['pid', 'name', 'cpu_percent', 'memory_percent', 'username', 'num_threads', 'memory_info']):
            try:
                if p.info['pid'] == 0:
                    continue

                mem_mb = p.info['memory_info'].rss / (1024 * 1024) if p.info['memory_info'] else 0
                raw_cpu = p.info['cpu_percent'] or 0
                normalized_cpu = raw_cpu / cpu_count

                procs.append({
                    'pid': p.info['pid'],
                    'name': p.info['name'],
                    'cpu': normalized_cpu,
                    'mem_pct': p.info['memory_percent'] or 0,
                    'mem_mb': mem_mb,
                    'threads': p.info['num_threads'] or 0,
                    'status': p.status(),
                    'user': p.info['username'] or 'N/A'
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: x['cpu'], reverse=True)
        self.cache['processes'] = procs[:200]
        self.data_queue.put(('processes', self.cache['processes']))

    def collect_system_info(self):
        try:
            boot = datetime.fromtimestamp(psutil.boot_time())
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            info = f"""
            SISTEMA OPERACIONAL
            -------------------
            OS: {platform.system()} {platform.release()}
            Versão: {platform.version()}
            Boot: {boot.strftime('%d/%m/%Y %H:%M:%S')}
            Uptime: {datetime.now() - boot}

            HARDWARE
            --------
            CPU: {psutil.cpu_count(logical=False)} Físicos / {psutil.cpu_count()} Lógicos
            Freq: {psutil.cpu_freq().current:.0f}Mhz

            MEMÓRIA RAM
            -----------
            Total: {mem.total / (1024 ** 3):.2f} GB
            Usado: {mem.used / (1024 ** 3):.2f} GB
            Disponível: {mem.available / (1024 ** 3):.2f} GB
            Percentual: {mem.percent:.1f}%

            ARMAZENAMENTO
            -------------
            Total: {disk.total / (1024 ** 3):.2f} GB
            Usado: {disk.used / (1024 ** 3):.2f} GB
            Livre: {disk.free / (1024 ** 3):.2f} GB
            Percentual: {disk.percent:.1f}%

            REDE
            ----
            Hostname: {socket.gethostname()}
            IP Local: {socket.gethostbyname(socket.gethostname())}
            """
            self.data_queue.put(('sys_info', info))
        except Exception as e:
            self.data_queue.put(('sys_info', f"Erro ao coletar informações: {e}"))

    def process_data_queue(self):
        try:
            while not self.data_queue.empty():
                dtype, data = self.data_queue.get_nowait()
                if dtype == 'metrics':
                    self.update_metrics_ui(data)
                elif dtype == 'processes':
                    self.update_process_ui(data)
                elif dtype == 'sys_info':
                    self.system_text.delete('1.0', tk.END)
                    self.system_text.insert('1.0', data)
        except:
            pass

        if self.is_running:
            self.window.after(100, self.process_data_queue)

    def update_metrics_ui(self, data):
        # Atualiza métricas básicas
        self.cpu_var.set(f"{data['cpu']:.1f}%")
        self.memory_var.set(f"{data['memory']:.1f}%")
        self.disk_var.set(f"{data['disk']:.1f}%")
        self.network_var.set(f"{data['network']:.1f} KB/s")
        self.process_var.set(str(len(self.cache['processes'])))

        # Atualiza métricas de uso total
        self.memory_used_var.set(f"Usado: {data['memory_used_gb']:.1f} GB / Total: {data['memory_total_gb']:.1f} GB")
        self.disk_used_var.set(f"Usado: {data['disk_used_gb']:.1f} GB / Total: {data['disk_total_gb']:.1f} GB")

        # Atualiza barras de progresso
        self.cpu_progress['value'] = data['cpu']
        self.mem_progress['value'] = data['memory']

        # Status do sistema
        status = "✅ Estável"
        color = "green"
        if data['cpu'] > 90 or data['memory'] > 90:
            status = "🔴 CRÍTICO"
            color = "red"
        elif data['cpu'] > 75 or data['memory'] > 75:
            status = "⚠️ Atenção"
            color = "orange"

        self.alert_var.set(status)
        self.alert_label.configure(foreground=color)

        # Log
        log_msg = f"[{datetime.now().strftime('%H:%M:%S')}] CPU: {data['cpu']}% | RAM: {data['memory']}% | RAM(GB): {data['memory_used_gb']:.1f}\n"
        self.info_text.insert('1.0', log_msg)
        if float(self.info_text.index('end')) > 100:
            self.info_text.delete('100.0', tk.END)

    def update_process_ui(self, processes):
        search = self.filter_var.get().lower()
        if search:
            processes = [p for p in processes if search in p['name'].lower() or search in str(p['pid'])]

        self.tree.delete(*self.tree.get_children())

        for p in processes:
            vals = (p['pid'], p['name'], f"{p['cpu']:.1f}%", f"{p['mem_pct']:.1f}%",
                    f"{p['mem_mb']:.1f}", p['threads'], p['status'], p['user'])

            tags = ()
            if p['cpu'] > 20:
                tags = ('high_cpu',)
            elif p['mem_pct'] > 10:
                tags = ('high_mem',)

            self.tree.insert('', 'end', values=vals, tags=tags)

        self.tree.tag_configure('high_cpu', foreground='red')
        self.tree.tag_configure('high_mem', foreground='orange')

    def update_charts_loop(self):
        if not self.is_running:
            return

        x = range(60)

        # Atualizar gráficos básicos
        self.line_cpu.set_data(x, self.cache['cpu_history'])
        self.line_mem.set_data(x, self.cache['memory_history'])
        self.line_dsk.set_data(x, self.cache['disk_history'])
        self.line_net.set_data(x, self.cache['network_history'])

        max_net = max(self.cache['network_history'])
        self.ax_net.set_ylim(0, max(100, max_net * 1.2))

        self.ax_cpu.relim()
        self.ax_cpu.autoscale_view()
        self.ax_mem.relim()
        self.ax_mem.autoscale_view()
        self.ax_dsk.relim()
        self.ax_dsk.autoscale_view()
        self.ax_net.relim()
        self.ax_net.autoscale_view()

        self.canvas_basic.draw_idle()

        # Verificar qual aba está ativa
        current_tab = self.notebook.select()
        if current_tab:
            tab_text = self.notebook.tab(current_tab, "text")

            # Atualizar gráficos detalhados se a aba estiver ativa
            if "Gráficos Detalhados" in tab_text:
                self.update_detailed_charts(x)

            # Atualizar gráficos de energia se a aba estiver ativa
            if "Energia" in tab_text:
                self.update_energy_charts()

        self.window.after(1000, self.update_charts_loop)

    def on_closing(self):
        if messagebox.askokcancel("Sair", "Deseja fechar o Monitor?"):
            self.is_running = False
            self.window.destroy()
            sys.exit(0)


if __name__ == "__main__":
    app = UltraOptimizedOSMonitor()
    app.window.mainloop()