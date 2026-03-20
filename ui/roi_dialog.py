"""
Diálogo interativo para seleção de ROI (Região de Interesse)
O usuário arrasta um retângulo sobre um frame de amostra da câmera.
"""
import customtkinter as ctk
import tkinter as tk
import cv2
import numpy as np
from PIL import Image, ImageTk
import logging

logger = logging.getLogger('PelletDetector.roi_dialog')

# Tamanho máximo do canvas de exibição
DISPLAY_MAX_W = 800
DISPLAY_MAX_H = 480


class ROIDialog(ctk.CTkToplevel):
    """Diálogo para definir ROI arrastando um retângulo sobre a imagem"""

    def __init__(self, parent, sample_frame, current_roi=None, on_apply=None):
        """
        Args:
            parent: Janela pai
            sample_frame: Frame OpenCV (BGR) para exibição
            current_roi: ROI atual (x, y, w, h) ou None
            on_apply: Callback chamado com (x, y, w, h) ou None ao aplicar
        """
        super().__init__(parent)
        self.title("Definir Região de Interesse (ROI)")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_apply = on_apply
        self.roi_result = current_roi

        # Frame original e dimensões
        self.original_frame = sample_frame
        self.frame_h, self.frame_w = sample_frame.shape[:2]

        # Escala para caber no canvas
        self.scale = min(DISPLAY_MAX_W / self.frame_w, DISPLAY_MAX_H / self.frame_h)
        self.display_w = int(self.frame_w * self.scale)
        self.display_h = int(self.frame_h * self.scale)

        # Estado do arrasto
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.rect_id = None

        # --- Layout ---
        instruction = ctk.CTkLabel(
            self,
            text="Arraste um retângulo sobre a imagem para definir a região de interesse.",
            font=ctk.CTkFont(size=12)
        )
        instruction.pack(padx=10, pady=(10, 5))

        # Canvas com a imagem
        self.canvas = tk.Canvas(
            self,
            width=self.display_w,
            height=self.display_h,
            bg='black',
            highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=5)

        # Preparar imagem de fundo
        frame_rgb = cv2.cvtColor(sample_frame, cv2.COLOR_BGR2RGB)
        frame_resized = cv2.resize(frame_rgb, (self.display_w, self.display_h))
        self.bg_image = ImageTk.PhotoImage(Image.fromarray(frame_resized))
        self.canvas.create_image(0, 0, anchor='nw', image=self.bg_image)

        # Bindings do mouse
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)

        # Campos numéricos
        fields_frame = ctk.CTkFrame(self)
        fields_frame.pack(padx=10, pady=5, fill='x')

        ctk.CTkLabel(fields_frame, text="X:").grid(row=0, column=0, padx=5, pady=5)
        self.entry_x = ctk.CTkEntry(fields_frame, width=70)
        self.entry_x.grid(row=0, column=1, padx=2, pady=5)

        ctk.CTkLabel(fields_frame, text="Y:").grid(row=0, column=2, padx=5, pady=5)
        self.entry_y = ctk.CTkEntry(fields_frame, width=70)
        self.entry_y.grid(row=0, column=3, padx=2, pady=5)

        ctk.CTkLabel(fields_frame, text="Largura:").grid(row=0, column=4, padx=5, pady=5)
        self.entry_w = ctk.CTkEntry(fields_frame, width=70)
        self.entry_w.grid(row=0, column=5, padx=2, pady=5)

        ctk.CTkLabel(fields_frame, text="Altura:").grid(row=0, column=6, padx=5, pady=5)
        self.entry_h = ctk.CTkEntry(fields_frame, width=70)
        self.entry_h.grid(row=0, column=7, padx=2, pady=5)

        apply_fields_btn = ctk.CTkButton(fields_frame, text="Aplicar Valores", width=110,
                                          command=self._apply_fields)
        apply_fields_btn.grid(row=0, column=8, padx=10, pady=5)

        # Botões de ação
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(padx=10, pady=10)

        apply_btn = ctk.CTkButton(btn_frame, text="Aplicar ROI", width=140,
                                   command=self._apply, font=ctk.CTkFont(weight="bold"))
        apply_btn.pack(side='left', padx=5)

        clear_btn = ctk.CTkButton(btn_frame, text="Limpar ROI", width=120,
                                   command=self._clear, fg_color='gray', hover_color='darkgray')
        clear_btn.pack(side='left', padx=5)

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancelar", width=100,
                                    command=self._cancel, fg_color='gray', hover_color='darkgray')
        cancel_btn.pack(side='left', padx=5)

        # Desenhar ROI existente se houver
        if current_roi is not None:
            self._set_roi_from_frame_coords(*current_roi)

        # Centralizar janela
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{x}+{y}")

    # --- Conversão de coordenadas ---

    def _canvas_to_frame(self, cx, cy):
        """Converte coordenadas do canvas para coordenadas do frame original"""
        return int(cx / self.scale), int(cy / self.scale)

    def _frame_to_canvas(self, fx, fy):
        """Converte coordenadas do frame original para coordenadas do canvas"""
        return fx * self.scale, fy * self.scale

    # --- Interação com mouse ---

    def _on_press(self, event):
        self.dragging = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

    def _on_drag(self, event):
        if not self.dragging:
            return

        # Clamp ao canvas
        ex = max(0, min(event.x, self.display_w))
        ey = max(0, min(event.y, self.display_h))

        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)

        self.rect_id = self.canvas.create_rectangle(
            self.drag_start_x, self.drag_start_y, ex, ey,
            outline='cyan', width=2, dash=(4, 4)
        )

    def _on_release(self, event):
        if not self.dragging:
            return
        self.dragging = False

        ex = max(0, min(event.x, self.display_w))
        ey = max(0, min(event.y, self.display_h))

        # Normalizar para top-left
        x1 = min(self.drag_start_x, ex)
        y1 = min(self.drag_start_y, ey)
        x2 = max(self.drag_start_x, ex)
        y2 = max(self.drag_start_y, ey)

        # Converter para coordenadas do frame
        fx1, fy1 = self._canvas_to_frame(x1, y1)
        fx2, fy2 = self._canvas_to_frame(x2, y2)

        fw = fx2 - fx1
        fh = fy2 - fy1

        if fw < 10 or fh < 10:
            # Retângulo muito pequeno, ignorar
            if self.rect_id is not None:
                self.canvas.delete(self.rect_id)
                self.rect_id = None
            return

        self.roi_result = (fx1, fy1, fw, fh)
        self._update_fields(fx1, fy1, fw, fh)
        self._draw_roi_rect(x1, y1, x2, y2)

    def _draw_roi_rect(self, x1, y1, x2, y2):
        """Redesenha o retângulo do ROI no canvas"""
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline='cyan', width=2
        )

    def _set_roi_from_frame_coords(self, fx, fy, fw, fh):
        """Define o ROI a partir de coordenadas do frame original"""
        self.roi_result = (fx, fy, fw, fh)
        self._update_fields(fx, fy, fw, fh)

        cx1, cy1 = self._frame_to_canvas(fx, fy)
        cx2, cy2 = self._frame_to_canvas(fx + fw, fy + fh)
        self._draw_roi_rect(cx1, cy1, cx2, cy2)

    def _update_fields(self, x, y, w, h):
        """Atualiza os campos numéricos"""
        for entry, val in [(self.entry_x, x), (self.entry_y, y),
                           (self.entry_w, w), (self.entry_h, h)]:
            entry.delete(0, tk.END)
            entry.insert(0, str(val))

    def _apply_fields(self):
        """Aplica valores dos campos numéricos como ROI"""
        try:
            x = int(self.entry_x.get())
            y = int(self.entry_y.get())
            w = int(self.entry_w.get())
            h = int(self.entry_h.get())
        except ValueError:
            return

        # Clamp aos limites do frame
        x = max(0, min(x, self.frame_w - 10))
        y = max(0, min(y, self.frame_h - 10))
        w = max(10, min(w, self.frame_w - x))
        h = max(10, min(h, self.frame_h - y))

        self._set_roi_from_frame_coords(x, y, w, h)

    # --- Botões ---

    def _apply(self):
        if self.roi_result is not None and self.on_apply:
            self.on_apply(self.roi_result)
        self.grab_release()
        self.destroy()

    def _clear(self):
        self.roi_result = None
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        for entry in [self.entry_x, self.entry_y, self.entry_w, self.entry_h]:
            entry.delete(0, tk.END)
        if self.on_apply:
            self.on_apply(None)
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.grab_release()
        self.destroy()


def grab_sample_frame(source):
    """
    Captura um frame de amostra de uma fonte de vídeo.

    Args:
        source: Caminho do vídeo, URL RTSP, ou índice de webcam (str ou int)

    Returns:
        Frame OpenCV (BGR) ou None se falhar
    """
    try:
        src = int(source)
    except (ValueError, TypeError):
        src = source

    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        logger.warning(f"Não foi possível abrir source para captura de ROI: {source}")
        return None

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        logger.warning(f"Não foi possível ler frame para captura de ROI: {source}")
        return None

    return frame
