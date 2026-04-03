from flask import Flask, request, render_template, send_from_directory, url_for, redirect, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from waitress import serve
import os
import qrcode
import psycopg2
import re

app = Flask(__name__)

app.secret_key = os.getenv('SECRET_KEY', 'super-secret-key')

def get_db():
    return psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50  * 1024 * 1024  

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
  msg = ''
  if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
    username = request.form['username']
    password = request.form['password']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM accounts WHERE username = %s', (username, ))
    account = cursor.fetchone()
    cursor.close()
    conn.close()
    if account and check_password_hash(account[2], password):
      session['loggedin'] = True
      session['id'] = account[0]
      session['username'] = account[1]
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
    conn = get_db()
    cursor = conn.cursor()
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
      cursor = conn.cursor()
      cursor.execute('INSERT INTO accounts (username, password, email) VALUES (%s, %s, %s)',(username, hashed_password, email))
      conn.commit()
      msg = "You have successfully registered!"
    cursor.close()
    conn.close()

  return render_template('register.html', msg=msg)

@app.route('/index', methods=['GET', 'POST'])
def index():
  if 'loggedin' not in session:
        return redirect(url_for('login'))
  files = os.listdir(UPLOAD_FOLDER)
  url = request.host_url
  qr_path = os.path.join("static", "qr.png")
  qr = qrcode.make(url)
  qr.save(qr_path)
  return render_template('index.html', files=files, qr="qr.png", url=url)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'zip', 'txt'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
@app.route('/upload', methods=["POST"])
def upload():
   if 'loggedin' not in session:
    return redirect(url_for('login'))
   file = request.files.get('file')
   if not file or file.filename == '':
        return redirect(url_for('index'))
   if file and allowed_file(file.filename):
    filename = secure_filename(file.filename)
    file.save(os.path.join(UPLOAD_FOLDER, filename))
   else:
    return "Invalid file type"
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
  port = int(os.environ.get("PORT", 5001))
  serve(app, host="0.0.0.0", port=port)
