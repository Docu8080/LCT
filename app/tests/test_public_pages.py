"""Public routes preserve HTTP 404 and API error contracts."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import server

class PublicPageTests(unittest.TestCase):
    def test_entry_html_preserves_utf8_text(self):
        response=TestClient(server.app).get('/')
        for text in ['ФСП Таланты','возможности находят вас','Загружаем ФСП Таланты']:
            self.assertIn(text,response.text)

    def test_public_pages_and_missing_routes(self):
        client = TestClient(server.app)
        for path in ['/', '/terms', '/privacy', '/cookies', '/help', '/accessibility', '/login', '/register','/refunds','/consent','/operator','/deletion','/licenses']:
            response = client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn('text/html', response.headers['content-type'])
            self.assertIn('/static/pages.js', response.text)
        for path in ['/404', '/not-a-real-page', '/nested/missing']:
            response = client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertIn('/static/pages.js', response.text)
        response = client.get('/api/not-a-real-endpoint')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {'detail': 'Not Found'})

