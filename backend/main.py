import os, json, secrets, hashlib, hmac, re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr, model_validator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlalchemy.types import String, Text, Integer
import pymupdf as fitz

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///./kala.db'), connect_args={'check_same_thread': False} if os.getenv('DATABASE_URL', 'sqlite:').startswith('sqlite') else {})
lock = RLock()
def now(): return datetime.now(timezone.utc).isoformat()
def fail(code, message): raise HTTPException(code, message)
class Base(DeclarativeBase): pass
class Record(Base):
    __tablename__='records'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    data: Mapped[str] = mapped_column(Text)
class User(Base):
    __tablename__='users'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    password: Mapped[str] = mapped_column(Text)
class Token(Base):
    __tablename__='sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    expires: Mapped[str] = mapped_column(String(40))
def db():
    with Session(engine) as s: yield s
def put(s, kind, value):
    value.setdefault('id', secrets.token_hex(12))
    row=s.get(Record,value['id'])
    if row: row.data=json.dumps(value,ensure_ascii=False)
    else: s.add(Record(id=value['id'],kind=kind,data=json.dumps(value,ensure_ascii=False)))
    s.flush(); return value
def get(s, kind, id):
    row=s.get(Record,id)
    if not row or row.kind!=kind: fail(404,'Record not found')
    return json.loads(row.data)
def allof(s, kind): return [json.loads(r.data) for r in s.query(Record).filter_by(kind=kind).all()]
def password(value, salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.scrypt(value.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def public(u): return dict(id=u.id,email=u.email,name=u.name,role=u.role)
def current(authorization: str=Header(default=''), s:Session=Depends(db)):
    token=authorization.removeprefix('Bearer ')
    row=s.get(Token,hashlib.sha256(token.encode()).hexdigest())
    if not row or row.expires<now(): fail(401,'Please sign in again')
    return s.get(User,row.user_id)
def roles(u,*rs):
    if u.role not in rs: fail(403,'Your role cannot perform this action')
def audit(s,b,u,event,detail=''):
    entry=dict(at=now(),actor=u.id,event=event,detail=detail)
    b.setdefault('history',[]).append(entry)
    put(s,'audit',dict(booking_id=b['id'],**entry))
    for uid in {b['customer_id'],b['artist_owner_id']}:
        put(s,'notification',dict(user_id=uid,booking_id=b['id'],message=event,at=now()))
def access(b,u):
    if u.id not in (b['customer_id'],b['artist_owner_id']) and u.role!='admin': fail(403,'This booking belongs to another user')
def locked(s,id):
    # Database row lock serializes all confirmations for one artist on PostgreSQL.
    s.query(Record).filter_by(id=id).with_for_update().first()
def conflicts(s,aid,start,end,exclude=''):
    return any(b['id']!=exclude and b['artist_id']==aid and b['status'] in ('confirmed','completed','disputed') and b['start']<end and b['end']>start for b in allof(s,'booking'))
def blocked(a,start,end):
    return any(start[:10]<=d<=end[:10] for d in a.get('unavailable',[]))
class Auth(BaseModel):
    email: EmailStr
    password: str=Field(min_length=10,max_length=128)
class Register(Auth):
    name: str=Field(min_length=2,max_length=120)
    role: str
    consent: bool
class Profile(BaseModel):
    name: str=Field(min_length=2,max_length=120)
    art_form: str=Field(min_length=2,max_length=80)
    location: str=Field(min_length=2,max_length=100)
    description: str=Field(min_length=10,max_length=3000)
    troupe_size: int=Field(ge=1,le=200)
    fee: int=Field(ge=0,le=10000000)
    experience: int=Field(default=0,ge=0,le=100)
    languages: list[str]=Field(default=['Tamil'],max_length=20)
    travel: str=Field(default='Tamil Nadu',max_length=200)
    conditions: str=Field(default='Safe stage and changing room required.',max_length=2000)
    photos: list[str]=Field(default=[],max_length=8)
    clips: list[str]=Field(default=[],max_length=4)
    consent: bool=False
    owner_email: EmailStr|None=None
    @model_validator(mode='after')
    def media(self):
        if any(not x.startswith('https://') for x in self.photos+self.clips): raise ValueError('Media links must use HTTPS')
        return self
class Request(BaseModel):
    artist_id: str
    start: datetime
    end: datetime
    venue: str=Field(min_length=3,max_length=300)
    requirements: str=Field(default='',max_length=3000)
    budget: int=Field(gt=0,le=10000000)
    @model_validator(mode='after')
    def dates(self):
        if self.start.tzinfo is None or self.end.tzinfo is None: raise ValueError('Use timezone-aware dates')
        if self.end<=self.start or self.end-self.start>timedelta(days=7): raise ValueError('Duration must be positive and at most seven days')
        if self.start<datetime.now(timezone.utc): raise ValueError('Choose a future date')
        return self
class Quote(BaseModel):
    performer: int=Field(ge=0,le=10000000)
    transport: int=Field(ge=0,le=10000000)
    equipment: int=Field(ge=0,le=10000000)
    accommodation: int=Field(ge=0,le=10000000)
    advance_percent: int=Field(default=30,ge=1,le=99)
    cancellation: str=Field(min_length=5,max_length=2000)
class Action(BaseModel):
    action: str
    note: str=Field(default='',max_length=2000)
class Extract(BaseModel):
    text: str=Field(min_length=1,max_length=3000)

def seed(s):
    if s.query(User).count(): return
    pw=os.getenv('DEMO_PASSWORD')
    if not pw: raise RuntimeError('Set DEMO_PASSWORD before enabling demo seeding')
    for id,name,role in [('artist1','Kaveri Karakattam','artist'),('artist2','Thendral Folk Arts','artist'),('artist3','Marabu Heritage','artist'),('customer1','Ananya College Events','customer'),('customer2','Arun Community Events','customer'),('operator','Assisted Desk','operator'),('admin','Review Team','admin')]:
        s.add(User(id=id,name=name,email=id+'@demo.example.com',role=role,password=password(pw)))
    for i,(name,art,loc,fee,desc) in enumerate([('Kaveri Karakattam','Karakattam','Thanjavur',18000,'A fictional eight-member troupe celebrating Tamil folk dance with traditional percussion.'),('Thendral Folk Arts','Karakattam','Chennai',16000,'A fictional Karakattam troupe offering energetic performances for college and community events.'),('Marabu Heritage','Heritage experience','Madurai',12000,'A fictional heritage host sharing storytelling, craft and local traditions through guided sessions.')],1):
        put(s,'artist',dict(id='troupe'+str(i),owner_id='artist'+str(i),name=name,art_form=art,location=loc,fee=fee,description=desc,troupe_size=8 if i<3 else 3,experience=6,languages=['Tamil','English'],travel='Tamil Nadu',conditions='Safe stage, drinking water and a changing room required.',photos=[],clips=[],consent=True,published=True,artist_approved=True,admin_reviewed=False,sample=True,unavailable=[]))
    s.commit()
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if os.getenv('SEED_DEMO','false').lower()=='true':
        with Session(engine) as s: seed(s)
    yield
app=FastAPI(title='KALA CONNECT',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173').split(','),allow_methods=['GET','POST','PUT'],allow_headers=['Authorization','Content-Type'])
@app.get('/api/health')
def health(): return {'status':'ok','payments':'simulated'}
@app.post('/api/register')
def register(data:Register,s:Session=Depends(db)):
    if data.role not in ('artist','customer'): fail(400,'Only artists and customers may self-register')
    if not data.consent: fail(400,'Consent is required')
    if s.query(User).filter_by(email=str(data.email).lower()).first(): fail(409,'Email already registered')
    u=User(id=secrets.token_hex(12),email=str(data.email).lower(),name=data.name,role=data.role,password=password(data.password));s.add(u);s.commit()
    return public(u)
@app.post('/api/login')
def login(data:Auth,s:Session=Depends(db)):
    u=s.query(User).filter_by(email=str(data.email).lower()).first()
    if not u or not hmac.compare_digest(u.password,password(data.password,u.password.split(':')[0])): fail(401,'Email or password is incorrect')
    raw=secrets.token_urlsafe(32);s.add(Token(id=hashlib.sha256(raw.encode()).hexdigest(),user_id=u.id,expires=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()));s.commit()
    return dict(token=raw,user=public(u))
@app.post('/api/logout')
def logout(authorization:str=Header(default=''),u=Depends(current),s:Session=Depends(db)):
    row=s.get(Token,hashlib.sha256(authorization.removeprefix('Bearer ').encode()).hexdigest())
    if row:s.delete(row);s.commit()
    return {'ok':True}
@app.get('/api/me')
def me(u=Depends(current)):return public(u)
@app.get('/api/artists')
def artists(art_form:str='',location:str='',max_fee:int=10000000,date:str='',s:Session=Depends(db)):
    result=[a for a in allof(s,'artist') if a['published'] and art_form.lower() in a['art_form'].lower() and location.lower() in a['location'].lower() and a['fee']<=max_fee]
    if date:
        try: start=datetime.fromisoformat(date).replace(tzinfo=timezone.utc).isoformat();end=(datetime.fromisoformat(date)+timedelta(days=1)).replace(tzinfo=timezone.utc).isoformat()
        except ValueError: fail(422,'Invalid date')
        result=[a for a in result if not conflicts(s,a['id'],start,end) and date not in a.get('unavailable',[])]
    return result
@app.get('/api/my-profiles')
def myprofiles(u=Depends(current),s:Session=Depends(db)):
    return [a for a in allof(s,'artist') if a['owner_id']==u.id or u.role in ('admin','operator')]
@app.post('/api/artists')
def create_profile(data:Profile,u=Depends(current),s:Session=Depends(db)):
    roles(u,'artist','operator')
    owner=u.id
    if u.role=='operator':
        other=s.query(User).filter_by(email=str(data.owner_email).lower(),role='artist').first()
        if not other: fail(400,'Enter an existing artist account email; artist must sign in to approve')
        owner=other.id
    a=data.model_dump(exclude={'owner_email'});a.update(owner_id=owner,published=False,artist_approved=False,admin_reviewed=False,sample=False,unavailable=[])
    put(s,'artist',a);s.commit();return a
@app.post('/api/artists/{id}/publish')
def publish(id:str,u=Depends(current),s:Session=Depends(db)):
    a=get(s,'artist',id)
    if a['owner_id']!=u.id or u.role!='artist': fail(403,'Only the artist may approve and publish')
    if not a['consent']: fail(400,'Consent to publish is required')
    a.update(published=True,artist_approved=True,approved_at=now());put(s,'artist',a);put(s,'audit',dict(artist_id=id,actor=u.id,event='artist_approved_publication',at=now()));s.commit();return a
@app.put('/api/artists/{id}')
def edit_profile(id:str,data:Profile,u=Depends(current),s:Session=Depends(db)):
    a=get(s,'artist',id)
    if a['owner_id']!=u.id or u.role!='artist':fail(403,'Only the owning artist may edit')
    a.update(data.model_dump(exclude={'owner_email'}));a.update(published=False,artist_approved=False);put(s,'artist',a);s.commit();return a
@app.post('/api/artists/{id}/availability')
def availability(id:str,dates:list[str],u=Depends(current),s:Session=Depends(db)):
    a=get(s,'artist',id)
    if a['owner_id']!=u.id:fail(403,'Only the owner may set availability')
    for d in dates:
        try: datetime.strptime(d,'%Y-%m-%d')
        except ValueError:fail(422,'Dates must be YYYY-MM-DD')
    a['unavailable']=sorted(set(dates));put(s,'artist',a);s.commit();return a
@app.post('/api/voice/extract')
def extract(data:Extract,u=Depends(current)):
    t=data.text
    result={}
    for word,english in [('கரகாட்டம்','Karakattam'),('Karakattam','Karakattam'),('பறையாட்டம்','Paraiattam')]:
        if word.lower() in t.lower():result['art_form']=english
    for word,english in [('தஞ்சாவூர்','Thanjavur'),('சென்னை','Chennai'),('மதுரை','Madurai'),('Thanjavur','Thanjavur')]:
        if word.lower() in t.lower():result['location']=english
    nums=re.findall(r'\d+',t)
    if nums: result['troupe_size']=min(int(nums[0]),200)
    if len(nums)>1:result['fee']=int(nums[1])
    if 'தமிழ்நாடு' in t:result['travel']='Tamil Nadu'
    return {'fields':result,'requires_confirmation':True,'method':'deterministic parser; review every field','transcript':t}
@app.post('/api/bookings')
def request_booking(data:Request,u=Depends(current),s:Session=Depends(db)):
    roles(u,'customer');a=get(s,'artist',data.artist_id)
    if not a['published']:fail(400,'Artist is not published')
    start=data.start.astimezone(timezone.utc).isoformat();end=data.end.astimezone(timezone.utc).isoformat()
    if conflicts(s,a['id'],start,end) or blocked(a,start,end):fail(409,'Artist is unavailable')
    b=dict(artist_id=a['id'],artist_owner_id=a['owner_id'],customer_id=u.id,start=start,end=end,venue=data.venue,requirements=data.requirements,budget=data.budget,status='requested',quote=None,quote_revision=0,artist_approved=False,customer_approved=False,milestones=[],history=[],case={'state':'awaiting_artist','suggestions':[]})
    put(s,'booking',b);audit(s,b,u,'requested');put(s,'booking',b);s.commit();return b
@app.get('/api/bookings')
def bookings(u=Depends(current),s:Session=Depends(db)):
    return [b for b in allof(s,'booking') if u.role=='admin' or u.id in (b['customer_id'],b['artist_owner_id'])]
@app.get('/api/notifications')
def notifications(u=Depends(current),s:Session=Depends(db)):return [n for n in allof(s,'notification') if n['user_id']==u.id]
@app.post('/api/bookings/{id}/quote')
def quote(id:str,data:Quote,u=Depends(current),s:Session=Depends(db)):
    with lock:
        locked(s,id);b=get(s,'booking',id)
        if u.id!=b['artist_owner_id'] or u.role!='artist':fail(403,'Only the artist can approve fees')
        if b['status'] not in ('requested','artist reviewing','counteroffer','customer reviewing'):fail(409,'Quotation is closed')
        a=get(s,'artist',b['artist_id'])
        b['approved_conditions']=a['conditions'];b['approved_artist_name']=a['name']
        b['quote']=data.model_dump();b['quote_revision']+=1;b.update(artist_approved=True,customer_approved=False,status='customer reviewing',case={'state':'awaiting_customer_approval','suggestions':[]})
        audit(s,b,u,'artist_approved_quote',str(b['quote_revision']));put(s,'booking',b);s.commit();return b
@app.post('/api/bookings/{id}/action')
def action(id:str,data:Action,u=Depends(current),s:Session=Depends(db)):
    with lock:
        locked(s,id);b=get(s,'booking',id);access(b,u)
        artist=u.id==b['artist_owner_id'] and u.role=='artist';customer=u.id==b['customer_id'] and u.role=='customer'
        a=get(s,'artist',b['artist_id']);act=data.action
        if act=='review':
            if not artist or b['status']!='requested':fail(409,'Only artist may review a new request')
            b['status']='artist reviewing'
        elif act=='counteroffer':
            if not customer or b['status']!='customer reviewing':fail(409,'Only customer may request a quote revision')
            b.update(status='counteroffer',artist_approved=False,customer_approved=False)
        elif act=='confirm':
            if not customer:fail(403,'Only the customer may accept an artist-approved quote')
            if b['status']!='customer reviewing' or not b['artist_approved'] or not b['quote']:fail(409,'Artist approval is required')
            locked(s,b['artist_id'])
            if conflicts(s,b['artist_id'],b['start'],b['end'],id) or blocked(a,b['start'],b['end']):fail(409,'These dates are no longer available')
            b.update(status='confirmed',customer_approved=True,case={'state':'confirmed_by_humans','suggestions':[]})
            q=b['quote'];total=sum(q[k] for k in ('performer','transport','equipment','accommodation'));advance=round(total*q['advance_percent']/100)
            b['milestones']=[dict(label='Advance',amount=advance,due=now(),paid=False,simulated=True),dict(label='Balance',amount=total-advance,due=b['end'],paid=False,simulated=True)]
        elif act in ('decline','cancel'):
            if not (artist or customer) or b['status'] in ('completed','cancelled','disputed'):fail(409,'Cannot cancel this booking')
            b['status']='cancelled'
            b['case']={'state':'alternatives_ready','suggestions':[x['id'] for x in allof(s,'artist') if x['id']!=a['id'] and x['published'] and x['art_form']==a['art_form'] and x['fee']<=b['budget'] and not conflicts(s,x['id'],b['start'],b['end']) and not blocked(x,b['start'],b['end'])]}
        elif act=='complete':
            if not artist or b['status']!='confirmed':fail(409,'Only artist may complete a confirmed event')
            if b['end']>now():fail(409,'Event must have ended before completion')
            b['status']='completed'
        elif act=='dispute':
            if not (artist or customer) or b['status'] not in ('confirmed','completed') or len(data.note)<5:fail(409,'Add a reason for a confirmed or completed booking')
            b['status']='disputed';b['case']['state']='admin_review_required'
        else:fail(400,'Unknown action')
        audit(s,b,u,act,data.note);put(s,'booking',b);s.commit();return b
@app.post('/api/bookings/{id}/payments/{index}')
def payment(id:str,index:int,u=Depends(current),s:Session=Depends(db)):
    with lock:
        locked(s,id);b=get(s,'booking',id)
        if u.id!=b['customer_id'] or u.role!='customer':fail(403,'Only the customer can simulate a payment')
        if b['status'] not in ('confirmed','completed') or index not in (0,1) or len(b['milestones'])!=2:fail(409,'No payable milestone')
        if b['milestones'][index]['paid']:fail(409,'Already simulated')
        b['milestones'][index].update(paid=True,paid_at=now());audit(s,b,u,'simulated_payment',str(index));put(s,'booking',b);s.commit();return b
@app.post('/api/bookings/{id}/reminder')
def reminder(id:str,data:Action,u=Depends(current),s:Session=Depends(db)):
    b=get(s,'booking',id);access(b,u)
    if u.id!=b['artist_owner_id']:fail(403,'Artist approval is required')
    overdue=[m for m in b['milestones'] if not m['paid'] and m['due']<now()]
    if not overdue:fail(409,'No overdue milestone')
    if data.action!='approve':fail(400,'Explicit approval required')
    audit(s,b,u,'approved_in_app_reminder',f"Simulated amount due: INR {sum(m['amount'] for m in overdue)}");put(s,'booking',b);s.commit();return b
@app.get('/api/bookings/{id}/agreement')
def agreement(id:str,u=Depends(current),s:Session=Depends(db)):
    b=get(s,'booking',id);access(b,u)
    if not b['artist_approved'] or not b['customer_approved'] or b['status'] not in ('confirmed','completed','disputed'):fail(409,'Both parties must approve first')
    a=get(s,'artist',b['artist_id']);q=b['quote'];total=sum(q[k] for k in ('performer','transport','equipment','accommodation'))
    doc=fitz.open();page=doc.new_page()
    font=os.getenv('TAMIL_FONT_PATH','')
    if not font or not Path(font).exists():fail(503,'Set TAMIL_FONT_PATH to a Tamil-capable font before generating bilingual PDFs')
    body=f"""KALA CONNECT • Booking agreement / நிகழ்ச்சி ஒப்பந்தம்
Booking / முன்பதிவு: {b['id']}
Artist / கலைஞர்: {b.get('approved_artist_name',a['name'])}
Start / தொடக்கம் (UTC): {b['start']}
End / முடிவு (UTC): {b['end']}
Venue / இடம்: {b['venue']}
Requirements / தேவைகள்: {b['requirements']}
Performer / கலைஞர் கட்டணம்: INR {q['performer']}
Transport / போக்குவரத்து: INR {q['transport']}
Equipment / உபகரணங்கள்: INR {q['equipment']}
Accommodation / தங்குமிடம்: INR {q['accommodation']}
Total / மொத்தம்: INR {total}
Advance / முன்பணம்: {q['advance_percent']}%; Balance / மீதி: {100-q['advance_percent']}%
Conditions / நிபந்தனைகள்: {b.get('approved_conditions',a['conditions'])}
Cancellation / ரத்து விதிகள்: {q['cancellation']}
Quote revision / கட்டண பதிப்பு: {b['quote_revision']}
Both parties approved / இரு தரப்பினரும் ஒப்புதல் அளித்தனர்.
All payments are SIMULATED. No escrow or real transfer.
அனைத்து பணப்பரிவர்த்தனைகளும் மாதிரி மட்டுமே.
Demo agreement; not an electronic signature service."""
    import html
    css="@font-face {font-family:tamil;src:url('"+Path(font).name+"')} body{font-family:tamil;font-size:12px;line-height:1.65;color:#132B39}"
    story=fitz.Story(html='<body>'+html.escape(body).replace('\n','<br>')+'</body>',user_css=css,archive=fitz.Archive(str(Path(font).parent)))
    # Paginate long requirements and cancellation terms rather than truncating.
    import io
    output=io.BytesIO();writer=fitz.DocumentWriter(output)
    more=True
    while more:
        device=writer.begin_page(fitz.Rect(0,0,595,842));more,_=story.place(fitz.Rect(40,40,555,802));story.draw(device);writer.end_page()
    writer.close()
    return Response(output.getvalue(),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="kala-agreement-{id}.pdf"'})
@app.get('/api/admin')
def admin(u=Depends(current),s:Session=Depends(db)):
    roles(u,'admin');return dict(profiles=allof(s,'artist'),bookings=allof(s,'booking'),audit=allof(s,'audit'),reports=allof(s,'report'))
@app.post('/api/reports')
def report(data:Action,u=Depends(current),s:Session=Depends(db)):
    if len(data.note)<5:fail(422,'Please describe the concern')
    r=put(s,'report',dict(actor=u.id,note=data.note,status='open',at=now()));s.commit();return r
@app.post('/api/admin/profiles/{id}/review')
def review_profile(id:str,u=Depends(current),s:Session=Depends(db)):
    roles(u,'admin');a=get(s,'artist',id);a['admin_reviewed']=True;put(s,'artist',a);put(s,'audit',dict(artist_id=id,actor=u.id,event='admin_reviewed_not_identity_verified',at=now()));s.commit();return a
@app.post('/api/admin/reports/{id}/resolve')
def resolve(id:str,data:Action,u=Depends(current),s:Session=Depends(db)):
    roles(u,'admin');r=get(s,'report',id);r.update(status='resolved',resolution=data.note);put(s,'report',r);put(s,'audit',dict(actor=u.id,event='report_resolved',report_id=id,at=now()));s.commit();return r

@app.post('/api/bookings/{id}/plan')
def plan(id:str,u=Depends(current),s:Session=Depends(db)):
    """Offline coordinator: propose, persist, then wait. Never changes an approval."""
    with lock:
        locked(s,id);b=get(s,'booking',id);access(b,u)
        a=get(s,'artist',b['artist_id'])
        eligible=[x for x in allof(s,'artist') if x['published'] and x['art_form']==a['art_form'] and x['fee']<=b['budget'] and not conflicts(s,x['id'],b['start'],b['end'],id) and not blocked(x,b['start'],b['end'])]
        b['case']['plan']={'generated_at':now(),'eligible_artists':[x['id'] for x in eligible],'proposed_quote':{'performer':a['fee'],'transport':0,'equipment':0,'accommodation':0,'advance_percent':30},'constraints':{'artist_available':not conflicts(s,a['id'],b['start'],b['end'],id) and not blocked(a,b['start'],b['end']),'starting_fee_within_budget':a['fee']<=b['budget']},'next_step':'Artist must independently edit and approve each amount. Zero logistics costs are placeholders, not estimates.','approved':False}
        audit(s,b,u,'workflow_proposed_no_commit');put(s,'booking',b);s.commit();return b

@app.get('/api/artists/{id}/calendar')
def calendar(id:str,s:Session=Depends(db)):
    a=get(s,'artist',id)
    if not a['published']:fail(404,'Profile not published')
    return {'unavailable':a.get('unavailable',[]),'reserved':[{'start':b['start'],'end':b['end']} for b in allof(s,'booking') if b['artist_id']==id and b['status'] in ('confirmed','completed','disputed')]}
