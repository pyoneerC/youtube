import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home_page(client):
    """Test que la página principal carga correctamente."""
    rv = client.get('/')
    assert rv.status_code == 200

def test_check_social_page(client):
    """Test que la página de verificación social carga correctamente."""
    rv = client.get('/check_social')
    assert rv.status_code == 200

def test_check_social_post(client):
    """Test del formulario de verificación social."""
    data = {
        'instagram_url': 'https://instagram.com/test',
        'twitter_url': 'https://twitter.com/test',
        'linkedin_url': 'https://linkedin.com/in/test',
        'facebook_url': 'https://facebook.com/test',
        'tiktok_url': 'https://tiktok.com/@test'
    }
    rv = client.post('/check_social', data=data)
    assert rv.status_code == 200
