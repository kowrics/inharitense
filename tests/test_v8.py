"""Corrected operational roles and read-only forecast demonstration."""
import pytest
from tests.test_v7 import role_client
from tests.conftest import get_csrf_token
from tests.test_refinements import create_item

@pytest.mark.parametrize('role',['Super User','Encoder','Report Generator','Employee'])
def test_demo_forecast_same_model_without_writes(app,app_module,hr_client,role):
 iid=create_item(hr_client,category='Office Supplies',qty=50)
 c=app_module.db();before=dict(c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone());moves=c.execute('SELECT COUNT(*) n FROM movements').fetchone()['n'];prs=c.execute('SELECT COUNT(*) n FROM purchase_requisitions').fetchone()['n'];c.close()
 client=role_client(app,role);response=client.get(f'/api/forecast-demo/{iid}')
 if role=='Employee':assert response.status_code==403;return
 assert response.status_code==200
 data=response.json;assert data['is_demo'] and data['item']['qty']==9 and 'Sample data' in data['data_source']
 f=data['forecast'];assert f['model']=='Linear Regression' and f['data_status']=='Sufficient data' and f['predicted_weekly']>0 and len(f['history_weeks'])==26
 assert f==app_module._forecast_from_weekly(data['item'],f['history_weeks'],5,3)
 c=app_module.db();assert dict(c.execute('SELECT * FROM inventory WHERE id=?',(iid,)).fetchone())==before
 assert c.execute('SELECT COUNT(*) n FROM movements').fetchone()['n']==moves and c.execute('SELECT COUNT(*) n FROM purchase_requisitions').fetchone()['n']==prs;c.close()
 real=client.get(f'/api/forecast/{iid}').json;assert not real.get('is_demo',False) and real['item']['qty']==50 and real['forecast']['data_status']=='Insufficient historical usage'

@pytest.mark.parametrize('params',['lead=-1','lead=nan','safety=inf','lead=invalid'])
def test_demo_validates_parameters(hr_client,params):
 assert hr_client.get('/api/forecast-demo/1?'+params).status_code==400

def test_encoder_can_assign_and_prepare_requisition_without_admin_rights(app,app_module,hr_client):
 encoder=role_client(app,'Encoder');iid=create_item(hr_client,qty=10);c=app_module.db();employee=c.execute("SELECT id FROM users WHERE role='Employee'").fetchone()['id'];c.close()
 assert encoder.post('/assignments/create',data=dict(inventory_id=iid,employee_id=employee,quantity=2,_csrf=get_csrf_token(encoder))).status_code==302
 assert app_module.get_item(iid)['qty']==8
 assert encoder.post('/requisitions/create',data=dict(inventory_id=iid,description='Replenish stock',quantity=5,_csrf=get_csrf_token(encoder))).status_code==302
 c=app_module.db();pr=c.execute('SELECT * FROM purchase_requisitions WHERE inventory_id=? ORDER BY id DESC',(iid,)).fetchone();assignment=c.execute('SELECT id FROM assignments WHERE inventory_id=?',(iid,)).fetchone();c.close()
 assert encoder.get(f'/requisitions/{pr["id"]}/print').status_code==200
 assert encoder.post(f'/assignments/{assignment["id"]}/ack',data=dict(signature_name='Encoder',_csrf=get_csrf_token(encoder))).status_code==403
 page=encoder.get('/').text
 for path in ['/assignments','/requisitions','/forecast']:assert f'href="{path}"' in page
 for path in ['/vendors','/users','/reports-v4']:assert f'href="{path}"' not in page and encoder.get(path).status_code==403

@pytest.mark.parametrize('data',[{'description':'Valid','quantity':'0'},{'description':'','quantity':'1'},{'description':'Valid','quantity':'bad'},{'description':'Valid','quantity':'1','inventory_id':'9999999'}])
def test_requisition_rejects_bad_data(app,data):
 encoder=role_client(app,'Encoder');data['_csrf']=get_csrf_token(encoder)
 assert encoder.post('/requisitions/create',data=data).status_code==400
