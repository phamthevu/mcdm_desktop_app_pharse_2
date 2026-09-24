from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFrame

class TabWelcome(QWidget):
    new_requested=pyqtSignal(); open_requested=pyqtSignal()
    def __init__(self):
        super().__init__(); root=QVBoxLayout(self); root.setContentsMargins(90,70,90,70); root.addStretch()
        title=QLabel('Research Studio'); title.setAlignment(Qt.AlignmentFlag.AlignCenter); title.setStyleSheet('font-size:28px;font-weight:700;')
        sub=QLabel('No project is open. Start by creating a project type or opening an existing .mcdm project.'); sub.setWordWrap(True); sub.setAlignment(Qt.AlignmentFlag.AlignCenter); sub.setStyleSheet('font-size:14px;color:#666;margin:12px;')
        root.addWidget(title); root.addWidget(sub)
        row=QHBoxLayout(); row.addStretch()
        new=QPushButton('＋  Create New Project'); new.setProperty('primary',True); new.setMinimumSize(220,58); new.clicked.connect(self.new_requested.emit)
        op=QPushButton('Open Existing Project'); op.setProperty('accent',True); op.setMinimumSize(220,58); op.clicked.connect(self.open_requested.emit)
        row.addWidget(new); row.addSpacing(18); row.addWidget(op); row.addStretch(); root.addLayout(row)
        hint=QLabel('New Project lets you choose MCDM, Quantitative Survey, or Qualitative In-depth Interview. Nothing is pre-selected.'); hint.setAlignment(Qt.AlignmentFlag.AlignCenter); hint.setStyleSheet('color:#777;margin-top:20px;'); root.addWidget(hint); root.addStretch()
