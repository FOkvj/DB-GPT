#!/usr/bin/env python3
import os
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

# 设置要共享的目录
shared_directory = "./"

authorizer = DummyAuthorizer()
# 添加用户（用户名，密码，共享目录，权限）
authorizer.add_user("t10", "1234", shared_directory, perm="elradfmw")

handler = FTPHandler
handler.authorizer = authorizer

if __name__ == "__main__":
    # 启动FTP服务器（端口21）
    server = FTPServer(("0.0.0.0", 21), handler)
    server.serve_forever()