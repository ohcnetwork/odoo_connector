from odoo import http
from odoo.http import request
import base64


class UserAuthentication:

    @classmethod
    def get_authenticated_user(cls,auth_header):
        try:
            if not auth_header or not auth_header.startswith("Basic "):
                raise ValueError("Missing or invalid Authorization header")
            auth_decoded = base64.b64decode(auth_header.split(" ")[1]).decode("utf-8")
            username, password = auth_decoded.split(":", 1)
            credential = {'login': username, 'password': password, 'type': 'password'}
            session_data = request.session.authenticate(
                request.session.db, credential
            )
            if not session_data:
                raise ValueError("Invalid username or password")

            user_env = request.env(user=session_data["uid"], su=False)

            if not user_env.user.exists():
                raise ValueError("user not found")
            return user_env

        except Exception as e:
            raise Exception(f"Authentication failed: {str(e)}")