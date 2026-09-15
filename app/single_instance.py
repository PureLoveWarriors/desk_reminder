"""单实例检测：保证同一账号下只运行一份 DeskReminder。

用 QLocalServer/QLocalSocket 做进程间通信：
- 启动时先尝试连接已有实例的本地服务，能连上说明已经在跑，
  发个消息通知它把窗口显示出来，然后自己退出。
- 连不上就自己起一个服务，等着接收后来者的“show”消息。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from . import config

_SERVER_NAME = f"{config.APP_NAME}-single-instance"


class SingleInstanceGuard(QObject):
    """is_primary=False 时说明已有实例在跑，调用方应立即退出。"""

    show_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server: QLocalServer | None = None
        self.is_primary = self._try_claim()

    def _try_claim(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(_SERVER_NAME)
        if socket.waitForConnected(200):
            socket.write(b"show")
            socket.waitForBytesWritten(200)
            socket.disconnectFromServer()
            return False

        # 连不上：没有实例在跑，或者上次异常退出留下了残留的 server 名字
        QLocalServer.removeServer(_SERVER_NAME)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._server.listen(_SERVER_NAME)
        return True

    def _on_new_connection(self):
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            sock.readyRead.connect(lambda s=sock: self._consume(s))
            sock.disconnected.connect(sock.deleteLater)

    def _consume(self, sock: QLocalSocket):
        sock.readAll()
        self.show_requested.emit()
