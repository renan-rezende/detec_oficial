"""
Visualização de detecções em tempo real — Otimizada

Otimizações aplicadas:
1. Gráfico de barras: artistas pré-criados, só atualiza alturas (sem ax.clear())
2. Gráfico de barras: throttle de 10 updates/s (não 33/s)
3. Gráfico de barras: draw_idle() ao invés de draw() bloqueante
4. CSV: cache com verificação de mtime (evita releitura desnecessária)
5. Gráfico de linha: draw_idle() ao invés de draw()
"""
import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk
import logging
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
import pandas as pd
import os
from datetime import datetime, timedelta
from config import UI_UPDATE_INTERVAL, RANGE_ORDER, RANGE_LABELS, DATA_DIR


logger = logging.getLogger('PelletDetector.detection_view')


class DetectionViewFrame(ctk.CTkFrame):
    """Frame de visualização de detecções com rendering otimizado"""

    def __init__(self, parent, camera_manager, camera_id):
        super().__init__(parent)

        self.parent = parent
        self.camera_manager = camera_manager
        self.camera_id = camera_id

        # Obter config da câmera
        self.config = camera_manager.cameras.get(camera_id)
        if self.config is None:
            logger.error(f"Câmera {camera_id} não encontrada")
            self.parent.show_camera_list()
            return

        # Estado interno
        self.time_interval = "1 hora"
        self._last_bar_update = 0.0     # Throttle do gráfico de barras
        self._csv_last_mtime = 0        # Cache: última modificação do CSV
        self._csv_cache = None           # Cache: DataFrame do CSV

        # ===== LAYOUT =====

        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=20, pady=15)

        title = ctk.CTkLabel(header_frame, text=f"Câmera: {self.config.name}",
                            font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(side="left", padx=10)

        back_btn = ctk.CTkButton(header_frame, text="← Voltar", width=100,
                                command=self.parent.show_camera_list)
        back_btn.pack(side="right", padx=10)

        # Container principal (split horizontal)
        main_container = ctk.CTkFrame(self)
        main_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Left: Vídeo (60%)
        video_frame = ctk.CTkFrame(main_container)
        video_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.video_label = ctk.CTkLabel(video_frame, text="Aguardando frames...")
        self.video_label.pack(fill="both", expand=True, padx=10, pady=10)

        self.info_label = ctk.CTkLabel(video_frame, text="Inicializando...",
                                      font=ctk.CTkFont(size=12))
        self.info_label.pack(pady=5)

        # Right: Gráficos (40%)
        graphs_container = ctk.CTkFrame(main_container, width=450)
        graphs_container.pack(side="right", fill="both", padx=(10, 0))
        graphs_container.pack_propagate(False)

        # === GRÁFICO DE BARRAS (artistas pré-criados) ===
        bar_graph_frame = ctk.CTkFrame(graphs_container)
        bar_graph_frame.pack(fill="both", expand=True, pady=(0, 10))

        bar_title = ctk.CTkLabel(bar_graph_frame, text="Distribuição Granulométrica",
                                 font=ctk.CTkFont(size=13, weight="bold"))
        bar_title.pack(pady=5)

        self.fig_bar = Figure(figsize=(5, 3), dpi=80, facecolor='#2b2b2b')
        self.ax_bar = self.fig_bar.add_subplot(111)
        self._setup_bar_chart()

        self.canvas_bar = FigureCanvasTkAgg(self.fig_bar, master=bar_graph_frame)
        self.canvas_bar_widget = self.canvas_bar.get_tk_widget()
        self.canvas_bar_widget.pack(fill="both", expand=True, padx=5, pady=5)
        self.canvas_bar.draw()  # Render inicial único

        # === GRÁFICO DE LINHA (Histórico Temporal) ===
        line_graph_frame = ctk.CTkFrame(graphs_container)
        line_graph_frame.pack(fill="both", expand=True)

        line_header = ctk.CTkFrame(line_graph_frame)
        line_header.pack(fill="x", padx=5, pady=5)

        line_title = ctk.CTkLabel(line_header, text="Histórico de Tamanho Médio",
                                 font=ctk.CTkFont(size=13, weight="bold"))
        line_title.pack(side="left", padx=5)

        ctk.CTkLabel(line_header, text="Intervalo:", font=ctk.CTkFont(size=10)).pack(side="left", padx=5)

        self.time_selector = ctk.CTkOptionMenu(
            line_header,
            values=["1 hora", "6 horas", "12 horas", "24 horas", "3 dias", "7 dias"],
            command=self.on_time_interval_changed,
            width=100,
            font=ctk.CTkFont(size=10)
        )
        self.time_selector.set("1 hora")
        self.time_selector.pack(side="left", padx=5)

        self.fig_line = Figure(figsize=(5, 3), dpi=80, facecolor='#2b2b2b')
        self.ax_line = self.fig_line.add_subplot(111)

        self.canvas_line = FigureCanvasTkAgg(self.fig_line, master=line_graph_frame)
        self.canvas_line_widget = self.canvas_line.get_tk_widget()
        self.canvas_line_widget.pack(fill="both", expand=True, padx=5, pady=5)

        # Render inicial do gráfico temporal
        self.update_line_graph()

        # Iniciar polling
        self.after(UI_UPDATE_INTERVAL, self.poll_frames)
        self.after(5000, self.update_line_graph_periodic)

        logger.info(f"Visualização da câmera {self.config.name} iniciada")

    # =========================================================================
    #  SETUP DO GRÁFICO DE BARRAS (criação única dos artistas)
    # =========================================================================
    def _setup_bar_chart(self):
        """
        Cria os artistas do gráfico de barras UMA VEZ.

        Em vez de chamar ax.clear() + ax.bar() + tight_layout() + canvas.draw()
        a cada frame (~33ms), pré-criamos as barras e textos aqui.
        Na atualização, só mudamos as alturas com bar.set_height() — ~1000x mais rápido.
        """
        ax = self.ax_bar
        ax.set_facecolor('#2b2b2b')
        ax.tick_params(colors='white', labelsize=7)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Criar barras com valor 0 (serão atualizadas incrementalmente)
        ranges = [RANGE_LABELS[r] for r in RANGE_ORDER]
        self._bars = ax.bar(ranges, [0] * len(ranges),
                            color='#1f77b4', edgecolor='white', linewidth=0.5)

        # Pré-criar textos de valor (inicialmente invisíveis)
        self._bar_texts = []
        for bar in self._bars:
            t = ax.text(bar.get_x() + bar.get_width() / 2., 0, '',
                        ha='center', va='bottom', fontsize=7, color='white')
            t.set_visible(False)
            self._bar_texts.append(t)

        # Configurar eixos (uma vez só)
        ax.set_ylabel('Relação (%)', color='white', fontsize=9)
        ax.set_ylim(0, 100)
        ax.set_xticklabels(ranges, rotation=45, ha='right', fontsize=7)
        ax.grid(axis='y', alpha=0.3, linestyle='--', color='gray')

        # tight_layout() é CARO — chamamos uma vez aqui, nunca mais no update
        self.fig_bar.tight_layout()

    # =========================================================================
    #  POLLING E UPDATES
    # =========================================================================
    def on_time_interval_changed(self, value):
        """Callback quando intervalo de tempo é alterado"""
        self.time_interval = value
        self._csv_last_mtime = 0  # Forçar re-render com novo filtro
        self.update_line_graph()

    def poll_frames(self):
        """Poll frames da câmera com throttle inteligente"""
        if not self.camera_manager.is_running(self.camera_id):
            self.video_label.configure(text="Câmera parada", image=None)
            self.info_label.configure(text="A câmera não está mais ativa")
            return

        data = self.camera_manager.get_frame(self.camera_id)

        if data is not None:
            analysis = data['analysis']
            inference_time = data['inference_time']

            # Atualizar vídeo (apenas quando há frame anotado)
            if data['frame'] is not None:
                self.update_video(data['frame'])

            # Throttle gráfico de barras: max ~10 updates/sec
            # (era ~33/s antes — matplotlib não precisa disso)
            now = time.monotonic()
            if (now - self._last_bar_update) >= 0.1:
                self.update_bar_graph(analysis['range_relations'])
                self._last_bar_update = now

            # Atualizar info (lightweight, sem throttle)
            roi_indicator = " | ROI: ativo" if getattr(self.config, 'roi', None) else ""
            info_text = (f"Pelotas: {analysis['total_pellets']} | "
                        f"Média: {analysis['media']:.1f}mm | "
                        f"Inferência: {inference_time:.1f}ms{roi_indicator}")
            self.info_label.configure(text=info_text)

        # Continuar polling
        self.after(UI_UPDATE_INTERVAL, self.poll_frames)

    def update_video(self, frame):
        """Atualiza frame de vídeo"""
        if frame is None:
            return

        # Converter BGR → RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Resize mantendo aspect ratio (OpenCV é mais rápido que PIL)
        max_height = 600
        max_width = 700
        height, width = frame_rgb.shape[:2]
        scale = min(max_width / width, max_height / height)
        new_width = int(width * scale)
        new_height = int(height * scale)

        frame_resized = cv2.resize(frame_rgb, (new_width, new_height))

        # Converter para PhotoImage
        image = Image.fromarray(frame_resized)
        photo = ImageTk.PhotoImage(image=image)

        self.video_label.configure(image=photo, text="")
        self.video_label.image = photo  # Manter referência (evita GC)

    # =========================================================================
    #  GRÁFICO DE BARRAS — atualização incremental
    # =========================================================================
    def update_bar_graph(self, range_relations):
        """
        Atualiza APENAS as alturas das barras existentes.

        Antes: ax.clear() → bar() → tight_layout() → draw()  (~50-200ms, segura GIL)
        Agora: set_height() → draw_idle()                     (~0.1-1ms, não bloqueia)
        """
        values = [range_relations[r] * 100 for r in RANGE_ORDER]

        for bar, val, text in zip(self._bars, values, self._bar_texts):
            bar.set_height(val)
            if val > 0:
                text.set_text(f'{val:.1f}%')
                text.set_position((bar.get_x() + bar.get_width() / 2., val))
                text.set_visible(True)
            else:
                text.set_visible(False)

        # draw_idle() agenda redraw para o próximo evento idle do Tk
        # (não bloqueia a thread principal como draw())
        self.canvas_bar.draw_idle()

    # =========================================================================
    #  GRÁFICO DE LINHA — com cache de CSV
    # =========================================================================
    def update_line_graph(self):
        """Atualiza gráfico temporal com cache inteligente de CSV"""
        try:
            csv_filename = f"{self.config.name.replace(' ', '_')}.csv"
            csv_path = os.path.join(DATA_DIR, csv_filename)

            if not os.path.exists(csv_path):
                self.show_empty_line_graph("CSV ainda não foi gerado")
                return

            # Cache: só relê CSV se o arquivo foi modificado
            try:
                current_mtime = os.path.getmtime(csv_path)
            except OSError:
                return

            if current_mtime != self._csv_last_mtime:
                try:
                    self._csv_cache = pd.read_csv(csv_path, parse_dates=['Data'])
                    self._csv_last_mtime = current_mtime
                except Exception as e:
                    logger.warning(f"Erro ao ler CSV: {e}")
                    self._csv_cache = None
                    return

            df = self._csv_cache
            if df is None or df.empty:
                self.show_empty_line_graph("Nenhum dado disponível")
                return

            # Calcular limite de tempo
            now = datetime.now()
            intervals = {
                "1 hora": timedelta(hours=1),
                "6 horas": timedelta(hours=6),
                "12 horas": timedelta(hours=12),
                "24 horas": timedelta(hours=24),
                "3 dias": timedelta(days=3),
                "7 dias": timedelta(days=7),
            }
            time_limit = now - intervals.get(self.time_interval, timedelta(hours=1))

            # Filtrar por intervalo
            df_filtered = df[df['Data'] >= time_limit]

            if df_filtered.empty:
                self.show_empty_line_graph(f"Sem dados nos últimos {self.time_interval}")
                return

            df_filtered = df_filtered.sort_values('Data').reset_index(drop=True)
            df_filtered['media_suavizada'] = df_filtered['media'].rolling(window=5, min_periods=1).mean()

            # Redesenhar gráfico (clear é OK aqui — só roda a cada 5s)
            self.ax_line.clear()
            self.ax_line.set_facecolor('#2b2b2b')
            self.ax_line.tick_params(colors='white', labelsize=7)
            self.ax_line.spines['bottom'].set_color('white')
            self.ax_line.spines['left'].set_color('white')
            self.ax_line.spines['top'].set_visible(False)
            self.ax_line.spines['right'].set_visible(False)

            self.ax_line.plot(df_filtered['Data'], df_filtered['media_suavizada'],
                             marker='o', markersize=3, linewidth=1.5,
                             color='#2ca02c', alpha=0.8)

            self.ax_line.set_xlabel('Tempo', color='white', fontsize=9)
            self.ax_line.set_ylabel('Tamanho Médio (mm)', color='white', fontsize=9)
            self.ax_line.set_ylim(0, 25)

            if self.time_interval in ("1 hora", "6 horas", "12 horas", "24 horas"):
                date_format = DateFormatter("%H:%M")
            else:
                date_format = DateFormatter("%d/%m %H:%M")

            self.ax_line.xaxis.set_major_formatter(date_format)
            self.fig_line.autofmt_xdate()

            self.ax_line.grid(True, alpha=0.3, linestyle='--', color='gray')
            self.fig_line.tight_layout()

            # draw_idle() ao invés de draw() — não bloqueia
            self.canvas_line.draw_idle()

        except Exception as e:
            logger.error(f"Erro ao atualizar gráfico temporal: {e}")
            self.show_empty_line_graph(f"Erro: {str(e)}")

    def show_empty_line_graph(self, message):
        """Mostra mensagem quando não há dados no gráfico temporal"""
        self.ax_line.clear()
        self.ax_line.text(0.5, 0.5, message,
                         ha='center', va='center', fontsize=10, color='white',
                         transform=self.ax_line.transAxes)
        self.ax_line.axis('off')
        self.canvas_line.draw_idle()

    def update_line_graph_periodic(self):
        """Atualização periódica do gráfico temporal (a cada 5 segundos)"""
        if self.winfo_exists():
            self.update_line_graph()
            self.after(5000, self.update_line_graph_periodic)
