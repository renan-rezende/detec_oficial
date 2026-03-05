"""
Visualização de detecções em tempo real
"""
import customtkinter as ctk
import cv2
import numpy as np
from PIL import Image, ImageTk
import logging
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
import pandas as pd
import os
from datetime import datetime, timedelta
from config import UI_UPDATE_INTERVAL, RANGE_ORDER, RANGE_LABELS


logger = logging.getLogger('PelletDetector.detection_view')


class DetectionViewFrame(ctk.CTkFrame):
    """Frame de visualização de detecções"""

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

        # Intervalo de tempo selecionado (padrão: 1 hora)
        self.time_interval = "1 hora"

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

        # Canvas para vídeo
        self.video_label = ctk.CTkLabel(video_frame, text="Aguardando frames...")
        self.video_label.pack(fill="both", expand=True, padx=10, pady=10)

        # Info abaixo do vídeo
        self.info_label = ctk.CTkLabel(video_frame, text="Inicializando...",
                                      font=ctk.CTkFont(size=12))
        self.info_label.pack(pady=5)

        # Right: Gráficos (40%)
        graphs_container = ctk.CTkFrame(main_container, width=450)
        graphs_container.pack(side="right", fill="both", padx=(10, 0))
        graphs_container.pack_propagate(False)

        # === GRÁFICO DE BARRAS (Distribuição) - TOP ===
        bar_graph_frame = ctk.CTkFrame(graphs_container)
        bar_graph_frame.pack(fill="both", expand=True, pady=(0, 10))

        bar_title = ctk.CTkLabel(bar_graph_frame, text="Distribuição Granulométrica",
                                 font=ctk.CTkFont(size=13, weight="bold"))
        bar_title.pack(pady=5)

        # Criar gráfico de barras matplotlib
        self.fig_bar = Figure(figsize=(5, 3), dpi=80, facecolor='#2b2b2b')
        self.ax_bar = self.fig_bar.add_subplot(111)
        self.ax_bar.set_facecolor('#2b2b2b')
        self.ax_bar.tick_params(colors='white', labelsize=7)
        self.ax_bar.spines['bottom'].set_color('white')
        self.ax_bar.spines['left'].set_color('white')
        self.ax_bar.spines['top'].set_visible(False)
        self.ax_bar.spines['right'].set_visible(False)

        self.canvas_bar = FigureCanvasTkAgg(self.fig_bar, master=bar_graph_frame)
        self.canvas_bar_widget = self.canvas_bar.get_tk_widget()
        self.canvas_bar_widget.pack(fill="both", expand=True, padx=5, pady=5)

        # Inicializar gráfico vazio
        self.update_bar_graph({range_name: 0.0 for range_name in RANGE_ORDER})

        # === GRÁFICO DE LINHA (Histórico Temporal) - BOTTOM ===
        line_graph_frame = ctk.CTkFrame(graphs_container)
        line_graph_frame.pack(fill="both", expand=True)

        # Header do gráfico temporal com controles
        line_header = ctk.CTkFrame(line_graph_frame)
        line_header.pack(fill="x", padx=5, pady=5)

        line_title = ctk.CTkLabel(line_header, text="Histórico de Tamanho Médio",
                                 font=ctk.CTkFont(size=13, weight="bold"))
        line_title.pack(side="left", padx=5)

        # Controle de intervalo de tempo
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

        # Criar gráfico de linha matplotlib
        self.fig_line = Figure(figsize=(5, 3), dpi=80, facecolor='#2b2b2b')
        self.ax_line = self.fig_line.add_subplot(111)
        self.ax_line.set_facecolor('#2b2b2b')
        self.ax_line.tick_params(colors='white', labelsize=7)
        self.ax_line.spines['bottom'].set_color('white')
        self.ax_line.spines['left'].set_color('white')
        self.ax_line.spines['top'].set_visible(False)
        self.ax_line.spines['right'].set_visible(False)

        self.canvas_line = FigureCanvasTkAgg(self.fig_line, master=line_graph_frame)
        self.canvas_line_widget = self.canvas_line.get_tk_widget()
        self.canvas_line_widget.pack(fill="both", expand=True, padx=5, pady=5)

        # Inicializar gráfico temporal vazio
        self.update_line_graph()

        # Iniciar polling
        self.after(UI_UPDATE_INTERVAL, self.poll_frames)

        # Atualizar gráfico temporal periodicamente (a cada 5 segundos)
        self.after(5000, self.update_line_graph_periodic)

        logger.info(f"Visualização da câmera {self.config.name} iniciada")

    def on_time_interval_changed(self, value):
        """Callback quando intervalo de tempo é alterado"""
        self.time_interval = value
        self.update_line_graph()

    def poll_frames(self):
        """Poll frames da câmera"""
        if not self.camera_manager.is_running(self.camera_id):
            # Câmera parou
            self.video_label.configure(text="Câmera parada", image=None)
            self.info_label.configure(text="A câmera não está mais ativa")
            return

        # Esvaziar queue e pegar APENAS o frame mais recente
        # Isso evita mostrar frames acumulados rapidamente
        data = None
        while True:
            new_data = self.camera_manager.get_frame(self.camera_id, timeout=0.01)
            if new_data is None:
                break  # Queue vazia
            data = new_data  # Guardar o último

        if data is not None:
            frame = data['frame']
            analysis = data['analysis']
            inference_time = data['inference_time']

            # Atualizar vídeo
            self.update_video(frame)

            # Atualizar gráfico de barras
            self.update_bar_graph(analysis['range_relations'])

            # Atualizar info
            info_text = (f"Pelotas: {analysis['total_pellets']} | "
                        f"Média: {analysis['media']:.1f}mm | "
                        f"Inferência: {inference_time:.1f}ms")
            self.info_label.configure(text=info_text)

        # Continuar polling
        self.after(UI_UPDATE_INTERVAL, self.poll_frames)

    def update_video(self, frame):
        """
        Atualiza frame de vídeo

        Args:
            frame: Frame OpenCV (BGR)
        """
        if frame is None:
            return

        # Converter BGR para RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Resize para caber na tela (mantendo aspect ratio)
        max_height = 600
        max_width = 700

        height, width = frame_rgb.shape[:2]
        scale = min(max_width / width, max_height / height)

        new_width = int(width * scale)
        new_height = int(height * scale)

        frame_resized = cv2.resize(frame_rgb, (new_width, new_height))

        # Converter para PIL Image
        image = Image.fromarray(frame_resized)

        # Converter para PhotoImage
        photo = ImageTk.PhotoImage(image=image)

        # Atualizar label
        self.video_label.configure(image=photo, text="")
        self.video_label.image = photo  # Manter referência

    def update_bar_graph(self, range_relations):
        """
        Atualiza gráfico de barras (distribuição granulométrica)

        Args:
            range_relations: Dict {range_name: relation}
        """
        # Limpar gráfico
        self.ax_bar.clear()

        # Preparar dados
        ranges = [RANGE_LABELS[r] for r in RANGE_ORDER]
        values = [range_relations[r] * 100 for r in RANGE_ORDER]  # Converter para %

        # Criar gráfico de barras
        bars = self.ax_bar.bar(ranges, values, color='#1f77b4', edgecolor='white', linewidth=0.5)

        # Adicionar valores nas barras
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                self.ax_bar.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.1f}%',
                           ha='center', va='bottom', fontsize=7, color='white')

        # Configurar eixos
        self.ax_bar.set_ylabel('Relação (%)', color='white', fontsize=9)
        self.ax_bar.set_ylim(0, 100)
        self.ax_bar.set_xticklabels(ranges, rotation=45, ha='right', fontsize=7)
        self.ax_bar.grid(axis='y', alpha=0.3, linestyle='--', color='gray')

        # Ajustar layout
        self.fig_bar.tight_layout()

        # Redesenhar
        self.canvas_bar.draw()

    def update_line_graph(self):
        """Atualiza gráfico de linha (histórico temporal)"""
        try:
            # Limpar gráfico
            self.ax_line.clear()

            # Obter caminho do CSV da câmera
            csv_filename = f"{self.config.name.replace(' ', '_')}.csv"
            csv_path = os.path.join('data', csv_filename)

            # Verificar se CSV existe
            if not os.path.exists(csv_path):
                self.show_empty_line_graph("CSV ainda não foi gerado")
                return

            # Ler CSV
            df = pd.read_csv(csv_path)

            if df.empty:
                self.show_empty_line_graph("Nenhum dado disponível")
                return

            # Converter coluna Data para datetime
            df['Data'] = pd.to_datetime(df['Data'])

            # Calcular limite de tempo baseado no intervalo selecionado
            now = datetime.now()

            if self.time_interval == "1 hora":
                time_limit = now - timedelta(hours=1)
            elif self.time_interval == "6 horas":
                time_limit = now - timedelta(hours=6)
            elif self.time_interval == "12 horas":
                time_limit = now - timedelta(hours=12)
            elif self.time_interval == "24 horas":
                time_limit = now - timedelta(hours=24)
            elif self.time_interval == "3 dias":
                time_limit = now - timedelta(days=3)
            elif self.time_interval == "7 dias":
                time_limit = now - timedelta(days=7)
            else:
                time_limit = now - timedelta(hours=1)  # Default

            # Filtrar dados pelo intervalo de tempo
            df_filtered = df[df['Data'] >= time_limit]

            if df_filtered.empty:
                self.show_empty_line_graph(f"Sem dados nos últimos {self.time_interval}")
                return

            # Ordenar por data
            df_filtered = df_filtered.sort_values('Data').reset_index(drop=True)

            # Aplicar média móvel (rolling average) das últimas 5 detecções para suavizar
            df_filtered['media_suavizada'] = df_filtered['media'].rolling(window=5, min_periods=1).mean()

            # Plotar linha suavizada
            self.ax_line.plot(df_filtered['Data'], df_filtered['media_suavizada'],
                             marker='o', markersize=3, linewidth=1.5,
                             color='#2ca02c', alpha=0.8)

            # Configurar eixos
            self.ax_line.set_xlabel('Tempo', color='white', fontsize=9)
            self.ax_line.set_ylabel('Tamanho Médio (mm)', color='white', fontsize=9)
            self.ax_line.set_ylim(0, 25)  # Escala fixa de 0 a 25mm

            # Formatar datas no eixo X
            if self.time_interval in ["1 hora", "6 horas", "12 horas"]:
                date_format = DateFormatter("%H:%M")
            elif self.time_interval == "24 horas":
                date_format = DateFormatter("%H:%M")
            else:  # 3 dias ou 7 dias
                date_format = DateFormatter("%d/%m %H:%M")

            self.ax_line.xaxis.set_major_formatter(date_format)
            self.fig_line.autofmt_xdate()

            # Grid
            self.ax_line.grid(True, alpha=0.3, linestyle='--', color='gray')

            # Ajustar layout
            self.fig_line.tight_layout()

            # Redesenhar
            self.canvas_line.draw()

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
        self.canvas_line.draw()

    def update_line_graph_periodic(self):
        """Atualização periódica do gráfico temporal (a cada 5 segundos)"""
        if self.winfo_exists():
            self.update_line_graph()
            self.after(5000, self.update_line_graph_periodic)
