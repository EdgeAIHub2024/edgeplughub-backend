#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Blueprint, jsonify, current_app
import platform
import os

server_bp = Blueprint('server', __name__)

@server_bp.route('/status', methods=['GET'])
def get_server_status():
    """获取服务器状态"""
    server_version = current_app.config.get('VERSION', '1.0.0')
    
    return jsonify({
        'status': 'ok',
        'online': True,
        'version': server_version,
        'platform': platform.platform(),
        'python_version': platform.python_version()
    }) 