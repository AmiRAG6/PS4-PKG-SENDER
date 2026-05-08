#!/bin/env python3
import sys
import os
import ftplib
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QGridLayout,
                             QLineEdit, QPushButton, QLabel, QProgressBar, QFileDialog, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont

class FTPWorker(QThread):
    progress_updated = pyqtSignal(int)
    finished_upload = pyqtSignal(bool, str)

    def __init__(self, host, port, user, passwd, file_path, remote_dir):
        super().__init__()
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.file_path = file_path
        self.remote_dir = remote_dir

    def run(self):
        try:
            # اتصال اولیه
            ftp = ftplib.FTP()
            ftp.connect(host=self.host, port=self.port, timeout=10)
            ftp.login(user=self.user, passwd=self.passwd)

            # 🔧 جلوگیری از تایم‌اوت کانال کنترل هنگام انتقال فایل‌های بزرگ
            ftp.sock.settimeout(300)  # 5 دقیقه انتظار

            # ورود به مسیر data/pkg (ساخت خودکار)
            folders = self.remote_dir.strip("/").split("/")
            for folder in folders:
                try:
                    ftp.cwd(folder)
                except ftplib.error_perm:
                    ftp.mkd(folder)
                    ftp.cwd(folder)

            filename = os.path.basename(self.file_path)
            total = os.path.getsize(self.file_path)
            sent = 0

            def callback(data):
                nonlocal sent
                sent += len(data)
                percent = int(sent / total * 100)
                self.progress_updated.emit(percent)

            with open(self.file_path, "rb") as f:
                ftp.storbinary(f"STOR {filename}", f, blocksize=8192, callback=callback)

            ftp.quit()
            self.finished_upload.emit(True, "آپلود با موفقیت انجام شد")

        except Exception as e:
            self.finished_upload.emit(False, str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FTP PKG Uploader | Final")
        self.setFixedSize(550, 450)

        # ---- تم دارک سبز ----
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QLabel { color: #e0e0e0; font-size: 12px; }
            QLineEdit {
                background-color: #2d2d2d; color: #ffffff;
                border: 1px solid #555; border-radius: 5px; padding: 5px;
            }
            QPushButton {
                background-color: #27ae60; color: white; border: none;
                padding: 8px 15px; border-radius: 5px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:pressed { background-color: #1e8449; }
            QPushButton:disabled { background-color: #555; color: #aaa; }
            QProgressBar {
                border: 1px solid #555; border-radius: 5px;
                text-align: center; background-color: #2d2d2d;
            }
            QProgressBar::chunk {
                background-color: #27ae60; border-radius: 5px;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        # هدر
        header = QLabel("FTP PKG Uploader")
        header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #27ae60;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)

        # گرید تنظیمات
        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Host:"), 0, 0)
        self.host_edit = QLineEdit("192.168.2.2")
        grid.addWidget(self.host_edit, 0, 1, 1, 2)

        grid.addWidget(QLabel("Port:"), 1, 0)
        self.port_edit = QLineEdit("2121")
        self.port_edit.setMaximumWidth(80)
        grid.addWidget(self.port_edit, 1, 1)

        grid.addWidget(QLabel("Username:"), 2, 0)
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("anonymous")
        grid.addWidget(self.user_edit, 2, 1, 1, 2)

        grid.addWidget(QLabel("Password:"), 3, 0)
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.pass_edit, 3, 1, 1, 2)

        main_layout.addLayout(grid)

        # تست اتصال
        self.test_btn = QPushButton("⚡ تست اتصال")
        self.test_btn.clicked.connect(self.test_connection)
        self.test_status = QLabel("")
        self.test_status.setStyleSheet("color: gray;")
        main_layout.addWidget(self.test_btn)
        main_layout.addWidget(self.test_status)

        # انتخاب فایل
        file_layout = QGridLayout()
        file_layout.addWidget(QLabel("فایل PKG:"), 0, 0)
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        file_layout.addWidget(self.file_edit, 0, 1)
        self.browse_btn = QPushButton("انتخاب فایل")
        self.browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.browse_btn, 0, 2)
        main_layout.addLayout(file_layout)

        self.dest_label = QLabel("مسیر مقصد: /data/pkg")
        self.dest_label.setStyleSheet("color: #aaa;")
        main_layout.addWidget(self.dest_label)

        # آپلود و پیشرفت
        self.upload_btn = QPushButton("🚀 آپلود به FTP")
        self.upload_btn.clicked.connect(self.start_upload)
        main_layout.addWidget(self.upload_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888;")
        main_layout.addWidget(self.status_label)

        self.worker = None

    def browse_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "انتخاب فایل PKG", "",
                                                  "PKG files (*.pkg);;All files (*.*)")
        if filename:
            self.file_edit.setText(filename)

    def test_connection(self):
        self.test_btn.setEnabled(False)
        self.test_status.setText("در حال بررسی...")
        self.test_status.setStyleSheet("color: orange;")

        class TestThread(QThread):
            result = pyqtSignal(bool, str)
            def __init__(self, host, port, user, passwd):
                super().__init__()
                self.host = host
                self.port = port
                self.user = user
                self.passwd = passwd
            def run(self):
                try:
                    host = self.host.strip()
                    port = int(self.port.strip() or 2121)
                    if not host:
                        raise ValueError("Host نمیتواند خالی باشد")
                    user = self.user.strip() or "anonymous"
                    passwd = self.passwd.strip()
                    ftp = ftplib.FTP()
                    ftp.connect(host=host, port=port, timeout=5)
                    ftp.login(user=user, passwd=passwd)
                    ftp.quit()
                    self.result.emit(True, "✓ متصل شد")
                except Exception as e:
                    self.result.emit(False, f"✗ {e}")

        self.test_thread = TestThread(self.host_edit.text(), self.port_edit.text(),
                                      self.user_edit.text(), self.pass_edit.text())
        self.test_thread.result.connect(self.on_test_result)
        self.test_thread.start()

    def on_test_result(self, success, msg):
        self.test_btn.setEnabled(True)
        if success:
            self.test_status.setText(msg)
            self.test_status.setStyleSheet("color: green;")
        else:
            self.test_status.setText(msg)
            self.test_status.setStyleSheet("color: red;")

    def start_upload(self):
        file_path = self.file_edit.text()
        if not file_path:
            QMessageBox.warning(self, "خطا", "لطفاً فایل PKG را انتخاب کنید.")
            return

        self.upload_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("در حال آپلود...")
        self.status_label.setStyleSheet("color: blue;")

        host = self.host_edit.text().strip()
        port = int(self.port_edit.text().strip() or 2121)
        user = self.user_edit.text().strip() or "anonymous"
        passwd = self.pass_edit.text().strip()

        self.worker = FTPWorker(host, port, user, passwd, file_path, "data/pkg")
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished_upload.connect(self.upload_finished)
        self.worker.start()

    def update_progress(self, percent):
        self.progress_bar.setValue(percent)
        self.status_label.setText(f"آپلود: {percent}%")

    def upload_finished(self, success, msg):
        self.upload_btn.setEnabled(True)
        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("✅ آپلود موفق")
            self.status_label.setStyleSheet("color: green;")
            QMessageBox.information(self, "موفقیت", msg)
        else:
            self.status_label.setText(f"❌ خطا: {msg}")
            self.status_label.setStyleSheet("color: red;")
            QMessageBox.critical(self, "شکست", msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
