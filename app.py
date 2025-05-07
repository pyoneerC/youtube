from flask import Flask, render_template, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # For session

# Hardcoded credentials
VALID_USER = 'eliberto'
VALID_PASS = 'demo123'

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    user = request.form['user']
    password = request.form['password']

    if user == VALID_USER and password == VALID_PASS:
        session['user'] = user
        return redirect('/dashboard')
    else:
        return render_template('login.html', error="Invalid credentials")

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    return render_template('dashboard.html', user=session['user'])

@app.route('/analyze', methods=['POST'])
def analyze():
    keyword = request.form['search']
    channel = request.form['channel']
    # Do something with keyword and channel...
    return render_template('dashboard.html', user=session['user'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
