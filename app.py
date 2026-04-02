from flask import Flask, request, render_template, send_from_directory, url_for, redirect, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from waitress import serve
import os
import qrcode
import socket
from flask_mysqldb import MySQL
import MySQLdb.cursors
from dotenv import load_dotenv
import re

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv('SECRET_KEY')

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.getenv('PASSWORD')
if not os.getenv('PASSWORD'):
    raise ValueError("MySQL PASSWORD not loaded from .env")
app.config['MYSQL_DB'] = 'flask_login'

mysql = MySQL(app)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
  msg = ''
  if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
    username = request.form['username']
    password = request.form['password']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM accounts WHERE username = %s', (username, ))
    account = cursor.fetchone()
    if account and check_password_hash(account['password'], password):
      session['loggedin'] = True
      session['id'] = account['id']
      session['username'] = account['username']
      session['msg'] = "Logged in Successfully!"
      return redirect(url_for('index'))
    else:
      msg = "Incorrect username OR password!"
  return render_template('login.html', msg=msg)

@app.route('/logout')
def logout():
  session.pop('loggedin', None)
  session.pop('id', None)
  session.pop('username', None)
  return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
  msg = ''
  if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'email' in request.form:
    username = request.form['username']
    password = request.form['password']
    email = request.form['email']
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM accounts WHERE username = %s',(username,))
    account = cursor.fetchone()
    
    if account:
      msg = "Account already exists!"
    elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
      msg = "Invalid email address!"
    elif not re.match(r'[A-Za-z0-9]+', username):
      msg = 'Username must contain only letters and numbers!'
    elif not username or not password or not email:
      msg = 'Please fill out the form!'
    else:
      hashed_password = generate_password_hash(password)
      cursor.execute('INSERT INTO accounts VALUES (NULL, %s, %s, %s)', (username, hashed_password, email))
      mysql.connection.commit()
      msg = "You have successfully registered!"
  return render_template('register.html', msg=msg)

@app.route('/index', methods=['GET', 'POST'])
def index():
  if 'loggedin' not in session:
        return redirect(url_for('login'))
  files = os.listdir(UPLOAD_FOLDER)
  ip = get_ip()
  url = f"http://{ip}:5001"
  qr_path = os.path.join("static", "qr.png")
  qr = qrcode.make(url)
  qr.save(qr_path)
  return render_template('index.html', files=files, qr="qr.png", url=url)
  
@app.route('/upload', methods=["POST"])
def upload():
   if 'loggedin' not in session:
    return redirect(url_for('login'))
   file = request.files.get('file')
   if not file or file.filename == '':
        return redirect(url_for('index'))
   if file:
    filename = secure_filename(file.filename)
    file.stream.seek(0)
    with open(os.path.join(UPLOAD_FOLDER, filename), "wb") as f:
      f.write(file.read())
   return redirect(url_for('index'))

@app.route("/download/<filename>")
def download(filename):
  if 'loggedin' not in session:
    return redirect(url_for('login'))
  filename = secure_filename(filename)
  return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route('/upload_chunk', methods=['POST'])
def upload_chunk():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    chunk = request.files['chunk']
    filename = secure_filename(request.form['filename'])
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    # If first chunk → clear file
    if not os.path.exists(filepath):
        open(filepath, "wb").close()

    with open(filepath, "ab") as f:
        f.write(chunk.read())

    return "Chunk received"

if __name__ == '__main__':
  serve(app, port=5001)