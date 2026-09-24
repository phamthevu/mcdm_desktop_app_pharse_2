from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QLocale
from PyQt6.QtGui import QDoubleValidator
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
            # CONTINUOUS — direct numeric text entry (no spin buttons).
            self.txt_eval = QLineEdit()
            self.txt_eval.setPlaceholderText(f"{self.c_min:g} – {self.c_max:g}")
            validator = QDoubleValidator(self.c_min, self.c_max, 8, self)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            validator.setLocale(QLocale.c())
            self.txt_eval.setValidator(validator)
            self.txt_eval.setFixedWidth(92)
            self.txt_eval.setToolTip(f"Enter a numeric value from {self.c_min:g} to {self.c_max:g}")
            self.txt_eval.textChanged.connect(self.valueChanged.emit)
            layout.addWidget(self.txt_eval)

            if self.use_z:
                lbl_sep = QLabel("|")
                lbl_sep.setStyleSheet("color: #666; font-weight: bold;")
                layout.addWidget(lbl_sep)

                self.txt_cert = QLineEdit()
                self.txt_cert.setPlaceholderText("0 – 1")
                cert_validator = QDoubleValidator(0.0, 1.0, 8, self)
                cert_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
                cert_validator.setLocale(QLocale.c())
                self.txt_cert.setValidator(cert_validator)
                self.txt_cert.setFixedWidth(72)
                self.txt_cert.setToolTip("Enter Z-number reliability from 0 to 1")
                self.txt_cert.textChanged.connect(self.valueChanged.emit)
                layout.addWidget(self.txt_cert)

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
            val_a = self.txt_eval.text().strip()
            if not self.use_z:
                return val_a
            val_b = self.txt_cert.text().strip()
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
            val_a = self.txt_eval.text().strip()
            if not self.use_z:
                return val_a
            val_b = self.txt_cert.text().strip()
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
                    float(code_str)
                    self.txt_eval.setText(str(code_str).strip())
                except ValueError:
                    pass
            else:
                clean_str = code_str.strip("() ")
                if ";" in clean_str:
                    parts = clean_str.split(";")
                    try:
                        float(parts[0].strip()); float(parts[1].strip())
                        self.txt_eval.setText(parts[0].strip())
                        self.txt_cert.setText(parts[1].strip())
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
            if hasattr(self, 'txt_eval'):
                self.txt_eval.clear()
                self.txt_eval.setStyleSheet("")
            if hasattr(self, 'txt_cert'):
                self.txt_cert.clear()
                self.txt_cert.setStyleSheet("")

    def validate_input(self, strictly_positive: bool = False):
        """Return (valid, message). Continuous cells must be explicitly filled."""
        if not self.is_continuous:
            return True, ""
        raw = self.txt_eval.text().strip()
        if not raw:
            self.txt_eval.setStyleSheet("border: 2px solid #dc3545;")
            return False, "A numeric value is required."
        try:
            value = float(raw)
        except ValueError:
            self.txt_eval.setStyleSheet("border: 2px solid #dc3545;")
            return False, "The value must be numeric."
        if value < self.c_min or value > self.c_max:
            self.txt_eval.setStyleSheet("border: 2px solid #dc3545;")
            return False, f"Value must be between {self.c_min:g} and {self.c_max:g}."
        if strictly_positive and value <= 0:
            self.txt_eval.setStyleSheet("border: 2px solid #dc3545;")
            return False, "AHP pairwise values must be greater than 0."
        self.txt_eval.setStyleSheet("")
        if self.use_z:
            raw_z = self.txt_cert.text().strip()
            if not raw_z:
                self.txt_cert.setStyleSheet("border: 2px solid #dc3545;")
                return False, "Z-number reliability is required."
            try:
                z = float(raw_z)
            except ValueError:
                self.txt_cert.setStyleSheet("border: 2px solid #dc3545;")
                return False, "Z-number reliability must be numeric."
            if not 0.0 <= z <= 1.0:
                self.txt_cert.setStyleSheet("border: 2px solid #dc3545;")
                return False, "Z-number reliability must be between 0 and 1."
            self.txt_cert.setStyleSheet("")
        return True, ""

    def numeric_value(self):
        if not self.is_continuous:
            return None
        try:
            return float(self.txt_eval.text().strip())
        except (TypeError, ValueError):
            return None
