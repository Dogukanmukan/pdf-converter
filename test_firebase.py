import unittest
from app import app, db
import firebase_admin
from firebase_admin import auth
import os

class TestFirebase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.test_user_email = "test@example.com"
        self.test_user_password = "testpassword123"

    def tearDown(self):
        # Clean up test user if exists
        try:
            user = auth.get_user_by_email(self.test_user_email)
            auth.delete_user(user.uid)
        except:
            pass

    def test_register(self):
        # Test user registration
        response = self.client.post('/register', data={
            'email': self.test_user_email,
            'password': self.test_user_password
        })
        self.assertEqual(response.status_code, 302)  # Should redirect after successful registration

        # Verify user exists in Firebase
        user = auth.get_user_by_email(self.test_user_email)
        self.assertIsNotNone(user)

        # Verify user document exists in Firestore
        user_doc = db.collection('users').document(user.uid).get()
        self.assertTrue(user_doc.exists)

    def test_login(self):
        # Create a test user first
        user = auth.create_user(
            email=self.test_user_email,
            password=self.test_user_password
        )

        # Test login
        response = self.client.post('/login', data={
            'email': self.test_user_email,
            'password': self.test_user_password
        })
        self.assertEqual(response.status_code, 302)  # Should redirect after successful login

if __name__ == '__main__':
    unittest.main()
