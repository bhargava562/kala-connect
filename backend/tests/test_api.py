import os, tempfile, unittest
from datetime import datetime, timedelta, timezone
os.environ['DATABASE_URL']='sqlite:///'+tempfile.mktemp(suffix='.db').replace('\\','/')
os.environ['SEED_DEMO']='true'
os.environ['DEMO_PASSWORD']='AutomatedTestPassword123!'
os.environ.setdefault('TAMIL_FONT_PATH','C:/Windows/Fonts/Nirmala.ttc' if os.name=='nt' else '/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf')
from fastapi.testclient import TestClient
from main import app,engine,Base,Session,seed,get,put

class BookingTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
        with Session(engine) as s:seed(s)
        self.client=TestClient(app)
        self.headers={}
        for name in ['artist1','artist2','customer1','customer2','operator','admin']:
            r=self.client.post('/api/login',json={'email':name+'@demo.example.com','password':os.environ['DEMO_PASSWORD']})
            self.assertEqual(r.status_code,200,r.text)
            self.headers[name]={'Authorization':'Bearer '+r.json()['token']}
    def req(self,artist='troupe1',customer='customer1'):
        start=datetime.now(timezone.utc)+timedelta(days=20)
        return self.client.post('/api/bookings',headers=self.headers[customer],json=dict(artist_id=artist,start=start.isoformat(),end=(start+timedelta(hours=2)).isoformat(),venue='College auditorium, Chennai',requirements='Tamil cultural evening',budget=30000))
    def quote(self,id,who='artist1'):
        return self.client.post('/api/bookings/'+id+'/quote',headers=self.headers[who],json=dict(performer=18000,transport=2000,equipment=1000,accommodation=0,advance_percent=30,cancellation='Mutually agreed seven-day cancellation notice.'))
    def act(self,id,action,who='customer1',note=''):
        return self.client.post('/api/bookings/'+id+'/action',headers=self.headers[who],json=dict(action=action,note=note))
    def test_authentication_and_privileged_registration(self):
        self.assertEqual(self.client.get('/api/bookings').status_code,401)
        for role in ['operator','admin']:
            r=self.client.post('/api/register',json=dict(email='new@example.com',password='longPassword123',name='New Person',role=role,consent=True));self.assertEqual(r.status_code,400)
        self.assertEqual(self.client.get('/api/admin',headers=self.headers['customer1']).status_code,403)
    def test_complete_approval_payment_journey(self):
        b=self.req().json();id=b['id']
        self.assertEqual(self.act(id,'confirm').status_code,409)
        self.assertEqual(self.quote(id,'artist2').status_code,403)
        self.assertEqual(self.quote(id).status_code,200)
        r=self.act(id,'confirm');self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['milestones'][0]['amount'],6300)
        self.assertTrue(r.json()['artist_approved']);self.assertTrue(r.json()['customer_approved'])
        r=self.client.post(f'/api/bookings/{id}/payments/0',headers=self.headers['customer1']);self.assertEqual(r.status_code,200);self.assertTrue(r.json()['milestones'][0]['simulated'])
        self.assertEqual(self.client.post(f'/api/bookings/{id}/payments/0',headers=self.headers['customer1']).status_code,409)
        self.assertEqual(self.act(id,'complete','artist1').status_code,409)
        pdf=self.client.get(f'/api/bookings/{id}/agreement',headers=self.headers['customer1'])
        if os.path.exists(os.environ['TAMIL_FONT_PATH']):
            self.assertEqual(pdf.status_code,200,pdf.text[:100] if pdf.status_code!=200 else '');self.assertTrue(pdf.content.startswith(b'%PDF'))
        else:self.assertEqual(pdf.status_code,503,'Missing Tamil font must produce an explicit error')
    def test_conflicting_confirmation(self):
        b1=self.req().json();b2=self.req(customer='customer2').json()
        self.quote(b1['id']);self.quote(b2['id'])
        self.assertEqual(self.act(b1['id'],'confirm').status_code,200)
        self.assertEqual(self.act(b2['id'],'confirm','customer2').status_code,409)
        self.assertEqual(self.req().status_code,409)
    def test_decline_recovery_does_not_reserve(self):
        b=self.req().json();r=self.act(b['id'],'decline','artist1');self.assertEqual(r.status_code,200)
        self.assertIn('troupe2',r.json()['case']['suggestions'])
        with Session(engine) as s:
            self.assertEqual(len([x for x in s.query(__import__('main').Record).filter_by(kind='booking')]),1)
    def test_owner_isolation(self):
        b=self.req().json()
        self.assertEqual(self.act(b['id'],'cancel','customer2').status_code,403)
        self.assertEqual(self.act(b['id'],'confirm','artist1').status_code,403)
        self.assertEqual(self.client.post('/api/artists/troupe1/availability',json=[],headers=self.headers['artist2']).status_code,403)
        self.assertEqual(self.client.get('/api/bookings/'+b['id']+'/agreement',headers=self.headers['customer2']).status_code,403)
    def test_operator_cannot_publish_or_quote(self):
        payload=dict(name='Assisted Troupe',art_form='Karakattam',location='Chennai',description='An artist-approved draft will follow.',troupe_size=5,fee=10000,owner_email='artist1@demo.example.com',consent=True)
        r=self.client.post('/api/artists',json=payload,headers=self.headers['operator']);self.assertEqual(r.status_code,200,r.text);id=r.json()['id']
        self.assertFalse(r.json()['published'])
        self.assertEqual(self.client.post('/api/artists/'+id+'/publish',headers=self.headers['operator']).status_code,403)
        self.assertEqual(self.client.post('/api/artists/'+id+'/publish',headers=self.headers['artist1']).status_code,200)
        b=self.req().json();self.assertEqual(self.quote(b['id'],'operator').status_code,403)
    def test_counteroffer_invalidates_previous_approval(self):
        b=self.req().json();self.quote(b['id']);r=self.act(b['id'],'counteroffer');self.assertFalse(r.json()['artist_approved']);self.assertEqual(self.act(b['id'],'confirm').status_code,409)
        self.quote(b['id']);self.assertEqual(self.act(b['id'],'confirm').status_code,200)
    def test_overdue_reminder_and_dispute(self):
        b=self.req().json();id=b['id'];self.quote(id);self.act(id,'confirm')
        # Fixture represents time passing after the event; public API disallows past requests.
        with Session(engine) as s:
            b=get(s,'booking',id);past=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat();b['end']=past;b['milestones'][1]['due']=past;put(s,'booking',b);s.commit()
        self.assertEqual(self.act(id,'complete','artist1').status_code,200)
        r=self.client.post(f'/api/bookings/{id}/reminder',headers=self.headers['artist1'],json={'action':'approve'});self.assertEqual(r.status_code,200)
        self.assertFalse(r.json()['milestones'][1]['paid'])
        self.assertEqual(self.act(id,'dispute','artist1','Final simulated payment overdue').status_code,200)
    def test_blocked_date_and_invalid_duration(self):
        date=(datetime.now(timezone.utc)+timedelta(days=20)).strftime('%Y-%m-%d')
        self.client.post('/api/artists/troupe1/availability',headers=self.headers['artist1'],json=[date]);self.assertEqual(self.req().status_code,409)
    def test_simulation_requires_confirmed_and_customer(self):
        id=self.req().json()['id']
        self.assertEqual(self.client.post(f'/api/bookings/{id}/payments/0',headers=self.headers['customer1']).status_code,409)
        self.assertEqual(self.client.post(f'/api/bookings/{id}/payments/0',headers=self.headers['artist1']).status_code,403)
    def test_real_registration_and_consent(self):
        payload=dict(email='organizer@example.org',password='LongerPassword123',name='Organizer',role='customer',consent=False)
        self.assertEqual(self.client.post('/api/register',json=payload).status_code,400)
        payload['consent']=True;self.assertEqual(self.client.post('/api/register',json=payload).status_code,200)
    def test_voice_is_only_a_draft(self):
        r=self.client.post('/api/voice/extract',headers=self.headers['artist1'],json={'text':'தஞ்சாவூர் கரகாட்டம் 8 18000 தமிழ்நாடு'})
        self.assertEqual(r.status_code,200);self.assertTrue(r.json()['requires_confirmation']);self.assertEqual(r.json()['fields']['fee'],18000)
    def test_workflow_plan_is_persisted_without_approval(self):
        b=self.req().json();r=self.client.post('/api/bookings/'+b['id']+'/plan',headers=self.headers['customer1'])
        self.assertEqual(r.status_code,200);self.assertFalse(r.json()['case']['plan']['approved'])
        self.assertFalse(r.json()['artist_approved']);self.assertEqual(r.json()['status'],'requested')
        self.assertIn('troupe2',r.json()['case']['plan']['eligible_artists'])
        current=self.client.get('/api/bookings',headers=self.headers['customer1']).json()[0]
        self.assertIn('plan',current['case'])
    def test_second_day_blocked_prevents_multiday_request(self):
        start=datetime.now(timezone.utc)+timedelta(days=30)
        self.client.post('/api/artists/troupe1/availability',headers=self.headers['artist1'],json=[(start+timedelta(days=1)).strftime('%Y-%m-%d')])
        r=self.client.post('/api/bookings',headers=self.headers['customer1'],json=dict(artist_id='troupe1',start=start.isoformat(),end=(start+timedelta(days=2)).isoformat(),venue='College auditorium',budget=30000))
        self.assertEqual(r.status_code,409)

if __name__=='__main__':unittest.main()
