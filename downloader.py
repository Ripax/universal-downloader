import sys
import os
import re
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QFrame, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QHBoxLayout,
    QMessageBox, QProgressBar, QComboBox
)
from PyQt5.QtGui import QIcon
from yt_dlp import YoutubeDL

title_message = "Please enter the link to the video you want to download in the field below."
VERSION = "1.0.1"

class FetchVideoInfoThread(QThread):
    infoFetched = pyqtSignal(dict)
    fetchFailed = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            ydl_opts = {'quiet': True, 'skip_download': True}
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.infoFetched.emit(info)
        except Exception as e:
            self.fetchFailed.emit(str(e))


class DownloadThread(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, url, download_path, format_str):
        super().__init__()
        self.url = url
        self.download_path = download_path
        self.format_str = format_str

    def run(self):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(self.download_path, '%(title)s.%(ext)s'),
                'format': self.format_str,
                'merge_output_format': 'mp4',
                'progress_hooks': [self.hook],
                'quiet': True,
                'cookies': 'cookies.txt',
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                                  'Chrome/115.0.0.0 Safari/537.36'
                }
            }
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished.emit(self.url)
        except Exception as e:
            self.failed.emit(str(e))

    def hook(self, d):
        if d['status'] == 'downloading':
            percent = float(d.get('downloaded_bytes', 0)) / float(d.get('total_bytes', 1)) * 100
            self.progress.emit(self.url, int(percent))


class VideoDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"UNIVERSAL::Video Downloader (v{VERSION})")
        self.setGeometry(300, 100, 700, 400)
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__),"icons", "video.png")))

        self.download_threads = {}
        self.url_to_row = {}
        self.video_info = None
        self.format_map = {}
        self.is_dark_theme = False  # Track current theme

        self.init_ui()
        self.load_stylesheet(os.path.join(os.path.dirname(__file__),"qss", "light.css"))  # Default light mode

    def load_stylesheet(self, filename):
        try:
            with open(filename, "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass

    def toggle_theme(self):
        """Switch between light and dark themes."""
        self.is_dark_theme = not self.is_dark_theme

        if self.is_dark_theme:
            self.load_stylesheet(os.path.join(os.path.dirname(__file__),"qss", "dark.css"))
            self.theme_toggle_btn.setIcon(QIcon(os.path.join(os.path.dirname(__file__),"icons", "moon.png")))  # Dark mode icon
        else:
            self.load_stylesheet(os.path.join(os.path.dirname(__file__),"qss", "light.css"))  # Default light mode
            self.theme_toggle_btn.setIcon(QIcon(os.path.join(os.path.dirname(__file__),"icons", "sun.png")))  # Light mode icon

    def init_ui(self):
        layout = QVBoxLayout()

        # Top bar
        top_bar = QHBoxLayout()
        top_bar.addStretch()

        # Theme toggle button (icon only)
        self.theme_toggle_btn = QPushButton()
        self.theme_toggle_btn.setIcon(QIcon(os.path.join(os.path.dirname(__file__),"icons", "sun.png")))  # Light mode start
        self.theme_toggle_btn.setIconSize(QSize(20, 20))
        self.theme_toggle_btn.setFixedSize(32, 32)
        self.theme_toggle_btn.setFlat(True)
        self.theme_toggle_btn.clicked.connect(self.toggle_theme)

        top_bar.addWidget(self.theme_toggle_btn)
        layout.addLayout(top_bar)

        # URL input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste video URL here")
        layout.addWidget(self.url_input)

        # Frame with video title
        self.frame = QFrame(self)
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setObjectName("frame")
        self.frame.setStyleSheet("""
            QFrame#frame {
                background-color: rgba(219, 246, 185, 0.5);
                border: 1px solid #294900;
                border-radius: 4px;
            }
        """)
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(3, 5, 3, 5)
        self.video_title_label = QLabel(title_message)
        self.video_title_label.setWordWrap(True)
        frame_layout.addWidget(self.video_title_label)
        layout.addWidget(self.frame)

        # Format + buttons row
        hlayout = QHBoxLayout()
        self.format_combo = QComboBox()
        hlayout.addWidget(self.format_combo)

        self.download_btn = QPushButton("Download")
        self.download_btn.setEnabled(False)
        hlayout.addWidget(self.download_btn)

        self.browse_btn = QPushButton("Select Download Folder")
        hlayout.addWidget(self.browse_btn)
        layout.addLayout(hlayout)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.resizeSection(0, 30)
        self.table.setIconSize(QSize(20, 20))
        layout.addWidget(self.table)

        self.setLayout(layout)
        self.download_path = os.path.expanduser("~/Videos/downloads")

        # Connections
        self.url_timer = QTimer(self)
        self.url_timer.setSingleShot(True)
        self.url_timer.timeout.connect(self.fetch_info_from_url)
        self.url_input.textChanged.connect(self.schedule_info_fetch)
        self.browse_btn.clicked.connect(self.select_download_folder)
        self.download_btn.clicked.connect(self.start_download)

    def schedule_info_fetch(self):
        self.url_timer.start(800)

    def fetch_info_from_url(self):
        url = self.url_input.text().strip()
        if not re.match(r'^https?://', url):
            return

        self.video_title_label.setText("Fetching video info...")
        self.download_btn.setEnabled(False)

        self.fetch_thread = FetchVideoInfoThread(url)
        self.fetch_thread.infoFetched.connect(self.on_info_fetched)
        self.fetch_thread.fetchFailed.connect(self.on_info_fetch_failed)
        self.fetch_thread.start()

    def on_info_fetched(self, info):
        title = info.get("title", "Unknown Title")
        self.video_title_label.setText(title)
        self.download_btn.setEnabled(True)
        self.video_info = info

        self.format_combo.clear()
        self.format_map.clear()
        formats = sorted(info.get("formats", []), key=lambda get_format: (get_format.get("height") or 0, get_format.get("tbr") or 0), reverse=True)
        seen = set()

        for f in formats:
            fmt_id = f.get("format_id")
            height = f.get("height")
            ext = f.get("ext")
            acodec = f.get("acodec", "none")
            vcodec = f.get("vcodec", "none")
            label = None

            if height and acodec != "none" and vcodec != "none":
                label = f"{height}p ({ext})"
            elif height and acodec == "none":
                label = f"{height}p video only ({ext})"
            elif height is None and vcodec == "none":
                label = f"Audio only ({ext}, {f.get('abr', '?')} kbps)"

            if label and fmt_id not in seen:
                seen.add(fmt_id)
                self.format_combo.addItem(label)
                self.format_map[label] = fmt_id

    def on_info_fetch_failed(self, error):
        self.video_title_label.setText("Failed to fetch video info")
        self.download_btn.setEnabled(False)
        QMessageBox.critical(self, "Error", f"Failed to fetch info: {error}")

    def select_download_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.download_path)
        if folder:
            self.download_path = folder

    def start_download(self):
        url = self.url_input.text().strip()
        title = self.video_info.get("title", url)
        site_icon_path = self.get_site_icon(url)

        row = self.table.rowCount()
        self.table.insertRow(row)
        icon_item = QTableWidgetItem()
        icon_item.setIcon(QIcon(site_icon_path))
        self.table.setItem(row, 0, icon_item)
        self.table.setItem(row, 1, QTableWidgetItem(title))

        progress_bar = QProgressBar()
        progress_bar.setValue(0)
        self.table.setCellWidget(row, 2, progress_bar)

        status_item = QTableWidgetItem("Queued")
        status_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 3, status_item)

        self.url_to_row[url] = row
        selected_label = self.format_combo.currentText()
        fmt_id = self.format_map.get(selected_label)

        if "video only" in selected_label.lower():
            fmt_id = f"{fmt_id}+bestaudio"

        thread = DownloadThread(url, self.download_path, fmt_id)
        thread.progress.connect(self.update_progress)
        thread.finished.connect(self.on_download_finished)
        thread.failed.connect(lambda error, u=url: self.on_download_failed(u, error))
        self.download_threads[url] = thread
        thread.start()
        self.url_input.clear()
        self.video_title_label.setText(title_message)
        self.format_combo.clear()

    def update_progress(self, url, percent):
        row = self.url_to_row.get(url)
        if row is not None:
            widget = self.table.cellWidget(row, 2)
            if isinstance(widget, QProgressBar):
                widget.setValue(percent)
            self.table.item(row, 3).setText("Downloading")

    def on_download_finished(self, url):
        row = self.url_to_row.get(url)
        if row is not None:
            self.table.item(row, 3).setText("✅ Done")
            self.download_btn.setEnabled(False)

    def on_download_failed(self, url, error):
        row = self.url_to_row.get(url)
        if row is not None:
            self.table.item(row, 3).setText("❌ Failed")

    @staticmethod
    def get_site_icon(url):
        if "youtube.com" in url or "youtu.be" in url:
            return "./youtube.png"
        elif "facebook.com" in url:
            return "./facebook.png"
        elif "x.com" in url or "twitter.com" in url:
            return "./x.png"
        return "./video.png"


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoDownloader()
    window.show()
    sys.exit(app.exec_())
