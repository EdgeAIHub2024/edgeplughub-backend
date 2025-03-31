from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    plugins = db.relationship('Plugin', backref='author', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Plugin(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    short_description = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    version = db.Column(db.String(20), nullable=False)
    author_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    icon_path = db.Column(db.String(255))
    package_path = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    downloads = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0.0)
    git_repo = db.Column(db.String(255))
    requires_auth = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Plugin {self.name}>'
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'short_description': self.short_description,
            'description': self.description,
            'version': self.version,
            'author': self.author.username,
            'icon_url': f'/static/{self.icon_path}' if self.icon_path else None,
            'category': self.category,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'status': self.status,
            'downloads': self.downloads,
            'rating': self.rating,
            'git_repo': self.git_repo,
            'requires_auth': self.requires_auth
        } 