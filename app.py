import os, sqlite3, hmac, secrets, io, base64, qrcode
from flask import Flask, request, jsonify, render_template_string, session, abort
app=Flask(__name__)
app.secret_key=os.environ['SECRET_KEY']
ADMIN=os.environ['ADMIN_PASSWORD']
DB=os.environ.get('DB_PATH','tickets.db')
COUNTS=[16,22,24,24,20,16,18,17,8,10,15,20]
SEATS={f'{r}-{i}':1500 if r<=2 else 800 if r<=5 else 500 for r,n in enumerate(COUNTS,1) for i in range(1,n+1)}
def db():
 c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row;return c
with db() as c:c.execute('CREATE TABLE IF NOT EXISTS bookings(seat TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,paid INTEGER DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP)')
with db() as c:
 cols={r['name'] for r in c.execute('PRAGMA table_info(bookings)')}
 if 'token' not in cols:c.execute('ALTER TABLE bookings ADD COLUMN token TEXT')
 if 'used' not in cols:c.execute('ALTER TABLE bookings ADD COLUMN used INTEGER DEFAULT 0')
 c.execute('CREATE UNIQUE INDEX IF NOT EXISTS ticket_token ON bookings(token)')
 for r in c.execute('SELECT seat FROM bookings WHERE paid=1 AND token IS NULL').fetchall():c.execute('UPDATE bookings SET token=? WHERE seat=?',(secrets.token_urlsafe(24),r['seat']))
@app.get('/')
def home():return render_template_string(open(os.path.join(os.path.dirname(__file__),'index.html')).read())
@app.get('/api/seats')
def seats():
 with db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM bookings')]
 return jsonify(admin=bool(session.get('admin')),bookings=rows if session.get('admin') else [{'seat':r['seat']} for r in rows])
@app.post('/api/login')
def login():
 if hmac.compare_digest(str(request.json.get('password','')),ADMIN):session['admin']=True;return jsonify(ok=True)
 return jsonify(error='Құпиясөз қате'),403
@app.post('/api/logout')
def logout():session.clear();return jsonify(ok=True)
@app.post('/api/book')
def book():
 d=request.json; ss=d.get('seats',[]);name=str(d.get('name','')).strip();phone=str(d.get('phone','')).strip()
 if not isinstance(ss,list) or not ss or any(not isinstance(s,str) or s not in SEATS for s in ss) or len(set(ss))!=len(ss) or not name or len(name)>100 or not phone or len(phone)>40:return jsonify(error='Мәліметтерді тексеріңіз'),400
 try:
  with db() as c:
   c.execute('BEGIN IMMEDIATE');c.executemany('INSERT INTO bookings(seat,name,phone) VALUES(?,?,?)',[(s,name,phone) for s in ss])
 except sqlite3.IntegrityError:return jsonify(error='Орындардың бірі броньдалған. Қайта таңдаңыз.'),409
 return jsonify(ok=True)
@app.post('/api/manage')
def manage():
 if not session.get('admin'):return jsonify(error='Рұқсат жоқ'),403
 d=request.json
 with db() as c:
  if d.get('action')=='cancel':c.execute('DELETE FROM bookings WHERE seat=?',(d.get('seat'),))
  elif d.get('action')=='paid':c.execute('UPDATE bookings SET paid=1, token=COALESCE(token,?) WHERE seat=?',(secrets.token_urlsafe(24),d.get('seat')))
  else:return jsonify(error='Қате әрекет'),400
 return jsonify(ok=True)
@app.get('/ticket/<token>')
def ticket(token):
 with db() as c:r=c.execute('SELECT seat,used FROM bookings WHERE token=? AND paid=1',(token,)).fetchone()
 if not r:abort(404)
 url=request.host_url.rstrip('/')+'/check/'+token
 buf=io.BytesIO();qrcode.make(url).save(buf,format='PNG')
 return render_template_string(TICKET, row=r['seat'].split('-')[0], seat=r['seat'].split('-')[1], price=SEATS[r['seat']], token=token, qr=base64.b64encode(buf.getvalue()).decode(), used=r['used'])
@app.get('/ticket/<token>/image.png')
def ticket_image(token):
 from PIL import Image, ImageDraw, ImageFont
 from flask import send_file
 with db() as c:r=c.execute('SELECT seat FROM bookings WHERE token=? AND paid=1',(token,)).fetchone()
 if not r:abort(404)
 im=Image.new('RGB',(1200,650),'#101827');d=ImageDraw.Draw(im)
 def text(x,y,t,size,color='white',bold=False):
  f=ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf',size)
  d.text((x,y),t,font=f,fill=color)
 d.rounded_rectangle((25,25,1175,625),radius=35,outline='#C5A66D',width=3)
 d.line((780,55,780,595),fill='#C5A66D',width=2)
 text(65,65,'ELECTRONIC TICKET',28,'#C5A66D')
 text(65,135,'КОНЦЕРТ 2026',62,bold=True)
 row,seat=r['seat'].split('-')
 text(65,260,f'{row}-қатар  /  {seat}-орын',48,bold=True)
 text(65,345,f"{SEATS[r['seat']]} KZT",40)
 text(65,450,'Төлем расталған',32,'#C5A66D')
 text(65,525,'Бір адамға арналған билет',25)
 qr=qrcode.QRCode(box_size=7,border=4);qr.add_data(request.host_url.rstrip('/')+'/check/'+token);qr.make(fit=True)
 pic=qr.make_image(fill_color='black',back_color='white').convert('RGB');im.paste(pic,(780+(395-pic.width)//2, (650-pic.height)//2))
 buf=io.BytesIO();im.save(buf,format='PNG');buf.seek(0)
 return send_file(buf,mimetype='image/png',download_name=f'ticket-{row}-{seat}.png',as_attachment=request.args.get('download')=='1',max_age=0)
@app.get('/check/<token>')
def check(token):
 if not session.get('admin'):return '<meta charset="utf-8"><p>Тексеру үшін админ ретінде кіріңіз.</p><a href="/?admin">Админ панелі</a>',403
 with db() as c:r=c.execute('SELECT seat,used FROM bookings WHERE token=? AND paid=1',(token,)).fetchone()
 return render_template_string(CHECK, r=r, token=token)
@app.post('/api/check')
def redeem():
 if not session.get('admin'):return jsonify(error='Рұқсат жоқ'),403
 with db() as c:
  c.execute('BEGIN IMMEDIATE')
  r=c.execute('SELECT used FROM bookings WHERE token=? AND paid=1',(request.json.get('token'),)).fetchone()
  if not r:return jsonify(error='Билет жарамсыз'),404
  if r['used']:return jsonify(error='Бұрын қолданылған'),409
  c.execute('UPDATE bookings SET used=1 WHERE token=?',(request.json.get('token'),))
 return jsonify(ok=True)
TICKET='''<!doctype html><html lang="kk"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{background:#111827;color:white;font:18px system-ui;padding:20px}main{max-width:480px;margin:auto;border:1px solid #64748b;border-radius:24px;padding:25px}img{width:220px;display:block;margin:20px auto}small{overflow-wrap:anywhere}button{padding:12px}@media print{button{display:none}}</style><main><small>ELECTRONIC TICKET</small><h1>КОНЦЕРТ 2026</h1><hr><h2>{{row}}-қатар · {{seat}}-орын</h2><h2>{{price}} ₸</h2><p>{{'Бұрын қолданылған' if used else '✓ Төлем расталған'}}</p><img src="data:image/png;base64,{{qr}}" alt="QR"><small>{{token}}</small><p>Бір адамға арналған</p><a style="color:white" href="/ticket/{{token}}/image.png?download=1">PNG суретті сақтау</a></main></html>'''
CHECK='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body style="font:22px system-ui;padding:24px"><h1 id="status">{% if not r %}Билет жарамсыз{% elif r.used %}Бұрын қолданылған{% else %}Билет жарамды{% endif %}</h1>{% if r %}<p>{{r.seat}}</p>{% endif %}{% if r and not r.used %}<button style="font:inherit;padding:15px" onclick="redeem(this)">Кіруді растау</button>{% endif %}<script>async function redeem(b){b.disabled=true;try{let r=await fetch('/api/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:{{token|tojson}}})});let j=await r.json();document.getElementById('status').textContent=j.ok?'Кіру расталды':j.error}catch(e){b.disabled=false}}</script></body>'''
@app.before_request
def protect():
 if request.method=='POST' and not request.is_json:return jsonify(error='JSON required'),415
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',8000)))
