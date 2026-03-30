"""
Formulário de cadastro de câmeras
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import logging
from core.camera_manager import CameraConfig
from utils.gpu_utils import get_gpu_options, parse_device_option
from config import MODEL_PATH, DEFAULT_DETECTION_RATE, DEFAULT_SCALE_MM_PIXEL, DEFAULT_CONFIDENCE, DEFAULT_MAX_DET, FRAME_DISPLAY_INTERVAL
from ui.roi_dialog import ROIDialog, grab_sample_frame


logger = logging.getLogger('PelletDetector.camera_form')


class CameraFormFrame(ctk.CTkFrame):
    """Frame de cadastro de câmera"""

    def __init__(self, parent, camera_manager):
        super().__init__(parent)

        self.parent = parent
        self.camera_manager = camera_manager

        # Título
        title = ctk.CTkLabel(self, text="Cadastro de Câmera",
                            font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(pady=20)

        # Form container
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(padx=40, pady=20, fill="both", expand=True)

        # Nome da câmera
        self.create_field(form_frame, "Nome da Câmera:", 0)
        self.name_entry = ctk.CTkEntry(form_frame, width=400, placeholder_text="Ex: Câmera Linha 1")
        self.name_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Caminho da câmera
        self.create_field(form_frame, "Caminho da Câmera:", 1)
        source_frame = ctk.CTkFrame(form_frame)
        source_frame.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.source_entry = ctk.CTkEntry(source_frame, width=300, placeholder_text="Ex: video.mp4, 0, rtsp://...")
        self.source_entry.pack(side="left", padx=(0, 5))

        browse_btn = ctk.CTkButton(source_frame, text="Procurar", width=90, command=self.browse_source)
        browse_btn.pack(side="left")

        # Caminho do modelo
        self.create_field(form_frame, "Caminho do Modelo:", 2)
        model_frame = ctk.CTkFrame(form_frame)
        model_frame.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        self.model_entry = ctk.CTkEntry(model_frame, width=300)
        self.model_entry.insert(0, MODEL_PATH)
        self.model_entry.pack(side="left", padx=(0, 5))

        model_browse_btn = ctk.CTkButton(model_frame, text="Procurar", width=90, command=self.browse_model)
        model_browse_btn.pack(side="left")

        # Inferências por segundo
        self.create_field(form_frame, "Inferências por Segundo:", 3)
        rate_frame = ctk.CTkFrame(form_frame)
        rate_frame.grid(row=3, column=1, padx=10, pady=10, sticky="w")

        self.rate_slider = ctk.CTkSlider(rate_frame, from_=1, to=10, number_of_steps=9, width=250)
        self.rate_slider.set(DEFAULT_DETECTION_RATE)
        self.rate_slider.pack(side="left", padx=(0, 10))

        self.rate_label = ctk.CTkLabel(rate_frame, text=f"{int(self.rate_slider.get())} inf/s")
        self.rate_label.pack(side="left")

        self.rate_slider.configure(command=lambda v: self.rate_label.configure(
            text=f"{int(v)} inf/s"))

        # Escala mm/pixel
        self.create_field(form_frame, "Escala (mm/pixel):", 4)
        self.scale_entry = ctk.CTkEntry(form_frame, width=150)
        self.scale_entry.insert(0, str(DEFAULT_SCALE_MM_PIXEL))
        self.scale_entry.grid(row=4, column=1, padx=10, pady=10, sticky="w")

        # Nível de confiança
        self.create_field(form_frame, "Nível de Confiança (%):", 5)
        conf_frame = ctk.CTkFrame(form_frame)
        conf_frame.grid(row=5, column=1, padx=10, pady=10, sticky="w")

        self.conf_slider = ctk.CTkSlider(conf_frame, from_=0, to=100, number_of_steps=20, width=250)
        self.conf_slider.set(DEFAULT_CONFIDENCE * 100)
        self.conf_slider.pack(side="left", padx=(0, 10))

        self.conf_label = ctk.CTkLabel(conf_frame, text=f"{int(self.conf_slider.get())}%")
        self.conf_label.pack(side="left")

        self.conf_slider.configure(command=lambda v: self.conf_label.configure(text=f"{int(v)}%"))

        # Máximo de detecções por frame
        self.create_field(form_frame, "Máx. Detecções por Frame:", 6)
        self.max_det_entry = ctk.CTkEntry(form_frame, width=150, placeholder_text="Ex: 100")
        self.max_det_entry.insert(0, str(DEFAULT_MAX_DET))
        self.max_det_entry.grid(row=6, column=1, padx=10, pady=10, sticky="w")

        # Intervalo de exibição de frame (segundos)
        self.create_field(form_frame, "Intervalo Exibição (s):", 7)
        display_frame = ctk.CTkFrame(form_frame)
        display_frame.grid(row=7, column=1, padx=10, pady=10, sticky="w")

        self.display_interval_entry = ctk.CTkEntry(display_frame, width=150, placeholder_text="Ex: 0")
        self.display_interval_entry.insert(0, str(FRAME_DISPLAY_INTERVAL))
        self.display_interval_entry.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(display_frame, text="0 = todos os frames",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")

        # Dispositivo (GPU/CPU)
        self.create_field(form_frame, "Dispositivo:", 8)
        self.device_options = get_gpu_options()
        self.device_menu = ctk.CTkOptionMenu(form_frame, values=self.device_options, width=400)
        self.device_menu.set(self.device_options[0])
        self.device_menu.grid(row=8, column=1, padx=10, pady=10, sticky="w")

        # Região de Interesse (ROI)
        self.create_field(form_frame, "Região de Interesse:", 9)
        roi_frame = ctk.CTkFrame(form_frame)
        roi_frame.grid(row=9, column=1, padx=10, pady=10, sticky="w")

        self.roi_status_label = ctk.CTkLabel(roi_frame, text="Não definida (frame inteiro)")
        self.roi_status_label.pack(side="left", padx=(0, 10))

        roi_btn = ctk.CTkButton(roi_frame, text="Definir ROI", width=120,
                                command=self.open_roi_dialog)
        roi_btn.pack(side="left", padx=(0, 5))

        roi_clear_btn = ctk.CTkButton(roi_frame, text="Limpar", width=80,
                                       command=self.clear_roi,
                                       fg_color="gray", hover_color="darkgray")
        roi_clear_btn.pack(side="left")

        self.roi_value = None

        # Botões
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(pady=20)

        add_btn = ctk.CTkButton(button_frame, text="Adicionar Câmera", width=180, height=40,
                               command=self.add_camera, font=ctk.CTkFont(size=14, weight="bold"))
        add_btn.pack(side="left", padx=10)

        cancel_btn = ctk.CTkButton(button_frame, text="Voltar", width=120, height=40,
                                   command=self.parent.show_camera_list,
                                   fg_color="gray", hover_color="darkgray")
        cancel_btn.pack(side="left", padx=10)

    def create_field(self, parent, label_text, row):
        """Cria label do campo"""
        label = ctk.CTkLabel(parent, text=label_text, font=ctk.CTkFont(size=13, weight="bold"))
        label.grid(row=row, column=0, padx=10, pady=10, sticky="e")

    def browse_source(self):
        """Abre diálogo para selecionar arquivo de vídeo"""
        filename = filedialog.askopenfilename(
            title="Selecionar Vídeo",
            filetypes=[("Arquivos de vídeo", "*.mp4 *.avi *.mov *.mkv"), ("Todos", "*.*")]
        )
        if filename:
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, filename)

    def open_roi_dialog(self):
        """Abre diálogo para definir ROI"""
        source = self.source_entry.get().strip()
        if not source:
            messagebox.showwarning("Aviso", "Informe o caminho da câmera antes de definir o ROI.")
            return

        frame = grab_sample_frame(source)
        if frame is None:
            messagebox.showerror("Erro", f"Não foi possível capturar frame da fonte:\n{source}")
            return

        ROIDialog(self, frame, current_roi=self.roi_value, on_apply=self._on_roi_applied)

    def _on_roi_applied(self, roi):
        """Callback quando ROI é definida ou limpa"""
        self.roi_value = roi
        if roi is not None:
            x, y, w, h = roi
            self.roi_status_label.configure(text=f"ROI: ({x}, {y}) {w}x{h}")
        else:
            self.roi_status_label.configure(text="Não definida (frame inteiro)")

    def clear_roi(self):
        """Limpa a ROI"""
        self.roi_value = None
        self.roi_status_label.configure(text="Não definida (frame inteiro)")

    def browse_model(self):
        """Abre diálogo para selecionar modelo"""
        filename = filedialog.askopenfilename(
            title="Selecionar Modelo",
            filetypes=[
                ("Todos os Modelos", "*.pt *.onnx *.engine"),
                ("Modelo PyTorch", "*.pt"),
                ("Modelo ONNX", "*.onnx"),
                ("Modelo TensorRT", "*.engine"),
                ("Todos", "*.*")
            ]
        )
        if filename:
            self.model_entry.delete(0, tk.END)
            self.model_entry.insert(0, filename)

    def validate_inputs(self):
        """Valida entradas do formulário"""
        errors = []

        # Nome
        name = self.name_entry.get().strip()
        if not name:
            errors.append("Nome da câmera é obrigatório")

        # Source
        source = self.source_entry.get().strip()
        if not source:
            errors.append("Caminho da câmera é obrigatório")
        else:
            # Verificar se é arquivo e se existe
            try:
                int(source)  # É índice de webcam
            except ValueError:
                # É arquivo ou URL
                if not source.startswith(('rtsp://', 'http://', 'https://')) and not os.path.exists(source):
                    errors.append(f"Arquivo não encontrado: {source}")

        # Modelo
        model_path = self.model_entry.get().strip()
        if not model_path:
            errors.append("Caminho do modelo é obrigatório")
        elif not os.path.exists(model_path):
            errors.append(f"Modelo não encontrado: {model_path}")
        else:
            # Validar compatibilidade modelo/dispositivo
            device_str = self.device_menu.get()
            model_ext = os.path.splitext(model_path)[1].lower()

            if model_ext == '.engine' and device_str == "CPU":
                errors.append("Modelos TensorRT (.engine) não podem rodar na CPU.\nUse um modelo .onnx ou .pt para CPU, ou selecione uma GPU.")

            if model_ext == '.pt':
                # Avisar que .pt será convertido automaticamente pelo YOLO
                logger.info(f"Modelo PyTorch detectado: {model_path}")

        # Escala
        try:
            scale = float(self.scale_entry.get())
            if scale <= 0:
                errors.append("Escala deve ser maior que zero")
        except ValueError:
            errors.append("Escala inválida (use número decimal)")

        # Max det
        try:
            max_det = int(self.max_det_entry.get())
            if max_det <= 0:
                errors.append("Máx. detecções deve ser maior que zero")
        except ValueError:
            errors.append("Máx. detecções inválido (use número inteiro)")

        # Intervalo de exibição
        try:
            display_interval = float(self.display_interval_entry.get())
            if display_interval < 0:
                errors.append("Intervalo de exibição deve ser >= 0")
        except ValueError:
            errors.append("Intervalo de exibição inválido (use número)")

        return errors

    def add_camera(self):
        """Adiciona câmera ao sistema"""
        # Validar
        errors = self.validate_inputs()

        if errors:
            messagebox.showerror("Erro de Validação", "\n".join(errors))
            return

        try:
            # Coletar dados
            name = self.name_entry.get().strip()
            source = self.source_entry.get().strip()
            model_path = self.model_entry.get().strip()
            detection_rate = int(self.rate_slider.get())
            scale_mm_pixel = float(self.scale_entry.get())
            confidence = self.conf_slider.get() / 100.0
            max_det = int(self.max_det_entry.get())
            frame_display_interval = float(self.display_interval_entry.get())
            device_str = self.device_menu.get()
            device = parse_device_option(device_str)

            # Criar config
            config = CameraConfig(
                name=name,
                source=source,
                model_path=model_path,
                detection_rate=detection_rate,
                scale_mm_pixel=scale_mm_pixel,
                confidence=confidence,
                device=device,
                max_det=max_det,
                roi=self.roi_value,
                frame_display_interval=frame_display_interval
            )

            # Adicionar ao manager
            camera_id = self.camera_manager.add_camera(config)

            logger.info(f"Câmera adicionada: {name} (ID: {camera_id})")

            # Mensagem de sucesso
            messagebox.showinfo("Sucesso", f"Câmera '{name}' adicionada com sucesso!")

            # Voltar para lista
            self.parent.show_camera_list()

        except Exception as e:
            logger.error(f"Erro ao adicionar câmera: {e}")
            messagebox.showerror("Erro", f"Erro ao adicionar câmera:\n{str(e)}")
