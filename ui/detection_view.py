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

        # Left: Vídeo (70%)
        video_frame = ctk.CTkFrame(main_container)
        video_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Canvas para vídeo
        self.video_label = ctk.CTkLabel(video_frame, text="Aguardando frames...")
        self.video_label.pack(fill="both", expand=True, padx=10, pady=10)

        # Info abaixo do vídeo
        self.info_label = ctk.CTkLabel(video_frame, text="Inicializando...",
                                      font=ctk.CTkFont(size=12))
        self.info_label.pack(pady=5)

        # Right: Gráfico de barras (30%)
        graph_frame = ctk.CTkFrame(main_container, width=350)
        graph_frame.pack(side="right", fill="both", padx=(10, 0))
        graph_frame.pack_propagate(False)

        graph_title = ctk.CTkLabel(graph_frame, text="Distribuição Granulométrica",
                                  font=ctk.CTkFont(size=14, weight="bold"))
        graph_title.pack(pady=10)

        # Criar gráfico matplotlib
        self.fig = Figure(figsize=(4, 6), dpi=80, facecolor='#2b2b2b')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='white', labelsize=8)
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)

        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True, padx=10, pady=10)

        # Inicializar gráfico vazio
        self.update_graph({range_name: 0.0 for range_name in RANGE_ORDER})

        # Iniciar polling
        self.after(UI_UPDATE_INTERVAL, self.poll_frames)

        logger.info(f"Visualização da câmera {self.config.name} iniciada")

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

            # Atualizar gráfico
            self.update_graph(analysis['range_relations'])

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
        max_width = 800

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

    def update_graph(self, range_relations):
        """
        Atualiza gráfico de barras

        Args:
            range_relations: Dict {range_name: relation}
        """
        # Limpar gráfico
        self.ax.clear()

        # Preparar dados
        ranges = [RANGE_LABELS[r] for r in RANGE_ORDER]
        values = [range_relations[r] * 100 for r in RANGE_ORDER]  # Converter para %

        # Criar gráfico de barras
        bars = self.ax.bar(ranges, values, color='#1f77b4', edgecolor='white', linewidth=0.5)

        # Adicionar valores nas barras
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                self.ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.1f}%',
                           ha='center', va='bottom', fontsize=8, color='white')

        # Configurar eixos
        self.ax.set_ylabel('Relação (%)', color='white', fontsize=10)
        self.ax.set_ylim(0, 100)
        self.ax.set_xticklabels(ranges, rotation=45, ha='right', fontsize=8)
        self.ax.grid(axis='y', alpha=0.3, linestyle='--', color='gray')

        # Ajustar layout
        self.fig.tight_layout()

        # Redesenhar
        self.canvas.draw()
