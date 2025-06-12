import pytest
from app import app
import json
from datetime import datetime

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

def test_health_check(client):
    """Test that health check endpoint returns correct response."""
    rv = client.get('/health')
    assert rv.status_code == 200
    data = json.loads(rv.data)
    assert data['status'] == 'healthy'
    assert 'version' in data
    assert 'timestamp' in data
    assert isinstance(datetime.fromisoformat(data['timestamp']), datetime)
    assert 'checks' in data
    assert isinstance(data['checks'], dict)

def test_metrics_endpoint(client):
    """Test that metrics endpoint is accessible."""
    rv = client.get('/metrics')
    assert rv.status_code == 200

def test_invalid_url(client):
    """Test handling of invalid URLs."""
    data = {
        'instagram_url': 'not-a-url',
        'twitter_url': '',
        'linkedin_url': '',
        'facebook_url': '',
        'tiktok_url': ''
    }
    rv = client.post('/check_social', data=data)
    assert rv.status_code == 400

def test_analytics_page(client):
    """Test that analytics page loads correctly."""
    rv = client.get('/analytics')
    assert rv.status_code == 200

def test_dashboard_page(client):
    """Test that dashboard page loads correctly."""
    rv = client.get('/dashboard')
    assert rv.status_code == 200

def test_error_handling(client):
    """Test 404 error handling."""
    rv = client.get('/non-existent-page')
    assert rv.status_code == 404
