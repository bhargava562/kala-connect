"""Create a clearly labeled historical demo fixture, without weakening API date checks."""
from datetime import datetime,timezone,timedelta
from main import engine,Session,Base,User,put,seed,audit,now
Base.metadata.create_all(engine)
with Session(engine) as s:
    if not s.query(User).filter_by(id='artist1').first():
        raise SystemExit('Run the API with SEED_DEMO=true first. This helper is only for demo data.')
    past=datetime.now(timezone.utc)-timedelta(days=3)
    b=dict(id='demo-overdue-case',artist_id='troupe1',artist_owner_id='artist1',customer_id='customer1',start=past.isoformat(),end=(past+timedelta(hours=2)).isoformat(),venue='FICTIONAL DEMO: College auditorium',requirements='Historical fixture for overdue milestone walkthrough',budget=25000,status='completed',quote={'performer':18000,'transport':2000,'equipment':1000,'accommodation':0,'advance_percent':30,'cancellation':'Demo cancellation terms agreed by fictional parties.'},quote_revision=1,artist_approved=True,customer_approved=True,approved_conditions='Safe stage and changing room.',approved_artist_name='Kaveri Karakattam',milestones=[dict(label='Advance',amount=6300,due=past.isoformat(),paid=True,simulated=True),dict(label='Balance',amount=14700,due=(past+timedelta(hours=2)).isoformat(),paid=False,simulated=True)],history=[],case={'state':'completed_demo_fixture','suggestions':[]})
    put(s,'booking',b);audit(s,b,s.get(User,'artist1'),'historical_demo_fixture','Fictional approvals and completion; no real event or money');put(s,'booking',b);s.commit()
print('Created demo-overdue-case. Sign in as artist1 or customer1 to inspect it.')
