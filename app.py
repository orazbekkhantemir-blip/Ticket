import os, sqlite3, hmac
from flask import Flask, request, jsonify, render_template_string, session
app=Flask(__name__)
app.secret_key=os.environ['SECRET_KEY']
ADMIN=os.environ['ADMIN_PASSWORD']
DB=os.environ.get('DB_PATH','tickets.db')
COUNTS=[16,22,24,24,20,16,18,17,8,10,15,20]
SEATS={f'{r}-{i}':1500 if r<=2 else 800 if r<=5 else 500 for r,n in enumerate(COUNTS,1) for i in range(1,n+1)}
def db():
 c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row;return c
with db() as c:c.execute('CREATE TABLE IF NOT EXISTS bookings(seat TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,paid INTEGER DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP)')
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
  elif d.get('action')=='paid':c.execute('UPDATE bookings SET paid=1 WHERE seat=?',(d.get('seat'),))
  else:return jsonify(error='Қате әрекет'),400
 return jsonify(ok=True)
@app.before_request
def protect():
 if request.method=='POST' and not request.is_json:return jsonify(error='JSON required'),415
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.environ.get('PORT',8000)))
