import os
from flask import Blueprint, request, jsonify, current_app, send_from_directory, send_file, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from models import db, Plugin, User
import uuid
from os import path, listdir
import json
from datetime import datetime
import shutil

plugins_bp = Blueprint('plugins', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'zip'}

@plugins_bp.route('', methods=['GET'])
def get_plugins():
    status = request.args.get('status', 'approved')
    category = request.args.get('category')
    
    query = Plugin.query
    
    if status:
        query = query.filter_by(status=status)
    if category:
        query = query.filter_by(category=category)
    
    plugins = query.all()
    return jsonify([p.to_dict() for p in plugins])

@plugins_bp.route('/<plugin_id>', methods=['GET'])
def get_plugin(plugin_id):
    plugin = Plugin.query.get_or_404(plugin_id)
    
    # Increment download counter for detail view
    plugin.downloads += 1
    db.session.commit()
    
    return jsonify(plugin.to_dict())

@plugins_bp.route('', methods=['POST'])
@jwt_required()
def create_plugin():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"msg": "User not found"}), 404
    
    # Parse form data
    name = request.form.get('name')
    short_description = request.form.get('short_description')
    description = request.form.get('description')
    version = request.form.get('version')
    category = request.form.get('category')
    git_repo = request.form.get('git_repo')
    requires_auth = True if request.form.get('requires_auth') == 'true' else False
    
    if not name or not description or not version or not category:
        return jsonify({"msg": "Missing required fields"}), 400
    
    # Handle icon upload
    icon_path = None
    if 'icon' in request.files:
        icon = request.files['icon']
        if icon.filename:
            filename = secure_filename(icon.filename)
            icon_uuid = str(uuid.uuid4())
            icon_filename = f"{icon_uuid}_{filename}"
            icon_path = os.path.join('icons', icon_filename)
            icon.save(os.path.join(current_app.config['UPLOAD_FOLDER'], icon_path))
    
    # Handle package upload
    if 'package' not in request.files:
        return jsonify({"msg": "No package file"}), 400
    
    package = request.files['package']
    if not package.filename:
        return jsonify({"msg": "No selected file"}), 400
    
    if not allowed_file(package.filename):
        return jsonify({"msg": "File type not allowed"}), 400
    
    filename = secure_filename(package.filename)
    package_uuid = str(uuid.uuid4())
    package_filename = f"{package_uuid}_{filename}"
    package_path = os.path.join('packages', package_filename)
    package.save(os.path.join(current_app.config['UPLOAD_FOLDER'], package_path))
    
    # Create plugin
    plugin = Plugin(
        name=name,
        short_description=short_description,
        description=description,
        version=version,
        author_id=user_id,
        icon_path=icon_path,
        package_path=package_path,
        category=category,
        git_repo=git_repo,
        requires_auth=requires_auth,
        status='pending'  # All plugins start as pending
    )
    
    db.session.add(plugin)
    db.session.commit()
    
    return jsonify(plugin.to_dict()), 201

@plugins_bp.route('/<plugin_id>/download', methods=['GET'])
def download_plugin(plugin_id):
    try:
        plugin = Plugin.query.get_or_404(plugin_id)
        
        if plugin.status != 'approved':
            return jsonify({"msg": "插件未批准，不允许下载"}), 403
        
        # 增加日志记录
        current_app.logger.info(f"请求下载插件: {plugin_id}, 名称: {plugin.name}, 状态: {plugin.status}")
        
        # 使用web目录路径
        web_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 获取web目录路径
        packages_dir = os.path.join(web_dir, 'uploads', 'packages')
        current_app.logger.info(f"查找插件包目录(web目录): {packages_dir}")
        
        if not os.path.exists(packages_dir):
            current_app.logger.error(f"插件包目录不存在: {packages_dir}")
            os.makedirs(packages_dir, exist_ok=True)
            current_app.logger.info(f"已创建插件包目录: {packages_dir}")
            return jsonify({"msg": "插件目录不存在，请联系管理员"}), 404
        
        # 列出目录内容
        try:
            files = os.listdir(packages_dir)
            current_app.logger.info(f"web/uploads/packages目录内容: {files}")
        except Exception as e:
            current_app.logger.error(f"读取插件包目录失败: {str(e)}")
            return jsonify({"msg": f"读取插件包目录失败: {str(e)}"}), 500
        
        # 优先级搜索策略：
        # 1. 检查数据库中记录的路径
        # 2. 特殊插件文件匹配
        # 3. 按插件ID查找
        # 4. 按插件名称查找
        # 5. 按包含插件名称的文件名查找
        
        # 方案1: 检查数据库中记录的路径
        package_path = plugin.package_path
        if package_path:
            full_path = os.path.join(web_dir, 'uploads', package_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                current_app.logger.info(f"从数据库记录找到插件包(web目录): {full_path}")
                return send_file(full_path, as_attachment=True)
            current_app.logger.warning(f"数据库记录的包路径无效(web目录): {full_path}")
        
        # 方案2: 特殊插件文件匹配
        special_files = {
            'face': 'face_detector.zip',
            'detector': 'face_detector.zip',
            'skin': 'skin_analyzer.zip',
            'analyzer': 'skin_analyzer.zip'
        }
        
        # 首先尝试特殊文件匹配
        file_candidates = []
        for keyword, special_file in special_files.items():
            if keyword in plugin.name.lower() and special_file in files:
                file_candidates.append(special_file)
                current_app.logger.info(f"按特殊规则找到匹配文件: {special_file}")
        
        # 方案3: 按插件ID查找
        id_filename = f"{plugin_id}.zip"
        if id_filename in files and id_filename not in file_candidates:
            file_candidates.append(id_filename)
            current_app.logger.info(f"按ID找到匹配文件: {id_filename}")
        
        # 方案4: 按插件名称查找
        name_filename = f"{plugin.name.lower().replace(' ', '_')}.zip"
        if name_filename in files and name_filename not in file_candidates:
            file_candidates.append(name_filename)
            current_app.logger.info(f"按名称找到匹配文件: {name_filename}")
        
        # 方案5: 按包含插件名称的文件查找
        plugin_name_lower = plugin.name.lower().replace(' ', '_')
        for filename in files:
            if plugin_name_lower in filename.lower() and filename not in file_candidates:
                file_candidates.append(filename)
                current_app.logger.info(f"按名称部分匹配找到文件: {filename}")
        
        # 如果找到了候选文件，返回第一个
        if file_candidates:
            selected_file = file_candidates[0]
            full_path = os.path.join(packages_dir, selected_file)
            
            # 检查文件是否是有效的zip文件
            try:
                import zipfile
                if zipfile.is_zipfile(full_path):
                    current_app.logger.info(f"验证为有效的zip文件(web目录): {full_path}")
                    
                    # 更新下载计数
                    plugin.downloads += 1
                    db.session.commit()
                    
                    # 返回文件
                    return send_file(full_path, as_attachment=True)
                else:
                    current_app.logger.error(f"找到的文件不是有效的zip文件(web目录): {full_path}")
            except Exception as e:
                current_app.logger.error(f"验证zip文件时出错: {str(e)}")
        
        # 没有找到匹配的文件
        current_app.logger.error(f"未找到匹配的插件包文件(web目录): {plugin.name} (ID: {plugin_id})")
        
        # 列出所有可用文件供参考
        file_info = "\n".join([f"- {f}" for f in files]) if files else "目录为空"
        current_app.logger.info(f"可用的包文件(web目录):\n{file_info}")
        
        return jsonify({"msg": "插件文件未找到，请联系管理员上传正确的插件包", "files_available": files}), 404
        
    except Exception as e:
        current_app.logger.error(f"下载插件时出错: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({"msg": f"下载插件时出错: {str(e)}"}), 500

@plugins_bp.route('/review/<plugin_id>', methods=['POST'])
@jwt_required()
def review_plugin(plugin_id):
    # 检查是否为管理员
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_admin:
        return jsonify({'message': 'Only admin can review plugins'}), 403
    
    plugin = Plugin.query.get_or_404(plugin_id)
    
    # 从表单或JSON中获取状态
    if request.is_json:
        status = request.json.get('status')
    else:
        status = request.form.get('status')
    
    if not status or status not in ['approved', 'rejected']:
        return jsonify({'message': 'Invalid status'}), 400
    
    plugin.status = status
    db.session.commit()
    
    return jsonify({'message': f'Plugin {status}', 'plugin': plugin.to_dict()})

@plugins_bp.route('/available', methods=['GET'])
def get_available_plugins():
    """获取可供下载的插件列表，供客户端应用中心使用"""
    category = request.args.get('category')
    
    query = Plugin.query.filter_by(status='approved')
    
    if category:
        query = query.filter_by(category=category)
    
    plugins = query.all()
    return jsonify([p.to_dict() for p in plugins])

@plugins_bp.route('/categories', methods=['GET'])
def get_plugin_categories():
    """获取所有可用的插件分类"""
    # 从所有已批准的插件中获取唯一的分类列表
    categories = db.session.query(Plugin.category).distinct().filter(Plugin.status=='approved').all()
    return jsonify([c[0] for c in categories])

@plugins_bp.route('/plugins/available', methods=['GET'])
def get_available_plugins_json():
    """获取可用的插件列表"""
    # 获取查询参数
    category = request.args.get('category')
    
    # 读取插件数据
    plugins_file = os.path.join(current_app.config['DATA_DIR'], 'plugins.json')
    if not os.path.exists(plugins_file):
        return jsonify([])
    
    with open(plugins_file, 'r') as f:
        plugins = json.load(f)
    
    # 如果指定了分类，筛选结果
    if category:
        plugins = [p for p in plugins if p.get('category') == category]
    
    return jsonify(plugins)

@plugins_bp.route('/plugins/<plugin_id>', methods=['GET'])
def get_plugin_json(plugin_id):
    """获取特定插件的详情"""
    # 读取插件数据
    plugins_file = os.path.join(current_app.config['DATA_DIR'], 'plugins.json')
    if not os.path.exists(plugins_file):
        return jsonify({"error": "Plugin not found"}), 404
    
    with open(plugins_file, 'r') as f:
        plugins = json.load(f)
    
    # 查找插件
    plugin = next((p for p in plugins if p.get('id') == plugin_id), None)
    if not plugin:
        return jsonify({"error": "Plugin not found"}), 404
    
    return jsonify(plugin)

@plugins_bp.route('/plugins/categories', methods=['GET'])
def get_categories():
    """获取插件分类列表"""
    # 读取插件数据
    plugins_file = os.path.join(current_app.config['DATA_DIR'], 'plugins.json')
    if not os.path.exists(plugins_file):
        return jsonify([])
    
    with open(plugins_file, 'r') as f:
        plugins = json.load(f)
    
    # 提取并去重分类
    categories = list(set(p.get('category', '未分类') for p in plugins))
    
    return jsonify(categories)

@plugins_bp.route('/plugins/<plugin_id>/icon', methods=['GET'])
def get_plugin_icon(plugin_id):
    """获取插件图标"""
    # 设置图标目录
    icons_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'icons')
    
    # 尝试多种可能的图标文件名，按优先级排列
    possible_icon_paths = [
        os.path.join(icons_dir, f"{plugin_id}.png"),  # 插件ID.png
        os.path.join(icons_dir, f"{plugin_id}.jpg"),  # 插件ID.jpg
    ]
    
    # 尝试查找插件数据，提取名称生成更多可能的文件名
    try:
        # 尝试从数据库获取插件
        plugin = Plugin.query.get(plugin_id)
        if plugin and plugin.name:
            plugin_name = plugin.name.lower().replace(' ', '_')
            possible_icon_paths.extend([
                os.path.join(icons_dir, f"{plugin_name}.png"),
                os.path.join(icons_dir, f"{plugin_name}.jpg")
            ])
    except Exception as e:
        current_app.logger.warning(f"从数据库获取插件信息失败: {e}")
        pass
        
    # 尝试从plugins.json文件获取插件信息
    try:
        plugins_file = os.path.join(current_app.config['DATA_DIR'], 'plugins.json')
        if os.path.exists(plugins_file):
            with open(plugins_file, 'r') as f:
                plugins = json.load(f)
                plugin_info = next((p for p in plugins if p.get('id') == plugin_id), None)
                if plugin_info and plugin_info.get('name'):
                    plugin_name = plugin_info['name'].lower().replace(' ', '_')
                    possible_icon_paths.extend([
                        os.path.join(icons_dir, f"{plugin_name}.png"),
                        os.path.join(icons_dir, f"{plugin_name}.jpg")
                    ])
    except Exception as e:
        current_app.logger.warning(f"从JSON文件获取插件信息失败: {e}")
        pass
    
    # 检查所有可能的图标路径
    for icon_path in possible_icon_paths:
        if os.path.exists(icon_path):
            current_app.logger.info(f"使用图标: {icon_path}")
            return send_file(icon_path)
    
    # 如果没有找到特定图标，返回默认图标
    default_icon_path = os.path.join(icons_dir, 'default.png')
    if os.path.exists(default_icon_path):
        current_app.logger.info(f"使用默认图标: {default_icon_path}")
        return send_file(default_icon_path)
    else:
        current_app.logger.warning(f"图标未找到: {plugin_id}")
        return jsonify({"error": "Icon not found"}), 404

@plugins_bp.route('/plugins/installed', methods=['GET'])
def get_installed_plugins():
    """获取已安装的插件列表"""
    installed_file = os.path.join(current_app.config['DATA_DIR'], 'installed_plugins.json')
    if not os.path.exists(installed_file):
        return jsonify([])
    
    with open(installed_file, 'r') as f:
        installed_plugins = json.load(f)
    
    return jsonify(installed_plugins)

@plugins_bp.route('/plugins/installed/<plugin_id>', methods=['POST'])
def add_installed_plugin(plugin_id):
    """添加已安装的插件"""
    # 读取请求数据
    plugin_data = request.json
    if not plugin_data:
        return jsonify({"error": "Invalid plugin data"}), 400
    
    # 确保插件ID存在
    if 'id' not in plugin_data:
        plugin_data['id'] = plugin_id
    
    # 读取当前已安装插件列表
    installed_file = os.path.join(current_app.config['DATA_DIR'], 'installed_plugins.json')
    installed_plugins = []
    if os.path.exists(installed_file):
        with open(installed_file, 'r') as f:
            installed_plugins = json.load(f)
    
    # 检查插件是否已经存在
    existing_plugin = next((p for p in installed_plugins if p.get('id') == plugin_id), None)
    if existing_plugin:
        # 更新已存在的插件
        for key, value in plugin_data.items():
            existing_plugin[key] = value
    else:
        # 添加新插件
        plugin_data['install_date'] = datetime.now().isoformat()
        installed_plugins.append(plugin_data)
    
    # 保存更新后的列表
    with open(installed_file, 'w') as f:
        json.dump(installed_plugins, f, indent=2)
    
    return jsonify({"success": True})

@plugins_bp.route('/plugins/installed/<plugin_id>', methods=['DELETE'])
def remove_installed_plugin(plugin_id):
    """移除已安装的插件"""
    # 读取当前已安装插件列表
    installed_file = os.path.join(current_app.config['DATA_DIR'], 'installed_plugins.json')
    if not os.path.exists(installed_file):
        return jsonify({"error": "No installed plugins"}), 404
    
    with open(installed_file, 'r') as f:
        installed_plugins = json.load(f)
    
    # 查找并移除插件
    updated_plugins = [p for p in installed_plugins if p.get('id') != plugin_id]
    if len(updated_plugins) == len(installed_plugins):
        return jsonify({"error": "Plugin not found"}), 404
    
    # 保存更新后的列表
    with open(installed_file, 'w') as f:
        json.dump(updated_plugins, f, indent=2)
    
    return jsonify({"success": True})

@plugins_bp.route('/plugins/upload', methods=['POST'])
def upload_plugin():
    """上传插件包"""
    # 检查是否有文件
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    # 检查文件格式
    if not file.filename.endswith('.zip'):
        return jsonify({"error": "Invalid file format, only .zip files are allowed"}), 400
    
    # 保存文件
    filename = secure_filename(file.filename)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'packages', filename)
    file.save(file_path)
    
    return jsonify({"success": True, "filename": filename})

@plugins_bp.route('/<plugin_id>/download-info', methods=['GET'])
def get_plugin_download_info(plugin_id):
    """获取插件下载信息，包括下载URL和图标URL
    
    返回: 
        {
            "download_url": "http://localhost:5000/api/plugins/<plugin_id>/download",
            "icon_url": "http://localhost:5000/api/plugins/<plugin_id>/icon",
            "name": "插件名称",
            "version": "1.0.0",
            "plugin_id": "<plugin_id>",
            "file_exists": true/false  # 是否找到了文件
        }
    """
    try:
        plugin = Plugin.query.get_or_404(plugin_id)
        
        if plugin.status != 'approved':
            return jsonify({"msg": "插件未批准，不允许下载"}), 403
        
        # 增加日志记录
        current_app.logger.info(f"获取插件下载信息: {plugin_id}, 名称: {plugin.name}, 状态: {plugin.status}")
        
        # 构建基础URL
        host_url = request.host_url.rstrip('/')
        api_base = f"{host_url}/api/plugins"
        
        # 获取web目录路径
        web_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        packages_dir = os.path.join(web_dir, 'uploads', 'packages')
        current_app.logger.info(f"查找插件包目录(web目录): {packages_dir}")
        
        file_exists = False
        
        # 确认目录存在
        if not os.path.exists(packages_dir):
            current_app.logger.error(f"插件包目录不存在(web目录): {packages_dir}")
            os.makedirs(packages_dir, exist_ok=True)
            current_app.logger.info(f"已创建插件包目录(web目录): {packages_dir}")
        else:
            # 列出目录内容
            try:
                files = os.listdir(packages_dir)
                current_app.logger.info(f"web/uploads/packages目录内容: {files}")
            except Exception as e:
                current_app.logger.error(f"读取插件包目录失败(web目录): {str(e)}")
                files = []
            
            # 优先级搜索策略
            # 1. 检查数据库中记录的路径
            if plugin.package_path:
                full_path = os.path.join(web_dir, 'uploads', plugin.package_path)
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    file_exists = True
                    current_app.logger.info(f"从数据库记录确认文件存在(web目录): {full_path}")
            
            # 2. 特殊插件文件匹配
            if not file_exists:
                special_files = {
                    'face': 'face_detector.zip',
                    'detector': 'face_detector.zip',
                    'skin': 'skin_analyzer.zip',
                    'analyzer': 'skin_analyzer.zip'
                }
                
                for keyword, special_file in special_files.items():
                    if keyword in plugin.name.lower() and special_file in files:
                        file_exists = True
                        current_app.logger.info(f"按特殊规则确认文件存在: {special_file}")
                        break
            
            # 3. 按插件ID查找
            if not file_exists:
                id_filename = f"{plugin_id}.zip"
                if id_filename in files:
                    file_exists = True
                    current_app.logger.info(f"按ID确认文件存在: {id_filename}")
            
            # 4. 按插件名称查找
            if not file_exists:
                name_filename = f"{plugin.name.lower().replace(' ', '_')}.zip"
                if name_filename in files:
                    file_exists = True
                    current_app.logger.info(f"按名称确认文件存在: {name_filename}")
            
            # 5. 按包含插件名称的文件查找
            if not file_exists:
                plugin_name_lower = plugin.name.lower().replace(' ', '_')
                for filename in files:
                    if plugin_name_lower in filename.lower():
                        file_exists = True
                        current_app.logger.info(f"按名称部分匹配确认文件存在: {filename}")
                        break
        
        # 构建下载URL
        download_url = f"{api_base}/{plugin_id}/download"
        
        # 构建图标URL
        icon_url = f"{api_base}/{plugin_id}/icon"
        
        # 如果存在图标文件但没有数据库记录，更新数据库
        icons_dir = os.path.join(web_dir, 'uploads', 'icons')
        if os.path.exists(icons_dir):
            icon_filename = f"{plugin_id}.png"
            icon_path = os.path.join(icons_dir, icon_filename)
            
            if os.path.exists(icon_path) and not plugin.icon_path:
                # 更新数据库记录
                rel_path = os.path.join('icons', icon_filename)
                plugin.icon_path = rel_path
                db.session.commit()
                current_app.logger.info(f"更新了图标路径到数据库: {rel_path}")
        
        # 返回下载信息
        result = {
            "download_url": download_url,
            "icon_url": icon_url,
            "name": plugin.name,
            "version": plugin.version,
            "plugin_id": plugin_id,
            "file_exists": file_exists
        }
        
        current_app.logger.info(f"获取到插件下载信息: {result}")
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"获取插件下载信息时出错: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({"msg": f"获取插件下载信息时出错: {str(e)}"}), 500

@plugins_bp.route('/direct/<path:plugin_path>', methods=['GET'])
def direct_plugin_download(plugin_path):
    """
    直接从public/plugins目录下载插件
    用于下载预置的插件包，如人脸检测和肤色分析插件
    """
    current_app.logger.info(f"请求直接下载插件: {plugin_path}")
    
    # 构建插件文件路径
    web_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    plugins_dir = os.path.join(web_dir, 'public', 'plugins')
    full_path = os.path.join(plugins_dir, plugin_path)
    
    current_app.logger.info(f"插件文件路径: {full_path}")
    
    # 检查文件是否存在
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        current_app.logger.error(f"插件文件不存在: {full_path}")
        return jsonify({"error": "Plugin file not found"}), 404
    
    # 检查是否是.zip文件
    if not full_path.endswith('.zip'):
        current_app.logger.error(f"请求的文件不是zip文件: {full_path}")
        return jsonify({"error": "Not a zip file"}), 400
    
    # 返回文件
    current_app.logger.info(f"发送插件文件: {full_path}")
    return send_file(full_path, as_attachment=True)

@plugins_bp.route('/manifest', methods=['GET'])
def get_plugins_manifest():
    """
    获取插件清单，提供可用插件的元数据
    """
    current_app.logger.info("请求插件清单")
    
    # 构建清单文件路径
    web_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(web_dir, 'public', 'plugins', 'manifest', 'plugins.json')
    
    current_app.logger.info(f"插件清单路径: {manifest_path}")
    
    # 检查文件是否存在
    if not os.path.exists(manifest_path) or not os.path.isfile(manifest_path):
        current_app.logger.error(f"插件清单文件不存在: {manifest_path}")
        return jsonify({"error": "Manifest file not found"}), 404
    
    # 读取清单文件
    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        current_app.logger.info("成功读取插件清单")
        return jsonify(manifest)
    except Exception as e:
        current_app.logger.error(f"读取插件清单出错: {str(e)}")
        return jsonify({"error": f"Failed to read manifest: {str(e)}"}), 500 