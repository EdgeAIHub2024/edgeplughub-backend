import os
from flask import Flask, jsonify, send_from_directory, render_template, redirect, url_for, request, session, flash
from flask_jwt_extended import JWTManager
from models import db, User, Plugin
from routes.auth import auth_bp
from routes.plugins import plugins_bp, review_plugin
from dotenv import load_dotenv
from flask_cors import CORS
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
import uuid

# 加载环境变量
load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# 配置
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///edgeplughub.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-secret-key')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'admin-secret-key')  # 为session添加密钥

# 初始化扩展
db.init_app(app)
jwt = JWTManager(app)

# 注册蓝图
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(plugins_bp, url_prefix='/api/plugins')

# 静态文件服务
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# 首页
@app.route('/')
def home():
    return redirect(url_for('client_page'))

# 旧的API首页路由
@app.route('/api')
def api_home():
    return jsonify({
        "name": "EdgePlugHub API",
        "version": "0.1.0",
        "description": "API for EdgePlugHub plugin marketplace"
    })

# 管理界面相关路由
@app.route('/admin')
def admin_redirect():
    return redirect(url_for('admin_login'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password) and user.is_admin:
            session['admin_id'] = user.id
            session['admin_username'] = user.username
            return redirect(url_for('admin_dashboard'))
        else:
            error = '用户名或密码错误，或者用户不是管理员'
    
    return render_template('admin/login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))

# 检查是否已登录的装饰器
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    plugins = Plugin.query.all()
    return render_template('admin/dashboard.html', 
                          plugins=plugins, 
                          admin_username=session.get('admin_username'))

@app.route('/admin/plugins')
@admin_required
def admin_plugins():
    plugins = Plugin.query.all()
    return render_template('admin/plugins.html', 
                          plugins=plugins, 
                          admin_username=session.get('admin_username'))

@app.route('/admin/plugins/upload', methods=['GET', 'POST'])
@admin_required
def admin_upload_plugin():
    if request.method == 'POST':
        # 获取表单数据
        name = request.form.get('name')
        short_description = request.form.get('short_description')
        description = request.form.get('description')
        version = request.form.get('version')
        category = request.form.get('category')
        
        # 验证必填字段
        if not name or not short_description or not description or not version or not category:
            flash('请填写所有必填字段', 'error')
            return redirect(url_for('admin_upload_plugin'))
        
        # 处理图标上传
        icon_path = None
        if 'icon' in request.files:
            icon = request.files['icon']
            if icon.filename:
                filename = secure_filename(icon.filename)
                icon_uuid = str(uuid.uuid4())
                icon_filename = f"{icon_uuid}_{filename}"
                icon_path = os.path.join('icons', icon_filename)
                
                # 确保目录存在
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'icons'), exist_ok=True)
                icon.save(os.path.join(app.config['UPLOAD_FOLDER'], icon_path))
        
        # 处理插件包上传
        if 'package' not in request.files or not request.files['package'].filename:
            flash('请上传插件包文件', 'error')
            return redirect(url_for('admin_upload_plugin'))
        
        package = request.files['package']
        filename = secure_filename(package.filename)
        package_uuid = str(uuid.uuid4())
        package_filename = f"{package_uuid}_{filename}"
        package_path = os.path.join('packages', package_filename)
        
        # 确保目录存在
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'packages'), exist_ok=True)
        package.save(os.path.join(app.config['UPLOAD_FOLDER'], package_path))
        
        # 创建插件记录
        admin_id = session.get('admin_id')
        plugin = Plugin(
            name=name,
            short_description=short_description,
            description=description,
            version=version,
            author_id=admin_id,
            icon_path=icon_path,
            package_path=package_path,
            category=category,
            status='approved'  # 管理员上传的插件直接批准
        )
        
        db.session.add(plugin)
        db.session.commit()
        
        flash('插件上传成功', 'success')
        return redirect(url_for('admin_plugins'))
    
    return render_template('admin/upload_plugin.html', 
                          admin_username=session.get('admin_username'))

@app.route('/admin/plugins/<plugin_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_plugin(plugin_id):
    plugin = Plugin.query.get_or_404(plugin_id)
    
    if request.method == 'POST':
        # 更新插件信息
        plugin.name = request.form.get('name')
        plugin.short_description = request.form.get('short_description')
        plugin.description = request.form.get('description')
        plugin.version = request.form.get('version')
        plugin.category = request.form.get('category')
        plugin.status = request.form.get('status')
        
        # 保存更改
        db.session.commit()
        
        flash('插件信息更新成功', 'success')
        return redirect(url_for('admin_plugins'))
    
    return render_template('admin/edit_plugin.html', 
                          plugin=plugin, 
                          admin_username=session.get('admin_username'))

@app.route('/admin/plugins/<plugin_id>/delete', methods=['POST'])
@admin_required
def admin_delete_plugin(plugin_id):
    plugin = Plugin.query.get_or_404(plugin_id)
    
    # 删除关联的文件
    if plugin.icon_path:
        icon_path = os.path.join(app.config['UPLOAD_FOLDER'], plugin.icon_path)
        if os.path.exists(icon_path):
            os.remove(icon_path)
    
    if plugin.package_path:
        package_path = os.path.join(app.config['UPLOAD_FOLDER'], plugin.package_path)
        if os.path.exists(package_path):
            os.remove(package_path)
    
    # 删除数据库记录
    db.session.delete(plugin)
    db.session.commit()
    
    flash('插件已删除', 'success')
    return redirect(url_for('admin_plugins'))

# 创建初始管理员用户和示例插件
def create_initial_data():
    with app.app_context():
        db.create_all()
        
        # 检查是否已有管理员用户
        admin = User.query.filter_by(is_admin=True).first()
        if not admin:
            from werkzeug.security import generate_password_hash
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created")
        
        # 添加初始插件
        if Plugin.query.count() == 0:
            face_detector = Plugin(
                name='Face Detector',
                short_description='检测图像和视频中的人脸',
                description='一个强大的人脸检测插件，使用OpenCV进行实时人脸检测，适用于图像和视频流。支持多人脸检测，可以标记出人脸位置并提取单个人脸图像。内置GUI界面，方便测试和使用。',
                version='1.0.0',
                author_id=admin.id,
                icon_path='icons/face_detector.png',
                package_path='packages/face_detector.zip',
                category='Computer Vision',
                status='approved',
                downloads=1250,
                rating=4.7
            )
            
            skin_analyzer = Plugin(
                name='Skin Tone Analyzer',
                short_description='分析图像中的肤色',
                description='先进的肤色分析插件，能够检测并分类基于各种颜色模型的肤色。该插件可以提取面部肤色区域，计算主要肤色，并基于不同的颜色空间(RGB, HSV, Lab等)给出肤色分类。适用于美容、时尚、健康等领域的应用开发。',
                version='1.0.0',
                author_id=admin.id,
                icon_path='icons/skin_analyzer.png',
                package_path='packages/skin_analyzer.zip',
                category='Computer Vision',
                status='approved',
                downloads=840,
                rating=4.5
            )
            
            db.session.add(face_detector)
            db.session.add(skin_analyzer)
            db.session.commit()
            print("Initial plugins created")

# 确保目录存在
os.makedirs(app.static_folder, exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'icons'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'packages'), exist_ok=True)

# 添加客户端页面路由
@app.route('/client')
def client_page():
    plugins = Plugin.query.filter_by(status='approved').all()
    return render_template('client/index.html', plugins=plugins)

@app.route('/client/plugin/<plugin_id>')
def client_plugin_detail(plugin_id):
    plugin = Plugin.query.get_or_404(plugin_id)
    if plugin.status != 'approved':
        flash('该插件不可用', 'error')
        return redirect(url_for('client_page'))
    return render_template('client/plugin_detail.html', plugin=plugin)

# 添加下载插件的路由
@app.route('/download/<plugin_id>')
def download_plugin(plugin_id):
    plugin = Plugin.query.get_or_404(plugin_id)
    
    if plugin.status != 'approved':
        flash('该插件不可用', 'error')
        return redirect(url_for('client_page'))
    
    # 增加下载计数
    plugin.downloads += 1
    db.session.commit()
    
    # 返回文件
    directory = os.path.join(app.config['UPLOAD_FOLDER'], os.path.dirname(plugin.package_path))
    filename = os.path.basename(plugin.package_path)
    
    return send_from_directory(directory, filename, as_attachment=True, 
                              download_name=f"{plugin.name}-{plugin.version}.zip")

# 在应用启动时初始化数据
create_initial_data()

@app.route('/api/plugins', methods=['GET'])
def get_plugins():
    # ... existing code ...

@app.route('/api/plugins/<plugin_id>', methods=['GET'])
def get_plugin_details(plugin_id):
    # ... existing code ...

@app.route('/api/plugins/download/<plugin_id>', methods=['GET'])
def download_plugin(plugin_id):
    # ... existing code ...

@app.route('/api/plugins/upload', methods=['POST'])
def upload_plugin():
    # ... existing code ...

@app.route('/api/auth/login', methods=['POST'])
def login():
    # ... existing code ...

@app.route('/api/auth/register', methods=['POST'])
def register():
    # ... existing code ...

if __name__ == '__main__':
    app.run(debug=True) 