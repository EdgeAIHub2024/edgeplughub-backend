import os
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from models import db, Plugin, User
import uuid

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

@plugins_bp.route('/download/<plugin_id>', methods=['GET'])
def download_plugin(plugin_id):
    plugin = Plugin.query.get_or_404(plugin_id)
    
    if plugin.status != 'approved':
        return jsonify({"msg": "Plugin not available for download"}), 403
    
    # Increment download counter
    plugin.downloads += 1
    db.session.commit()
    
    # Return the file
    directory = os.path.join(current_app.config['UPLOAD_FOLDER'], os.path.dirname(plugin.package_path))
    filename = os.path.basename(plugin.package_path)
    
    return send_from_directory(directory, filename, as_attachment=True, 
                              attachment_filename=f"{plugin.name}-{plugin.version}.zip")

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