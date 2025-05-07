from datetime import datetime

from flask import Flask
from flask import redirect, session

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
    if 'user' not in session:
        return redirect('/')

    keyword = request.form['search']
    channel = request.form['channel']
    start_date = request.form['start_date']
    end_date = request.form['end_date']

    # Parse dates
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # 🔧 Mock posts and comments
    posts = [
        {
            'title': f'{channel} Post 1',
            'comments': [
                {'text': 'Amazing!', 'type': 'positive'},
                {'text': 'Could be better.', 'type': 'suggestion'}
            ],
            'date': '2025-01-15',
            'engagement': 78
        },
        {
            'title': f'{channel} Post 2',
            'comments': [
                {'text': 'Bad experience.', 'type': 'negative'},
                {'text': 'Great stuff!', 'type': 'positive'}
            ],
            'date': '2025-03-01',
            'engagement': 64
        }
    ]

    # Filter by date
    filtered = [p for p in posts if start <= datetime.strptime(p['date'], "%Y-%m-%d") <= end]

    return render_template('dashboard.html', user=session['user'], results=filtered, keyword=keyword, channel=channel, start=start_date, end=end_date)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

from flask import request, render_template, send_file
from xhtml2pdf import pisa
import io, json

@app.route('/report', methods=['POST'])
def report():
    data = json.loads(request.form['data'])
    chart_img = request.form.get('chart')  # base64 string

    # Render HTML with chart and results
    html = render_template("report_template.html", results=data, chart_img=chart_img)

    # Create PDF
    pdf = io.BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=pdf)
    pdf.seek(0)

    # Return as downloadable file
    return send_file(
        pdf,
        mimetype="application/pdf",
        download_name="report.pdf",
        as_attachment=True
    )


if __name__ == '__main__':
    app.run()