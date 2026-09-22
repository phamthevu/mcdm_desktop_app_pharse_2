from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLabel, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from typing import List
from core.models import ScaleItem


class MatrixCellWidget(QWidget):
    """Widget ô ma trận gọn gàng: CHỈ HIỂN THỊ CODE."""
    valueChanged = pyqtSignal()

    def __init__(self, is_continuous: bool, use_z: bool, 
                 scales_a: List[ScaleItem] = None, scales_b: List[ScaleItem] = None,
                 c_min: float = 0.0, c_max: float = 10.0, parent=None):
        super().__init__(parent)
        self.is_continuous = is_continuous
        self.use_z = use_z
        self.scales_a = scales_a or []
        self.scales_b = scales_b or []
        self.c_min = c_min
        self.c_max = c_max
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if not self.is_continuous:
            # CATEGORICAL (Dropdown: CHỈ HIỂN THỊ CODE)
            self.cb_eval = QComboBox()
            self.cb_eval.setFixedWidth(65)
            for s in self.scales_a:
                # Tooltip vẫn hiển thị tên đầy đủ để chuyên gia rê chuột xem nếu cần
                self.cb_eval.addItem(s.code, userData=s)
                self.cb_eval.setItemData(self.cb_eval.count() - 1, f"{s.code}: {s.linguistic} ({s.value})", Qt.ItemDataRole.ToolTipRole)
            
            self.cb_eval.currentIndexChanged.connect(self.valueChanged.emit)
            layout.addWidget(self.cb_eval)

            if self.use_z:
                lbl_sep = QLabel("|")
                lbl_sep.setStyleSheet("color: #666; font-weight: bold;")
                layout.addWidget(lbl_sep)

                self.cb_cert = QComboBox()
                self.cb_cert.setFixedWidth(65)
                for s in self.scales_b:
                    self.cb_cert.addItem(s.code, userData=s)
                    self.cb_cert.setItemData(self.cb_cert.count() - 1, f"{s.code}: {s.linguistic} ({s.value})", Qt.ItemDataRole.ToolTipRole)
                
                self.cb_cert.currentIndexChanged.connect(self.valueChanged.emit)
                layout.addWidget(self.cb_cert)

        else:
            # CONTINUOUS
            self.spin_eval = QDoubleSpinBox()
            self.spin_eval.setRange(self.c_min, self.c_max)
            self.spin_eval.setSingleStep(0.5)
            self.spin_eval.setValue(self.c_min)
            self.spin_eval.setFixedWidth(70)
            self.spin_eval.valueChanged.connect(self.valueChanged.emit)
            layout.addWidget(self.spin_eval)

            if self.use_z:
                lbl_sep = QLabel("|")
                lbl_sep.setStyleSheet("color: #666; font-weight: bold;")
                layout.addWidget(lbl_sep)

                self.spin_cert = QDoubleSpinBox()
                self.spin_cert.setRange(0.0, 1.0)
                self.spin_cert.setSingleStep(0.05)
                self.spin_cert.setValue(1.0)
                self.spin_cert.setFixedWidth(60)
                self.spin_cert.valueChanged.connect(self.valueChanged.emit)
                layout.addWidget(self.spin_cert)

    def get_code(self) -> str:
        """Lấy giá trị Code."""
        if not self.is_continuous:
            data_a = self.cb_eval.currentData()
            code_a = data_a.code if data_a else ""
            if not self.use_z:
                return code_a
            data_b = self.cb_cert.currentData()
            code_b = data_b.code if data_b else ""
            return f"({code_a}; {code_b})"
        else:
            val_a = round(self.spin_eval.value(), 2)
            if not self.use_z:
                return str(val_a)
            val_b = round(self.spin_cert.value(), 2)
            return f"({val_a}; {val_b})"

    def get_value(self) -> str:
        """Lấy giá trị số / Fuzzy vector."""
        if not self.is_continuous:
            data_a = self.cb_eval.currentData()
            val_a = str(data_a.value) if data_a else ""
            if not self.use_z:
                return val_a
            data_b = self.cb_cert.currentData()
            val_b = str(data_b.value) if data_b else ""
            return f"({val_a}; {val_b})"
        else:
            val_a = round(self.spin_eval.value(), 2)
            if not self.use_z:
                return str(val_a)
            val_b = round(self.spin_cert.value(), 2)
            return f"({val_a}; {val_b})"

    def set_value_by_code(self, code_str: str):
        """Khôi phục trạng thái ô từ mã code đã lưu."""
        if not code_str:
            return
        if not self.is_continuous:
            if not self.use_z:
                for idx in range(self.cb_eval.count()):
                    if self.cb_eval.itemText(idx) == code_str:
                        self.cb_eval.setCurrentIndex(idx)
                        break
            else:
                # Dạng (VH; VLk)
                clean_str = code_str.strip("() ")
                if ";" in clean_str:
                    parts = clean_str.split(";")
                    code_a, code_b = parts[0].strip(), parts[1].strip()
                    for idx in range(self.cb_eval.count()):
                        if self.cb_eval.itemText(idx) == code_a:
                            self.cb_eval.setCurrentIndex(idx)
                            break
                    for idx in range(self.cb_cert.count()):
                        if self.cb_cert.itemText(idx) == code_b:
                            self.cb_cert.setCurrentIndex(idx)
                            break
        else:
            if not self.use_z:
                try:
                    self.spin_eval.setValue(float(code_str))
                except ValueError:
                    pass
            else:
                clean_str = code_str.strip("() ")
                if ";" in clean_str:
                    parts = clean_str.split(";")
                    try:
                        self.spin_eval.setValue(float(parts[0].strip()))
                        self.spin_cert.setValue(float(parts[1].strip()))
                    except ValueError:
                        pass

    def reset_to_default(self):
        """Khôi phục ô về giá trị mặc định ban đầu."""
        if not self.is_continuous:
            if hasattr(self, 'cb_eval'):
                self.cb_eval.setCurrentIndex(0)
            if hasattr(self, 'cb_cert'):
                self.cb_cert.setCurrentIndex(0)
        else:
            if hasattr(self, 'spin_eval'):
                self.spin_eval.setValue(self.c_min)
            if hasattr(self, 'spin_cert'):
                self.spin_cert.setValue(1.0)