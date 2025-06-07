from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import pandas as pd
import xml.etree.ElementTree as ET
import json
import configparser
from datetime import datetime
import os

# Configuración inicial de Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'hello-esime-secret-key'
socketio = SocketIO(app)

# Rutas para archivos de datos
USERS_CSV = 'data/usuarios.csv'
MESSAGES_XML = 'data/mensajes.xml'
STATS_JSON = 'data/stats.json'
CONFIG_INI = 'data/config.ini'

# Configuración para archivos
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# En app.py, modificar la función upload_file
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No se seleccionó archivo'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
        
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
                
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            return jsonify({
                'success': True, 
                'filename': filename,
                'size': os.path.getsize(file_path),
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Tipo de archivo no permitido'}), 400

@app.route('/files')
def list_files():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    files = []
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            files.append({
                'name': filename,
                'size': os.path.getsize(file_path),
                'date': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
            })
    
    return render_template('files.html', files=files)

@app.route('/download/<filename>')
def download_file(filename):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

def init_users_csv():
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists(USERS_CSV):
        df = pd.DataFrame(columns=[
            'username', 'password_hash', 'nickname', 
            'avatar', 'role', 'banned', 
            'created_date', 'last_login'
        ])
        df.to_csv(USERS_CSV, index=False, encoding='utf-8-sig')

def get_user(username):
    try:
        df = pd.read_csv(USERS_CSV, encoding='utf-8-sig')
        user = df[df['username'] == username]
        return user.to_dict('records')[0] if not user.empty else None
    except Exception as e:
        print(f"Error al obtener usuario: {e}")
        return None

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Obtener historial de mensajes
    chat_history = []
    try:
        tree = ET.parse(MESSAGES_XML)
        root = tree.getroot()
        for message in root.findall('.//message'):
            chat_history.append({
                'message': message.text,
                'sender': message.get('username'),
                'timestamp': message.get('timestamp')
            })
    except Exception as e:
        print(f"Error al cargar mensajes: {e}")
    
    # Obtener lista de archivos
    files = []
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            files.append({
                'name': filename,
                'size': os.path.getsize(file_path),
                'date': datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
            })
    
    return render_template('chat.html', chat_history=chat_history, files=files)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = get_user(username)
        if user and check_password_hash(user['password_hash'], password):
            if user['banned']:
                return "Usuario suspendido", 403
            
            session['username'] = username
            session['role'] = user['role']
            
            # Actualizar último login
            df = pd.read_csv(USERS_CSV)
            df.loc[df['username'] == username, 'last_login'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            df.to_csv(USERS_CSV, index=False)
            
            return redirect(url_for('index'))
        
        return "Usuario o contraseña incorrectos", 401
    
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        nickname = request.form.get('nickname')
        
        # Verificar si el usuario ya existe
        if get_user(username):
            return "El usuario ya existe", 400
        
        new_user = {
            'username': username,
            'password_hash': generate_password_hash(password),
            'nickname': nickname,
            'avatar': 'default.png',
            'role': 'user',
            'banned': False,
            'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'last_login': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            df = pd.read_csv(USERS_CSV, encoding='utf-8-sig')
        except:
            # Si hay error al leer, inicializar nuevo DataFrame
            df = pd.DataFrame(columns=[
                'username', 'password_hash', 'nickname', 
                'avatar', 'role', 'banned', 
                'created_date', 'last_login'
            ])
        
        df = df._append(new_user, ignore_index=True)
        df.to_csv(USERS_CSV, index=False, encoding='utf-8-sig')
        
        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@socketio.on('get_messages')
def handle_get_messages():
    try:
        tree = ET.parse(MESSAGES_XML)
        root = tree.getroot()
        messages = []
        
        for message in root.findall('.//message'):
            messages.append({
                'message': message.text,
                'sender': message.get('username'),
                'timestamp': message.get('timestamp')[-8:]  # Solo hora:minuto:segundo
            })
        
        # Emitir mensajes solo al cliente que los solicitó
        emit('messages_history', messages)
        
    except Exception as e:
        print(f"Error al cargar mensajes: {e}")


@socketio.on('message')
def handle_message(data):
    try:
        # Obtener mensaje y usuario actual
        message = data.get('message')
        username = session.get('username')
        
        if not message or not username:
            return
        
        # Guardar mensaje en XML
        tree = ET.parse(MESSAGES_XML)
        root = tree.getroot()
        messages = root.find('messages')
        
        new_message = ET.SubElement(messages, 'message')
        new_message.set('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        new_message.set('username', username)
        new_message.text = message
        
        tree.write(MESSAGES_XML)
        
        # Actualizar estadísticas
        with open(STATS_JSON, 'r') as f:
            stats = json.load(f)
        
        stats['total_messages'] += 1
        stats['last_activity'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        today = datetime.now().strftime('%Y-%m-%d')
        stats['messages_per_day'][today] = stats['messages_per_day'].get(today, 0) + 1
        
        with open(STATS_JSON, 'w') as f:
            json.dump(stats, f, indent=4)
        
        # Emitir mensaje a todos los usuarios
        emit('message', {
            'message': message,
            'sender': username,
            'timestamp': datetime.now().strftime('%H:%M')
        }, broadcast=True)
        
    except Exception as e:
        print(f"Error al manejar mensaje: {e}")

# Inicializar el CSV de usuarios al arrancar la aplicación
init_users_csv()

if __name__ == '__main__':
    socketio.run(app, debug=True)